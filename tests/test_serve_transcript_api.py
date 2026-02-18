"""Tests for the transcript page API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

# Smoke-test fixture has 1 session (s1) with 2 speakers (m1, p1),
# 7 transcript segments, and 4 quotes.


@pytest.fixture()
def client() -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Basic endpoint
# ---------------------------------------------------------------------------


class TestTranscriptEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/transcripts/s1")
        assert resp.status_code == 200

    def test_404_nonexistent_session(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/transcripts/s99")
        assert resp.status_code == 404

    def test_404_nonexistent_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/transcripts/s1")
        assert resp.status_code == 404

    def test_response_has_required_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        assert "session_id" in data
        assert "session_number" in data
        assert "duration_seconds" in data
        assert "has_media" in data
        assert "project_name" in data
        assert "report_filename" in data
        assert "speakers" in data
        assert "segments" in data
        assert "annotations" in data


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------


class TestTranscriptMetadata:
    def test_session_id(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        assert data["session_id"] == "s1"

    def test_session_number(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        assert data["session_number"] == 1

    def test_report_filename(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        assert data["report_filename"].startswith("bristlenose-")
        assert data["report_filename"].endswith("-report.html")


# ---------------------------------------------------------------------------
# Speakers
# ---------------------------------------------------------------------------


class TestTranscriptSpeakers:
    def test_speaker_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        assert len(data["speakers"]) == 2

    def test_speaker_sort_order(self, client: TestClient) -> None:
        """Moderators (m-codes) should come before participants (p-codes)."""
        data = client.get("/api/projects/1/transcripts/s1").json()
        codes = [s["code"] for s in data["speakers"]]
        assert codes[0] == "m1"
        assert codes[1] == "p1"

    def test_speaker_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        speaker = data["speakers"][0]
        assert "code" in speaker
        assert "name" in speaker
        assert "role" in speaker


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------


class TestTranscriptSegments:
    def test_segment_count(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        # Smoke-test has 8 segments (alternating m1/p1 conversation)
        assert len(data["segments"]) == 8

    def test_segments_ordered_by_time(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        times = [s["start_time"] for s in data["segments"]]
        assert times == sorted(times)

    def test_moderator_segments_flagged(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        moderator_segs = [s for s in data["segments"] if s["is_moderator"]]
        assert len(moderator_segs) > 0
        for seg in moderator_segs:
            assert seg["speaker_code"].startswith("m")

    def test_segment_has_required_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        seg = data["segments"][0]
        for field in ("speaker_code", "start_time", "end_time", "text",
                      "is_moderator", "is_quoted", "quote_ids"):
            assert field in seg, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Quoted segments and annotations
# ---------------------------------------------------------------------------


class TestTranscriptQuotes:
    def test_quoted_segments_exist(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        quoted = [s for s in data["segments"] if s["is_quoted"]]
        assert len(quoted) > 0

    def test_quoted_segments_have_quote_ids(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        quoted = [s for s in data["segments"] if s["is_quoted"]]
        for seg in quoted:
            assert len(seg["quote_ids"]) > 0

    def test_moderator_segments_not_quoted(self, client: TestClient) -> None:
        """Moderator segments should never be marked as quoted."""
        data = client.get("/api/projects/1/transcripts/s1").json()
        for seg in data["segments"]:
            if seg["is_moderator"]:
                assert not seg["is_quoted"]

    def test_annotations_keyed_by_dom_id(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        for key in data["annotations"]:
            assert key.startswith("q-")

    def test_annotation_has_label(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        # At least one annotation should have a label (cluster/theme assignment)
        labels = [a["label"] for a in data["annotations"].values()]
        non_empty = [lb for lb in labels if lb]
        assert len(non_empty) > 0

    def test_annotation_fields(self, client: TestClient) -> None:
        data = client.get("/api/projects/1/transcripts/s1").json()
        if data["annotations"]:
            ann = next(iter(data["annotations"].values()))
            for field in ("label", "label_type", "sentiment", "participant_id",
                          "start_timecode", "end_timecode", "verbatim_excerpt",
                          "tags", "deleted_badges"):
                assert field in ann, f"Missing annotation field: {field}"


# ---------------------------------------------------------------------------
# Researcher state round-trips
# ---------------------------------------------------------------------------


class TestTranscriptResearcherState:
    def test_tags_round_trip(self, client: TestClient) -> None:
        """Tags applied via PUT show up in transcript annotations."""
        # Apply a tag to the first quote
        client.put(
            "/api/projects/1/tags",
            json={"q-p1-10": ["usability"]},
        )
        data = client.get("/api/projects/1/transcripts/s1").json()
        ann = data["annotations"].get("q-p1-10")
        if ann:
            tag_names = [t["name"] for t in ann["tags"]]
            assert "usability" in tag_names

    def test_deleted_badges_round_trip(self, client: TestClient) -> None:
        """Deleted badges applied via PUT show up in transcript annotations."""
        client.put(
            "/api/projects/1/deleted-badges",
            json={"q-p1-10": ["confusion"]},
        )
        data = client.get("/api/projects/1/transcripts/s1").json()
        ann = data["annotations"].get("q-p1-10")
        if ann:
            assert "confusion" in ann["deleted_badges"]
