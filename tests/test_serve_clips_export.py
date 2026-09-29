"""Tests for clip extraction API endpoints."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.clip_manifest import ClipSpec
from bristlenose.server.clip_subtitles import Cue, to_webvtt
from bristlenose.server.models import Quote, QuoteEdit
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.routes import clips_export
from bristlenose.utils.fs import CloudFetchTimeoutError
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with imported smoke-test data."""
    # Reset module-level job state between tests
    clips_export._jobs.clear()
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


class TestStartClipExtraction:
    def test_ffmpeg_missing_returns_422(self, client: TestClient) -> None:
        with patch(
            "bristlenose.server.routes.clips_export.FFmpegBackend.check_available",
            return_value=(False, "FFmpeg not found on PATH"),
        ):
            resp = client.post("/api/projects/1/export/clips")
            assert resp.status_code == 422
            assert "not found" in resp.json()["detail"].lower()

    def test_no_clips_returns_no_clips_status(self, client: TestClient) -> None:
        """No starred or hero quotes with media → total: 0."""
        with patch(
            "bristlenose.server.routes.clips_export.FFmpegBackend.check_available",
            return_value=(True, ""),
        ):
            resp = client.post("/api/projects/1/export/clips")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0
            assert data["status"] == "no_clips"

    def test_project_not_found(self, client: TestClient) -> None:
        with patch(
            "bristlenose.server.routes.clips_export.FFmpegBackend.check_available",
            return_value=(True, ""),
        ):
            resp = client.post("/api/projects/999/export/clips")
            assert resp.status_code == 404

    def test_concurrent_job_returns_409(self, client: TestClient) -> None:
        # Simulate a running job
        clips_export._jobs[1] = {"status": "running", "progress": 0, "total": 5}
        with patch(
            "bristlenose.server.routes.clips_export.FFmpegBackend.check_available",
            return_value=(True, ""),
        ):
            resp = client.post("/api/projects/1/export/clips")
            assert resp.status_code == 409

    def test_requires_auth(self) -> None:
        """Unauthenticated request gets 401."""
        clips_export._jobs.clear()
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        raw_client = TestClient(app, base_url="http://127.0.0.1")
        resp = raw_client.post("/api/projects/1/export/clips")
        assert resp.status_code == 401

    def test_ids_scope_skips_featured_union(self, client: TestClient) -> None:
        """When the scope picker hands over ids, the hero/union path is skipped."""
        with patch(
            "bristlenose.server.routes.clips_export.FFmpegBackend.check_available",
            return_value=(True, ""),
        ), patch(
            "bristlenose.server.routes.clips_export.pick_featured_quotes",
        ) as mock_featured:
            resp = client.post(
                "/api/projects/1/export/clips", json={"ids": ["q-p1-10"]}
            )
            assert resp.status_code == 200
            # Exactly-these-quotes selection must not fall back to featured heroes.
            mock_featured.assert_not_called()

    def test_no_ids_uses_featured_union(self, client: TestClient) -> None:
        """With no ids (legacy no-scope caller), the featured union still runs."""
        with patch(
            "bristlenose.server.routes.clips_export.FFmpegBackend.check_available",
            return_value=(True, ""),
        ), patch(
            "bristlenose.server.routes.clips_export.pick_featured_quotes",
            return_value=[],
        ) as mock_featured:
            resp = client.post("/api/projects/1/export/clips")
            assert resp.status_code == 200
            mock_featured.assert_called_once()


class TestCancelClipExtraction:
    def test_no_job_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/projects/1/export/clips/cancel")
        assert resp.status_code == 404

    def test_completed_job_returns_404(self, client: TestClient) -> None:
        """A finished job can't be cancelled."""
        clips_export._jobs[1] = {"status": "completed", "output_dir": "/tmp/clips"}
        resp = client.post("/api/projects/1/export/clips/cancel")
        assert resp.status_code == 404

    def test_running_job_is_cancelled(self, client: TestClient) -> None:
        """Cancelling a running job flips its status; the loop reads that flag."""
        clips_export._jobs[1] = {"status": "running", "progress": 2, "total": 10}
        resp = client.post("/api/projects/1/export/clips/cancel")
        assert resp.status_code == 200
        assert resp.json() == {"cancelled": True}
        assert clips_export._jobs[1]["status"] == "cancelled"

        # Status endpoint surfaces the cancelled terminal state.
        status = client.get("/api/projects/1/export/clips/status")
        assert status.json()["status"] == "cancelled"

    def test_requires_auth(self) -> None:
        clips_export._jobs.clear()
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        raw_client = TestClient(app, base_url="http://127.0.0.1")
        resp = raw_client.post("/api/projects/1/export/clips/cancel")
        assert resp.status_code == 401


