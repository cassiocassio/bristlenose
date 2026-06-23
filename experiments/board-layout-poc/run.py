"""Run the trivial board layout against a project's intermediate JSON → SVG.

Usage:
    python run.py [INTERMEDIATE_DIR] [OUT_SVG]

Defaults to the committed smoke-test fixture so it runs with no arguments.
"""

from __future__ import annotations

import sys
from pathlib import Path

from layout import layout_board, load_columns
from render_svg import render_svg

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_INTERMEDIATE = (
    REPO / "tests/fixtures/smoke-test/input/bristlenose-output/.bristlenose/intermediate"
)
DEFAULT_OUT = HERE / "sample-board.svg"


def main() -> None:
    intermediate = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INTERMEDIATE
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT

    columns = load_columns(intermediate)
    n_quotes = sum(len(c.quotes) for c in columns)
    board = layout_board(columns, title=f"Research board — first draft ({n_quotes} quotes)")
    out.write_text(render_svg(board), encoding="utf-8")

    print(f"columns: {len(columns)}  ({', '.join(c.label for c in columns)})")
    print(f"quotes:  {n_quotes}")
    print(f"board:   {board.width:.0f} × {board.height:.0f} px")
    print(f"wrote:   {out}")


if __name__ == "__main__":
    main()
