"""Anti-drift gate — a screen-reader label may not be a hardcoded English string.

``aria-label`` is the one piece of user-facing text with no pixels.  A missing
translation on a *visible* string is caught by the eye the first time anyone
opens the app in their own language; a missing translation on an accessible
name is heard only by someone running VoiceOver in that language, which is
nobody on this team.  So the class rots silently and indefinitely.

That is not hypothetical.  ``islands/QuoteGroup.tsx`` shipped two of them —
``aria-label={`Edit ${itemType} title`}`` and its description sibling — in a
file with **zero** i18n call sites, and no gate in the repo could see it.  This
is failure class 2 of ``docs/i18n-defects.md``: ``scripts/check-locales.py``
diffs each locale *against* ``en``, so a surface never enrolled in English has
nothing to be missing from and is invisible **by construction**.  ``--strict``
does not close that hole; nothing does, because every other gate we own asks
"do the things I was told to enumerate agree?" rather than "is anything missing
that nobody enumerated?"

**The rule: an aria-label may not carry a human-readable string literal unless
it came from ``t()``.**  That derives the legitimate cases instead of
allow-listing them by hand — ``aria-label={book.title}``,
``aria-label={ariaLabel}`` and ``aria-label={iconOnly ? label : undefined}``
pass on their own merits, because they interpolate data or forward a prop and
name no English of their own.  A hand-written list of "these ones are fine"
would need editing every time a component gained a pass-through, and would
drift the way any list nothing recomputes drifts.

**Why the expression, not the line.**  The fix for QuoteGroup is a two-arm
ternary spread over four lines, so a line-oriented matcher reads
``aria-label={`` and finds no literal in it — green, having inspected nothing.
The scan brace-balances the whole attribute value.  Same lesson as the
proximity gate in root ``CLAUDE.md``: a gate whose verdict changes when you add
a newline is measuring the wrong thing.

**Why an interpolated noun is not a fix.**  ``t("quotes.edit", { itemType })``
would satisfy this gate and still be wrong: the noun lands nominative in a
frame the language may inflect.  Polish wants genitive *sekcji* against a
nominative *Sekcje*, Russian *раздела* against *Разделы*, Turkish the
possessive-accusative *başlığını*.  Hence four whole-sentence keys for the two
QuoteGroup labels rather than one parameterised one.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "frontend" / "src"

# Dev-only surfaces. English by design, not by omission: the responsive
# playground and the Jinja2-vs-React visual diff are contributor tools behind
# `serve --dev` / a separate entry point, and are never in a researcher's
# build. Same standing as CLI terminal chrome in docs/design-i18n.md
# §"Which surfaces are targets" — a property of the surface, not a stage.
_DEV_ONLY = frozenset({"components/PlaygroundFab.tsx", "pages/VisualDiff.tsx"})

# Shipping components that carry the defect today. Named so the debt is
# visible and can only shrink: a new one fails as an unexpected finding, and a
# fixed one fails until it is struck from this set. Ratchet semantics, per the
# gate policy in root CLAUDE.md — the number may not rise by accident.
_KNOWN_UNENROLLED = frozenset({
    "components/EditableText.tsx",
    "components/EyeToggle.tsx",
    "components/ModalNav.tsx",
    "components/TagRow.tsx",
})
# TagGroupCard struck 23 Sep 2026 (0.31.1): its eye toggle built
# `Show ${name}` / `Hide ${name}` in English while the identical control in
# TagSidebar had used t("tags.showFramework"/"hideFramework") since it shipped.
# Now t("tags.showGroup"/"hideGroup") — separate keys rather than the framework
# pair, because sharing one key across two surfaces is how a later reword in one
# silently changes the other.

# A literal carrying a letter — i.e. words, not "", "-" or a lone separator.
_WORDY_LITERAL = re.compile(r'"[^"\n]*[A-Za-z][^"\n]*"|`[^`]*[A-Za-z][^`]*`')
_CALLS_T = re.compile(r"\bt\(")


def _attribute_expressions(src: str) -> list[str]:
    """Every ``aria-label`` value in ``src``, brace-balanced, as written."""
    out: list[str] = []
    for m in re.finditer(r"aria-label=", src):
        i = m.end()
        if src[i] == '"':                       # aria-label="literal"
            out.append(src[i : src.index('"', i + 1) + 1])
            continue
        depth = 0                               # aria-label={ … }
        for j in range(i, len(src)):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    out.append(src[i : j + 1])
                    break
    return out


def _sources() -> list[Path]:
    return [p for p in sorted(_SRC.rglob("*.tsx")) if ".test." not in p.name]


def _offenders() -> dict[str, list[str]]:
    """Files holding an aria-label with English of its own, keyed by rel path."""
    found: dict[str, list[str]] = {}
    for path in _sources():
        rel = path.relative_to(_SRC).as_posix()
        if rel in _DEV_ONLY:
            continue
        for expr in _attribute_expressions(path.read_text(encoding="utf-8")):
            if _CALLS_T.search(expr):
                continue
            if _WORDY_LITERAL.search(expr):
                found.setdefault(rel, []).append(" ".join(expr.split())[:70])
    return found


def test_frontend_sources_are_discoverable() -> None:
    """The scan is worthless if it silently reads nothing."""
    assert _SRC.is_dir(), f"missing frontend source tree: {_SRC}"
    assert len(_sources()) > 20


def test_matcher_reads_the_whole_expression_not_the_line() -> None:
    """A multi-line ternary must be inspected, not skipped as an empty line.

    The QuoteGroup fix has exactly this shape; a line-oriented matcher would
    pass it without looking at either arm.
    """
    multi = 'x aria-label={\n  a === "s"\n    ? t("k.one")\n    : t("k.two")\n} y'
    assert _attribute_expressions(multi) == [
        '{\n  a === "s"\n    ? t("k.one")\n    : t("k.two")\n}'
    ]
    # …and the hardcoded shape this gate exists to catch is caught across lines.
    hard = "x aria-label={\n  a\n    ? `Show ${n}`\n    : `Hide ${n}`\n} y"
    (expr,) = _attribute_expressions(hard)
    assert not _CALLS_T.search(expr) and _WORDY_LITERAL.search(expr)


def test_pass_through_labels_are_not_reported() -> None:
    """Forwarding data or a prop names no English and must stay legal."""
    for benign in ("{book.title}", "{ariaLabel}", "{iconOnly ? label : undefined}"):
        assert not _WORDY_LITERAL.search(benign), benign


def test_quote_surfaces_carry_no_hardcoded_screen_reader_text() -> None:
    """The islands are the researcher's quote workspace — all enrolled."""
    islands = {k: v for k, v in _offenders().items() if k.startswith("islands/")}
    assert islands == {}, f"hardcoded aria-label in a quote surface: {islands}"


def test_known_unenrolled_set_has_not_grown() -> None:
    """A new hardcoded label anywhere in the SPA fails here."""
    new = set(_offenders()) - _KNOWN_UNENROLLED
    assert new == set(), (
        "new hardcoded aria-label(s) — translate via t(), or add to _DEV_ONLY "
        f"if the surface is a contributor tool: { {k: _offenders()[k] for k in new} }"
    )


def test_known_unenrolled_set_has_not_gone_stale() -> None:
    """A fixed file must leave the set, so the debt list cannot rot."""
    fixed = _KNOWN_UNENROLLED - set(_offenders())
    assert fixed == set(), (
        f"these no longer carry a hardcoded aria-label — strike them from "
        f"_KNOWN_UNENROLLED: {sorted(fixed)}"
    )
