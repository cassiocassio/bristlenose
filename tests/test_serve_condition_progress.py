"""The condition endpoint carries the SPA's refresh key and the lens readiness.

docs/design-progressive-lenses.md §3.2: ``data_version`` moves after every
successful import (``/last-run`` is pinned and moves only on a completed run, so
it cannot carry the per-session imports Phase 1 adds); ``lenses`` is the one
derivation the web nav and the Mac's lens rail read.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from bristlenose.events import KindEnum, RunCompletedEvent, new_run_id
from bristlenose.server.app import _make_run_completed_handler, create_app
from bristlenose.server.lens_readiness import LENSES, Progress
from tests.conftest import AuthTestClient

_TS = "2026-10-12T20:00:00Z"


def _completed(rid: str) -> RunCompletedEvent:
    return RunCompletedEvent(ts=_TS, run_id=rid, kind=KindEnum.RUN, started_at=_TS, ended_at=_TS)


def _app(tmp_path: Path):
    project = tmp_path / "project"
    (project / "bristlenose-output").mkdir(parents=True)
    return project, create_app(project_dir=project, dev=True, db_url="sqlite://")


def test_a_fresh_serve_reports_version_zero_and_every_lens(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    with AuthTestClient(app) as client:
        body = client.get("/api/projects/1/condition").json()
    assert body["data_version"] == 0
    assert body["lenses"] == dict.fromkeys(LENSES, True)


def test_a_successful_import_moves_the_version_and_a_failed_one_does_not(
    tmp_path: Path, monkeypatch,
) -> None:
    project, app = _app(tmp_path)
    outcomes = iter([None, RuntimeError("disk full")])

    def _import(_db, _dir):
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result

    monkeypatch.setattr("bristlenose.server.importer.import_project", _import)
    handler = _make_run_completed_handler(app, app.state.db_factory, project)
    with AuthTestClient(app) as client:
        asyncio.run(handler(_completed(new_run_id())))
        assert client.get("/api/projects/1/condition").json()["data_version"] == 1
        asyncio.run(handler(_completed(new_run_id())))
        assert client.get("/api/projects/1/condition").json()["data_version"] == 1, (
            "a failed import claimed a new data version; the SPA would refetch into stale data"
        )


def test_lenses_follow_the_progress_overlay(tmp_path: Path) -> None:
    _, app = _app(tmp_path)
    with AuthTestClient(app) as client:
        app.state.progress = Progress(readable=frozenset({"s1"}))
        lenses = client.get("/api/projects/1/condition").json()["lenses"]
    assert lenses["sessions"] and not lenses["quotes"] and not lenses["signals"]
