"""Build docs/mockups/transcription-diagnostics.html from diagnostics_data.py output.

Numbers only: the page carries levels, counts and rates per session, never any
transcript text. The Sessions grid and the slice under a row use the shipped CSS
(the grid from the capitalisation mockup's inlined block, the slice from
bristlenose/theme/organisms/session-tapestry.css, read from the tree).

    .venv/bin/python experiments/transcript-readability/diagnostics_mockup.py DATA_DIR
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/mockups/transcription-diagnostics.html"
LABELS = {
    "ikea-s1": ("s1", "English", "IKEA shopping interview (Teams recording)"),
    "es-1": ("s2", "Spanish", "Harness-maker, Castile — field tape"),
    "fr-2": ("s3", "French", "Museum visit interview, Strasbourg"),
    "pt-br-1": ("s4", "Portuguese", "Residents' association, São Paulo"),
    "de-2": ("s5", "German", "Radio interview, Bavaria"),
}


def shipped_css() -> str:
    src = (REPO / "docs/mockups/transcript-paragraph-capitalisation.html").read_text(encoding="utf-8")
    lines = src.split("\n")
    start = lines.index("<style>")
    end = start + lines[start:].index("</style>")
    grid = "\n".join(lines[start + 1:end])
    tapestry = (REPO / "bristlenose/theme/organisms/session-tapestry.css").read_text(encoding="utf-8")
    return ("<style>\n" + grid + "\n/* ════ bristlenose/theme/organisms/session-tapestry.css — whole file ════ */\n"
            + tapestry + "\n</style>")


def main(data_dir: str) -> int:
    rows = []
    for sid in LABELS:
        p = Path(data_dir) / f"{sid}.json"
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            d["label"] = LABELS[sid]
            rows.append(d)
    data = json.dumps(rows, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    OUT.write_text(PAGE.replace("{{CSS}}", shipped_css()).replace("{{DATA}}", data), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} sessions)")
    return 0


PAGE = r"""<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcription diagnostics</title>
{{CSS}}
<style>
/* MOCKUP CHROME and the PROPOSED diagnostics block. Chrome is prefixed m-;
   the proposed product classes are prefixed bn-dx- and are not shipped. */
html { color-scheme: light; }
body { padding: 0; }
.m-wrap { max-width: 1400px; margin: 0 auto; padding: 1.5rem clamp(1rem, 3vw, 2rem) 5rem;
  display: flex; flex-direction: column; gap: 1.2rem; }
.m-title { font-size: var(--bn-text-display); font-weight: var(--bn-weight-strong); margin: 0; }
.m-lede { color: var(--bn-colour-muted); max-width: 100ch; margin: .3rem 0 0; }
.m-toolbar { position: sticky; top: 0; z-index: 300; display: flex; flex-wrap: wrap; gap: .7rem 1.4rem;
  align-items: center; padding: .55rem .9rem; background: var(--bn-colour-bg);
  border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md);
  box-shadow: 0 2px 8px var(--bn-colour-shadow); font-size: var(--bn-text-caption); }
