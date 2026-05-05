"""Tests for the React-bundle static serving in serve mode.

Replaces the previous Starlette ``StaticFiles`` mount with in-memory
``read_bytes`` routes — needed because the streaming path (sendfile /
aiofiles) returns 500 under macOS App Sandbox.  Tests cover the happy path,
the 404 fallthrough, the path-traversal guard, the cache headers, and the
``BRISTLENOSE_DEBUG_500`` exception-handler envelope.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bristlenose.server import app as app_module
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient


@pytest.fixture()
def static_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal Vite-style static tree and point ``_STATIC_DIR`` at it."""
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    (root / "assets" / "main-abc.js").write_text("export default 1;\n", encoding="utf-8")
    (root / "assets" / "main-abc.css").write_text(":root{color:red}\n", encoding="utf-8")
    (root / "assets" / "font.woff2").write_bytes(b"\x00\x01\x02woff2-bytes")
    monkeypatch.setattr(app_module, "_STATIC_DIR", root)
    return root


@pytest.fixture()
def client(static_root: Path) -> AuthTestClient:
    app = create_app(dev=False, db_url="sqlite://")
    return AuthTestClient(app)


class TestStaticServingHappyPath:
    def test_serves_js_with_correct_mime(self, client: AuthTestClient) -> None:
        resp = client.get("/static/assets/main-abc.js")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/javascript") or \
               resp.headers["content-type"].startswith("text/javascript")
        assert resp.text == "export default 1;\n"

    def test_serves_css(self, client: AuthTestClient) -> None:
        resp = client.get("/static/assets/main-abc.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")

    def test_serves_html(self, client: AuthTestClient) -> None:
        resp = client.get("/static/index.html")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "<html>ok</html>" in resp.text

    def test_serves_woff2_as_octet_or_font(self, client: AuthTestClient) -> None:
        resp = client.get("/static/assets/font.woff2")
        assert resp.status_code == 200
        # mimetypes may or may not know woff2 depending on platform — accept
        # either the registered font/woff2 or the octet-stream fallback.
        assert resp.headers["content-type"] in {
            "font/woff2",
            "application/font-woff2",
            "application/octet-stream",
        }
        assert resp.content == b"\x00\x01\x02woff2-bytes"

    def test_assets_alias_serves_same_file(self, client: AuthTestClient) -> None:
        """Vite's lazy-load runtime requests /assets/foo.js without /static prefix."""
        resp = client.get("/assets/main-abc.js")
        assert resp.status_code == 200
        assert resp.text == "export default 1;\n"

    def test_cache_control_immutable_for_hashed_chunks(
        self, client: AuthTestClient
    ) -> None:
        resp = client.get("/static/assets/main-abc.js")
        assert resp.headers.get("cache-control") == "public, max-age=31536000, immutable"

    def test_cache_control_no_cache_for_index_html(
        self, client: AuthTestClient
    ) -> None:
        # index.html is not content-hashed — must NOT be served immutable, or
        # bundle updates would be invisible to the WKWebView for up to a year.
        resp = client.get("/static/index.html")
        assert resp.headers.get("cache-control") == "no-cache"


class TestStaticServingMissing:
    def test_missing_file_returns_404(self, client: AuthTestClient) -> None:
        resp = client.get("/static/assets/does-not-exist.js")
        assert resp.status_code == 404

    def test_missing_file_under_assets_alias_returns_404(self, client: AuthTestClient) -> None:
        resp = client.get("/assets/does-not-exist.js")
        assert resp.status_code == 404


class TestStaticServingPathTraversal:
    @pytest.mark.parametrize(
        "path",
        [
            "/static/../etc/passwd",
            "/static/assets/../../etc/passwd",
            "/assets/../../etc/passwd",
        ],
    )
    def test_traversal_rejected(self, client: AuthTestClient, path: str) -> None:
        resp = client.get(path)
        # Starlette may normalise some traversal attempts before they reach our
        # route (returning 404), and our guard rejects the rest with 403.
        # Either is acceptable — what matters is we never serve the target.
        assert resp.status_code in {403, 404}


class TestDebug500Envelope:
    """Tracebacks surface in the response body only when BOTH dev=True AND
    BRISTLENOSE_DEBUG_500=1.  Either gate alone keeps the generic message —
    so a stale env var in a shipping (non-dev) sidecar can't leak traces."""

    def test_dev_plus_envvar_returns_traceback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import FastAPI

        from bristlenose.server.app import create_app

        monkeypatch.setenv("BRISTLENOSE_DEBUG_500", "1")
        app: FastAPI = create_app(dev=True, db_url="sqlite://")

        @app.get("/_boom")
        async def _boom() -> None:
            raise RuntimeError("kaboom")

        client = AuthTestClient(app, raise_server_exceptions=False)
        resp = client.get("/_boom")
        assert resp.status_code == 500
        assert "RuntimeError" in resp.text
        assert "kaboom" in resp.text

    def test_envvar_without_dev_returns_generic_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import FastAPI

        from bristlenose.server.app import create_app

        monkeypatch.setenv("BRISTLENOSE_DEBUG_500", "1")
        app: FastAPI = create_app(dev=False, db_url="sqlite://")

        @app.get("/_boom")
        async def _boom() -> None:
            raise RuntimeError("kaboom")

        client = AuthTestClient(app, raise_server_exceptions=False)
        resp = client.get("/_boom")
        assert resp.status_code == 500
        assert "kaboom" not in resp.text
        assert "Internal Server Error" in resp.text

    def test_no_envvar_returns_generic_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import FastAPI

        from bristlenose.server.app import create_app

        monkeypatch.delenv("BRISTLENOSE_DEBUG_500", raising=False)
        app: FastAPI = create_app(dev=True, db_url="sqlite://")

        @app.get("/_boom")
        async def _boom() -> None:
            raise RuntimeError("kaboom")

        client = AuthTestClient(app, raise_server_exceptions=False)
        resp = client.get("/_boom")
        assert resp.status_code == 500
        assert "kaboom" not in resp.text
        assert "Internal Server Error" in resp.text
