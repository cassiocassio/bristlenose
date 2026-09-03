"""Tests for the AutoCode engine — job runner with mocked LLM.

These tests exercise ``run_autocode_job()`` end-to-end against an
in-memory SQLite database with a mocked ``LLMClient``.  No real LLM
calls are made.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker

from bristlenose.llm.failure_classifier import LLMFailureKind
from bristlenose.llm.structured import AutoCodeBatchResult, AutoCodeTagAssignment
from bristlenose.server.autocode import (
    BATCH_SIZE,
    reapply_active_frameworks,
    reapply_to_new_quotes,
    run_autocode_job,
)
from bristlenose.server.codebook import get_template
from bristlenose.server.db import Base
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProjectFrameworkState,
    ProposedTag,
    Quote,
    QuoteTag,
    Session,
    TagDefinition,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite DB with all tables and return a session."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    yield session
    session.close()


@pytest.fixture()
def project_with_garrett(db_session: SASession):
    """Create a project with imported Garrett framework and sample quotes.

    Returns (project_id, framework_id, db_factory).
    """
    db = db_session

    # Create project
    project = Project(name="Test Project", slug="test", input_dir="/tmp/in", output_dir="/tmp/out")
    db.add(project)
    db.flush()

    # Import Garrett framework groups and tags
    template = get_template("garrett")
    assert template is not None

    for group_tmpl in template.groups:
        group = CodebookGroup(
            name=group_tmpl.name,
            subtitle=group_tmpl.subtitle,
            colour_set=group_tmpl.colour_set,
            framework_id="garrett",
        )
        db.add(group)
        db.flush()
        db.add(ProjectCodebookGroup(
            project_id=project.id, codebook_group_id=group.id
        ))
        for tag_tmpl in group_tmpl.tags:
            db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))

    # Create sample quotes
    for i in range(10):
        db.add(Quote(
            project_id=project.id,
            session_id="s1",
            participant_id="p1",
            start_timecode=float(i * 10),
            end_timecode=float(i * 10 + 5),
            text=f"Sample quote number {i} about the product",
            quote_type="screen_specific",
            topic_label="Dashboard",
            sentiment="frustration" if i % 2 == 0 else None,
        ))

    # Create the AutoCodeJob row (as the API endpoint would)
    job = AutoCodeJob(
        project_id=project.id,
        framework_id="garrett",
        status="pending",
    )
    db.add(job)
    db.commit()

    session_cls = sessionmaker(bind=db.get_bind())

    def db_factory() -> SASession:
        return session_cls()

    return project.id, "garrett", db_factory


def _mock_settings():
    """Create a mock BristlenoseSettings."""
    settings = MagicMock()
    settings.llm_provider = "anthropic"
    settings.llm_model = "claude-sonnet-4-20250514"
    settings.llm_max_tokens = 32768
    settings.llm_temperature = 0.1
    settings.llm_concurrency = 1
    settings.anthropic_api_key = "test-key"
    return settings


def _make_batch_result(
    n_quotes: int,
    tag_name: str = "user need",
    confidence: float = 0.85,
) -> AutoCodeBatchResult:
    """Create a mock LLM result that tags every quote with the same tag."""
    return AutoCodeBatchResult(
        assignments=[
            AutoCodeTagAssignment(
                quote_index=i,
                tag_name=tag_name,
                confidence=confidence,
                rationale=f"Rationale for quote {i}",
            )
            for i in range(n_quotes)
        ]
    )


def _patch_llm(mock_analyze, input_tokens=0, output_tokens=0):
    """Return a pair of patch context managers for LLMClient and LLMUsageTracker.

    Usage::

        with _patch_llm(my_mock_fn, 4000, 750):
            asyncio.run(run_autocode_job(...))
    """
    tracker = MagicMock()
    tracker.input_tokens = input_tokens
    tracker.output_tokens = output_tokens

    client = MagicMock()
    client.analyze = mock_analyze
    client.tracker = tracker

    class _Combined:
        """Context manager that patches LLMClient."""

        def __enter__(self):
            self._p1 = patch(
                "bristlenose.llm.client.LLMClient", return_value=client
            )
            self._p1.__enter__()
            return self

        def __exit__(self, *args):
            self._p1.__exit__(*args)

    return _Combined()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunAutoCodeJob:
    """Tests for the background job runner."""

    def test_completes_successfully(self, project_with_garrett) -> None:
        """Job runs to completion with mocked LLM."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = _make_batch_result(10, "user need", 0.85)

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        assert job is not None
        assert job.status == "completed"
        assert job.total_quotes == 10
        assert job.proposed_count == 10
        assert job.completed_at is not None
        db.close()

    def test_progress_update_failure_does_not_discard_proposals(
        self, project_with_garrett
    ) -> None:
        """A failed progress-counter write must never sink the batch's proposals.

        Regression for the AutoCode "0 of 0 proposals" bug: the incremental
        ``processed_quotes`` UPDATE hit SQLite's "database is locked" under
        concurrent writers; the exception propagated out of the batch, ``gather``
        treated the whole batch as failed, and a full LLM batch landed as zero
        proposals (26 Jul 2026 — 38 proposals returned, all lost). The progress
        write is now write-only + non-fatal, so the proposals survive it.
        """
        from sqlalchemy.orm import Query

        project_id, framework_id, db_factory = project_with_garrett
        mock_result = _make_batch_result(10, "user need", 0.85)

        real_update = Query.update

        def _boom_on_progress(self, values, *args, **kwargs):  # type: ignore[no-untyped-def]
            # Only the progress-counter UPDATE sets processed_quotes; make it fail
            # the way a locked DB would, and leave every other update untouched.
            if any("processed_quotes" in str(k) for k in values):
                raise Exception("database is locked")
            return real_update(self, values, *args, **kwargs)

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750), patch.object(
            Query, "update", _boom_on_progress
        ):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        proposals = db.query(ProposedTag).all()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        # The proposals survived the (simulated) locked progress write…
        assert len(proposals) == 10
        # …and the job completed with the real count, not a fake "0".
        assert job is not None
        assert job.status == "completed"
        assert job.proposed_count == 10
        db.close()

    def test_creates_proposed_tag_rows(self, project_with_garrett) -> None:
        """ProposedTag rows are created for each assignment."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = _make_batch_result(10, "user need", 0.85)

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        proposals = db.query(ProposedTag).all()
        assert len(proposals) == 10
        for p in proposals:
            assert p.confidence == 0.85
            assert p.status == "pending"
            assert "Rationale for quote" in p.rationale
        db.close()

    def test_stores_confidence_and_rationale(self, project_with_garrett) -> None:
        """ProposedTag has correct confidence and rationale from LLM."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=0,
                    tag_name="visual design",
                    confidence=0.92,
                    rationale="Clear reference to colours and imagery",
                ),
                AutoCodeTagAssignment(
                    quote_index=1,
                    tag_name="user need",
                    confidence=0.18,
                    rationale="Weak match — mostly navigational",
                ),
            ]
        )

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        proposals = db.query(ProposedTag).order_by(ProposedTag.confidence.desc()).all()
        assert len(proposals) == 2
        assert proposals[0].confidence == 0.92
        assert "colours" in proposals[0].rationale
        assert proposals[1].confidence == 0.18
        db.close()

    def test_every_batch_failing_is_a_failed_job_not_a_completed_one(
        self, project_with_garrett
    ) -> None:
        """All batches dead ⇒ ``failed``, and the exception gets classified.

        This test used to assert ``completed``, on the reasoning that batch
        failures are per-batch and the job survives them. True of *a* batch;
        false of all of them. ``gather(return_exceptions=True)`` means nothing
        reaches the outer handler, so the job recorded a success with
        ``processed_quotes=0`` and no ``failure_kind`` — and the surfaces read
        that as a partial, offering "Tagged 0 of 33 quotes … View Report"
        against an empty report.
        """
        project_id, framework_id, db_factory = project_with_garrett

        with _patch_llm(AsyncMock(side_effect=RuntimeError("LLM API error"))):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        assert job is not None
        assert job.status == "failed"
        assert job.processed_quotes == 0
        # Unrecognisable to the classifier, but named rather than left blank —
        # "" is what the UI reads as "never classified".
        assert job.failure_kind == "unknown"
        proposals = db.query(ProposedTag).all()
        assert len(proposals) == 0
        db.close()

    def test_out_of_credit_batches_are_classified_not_left_blank(
        self, project_with_garrett
    ) -> None:
        """The screenshot case: an exhausted account, named as one.

        Anthropic serves out-of-credit as a **400**, so nothing short of the
        classifier can tell it from an ordinary bad request — and the sentence
        the researcher needs ("your account is out of credit", an ERROR) is
        chosen from ``failure_kind`` alone.
        """
        project_id, framework_id, db_factory = project_with_garrett

        boom = RuntimeError(
            "Error code: 400 - {'type': 'error', 'error': {'type': "
            "'invalid_request_error', 'message': 'Your credit balance is too "
            "low to access the Anthropic API.'}}"
        )
        with _patch_llm(AsyncMock(side_effect=boom)):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        assert job is not None
        assert job.status == "failed"
        assert job.failure_kind == LLMFailureKind.OUT_OF_CREDIT.value
        db.close()

    def test_unrecognized_tag_name_skipped(self, project_with_garrett) -> None:
        """Unknown tag from LLM is skipped — no ProposedTag created."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=0,
                    tag_name="nonexistent tag",
                    confidence=0.9,
                    rationale="This tag doesn't exist",
                ),
                AutoCodeTagAssignment(
                    quote_index=1,
                    tag_name="user need",  # This one exists
                    confidence=0.85,
                    rationale="Valid tag",
                ),
            ]
        )

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        proposals = db.query(ProposedTag).all()
        # Only "user need" should have created a proposal
        assert len(proposals) == 1
        db.close()

    def test_invalid_quote_index_skipped(self, project_with_garrett) -> None:
        """Out-of-range quote index from LLM is skipped gracefully."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=99,  # Out of range
                    tag_name="user need",
                    confidence=0.9,
                    rationale="Bad index",
                ),
                AutoCodeTagAssignment(
                    quote_index=0,  # Valid
                    tag_name="user need",
                    confidence=0.85,
                    rationale="Valid index",
                ),
            ]
        )

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        proposals = db.query(ProposedTag).all()
        assert len(proposals) == 1
        db.close()

    def test_token_usage_tracked(self, project_with_garrett) -> None:
        """Job row has input_tokens and output_tokens after completion."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = _make_batch_result(10, "user need", 0.85)

        with _patch_llm(AsyncMock(return_value=mock_result), 4200, 800):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        assert job is not None
        assert job.input_tokens == 4200
        assert job.output_tokens == 800
        assert job.llm_provider == "anthropic"
        assert "claude" in job.llm_model
        db.close()

    def test_empty_project_no_quotes(self, db_session: SASession) -> None:
        """Job with 0 quotes completes immediately (no LLM calls)."""
        db = db_session
        project = Project(name="Empty", slug="empty", input_dir="/tmp", output_dir="/tmp")
        db.add(project)
        db.flush()

        # Import Garrett (no quotes)
        template = get_template("garrett")
        assert template is not None
        for group_tmpl in template.groups:
            group = CodebookGroup(
                name=group_tmpl.name, subtitle=group_tmpl.subtitle,
                colour_set=group_tmpl.colour_set, framework_id="garrett",
            )
            db.add(group)
            db.flush()
            for tag_tmpl in group_tmpl.tags:
                db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))

        job = AutoCodeJob(project_id=project.id, framework_id="garrett", status="pending")
        db.add(job)
        db.commit()

        session_cls = sessionmaker(bind=db.get_bind())

        mock_analyze = AsyncMock()
        with _patch_llm(mock_analyze):
            asyncio.run(
                run_autocode_job(session_cls, project.id, "garrett", _mock_settings())
            )

        db2 = session_cls()
        job = db2.query(AutoCodeJob).first()
        assert job is not None
        assert job.status == "completed"
        assert job.total_quotes == 0
        # LLM should not have been called
        mock_analyze.assert_not_called()
        db2.close()

    def test_missing_template_fails(self, db_session: SASession) -> None:
        """Job with nonexistent framework_id fails gracefully."""
        db = db_session
        project = Project(
            name="Bad", slug="bad", input_dir="/tmp", output_dir="/tmp"
        )
        db.add(project)
        db.flush()

        job = AutoCodeJob(
            project_id=project.id, framework_id="nonexistent", status="pending"
        )
        db.add(job)
        db.commit()

        session_cls = sessionmaker(bind=db.get_bind())

        with _patch_llm(AsyncMock()):
            asyncio.run(
                run_autocode_job(session_cls, project.id, "nonexistent", _mock_settings())
            )

        db2 = session_cls()
        job = db2.query(AutoCodeJob).first()
        assert job is not None
        assert job.status == "failed"
        assert "not found" in job.error_message.lower()
        db2.close()

    def test_job_sets_running_then_completed(self, project_with_garrett) -> None:
        """Job transitions from pending → running → completed."""
        project_id, framework_id, db_factory = project_with_garrett

        # Track status transitions by capturing the status when analyze is called
        statuses_during_llm: list[str] = []

        async def tracking_analyze(system_prompt, user_prompt, response_model, **kw):
            db = db_factory()
            job = db.query(AutoCodeJob).filter_by(
                project_id=project_id, framework_id=framework_id
            ).first()
            if job:
                statuses_during_llm.append(job.status)
            db.close()
            return _make_batch_result(10, "user need", 0.85)

        with _patch_llm(AsyncMock(side_effect=tracking_analyze), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        # During LLM call, job should have been "running"
        assert len(statuses_during_llm) == 1
        assert statuses_during_llm[0] == "running"

        # After completion
        db = db_factory()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        assert job is not None
        assert job.status == "completed"
        db.close()

    def test_processed_quotes_count(self, project_with_garrett) -> None:
        """Job tracks processed_quotes count correctly."""
        project_id, framework_id, db_factory = project_with_garrett

        mock_result = _make_batch_result(10, "user need", 0.85)

        with _patch_llm(AsyncMock(return_value=mock_result), 4000, 750):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )

        db = db_factory()
        job = db.query(AutoCodeJob).filter_by(
            project_id=project_id, framework_id=framework_id
        ).first()
        assert job is not None
        assert job.processed_quotes == 10
        db.close()

    def test_progress_visible_mid_job(self, db_session: SASession) -> None:
        """Per-batch progress commits are visible to separate DB sessions mid-job.

        This is the core test for the progress-reporting fix: a polling query
        (like GET /status) must see non-zero processed_quotes before the job
        finishes.
        """
        db = db_session
        project = Project(
            name="Progress", slug="progress", input_dir="/tmp", output_dir="/tmp"
        )
        db.add(project)
        db.flush()

        template = get_template("garrett")
        assert template is not None
        for group_tmpl in template.groups:
            group = CodebookGroup(
                name=group_tmpl.name, subtitle=group_tmpl.subtitle,
                colour_set=group_tmpl.colour_set, framework_id="garrett",
            )
            db.add(group)
            db.flush()
            for tag_tmpl in group_tmpl.tags:
                db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))

        # 50 quotes = 2 batches of 25
        for i in range(50):
            db.add(Quote(
                project_id=project.id, session_id="s1",
                participant_id="p1", start_timecode=float(i * 10),
                end_timecode=float(i * 10 + 5),
                text=f"Quote {i}", quote_type="screen_specific",
            ))

        job = AutoCodeJob(
            project_id=project.id, framework_id="garrett", status="pending"
        )
        db.add(job)
        db.commit()

        session_cls = sessionmaker(bind=db.get_bind())

        # Capture progress snapshots from a separate DB session after each batch
        progress_snapshots: list[int] = []
        call_count = 0

        async def tracking_analyze(system_prompt, user_prompt, response_model, **kw):
            nonlocal call_count
            import re
            n = len(re.findall(r"^\d+\. \[", user_prompt, re.MULTILINE))
            call_count += 1
            result = _make_batch_result(n, "user need", 0.8)
            # After the first batch, yield control so the progress commit runs,
            # then read progress from a fresh session (simulating a poll).
            if call_count == 2:
                await asyncio.sleep(0)  # Yield to event loop
                poll_db = session_cls()
                poll_job = poll_db.query(AutoCodeJob).filter_by(
                    project_id=project.id, framework_id="garrett"
                ).first()
                if poll_job:
                    progress_snapshots.append(poll_job.processed_quotes)
                poll_db.close()
            return result

        settings = _mock_settings()
        settings.llm_concurrency = 1  # Sequential batches for deterministic ordering

        with _patch_llm(AsyncMock(side_effect=tracking_analyze)):
            asyncio.run(
                run_autocode_job(session_cls, project.id, "garrett", settings)
            )

        # The snapshot taken during the second batch should show the first
        # batch's 25 quotes already committed.
        assert len(progress_snapshots) == 1
        assert progress_snapshots[0] == 25


class TestBatching:
    """Tests for the batching behaviour within the job runner."""

    def test_batches_of_25(self, db_session: SASession) -> None:
        """100 quotes produce 4 LLM calls (4 batches of 25)."""
        db = db_session
        project = Project(name="Large", slug="large", input_dir="/tmp", output_dir="/tmp")
        db.add(project)
        db.flush()

        template = get_template("garrett")
        assert template is not None
        for group_tmpl in template.groups:
            group = CodebookGroup(
                name=group_tmpl.name, subtitle=group_tmpl.subtitle,
                colour_set=group_tmpl.colour_set, framework_id="garrett",
            )
            db.add(group)
            db.flush()
            for tag_tmpl in group_tmpl.tags:
                db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))

        # Add 100 quotes
        for i in range(100):
            db.add(Quote(
                project_id=project.id, session_id=f"s{i // 20 + 1}",
                participant_id="p1", start_timecode=float(i * 10),
                end_timecode=float(i * 10 + 5),
                text=f"Quote {i}", quote_type="screen_specific",
            ))

        job = AutoCodeJob(project_id=project.id, framework_id="garrett", status="pending")
        db.add(job)
        db.commit()

        session_cls = sessionmaker(bind=db.get_bind())

        # Mock LLM to return a result matching the batch size dynamically
        call_sizes: list[int] = []

        async def mock_analyze(system_prompt, user_prompt, response_model, **kwargs):
            import re
            n_quotes = len(re.findall(r"^\d+\. \[", user_prompt, re.MULTILINE))
            call_sizes.append(n_quotes)
            return _make_batch_result(n_quotes, "user need", 0.8)

        with _patch_llm(AsyncMock(side_effect=mock_analyze)):
            asyncio.run(
                run_autocode_job(session_cls, project.id, "garrett", _mock_settings())
            )

        assert len(call_sizes) == 4  # 100 / 25 = 4 batches
        assert all(s == BATCH_SIZE for s in call_sizes)

    def test_a_genuine_partial_stays_completed_but_carries_the_reason(
        self, db_session: SASession
    ) -> None:
        """Some batches landed ⇒ still ``completed``; it has usable proposals.

        The distinction from the all-failed case is the whole point: a partial
        has something behind the report link, so it keeps it. What it lacked
        was any record of *why* the rest are missing — ``failure_kind`` is now
        set on a completed job too, so a surface can say "rate limited" instead
        of leaving the shortfall to be guessed at.
        """
        db = db_session
        project = Project(name="Half", slug="half", input_dir="/tmp", output_dir="/tmp")
        db.add(project)
        db.flush()

        template = get_template("garrett")
        assert template is not None
        for group_tmpl in template.groups:
            group = CodebookGroup(
                name=group_tmpl.name, subtitle=group_tmpl.subtitle,
                colour_set=group_tmpl.colour_set, framework_id="garrett",
            )
            db.add(group)
            db.flush()
            for tag_tmpl in group_tmpl.tags:
                db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))

        # Two batches: 25 + 5.
        for i in range(30):
            db.add(Quote(
                project_id=project.id, session_id="s1", participant_id="p1",
                start_timecode=float(i * 10), end_timecode=float(i * 10 + 5),
                text=f"Quote {i}", quote_type="screen_specific",
            ))

        db.add(AutoCodeJob(project_id=project.id, framework_id="garrett", status="pending"))
        db.commit()
        session_cls = sessionmaker(bind=db.get_bind())

        # First call succeeds, every later one is rate-limited.
        calls = {"n": 0}

        async def flaky(system_prompt, user_prompt, response_model, **kwargs):
            import re
            n_quotes = len(re.findall(r"^\d+\. \[", user_prompt, re.MULTILINE))
            calls["n"] += 1
            if calls["n"] == 1:
                return _make_batch_result(n_quotes, "user need", 0.8)
            raise RuntimeError(
                "Error code: 429 - {'type': 'error', 'error': {'type': "
                "'rate_limit_error', 'message': 'rate limit exceeded'}}"
            )

        with _patch_llm(AsyncMock(side_effect=flaky)):
            asyncio.run(
                run_autocode_job(session_cls, project.id, "garrett", _mock_settings())
            )

        job = db.query(AutoCodeJob).filter_by(
            project_id=project.id, framework_id="garrett"
        ).first()
        assert job is not None
        assert job.status == "completed"
        assert 0 < job.processed_quotes < 30
        assert job.proposed_count > 0
        assert job.failure_kind == LLMFailureKind.RATE_LIMITED.value

    def test_partial_last_batch(self, db_session: SASession) -> None:
        """27 quotes produce 2 LLM calls (25 + 2)."""
        db = db_session
        project = Project(
            name="Partial", slug="partial", input_dir="/tmp", output_dir="/tmp"
        )
        db.add(project)
        db.flush()

        template = get_template("garrett")
        assert template is not None
        for group_tmpl in template.groups:
            group = CodebookGroup(
                name=group_tmpl.name, subtitle=group_tmpl.subtitle,
                colour_set=group_tmpl.colour_set, framework_id="garrett",
            )
            db.add(group)
            db.flush()
            for tag_tmpl in group_tmpl.tags:
                db.add(TagDefinition(name=tag_tmpl.name, codebook_group_id=group.id))

        for i in range(27):
            db.add(Quote(
                project_id=project.id, session_id="s1",
                participant_id="p1", start_timecode=float(i * 10),
                end_timecode=float(i * 10 + 5),
                text=f"Quote {i}", quote_type="screen_specific",
            ))

        job = AutoCodeJob(project_id=project.id, framework_id="garrett", status="pending")
        db.add(job)
        db.commit()

        session_cls = sessionmaker(bind=db.get_bind())
        call_count = 0

        async def mock_analyze(system_prompt, user_prompt, response_model, **kwargs):
            nonlocal call_count
            import re
            n_quotes = len(re.findall(r"^\d+\. \[", user_prompt, re.MULTILINE))
            call_count += 1
            return _make_batch_result(n_quotes, "user need", 0.8)

        with _patch_llm(AsyncMock(side_effect=mock_analyze)):
            asyncio.run(
                run_autocode_job(session_cls, project.id, "garrett", _mock_settings())
            )

        assert call_count == 2  # 25 + 2

        db2 = session_cls()
        job = db2.query(AutoCodeJob).first()
        assert job is not None
        assert job.proposed_count == 27
        db2.close()


class TestReapplyToNewQuotes:
    """Delta re-apply — new quotes coded at the stored cutoff; existing quotes
    and human tags left alone."""

    def _apply_original(
        self, project_id, framework_id, db_factory, threshold=0.7
    ) -> None:
        """Run the original autocode over the 10 fixture quotes, then stamp the
        stored accept cutoff (as accept-all would)."""
        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(10, "user need", 0.85))
        ):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            job.applied_upper_threshold = threshold
            # Pin the apply time to a fixed past date so the "new session"
            # comparison is deterministic (the new session below imports "after").
            job.completed_at = datetime(2020, 1, 1)
            db.commit()
        finally:
            db.close()

    def _add_quotes(self, db_factory, project_id, n) -> None:
        """Add a genuinely-new session (imported after the apply) with n quotes.

        first_imported_at = 2021, later than the apply's pinned 2020 completed_at,
        so the session-recency delta treats these quotes as new.
        """
        db = db_factory()
        try:
            db.add(
                Session(
                    project_id=project_id,
                    session_id="s2",
                    session_number=2,
                    first_imported_at=datetime(2021, 1, 1),
                )
            )
            for i in range(n):
                db.add(
                    Quote(
                        project_id=project_id,
                        session_id="s2",
                        participant_id="p2",
                        start_timecode=float(1000 + i * 10),
                        end_timecode=float(1000 + i * 10 + 5),
                        text=f"New wave quote {i}",
                        quote_type="screen_specific",
                        topic_label="Dashboard",
                    )
                )
            db.commit()
        finally:
            db.close()

    def test_codes_only_new_quotes_at_stored_cutoff(
        self, project_with_garrett
    ) -> None:
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)

        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(3, "user need", 0.85))
        ):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings()
                )
            )

        assert accepted == 3
        db = db_factory()
        try:
            # Exactly the 3 new quotes get QuoteTags — the original 10 were only
            # proposed, never accepted in this test, so still 0.
            assert db.query(QuoteTag).count() == 3
            assert all(qt.source == "autocode" for qt in db.query(QuoteTag).all())
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert job.total_quotes == 13  # 10 original + 3 new
        finally:
            db.close()

    def test_untagged_existing_quotes_not_recoded(
        self, project_with_garrett
    ) -> None:
        """Regression: existing quotes the LLM never tagged (no proposal row) must
        NOT be re-coded — the delta is session-recency, not 'has-no-proposal'.
        With the old heuristic these 6 quotes would be re-sent and re-tagged."""
        project_id, framework_id, db_factory = project_with_garrett
        # Original apply tags only 4 of the 10 quotes → 6 existing quotes have no
        # proposal row at all.
        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(4, "user need", 0.85))
        ):
            asyncio.run(
                run_autocode_job(db_factory, project_id, framework_id, _mock_settings())
            )
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            job.applied_upper_threshold = 0.7
            job.completed_at = datetime(2020, 1, 1)
            db.commit()
        finally:
            db.close()
        self._add_quotes(db_factory, project_id, 2)  # a new session, 2 quotes

        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(2, "user need", 0.85))
        ):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings()
                )
            )

        # Only the 2 new-session quotes — never the 6 untagged existing ones.
        assert accepted == 2

    def test_duplicate_quote_assignments_deduped_not_perpetual_failure(
        self, project_with_garrett
    ) -> None:
        """Regression: an LLM that returns two assignments for one quote must not
        violate the (job_id, quote_id) constraint and roll the whole re-apply back
        to a silent 0 — which would re-select and re-fail the same new sessions on
        every subsequent run, forever. Dedup keeps one proposal per quote."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 2)  # new session, 2 quotes

        # Three assignments for two quotes: quote_index 0 twice (double-tag) + 1.
        dup = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=0, tag_name="user need", confidence=0.9, rationale="a"
                ),
                AutoCodeTagAssignment(
                    quote_index=0, tag_name="user need", confidence=0.8, rationale="b"
                ),
                AutoCodeTagAssignment(
                    quote_index=1, tag_name="user need", confidence=0.85, rationale="c"
                ),
            ]
        )
        with _patch_llm(AsyncMock(return_value=dup)):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings()
                )
            )

        # Both new quotes coded exactly once — no IntegrityError, no silent 0.
        assert accepted == 2
        db = db_factory()
        try:
            assert db.query(QuoteTag).count() == 2
            # Watermark advanced off the pinned sentinel → a re-run is a clean
            # no-op, not a perpetual re-fail.
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert job.completed_at != datetime(2020, 1, 1)
        finally:
            db.close()

    def test_below_cutoff_new_quotes_not_accepted(
        self, project_with_garrett
    ) -> None:
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 2)

        # LLM tags the new quotes at 0.5 — below the 0.7 cutoff → denied.
        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(2, "user need", 0.5))
        ):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings()
                )
            )

        assert accepted == 0
        db = db_factory()
        try:
            assert db.query(QuoteTag).count() == 0
        finally:
            db.close()

    def test_no_new_quotes_is_noop(self, project_with_garrett) -> None:
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory)
        mock_analyze = AsyncMock()
        with _patch_llm(mock_analyze):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings()
                )
            )
        assert accepted == 0
        mock_analyze.assert_not_called()

    def _mark_running(self, db_factory, project_id, framework_id) -> None:
        """Simulate the route setting the job 'running' before the catch-up runs."""
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            job.status = "running"
            db.commit()
        finally:
            db.close()

    def test_track_status_restores_completed_after_coding(
        self, project_with_garrett
    ) -> None:
        """track_status: a 'running' job (set by the route) is restored to
        'completed' once the delta is coded — so the chip's poll resolves."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        self._mark_running(db_factory, project_id, framework_id)

        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(3, "user need", 0.85))
        ):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings(),
                    track_status=True,
                )
            )
        assert accepted == 3
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert job.status == "completed"
        finally:
            db.close()

    def test_track_status_restores_completed_on_no_delta(
        self, project_with_garrett
    ) -> None:
        """track_status: even when there's nothing to code, a 'running' job must not
        be left spinning — the finally restores 'completed'."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        # No new sessions → the delta is empty.
        self._mark_running(db_factory, project_id, framework_id)

        mock_analyze = AsyncMock()
        with _patch_llm(mock_analyze):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings(),
                    track_status=True,
                )
            )
        assert accepted == 0
        mock_analyze.assert_not_called()
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert job.status == "completed"  # not left "running"
        finally:
            db.close()

    def test_track_status_sets_failed_on_error(
        self, project_with_garrett, monkeypatch
    ) -> None:
        """track_status: an error mid-catch-up marks the job "failed" — and the
        finally must NOT then upgrade it back to "completed" (a false success on
        lost work)."""
        import bristlenose.server.autocode as ac

        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        self._mark_running(db_factory, project_id, framework_id)

        def _boom(*_a, **_k):
            raise RuntimeError("taxonomy build blew up")

        monkeypatch.setattr(ac, "build_tag_taxonomy", _boom)
        with _patch_llm(AsyncMock()):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings(),
                    track_status=True,
                )
            )
        assert accepted == 0
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert job.status == "failed"  # NOT falsely "completed"
        finally:
            db.close()

    def test_reapply_active_frameworks_covers_applied(
        self, project_with_garrett
    ) -> None:
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(3, "user need", 0.85))
        ):
            results = asyncio.run(
                reapply_active_frameworks(db_factory, project_id, _mock_settings())
            )
        assert results == {"garrett": 3}

    def test_reapply_active_frameworks_none_applied(
        self, project_with_garrett
    ) -> None:
        # Fixture job is 'pending' — no completed jobs → nothing to re-apply.
        project_id, framework_id, db_factory = project_with_garrett
        results = asyncio.run(
            reapply_active_frameworks(db_factory, project_id, _mock_settings())
        )
        assert results == {}

    def test_reapply_active_frameworks_skips_removed(
        self, project_with_garrett
    ) -> None:
        """Applied but since REMOVED (group links dropped) → not re-applied.
        Remove stops maintenance; the gate is ever-applied ∩ linked ∩ enabled."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        # Uninstall: drop every ProjectCodebookGroup link for this project.
        db = db_factory()
        try:
            db.query(ProjectCodebookGroup).filter_by(
                project_id=project_id
            ).delete()
            db.commit()
        finally:
            db.close()

        mock_analyze = AsyncMock()
        with _patch_llm(mock_analyze):
            results = asyncio.run(
                reapply_active_frameworks(db_factory, project_id, _mock_settings())
            )

        assert results == {}  # removed framework skipped, not coded
        mock_analyze.assert_not_called()
        db = db_factory()
        try:
            assert db.query(QuoteTag).count() == 0
        finally:
            db.close()

    def test_reapply_active_frameworks_skips_disabled(
        self, project_with_garrett
    ) -> None:
        """Applied + still linked, but DISABLED (enabled=False) → not re-applied.
        "Off means off" (design-codebook-state-model.md §8): a disabled codebook
        stops maintaining new sessions, so the LLM is never called and the new
        quotes stay uncoded until re-enable fires a catch-up."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        # Turn the codebook OFF for this project.
        db = db_factory()
        try:
            db.add(
                ProjectFrameworkState(
                    project_id=project_id, framework_id=framework_id, enabled=False
                )
            )
            db.commit()
        finally:
            db.close()

        mock_analyze = AsyncMock()
        with _patch_llm(mock_analyze):
            results = asyncio.run(
                reapply_active_frameworks(db_factory, project_id, _mock_settings())
            )

        assert results == {}  # disabled framework skipped, not coded
        mock_analyze.assert_not_called()
        db = db_factory()
        try:
            assert db.query(QuoteTag).count() == 0
        finally:
            db.close()

    def test_reapply_active_frameworks_covers_explicitly_enabled(
        self, project_with_garrett
    ) -> None:
        """An explicit enabled=True row behaves exactly like the default (no row):
        the framework is maintained. Guards against the gate accidentally requiring
        a row, or treating any row as 'off'."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        db = db_factory()
        try:
            db.add(
                ProjectFrameworkState(
                    project_id=project_id, framework_id=framework_id, enabled=True
                )
            )
            db.commit()
        finally:
            db.close()

        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(3, "user need", 0.85))
        ):
            results = asyncio.run(
                reapply_active_frameworks(db_factory, project_id, _mock_settings())
            )

        assert results == {"garrett": 3}

    def test_reapply_active_frameworks_maintains_stuck_running_job(
        self, project_with_garrett
    ) -> None:
        """Crash-recovery regression: a job left "running" (e.g. a crash during an
        on-enable catch-up, before its finally restored "completed") must STILL be
        maintained — the gate is completed_at, not status="completed". Otherwise the
        framework would be silently dropped from all future coding forever."""
        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)
        # Simulate the crashed catch-up: healthy job, completed_at set, but stuck
        # at "running" because the finally never ran.
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            job.status = "running"
            db.commit()
        finally:
            db.close()

        with _patch_llm(
            AsyncMock(return_value=_make_batch_result(3, "user need", 0.85))
        ):
            results = asyncio.run(
                reapply_active_frameworks(db_factory, project_id, _mock_settings())
            )
        # Maintained despite the stuck status — the new sessions get coded.
        assert results == {"garrett": 3}

    def test_never_applied_is_noop(self, project_with_garrett) -> None:
        """No completed job (fixture job is 'pending') → returns 0, no LLM call."""
        project_id, framework_id, db_factory = project_with_garrett
        self._add_quotes(db_factory, project_id, 2)
        mock_analyze = AsyncMock()
        with _patch_llm(mock_analyze):
            accepted = asyncio.run(
                reapply_to_new_quotes(
                    db_factory, project_id, framework_id, _mock_settings()
                )
            )
        assert accepted == 0
        mock_analyze.assert_not_called()


class TestStartCatchUps:
    """`_start_catch_ups` is the delta gate the on-enable route runs synchronously:
    it marks a job 'running' (for the chip) only when there's a real catch-up."""

    _apply_original = TestReapplyToNewQuotes._apply_original
    _add_quotes = TestReapplyToNewQuotes._add_quotes

    def test_offers_and_marks_running_when_new_sessions(
        self, project_with_garrett
    ) -> None:
        from bristlenose.server.routes.data import _start_catch_ups

        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        self._add_quotes(db_factory, project_id, 3)  # new session after the apply

        db = db_factory()
        try:
            started = _start_catch_ups(db, project_id, [framework_id])
        finally:
            db.close()
        assert started == [framework_id]

        # The job is flipped to "running" so the chip's first poll catches it.
        db = db_factory()
        try:
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert job.status == "running"
        finally:
            db.close()

    def test_no_catch_up_when_no_new_sessions(
        self, project_with_garrett
    ) -> None:
        from bristlenose.server.routes.data import _start_catch_ups

        project_id, framework_id, db_factory = project_with_garrett
        self._apply_original(project_id, framework_id, db_factory, threshold=0.7)
        # No _add_quotes → no session imported after the apply watermark.

        db = db_factory()
        try:
            started = _start_catch_ups(db, project_id, [framework_id])
            job = (
                db.query(AutoCodeJob)
                .filter_by(project_id=project_id, framework_id=framework_id)
                .one()
            )
            assert started == []
            assert job.status == "completed"  # untouched
        finally:
            db.close()

    def test_no_catch_up_when_never_applied(
        self, project_with_garrett
    ) -> None:
        from bristlenose.server.routes.data import _start_catch_ups

        # Fixture job is 'pending' (completed_at is None) → never applied.
        project_id, framework_id, db_factory = project_with_garrett
        self._add_quotes(db_factory, project_id, 3)
        db = db_factory()
        try:
            assert _start_catch_ups(db, project_id, [framework_id]) == []
        finally:
            db.close()


