#!/usr/bin/env python3
"""Generates docs/mockups/quote-edit-breaks.html.

The shipped quote card beside the proposal for editing a quote drawn as paragraphs, both live.
The left card IS frontend/src/islands/QuoteCard.tsx, bundled from the tree; the right card is
frontend/mockups/quote-edit-breaks/ProposedQuoteCard.tsx, a copy of it with the proposal. The
stylesheet is the whole shipped theme (`get_default_css()`, what `bristlenose serve` sends), so
nothing is retyped. The only new CSS is the PROPOSED block below; the `mk-` rules are page chrome.

The committed page was built from `c5de7d0f2`, before the proposal was built into the real card
(21 Nov 2026), so its left side is the old behaviour. Regenerating it now draws the new card on
both sides: keep the committed HTML as the before/after record.

Run:  .venv/bin/python docs/mockups/quote-edit-breaks.gen.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "mockups" / "quote-edit-breaks"
OUT = ROOT / "docs" / "mockups" / "quote-edit-breaks.html"

sys.path.insert(0, str(ROOT))
from bristlenose.stages.s12_render.theme_assets import get_default_css  # noqa: E402

PROPOSED_CSS = """\
/* ════ PROPOSED — the only new rules ════ */
/* A quote mark keeps its box while editing (shipped: display none), so the
   first and last lines do not move; the bracket is laid over it. */
.bn-proposed .quote-card.editing .smart-quote { display: inline; visibility: hidden; }
.bn-mark, .bn-anchor { position: relative; }
.bn-mark > .crop-handle {
    position: absolute;
    left: 50%;
    bottom: 0;
    transform: translateX(-50%);
}
/* In trimming, a bracket away from the quote marks sits in the gap between two
   words and takes no room (shipped: an inline glyph that pushes the words). */
.bn-anchor > .crop-handle { position: absolute; bottom: 0; }
.bn-anchor-start > .crop-handle { right: -0.12em; }
.bn-anchor-end > .crop-handle { left: -0.12em; }
.bn-proposed .quote-text[contenteditable="true"] { outline: none; }
"""

CHROME_CSS = """\
/* ════ page chrome (mk-), not product ════ */
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text); }
.quote-group .quote-card { content-visibility: visible; }
.mk-bar {
    position: sticky; top: 0; z-index: 10;
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px;
    padding: 10px 16px;
    font: var(--bn-text-label)/1.4 var(--bn-font-body);
    background: var(--bn-colour-inspector-bg, var(--bn-colour-hover));
    border-bottom: 1px solid var(--bn-colour-border);
}
.mk-bar label { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.mk-built, .mk-num { color: var(--bn-colour-muted); font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); }
.mk-label { color: var(--bn-colour-muted); }
.mk-sep { width: 1px; height: 18px; background: var(--bn-colour-border); }
.mk-key { margin: 12px 16px 0; font: var(--bn-text-caption)/1.4 var(--bn-font-body); color: var(--bn-colour-muted); }
.mk-key-artefact, .mk-key-comment {
    font-family: var(--bn-font-mono); padding: 1px 6px; border-radius: 3px; margin-right: 4px;
    border: 1px solid var(--bn-colour-border);
}
.mk-key-comment {
    border: 4px solid transparent; border-left: 2px solid var(--bn-colour-muted);
    background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
        repeating-linear-gradient(135deg, var(--bn-colour-border) 0 3px, transparent 3px 6px) border-box;
}
.mk-cols { display: flex; flex-wrap: wrap; gap: 24px; padding: 16px; align-items: flex-start; }
.mk-col { flex: 1 1 560px; min-width: 0; }
.mk-frame { border: 1px solid var(--bn-colour-border); border-radius: 8px; overflow: hidden; }
.mk-frame-bar {
    font: var(--bn-text-caption)/1 var(--bn-font-mono); color: var(--bn-colour-muted);
    padding: 7px 10px; border-bottom: 1px solid var(--bn-colour-border); background: var(--bn-colour-hover);
}
.mk-stage { padding: 8px 24px 24px; overflow-x: auto; }
.mk-stage .quote-group { display: grid; grid-template-columns: minmax(0, 1fr); }
.mk-comment {
    margin-top: 16px; padding: 4px 16px 12px;
    font: var(--bn-text-label)/1.45 var(--bn-font-body);
    border: 7px solid transparent; border-left: 3px solid var(--bn-colour-muted);
    background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
        repeating-linear-gradient(135deg, var(--bn-colour-border) 0 5px, transparent 5px 10px) border-box;
}
.mk-comment h3 { font-size: var(--bn-text-label); font-weight: var(--bn-weight-emphasis); margin: 12px 0 6px; }
.mk-log { list-style: none; margin: 0; padding: 0; font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); min-height: 9em; }
.mk-log li { padding: 1px 0; }
.mk-log-key { color: var(--bn-colour-muted); }
.mk-log-write { color: var(--bn-colour-accent); }
.mk-log-empty { color: var(--bn-colour-muted); font-family: var(--bn-font-body); }
.mk-rows { border-collapse: collapse; width: 100%; }
.mk-rows th, .mk-rows td { text-align: left; vertical-align: top; padding: 5px 8px; border-top: 1px solid var(--bn-colour-border); }
.mk-rows th[scope="row"] { width: 34%; font-weight: var(--bn-weight-normal); }
.mk-rows-group th { padding-top: 14px; border-top: none; color: var(--bn-colour-muted); font-weight: var(--bn-weight-emphasis); }
.mk-rows kbd { font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); }
.mk-rows tr.mk-diff td, .mk-rows tr.mk-diff th[scope="row"] { background: color-mix(in srgb, var(--bn-colour-highlight) 55%, transparent); }
.mk-rows tr.mk-same { color: var(--bn-colour-muted); }
.mk-tag {
    margin-left: 6px; font: var(--bn-text-micro)/1 var(--bn-font-mono); text-transform: uppercase;
    padding: 1px 4px; border-radius: 3px; border: 1px solid var(--bn-colour-border); color: var(--bn-colour-muted);
}
.mk-tag-open { border-color: var(--bn-colour-accent); color: var(--bn-colour-accent); }
"""


def built_from() -> str:
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--", "frontend/src"], capture_output=True, text=True
    ).stdout.strip()
    return sha + (" + uncommitted frontend/src" if dirty else "")


def main() -> None:
    with tempfile.TemporaryDirectory() as out:
        env = {"BN_MOCKUP_OUT": out, "BN_BUILT_FROM": built_from()}
        subprocess.run(
            ["npx", "vite", "build", "--config", str(SRC / "vite.config.ts"), "--logLevel", "warn"],
            cwd=ROOT / "frontend",
            env={**os.environ, **env},
            check=True,
        )
        js = (Path(out) / "app.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        css_file = Path(out) / "app.css"
        app_css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""
    page = f"""<!doctype html>
<!-- GENERATED by docs/mockups/quote-edit-breaks.gen.py from {env["BN_BUILT_FROM"]}. Do not edit. -->
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quote Edit Paragraphs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..700&display=swap" rel="stylesheet">
<style>
/* ════ bristlenose/theme — get_default_css(), the whole shipped stylesheet ════ */
{get_default_css()}
</style>
<style>
/* ════ CSS imported by the React components (the Vite bundle) ════ */
{app_css}
</style>
<style>
{PROPOSED_CSS}
{CHROME_CSS}
</style>
</head>
<body>
<div id="root"></div>
<script type="module">
{js}
</script>
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()
