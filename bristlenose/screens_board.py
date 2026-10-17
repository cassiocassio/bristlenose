"""The Screens lens as a Miro board: one frame per screengrab, quotes placed as the lens places them.

Pure and stdlib-only, like `board_layout`: the server hands it the shot list (`screen_text/shots.py`)
with each still's pixel size, the quotes' words, and the researcher's saved arrangements; it returns
frames in board coordinates, each holding its still and its stickies in the frame's own coordinates,
so a workshop that drags a frame drags everything in it (`docs/design-screens-export.md` §6).

The placement rules are the lens's (`frontend/src/islands/screens/layout.ts`), ported rather than
re-imagined: which edge a pinned quote annotates, how a column stacks, how a band wraps, and how a
saved arrangement's intent becomes a spot. Both copies read `tests/fixtures/screens-layout-contract.json`,
so they cannot quietly disagree. Only the parts a board needs are ported: leaders, modes and
hysteresis are the lens's screen-width concerns, and a board has room for two columns always.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# ── The lens's constants (layout.ts) ─────────────────────────────────────────

COLUMN_GUTTER = 32
STAGGER_STEP = 8
STAGGER_STEPS = 3
MAX_STAGGER = STAGGER_STEP * STAGGER_STEPS
GUTTER = 12
MIN_STEP = 46
BAND_Y = 0.15
BAND_X = 0.2

# ── The board's own sizes ────────────────────────────────────────────────────

#: The still's width on the board. Miro keeps an image's aspect from its width.
SHOT_W = 1200.0
#: A sticky's width; Miro draws a square-shaped sticky this much taller than wide (measured
#: 17 Oct 2026: width 200 came back 229.146 tall).
STICKY_W = 300.0
STICKY_ASPECT = 229.14572864321605 / 200
STICKY_H = STICKY_W * STICKY_ASPECT
#: Inside a frame, round its contents; between frames, room for the team's own stickies.
FRAME_PAD = 80.0
FRAME_GAP = 400.0
ROW_GAP = 500.0


def edge_for(box: Sequence[float], mode: str = "lr") -> str:
    """Which edge an automatic card about the line `box` (x, y, w, h in 0–1) annotates."""
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    if mode == "rows":
        return "T" if cy < 0.5 else "B"
    if BAND_X <= cx <= 1 - BAND_X:
        if cy < BAND_Y:
            return "T"
        if cy > 1 - BAND_Y:
            return "B"
    return "L" if mode == "lr" and cx < 0.5 else "R"


def place_column(cards: Sequence[tuple[float, float]], limit: float) -> tuple[list[float], bool]:
    """Tops for a column of (want, height) cards, and whether it stacked (layout.ts placeColumn)."""
    if not cards:
        return [], False
    tops: list[float] = []
    y = 0.0
    for want, height in cards:
        top = max(want, y)
        tops.append(top)
        y = top + height + GUTTER
    last_h = cards[-1][1]
    budget = max(limit, 320)
    if tops[-1] + last_h <= budget or len(cards) < 2:
        return tops, False
    start = max(0.0, min(cards[0][0], budget - last_h - MIN_STEP * (len(cards) - 1)))
    step = max(MIN_STEP, (budget - start - last_h) / (len(cards) - 1))
    return [start + i * step for i in range(len(cards))], True


def place_row(cards: Sequence[tuple[float, float, float]], limit: float) -> tuple[list[float], list[float], float]:
    """Lefts and tops for a band of (want, width, height) cards, and its height (placeRow)."""
    lefts: list[float] = []
    tops: list[float] = []
    x = line_top = line_h = 0.0
    for want, width, height in cards:
        left = min(max(want, x), max(x, limit - width))
        if left + width > limit and x > 0:
            line_top += line_h + GUTTER
            line_h = 0.0
            x = 0.0
            left = min(max(0.0, want), max(0.0, limit - width))
        left = max(0.0, left)
        lefts.append(left)
        tops.append(line_top)
        line_h = max(line_h, height)
        x = left + width + GUTTER
    return lefts, tops, (line_top + line_h if cards else 0.0)


def compose(cards: Sequence[tuple[str, Sequence[float]]], shot_w: float, shot_h: float,
            card_w: float, card_h: float, mode: str = "lr") -> dict[str, Any]:
    """Where every pinned card goes (layout.ts composeBoard), for cards of one size.

    `cards` is (id, anchor box) in time order. Returns {"at": {id: {edge, top, left, z}},
    "band": {"T": h, "B": h}}: a column's spot is in its own track (left is the stagger), a
    band's in its own box above or below the still."""
    at: dict[str, dict[str, Any]] = {}
    band = {"T": 0.0, "B": 0.0}
    for side in ("L", "R"):
        col = [(cid, box, i, max(0.0, (box[1] + box[3] / 2) * shot_h - 20))
               for i, (cid, box) in enumerate(cards) if edge_for(box, mode) == side]
        col.sort(key=lambda c: (c[3], c[2]))
        if not col:
            continue
        tops, stacked = place_column([(c[3], card_h) for c in col], shot_h)
        for i, c in enumerate(col):
            k = i % (STAGGER_STEPS + 1) if stacked else 0
            left = MAX_STAGGER - k * STAGGER_STEP if side == "L" else k * STAGGER_STEP
            at[c[0]] = {"edge": side, "top": tops[i], "left": left, "z": 2 + i}
    for edge in ("T", "B"):
        row = [(cid, box, i) for i, (cid, box) in enumerate(cards) if edge_for(box, mode) == edge]
        row.sort(key=lambda c: (c[1][0] + c[1][2] / 2, c[2]))
        if not row:
            continue
        lefts, tops, height = place_row(
            [((c[1][0] + c[1][2] / 2) * shot_w - card_w / 2, card_w, card_h) for c in row], shot_w)
        for i, c in enumerate(row):
            at[c[0]] = {"edge": edge, "top": tops[i], "left": lefts[i], "z": 2}
        band[edge] = height
    return {"at": at, "band": band}


