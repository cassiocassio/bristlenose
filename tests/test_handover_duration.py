"""The hand-over dim's duration is one number, written twice.

`useLensRead` holds `.bn-handover` on a lens for `HANDOVER_MS`, and
`organisms/toolbar.css` plays `bn-handover` for its own duration. If the two
drift, the class comes off mid-animation (cutting the fade short) or lingers
after it. A hook cannot read a stylesheet, so this reads both files. Pytest-side
because the TypeScript suite has no node types for a file read and Vite refuses
a raw import from outside frontend/ (see tests/test_sidebar_floor_tokens.py).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "frontend" / "src" / "hooks" / "useLensRead.ts"
CSS = ROOT / "bristlenose" / "theme" / "organisms" / "toolbar.css"


def test_handover_ms_matches_the_css_animation() -> None:
    hook = re.search(r"export const HANDOVER_MS = (\d+);", HOOK.read_text(encoding="utf-8"))
    assert hook, f"HANDOVER_MS not found in {HOOK}"
    css = re.search(
        r"\.bn-handover\s*\{[^}]*animation:\s*bn-handover\s+(\d+)ms",
        CSS.read_text(encoding="utf-8"),
    )
    assert css, f".bn-handover's animation not found in {CSS}"
    assert int(hook.group(1)) == int(css.group(1))
