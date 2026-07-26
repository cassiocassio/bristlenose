"""SQLite connection pragmas.

The busy timeout is a regression guard, not tuning: WAL allows one writer at a
time, and AutoCode runs its batches concurrently. Without a non-zero busy
timeout, the instant two batch writes collide SQLite raises
``OperationalError: database is locked``, the batch is dropped, and the job
reports "0 proposals" while real proposals were lost (26 Jul 2026 — every
JJG/Nielsen tag stuck at count 0 despite the LLM returning 38 proposals).
"""

from __future__ import annotations

from bristlenose.server.db import get_engine


def _pragma(engine, name):  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return conn.exec_driver_sql(f"PRAGMA {name}").scalar()


def test_busy_timeout_is_set(tmp_path):
    """A non-zero write-lock busy timeout — the fix for concurrent AutoCode
    batch writes silently dropping proposals to 'database is locked'."""
    engine = get_engine(f"sqlite:///{tmp_path / 'bn.db'}")
    assert _pragma(engine, "busy_timeout") == 5000


def test_wal_and_foreign_keys_still_set(tmp_path):
    """Guard the rest of the pragma set the busy timeout sits alongside."""
    engine = get_engine(f"sqlite:///{tmp_path / 'bn.db'}")
    assert str(_pragma(engine, "journal_mode")).lower() == "wal"
    assert _pragma(engine, "foreign_keys") == 1
