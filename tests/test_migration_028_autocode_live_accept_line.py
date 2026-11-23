"""Migration 028: a first apply's live accept line (``autocode_jobs.live_accept_line``).

The line a run's batches accept at never falls during the run, and a resumed run
continues from it (docs/design-autocode-landing-plan.md D6). NULL for every job from
before the migration: none was accepted live.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from tests.test_migration_025_autocode_sent_quotes import _JOB, _insert


def _db_at_027(tmp_path: Path) -> sa.Engine:
    """A database as 027 left it: no ``live_accept_line``."""
    from bristlenose.server.db import create_session_factory, init_db
    from bristlenose.server.models import Project

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    db = create_session_factory(engine)()
    db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
    db.commit()
    db.close()
    with engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE autocode_jobs DROP COLUMN live_accept_line"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '027'"))
        conn.commit()
    return engine


def test_an_old_job_gets_no_live_line(tmp_path: Path) -> None:
    from bristlenose.server.db import run_migrations
    from tests.test_migrations import MIGRATION_HEAD

    engine = _db_at_027(tmp_path)
    with engine.connect() as conn:
        _insert(conn, _JOB, fw="garrett", done="2026-10-02 00:00:00")
        conn.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        lines = conn.execute(sa.text("SELECT live_accept_line FROM autocode_jobs")).all()
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert version == MIGRATION_HEAD
    assert lines == [(None,)]


def test_a_fresh_database_upgrades_cleanly(tmp_path: Path) -> None:
    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    init_db(engine)
    run_migrations(engine)
    with engine.connect() as conn:
        columns = {c["name"] for c in sa.inspect(conn).get_columns("autocode_jobs")}
    assert "live_accept_line" in columns
