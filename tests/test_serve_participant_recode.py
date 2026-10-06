"""§J7 R2: a speaker recoded into or out of participant, relabel only.

``docs/design-people.md`` §J7. Held on the slot like R1, and nothing is
re-analysed. Two things follow that R1 never had to carry:

- **Out of participant**, the session's quotes are the moderator's words: they
  leave every evidence surface (the Quotes lens, the dashboard, search, the
  exports), hidden and never deleted, so the undo brings them back with their
  stars. One predicate, ``speaker_slots.evidence_out``.
- **Into participant**, the speaker is a research subject now, so an anonymised
  export blanks their name — the privacy gate, which works only because every
  route emits the code of what the speaker *is*, never the tag's letter.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_serve_moderator_identities import _TWO, _client, _project, _reimport, _slots


def _with_quotes(tmp_path: Path) -> Path:
    project = _project(tmp_path, _TWO)
    inter = project / "bristlenose-output" / ".bristlenose" / "intermediate"
    quotes = [
        {"session_id": sid, "participant_id": pid, "start_timecode": 10.0,
         "end_timecode": 18.0, "text": f"Quote from {pid}", "topic_label": "Start",
         "quote_type": "screen_specific", "sentiment": "delight", "intensity": 2}
        for sid, pid in (("s1", "p1"), ("s2", "p2"))
    ]
    (inter / "screen_clusters.json").write_text(json.dumps([{
        "screen_label": "Start", "description": "", "display_order": 1, "quotes": quotes,
    }]))
    return project


def _quote_ids(client: TestClient) -> set[str]:
    body = client.get("/api/projects/1/quotes").json()
    return {q["dom_id"] for group in ("sections", "themes")
            for g in body[group] for q in g["quotes"]}


def _martin(client: TestClient) -> str:
    return _slots(client)[("s1", "m1")]["person"]


class TestOutOfParticipant:
    def test_p1_recoded_as_the_moderator_reads_as_them(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1",
                          json={"kind": "moderator", "person": _martin(client)})
        assert resp.status_code == 200, resp.text
        slot = _slots(client)[("s1", "p1")]
        assert (slot["speaker_code"], slot["role"], slot["name"]) == ("m1", "researcher", "Martin")

    def test_the_sessions_quotes_leave_the_evidence_and_the_others_stay(
        self, tmp_path: Path,
    ) -> None:
        client = _client(_with_quotes(tmp_path))
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}
        client.put("/api/projects/1/sessions/s1/speakers/p1",
                   json={"kind": "moderator", "person": _martin(client)})
        assert _quote_ids(client) == {"q-p2-10"}
        stats = client.get("/api/projects/1/dashboard").json()
        assert all(fq["participant_id"] != "p1" for fq in stats["featured_quotes"])
        info = client.get("/api/projects/1/info").json()
        assert info["participant_count"] == 1

    def test_undo_brings_the_participant_and_their_starred_quote_back(
        self, tmp_path: Path,
    ) -> None:
        client = _client(_with_quotes(tmp_path))
        client.put("/api/projects/1/starred", json={"q-p1-10": True})
        client.put("/api/projects/1/sessions/s1/speakers/p1",
                   json={"kind": "moderator", "person": _martin(client)})
        # The undo the picker sends: the role, and no uuid — a participant's
        # never leaves the server.
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1",
                          json={"kind": "participant", "confirmed": True})
        assert resp.status_code == 200, resp.text
        slot = _slots(client)[("s1", "p1")]
        assert (slot["speaker_code"], slot["name"], slot["person"]) == ("p1", "P1", "")
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}
        assert client.get("/api/projects/1/starred").json() == {"q-p1-10": True}

    def test_a_re_run_keeps_the_recode_and_leaves_martin_unrenamed(self, tmp_path: Path) -> None:
        project = _with_quotes(tmp_path)
        client = _client(project)
        client.put("/api/projects/1/sessions/s1/speakers/p1",
                   json={"kind": "moderator", "person": _martin(client)})
        _reimport(client, project)
        slot = _slots(client)[("s1", "p1")]
        assert (slot["speaker_code"], slot["name"]) == ("m1", "Martin")
        assert _quote_ids(client) == {"q-p2-10"}

    def test_a_people_write_cannot_rename_the_recoded_slot(self, tmp_path: Path) -> None:
        """The Sessions grid sends the whole people map; a stale ``p1`` entry
        must not land on Martin."""
        client = _client(_with_quotes(tmp_path))
        client.put("/api/projects/1/sessions/s1/speakers/p1",
                   json={"kind": "moderator", "person": _martin(client)})
        client.put("/api/projects/1/people",
                   json={"p1": {"full_name": "Someone Else", "short_name": "SE", "role": ""}})
        assert _slots(client)[("s1", "m1")]["name"] == "Martin"

    def test_no_read_still_credits_the_recoded_participant(self, tmp_path: Path) -> None:
        """The R2 route walk: after p1 is recoded as the moderator, no project
        read may emit ``p1`` as anyone's code or credit."""
        import re

        client = _client(_with_quotes(tmp_path))
        client.put("/api/projects/1/sessions/s1/speakers/p1",
                   json={"kind": "moderator", "person": _martin(client)})
        spec = client.app.openapi()
        prefix = "/api/projects/{project_id}"
        codes: list[str] = []
        called = 0

        def walk(value: object, key: str = "") -> None:
            if isinstance(value, dict):
                for k, v in value.items():
                    walk(v, k)
            elif isinstance(value, list):
                for v in value:
                    walk(v, key)
            elif isinstance(value, str) and key in {"code", "speaker_code", "participant_id"}:
                codes.append(value)

        for path, item in spec["paths"].items():
            if "get" not in item or not path.startswith(prefix):
                continue
            params = set(re.findall(r"\{(\w+)\}", path)) - {"project_id"}
            if params - {"session_id"}:
                continue
            for sid in (["s1", "s2"] if "session_id" in params else [None]):
                url = path.replace("{project_id}", "1").replace("{session_id}", sid or "")
                resp = client.get(url)
                if resp.status_code != 200 or "json" not in resp.headers.get("content-type", ""):
                    continue
                called += 1
                walk(resp.json())
        assert called >= 5
        assert "p2" in codes, "the other participant is still there"
        assert "p1" not in codes, "a read still credits the recoded participant"


