#!/usr/bin/env python3
"""Generate docs/mockups/autocode-open-questions.html.

One section per question left open in docs/design-autocode-landing-plan.md, each option drawn
side by side, so the owner can close them one at a time (23 Nov 2026).

Reuses the drawing code of the two sibling generators (the tag sidebar overview and the progress
states) rather than copying it, so every frame here is the same pixels as those mockups.
Question 1 reads the AutoCode confidences of every trial study under the private folders; it
prints only numbers, and names no study except Talismanic (public test data).

    .venv/bin/python docs/mockups/autocode-open-questions.gen.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "docs/mockups"
OUT = HERE / "autocode-open-questions.html"


def load(name: str, file: str):  # noqa: ANN201
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


SB = load("sidebar_gen", "tag-sidebar-autocode-histogram.gen.py")
ST = load("states_gen", "autocode-progress-states.gen.py")
E = SB.E

# ── Q1 data: every trial study's AutoCode confidences ─────────────────────────────────────────
SEARCH = [ROOT / "trial-runs", Path.home() / "Documents"]


def studies() -> list[dict]:
    seen, out = set(), []
    for root in SEARCH:
        for db_path in sorted(root.glob("**/.bristlenose/bristlenose.db")):
            if len(db_path.relative_to(root).parts) > 6:
                continue
            try:
                db = sqlite3.connect("file:" + str(db_path) + "?mode=ro&immutable=1", uri=True)
                rows = db.execute(
                    "select j.framework_id, p.confidence from proposed_tags p "
                    "join autocode_jobs j on j.id = p.job_id"
                ).fetchall()
            except sqlite3.Error:
                continue
            by: dict[str, list[float]] = {}
            for fw, c in rows:
                by.setdefault(fw, []).append(float(c))
            for fw, cs in by.items():
                key = (fw, len(cs), round(sum(cs), 2))
                if key in seen or len(cs) < 10:
                    continue
                seen.add(key)
                public = "talismanic" in str(db_path).lower()
                out.append({"fw": fw, "confs": sorted(cs, reverse=True), "public": public})
    out.sort(key=lambda s: (s["fw"] != "uxr", -len(s["confs"])))
    letter = 0
    for s in out:
        if s["public"]:
            s["label"] = "Talismanic"
        else:
            s["label"] = "Study " + chr(ord("A") + letter)
            letter += 1
    return out


NAMES = {"uxr": "UXR", "nielsen": "Nielsen", "norman": "Norman", "yablonski": "Yablonski",
         "cli-ux": "CLI UX", "garrett": "Garrett"}
TOP, BOTTOM = 0.30, 0.10


def cut(confs: list[float], rule: str) -> tuple[float, float]:
    """(exclude-below, accept-at-or-above) for one study under one rule."""
    if rule == "fixed":
        return (0.30, 0.70)
    n = len(confs)
    hi = confs[max(0, math.ceil(n * TOP) - 1)]  # the value at the 30% rank; ties at it go too
    lo_val = confs[min(n - 1, n - math.ceil(n * BOTTOM))]
    if rule == "pct":
        return (min(lo_val + 1e-9, hi), hi)
    return (0.30, max(hi, 0.70))  # hybrid: the strongest 30%, never below 0.70


def q1(rows: list[dict]) -> str:
    head = (
        '<tr><th>Study · codebook</th><th>n</th><th>Fixed lines<br><small>accept ≥ 0.70, exclude &lt; 0.30</small></th>'
        "<th>Percentages<br><small>accept strongest 30%, exclude weakest 10%</small></th>"
        "<th>Hybrid<br><small>strongest 30%, never below 0.70; exclude &lt; 0.30</small></th></tr>"
    )
    body = []
    for s in rows:
        cells = []
        for rule in ("fixed", "pct", "hybrid"):
            lines = cut(s["confs"], rule)
            items = SB.items_of(s["confs"], lines)
            scale = max(5, max(sum(b.values()) for b in SB.bins_of(items)))
            tally = SB.tally_of(items)
            share = str(round(tally["acc"] / len(items) * 100)) + "% accepted"
            cells.append(
                '<td><div class="q1h">' + SB.histogram(items, scale, "zone", lines) + "</div>"
                '<div class="ov-meta">' + SB.tally_html(tally) + '</div><div class="q1s">' + share + "</div></td>"
            )
        body.append(
            "<tr><td><b>" + E(s["label"]) + "</b> · " + E(NAMES.get(s["fw"], s["fw"])) + "</td><td>"
            + str(len(s["confs"])) + "</td>" + "".join(cells) + "</tr>"
        )
    return '<table class="q1">' + head + "".join(body) + "</table>"


# ── Q2 data: three codebooks, one of them running ─────────────────────────────────────────────
def q2_data(run: dict) -> str:
    uxr = [p[2] for p in run["props"]]
    data = {
        "books": [
            {"title": "Bristlenose UXR Codebook", "confs": uxr, "lines": [0.30, 0.70], "running": False},
            {"title": "Norman's Design Principles", "confs": SB.invented(5, 70, 3.2, 2.0), "lines": [0.25, 0.60],
             "running": False},
            {"title": "Garrett's Elements of UX", "confs": SB.invented(23, 320, 9.0, 3.0), "lines": [0.40, 0.80],
             "running": True},
        ],
    }
    return json.dumps(data).replace("<", "\\u003c")


# ── Q4: Signals while two codebooks run (schematic) ───────────────────────────────────────────
def signals_frame(title: str, note: str, cards: list[tuple[str, str]], line: str) -> str:
    cs = "".join('<div class="sigcard ' + k + '"><b>' + E(name) + "</b></div>" for name, k in cards)
    return (
        '<figure class="sigfig"><div class="chrome"><span>' + E(title) + "</span><span>" + E(note) + "</span></div>"
        '<div class="sigart"><div class="sigline">' + E(line) + '</div><div class="sigcards">' + cs + "</div></div></figure>"
    )


def q4() -> str:
    old = [("Behaviour", ""), ("Pain points", ""), ("Mental models", "")]
    garrett = [("Behaviour", ""), ("Pain points", ""), ("Scope", "new"), ("Structure", "new"), ("Mental models", "")]
    both = [("Behaviour", ""), ("Scope", ""), ("Feedback", "new"), ("Pain points", ""), ("Structure", ""),
            ("Mapping", "new"), ("Mental models", "")]
    a = (
        signals_frame("1 · Garrett finishes, Norman still running", "rebuilt now", garrett, "Signals")
        + signals_frame("2 · Norman finishes", "rebuilt again: cards reorder", both, "Signals")
    )
    b = (
        signals_frame("1 · Garrett finishes, Norman still running", "unchanged: last report", old, "Signals")
        + signals_frame("2 · Norman finishes", "rebuilt once", both, "Signals")
    )
    return (
        '<div class="opt"><h4>A · Rebuild as each one finishes (today)</h4><div class="row">' + a + "</div></div>"
        '<div class="opt"><h4>B · Rebuild once, when the last finishes</h4><div class="row">' + b + "</div></div>"
    )


# ── Q5: before any run, with Sentiment in the sidebar ─────────────────────────────────────────
SENTIMENT_ORDER = ["frustration", "confusion", "doubt", "surprise", "confidence", "delight", "satisfaction"]


def sentiment_codebook(counts: dict[str, int]) -> str:
    top = max(1, max(counts.values()))
    rows = "".join(
        '<div class="tag-row"><span class="tag-name-area"><label class="tag-checkbox-label">'
        '<input type="checkbox" class="bn-checkbox" checked aria-label="' + name + '"></label>'
        '<span class="badge" style="background-color:var(--bn-sentiment-' + name + '-bg)">' + name + "</span></span>"
        '<span class="tag-bar-area"><span class="tag-bar-track"><span class="tag-micro-bar" style="width:'
        + str(round(counts.get(name, 0) / top * 100)) + "%;background-color:var(--bn-sentiment-" + name + ')"></span></span>'
        '<span class="tag-count is-accepted">' + (str(counts[name]) if counts.get(name) else "") + "</span></span></div>"
        for name in SENTIMENT_ORDER
    )
    return (
        '<details class="codebook-framework" open><summary>' + SB.CHEVRON.replace(" ov-chev", "")
        + '<div class="codebook-info"><div class="codebook-title">' + E(SB.t("tags.frameworkSentiment"))
        + "</div></div></summary><div class=\"codebook-body\"><div class=\"tag-filter-group\" "
        'style="background:var(--bn-group-sentiment)"><div class="tag-filter-group-tags">' + rows
        + "</div></div></div></details>"
    )


def sentiment_counts(db_path: Path) -> dict[str, int]:
    db = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    return {s: n for s, n in db.execute("select sentiment, count(*) from quotes group by sentiment") if s}


def pre_run_sidebar(run: dict, line: str, sentiment: str) -> str:
    html = SB.sidebar(run, '<div class="tag-sidebar-subtitle">' + E(line) + "</div>", groups=0)
    return html.replace('<div class="tag-sidebar-body">', '<div class="tag-sidebar-body">' + sentiment, 1)


# ── Q6: the Mac line's words for a stopped or failed AutoCode ─────────────────────────────────
def q6() -> str:
    words = [
        ("Stopped by the researcher", "chrome.pipeline.stopped", "", ""),
        ("Out of credit", "pipeline.diagnostic.pill.out_of_credit", "e", ""),
        ("Key rejected", "pipeline.diagnostic.pill.auth", "e", ""),
    ]
    frames = []
    for title, key, glyph, _ in words:
        frames.append(
            '<figure><div class="chrome"><span>' + E(title) + "</span><span>desktop." + E(key) + "</span></div>"
            + ST.mac(ST.d("desktop." + key), glyph=glyph) + "</figure>"
        )
    partial = []
    for key in ("chrome.pipeline.partialRun", "pipeline.diagnostic.header.someStepsFailed",
                "pipeline.diagnostic.pill.unknown"):
        partial.append(
            '<figure><div class="chrome"><span>Finished, some batches failed</span><span>desktop.' + E(key)
            + "</span></div>" + ST.mac(ST.d("desktop." + key), glyph="w") + "</figure>"
        )
    return (
        '<div class="opt"><h4>The three with one obvious word</h4><div class="row">' + "".join(frames) + "</div></div>"
        '<div class="opt"><h4>Finished, but some batches failed: which of the run\'s three phrases?</h4>'
        '<div class="row">' + "".join(partial) + "</div></div>"
    )


# ── page ──────────────────────────────────────────────────────────────────────────────────────
def section(n: int, title: str, question: str, body: str) -> str:
    return (
        '<section id="q' + str(n) + '"><h2>' + str(n) + " · " + E(title) + '</h2><p class="q">' + E(question)
        + "</p>" + body + "</section>"
    )


def build() -> str:
    run = SB.read_run(SB.DEFAULT_DB)
    rows = studies()
    third = run["props"][len(run["props"]) // 3][0]

    s1 = section(1, "Default cut: fixed lines, percentages, or a hybrid",
                 "Measured on every AutoCode run in the trial studies (Phase 0a). Which rule cuts a first run?",
                 q1(rows))
    s2 = section(2, "Split view during a run",
                 "Garrett is running; UXR and Norman are finished. When Garrett's chart outgrows the shared scale, "
                 "do the still charts shrink as it grows, or hold until the run ends?",
                 '<div class="q2ctl"><button id="q2play">▶ Play the run</button> <span id="q2t"></span></div>'
                 '<div class="row"><div class="opt"><h4>A · Shrink as it grows</h4><div id="q2a" class="q2sb"></div></div>'
                 '<div class="opt"><h4>B · Hold, rescale once at the end</h4><div id="q2b" class="q2sb"></div></div></div>')
    catch = []
    for label, review in (("before", "live"), ("during the 30 s pass", "inactive"), ("after", "live")):
        catch.append((label, review))
    a3 = "".join(
        '<figure><div class="chrome"><span>' + E(lbl) + "</span><span></span></div><div class=\"q3line\">"
        + SB.overview(run, open_=False, review="live") + "</div></figure>" for lbl, _ in catch
    )
    b3 = "".join(
        '<figure><div class="chrome"><span>' + E(lbl) + "</span><span></span></div><div class=\"q3line\">"
        + SB.overview(run, open_=False, review=rv) + "</div></figure>" for lbl, rv in catch
    )
    s3 = section(3, "Catch-up passes and Review",
                 "A catch-up codes a few quotes after an unhide or a speaker fix, in 10 to 60 s. Its tags land with the "
                 "same playback. Does Review go inactive while it runs?",
                 '<div class="opt"><h4>A · Review stays live</h4><div class="row">' + a3 + "</div></div>"
                 '<div class="opt"><h4>B · Review inactive while any pass runs</h4><div class="row">' + b3 + "</div></div>")
    s4 = section(4, "Signals when two codebooks run at once",
                 "Schematic, not the Signals lens's real cards. Garrett and Norman start together; Garrett finishes first.",
                 q4())
    counts = sentiment_counts(SB.DEFAULT_DB)
    sent = sentiment_codebook(counts)
    n_sent = 7
    s5 = section(5, "Before any run: does the top line count Sentiment?",
                 "No overview yet, so the line just counts tags. Sentiment's real counts from Talismanic, in the "
                 "Sessions grid's order and colours (D15).",
                 '<div class="row"><div class="opt"><h4>A · Every tag but Sentiment</h4>'
                 + pre_run_sidebar(run, SB.t("tags.countTags", count=34), sent) + "</div>"
                 '<div class="opt"><h4>B · Every tag</h4>'
                 + pre_run_sidebar(run, SB.t("tags.countTags", count=34 + n_sent), sent) + "</div></div>")
    s6 = section(6, "The Mac line for a stopped or failed AutoCode",
                 "D13: reuse the pipeline run's words. Three map one to one; the partial case has three candidates.",
                 q6())
    _ = third
    page = PAGE.replace("/*CSS*/", SB.css_blocks() + "\n" + roll_css() + "\n" + overview_css())
    return page.replace("<!--SECTIONS-->", s1 + s2 + s3 + s4 + s5 + s6).replace("/*Q2DATA*/null", q2_data(run))


def roll_css() -> str:
    lines = ST.ROLL.read_text(encoding="utf-8").splitlines()[ST.ROLL_FIRST - 1 : ST.ROLL_LAST]
    return "/* ════ docs/mockups/sidebar-status-roll.html — lines " + str(ST.ROLL_FIRST) + "–" + str(ST.ROLL_LAST) + " ════ */\n" + "\n".join(lines)


def overview_css() -> str:
    page = SB.PAGE
    start = page.index("/* ════ NEW")
    end = page.index("/* ════ mockup chrome")
    return page[start:end]


PAGE = """<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoCode open questions</title>
<style>
/*CSS*/

