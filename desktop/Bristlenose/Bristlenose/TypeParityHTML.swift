#if DEBUG
import Foundation

// MARK: - Type Parity Inspector — embedded WebKit page
//
// Self-contained HTML/CSS/JS for the WebKit (right) column. Kept as a Swift
// string literal so it ships with no Copy-Bundle-Resources wiring and no
// dependency on a running sidecar. SF Pro resolves via -apple-system in WKWebView
// on macOS, so the rendering is faithful without serving the real theme CSS.
//
// Contract with Swift (TypeParityController):
//   window.__typeParityInit(payload)  — payload = {native, tokens, fingerprint, sample, mode, smoothing}
//   window.__typeParityCollect()      — returns JSON string {rows, fingerprint}
//
// Each row = one bn token. A pulldown assigns the macOS style it should match.
// "old" shows the current tokens-desktop.css value; "new" seeds from the assigned
// native style's measured metrics. size / line-height / letter-spacing are
// contenteditable so the values can be nudged until the rendered width delta is
// ~0 and it looks right by eye. The measured web width vs native width is shown
// per row — width-matching is how you recover Apple's automatic tracking in CSS.

enum TypeParityHTML {
    static let page = #"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  :root { color-scheme: light dark; }
  html { font: 13px -apple-system, "SF Pro Text", system-ui, sans-serif; }
  body {
    margin: 0; padding: 0 16px 40px;
    -webkit-font-smoothing: auto;          /* default; the calibration baseline */
    background: Canvas; color: CanvasText;
  }
  body.smooth-antialiased { -webkit-font-smoothing: antialiased; }
  #env {
    position: sticky; top: 0; z-index: 2;
    padding: 8px 0; margin-bottom: 8px;
    font-size: 11px; color: GrayText;
    background: Canvas; border-bottom: 1px solid color-mix(in srgb, GrayText 30%, transparent);
  }
  .row {
    padding: 22px 0; border-bottom: 1px solid color-mix(in srgb, GrayText 18%, transparent);
  }
  .meta { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-bottom: 4px; }
  .meta .name { font-weight: 600; min-width: 130px; }
  select { font: inherit; }
  .spec { font-size: 11px; color: GrayText; font-variant-numeric: tabular-nums; }
  .sample { display: inline-block; white-space: nowrap; margin-top: 10px; }
  .spec .field {
    display: inline-block; min-width: 3.5em; padding: 0 3px;
    border-bottom: 1px dashed color-mix(in srgb, GrayText 50%, transparent);
    cursor: text; outline: none;
  }
  .spec .field:focus { background: color-mix(in srgb, Highlight 25%, transparent); }
  .delta.ok { color: green; }
  .delta.warn { color: #c60; }
  #toolbar { padding: 6px 0; display: flex; gap: 10px; align-items: baseline; }
  button { font: inherit; }
  .fit { margin-left: 8px; font-size: 10px; }
  .hint { font-size: 11px; color: GrayText; margin: 6px 0 0; }
</style>
</head>
<body>
  <div id="env">Type Parity Inspector — waiting for native metrics…</div>
  <div id="toolbar">
    <button id="fitall" type="button">Fit all widths</button>
    <span class="hint">solves letter-spacing so each web width matches its native target (Δ→0)</span>
  </div>
  <div id="rows"></div>
  <p class="hint">size / line-height / letter-spacing are editable. Match the
     <b>web width</b> to the <b>native width</b> (Δ→0) and trust your eye, then
     use Export in the toolbar.</p>

<script>
"use strict";
let STATE = { native: {}, tokens: [], fingerprint: {}, sample: "", mode: "new", smoothing: "auto" };

const STYLE_ORDER = ["largeTitle","title1","title2","title3","headline","body",
                     "callout","subheadline","footnote","caption1","caption2"];

window.__typeParityInit = function (payload) {
  STATE = payload;
  document.body.classList.toggle("smooth-antialiased", payload.smoothing === "antialiased");
  const fp = payload.fingerprint || {};
  document.getElementById("env").textContent =
    `Environment — macOS ${fp.macOS}, scale @${fp.scale}×, colour ${fp.colorSpace} · mode: ${payload.mode}`;
  buildRows();
};

// Seed values for a row given the current mode + assigned macOS style.
function seedFor(tok, macStyle) {
  if (STATE.mode === "old") {
    return { px: tok.oldPx, lh: +(tok.oldPx * tok.oldLineHeight).toFixed(2), ls: 0, weight: 400 };
  }
  const n = STATE.native[macStyle] || {};
  return {
    px: round2(n.pointSize ?? tok.oldPx),
    lh: round2(n.lineHeight ?? tok.oldPx * tok.oldLineHeight),
    ls: 0,
    weight: n.cssWeight ?? 400
  };
}

function buildRows() {
  const host = document.getElementById("rows");
  host.innerHTML = "";
  for (const tok of STATE.tokens) {
    const assigned = tok.bestMacStyle;
    const seed = seedFor(tok, assigned);
    const row = document.createElement("div");
    row.className = "row";
    row.dataset.token = tok.token;

    // meta line: name + macOS-style pulldown
    const meta = document.createElement("div");
    meta.className = "meta";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = tok.label;
    meta.appendChild(name);

    const sel = document.createElement("select");
    for (const s of STYLE_ORDER) {
      const o = document.createElement("option");
      o.value = s;
      const n = STATE.native[s];
      o.textContent = n ? `${s} (${round2(n.pointSize)}pt)` : s;
      if (s === assigned) o.selected = true;
      sel.appendChild(o);
    }
    sel.addEventListener("change", () => {
      const newSeed = seedFor(tok, sel.value);
      row.dataset.macStyle = sel.value;
      setField(row, "px", newSeed.px);
      setField(row, "lh", newSeed.lh);
      setField(row, "ls", newSeed.ls);
      setField(row, "weight", newSeed.weight);
      applyRow(row);
    });
    row.dataset.macStyle = assigned;
    meta.appendChild(sel);
    row.appendChild(meta);

    // spec line: editable fields + measured widths
    const spec = document.createElement("div");
    spec.className = "spec";
    spec.innerHTML =
      `size <span class="field" contenteditable data-k="px">${seed.px}</span>px · ` +
      `line-height <span class="field" contenteditable data-k="lh">${seed.lh}</span>px · ` +
      `tracking <span class="field" contenteditable data-k="ls">${seed.ls}</span>em · ` +
      `weight <span class="field" contenteditable data-k="weight">${seed.weight}</span> · ` +
      `native <span class="nativew">–</span>px · web <span class="webw">–</span>px · ` +
      `<span class="delta">Δ –</span>` +
      `<button class="fit" type="button">fit</button>`;
    row.appendChild(spec);

    spec.querySelector(".fit").addEventListener("click", () => fitRow(row));

    // sample line — the thing being judged
    const sample = document.createElement("div");
    sample.className = "sample";
    sample.textContent = STATE.sample;
    row.appendChild(sample);

    spec.querySelectorAll(".field").forEach(f => {
      f.addEventListener("input", () => applyRow(row));
      f.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); f.blur(); } });
    });

    host.appendChild(row);
    applyRow(row);
  }
}