class TestClipStatus:
    def test_no_job_returns_idle(self, client: TestClient) -> None:
        resp = client.get("/api/projects/1/export/clips/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["total"] == 0

    def test_running_job_returns_progress(self, client: TestClient) -> None:
        clips_export._jobs[1] = {
            "status": "running",
            "progress": 3,
            "total": 10,
            "completed_count": 3,
            "skipped_count": 0,
            "current_clip": "p1 03m45 Sarah",
            "output_dir": None,
        }
        resp = client.get("/api/projects/1/export/clips/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["progress"] == 3
        assert data["total"] == 10

    def test_completed_job_returns_output_dir(self, client: TestClient) -> None:
        clips_export._jobs[1] = {
            "status": "completed",
            "progress": 10,
            "total": 10,
            "completed_count": 8,
            "skipped_count": 2,
            "current_clip": "",
            "output_dir": "/tmp/clips",
        }
        resp = client.get("/api/projects/1/export/clips/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_count"] == 8
        assert data["skipped_count"] == 2
        assert data["output_dir"] == "/tmp/clips"


class TestRevealClips:
    def test_no_job_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/projects/1/export/clips/reveal")
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, client: TestClient, tmp_path: Path) -> None:
        """Path outside output dir is rejected."""
        clips_export._jobs[1] = {
            "status": "completed",
            "output_dir": "/etc/evil",
        }
        resp = client.post("/api/projects/1/export/clips/reveal")
        assert resp.status_code in (403, 404)

    def test_reveal_calls_open(self, client: TestClient, tmp_path: Path) -> None:
        """On macOS, 'open -R' is called."""
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "test.mp4").write_bytes(b"fake")

        # Point the job at a real directory inside project output
        clips_export._jobs[1] = {
            "status": "completed",
            "output_dir": str(clips_dir),
        }

        # The fixture project_dir is _FIXTURE_DIR, output resolves relative to it.
        # For this test, we need the clips_dir to be inside the output_dir.
        # Since the fixture dir may not contain 'bristlenose-output', this test
        # verifies the path validation rejects out-of-tree paths.
        resp = client.post("/api/projects/1/export/clips/reveal")
        # The tmp_path clips_dir is not inside the fixture dir, so this should be
        # rejected by the is_relative_to check.
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------


def _spec(source: Path, start: float = 7.0, end: float = 20.0) -> ClipSpec:
    return ClipSpec(
        quote_id="q-p1-10", participant_id="p1", session_id="s1",
        source_path=source, start=start, end=end, raw_start=10.0,
        speaker_name="", quote_gist="i found the dashboard",
        is_audio_only=False, is_starred=True, is_hero=False,
    )


class TestClipCues:
    """Built against the smoke project's real transcript and quote rows."""

    def _db(self, client: TestClient):  # type: ignore[no-untyped-def]
        return client.app.state.db_factory()  # type: ignore[attr-defined]

    def test_everyone_audible_is_subtitled_with_bbc_colours(self, client: TestClient) -> None:
        db = self._db(client)
        try:
            cues = clips_export._build_clip_cues(db, 1, _spec(_FIXTURE_DIR / "x.mp4"))
        finally:
            db.close()
        # The padding before the quote carries the moderator's question.
        assert cues[0].speaker_code == "m1" and cues[0].colour == "yellow"
        assert {c.speaker_code: c.colour for c in cues}["p1"] == "white"
        assert cues[0].start == 0.0
        assert all(c.end <= 13.0 + 1e-9 for c in cues)
        text = " ".join(line for c in cues for line in c.lines)
        assert "dashboard pretty confusing" in text

    def test_researcher_correction_reaches_the_subtitles(self, client: TestClient) -> None:
        db = self._db(client)
        try:
            quote = db.query(Quote).filter(Quote.start_timecode == 10.0).one()
            db.add(QuoteEdit(
                quote_id=quote.id,
                edited_text=quote.text.replace("dashboard", "DashBoard Pro"),
            ))
            db.commit()
            cues = clips_export._build_clip_cues(db, 1, _spec(_FIXTURE_DIR / "x.mp4"))
        finally:
            db.close()
        text = " ".join(line for c in cues for line in c.lines)
        assert "DashBoard Pro" in text
        assert "the dashboard pretty" not in text

    def test_no_speaker_name_or_code_in_the_subtitles(self, client: TestClient) -> None:
        db = self._db(client)
        try:
            cues = clips_export._build_clip_cues(db, 1, _spec(_FIXTURE_DIR / "x.mp4"))
        finally:
            db.close()
        vtt = to_webvtt(cues)
        assert "p1" not in vtt and "m1" not in vtt


