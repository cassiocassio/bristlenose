"""The Screens lens as a Miro board: one frame per screen, everyone's quotes stacked beneath it.

Pure and stdlib-only, like `board_layout`. The server hands it the screens in journey order
(`screen_text/shots.py` `journey`) with each still's pixel size; it returns frames in board
coordinates, each holding its still and its stickies in the frame's own coordinates, so a
workshop that drags a frame drags everything in it (`docs/design-screens-export.md` §6).

Quotes are stacked under the still, a new row for each participant, rather than placed round it
as the lens places them: that placement rests on a participant reading the page's own words
aloud, and "this bit over here" with a wave of the mouse never lands. On a board the team will
rearrange anyway, plain stacks are the reliable shape (owner, 17 Oct 2026).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bristlenose.board_layout import SET_STAGGER, QuotePart, set_extent, set_tops

#: The still's width on the board. Miro keeps an image's aspect from its width.
SHOT_W = 1200.0
#: Between quote sets in a row and between rows. Stickies are sized by their text (one size of
#: type, `board_layout.quote_parts`), so a row holds as many as fit the screengrab's width.
GAP = 24.0
#: Between the still and the first row, and between one participant's rows and the next's.
SECTION_GAP = 64.0
#: How far each further participant's screengrab sits down and right of the one before it, behind
#: it: enough to count them and grab one, not enough to cover the front one's content.
CASCADE = 40.0
#: Inside a frame, round its contents; between frames, room for the team's own stickies.
FRAME_PAD = 80.0
FRAME_GAP = 400.0


@dataclass
class ScreenSticky:
    dom_id: str
    #: Top-left, in the frame's coordinates, and size (Miro takes the width and keeps the shape).
    x: float
    y: float
    width: float
    height: float = 0.0
    #: The words this sticky shows (quote marks placed); only a quote's last part is attributed.
    text: str = ""
    attributed: bool = True
    #: The parts of one split quote share a set number, so the board groups them.
    set_id: int | None = None


@dataclass
class ScreenStill:
    """One participant's screengrab of the screen, in the frame's coordinates (top-left)."""

    filename: str
    #: "P3 · Checkout": Miro shows an image's title when it is selected, which is how a researcher
    #: peeking under the front one tells whose it is.
    title: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class ScreenFrame:
    title: str
    #: Top-left on the board, and size.
    x: float
    y: float
    width: float
    height: float
    #: Every participant's screengrab, in the order to create them: back first, so the front one,
    #: created last, is drawn on top.
    stills: list[ScreenStill] = field(default_factory=list)
    stickies: list[ScreenSticky] = field(default_factory=list)


def lay_out_screen(groups: Sequence[tuple[str, Sequence[str]]],
                   versions: Sequence[tuple[str, str, tuple[int, int]]],
                   parts: Mapping[str, Sequence[QuotePart]],
                   set_ids: list[int] | None = None) -> tuple[float, float, list[ScreenStill], list[ScreenSticky]]:
    """One screen's frame contents: (width, height, stills back first, stickies), frame coordinates.

    `versions` is (filename, title, pixel size) for each participant's screengrab, front first; the
    rest cascade down and right behind it. `groups` is (participant code, quote ids) in the order to
    lay them out beneath: each participant starts a new row, and a row takes quote sets left to
    right as far as the screengrabs' width. `parts` is each quote's stickies (`quote_parts`); a
    quote without parts is one the board cannot write and is left out."""
    set_ids = set_ids if set_ids is not None else [0]
    stills: list[ScreenStill] = []
    bottom = FRAME_PAD
    for k, (name, title, (pw, ph)) in enumerate(versions):
        h = SHOT_W * ph / pw if pw else SHOT_W * 9 / 16
        stills.append(ScreenStill(name, title, FRAME_PAD + k * CASCADE, FRAME_PAD + k * CASCADE, SHOT_W, h))
        bottom = max(bottom, FRAME_PAD + k * CASCADE + h)
    row_w = SHOT_W + max(len(versions) - 1, 0) * CASCADE
    right = FRAME_PAD + row_w
    stickies: list[ScreenSticky] = []
    y = bottom
    for _, doms in groups:
        sets = [(d, parts[d]) for d in doms if parts.get(d)]
        if not sets:
            continue
        y += SECTION_GAP
        x, row_h = FRAME_PAD, 0.0
        for d, ps in sets:
            w, h = set_extent(ps)
            if x > FRAME_PAD and x + w > FRAME_PAD + row_w:  # the next row
                x, y, row_h = FRAME_PAD, y + row_h + GAP, 0.0
            set_id = None
            if len(ps) > 1:
                set_ids[0] += 1
                set_id = set_ids[0]
            for k, (top, p) in enumerate(zip(set_tops(ps), ps, strict=True)):
                stickies.append(ScreenSticky(d, x + k * SET_STAGGER, y + top, p.width, p.height,
                                             p.text, p.attributed, set_id))
            right = max(right, x + w)
            row_h = max(row_h, h)
            x += w + GAP
        y += row_h
    return right + FRAME_PAD, y + FRAME_PAD, stills[::-1], stickies


def lay_out_board(screens: Sequence[Mapping[str, Any]], still_px: Mapping[str, tuple[int, int]],
                  parts: Mapping[str, Sequence[QuotePart]]) -> list[ScreenFrame]:
    """Every screen as a frame, in one row left to right in the order given (journey order).

    `still_px` maps a version's still filename to its pixel size; a version without one is left out
    (its still could not be made), and a screen with none at all is left out."""
    frames: list[ScreenFrame] = []
    x = 0.0
    set_ids = [0]  # one count across the board, so every set's number is its own
    for sc in screens:
        versions = [(v["filename"], f"{v['code'].upper()} · {v.get('title') or sc['title']}", still_px[v["filename"]])
                    for v in sc["versions"] if v["filename"] in still_px]
        if not versions:
            continue
        w, h, stills, stickies = lay_out_screen(sc["groups"], versions, parts, set_ids)
        frames.append(ScreenFrame(sc["title"], x, 0.0, w, h, stills, stickies))
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
