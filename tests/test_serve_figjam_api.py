"""The FigJam board download — `GET /api/projects/{id}/export/figjam-board.json`.

Smoke-test fixture: one session, four quotes (q-p1-10, q-p1-26, q-p1-46,
q-p1-66). No network: FigJam is a download, not a push.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app
from bristlenose.server.models import Project
from tests.conftest import LOOPBACK_BASE_URL, AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_URL = "/api/projects/1/export/figjam-board.json"


@pytest.fixture()
def client() -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def _quotes(doc: dict) -> list[dict]:
    return [q for f in doc["frames"] for c in f["columns"] for q in c["quotes"]]


def test_downloads_the_board_document(client: TestClient) -> None:
    resp = client.get(_URL)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert '-figjam-board.json"' in disposition
    doc = resp.json()
    assert (doc["format"], doc["version"]) == ("bristlenose-board", 1)
    assert len(_quotes(doc)) == 4


def test_scope_is_the_selected_quotes(client: TestClient) -> None:
    doc = client.get(_URL, params={"quote_ids": "q-p1-10,q-p1-46"}).json()
    assert [q["attribution"] for q in _quotes(doc)] == ["— P1 · 00:10", "— P1 · 00:46"]


def test_hidden_quotes_stay_off_the_board(client: TestClient) -> None:
    client.put("/api/projects/1/hidden", json={"q-p1-10": True})
    doc = client.get(_URL).json()
    assert "— P1 · 00:10" not in [q["attribution"] for q in _quotes(doc)]
    assert len(_quotes(doc)) == 3


def test_nothing_selected_is_a_reason_the_clients_already_translate(client: TestClient) -> None:
    resp = client.get(_URL, params={"quote_ids": "q-p9-999"})
    assert resp.status_code == 404
    assert resp.json()["reason"] == "no_quotes_selected"


def test_unknown_project_is_404(client: TestClient) -> None:
    assert client.get("/api/projects/99/export/figjam-board.json").status_code == 404


def test_the_board_speaks_lang(client: TestClient) -> None:
    en = client.get(_URL).json()
    es = client.get(_URL, params={"lang": "es"}).json()
    assert es["locale"] == "es"
    assert es["frames"][0]["title"] != en["frames"][0]["title"]


def test_a_project_named_outside_latin_1_still_downloads(client: TestClient) -> None:
    """Starlette encodes headers as Latin-1, so a bare `filename="駅…"` is a 500.
    The name goes in `filename*`, percent-encoded."""
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        db.get(Project, 1).name = "駅の調査 Łódź"
        db.commit()
    finally:
        db.close()
    resp = client.get(_URL)
    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert disposition.isascii()
    assert "filename*=UTF-8''" in disposition
    star = disposition.split("filename*=UTF-8''", 1)[1]
    assert unquote(star) == "駅の調査 Łódź-figjam-board.json"
    assert 'filename="' in disposition  # the ASCII fallback for old readers
    assert "駅の調査" in json.loads(resp.content)["title"]


def test_needs_the_token(client: TestClient) -> None:
    bare = TestClient(client.app, base_url=LOOPBACK_BASE_URL)
    assert bare.get(_URL).status_code == 401


# ── review fixes, 17 Oct 2026 ────────────────────────────────────────────────


def test_an_id_too_large_for_sqlite_is_no_quotes_not_a_500(client: TestClient) -> None:
    resp = client.get(_URL, params={"quote_ids": "q-p1-99999999999999999999"})
    assert resp.status_code == 404
    assert resp.json()["reason"] == "no_quotes_selected"


def test_a_repeated_id_puts_the_quote_on_the_board_once(client: TestClient) -> None:
    # `010` is a second spelling of the same id, so it survives the id dedupe
    # and has to be caught on the resolved quote.
    doc = client.get(_URL, params={"quote_ids": "q-p1-10,q-p1-010,q-p1-10,q-p1-26"}).json()
    assert [q["attribution"] for q in _quotes(doc)] == ["— P1 · 00:10", "— P1 · 00:26"]


@pytest.mark.parametrize("raw", ["zz\nINJECT", "xx", "ES"])
def test_the_document_names_the_language_its_words_are_in(client: TestClient, raw: str) -> None:
    """The raw value used to be written into the document and the log, so a
    board in English could say `zz` and a newline could forge a log line."""
    from bristlenose.i18n import SUPPORTED_LOCALES, canonical_locale

    doc = client.get(_URL, params={"lang": raw}).json()
    assert doc["locale"] == canonical_locale(raw)
    assert doc["locale"] in SUPPORTED_LOCALES


@pytest.mark.parametrize("base", [
    "drive.example.com/clips",          # no scheme: asked for links, would get none
    "javascript:alert(1)",
    "https://user:token@x.example/c",   # credentials would be published on the board
])
def test_a_clip_folder_that_cannot_become_links_is_refused(client: TestClient, base: str) -> None:
    resp = client.get(_URL, params={"clips_base": base})
    assert resp.status_code == 400
    assert resp.json()["reason"] == "clips_base_not_http"


def test_a_good_clip_folder_links_every_quote(client: TestClient) -> None:
    doc = client.get(_URL, params={"clips_base": "https://x.example/c"}).json()
    assert all(q["clip_url"].startswith("https://x.example/c/") for q in _quotes(doc))


def test_the_download_is_never_sniffed_or_cached(client: TestClient) -> None:
    resp = client.get(_URL)
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "no-store"


def test_requested_counts_distinct_ids_so_a_stale_selection_shows(client: TestClient) -> None:
    doc = client.get(_URL, params={"quote_ids": "q-p1-10,q-p1-10,q-p9-999"}).json()
    assert (doc["requested"], doc["totals"]["quotes"]) == (2, 1)
    assert client.get(_URL).json()["requested"] is None


def test_long_quotes_split_unless_the_researcher_unticks_it(client: TestClient, monkeypatch) -> None:
    """The Miro panels' "Break long quotes into multiple sticky notes", ticked by
    default; the FigJam download takes the same switch."""
    monkeypatch.setattr("bristlenose.board_layout.SPLIT_AT", 10)
    split = client.get(_URL).json()
    whole = client.get(_URL, params={"split_long_quotes": "false"}).json()
    assert max(len(q["parts"]) for q in _quotes(split)) > 1
    assert all(len(q["parts"]) == 1 for q in _quotes(whole))


def test_square_by_default_and_rectangle_on_request(client: TestClient) -> None:
    """FigJam's default is square, Miro's rectangle (owner); the dialog offers both."""
    assert client.get(_URL).json()["sticky_shape"] == "square"
    assert client.get(_URL, params={"sticky_shape": "rectangle"}).json()["sticky_shape"] == "rectangle"
    assert client.get(_URL, params={"sticky_shape": "circle"}).status_code == 422


def test_a_board_name_titles_the_board_and_names_the_file(client: TestClient) -> None:
    resp = client.get(_URL, params={"board_name": "Kitchen study, round 2"})
    assert resp.json()["title"].startswith("Kitchen study, round 2")
    assert 'Kitchen study, round 2-figjam-board.json' in resp.headers["content-disposition"]
    blank = client.get(_URL, params={"board_name": "   "}).json()
    assert blank["title"] == client.get(_URL).json()["title"]


def test_a_long_quote_breaks_where_its_speaker_paused(client: TestClient, monkeypatch) -> None:
    """The word timings the transcript keeps reach the board: an unpunctuated quote breaks at
    the speaker's pause, not at whichever word sits nearest the middle."""
    from bristlenose.server.models import Quote, TranscriptSegment
    from bristlenose.server.models import Session as StudySession

    said = ("we tried every one of the tools they had on offer that year and none of them stayed "
            "open long enough to finish a single thing we started on a monday morning before the "
            "coffee ran out and the meeting room filled up with the people from the other floor")
    tokens = said.split()
    at = tokens.index("finish")
    words, t = [], 10.0
    for i, w in enumerate(tokens):
        words.append({"t": w, "s": round(t, 2), "e": round(t + 0.3, 2)})
        t += 0.3 + (1.2 if i == at else 0.0)
    db = client.app.state.db_factory()
    try:
        quote = db.query(Quote).filter_by(participant_id="p1", start_timecode=10.0).one()
        quote.text, quote.end_timecode = said, t
        session = db.query(StudySession).filter_by(session_id=quote.session_id).one()
        seg = (db.query(TranscriptSegment).filter_by(session_id=session.id)
               .order_by(TranscriptSegment.start_time).first())
        seg.words_json = json.dumps(words)
        db.commit()
    finally:
        db.close()
    monkeypatch.setattr("bristlenose.board_layout.SPLIT_AT", 200)
    [quote_doc] = _quotes(client.get(_URL, params={"quote_ids": "q-p1-10"}).json())
    assert quote_doc["parts"][0].rstrip("…").split()[-1] == "finish"


def test_a_quote_splits_by_the_rules_of_the_language_it_was_spoken_in(
        client: TestClient, monkeypatch) -> None:
    """The session's spoken language reaches the splitter: in Czech a part may not end on the
    one-letter preposition *v* (ČSN 01 6910), which English rules would happily end on."""
    from bristlenose.server.models import Quote
    from bristlenose.server.models import Session as StudySession

    said = "dlouho " * 19 + "v praze" + " dlouho" * 19
    db = client.app.state.db_factory()
    try:
        quote = db.query(Quote).filter_by(participant_id="p1", start_timecode=10.0).one()
        quote.text = said
        session = db.query(StudySession).filter_by(session_id=quote.session_id).one()
        db.commit()
        monkeypatch.setattr("bristlenose.board_layout.SPLIT_AT", 200)

        def first_part(language: str | None) -> str:
            session.language = language
            db.commit()
            [doc] = _quotes(client.get(_URL, params={"quote_ids": "q-p1-10"}).json())
            return doc["parts"][0]

        english, czech = first_part(None), first_part("cs")
        # English rules have no word against ending on "v"; Czech typography forbids it.
        assert not czech.endswith(" v…") and czech != english
    finally:
        db.close()
