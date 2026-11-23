#!/usr/bin/env python3
"""Generate docs/mockups/autocode-mac-popup.html: the first-run AutoCode pop-up inside the Mac app,
today and under each option for Phase 5 (docs/design-autocode-landing-plan.md).

The owner asked (23 Nov 2026): what the first-run AutoCode pop-up carries in the Mac app, what is
proposed to keep and why, with before and after mockups. The pop-up and the sidebar line are drawn
by the sibling generator autocode-progress-states.gen.py (shipped CSS, shipped words by key), so
they are the product's pixels. The window, the page behind and the row menu are stand-ins; any
word that is not a shipped string is flagged in the frame's chrome bar.

    .venv/bin/python docs/mockups/autocode-mac-popup.gen.py
"""

from __future__ import annotations

import html
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "docs/mockups"
OUT = HERE / "autocode-mac-popup.html"


def load(name: str, file: str):  # noqa: ANN201
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


ST = load("states_gen", "autocode-progress-states.gen.py")
E = html.escape
AC = "desktop.chrome.pipeline.autocode"


def window(sidebar: str, chips: str, menu: str = "") -> str:
    return (
        '<div class="win"><div class="winbar"><i></i><i></i><i></i></div><div class="winbody">'
        '<div class="winside">' + sidebar + menu + "</div>"
        '<div class="winmain"><div class="page-ghost"></div><div class="stackhere">' + chips + "</div></div></div></div>"
    )


def fr(title: str, note: str, body: str, flag: bool = False) -> str:
    return (
        '<figure><div class="chrome"><span>' + E(title) + '</span><span class="' + ("flag" if flag else "") + '">'
        + E(note) + "</span></div>" + body + "</figure>"
    )


def row_menu() -> str:
    return (
        '<div class="ctxmenu"><div>Open</div><div>Show in Finder</div><hr>'
        '<div class="hl">Stop AutoCode</div></div>'
    )


def build() -> str:
    run = ST.mac(ST.d(AC, done=48, total=ST.N), shimmer=True)
    rest = ST.mac(None)
    sig = ST.mac(ST.d("desktop.chrome.pipeline.pickingUpSignals"))
    failed_line = ST.mac(ST.d("desktop.pipeline.diagnostic.pill.out_of_credit"), glyph="e")
    stopped_line = ST.mac(ST.d("desktop.chrome.pipeline.stopped"))
    c_run = ST.chip_running(48)
    c_done = ST.chip_done("1m 4s")
    # The app now drops the failure sentence's own full stop (commit 9bd25a009), so draw one, as shipped.
    c_fail = ST.chip_failed("codebook.autocodeFailure.outOfCredit").replace("credit..", "credit.")
    c_cancel = ST.chip_cancelled()
    catch_up = (
        '<div class="activity-chip" data-status="running"><span class="chip-label bn-thinking-shimmer">'
        + E(ST.c("autocode.chip.recoding")) + "&hellip;</span></div>"
    )

    today = [
        fr("Today · running", "sidebar line and pop-up both show progress; Cancel only in the pop-up", window(run, c_run)),
        fr("Today · finished", "sidebar hands over to Signals; pop-up: duration and View Report", window(sig, c_done)),
        fr("Today · failed (out of credit)", "sidebar line gone; the pop-up is the only place it shows", window(rest, c_fail)),
        fr("Today · stopped", "sidebar line gone; pop-up says cancelled", window(rest, c_cancel)),
    ]
    a = [
        fr("A · running", "unchanged from today", window(run, c_run)),
        fr("A · failed", "NEW: the sidebar keeps a line (D23); the pop-up as today", window(failed_line, c_fail)),
        fr("A · stopped", "NEW: the sidebar keeps 'Stopped' (D23); the pop-up as today", window(stopped_line, c_cancel)),
    ]
    b = [
        fr("B · running", "NO pop-up; Stop moves to the row's menu: 'Stop AutoCode' is NEW COPY", window(run, "", row_menu()), flag=True),
        fr("B · finished", "LOST: the duration and View Report (no other link opens the review)", window(sig, ""), flag=True),
        fr("B · failed", "the sidebar line only; LOST: the sentence saying which failure", window(failed_line, ""), flag=True),
    ]
    d = [
        fr("D · running", "NO pop-up while it runs; Stop in the row's menu (NEW COPY)", window(run, "", row_menu()), flag=True),
        fr("D · finished", "the pop-up appears at the end, as today", window(sig, c_done)),
        fr("D · failed", "sidebar line plus the pop-up at the end", window(failed_line, c_fail)),
    ]
    keep = [fr("All options · other pop-ups stay", "catch-up, clip and screens exports, Copy Screens: untouched", window(rest, catch_up))]

    def section(title: str, lede: str, frames: list[str]) -> str:
        return '<section><h2>' + E(title) + '</h2><p class="q">' + E(lede) + '</p><div class="frames">' + "".join(frames) + "</div></section>"

    body = (
        section("Before: today in the Mac app", "The first-run AutoCode pop-up is the web app's activity pop-up, shown inside the window.", today)
        + section("A · Keep the pop-up (recommended)", "Nothing is taken away. The sidebar line gains the stopped and failed states it lacks today.", a)
        + section("B · Hide the first-run pop-up; Stop in the row's menu", "No duplicate progress during a run, at the cost of Stop's place, View Report and the failure sentence.", b)
        + section("D · Hide it while it runs; show it when it ends", "A middle way: no duplicate progress; the ending and View Report stay; Stop still needs a new home.", d)
        + section("Whatever you choose", "These pop-ups are not the first-run AutoCode one, and Phase 5 must not touch them.", keep)
    )
    return PAGE.replace("/*CSS*/", ST.css_blocks()).replace("<!--BODY-->", body)


