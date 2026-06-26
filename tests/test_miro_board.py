"""Unit tests for the pure Miro board layout engine (no network, no DB)."""

from __future__ import annotations

from bristlenose.miro_board import (
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
        for upper, lower in zip(col, col[1:]):
            assert upper.y + upper.height <= lower.y + 0.01


def test_empty_columns_safe() -> None:
    board = layout_board([], "Empty")
    assert board.frames == []
    assert board.width > 0 and board.height > 0
