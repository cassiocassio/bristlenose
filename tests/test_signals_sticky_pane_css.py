"""The Signals heatmap pane is pinned by `position: sticky` — and that fails silently.

Since 26 Sep 2026 the Signals lens scrolls the page like every other lens, and
the heatmap pane (`.inspector-panel`) stays on the window bottom with
`position: sticky; bottom: 0`. Sticky resolves against the nearest ancestor
that clips or scrolls, so if anything between the pane and the page gains
`overflow: hidden | auto | scroll`, the pane pins to THAT box instead of the
window: no error, it just stops sticking. That is precisely the shape the lens
had before (a height-capped grid with `overflow: hidden` down the chain), so
the regression is one well-meant rule away.

Three contracts, all read from the assembled theme (what ships), not a file:

1. No rule whose SUBJECT is a box in the pane's ancestor chain sets a
   clipping/scrolling overflow.
2. The pane itself is sticky at bottom 0.
3. The scroll-margin that stops jump-to-card landing behind the pane reads the
   custom property InspectorPanel.tsx actually publishes — the two sides are in
   different languages, so nothing else ties the name together. And it is NOT
   `scroll-padding` on <html>: that reserves the strip the pane sits in, so
   focusing a control inside the pane scrolled the page (measured +19–523px).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from bristlenose.stages.s12_render.theme_assets import load_default_css

REPO = Path(__file__).resolve().parent.parent

# Every box between .inspector-panel and the page, outermost first:
# .layout > .center > main.bn-main > .signals-layout > .inspector-panel
# (.signals-center is the pane's sibling, listed because an overflow there is
# what brought the private scroll model back last time, and the datum rule
# still keys on it.)
_CHAIN = ("layout", "center", "bn-main", "signals-layout", "signals-center")
_CHAIN_ELEMENTS = ("main",)  # .bn-main is a <main>; a bare `main {}` rule reaches it too
# Any of the values, in either slot of the two-value form (`overflow: visible hidden`).
# `clip` is deliberately allowed: it clips without making a scroll container,
# so sticky still resolves against the window.
_CLIPPING = re.compile(r"^overflow(-x|-y)?\s*:[^;]*\b(hidden|auto|scroll)\b", re.I)


def _rules(css: str) -> list[tuple[str, str]]:
    """Flatten the stylesheet into (selector-list, body) pairs, entering @media /
    @supports blocks and skipping @keyframes and other at-rules' contents."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[tuple[str, str]] = []

    def walk(text: str) -> None:
        i = 0
        while i < len(text):
            open_ = text.find("{", i)
            if open_ == -1:
                return
            prelude = text[i:open_].strip().split(";")[-1].strip()
            depth, j = 1, open_ + 1
            while j < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            body = text[open_ + 1 : j - 1]
            if prelude.startswith(("@media", "@supports", "@layer", "@container")):
                walk(body)
            elif not prelude.startswith("@"):
                out.append((prelude, body))
            i = j

    walk(css)
    return out


def _top_level_split(text: str, seps: str) -> list[str]:
    """Split on any char in `seps` that is not inside (...), so `:is(a, b)` and
    `:has(> .x)` stay whole."""
    parts, depth, cur = [], 0, []
    for ch in text:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch in seps and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p for p in (x.strip() for x in parts) if p]


def _subject(selector: str) -> str:
    """The rightmost compound of one selector — the element the rule styles."""
    return _top_level_split(selector, " >+~")[-1]


def _targets_chain(selector_list: str) -> list[str]:
    hits = []
    for sel in _top_level_split(selector_list, ","):
        # :has()/:not() test other elements; they don't make this one the subject
        subject = re.sub(r":(has|not)\((?:[^()]|\([^()]*\))*\)", "", _subject(sel))
        classes = set(re.findall(r"\.([\w-]+)", subject))
        element = re.match(r"[a-z]+", subject)
        if classes & set(_CHAIN) or (element and element.group(0) in _CHAIN_ELEMENTS):
            hits.append(sel.strip())
    return hits


@pytest.fixture(scope="module")
def rules() -> list[tuple[str, str]]:
    return _rules(load_default_css())


def test_no_ancestor_of_the_pane_clips_or_scrolls(rules):
    offenders = []
    for selector_list, body in rules:
        hits = _targets_chain(selector_list)
        if not hits:
            continue
        for decl in body.split(";"):
            if _CLIPPING.match(decl.strip()):
                offenders.append(f"{', '.join(hits)} {{ {decl.strip()} }}")
    assert not offenders, (
        "A box in the heatmap pane's ancestor chain clips or scrolls, so the "
        "sticky pane pins to it instead of the window:\n  " + "\n  ".join(offenders)
    )


def test_the_pane_is_sticky_at_the_window_bottom(rules):
    bodies = [b for s, b in rules if any(x.strip() == ".inspector-panel" for x in s.split(","))]
    decls = {
        k.strip(): v.strip()
        for body in bodies
        for k, _, v in (d.partition(":") for d in body.split(";") if ":" in d)
    }
    assert decls.get("position") == "sticky"
    assert decls.get("bottom") == "0"


def test_scroll_margin_reads_the_property_the_panel_publishes(rules):
    tsx = (REPO / "frontend/src/components/InspectorPanel.tsx").read_text()
    m = re.search(r'PANE_HEIGHT_VAR\s*=\s*"(--[\w-]+)"', tsx)
    assert m, "InspectorPanel.tsx no longer exports PANE_HEIGHT_VAR as a string literal"
    var = m.group(1)
    bodies = [b for s, b in rules if s.strip() == ".signals-center *"]
    assert any(
        re.search(rf"scroll-margin-bottom\s*:\s*var\({re.escape(var)}\b", b) for b in bodies
    ), f"no `.signals-center * {{ scroll-margin-bottom: var({var}, …) }}` in the theme"


def test_the_page_carries_no_scroll_padding_for_the_pane(rules):
    offenders = [
        s for s, b in rules
        if re.search(r"(^|[\s,])(html|:root)\b", s) and "scroll-padding" in b
    ]
    assert not offenders, (
        "scroll-padding on the page reserves the strip the pinned pane sits in, "
        f"so focusing a control inside the pane scrolls the page: {offenders}"
    )
