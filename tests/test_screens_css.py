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


# The owner, 15 Oct 2026: focus and selection on the Screens lens look and work exactly as on the
# Quotes lens, so a change to the focus model reaches both with nothing re-implemented. The shared
# .bn-focused / .bn-selected (bristlenose/theme/atoms/interactive.css) are the only visuals; this
# file may add stacking order and nothing else on any rule that names a focus or selection state.
# Before this, an `.is-lifted` box-shadow overrode the shared dark-mode focus ring.
# The gate is about CARDS. The board's own controls (menu items, "On p2's screen", the version
# radios) still carry the house :focus-visible ring, as Discussion's do; a gate that caught them
# sent them back to the browser's default ring (15 Oct 2026).
CARD_STATES = re.compile(r"bn-focused|bn-selected|is-lifted|is-focused")
CARD = re.compile(r"screens-card|quote-card")
FOCUS = re.compile(r":focus|focus-within")
# opacity, filter and transform too: dimming the other cards with `opacity: .5` is the same
# recolour by another name, and would have passed a colour-only list (code review, 15 Oct 2026).
VISUAL = re.compile(r"^(color|background(-.*)?|box-shadow|border(-.*)?|outline(-.*)?|opacity|filter|transform)$")


def _card_focus_rule(sel: str) -> bool:
    return bool(CARD_STATES.search(sel) or (FOCUS.search(sel) and CARD.search(sel)))


def test_focus_and_selection_add_only_stacking_order() -> None:
    offenders = [f"{sel} {{ {p} }}" for sel, props in _rules() if _card_focus_rule(sel)
                 for p in props if VISUAL.match(p)]
    assert offenders == []


def test_the_focus_gate_reads_rules_it_could_refuse() -> None:
    # A gate that matched no card focus rule would pass by reading nothing.
    assert any(_card_focus_rule(sel) for sel, _ in _rules())


def test_the_info_line_never_wraps() -> None:
    """The Arrangement control appears on the first drag; a wrapping line pushed the whole board
    down 21px at 800px — the one moment nothing may move (owner, 15 Oct 2026)."""
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.S)
    m = re.search(r"(?m)^\.screens-sub\s*\{([^}]*)\}", text)
    assert m, "the .screens-sub rule must exist"
    assert re.search(r"flex-wrap:\s*nowrap", m.group(1))


def test_the_leader_halo_is_never_softened_by_opacity() -> None:
    """R3's halo is blurred, never faded: opacity lets the ink under it through beside the line
    (3.0:1 at 85%, 2.4:1 at 75%; experiments/screens-lens/leader-styles.md §7)."""
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.S)
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", text)
    casing = [(sel.strip(), body) for sel, body in rules if "lead-casing" in sel]
    assert casing, "no rule names lead-casing: the gate would pass on nothing"
    for sel, body in casing:
        assert not re.search(r"(^|[;\s])(stroke-|fill-)?opacity\s*:|filter\s*:\s*opacity", body), sel