.m-group { display: flex; align-items: center; gap: .4rem; }
.m-group > b { font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); }
.m-seg { display: inline-flex; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md); overflow: hidden; }
.m-seg button { all: unset; cursor: pointer; padding: .25rem .6rem; color: var(--bn-colour-text); }
.m-seg button + button { border-left: 1px solid var(--bn-colour-border); }
.m-seg button[aria-pressed="true"] { background: var(--bn-colour-accent); color: #fff; }
.m-frame { border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; background: var(--bn-colour-bg); }
.m-chrome { display: flex; justify-content: space-between; padding: .4rem .75rem; font-family: var(--bn-font-mono);
  font-size: var(--bn-text-badge); color: var(--bn-colour-muted); background: var(--bn-colour-hover);
  border-bottom: 1px solid var(--bn-colour-border); }
.m-stage { padding: .5rem 1rem 1rem; overflow-x: auto; }
.m-commentary { background: repeating-linear-gradient(135deg, var(--bn-colour-hover) 0 4px, transparent 4px 8px);
  border-left: 3px solid var(--bn-colour-muted); border-radius: var(--bn-radius-md); padding: 1rem 1.2rem;
  font-size: var(--bn-text-label); line-height: 1.55; }
.m-commentary .m-label { font-family: var(--bn-font-mono); font-size: var(--bn-text-badge); text-transform: uppercase;
  letter-spacing: .08em; color: var(--bn-colour-muted); display: block; margin-bottom: .5rem; }
.m-commentary p { margin: 0 0 .6rem; max-width: 100ch; }
.m-thumb { width: 96px; height: 54px; border-radius: var(--bn-radius-sm); background: var(--bn-colour-hover); }
.m-file { color: var(--bn-colour-muted); }
body.m-hide .bn-dx { display: none; }
body.m-hide .bn-tapestry { padding-bottom: .6rem; }
body.m-hide .bn-sessions-row.bn-tapestry-open { background: none; border-bottom-color: var(--bn-colour-border); }

/* ── PROPOSED: the diagnostics block inside the slice ─────────────────────── */
.bn-dx { padding: 0 0 1rem; display: grid; gap: .6rem; }
.bn-dx-head { padding: 0 var(--bn-space-md); }
.bn-dx-stats { padding: 0 var(--bn-space-md); }
.bn-dx-scroll { padding-top: 0; }
.bn-dx-head { display: flex; align-items: baseline; gap: .8rem; flex-wrap: wrap; }
.bn-dx-title { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: .25rem;
  font-size: var(--bn-text-caption); font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); }
.bn-dx-title:hover { color: var(--bn-colour-text); }
.bn-dx-title:focus-visible { outline: 2px solid var(--bn-colour-accent); outline-offset: 2px; border-radius: var(--bn-radius-sm); }
.bn-dx-title .bn-tapestry-toggle { margin: 0; pointer-events: none; }
.bn-dx-body { display: grid; gap: .8rem; }
.bn-dx:not(.bn-dx-open) .bn-dx-body { display: none; }
/* Mockup chrome: where the shipped session timeline sits, not redrawn here. */
.m-timeline { margin: .6rem var(--bn-space-md) 0; height: 54px; border: 1px dashed var(--bn-colour-border);
  border-radius: var(--bn-radius-md); display: grid; place-items: center; font-family: var(--bn-font-mono);
  font-size: var(--bn-text-badge); color: var(--bn-colour-muted); }
.bn-dx-micro { font-size: var(--bn-text-caption); color: var(--bn-colour-muted); font-variant-numeric: tabular-nums; }
.bn-dx-listen { margin-top: .35rem; color: var(--bn-colour-muted); }
.bn-dx-listen .timecode { cursor: pointer; }
.bn-dx-lanes { display: grid; grid-template-columns: 7.5rem 1fr; gap: 2px .6rem; align-items: center; }
.bn-dx-lane-label { font-size: var(--bn-text-caption); color: var(--bn-colour-muted); text-align: right; }
.bn-dx-lane { height: 22px; display: block; width: 100%; }
.bn-dx-axis { height: 14px; }
.bn-dx-axis text { font-family: var(--bn-font-mono); font-size: 9px; fill: var(--bn-colour-muted); }
.bn-dx-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: .6rem; }
.bn-dx-card { border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md); padding: .5rem .7rem;
  background: var(--bn-colour-bg); font-size: var(--bn-text-caption); }
.bn-dx-card h4 { margin: 0 0 .3rem; font-size: var(--bn-text-caption); font-weight: var(--bn-weight-emphasis);
  color: var(--bn-colour-muted); }
