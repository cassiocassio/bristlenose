#!/usr/bin/env python3
"""Generate docs/mockups/autocode-levels-slider.html: the review dialog's threshold slider,
modelled on Pixelmator Pro's Levels control (owner, 24 Nov 2026).

Today's slider is a 4 px track under the histogram with two round thumbs and their values
floating above. The owner asked for Levels: the thumbs sit on the histogram's bottom edge
as pointers, a dotted guide rises from each through the histogram, the zones are grey,
orange and green, and perhaps the numbers sit inside the thumbs.

Three frames, all live (drag a thumb, or focus it and use the arrow keys):
  0. today, the shipped markup and CSS;
  A. Levels, Pixelmator-true: small filled pointers, the value under each;
  B. Levels with the value inside the pointer.

Every block of CSS is read from the theme and headed with its path, so the tokens, the
histogram and the zone counters are the shipped ones; only the Levels rules are new, and
they sit in one block at the end headed "NEW". The confidences are invented (23 numbers
shaped like a real run); the squares take the shipped tag tints.

    .venv/bin/python docs/mockups/autocode-levels-slider.gen.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/autocode-levels-slider.html"
THEME = ROOT / "bristlenose/theme"
CSS = [
    "tokens.css",
    "tokens-typography.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "molecules/threshold-review.css",
]

# (confidence, tint) — a run shaped like the screenshot's: 23 proposals.
RUN = [
    (0.17, "ux"), (0.31, "ux"), (0.33, "task"), (0.37, "emo"), (0.41, "trust"),
    (0.46, "opp"), (0.48, "trust"), (0.53, "emo"), (0.57, "ux"), (0.58, "opp"),
    (0.59, "emo"), (0.59, "emo"), (0.62, "emo"), (0.68, "ux"), (0.72, "task"),
    (0.73, "opp"), (0.74, "emo"), (0.77, "ux"), (0.78, "ux"), (0.79, "emo"),
    (0.83, "emo"), (0.88, "ux"), (0.93, "ux"),
]

NEW_CSS = """
/* ════ NEW — the Levels control (not in the theme) ════ */

/* The histogram becomes the control's box, as in Pixelmator: the three zones tint its
   background, and the squares stand on its floor. */
.lv { position: relative; user-select: none; touch-action: none; }
.lv-box {
    position: relative;
    height: 120px;
    margin-top: var(--bn-space-md);
    border-radius: var(--bn-radius-sm) var(--bn-radius-sm) 0 0;
    overflow: hidden;
}
.lv-band { position: absolute; top: 0; bottom: 0; }
.lv-band--grey  { background: color-mix(in srgb, var(--bn-colour-muted) 9%, transparent); }
.lv-band--amber { background: color-mix(in srgb, var(--bn-colour-warning) 13%, transparent); }
.lv-band--green { background: color-mix(in srgb, var(--bn-colour-positive) 11%, transparent); }
.lv-box .threshold-histogram { position: absolute; inset: 0; margin: 0; }
.lv-floor { height: 1px; background: var(--bn-colour-border); }

/* The guide: dotted, from the pointer's tip to the top of the box. */
.lv-guide {
    position: absolute; top: 0; bottom: 0; width: 0;
    border-left: 1px dotted var(--lv-ink);
    pointer-events: none;
}

/* The pointers hang from the floor, tip up at the value. */
.lv-rail { position: relative; height: 36px; }
.lv-thumb {
    position: absolute; top: 0;
    transform: translateX(-50%);
    cursor: grab;
    outline: none;
    display: flex; flex-direction: column; align-items: center;
}
.lv-thumb:active { cursor: grabbing; }
.lv-thumb svg { display: block; overflow: visible; filter: drop-shadow(0 1px 1px rgb(0 0 0 / 0.18)); }
.lv-thumb:focus-visible svg { filter: drop-shadow(0 0 0 2px var(--bn-colour-accent)); }
.lv-thumb:focus-visible .lv-shape { stroke: var(--bn-colour-accent); stroke-width: 2; }
.lv-value {
    font-family: var(--bn-font-body);
    font-variant-numeric: tabular-nums;
    font-size: var(--bn-text-micro);
    color: var(--bn-colour-text);
    pointer-events: none;
}

/* A: filled pointer, value under it. */
.lv--a .lv-shape { fill: var(--lv-ink); stroke: none; }
.lv--a .lv-value { margin-top: 2px; }

/* B: the value inside the pointer, which widens to hold it; outlined, so the figure is
   text colour on the dialog's ground in both schemes (white on amber is 2:1). */
.lv--b .lv-thumb { display: block; width: 40px; height: 24px; }
.lv--b .lv-shape { fill: var(--bn-modal-bg); stroke: var(--lv-ink); stroke-width: 1.5; }
.lv--b .lv-value {
    position: absolute; left: 0; right: 0; top: 7px;
    text-align: center; line-height: 15px;
    font-weight: var(--bn-weight-emphasis);
}

