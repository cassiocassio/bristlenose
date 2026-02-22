"""Tests for the sessions API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


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


class TestSessionsEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/sessions")
        assert resp.status_code == 200

    def test_returns_sessions_list(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        assert "sessions" in data
        assert "moderator_names" in data
        assert "observer_names" in data
        assert "source_folder_uri" in data

    def test_session_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        assert len(data["sessions"]) == 1

    def test_session_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        assert session["session_id"] == "s1"
        assert session["session_number"] == 1
        assert session["duration_seconds"] == 78.0
        assert session["session_date"] is not None

    def test_session_speakers(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        speakers = session["speakers"]
        assert len(speakers) == 2
        codes = {sp["speaker_code"] for sp in speakers}
        assert codes == {"m1", "p1"}

    def test_speaker_roles(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        speakers = data["sessions"][0]["speakers"]
        roles = {sp["speaker_code"]: sp["role"] for sp in speakers}
        assert roles["m1"] == "researcher"
        assert roles["p1"] == "participant"

    def test_speaker_ordering(self, client: TestClient) -> None:
        """Moderators should come before participants."""
        data = client.get("/api/projects/1/sessions").json()
        speakers = data["sessions"][0]["speakers"]
        assert speakers[0]["speaker_code"] == "m1"
        assert speakers[1]["speaker_code"] == "p1"

    def test_journey_labels(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        # p1 has quotes in Dashboard and Search clusters
        assert "Dashboard" in session["journey_labels"]
        assert "Search" in session["journey_labels"]

    def test_journey_label_order(self, client: TestClient) -> None:
        """Journey labels should be ordered by cluster display_order."""
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        labels = session["journey_labels"]
        # Dashboard has display_order=1, Search has display_order=2
        assert labels.index("Dashboard") < labels.index("Search")

    def test_sentiment_counts(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        sentiments = session["sentiment_counts"]
        # From the fixture: confusion, frustration, delight, frustration
        assert "confusion" in sentiments
        assert "frustration" in sentiments
        assert "delight" in sentiments

    def test_source_files(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        assert len(session["source_files"]) == 1
        sf = session["source_files"][0]
        assert sf["file_type"] == "subtitle_vtt"
        assert "Session 1.vtt" in sf["filename"]

    def test_has_media_flags(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        # VTT files don't set has_media
        assert session["has_media"] is False
        assert session["has_video"] is False

    def test_source_folder_uri(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        uri = data["source_folder_uri"]
        assert uri.startswith("file:///")
        assert "smoke-test" in uri or "input" in uri


class TestSessionsErrors:
    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/sessions")
        assert resp.status_code == 404

    def test_404_on_empty_db(self, client_empty: TestClient) -> None:
        resp = client_empty.get("/api/projects/1/sessions")
        assert resp.status_code == 404


class TestSessionsResponseShape:
    """Verify the response matches the Pydantic models exactly."""

    def test_session_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        session = data["sessions"][0]
        expected_keys = {
            "session_id",
            "session_number",
            "session_date",
            "duration_seconds",
            "has_media",
            "has_video",
            "speakers",
            "journey_labels",
            "sentiment_counts",
            "source_files",
        }
        assert set(session.keys()) == expected_keys

    def test_speaker_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        speaker = data["sessions"][0]["speakers"][0]
        expected_keys = {"speaker_code", "name", "role"}
        assert set(speaker.keys()) == expected_keys

    def test_source_file_has_all_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/sessions").json()
        sf = data["sessions"][0]["source_files"][0]
        expected_keys = {"path", "file_type", "filename"}
        assert set(sf.keys()) == expected_keys
