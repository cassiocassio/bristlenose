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
        (s["session_id"], sp["slot_code"]): sp["name_confirmed"]
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
        assert next(sp for sp in s1["speakers"] if sp["slot_code"] == "m1")["name"] == "Martin"

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
    def test_a_011_db_reaches_head_with_every_name_a_proposal(self, tmp_path: Path) -> None:
        """A database at 011 gains 012's flag and 013 turns it into the slot
        state: every existing name a proposal."""
        from bristlenose.server.db import init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
        init_db(engine)
        with engine.connect() as conn:  # roll the fresh DB back to how 011 left it
            # The row below names no real session or person; foreign keys are
            # switched off for the fixture only, as run_migrations itself does.
            conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
            for column in ("state", "evidence"):
                conn.execute(sa.text(f"ALTER TABLE session_speakers DROP COLUMN {column}"))
            for column in ("code", "uuid", "origin", "me"):
                conn.execute(sa.text(f"ALTER TABLE persons DROP COLUMN {column}"))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '011'"))
            conn.execute(sa.text(
                "INSERT INTO session_speakers (id, session_id, person_id, speaker_code,"
                " speaker_role, words_spoken, pct_words, pct_time_speaking, source_file)"
                " VALUES (1, 1, 1, 'm1', 'researcher', 0, 0, 0, '')"
            ))
            conn.commit()
        run_migrations(engine)
        with engine.connect() as conn:
            rows = conn.execute(sa.text("SELECT state FROM session_speakers")).all()
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        assert rows == [("proposed",)]
        from tests.test_migrations import MIGRATION_HEAD

        assert version == MIGRATION_HEAD


class TestReimportKeepsAConfirmedName:
    def test_a_confirmed_name_is_kept_and_a_proposal_follows_the_evidence(
        self, tmp_path: Path,
    ) -> None:
        """Once the researcher has said yes to a name in one session, a re-import
        bringing other evidence for that session must keep it; a proposed slot
        follows the evidence. (Pinned at 5afae01c against the importer's
        collision repair; re-homed when route C Phase 1 replaced it — the
        per-slot ``state``, not a name comparison, is what keeps it now.)"""
        import json

        from bristlenose.server.importer import import_project

        project = _project(tmp_path, session_names=_PER_SESSION)
        client = _client(project)
        client.put("/api/projects/1/sessions/s1/speakers/m1", json={"confirmed": True})
        inter = tmp_path / "bristlenose-output" / ".bristlenose" / "intermediate"
        other = {sid: {"m1": {"full_name": "Kerri Ng", "short_name": "Kerri", "role": "",
                              "evidence": "platform-name"}} for sid in ("s1", "s2")}
        (inter / "session-speakers.json").write_text(
            json.dumps({"version": 2, "sessions": other})
        )
        db = client.app.state.db_factory()
        try:
            import_project(db, project)
            db.commit()
        finally:
            db.close()
        sessions = client.get("/api/projects/1/sessions").json()["sessions"]
        names = {(s["session_id"], sp["slot_code"]): (sp["name"], sp["name_confirmed"])
                 for s in sessions for sp in s["speakers"]}
        assert names[("s1", "m1")] == ("Martin", True)
        assert names[("s2", "m1")] == ("Kerri", False)
