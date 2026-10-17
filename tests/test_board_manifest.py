"""The FigJam board document — what leaves the machine for the plugin.

Pins the version-1 contract the plugin reads, that a FigJam board and a Miro
board of the same selection agree on order, that any character a quote can hold
stays inside its string, and that no participant name reaches the bytes.
"""

from __future__ import annotations

import json
import logging

import pytest

from bristlenose.board_layout import (
    DEFAULT_QUOTE_TOKEN,
    HEADER_TOKEN,
    SENTIMENT_TOKEN,
    BoardStrings,
    Column,
    QuoteCard,
    quote_sort_key,
)
from bristlenose.board_manifest import FORMAT, VERSION, build_manifest, to_json
from bristlenose.board_palette import FIGJAM_TOKEN_HEX
from bristlenose.server.export_core import ExportableQuote
from bristlenose.server.miro_export import build_figjam_manifest


def _card(text: str, pid: str = "p1", session: str = "s1", start: float = 10.0,
          sentiment: str | None = None, link: str | None = None) -> QuoteCard:
    return QuoteCard(text=text, participant_id=pid, session_id=session,
                     start_timecode=start, sentiment=sentiment, link_url=link)


def _tokens_used(m: dict) -> set[str]:
    cols = [c for f in m["frames"] for c in f["columns"]]
    return {c["colour"] for c in cols} | {q["colour"] for c in cols for q in c["quotes"]}


def _manifest(columns: list[Column], **kw) -> dict:
    return build_manifest(
        columns, "Study — research board (3 quotes)",
        strings=BoardStrings(), clip_label="clip", palette=FIGJAM_TOKEN_HEX,
        locale="en", generator="Bristlenose test", **kw,
    )


def _export_quote(text: str, *, section: str = "Checkout", theme: str = "",
                  code: str = "p2", name: str = "Jane Secret",
                  source_file: str = "jane-doe.mov", timecode: str = "0:30",
                  session: str = "s1") -> ExportableQuote:
    return ExportableQuote(
        text=text, participant_code=code, participant_name=name, section=section,
        theme=theme, sentiment="frustration", tags="", starred=False,
        timecode=timecode, session=session, source_file=source_file,
    )


# ── the version-1 contract ───────────────────────────────────────────────────

_TOP_KEYS = {"format": str, "version": int, "min_reader_version": int, "generator": str,
             "locale": str, "title": str, "sticky_shape": str, "strings": dict,
             "palette": dict, "totals": dict, "frames": list}
_COLUMN_KEYS = {"label", "count", "quote_count", "colour", "quotes"}
_QUOTE_KEYS = {"parts", "attribution", "colour", "clip_url"}


def test_document_shape_is_the_version_1_contract():
    cols = [
        Column("Checkout", "section", [_card("Too many steps", start=40.0)]),
        Column("Trust", "theme", [_card("Is this safe?", pid="p3")]),
    ]
    m = _manifest(cols)

    assert (m["format"], m["version"]) == (FORMAT, VERSION) == ("bristlenose-board", 1)
    # The version-1 contract is the keys and their types. A new optional key is
    # allowed (the plugin ignores what it does not know); a renamed or retyped
    # one fails here and needs a version bump.
    assert _TOP_KEYS.keys() <= m.keys()
    assert all(isinstance(m[k], t) for k, t in _TOP_KEYS.items())
    col0 = m["frames"][0]["columns"][0]
    assert _COLUMN_KEYS <= col0.keys()
    assert _QUOTE_KEYS <= col0["quotes"][0].keys()
    assert [f["kind"] for f in m["frames"]] == ["section", "theme"]
    assert [f["title"] for f in m["frames"]] == ["Sections", "Themes"]
    col = m["frames"][0]["columns"][0]
    assert (col["label"], col["count"], col["colour"]) == ("Checkout", "1 quote", "light_pink")
    assert col["quotes"] == [{
        "parts": ["“Too many steps”"],
        "attribution": "— P1 · 00:40",
        "colour": "light_yellow",
        "clip_url": None,
    }]
    assert m["strings"] == {"clip": "▶ clip"}
    assert m["sticky_shape"] == "rectangle"  # the house shape on every board


