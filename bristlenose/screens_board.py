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

from bristlenose.board_layout import RECT_ASPECT

#: The still's width on the board. Miro keeps an image's aspect from its width.
SHOT_W = 1200.0
#: Stickies per row under the still, and their size: four of the house rectangle span the still.
PER_ROW = 4
GAP = 24.0
STICKY_W = (SHOT_W - (PER_ROW - 1) * GAP) / PER_ROW
STICKY_H = STICKY_W * RECT_ASPECT
#: Between the still and the first row, and between one participant's rows and the next's.
SECTION_GAP = 64.0
#: Inside a frame, round its contents; between frames, room for the team's own stickies.
FRAME_PAD = 80.0
FRAME_GAP = 400.0


@dataclass
class ScreenSticky:
    dom_id: str
    #: Top-left, in the frame's coordinates.
    x: float
    y: float


@dataclass
class ScreenFrame:
    title: str
    filename: str
    #: Top-left on the board, and size.
    x: float
    y: float
    width: float
    height: float
    #: The still's top-left in the frame, and its size.
    shot: tuple[float, float, float, float]
    stickies: list[ScreenSticky] = field(default_factory=list)


def lay_out_screen(groups: Sequence[tuple[str, Sequence[str]]], still_px: tuple[int, int],
                   known: set[str] | None = None) -> tuple[float, float, tuple[float, float, float, float],
                                                           list[ScreenSticky]]:
    """One screen's frame contents: (width, height, still rect, stickies), in frame coordinates.

    `groups` is (participant code, quote ids) in the order to stack them; each participant starts
    a new row. `known` limits the stickies to quotes the board can write."""
    pw, ph = still_px
    sh = SHOT_W * ph / pw if pw else SHOT_W * 9 / 16
    stickies: list[ScreenSticky] = []
    y = FRAME_PAD + sh
    for _, doms in groups:
        doms = [d for d in doms if known is None or d in known]
        if not doms:
            continue
        y += SECTION_GAP
        for i, d in enumerate(doms):
            row, col = divmod(i, PER_ROW)
            stickies.append(ScreenSticky(d, FRAME_PAD + col * (STICKY_W + GAP), y + row * (STICKY_H + GAP)))
        rows = (len(doms) + PER_ROW - 1) // PER_ROW
        y += rows * STICKY_H + (rows - 1) * GAP
    return SHOT_W + 2 * FRAME_PAD, y + FRAME_PAD, (FRAME_PAD, FRAME_PAD, SHOT_W, sh), stickies


def lay_out_board(screens: Sequence[Mapping[str, Any]], still_px: Mapping[str, tuple[int, int]],
                  known: set[str] | None = None) -> list[ScreenFrame]:
    """Every screen as a frame, in one row left to right in the order given (journey order).

    `still_px` maps a screen's still filename to its pixel size; a screen without one is left
    out (its still could not be made)."""
    frames: list[ScreenFrame] = []
    x = 0.0
    for sc in screens:
        px = still_px.get(sc["filename"])
        if px is None:
            continue
        w, h, rect, stickies = lay_out_screen(sc["groups"], px, known)
        frames.append(ScreenFrame(sc["title"], sc["filename"], x, 0.0, w, h, rect, stickies))
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
