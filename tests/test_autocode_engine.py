"""Tests for the AutoCode engine — job runner with mocked LLM.

These tests exercise ``run_autocode_job()`` end-to-end against an
in-memory SQLite database with a mocked ``LLMClient``.  No real LLM
calls are made.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker

from bristlenose.llm.structured import AutoCodeBatchResult, AutoCodeTagAssignment
from bristlenose.server.autocode import BATCH_SIZE, run_autocode_job
from bristlenose.server.codebook import get_template
from bristlenose.server.db import Base
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProposedTag,
    Quote,
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

    def test_handles_llm_failure(self, project_with_garrett) -> None:
        """Per-batch LLM errors are handled gracefully — no proposals stored."""
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
        # Batch failures are per-batch — job still completes
        assert job.status == "completed"
        proposals = db.query(ProposedTag).all()
        assert len(proposals) == 0  # No proposals from a failed batch
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
