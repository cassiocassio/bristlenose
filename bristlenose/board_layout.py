"""Target-agnostic board IR + trivial layout engine for the whiteboard bridges.

Near-pure stdlib (no pydantic models, no I/O) so it stays fast, testable, and
renderer-agnostic. The layout engine turns grouped quotes into a `Board` of
frames + stickies + text items in absolute board coordinates; renderers
(`miro_render_svg` for preview, `miro_client`/`server.miro_export` for the real
Miro push) translate the IR to a concrete surface. `board_manifest` reads the
same columns, ordering and colour tokens but not the geometry: FigJam stickies
grow with their text, so the in-editor plugin does its own vertical layout.

**The board's words arrive as `BoardStrings`; this module never resolves them.**
A Miro board is a deliverable a researcher hands to a client, which puts it on
the localised side of the surface table (`docs/design-i18n.md`) — so the locale
belongs to `server.miro_export`, which knows who asked, and geometry stays here.
The defaults are the English the board shipped with, so a caller that has no
locale is unchanged; `count_noun` is one of them, because English plurals have
exactly one source of truth in this repo (CLAUDE.md § CLI plurals) and a local
mirror would be a second.

Ported and generalised from experiments/board-layout-poc/.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from bristlenose.utils.text import count_noun
from bristlenose.utils.timecodes import format_timecode

# --- layout constants (board px) -------------------------------------------
#: Every board's stickies are Miro's wide rectangle: a quote wraps in longer, fewer lines than in
#: a square (owner, 17 Oct 2026: "nearly always better").
STICKY_SHAPE = "rectangle"
#: Miro sizes a sticky from its width alone and keeps the shape's proportion, so the height the
#: layout reserves must be the one Miro draws. Measured 17 Oct 2026: a rectangle 300 wide is
#: 195.43 tall (450 is 293.14); a square 200 wide is 229.15. The old fixed heights (quote 200,
#: header 76) were less than a 240-wide square's 275, so a column's stickies overlapped.
RECT_ASPECT = 195.42857142857142 / 300
#: 300, not the 240 the squares had: a rectangle that narrow is 156 tall, and Miro shrinks a long
#: quote's type to fit (project-ikea's quotes: median 122 characters, p90 256). Owner, 17 Oct 2026.
STICKY_W = 300.0
QUOTE_H = STICKY_W * RECT_ASPECT
HEADER_H = QUOTE_H
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


def english_quote_count(n: int) -> str:
    return count_noun(n, "quote")


@dataclass(frozen=True)
class BoardStrings:
    """Every word the board says that is not the researcher's own data.

    `quote_count` is a callable rather than a template because the plural form
    is a function of the number in fourteen of the twenty-one languages, and
    `2 cytaty` / `5 cytatów` is not something a format string can reach.
    """

    sections: str = "Sections"
    themes: str = "Themes"
    quote_count: Callable[[int], str] = english_quote_count


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


def quote_sort_key(q: QuoteCard) -> tuple[int, float]:
    return (_session_num(q.session_id), q.start_timecode)


def fmt_timecode(seconds: float) -> str:
    """The house timecode (``05:30`` / ``1:30:00``) on a sticky's attribution.

    Was ``f"{total // 60}:{total % 60:02d}"`` — minutes never rolled into hours,
    so an hour read ``60:00`` and, from 100 minutes, the output could not be
    parsed back at all. The corpus's longest session is 99.7 minutes.
    """
    return format_timecode(seconds)


#: Miro refuses a sticky whose content, markup included, is longer than this, and with it the
#: whole batch the sticky was in.
MIRO_STICKY_MAX = 6000


def fit_miro_sticky(body: str, rest: str) -> str:
    """``escape(body) + rest`` as a sticky's content, the body cut only if Miro would refuse it.

    Quotes are never shortened for readability (owner, 17 Oct 2026): a rectangle sticky shrinks
    its type to fit, and a participant's words cut from a deliverable are words lost with nothing
    to say so. Across the trial runs 62% of quotes ran past the old 300-character cut; the longest
    was 2,157 characters, a third of Miro's limit."""
    from html import escape

    out = escape(body) + rest
    while len(out) > MIRO_STICKY_MAX and body:
        body = body[: max(0, len(body) - (len(out) - MIRO_STICKY_MAX) - 1)].rstrip()
        out = escape(body + "…") + rest
    return out


def attribution(participant_id: str, timecode: float) -> str:
    """The italic line under a quote: ``— P2 · 00:22``. One copy for every board."""
    return f"— {participant_id.upper()} · {fmt_timecode(timecode)}"


def quoted(text: str) -> str:
    """A quote as a sticky shows it, in curly marks."""
    return f"“{text.strip()}”"


def quote_colour(q: QuoteCard, colour_by: str) -> str:
    if colour_by != "sentiment":  # "none" (or anything else) -> single colour
        return DEFAULT_QUOTE_TOKEN
    if q.sentiment:
        return SENTIMENT_TOKEN.get(q.sentiment, DEFAULT_QUOTE_TOKEN)
    return DEFAULT_QUOTE_TOKEN


def _build_frame(
    columns: list[Column], kind: str, title: str, left_x: float, colour_by: str,
    strings: BoardStrings,
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
            colour=HEADER_TOKEN, text=f"{col.label}\n{strings.quote_count(len(col.quotes))}",
        ))
        sy = FRAMES_Y + FRAME_PAD + HEADER_H + GAP_Y
        for q in sorted(col.quotes, key=quote_sort_key):
            stickies.append(Sticky(
                x=cx, y=sy, width=STICKY_W, height=QUOTE_H,
                colour=quote_colour(q, colour_by), text=quoted(q.text),
                participant_id=q.participant_id, timecode=q.start_timecode, link_url=q.link_url,
            ))
            sy += QUOTE_H + GAP_Y
    return frame, stickies


def layout_board(columns: list[Column], title: str, colour_by: str = "sentiment",
                 strings: BoardStrings | None = None) -> Board:
    """Two named frames: sections (left) then themes (right). Pure geometry."""
    strings = strings or BoardStrings()
    sections = [c for c in columns if c.kind == "section"]
    themes = [c for c in columns if c.kind == "theme"]

    board = Board(title=title)
    board.texts.append(TextItem(title, MARGIN, TITLE_Y, 22.0, "700"))

    x = MARGIN
    if sections:
        frame, stk = _build_frame(sections, "section", strings.sections, x, colour_by, strings)
        board.frames.append(frame)
        board.stickies.extend(stk)
        x = frame.x + frame.width + FRAME_GAP
    if themes:
        frame, stk = _build_frame(themes, "theme", strings.themes, x, colour_by, strings)
        board.frames.append(frame)
        board.stickies.extend(stk)

    right = max((f.x + f.width for f in board.frames), default=MARGIN)
    bottom = max((f.y + f.height for f in board.frames), default=FRAMES_Y)
    board.width = right + MARGIN
    board.height = bottom + MARGIN
    return board
