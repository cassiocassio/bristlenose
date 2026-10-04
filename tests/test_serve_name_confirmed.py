"""A speaker's name is a proposal until a person says yes to it.

``session_speakers.name_confirmed`` (migration 012) is route C's slot state,
the part the person picker needs (``docs/design-people.md`` § UX iteration 3):
a name the pipeline found is drawn as proposed — a dotted ring, a grey name —
and the picker's Enter, or any typed or picked name, confirms it.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from fastapi.testclient import TestClient

from tests.test_serve_per_session_moderators import _PER_SESSION, _client, _project


def _confirmed(client: TestClient) -> dict[tuple[str, str], bool]:
    sessions = client.get("/api/projects/1/sessions").json()["sessions"]
    return {
        (s["session_id"], sp["speaker_code"]): sp["name_confirmed"]
        for s in sessions for sp in s["speakers"]
    }


class TestProposedUntilConfirmed:
    def test_pipeline_names_arrive_proposed(self, tmp_path: Path) -> None:
        confirmed = _confirmed(_client(_project(tmp_path, session_names=_PER_SESSION)))
        assert confirmed and not any(confirmed.values())

    def test_a_typed_name_confirms_only_that_session(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"short_name": "Joanna"})
        confirmed = _confirmed(client)
        assert confirmed[("s2", "m1")] is True
        assert confirmed[("s1", "m1")] is False

    def test_confirming_keeps_the_name(self, tmp_path: Path) -> None:
        """The picker's Enter on a proposed name: yes, without a rename."""
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        resp = client.put("/api/projects/1/sessions/s1/speakers/m1", json={"confirmed": True})
        assert resp.status_code == 200
        assert _confirmed(client)[("s1", "m1")] is True
        sessions = client.get("/api/projects/1/sessions").json()["sessions"]
        s1 = next(s for s in sessions if s["session_id"] == "s1")
        assert next(sp for sp in s1["speakers"] if sp["speaker_code"] == "m1")["name"] == "Martin"

    def test_a_role_edit_alone_confirms_nothing(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        client.put("/api/projects/1/sessions/s1/speakers/m1", json={"role": "Lead"})
        assert _confirmed(client)[("s1", "m1")] is False

    def test_people_put_confirms_only_the_participant_it_renamed(self, tmp_path: Path) -> None:
        """The Sessions table sends the whole map on every write; confirming each
        entry it carries would confirm every participant at the first rename."""
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        people = client.get("/api/projects/1/people").json()
        people["p1"]["short_name"] = "Annie"
        assert client.put("/api/projects/1/people", json=people).status_code == 200
        confirmed = _confirmed(client)
        assert confirmed[("s1", "p1")] is True
        assert confirmed[("s2", "p2")] is False


class TestMigration:
    def test_012_adds_the_column_to_an_existing_db(self, tmp_path: Path) -> None:
        """A database at 011 gains the column, every existing name a proposal."""
        from bristlenose.server.db import init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
        init_db(engine)
        with engine.connect() as conn:  # roll the fresh DB back to how 011 left it
            # The row below names no real session or person; foreign keys are
            # switched off for the fixture only, as run_migrations itself does.
            conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
            conn.execute(sa.text("ALTER TABLE session_speakers DROP COLUMN name_confirmed"))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '011'"))
            conn.execute(sa.text(
                "INSERT INTO session_speakers (id, session_id, person_id, speaker_code,"
                " speaker_role, words_spoken, pct_words, pct_time_speaking, source_file)"
                " VALUES (1, 1, 1, 'm1', 'researcher', 0, 0, 0, '')"
            ))
            conn.commit()
        run_migrations(engine)
        with engine.connect() as conn:
            rows = conn.execute(sa.text("SELECT name_confirmed FROM session_speakers")).all()
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        assert rows == [(0,)]
        assert version == "012"


class TestReimportKeepsAConfirmedName:
    def test_a_confirmed_shared_name_is_not_repaired_away(self) -> None:
        """A legacy project gave every session's m1 the shared people.yaml name.
        Once the researcher has said yes to it in one session, a re-import must
        not treat it as a collision and swap in that session's own name."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as DbSession

        from bristlenose.server.importer import _update_persons_from_people
        from bristlenose.server.models import Base, Person, SessionSpeaker

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with DbSession(engine) as db:
            shared = {"full_name": "Martin Storey", "short_name": "Martin"}
            yes = Person(full_name="Martin Storey", short_name="Martin")
            guess = Person(full_name="Martin Storey", short_name="Martin")
            db.add_all([yes, guess])
            db.flush()
            confirmed = SessionSpeaker(session_id=1, person_id=yes.id, speaker_code="m1",
                                       speaker_role="researcher", name_confirmed=True)
            proposed = SessionSpeaker(session_id=2, person_id=guess.id, speaker_code="m1",
                                      speaker_role="researcher", name_confirmed=False)
            own = {"m1": {"full_name": "Kerri Ng", "short_name": "Kerri"}}
            _update_persons_from_people(db, [confirmed], {"m1": shared}, own)
            _update_persons_from_people(db, [proposed], {"m1": shared}, own)
            assert (yes.full_name, yes.short_name) == ("Martin Storey", "Martin")
            # The proposed collision is still repaired, as before.
            assert (guess.full_name, guess.short_name) == ("Kerri Ng", "Kerri")