class TestPrivacyReview:
    """Two holes the privacy review found in the first R2 build."""

    def test_out_of_participant_must_say_who_they_were(self, tmp_path: Path) -> None:
        """A role alone would leave the participant's own record on a moderator
        slot — named, uuid on the wire, and kept by an anonymised export."""
        client = _client(_with_quotes(tmp_path))
        for body in ({"kind": "moderator"}, {"kind": "moderator", "full_name": "Bob"}):
            resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json=body)
            assert resp.status_code == 409, body
        slot = _slots(client)[("s1", "p1")]
        assert (slot["speaker_code"], slot["name"], slot["person"]) == ("p1", "P1", "")

    def test_a_moderator_elsewhere_recoded_into_participant_gets_their_own_record(
        self, tmp_path: Path,
    ) -> None:
        """Martin moderates s1; recoding s2's moderator as Martin-the-participant
        must not share his team identity, which stays named in an export."""
        client = _client(_with_quotes(tmp_path))
        martin = _martin(client)
        client.put("/api/projects/1/sessions/s2/speakers/m1",
                   json={"kind": "moderator", "person": martin})
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1",
                          json={"kind": "participant", "person": martin})
        assert resp.status_code == 200, resp.text
        slots = _slots(client)
        assert slots[("s1", "m1")]["person"] == martin
        assert (slots[("s2", "m1")]["speaker_code"], slots[("s2", "m1")]["person"]) == ("p3", "")
        # Renaming the participant does not rename the moderator.
        client.put("/api/projects/1/sessions/s2/speakers/m1",
                   json={"kind": "participant", "full_name": "M S", "short_name": "MS"})
        assert _slots(client)[("s1", "m1")]["name"] == "Martin"


