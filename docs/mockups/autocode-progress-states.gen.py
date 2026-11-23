#!/usr/bin/env python3
"""Generate docs/mockups/autocode-progress-states.html.

Where AutoCode's progress is told, one frame per moment, on the two surfaces:
the Mac sidebar's project line and the CLI web app's activity pop-up. Companion
to the interactive lab in experiments/autocode-landing/.

The CSS is read from the tree, each block headed with its path and line range,
so the pop-up cannot drift from what ships. The sidebar row is SwiftUI, so its
drawing is lifted from docs/mockups/sidebar-status-roll.html (ProjectCellSpec
metrics), not from shipped CSS. Every word in a frame is a shipped locale value
read here by key; a frame with no shipped wording is drawn hatched and empty,
and its candidates sit in the string plan, not in the frame.

    .venv/bin/python docs/mockups/autocode-progress-states.gen.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/autocode-progress-states.html"
THEME = ROOT / "bristlenose/theme"
CSS = [
    "tokens.css",
    "tokens-typography.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "atoms/shimmer.css",
    "atoms/activity-chip.css",
]
ROLL = ROOT / "docs/mockups/sidebar-status-roll.html"
ROLL_FIRST, ROLL_LAST = 123, 145  # the drawn sidebar rows block in that mockup

COMMON = json.loads((ROOT / "bristlenose/locales/en/common.json").read_text(encoding="utf-8"))
DESKTOP = json.loads((ROOT / "bristlenose/locales/en/desktop.json").read_text(encoding="utf-8"))

TITLE = "Bristlenose UXR Codebook"  # the framework's title, as in the Codebook lens
N = 112


def key(tree: dict, path: str) -> str:
    node = tree
    for part in path.split("."):
        node = node[part]
    if not isinstance(node, str):
        raise KeyError(path)
    return node


def fill(text: str, **values: object) -> str:
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", str(value))
    return text


def c(path: str, **values: object) -> str:
    return fill(key(COMMON, path), **values)


def d(path: str, **values: object) -> str:
    return fill(key(DESKTOP, path.removeprefix("desktop.")), **values)


def css_blocks() -> str:
    out = []
    for rel in CSS:
        text = (THEME / rel).read_text(encoding="utf-8")
        last = text.count("\n") + 1
        out.append("/* ════ bristlenose/theme/" + rel + " — lines 1–" + str(last) + " ════ */\n" + text)
    lines = ROLL.read_text(encoding="utf-8").splitlines()[ROLL_FIRST - 1 : ROLL_LAST]
    head = "/* ════ docs/mockups/sidebar-status-roll.html — lines "
    out.append(head + str(ROLL_FIRST) + "–" + str(ROLL_LAST) + " ════ */\n" + "\n".join(lines))
    return "\n".join(out)


LUCIDE = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "warning": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
    '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "failed": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}


def icon(name: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + LUCIDE[name]
        + "</svg>"
    )


E = html.escape
LABEL = c("autocode.chip.coding", title=TITLE)
CODED = c("autocode.chip.coded", title=TITLE)
CLOSE = '<button class="chip-close" aria-label="' + E(c("activity.dismiss")) + '">' + icon("close") + "</button>"
VIEW = '<a class="chip-link" href="#">' + E(c("codebook.viewReport")) + "</a>"


def chip_running(done: int) -> str:
    return (
        '<div class="activity-chip" data-status="running"><span class="chip-label bn-thinking-shimmer">'
        + E(LABEL + " " + str(done) + "/" + str(N))
        + "&hellip;</span>"
        + '<button class="chip-cancel">' + E(c("activity.cancel")) + "</button></div>"
    )


def chip_done(duration: str) -> str:
    text = CODED + " " + c("activity.durationIn", duration=duration) + "."
    return (
        '<div class="activity-chip" data-status="completed"><span class="chip-check">' + icon("check")
        + "</span><span>" + E(text) + "</span>" + VIEW + CLOSE + "</div>"
    )


def chip_partial(done: int) -> str:
    text = c("autocode.toast.donePartial", processed=done, total=N)
    return (
        '<div class="activity-chip" data-status="partial"><span class="chip-warning">' + icon("warning")
        + "</span><span>" + E(text) + "</span>" + VIEW + CLOSE + "</div>"
    )


def chip_failed(error_key: str) -> str:
    text = c("activity.failed", label=LABEL, error=c(error_key))
    return (
        '<div class="activity-chip" data-status="failed"><span class="chip-error">' + icon("failed")
        + "</span><span>" + E(text) + "</span>" + CLOSE + "</div>"
    )


def chip_cancelled() -> str:
    text = c("activity.cancelled", label=LABEL)
    return (
        '<div class="activity-chip" data-status="cancelled"><span class="chip-error">' + icon("failed")
        + "</span><span>" + E(text) + "</span>" + CLOSE + "</div>"
    )


def mac(line: str | None, shimmer: bool = False, glyph: str = "") -> str:
    if line is None:
        sub = '<div class="subline"><div class="sub hole"></div></div>'
    else:
        cls = "tx bn-thinking-shimmer mac-shimmer" if shimmer else "tx"
        g = '<span class="g ' + glyph + '">' + ("⚠" if glyph == "w" else "✕") + "</span>" if glyph else ""
        sub = (
            '<div class="subline"><div class="sub"><div class="ln">' + g
            + '<span class="' + cls + '">' + E(line) + "</span></div></div></div>"
        )
    return (
        '<div class="art"><div class="sb">'
        '<div class="row sel"><div class="ico"><i></i></div><div class="col" style="--budget:24ch">'
        '<div class="t">Talismanic</div>' + sub + "</div></div>"
        '<div class="row"><div class="ico"><i></i></div><div class="col" style="--budget:24ch">'
        '<div class="t">Opholdsstue</div></div></div>'
        "</div></div>"
    )


def cli(chip: str | None) -> str:
    inner = chip if chip else '<div class="chiphole"></div>'
    return '<div class="cliart"><div class="page-ghost"></div><div class="stackhere">' + inner + "</div></div>"


AC = "desktop.chrome.pipeline.autocode"
SIG = "desktop.chrome.pipeline.pickingUpSignals"
# D23 (landing plan, owner 23 Nov 2026): the Mac's ended lines, all the pipeline run's own words.
PARTIAL = "desktop.chrome.pipeline.partialRun"
STOPPED = "desktop.chrome.pipeline.stopped"
CREDIT = "desktop.pipeline.category.outOfCredit"
KEY = "desktop.pipeline.category.auth"

# (state title, mac frame, mac chrome note, cli frame, cli chrome note)
STATES = [
    ("1 · Waiting for the first batch",
     mac(d(AC, done=0, total=N), shimmer=True), AC,
     cli(chip_running(0)), "autocode.chip.coding + progress + activity.cancel"),
    ("2 · Tags landing",
     mac(d(AC, done=48, total=N), shimmer=True), AC,
     cli(chip_running(48)), "autocode.chip.coding + progress"),
    ("3 · Server finished, screen still playing out the last tags",
     mac(d(SIG)), SIG + " (hands over at the total, today)",
     cli(chip_running(112)), "running until playback ends: a decision, see D2"),
    ("4 · Done",
     mac(None), "the row's resting line (unchanged)",
     cli(chip_done("1m 4s")), "autocode.chip.coded + activity.durationIn + codebook.viewReport"),
    ("5 · Finished, but some batches failed",
     mac(d(PARTIAL), glyph="w"), PARTIAL + ", warning glyph (D23, S1)",
     cli(chip_partial(87)), "autocode.toast.donePartial"),
    ("6 · Stopped by the researcher",
     mac(d(STOPPED)), STOPPED + ", no glyph (D23, S2)",
     cli(chip_cancelled()), "activity.cancelled"),
    ("7 · Failed partway: out of credit",
     mac(d(CREDIT), glyph="e"), CREDIT + ", error glyph (D23, S3)",
     cli(chip_failed("codebook.autocodeFailure.outOfCredit")), "activity.failed + autocodeFailure.outOfCredit"),
    ("8 · Failed partway: key rejected",
     mac(d(KEY), glyph="e"), KEY + ", error glyph (D23, S3)",
     cli(chip_failed("codebook.autocodeFailure.invalidKey")), "activity.failed + autocodeFailure.invalidKey"),
]

STRING_PLAN = [
    ("S1", "Mac line, finished with some batches failed",
     "Settled by D23: <code>" + PARTIAL + "</code> “" + E(d(PARTIAL))
     + "”, the run's own words, with the warning glyph. The glyph opens the AutoCode popover: "
     "the pop-up's sentence (<code>autocode.toast.donePartial</code>) and the failure's."),
    ("S2", "Mac line, stopped by the researcher",
     "Settled by D23: <code>" + STOPPED + "</code> “" + E(d(STOPPED))
     + "”, which the run line already uses, with no glyph and no count (the researcher stopped it)."),
    ("S3", "Mac line, failed (credit, key)",
     "Settled by D23: the run's own category labels, <code>" + CREDIT + "</code> “" + E(d(CREDIT))
     + "” and <code>" + KEY + "</code> “" + E(d(KEY)) + "”, with the error glyph, which opens "
     "the AutoCode popover with the long sentence (<code>codebook.autocodeFailure.*</code>). Other "
     "failures take their category's label the same way (“" + E(d("pipeline.category.quota"))
     + "”, …), or “" + E(d("pipeline.diagnostic.header.failed")) + "” when there is none."),
]

DECISIONS = [
    ("D1", "Whose count does the Mac line show?",
     "The line is native and polls the server (<code>/autocode/jobs</code>), so it counts what the "
     "server has saved. It cannot see the window's playback, and with no window open there is no "
     "playback at all. So the Mac line counts the server's progress, the window shows the landing, "
     "and the two differ by up to one call's worth while a run is live. The lab's “Status line "
     "counts” handle shows both."),
    ("D2", "When does the pop-up say done?",
     "It polls the server and says done when the job does, while the last tags may still be "
     "landing for 1 to 2 s. Either it waits for the page's playback (it lives in the same page, "
     "so it can), or it says done and the last tags land under it."),
    ("D3", "Frame 3 on the Mac: Signals takes the line at the total",
     "<code>ProjectSubtitle.swift</code> hands the line to “" + E(d(SIG)) + "” when the count "
     "reaches its total, which is when the Signals build begins. With playback, the window is "
     "still landing tags at that moment. Probably fine: the line is about the server's work."),
    ("D4", "Taking the pop-up away on the Mac needs frames 5 to 8 on the row first",
     "The row now keeps a line for a stopped, failed or partly failed first apply (D23, Phase 5a), "
     "read from <code>/autocode/jobs?include_ended=true</code>. It outlives the study's server "
     "(a failure seen before the reap is still there after it) and clears when the researcher "
     "opens the study or starts the codebook again. Hiding the pop-up inside the app is Phase 5b."),
    ("D5", "Frames 7 and 8: the pop-up ends with two full stops",
     "<code>activity.failed</code> is “{{label}} failed: {{error}}.” and every "
     "<code>codebook.autocodeFailure.*</code> sentence already ends with a full stop, so the chip "
     "reads “…out of credit..”. Drawn here as it renders. A fix, separate from this design."),
]


def build() -> str:
    rows = []
    for title, mac_html, mac_note, cli_html, cli_note in STATES:
        hole = mac_note.startswith("NO SHIPPED")
        rows.append(
            '<div class="state"><h3>' + E(title) + "</h3>"
            '<div class="pair">'
            '<figure><div class="chrome"><span>Mac sidebar</span><span class="' + ("flag" if hole else "")
            + '">' + E(mac_note) + "</span></div>" + mac_html + "</figure>"
            '<figure><div class="chrome"><span>CLI web app pop-up</span><span>' + E(cli_note)
            + "</span></div>" + cli_html + "</figure>"
            "</div></div>"
        )
    plan = "".join(
        "<tr><td><b>" + a + "</b></td><td>" + E(b) + "</td><td>" + t + "</td></tr>" for a, b, t in STRING_PLAN
    )
    dec = "".join("<dt><b>" + a + "</b> " + E(b) + "</dt><dd>" + t + "</dd>" for a, b, t in DECISIONS)
    return PAGE.replace("/*CSS*/", css_blocks()).replace("<!--STATES-->", "".join(rows)).replace(
        "<!--PLAN-->", plan
    ).replace("<!--DECISIONS-->", dec)


PAGE = """<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoCode progress states</title>
<style>
/*CSS*/

