"""The unauthenticated file-serving routes must not leak the project's private files.

``/report/*`` and ``/media/*`` are deliberately outside the bearer-token gate
(the WKWebView and ``<video>`` load them without an Authorization header), so
the only thing standing between a local process and the files on disk is the
path guard. These tests use a bare ``TestClient`` — no token — because that is
exactly what such a caller has.

What must never be reachable (root ``CLAUDE.md``): ``.bristlenose/pii_summary.txt``
and ``.bristlenose/llm-calls.jsonl``, both re-identification keys; and nothing
outside the served root at all.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

_VITE_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head><script type="module" crossorigin src="/assets/main-abc123.js"></script></head>
  <body><div id="bn-app-root" data-project-id="1"></div></body>
</html>
"""

_PII_KEY = "Sarah Jones -> [NAME] at 00:01:23"
_OUTSIDE = "outside the output dir"


def _seed_project(project_dir: Path) -> None:
    """A project with the private files a real run leaves behind."""
    (project_dir / "outside.txt").write_text(_OUTSIDE)

    output_dir = project_dir / "bristlenose-output"
    internal = output_dir / ".bristlenose"
    internal.mkdir(parents=True)
    (internal / "pii_summary.txt").write_text(_PII_KEY)
    (internal / "llm-calls.jsonl").write_text('{"session_id": "s1"}\n')
    (internal / "report.css").write_text("/* a dotdir file with an allowed suffix */")

    assets = output_dir / "assets"
    (assets / "thumbnails").mkdir(parents=True)
    (assets / "bristlenose-theme.css").write_text("body { color: red; }")
    (assets / "bristlenose-logo.png").write_bytes(b"\x89PNG fake")
    (assets / "bristlenose-player.html").write_text("<!doctype html><title>player</title>")
    (assets / "thumbnails" / "s1.jpg").write_bytes(b"fake-jpg")
    # A symlink inside the served root that points out of it, and one that
    # stays inside the output dir but lands in the dot-directory.
    (assets / "escape.css").symlink_to(project_dir / "outside.txt")
    (assets / "leak.css").symlink_to(Path("..") / ".bristlenose" / "report.css")
    (output_dir / "report.css").write_text("/* output root, outside assets/ */")
    # Inside /media/'s root (the project dir), lands on the key — refused on
    # suffix since /media/ became recordings-only.
    (project_dir / "notes.txt").symlink_to(
        Path("bristlenose-output") / ".bristlenose" / "pii_summary.txt"
    )
    # Allowed suffix at both ends, lands in the dot-directory — only the
    # post-resolve dot check stops this one.
    (internal / "cache.wav").write_bytes(b"dotdir audio")
    (project_dir / "clip.wav").symlink_to(
        Path("bristlenose-output") / ".bristlenose" / "cache.wav"
    )
    (output_dir / "bristlenose-x-report.html").write_text("<p>static report: Sarah Jones</p>")

    (output_dir / "people.yaml").write_text("participants:\n  p1: {full_name: Sarah Jones}\n")
    (output_dir / "sessions").mkdir()
    (output_dir / "sessions" / "transcript_s1.html").write_text("<p>transcript</p>")


@pytest.fixture(params=["prod", "dev"])
def client(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Unauthenticated client against the prod mount and the ``serve --dev`` mount."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _seed_project(project_dir)

    if request.param == "dev":
        monkeypatch.setenv("_BRISTLENOSE_DEV", "1")
        app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    else:
        monkeypatch.delenv("_BRISTLENOSE_DEV", raising=False)
        static_dir = tmp_path / "static"
        (static_dir / "assets").mkdir(parents=True)
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)
        (static_dir / "assets" / "main-abc123.js").write_text("// bundle")
        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(project_dir=project_dir, dev=False, db_url="sqlite://")
    yield TestClient(app, base_url="http://127.0.0.1")


class TestReportPrivateFilesRefused:
    @pytest.mark.parametrize(
        "url",
        [
            "/report/.bristlenose/pii_summary.txt",
            "/report/.bristlenose/llm-calls.jsonl",
            # An allowed suffix does not make a dot-directory servable.
            "/report/.bristlenose/report.css",
            "/report/%2Ebristlenose/pii_summary.txt",
            "/report/assets/leak.css",
            "/report/assets/%2E%2E/.bristlenose/report.css",
        ],
    )
    def test_dot_directory(self, client: TestClient, url: str) -> None:
        resp = client.get(url)
        assert resp.status_code == 404
        assert _PII_KEY not in resp.text

    @pytest.mark.parametrize(
        "url",
        [
            "/report/..%2Foutside.txt",
            "/report/%2E%2E/outside.txt",
            "/report/assets/..%2F..%2Foutside.txt",
            "/report/assets/escape.css",
        ],
    )
    def test_escape_from_output_dir(self, client: TestClient, url: str) -> None:
        resp = client.get(url)
        assert resp.status_code == 404
        assert _OUTSIDE not in resp.text

    @pytest.mark.parametrize(
        "url",
        [
            # people.yaml carries real names; the SPA never loads it.
            "/report/people.yaml",
            # The SPA loads only from assets/ — the static report and
            # transcript pages are full-name-bearing and not served.
            "/report/bristlenose-x-report.html",
            "/report/sessions/transcript_s1.html",
            "/report/report.css",
            "/report/assets/thumbnails/s1.txt",
        ],
    )
    def test_outside_the_asset_allowlist(self, client: TestClient, url: str) -> None:
        resp = client.get(url)
        assert resp.status_code == 404
        assert "Sarah Jones" not in resp.text

    def test_nul_byte_is_not_a_server_error(self, client: TestClient) -> None:
        assert client.get("/report/assets/x.css%00").status_code == 404


class TestReportAssetsStillServed:
    @pytest.mark.parametrize(
        "url",
        [
            "/report/assets/bristlenose-logo.png",
            "/report/assets/bristlenose-player.html",
            "/report/assets/thumbnails/s1.jpg",
        ],
    )
    def test_legitimate_asset(self, client: TestClient, url: str) -> None:
        assert client.get(url).status_code == 200

    def test_theme_css(self, client: TestClient) -> None:
        assert client.get("/report/assets/bristlenose-theme.css").status_code == 200


class TestMediaPrivateFilesRefused:
    """``/media/`` serves the whole project dir and allows ``.txt`` — the same key."""

    @pytest.mark.parametrize(
        "url",
        [
            "/media/bristlenose-output/.bristlenose/pii_summary.txt",
            "/media/bristlenose-output/%2Ebristlenose/pii_summary.txt",
            "/media/notes.txt",
        ],
    )
    def test_dot_directory(self, client: TestClient, url: str) -> None:
        resp = client.get(url)
        assert resp.status_code in (403, 404)
        assert _PII_KEY not in resp.text

    def test_symlink_into_dot_directory(self, client: TestClient) -> None:
        resp = client.get("/media/clip.wav")
        assert resp.status_code == 403
        assert b"dotdir audio" not in resp.content

    def test_media_still_served(self, client: TestClient) -> None:
        (Path(client.app.state.project_dir) / "interview.mp4").write_bytes(b"fake-mp4")
        assert client.get("/media/interview.mp4").status_code == 200
