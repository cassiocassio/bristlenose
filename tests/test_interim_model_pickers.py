"""Every interim model picker says so, and points at the plan.

``docs/design-pluggable-llm-routing.md`` §"Interim model pickers: fix, don't
grow" lists the sites that pick a model on their own until the per-stage
resolver exists, and holds them to small fixes. The comment at each site is how
someone editing it finds that rule; this keeps the doc's list and the code in
step, in both directions a list can rot: a site listed without the comment, and
a listed path that no longer exists.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "design-pluggable-llm-routing.md"
POINTER = "design-pluggable-llm-routing.md"


def _listed_sites() -> list[Path]:
    text = DOC.read_text(encoding="utf-8")
    start = text.index("### Interim model pickers: fix, don't grow")
    end = text.index("\n### ", start + 1)
    section = text[start:end]
    paths = re.findall(r"^\| `([^`]+\.(?:py|swift))`", section, flags=re.M)
    return [ROOT / p.replace("desktop/…/", "desktop/Bristlenose/Bristlenose/") for p in paths]


def test_the_section_lists_sites() -> None:
    # Guards the parse: an empty list would make the next test pass vacuously.
    assert len(_listed_sites()) >= 8


def test_every_listed_site_exists_and_points_at_the_plan() -> None:
    missing = [p for p in _listed_sites() if not p.exists()]
    assert not missing, f"listed in the doc but gone: {missing}"
    unmarked = [
        str(p.relative_to(ROOT)) for p in _listed_sites()
        if POINTER not in p.read_text(encoding="utf-8")
    ]
    assert not unmarked, f"interim model picker with no pointer to the plan: {unmarked}"
