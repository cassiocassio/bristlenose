"""The Signals card stack is held to the shared reading width (3 Nov 2026).

One reading width in the product, not a private one per lens: Discussion and
Quotes' Single column already use --bn-max-width. A cap that quietly changed
value, or leaked into the sealed static report, would drift the lenses apart.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "bristlenose" / "theme" / "organisms" / "signals.css").read_text(
    encoding="utf-8"
)


def test_the_card_stack_is_held_to_the_shared_reading_width() -> None:
    rule = re.search(r"\.signals-center \.signal-cards\s*\{([^}]*)\}", CSS)
    assert rule is not None
    assert "max-width: var(--bn-max-width)" in rule.group(1)


def test_the_cap_is_scoped_to_the_spa_so_the_static_report_keeps_its_width() -> None:
    bare = re.search(r"(?m)^\.signal-cards\s*\{([^}]*)\}", CSS)
    assert bare is not None
    assert "max-width" not in bare.group(1)