def rect_from_intent(intent: Mapping[str, Any], shot: tuple[float, float, float, float],
                     card_w: float, card_h: float) -> tuple[float, float]:
    """Where a card with a saved intent sits, against the still at `shot` (left, top, w, h)
    (layout.ts rectFromIntent). An edge card's distance out never goes negative."""
    sl, st, sw, sh = shot
    if intent.get("kind") == "over":
        return sl + float(intent["x"]) * sw, st + float(intent["y"]) * sh
    out = max(0.0, float(intent.get("out", 0)))
    along = float(intent.get("along", 0))
    e = intent.get("edge")
    if e == "L":
        return sl - out - card_w, st + along * sh
    if e == "R":
        return sl + sw + out, st + along * sh
    if e == "T":
        return sl + along * sw, st - out - card_h
    return sl + along * sw, st + sh + out


# ── The board ────────────────────────────────────────────────────────────────


@dataclass
class ScreenSticky:
    dom_id: str
    #: Top-left, in the frame's coordinates.
    x: float
    y: float
    z: int = 1


@dataclass
class ScreenFrame:
    title: str
    session_id: str
    filename: str
    #: Top-left on the board, and size.
    x: float
    y: float
    width: float
    height: float
    #: The still's top-left in the frame, and its size.
    shot: tuple[float, float, float, float]
    stickies: list[ScreenSticky] = field(default_factory=list)


