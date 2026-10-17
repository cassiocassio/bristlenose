"""Unit tests for the pure Miro board layout engine (no network, no DB)."""

from __future__ import annotations

import itertools

import pytest

from bristlenose.board_layout import (
    DEFAULT_QUOTE_TOKEN,
    HEADER_TOKEN,
    Column,
    QuoteCard,
    layout_board,
)


def _q(text: str, sid: str, tc: float, sentiment: str | None = None) -> QuoteCard:
    return QuoteCard(text=text, participant_id="p1", session_id=sid,
                     start_timecode=tc, sentiment=sentiment)


def _columns() -> list[Column]:
    return [
        Column("Dashboard", "section", [_q("a", "s1", 26, "frustration"),
                                        _q("b", "s1", 10, "confusion")]),
        Column("Search", "section", [_q("c", "s2", 5, "delight")]),
        Column("Onboarding", "theme", [_q("d", "s1", 66)]),
    ]


def test_two_named_frames_sections_then_themes() -> None:
    board = layout_board(_columns(), "T")
    assert [(f.title, f.kind) for f in board.frames] == [
        ("Sections", "section"),
        ("Themes", "theme"),
    ]
    # Sections frame is left of the Themes frame.
    assert board.frames[0].x < board.frames[1].x


def test_header_sticky_per_column() -> None:
    board = layout_board(_columns(), "T")
    headers = [s for s in board.stickies if s.kind == "header"]
    assert len(headers) == 3  # one per column
    assert all(s.colour == HEADER_TOKEN for s in headers)
    assert any("Dashboard" in s.text for s in headers)


def test_header_count_is_singular_or_plural_never_parenthesised() -> None:
    # A board is a client-facing deliverable, so "1 quote(s)" is not acceptable.
    # Dashboard has 2 quotes, Search has 1 — pin both branches.
    board = layout_board(_columns(), "T")
    text = {s.text.split("\n")[0]: s.text for s in board.stickies if s.kind == "header"}
    assert text["Dashboard"].endswith("2 quotes")
    assert text["Search"].endswith("1 quote")
    assert not any("(s)" in s for s in text.values())


def test_quotes_sorted_session_then_time() -> None:
    board = layout_board(_columns(), "T")
    # Dashboard column: s1@10 before s1@26 -> "b" above "a" (smaller y first).
    quotes = [s for s in board.stickies if s.kind == "quote"]
    dash = sorted([s for s in quotes if "a" in s.text or "b" in s.text],
                  key=lambda s: s.y)
    assert dash[0].text == "“b”"
    assert dash[1].text == "“a”"


def test_colour_by_sentiment_maps_tokens() -> None:
    board = layout_board(_columns(), "T", colour_by="sentiment")
    by_text = {s.text: s.colour for s in board.stickies if s.kind == "quote"}
    assert by_text["“c”"] == "green"          # delight
    assert by_text["“a”"] == "red"            # frustration
    assert by_text["“d”"] == DEFAULT_QUOTE_TOKEN  # no sentiment -> default


def test_colour_by_none_is_default() -> None:
    board = layout_board(_columns(), "T", colour_by="none")
    quotes = [s for s in board.stickies if s.kind == "quote"]
    assert all(s.colour == DEFAULT_QUOTE_TOKEN for s in quotes)


def test_no_overlap_within_column() -> None:
    board = layout_board(_columns(), "T")
    # Stickies in the same column (same x) must not vertically overlap.
    by_x: dict[float, list] = {}
    for s in board.stickies:
        by_x.setdefault(s.x, []).append(s)
    for col in by_x.values():
        col.sort(key=lambda s: s.y)
        for upper, lower in itertools.pairwise(col):
            assert upper.y + upper.height <= lower.y + 0.01


def test_empty_columns_safe() -> None:
    board = layout_board([], "Empty")
    assert board.frames == []
    assert board.width > 0 and board.height > 0


