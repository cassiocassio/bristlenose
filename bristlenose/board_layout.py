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

import math
import re
from collections.abc import Callable, Sequence
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
    #: Only the last part of a split quote carries the attribution line and the clip link.
    attributed: bool = True
    #: The parts of one split quote share a set number, so the board groups them; None for a
    #: quote on one sticky.
    set_id: int | None = None


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


#: A quote longer than this becomes two stickies, and longer than twice it, three; never more than
#: three, a longer last part simply growing. Chosen by the owner on 17 Oct 2026 from sample boards of
#: real sessions at 650, 325 and about two sentences: across the trial runs' 720 quotes, 325 leaves
#: 44% whole, 37% as pairs and 19% as trios, each part about 55 words — roughly what a researcher
#: trims a quote to by hand.
SPLIT_AT = 325
MAX_PARTS = 3
#: Where a part may end, best first: a sentence, then a clause, then a phrase, then any word.
_BREAKS = (
    re.compile(r"[.?!…][\"”’)]*\s+"),
    re.compile(r"[;:]\s+|\s+[—–]\s+"),
    re.compile(r",\s+"),
    re.compile(r"\s+"),
)


def split_quote(text: str, at: int = SPLIT_AT, max_parts: int = MAX_PARTS) -> list[str]:
    """A quote as one, two or three parts that each read on their own, as researchers split a
    long quote by hand: at the most natural break near each even split, a part that goes on ending
    in "…" and the next beginning with one. The words are never changed, only where they break."""
    text = text.strip()
    n = max(1, min(max_parts, -(-len(text) // at)))
    if n == 1:
        return [text]
    cuts: list[int] = []
    start = 0
    for k in range(1, n):
        target = round(len(text) * k / n)
        window = max(40, (len(text) // n) // 4)
        lo, hi = max(start + 1, target - window), min(len(text) - 1, target + window)
        best: int | None = None
        for pattern in _BREAKS:
            ends = [m.end() for m in pattern.finditer(text, lo, hi)]
            if ends:
                best = min(ends, key=lambda e: abs(e - target))
                break
        cuts.append(best if best is not None else target)
        start = cuts[-1]
    parts = [text[a:b].strip() for a, b in zip([0, *cuts], [*cuts, len(text)], strict=True)]
    out: list[str] = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            # "successful." goes on as "successful…": the full stop gives way to the ellipsis, as
            # in a hand-split quote; a question or an exclamation keeps its mark.
            part = part.rstrip(",;:—– ").removesuffix(".") + ("" if part.endswith("…") else "…")
        if i > 0:
            part = "…" + part
        out.append(part)
    return out


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


#: Sticky width from its text: Miro fits the type to the box and a rectangle keeps its
#: proportions, so for every sticky to show the same size of type its area must follow its text —
#: its width the square root of its length. The factor is the owner's own hand: resizing split
#: quotes in Miro until the type matched, 207 characters came to 255 wide, 293 to 281, 329 to 330,
#: 227 to 255 (17 Oct 2026). Lines then run about 8–10 words, which is a comfortable measure.
SIZE_K = 17.0
#: Between the parts of one quote, and how far each part steps right of the one before: the set
#: reads as one quote, the left edges stepping, the right edges where their own widths put them.
SET_GAP = 12.0
SET_STAGGER = 24.0


def sticky_width(chars: int) -> float:
    """The width that shows ``chars`` characters at the board's one size of type."""
    return SIZE_K * math.sqrt(max(chars, 1))


@dataclass
class QuotePart:
    """One sticky of a quote: its words (with the quote marks it carries), whether the attribution
    goes on it, and its size."""

    text: str
    attributed: bool
    width: float
    height: float


def quote_part_texts(text: str, split: bool = True) -> list[str]:
    """A quote's words as each sticky shows them, board-neutral: one string, or with ``split`` a
    long quote's two or three parts (`split_quote`), the opening mark on the first and the closing
    mark on the last. The attribution goes on the last part; the board adds it. FigJam and Miro both
    build on this, so a quote breaks in the same places on either board."""
    parts = split_quote(text, SPLIT_AT, MAX_PARTS) if split else [text.strip()]
    return [("“" if k == 0 else "") + part + ("”" if k == len(parts) - 1 else "")
            for k, part in enumerate(parts)]


def quote_parts(text: str, attribution_line: str, split: bool = True) -> list[QuotePart]:
    """A quote as the stickies a Miro board shows it on (`quote_part_texts`), each sized so the
    type comes out the same."""
    shown = quote_part_texts(text, split)
    out: list[QuotePart] = []
    for k, part in enumerate(shown):
        last = k == len(shown) - 1
        w = sticky_width(len(part) + (len(attribution_line) if last else 0))
        out.append(QuotePart(part, last, w, w * RECT_ASPECT))
    return out


def set_extent(parts: Sequence[QuotePart]) -> tuple[float, float]:
    """(width, height) of a quote's stickies laid out as a set."""
    w = max((p.width + k * SET_STAGGER for k, p in enumerate(parts)), default=0.0)
    h = sum(p.height for p in parts) + max(len(parts) - 1, 0) * SET_GAP
    return w, h


def quote_colour(q: QuoteCard, colour_by: str) -> str:
    if colour_by != "sentiment":  # "none" (or anything else) -> single colour
        return DEFAULT_QUOTE_TOKEN
    if q.sentiment:
        return SENTIMENT_TOKEN.get(q.sentiment, DEFAULT_QUOTE_TOKEN)
    return DEFAULT_QUOTE_TOKEN


def _build_frame(
    columns: list[Column], kind: str, title: str, left_x: float, colour_by: str,
    strings: BoardStrings, split: bool = True, set_ids: list[int] | None = None,
) -> tuple[Frame, list[Sticky]]:
    """A frame of columns, each a header and its quotes stacked to their real heights. A column is
    as wide as its widest quote set: stickies are sized by their text, not to a grid."""
    set_ids = set_ids if set_ids is not None else [0]
    stickies: list[Sticky] = []
    cx = left_x + FRAME_PAD
    bottom = FRAMES_Y + FRAME_PAD + HEADER_H
    for col in columns:
        sets = [(q, quote_parts(q.text, attribution(q.participant_id, q.start_timecode), split))
                for q in sorted(col.quotes, key=quote_sort_key)]
        col_w = max([STICKY_W] + [set_extent(parts)[0] for _, parts in sets])
        stickies.append(Sticky(
            kind="header", x=cx, y=FRAMES_Y + FRAME_PAD, width=STICKY_W, height=HEADER_H,
            colour=HEADER_TOKEN, text=f"{col.label}\n{strings.quote_count(len(col.quotes))}",
        ))
        sy = FRAMES_Y + FRAME_PAD + HEADER_H + GAP_Y
        for q, parts in sets:
            set_id = None
            if len(parts) > 1:
                set_ids[0] += 1
                set_id = set_ids[0]
            for k, part in enumerate(parts):
                stickies.append(Sticky(
                    x=cx + k * SET_STAGGER, y=sy, width=part.width, height=part.height,
                    colour=quote_colour(q, colour_by), text=part.text,
                    participant_id=q.participant_id, timecode=q.start_timecode, link_url=q.link_url,
                    attributed=part.attributed, set_id=set_id,
                ))
                sy += part.height + (SET_GAP if k < len(parts) - 1 else 0)
            sy += GAP_Y
        bottom = max(bottom, sy - GAP_Y)
        cx += col_w + GAP_X
    frame_w = (cx - GAP_X if columns else cx) - left_x + FRAME_PAD
    frame = Frame(title=title, x=left_x, y=FRAMES_Y, width=frame_w,
                  height=bottom - FRAMES_Y + FRAME_PAD, kind=kind)
    return frame, stickies


def layout_board(columns: list[Column], title: str, colour_by: str = "sentiment",
                 strings: BoardStrings | None = None, split: bool = True) -> Board:
    """Two named frames: sections (left) then themes (right). Pure geometry."""
    strings = strings or BoardStrings()
    sections = [c for c in columns if c.kind == "section"]
    themes = [c for c in columns if c.kind == "theme"]

    board = Board(title=title)
    board.texts.append(TextItem(title, MARGIN, TITLE_Y, 22.0, "700"))

    x = MARGIN
    set_ids = [0]  # one count across both frames, so every set's number is its own
    if sections:
        frame, stk = _build_frame(sections, "section", strings.sections, x, colour_by, strings,
                                  split, set_ids)
        board.frames.append(frame)
        board.stickies.extend(stk)
        x = frame.x + frame.width + FRAME_GAP
    if themes:
        frame, stk = _build_frame(themes, "theme", strings.themes, x, colour_by, strings,
                                  split, set_ids)
        board.frames.append(frame)
        board.stickies.extend(stk)

    right = max((f.x + f.width for f in board.frames), default=MARGIN)
    bottom = max((f.y + f.height for f in board.frames), default=FRAMES_Y)
    board.width = right + MARGIN
    board.height = bottom + MARGIN
    return board
