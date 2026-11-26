"""The study database is owner-only, like ``people.yaml`` and the transcripts beside it.

It holds participant names and every quote, and it was created at the umask default
(``0644``): readable by every local account when a study lives outside the home folder's
private subfolders (26 Nov 2026).
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from bristlenose.server.db import get_engine, sqlite_url

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _write(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS t (x)")
        conn.exec_driver_sql("INSERT INTO t VALUES (1)")


def test_a_new_database_and_its_wal_are_owner_only(tmp_path: Path) -> None:
    db = tmp_path / "bristlenose.db"
    old = os.umask(0o022)
    try:
        engine = get_engine(sqlite_url(db))
        _write(engine)
        # Read while the connection is open: the -wal and -shm exist only then.
        with engine.connect():
            modes = {p.name: _mode(p) for p in tmp_path.iterdir()}
        engine.dispose()
    finally:
        os.umask(old)
    assert {"bristlenose.db", "bristlenose.db-wal", "bristlenose.db-shm"} <= modes.keys()
    assert set(modes.values()) == {0o600}, modes


def test_an_existing_world_readable_database_is_tightened(tmp_path: Path) -> None:
    db = tmp_path / "bristlenose.db"
    engine = get_engine(sqlite_url(db))
    _write(engine)
    engine.dispose()
    db.chmod(0o644)
    wal = tmp_path / "bristlenose.db-wal"
    wal.write_bytes(b"")
    wal.chmod(0o644)

    engine = get_engine(sqlite_url(db))
    engine.dispose()
    assert _mode(db) == 0o600
    assert _mode(wal) == 0o600


def test_in_memory_database_touches_no_file(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    get_engine("sqlite://").dispose()
    assert list(tmp_path.iterdir()) == []