def test_flat_by_default_with_figjams_own_palette_colours():
    """Decided 17 Oct 2026: pink headers, yellow quotes, in FigJam's palette —
    and only the tokens the board uses, so the plugin never meets a colour it
    has no card for."""
    cols = [Column("Checkout", "section", [_card("a", sentiment="frustration")])]
    m = _manifest(cols)
    assert m["palette"] == {"light_pink": "#FFA8DB", "light_yellow": "#FFE299"}
    assert m["frames"][0]["columns"][0]["quotes"][0]["colour"] == "light_yellow"


def test_an_empty_frame_is_left_out_not_drawn_empty():
    m = _manifest([Column("Trust", "theme", [_card("a")])])
    assert [f["kind"] for f in m["frames"]] == ["theme"]


def test_quote_order_is_the_miro_boards_order():
    """The same selection must read in the same order on either board: session
    number first (s2 before s10), then time."""
    cards = [
        _card("late s10", session="s10", start=5.0),
        _card("s2 at 90", session="s2", start=90.0),
        _card("s2 at 3", session="s2", start=3.0),
    ]
    cols = [Column("Checkout", "section", cards)]
    from_manifest = [q["attribution"] for q in _manifest(cols)["frames"][0]["columns"][0]["quotes"]]
    assert from_manifest == ["— P1 · 00:03", "— P1 · 01:30", "— P1 · 00:05"]
    from_layout = [c.text for c in sorted(cards, key=quote_sort_key)]
    assert from_layout == ["s2 at 3", "s2 at 90", "late s10"]


# ── what a quote can hold stays inside its string ────────────────────────────


@pytest.mark.parametrize("text", [
    'She said "no" and left',
    "C:\\Users\\jane\\path",
    "</script><script>alert(1)</script>",
    "line\u2028separator and \u2029 paragraph",
    "nul\x00bell\x07tab\t",
    "駅の券売機 👩🏽‍💻 مرحبا",
])
def test_hostile_text_round_trips_and_the_bytes_are_ascii(text):
    out = to_json(_manifest([Column("C", "section", [_card(text)])]))
    assert out.isascii()
    back = json.loads(out)
    assert back["frames"][0]["columns"][0]["quotes"][0]["parts"] == [f"“{text.strip()}”"]


# ── the anonymisation boundary, on the serialised bytes ──────────────────────


def test_no_name_and_no_name_bearing_filename_reaches_the_bytes(monkeypatch):
    """The per-board egress test the design doc asks for: plant a display name
    AND a filename made of one, serialise, and look for both."""
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *a, **k: [_export_quote("I gave up at the payment page")],
    )
    out = to_json(build_figjam_manifest(None, 1, "Renfe", None,
                                        clips_base="https://drive.example.com/c"))
    low = out.lower()
    assert "jane" not in low and "secret" not in low and "jane-doe" not in low
    assert "— P2 · 00:30" in json.loads(out)["frames"][0]["columns"][0]["quotes"][0]["attribution"]


# ── the server builder: words, title, clip links ─────────────────────────────


def test_builder_speaks_the_callers_locale(monkeypatch):
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *a, **k: [_export_quote("Uno"), _export_quote("Dos", timecode="0:40")],
    )
    m = build_figjam_manifest(None, 1, "Renfe", None, locale="es")
    assert m["locale"] == "es"
    assert m["frames"][0]["title"] != "Sections"
    assert m["frames"][0]["columns"][0]["count"] != "2 quotes"
    assert "Renfe" in m["title"]


def test_clip_link_only_with_an_http_folder(monkeypatch):
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *a, **k: [_export_quote("Uno")],
    )
    with_base = build_figjam_manifest(None, 1, "R", None, clips_base="https://x.example/c/")
    without = build_figjam_manifest(None, 1, "R", None)
    q = lambda m: m["frames"][0]["columns"][0]["quotes"][0]  # noqa: E731
    assert q(with_base)["clip_url"] == "https://x.example/c/s1-p2-30.mp4"
    assert q(without)["clip_url"] is None