/* ════ mockup chrome (not product) ════ */
:root { color-scheme: light dark; }
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text);
  font-family: var(--bn-font-body); font-size: var(--bn-text-label); }
.wrap { max-width: 1280px; margin: 0 auto; padding: 0 20px 80px; }
.bar { position: sticky; top: 0; z-index: 10; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
  padding: 8px 20px; background: var(--bn-colour-badge-bg); border-bottom: 1px solid var(--bn-colour-border);
  font-family: var(--bn-font-mono); font-size: 11px; }
.bar a { color: var(--bn-colour-accent); }
h1 { font-size: var(--bn-text-title); font-weight: var(--bn-weight-emphasis); margin: 22px 0 4px; }
h2 { font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 36px 0 4px;
  padding-top: 12px; border-top: 1px solid var(--bn-colour-border); }
h4 { font-size: var(--bn-text-label); font-weight: var(--bn-weight-emphasis); margin: 12px 0 6px; }
.q { color: var(--bn-colour-muted); max-width: 80ch; margin: 0 0 12px; }
.row { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-start; }
figure { margin: 0; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; }
.chrome { display: flex; justify-content: space-between; gap: .6rem; padding: .3rem .6rem;
  background: var(--bn-colour-badge-bg); color: var(--bn-colour-badge-text); font-family: var(--bn-font-mono);
  font-size: var(--bn-text-micro); border-bottom: 1px solid var(--bn-colour-border); }
