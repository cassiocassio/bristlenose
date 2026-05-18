"""Tests for the server-rendered status page intercept.

Covers both the pure helpers (``detect_status`` / ``render_page``) and the
end-to-end intercept that fires from ``/report/`` when the latest run isn't
in a state the SPA can render.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    append_event,
    events_path,
    new_run_id,
)
from bristlenose.server.app import create_app
from bristlenose.server.status_page import (
    StatusInfo,
    detect_status,
    render_page,
)
from bristlenose.ui_kinds import MessageKind
from tests.conftest import AuthTestClient


def _seed_completed(output_dir: Path) -> None:
    """Write a RunCompletedEvent so the watcher seeds ``app.state.last_run``."""
    append_event(
        events_path(output_dir),
        RunCompletedEvent(
            ts="2026-05-10T20:00:00Z",
            run_id=new_run_id(),
            kind=KindEnum.RUN,
            started_at="2026-05-10T19:00:00Z",
            ended_at="2026-05-10T20:00:00Z",
        ),
    )


def _seed_failed(output_dir: Path, *, message: str = "Provider returned 503") -> None:
    append_event(
        events_path(output_dir),
        RunFailedEvent(
            ts="2026-05-10T20:00:00Z",
            run_id=new_run_id(),
            kind=KindEnum.RUN,
            started_at="2026-05-10T19:00:00Z",
            ended_at="2026-05-10T20:00:00Z",
            cause=Cause(
                category=CauseCategoryEnum.API_SERVER,
                code="503",
                stage="s10_quote_extraction",
                provider="anthropic",
                message=message,
            ),
        ),
    )


def _seed_cancelled(output_dir: Path) -> None:
    append_event(
        events_path(output_dir),
        RunCancelledEvent(
            ts="2026-05-10T20:00:00Z",
            run_id=new_run_id(),
            kind=KindEnum.RUN,
            started_at="2026-05-10T19:00:00Z",
            ended_at="2026-05-10T20:00:00Z",
            cause=Cause(category=CauseCategoryEnum.USER_SIGNAL, signal=2),
        ),
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestDetectStatus:
    def test_no_run_yet_cli(self, tmp_path: Path) -> None:
        info = detect_status(tmp_path, {}, platform="")
        assert info is not None
        assert info.kind == MessageKind.INFO
        assert "Nothing to see here" in info.short
        assert info.long is not None
        assert info.long.startswith("$ bristlenose run")
        assert info.long_is_mono

    def test_no_run_yet_desktop(self, tmp_path: Path) -> None:
        info = detect_status(tmp_path, {}, platform="desktop")
        assert info is not None
        assert info.kind == MessageKind.INFO
        assert "No interviews" in info.short
        assert info.long is not None
        assert "Drop a folder" in info.long

    def test_completed_lets_spa_render(self, tmp_path: Path) -> None:
        last_run = {1: {"run_id": "X", "outcome": "completed", "completed_at": "t"}}
        assert detect_status(tmp_path, last_run) is None

    def test_failed_surfaces_cause_message(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        _seed_failed(out, message="Quota exceeded — top up the account")
        last_run = {1: {"run_id": "X", "outcome": "failed", "completed_at": "t"}}
        info = detect_status(out, last_run)
        assert info is not None
        assert info.kind == MessageKind.ERROR
        assert info.short == "Last run failed."
        assert info.long == "Quota exceeded — top up the account"
        assert info.details is not None
        assert "category: api_server" in info.details
        assert "code: 503" in info.details

    def test_cancelled_surfaces_warning(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir()
        _seed_cancelled(out)
        last_run = {1: {"run_id": "X", "outcome": "cancelled", "completed_at": "t"}}
        info = detect_status(out, last_run)
        assert info is not None
        assert info.kind == MessageKind.WARNING
        assert "cancelled" in info.short.lower()

    def test_failed_with_no_events_file_still_intercepts(self, tmp_path: Path) -> None:
        """``last_run`` says failed but events file missing: still intercept, details empty."""
        last_run = {1: {"run_id": "X", "outcome": "failed", "completed_at": "t"}}
        info = detect_status(tmp_path, last_run)
        assert info is not None
        assert info.kind == MessageKind.ERROR
        # No cause/log → no details block
        assert info.details is None or info.details == ""

    def test_unknown_outcome_does_not_intercept(self, tmp_path: Path) -> None:
        last_run = {1: {"run_id": "X", "outcome": "weird-future-value"}}
        assert detect_status(tmp_path, last_run) is None

    def test_corrupt_events_file_does_not_crash(self, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        events_path(out).parent.mkdir(parents=True)
        events_path(out).write_text("{ not json\n", encoding="utf-8")
        last_run = {1: {"run_id": "X", "outcome": "failed"}}
        info = detect_status(out, last_run)
        assert info is not None
        assert info.kind == MessageKind.ERROR


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


class TestRenderPage:
    def test_renders_short_and_long(self) -> None:
        html = render_page(
            StatusInfo(
                kind=MessageKind.INFO,
                short="Nothing to see here, yet.",
                long="$ bristlenose run interviews/",
                details=None,
                long_is_mono=True,
            ),
        )
        assert "<!doctype html>" in html
        assert "Nothing to see here" in html
        assert "$ bristlenose run interviews/" in html
        assert 'data-status-kind="info"' in html
        assert "is-mono" in html

    def test_escapes_short_and_long(self) -> None:
        html = render_page(
            StatusInfo(
                kind=MessageKind.ERROR,
                short="<script>evil()</script>",
                long="payload & more",
                details=None,
            ),
        )
        assert "<script>evil()</script>" not in html
        assert "&lt;script&gt;" in html
        assert "payload &amp; more" in html

    def test_details_block_present_when_details(self) -> None:
        html = render_page(
            StatusInfo(
                kind=MessageKind.ERROR,
                short="Last run failed.",
                long=None,
                details="category: api_server\ncode: 503",
            ),
        )
        assert "<details" in html
        assert "Show details" in html
        assert "category: api_server" in html

    def test_no_details_block_when_no_details(self) -> None:
        html = render_page(
            StatusInfo(
                kind=MessageKind.INFO,
                short="Nothing to see here, yet.",
                long=None,
                details=None,
            ),
        )
        assert "<details" not in html

    def test_footer_uses_supplied_urls(self) -> None:
        html = render_page(
            StatusInfo(kind=MessageKind.INFO, short="x", long=None, details=None),
            feedback_url="https://example.com/feedback",
            help_url="https://example.com/help",
        )
        assert "https://example.com/feedback" in html
        assert "https://example.com/help" in html

    def test_html_root_attrs_injected(self) -> None:
        html = render_page(
            StatusInfo(kind=MessageKind.INFO, short="x", long=None, details=None),
            html_root_attrs='data-platform="desktop"',
        )
        assert 'data-platform="desktop"' in html


# ---------------------------------------------------------------------------
# Integration: intercept fires from /report/* in prod and dev mounts
# ---------------------------------------------------------------------------


_VITE_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <script type="module" crossorigin src="/assets/main-abc123.js"></script>
  </head>
  <body><div id="bn-app-root" data-project-id="1"></div></body>
</html>
"""


