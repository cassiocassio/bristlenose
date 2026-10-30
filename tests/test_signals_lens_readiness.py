"""The Signals lens is withheld while its first report is being built.

Plan: docs/design-signals-lens-readiness.md. The rules these pin:

* "has a report" means a stored snapshot with at least one card, not a row:
  a study with nothing to show stores an empty snapshot at serve start;
* the lens is withheld only while a build is in flight AND there is no such
  report: a rebuild over an existing report never takes away what is readable;
* the fact is set where a run's overlay ends (the lens would otherwise light at
  once and go dim when the build starts) and ended in the task's finally, and is
  never set when no cloud model means nothing will be built;
* the snapshot reader says a report is on its way, so the page keeps asking.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from bristlenose.events import KindEnum, RunCompletedEvent, new_run_id
from bristlenose.server import app as app_module
from bristlenose.server.app import _make_run_completed_handler, create_app
from bristlenose.server.lens_readiness import Progress, lens_readiness
from bristlenose.server.models import Project, SignalSnapshot
from bristlenose.server.signal_snapshots import (
    begin_signals_preparing,
    end_signals_preparing,
    signals_preparing,
    snapshot_has_cards,
    store_completed_snapshot,
)
from tests.conftest import AuthTestClient

CARD = {"codebooks": [{"codebook_id": "garrett", "signals": [{"signal_name": "n"}]}]}
EMPTY = {"codebooks": []}


# ── lens_readiness ────────────────────────────────────────────────────────────

def test_preparing_withholds_signals_with_no_run_in_play() -> None:
    ready = lens_readiness(None, signals_preparing=True)
    assert ready["signals"] is False
    assert all(v for k, v in ready.items() if k != "signals")


def test_preparing_is_off_by_default() -> None:
    assert lens_readiness(None)["signals"] is True


def test_preparing_withholds_signals_after_a_progressive_run_joins() -> None:
    joined = Progress(joined=True)
    assert lens_readiness(joined)["signals"] is True
    assert lens_readiness(joined, signals_preparing=True)["signals"] is False


# ── snapshot_has_cards ────────────────────────────────────────────────────────

def _snapshot(payload: dict) -> SignalSnapshot:
    import json

    return SignalSnapshot(project_id=1, source="t", payload_version=5, payload=json.dumps(payload))


def test_a_snapshot_with_a_card_has_cards() -> None:
    assert snapshot_has_cards(_snapshot(CARD)) is True


def test_an_empty_snapshot_is_not_a_report() -> None:
    assert snapshot_has_cards(_snapshot(EMPTY)) is False
    assert snapshot_has_cards(_snapshot({"codebooks": [{"codebook_id": "x", "signals": []}]})) is False


def test_no_snapshot_is_not_a_report() -> None:
    assert snapshot_has_cards(None) is False


# ── the flag ──────────────────────────────────────────────────────────────────

def test_the_flag_counts_overlapping_builds_and_never_goes_negative() -> None:
    state = SimpleNamespace()
    assert signals_preparing(state) is False
    begin_signals_preparing(state)
    begin_signals_preparing(state)
    end_signals_preparing(state)
    assert signals_preparing(state) is True
    end_signals_preparing(state)
    assert signals_preparing(state) is False
    end_signals_preparing(state)
    assert signals_preparing(state) is False


def test_the_startup_repair_counts_as_preparing() -> None:
    assert signals_preparing(SimpleNamespace(initial_signal_snapshot_pending=True)) is True


# ── the endpoints ─────────────────────────────────────────────────────────────

def _client(tmp_path, payload: dict | None):
    project_dir = tmp_path / "project"
    (project_dir / "bristlenose-output").mkdir(parents=True)
    app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        project = db.query(Project).first()
        if project is None:
            project = Project(name="P", slug="p", input_dir="/in", output_dir="/out")
            db.add(project)
            db.flush()
        if payload is not None:
            store_completed_snapshot(db, project.id, source="t", payload=payload)
        db.commit()
        project_id = project.id
    finally:
        db.close()
    app.state.initial_signal_snapshot_pending = False
    return app, AuthTestClient(app), project_id


def _signals_lit(client, project_id: int) -> bool:
    return client.get(f"/api/projects/{project_id}/condition").json()["lenses"]["signals"]


def test_the_lens_is_withheld_while_the_first_report_is_built(tmp_path) -> None:
    app, client, pid = _client(tmp_path, None)
    assert _signals_lit(client, pid) is True
    begin_signals_preparing(app.state)
    assert _signals_lit(client, pid) is False
    end_signals_preparing(app.state)
    assert _signals_lit(client, pid) is True


def test_an_empty_report_does_not_keep_the_lens_lit_during_the_build(tmp_path) -> None:
    app, client, pid = _client(tmp_path, EMPTY)
    begin_signals_preparing(app.state)
    assert _signals_lit(client, pid) is False


def test_a_report_with_cards_keeps_the_lens_lit_during_a_rebuild(tmp_path) -> None:
    app, client, pid = _client(tmp_path, CARD)
    begin_signals_preparing(app.state)
    assert _signals_lit(client, pid) is True


def test_the_snapshot_reader_says_a_report_is_on_its_way(tmp_path) -> None:
    app, client, pid = _client(tmp_path, None)
    url = f"/api/projects/{pid}/signals/snapshot"
    assert client.get(url).json()["pending"] is False
    begin_signals_preparing(app.state)
    body = client.get(url).json()
    assert body["snapshot"] is None and body["pending"] is True


def test_an_empty_report_is_still_pending_while_the_build_runs(tmp_path) -> None:
    app, client, pid = _client(tmp_path, EMPTY)
    begin_signals_preparing(app.state)
    body = client.get(f"/api/projects/{pid}/signals/snapshot").json()
    assert body["snapshot"] is not None and body["pending"] is True


def test_a_report_with_cards_is_never_pending(tmp_path) -> None:
    app, client, pid = _client(tmp_path, CARD)
    begin_signals_preparing(app.state)
    assert client.get(f"/api/projects/{pid}/signals/snapshot").json()["pending"] is False


# ── where a run's overlay ends ────────────────────────────────────────────────

def _completed_event() -> RunCompletedEvent:
    return RunCompletedEvent(
        ts="2026-10-30T00:00:00Z", run_id=new_run_id(), kind=KindEnum.RUN,
        started_at="2026-10-30T00:00:00Z", ended_at="2026-10-30T00:01:00Z",
    )


def _handler_app(tmp_path, monkeypatch, provider: str):
    project_dir = tmp_path / "project"
    (project_dir / "bristlenose-output").mkdir(parents=True)
    app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        db.add(Project(name="P", slug="p", input_dir="/in", output_dir="/out"))
        db.commit()
    finally:
        db.close()
    app.state.initial_signal_snapshot_pending = False
    app.state.settings = SimpleNamespace(llm_provider=provider)
    monkeypatch.setattr("bristlenose.server.importer.import_project", lambda _db, _path: None)
    monkeypatch.setattr("bristlenose.server.elaboration._has_api_key", lambda _s: True)
    return app, project_dir


def test_a_finished_run_notes_the_build_before_the_reapply_and_ends_it(
    tmp_path, monkeypatch,
) -> None:
    app, project_dir = _handler_app(tmp_path, monkeypatch, "openai")
    release = {}

    async def fake_reapply(_factory, _pid, _settings):
        await release["event"].wait()

    built: list[bool] = []

    async def fake_materialise(_db, _pid, *, source, project_dir):
        built.append(signals_preparing(app.state))

    monkeypatch.setattr("bristlenose.server.autocode.reapply_active_frameworks", fake_reapply)
    monkeypatch.setattr(
        "bristlenose.server.routes.signals.materialise_completed_signal_snapshot", fake_materialise,
    )
    handler = _make_run_completed_handler(app, app.state.db_factory, project_dir)

    async def scenario() -> None:
        release["event"] = asyncio.Event()
        await handler(_completed_event())
        # The overlay ended and the codebook re-apply is still running: the lens
        # must already be withheld, or it would light and then go dim.
        assert app.state.progress is None
        assert signals_preparing(app.state) is True
        release["event"].set()
        await asyncio.gather(*app_module._REAPPLY_AFTER_RUN_TASKS)
        assert signals_preparing(app.state) is False

    asyncio.run(scenario())
    assert built == [True]


def test_a_failed_build_still_ends_the_preparing_fact(tmp_path, monkeypatch) -> None:
    app, project_dir = _handler_app(tmp_path, monkeypatch, "openai")

    async def fake_reapply(_factory, _pid, _settings):
        raise RuntimeError("provider down")

    monkeypatch.setattr("bristlenose.server.autocode.reapply_active_frameworks", fake_reapply)
    handler = _make_run_completed_handler(app, app.state.db_factory, project_dir)

    async def scenario() -> None:
        await handler(_completed_event())
        await asyncio.gather(*app_module._REAPPLY_AFTER_RUN_TASKS)
        assert signals_preparing(app.state) is False

    asyncio.run(scenario())


def test_no_cloud_model_never_notes_a_build(tmp_path, monkeypatch) -> None:
    app, project_dir = _handler_app(tmp_path, monkeypatch, "local")
    handler = _make_run_completed_handler(app, app.state.db_factory, project_dir)

    async def scenario() -> None:
        await handler(_completed_event())
        assert signals_preparing(app.state) is False

    asyncio.run(scenario())
