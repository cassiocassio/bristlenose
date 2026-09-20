"""The fit-to-width floor in SidebarStore.ts is the CSS token it names.

`CONTENT_FLOOR_PX` and `MINIMAP_WIDTH_PX` restate `--bn-quote-max-width` and
`--bn-minimap-width` in pixels because a store cannot read a stylesheet. A
restated number drifts, and a floor that drifts protects a card of a different
size — so this reads both files and diffs them. Pytest-side because the
TypeScript suite has no node types for a file read and Vite refuses a raw import
from outside frontend/ (see safeUrl.test.ts for the same constraint).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "bristlenose" / "theme" / "tokens.css"
STORE = ROOT / "frontend" / "src" / "contexts" / "SidebarStore.ts"

REM_PX = 16


def _token_px(name: str) -> float:
    m = re.search(rf"{re.escape(name)}:\s*([\d.]+)rem", TOKENS.read_text())
    assert m, f"{name} not found in {TOKENS}"
    return float(m.group(1)) * REM_PX


def _store_const(name: str) -> float:
    m = re.search(rf"export const {name} = (\d+(?:\.\d+)?);", STORE.read_text())
    assert m, f"{name} not found in {STORE}"
    return float(m.group(1))


@pytest.mark.parametrize(
    ("constant", "token"),
    [
        ("CONTENT_FLOOR_PX", "--bn-quote-max-width"),
        ("MINIMAP_WIDTH_PX", "--bn-minimap-width"),
    ],
)
def test_store_floor_matches_css_token(constant: str, token: str) -> None:
    assert _store_const(constant) == _token_px(token)