@pytest.fixture()
def prod_app_factory(tmp_path: Path):
    """Build a prod-mode TestClient with a configurable project state."""

    def _make() -> tuple[TestClient, Path]:
        output_dir = tmp_path / "bristlenose-output"
        output_dir.mkdir(exist_ok=True)
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)
        (static_dir / "assets").mkdir()
        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(project_dir=tmp_path, dev=False, db_url="sqlite://")
        return AuthTestClient(app), output_dir

    return _make


class TestProdIntercept:
    def test_no_run_yet_intercepts_with_status_page(self, prod_app_factory) -> None:
        client, _ = prod_app_factory()
        resp = client.get("/report/")
        assert resp.status_code == 200
        assert "Nothing to see here" in resp.text
        # SPA root must NOT mount
        assert 'id="bn-app-root"' not in resp.text

    def test_failed_run_intercepts(self, prod_app_factory, tmp_path: Path) -> None:
        # Seed BEFORE app creation so the event watcher's startup pass picks it up.
        out = tmp_path / "bristlenose-output"
        out.mkdir(exist_ok=True)
        _seed_failed(out, message="Provider 503 mid-stage")
        client, _ = prod_app_factory()
        resp = client.get("/report/")
        assert resp.status_code == 200
        assert "Last run failed" in resp.text
        assert "Provider 503 mid-stage" in resp.text
        assert 'id="bn-app-root"' not in resp.text

    def test_cancelled_run_intercepts(self, prod_app_factory, tmp_path: Path) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir(exist_ok=True)
        _seed_cancelled(out)
        client, _ = prod_app_factory()
        resp = client.get("/report/")
        assert resp.status_code == 200
        assert "cancelled" in resp.text.lower()
        assert 'id="bn-app-root"' not in resp.text

    def test_completed_run_falls_through_to_spa(
        self, prod_app_factory, tmp_path: Path,
    ) -> None:
        out = tmp_path / "bristlenose-output"
        out.mkdir(exist_ok=True)
        _seed_completed(out)
        client, _ = prod_app_factory()
        resp = client.get("/report/")
        assert resp.status_code == 200
        assert 'id="bn-app-root"' in resp.text
        # Status-page footer link must NOT be there
        assert "Send feedback" not in resp.text or "bn-status" not in resp.text

    def test_intercept_applies_to_nested_routes(self, prod_app_factory) -> None:
        client, _ = prod_app_factory()
        for path in ["/report/quotes", "/report/sessions/s1"]:
            resp = client.get(path)
            assert resp.status_code == 200
            assert "Nothing to see here" in resp.text

    def test_desktop_platform_text(
        self,
        prod_app_factory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("BRISTLENOSE_PLATFORM", "desktop")
        client, _ = prod_app_factory()
        resp = client.get("/report/")
        assert "No interviews" in resp.text
        assert 'data-platform="desktop"' in resp.text

    def test_feedback_url_override(
        self,
        prod_app_factory,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("BRISTLENOSE_FEEDBACK_URL", "https://example.test/fb")
        client, _ = prod_app_factory()
        resp = client.get("/report/")
        assert "https://example.test/fb" in resp.text


class TestSmokeFixtureMountsSPA:
    """Contract test: the on-disk smoke fixture must boot into the SPA.

    The Playwright perf-gate suite boots ``bristlenose serve`` against this
    fixture and expects ``/report/quotes/`` to render the React SPA. If the
    fixture is missing a terminus event (or the run never completed), the
    status page intercepts and ``#bn-app-root`` is never created — the
    failure surfaces in CI as ``DOM nodes — Quotes`` timing out, which is
    far away from the actual cause. This test catches the regression at the
    pytest layer where it's cheap to diagnose.

    See ``e2e/tests/spa-mounts.spec.ts`` for the parallel Playwright check.
    """

    def test_report_quotes_renders_react_root(self, tmp_path: Path) -> None:
        # The CI test job doesn't build the React bundle (see CLAUDE.md
        # "React bundle missing in CI test job"), so ``_STATIC_DIR`` is empty
        # and ``_mount_prod_report`` would fail loud with "Build incomplete".
        # Patch a synthetic Vite-shaped index.html into ``_STATIC_DIR`` —
        # same pattern as ``TestProdIntercept``'s ``prod_app_factory`` above.
        # This still exercises the real status-page interceptor against the
        # real smoke fixture's events file, which is what we want to assert.
        fixture_dir = (
            Path(__file__).parent / "fixtures" / "smoke-test" / "input"
        )
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text(_VITE_INDEX_HTML)
        (static_dir / "assets").mkdir()
        with patch("bristlenose.server.app._STATIC_DIR", static_dir):
            app = create_app(project_dir=fixture_dir, dev=False, db_url="sqlite://")
        client = AuthTestClient(app)
        resp = client.get("/report/quotes/")
        assert resp.status_code == 200, resp.text
        # SPA mount point must be present — status-page intercept must NOT fire.
        assert 'id="bn-app-root"' in resp.text, (
            "Smoke fixture is not in a 'completed run' state — the status "
            "page intercepted /report/quotes/. Ensure "
            "tests/fixtures/smoke-test/input/bristlenose-output/.bristlenose/"
            "pipeline-events.jsonl contains a RunCompletedEvent for project 1."
        )
        assert "Nothing to see here" not in resp.text
        assert "bn-status-page" not in resp.text
