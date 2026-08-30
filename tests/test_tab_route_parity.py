"""Every native `Tab` must have a matching route in the SPA's navigation shim.

WHY THIS EXISTS
---------------
`Tab.swift`'s doc comment states the contract in words:

    Raw values match the keys expected by `window.switchToTab(tab)` in
    `frontend/src/shims/navigation.ts`.

Nothing enforced it, and the shim's lookup ends `?? "/report/"` — so an
unknown tab key does not fail, it **silently navigates to the Project tab**.

On 30 Aug 2026 `Tab.codebookV2` shipped in the sidebar rail and in the ⌘-number
shortcuts with no `codebookV2` entry in `TAB_ROUTES`. Clicking the lens and
pressing its shortcut both went to `/report/`, which — if you were already on
the Project tab — looked exactly like a dead control. Every Swift test passed
(the Swift side was correct), every vitest passed (the route existed in the
router), and the server served `/report/codebook-v2/` with a 200. The defect
lived entirely in the gap between the two files, which is the one place neither
suite looks.

This test reads both files as text. That is deliberate: the contract is a
cross-language one, and a fixture would be a third copy to drift.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_TAB_SWIFT = _ROOT / "desktop/Bristlenose/Bristlenose/Tab.swift"
_NAV_TS = _ROOT / "frontend/src/shims/navigation.ts"


def _swift_tab_routes() -> dict[str, str]:
    """Parse the `route` computed property's switch into {case: route}."""
    src = _TAB_SWIFT.read_text(encoding="utf-8")
    body = re.search(r"var route: String \{(.*?)\n    \}", src, re.S)
    assert body, "Tab.swift: could not find the `route` computed property"
    pairs = re.findall(r'case \.(\w+):\s*"([^"]+)"', body.group(1))
    assert pairs, "Tab.swift: `route` switch parsed to nothing — shape changed?"
    return dict(pairs)


def _swift_tab_cases() -> list[str]:
    """Every case of `enum Tab`, from its single declaration line."""
    src = _TAB_SWIFT.read_text(encoding="utf-8")
    decl = re.search(r"enum Tab: String[^{]*\{\s*\n\s*case ([^\n]+)", src)
    assert decl, "Tab.swift: could not find the `enum Tab` case declaration"
    return [c.strip() for c in decl.group(1).split(",")]


def _ts_tab_routes() -> dict[str, str]:
    """Parse `TAB_ROUTES` in navigation.ts into {key: route}."""
    src = _NAV_TS.read_text(encoding="utf-8")
    body = re.search(r"const TAB_ROUTES: Record<string, string> = \{(.*?)\n\};", src, re.S)
    assert body, "navigation.ts: could not find TAB_ROUTES"
    pairs = re.findall(r'(\w+):\s*"([^"]+)"', body.group(1))
    assert pairs, "navigation.ts: TAB_ROUTES parsed to nothing — shape changed?"
    return dict(pairs)


def test_every_tab_case_has_a_route_in_the_shim() -> None:
    """The bug this file exists for: a Tab the shim has never heard of."""
    cases = _swift_tab_cases()
    ts = _ts_tab_routes()
    missing = [c for c in cases if c not in ts]
    assert not missing, (
        f"Tab case(s) with no TAB_ROUTES entry: {missing}. "
        f"window.switchToTab falls back to '/report/', so these lenses "
        f"silently navigate to the Project tab instead of failing. "
        f"Add them to {_NAV_TS.relative_to(_ROOT)}."
    )


def test_swift_and_shim_agree_on_every_route() -> None:
    """Present in both, but pointing at different paths, is just as broken."""
    swift = _swift_tab_routes()
    ts = _ts_tab_routes()
    disagreements = {
        case: (route, ts[case])
        for case, route in swift.items()
        if case in ts and ts[case] != route
    }
    assert not disagreements, (
        "Tab.swift and navigation.ts disagree on {case: (swift, ts)}: "
        f"{disagreements}"
    )


def test_swift_route_switch_covers_every_tab_case() -> None:
    """A Tab with no `route` arm would not compile, but pin the parse anyway.

    If this fails and the others pass, the regexes have drifted from the
    files rather than the files from each other — fix the parse, not the code.
    """
    assert set(_swift_tab_cases()) == set(_swift_tab_routes())


@pytest.mark.parametrize("path", [_TAB_SWIFT, _NAV_TS])
def test_contract_files_exist(path: Path) -> None:
    """A rename must fail loudly here, not silently skip the whole gate."""
    assert path.is_file(), f"missing contract file: {path}"