function applyRow(row) {
  const px = num(getField(row, "px"));
  const lh = num(getField(row, "lh"));
  const ls = num(getField(row, "ls"));
  const weight = num(getField(row, "weight")) || 400;
  const sample = row.querySelector(".sample");
  sample.style.fontSize = px + "px";
  sample.style.lineHeight = lh + "px";
  sample.style.letterSpacing = ls + "em";
  sample.style.fontWeight = weight;

  // Measure rendered width (web) vs native advance width for the assigned style.
  const webW = sample.getBoundingClientRect().width;
  const nativeW = (STATE.native[row.dataset.macStyle] || {}).sampleWidth ?? 0;
  row.querySelector(".webw").textContent = round1(webW);
  row.querySelector(".nativew").textContent = round1(nativeW);
  const d = webW - nativeW;
  const deltaEl = row.querySelector(".delta");
  deltaEl.textContent = "Δ " + (d >= 0 ? "+" : "") + round1(d);
  deltaEl.className = "delta " + (Math.abs(d) <= 0.75 ? "ok" : "warn");
}

// Auto-fit: solve letter-spacing so web width matches the native target.
// width(ls) is linear in ls, so a 2-sample secant step lands it in ~1-2 passes.
// This recovers Apple's automatic per-size tracking (which CSS doesn't apply) by
// width-matching, in the real WebKit engine — no screenshots, no pixel diffing.
function fitRow(row) {
  const sample = row.querySelector(".sample");
  const nativeW = (STATE.native[row.dataset.macStyle] || {}).sampleWidth ?? 0;
  if (!nativeW) return;                 // no target (e.g. unmapped) — skip
  let ls = num(getField(row, "ls"));
  for (let i = 0; i < 8; i++) {
    const w0 = widthAt(sample, ls);
    const d = nativeW - w0;
    if (Math.abs(d) <= 0.4) break;      // within sub-pixel tolerance
    const probe = 0.01;                 // em
    const slope = (widthAt(sample, ls + probe) - w0) / probe;  // px per em
    if (Math.abs(slope) < 1e-6) break;  // degenerate (1-char sample) — bail
    const next = ls + d / slope;
    if (!isFinite(next)) break;
    ls = Math.max(-0.2, Math.min(0.4, next));  // sane tracking bounds
  }
  setField(row, "ls", round3(ls));
  applyRow(row);                        // re-applies all fields + recomputes Δ
}

function widthAt(sample, ls) {
  sample.style.letterSpacing = ls + "em";
  return sample.getBoundingClientRect().width;   // sync layout flush on read
}

function fitAll() {
  document.querySelectorAll(".row").forEach(fitRow);
}

function round3(v) { return Math.round(v * 1000) / 1000; }

window.__typeParityCollect = function () {
  const rows = [...document.querySelectorAll(".row")].map(row => {
    const macStyle = row.dataset.macStyle;
    const n = STATE.native[macStyle] || {};
    return {
      token: row.dataset.token,
      macStyle,
      sizePx: num(getField(row, "px")),
      lineHeightPx: num(getField(row, "lh")),
      letterSpacingEm: num(getField(row, "ls")),
      weight: num(getField(row, "weight")) || 400,
      nativePt: n.pointSize ?? 0,
      nativeWidth: n.sampleWidth ?? 0,
      webWidth: row.querySelector(".sample").getBoundingClientRect().width
    };
  });
  // Return a structured object — WebKit bridges it to NSDictionary for the
  // Swift side (more reliable than round-tripping a JSON string).
  return { rows: rows, fingerprint: STATE.fingerprint };
};

// helpers
function getField(row, k) { return row.querySelector(`.field[data-k="${k}"]`).textContent; }
function setField(row, k, v) { row.querySelector(`.field[data-k="${k}"]`).textContent = v; }
function num(s) { const v = parseFloat(s); return isFinite(v) ? v : 0; }
function round1(v) { return Math.round(v * 10) / 10; }
function round2(v) { return Math.round(v * 100) / 100; }

document.getElementById("fitall").addEventListener("click", fitAll);
</script>
</body>
</html>
"""#
}
#endif
