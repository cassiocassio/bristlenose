"""No component draws its own icon: every icon goes through components/Icon.tsx (Lucide).

The rule was written in July 2026 and broken in October, which is why it is a test:
docs/design-icon-system.md § Implementation. A chart or diagram is not an icon, so the
files that draw one are allowed exactly as many ``<svg`` as they draw, by name. A new
chart is a new row here with its reason; a new icon is a concept in Icon.tsx.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"

# file (relative to frontend/src) → (inline <svg> it may contain, what it draws)
CHARTS: dict[str, tuple[int, str]] = {
    "components/Metric.tsx": (1, "signal intensity dots"),
    "islands/SignalsPage.tsx": (1, "signal intensity dots"),
    "components/TranscriptionDiagnostics.tsx": (1, "diagnostic lanes: sound, pace, gaps"),
    "components/SessionTapestry.tsx": (1, "the session timeline"),
    "islands/screens/ScreensLens.tsx": (1, "leader lines from screens to quotes"),
    "islands/discussion/DiscussionLens.tsx": (1, "wires between the guide and the talk"),
}


def _svg_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in SRC.rglob("*.tsx"):
        if ".test." in f.name:
            continue
        # count drawn elements, not prose about them: strip comments first
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", f.read_text(), flags=re.S)
        n = len(re.findall(r"<svg\b", code))
        if n:
            counts[str(f.relative_to(SRC))] = n
    return counts


def test_no_component_draws_its_own_icon() -> None:
    over = {
        f: n for f, n in _svg_counts().items()
        if n > CHARTS.get(f, (0, ""))[0]
    }
    assert not over, (
        "inline <svg> outside the chart allowlist — use <Icon name=…> "
        f"(add a concept to components/Icon.tsx if it is missing): {over}"
    )


def test_the_chart_allowlist_is_not_stale() -> None:
    counts = _svg_counts()
    stale = {f: n for f, (n, _) in CHARTS.items() if counts.get(f, 0) < n}
    assert not stale, f"allowlisted charts no longer drawn — lower or remove the row: {stale}"


def test_lucide_is_reached_only_through_icon_tsx() -> None:
    """A direct import would skip the facade: no stem, no label rule, no concept name."""
    direct = sorted(
        str(f.relative_to(SRC)) for f in SRC.rglob("*.ts*")
        if f.name not in ("Icon.tsx",) and ".test." not in f.name
        and re.search(r"""from\s+["']lucide-react""", f.read_text())
    )
    assert not direct, f"import icons through components/Icon.tsx, not lucide-react: {direct}"
