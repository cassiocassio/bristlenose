"""A researcher's own paragraph breaks in a quote: written, read back, dropped when the words change.

The quote card sends the breaks with the wording they were placed in
(``PATCH /quote-breaks``), and ``GET /quotes`` hands them back as
``researcher_breaks`` only while that wording is still the quote's.
docs/design-quote-anchor.md §3.4.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server import quote_breaks
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
QID = "q-p1-26"


@pytest.fixture()
def client() -> TestClient:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def _quote(client: TestClient, dom_id: str = QID) -> dict:
    data = client.get("/api/projects/1/quotes").json()
    for group in (*data["sections"], *data["themes"]):
        for q in group["quotes"]:
            if q["dom_id"] == dom_id:
                return q
    raise AssertionError(f"{dom_id} not in /quotes")


def _breaks_for(text: str) -> list[int]:
    """Two breaks that fall between words of `text`."""
    n = len(text.split())
    assert n >= 4, "the fixture quote is long enough to break twice"
    return [0, n // 2]


def test_no_breaks_by_default(client: TestClient) -> None:
    assert _quote(client)["researcher_breaks"] is None


def test_breaks_round_trip(client: TestClient) -> None:
    text = _quote(client)["text"]
    breaks = _breaks_for(text)
    r = client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": breaks, "text": text}})
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "unresolved": []}
    assert _quote(client)["researcher_breaks"] == breaks


def test_an_empty_list_is_kept_as_a_choice(client: TestClient) -> None:
    text = _quote(client)["text"]
    client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": [], "text": text}})
    assert _quote(client)["researcher_breaks"] == []


def test_null_clears(client: TestClient) -> None:
    text = _quote(client)["text"]
    client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": [0], "text": text}})
    client.patch("/api/projects/1/quote-breaks", json={QID: None})
    assert _quote(client)["researcher_breaks"] is None


def test_breaks_follow_an_edit_made_with_them(client: TestClient) -> None:
    """The card sends the edited words and the breaks placed in them; both land."""
    edited = "One two three. Four five six. Seven eight nine."
    client.patch("/api/projects/1/edits", json={QID: edited})
    client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": [2, 5], "text": edited}})
    q = _quote(client)
    assert q["edited_text"] == edited
    assert q["researcher_breaks"] == [2, 5]


def test_breaks_stop_showing_when_the_words_change(client: TestClient) -> None:
    """A later edit that sends no breaks rewords the quote: the old breaks no longer fit."""
    text = _quote(client)["text"]
    client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": [0], "text": text}})
    client.patch("/api/projects/1/edits", json={QID: "Entirely different words now."})
    assert _quote(client)["researcher_breaks"] is None


def test_spacing_alone_is_not_a_change_of_words(client: TestClient) -> None:
    text = _quote(client)["text"]
    client.patch(
        "/api/projects/1/quote-breaks",
        json={QID: {"breaks": [0], "text": "  " + text.replace(" ", "  ") + "\n"}},
    )
    assert _quote(client)["researcher_breaks"] == [0]


@pytest.mark.parametrize(
    "breaks",
    [[-1], [999], [3, 3], [5, 2]],
    ids=["before-the-first-word", "past-the-last-word", "repeated", "out-of-order"],
)
def test_breaks_must_fall_between_words(client: TestClient, breaks: list[int]) -> None:
    text = _quote(client)["text"]
    r = client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": breaks, "text": text}})
    assert r.status_code == 422
    assert _quote(client)["researcher_breaks"] is None


def test_a_break_after_the_last_word_is_refused(client: TestClient) -> None:
    text = _quote(client)["text"]
    last = len(text.split()) - 1
    r = client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": [last], "text": text}})
    assert r.status_code == 422


def test_an_unknown_quote_is_unresolved(client: TestClient) -> None:
    r = client.patch(
        "/api/projects/1/quote-breaks", json={"q-p9-999": {"breaks": [0], "text": "a b"}},
    )
    assert r.json() == {"status": "ok", "unresolved": ["q-p9-999"]}


def test_breaks_do_not_pin_the_quote(client: TestClient) -> None:
    """Presentation, not curation: a quote with only breaks is not frozen against a re-run."""
    from bristlenose.server.importer import _pinned_quote_ids
    from bristlenose.server.models import Quote

    text = _quote(client)["text"]
    client.patch("/api/projects/1/quote-breaks", json={QID: {"breaks": [0], "text": text}})
    db = client.app.state.db_factory()  # type: ignore[attr-defined]
    try:
        pinned = _pinned_quote_ids(db, 1)
        row = db.query(Quote).filter(Quote.participant_id == "p1", Quote.start_timecode >= 26,
                                     Quote.start_timecode < 27).one()
        assert row.id not in pinned
    finally:
        db.close()


def test_verify_ignores_spacing_only() -> None:
    assert quote_breaks.verify_of("a  b\nc") == quote_breaks.verify_of("a b c")
    assert quote_breaks.verify_of("a b c") != quote_breaks.verify_of("a b d")


def test_a_row_that_cannot_be_read_is_not_shown() -> None:
    assert quote_breaks.decode("not json") is None
    assert quote_breaks.decode(quote_breaks.encode([1, 4])) == [1, 4]