PAGE = """<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoCode pop-up in the Mac app</title>
<style>
/*CSS*/

/* ════ mockup chrome (not product): window stand-in, page ghost, row menu ════ */
:root { color-scheme: light dark; }
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text); font-family: var(--bn-font-body);
  font-size: var(--bn-text-label); }
.wrap { max-width: 1280px; margin: 0 auto; padding: 0 20px 80px; }
h1 { font-size: var(--bn-text-title); font-weight: var(--bn-weight-emphasis); margin: 22px 0 4px; }
h2 { font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 30px 0 4px; padding-top: 10px;
  border-top: 1px solid var(--bn-colour-border); }
.q { color: var(--bn-colour-muted); max-width: 90ch; margin: 0 0 10px; }
.frames { display: flex; flex-wrap: wrap; gap: 14px; }
figure { margin: 0; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; width: 600px; }
.chrome { display: flex; justify-content: space-between; gap: .6rem; padding: .3rem .6rem; background: var(--bn-colour-badge-bg);
  color: var(--bn-colour-badge-text); font-family: var(--bn-font-mono); font-size: var(--bn-text-micro);
  border-bottom: 1px solid var(--bn-colour-border); }
.chrome .flag { color: #d92d20; }
.win { background: var(--bn-colour-bg); }
.winbar { height: 22px; display: flex; gap: 6px; align-items: center; padding: 0 10px; border-bottom: 1px solid var(--bn-colour-border); }
.winbar i { width: 10px; height: 10px; border-radius: 50%; background: var(--bn-colour-border); display: block; }
.winbody { display: grid; grid-template-columns: 220px 1fr; height: 220px; }
.winside { position: relative; border-right: 1px solid var(--bn-colour-border); }
.winside .art { padding: 8px 6px; }
.winmain { position: relative; }
.page-ghost { position: absolute; inset: 14px 16px; background: repeating-linear-gradient(transparent 0 12px,
  var(--bn-colour-badge-bg) 12px 14px); opacity: .7; }
.stackhere { position: absolute; right: 12px; bottom: 12px; left: 12px; display: flex; justify-content: flex-end; }
.stackhere .activity-chip { max-width: 100%; }
.ln .tx.mac-shimmer { --bn-shimmer-base: var(--bn-colour-muted); --bn-shimmer-peak: var(--bn-colour-text); }
.ctxmenu { position: absolute; left: 120px; top: 40px; width: 150px; padding: 4px; border-radius: 7px; z-index: 3;
  background: var(--bn-colour-bg); border: 1px solid var(--bn-colour-border); box-shadow: 0 8px 24px rgba(0,0,0,.18);
  font-size: 13px; }
.ctxmenu div { padding: 2px 8px; border-radius: 4px; }
.ctxmenu .hl { background: var(--bn-colour-accent); color: #fff; }
.ctxmenu hr { border: 0; border-top: 1px solid var(--bn-colour-border); margin: 4px 0; }
.commentary { margin-top: 30px; padding: 14px 18px; border: 7px solid transparent; border-left: 3px solid var(--bn-colour-muted);
  background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
  repeating-linear-gradient(135deg, var(--bn-colour-badge-bg) 0 5px, transparent 5px 10px) border-box; }
.commentary .lab { font-family: var(--bn-font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--bn-colour-muted); }
.commentary table { border-collapse: collapse; width: 100%; } .commentary td, .commentary th { text-align: left;
  border-top: 1px solid var(--bn-colour-border); padding: 6px 8px; vertical-align: top; }
</style>
</head>
<body>
<div class="wrap">
<h1>The first-run AutoCode pop-up in the Mac app</h1>
<p class="q">Pop-ups and sidebar lines are the shipped CSS and words (from autocode-progress-states.gen.py); the window,
the page behind them and the row menu are stand-ins. Red chrome notes mark what an option loses or adds.</p>
<!--BODY-->
<section class="commentary"><div class="lab">Commentary · what the first-run pop-up carries</div>
<table>
<tr><th>What</th><th>Where else it exists today</th><th>A</th><th>B</th><th>D</th></tr>
<tr><td>Progress while it runs ("48/112")</td><td>The sidebar line ("AutoCode · 48 of 112")</td><td>both</td><td>sidebar</td><td>sidebar</td></tr>
<tr><td><b>Cancel</b></td><td>Nowhere: the only way to stop AutoCode in the app</td><td>pop-up</td><td>row menu (new)</td><td>row menu (new)</td></tr>
<tr><td>Done, with its duration</td><td>Nowhere (the sidebar hands over to Signals)</td><td>yes</td><td>lost</td><td>yes</td></tr>
<tr><td><b>View Report</b> (opens the review dialog)</td><td>The codebook's own Review door, in the Codebook lens</td><td>yes</td><td>lost here</td><td>yes</td></tr>
<tr><td>Partial: "Tagged 87 of 112 quotes. Some batches failed."</td><td>Nowhere</td><td>yes</td><td>sidebar "Partial run" only</td><td>yes</td></tr>
<tr><td>Which failure (credit, key, rate limit, network, model)</td><td>Nowhere</td><td>yes</td><td>sidebar words only</td><td>yes</td></tr>
<tr><td>Dismiss ×</td><td>—</td><td>yes</td><td>—</td><td>yes</td></tr>
<tr><td><i>Unseen:</i> tells the app an account is out of credit or a key failed (Settings)</td><td>Nowhere</td><td>yes</td><td>must run headless</td><td>yes</td></tr>
<tr><td><i>Unseen:</i> refreshes the lenses when coding ends</td><td>Nowhere</td><td>yes</td><td>must run headless</td><td>yes</td></tr>
</table>
<p><b>Recommendation: A.</b> The only thing B or D removes is the duplicate progress while a run codes, and each pays for it with
new work (a new home and new words for Stop) and, in B, with View Report and the failure sentence. A keeps everything and
adds what was missing: the sidebar line for a stopped or failed run.</p>
</section>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("wrote " + str(OUT.relative_to(ROOT)))
