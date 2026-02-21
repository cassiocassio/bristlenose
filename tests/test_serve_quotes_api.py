"""Tests for the quotes API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Quote DOM IDs present in the smoke-test fixture:
# q-p1-10 (Dashboard - confusion), q-p1-26 (Dashboard - frustration),
# q-p1-46 (Search - delight), q-p1-66 (Onboarding gaps theme - frustration)


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data."""
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


@pytest.fixture()
def client_empty() -> TestClient:
    """Create a test client with no project data."""
    app = create_app(dev=True, db_url="sqlite://")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Basic endpoint
# ---------------------------------------------------------------------------


class TestQuotesEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/quotes")
        assert resp.status_code == 200

    def test_response_has_sections_and_themes(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        assert "sections" in data
        assert "themes" in data
        assert "total_quotes" in data
        assert "total_hidden" in data
        assert "total_starred" in data

    def test_total_quotes_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        assert data["total_quotes"] == 4

    def test_total_hidden_zero_initially(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        assert data["total_hidden"] == 0

    def test_total_starred_zero_initially(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        assert data["total_starred"] == 0


# ---------------------------------------------------------------------------
# Sections (screen clusters)
# ---------------------------------------------------------------------------


class TestQuotesSections:
    def test_section_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        assert len(data["sections"]) == 2

    def test_section_ordering(self, client: TestClient) -> None:
        """Sections should be ordered by display_order."""
        data = client.get("/api/projects/1/quotes").json()
        labels = [s["screen_label"] for s in data["sections"]]
        assert labels == ["Dashboard", "Search"]

    def test_dashboard_section_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        dashboard = data["sections"][0]
        assert dashboard["screen_label"] == "Dashboard"
        assert "description" in dashboard
        assert dashboard["display_order"] == 1
        assert "cluster_id" in dashboard

    def test_search_section_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        search = data["sections"][1]
        assert search["screen_label"] == "Search"
        assert search["display_order"] == 2

    def test_dashboard_has_two_quotes(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        dashboard = data["sections"][0]
        assert len(dashboard["quotes"]) == 2

    def test_search_has_one_quote(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        search = data["sections"][1]
        assert len(search["quotes"]) == 1

    def test_quote_ordering_within_section(self, client: TestClient) -> None:
        """Quotes within a section should be ordered by start_timecode."""
        data = client.get("/api/projects/1/quotes").json()
        dashboard = data["sections"][0]
        timecodes = [q["start_timecode"] for q in dashboard["quotes"]]
        assert timecodes == sorted(timecodes)
        assert timecodes == [10.0, 26.0]


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------


class TestQuotesThemes:
    def test_theme_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        assert len(data["themes"]) == 1

    def test_onboarding_theme_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        theme = data["themes"][0]
        assert theme["theme_label"] == "Onboarding gaps"
        assert "description" in theme
        assert "theme_id" in theme

    def test_onboarding_has_one_quote(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        theme = data["themes"][0]
        assert len(theme["quotes"]) == 1


# ---------------------------------------------------------------------------
# Quote fields
# ---------------------------------------------------------------------------


class TestQuoteFields:
    def _get_dashboard_first_quote(self, client: TestClient) -> dict:  # type: ignore[type-arg]
        data = client.get("/api/projects/1/quotes").json()
        return data["sections"][0]["quotes"][0]

    def test_quote_has_all_fields(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        expected = {
            "dom_id", "text", "verbatim_excerpt", "participant_id",
            "session_id", "speaker_name", "start_timecode", "end_timecode",
            "sentiment", "intensity", "researcher_context", "quote_type",
            "topic_label", "is_starred", "is_hidden", "edited_text",
            "tags", "deleted_badges", "proposed_tags", "segment_index",
        }
        assert set(q.keys()) == expected

    def test_quote_dom_id(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["dom_id"] == "q-p1-10"

    def test_quote_text(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert "dashboard" in q["text"].lower()

    def test_quote_timecodes(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["start_timecode"] == 10.0
        assert q["end_timecode"] == 18.0

    def test_quote_sentiment(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["sentiment"] == "confusion"

    def test_quote_intensity(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["intensity"] == 2

    def test_quote_researcher_context(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["researcher_context"] == "When asked about dashboard experience"

    def test_quote_type_screen_specific(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["quote_type"] == "screen_specific"

    def test_quote_type_general_context(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        theme_quote = data["themes"][0]["quotes"][0]
        assert theme_quote["quote_type"] == "general_context"

    def test_quote_topic_label(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["topic_label"] == "Dashboard"

    def test_quote_participant_id(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["participant_id"] == "p1"

    def test_quote_session_id(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert q["session_id"] == "s1"

    def test_speaker_name_fallback(self, client: TestClient) -> None:
        """When no name is set, speaker_name falls back to participant_id."""
        q = self._get_dashboard_first_quote(client)
        # Smoke-test fixture doesn't set person names, so fallback to code
        assert q["speaker_name"] == "p1"

    def test_quote_verbatim_excerpt(self, client: TestClient) -> None:
        q = self._get_dashboard_first_quote(client)
        assert "verbatim_excerpt" in q

    def test_search_quote_sentiment(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        search_quote = data["sections"][1]["quotes"][0]
        assert search_quote["sentiment"] == "delight"
        assert search_quote["dom_id"] == "q-p1-46"

    def test_theme_quote_sentiment(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        theme_quote = data["themes"][0]["quotes"][0]
        assert theme_quote["sentiment"] == "frustration"
        assert theme_quote["dom_id"] == "q-p1-66"


# ---------------------------------------------------------------------------
# Researcher state
# ---------------------------------------------------------------------------


class TestQuoteResearcherState:
    def test_default_not_starred(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["is_starred"] is False

    def test_default_not_hidden(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["is_hidden"] is False

    def test_default_no_edited_text(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["edited_text"] is None

    def test_default_no_tags(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["tags"] == []

    def test_default_no_deleted_badges(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["deleted_badges"] == []

    def test_starred_reflected(self, client: TestClient) -> None:
        """Star a quote via data API, then verify it appears in quotes GET."""
        client.put(
            "/api/projects/1/starred",
            json={"q-p1-10": True},
        )
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["dom_id"] == "q-p1-10"
        assert q["is_starred"] is True

    def test_hidden_reflected(self, client: TestClient) -> None:
        """Hide a quote via data API, then verify it appears in quotes GET."""
        client.put(
            "/api/projects/1/hidden",
            json={"q-p1-26": True},
        )
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][1]
        assert q["dom_id"] == "q-p1-26"
        assert q["is_hidden"] is True

    def test_edited_text_reflected(self, client: TestClient) -> None:
        """Edit a quote via data API, then verify it appears in quotes GET."""
        client.put(
            "/api/projects/1/edits",
            json={"q-p1-10": "Corrected text here"},
        )
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["dom_id"] == "q-p1-10"
        assert q["edited_text"] == "Corrected text here"

    def test_tags_reflected(self, client: TestClient) -> None:
        """Add tags via data API, then verify they appear in quotes GET."""
        client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["accessibility", "navigation"]},
        )
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["dom_id"] == "q-p1-10"
        tag_names = sorted(t["name"] for t in q["tags"])
        assert tag_names == ["accessibility", "navigation"]
        # Tags should have codebook_group info
        for tag in q["tags"]:
            assert "codebook_group" in tag
            assert tag["codebook_group"] == "Uncategorised"

    def test_deleted_badges_reflected(self, client: TestClient) -> None:
        """Delete a badge via data API, then verify it appears in quotes GET."""
        client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": ["confusion"]},
        )
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["dom_id"] == "q-p1-10"
        assert q["deleted_badges"] == ["confusion"]

    def test_total_hidden_count(self, client: TestClient) -> None:
        """After hiding quotes, total_hidden should reflect the count."""
        client.put(
            "/api/projects/1/hidden",
            json={"q-p1-10": True, "q-p1-26": True},
        )
        data = client.get("/api/projects/1/quotes").json()
        assert data["total_hidden"] == 2

    def test_total_starred_count(self, client: TestClient) -> None:
        """After starring a quote, total_starred should reflect the count."""
        client.put(
            "/api/projects/1/starred",
            json={"q-p1-46": True},
        )
        data = client.get("/api/projects/1/quotes").json()
        assert data["total_starred"] == 1

    def test_speaker_name_after_rename(self, client: TestClient) -> None:
        """After renaming a person via people API, speaker_name updates."""
        client.put(
            "/api/projects/1/people",
            json={"p1": {"full_name": "Alice Johnson", "short_name": "Alice", "role": ""}},
        )
        data = client.get("/api/projects/1/quotes").json()
        q = data["sections"][0]["quotes"][0]
        assert q["speaker_name"] == "Alice"


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestQuotesResponseShape:
    def test_section_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        section = data["sections"][0]
        expected = {"cluster_id", "screen_label", "description", "display_order", "quotes"}
        assert set(section.keys()) == expected

    def test_theme_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/quotes").json()
        theme = data["themes"][0]
        expected = {"theme_id", "theme_label", "description", "quotes"}
        assert set(theme.keys()) == expected


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestQuotesErrors:
    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/quotes")
        assert resp.status_code == 404

    def test_404_on_empty_db(self, client_empty: TestClient) -> None:
        resp = client_empty.get("/api/projects/1/quotes")
        assert resp.status_code == 404
