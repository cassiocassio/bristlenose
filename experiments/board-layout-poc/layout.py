"""Trivial v0 layout engine for the research-board POC.

Two named frames: a "Sections" frame (left) holding one column per screen
cluster, and a "Themes" frame (right) holding one column per theme group — the
same left-to-right org as the quotes page. (Miro frames don't nest, so the
per-column labels are text items *inside* the big frame, not sub-frames.) Within
a column, yellow quote stickies stack in session-then-time order. Uniform grid,
fixed sizes, no overlap. Deliberately dumb — the point is to see whether even
the dumbest arrangement is useful.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from board_model import Board, Frame, Sticky, TextItem

# --- layout constants (board px) -------------------------------------------
STICKY_W = 240.0
QUOTE_H = 200.0
HEADER_H = 76.0  # pale-pink column-title sticky
GAP_X = 36.0  # between columns inside a frame
GAP_Y = 24.0  # between stickies in a column
FRAME_PAD = 28.0  # inner padding of a big frame
FRAME_GAP = 72.0  # between the Sections frame and the Themes frame
MARGIN = 64.0
TITLE_Y = 46.0  # board-title baseline
FRAMES_Y = 120.0  # top edge of the big frames

# --- colours ----------------------------------------------------------------
QUOTE_FILL = "#FFF9B1"  # sticky yellow
HEADER_FILL = "#FADADD"  # pale pink column-title sticky
SECTIONS_FILL = "#ECEFF5"  # pale blue-grey container
THEMES_FILL = "#F2ECF6"  # pale violet container


@dataclass
class Column:
    label: str
    kind: str  # "section" | "theme"
    quotes: list[dict]


def _session_num(session_id: str) -> int:
    m = re.search(r"(\d+)", session_id or "")
    return int(m.group(1)) if m else 0


def _quote_sort_key(q: dict) -> tuple[int, float]:
    return (_session_num(q.get("session_id", "")), float(q.get("start_timecode", 0.0)))


def _compose_quote_text(q: dict) -> str:
    """Quote body only. Attribution is carried on the Sticky and rendered after
    the quote as muted/italic supporting text — the meaning leads."""
    return f"“{str(q.get('text', '')).strip()}”"


def load_columns(intermediate_dir: Path) -> list[Column]:
    """Read screen_clusters.json (sections) + theme_groups.json (themes)."""
    columns: list[Column] = []

    sc_path = intermediate_dir / "screen_clusters.json"
    if sc_path.exists():
        clusters = json.loads(sc_path.read_text(encoding="utf-8"))
        clusters.sort(key=lambda c: c.get("display_order", 0))
        for c in clusters:
            columns.append(Column(c.get("screen_label", "Section"), "section",
                                  list(c.get("quotes", []))))

    tg_path = intermediate_dir / "theme_groups.json"
    if tg_path.exists():
        themes = json.loads(tg_path.read_text(encoding="utf-8"))
        for t in themes:
            columns.append(Column(t.get("theme_label", "Theme"), "theme",
                                  list(t.get("quotes", []))))

    return columns


def _build_frame(
    columns: list[Column], kind: str, title: str, left_x: float
) -> tuple[Frame, list[Sticky], list[TextItem]]:
    """Lay out one big frame full of columns, returning the frame + its contents."""
    n = len(columns)
    max_q = max((len(c.quotes) for c in columns), default=0)
    quotes_h = max_q * (QUOTE_H + GAP_Y) - GAP_Y if max_q else 0
    inner_h = HEADER_H + (GAP_Y + quotes_h if max_q else 0)
    frame_w = FRAME_PAD * 2 + n * STICKY_W + max(0, n - 1) * GAP_X
    frame_h = FRAME_PAD * 2 + inner_h
    fill = SECTIONS_FILL if kind == "section" else THEMES_FILL

    frame = Frame(title=title, x=left_x, y=FRAMES_Y, width=frame_w, height=frame_h,
                  fill=fill, kind=kind)
    stickies: list[Sticky] = []
    titles: list[TextItem] = []

    for i, col in enumerate(columns):
        cx = left_x + FRAME_PAD + i * (STICKY_W + GAP_X)
        # pale-pink column-title sticky — the natural Miro affordance for a header
        stickies.append(Sticky(
            kind="header", x=cx, y=FRAMES_Y + FRAME_PAD, width=STICKY_W, height=HEADER_H,
            fill=HEADER_FILL, text=f"{col.label}\n{len(col.quotes)} quote(s)",
        ))
        sy = FRAMES_Y + FRAME_PAD + HEADER_H + GAP_Y
        for q in sorted(col.quotes, key=_quote_sort_key):
            stickies.append(Sticky(
                x=cx, y=sy, width=STICKY_W, height=QUOTE_H, fill=QUOTE_FILL,
                text=_compose_quote_text(q), session_id=q.get("session_id", ""),
                timecode=float(q.get("start_timecode", 0.0)),
                participant_id=q.get("participant_id", ""),
            ))
            sy += QUOTE_H + GAP_Y

    return frame, stickies, titles


def layout_board(columns: list[Column], title: str) -> Board:
    sections = [c for c in columns if c.kind == "section"]
    themes = [c for c in columns if c.kind == "theme"]

    board = Board(title=title)
    board.texts.append(TextItem(title, MARGIN, TITLE_Y, 22.0, "#1A1A1A", "700"))

    x = MARGIN
    if sections:
        frame, stk, ttl = _build_frame(sections, "section", "Sections", x)
        board.frames.append(frame)
        board.stickies.extend(stk)
        board.texts.extend(ttl)
        x = frame.x + frame.width + FRAME_GAP
    if themes:
        frame, stk, ttl = _build_frame(themes, "theme", "Themes", x)
        board.frames.append(frame)
        board.stickies.extend(stk)
        board.texts.extend(ttl)

    right = max((f.x + f.width for f in board.frames), default=MARGIN)
    bottom = max((f.y + f.height for f in board.frames), default=FRAMES_Y)
    board.width = right + MARGIN
    board.height = bottom + MARGIN
    return board
