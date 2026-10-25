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
    (tmp_path / "secret.env").write_text("API_KEY=hunter2", encoding="utf-8")
    (tmp_path / "data.db").write_bytes(b"SQLite")
    (tmp_path / "script.py").write_text("import os", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]", encoding="utf-8")
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
        target.write_text("Sarah Jones, 07700 900123", encoding="utf-8")
        c = TestClient(
            create_app(project_dir=tmp_path, db_url="sqlite://"), base_url="http://127.0.0.1"
        )
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


class TestRecordingNamesWithReservedCharacters:
    """N173: the player assigns the video map's URI to ``video.src``, so a ``#``
    in a file or folder name started a fragment and a ``?`` a query. The browser
    requested the cut-off path, got a 403, and every timecode opened on nothing."""

    NAMES = [
        "Participant #3.mp4",
        "Round #1/P?2 call.mov",
        "100% done.mp4",
        "50%41 off.mp4",  # a literal %41, which an unencoded path reads as "A"
        "Café 你好.m4a",
        "plain.mp4",
    ]

    @pytest.mark.parametrize("name", NAMES)
    def test_the_video_map_uri_plays_as_the_browser_resolves_it(
        self, tmp_path: Path, name: str,
    ) -> None:
        import shutil
        from urllib.parse import unquote, urljoin, urlsplit

        from bristlenose.server.models import Session as SessionModel
        from bristlenose.server.models import SourceFile

        project = tmp_path / "input"
        shutil.copytree(_FIXTURE_DIR, project)
        video = project / name
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"fake-media")
        app = create_app(project_dir=project, dev=False, db_url="sqlite://")
        db = app.state.db_factory()
        try:
            sess = db.query(SessionModel).filter_by(session_id="s1").one()
            db.add(SourceFile(session_id=sess.id, file_type="video", path=str(video), size_bytes=1))
            db.commit()
        finally:
            db.close()
        client = AuthTestClient(app)

        body = client.get("/api/projects/1/video-map").json()
        uri = body["video_map"]["s1"]

        # What the browser requests for `video.src = uri` on the player page:
        # the fragment and the query are not part of the request path.
        page = "http://127.0.0.1:8150" + body["player_url"]
        sent = urlsplit(urljoin(page, uri))
        # The server decodes a request path once (uvicorn does; verified against
        # a live one, 25 Oct 2026), and what it decodes to is the file's name.
        assert unquote(sent.path) == "/media/" + name, (uri, sent.path)
        if "%" in name:
            # Starlette's TestClient decodes a path twice, so a literal "%41"
            # reads back as "A" here and not on a real server: the check above
            # is the whole claim for these names.
            return
        resp = client.get(sent.path)
        assert resp.status_code == 200, (uri, sent.path)
        assert resp.content == b"fake-media"

    def test_a_recording_outside_the_project_folder_is_encoded_too(self, tmp_path: Path) -> None:
        from bristlenose.server.routes.sessions import _file_to_media_uri

        elsewhere = tmp_path / "elsewhere" / "Participant #3?.mp4"
        project = tmp_path / "project"
        project.mkdir()
        assert _file_to_media_uri(str(elsewhere), project) == "/media/Participant%20%233%3F.mp4"
        assert _file_to_media_uri(str(elsewhere), None) == "/media/Participant%20%233%3F.mp4"
