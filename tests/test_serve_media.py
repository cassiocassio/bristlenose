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

    def test_vtt(self, client: TestClient) -> None:
        assert client.get("/media/subs.vtt").status_code == 200

    def test_jpg(self, client: TestClient) -> None:
        assert client.get("/media/thumb.jpg").status_code == 200

    def test_nested_subdir(self, client: TestClient) -> None:
        assert client.get("/media/subdir/nested.mp4").status_code == 200


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