class TestReconcileOrphanedJobs:
    """Startup reconciliation of AutoCodeJob rows stranded by a crash.

    No job survives a serve restart, so any 'running'/'pending' row at boot was
    orphaned — its finally never ran, so the persisted status is a UI-visible lie.
    """

    def _make_job(
        self, db, project_id, framework_id, status, completed_at
    ):
        from bristlenose.server.models import AutoCodeJob

        job = AutoCodeJob(
            project_id=project_id,
            framework_id=framework_id,
            status=status,
            completed_at=completed_at,
        )
        db.add(job)
        db.commit()
        return job

    def test_initial_apply_orphan_becomes_failed(self, db_session) -> None:
        """A crashed initial apply (running, never completed) → failed + message."""
        from bristlenose.server.autocode import reconcile_orphaned_jobs
        from bristlenose.server.models import AutoCodeJob, Project

        project = Project(
            name="P", slug="p", input_dir="/tmp/in", output_dir="/tmp/out"
        )
        db_session.add(project)
        db_session.flush()
        job = self._make_job(
            db_session, project.id, "garrett", "running", completed_at=None
        )

        changed = reconcile_orphaned_jobs(db_session)

        assert changed == 1
        db_session.refresh(job)
        assert job.status == "failed"
        assert job.error_message  # non-empty, chip/UI can show it
        # Sanity: still one job, not deleted.
        assert db_session.query(AutoCodeJob).count() == 1

    def test_pending_orphan_becomes_failed(self, db_session) -> None:
        """A pending job that never started (task GC'd before run) → failed."""
        from bristlenose.server.autocode import reconcile_orphaned_jobs
        from bristlenose.server.models import Project

        project = Project(
            name="P", slug="p", input_dir="/tmp/in", output_dir="/tmp/out"
        )
        db_session.add(project)
        db_session.flush()
        job = self._make_job(
            db_session, project.id, "garrett", "pending", completed_at=None
        )

        assert reconcile_orphaned_jobs(db_session) == 1
        db_session.refresh(job)
        assert job.status == "failed"

    def test_catch_up_orphan_restored_to_completed(self, db_session) -> None:
        """A running job that HAD completed (catch-up flip crashed) → completed.

        completed_at is set, so the initial apply finished — the data-loss half
        is already safe (ca944a0a); here we restore the status so the UI stops
        showing 'running' without misreporting real applied work as 'failed'.
        """
        from datetime import datetime, timezone

        from bristlenose.server.autocode import reconcile_orphaned_jobs
        from bristlenose.server.models import Project

        project = Project(
            name="P", slug="p", input_dir="/tmp/in", output_dir="/tmp/out"
        )
        db_session.add(project)
        db_session.flush()
        job = self._make_job(
            db_session,
            project.id,
            "garrett",
            "running",
            completed_at=datetime.now(timezone.utc),
        )

        assert reconcile_orphaned_jobs(db_session) == 1
        db_session.refresh(job)
        assert job.status == "completed"
        assert job.error_message == ""  # not misreported as a failure

    def test_terminal_jobs_left_alone(self, db_session) -> None:
        """completed / failed / cancelled jobs are never touched."""
        from datetime import datetime, timezone

        from bristlenose.server.autocode import reconcile_orphaned_jobs
        from bristlenose.server.models import Project

        project = Project(
            name="P", slug="p", input_dir="/tmp/in", output_dir="/tmp/out"
        )
        db_session.add(project)
        db_session.flush()
        now = datetime.now(timezone.utc)
        completed = self._make_job(
            db_session, project.id, "garrett", "completed", completed_at=now
        )
        failed = self._make_job(
            db_session, project.id, "norman", "failed", completed_at=now
        )
        cancelled = self._make_job(
            db_session, project.id, "uxr", "cancelled", completed_at=now
        )

        assert reconcile_orphaned_jobs(db_session) == 0
        for job, expected in (
            (completed, "completed"),
            (failed, "failed"),
            (cancelled, "cancelled"),
        ):
            db_session.refresh(job)
            assert job.status == expected

    def test_project_scoping(self, db_session) -> None:
        """An explicit project_id scopes the sweep to that project."""
        from bristlenose.server.autocode import reconcile_orphaned_jobs
        from bristlenose.server.models import Project

        p1 = Project(name="A", slug="a", input_dir="/tmp/a", output_dir="/tmp/oa")
        p2 = Project(name="B", slug="b", input_dir="/tmp/b", output_dir="/tmp/ob")
        db_session.add_all([p1, p2])
        db_session.flush()
        j1 = self._make_job(
            db_session, p1.id, "garrett", "running", completed_at=None
        )
        j2 = self._make_job(
            db_session, p2.id, "garrett", "running", completed_at=None
        )

        assert reconcile_orphaned_jobs(db_session, project_id=p1.id) == 1
        db_session.refresh(j1)
        db_session.refresh(j2)
        assert j1.status == "failed"
        assert j2.status == "running"  # other project untouched