.lv-thumb--lower { --lv-ink: var(--bn-colour-warning); }
.lv-thumb--upper { --lv-ink: var(--bn-colour-positive); }
.lv-guide--lower { --lv-ink: var(--bn-colour-warning); }
.lv-guide--upper { --lv-ink: var(--bn-colour-positive); }
"""

CHROME_CSS = """
/* ════ mockup chrome (not the product) ════ */
html { color-scheme: light dark; }
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text);
       font-family: var(--bn-font-body); font-size: var(--bn-text-body); }
.page { max-width: 960px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: var(--bn-text-title); font-weight: var(--bn-weight-emphasis); margin: 0 0 4px; }
.lede { color: var(--bn-colour-muted); margin: 0 0 16px; max-width: 70ch; }
.bar { position: sticky; top: 0; z-index: 5; display: flex; gap: 16px; flex-wrap: wrap;
       padding: 8px 0; background: var(--bn-colour-bg); font-size: var(--bn-text-caption);
       border-bottom: 1px solid var(--bn-colour-border); margin-bottom: 20px; }
.bar label { display: inline-flex; gap: 4px; align-items: baseline; }
.key { font-size: var(--bn-text-caption); color: var(--bn-colour-muted); margin-bottom: 20px; }
.frame { border: 1px solid var(--bn-colour-border); border-radius: 10px; overflow: hidden;
         margin: 0 0 12px; background: var(--bn-modal-bg); color: var(--bn-colour-text); }
.frame-bar { font: 500 11px/1 ui-monospace, Menlo, monospace; color: var(--bn-colour-muted);
             padding: 8px 12px; border-bottom: 1px solid var(--bn-colour-border);
             background: color-mix(in srgb, var(--bn-colour-muted) 6%, var(--bn-modal-bg)); }
.frame-body { padding: var(--bn-space-lg); max-width: 848px; }
.commentary { margin: 0 0 36px; padding: 12px 14px; font-size: var(--bn-text-label);
    border: 7px solid transparent; border-left: 3px solid var(--bn-colour-muted);
    background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
      repeating-linear-gradient(135deg, color-mix(in srgb, var(--bn-colour-muted) 22%, transparent)
        0 5px, transparent 5px 10px) border-box; }
.commentary b.lab { font: 600 10px/1 ui-monospace, Menlo, monospace; letter-spacing: .06em;
    text-transform: uppercase; color: var(--bn-colour-muted); display: block; margin-bottom: 6px; }
.commentary p { margin: 0 0 6px; max-width: 75ch; }
.frame .threshold-zone-counters { margin-top: var(--bn-space-sm); }
"""

SCRIPT = r"""
const RUN = __RUN__;
const BINS = 20, STEP = 0.05, GAP = 0.05;
const snap = (v) => Math.round(v / STEP) * STEP;
const bin = (c) => Math.max(0, Math.min(Math.floor(c / 0.05 + 1e-9), BINS - 1));

function histogram(el) {
  const bins = Array.from({ length: BINS }, () => []);
  RUN.forEach(([c, tint]) => bins[bin(c)].push(tint));
  el.style.setProperty('--bn-hist-stack', Math.max(...bins.map((b) => b.length)));
  el.innerHTML = bins.map((b) => '<div class="threshold-histogram-bin">' +
    b.map((t) => '<div class="threshold-histogram-square" style="background:var(--bn-' + t + '-1-bg)"></div>').join('') +
    '</div>').join('');
}

function counters(root, lower, upper) {
  const n = (f) => RUN.filter(([c]) => f(c)).length;
  root.querySelector('[data-c=ex]').textContent = n((c) => c < lower - 1e-9);
  root.querySelector('[data-c=te]').textContent = n((c) => c >= lower - 1e-9 && c < upper - 1e-9);
  root.querySelector('[data-c=ac]').textContent = n((c) => c >= upper - 1e-9);
}

function wire(root, draw) {
  const state = { lower: 0.30, upper: 0.60 };
  const track = root.querySelector('[data-track]');
  const set = (which, v) => {
    v = snap(Math.min(1, Math.max(0, v)));
    if (which === 'lower') v = Math.min(v, snap(state.upper - GAP));
    else v = Math.max(v, snap(state.lower + GAP));
    state[which] = v; draw(root, state); counters(root, state.lower, state.upper);
  };
  root.querySelectorAll('[data-thumb]').forEach((th) => {
    const which = th.dataset.thumb;
    th.addEventListener('pointerdown', (e) => {
      th.setPointerCapture(e.pointerId); th.focus();
      const move = (ev) => {
        const r = track.getBoundingClientRect();
        set(which, (ev.clientX - r.left) / r.width);
      };
      th.addEventListener('pointermove', move);
      th.addEventListener('pointerup', () => th.removeEventListener('pointermove', move), { once: true });
    });
    th.addEventListener('keydown', (e) => {
      const d = { ArrowLeft: -STEP, ArrowDown: -STEP, ArrowRight: STEP, ArrowUp: STEP }[e.key];
      if (d) { e.preventDefault(); set(which, state[which] + d); }
    });
  });
  draw(root, state); counters(root, state.lower, state.upper);
}

