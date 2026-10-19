"""A FigJam board and a Miro board of the same selection say the same thing.

Each export was tested on its own; nothing read both off one fixture. These
tests build the Miro layout (`layout_board`, what `push_to_miro` sends) and the
FigJam document (`build_manifest`, what the plugin draws) from the same columns,
and from the same database through the routes' own builders, and compare what a
researcher reads on each: which quotes, in what order, in which columns, split
where, attributed how, coloured how, under which headings and title.

Geometry is not compared: FigJam stickies grow with their text, so the plugin
lays out its own columns (`board_manifest`'s docstring). Colour is compared on
the flat baseline, the only colouring FigJam offers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bristlenose.board_layout import (
    BoardStrings,
    Column,
    QuoteCard,
    attribution,
    layout_board,
)
from bristlenose.board_manifest import build_manifest
from bristlenose.board_palette import FIGJAM_TOKEN_HEX
from bristlenose.server import miro_export
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

_LONG = " ".join(f"Sentence {i} is about the checkout page and what it asked of me." for i in range(12))
_UNPUNCTUATED = ("then on the second day " * 3 +  # long enough to split, the pause near the middle
                 "we tried every one of the tools they had on offer that year and none of them "
                 "stayed open long enough to finish a single thing we started on a monday morning "
                 "before the coffee ran out and the meeting room filled up with people from upstairs "
                 "who wanted the room back for a call with a supplier about the next quarter")


#: Unpunctuated, so only BudouX's phrases can say where it breaks.
_JAPANESE = "この画面は最初に見たときにどこを押せばいいのか全然わからなくて" * 11
#: Czech typography forbids ending a line on the preposition *v*; English rules would.
_CZECH = "dlouho " * 26 + "v praze" + " dlouho" * 26


def _miro_view(board: Any) -> dict[str, Any]:
    """What a Miro board says, read back off its stickies: frames → columns → quotes."""
    frames = []
    for frame in board.frames:
        inside = [s for s in board.stickies if frame.x <= s.x < frame.x + frame.width]
        columns: list[dict[str, Any]] = []
        last_set: object = object()
        for s in inside:
            if s.kind == "header":
                label, count = s.text.split("\n")
                columns.append({"label": label, "count": count, "colour": s.colour, "quotes": []})
                last_set = object()
                continue
            quotes = columns[-1]["quotes"]
            if s.set_id is None or s.set_id != last_set:
                quotes.append({"parts": [], "colour": s.colour})
            last_set = s.set_id
            q = quotes[-1]
            q["parts"].append(s.text)
            assert s.colour == q["colour"], "every part of a quote is one colour"
            if s.attributed:
                q["attribution"] = attribution(s.participant_id, s.timecode)
                q["clip_url"] = s.link_url
        frames.append({"kind": frame.kind, "title": frame.title, "columns": columns})
    return {"title": board.title, "frames": frames}


def _figjam_view(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": doc["title"],
        "frames": [{
            "kind": f["kind"], "title": f["title"],
            "columns": [{
                "label": c["label"], "count": c["count"], "colour": c["colour"],
                "quotes": [{k: q[k] for k in ("parts", "colour", "attribution", "clip_url")}
                           for q in c["quotes"]],
            } for c in f["columns"]],
        } for f in doc["frames"]],
    }


def _card(text: str, pid: str, session: str, start: float, **kw: Any) -> QuoteCard:
    return QuoteCard(text=text, participant_id=pid, session_id=session, start_timecode=start, **kw)


def _columns() -> list[Column]:
    """Two sessions out of order (s10 before s2 by string, after it by number), a theme column,
    an hour-long timecode, a clip link, a split quote with pauses, and one in Japanese."""
    ja = _JAPANESE
    pause_at = _UNPUNCTUATED.index(" finish ") + len(" finish")
    return [
        Column("Checkout", "section", [
            _card(_LONG, "p3", "s10", 5.0, sentiment="frustration", link_url="https://x.example/c/a.mp4"),
            _card("Too many steps.", "p2", "s2", 3725.0, sentiment="delight"),
            _card(_UNPUNCTUATED, "p2", "s2", 90.0, pauses={pause_at: 1.4}),
        ]),
        Column("Search", "section", [
            _card(ja, "p4", "s3", 61.0, language="ja"),
            _card(_CZECH, "p4", "s3", 30.0, language="cs"),
        ]),
        Column("Trust", "theme", [
            _card("Is this safe?", "p1", "s1", 12.0, sentiment="confusion"),
            _card(_LONG + " Then I gave up.", "p1", "s1", 4.0),
        ]),
    ]


@pytest.mark.parametrize("split", [True, False])
@pytest.mark.parametrize("shape", ["square", "rectangle"])
def test_both_boards_say_the_same_words_in_the_same_order(split: bool, shape: str) -> None:
    columns = _columns()
    title = "Study — research board"
    strings = BoardStrings()
    miro = layout_board(columns, title, colour_by="none", strings=strings, split=split, shape=shape)
    figjam = build_manifest(columns, title, strings=strings, clip_label="clip",
                            palette=FIGJAM_TOKEN_HEX, locale="en", generator="test",
                            split=split, sticky_shape=shape)
    a, b = _miro_view(miro), _figjam_view(figjam)
    assert a == b
    # And the comparison has something in it to compare.
    quotes = [q for f in b["frames"] for c in f["columns"] for q in c["quotes"]]
    assert len(quotes) == 7
    assert (max(len(q["parts"]) for q in quotes) > 1) is split


def test_what_both_boards_say_is_what_the_shared_rules_say() -> None:
    """The comparison above cannot see a shared helper going wrong for both boards at once, so
    this pins the outcome. Every assertion is one a broken helper failed (mutation-proved,
    19 Oct 2026); before it, the Miro tests missed a sort that ignored the session and a split
    that ignored the speaker's pauses, the session's language or BudouX."""
    from bristlenose.board_layout import _phrase_parser

    view = _figjam_view(build_manifest(
        _columns(), "t", strings=BoardStrings(), clip_label="clip", palette=FIGJAM_TOKEN_HEX,
        locale="en", generator="test"))
    assert view == _miro_view(layout_board(_columns(), "t", colour_by="none"))
    cols = {c["label"]: c for f in view["frames"] for c in f["columns"]}
    # Session by number (s2 before s10), then time; codes in capitals; the house timecode.
    assert [q["attribution"] for q in cols["Checkout"]["quotes"]] == [
        "— P2 · 01:30", "— P2 · 1:02:05", "— P3 · 00:05"]
    assert [q["attribution"] for q in cols["Trust"]["quotes"]] == ["— P1 · 00:04", "— P1 · 00:12"]
    # The speaker's pause decides the unpunctuated quote's break.
    paused = cols["Checkout"]["quotes"][0]["parts"]
    assert paused[0].rstrip("…").split()[-1] == "finish"
    # The session's language: a Czech part never ends on "v".
    czech, japanese = (q["parts"] for q in cols["Search"]["quotes"])
    assert len(czech) == 2 and not czech[0].endswith(" v…")
    # Japanese breaks between two of BudouX's phrases, never inside one.
    assert len(japanese) > 1
    phrases = _phrase_parser("ja").parse(_JAPANESE)
    ends = {len("".join(phrases[:i])) for i in range(1, len(phrases))}
    at = 0
    for part in japanese[:-1]:
        at += len(part.strip("“”…"))
        assert at in ends, part[-6:]


def test_the_sticky_shape_changes_geometry_never_where_a_quote_breaks() -> None:
    """Square and rectangle are a drawing choice: the words on each sticky are the same."""
    columns = _columns()
    square = _miro_view(layout_board(columns, "t", colour_by="none", shape="square"))
    rect = _miro_view(layout_board(columns, "t", colour_by="none", shape="rectangle"))
    assert square == rect


# ── through the database: the selection both routes are given ────────────────


@pytest.fixture()
def db():
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    client = AuthTestClient(app)
    session = app.state.db_factory()
    # Long enough to split, with the session's language set, so the pauses and the
    # language rules both have to reach both builders.
    from bristlenose.server.models import Quote
    from bristlenose.server.models import Session as StudySession

    quote = session.query(Quote).filter_by(participant_id="p1", start_timecode=10.0).one()
    quote.text = _UNPUNCTUATED
    words, t = [], 10.0
    for w in _UNPUNCTUATED.split():
        words.append({"t": w, "s": round(t, 2), "e": round(t + 0.3, 2)})
        t += 0.3 + (1.2 if w == "finish" else 0.0)
    quote.end_timecode = t
    study = session.query(StudySession).filter_by(session_id=quote.session_id).one()
    study.language = "en"
    from bristlenose.server.models import TranscriptSegment

    seg = (session.query(TranscriptSegment).filter_by(session_id=study.id)
           .order_by(TranscriptSegment.start_time).first())
    seg.words_json = json.dumps(words)
    session.query(Quote).filter_by(participant_id="p1", start_timecode=46.0).one().text = _LONG
    session.commit()
    try:
        yield client, session
    finally:
        session.close()


def _both(session: Any, quote_ids: list[str] | None, **kw: Any) -> tuple[dict, dict]:
    miro = miro_export.build_board(session, 1, "Study", quote_ids, colour_by="none", **kw)
    figjam = miro_export.build_figjam_manifest(session, 1, "Study", quote_ids, **kw)
    return _miro_view(miro), _figjam_view(figjam)


def _attributions(view: dict) -> list[str]:
    return [q["attribution"] for f in view["frames"] for c in f["columns"] for q in c["quotes"]]


@pytest.mark.parametrize("quote_ids", [
    None,                                              # all but hidden
    ["q-p1-46", "q-p1-10"],                            # a selection, in click order
    ["q-p1-10", "q-p1-010", "q-p1-10", "q-p1-66"],     # repeated, and a second spelling
    ["q-p1-26", "nonsense", "q-p9-999"],               # malformed and stale ids beside a good one
])
def test_a_selection_puts_the_same_quotes_on_both_boards(db, quote_ids) -> None:
    client, session = db
    client.put("/api/projects/1/hidden", json={"q-p1-26": True})
    a, b = _both(session, quote_ids)
    assert a == b
    assert _attributions(b), "the case under test should put something on the board"
    assert len(set(_attributions(b))) == len(_attributions(b)), "a repeated id is one quote"


def test_hidden_quotes_stay_off_both_boards_unless_selected(db) -> None:
    client, session = db
    client.put("/api/projects/1/hidden", json={"q-p1-26": True})
    a, b = _both(session, None)
    assert "— P1 · 00:26" not in _attributions(a) == _attributions(b)
    assert a["title"] == b["title"] == "Study — research board (3 quotes)"
    # An explicit selection is the researcher's word for it, hidden or not, on either board.
    a, b = _both(session, ["q-p1-26"])
    assert _attributions(a) == _attributions(b) == ["— P1 · 00:26"]


def test_a_long_quote_breaks_in_the_same_place_on_both_boards(db, monkeypatch) -> None:
    _, session = db
    monkeypatch.setattr("bristlenose.board_layout.SPLIT_AT", 120)
    a, b = _both(session, ["q-p1-10", "q-p1-46"])
    assert a == b
    parts = [q["parts"] for f in b["frames"] for c in f["columns"] for q in c["quotes"]]
    assert all(len(p) > 1 for p in parts)
    # The speaker's pause reached both: the first part ends where they stopped.
    assert any(p[0].rstrip("…").split()[-1] == "finish" for p in parts)


@pytest.mark.parametrize("locale", ["en", "pl", "ja"])
def test_both_boards_speak_the_callers_language_alike(db, locale) -> None:
    _, session = db
    a, b = _both(session, None, locale=locale)
    assert a == b


def test_both_boards_link_the_same_clips(db) -> None:
    _, session = db
    a, b = _both(session, None, clips_base="https://x.example/clips/")
    assert a == b
    links = [q["clip_url"] for f in b["frames"] for c in f["columns"] for q in c["quotes"]]
    assert links and all(u and u.startswith("https://x.example/clips/") for u in links)


def test_the_sessions_language_reaches_both_boards(db) -> None:
    """`build_columns` hands each quote its session's language: Czech rules keep "v" off the end
    of a part on both boards, where English rules would end the first part on it."""
    from bristlenose.server.models import Quote
    from bristlenose.server.models import Session as StudySession

    _, session = db
    quote = session.query(Quote).filter_by(participant_id="p1", start_timecode=66.0).one()
    quote.text = _CZECH
    session.query(StudySession).filter_by(session_id=quote.session_id).one().language = "cs"
    session.commit()
    a, b = _both(session, ["q-p1-66"])
    assert a == b
    [parts] = [q["parts"] for f in b["frames"] for c in f["columns"] for q in c["quotes"]]
    assert len(parts) == 2 and not parts[0].endswith(" v…")


def test_theme_columns_follow_the_quotes_lens_order(db) -> None:
    """Themes read on the board in the order the Quotes lens's Themes navigation lists them, not
    by whichever theme has the earliest quote: here the second theme's quote comes first."""
    from bristlenose.server.models import ClusterQuote, Quote, ThemeGroup, ThemeQuote

    client, session = db
    first = session.query(ThemeGroup).filter_by(project_id=1).order_by(ThemeGroup.id).first()
    later = ThemeGroup(project_id=1, theme_label="Later theme")
    session.add(later)
    session.flush()
    early_quote = session.query(Quote).filter_by(participant_id="p1", start_timecode=46.0).one()
    session.query(ClusterQuote).filter_by(quote_id=early_quote.id).delete()
    session.add(ThemeQuote(quote_id=early_quote.id, theme_id=later.id))
    session.commit()

    lens = [t["theme_label"] for t in client.get("/api/projects/1/quotes").json()["themes"]]
    assert lens[:2] == [first.theme_label, "Later theme"]
    a, b = _both(session, None)
    assert a == b
    [themes] = [f["columns"] for f in b["frames"] if f["kind"] == "theme"]
    assert [c["label"] for c in themes] == lens[:2]