def lay_out_shot(shot: Mapping[str, Any], still_px: tuple[int, int],
                 arrangement: Mapping[str, Mapping[str, Any]] | None = None,
                 known: set[str] | None = None) -> tuple[float, float, tuple[float, float, float, float],
                                                         list[ScreenSticky]]:
    """One still's frame contents: (width, height, still rect, stickies), all in frame coordinates.

    Pinned quotes go round the still as the lens places them, or where the researcher's saved
    arrangement put them; every other quote of that participant on that screen goes in rows
    beneath. `known` limits the stickies to quotes the board can write (hidden ones are already
    out of the shot list)."""
    pw, ph = still_px
    sw = SHOT_W
    sh = SHOT_W * ph / pw if pw else SHOT_W * 9 / 16
    pins = [(p["dom_id"], p["box"]) for p in shot["pins"] if known is None or p["dom_id"] in known]
    loose = [d for d in shot["loose"] if known is None or d in known]
    # Card positions relative to the still's top-left, whichever rule placed them.
    rel: dict[str, tuple[float, float, int]] = {}
    if arrangement:
        for cid, _ in pins:
            if cid in arrangement:
                x, y = rect_from_intent(arrangement[cid], (0, 0, sw, sh), STICKY_W, STICKY_H)
                rel[cid] = (x, y, int(arrangement[cid].get("z", 1)))
        # A quote the arrangement places (a card the researcher moved out of the list) is placed.
        for cid in loose:
            if cid in arrangement:
                x, y = rect_from_intent(arrangement[cid], (0, 0, sw, sh), STICKY_W, STICKY_H)
                rel[cid] = (x, y, int(arrangement[cid].get("z", 1)))
    unplaced_pins = [(cid, box) for cid, box in pins if cid not in rel]
    if unplaced_pins:
        comp = compose(unplaced_pins, sw, sh, STICKY_W, STICKY_H)
        band_t = comp["band"]["T"]
        for cid, spot in comp["at"].items():
            e = spot["edge"]
            if e == "L":
                x = -(COLUMN_GUTTER + MAX_STAGGER + STICKY_W) + spot["left"]
                y = spot["top"]
            elif e == "R":
                x = sw + COLUMN_GUTTER + spot["left"]
                y = spot["top"]
            elif e == "T":
                x = spot["left"]
                y = -(COLUMN_GUTTER + band_t) + spot["top"]
            else:
                x = spot["left"]
                y = sh + COLUMN_GUTTER + spot["top"]
            rel[cid] = (x, y, spot["z"])
    # Everything else said here, in rows under whatever is already below the still.
    rest = [d for d in loose if d not in rel]
    below = max([sh] + [y + STICKY_H for x, y, _ in rel.values()])
    if rest:
        lo = min([0.0] + [x for x, _, _ in rel.values()])
        hi = max([sw] + [x + STICKY_W for x, _, _ in rel.values()])
        lefts, tops, _ = place_row([(0.0, STICKY_W, STICKY_H)] * len(rest), hi - lo)
        for d, left, top in zip(rest, lefts, tops, strict=True):
            rel[d] = (lo + left, below + COLUMN_GUTTER + top, 1)
    xs = [0.0, sw] + [x for x, _, _ in rel.values()] + [x + STICKY_W for x, _, _ in rel.values()]
    ys = [0.0, sh] + [y for _, y, _ in rel.values()] + [y + STICKY_H for _, y, _ in rel.values()]
    ox, oy = FRAME_PAD - min(xs), FRAME_PAD - min(ys)
    width = max(xs) - min(xs) + 2 * FRAME_PAD
    height = max(ys) - min(ys) + 2 * FRAME_PAD
    stickies = [ScreenSticky(d, x + ox, y + oy, z)
                for d, (x, y, z) in sorted(rel.items(), key=lambda kv: kv[1][2])]
    return width, height, (ox, oy, sw, sh), stickies


def lay_out_board(shots: Sequence[Mapping[str, Any]], still_px: Mapping[str, tuple[int, int]],
                  arrangements: Mapping[tuple[str, str], Mapping[str, Mapping[str, Any]]] | None = None,
                  known: set[str] | None = None) -> list[ScreenFrame]:
    """Every still as a frame: a row per participant, left to right in the shot list's order.

    `still_px` maps a shot's filename to its pixel size; a shot without one is left out (its still
    could not be made). `arrangements` is keyed (screen key, session id)."""
    frames: list[ScreenFrame] = []
    y = 0.0
    row: list[ScreenFrame] = []
    session = None
    x = 0.0

    def close_row() -> float:
        return max((f.height for f in row), default=0.0)

    for shot in shots:
        px = still_px.get(shot["filename"])
        if px is None:
            continue
        if shot["session_id"] != session:
            if row:
                y += close_row() + ROW_GAP
            row, x, session = [], 0.0, shot["session_id"]
        arr = (arrangements or {}).get((shot["screen_key"], shot["session_id"]))
        w, h, rect, stickies = lay_out_shot(shot, px, arr, known)
        frame = ScreenFrame(f"{shot['code'].upper()} · {shot['title']}", shot["session_id"],
                            shot["filename"], x, y, w, h, rect, stickies)
        frames.append(frame)
        row.append(frame)
        x += w + FRAME_GAP
    return frames


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """A JPEG's (width, height) from its start-of-frame marker, or None if it has none."""
    i = 2
    n = len(data)
    if data[:2] != b"\xff\xd8":
        return None
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return (w, h) if w and h else None
        i += 2 + length
    return None
