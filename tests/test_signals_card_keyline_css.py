"""A selected Signals card's keyline goes all the way round, whatever its place in the run.

Cards in a run share one hairline (`.signal-card:not(:first-child)` has no top border), so
a selected later card had no top keyline of its own. The selected card now draws its top
edge over the shared hairline, pulled up by one border so the layout does not move
(owner, 31 Oct 2026; measured in Chromium and WebKit, docs/design-signals-lens-readiness.md).
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "bristlenose/theme/organisms/signals.css").read_text(
    encoding="utf-8"
)


def _rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_a_selected_later_card_draws_its_own_top_keyline() -> None:
    body = _rule(".signal-card.bn-selected:not(:first-child)")
    assert re.search(r"border-top:\s*1px solid var\(--signal-card-selected-border", body)


def test_the_top_keyline_does_not_move_the_layout() -> None:
    body = _rule(".signal-card.bn-selected:not(:first-child)")
    # one border drawn, one border pulled back: net height unchanged
    assert re.search(r"margin-top:\s*-1px", body)
    assert re.search(r"z-index:\s*1", body)


def test_an_unselected_later_card_still_shares_the_hairline() -> None:
    assert re.search(r"border-top:\s*none", _rule(".signal-card:not(:first-child)"))