// Frame 0: the shipped slider.
function drawToday(root, s) {
  const pct = (v) => (v * 100) + '%';
  const seg = root.querySelectorAll('.threshold-slider-segment');
  seg[0].style.left = '0'; seg[0].style.width = pct(s.lower);
  seg[1].style.left = pct(s.lower); seg[1].style.width = pct(s.upper - s.lower);
  seg[2].style.left = pct(s.upper); seg[2].style.width = pct(1 - s.upper);
  root.querySelectorAll('[data-thumb]').forEach((th) => {
    const v = s[th.dataset.thumb];
    th.style.left = pct(v); th.setAttribute('aria-valuenow', v.toFixed(2));
    th.querySelector('.threshold-slider-label').textContent = v.toFixed(2);
  });
}

// Frames A and B: Levels.
function drawLevels(root, s) {
  const pct = (v) => (v * 100) + '%';
  const b = root.querySelectorAll('.lv-band');
  b[0].style.left = '0'; b[0].style.width = pct(s.lower);
  b[1].style.left = pct(s.lower); b[1].style.width = pct(s.upper - s.lower);
  b[2].style.left = pct(s.upper); b[2].style.width = pct(1 - s.upper);
  ['lower', 'upper'].forEach((w) => {
    root.querySelector('.lv-guide--' + w).style.left = pct(s[w]);
    const th = root.querySelector('[data-thumb=' + w + ']');
    th.style.left = pct(s[w]); th.setAttribute('aria-valuenow', s[w].toFixed(2));
    th.querySelector('.lv-value').textContent = s[w].toFixed(2);
  });
}

document.querySelectorAll('.threshold-histogram').forEach(histogram);
document.querySelectorAll('[data-frame=today]').forEach((r) => wire(r, drawToday));
document.querySelectorAll('[data-frame=levels]').forEach((r) => wire(r, drawLevels));

// Chrome: palette and scheme.
document.querySelectorAll('[name=pal]').forEach((i) => i.addEventListener('change', () =>
  document.documentElement.dataset.colorTheme = i.value));
document.querySelectorAll('[name=sch]').forEach((i) => i.addEventListener('change', () =>
  document.documentElement.style.colorScheme = i.value === 'auto' ? '' : i.value));
"""

COUNTERS = """
<div class="threshold-zone-counters">
  <span class="threshold-zone-counter threshold-zone-counter--exclude">Exclude
    <span class="threshold-zone-counter-count" data-c="ex"></span></span>
  <span class="threshold-zone-counter threshold-zone-counter--tentative">Tentative
    <span class="threshold-zone-counter-count" data-c="te"></span></span>
  <span class="threshold-zone-counter threshold-zone-counter--accept">Accept
    <span class="threshold-zone-counter-count" data-c="ac"></span></span>
</div>"""

AXIS = """
<div class="threshold-histogram-axis"><span>0.0</span><span>0.2</span><span>0.4</span>
<span>0.6</span><span>0.8</span><span>1.0</span></div>"""

TODAY = """
<div data-frame="today">
  <div class="threshold-histogram"></div>""" + AXIS + """
  <div class="threshold-slider">
    <div class="threshold-slider-track" data-track>
      <div class="threshold-slider-segment threshold-slider-segment--grey"></div>
      <div class="threshold-slider-segment threshold-slider-segment--amber"></div>
      <div class="threshold-slider-segment threshold-slider-segment--green"></div>
    </div>
    <div class="threshold-slider-thumb" data-thumb="lower" role="slider" tabindex="0"
      aria-label="Lower threshold" aria-valuemin="0" aria-valuemax="1">
      <span class="threshold-slider-label"></span></div>
    <div class="threshold-slider-thumb" data-thumb="upper" role="slider" tabindex="0"
      aria-label="Upper threshold" aria-valuemin="0" aria-valuemax="1">
      <span class="threshold-slider-label"></span></div>
  </div>""" + COUNTERS + """
