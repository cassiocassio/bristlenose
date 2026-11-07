"""A run's import must not meet a re-apply's commit in flight (N92, owner ruling 4 Nov 2026).

The import rebuilds the quote rows, and a re-apply writes its proposals in one commit at the
end against the ids it read. One still coding when the next run's import landed lost that
commit to a foreign-key failure after every batch was paid for. The import now holds the
re-applies at their next batch (what answered is banked, the rest stays owed: the Stop and
switch-off path) and waits for them, for a bounded time.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bristlenose.server.autocode as ac
from bristlenose.server.app import _make_run_completed_handler, create_app
from bristlenose.server.models import (
    AutoCodeSentQuote,
    ProposedTag,
    Quote,
    QuoteTag,
)
from tests.test_autocode_catch_up import _app, _apply, _Model, _more_quotes
from tests.test_serve_last_run_endpoint import _after_run_tasks, _completed, _seed_project


@pytest.fixture(autouse=True)
def _clean() -> Any:
    ac._REAPPLY_IN_FLIGHT.clear()
    ac._IMPORTS_RUNNING = 0
    yield
    ac._REAPPLY_IN_FLIGHT.clear()
    ac._IMPORTS_RUNNING = 0


@pytest.fixture
def owed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """An applied codebook with three new quotes owed, one per batch, and a model whose first
    call of the re-apply waits on ``gate``."""
    monkeypatch.setattr(ac, "BATCH_SIZE", 1)
    app, _client = _app(tmp_path)
    model = _Model()
    _apply(app, model, "garrett")
    applied = len(model.prompts)
    _more_quotes(app, 3)
    gate, out = threading.Event(), threading.Event()
    real = model.analyze

    async def slow(**kw: Any) -> Any:
        if len(model.prompts) == applied:
            out.set()
            await asyncio.get_running_loop().run_in_executor(None, gate.wait)
        return await real(**kw)

    model.analyze = slow  # type: ignore[method-assign]
    yield app, model, applied, gate, out
    gate.set()  # a failed test must not leave a thread waiting for ever


def _rebuild_burst_quotes(app: Any) -> list[int]:
    """What the import does to the quotes: they go, with what hangs off them."""
    db = app.state.db_factory()
    try:
        ids = [q.id for q in db.query(Quote).filter(Quote.text.like("burst quote%"))]
        for model in (ProposedTag, QuoteTag, AutoCodeSentQuote):
            db.query(model).filter(model.quote_id.in_(ids)).delete(synchronize_session=False)
        db.query(Quote).filter(Quote.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        return ids
    finally:
        db.close()


async def _until(flag: threading.Event) -> None:
    async def poll() -> None:
        while not flag.is_set():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(poll(), timeout=10)


@pytest.mark.asyncio
async def test_an_import_waits_for_the_batch_out_and_nothing_is_rolled_back(
    owed: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    app, model, applied, gate, out = owed
    banked_at_import: list[int] = []
    imported = threading.Event()

    async def the_import() -> None:
        async with ac.reapplies_paused_for_import():
            imported.set()
            db = app.state.db_factory()
            banked_at_import.append(db.query(ProposedTag).join(Quote).filter(
                Quote.text.like("burst quote%")).count())
            db.close()
            _rebuild_burst_quotes(app)

    try:
        with model, caplog.at_level(logging.ERROR, logger="bristlenose.server.autocode"):
            reapply = asyncio.ensure_future(
                ac.reapply_active_frameworks(app.state.db_factory, 1, app.state.settings)
            )
            await _until(out)
            imp = asyncio.ensure_future(the_import())
            await asyncio.sleep(0.3)
            assert not imported.is_set(), "the import waits while a batch is out"
            gate.set()
            await asyncio.wait_for(asyncio.gather(reapply, imp), timeout=10)
    finally:
        gate.set()  # a failure must not leave the call's thread waiting for ever

    assert not [r for r in caplog.records if "Re-apply failed" in r.getMessage()], "no rollback"
    assert len(model.prompts) - applied == 1, "only the batch already out was paid for"
    assert banked_at_import == [1], "what answered was banked before the import began"
    assert ac._IMPORTS_RUNNING == 0


@pytest.mark.asyncio
async def test_what_the_pause_left_unsent_is_coded_once_the_import_is_done(owed: Any) -> None:
    app, model, applied, gate, out = owed
    try:
        with model:
            reapply = asyncio.ensure_future(
                ac.reapply_active_frameworks(app.state.db_factory, 1, app.state.settings)
            )
            await _until(out)

            async def the_import() -> None:
                async with ac.reapplies_paused_for_import():
                    pass  # the quotes are kept this time: the question is only what stays owed

            imp = asyncio.ensure_future(the_import())
            await asyncio.sleep(0.2)
            gate.set()
            await asyncio.wait_for(asyncio.gather(reapply, imp), timeout=10)
            assert len(model.prompts) - applied == 1
            # The next run's own re-apply: the two unsent quotes are owed, the sent one is not.
            await ac.reapply_active_frameworks(app.state.db_factory, 1, app.state.settings)
    finally:
        gate.set()
    assert len(model.prompts) - applied == 3, "each quote was sent once, none twice"


@pytest.mark.asyncio
async def test_a_re_apply_that_starts_during_an_import_sends_nothing(
    owed: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, model, applied, gate, _out = owed
    gate.set()  # no call waits: the point is what is sent, not when
    reads: list[int] = []
    real_owed = ac.owed_quotes

    def _watched(*a: Any, **k: Any) -> Any:
        reads.append(1)  # recorded, not raised: a pass swallows its own exceptions
        return real_owed(*a, **k)

    with model:
        async with ac.reapplies_paused_for_import():
            monkeypatch.setattr(ac, "owed_quotes", _watched)  # the first read of a pass
            await ac.reapply_active_frameworks(app.state.db_factory, 1, app.state.settings)
            assert len(model.prompts) == applied
            assert reads == [], "a re-apply started during an import read the quotes table"
            monkeypatch.setattr(ac, "owed_quotes", real_owed)
        await ac.reapply_active_frameworks(app.state.db_factory, 1, app.state.settings)
    assert len(model.prompts) - applied > 0, "and it codes once the import is over"


@pytest.mark.asyncio
async def test_the_wait_is_bounded_when_a_call_does_not_answer(
    owed: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    app, model, _applied, gate, out = owed
    monkeypatch.setattr(ac, "IMPORT_WAIT_S", 0.3)
    try:
        with model, caplog.at_level(logging.WARNING, logger="bristlenose.server.autocode"):
            reapply = asyncio.ensure_future(
                ac.reapply_active_frameworks(app.state.db_factory, 1, app.state.settings)
            )
            await _until(out)
            async def paused() -> None:
                async with ac.reapplies_paused_for_import():
                    assert not reapply.done(), "the call still has not answered"

            await asyncio.wait_for(paused(), timeout=5)  # bounded, or it never returns
            assert ac._IMPORTS_RUNNING == 0
            assert any("still coding" in r.getMessage() for r in caplog.records)
            gate.set()
            await asyncio.wait_for(reapply, timeout=10)
    finally:
        gate.set()


@pytest.mark.asyncio
async def test_the_run_completed_handler_imports_only_after_a_live_re_apply_has_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    project_dir = _seed_project(tmp_path)
    app = create_app(project_dir=project_dir, dev=True, db_url="sqlite://")
    app.state.last_run = {}
    app.state.settings = SimpleNamespace(llm_provider="anthropic")
    events: list[str] = []

    async def earlier_re_apply() -> None:
        # Coding the run before this one; it stops at its next batch once an import asks.
        while not ac._IMPORTS_RUNNING:
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)
        events.append("re-apply banked and stopped")

    ac.register_reapply(1, "garrett", asyncio.ensure_future(earlier_re_apply()))

    def fake_import_project(db: Any, project_dir: Path, **kw: Any) -> Any:
        events.append("import")
        return SimpleNamespace(id=1)

    monkeypatch.setattr("bristlenose.server.importer.import_project", fake_import_project)

    async def no_reapply(*_a: Any, **_k: Any) -> dict:
        return {}

    monkeypatch.setattr("bristlenose.server.autocode.reapply_active_frameworks", no_reapply)
    monkeypatch.setattr("bristlenose.server.elaboration._has_api_key", lambda _s: True)
    monkeypatch.setattr(
        "bristlenose.server.routes.signals.materialise_completed_signal_snapshot",
        lambda *a, **k: asyncio.sleep(0),
    )
    handler = _make_run_completed_handler(app, app.state.db_factory, project_dir)
    await asyncio.wait_for(handler(_completed("r2")), timeout=10)
    await _after_run_tasks()
    assert events == ["re-apply banked and stopped", "import"]
