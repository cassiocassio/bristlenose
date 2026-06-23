"""Trivial v0 layout engine for the research-board POC.

One column per section (screen cluster), then one column per theme (theme
group), left to right — the same org as the quotes page. Each column is a
pale-pink header sticky on top, with yellow quote stickies stacked below it in
session-then-time order. Uniform grid, fixed sizes, no overlap. Deliberately
dumb: the point is to eyeball whether even the dumbest arrangement is useful.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from board_model import Board, Sticky

# --- layout constants (board px) -------------------------------------------
STICKY_W = 240.0
HEADER_H = 88.0
QUOTE_H = 200.0
GAP_X = 48.0  # between columns
GAP_Y = 28.0  # between stickies in a column
MARGIN = 64.0  # board edge padding

# --- colours ----------------------------------------------------------------
HEADER_FILL = "#FADADD"  # pale pink
QUOTE_FILL = "#FFF9B1"  # sticky yellow (Miro's default yellow)


@dataclass
class Column:
    """A section or theme, with its quotes (raw dicts from intermediate JSON)."""

    label: str
    kind: str  # "section" | "theme"
    quotes: list[dict]


def _session_num(session_id: str) -> int:
    """Extract the trailing integer from 's1', 's12' for natural ordering."""
    m = re.search(r"(\d+)", session_id or "")
    return int(m.group(1)) if m else 0


def _quote_sort_key(q: dict) -> tuple[int, float]:
    return (_session_num(q.get("session_id", "")), float(q.get("start_timecode", 0.0)))


def _fmt_timecode(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _compose_quote_text(q: dict) -> str:
    """The quote body only. Attribution (participant + timecode) is carried as
    metadata on the Sticky and rendered after the quote as muted supporting text —
    the meaning leads, the who/when trails."""
    body = str(q.get("text", "")).strip()
    return f"“{body}”"


def load_columns(intermediate_dir: Path) -> list[Column]:
    """Read screen_clusters.json + theme_groups.json into ordered columns.

    Sections first (by display_order), then themes (file order) — left to right.
    """
    columns: list[Column] = []

    sc_path = intermediate_dir / "screen_clusters.json"
    if sc_path.exists():
        clusters = json.loads(sc_path.read_text(encoding="utf-8"))
        clusters.sort(key=lambda c: c.get("display_order", 0))
        for c in clusters:
            columns.append(
                Column(label=c.get("screen_label", "Section"), kind="section",
                       quotes=list(c.get("quotes", [])))
            )

    tg_path = intermediate_dir / "theme_groups.json"
    if tg_path.exists():
        themes = json.loads(tg_path.read_text(encoding="utf-8"))
        for t in themes:
            columns.append(
                Column(label=t.get("theme_label", "Theme"), kind="theme",
                       quotes=list(t.get("quotes", [])))
            )

    return columns


def layout_board(columns: list[Column], title: str) -> Board:
    """Place stickies: header on top, quotes below in session→time order."""
    board = Board(title=title)
    tallest = 0.0

    for col_idx, col in enumerate(columns):
        x = MARGIN + col_idx * (STICKY_W + GAP_X)
        y = MARGIN

        header_label = f"{col.label}\n{len(col.quotes)} quote(s) · {col.kind}"
        board.stickies.append(
            Sticky(kind="header", x=x, y=y, width=STICKY_W, height=HEADER_H,
                   fill=HEADER_FILL, text=header_label)
        )
        y += HEADER_H + GAP_Y

        for q in sorted(col.quotes, key=_quote_sort_key):
            board.stickies.append(
                Sticky(
                    kind="quote", x=x, y=y, width=STICKY_W, height=QUOTE_H,
                    fill=QUOTE_FILL, text=_compose_quote_text(q),
                    session_id=q.get("session_id", ""),
                    timecode=float(q.get("start_timecode", 0.0)),
                    participant_id=q.get("participant_id", ""),
                )
            )
            y += QUOTE_H + GAP_Y

        tallest = max(tallest, y - GAP_Y + MARGIN)

    n = len(columns)
    board.width = MARGIN * 2 + n * STICKY_W + max(0, n - 1) * GAP_X if n else MARGIN * 2
    board.height = tallest if tallest else MARGIN * 2
    return board
