"""Every ``var(--bn-*)`` used without a fallback must resolve to a defined token.

An undefined custom property is invalid at computed-value time: an inherited
property like ``color`` silently falls back to the inherited value, so the rule
does nothing and nothing errors.  That is how ``--bn-colour-success`` and
``--bn-colour-danger`` shipped -- used sixteen times across the theme, defined
nowhere, leaving the tick and cross on the AutoCode toast and the activity chip
with no colour at all (found 30 Aug 2026, fixed by adding ``--bn-colour-positive``
and ``--bn-colour-warning`` to the palette contract).

Uses *with* a fallback are allowed: they degrade to a real value.  They are still
worth avoiding -- eleven of the sixteen pinned a light-mode hex, so they were
wrong in dark mode -- but only the no-fallback form is a silent failure.
"""

from __future__ import annotations

import re
from pathlib import Path

_THEME = Path(__file__).resolve().parent.parent / "bristlenose" / "theme"
_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"

_DEFINED_RE = re.compile(r"(--bn-[\w-]+)\s*:")
# var(--bn-x) with no comma before the closing paren == no fallback.
_USED_NO_FALLBACK_RE = re.compile(r"var\(\s*(--bn-[\w-]+)\s*\)")

# Set at runtime rather than declared in CSS.
_RUNTIME_DEFINED = {
    "--bn-sidebar-width",  # written by the drag-resize handler
}


def _css_files() -> list[Path]:
    return sorted(
        [p for p in _THEME.rglob("*.css")]
        + [p for p in _FRONTEND.rglob("*.css")]
    )


def test_every_no_fallback_token_use_resolves() -> None:
    defined: set[str] = set(_RUNTIME_DEFINED)
    used: dict[str, list[str]] = {}

    for path in _css_files():
        text = path.read_text(encoding="utf-8")
        defined.update(_DEFINED_RE.findall(text))
        for token in _USED_NO_FALLBACK_RE.findall(text):
            used.setdefault(token, []).append(path.name)

    missing = {t: sorted(set(w)) for t, w in used.items() if t not in defined}
    assert not missing, (
        "CSS custom properties used with no fallback and defined nowhere -- "
        "these render as if the declaration were absent:\n"
        + "\n".join(f"  {t}  <- {', '.join(w)}" for t, w in sorted(missing.items()))
    )
