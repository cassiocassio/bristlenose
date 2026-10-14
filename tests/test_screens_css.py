"""The Screens lens's cards are what they are: selecting one never changes its size or the layout.

The owner, 14 Oct 2026: a card on the board keeps one size; selecting it (a press, or keyboard focus)
only raises it and shows the shipped focus treatment, and hovering changes nothing about its size.
The lens's first build clamped every quote to seven lines and unclamped the selected one, so a
selected card grew, its column re-placed around it, and under hover a different card then sat under
the pointer — flicker.

This reads the stylesheet as text because jsdom applies no CSS and vitest serves stylesheets empty,
even with ``?raw`` (measured while writing this), so no frontend test can see a rule. Every rule
whose selector names a selected, focused, hovered or edited state may set only properties that
cannot move anything; and no quote is clamped to a number of lines.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).parents[1] / "frontend/src/islands/screens/screens.css"

STATES = re.compile(r"is-lifted|bn-focused|focus-within|:hover|:focus|\.editing|\.focus\b")
SAFE = {
    "z-index", "box-shadow", "color", "background", "background-color", "opacity", "outline",
    "outline-offset", "border-color", "text-decoration", "cursor", "transition", "fill", "stroke",
    # Takes the same space visible or not: the arrangement control swaps its words this way.
    "visibility",
}


def _rules() -> list[tuple[str, list[str]]]:
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.S)
    out = []
    # Innermost blocks only: an @container or @media wrapper's braces hold rules, not declarations.
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        props = [d.split(":")[0].strip().lower() for d in m.group(2).split(";") if d.strip()]
        out.append((m.group(1).strip(), props))
    return out


def test_the_stylesheet_is_read() -> None:
    # A parser that found nothing would pass both tests below.
    rules = _rules()
    assert len(rules) > 40
    assert any(STATES.search(sel) for sel, _ in rules)


def test_a_selected_focused_or_hovered_card_never_changes_size_or_layout() -> None:
    offenders = [f"{sel} {{ {p} }}" for sel, props in _rules() if STATES.search(sel)
                 for p in props if p not in SAFE]
    assert offenders == []


def test_no_quote_is_clamped_to_a_number_of_lines() -> None:
    clamped = [sel for sel, props in _rules() if "quote" in sel and any("line-clamp" in p for p in props)]
    assert clamped == []
