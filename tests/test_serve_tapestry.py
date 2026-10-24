"""GET /api/projects/{id}/tapestry — the Sessions grid's timeline slice."""

from __future__ import annotations

import itertools
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.routes.tapestry import section_visits
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
    assert all(a["speaker"] != b["speaker"] for a, b in itertools.pairwise(turns))  # merged
    assert all(a["t1"] == b["t0"] for a, b in itertools.pairwise(turns))           # contiguous
    assert turns[-1]["t1"] == s["duration_seconds"]
    assert {t["speaker"][0] for t in turns} == {"m", "p"}


def test_every_quote_is_in_one_section_or_one_theme(client: TestClient) -> None:
    quotes = _session(client)["quotes"]
    assert quotes
    assert all((q["section"] is None) != (q["theme"] is None) for q in quotes)


def test_section_flags_sit_at_each_visits_first_quote(client: TestClient) -> None:
    s = _session(client)
    visits: list[tuple[str, float]] = []
    for q in sorted(s["quotes"], key=lambda q: q["t0"]):
        if q["section"] and (not visits or visits[-1][0] != q["section"]):
            visits.append((q["section"], q["t0"]))
    assert visits
    assert [(f["label"], f["t0"]) for f in s["sections"]] == visits


def test_a_section_visited_twice_is_flagged_twice() -> None:
    # The basket, away to a modal, back to the basket: three visits, two places. A theme quote
    # (no section) between two basket quotes neither ends the visit nor starts one.
    flags = section_visits([
        (40.0, "Basket"), (10.0, "Home"), (35.0, None), (30.0, "Basket"),
        (55.0, "Modal"), (70.0, "Basket"), (80.0, "Basket"),
    ])
    assert [(f.label, f.t0) for f in flags] == [("Home", 10.0), ("Basket", 30.0), ("Modal", 55.0), ("Basket", 70.0)]


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
    ]}), encoding="utf-8")
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
    out.joinpath("s1.json").write_text("{not json", encoding="utf-8")
    client = AuthTestClient(create_app(project_dir=project, dev=True, db_url="sqlite://"))
    assert all(t["colour"] is None for t in _session(client)["turns"])


def test_no_strip_file_means_no_strip(client: TestClient) -> None:
    assert _session(client)["strip"] is None


def test_an_unreadable_strip_file_degrades_to_none(tmp_path: Path) -> None:
    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    out = project / "bristlenose-output" / ".bristlenose" / "intermediate" / "scene-strips"
    out.mkdir(parents=True)
    out.joinpath("s1.json").write_text('{"fps": 4}', encoding="utf-8")  # half a record: serve may be mid-write
    client = AuthTestClient(create_app(project_dir=project, dev=True, db_url="sqlite://"))
    assert _session(client)["strip"] is None


def test_unknown_project_is_404(client: TestClient) -> None:
    assert client.get("/api/projects/99/tapestry").status_code == 404


def test_transcription_quality_serves_records_for_known_sessions(tmp_path: Path) -> None:
    from bristlenose import transcription_quality as tq

    project = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, project)
    output = project / "bristlenose-output"
    rec = {"version": tq.RECORD_VERSION, "session_id": "s1", "duration_s": 60.0}
    tq.write_record(output, "s1", rec)
    # A record for a session the project no longer has is not served.
    tq.write_record(output, "s9", {**rec, "session_id": "s9"})
    client = AuthTestClient(create_app(project_dir=project, dev=True, db_url="sqlite://"))
    body = client.get("/api/projects/1/transcription-quality").json()
    assert set(body["sessions"]) == {"s1"}
    assert body["sessions"]["s1"]["duration_s"] == 60.0


def test_transcription_quality_with_no_records_is_empty(client: TestClient) -> None:
    body = client.get("/api/projects/1/transcription-quality").json()
    assert body == {"sessions": {}}
