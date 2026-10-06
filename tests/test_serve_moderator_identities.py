"""Route C, Phase 1: a moderator is an identity, and a session's slot points at one.

Moderator and observer codes restart in every session, so the token ``m1`` in a
transcript is a *slot* — "the first moderator of this session" — not a person.
Phase 1 (``docs/design-people.md`` §H H9) gives each moderator and observer a
``Person`` with a project-wide code, numbered as they first appear, and makes
``session_speakers.person_id`` the per-session map: ``null`` when nothing
identifies the slot (rendered ``m?``), ``proposed`` when the pipeline's evidence
named it, ``confirmed`` when a person said so. Every route emits the identity's
code, so session 2's moderator reads ``m2`` wherever it appears, and nothing a
client looks up by code can fetch another session's moderator.
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
import yaml
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_TRANSCRIPT = (
    "# Transcript: {sid}\n# Date: 2026-09-{day}\n# Duration: 00:01:00\n\n"
    "[00:02] [m1] Welcome, thanks for coming in today.\n"
    "[00:10] [{pid}] Thanks for having me, it is good to be here.\n"
    "[00:20] [m1] Shall we start?\n"
)


def _entry(full: str, evidence: str, role: str = "") -> dict:
    return {
        "full_name": full,
        "short_name": full.split()[0] if full else "",
        "role": role,
        "evidence": evidence,
    }


def _project(
    tmp_path: Path,
    names: dict,
    *,
    sessions: tuple[tuple[str, str, str], ...] = (("s1", "p1", "20"), ("s2", "p2", "21")),
    stats: dict | None = None,
) -> Path:
    out = tmp_path / "bristlenose-output"
    inter = out / ".bristlenose" / "intermediate"
    inter.mkdir(parents=True, exist_ok=True)
    (inter / "metadata.json").write_text('{"project_name": "Identities"}')
    (inter / "screen_clusters.json").write_text("[]")
    (inter / "theme_groups.json").write_text("[]")
    raw = out / "transcripts-raw"
    raw.mkdir(exist_ok=True)
    for sid, pid, day in sessions:
        (raw / f"{sid}.txt").write_text(_TRANSCRIPT.format(sid=sid, pid=pid, day=day))
    participants = {
        pid: {"computed": {"participant_id": pid, "session_id": sid},
              "editable": {"full_name": f"Person {pid}", "short_name": pid.upper(), "role": ""}}
        for sid, pid, _ in sessions
    }
    (out / "people.yaml").write_text(yaml.safe_dump({"participants": participants}))
    payload: dict = {"version": 2, "sessions": names}
    if stats is not None:
        payload["stats"] = stats
    (inter / "session-speakers.json").write_text(json.dumps(payload))
    return tmp_path


def _write_names(tmp_path: Path, names: dict) -> None:
    path = tmp_path / "bristlenose-output" / ".bristlenose" / "intermediate"
    (path / "session-speakers.json").write_text(json.dumps({"version": 2, "sessions": names}))


def _client(project_dir: Path) -> TestClient:
    return AuthTestClient(create_app(project_dir=project_dir, dev=True, db_url="sqlite://"))


def _reimport(client: TestClient, project_dir: Path) -> None:
    from bristlenose.server.importer import import_project

    db = client.app.state.db_factory()
    try:
        import_project(db, project_dir)
        db.commit()
    finally:
        db.close()


def _slots(client: TestClient) -> dict[tuple[str, str], dict]:
    """(session, slot code) → the speaker row the Sessions API sends."""
    sessions = client.get("/api/projects/1/sessions").json()["sessions"]
    return {(s["session_id"], sp["slot_code"]): sp for s in sessions for sp in s["speakers"]}


_TWO = {
    "s1": {"m1": _entry("Martin Storey", "platform-name", "UX researcher")},
    "s2": {"m1": _entry("Kerri Lee", "platform-name")},
}


class TestIdentityCodes:
    def test_two_moderators_read_m1_and_m2(self, tmp_path: Path) -> None:
        """The visible change: session 2's moderator is ``m2``, not a second ``m1``."""
        slots = _slots(_client(_project(tmp_path, _TWO)))
        assert (slots[("s1", "m1")]["speaker_code"], slots[("s1", "m1")]["name"]) == ("m1", "Martin")
        assert (slots[("s2", "m1")]["speaker_code"], slots[("s2", "m1")]["name"]) == ("m2", "Kerri")

    def test_people_names_both_moderators_by_their_own_code(self, tmp_path: Path) -> None:
        """The pinned limitation, re-homed: both names survive in the one map."""
        people = _client(_project(tmp_path, _TWO)).get("/api/projects/1/people").json()
        assert people["m1"]["short_name"] == "Martin"
        assert people["m2"]["short_name"] == "Kerri"
        assert people["p1"]["short_name"] == "P1"

    def test_the_transcript_emits_the_identity_code_on_every_segment(self, tmp_path: Path) -> None:
        body = _client(_project(tmp_path, _TWO)).get("/api/projects/1/transcripts/s2").json()
        mods = [sp for sp in body["speakers"] if sp["role"] == "researcher"]
        assert [(sp["code"], sp["name"]) for sp in mods] == [("m2", "Kerri")]
        codes = {seg["speaker_code"] for seg in body["segments"]}
        assert codes == {"m2", "p2"}

    def test_one_platform_name_in_two_sessions_is_one_person(self, tmp_path: Path) -> None:
        """P2: a name-only platform label mints one identity per distinct name."""
        same = {"s1": _TWO["s1"], "s2": {"m1": _entry("Martin Storey", "platform-name")}}
        client = _client(_project(tmp_path, same))
        slots = _slots(client)
        assert slots[("s1", "m1")]["speaker_code"] == slots[("s2", "m1")]["speaker_code"] == "m1"
        assert "m2" not in client.get("/api/projects/1/people").json()

    def test_a_participant_keeps_its_code(self, tmp_path: Path) -> None:
        slots = _slots(_client(_project(tmp_path, _TWO)))
        assert slots[("s2", "p2")]["speaker_code"] == "p2"
        assert slots[("s2", "p2")]["name"] == "P2"

    def test_a_heard_name_is_proposed(self, tmp_path: Path) -> None:
        """A Whisper-only session keeps the name it shows today, as a proposal
        (owner's call pending — ``design-people.md`` H9, finding 4)."""
        heard = {"s1": {"m1": _entry("Dana Whitfield", "heard")}}
        slot = _slots(_client(_project(tmp_path, heard)))[("s1", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["name_confirmed"]) == ("m1", "Dana", False)


class TestUnidentified:
    """A slot nothing names is ``m?`` — never dropped, never another session's."""

    _ONE = {"s1": _TWO["s1"]}  # s2's moderator: no evidence at all

    def test_the_slot_reads_m_question(self, tmp_path: Path) -> None:
        slot = _slots(_client(_project(tmp_path, self._ONE)))[("s2", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["name_confirmed"]) == ("m?", "", False)

    def test_people_has_no_entry_a_lookup_could_hit(self, tmp_path: Path) -> None:
        people = _client(_project(tmp_path, self._ONE)).get("/api/projects/1/people").json()
        assert set(people) == {"m1", "p1", "p2"}

    def test_the_transcript_keeps_the_speaker(self, tmp_path: Path) -> None:
        body = _client(_project(tmp_path, self._ONE)).get("/api/projects/1/transcripts/s2").json()
        assert ("m?", "researcher") in {(sp["code"], sp["role"]) for sp in body["speakers"]}
        assert "m?" in {seg["speaker_code"] for seg in body["segments"]}

    def test_the_inner_joins_keep_it(self, tmp_path: Path) -> None:
        """The sites that inner-joined ``session_speakers`` to ``persons`` (five,
        two of them in grounding; the transcript route is covered above)."""
        from bristlenose.server.export_core import _load_speakers
        from bristlenose.server.grounding import resolve_session_speaker_names
        from bristlenose.server.routes.clips_export import _load_speaker_names

        client = _client(_project(tmp_path, self._ONE))
        db = client.app.state.db_factory()
        try:
            assert ("s2", "m1") in _load_speakers(db, 1)
            assert ("s2", "m1") in _load_speaker_names(db, 1)
            per_session = resolve_session_speaker_names(db, 1)
            assert per_session["s1"] == {"m1": "Martin"}
            assert "m1" not in per_session.get("s2", {})
        finally:
            db.close()


class TestReRun:
    def test_a_confirmed_slot_is_never_touched(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO)
        client = _client(project)
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"confirmed": True})
        _write_names(tmp_path, {"s1": _TWO["s1"], "s2": {"m1": _entry("Someone Else", "heard")}})
        _reimport(client, project)
        slot = _slots(client)[("s2", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["name_confirmed"]) == ("m2", "Kerri", True)

    def test_a_proposal_follows_the_evidence(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO)
        client = _client(project)
        _write_names(tmp_path, {"s1": _TWO["s1"], "s2": {"m1": _entry("Martin Storey", "platform-name")}})
        _reimport(client, project)
        assert _slots(client)[("s2", "m1")]["speaker_code"] == "m1"
        assert "m2" not in client.get("/api/projects/1/people").json(), (
            "an identity no slot uses is hidden (kept, §J8.10)"
        )

    def test_codes_stay_put_across_a_plain_re_run(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO)
        client = _client(project)
        before = {k: v["speaker_code"] for k, v in _slots(client).items()}
        _reimport(client, project)
        assert {k: v["speaker_code"] for k, v in _slots(client).items()} == before


class TestPick:
    def test_the_route_addresses_the_slot_never_the_identity(self, tmp_path: Path) -> None:
        """Both are ``mN``; a pick renumbers identities, so a display code held
        by a stale grid could name a different slot. Only the slot code works."""
        client = _client(_project(tmp_path, _TWO))
        assert client.put(
            "/api/projects/1/sessions/s2/speakers/m1", json={"short_name": "Kez"},
        ).status_code == 200
        assert _slots(client)[("s2", "m1")]["name"] == "Kez"
        assert client.put(
            "/api/projects/1/sessions/s2/speakers/m2", json={"short_name": "No"},
        ).status_code == 404

    def test_picking_a_person_points_the_slot_at_them(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1", json={"person": "m1"})
        assert resp.status_code == 200
        slot = _slots(client)[("s2", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["name_confirmed"]) == ("m1", "Martin", True)
        assert "m2" not in client.get("/api/projects/1/people").json()

    def test_a_name_typed_on_an_unknown_slot_makes_someone_new(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, {"s1": _TWO["s1"]}))
        resp = client.put(
            "/api/projects/1/sessions/s2/speakers/m1",
            json={"full_name": "Kerri Lee", "short_name": "Kerri"},
        )
        assert resp.status_code == 200
        slot = _slots(client)[("s2", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["name_confirmed"]) == ("m2", "Kerri", True)

    def test_confirming_an_unknown_slot_is_refused(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, {"s1": _TWO["s1"]}))
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1", json={"confirmed": True})
        assert resp.status_code == 409

    def test_picking_across_roles_is_refused(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1", json={"person": "p1"})
        assert resp.status_code == 409


class TestStats:
    def test_the_importer_sets_per_session_stats(self, tmp_path: Path) -> None:
        stats = {"s1": {
            "m1": {"words_spoken": 9, "pct_words": 0.0, "pct_time_speaking": 30.0,
                   "source_file": "s1.vtt"},
            "p1": {"words_spoken": 11, "pct_words": 55.0, "pct_time_speaking": 40.0,
                   "source_file": "s1.vtt"},
        }}
        client = _client(_project(tmp_path, _TWO, stats=stats))
        db = client.app.state.db_factory()
        try:
            from bristlenose.server.models import SessionSpeaker

            p1 = db.query(SessionSpeaker).filter_by(speaker_code="p1").one()
            assert (p1.words_spoken, p1.pct_words, p1.pct_time_speaking, p1.source_file) == (
                11, 55.0, 40.0, "s1.vtt",
            )
        finally:
            db.close()


class TestMigration:
    def test_013_moves_the_confirmed_flag_into_the_slot_state(self, tmp_path: Path) -> None:
        from bristlenose.server.db import init_db, run_migrations

        engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
        init_db(engine)
        with engine.connect() as conn:  # roll the fresh DB back to how 012 left it
            conn.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")
            for table, column in (
                ("session_speakers", "state"), ("session_speakers", "evidence"),
                ("persons", "code"), ("persons", "uuid"), ("persons", "origin"),
                ("persons", "me"),
            ):
                conn.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN {column}"))
            conn.execute(sa.text(
                "ALTER TABLE session_speakers ADD COLUMN name_confirmed BOOLEAN"
                " NOT NULL DEFAULT 0"
            ))
            conn.execute(sa.text("UPDATE alembic_version SET version_num = '012'"))
            conn.execute(sa.text(
                "INSERT INTO persons (id, full_name, short_name, role_title, persona, notes,"
                " created_at)"
                " VALUES (1, 'Jo Lee', 'Jo', '', '', '', '2026-10-04'),"
                " (2, 'Ann', 'Ann', '', '', '', '2026-10-04')"
            ))
            conn.execute(sa.text(
                "INSERT INTO session_speakers (id, session_id, person_id, speaker_code,"
                " speaker_role, words_spoken, pct_words, pct_time_speaking, source_file,"
                " name_confirmed) VALUES"
                " (1, 1, 1, 'm1', 'researcher', 0, 0, 0, '', 1),"
                " (2, 1, 2, 'p1', 'participant', 0, 0, 0, '', 0)"
            ))
            conn.commit()
        run_migrations(engine)
        with engine.connect() as conn:
            states = conn.execute(sa.text(
                "SELECT speaker_code, state FROM session_speakers ORDER BY id"
            )).all()
            uuids = conn.execute(sa.text("SELECT uuid FROM persons")).scalars().all()
            columns = {c["name"] for c in sa.inspect(conn).get_columns("session_speakers")}
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
            conn.execute(sa.text(  # person_id is nullable now: the unknown slot
                "INSERT INTO session_speakers (session_id, person_id, speaker_code,"
                " speaker_role, words_spoken, pct_words, pct_time_speaking, source_file)"
                " VALUES (1, NULL, 'm2', 'researcher', 0, 0, 0, '')"
            ))
        assert states == [("m1", "confirmed"), ("p1", "proposed")]
        assert all(uuids) and len(set(uuids)) == 2
        assert "name_confirmed" not in columns
        assert version == "013"


class TestThreeActs:
    """``design-people.md`` §J8, answer 2: a pick points the slot at a person,
    someone new is made by an explicit ``create``, and a name is always a
    spelling fix for the person the slot holds, everywhere. A name never
    decides which act it is, because two people can share one."""

    _SHARED = {
        "s1": {"m1": _entry("Kerri Lee", "platform-name")},
        "s2": {"m1": _entry("Kerri Lee", "platform-name")},
        "s3": {"m1": _entry("Martin Storey", "platform-name")},
    }
    _THREE = (("s1", "p1", "20"), ("s2", "p2", "21"), ("s3", "p3", "22"))

    def _client(self, tmp_path: Path) -> TestClient:
        return _client(_project(tmp_path, self._SHARED, sessions=self._THREE))

    def test_a_name_fixes_the_spelling_everywhere(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"short_name": "Kez"})
        slots = _slots(client)
        assert slots[("s1", "m1")]["name"] == "Kez", "the same person, so every session"
        assert slots[("s1", "m1")]["person"] == slots[("s2", "m1")]["person"]

    def test_a_name_never_joins_two_people(self, tmp_path: Path) -> None:
        """Only a pick joins. A name that matches someone else is refused
        (§J8.11), never read as "point at them"."""
        client = self._client(tmp_path)
        client.put("/api/projects/1/sessions/s2/speakers/m1",
                   json={"full_name": "Martin Storey", "short_name": "Martin"})
        slots = _slots(client)
        assert slots[("s2", "m1")]["person"] != slots[("s3", "m1")]["person"]

    def test_a_pick_by_uuid_points_the_slot_and_keeps_their_names(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        martin = _slots(client)[("s3", "m1")]["person"]
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"person": martin})
        slots = _slots(client)
        assert slots[("s2", "m1")]["person"] == martin
        assert slots[("s2", "m1")]["full_name"] == "Martin Storey"
        assert slots[("s2", "m1")]["name_confirmed"] is True
        assert slots[("s1", "m1")]["name"] == "Kerri", "s1 is untouched"

    def test_create_makes_someone_new_once(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        new = "11111111-2222-4333-8444-555555555555"
        body = {"person": new, "create": True, "full_name": "Dana Whitfield", "short_name": "Dana"}
        assert client.put("/api/projects/1/sessions/s2/speakers/m1", json=body).status_code == 200
        assert client.put("/api/projects/1/sessions/s2/speakers/m1", json=body).status_code == 200
        slots = _slots(client)
        assert (slots[("s2", "m1")]["person"], slots[("s2", "m1")]["name"]) == (new, "Dana")
        assert slots[("s1", "m1")]["name"] == "Kerri"
        assert len({s["speaker_code"] for k, s in slots.items() if k[1] == "m1"}) == 3

    def test_an_unknown_uuid_without_create_is_refused(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1",
                          json={"person": "00000000-0000-4000-8000-000000000000"})
        assert resp.status_code == 404

    def test_clear_returns_the_slot_to_unknown_and_keeps_the_person(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        martin = _slots(client)[("s3", "m1")]["person"]
        client.put("/api/projects/1/sessions/s3/speakers/m1", json={"clear": True})
        slot = _slots(client)[("s3", "m1")]
        assert (slot["speaker_code"], slot["person"]) == ("m?", "")
        # The undo: Martin had no other session, and is still there to point at.
        resp = client.put("/api/projects/1/sessions/s3/speakers/m1",
                          json={"person": martin, "confirmed": False})
        assert resp.status_code == 200
        slot = _slots(client)[("s3", "m1")]
        assert (slot["person"], slot["name"], slot["name_confirmed"]) == (martin, "Martin", False)

    def test_a_participant_is_not_picked(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        martin = _slots(client)[("s3", "m1")]["person"]
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"person": martin})
        assert resp.status_code == 409

    def test_participants_carry_no_uuid(self, tmp_path: Path) -> None:
        """A participant's uuid would link them across studies in an
        anonymised export."""
        client = self._client(tmp_path)
        assert all(s["person"] == "" for k, s in _slots(client).items() if k[1].startswith("p"))

    def test_someone_new_cannot_take_a_name_already_in_the_study(self, tmp_path: Path) -> None:
        """§J8.11: refuse a second "Martin"; the researcher tells them apart."""
        client = self._client(tmp_path)
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1", json={
            "person": "11111111-2222-4333-8444-555555555555", "create": True,
            "full_name": "martin storey", "short_name": "Martin",
        })
        assert resp.status_code == 409
        assert resp.json()["detail"] == {"reason": "name-taken", "name": "Martin Storey"}
        assert _slots(client)[("s2", "m1")]["name"] == "Kerri", "nothing changed"

    def test_a_rename_cannot_take_someone_elses_name(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1", json={"short_name": "Martin"})
        assert resp.status_code == 409

    def test_a_person_may_keep_their_own_name(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        resp = client.put("/api/projects/1/sessions/s3/speakers/m1",
                          json={"full_name": "Martin Storey", "short_name": "Martin"})
        assert resp.status_code == 200


class TestNotThisPerson:
    """§J8.8: the picker's ✕ says "not this person". The slot returns to
    unknown and a re-run must not propose the refused name again."""

    def test_a_cleared_slot_survives_a_re_run(self, tmp_path: Path) -> None:
        project = _project(tmp_path, _TWO)
        client = _client(project)
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"clear": True})
        _reimport(client, project)
        slot = _slots(client)[("s2", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["person"]) == ("m?", "", "")

    def test_a_pick_after_a_clear_still_works(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, _TWO))
        martin = _slots(client)[("s1", "m1")]["person"]
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"clear": True})
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"person": martin})
        assert _slots(client)[("s2", "m1")]["person"] == martin


