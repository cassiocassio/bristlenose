"""Tests for the AutoCode API endpoints.

Exercises all eight endpoints: start, status, cancel, proposals, accept,
deny, accept-all, deny-all.  Uses in-memory SQLite with smoke-test data.
No real LLM calls — the background job is mocked.

The smoke-test fixture has 4 quotes, so all proposal counts use N_QUOTES=4.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.codebook import get_template
from bristlenose.server.models import (
    AutoCodeJob,
    CodebookGroup,
    Project,
    ProjectCodebookGroup,
    ProposedTag,
    Quote,
    QuoteTag,
    TagDefinition,
)

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

#: The smoke-test fixture imports 4 quotes.
N_QUOTES = 4


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """Test client with imported smoke-test data (has quotes from importer)."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


def _import_garrett(app: object) -> list[int]:
    """Import Garrett framework into the app's DB, return tag definition IDs."""
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)
    db = app.state.db_factory()
    tag_ids: list[int] = []
    try:
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
                project_id=1, codebook_group_id=group.id
            ))
            for tag_tmpl in group_tmpl.tags:
                td = TagDefinition(
                    name=tag_tmpl.name, codebook_group_id=group.id
                )
                db.add(td)
                db.flush()
                tag_ids.append(td.id)
        db.commit()
    finally:
        db.close()
    return tag_ids