def test_no_clip_folder_is_not_logged_as_a_refusal(monkeypatch, caplog):
    """Every board built without clip links used to log 'Ignoring clips_base'
    once per quote, because an empty folder failed the URL check."""
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *a, **k: [_export_quote("Uno"), _export_quote("Dos", timecode="0:40")],
    )
    with caplog.at_level(logging.WARNING, logger="bristlenose.server.miro_export"):
        build_figjam_manifest(None, 1, "R", None)
    assert not [r for r in caplog.records if "clips_base" in r.getMessage()]


def test_builder_paints_with_figjams_palette_not_miros(monkeypatch):
    monkeypatch.setattr(
        "bristlenose.server.miro_export.extract_quotes_for_export",
        lambda *a, **k: [_export_quote("Uno")],
    )
    m = build_figjam_manifest(None, 1, "R", None)
    assert m["palette"] == {t: FIGJAM_TOKEN_HEX[t] for t in m["palette"]}
    assert set(m["palette"]) == _tokens_used(m)


def test_every_board_colour_token_has_a_figjam_colour():
    """A new sentiment token without a FigJam colour must fail here, not turn a
    sticky yellow on a researcher's board."""
    tokens = {HEADER_TOKEN, DEFAULT_QUOTE_TOKEN, *SENTIMENT_TOKEN.values()}
    assert tokens <= FIGJAM_TOKEN_HEX.keys()
    cols = [Column("C", "section", [_card(s, sentiment=s) for s in SENTIMENT_TOKEN])]
    m = _manifest(cols, colour_by="sentiment")
    assert set(m["palette"]) == _tokens_used(m)


def test_a_token_with_no_colour_is_an_error_not_a_yellow_sticky():
    cols = [Column("C", "section", [_card("a")])]
    with pytest.raises(KeyError):
        build_manifest(cols, "t", strings=BoardStrings(), clip_label="clip",
                       palette={"light_pink": "#FFA8DB"}, locale="en", generator="g")


def test_counts_are_integers_a_reader_can_check_its_work_against():
    cols = [
        Column("Checkout", "section", [_card("a"), _card("b", start=20.0)]),
        Column("Trust", "theme", [_card("c")]),
    ]
    m = _manifest(cols, requested=5)
    assert m["totals"] == {"frames": 2, "columns": 2, "quotes": 3}
    assert [c["quote_count"] for f in m["frames"] for c in f["columns"]] == [2, 1]
    assert m["requested"] == 5
    assert _manifest(cols)["requested"] is None  # None means "all"


def test_the_envelope_says_which_readers_can_draw_it():
    m = _manifest([Column("C", "section", [_card("a")])])
    assert m["min_reader_version"] <= m["version"]


def test_a_long_quote_arrives_in_parts_split_where_the_miro_board_splits_it():
    """One splitter for every board: the parts are `quote_part_texts`'s, so a
    quote breaks in the same places on Miro and FigJam, and no word is lost."""
    from bristlenose.board_layout import SPLIT_AT, quote_part_texts

    long = " ".join(f"Sentence number {i} is about the checkout page." for i in range(30))
    assert len(long) > 2 * SPLIT_AT
    parts = _manifest([Column("C", "section", [_card(long)])])["frames"][0]["columns"][0]["quotes"][0]["parts"]
    assert parts == quote_part_texts(long)
    assert len(parts) == 3
    assert parts[0].startswith("“") and parts[-1].endswith("”")
    assert parts[0].endswith("…") and parts[1].startswith("…")
    # The splitter swaps a part's closing full stop for the "…" (as a hand split does).
    words = lambda s: [w.rstrip(".") for w in s.replace("“", "").replace("”", "").replace("…", "").split()]  # noqa: E731
    assert [w for p in parts for w in words(p)] == words(long)
