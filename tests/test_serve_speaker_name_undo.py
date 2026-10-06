"""The server half of undoing a speaker name: a slot goes back to exactly what it held.

Edit ▸ Undo after a pick, a confirm or a typed name restores the name *and* the
confirmed state (``docs/design-people.md`` §B10). The SPA does that with the
routes it already writes through, so these pin the parts it relies on: that
``/sessions`` reports both stored names, and that an explicit
``{"confirmed": false}`` returns a slot to proposed even when the same request
carries a name — the rule that a sent name confirms must not swallow an undo.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from tests.test_serve_per_session_moderators import _PER_SESSION, _client, _project


def _slot(client: TestClient, sid: str, code: str) -> dict:
    """By the transcript's slot code: ``speaker_code`` is the identity's
    (route C Phase 1), and a pick can change it."""
    sessions = client.get("/api/projects/1/sessions").json()["sessions"]
    sess = next(s for s in sessions if s["session_id"] == sid)
    return next(sp for sp in sess["speakers"] if sp["slot_code"] == code)


def _state(slot: dict) -> tuple[str, str, bool]:
    return slot["full_name"], slot["short_name"], slot["name_confirmed"]


class TestSessionsReportsBothNames:
    def test_full_and_short_name_are_reported(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        assert _state(_slot(client, "s1", "m1")) == ("Martin Storey", "Martin", False)


class TestUndoAModeratorPick:
    def test_restoring_the_before_state_returns_the_slot_to_proposed(
        self, tmp_path: Path,
    ) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        before = _slot(client, "s1", "m1")
        # The pick names the person by uuid (design-people.md §J8, answer 2).
        # Jo is session 2's moderator, so s1 now points at them, and they keep
        # their own names.
        jo = _slot(client, "s2", "m1")["person"]
        client.put("/api/projects/1/sessions/s1/speakers/m1", json={"person": jo})
        assert _state(_slot(client, "s1", "m1")) == ("Jo Lee", "Jo", True)
        assert _slot(client, "s1", "m1")["speaker_code"] == _slot(client, "s2", "m1")[
            "speaker_code"]
        # The undo: one request pointing back at the person the slot held, with
        # their names and the flag. Martin had no other session; he was kept.
        resp = client.put("/api/projects/1/sessions/s1/speakers/m1", json={
            "person": before["person"],
            "full_name": before["full_name"], "short_name": before["short_name"],
            "confirmed": before["name_confirmed"],
        })
        assert resp.status_code == 200
        assert _state(_slot(client, "s1", "m1")) == ("Martin Storey", "Martin", False)

    def test_undoing_a_confirm_keeps_the_name(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"confirmed": True})
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"confirmed": False})
        assert _state(_slot(client, "s2", "m1")) == ("Jo Lee", "Jo", False)


class TestUndoAParticipantRename:
    def test_people_then_confirmed_restores_name_flag_and_yaml(self, tmp_path: Path) -> None:
        """Participants are named through ``/people`` (written through to
        ``people.yaml`` so a re-run keeps the name), which can only confirm.
        The undo writes the old name there, then the flag on the slot."""
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        people = client.get("/api/projects/1/people").json()
        before = dict(people["p1"])
        people["p1"]["short_name"] = "Annie"
        client.put("/api/projects/1/people", json=people)
        assert _slot(client, "s1", "p1")["name_confirmed"] is True

        people = client.get("/api/projects/1/people").json()
        people["p1"] = before
        client.put("/api/projects/1/people", json=people)
        client.put("/api/projects/1/sessions/s1/speakers/p1", json={"confirmed": False})

        assert _state(_slot(client, "s1", "p1")) == ("Ann Archer", "Ann", False)
        written = yaml.safe_load((tmp_path / "bristlenose-output" / "people.yaml").read_text(encoding="utf-8"))
        assert written["participants"]["p1"]["editable"]["short_name"] == "Ann"
