"""Each session's moderator keeps its own name in serve.

Moderator and observer codes restart per session, so every session's first
moderator is ``m1`` — and ``people.yaml``, keyed by code, held one name for all
of them. The pipeline now writes each session's own names
(``.bristlenose/intermediate/session-speakers.json``); serve names ``m*``/``o*``
speakers from that, and renames them one session at a time. The owner's
weekend fix of 3 Oct 2026, a step towards route C (``docs/design-people.md``
§H H9).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_TRANSCRIPT = (
    "# Transcript: {sid}\n# Date: 2026-09-{day}\n# Duration: 00:01:00\n\n"
    "[00:02] [m1] Welcome, thanks for coming.\n"
    "[00:10] [{pid}] Thanks for having me.\n"
)


def _project(tmp_path: Path, *, session_names: dict | None) -> Path:
    out = tmp_path / "bristlenose-output"
    inter = out / ".bristlenose" / "intermediate"
    inter.mkdir(parents=True)
    (inter / "metadata.json").write_text('{"project_name": "Two moderators"}', encoding="utf-8")
    (inter / "screen_clusters.json").write_text("[]", encoding="utf-8")
    (inter / "theme_groups.json").write_text("[]", encoding="utf-8")
    raw = out / "transcripts-raw"
    raw.mkdir()
    for sid, pid, day in (("s1", "p1", "20"), ("s2", "p2", "21")):
        (raw / f"{sid}.txt").write_text(_TRANSCRIPT.format(sid=sid, pid=pid, day=day), encoding="utf-8")

    # What the pipeline writes today: one m1 entry, the last session's name.
    def entry(full: str, short: str) -> dict:
        return {"computed": {"participant_id": "x", "session_id": "s1"},
                "editable": {"full_name": full, "short_name": short, "role": ""}}

    (out / "people.yaml").write_text(yaml.safe_dump({"participants": {
        "p1": entry("Ann Archer", "Ann"),
        "p2": entry("Bea Baker", "Bea"),
        "m1": entry("Jo Lee", "Jo"),
    }}), encoding="utf-8")
    if session_names is not None:
        (inter / "session-speakers.json").write_text(
            json.dumps({"version": 1, "sessions": session_names}), encoding="utf-8"
        )
    return tmp_path


_PER_SESSION = {
    "s1": {"m1": {"full_name": "Martin Storey", "short_name": "Martin", "role": "UX researcher"}},
    "s2": {"m1": {"full_name": "Jo Lee", "short_name": "Jo", "role": ""}},
}


def _client(project_dir: Path) -> TestClient:
    return AuthTestClient(create_app(project_dir=project_dir, dev=True, db_url="sqlite://"))


def _speaker_names(client: TestClient) -> dict[tuple[str, str], str]:
    sessions = client.get("/api/projects/1/sessions").json()["sessions"]
    return {
        (s["session_id"], sp["speaker_code"]): sp["name"]
        for s in sessions for sp in s["speakers"]
    }


class TestImport:
    def test_each_session_names_its_own_moderator(self, tmp_path: Path) -> None:
        names = _speaker_names(_client(_project(tmp_path, session_names=_PER_SESSION)))
        assert names[("s1", "m1")] == "Martin"
        assert names[("s2", "m1")] == "Jo"
        # Participants are still named from people.yaml.
        assert names[("s1", "p1")] == "Ann"
        assert names[("s2", "p2")] == "Bea"

    def test_both_moderators_reach_the_header(self, tmp_path: Path) -> None:
        body = _client(_project(tmp_path, session_names=_PER_SESSION)).get(
            "/api/projects/1/sessions"
        ).json()
        assert sorted(body["moderator_names"]) == ["Jo", "Martin"]

    def test_a_session_without_a_name_is_not_given_the_shared_one(self, tmp_path: Path) -> None:
        only_s2 = {"s2": _PER_SESSION["s2"]}
        names = _speaker_names(_client(_project(tmp_path, session_names=only_s2)))
        assert names[("s1", "m1")] == "", "people.yaml's m1 belongs to whichever session ran last"
        assert names[("s2", "m1")] == "Jo"

    def test_a_project_not_re_run_falls_back_to_people_yaml(self, tmp_path: Path) -> None:
        names = _speaker_names(_client(_project(tmp_path, session_names=None)))
        assert names[("s1", "m1")] == names[("s2", "m1")] == "Jo"  # as before the fix


class TestRename:
    def test_renaming_one_sessions_moderator_leaves_the_other(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        resp = client.put(
            "/api/projects/1/sessions/s2/speakers/m1",
            json={"short_name": "Joanna"},
        )
        assert resp.status_code == 200
        names = _speaker_names(client)
        assert names[("s2", "m1")] == "Joanna"
        assert names[("s1", "m1")] == "Martin"

    def test_only_the_fields_sent_change(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        client.put("/api/projects/1/sessions/s1/speakers/m1", json={"short_name": "Marty"})
        client.put("/api/projects/1/sessions/s1/speakers/m1", json={"role": "Lead"})
        transcript = client.get("/api/projects/1/transcripts/s1").json()
        mod = next(sp for sp in transcript["speakers"] if sp["code"] == "m1")
        assert mod["name"] == "Marty"

    def test_people_put_no_longer_touches_a_moderator(self, tmp_path: Path) -> None:
        """The Sessions table sends the whole code-keyed map on every rename,
        including /people's single ``m1`` entry — which used to be written onto
        whichever session's m1 came first."""
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        people = client.get("/api/projects/1/people").json()
        people["p1"]["short_name"] = "Annie"
        people["m1"] = {"full_name": "Someone Else", "short_name": "Else", "role": ""}
        assert client.put("/api/projects/1/people", json=people).status_code == 200
        names = _speaker_names(client)
        assert names[("s1", "p1")] == "Annie"
        assert names[("s1", "m1")] == "Martin"
        assert names[("s2", "m1")] == "Jo"
        # …and the shared people.yaml m1 entry is not rewritten either.
        written = yaml.safe_load((tmp_path / "bristlenose-output" / "people.yaml").read_text(encoding="utf-8"))
        assert written["participants"]["m1"]["editable"]["short_name"] == "Jo"

    def test_unknown_session_or_speaker_is_404(self, tmp_path: Path) -> None:
        client = _client(_project(tmp_path, session_names=_PER_SESSION))
        assert client.put("/api/projects/1/sessions/s9/speakers/m1", json={}).status_code == 404
        assert client.put("/api/projects/1/sessions/s1/speakers/m7", json={}).status_code == 404


