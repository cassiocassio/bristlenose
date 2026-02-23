"""Tests for the moderator question API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import Quote as QuoteModel

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Smoke-test transcript (s1.txt):
# [00:02] [m1] Thanks for joining me today. Can you tell me about your experience...
# [00:10] [p1] Sure. I found the dashboard pretty confusing at first...
# [00:19] [m1] What specifically was confusing about it?
# [00:26] [p1] The navigation was hidden behind a hamburger menu...
# [00:39] [m1] And how did you feel about the search feature?
# [00:46] [p1] Oh, the search was great actually...
# [00:56] [m1] Good to hear. Any other thoughts on the overall experience?
# [01:06] [p1] I think the onboarding could be better...
#
# Segments (0-based): 0=m1, 1=p1, 2=m1, 3=p1, 4=m1, 5=p1, 6=m1, 7=p1
# Quotes: q-p1-10 (seg 1), q-p1-26 (seg 3), q-p1-46 (seg 5), q-p1-66 (seg 7)


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data.

    The fixture quotes default to segment_index=-1 (pre-v0.11 data).
    Tests that need segment_index > 0 must update quotes via the DB.
    """
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


def _set_quote_segment_index(
    client: TestClient, dom_id_prefix: str, segment_index: int,
) -> None:
    """Update a quote's segment_index directly in the database."""
    db = client.app.state.db_factory()  # type: ignore[union-attr]
    try:
        quote = (
            db.query(QuoteModel)
            .filter(
                QuoteModel.participant_id == "p1",
                QuoteModel.start_timecode == float(dom_id_prefix),
            )
            .first()
        )
        assert quote is not None, f"Quote with start_timecode={dom_id_prefix} not found"
        quote.segment_index = segment_index
        db.commit()
    finally:
        db.close()


class TestModeratorQuestionEndpoint:
    """Tests for GET /api/projects/{id}/quotes/{dom_id}/moderator-question."""

    def test_returns_404_for_nonexistent_quote(self, client: TestClient) -> None:
        resp = client.get(
            "/api/projects/1/quotes/q-p1-99999/moderator-question",
        )
        assert resp.status_code == 404

    def test_returns_404_for_segment_index_minus_one(self, client: TestClient) -> None:
        """Quotes with segment_index=-1 (legacy) return 404."""
        resp = client.get(
            "/api/projects/1/quotes/q-p1-10/moderator-question",
        )
        assert resp.status_code == 404

    def test_returns_404_for_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get(
            "/api/projects/999/quotes/q-p1-10/moderator-question",
        )
        assert resp.status_code == 404

    def test_happy_path_returns_moderator_segment(self, client: TestClient) -> None:
        """Quote q-p1-26 at segment_index=3 should find m1 at segment_index=2."""
        _set_quote_segment_index(client, "26", segment_index=3)
        resp = client.get(
            "/api/projects/1/quotes/q-p1-26/moderator-question",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["speaker_code"] == "m1"
        assert data["segment_index"] == 2
        assert "confusing" in data["text"].lower()

    def test_response_shape(self, client: TestClient) -> None:
        """Response has all expected fields."""
        _set_quote_segment_index(client, "26", segment_index=3)
        data = client.get(
            "/api/projects/1/quotes/q-p1-26/moderator-question",
        ).json()
        assert set(data.keys()) == {
            "text",
            "speaker_code",
            "start_time",
            "end_time",
            "segment_index",
        }

    def test_finds_non_adjacent_moderator(self, client: TestClient) -> None:
        """If the immediately preceding segment is a participant, skip to the
        moderator before that.

        Segment layout: 0=m1, 1=p1, 2=m1, 3=p1, 4=m1, 5=p1
        Quote at segment 5 → should find m1 at segment 4.
        """
        _set_quote_segment_index(client, "46", segment_index=5)
        resp = client.get(
            "/api/projects/1/quotes/q-p1-46/moderator-question",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["speaker_code"] == "m1"
        assert data["segment_index"] == 4
        assert "search" in data["text"].lower()

    def test_first_participant_segment_returns_moderator(
        self, client: TestClient,
    ) -> None:
        """Quote at segment_index=1 should find m1 at segment_index=0."""
        _set_quote_segment_index(client, "10", segment_index=1)
        resp = client.get(
            "/api/projects/1/quotes/q-p1-10/moderator-question",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["speaker_code"] == "m1"
        assert data["segment_index"] == 0

    def test_segment_index_zero_returns_404(self, client: TestClient) -> None:
        """segment_index=0 means no segment before it — 404."""
        _set_quote_segment_index(client, "10", segment_index=0)
        resp = client.get(
            "/api/projects/1/quotes/q-p1-10/moderator-question",
        )
        # segment_index < 1 → 404
        assert resp.status_code == 404

    def test_timecodes_are_floats(self, client: TestClient) -> None:
        _set_quote_segment_index(client, "26", segment_index=3)
        data = client.get(
            "/api/projects/1/quotes/q-p1-26/moderator-question",
        ).json()
        assert isinstance(data["start_time"], (int, float))
        assert isinstance(data["end_time"], (int, float))
