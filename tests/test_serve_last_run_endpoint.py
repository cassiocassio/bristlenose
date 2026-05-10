"""Tests for the ``/api/projects/{id}/last-run`` endpoint and its race contract.

The bug this guards against: SPA polls ``/last-run``, sees a new
``run_id``, refetches ``/sessions`` and ``/quotes`` — but the post-pipeline
SQLite re-import hadn't finished, so the refetch reads stale (or empty)
data. The contract is **import-then-publish**: ``app.state.last_run``
must only become observable after ``import_project`` has returned.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bristlenose.events import (
    KindEnum,
    Process,
    RunCompletedEvent,
    RunStartedEvent,
    append_event,
    events_path,
    new_run_id,
)
from bristlenose.server.app import _make_run_completed_handler, create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_TS = "2026-05-09T13:00:00Z"


def _process() -> Process:
    return Process(
        pid=1234,
        start_time=_TS,
        hostname="testhost",
        user="tester",
        bristlenose_version="0.0.0-test",
        python_version="3.12",
        os="darwin-arm64",
    )


def _completed(run_id: str) -> RunCompletedEvent:
    return RunCompletedEvent(
        ts=_TS,
        run_id=run_id,
        kind=KindEnum.RUN,
        started_at=_TS,
        ended_at=_TS,
    )


# ---------------------------------------------------------------------------
# Endpoint shape
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


class TestEndpointShape:
    def test_returns_null_when_no_run_yet(self, client: TestClient) -> None:
        """Fresh project (no events file) → endpoint returns null."""
        # Smoke-test fixture has no pipeline-events.jsonl on disk.
        resp = client.get("/api/projects/1/last-run")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_404_unknown_project(self, client: TestClient) -> None:
        resp = client.get("/api/projects/999/last-run")
        assert resp.status_code == 404

    def test_requires_auth(self) -> None:
        """Bare TestClient (no bearer token) → 401."""
        app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
        bare = TestClient(app)
        resp = bare.get("/api/projects/1/last-run")
        assert resp.status_code == 401

    def test_returns_pinned_fields_when_set(self, client: TestClient) -> None:
        """Response shape is exactly {run_id, outcome, completed_at} — no extras."""
        rid = new_run_id()
        client.app.state.last_run[1] = {  # type: ignore[attr-defined]
            "run_id": rid,
            "outcome": "completed",
            "completed_at": "2026-05-09T13:01:02Z",
        }
        resp = client.get("/api/projects/1/last-run")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"run_id", "outcome", "completed_at"}
        assert body == {
            "run_id": rid,
            "outcome": "completed",
            "completed_at": "2026-05-09T13:01:02Z",
        }


# ---------------------------------------------------------------------------
# Startup seed: events file exists before create_app
# ---------------------------------------------------------------------------


def _seed_project(tmp_path: Path) -> Path:
    """Build a minimum project dir that has an events file with a terminus."""
    project_dir = tmp_path / "project"
    output_dir = project_dir / "bristlenose-output"
    output_dir.mkdir(parents=True)
    return project_dir


class TestStartupSeed:
    def test_seeds_last_run_from_existing_events(self, tmp_path: Path) -> None:
        project_dir = _seed_project(tmp_path)
        events_file = events_path(project_dir / "bristlenose-output")
        rid = new_run_id()
        # Earlier started + completed, then a later completed — seed should
        # pick the most recent terminus.
        rid_earlier = new_run_id()
        append_event(events_file, RunStartedEvent(
            ts=_TS, run_id=rid_earlier, kind=KindEnum.RUN,
            started_at=_TS, process=_process(),
        ))
        append_event(events_file, _completed(rid_earlier))
        append_event(events_file, _completed(rid))

        app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
        client = AuthTestClient(app)
        resp = client.get("/api/projects/1/last-run")
        assert resp.status_code == 200
        body = resp.json()
        assert body is not None
        assert body["run_id"] == rid
        assert body["outcome"] == "completed"

    def test_no_seed_when_events_file_absent(self, tmp_path: Path) -> None:
        project_dir = _seed_project(tmp_path)
        app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
        assert app.state.last_run == {}


# ---------------------------------------------------------------------------
# Race regression: importer completes BEFORE last_run becomes observable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_imports_before_publishing_last_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The load-bearing correctness fix.

    Reverse this ordering and the SPA gets a fresh ``run_id`` while the
    DB still holds the previous run's data — the bug v3 exists to fix.
    """
    project_dir = _seed_project(tmp_path)
    app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    # Fresh state — strip any seed.
    app.state.last_run = {}

    # Spy: snapshot last_run at the moment import_project is invoked.
    snapshot_during_import: dict[str, Any] = {}
    import_started = threading.Event()
    import_release = threading.Event()

    def fake_import_project(_db: Any, _project_dir: Any) -> None:
        # Capture last_run state at the instant import begins, then block
        # until the test releases. If the handler had assigned last_run
        # before calling us, the snapshot would be non-empty.
        snapshot_during_import.update(dict(app.state.last_run))
        import_started.set()
        # Hold for a few ticks so a buggy implementation that assigned
        # last_run early would have plenty of time to be observed.
        import_release.wait(timeout=2.0)

    monkeypatch.setattr(
        "bristlenose.server.importer.import_project", fake_import_project,
    )

    handler = _make_run_completed_handler(
        app, app.state.db_factory, project_dir,
    )

    rid = new_run_id()
    handler_task = asyncio.create_task(handler(_completed(rid)))

    # Wait until import is in-flight, then assert ordering invariant.
    await asyncio.to_thread(import_started.wait, 2.0)
    assert import_started.is_set(), "import_project never ran"
    assert snapshot_during_import == {}, (
        "last_run was published before import completed — race regression"
    )
    # last_run is still empty *during* the import too.
    assert app.state.last_run == {}

    # Release the import; handler completes and publishes last_run.
    import_release.set()
    await handler_task

    assert app.state.last_run[1]["run_id"] == rid
    assert app.state.last_run[1]["outcome"] == "completed"
    assert app.state.last_run[1]["completed_at"] == _TS


# ---------------------------------------------------------------------------
# End-to-end via the watcher (slower; covers the wiring)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watcher_populates_last_run_on_new_run_completed(
    tmp_path: Path,
) -> None:
    """End-to-end via the watcher — RUN_COMPLETED → import → last_run set."""
    from bristlenose.server.event_watcher import run_event_watcher

    project_dir = _seed_project(tmp_path)
    app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    app.state.last_run = {}

    handler = _make_run_completed_handler(
        app, app.state.db_factory, project_dir,
    )
    events_file = events_path(project_dir / "bristlenose-output")

    task = asyncio.create_task(
        run_event_watcher(events_file, handler, poll_interval=0.05),
    )
    try:
        await asyncio.sleep(0.1)
        rid = new_run_id()
        append_event(events_file, RunStartedEvent(
            ts=_TS, run_id=rid, kind=KindEnum.RUN,
            started_at=_TS, process=_process(),
        ))
        append_event(events_file, _completed(rid))
        # Allow watcher tick + handler import to complete.
        for _ in range(20):
            await asyncio.sleep(0.1)
            if app.state.last_run.get(1, {}).get("run_id") == rid:
                break
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert app.state.last_run[1]["run_id"] == rid
    # And the endpoint mirrors it.
    resp = AuthTestClient(app).get("/api/projects/1/last-run")
    assert resp.json()["run_id"] == rid