class TestReimportOfAProjectImportedBeforeTheFix:
    """A project imported before the per-session file existed has the shared
    people.yaml m1 name on every session's moderator. Re-running it must fix
    that, while a name the researcher has since given one session survives."""

    def _reimport(self, client: TestClient, project_dir: Path) -> None:
        from bristlenose.server.importer import import_project

        db = client.app.state.db_factory()
        try:
            import_project(db, project_dir)
            db.commit()
        finally:
            db.close()

    def test_re_run_replaces_the_collided_name(self, tmp_path: Path) -> None:
        project_dir = _project(tmp_path, session_names=None)
        client = _client(project_dir)
        assert _speaker_names(client)[("s1", "m1")] == "Jo"  # collided, as before

        inter = tmp_path / "bristlenose-output" / ".bristlenose" / "intermediate"
        (inter / "session-speakers.json").write_text(
            json.dumps({"version": 1, "sessions": _PER_SESSION}), encoding="utf-8"
        )
        self._reimport(client, project_dir)
        names = _speaker_names(client)
        assert names[("s1", "m1")] == "Martin"
        assert names[("s2", "m1")] == "Jo"

    def test_a_per_session_rename_survives_re_import(self, tmp_path: Path) -> None:
        project_dir = _project(tmp_path, session_names=_PER_SESSION)
        client = _client(project_dir)
        client.put("/api/projects/1/sessions/s2/speakers/m1", json={"short_name": "Joanna"})
        self._reimport(client, project_dir)
        names = _speaker_names(client)
        assert names[("s2", "m1")] == "Joanna"
        assert names[("s1", "m1")] == "Martin"
