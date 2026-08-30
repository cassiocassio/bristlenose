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


# ── Brace balance ──────────────────────────────────────────────────────────


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_every_theme_stylesheet_has_balanced_braces() -> None:
    """An unbalanced brace silently discards every rule after it.

    CSS has no error channel. One extra `}` closes a block early, the parser
    resynchronises, and every subsequent rule in that file is dropped — no
    warning in the build, no console error, nothing in the network tab. The
    page just renders as though those rules were never written.

    Found on 30 Aug 2026: a block replacement in `codebook-v2.css` left the old
    rule's closing brace behind, and everything below it stopped applying. The
    visible symptom was a page whose two-column head had become one column and
    a 240px gutter rendering 892px wide — which reads as a layout bug in the
    component, not as a stylesheet that stopped being parsed two hundred lines
    earlier. `getComputedStyle` said `display: block` while the file plainly
    said `flex`, and the tell was that NO rule matched the selector at all.

    Counted after stripping comments, since prose legitimately contains braces.
    """
    offenders: dict[str, tuple[int, int]] = {}
    for path in sorted(_THEME.rglob("*.css")):
        css = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        opened, closed = css.count("{"), css.count("}")
        if opened != closed:
            offenders[str(path.relative_to(_THEME))] = (opened, closed)

    assert not offenders, (
        "unbalanced braces — every rule after the imbalance is silently "
        "discarded by the CSS parser:\n"
        + "\n".join(f"  {f}: {o} open, {c} close" for f, (o, c) in offenders.items())
    )


def test_no_stylesheet_closes_more_than_it_opens_partway() -> None:
    """Balanced overall is not enough — where it goes negative is the damage.

    A file can be balanced and still broken: an extra `}` early and a missing
    one late cancel out in the totals while the middle of the file is orphaned.
    Track the running depth and fail on the first line that closes a block
    nothing opened.
    """
    for path in sorted(_THEME.rglob("*.css")):
        depth = 0
        for lineno, line in enumerate(
            _strip_comments(path.read_text(encoding="utf-8", errors="replace")).splitlines(),
            start=1,
        ):
            depth += line.count("{") - line.count("}")
            assert depth >= 0, (
                f"{path.relative_to(_THEME)}:{lineno} closes a block nothing "
                f"opened — every rule below this line is discarded"
            )
