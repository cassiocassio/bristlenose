"""The tab bar's full-spacing probe must never take the condensed padding.

The bar measures its own one-row width in each spacing from two empty probes
(frontend/src/components/navBarMeasure.ts): one plain (`.bn-nav-probe >
.bn-tab`), one inside an inner `.bn-global-nav--condensed` span. Both sit inside
the bar, so when the bar itself is condensed, a condensed rule written as a
bare descendant selector reached the full probe too. The bar then measured its
full width as its condensed one, judged full spacing to fit, went back to it,
measured correctly, condensed again — every frame, at any window just under the
full width (seen as violent jitter on the Project page, 19 Oct 2026).

Read from the assembled theme (what ships). Every rule that sets a horizontal
padding under `.bn-global-nav--condensed` must exclude the full probe; and the
two components must keep the probe shapes those rules assume.
"""

from __future__ import annotations

import re
from pathlib import Path

from bristlenose.stages.s12_render.theme_assets import load_default_css

REPO = Path(__file__).resolve().parent.parent
_PADDING = re.compile(r"^\s*padding(-left|-right|-inline)?\s*:", re.I | re.M)


def _rules(css: str) -> list[tuple[str, str]]:
    """(selector-list, body) pairs, entering @media/@supports blocks."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    out: list[tuple[str, str]] = []

    def walk(text: str) -> None:
        i = 0
        while (open_ := text.find("{", i)) != -1:
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


def _selectors(prelude: str) -> list[str]:
    """Split a selector list on top-level commas (not inside :not(...))."""
    parts, depth, cur = [], 0, []
    for ch in prelude:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def test_condensed_padding_never_reaches_the_full_probe() -> None:
    found = []
    for prelude, body in _rules(load_default_css()):
        if not _PADDING.search(body):
            continue
        for sel in _selectors(prelude):
            if ".bn-global-nav--condensed" in sel:
                found.append(sel)
    assert found, "no condensed padding rule found — has the fit cascade's CSS moved?"
    for sel in found:
        assert ":not(.bn-nav-probe >" in sel.replace("  ", " "), (
            f"{sel!r} would give the full probe the condensed padding while the bar is "
            "condensed, and the bar would flip between its two spacings every frame")


def test_the_probes_keep_the_shape_the_rules_assume() -> None:
    """The full probe is a direct child of .bn-nav-probe; the condensed one sits a span deeper."""
    for name in ("NavBar.tsx", "NavTools.tsx"):
        src = (REPO / "frontend/src/components" / name).read_text(encoding="utf-8")
        probe = src[src.index('className="bn-nav-probe"'):]
        probe = probe[: probe.index("</span>\n      </span>")]
        full, condensed = probe.split('<span className="bn-global-nav--condensed">')
        assert 'className="bn-tab' in full and "ref={probeFull}" in full, name
        assert 'className="bn-tab' in condensed and "ref={probeCondensed}" in condensed, name