.bn-dx-kv { display: grid; grid-template-columns: 1fr auto auto; gap: 1px .6rem; }
.bn-dx-kv span:nth-child(3n+2), .bn-dx-kv span:nth-child(3n) { text-align: right; font-variant-numeric: tabular-nums; }
.bn-dx-kv span:nth-child(3n) { color: var(--bn-colour-muted); }
.bn-dx-chips { display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .35rem; }
.bn-dx-chips .badge { font-size: var(--bn-text-badge); }
.bn-dx-hist { width: 100%; height: 46px; display: block; margin-top: .3rem; }
.bn-dx-hist text { font-family: var(--bn-font-mono); font-size: 8px; fill: var(--bn-colour-muted); }
</style>
</head>
<body>
<div class="m-wrap">
<header>
  <h1 class="m-title">Transcription diagnostics in the Sessions grid</h1>
  <p class="m-lede">Proposal, drawn on real measurements: five public recordings in five languages, transcribed
  through the shipped stage 5 with the style prompt and the skipped-window net. Numbers only; no transcript text
  is on this page. The grid and the slice under a row are the shipped CSS; the diagnostics block inside the slice
  is new and proposed.</p>
</header>
<div class="m-toolbar">
  <div class="m-group"><b>Diagnostics menu</b><span class="m-seg">
    <button data-dx="on" aria-pressed="true">On</button><button data-dx="off" aria-pressed="false">Off (default)</button></span></div>
  <div class="m-group"><b>Blocks</b><span class="m-seg">
    <button data-all="open" aria-pressed="false">Open all</button><button data-all="closed" aria-pressed="false">Close all</button></span></div>
  <div class="m-group"><b>Appearance</b><span class="m-seg">
    <button data-scheme="light" aria-pressed="true">Light</button><button data-scheme="dark" aria-pressed="false">Dark</button></span></div>
  <div class="m-group"><b>Type</b><span class="m-seg">
    <button data-platform="desktop" aria-pressed="true">Mac app (SF)</button><button data-platform="web" aria-pressed="false">Browser (Inter)</button></span></div>
