"""Migration 027: how each AutoCode decision was made (``proposed_tags.decided_by``).

Every proposal decided before it gets "unknown": pinned like a researcher's decision
against a later re-cut, never counted as a rejection (docs/design-autocode-landing-plan.md
D2, D4, review 7). A pending one stays NULL.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from tests.test_migration_025_autocode_sent_quotes import _JOB, _insert, _quote


def _db_at_026(tmp_path: Path) -> sa.Engine:
    """A database as 026 left it: no ``decided_by``."""
    from bristlenose.server.db import create_session_factory, init_db
    from bristlenose.server.models import Project

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    db = create_session_factory(engine)()
    db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
    db.commit()
    db.close()
    with engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE proposed_tags DROP COLUMN decided_by"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '026'"))
        conn.commit()
    return engine


def test_decided_proposals_become_unknown_and_pending_ones_stay_null(tmp_path: Path) -> None:
    from bristlenose.server.db import run_migrations
    from tests.test_migrations import MIGRATION_HEAD

    engine = _db_at_026(tmp_path)
    with engine.connect() as conn:
        job = _insert(conn, _JOB, fw="garrett", done="2026-10-02 00:00:00")
        group = _insert(conn, "INSERT INTO codebook_groups (name, subtitle, colour_set,"
                              " sort_order, created_at) VALUES ('G', '', 'ux', 0,"
                              " '2026-10-01 00:00:00')")
        tag = _insert(conn, "INSERT INTO tag_definitions (name, codebook_group_id)"
                            " VALUES ('t', :g)", g=group)
        ids = {}
        for n, status in enumerate(("pending", "accepted", "denied"), start=1):
            ids[status] = _insert(
                conn,
                "INSERT INTO proposed_tags (job_id, quote_id, tag_definition_id,"
                " confidence, rationale, status) VALUES (:j, :q, :t, 0.8, '', :s)",
                j=job, q=_quote(conn, "s1", "p1", n), t=tag, s=status,
            )
        conn.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        got = dict(conn.execute(sa.text("SELECT status, decided_by FROM proposed_tags")).all())
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert version == MIGRATION_HEAD
    assert got == {"pending": None, "accepted": "unknown", "denied": "unknown"}


def test_a_fresh_database_upgrades_cleanly(tmp_path: Path) -> None:
    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    init_db(engine)
    run_migrations(engine)
    with engine.connect() as conn:
        columns = {c["name"] for c in sa.inspect(conn).get_columns("proposed_tags")}
    assert "decided_by" in columns
