"""Migration 022: AutoCode per-session stamps, backfilled from the watermark (RE#66).

Until 022 one timestamp per codebook said which sessions it had coded: those
first imported at or before ``AutoCodeJob.completed_at``. The backfill writes a
stamp for exactly those, so an upgraded project's next re-apply sends what it
would have sent before, and nothing it had already paid for.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa


def _insert(conn: sa.Connection, sql: str, **params: object) -> int:
    conn.execute(sa.text(sql), params)
    return int(conn.execute(sa.text("SELECT last_insert_rowid()")).scalar_one())


def test_stamps_backfill_from_the_watermark(tmp_path: Path) -> None:
    from bristlenose.server.db import create_session_factory, init_db, run_migrations
    from bristlenose.server.models import Project

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    db = create_session_factory(engine)()
    db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
    db.commit()
    db.close()
    with engine.connect() as conn:  # roll the fresh DB back to how 021 left it
        conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
        conn.execute(sa.text("DROP TABLE autocode_session_stamps"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '021'"))
        sessions = {}
        for sid, imported in (("s1", "2019-06-01 00:00:00"), ("s2", "2021-01-01 00:00:00"),
                              ("s3", None)):
            sessions[sid] = _insert(
                conn,
                "INSERT INTO sessions (project_id, session_id, session_number,"
                " duration_seconds, has_media, has_video, first_imported_at)"
                " VALUES (1, :sid, 1, 0, 0, 0, :imported)",
                sid=sid, imported=imported,
            )
        applied = _insert(
            conn,
            "INSERT INTO autocode_jobs (project_id, framework_id, status, total_quotes,"
            " processed_quotes, proposed_count, catch_up_total, catch_up_processed,"
            " error_message, failure_kind, llm_provider, llm_model, prompt_version,"
            " input_tokens, output_tokens, started_at, completed_at)"
            " VALUES (1, 'garrett', 'completed', 0, 0, 0, 0, 0, '', '', '', '', '', 0, 0,"
            " '2020-01-01', '2020-01-01 00:00:00')",
        )
        _insert(
            conn,
            "INSERT INTO autocode_jobs (project_id, framework_id, status, total_quotes,"
            " processed_quotes, proposed_count, catch_up_total, catch_up_processed,"
            " error_message, failure_kind, llm_provider, llm_model, prompt_version,"
            " input_tokens, output_tokens, started_at, completed_at)"
            " VALUES (1, 'norman', 'failed', 0, 0, 0, 0, 0, '', '', '', '', '', 0, 0,"
            " '2020-01-01', NULL)",
        )
        # A first apply stopped on an older release: the Stop set completed_at.
        stopped_first = _insert(
            conn,
            "INSERT INTO autocode_jobs (project_id, framework_id, status, total_quotes,"
            " processed_quotes, proposed_count, catch_up_total, catch_up_processed,"
            " error_message, failure_kind, llm_provider, llm_model, prompt_version,"
            " input_tokens, output_tokens, started_at, completed_at)"
            " VALUES (1, 'uxr', 'cancelled', 0, 0, 0, 0, 0, '', '', '', '', '', 0, 0,"
            " '2020-01-01 09:00:00', '2020-01-01 09:30:00.123456')",
        )
        # A catch-up stopped since 20 Oct: its start is past the job's completed_at.
        stopped_catch_up = _insert(
            conn,
            "INSERT INTO autocode_jobs (project_id, framework_id, status, total_quotes,"
            " processed_quotes, proposed_count, catch_up_total, catch_up_processed,"
            " error_message, failure_kind, llm_provider, llm_model, prompt_version,"
            " input_tokens, output_tokens, started_at, completed_at)"
            " VALUES (1, 'morville', 'cancelled', 0, 0, 0, 0, 0, '', '', '', '', '', 0, 0,"
            " '2021-02-01 00:00:00.000000', '2020-01-01 00:00:00.000000')",
        )
        conn.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT job_id, session_id FROM autocode_session_stamps")).all()
        completed = dict(conn.execute(sa.text(
            "SELECT id, completed_at FROM autocode_jobs")).all())
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    # At or before the watermark, and the sessions with no import time, which the
    # watermark never selected: stamped. After it: owed. Never applied: nothing.
    assert sorted(rows) == sorted([
        (applied, sessions["s1"]), (applied, sessions["s3"]),
        (stopped_catch_up, sessions["s1"]), (stopped_catch_up, sessions["s3"]),
    ])
    # The stopped first apply is not applied (#65): nothing maintains it, and
    # Apply can retry it. The stopped catch-up keeps its job's time.
    assert completed[stopped_first] is None
    assert completed[stopped_catch_up] is not None
    from tests.test_migrations import MIGRATION_HEAD

    assert version == MIGRATION_HEAD


def test_a_fresh_database_upgrades_cleanly(tmp_path: Path) -> None:
    """On a fresh DB ``create_all`` has made the table before 022 runs."""
    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    init_db(engine)
    run_migrations(engine)
    with engine.connect() as conn:
        assert "autocode_session_stamps" in sa.inspect(conn).get_table_names()
