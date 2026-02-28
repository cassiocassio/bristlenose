"""Tests for the bristlenose serve command and FastAPI server."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose import __version__
from bristlenose.server.app import (
    _extract_bundle_tags,
    _strip_vanilla_js,
    _transform_report_html,
    _transform_transcript_html,
    create_app,
)
from bristlenose.server.db import Base, get_engine, init_db


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with an in-memory SQLite database."""
    app = create_app(dev=True, db_url="sqlite://")
    return TestClient(app)


@pytest.fixture()
def engine():
    """Create an in-memory SQLAlchemy engine for database tests."""
    return get_engine("sqlite://")


class TestHealthEndpoint:
    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_returns_version(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert data["version"] == __version__

    def test_returns_status(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert data["status"] == "ok"


class TestDatabase:
    def test_init_db_creates_tables(self, engine) -> None:  # type: ignore[no-untyped-def]
        init_db(engine)
        table_names = Base.metadata.tables.keys()
        assert "projects" in table_names

    def test_init_db_is_idempotent(self, engine) -> None:  # type: ignore[no-untyped-def]
        init_db(engine)
        init_db(engine)  # should not raise


class TestAppFactory:
    def test_create_app_returns_fastapi(self) -> None:
        from fastapi import FastAPI

        app = create_app(dev=True, db_url="sqlite://")
        assert isinstance(app, FastAPI)

    def test_create_app_without_project_dir(self) -> None:
        """App should work without a project directory (no report to serve)."""
        app = create_app(dev=True, db_url="sqlite://")
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200


class TestServeCommand:
    def test_serve_in_commands_set(self) -> None:
        from bristlenose.cli import _COMMANDS

        assert "serve" in _COMMANDS

    def test_serve_help_works(self) -> None:
        """The serve --help should run without errors."""
        from typer.testing import CliRunner

        from bristlenose.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output.lower()


# ---------------------------------------------------------------------------
# Minimal HTML fragments for unit tests
# ---------------------------------------------------------------------------

_REPORT_HTML = """\
<html><head></head><body>
<!-- bn-app -->
<nav>old nav</nav>
<!-- bn-dashboard --><div>old dashboard</div><!-- /bn-dashboard -->
<!-- bn-session-table --><table>old</table><!-- /bn-session-table -->
<!-- bn-quote-sections --><div>old sections</div><!-- /bn-quote-sections -->
<!-- bn-quote-themes --><div>old themes</div><!-- /bn-quote-themes -->
<!-- bn-codebook --><div>old codebook</div><!-- /bn-codebook -->
<!-- /bn-app -->
<script>
(function() {
var BRISTLENOSE_VIDEO_MAP = {"s1":"/media/s1.mp4"};
var BN_PARTICIPANTS = {};
window.BRISTLENOSE_ANALYSIS = {"signals":[]};
window.BRISTLENOSE_VIDEO_MAP = BRISTLENOSE_VIDEO_MAP;
window.BRISTLENOSE_PLAYER_URL = 'assets/bristlenose-player.html';
/* bristlenose report.js — auto-generated from bristlenose/theme/js/ */

// --- js/storage.js ---
function initStorage() { console.log("storage"); }

// --- js/main.js ---
function initMain() { initStorage(); }
})();
</script>
</body></html>
"""

_TRANSCRIPT_HTML = """\
<html><head></head><body>
<!-- bn-transcript-page --><div>old transcript</div><!-- /bn-transcript-page -->
</body></html>
"""

_VITE_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <script type="module" crossorigin src="/assets/main-abc123.js"></script>
    <link rel="modulepreload" crossorigin href="/assets/SessionsTable-def456.js">
  </head>
  <body><div id="bn-react-root"></div></body>
</html>
"""


class TestExtractBundleTags:
    def test_rewrites_asset_paths(self, tmp_path: Path) -> None:
        index = tmp_path / "index.html"
        index.write_text(_VITE_INDEX_HTML)
        with patch("bristlenose.server.app._STATIC_DIR", tmp_path):
            result = _extract_bundle_tags()
        assert "/static/assets/main-abc123.js" in result
        assert "/static/assets/SessionsTable-def456.js" in result
        # Original /assets/ paths should not appear
        assert 'src="/assets/' not in result
        assert 'href="/assets/' not in result

    def test_returns_empty_when_no_build(self, tmp_path: Path) -> None:
        with patch("bristlenose.server.app._STATIC_DIR", tmp_path):
            assert _extract_bundle_tags() == ""

    def test_preserves_attributes(self, tmp_path: Path) -> None:
        index = tmp_path / "index.html"
        index.write_text(_VITE_INDEX_HTML)
        with patch("bristlenose.server.app._STATIC_DIR", tmp_path):
            result = _extract_bundle_tags()
        assert "crossorigin" in result
        assert 'type="module"' in result
        assert 'rel="modulepreload"' in result


class TestTransformReportHtml:
    def test_swaps_bn_app_markers(self) -> None:
        result = _transform_report_html(_REPORT_HTML, project_dir=None)
        assert 'id="bn-app-root"' in result
        # Original content inside bn-app markers should be gone
        assert "old nav" not in result
        assert "old dashboard" not in result
        assert "old sections" not in result

    def test_strips_vanilla_js_modules(self) -> None:
        result = _transform_report_html(_REPORT_HTML, project_dir=None)
        # Module code should be stripped
        assert "initStorage" not in result
        assert "initMain" not in result
        assert "js/storage.js" not in result
        # Globals should survive
        assert "window.BRISTLENOSE_VIDEO_MAP" in result
        assert "window.BRISTLENOSE_PLAYER_URL" in result
        assert "window.BRISTLENOSE_ANALYSIS" in result

    def test_injects_api_base(self) -> None:
        result = _transform_report_html(_REPORT_HTML, project_dir=None)
        assert "window.BRISTLENOSE_API_BASE" in result

    def test_preserves_structure(self) -> None:
        result = _transform_report_html(_REPORT_HTML, project_dir=None)
        assert "</body>" in result
        assert "</html>" in result


class TestTransformTranscriptHtml:
    def test_swaps_transcript_marker(self) -> None:
        result = _transform_transcript_html(
            _TRANSCRIPT_HTML, session_id="s3", project_dir=None
        )
        assert 'id="bn-transcript-page-root"' in result
        assert 'data-session-id="s3"' in result
        assert "old transcript" not in result

    def test_injects_api_base(self) -> None:
        result = _transform_transcript_html(
            _TRANSCRIPT_HTML, session_id="s1", project_dir=None
        )
        assert "window.BRISTLENOSE_API_BASE" in result


class TestStripVanillaJs:
    """Tests for _strip_vanilla_js() — Step 8 vanilla JS retirement."""

    _HTML_WITH_IIFE = """\
<html><head></head><body>
<script>
(function() {
var BRISTLENOSE_VIDEO_MAP = {"s1":"/media/s1.mp4"};
window.BRISTLENOSE_VIDEO_MAP = BRISTLENOSE_VIDEO_MAP;
window.BRISTLENOSE_PLAYER_URL = 'assets/bristlenose-player.html';
/* bristlenose report.js — auto-generated from bristlenose/theme/js/ */

// --- js/storage.js ---
function initStorage() { console.log("storage"); }

// --- js/main.js ---
function initMain() { initStorage(); }
})();
</script>
</body></html>
"""

    def test_removes_module_code(self) -> None:
        result = _strip_vanilla_js(self._HTML_WITH_IIFE)
        assert "initStorage" not in result
        assert "initMain" not in result
        assert "js/storage.js" not in result
        assert "js/main.js" not in result

    def test_keeps_globals(self) -> None:
        result = _strip_vanilla_js(self._HTML_WITH_IIFE)
        assert "window.BRISTLENOSE_VIDEO_MAP" in result
        assert "window.BRISTLENOSE_PLAYER_URL" in result
        assert "BRISTLENOSE_VIDEO_MAP" in result

    def test_keeps_iife_structure(self) -> None:
        result = _strip_vanilla_js(self._HTML_WITH_IIFE)
        assert "(function() {" in result
        assert "})();" in result
        assert "<script>" in result
        assert "</script>" in result

    def test_noop_without_marker(self) -> None:
        html = "<html><body><script>alert(1);</script></body></html>"
        assert _strip_vanilla_js(html) == html

    def test_noop_without_iife_close(self) -> None:
        html = (
            "<html><body><script>"
            "/* bristlenose report.js — auto-generated from bristlenose/theme/js/ */"
            "some code</script></body></html>"
        )
        assert _strip_vanilla_js(html) == html

    def test_preserves_analysis_global(self) -> None:
        html = """\
<script>
(function() {
window.BRISTLENOSE_ANALYSIS = {"signals":[{"location":"Login"}]};
/* bristlenose report.js — auto-generated from bristlenose/theme/js/ */

// --- js/main.js ---
function init() {}
})();
</script>
"""
        result = _strip_vanilla_js(html)
        assert "BRISTLENOSE_ANALYSIS" in result
        assert '"Login"' in result
        assert "function init" not in result


class TestProdServeReport:
    """Integration tests for production serve mode with React islands."""

    @pytest.fixture()
    def prod_client(self, tmp_path: Path) -> TestClient:
        """Create a test client in production mode with a mock report."""
        # Set up mock output directory with a report file
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()
        report = output_dir / "bristlenose-test-report.html"
        report.write_text(_REPORT_HTML)
        (output_dir / "index.html").symlink_to(report.name)

        # Set up mock static directory with a built index.html
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)
        assets_dir = static_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "main-abc123.js").write_text("// react bundle")
        (assets_dir / "SessionsTable-def456.js").write_text("// chunk")

        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(
                project_dir=tmp_path, dev=False, db_url="sqlite://"
            )
        return TestClient(app)

    def test_report_contains_react_app_root(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        assert resp.status_code == 200
        assert 'id="bn-app-root"' in resp.text
        # Original island content should be gone
        assert "old dashboard" not in resp.text

    def test_report_contains_bundle_script(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        assert "/static/assets/main-abc123.js" in resp.text

    def test_report_contains_api_base(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        assert "window.BRISTLENOSE_API_BASE" in resp.text

    def test_report_has_no_dev_features(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        html = resp.text
        assert "localhost:5173" not in html
        assert "@vite/client" not in html
        assert "bn-dev-overlay-toggle" not in html
        assert "RefreshRuntime" not in html

    def test_report_redirect(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "/report/"

    def test_no_bundle_falls_back_to_static(self, tmp_path: Path) -> None:
        """When no React bundle exists, serve vanilla HTML without mount divs."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()
        report = output_dir / "bristlenose-test-report.html"
        report.write_text(_REPORT_HTML)
        (output_dir / "index.html").symlink_to(report.name)

        empty_static = tmp_path / "empty-static"
        empty_static.mkdir()

        with patch("bristlenose.server.app._STATIC_DIR", empty_static):
            app = create_app(
                project_dir=tmp_path, dev=False, db_url="sqlite://"
            )
        client = TestClient(app)
        resp = client.get("/report/")
        assert resp.status_code == 200
        # Should serve vanilla HTML — no React app root injected
        assert 'id="bn-app-root"' not in resp.text
        assert "old dashboard" in resp.text


class TestProdServeTranscript:
    """Integration tests for transcript pages in production serve mode."""

    @pytest.fixture()
    def prod_client(self, tmp_path: Path) -> TestClient:
        """Create a test client with a mock transcript page."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()
        report = output_dir / "bristlenose-test-report.html"
        report.write_text(_REPORT_HTML)
        (output_dir / "index.html").symlink_to(report.name)

        sessions_dir = output_dir / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "transcript_s1.html").write_text(_TRANSCRIPT_HTML)

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)
        assets_dir = static_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "main-abc123.js").write_text("// react bundle")
        (assets_dir / "SessionsTable-def456.js").write_text("// chunk")

        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(
                project_dir=tmp_path, dev=False, db_url="sqlite://"
            )
        return TestClient(app)

    def test_transcript_contains_react_mount(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/sessions/transcript_s1.html")
        assert resp.status_code == 200
        assert 'id="bn-transcript-page-root"' in resp.text
        assert 'data-session-id="s1"' in resp.text

    def test_transcript_contains_bundle_script(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/sessions/transcript_s1.html")
        assert "/static/assets/main-abc123.js" in resp.text

    def test_transcript_has_no_dev_features(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/sessions/transcript_s1.html")
        assert "localhost:5173" not in resp.text

    def test_transcript_404_for_missing(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/sessions/transcript_s99.html")
        assert resp.status_code == 404

    def test_non_transcript_session_serves_spa(self, prod_client: TestClient) -> None:
        """Non-transcript session paths serve SPA HTML for React Router."""
        resp = prod_client.get("/report/sessions/notvalid.html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