/* ════ mockup chrome (not product) ════ */
:root { color-scheme: light dark; }
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text);
  font-family: var(--bn-font-body); font-size: var(--bn-text-label); }
.wrap { max-width: 1060px; margin: 0 auto; padding: 0 20px 60px; }
.bar { position: sticky; top: 0; z-index: 10; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
  padding: 8px 20px; background: var(--bn-colour-badge-bg); border-bottom: 1px solid var(--bn-colour-border);
  font-family: var(--bn-font-mono); font-size: 11px; }
.bar select { font: inherit; }
.rmnote { display: none; color: #b4701c; }
@media (prefers-reduced-motion: reduce) { .rmnote { display: inline; } }
h1 { font-size: var(--bn-text-title); font-weight: var(--bn-weight-emphasis); margin: 22px 0 4px; }
.lede { color: var(--bn-colour-muted); max-width: 70ch; margin: 0 0 14px; }
.key { display: flex; gap: 16px; font-family: var(--bn-font-mono); font-size: 11px; margin-bottom: 18px; }
.key span { display: inline-flex; align-items: center; gap: 6px; }
.key i { width: 18px; height: 12px; display: inline-block; border: 1px solid var(--bn-colour-border); }
.key i.hatch { background: repeating-linear-gradient(135deg, var(--bn-colour-badge-bg) 0 3px, transparent 3px 6px); }
.state { margin: 0 0 18px; }
.state h3 { font-size: var(--bn-text-label); font-weight: var(--bn-weight-emphasis); margin: 0 0 6px; }
.pair { display: grid; grid-template-columns: 300px 1fr; gap: 14px; }
@media (max-width: 720px) { .pair { grid-template-columns: 1fr; } }
figure { margin: 0; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; }
.chrome { display: flex; justify-content: space-between; gap: .6rem; padding: .3rem .6rem;
  background: var(--bn-colour-badge-bg); color: var(--bn-colour-badge-text); font-family: var(--bn-font-mono);
  font-size: var(--bn-text-micro); border-bottom: 1px solid var(--bn-colour-border); }
.chrome .flag { color: #d92d20; }
.ln .tx.mac-shimmer { --bn-shimmer-base: var(--bn-colour-muted); --bn-shimmer-peak: var(--bn-colour-text); }
.sub.hole { background: repeating-linear-gradient(135deg, var(--bn-colour-badge-bg) 0 3px, transparent 3px 6px);
  border-radius: 2px; }
.cliart { position: relative; height: 92px; background: var(--bn-colour-bg); }
.page-ghost { position: absolute; inset: 12px 14px; background: repeating-linear-gradient(
  transparent 0 12px, var(--bn-colour-badge-bg) 12px 14px); opacity: .7; }
.stackhere { position: absolute; right: 14px; bottom: 12px; }
.chiphole { width: 360px; height: 38px; border-radius: var(--bn-radius-lg);
  background: repeating-linear-gradient(135deg, var(--bn-colour-badge-bg) 0 4px, transparent 4px 8px); }
.commentary { margin-top: 30px; padding: 12px 16px; border: 7px solid transparent; border-left: 3px solid var(--bn-colour-muted);
  background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
  repeating-linear-gradient(135deg, var(--bn-colour-badge-bg) 0 5px, transparent 5px 10px) border-box; }
.commentary .lab { font-family: var(--bn-font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--bn-colour-muted); }
.commentary h2 { font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 14px 0 6px; }
.commentary table { border-collapse: collapse; width: 100%; }
.commentary td { border-top: 1px solid var(--bn-colour-border); padding: 6px 8px; vertical-align: top; }
.commentary dt { margin-top: 10px; }
.commentary dd { margin: 3px 0 0 0; color: var(--bn-colour-text); max-width: 80ch; line-height: 1.5; }
code { font-family: var(--bn-font-mono); font-size: .92em; }
</style>
</head>
<body>
<div class="bar">
  <span>autocode-progress-states</span>
  <label>Palette <select id="pal"><option value="default">default</option><option value="edo">edo</option></select></label>
  <label>Scheme <select id="sch"><option value="">auto</option><option value="light">light</option><option value="dark">dark</option></select></label>
  <label>Motion <select id="mot"><option value="on">on</option><option value="off">off</option></select></label>
  <span class="rmnote">Your system's reduced-motion setting freezes the shimmer whatever this says.</span>
</div>
<div class="wrap">
<h1>AutoCode progress: every moment, both surfaces</h1>
<p class="lede">Where a researcher learns how AutoCode is going: the Mac sidebar's project line and the CLI web
app's pop-up. Generated by <code>autocode-progress-states.gen.py</code>: shipped CSS, shipped words, read by key.
The landing itself (tags, bars, pacing) is in <code>experiments/autocode-landing/</code>.</p>
<div class="key"><span><i></i> artefact: ships as drawn</span><span><i class="hatch"></i> hatched: no shipped
wording, or commentary</span></div>
<!--STATES-->
<section class="commentary">
  <div class="lab">Commentary</div>
  <h2>String plan</h2>
  <table><!--PLAN--></table>
  <h2>Decisions this page surfaces</h2>
  <dl><!--DECISIONS--></dl>
</section>
</div>
<script>
const root = document.documentElement;
document.getElementById("pal").onchange = e => root.dataset.colorTheme = e.target.value;
document.getElementById("sch").onchange = e => { if (e.target.value) root.dataset.theme = e.target.value; else delete root.dataset.theme; };
document.getElementById("mot").onchange = e => root.dataset.analysisAnimation = e.target.value;
</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("wrote " + str(OUT.relative_to(ROOT)))