</div>"""

# Pointer shapes, tip up at x = 0 of the thumb's centre line.
SHAPE_A = ('<svg width="14" height="16" viewBox="-7 0 14 16"><path class="lv-shape" '
           'd="M0 0.5 L6.5 6 L6.5 15.5 L-6.5 15.5 L-6.5 6 Z"/></svg>')
SHAPE_B = ('<svg width="40" height="24" viewBox="-20 0 40 24"><path class="lv-shape" '
           'd="M0 0.75 L5.5 6 L18.5 6 Q19.25 6 19.25 6.75 L19.25 22.5 Q19.25 23.25 18.5 23.25 '
           'L-18.5 23.25 Q-19.25 23.25 -19.25 22.5 L-19.25 6.75 Q-19.25 6 -18.5 6 L-5.5 6 Z"/></svg>')


def levels(variant: str, shape: str) -> str:
    thumbs = ""
    for which, label in (("lower", "Lower threshold"), ("upper", "Upper threshold")):
        thumbs += (
            '<div class="lv-thumb lv-thumb--' + which + '" data-thumb="' + which
            + '" role="slider" tabindex="0" aria-label="' + label
            + '" aria-valuemin="0" aria-valuemax="1">' + shape
            + '<span class="lv-value"></span></div>'
        )
    return (
        '<div data-frame="levels" class="lv lv--' + variant + '">'
        '<div class="lv-box" data-track>'
        '<div class="lv-band lv-band--grey"></div><div class="lv-band lv-band--amber"></div>'
        '<div class="lv-band lv-band--green"></div>'
        '<div class="threshold-histogram"></div>'
        '<div class="lv-guide lv-guide--lower"></div><div class="lv-guide lv-guide--upper"></div>'
        '</div><div class="lv-floor"></div>'
        '<div class="lv-rail">' + thumbs + '</div>' + COUNTERS + '</div>'
    )


FRAMES = [
    ("0 · today (shipped markup and CSS)", TODAY, """
<p>The track is a separate 4 px line under the histogram, with its own colours; the values
float above the thumbs and collide with the axis labels at 0.6 and 0.8.</p>"""),
    ("A · Levels, Pixelmator-true: filled pointers, value under each", levels("a", SHAPE_A), """
<p>The histogram is the control: the zones tint its ground grey, orange and green, the
pointers hang from its floor tip-up at the value, and a dotted guide in the pointer's
colour runs up through the squares, so you see which squares a line is about to cross.
The axis labels go: the two values are the only numbers that matter here.</p>
<p>The lower pointer is orange (the line where tentative starts), the upper green (where
accept starts). The 4 px track is gone; the counters stay.</p>"""),
    ("B · Levels, the value inside the pointer", levels("b", SHAPE_B), """
<p>Your suggestion: the number lives in the pointer, which widens to hold it. Outlined
rather than filled, so the figure is text colour on the dialog's ground: white on the
amber fill is 2:1 and dark on the green fill is not much better. The pointers are 38 px
wide, so at the minimum gap (0.05 = ~42 px here) they nearly touch; A never does.</p>"""),
]


def main() -> None:
    blocks = []
    for rel in CSS:
        text = (THEME / rel).read_text(encoding="utf-8")
        n = text.count("\n") + 1
        blocks.append("/* ════ bristlenose/theme/" + rel + " — lines 1–" + str(n) + " ════ */\n" + text)
    css = "\n".join(blocks) + NEW_CSS + CHROME_CSS

    frames = ""
    for title, body, note in FRAMES:
        frames += (
            '<section class="frame"><div class="frame-bar">' + title + '</div>'
            '<div class="frame-body">' + body + '</div></section>'
            '<aside class="commentary"><b class="lab">Commentary</b>' + note + '</aside>'
        )

    script = SCRIPT.replace("__RUN__", json.dumps(RUN))
    page = (
        '<!DOCTYPE html>\n<html lang="en" data-color-theme="default"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>AutoCode review: Levels-style slider</title>'
        "<!-- Generated by docs/mockups/autocode-levels-slider.gen.py; do not edit by hand. -->"
        "<style>" + css + "</style></head><body><div class='page'>"
        "<h1>The review dialog's slider, as Levels</h1>"
        "<p class='lede'>Pixelmator Pro's Levels control applied to the AutoCode review "
        "dialog's two thresholds. Every frame is live: drag a pointer, or focus it and use "
        "the arrow keys. Shipped theme CSS throughout; the Levels rules are the one block "
        "marked NEW.</p>"
        "<div class='bar'>Palette <label><input type=radio name=pal value=default checked>default</label>"
        "<label><input type=radio name=pal value=edo>edo</label> · Scheme "
        "<label><input type=radio name=sch value=auto checked>auto</label>"
        "<label><input type=radio name=sch value=light>light</label>"
        "<label><input type=radio name=sch value=dark>dark</label></div>"
        "<p class='key'>Framed panels are the product, drawn at the dialog's width. "
        "Hatched panels are commentary.</p>"
        + frames
        + "</div><script>" + script + "</script></body></html>\n"
    )
    OUT.write_text(page, encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