class TestCodeReview:
    """Holes the code review found in the first R2 build."""

    def test_picking_the_moderator_under_participant_means_back_to_who_they_were(
        self, tmp_path: Path,
    ) -> None:
        """The Participant segment of a recoded-out slot offers the moderator it
        holds; picking it must not make the moderator a participant and orphan
        the participant."""
        client = _client(_with_quotes(tmp_path))
        martin = _martin(client)
        client.put("/api/projects/1/sessions/s1/speakers/p1", json={"kind": "moderator", "person": martin})
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1",
                          json={"kind": "participant", "person": martin})
        assert resp.status_code == 200, resp.text
        slots = _slots(client)
        assert (slots[("s1", "p1")]["speaker_code"], slots[("s1", "p1")]["name"]) == ("p1", "P1")
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}
        # Martin is still free to moderate.
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1", json={"person": martin})
        assert resp.status_code == 200, resp.text

    def test_a_moderator_recoded_in_is_still_free_to_moderate_elsewhere(
        self, tmp_path: Path,
    ) -> None:
        client = _client(_with_quotes(tmp_path))
        kerri = _slots(client)[("s2", "m1")]["person"]
        client.put("/api/projects/1/sessions/s2/speakers/m1",
                   json={"kind": "participant", "person": kerri})
        resp = client.put("/api/projects/1/sessions/s1/speakers/m1", json={"person": kerri})
        assert resp.status_code == 200, resp.text
        assert _slots(client)[("s1", "m1")]["name"] == "Kerri"