class TestExtractionWritesSubtitles:
    def _cues(self) -> list[Cue]:
        return [Cue(start=0.0, end=2.0, speaker_code="p1", colour="white", lines=("Hi.",))]

    def _run(self, tmp_path: Path, cues: dict[int, list[Cue]], fail_with_subs: bool) -> dict:
        calls: list[Path | None] = []

        def fake_extract(self, source, output, start, end, subtitles=None, subtitle_language="und"):  # type: ignore[no-untyped-def]
            calls.append(subtitles)
            if subtitles is not None:
                assert subtitles.exists()  # the temp SRT is there while ffmpeg runs
                if fail_with_subs:
                    return None
            output.write_bytes(b"clip")
            return output

        clips_export._jobs[1] = {"status": "running", "progress": 0, "total": 1}
        with patch.object(clips_export.FFmpegBackend, "extract_clip", fake_extract):
            asyncio.run(clips_export._run_clip_extraction(
                1, [_spec(tmp_path / "src.mp4")], tmp_path, 1, False, False, cues,
            ))
        manifest = json.loads((tmp_path / "clips_manifest.json").read_text())
        return {"calls": calls, "manifest": manifest}

    def test_vtt_beside_the_clip_and_in_the_manifest(self, tmp_path: Path) -> None:
        out = self._run(tmp_path, {0: self._cues()}, fail_with_subs=False)
        entry = out["manifest"]["clips"][0]
        assert entry["subtitles"] == entry["filename"].rsplit(".", 1)[0] + ".vtt"
        assert (tmp_path / entry["subtitles"]).read_text().startswith("WEBVTT")
        assert len(out["calls"]) == 1 and out["calls"][0] is not None
        assert not list(tmp_path.glob(".*.srt.tmp"))  # temp SRT cleaned up

    def test_failed_subtitle_mux_still_cuts_the_clip(self, tmp_path: Path) -> None:
        out = self._run(tmp_path, {0: self._cues()}, fail_with_subs=True)
        assert out["calls"][0] is not None and out["calls"][1] is None
        assert out["manifest"]["completed"] == 1
        assert not list(tmp_path.glob(".*.srt.tmp"))

    def test_no_transcript_text_means_no_vtt(self, tmp_path: Path) -> None:
        out = self._run(tmp_path, {}, fail_with_subs=False)
        assert out["manifest"]["clips"][0]["subtitles"] is None
        assert out["calls"] == [None]
        assert not list(tmp_path.glob("*.vtt"))

    def test_stale_vtt_from_an_earlier_export_is_removed(self, tmp_path: Path) -> None:
        stale = tmp_path / "p1 00m10 i found the dashboard.vtt"
        stale.write_text("WEBVTT\n")
        out = self._run(tmp_path, {}, fail_with_subs=False)
        assert out["manifest"]["clips"][0]["subtitles"] is None
        assert not stale.exists()

    def test_temp_srt_never_lands_in_the_clips_folder(self, tmp_path: Path) -> None:
        seen: list[Path] = []

        def fake_extract(self, source, output, start, end, subtitles=None, subtitle_language="und"):  # type: ignore[no-untyped-def]
            if subtitles is not None:
                seen.append(subtitles)
            output.write_bytes(b"clip")
            return output

        clips_export._jobs[1] = {"status": "running", "progress": 0, "total": 1}
        with patch.object(clips_export.FFmpegBackend, "extract_clip", fake_extract):
            asyncio.run(clips_export._run_clip_extraction(
                1, [_spec(tmp_path / "src.mp4")], tmp_path, 1, False, False,
                {0: self._cues()},
            ))
        assert seen and seen[0].parent != tmp_path
        assert not seen[0].exists()

    def test_write_error_marks_the_job_failed_not_running(self, tmp_path: Path) -> None:
        # A stranded "running" job refuses every later export with a 409.
        def fake_extract(self, source, output, start, end, subtitles=None, subtitle_language="und"):  # type: ignore[no-untyped-def]
            output.write_bytes(b"clip")
            return output

        clips_export._jobs[1] = {"status": "running", "progress": 0, "total": 1}
        with patch.object(clips_export.FFmpegBackend, "extract_clip", fake_extract), \
                patch.object(clips_export, "build_clip_filename", side_effect=OSError("disk full")):
            asyncio.run(clips_export._run_clip_extraction(
                1, [_spec(tmp_path / "src.mp4")], tmp_path, 1, False, False, {},
            ))
        assert clips_export._jobs[1]["status"] == "failed"

    def test_cloud_timeout_skips_the_clip_without_a_retry(self, tmp_path: Path) -> None:
        calls: list[object] = []

        def fake_extract(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(args)
            return None

        def never_arrives(path):  # type: ignore[no-untyped-def]
            raise CloudFetchTimeoutError(path, 1800.0)

        clips_export._jobs[1] = {"status": "running", "progress": 0, "total": 1}
        with patch.object(clips_export.FFmpegBackend, "extract_clip", fake_extract), \
                patch.object(clips_export, "ensure_materialised", never_arrives):
            asyncio.run(clips_export._run_clip_extraction(
                1, [_spec(tmp_path / "src.mp4")], tmp_path, 1, False, False,
                {0: self._cues()},
            ))
        assert calls == []  # ffmpeg never ran, so nothing was run twice
        assert clips_export._jobs[1]["skipped_count"] == 1


class TestExportComposesSubtitles:
    """The whole route: POST → cues built from the DB → job → files."""

    def test_export_writes_a_vtt_built_from_the_transcript(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        def fake_extract(self, source, output, start, end, subtitles=None, subtitle_language="und"):  # type: ignore[no-untyped-def]
            output.write_bytes(b"clip")
            return output

        media = ({"s1": (tmp_path / "s1.mp4", False)}, {"s1": 120.0})
        with patch.object(clips_export.FFmpegBackend, "check_available", return_value=(True, "")), \
                patch.object(clips_export.FFmpegBackend, "extract_clip", fake_extract), \
                patch.object(clips_export, "_load_session_media", return_value=media), \
                patch.object(clips_export, "_resolve_output_dir", return_value=tmp_path):
            resp = client.post("/api/projects/1/export/clips", json={"ids": ["q-p1-10"]})
            assert resp.status_code == 200 and resp.json()["status"] == "started"
            for _ in range(100):
                if client.get("/api/projects/1/export/clips/status").json()["status"] != "running":
                    break
                time.sleep(0.05)
        manifest = json.loads((tmp_path / "clips" / "clips_manifest.json").read_text())
        vtt = (tmp_path / "clips" / manifest["clips"][0]["subtitles"]).read_text()
        assert "dashboard pretty confusing" in vtt.replace("\n", " ")

    def test_a_failing_subtitle_build_does_not_fail_the_export(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        media = ({"s1": (tmp_path / "s1.mp4", False)}, {"s1": 120.0})
        with patch.object(clips_export.FFmpegBackend, "check_available", return_value=(True, "")), \
                patch.object(clips_export, "_load_session_media", return_value=media), \
                patch.object(clips_export, "_resolve_output_dir", return_value=tmp_path), \
                patch.object(clips_export, "_build_clip_cues", side_effect=RuntimeError("boom")), \
                patch.object(clips_export, "_run_clip_extraction") as run:
            resp = client.post("/api/projects/1/export/clips", json={"ids": ["q-p1-10"]})
        assert resp.status_code == 200
        assert run.call_args[0][6] == {0: []}  # cues_by_clip


class TestSubtitleLanguage:
    def test_detected_language_else_the_app_language(self, client: TestClient) -> None:
        db = client.app.state.db_factory()  # type: ignore[attr-defined]
        try:
            sess = db.query(SessionModel).filter_by(session_id="s1").one()
            sess.language = None
            db.commit()
            with patch.object(clips_export, "get_locale", return_value="de"):
                assert clips_export._subtitle_languages(db, 1) == {"s1": "deu"}
            sess.language = "ja"
            db.commit()
            with patch.object(clips_export, "get_locale", return_value="de"):
                assert clips_export._subtitle_languages(db, 1) == {"s1": "jpn"}
        finally:
            db.close()

    def test_job_tags_each_clip_with_its_sessions_language(self, tmp_path: Path) -> None:
        seen: list[str] = []

        def fake_extract(self, source, output, start, end, subtitles=None, subtitle_language="und"):  # type: ignore[no-untyped-def]
            if subtitles is not None:
                seen.append(subtitle_language)
            output.write_bytes(b"clip")
            return output

        cue = Cue(start=0.0, end=2.0, speaker_code="p1", colour="white", lines=("Hi.",))
        clips_export._jobs[1] = {"status": "running", "progress": 0, "total": 1}
        with patch.object(clips_export.FFmpegBackend, "extract_clip", fake_extract):
            asyncio.run(clips_export._run_clip_extraction(
                1, [_spec(tmp_path / "src.mp4")], tmp_path, 1, False, False,
                {0: [cue]}, {"s1": "jpn"},
            ))
        assert seen == ["jpn"]
