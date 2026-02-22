"""Tests for the dashboard API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Smoke-test fixture has 1 session (s1) with 2 speakers (m1, p1),
# 4 quotes (q-p1-10, q-p1-26, q-p1-46, q-p1-66),
# 2 sections (Dashboard, Search), 1 theme (Onboarding gaps).


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


class TestDashboardEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/dashboard")
        assert resp.status_code == 200

    def test_response_has_top_level_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        expected = {
            "stats", "sessions", "featured_quotes",
            "sections", "themes", "moderator_header", "observer_header",
            "coverage",
        }
        assert set(data.keys()) == expected


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestDashboardStats:
    def test_session_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["session_count"] == 1

    def test_quotes_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["quotes_count"] == 4

    def test_sections_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["sections_count"] == 2

    def test_themes_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["themes_count"] == 1

    def test_total_duration_seconds(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["total_duration_seconds"] == 78.0

    def test_total_duration_human(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["total_duration_human"] == "1m"

    def test_total_words(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        # Smoke-test fixture VTT doesn't populate words_spoken; just check type.
        assert isinstance(data["stats"]["total_words"], int)

    def test_ai_tags_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        # All 4 quotes have sentiment tags.
        assert data["stats"]["ai_tags_count"] == 4

    def test_user_tags_count_initially_zero(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["user_tags_count"] == 0

    def test_user_tags_count_after_tagging(self, client: TestClient) -> None:
        """After adding user tags, the count updates."""
        client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["accessibility", "navigation"]},
        )
        data = client.get("/api/projects/1/dashboard").json()
        assert data["stats"]["user_tags_count"] == 2

    def test_stats_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        expected = {
            "session_count", "total_duration_seconds", "total_duration_human",
            "total_words", "quotes_count", "sections_count", "themes_count",
            "ai_tags_count", "user_tags_count",
        }
        assert set(data["stats"].keys()) == expected


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class TestDashboardSessions:
    def test_session_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert len(data["sessions"]) == 1

    def test_session_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        session = data["sessions"][0]
        assert session["session_id"] == "s1"
        assert session["session_number"] == 1
        assert session["duration_seconds"] == 78.0
        assert session["duration_human"] == "1m"

    def test_session_speakers(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        session = data["sessions"][0]
        codes = {sp["speaker_code"] for sp in session["speakers"]}
        assert codes == {"m1", "p1"}

    def test_speaker_ordering(self, client: TestClient) -> None:
        """Moderators before participants."""
        data = client.get("/api/projects/1/dashboard").json()
        speakers = data["sessions"][0]["speakers"]
        assert speakers[0]["speaker_code"] == "m1"
        assert speakers[1]["speaker_code"] == "p1"

    def test_session_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        session = data["sessions"][0]
        expected = {
            "session_id", "session_number", "session_date",
            "duration_seconds", "duration_human", "speakers",
            "source_filename", "has_media", "sentiment_counts",
        }
        assert set(session.keys()) == expected

    def test_speaker_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        speaker = data["sessions"][0]["speakers"][0]
        expected = {"speaker_code", "name", "role"}
        assert set(speaker.keys()) == expected

    def test_sentiment_counts(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        sentiments = data["sessions"][0]["sentiment_counts"]
        # Fixture: confusion, frustration, delight, frustration
        assert "confusion" in sentiments
        assert "frustration" in sentiments
        assert "delight" in sentiments


# ---------------------------------------------------------------------------
# Featured quotes
# ---------------------------------------------------------------------------


class TestDashboardFeaturedQuotes:
    def test_featured_quotes_returned(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert len(data["featured_quotes"]) > 0

    def test_featured_quotes_max_nine(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert len(data["featured_quotes"]) <= 9

    def test_featured_quote_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        fq = data["featured_quotes"][0]
        expected = {
            "dom_id", "text", "participant_id", "session_id",
            "speaker_name", "start_timecode", "end_timecode",
            "sentiment", "intensity", "researcher_context",
            "rank", "has_media", "is_starred", "is_hidden",
        }
        assert set(fq.keys()) == expected

    def test_featured_quotes_have_sequential_ranks(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        ranks = [fq["rank"] for fq in data["featured_quotes"]]
        assert ranks == list(range(len(ranks)))

    def test_featured_quote_dom_id_format(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        for fq in data["featured_quotes"]:
            assert fq["dom_id"].startswith("q-")

    def test_featured_quotes_not_starred_initially(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        for fq in data["featured_quotes"]:
            assert fq["is_starred"] is False

    def test_featured_quotes_not_hidden_initially(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        for fq in data["featured_quotes"]:
            assert fq["is_hidden"] is False

    def test_starred_reflected_in_featured(self, client: TestClient) -> None:
        """Star a quote, then check it shows as starred in featured."""
        data = client.get("/api/projects/1/dashboard").json()
        first_dom_id = data["featured_quotes"][0]["dom_id"]

        client.put(
            "/api/projects/1/starred",
            json={first_dom_id: True},
        )
        data = client.get("/api/projects/1/dashboard").json()
        matching = [fq for fq in data["featured_quotes"] if fq["dom_id"] == first_dom_id]
        assert len(matching) == 1
        assert matching[0]["is_starred"] is True

    def test_hidden_reflected_in_featured(self, client: TestClient) -> None:
        """Hide a quote, then check it shows as hidden in featured."""
        data = client.get("/api/projects/1/dashboard").json()
        first_dom_id = data["featured_quotes"][0]["dom_id"]

        client.put(
            "/api/projects/1/hidden",
            json={first_dom_id: True},
        )
        data = client.get("/api/projects/1/dashboard").json()
        matching = [fq for fq in data["featured_quotes"] if fq["dom_id"] == first_dom_id]
        assert len(matching) == 1
        assert matching[0]["is_hidden"] is True


# ---------------------------------------------------------------------------
# Navigation items (sections + themes)
# ---------------------------------------------------------------------------


class TestDashboardNavItems:
    def test_sections_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert len(data["sections"]) == 2

    def test_section_labels(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        labels = [s["label"] for s in data["sections"]]
        assert "Dashboard" in labels
        assert "Search" in labels

    def test_section_ordering(self, client: TestClient) -> None:
        """Sections ordered by display_order."""
        data = client.get("/api/projects/1/dashboard").json()
        labels = [s["label"] for s in data["sections"]]
        assert labels.index("Dashboard") < labels.index("Search")

    def test_section_anchor_format(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        for s in data["sections"]:
            assert s["anchor"].startswith("section-")

    def test_dashboard_section_anchor(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        dashboard = [s for s in data["sections"] if s["label"] == "Dashboard"][0]
        assert dashboard["anchor"] == "section-dashboard"

    def test_themes_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert len(data["themes"]) == 1

    def test_theme_label(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["themes"][0]["label"] == "Onboarding gaps"

    def test_theme_anchor_format(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert data["themes"][0]["anchor"] == "theme-onboarding-gaps"

    def test_nav_item_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        for item in data["sections"] + data["themes"]:
            assert set(item.keys()) == {"label", "anchor"}


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestDashboardHeaders:
    def test_moderator_header_present(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        # m1 has no name in fixture, so header should be empty.
        assert isinstance(data["moderator_header"], str)

    def test_observer_header_present(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        assert isinstance(data["observer_header"], str)

    def test_moderator_header_after_rename(self, client: TestClient) -> None:
        """After renaming m1, the header should include the name."""
        client.put(
            "/api/projects/1/people",
            json={"m1": {"full_name": "Sarah Chen", "short_name": "Sarah", "role": ""}},
        )
        data = client.get("/api/projects/1/dashboard").json()
        assert "Sarah" in data["moderator_header"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDashboardErrors:
    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/dashboard")
        assert resp.status_code == 404

    def test_404_on_empty_db(self, client_empty: TestClient) -> None:
        resp = client_empty.get("/api/projects/1/dashboard")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


class TestDashboardCoverage:
    def test_coverage_present_in_response(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        # Smoke-test fixture has transcript segments, so coverage should exist.
        assert "coverage" in data

    def test_coverage_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        cov = data["coverage"]
        if cov is None:
            pytest.skip("No transcript segments in fixture")
        expected = {"pct_in_report", "pct_moderator", "pct_omitted", "omitted_by_session"}
        assert set(cov.keys()) == expected

    def test_coverage_percentages_are_integers(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        cov = data["coverage"]
        if cov is None:
            pytest.skip("No transcript segments in fixture")
        assert isinstance(cov["pct_in_report"], int)
        assert isinstance(cov["pct_moderator"], int)
        assert isinstance(cov["pct_omitted"], int)

    def test_coverage_percentages_sum_roughly_to_100(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        cov = data["coverage"]
        if cov is None:
            pytest.skip("No transcript segments in fixture")
        total = cov["pct_in_report"] + cov["pct_moderator"] + cov["pct_omitted"]
        # Rounding can cause ±1 deviation.
        assert 98 <= total <= 102

    def test_coverage_omitted_sessions_are_list(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        cov = data["coverage"]
        if cov is None:
            pytest.skip("No transcript segments in fixture")
        assert isinstance(cov["omitted_by_session"], list)

    def test_omitted_session_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        cov = data["coverage"]
        if cov is None or not cov["omitted_by_session"]:
            pytest.skip("No omitted sessions in fixture")
        sess = cov["omitted_by_session"][0]
        expected = {"session_number", "session_id", "full_segments", "fragments_html"}
        assert set(sess.keys()) == expected

    def test_omitted_segment_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/dashboard").json()
        cov = data["coverage"]
        if cov is None:
            pytest.skip("No transcript segments in fixture")
        for sess in cov["omitted_by_session"]:
            for seg in sess["full_segments"]:
                expected = {"speaker_code", "start_time", "text", "session_id"}
                assert set(seg.keys()) == expected