.tag-sidebar.mock-sidebar { visibility: visible; opacity: 1; position: static; grid-column: auto; height: auto;
  margin: 0; padding-top: 0.5rem; max-height: 470px; overflow: hidden; border: 1px solid var(--bn-colour-border);
  border-radius: var(--bn-radius-lg); }
table.q1 { border-collapse: collapse; width: 100%; }
table.q1 th { text-align: left; font-weight: var(--bn-weight-emphasis); padding: 6px 8px; vertical-align: bottom;
  border-bottom: 1px solid var(--bn-colour-border); }
table.q1 th small { font-weight: var(--bn-weight-normal); color: var(--bn-colour-muted); }
table.q1 td { padding: 6px 8px; border-bottom: 1px solid var(--bn-colour-border); vertical-align: top; }
.q1h { width: 220px; }
.q1s { font-family: var(--bn-font-mono); font-size: 11px; color: var(--bn-colour-muted); }
.q2ctl { margin: 8px 0; }
.q2ctl button { font: inherit; padding: 3px 10px; border-radius: 5px; border: 0; background: var(--bn-colour-accent);
  color: #fff; cursor: pointer; }
.q2sb { width: 280px; padding: 8px 12px; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg);
  background: var(--bn-colour-inspector-bg); }
.q3line { width: 260px; padding: 8px 6px; background: var(--bn-colour-inspector-bg); }
.sigfig { width: 300px; }
.sigart { padding: 10px; }
.sigline { font-weight: var(--bn-weight-emphasis); margin-bottom: 6px; }
.sigcards { display: flex; flex-direction: column; gap: 4px; }
.sigcard { padding: 6px 8px; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md);
  font-size: var(--bn-text-caption); }