</div>
<div class="m-frame"><div class="m-chrome"><span><b>Sessions</b></span><span>artefact</span></div>
<div class="m-stage"><section class="bn-session-table"><div class="bn-sessions-grid" role="table" id="m-grid"></div></section></div></div>
<aside class="m-commentary"><span class="m-label">Commentary</span>
<p><b>What each strip is.</b> All strips share one time scale across sessions, as the session timeline does, so
sessions compare by eye. <i>Sound</i>: the loudest tenth of each 10 s (90th-percentile level), with the
recording's noise floor dashed. <i>Pace</i>: words a minute. <i>Doubt</i>: share of words Whisper gave under 0.5
confidence, darker is more. <i>Gaps</i>: stretches with sound but almost no words; outlined ones the net
re-transcribed, filled ones are still empty.</p>
<p><b>Placement.</b> Under the session timeline, in the same slice, collapsed by default behind its own
disclosure triangle, and present at all only when the Diagnostics menu is on (the user's preference, off by
default). The two headline numbers stay beside the heading while the block is closed.</p>
<p><b>The headline.</b> Beside "Diagnostics", always: the share of decode windows Whisper had to retry,
and how long the recording has sound but no words. Of everything measured, these two separated the worst
recording (a field tape: 59% retried, 8 minutes with sound but no words) from the rest (1–8% retried,
seconds at most). Mean word confidence did not: the field tape scored 0.87, a clean interview 0.86, because it
only averages the words Whisper wrote and skipped speech has none. It stays in the Confidence panel as background.</p>
<p><b>What it is not.</b> An accuracy score. None of these numbers knows what was said; they say where to listen.
Overlapping speech, the commonest cause of lost words, is not here yet: the voice pass would have to report it.</p>
<p><b>Placeholders.</b> Thumbnails, dates and speakers are mockup filler; the session timeline lanes that sit
above this block in the shipped slice are left out to keep the page about diagnostics.</p>
</aside>
</div>
<script>
const D = {{DATA}};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]);
const tc = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const pct = (n, d) => d ? `${(100 * n / d).toFixed(1)}%` : "—";
const longest = Math.max(...D.map(d => d.duration_s));
// The session timeline's own geometry (SessionTapestry.tsx, tapestryScale.ts, tapestryTuning.ts):
// labels at x=12, plot from a 82px gutter, 14px right margin, one scale for every slice.
const GUTTER = 82, RIGHT = 14, LABEL_X = 12, CAPTION_PX = 12, centre = px => px * 0.35;
const fitScale = (len, width) => Math.min(4, Math.max(1, len / Math.max(1, width - GUTTER - RIGHT)));
let sPerPx = 2;
const X = s => GUTTER + s / sPerPx;
const tickStep = () => [60, 120, 300, 600, 900, 1800].find(st => st / sPerPx >= 64) ?? 3600;
const mmss = s => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function ticksSvg(d, y) {
  let t = "";
  for (let tk = 0; tk <= d.duration_s; tk += tickStep())
    t += `<text class="bn-tp-tick" x="${X(tk)}" y="${y}" text-anchor="${tk ? "middle" : "start"}">${mmss(tk)}</text>`;
  return t;
}
const label = (txt, mid) => `<text class="bn-tp-lane" x="${LABEL_X}" y="${mid + centre(CAPTION_PX)}">${txt}</text>`;
// Stand-in for the shipped timeline: its labels, tracks and ticks at the shipped y positions
// (flag 18, clips 16/18, sentiment band, three theme rows), with no content.
function timelineSvg(d) {
  const flagH = 18, clipH = 16, MT = { y: flagH + 12, h: clipH }, PT = { y: flagH + 12 + clipH + 3, h: clipH + 2 };
  const SE = { mid: PT.y + PT.h + 41 }, TG = { y: SE.mid + 40, row: 22 }, H = TG.y + TG.row * 3 + 14;
  const W = Math.ceil(X(d.duration_s) + RIGHT), x0 = X(0), w = X(d.duration_s) - x0;
  return `<svg class="bn-tapestry-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">` +
    label("Sections", 2.5 + flagH / 2) + label("Moderator", MT.y + MT.h / 2) + label("Participant", PT.y + PT.h / 2) +
    label("Sentiment", SE.mid) + label("Themes", TG.y + 9) +
    `<rect class="bn-tp-track" x="${x0}" y="${MT.y}" width="${w}" height="${MT.h}"/>` +
    `<rect class="bn-tp-track" x="${x0}" y="${PT.y}" width="${w}" height="${PT.h}"/>` +
    `<line class="bn-tp-axis" x1="${x0}" x2="${x0 + w}" y1="${SE.mid}" y2="${SE.mid}"/>` +
    `<text x="${x0 + w / 2}" y="${SE.mid - 14}" text-anchor="middle" class="bn-tp-tick">session timeline content not drawn in this mockup</text>` +
    ticksSvg(d, H - 2) + `</svg>`;
}
// Diagnostics: the same x geometry, four lanes of the clip lanes' height.
function diagSvg(d) {
  const LH = 18, GAP = 5, top = 4, lanes = ["Sound", "Pace", "Doubt", "Gaps"];
  const y = i => top + i * (LH + GAP), H = y(4) + 14;
  const W = Math.ceil(X(d.duration_s) + RIGHT), b = d.series.bin_s, bw = Math.max(0.5, b / sPerPx);
  let g = lanes.map((n, i) => label(n, y(i) + LH / 2)).join("");
  // Sound: 90th-percentile level per bin, -70..0 dBFS; the floor dashed.
  const yS = v => y(0) + LH - LH * Math.max(0, Math.min(1, (v + 70) / 70));
  const pts = d.series.level_p90.map((v, i) => `${X(i * b + b / 2).toFixed(1)},${(v == null ? y(0) + LH : yS(v)).toFixed(1)}`);
  g += `<path d="M${X(0)},${y(0) + LH} L${pts.join(" L")} L${X(d.duration_s)},${y(0) + LH} Z" fill="var(--bn-colour-muted)" opacity=".35"/>`;
  g += `<line x1="${X(0)}" x2="${X(d.duration_s)}" y1="${yS(d.audio.floor_dbfs)}" y2="${yS(d.audio.floor_dbfs)}" stroke="var(--bn-colour-text)" stroke-dasharray="3 3" opacity=".5"/>`;
  // Pace: words a minute per bin, 0..240.
  g += d.series.wpm.map((v, i) => { const h = Math.min(LH, LH * v / 240);
    return `<rect x="${X(i * b)}" y="${y(1) + LH - h}" width="${Math.max(0.5, bw - 0.6)}" height="${h}" fill="var(--bn-colour-accent)" opacity=".55"/>`; }).join("");
  // Doubt: share of words under 0.5 confidence, darker is more.
  g += d.series.low_conf.map((v, i) => v == null ? "" :
    `<rect x="${X(i * b)}" y="${y(2) + 2}" width="${bw}" height="${LH - 4}" fill="var(--bn-colour-text)" opacity="${(0.05 + 0.85 * Math.min(1, v * 2.5)).toFixed(2)}"/>`).join("");
  // Gaps: recovered outlined, still empty filled.
  const empty = d.repair.still_empty;
  const recovered = d.repair.found;  // every found stretch outlined; what is still empty filled on top
  g += `<rect class="bn-tp-track" x="${X(0)}" y="${y(3)}" width="${X(d.duration_s) - X(0)}" height="${LH}"/>`;
  g += recovered.map(([a, e]) => `<rect x="${X(a)}" y="${y(3) + 1}" width="${Math.max(1.5, X(e) - X(a))}" height="${LH - 2}" fill="none" stroke="var(--bn-colour-accent)" stroke-width="1.5"/>`).join("");
  g += empty.map(([a, e]) => `<rect x="${X(a)}" y="${y(3) + 1}" width="${Math.max(1.5, X(e) - X(a))}" height="${LH - 2}" fill="var(--bn-colour-text)" opacity=".7"/>`).join("");
  return `<svg class="bn-tapestry-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${g}${ticksSvg(d, H - 2)}</svg>`;
}
function hist(h) {
  const max = Math.max(...h), bw = 100 / h.length;
  return `<svg class="bn-dx-hist" viewBox="0 0 100 46" preserveAspectRatio="none">` + h.map((v, i) =>
    `<rect x="${i * bw + .5}" y="${36 - 34 * v / max}" width="${bw - 1}" height="${34 * v / max}" fill="var(--bn-colour-accent)" opacity="${i < 5 ? .45 : .8}"/>`).join("") +
    `<text x="0" y="45">0</text><text x="50" y="45" text-anchor="middle">0.5</text><text x="100" y="45" text-anchor="end">1</text></svg>`;
}
function kv(rows) { return `<div class="bn-dx-kv">` + rows.map(([k, a, b]) => `<span>${k}</span><span>${a}</span><span>${b ?? ""}</span>`).join("") + `</div>`; }
const dur = sec => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`;
function stats(d) {
  const t = d.text, r = d.recognition, a = d.audio, p = d.repair;
  const foundS = p.found.reduce((x, [s, e]) => x + e - s, 0), emptyS = p.still_empty.reduce((x, [s, e]) => x + e - s, 0);
  const fillTotal = Object.values(t.fillers).reduce((x, y) => x + y, 0);
  const chips = Object.entries(t.fillers).sort((x, y) => y[1] - x[1]).map(([f, n]) => `<span class="badge">${esc(f)} ${n}</span>`).join("");
  const conf = r.confidence_hist.reduce((x, y) => x + y, 0);
  return `<div class="bn-dx-stats">` +
    `<div class="bn-dx-card"><h4>Audio</h4>${kv([
      ["Noise floor", `${a.floor_dbfs} dBFS`], ["Peak", `${a.peak_dbfs} dBFS`],
      ["Sound", pct(a.active_share, 1), `of ${tc(d.duration_s)}`], ["Clipped", pct(a.clipped_share, 1)]])}</div>` +
    `<div class="bn-dx-card"><h4>Recognition</h4>${kv([
      ["Language", esc(d.detected), "detected"], ["Style prompt", "on"],
      ["Windows", r.decode_segments, "segments"], ["Fell back", r.fallback_segments, pct(r.fallback_segments, r.decode_segments)],
      ["Re-decoded", r.redecode_calls, "stretches"]])}</div>` +
    `<div class="bn-dx-card"><h4>Confidence</h4>${kv([
      ["Mean", r.mean_confidence.toFixed(2)], ["Under 0.5", r.low_confidence_words, pct(r.low_confidence_words, conf)]])}${hist(r.confidence_hist)}</div>` +
    `<div class="bn-dx-card"><h4>Text</h4>${kv([
      ["Words", t.words.toLocaleString("en"), `${t.wpm} a minute`], ["Sentence ends", t.sentence_ends, `${(100 * t.sentence_ends / Math.max(1, t.words)).toFixed(1)} per 100 words`],
      ["Longest unpunctuated", t.longest_unpunctuated, "words"], ["Segments", t.segments]])}</div>` +
    `<div class="bn-dx-card"><h4>Fillers</h4>${kv([["Total", fillTotal, `${(100 * fillTotal / Math.max(1, t.words)).toFixed(1)} per 100 words`]])}<div class="bn-dx-chips">${chips || '<span class="m-file">none written</span>'}</div></div>` +
    `<div class="bn-dx-card"><h4>Gaps and repairs</h4>${kv([
      // In time, which adds up: every still-empty second lies inside a found stretch,
      // and a re-decode can fill part of a stretch and leave holes in it.
      ["Sound, no words", dur(foundS), `${p.found.length} ${p.found.length === 1 ? "stretch" : "stretches"}`],
      ["Filled by re-decoding", dur(foundS - emptyS), `${p.recovered_words.toLocaleString("en")} words`],
      ["Still no words", dur(emptyS), `${p.still_empty.length} ${p.still_empty.length === 1 ? "place" : "places"}`],
      ["Prompt echoes dropped", p.echoes_dropped], ["Silent lines dropped", p.silent_dropped]])}${listen(d)}</div>` +
    `</div>`;
}
// The headline: share of decode windows Whisper had to retry, and how long the recording has
// sound but no words. The two numbers that separated the worst recording from the rest.
function micro(d) {
  const r = d.recognition, empty = d.repair.still_empty.reduce((x, [a, b]) => x + b - a, 0);
  const retried = r.decode_segments ? Math.round(100 * r.fallback_segments / r.decode_segments) : 0;
  const dur = `${Math.floor(empty / 60)}:${String(Math.round(empty % 60)).padStart(2, "0")}`;
  return `<span class="bn-dx-micro">${retried}% retried · ${dur} with no words</span>`;
}
function listen(d) {
  const e = d.repair.still_empty;
  if (!e.length) return "";
  return `<div class="bn-dx-listen">Listen at ` + e.map(([a]) =>
    `<span class="timecode"><span class="timecode-bracket">[</span>${mmss(a)}<span class="timecode-bracket">]</span></span>`).join(" ") + `</div>`;
}
function row(d) {
  const [sid, lang, title] = d.label;
  return `<div class="bn-sessions-row bn-tapestry-open" role="row" data-session="${sid}">` +
    `<div class="bn-sessions-cell bn-cell-id" role="cell"><button class="bn-tapestry-toggle" aria-expanded="true"><svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 1.5 L7 5 L3 8.5"/></svg></button><a href="#">${sid}</a></div>` +
    `<div class="bn-sessions-cell bn-cell-thumb" role="cell"><div class="m-thumb"></div></div>` +
    `<div class="bn-sessions-cell bn-cell-speakers" role="cell">${lang}</div>` +
    `<div class="bn-sessions-cell bn-cell-start" role="cell">12 Oct 2026</div>` +
    `<div class="bn-sessions-cell bn-cell-sentiment" role="cell"></div>` +
    `<div class="bn-sessions-cell bn-cell-duration" role="cell">${tc(d.duration_s)}</div>` +
    `<div class="bn-sessions-cell bn-cell-file m-file" role="cell">${esc(title)}</div></div>` +
    `<div class="bn-tapestry" role="row"><div class="bn-tapestry-scroll" data-sync="${sid}">${timelineSvg(d)}</div>` +
    `<div class="bn-dx">` +
    `<div class="bn-dx-head"><button type="button" class="bn-dx-title" aria-expanded="false">` +
    `<span class="bn-tapestry-toggle" aria-expanded="false"><svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 1.5 L7 5 L3 8.5"/></svg></span>Diagnostics</button>${micro(d)}</div>` +
    `<div class="bn-dx-body"><div class="bn-tapestry-scroll bn-dx-scroll" data-sync="${sid}">${diagSvg(d)}</div>` +
    stats(d) + `</div></div></div>`;
}
function render() {
const grid = document.getElementById("m-grid");
sPerPx = fitScale(longest, grid.clientWidth || 1000);
const open = new Set([...document.querySelectorAll(".bn-dx.bn-dx-open")].map(x => x.closest(".bn-tapestry").previousElementSibling.dataset.session));
grid.innerHTML =
  `<div class="bn-sessions-row bn-sessions-head" role="row"><div class="bn-sessions-cell bn-cell-id">Session</div><div class="bn-sessions-cell bn-cell-thumb"></div>` +
  `<div class="bn-sessions-cell bn-cell-speakers">Language</div><div class="bn-sessions-cell bn-cell-start">Start</div><div class="bn-sessions-cell bn-cell-sentiment"></div>` +
  `<div class="bn-sessions-cell bn-cell-duration">Duration</div><div class="bn-sessions-cell bn-cell-file">Interview</div></div>` + D.map(row).join("");
grid.querySelectorAll(".bn-dx").forEach(dx => { if (open.has(dx.closest(".bn-tapestry").previousElementSibling.dataset.session)) setOpen(dx, true); });
}
// Scroll the timeline and its diagnostics together, so they stay aligned when either scrolls.
document.addEventListener("scroll", e => { const el = e.target; if (!el.dataset || !el.dataset.sync) return;
  document.querySelectorAll(`[data-sync="${el.dataset.sync}"]`).forEach(o => { if (o !== el) o.scrollLeft = el.scrollLeft; }); }, true);
addEventListener("resize", render);
function wire(sel, key, apply) { const b = document.querySelectorAll(sel); b.forEach(x => x.addEventListener("click", () => {
  b.forEach(y => y.setAttribute("aria-pressed", y === x ? "true" : "false")); apply(x.dataset[key]); })); }
wire("[data-dx]", "dx", v => document.body.classList.toggle("m-hide", v === "off"));
function setOpen(dx, open) { dx.classList.toggle("bn-dx-open", open);
  dx.querySelectorAll("[aria-expanded]").forEach(e => e.setAttribute("aria-expanded", String(open))); }
document.addEventListener("click", e => { const b = e.target.closest(".bn-dx-title"); if (!b) return;
  const dx = b.closest(".bn-dx"); setOpen(dx, !dx.classList.contains("bn-dx-open")); });
wire("[data-all]", "all", v => document.querySelectorAll(".bn-dx").forEach(dx => setOpen(dx, v === "open")));
render();
wire("[data-scheme]", "scheme", v => { document.documentElement.style.colorScheme = v; });
wire("[data-platform]", "platform", v => v === "desktop" ? document.documentElement.setAttribute("data-platform", "desktop") : document.documentElement.removeAttribute("data-platform"));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
