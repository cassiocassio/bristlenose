"""Anti-drift gate — every class named in ``export.css`` must still be rendered.

``bristlenose/theme/templates/export.css`` is the read-only gate for the
self-contained HTML export: every rule is ``.bn-export-mode <selector> { … }``,
hiding the mutation affordances so a shared report reads as a finished document
(``docs/design-export-html.md``).  The rules are pure CSS, so a class rename in
``frontend/src`` defeats one **silently** — no error, no failing test, just a
control that reappears in every exported report from then on.

That is not hypothetical.  On 15 Aug 2026 five selectors were found stale at
once; ``.badge-accept`` / ``.badge-deny`` had been renamed to
``.badge-action-accept`` / ``.badge-action-deny`` by the badge-action-pill
redesign, and the autocode accept/deny control had been visible in exports for
an unknown period.  This is the mechanical stop, in the spirit of
``test_serve_export_coverage.py``: a selector that matches nothing is either a
dead rule or a broken gate, and both are worth failing on.

**Why ``frontend/src`` is the whole corpus.** The ``bn-export-mode`` body class
is written in exactly one place — ``routes/export.py``'s ``_build_export_html``
— onto a document whose body is ``<div id="bn-app-root">`` plus the single-file
React bundle.  The frozen vanilla renderer in ``bristlenose/theme/js/`` never
receives that class, so a rule naming a vanilla-only class could never fire.
Widening the search to ``bristlenose/theme/`` would green-light exactly the dead
rules this gate exists to catch.

**Why whole-token matching.** A substring search reports ``.badge-accept`` as
found, because ``badge-accept-flash`` (a live animation class) contains it — the
very selector that shipped broken would have passed a naive gate.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXPORT_CSS = _REPO_ROOT / "bristlenose" / "theme" / "templates" / "export.css"
_FRONTEND_SRC = _REPO_ROOT / "frontend" / "src"

#: Applied by ``routes/export.py`` to ``<body>``, so it has no React call site.
_GATE_CLASS = "bn-export-mode"

#: Markup-producing sources.  Deliberately excludes ``.css`` — a class that
#: exists only in a stylesheet is precisely the dead case.
_SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}

#: Floor for the discovered corpus, well under the real count (~148 at time of
#: writing).  A glob that silently stops matching would otherwise turn this
#: whole module into a gate that cannot fail.
_MIN_SOURCE_FILES = 50

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_RULE_RE = re.compile(r"([^{}]+)\{[^{}]*\}")
_CLASS_RE = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")


def _token_re(class_name: str) -> re.Pattern[str]:
    """Match ``class_name`` only as a whole class token.

    ``-`` is a class-name character, so the boundary has to exclude it as well
    as ``\\w`` — otherwise ``badge-accept`` matches inside ``badge-accept-flash``.
    """
    return re.compile(rf"(?<![\w-]){re.escape(class_name)}(?![\w-])")


def _export_css_classes() -> set[str]:
    """Class names targeted by ``export.css``, minus the gate class itself.

    Comments are stripped first (they quote retired selectors as documentation).
    Attribute selectors such as ``[draggable="true"]`` carry no class and are
    skipped by construction.
    """
    body = _COMMENT_RE.sub("", _EXPORT_CSS.read_text(encoding="utf-8"))
    classes: set[str] = set()
    for selectors in _RULE_RE.findall(body):
        for selector in selectors.split(","):
            classes.update(_CLASS_RE.findall(selector))
    classes.discard(_GATE_CLASS)
    return classes


def _frontend_sources() -> list[Path]:
    """React sources that can render a class, excluding tests.

    Tests are excluded on purpose: a class spelled only in a ``.test.tsx``
    assertion is not rendered anywhere, which is how ``.bn-counter`` stayed
    plausible for so long (it survived as a ``data-testid``, never a class).
    """
    return [
        path
        for path in sorted(_FRONTEND_SRC.rglob("*"))
        if path.is_file()
        and path.suffix in _SOURCE_SUFFIXES
        and ".test." not in path.name
        and not {"__tests__", "__mocks__"} & set(path.parts)
    ]


def test_matcher_requires_a_whole_class_token() -> None:
    """The matcher rejects substring hits (the trap the 15 Aug bug would set)."""
    pattern = _token_re("badge-accept")
    assert pattern.search('className="badge badge-accept"')
    assert not pattern.search('className="badge-accept-flash"')
    assert not pattern.search('className="my-badge-accept"')


def test_frontend_sources_are_discoverable() -> None:
    """The corpus is real — otherwise every assertion below passes vacuously."""
    sources = _frontend_sources()
    assert len(sources) >= _MIN_SOURCE_FILES, (
        f"Only {len(sources)} frontend source file(s) found under {_FRONTEND_SRC}. "
        "The gate below cannot fail against an empty corpus — fix the discovery "
        "glob (or lower _MIN_SOURCE_FILES if the frontend really did shrink)."
    )


def test_export_css_targets_something() -> None:
    """The parser is reading real rules (guards against a parse regression)."""
    classes = _export_css_classes()
    assert len(classes) >= 10, (
        f"Parsed only {len(classes)} class selector(s) from {_EXPORT_CSS}. "
        "Expected the full read-only rule set — check _RULE_RE / _CLASS_RE."
    )
    assert _GATE_CLASS not in classes


def test_every_export_css_class_is_rendered_by_the_spa() -> None:
    """No export.css rule names a class the React SPA never renders (the gate)."""
    sources = _frontend_sources()
    texts = [path.read_text(encoding="utf-8", errors="ignore") for path in sources]

    unmatched = sorted(
        class_name
        for class_name in _export_css_classes()
        if not any(_token_re(class_name).search(text) for text in texts)
    )

    assert not unmatched, (
        "export.css hides class(es) that no longer exist in frontend/src:\n  ."
        + "\n  .".join(unmatched)
        + "\n\nThe rule matches nothing, so the control it was meant to hide is "
        "visible in every exported report. Either:\n"
        "  • the class was renamed — point the rule at the current class "
        "(prefer the stable container over a leaf, as .badge-action-pill does), or\n"
        "  • the control is gone / already gated in JSX via isExportMode() — "
        "delete the dead rule.\n"
        "Do not add an allow-list entry: 'it lives in the vanilla renderer' is "
        "not a reason to keep it. bn-export-mode is only ever applied to the "
        "React export, so a vanilla-only class can never match."
    )