def test_stickies_are_rectangles_and_the_layout_reserves_what_miro_draws() -> None:
    """Miro sizes a sticky from its width and keeps the shape's proportion (measured 17 Oct 2026:
    a rectangle 300 wide is 195.43 tall). A column spaced for any other height overlaps."""
    from bristlenose import board_layout as bl
    from bristlenose.server.miro_export import _sticky_item

    assert bl.STICKY_SHAPE == "rectangle"
    assert bl.QUOTE_H == bl.HEADER_H == bl.STICKY_W * 195.42857142857142 / 300
    s = bl.Sticky(kind="quote", x=0, y=0, width=bl.STICKY_W, height=bl.QUOTE_H, colour="light_yellow",
                  text="hello", participant_id="p1", timecode=1.0)
    assert _sticky_item(s)["data"]["shape"] == "rectangle"


# ── Long quotes as two or three stickies (owner, 17 Oct 2026) ─────────────────────────────────


def test_a_quote_under_the_split_stays_whole_and_a_long_one_breaks_at_sentence_ends() -> None:
    from bristlenose.board_layout import SPLIT_AT, quote_part_texts, split_quote

    short = "It was fine. I found the jars."
    assert split_quote(short) == [short]
    long_ = " ".join(f"Sentence number {i} goes on for a while about the jars." for i in range(30))
    parts = split_quote(long_)
    assert 2 <= len(parts) <= 3 and all(len(p) <= SPLIT_AT + 120 for p in parts)
    assert parts[0].endswith("…") and parts[1].startswith("…")
    # Only the breaks change: take the dots off and the words are the quote's, in order.
    joined = " ".join(p.strip("…") for p in parts)
    assert joined.replace(". ", " ").replace(".", "") == long_.replace(". ", " ").replace(".", "")
    shown = quote_part_texts(long_)
    assert shown[0].startswith("“") and shown[-1].endswith("”") and not shown[1].startswith("“")


def test_never_more_than_three_parts_and_never_a_split_when_asked_not_to() -> None:
    from bristlenose.board_layout import quote_part_texts, split_quote

    huge = "A sentence. " * 400
    assert len(split_quote(huge)) == 3
    assert quote_part_texts(huge, split=False) == [f"“{huge.strip()}”"]


def test_every_sticky_shows_the_same_size_of_type() -> None:
    """Miro fits type to the box and a rectangle keeps its shape, so the area follows the text:
    the width goes with the square root of the length (the owner's hand: 207 chars → 255 wide)."""
    from bristlenose.board_layout import SIZE_K, quote_parts, sticky_width

    assert round(sticky_width(207)) == round(SIZE_K * 207 ** 0.5) and 240 < sticky_width(207) < 260
    [p] = quote_parts("x" * 100, "— P1 · 0:10")
    [q] = quote_parts("x" * 400, "— P1 · 0:10")
    assert q.width / p.width == pytest.approx(((400 + 13) / (100 + 13)) ** 0.5, rel=0.01)


def test_the_quotes_board_stacks_a_set_stepping_right_with_only_the_last_attributed() -> None:
    from bristlenose.board_layout import SET_GAP, SET_STAGGER, Column, QuoteCard, layout_board

    long_ = " ".join(f"Sentence {i} is about the jars and the shelf and the bag." for i in range(20))
    board = layout_board([Column("Basket", "section", [QuoteCard(long_, "p1", "s1", 12.0)])], "B")
    parts = [s for s in board.stickies if s.kind == "quote"]
    assert len(parts) == 2 and parts[0].set_id == parts[1].set_id is not None
    assert [s.attributed for s in parts] == [False, True]
    assert parts[1].x == parts[0].x + SET_STAGGER
    assert parts[1].y == pytest.approx(parts[0].y + parts[0].height + SET_GAP)
    unsplit = layout_board([Column("Basket", "section", [QuoteCard(long_, "p1", "s1", 12.0)])], "B", split=False)
    assert [s.set_id for s in unsplit.stickies if s.kind == "quote"] == [None]
