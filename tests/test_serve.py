"""Tests for the bristlenose serve command and FastAPI server."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose import __version__
from bristlenose.server.app import create_app
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

    def test_project_dir_stored_on_app_state(self, tmp_path: Path) -> None:
        """project_dir should be accessible via app.state."""
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        assert app.state.project_dir == tmp_path


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
# Vite build index.html fixture
# ---------------------------------------------------------------------------

_VITE_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <script type="module" crossorigin src="/assets/main-abc123.js"></script>
    <link rel="modulepreload" crossorigin href="/assets/SessionsTable-def456.js">
  </head>
  <body><div id="bn-app-root" data-project-id="1"></div></body>
</html>
"""


class TestProdServeReport:
    """Integration tests for production serve mode — SPA serving."""

    @pytest.fixture()
    def prod_client(self, tmp_path: Path) -> TestClient:
        """Create a test client in production mode with a Vite build."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()

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

    def test_report_contains_app_root(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        assert resp.status_code == 200
        assert 'id="bn-app-root"' in resp.text

    def test_report_contains_bundle_script(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        assert "/static/assets/main-abc123.js" in resp.text

    def test_report_contains_theme_css(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        assert "bristlenose-theme.css" in resp.text

    def test_report_has_no_dev_features(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report/")
        html = resp.text
        assert "localhost:5173" not in html
        assert "@vite/client" not in html
        assert "RefreshRuntime" not in html

    def test_report_redirect(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/report", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "/report/"

    def test_spa_routes_return_html(self, prod_client: TestClient) -> None:
        """All non-asset /report/* paths return SPA HTML."""
        for path in ["/report/quotes", "/report/sessions/s1", "/report/codebook"]:
            resp = prod_client.get(path)
            assert resp.status_code == 200
            assert 'id="bn-app-root"' in resp.text

    def test_output_dir_assets_served(self, prod_client: TestClient) -> None:
        """Files with extensions in the output dir are served as assets."""
        # The output dir was created but is empty — expect 404 for missing asset
        resp = prod_client.get("/report/assets/bristlenose-theme.css")
        assert resp.status_code == 404

    def test_existing_output_asset_served(self, tmp_path: Path) -> None:
        """An actual file in the output dir is served via FileResponse."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()
        assets_dir = output_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "bristlenose-theme.css").write_text("body { color: red; }")

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)

        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(
                project_dir=tmp_path, dev=False, db_url="sqlite://"
            )
        client = TestClient(app)
        resp = client.get("/report/assets/bristlenose-theme.css")
        assert resp.status_code == 200
        assert "color: red" in resp.text

    def test_no_bundle_falls_back_to_static(self, tmp_path: Path) -> None:
        """When no React bundle exists, serve vanilla HTML from output dir."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()
        report = output_dir / "bristlenose-test-report.html"
        report.write_text("<html><body>vanilla report</body></html>")
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
        assert "vanilla report" in resp.text


class TestProdServeTranscript:
    """Transcript paths now serve SPA HTML (React Router handles routing)."""

    @pytest.fixture()
    def prod_client(self, tmp_path: Path) -> TestClient:
        """Create a test client with a Vite build and output dir."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()

        # Create a transcript file in the output dir (legacy artifact)
        sessions_dir = output_dir / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "transcript_s1.html").write_text("<html>transcript</html>")

        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)
        assets_dir = static_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "main-abc123.js").write_text("// react bundle")

        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(
                project_dir=tmp_path, dev=False, db_url="sqlite://"
            )
        return TestClient(app)

    def test_transcript_html_served_as_file(self, prod_client: TestClient) -> None:
        """Transcript HTML files are served from the output dir (file extension)."""
        resp = prod_client.get("/report/sessions/transcript_s1.html")
        assert resp.status_code == 200
        assert "transcript" in resp.text

    def test_session_path_serves_spa(self, prod_client: TestClient) -> None:
        """Session paths without extension serve SPA HTML for React Router."""
        resp = prod_client.get("/report/sessions/s1")
        assert resp.status_code == 200
        assert 'id="bn-app-root"' in resp.text

    def test_missing_html_file_returns_404(self, prod_client: TestClient) -> None:
        """Missing HTML files return 404 (not SPA HTML)."""
        resp = prod_client.get("/report/sessions/transcript_s99.html")
        assert resp.status_code == 404


class TestDevServeReport:
    """Integration tests for dev serve mode — Vite HMR scripts."""

    @pytest.fixture()
    def dev_client(self, tmp_path: Path) -> TestClient:
        """Create a test client in dev mode with an output dir."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()

        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        return TestClient(app)

    def test_dev_report_contains_app_root(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/report/")
        assert resp.status_code == 200
        assert 'id="bn-app-root"' in resp.text

    def test_dev_report_has_vite_scripts(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/report/")
        html = resp.text
        assert "localhost:5173" in html
        assert "@vite/client" in html
        assert "RefreshRuntime" in html
        assert "src/main.tsx" in html

    def test_dev_report_has_theme_css(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/report/")
        assert "bristlenose-theme.css" in resp.text

    def test_dev_report_redirect(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/report", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "/report/"

    def test_dev_spa_routes_return_html(self, dev_client: TestClient) -> None:
        """All non-asset /report/* paths return dev HTML."""
        for path in ["/report/quotes", "/report/sessions/s1", "/report/codebook"]:
            resp = dev_client.get(path)
            assert resp.status_code == 200
            assert 'id="bn-app-root"' in resp.text