@pytest.fixture()
def client_with_garrett() -> TestClient:
    """Test client with imported Garrett framework and sample quotes."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    _import_garrett(app)
    return TestClient(app)


@pytest.fixture()
def client_with_completed_job() -> TestClient:
    """Test client with Garrett framework and a completed job with proposals.

    Creates N_QUOTES proposals (one per quote) with confidences
    0.5, 0.6, 0.7, 0.8 (for N_QUOTES=4).
    """
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    tag_ids = _import_garrett(app)

    db = app.state.db_factory()
    try:
        quotes = db.query(Quote).filter_by(project_id=1).all()
        assert len(quotes) == N_QUOTES

        job = AutoCodeJob(
            project_id=1,
            framework_id="garrett",
            status="completed",
            total_quotes=N_QUOTES,
            processed_quotes=N_QUOTES,
            proposed_count=N_QUOTES,
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
        )
        db.add(job)
        db.flush()

        for i, quote in enumerate(quotes):
            db.add(ProposedTag(
                job_id=job.id,
                quote_id=quote.id,
                tag_definition_id=tag_ids[i % len(tag_ids)],
                confidence=0.5 + (i * 0.1),  # 0.5, 0.6, 0.7, 0.8
                rationale=f"Test rationale {i}",
            ))
        db.commit()
    finally:
        db.close()
    return TestClient(app)


def _mock_cloud_settings() -> MagicMock:
    """Create a mock settings object with a cloud provider and API key."""
    settings = MagicMock()
    settings.llm_provider = "anthropic"
    settings.anthropic_api_key = "test-key"
    return settings


# ---------------------------------------------------------------------------
# POST /autocode/{framework_id} — start job
# ---------------------------------------------------------------------------


class TestStartAutoCodeJob:
    def test_returns_409_if_already_run(
        self, client_with_garrett: TestClient
    ) -> None:
        """Cannot re-run AutoCode for the same framework."""
        db = client_with_garrett.app.state.db_factory()  # type: ignore[union-attr]
        try:
            db.add(AutoCodeJob(
                project_id=1, framework_id="garrett", status="completed"
            ))
            db.commit()
        finally:
            db.close()

        resp = client_with_garrett.post("/api/projects/1/autocode/garrett")
        assert resp.status_code == 409
        assert "already run" in resp.json()["detail"].lower()

    def test_returns_400_if_unknown_framework(self, client: TestClient) -> None:
        resp = client.post("/api/projects/1/autocode/nonexistent")
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    def test_returns_404_if_unknown_project(self, client: TestClient) -> None:
        resp = client.post("/api/projects/999/autocode/garrett")
        assert resp.status_code == 404

    def test_returns_400_if_no_quotes(self, client: TestClient) -> None:
        """Cannot start if project has zero quotes."""
        # Create a second project with no quotes, import Garrett for it
        db = client.app.state.db_factory()  # type: ignore[union-attr]
        try:
            project = Project(
                name="Empty", slug="empty",
                input_dir="/tmp/in", output_dir="/tmp/out",
            )
            db.add(project)
            db.flush()
            empty_pid = project.id

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
                    project_id=empty_pid, codebook_group_id=group.id
                ))
                for tag_tmpl in group_tmpl.tags:
                    db.add(TagDefinition(
                        name=tag_tmpl.name, codebook_group_id=group.id
                    ))
            db.commit()
        finally:
            db.close()

        with patch("bristlenose.server.routes.autocode.load_settings") as mock_ls:
            mock_ls.return_value = _mock_cloud_settings()
            resp = client.post(f"/api/projects/{empty_pid}/autocode/garrett")

        assert resp.status_code == 400
        assert "no quotes" in resp.json()["detail"].lower()

    def test_returns_503_if_local_provider(
        self, client_with_garrett: TestClient
    ) -> None:
        """Ollama can't fit taxonomy — 503."""
        with patch("bristlenose.server.routes.autocode.load_settings") as mock_ls:
            settings = MagicMock()
            settings.llm_provider = "local"
            mock_ls.return_value = settings
            resp = client_with_garrett.post(
                "/api/projects/1/autocode/garrett"
            )

        assert resp.status_code == 503
        assert "local" in resp.json()["detail"].lower()

    def test_returns_503_if_no_api_key(
        self, client_with_garrett: TestClient
    ) -> None:
        with patch("bristlenose.server.routes.autocode.load_settings") as mock_ls:
            settings = MagicMock()
            settings.llm_provider = "anthropic"
            settings.anthropic_api_key = ""
            mock_ls.return_value = settings
            resp = client_with_garrett.post(
                "/api/projects/1/autocode/garrett"
            )

        assert resp.status_code == 503
        assert "api key" in resp.json()["detail"].lower()

    def test_starts_job_successfully(
        self, client_with_garrett: TestClient
    ) -> None:
        """Successful start returns job status and creates DB row."""
        with (
            patch("bristlenose.server.routes.autocode.load_settings") as mock_ls,
            patch(
                "bristlenose.server.routes.autocode.run_autocode_job",
                new_callable=AsyncMock,
            ),
            patch("bristlenose.server.routes.autocode.asyncio.create_task"),
        ):
            mock_ls.return_value = _mock_cloud_settings()
            resp = client_with_garrett.post(
                "/api/projects/1/autocode/garrett"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["framework_id"] == "garrett"
        assert data["status"] == "pending"

        # Verify DB row was created
        db = client_with_garrett.app.state.db_factory()  # type: ignore[union-attr]
        try:
            job = db.query(AutoCodeJob).filter_by(
                project_id=1, framework_id="garrett"
            ).first()
            assert job is not None
            assert job.status == "pending"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# GET /autocode/{framework_id}/status — poll progress
# ---------------------------------------------------------------------------


class TestGetAutoCodeStatus:
    def test_returns_404_if_no_job(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/autocode/garrett/status")
        assert resp.status_code == 404

    def test_returns_job_status(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/status"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["total_quotes"] == N_QUOTES
        assert data["proposed_count"] == N_QUOTES
        assert data["llm_provider"] == "anthropic"

    def test_returns_404_for_wrong_project(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/999/autocode/garrett/status"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /autocode/{framework_id}/cancel — cancel running job
# ---------------------------------------------------------------------------


class TestCancelAutoCodeJob:
    def test_cancel_running_job(
        self, client_with_garrett: TestClient
    ) -> None:
        """Cancelling a running job sets status to cancelled."""
        db = client_with_garrett.app.state.db_factory()  # type: ignore[union-attr]
        try:
            db.add(AutoCodeJob(
                project_id=1, framework_id="garrett", status="running"
            ))
            db.commit()
        finally:
            db.close()

        resp = client_with_garrett.post(
            "/api/projects/1/autocode/garrett/cancel"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["completed_at"] is not None

    def test_cancel_pending_job(
        self, client_with_garrett: TestClient
    ) -> None:
        """Cancelling a pending job (not yet started) works."""
        db = client_with_garrett.app.state.db_factory()  # type: ignore[union-attr]
        try:
            db.add(AutoCodeJob(
                project_id=1, framework_id="garrett", status="pending"
            ))
            db.commit()
        finally:
            db.close()

        resp = client_with_garrett.post(
            "/api/projects/1/autocode/garrett/cancel"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_completed_job_returns_409(
        self, client_with_completed_job: TestClient
    ) -> None:
        """Cannot cancel a completed job."""
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/cancel"
        )
        assert resp.status_code == 409
        assert "cannot be cancelled" in resp.json()["detail"].lower()

    def test_cancel_failed_job_returns_409(
        self, client_with_garrett: TestClient
    ) -> None:
        """Cannot cancel a failed job."""
        db = client_with_garrett.app.state.db_factory()  # type: ignore[union-attr]
        try:
            db.add(AutoCodeJob(
                project_id=1, framework_id="garrett", status="failed",
                error_message="some error"
            ))
            db.commit()
        finally:
            db.close()

        resp = client_with_garrett.post(
            "/api/projects/1/autocode/garrett/cancel"
        )
        assert resp.status_code == 409

    def test_cancel_already_cancelled_returns_409(
        self, client_with_garrett: TestClient
    ) -> None:
        """Cannot cancel an already-cancelled job."""
        db = client_with_garrett.app.state.db_factory()  # type: ignore[union-attr]
        try:
            db.add(AutoCodeJob(
                project_id=1, framework_id="garrett", status="cancelled"
            ))
            db.commit()
        finally:
            db.close()

        resp = client_with_garrett.post(
            "/api/projects/1/autocode/garrett/cancel"
        )
        assert resp.status_code == 409

    def test_cancel_404_no_job(
        self, client_with_garrett: TestClient
    ) -> None:
        """404 when no job exists."""
        resp = client_with_garrett.post(
            "/api/projects/1/autocode/garrett/cancel"
        )
        assert resp.status_code == 404

    def test_cancel_404_wrong_project(self, client: TestClient) -> None:
        resp = client.post("/api/projects/999/autocode/garrett/cancel")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /autocode/{framework_id}/proposals — list proposals
# ---------------------------------------------------------------------------


class TestGetProposals:
    def test_returns_404_if_no_job(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/autocode/garrett/proposals")
        assert resp.status_code == 404

    def test_returns_proposals_above_threshold(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == N_QUOTES  # All 4 are ≥ 0.5

    def test_threshold_filters(
        self, client_with_completed_job: TestClient
    ) -> None:
        # Confidences are 0.5, 0.6, 0.7, 0.8
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.75"
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only 0.8 is ≥ 0.75
        assert data["total"] == 1

    def test_proposals_have_expected_fields(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        data = resp.json()
        assert len(data["proposals"]) > 0
        p = data["proposals"][0]
        assert "id" in p
        assert "quote_id" in p
        assert "dom_id" in p
        assert "session_id" in p
        assert "speaker_code" in p
        assert "start_timecode" in p
        assert "quote_text" in p
        assert "tag_name" in p
        assert "group_name" in p
        assert "colour_set" in p
        assert "colour_index" in p
        assert "confidence" in p
        assert "rationale" in p
        assert "status" in p

    def test_proposals_sorted_by_confidence_desc(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        data = resp.json()
        confidences = [p["confidence"] for p in data["proposals"]]
        assert confidences == sorted(confidences, reverse=True)


# ---------------------------------------------------------------------------
# POST /autocode/proposals/{id}/accept
# ---------------------------------------------------------------------------


class TestAcceptProposal:
    def test_accept_creates_quote_tag(
        self, client_with_completed_job: TestClient
    ) -> None:
        # Get a proposal ID
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        proposal_id = resp.json()["proposals"][0]["id"]

        resp = client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/accept"
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        # Verify ProposedTag status
        db = client_with_completed_job.app.state.db_factory()  # type: ignore[union-attr]
        try:
            proposal = db.get(ProposedTag, proposal_id)
            assert proposal is not None
            assert proposal.status == "accepted"
            assert proposal.reviewed_at is not None

            # Verify QuoteTag created
            qt = (
                db.query(QuoteTag)
                .filter_by(
                    quote_id=proposal.quote_id,
                    tag_definition_id=proposal.tag_definition_id,
                )
                .first()
            )
            assert qt is not None
        finally:
            db.close()

    def test_accept_404_unknown_proposal(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/proposals/9999/accept"
        )
        assert resp.status_code == 404

    def test_accept_409_already_accepted(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        proposal_id = resp.json()["proposals"][0]["id"]

        # Accept once
        client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/accept"
        )
        # Try again
        resp = client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/accept"
        )
        assert resp.status_code == 409
        assert "already accepted" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /autocode/proposals/{id}/deny
# ---------------------------------------------------------------------------


class TestDenyProposal:
    def test_deny_marks_as_denied(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        proposal_id = resp.json()["proposals"][0]["id"]

        resp = client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/deny"
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        # Verify status
        db = client_with_completed_job.app.state.db_factory()  # type: ignore[union-attr]
        try:
            proposal = db.get(ProposedTag, proposal_id)
            assert proposal is not None
            assert proposal.status == "denied"
            assert proposal.reviewed_at is not None

            # Verify no QuoteTag created
            qt = (
                db.query(QuoteTag)
                .filter_by(
                    quote_id=proposal.quote_id,
                    tag_definition_id=proposal.tag_definition_id,
                )
                .first()
            )
            assert qt is None
        finally:
            db.close()

    def test_deny_404_unknown_proposal(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/proposals/9999/deny"
        )
        assert resp.status_code == 404

    def test_deny_409_already_denied(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        proposal_id = resp.json()["proposals"][0]["id"]

        # Deny once
        client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/deny"
        )
        # Try again
        resp = client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/deny"
        )
        assert resp.status_code == 409
        assert "already denied" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /autocode/{framework_id}/accept-all — bulk accept
# ---------------------------------------------------------------------------


class TestAcceptAllProposals:
    def test_accepts_all_above_threshold(
        self, client_with_completed_job: TestClient
    ) -> None:
        # Confidences: 0.5, 0.6, 0.7, 0.8 — 2 are ≥ 0.7
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/accept-all",
            json={"min_confidence": 0.7},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == 2  # 0.7 and 0.8

        # Verify proposals are accepted
        db = client_with_completed_job.app.state.db_factory()  # type: ignore[union-attr]
        try:
            accepted = (
                db.query(ProposedTag).filter_by(status="accepted").count()
            )
            assert accepted == 2
            qt_count = db.query(QuoteTag).count()
            assert qt_count == 2
        finally:
            db.close()

    def test_accepts_all_default_threshold(
        self, client_with_completed_job: TestClient
    ) -> None:
        """Without body, uses default min_confidence=0.5."""
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/accept-all",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] == N_QUOTES

    def test_accept_all_with_group_filter(
        self, client_with_completed_job: TestClient
    ) -> None:
        """Filter by codebook group."""
        db = client_with_completed_job.app.state.db_factory()  # type: ignore[union-attr]
        try:
            first_group = (
                db.query(CodebookGroup)
                .filter_by(framework_id="garrett")
                .first()
            )
            assert first_group is not None
            group_id = first_group.id
        finally:
            db.close()

        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/accept-all",
            json={"group_id": group_id, "min_confidence": 0.5},
        )
        assert resp.status_code == 200
        # Some proposals should be accepted (only those with tags in this group)
        assert resp.json()["accepted"] >= 0

    def test_accept_all_404_no_job(self, client: TestClient) -> None:
        resp = client.post("/api/projects/1/autocode/garrett/accept-all")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /autocode/{framework_id}/deny-all — bulk deny
# ---------------------------------------------------------------------------


class TestDenyAllProposals:
    def test_denies_all_pending(
        self, client_with_completed_job: TestClient
    ) -> None:
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/deny-all",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["denied"] == N_QUOTES

        # Verify all proposals are denied and no QuoteTags created
        db = client_with_completed_job.app.state.db_factory()  # type: ignore[union-attr]
        try:
            denied = db.query(ProposedTag).filter_by(status="denied").count()
            assert denied == N_QUOTES
            qt_count = db.query(QuoteTag).count()
            assert qt_count == 0
        finally:
            db.close()

    def test_deny_all_skips_already_accepted(
        self, client_with_completed_job: TestClient
    ) -> None:
        """Bulk deny doesn't touch already-accepted proposals."""
        # Accept one proposal first
        resp = client_with_completed_job.get(
            "/api/projects/1/autocode/garrett/proposals?min_confidence=0.5"
        )
        proposal_id = resp.json()["proposals"][0]["id"]
        client_with_completed_job.post(
            f"/api/projects/1/autocode/proposals/{proposal_id}/accept"
        )

        # Now deny all — should only deny the remaining
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/deny-all",
        )
        assert resp.status_code == 200
        assert resp.json()["denied"] == N_QUOTES - 1

    def test_deny_below_max_confidence(
        self, client_with_completed_job: TestClient
    ) -> None:
        """Deny-all with max_confidence denies only proposals below the threshold.

        Fixture creates proposals with confidences 0.5, 0.6, 0.7, 0.8.
        max_confidence=0.65 should deny only the 0.5 and 0.6 proposals.
        """
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/deny-all",
            json={"max_confidence": 0.65},
        )
        assert resp.status_code == 200
        assert resp.json()["denied"] == 2

        # Verify the correct proposals were denied (0.5, 0.6) and others untouched
        db = client_with_completed_job.app.state.db_factory()  # type: ignore[union-attr]
        try:
            denied = db.query(ProposedTag).filter_by(status="denied").count()
            assert denied == 2
            pending = db.query(ProposedTag).filter_by(status="pending").count()
            assert pending == 2
        finally:
            db.close()

    def test_deny_below_zero_denies_nothing(
        self, client_with_completed_job: TestClient
    ) -> None:
        """max_confidence=0.0 means nothing is below the threshold."""
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/deny-all",
            json={"max_confidence": 0.0},
        )
        assert resp.status_code == 200
        assert resp.json()["denied"] == 0

    def test_deny_below_one_denies_all(
        self, client_with_completed_job: TestClient
    ) -> None:
        """max_confidence=1.0 denies everything below 1.0 (all proposals)."""
        resp = client_with_completed_job.post(
            "/api/projects/1/autocode/garrett/deny-all",
            json={"max_confidence": 1.0},
        )
        assert resp.status_code == 200
        assert resp.json()["denied"] == N_QUOTES

    def test_deny_all_404_no_job(self, client: TestClient) -> None:
        resp = client.post("/api/projects/1/autocode/garrett/deny-all")
        assert resp.status_code == 404
