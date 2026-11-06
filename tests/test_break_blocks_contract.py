"""Three surfaces draw a long quote as `.bn-block` spans inside a `.quote-text`: QuoteCard,
the Uncategorised floor and Signals evidence. One rule in `display-prefs.css` styles them.
Each surface has its own markup, so nothing else ties them together: delete the rule or
rename the class on one surface and every component test still passes, while the quote
loses its paragraph gaps. This pins the shared names (a vitest cannot read the theme
directory: Vite refuses files outside the frontend root)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "bristlenose/theme/organisms/display-prefs.css"
SURFACES = [
    "frontend/src/islands/QuoteCard.tsx",
    "frontend/src/islands/UncategorisedFloor.tsx",
    "frontend/src/islands/SignalsPage.tsx",
]


def test_the_theme_styles_a_block_inside_a_quotes_text() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert re.search(r"\.quote-text\s+\.bn-block\s*\{", css)
    assert re.search(r"\.quote-text\s+\.bn-block:last-child\s*\{", css)


@pytest.mark.parametrize("surface", SURFACES)
def test_each_surface_draws_blocks_with_the_classes_the_theme_styles(surface: str) -> None:
    src = (ROOT / surface).read_text(encoding="utf-8")
    assert 'className="bn-block"' in src
    assert 'className="quote-text"' in src
