"""A serve connection binds to one tree: a restore cannot land inside its binding.

SQLite opens a database's main file, ``-wal`` and ``-shm`` by path at different
instants (connect; the pragma that turns on WAL; the first read). The failing
re-analysis of ``test_lifecycle_scenarios`` restores the report while the serve's
reattach is opening a connection to the run's fresh, empty database — and on
macOS CI (2 Nov 2026) the restore landed between those instants: the connection
held the empty database as its main file and the restored report's log as its
log, ``create_all`` wrote the new schema into that log, and every reader of the
restored report found a hybrid (``no such table: screen_clusters`` under a
project row) and then ``database disk image is malformed`` — the test's own raw
``sqlite3`` read included.

Here the binding is held open on purpose, from inside the pragma hook, and the
restore is started meanwhile: it must wait (the swaps hold the study folder's
settle lock exclusive; a binding holds it shared), and afterwards the restored
report is whole and the star made before the run is still there.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from bristlenose.server import db as server_db
from bristlenose.utils import output_backup
from tests.test_lifecycle_scenarios import _client, _db, _star, _starred
from tests.test_serve_condition import _failed, _started
from tests.test_serve_project_root import _app, _project, _rows, _sessions, _wait
from tests.test_serve_project_root import fast_watcher as fast_watcher  # noqa: F401


def test_a_restore_waits_for_a_connection_mid_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast_watcher,  # noqa: F811
) -> None:
    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    armed = threading.Event()
    paused = threading.Event()
    go = threading.Event()
    real_pragma = server_db._set_sqlite_pragma

    def pragma_that_pauses_once(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        # Inside the binding: the main file is open, the log is not yet.
        if armed.is_set() and not paused.is_set():
            paused.set()
            assert go.wait(10), "the test never released the binding"
        real_pragma(dbapi_connection, connection_record)

    monkeypatch.setattr(server_db, "_set_sqlite_pragma", pragma_that_pauses_once)

    with _client(_app(proj, tmp_path)) as client:
        _star(client)
        stash = output_backup.stash(out)
        assert stash is not None
        armed.set()
        (out / ".bristlenose").mkdir(parents=True, exist_ok=True)  # the run's first act
        _started(out, "BAD")
        assert paused.wait(10), "the reattach never opened a connection"
        _failed(out, "BAD")

        outcome: list[output_backup.RestoreOutcome] = []
        restore = threading.Thread(
            target=lambda: outcome.append(output_backup.restore(stash, out)), daemon=True,
        )
        restore.start()
        restore.join(0.5)
        assert restore.is_alive(), "the restore swapped the folder inside a connection's binding"

        go.set()
        restore.join(10)
        assert not restore.is_alive() and outcome and outcome[0].report_is_back

        assert _wait(lambda: _sessions(client)), "the restored report never answered"
        con = sqlite3.connect(_db(proj))
        try:
            assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        finally:
            con.close()
        assert len(_rows(_db(proj))) == 1
        assert _wait(lambda: _starred(client)), "a failed re-analyse lost the researcher's star"


def test_a_failed_heal_is_retried_after_the_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast_watcher,  # noqa: F811
) -> None:
    """A heal that opened the run's tree and then failed left its record as it
    was; the restore brought the original inodes back, equal to that record, so
    no later change reattached and every request read the dead tree."""
    from sqlalchemy import inspect

    proj = _project(tmp_path)
    out = proj / "bristlenose-output"
    failing = threading.Event()
    real_ensure_schema = server_db.ensure_schema

    def heal_that_fails_while_armed(engine):  # type: ignore[no-untyped-def]
        if failing.is_set():
            engine.dispose()
            inspect(engine).get_table_names()  # the pool now holds the run's tree
            raise RuntimeError("heal cut short")
        real_ensure_schema(engine)

    monkeypatch.setattr(server_db, "ensure_schema", heal_that_fails_while_armed)

    with _client(_app(proj, tmp_path)) as client:
        _star(client)
        stash = output_backup.stash(out)
        assert stash is not None
        failing.set()
        (out / ".bristlenose").mkdir(parents=True, exist_ok=True)
        _started(out, "BAD")
        _failed(out, "BAD")
        assert _wait(lambda: not _sessions(client)), "the pool never moved onto the run's tree"
        failing.clear()
        assert output_backup.restore(stash, out).report_is_back
        assert _wait(lambda: _sessions(client)), "the restored report never answered"
        assert _wait(lambda: _starred(client)), "a failed re-analyse lost the researcher's star"


def test_binding_waits_for_an_exclusive_hold_in_another_thread(tmp_path: Path) -> None:
    out = tmp_path / "study" / "bristlenose-output"
    out.mkdir(parents=True)
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with output_backup._settling(out):
            held.set()
            release.wait(10)

    holder = threading.Thread(target=hold, daemon=True)
    holder.start()
    assert held.wait(5)

    entered = threading.Event()
    binder = threading.Thread(
        target=lambda: (output_backup.binding(out).__enter__(), entered.set()), daemon=True,
    )
    binder.start()
    assert not entered.wait(0.3), "a binding entered while another thread held the lock"
    release.set()
    assert entered.wait(5)
    holder.join(5)


def test_binding_passes_for_the_thread_that_holds_the_lock(tmp_path: Path) -> None:
    out = tmp_path / "study" / "bristlenose-output"
    out.mkdir(parents=True)
    with output_backup._settling(out), output_backup.binding(out):
        pass  # no self-deadlock
