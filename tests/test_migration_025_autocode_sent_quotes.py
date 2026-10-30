"""Migration 025: the register of sent quotes replaces the per-session stamps (ruling 4).

A stamp said a session was coded, whatever it held. 025 writes the register from what
the database can still say: every proposal is a quote that was sent, and so is every
quote of a stamped session that counts today. A hidden quote, or one whose participant
was recoded as a moderator or observer, is left off: AutoCode has not sent those since
25 Oct 2026 (N175), so unhiding it later must find it owed. A quote the model declined
to tag is on the register (marking it owed would pay for every coded session again).
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

_JOB = (
    "INSERT INTO autocode_jobs (project_id, framework_id, status, total_quotes,"
    " processed_quotes, proposed_count, catch_up_total, catch_up_processed,"
    " error_message, failure_kind, llm_provider, llm_model, prompt_version,"
    " input_tokens, output_tokens, started_at, completed_at)"
    " VALUES (1, :fw, 'completed', 0, 0, 0, 0, 0, '', '', '', '', '', 0, 0,"
    " '2026-10-01 00:00:00', :done)"
)


def _insert(conn: sa.Connection, sql: str, **params: object) -> int:
    conn.execute(sa.text(sql), params)
    return int(conn.execute(sa.text("SELECT last_insert_rowid()")).scalar_one())


def _quote(conn: sa.Connection, sid: str, who: str, n: int) -> int:
    return _insert(
        conn,
        "INSERT INTO quotes (project_id, session_id, participant_id, start_timecode,"
        " end_timecode, text, verbatim_excerpt, topic_label, quote_type, intensity,"
        " segment_index) VALUES (1, :sid, :who, :start, :end, :text, '', '',"
        " 'screen_specific', 1, -1)",
        sid=sid, who=who, start=float(n * 10), end=float(n * 10 + 5), text=f"{sid} quote {n}",
    )


def _db_at_022(tmp_path: Path) -> sa.Engine:
    """A database as 022 left it: the stamps table, no register."""
    from bristlenose.server.db import create_session_factory, init_db
    from bristlenose.server.models import Project

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    db = create_session_factory(engine)()
    db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
    db.commit()
    db.close()
    with engine.connect() as conn:
        conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
        conn.execute(sa.text("DROP TABLE autocode_sent_quotes"))
        conn.execute(sa.text(
            "CREATE TABLE autocode_session_stamps (id INTEGER PRIMARY KEY,"
            " job_id INTEGER NOT NULL REFERENCES autocode_jobs(id),"
            " session_id INTEGER NOT NULL REFERENCES sessions(id),"
            " coded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            " UNIQUE (job_id, session_id))"
        ))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '022'"))
        conn.commit()
    return engine


def test_the_register_is_written_from_stamps_and_proposals(tmp_path: Path) -> None:
    from bristlenose.server.autocode import owed_quotes
    from bristlenose.server.db import create_session_factory, run_migrations
    from bristlenose.server.models import AutoCodeJob, QuoteState
    from tests.test_migrations import MIGRATION_HEAD

    engine = _db_at_022(tmp_path)
    with engine.connect() as conn:
        pk = {}
        for sid in ("s1", "s2"):
            pk[sid] = _insert(
                conn,
                "INSERT INTO sessions (project_id, session_id, session_number,"
                " duration_seconds, has_media, has_video) VALUES (1, :sid, 1, 0, 0, 0)",
                sid=sid,
            )
        # s1 is stamped. Its quotes: 1 the model declined (no proposal), 2 proposed,
        # 3 hidden with nothing, 4 hidden WITH a proposal (sent before N175), 5 a
        # participant p2 recoded as an observer, nothing proposed.
        q = {n: _quote(conn, "s1", "p2" if n == 5 else "p1", n) for n in range(1, 6)}
        # s2 is not stamped: 6 has a proposal (a partial apply), 7 has neither.
        q[6] = _quote(conn, "s2", "p1", 6)
        q[7] = _quote(conn, "s2", "p1", 7)
        for n in (3, 4):
            _insert(conn, "INSERT INTO quote_states (quote_id, is_hidden, is_starred)"
                          " VALUES (:q, 1, 0)", q=q[n])
        _insert(
            conn,
            "INSERT INTO session_speakers (session_id, speaker_code, speaker_role,"
            " words_spoken, pct_words, pct_time_speaking, source_file)"
            " VALUES (:s, 'p2', 'observer', 0, 0, 0, '')", s=pk["s1"],
        )
        garrett = _insert(conn, _JOB, fw="garrett", done="2026-10-02 00:00:00")
        norman = _insert(conn, _JOB, fw="norman", done="2026-10-03 00:00:00")
        never = _insert(conn, _JOB, fw="uxr", done=None)
        tag = _insert(conn, "INSERT INTO codebook_groups (name, subtitle, colour_set,"
                            " sort_order, created_at) VALUES ('G', '', 'ux', 0,"
                            " '2026-10-01 00:00:00')")
        td = _insert(conn, "INSERT INTO tag_definitions (name, codebook_group_id)"
                           " VALUES ('t', :g)", g=tag)
        for job, quote in ((garrett, 2), (garrett, 4), (garrett, 6), (never, 6)):
            _insert(
                conn,
                "INSERT INTO proposed_tags (job_id, quote_id, tag_definition_id,"
                " confidence, rationale, status) VALUES (:j, :q, :t, 0.8, '', 'pending')",
                j=job, q=q[quote], t=td,
            )
        for job in (garrett, norman):
            conn.execute(sa.text(
                "INSERT INTO autocode_session_stamps (job_id, session_id) VALUES (:j, :s)"),
                {"j": job, "s": pk["s1"]})
        conn.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        rows = {
            (job, quote) for job, quote in conn.execute(sa.text(
                "SELECT job_id, quote_id FROM autocode_sent_quotes"))
        }
        tables = sa.inspect(conn).get_table_names()
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    assert "autocode_session_stamps" not in tables
    assert version == MIGRATION_HEAD
    assert rows == {
        # garrett: the stamped session's quotes that count (1, 2), every proposal
        # (2, 4, 6), and nothing for the hidden 3 or the recoded-out 5.
        (garrett, q[1]), (garrett, q[2]), (garrett, q[4]), (garrett, q[6]),
        # norman has no proposals: only what its stamp covers that counts.
        (norman, q[1]), (norman, q[2]),
        # A job that was never applied has the proposal it holds and no stamp.
        (never, q[6]),
    }

    # The point of leaving them off: the quote becomes owed the moment it counts.
    db = create_session_factory(engine)()
    try:
        job = db.get(AutoCodeJob, garrett)
        owed = {x.id for x in owed_quotes(db, job)}
        assert owed == {q[7]}, "a quote with neither proposal nor stamp is owed"
        db.query(QuoteState).filter(QuoteState.quote_id == q[3]).update({"is_hidden": False})
        db.execute(sa.text("DELETE FROM session_speakers"))
        db.commit()
        assert {x.id for x in owed_quotes(db, job)} == {q[3], q[5], q[7]}
    finally:
        db.close()


def test_a_fresh_database_upgrades_cleanly(tmp_path: Path) -> None:
    """On a fresh DB ``create_all`` has made the register and never the stamps."""
    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    init_db(engine)
    run_migrations(engine)
    with engine.connect() as conn:
        tables = sa.inspect(conn).get_table_names()
    assert "autocode_sent_quotes" in tables
    assert "autocode_session_stamps" not in tables


def test_the_chain_from_021_lands_the_same_register(tmp_path: Path) -> None:
    """022 still builds the stamps from the watermark and 025 turns them into the
    register, so a database that skipped releases ends where one that did not does."""
    from bristlenose.server.db import create_session_factory, init_db, run_migrations
    from bristlenose.server.models import Project

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'older.db'}")
    init_db(engine)
    db = create_session_factory(engine)()
    db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
    db.commit()
    db.close()
    with engine.connect() as conn:
        conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
        conn.execute(sa.text("DROP TABLE autocode_sent_quotes"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '021'"))
        sid = _insert(
            conn,
            "INSERT INTO sessions (project_id, session_id, session_number, duration_seconds,"
            " has_media, has_video, first_imported_at)"
            " VALUES (1, 's1', 1, 0, 0, 0, '2019-06-01 00:00:00')",
        )
        quote = _quote(conn, "s1", "p1", 1)
        job = _insert(conn, _JOB, fw="garrett", done="2020-01-01 00:00:00")
        conn.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT job_id, quote_id FROM autocode_sent_quotes")).all()
    assert sid and rows == [(job, quote)]
