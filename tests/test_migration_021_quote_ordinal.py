"""Migration 021: a quote's ordinal within its second (R86).

An existing database gains ``quotes.ordinal`` backfilled with the importer's
ranking, so a row that was already here keeps the id the importer would mint
for it, and the star on it stays put. The migration carries its own copy of
the ranking function; the second test holds it to the importer's.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import sqlalchemy as sa

from bristlenose.server.importer import rank_quote_ordinals
from bristlenose.server.models import Project

_MIGRATION = (
    Path(__file__).parent.parent / "bristlenose" / "server" / "alembic" / "versions"
    / "021_quote_ordinal.py"
)


def _migration_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("migration_021", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_QUOTE_COLUMNS = (
    "project_id, session_id, participant_id, start_timecode, end_timecode, text,"
    " verbatim_excerpt, topic_label, quote_type, intensity, segment_index"
)


def _insert_quote(conn: sa.Connection, start: float, end: float, text: str) -> int:
    conn.execute(sa.text(
        f"INSERT INTO quotes ({_QUOTE_COLUMNS}) VALUES"
        " (1, 's1', 'p1', :start, :end, :text, :text, 'Checkout', 'screen_specific', 1, -1)"
    ), {"start": start, "end": end, "text": text})
    return int(conn.execute(sa.text("SELECT last_insert_rowid()")).scalar_one())


class TestBackfill:
    def test_ordinal_backfill_matches_the_importer_ranking(self, tmp_path: Path) -> None:
        """A 020 database: two rows in one second (the earlier one starred), one alone.
        After the upgrade the earlier keeps ordinal 0 and its star; the later is 1."""
        from bristlenose.server.db import create_session_factory, init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
        init_db(engine)
        db = create_session_factory(engine)()
        db.add(Project(id=1, name="Old", input_dir=str(tmp_path), output_dir=str(tmp_path)))
        db.commit()
        db.close()

        with engine.connect() as conn:  # roll the fresh DB back to how 020 left it
            conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
            conn.execute(sa.text("DROP INDEX uq_quote_stable_key"))
            conn.execute(sa.text("ALTER TABLE quotes DROP COLUMN ordinal"))
            conn.execute(sa.text(
                "CREATE INDEX ix_quote_stable_key ON quotes"
                " (project_id, session_id, participant_id, start_timecode)"
            ))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '020'"))
            later = _insert_quote(conn, 10.4, 30.0, "the later one, written first")
            earlier = _insert_quote(conn, 10.0, 20.0, "the earlier one")
            alone = _insert_quote(conn, 25.0, 40.0, "on its own")
            conn.execute(sa.text(
                "INSERT INTO quote_states (quote_id, is_hidden, is_starred)"
                " VALUES (:q, 0, 1)"), {"q": earlier})
            conn.commit()

        run_migrations(engine)

        with engine.connect() as conn:
            ordinals = dict(conn.execute(sa.text("SELECT id, ordinal FROM quotes")).all())
            starred = conn.execute(sa.text(
                "SELECT quote_id FROM quote_states WHERE is_starred = 1")).scalars().all()
            indexes = {i["name"]: i for i in sa.inspect(conn).get_indexes("quotes")}
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        assert ordinals == {earlier: 0, later: 1, alone: 0}
        assert starred == [earlier]
        assert "ix_quote_stable_key" not in indexes
        assert indexes["uq_quote_stable_key"]["unique"]
        assert indexes["uq_quote_stable_key"]["column_names"][-1] == "ordinal"
        from tests.test_migrations import MIGRATION_HEAD

        assert version == MIGRATION_HEAD


    def test_two_identical_rows_take_two_ordinals(self, tmp_path: Path) -> None:
        """A duplicate row left by a race before the index existed must not stop the unique
        index being built: identical rows rank apart, by id."""
        from bristlenose.server.db import create_session_factory, init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'dup.db'}")
        init_db(engine)
        db = create_session_factory(engine)()
        db.add(Project(id=1, name="Dup", input_dir=str(tmp_path), output_dir=str(tmp_path)))
        db.commit()
        db.close()
        with engine.connect() as conn:
            conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
            conn.execute(sa.text("DROP INDEX uq_quote_stable_key"))
            conn.execute(sa.text("ALTER TABLE quotes DROP COLUMN ordinal"))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '020'"))
            a = _insert_quote(conn, 10.0, 20.0, "the same words")
            b = _insert_quote(conn, 10.0, 20.0, "the same words")
            conn.commit()
        run_migrations(engine)
        with engine.connect() as conn:
            ordinals = dict(conn.execute(sa.text("SELECT id, ordinal FROM quotes")).all())
            indexes = {i["name"] for i in sa.inspect(conn).get_indexes("quotes")}
        assert ordinals == {a: 0, b: 1}
        assert "uq_quote_stable_key" in indexes


class TestRankingCopy:
    def test_the_key_is_built_alike_from_a_row_and_from_json(self) -> None:
        """The backfill ranks what it reads from the table; the importer ranks what it reads
        from JSON. Both must build the same key, nulls included, or the backfill disagrees
        with the next import."""
        from bristlenose.server.importer import _rank_key

        copy = _migration_module()._rank_key_from_row
        # The same five parts; the sixth is the tiebreak: the row id here, 0 from JSON.
        assert copy("s1", "p1", 53.0, 71.0, "words", "the text", 7)[:5] == _rank_key({
            "session_id": "s1", "participant_id": "p1", "start_timecode": 53.0,
            "end_timecode": 71.0, "verbatim_excerpt": "words", "text": "the text"})[:5]
        assert copy("s1", "p1", 53.0, 71.0, "words", "the text", 7)[5] == 7
        assert _rank_key({"session_id": "s1", "participant_id": "p1", "start_timecode": 53.0,
                          "end_timecode": 71.0, "verbatim_excerpt": "words"})[5] == 0
        # Nulls, and the fall-back to the text when there is no excerpt.
        assert copy("s1", "p1", 53, None, None, "only text", 1)[:5] == _rank_key({
            "session_id": "s1", "participant_id": "p1", "start_timecode": 53,
            "end_timecode": None, "verbatim_excerpt": None, "text": "only text"})[:5]
        assert copy("s1", "p1", 53, None, "", "only text", 1)[4] == "only text"
        assert copy("s1", "p1", 53, None, None, None, 1)[:5] == _rank_key(
            {"session_id": "s1", "participant_id": "p1", "start_timecode": 53})[:5]

    def test_migration_ranking_matches_the_importers(self) -> None:
        """The migration's inline copy and the importer's helper rank alike, on a
        hand-made mix and on a random one."""
        copy = _migration_module()._rank_quote_ordinals
        fixed = [
            ("s1", "p1", 53.0, 71.0, "second half", 0),
            ("s1", "p1", 53.0, 60.0, "first half", 0),
            ("s1", "p1", 53.0, 60.0, "first half", 0),  # the same quote twice: one ordinal
            ("s1", "p1", 53.9, 55.0, "a third, later in the second", 0),
            ("s1", "p1", 54.0, 55.0, "next second", 0),
            ("s1", "p2", 53.0, 60.0, "another speaker", 0),
            ("s2", "p1", 53.0, 60.0, "another session", 0),
            ("s1", "p1", 53.0, 60.0, "first half", 9),  # an identical ROW: its own ordinal
        ]
        # Start first, then end: the pair at 53.0 are 0 and 1, the one at 53.9 is 2.
        expected = {
            fixed[0]: 2, fixed[1]: 0, fixed[7]: 1, fixed[3]: 3, fixed[4]: 0, fixed[5]: 0,
            fixed[6]: 0,
        }
        assert rank_quote_ordinals(fixed) == expected
        assert copy(fixed) == expected

        rng = random.Random(86)
        for _ in range(50):
            keys = [
                (f"s{rng.randint(1, 2)}", f"p{rng.randint(1, 2)}",
                 float(rng.randint(10, 12)) + rng.choice([0.0, 0.25, 0.5]),
                 float(rng.randint(20, 40)), rng.choice(["a", "b", "c"]), rng.choice([0, 0, 5]))
                for _ in range(rng.randint(1, 12))
            ]
            assert copy(keys) == rank_quote_ordinals(keys)
