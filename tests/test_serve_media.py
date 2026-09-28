"""Tests for the /media/ endpoint extension allowlist and path-traversal guard."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    """Client with a project dir containing test files."""
    # Create allowed and disallowed files
    (tmp_path / "video.mp4").write_bytes(b"fake-mp4")
    (tmp_path / "audio.wav").write_bytes(b"fake-wav")
    (tmp_path / "subs.vtt").write_bytes(b"WEBVTT")
    (tmp_path / "thumb.jpg").write_bytes(b"fake-jpg")
    (tmp_path / "secret.env").write_text("API_KEY=hunter2")
    (tmp_path / "data.db").write_bytes(b"SQLite")
    (tmp_path / "script.py").write_text("import os")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.mp4").write_bytes(b"fake-mp4")
    app = create_app(project_dir=tmp_path, db_url="sqlite://")
    return AuthTestClient(app)


class TestAllowedExtensions:
    def test_mp4(self, client: TestClient) -> None:
        assert client.get("/media/video.mp4").status_code == 200

    def test_wav(self, client: TestClient) -> None:
        assert client.get("/media/audio.wav").status_code == 200

    def test_nested_subdir(self, client: TestClient) -> None:
        assert client.get("/media/subdir/nested.mp4").status_code == 200

    def test_every_ingestible_recording_suffix(self, tmp_path: Path) -> None:
        """What ingest accepts as a recording, the player can be pointed at."""
        from bristlenose.models import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

        for ext in sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS):
            (tmp_path / f"rec{ext}").write_bytes(b"fake")
        c = AuthTestClient(create_app(project_dir=tmp_path, db_url="sqlite://"))
        for ext in sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS):
            assert c.get(f"/media/rec{ext}").status_code == 200, ext


class TestOnlyRecordingsServed:
    """``/media/`` is unauthenticated and rooted at the project dir, so it
    serves recordings and nothing else. The only producer of ``/media/`` URLs
    (``_file_to_media_uri``, via the video map) points at video/audio source
    files; transcripts, subtitles, .docx and images are never requested there.
    With ``--redact-pii`` on, ``transcripts-raw/`` holds every original PII
    value in context.
    """

    @pytest.mark.parametrize(
        "rel",
        [
            "bristlenose-output/transcripts-raw/s1.txt",
            "bristlenose-output/transcripts-raw/s1.md",
            "interview.docx",
            "subs.vtt",
            "subs.srt",
            "thumb.jpg",
            "thumb.png",
        ],
    )
    def test_non_recording_refused(self, tmp_path: Path, rel: str) -> None:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Sarah Jones, 07700 900123")
        c = TestClient(create_app(project_dir=tmp_path, db_url="sqlite://"))
        resp = c.get(f"/media/{rel}")
        assert resp.status_code == 403
        assert "Sarah Jones" not in resp.text


class TestBlockedExtensions:
    def test_env_file(self, client: TestClient) -> None:
        assert client.get("/media/secret.env").status_code == 403

    def test_db_file(self, client: TestClient) -> None:
        assert client.get("/media/data.db").status_code == 403

    def test_python_file(self, client: TestClient) -> None:
        assert client.get("/media/script.py").status_code == 403

    def test_git_config(self, client: TestClient) -> None:
        assert client.get("/media/.git/config").status_code == 403


class TestPathTraversal:
    def test_dotdot_blocked(self, client: TestClient) -> None:
        assert client.get("/media/../../../etc/passwd").status_code in (403, 404)

    def test_encoded_dotdot_blocked(self, client: TestClient) -> None:
        assert client.get("/media/..%2F..%2F..%2Fetc%2Fpasswd").status_code in (403, 404)


class TestNotFound:
    def test_missing_file(self, client: TestClient) -> None:
        assert client.get("/media/nonexistent.mp4").status_code == 404