class TestLetteredUnknowns:
    """§J8.9: two unknown moderators in one session never read as the same
    ``m?``; the letter is the slot's place among that role's speakers."""

    def test_letters_follow_slot_order(self) -> None:
        from bristlenose.server.speaker_slots import lettered

        assert lettered(["m2", "m1"]) == {"m1": "A", "m2": "B"}
        assert lettered(["m1"]) == {}
        assert lettered([f"m{i}" for i in range(1, 29)])["m27"] == "AA"

    def test_two_unknown_moderators_are_ma_and_mb(self, tmp_path: Path) -> None:
        from bristlenose.server.models import SessionSpeaker

        client = _client(_project(tmp_path, {"s1": _TWO["s1"]}))
        db = client.app.state.db_factory()
        try:
            s2 = db.query(SessionSpeaker).filter_by(speaker_code="m1").all()
            sess = [sp for sp in s2 if sp.session.session_id == "s2"][0]
            db.add(SessionSpeaker(session_id=sess.session_id, person_id=None,
                                  speaker_code="m2", speaker_role="researcher"))
            db.commit()
        finally:
            db.close()
        slots = _slots(client)
        assert (slots[("s2", "m1")]["speaker_code"], slots[("s2", "m2")]["speaker_code"]) == (
            "mA?", "mB?",
        )
        assert slots[("s1", "m1")]["speaker_code"] == "m1", "one moderator needs no letter"

    def test_naming_one_leaves_the_others_letter(self, tmp_path: Path) -> None:
        from bristlenose.server.models import SessionSpeaker

        client = _client(_project(tmp_path, {"s1": _TWO["s1"]}))
        db = client.app.state.db_factory()
        try:
            sess = [sp for sp in db.query(SessionSpeaker).filter_by(speaker_code="m1")
                    if sp.session.session_id == "s2"][0]
            db.add(SessionSpeaker(session_id=sess.session_id, person_id=None,
                                  speaker_code="m2", speaker_role="researcher"))
            db.commit()
        finally:
            db.close()
        client.put("/api/projects/1/sessions/s2/speakers/m1",
                   json={"full_name": "Dana Whitfield", "short_name": "Dana"})
        assert _slots(client)[("s2", "m2")]["speaker_code"] == "mB?"
