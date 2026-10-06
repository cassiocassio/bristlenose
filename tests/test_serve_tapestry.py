"""GET /api/projects/{id}/tapestry — the Sessions grid's timeline slice."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def client() -> TestClient:
    return AuthTestClient(create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://"))


def _session(client: TestClient) -> dict:
    data = client.get("/api/projects/1/tapestry").json()
    assert [s["session_id"] for s in data["sessions"]] == ["s1"]
    return data["sessions"][0]


def test_turns_merge_segments_and_cover_the_recording(client: TestClient) -> None:
    s = _session(client)
    turns = s["turns"]
    assert all(a["speaker"] != b["speaker"] for a, b in zip(turns, turns[1:]))  # merged
    assert all(a["t1"] == b["t0"] for a, b in zip(turns, turns[1:]))           # contiguous
    assert turns[-1]["t1"] == s["duration_seconds"]
    assert {t["speaker"][0] for t in turns} == {"m", "p"}


def test_every_quote_is_in_one_section_or_one_theme(client: TestClient) -> None:
    quotes = _session(client)["quotes"]
    assert quotes
    assert all((q["section"] is None) != (q["theme"] is None) for q in quotes)


def test_section_flags_sit_at_each_sections_first_quote(client: TestClient) -> None:
    s = _session(client)
    firsts: dict[str, float] = {}
    for q in s["quotes"]:
        if q["section"] and q["section"] not in firsts:
            firsts[q["section"]] = q["t0"]
    assert [(f["label"], f["t0"]) for f in s["sections"]] == sorted(firsts.items(), key=lambda kv: kv[1])


def test_hidden_quotes_are_left_out(client: TestClient) -> None:
    before = len(_session(client)["quotes"])
    quotes = client.get("/api/projects/1/quotes").json()
    dom_id = next(q["dom_id"] for sec in quotes["sections"] for q in sec["quotes"])
    assert client.put("/api/projects/1/hidden", json={dom_id: True}).status_code == 200
    assert len(_session(client)["quotes"]) == before - 1


def test_quote_edits_apply_and_long_quotes_say_they_are_cut(client: TestClient) -> None:
    quotes = client.get("/api/projects/1/quotes").json()
    dom_id = next(q["dom_id"] for sec in quotes["sections"] for q in sec["quotes"])
    long = "edited " + "word " * 200
    assert client.put("/api/projects/1/edits", json={dom_id: long}).status_code == 200
    texts = [q["text"] for q in _session(client)["quotes"]]
    cut = [t for t in texts if t.startswith("edited ")]
    assert len(cut) == 1 and cut[0].endswith("…") and len(cut[0]) <= 401


def test_no_colours_file_means_no_colours(client: TestClient) -> None:
    assert all(t["colour"] is None for t in _session(client)["turns"])


def test_scene_colours_are_matched_to_turns_by_time(tmp_path: Path) -> None:
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    out = project / "bristlenose-output" / ".bristlenose" / "intermediate" / "scene-colours"
    out.mkdir(parents=True)
    # Pipeline turns need not match today's: a colour applies to the turn whose midpoint it covers.
    out.joinpath("s1.json").write_text(json.dumps({"version": 1, "turns": [
        {"t0": 0, "t1": 30, "speaker": "x", "colour": "#aabbcc", "share": 0.4},
        # The pipeline's last turn ends at the last speech, short of the recording's end; the
        # route's last turn runs to the end, so its midpoint can fall past this one.
        {"t0": 30, "t1": 40, "speaker": "x", "colour": "#112233", "share": 0.3},
    ]}))
    client = AuthTestClient(create_app(project_dir=project, dev=True, db_url="sqlite://"))
    turns = _session(client)["turns"]
    for t in turns:
        assert t["colour"] == ("#aabbcc" if (t["t0"] + t["t1"]) / 2 < 30 else "#112233")
    assert turns[-1]["colour"] == "#112233"


def test_an_unreadable_colours_file_degrades_to_none(tmp_path: Path) -> None:
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    out = project / "bristlenose-output" / ".bristlenose" / "intermediate" / "scene-colours"
    out.mkdir(parents=True)
    out.joinpath("s1.json").write_text("{not json")
    client = AuthTestClient(create_app(project_dir=project, dev=True, db_url="sqlite://"))
    assert all(t["colour"] is None for t in _session(client)["turns"])


def test_unknown_project_is_404(client: TestClient) -> None:
    assert client.get("/api/projects/99/tapestry").status_code == 404
