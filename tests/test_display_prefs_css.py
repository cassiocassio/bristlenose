"""The Display preferences' stylesheet (docs/design-display-preferences.md).

Three things would fail silently: the file left out of the bundle, the file
registered before the grid rule it has to beat, and a rule that reaches past
the quote content (the whole point is that the chrome never changes size).
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.stages.s12_render.theme_assets import _THEME_FILES

THEME = Path(__file__).resolve().parent.parent / "bristlenose" / "theme"
CSS = (THEME / "organisms" / "display-prefs.css").read_text(encoding="utf-8")


def _selectors(css: str) -> list[str]:
    """Each rule's selectors, split on top-level commas (not those inside :is(...))."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    for block in re.finditer(r"([^{}]+)\{", css):
        depth, cur = 0, ""
        for ch in block.group(1):
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                out.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            out.append(cur.strip())
    return out


def test_registered_after_the_grid_rule_it_overrides() -> None:
    files = list(_THEME_FILES)
    assert "organisms/display-prefs.css" in files
    assert files.index("organisms/display-prefs.css") > files.index("organisms/responsive-grid.css")


def test_single_column_reuses_the_existing_reading_width_not_a_second_one() -> None:
    """Discussion already caps at --bn-max-width; Single column must use the same token."""
    assert "max-width: var(--bn-max-width)" in CSS
    assert "--bn-quote-single-width" not in (THEME / "tokens.css").read_text(encoding="utf-8")
    assert "--bn-quote-single-width" not in CSS


def test_every_rule_is_scoped_to_the_quote_content() -> None:
    allowed = (
        'html[data-bn-layout="single"] .quote-group',
        'html[data-bn-layout="single"] section:has(> .quote-group)',
        'html[data-bn-density="custom"] .quote-group',
        ".quote-text .bn-block",
        ".display-menu",
    )
    # exact, or the allowed selector followed by a space (a descendant) or a colon (a pseudo-class):
    # `.quote-groupx` must not pass
    stray = [s for s in _selectors(CSS) if not any(s == a or s.startswith((a + " ", a + ":")) for a in allowed)]
    assert stray == []


def test_single_column_sets_the_track_and_never_the_display() -> None:
    rule = re.search(r'html\[data-bn-layout="single"\] \.quote-group\s*\{([^}]*)\}', CSS)
    assert rule is not None
    assert "grid-template-columns" in rule.group(1)
    # Switching display between grid-lanes and grid left the cards' contents unpainted.
    assert "display" not in rule.group(1)


def test_density_rules_apply_only_off_normal_and_read_the_signed_variable() -> None:
    """Normal is today's screen, so no density rule may match it."""
    selectors = [x for x in _selectors(CSS) if "data-bn-density" in x]
    assert selectors and all('data-bn-density="custom"' in x for x in selectors)
    assert "--bn-density-s" in CSS