.sigcard.new { border-color: var(--bn-colour-accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--bn-colour-accent) 25%, transparent); }
.art { padding: 8px; background: var(--bn-colour-quote-bg); }
</style>
</head>
<body>
<div class="bar"><span>autocode-open-questions</span>
  <a href="#q1">1 cut</a><a href="#q2">2 split scale</a><a href="#q3">3 catch-ups</a><a href="#q4">4 Signals</a>
  <a href="#q5">5 pre-run count</a><a href="#q6">6 Mac words</a></div>
<div class="wrap">
<h1>AutoCode landing: the open questions</h1>
<p class="q">From docs/design-autocode-landing-plan.md § Open. Each option drawn side by side, in shipped CSS and words.
Shapes of the Norman and Garrett codebooks in 2 and 4 are invented.</p>
<!--SECTIONS-->
</div>
<script>
const Q2 = /*Q2DATA*/null;
const BINS = 20, H = 34;
function zone(c, l) { return c >= l[1] ? "acc" : c < l[0] ? "exc" : "ten"; }
function bins(confs, l) {
  const b = Array.from({ length: BINS }, () => ({ acc: 0, ten: 0, exc: 0 }));
  for (const c of confs) b[Math.min(BINS - 1, Math.floor(c * BINS))][zone(c, l)]++;
  return b;
}
function tallest(confs, l) { return Math.max(1, ...bins(confs, l).map(x => x.acc + x.ten + x.exc)); }
function nice(x) { for (const s of [5, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100]) if (s >= x) return s; return x; }
function chart(confs, l, scale) {
  const cols = bins(confs, l).map(b => '<span class="ov-bin">' + ["exc", "ten", "acc"].filter(k => b[k]).map(k =>
    '<i class="ov-seg ov-' + k + '" style="height:' + (b[k] / scale * 100) + '%;transition:height .5s ease"></i>').join("") + "</span>").join("");
  const ticks = '<span class="ov-tick" style="left:' + l[0] * 100 + '%"></span><span class="ov-tick" style="left:' + l[1] * 100 + '%"></span>';
  return '<div class="ov-hist ov-zone">' + cols + ticks + "</div>";
}
let landed = 0, timer = null;
function draw(mode, done) {
  const running = Q2.books.find(b => b.running);
  const total = running.confs.length;
  const now = Math.round(landed);
  const shown = Q2.books.map(b => b.running ? b.confs.slice(0, now) : b.confs);
  const grown = Math.max(...Q2.books.map((b, i) => tallest(shown[i], b.lines)));
  const still = Math.max(...Q2.books.filter(b => !b.running).map(b => tallest(b.confs, b.lines)));
  const shared = nice(grown * 1.25);
  const holdStill = nice(still * 1.25);
  return Q2.books.map((b, i) => {
    let scale = shared;
    if (mode === "hold" && !done) scale = b.running ? Math.max(shared, holdStill) : holdStill;
    const t = { acc: 0, ten: 0, exc: 0 }; shown[i].forEach(c => t[zone(c, b.lines)]++);
    return '<div class="ov-block"><div class="ov-fw"><span>' + b.title + '</span></div>' + chart(shown[i], b.lines, scale) +
      '<div class="ov-meta">Excluded ' + t.exc + ' · Tentative ' + t.ten + ' · Accepted ' + t.acc + (b.running && !done ? ' · running' : '') + '</div></div>';
  }).join("");
}
function render(done) {
  document.getElementById("q2a").innerHTML = draw("shrink", done);
  document.getElementById("q2b").innerHTML = draw("hold", done);
  const r = Q2.books.find(b => b.running);
  document.getElementById("q2t").textContent = Math.round(landed) + " of " + r.confs.length + " landed" + (done ? " · run finished" : "");
}
function play() {
  clearInterval(timer); landed = 0; render(false);
  const total = Q2.books.find(b => b.running).confs.length;
  timer = setInterval(() => {
    landed = Math.min(total, landed + total / 80);
    const done = landed >= total;
    render(done);
    if (done) clearInterval(timer);
  }, 100);
}
document.getElementById("q2play").addEventListener("click", play);
render(false);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("wrote " + str(OUT.relative_to(ROOT)))
