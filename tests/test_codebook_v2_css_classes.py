"""Every CSS class the v2 lens names must exist in the theme.

WHY THIS EXISTS
---------------
`CodebookV2UninstallSheet` rendered its backdrop as `.bn-modal-overlay`. The
house pair is `.bn-overlay` + `.bn-modal` (`theme/atoms/modal.css`), and
`.bn-modal-overlay` is defined nowhere.

A class that does not exist does not error. The inner card still looked like a
card, because `.bn-modal` is real — only the backdrop was invented, so it had no
`position: fixed`, no z-index, no dimming and no centring. The result was a
**destructive confirmation rendering inline at the bottom of the page**: the
researcher clicks Uninstall and the viewport shows nothing, because the sheet is
1,500px further down in the document flow. Found by opening it and getting a
blank screen; no test, no console error, no build warning.

This is the sibling of `tests/test_export_css_selectors.py`, which exists
because the same silence bites the export gate from the other direction.

WHAT IT CANNOT CHECK
--------------------
That a class which *exists* is the *right* one. `.bn-modal` and
`.codebook-modal` are both real; picking the wrong one still compiles and still
passes here. This gate catches names that resolve to nothing at all, which is
the failure mode with no other signal.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_THEME = _ROOT / "bristlenose/theme"
_SRC = _ROOT / "frontend/src"


def _theme_css() -> str:
    return "\n".join(
        f.read_text(encoding="utf-8", errors="replace") for f in _THEME.rglob("*.css")
    )


def _classes_used_by_v2() -> set[str]:
    """Every class name the v2 lens's own components put on an element."""
    used: set[str] = set()
    for f in _SRC.rglob("CodebookV2*.tsx"):
        if ".test." in f.name:
            continue
        text = f.read_text(encoding="utf-8")
        # Template literals: drop `${...}` and keep the literal segments, so
        # `pg-author${x ? " prov-system" : ""}` yields both real names.
        for m in re.findall(r"className=\{`([^`]*)`", text):
            used.update(c for c in re.sub(r"\$\{[^}]*\}", " ", m).split() if c)
        for m in re.findall(r'className="([^"]*)"', text):
            used.update(c for c in m.split() if c)
        # Ternaries: className={cond ? "a" : "b"}
        for block in re.findall(r"className=\{[^}]*\}", text):
            for quoted in re.findall(r'"([a-z][\w -]*)"', block):
                used.update(quoted.split())
    return used


def test_every_v2_class_resolves_to_real_css() -> None:
    css = _theme_css()
    used = _classes_used_by_v2()
    assert used, "parsed no classes from the v2 lens — the regexes have drifted"

    # Whole-token match. `-` is a class-name character, so `\b` is not enough:
    # a substring search finds `.bn-modal` inside `.bn-modal-overlay` and
    # reports the invented name as present — passing the exact bug this file
    # exists to catch. Same trap `test_export_css_selectors.py` documents.
    missing = sorted(
        c for c in used
        if not re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", css)
    )
    assert not missing, (
        f"v2 names {len(missing)} CSS class(es) that exist nowhere in "
        f"bristlenose/theme: {missing}. A class that does not exist does not "
        f"error — it silently contributes no styling, which is how a modal "
        f"backdrop lost `position: fixed` and a destructive sheet rendered "
        f"inline at the bottom of the page."
    )


def test_the_uninstall_sheet_uses_the_house_overlay() -> None:
    """The specific regression, named.

    `.bn-overlay` is `opacity: 0; visibility: hidden` at rest and is revealed
    by `.visible`. This sheet mounts conditionally rather than toggling, so it
    has to arrive already visible; once it rendered inline with an invented
    backdrop class, and once it would have been invisible without `.visible`.
    Since 24 Oct 2026 it draws through the shared Dialog, opened, and Dialog
    adds `visible` while open; `Dialog.test.tsx` pins that half.
    """
    sheet = (_SRC / "components/CodebookV2UninstallSheet.tsx").read_text(encoding="utf-8")
    assert re.search(r"<Dialog\s+open\b", sheet), (
        "the uninstall sheet must draw through Dialog, opened: it mounts "
        "conditionally instead of toggling `open`"
    )
    dialog = (_SRC / "components/Dialog.tsx").read_text(encoding="utf-8")
    assert 'open ? "visible" : ""' in dialog, "Dialog must add `visible` while open"
    # On the JSX, not anywhere in the file: a comment may name the retired
    # class to explain it, and a bare substring search would fail on that.
    assert 'className="bn-modal-overlay"' not in sheet, "that class is defined nowhere"
