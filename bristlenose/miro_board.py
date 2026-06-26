"""Target-agnostic board IR + trivial layout engine for the Miro bridge.

Pure stdlib (no bristlenose/pydantic imports) so it stays fast, testable, and
renderer-agnostic. The layout engine turns grouped quotes into a `Board` of
frames + stickies + text items in absolute board coordinates; renderers
(`miro_render_svg` for preview, `miro_client`/`server.miro_export` for the real
Miro push) translate the IR to a concrete surface.

Ported and generalised from experiments/board-layout-poc/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- layout constants (board px) -------------------------------------------
STICKY_W = 240.0
QUOTE_H = 200.0
HEADER_H = 76.0
GAP_X = 36.0
GAP_Y = 24.0
FRAME_PAD = 28.0
FRAME_GAP = 72.0
MARGIN = 64.0
TITLE_Y = 46.0
FRAMES_Y = 120.0

# --- colour tokens (Miro named-palette values; renderers map to their own) ---
# Tokens ARE Miro's named sticky colours, so the Miro renderer is identity and
# only the SVG preview needs a token->hex map.
HEADER_TOKEN = "light_pink"
DEFAULT_QUOTE_TOKEN = "light_yellow"

# Bristlenose sentiment -> colour token. Unknown/None -> default.
SENTIMENT_TOKEN = {
    "positive": "light_green",
    "delight": "green",
    "negative": "light_pink",
    "frustration": "red",
    "confusion": "light_blue",
    "neutral": "gray",
    "mixed": "light_yellow",
}


@dataclass
class QuoteCard:
    """The minimal quote shape the layout engine needs (decoupled from DB)."""

    text: str
    participant_id: str
    session_id: str
    start_timecode: float
    sentiment: str | None = None
    link_url: str | None = None  # optional clip link


@dataclass
class Column:
    """One section or theme + its quotes."""

    label: str
    kind: str  # "section" | "theme"
    quotes: list[QuoteCard]


@dataclass
class Frame:
    title: str
    x: float
    y: float
    width: float
    height: float
    kind: str  # "section" | "theme"


@dataclass
class Sticky:
    x: float
    y: float
    width: float
    height: float
    colour: str  # colour token
    text: str
    kind: str = "quote"  # "header" | "quote"
    participant_id: str = ""
    timecode: float = 0.0
    link_url: str | None = None


@dataclass
class TextItem:
    text: str
    x: float
    y: float
    size: float
    weight: str = "700"


@dataclass
class Board:
    title: str
    frames: list[Frame] = field(default_factory=list)
    stickies: list[Sticky] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


def _session_num(session_id: str) -> int:
    m = re.search(r"(\d+)", session_id or "")
    return int(m.group(1)) if m else 0


def _quote_sort_key(q: QuoteCard) -> tuple[int, float]:
    return (_session_num(q.session_id), q.start_timecode)


def fmt_timecode(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _quote_colour(q: QuoteCard, colour_by: str) -> str:
    if colour_by != "sentiment":  # "none" (or anything else) -> single colour
        return DEFAULT_QUOTE_TOKEN
    if q.sentiment:
        return SENTIMENT_TOKEN.get(q.sentiment, DEFAULT_QUOTE_TOKEN)
    return DEFAULT_QUOTE_TOKEN


def _build_frame(
    columns: list[Column], kind: str, title: str, left_x: float, colour_by: str
) -> tuple[Frame, list[Sticky]]:
    n = len(columns)
    max_q = max((len(c.quotes) for c in columns), default=0)
    quotes_h = max_q * (QUOTE_H + GAP_Y) - GAP_Y if max_q else 0
    inner_h = HEADER_H + (GAP_Y + quotes_h if max_q else 0)
    frame_w = FRAME_PAD * 2 + n * STICKY_W + max(0, n - 1) * GAP_X
    frame_h = FRAME_PAD * 2 + inner_h
    frame = Frame(title=title, x=left_x, y=FRAMES_Y, width=frame_w, height=frame_h, kind=kind)

    stickies: list[Sticky] = []
    for i, col in enumerate(columns):
        cx = left_x + FRAME_PAD + i * (STICKY_W + GAP_X)
        stickies.append(Sticky(
            kind="header", x=cx, y=FRAMES_Y + FRAME_PAD, width=STICKY_W, height=HEADER_H,
            colour=HEADER_TOKEN, text=f"{col.label}\n{len(col.quotes)} quote(s)",
        ))
        sy = FRAMES_Y + FRAME_PAD + HEADER_H + GAP_Y
        for q in sorted(col.quotes, key=_quote_sort_key):
            stickies.append(Sticky(
                x=cx, y=sy, width=STICKY_W, height=QUOTE_H,
                colour=_quote_colour(q, colour_by), text=f"“{q.text.strip()}”",
                participant_id=q.participant_id, timecode=q.start_timecode, link_url=q.link_url,
            ))
            sy += QUOTE_H + GAP_Y
    return frame, stickies


def layout_board(columns: list[Column], title: str, colour_by: str = "sentiment") -> Board:
    """Two named frames: Sections (left) then Themes (right). Pure geometry."""
    sections = [c for c in columns if c.kind == "section"]
    themes = [c for c in columns if c.kind == "theme"]

    board = Board(title=title)
    board.texts.append(TextItem(title, MARGIN, TITLE_Y, 22.0, "700"))

    x = MARGIN
    if sections:
        frame, stk = _build_frame(sections, "section", "Sections", x, colour_by)
        board.frames.append(frame)
        board.stickies.extend(stk)
        x = frame.x + frame.width + FRAME_GAP
    if themes:
        frame, stk = _build_frame(themes, "theme", "Themes", x, colour_by)
        board.frames.append(frame)
        board.stickies.extend(stk)

    right = max((f.x + f.width for f in board.frames), default=MARGIN)
    bottom = max((f.y + f.height for f in board.frames), default=FRAMES_Y)
    board.width = right + MARGIN
    board.height = bottom + MARGIN
    return board
