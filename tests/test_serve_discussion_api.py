"""GET /api/projects/{id}/discussion — the Discussion lens's record, as served.

Codes only (names come from /sessions); a hidden quote is left out and an edited
one shows its edit, so the lens never disagrees with the Quotes lens; a record
built from other quotes reads as stale, never as current.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from bristlenose.discussion.stage import quotes_sha
from bristlenose.models import ExtractedQuote, QuoteType
from bristlenose.server.app import create_app
from bristlenose.server.models import Quote
from tests.conftest import AuthTestClient

_FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "input"
    shutil.copytree(_FIXTURE, root)
    app = create_app(project_dir=root, dev=True, db_url="sqlite://")
    client = AuthTestClient(app)
    db = app.state.db_factory()
    try:
        quotes = [(q.session_id, q.participant_id, q.start_timecode, q.text)
                  for q in db.query(Quote).order_by(Quote.start_timecode).all()]
    finally:
        db.close()
    return root / "bristlenose-output" / ".bristlenose" / "intermediate", client, quotes


def _record(quotes, status="complete"):
    return {
        "version": 1, "status": status, "guide": True, "guide_sha": "x", "quotes_sha": "",
        "sessions": [{"id": "s1", "number": 1, "participants": ["p1"], "duration": "05:00",
                      "seconds": 300.0, "state": "ok"}],
        "spine": [{"id": "s1", "title": "About you", "kind": "questions", "items": [
            {"id": "s1.1", "terse": "Household", "text": "Who do you live with?"},
            {"id": "s1.2", "terse": "Never", "text": "A line never asked"}]}],
        "sections": [{"id": "s1", "title": "About you", "heading": "About you", "kind": "questions",
                      "origin": "planned", "items": [
                          {"id": "s1.1", "terse": "Household", "verbatim": "Who do you live with?",
                           "source": "both", "placed": "", "role": "core",
                           "asks": [{"turn": "s1@00:05", "session": "s1", "sec": 5.0}]},
                          {"id": "s1.2", "terse": "Never", "verbatim": "A line never asked",
                           "source": "planned", "placed": "", "role": "core", "asks": []}]}],
        "standalone": [], "turns": [],
        "quotes": [{"session": s, "participant": p, "sec": t, "time": "00:10", "text": x,
                    "after_item": "s1.1", "section": "s1", "how": "anchor", "sentiment": None}
                   for s, p, t, x in quotes],
        "stats": {},
    }


def _write(intermediate: Path, record: dict) -> None:
    intermediate.mkdir(parents=True, exist_ok=True)
    (intermediate / "discussion.json").write_text(json.dumps(record), encoding="utf-8")


def test_no_record_is_not_run(project):
    _, client, _ = project
    body = client.get("/api/projects/1/discussion").json()
    assert body == {"status": "not_run", "record": None}


def test_a_record_is_served_with_codes_and_no_names(project):
    intermediate, client, quotes = project
    _write(intermediate, _record(quotes))
    body = client.get("/api/projects/1/discussion").json()
    assert body["status"] == "ready"
    assert body["record"]["sessions"][0]["participants"] == ["p1"]
    assert len(body["record"]["quotes"]) == len(quotes)


def test_partial_and_failed_records_say_so(project):
    intermediate, client, quotes = project
    _write(intermediate, _record(quotes, status="partial"))
    assert client.get("/api/projects/1/discussion").json()["status"] == "partial"
    _write(intermediate, _record(quotes, status="failed"))
    assert client.get("/api/projects/1/discussion").json()["status"] == "failed"


def test_a_hidden_quote_is_left_out_and_an_edit_is_shown(project):
    intermediate, client, quotes = project
    _write(intermediate, _record(quotes))
    first, second = (f"q-{p}-{int(t)}" for _, p, t, _ in quotes[:2])
    assert client.put("/api/projects/1/hidden", json={first: True}).status_code == 200
    assert client.put("/api/projects/1/edits", json={second: "edited words"}).status_code == 200
    served = client.get("/api/projects/1/discussion").json()["record"]["quotes"]
    secs = [q["sec"] for q in served]
    assert quotes[0][2] not in secs
    assert next(q for q in served if q["sec"] == quotes[1][2])["text"] == "edited words"


def test_a_record_built_from_other_quotes_is_stale(project):
    intermediate, client, quotes = project
    current = [ExtractedQuote(session_id=s, participant_id=p, start_timecode=t, end_timecode=t + 1,
                              text=x, topic_label="x", quote_type=QuoteType.GENERAL_CONTEXT)
               for s, p, t, x in quotes]
    (intermediate / "extracted_quotes.json").write_text(
        json.dumps([q.model_dump(mode="json") for q in current]), encoding="utf-8")
    record = _record(quotes)
    record["quotes_sha"] = quotes_sha(current)
    _write(intermediate, record)
    assert client.get("/api/projects/1/discussion").json()["status"] == "ready"
    record["quotes_sha"] = "built-from-something-else"
    _write(intermediate, record)
    assert client.get("/api/projects/1/discussion").json() == {"status": "stale", "record": None}


def test_an_unreadable_record_is_not_run_not_an_error(project):
    intermediate, client, _ = project
    intermediate.mkdir(parents=True, exist_ok=True)
    (intermediate / "discussion.json").write_text("{not json", encoding="utf-8")
    assert client.get("/api/projects/1/discussion").json()["status"] == "not_run"


def test_quotes_sharing_a_key_are_matched_by_text(project):
    """The model gives whole-second timecodes, so two quotes can share a key
    and the report keeps one row for it. Hiding that one must not hide the
    other, and the other must keep its own words."""
    intermediate, client, quotes = project
    s, p, t, text = quotes[0]
    record = _record(quotes)
    twin = dict(record["quotes"][0], text="A different quote at the same second")
    record["quotes"].append(twin)
    _write(intermediate, record)
    served = client.get("/api/projects/1/discussion").json()["record"]
    # the report holds the first; the twin is not in it, so it is left out and counted
    assert [q["text"] for q in served["quotes"] if q["sec"] == t] == [text]
    assert served["stats"]["quotes_not_in_report"] == 1
    assert client.put("/api/projects/1/hidden", json={f"q-{p}-{int(t)}": True}).status_code == 200
    served = client.get("/api/projects/1/discussion").json()["record"]
    assert not [q for q in served["quotes"] if q["sec"] == t]


def test_a_quote_the_report_does_not_hold_is_left_out(project):
    """Never clustered or themed, so not in Quotes — and nothing could hide it."""
    intermediate, client, quotes = project
    record = _record(quotes)
    record["quotes"].append(dict(record["quotes"][0], sec=9999.0, text="never in the report"))
    _write(intermediate, record)
    served = client.get("/api/projects/1/discussion").json()["record"]
    assert all(q["sec"] != 9999.0 for q in served["quotes"])
    assert len(served["quotes"]) == len(quotes)


def test_the_anonymised_export_keeps_only_the_guide_lines_that_were_asked():
    from bristlenose.server.routes.export import _anonymise_data

    endpoints = {"/discussion": {"status": "ready", "record": _record([])}}
    _anonymise_data(endpoints)
    record = endpoints["/discussion"]["record"]
    assert [i["id"] for i in record["spine"][0]["items"]] == ["s1.1"]
    assert [i["id"] for i in record["sections"][0]["items"]] == ["s1.1"]


def test_the_anonymised_export_drops_the_guide_file_name():
    from bristlenose.server.routes.export import _anonymise_data

    rec = _record([])
    rec["guide_file"] = "Acme renewal guide.docx"
    endpoints = {"/discussion": {"status": "ready", "record": rec}}
    _anonymise_data(endpoints)
    assert "Acme" not in str(endpoints["/discussion"])


def test_the_anonymised_export_drops_a_guide_section_nobody_asked_about():
    from bristlenose.server.routes.export import _anonymise_data

    rec = _record([])
    rec["spine"].append({"id": "s2", "title": "Your divorce and custody arrangements",
                         "kind": "questions", "items": [{"id": "s2.1", "terse": "x", "text": "x"}]})
    rec["sections"].append({"id": "s2", "title": "Your divorce and custody arrangements",
                            "heading": "h", "kind": "questions", "origin": "planned", "items": [
                                {"id": "s2.1", "terse": "x", "verbatim": "x", "source": "planned",
                                 "placed": "", "role": "core", "asks": []}]})
    rec["sections"].append({"id": "e1", "title": "Prices", "heading": "Prices", "kind": "questions",
                            "origin": "emergent", "items": []})
    endpoints = {"/discussion": {"status": "ready", "record": rec}}
    _anonymise_data(endpoints)
    text = str(endpoints["/discussion"])
    assert "divorce" not in text
    assert [s["id"] for s in endpoints["/discussion"]["record"]["sections"]] == ["s1", "e1"]