class TestIntoParticipant:
    def _recode_kerri(self, client: TestClient) -> None:
        kerri = _slots(client)[("s2", "m1")]["person"]
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1",
                          json={"kind": "participant", "person": kerri})
        assert resp.status_code == 200, resp.text

    def test_a_moderator_recoded_as_a_participant_takes_a_new_number(
        self, tmp_path: Path,
    ) -> None:
        client = _client(_with_quotes(tmp_path))
        self._recode_kerri(client)
        slot = _slots(client)[("s2", "m1")]
        assert (slot["speaker_code"], slot["role"], slot["name"]) == ("p3", "participant", "Kerri")
        assert slot["person"] == "", "a participant carries no uuid"

    def test_an_anonymised_export_blanks_them(self, tmp_path: Path) -> None:
        """The privacy gate (§J7 R2): Kerri is a participant now, so every
        surface the export embeds must lose her name."""
        from bristlenose.server.routes.export import _anonymise_data

        client = _client(_with_quotes(tmp_path))
        self._recode_kerri(client)
        endpoints = {
            path: client.get(f"/api/projects/1{path}").json()
            for path in ("/people", "/sessions", "/dashboard", "/quotes",
                         "/transcripts/s1", "/transcripts/s2")
        }
        assert "Kerri" in json.dumps(endpoints)
        _anonymise_data(endpoints)
        assert "Kerri" not in json.dumps(endpoints)

    def test_another_participant_cannot_be_picked(self, tmp_path: Path) -> None:
        """That would join two people; a recode does not."""
        client = _client(_with_quotes(tmp_path))
        resp = client.put("/api/projects/1/sessions/s2/speakers/m1",
                          json={"kind": "participant", "person": "p1"})
        assert resp.status_code == 409

    def test_undo_makes_them_the_moderator_again(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        kerri = _slots(client)[("s2", "m1")]["person"]
        self._recode_kerri(client)
        client.put("/api/projects/1/sessions/s2/speakers/m1",
                   json={"kind": "moderator", "person": kerri})
        slot = _slots(client)[("s2", "m1")]
        assert (slot["speaker_code"], slot["name"], slot["person"]) == ("m2", "Kerri", kerri)


def test_014_adds_the_held_participant_to_a_013_database(tmp_path: Path) -> None:
    import sqlalchemy as sa

    from bristlenose.server.db import init_db, run_migrations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    init_db(engine)
    with engine.connect() as conn:
        conn.execute(sa.text("ALTER TABLE session_speakers DROP COLUMN participant_person_id"))
        conn.execute(sa.text("UPDATE alembic_version SET version_num = '013'"))
        conn.commit()
    run_migrations(engine)
    with engine.connect() as conn:
        columns = {c["name"] for c in sa.inspect(conn).get_columns("session_speakers")}
    assert "participant_person_id" in columns


def test_the_tapestry_draws_a_recoded_participant_on_the_moderators_track(tmp_path: Path) -> None:
    """``/tapestry`` carries ``team`` per turn from the slot's role, so the
    timeline never reads the tag's letter (the tapestry session's ask)."""
    client = _client(_with_quotes(tmp_path))
    client.put("/api/projects/1/sessions/s1/speakers/p1",
               json={"kind": "moderator", "person": _martin(client)})
    sessions = client.get("/api/projects/1/tapestry").json()["sessions"]
    s1 = next(s for s in sessions if s["session_id"] == "s1")
    assert {t["speaker"]: t["team"] for t in s1["turns"]} == {"m1": True, "p1": True}
    s2 = next(s for s in sessions if s["session_id"] == "s2")
    assert {t["speaker"]: t["team"] for t in s2["turns"]} == {"m1": True, "p2": False}


class TestSwap:
    """§J7 call 4: the pipeline called the moderator ``p1`` and the participant
    ``m1``. One act, never a moment with no participant, and its own undo."""

    def _swap(self, client: TestClient) -> None:
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        assert resp.status_code == 200, resp.text

    def test_the_two_exchange_roles_and_people(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        martin = _martin(client)
        self._swap(client)
        slots = _slots(client)
        assert (slots[("s1", "p1")]["speaker_code"], slots[("s1", "p1")]["name"],
                slots[("s1", "p1")]["person"]) == ("m1", "Martin", martin)
        assert (slots[("s1", "m1")]["speaker_code"], slots[("s1", "m1")]["name"],
                slots[("s1", "m1")]["person"]) == ("p3", "P1", "")
        assert _quote_ids(client) == {"q-p2-10"}, "the moderator's words leave the evidence"

    def test_swapping_again_puts_everything_back(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        before = _slots(client)
        self._swap(client)
        resp = client.put("/api/projects/1/sessions/s1/speakers/m1", json={"swap_with": "p1"})
        assert resp.status_code == 200, resp.text
        assert _slots(client) == before
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}

    def test_the_participant_is_anonymised_where_they_now_sit(self, tmp_path: Path) -> None:
        from bristlenose.server.routes.export import _anonymise_data

        client = _client(_with_quotes(tmp_path))
        client.put("/api/projects/1/people",
                   json={"p1": {"full_name": "Wylie Coyote", "short_name": "Wylie", "role": ""}})
        self._swap(client)
        endpoints = {
            path: client.get(f"/api/projects/1{path}").json()
            for path in ("/people", "/sessions", "/dashboard", "/transcripts/s1")
        }
        assert "Wylie" in json.dumps(endpoints)
        _anonymise_data(endpoints)
        assert "Wylie" not in json.dumps(endpoints)

    def test_a_swap_between_two_recodes_unwinds_back_to_the_start(self, tmp_path: Path) -> None:
        """Review, 6 Oct: the swap must leave an earlier recode's way home intact."""
        client = _client(_with_quotes(tmp_path))
        before = _slots(client)
        martin, kerri = _martin(client), _slots(client)[("s2", "m1")]["person"]
        def put(slot: str, body: dict):
            return client.put(f"/api/projects/1/sessions/s1/speakers/{slot}", json=body)

        assert put("p1", {"kind": "moderator", "person": kerri}).status_code == 200
        assert put("m1", {"kind": "participant", "person": martin}).status_code == 200
        assert put("p1", {"swap_with": "m1"}).status_code == 200
        # Undo, newest first: the swap, the recode in, the recode out.
        assert put("p1", {"swap_with": "m1"}).status_code == 200
        assert put("m1", {"kind": "moderator", "person": martin}).status_code == 200
        assert put("p1", {"kind": "participant", "confirmed": True}).status_code == 200
        after = _slots(client)
        assert {k: (v["speaker_code"], v["name"]) for k, v in after.items()} == {
            k: (v["speaker_code"], v["name"]) for k, v in before.items()
        }
        assert _quote_ids(client) == {"q-p1-10", "q-p2-10"}

    def test_a_slot_with_nobody_swaps_as_nobody(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        client.put("/api/projects/1/sessions/s1/speakers/m1", json={"clear": True})
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        assert resp.status_code == 200, resp.text
        slots = _slots(client)
        assert (slots[("s1", "p1")]["speaker_code"], slots[("s1", "p1")]["name"]) == ("m?", "")
        assert slots[("s1", "m1")]["name"] == "P1"

    def test_an_unknown_speaker_is_not_found(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "o9"})
        assert resp.status_code == 404

    def test_two_of_the_team_are_not_swapped(self, tmp_path: Path) -> None:
        client = _client(_with_quotes(tmp_path))
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "p1"})
        assert resp.status_code == 404
        kerri = _slots(client)[("s2", "m1")]["person"]
        client.put("/api/projects/1/sessions/s1/speakers/p1",
                   json={"kind": "observer", "person": kerri})
        resp = client.put("/api/projects/1/sessions/s1/speakers/p1", json={"swap_with": "m1"})
        assert resp.status_code == 409
