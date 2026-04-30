"""Tests for the bristlenose serve command and FastAPI server."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose import __version__
from bristlenose.server.app import create_app
from bristlenose.server.db import Base, get_engine, init_db
from tests.conftest import AuthTestClient


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with an in-memory SQLite database."""
    app = create_app(dev=True, db_url="sqlite://")
    return AuthTestClient(app)


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

    def test_returns_default_links_and_feedback(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("BRISTLENOSE_GITHUB_ISSUES_URL", raising=False)
        monkeypatch.delenv("BRISTLENOSE_FEEDBACK_ENABLED", raising=False)
        monkeypatch.delenv("BRISTLENOSE_FEEDBACK_URL", raising=False)
        data = client.get("/api/health").json()
        assert (
            data["links"]["github_issues_url"]
            == "https://github.com/cassiocassio/bristlenose/issues/new"
        )
        assert data["feedback"]["enabled"] is True
        assert data["feedback"]["url"] == "https://bristlenose.app/feedback.php"

    def test_respects_feedback_env_overrides(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("BRISTLENOSE_GITHUB_ISSUES_URL", "https://example.com/issues/new")
        monkeypatch.setenv("BRISTLENOSE_FEEDBACK_ENABLED", "false")
        monkeypatch.setenv("BRISTLENOSE_FEEDBACK_URL", "https://example.com/feedback")
        data = client.get("/api/health").json()
        assert data["links"]["github_issues_url"] == "https://example.com/issues/new"
        assert data["feedback"]["enabled"] is False
        assert data["feedback"]["url"] == "https://example.com/feedback"

    def test_telemetry_dev_default_points_at_local_stub(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """In dev mode, health advertises the local /api/dev/telemetry stub."""
        monkeypatch.delenv("BRISTLENOSE_TELEMETRY_ENABLED", raising=False)
        monkeypatch.delenv("BRISTLENOSE_TELEMETRY_URL", raising=False)
        data = client.get("/api/health").json()
        assert data["telemetry"]["enabled"] is True
        assert data["telemetry"]["url"] == "/api/dev/telemetry"

    def test_telemetry_non_dev_default_points_at_production(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without --dev, health advertises the production PHP endpoint."""
        monkeypatch.delenv("BRISTLENOSE_TELEMETRY_ENABLED", raising=False)
        monkeypatch.delenv("BRISTLENOSE_TELEMETRY_URL", raising=False)
        app = create_app(dev=False, db_url="sqlite://")
        non_dev_client = AuthTestClient(app)
        data = non_dev_client.get("/api/health").json()
        assert data["telemetry"]["enabled"] is True
        assert data["telemetry"]["url"] == "https://bristlenose.app/telemetry.php"

    def test_respects_telemetry_env_overrides(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("BRISTLENOSE_TELEMETRY_ENABLED", "false")
        monkeypatch.setenv("BRISTLENOSE_TELEMETRY_URL", "https://example.com/telemetry.php")
        data = client.get("/api/health").json()
        assert data["telemetry"]["enabled"] is False
        assert data["telemetry"]["url"] == "https://example.com/telemetry.php"


class TestDevTelemetryStub:
    """The /api/dev/telemetry stub — stands in for bristlenose.app/telemetry.php."""

    @pytest.fixture(autouse=True)
    def _clean_jsonl(self, client: TestClient) -> None:
        """Truncate the PID-scoped JSONL between tests so ordering is deterministic."""
        client.delete("/api/dev/telemetry")

    def _event(
        self,
        *,
        tag_id: str = "usability-problem",
        prompt_version: str = "usability-problem-abcd1234",
        event_type: str = "rejected",
        researcher_id: str = "11111111-1111-1111-1111-111111111111",
    ) -> dict[str, str]:
        return {
            "tag_id": tag_id,
            "prompt_version": prompt_version,
            "event_type": event_type,
            "researcher_id": researcher_id,
        }

    def test_post_accepts_valid_batch(self, client: TestClient) -> None:
        resp = client.post(
            "/api/dev/telemetry",
            json={"events": [self._event(), self._event(event_type="accepted")]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["received"] == 2
        # PID-scoped filename, e.g. bristlenose-dev-telemetry-12345.jsonl
        assert "bristlenose-dev-telemetry-" in body["written_to"]
        assert body["written_to"].endswith(".jsonl")

    def test_get_returns_previously_posted_events(self, client: TestClient) -> None:
        client.post("/api/dev/telemetry", json={"events": [self._event()]})
        client.post("/api/dev/telemetry", json={"events": [self._event(event_type="edited")]})
        resp = client.get("/api/dev/telemetry")
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert [e["event_type"] for e in events] == ["rejected", "edited"]

    def test_delete_truncates_jsonl(self, client: TestClient) -> None:
        client.post("/api/dev/telemetry", json={"events": [self._event()]})
        client.delete("/api/dev/telemetry")
        resp = client.get("/api/dev/telemetry")
        assert resp.json()["events"] == []

    def test_rejects_non_list_events(self, client: TestClient) -> None:
        resp = client.post("/api/dev/telemetry", json={"events": "nope"})
        assert resp.status_code == 422

    def test_rejects_empty_batch(self, client: TestClient) -> None:
        resp = client.post("/api/dev/telemetry", json={"events": []})
        assert resp.status_code == 422

    def test_rejects_missing_required_field(self, client: TestClient) -> None:
        bad = self._event()
        del bad["tag_id"]
        resp = client.post("/api/dev/telemetry", json={"events": [bad]})
        assert resp.status_code == 422
        assert any("tag_id" in str(err) for err in resp.json()["detail"])

    def test_rejects_unknown_event_type(self, client: TestClient) -> None:
        resp = client.post(
            "/api/dev/telemetry",
            json={"events": [self._event(event_type="liked")]},
        )
        assert resp.status_code == 422

    def test_rejects_unknown_field(self, client: TestClient) -> None:
        """Enforces the methodology doc's 'Four fields. Nothing else.' invariant."""
        bad = self._event()
        bad["timestamp"] = "2026-04-24T12:00:00Z"
        resp = client.post("/api/dev/telemetry", json={"events": [bad]})
        assert resp.status_code == 422
        assert any("timestamp" in str(err) or "extra" in str(err).lower()
                   for err in resp.json()["detail"])

    def test_rejects_batch_larger_than_max(self, client: TestClient) -> None:
        """Caps batch size to prevent amplification DoS."""
        events = [self._event(researcher_id=f"r-{i:04d}") for i in range(501)]
        resp = client.post("/api/dev/telemetry", json={"events": events})
        assert resp.status_code == 422

    def test_accepts_batch_at_max_size(self, client: TestClient) -> None:
        events = [self._event(researcher_id=f"r-{i:04d}") for i in range(500)]
        resp = client.post("/api/dev/telemetry", json={"events": events})
        assert resp.status_code == 200
        assert resp.json()["received"] == 500

    def test_stub_absent_without_dev_flag(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When --dev is off, the stub endpoint isn't mounted."""
        app = create_app(dev=False, db_url="sqlite://")
        non_dev_client = AuthTestClient(app)
        resp = non_dev_client.post(
            "/api/dev/telemetry",
            json={"events": [self._event()]},
        )
        assert resp.status_code == 404

    def test_stub_requires_bearer_token(self) -> None:
        """Regression tripwire: /api/dev/telemetry must never leak into auth exemptions.

        The dev stub is local-dev-only, but it writes to disk — a future change
        to `_AUTH_EXEMPT_PREFIXES` in middleware.py that accidentally covers
        `/api/dev/` would let any browser tab POST forged events. Guard it.
        """
        app = create_app(dev=True, db_url="sqlite://")
        raw = TestClient(app)  # no auth header
        assert raw.post("/api/dev/telemetry", json={"events": [self._event()]}).status_code == 401
        assert raw.get("/api/dev/telemetry").status_code == 401
        assert raw.delete("/api/dev/telemetry").status_code == 401


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
        return AuthTestClient(app)

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
        """Files with extensions in the output dir are served as assets.

        Special case: the theme CSS route falls back to the bundled default
        when the per-project file doesn't exist (commit 9e6224b — without
        this, brand-new projects render the SPA unstyled). So an empty
        output dir still serves CSS, just from the package source rather
        than the project's rendered assets.
        """
        resp = prod_client.get("/report/assets/bristlenose-theme.css")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/css")
        # Bundled fallback marker — present in load_default_css() output.
        assert "default research report theme" in resp.text

        # Other missing asset paths still 404 — fallback is theme-CSS only.
        resp = prod_client.get("/report/assets/missing-thumbnail.png")
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

    def test_no_bundle_returns_500_fail_loud(self, tmp_path: Path) -> None:
        """When no React bundle exists, fail loud with 500 — don't fall back
        to the deprecated static render.

        Updated 21 Apr 2026 (P1 from c3-bundle-completeness): previously
        this fell back to static-rendered HTML, which masked BUG-3 in the
        C3 smoke test (broken bundle appeared to "work" but served the
        deprecated UI). Static render is vestigial scaffolding being
        phased out, not a serve-mode degradation path.
        """
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()
        # Even if a static-rendered HTML exists on disk, serve mode must
        # NOT fall back to it.
        report = output_dir / "bristlenose-test-report.html"
        report.write_text("<html><body>vanilla report</body></html>")

        empty_static = tmp_path / "empty-static"
        empty_static.mkdir()

        with patch("bristlenose.server.app._STATIC_DIR", empty_static):
            app = create_app(
                project_dir=tmp_path, dev=False, db_url="sqlite://"
            )
        client = TestClient(app)
        resp = client.get("/report/")
        assert resp.status_code == 500
        # Error page should clearly identify the build issue
        assert "Build incomplete" in resp.text or "bundle" in resp.text.lower()
        # Must NOT have served the static-rendered content
        assert "vanilla report" not in resp.text


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
        return AuthTestClient(app)

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
    def dev_client(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        """Create a test client in HMR dev mode (serve --dev) with an output dir."""
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir()

        # serve --dev sets this env var before calling create_app via uvicorn reload
        monkeypatch.setenv("_BRISTLENOSE_DEV", "1")
        app = create_app(project_dir=tmp_path, dev=True, db_url="sqlite://")
        return AuthTestClient(app)

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
