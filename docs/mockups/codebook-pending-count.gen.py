#!/usr/bin/env python3
"""Generate docs/mockups/codebook-pending-count.html.

The Codebook lens sidebar's pending count (`.v2-nav-pending`, the proposals waiting for review on a
codebook's row) drawn in a dozen styles: the shipped grey pill, bare numbers in body or muted ink,
plain or bold, an outlined pill, and white on a coloured circle. Each style is drawn on the same
shipped sidebar, captured from a running `serve --dev` on 24 Nov 2026 (the trial run's name is
replaced with "Demo study"), with one row added so every state is on screen: the selected row, a
plain row, and a switched-off row with a three-digit count. The chrome bar of each frame prints the
count's live contrast against what is actually behind it.

The theme CSS, the capture and the locale reader are borrowed from the applied-slot generator beside
this one, so the two pages cannot drift apart.

    .venv/bin/python docs/mockups/codebook-pending-count.gen.py
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("applied_slot_gen", HERE / "codebook-applied-slot.gen.py")
assert _spec and _spec.loader
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

OUT = HERE / "codebook-pending-count.html"
E = base.E
t = base.t

# The capture's own width: the drag handle's aria-valuenow when it was taken.
SIDEBAR_WIDTH = 240

NIELSEN = (
    '<a href="#" class="toc-link codebook-toc-link v2-nav-row codebook-disabled" '
    'data-testid="bn-v2-nav-row-nielsen"><span class="v2-nav-text"><span class="codebook-toc-label">'
    "10 Usability Heuristics for User Interface Design</span>"
    '<span class="v2-nav-provenance">Jakob Nielsen</span></span>'
    '<span class="v2-nav-pending">128</span><span class="sw mini offstate" role="switch" tabindex="0" '
    'aria-checked="false" aria-label="10 Usability Heuristics for User Interface Design"></span></a>'
)

# (class, name, what it is). Order: shipped, the bare numbers, the pills, the circles.
VARIANTS = [
    ("pv-shipped", "Shipped", "grey pill (badge colours), micro, regular weight"),
    ("pv-bare-muted", "Bare, muted", "no shape; muted ink, regular"),
    ("pv-bare-muted-bold", "Bare, muted, bold", "no shape; muted ink, emphasis weight"),
    ("pv-bare-muted-selink", "Bare, muted; ink when selected", "no shape; muted ink, body ink on the selected row"),
    ("pv-bare-ink", "Bare, ink", "no shape; body ink, regular"),
    ("pv-bare-ink-bold", "Bare, ink, bold", "no shape; body ink, emphasis weight"),
    ("pv-pill-bold", "Pill, bold", "the shipped pill at emphasis weight"),
    ("pv-pill-outline", "Pill, outlined", "no fill; a hairline ring in the hover border colour"),
    ("pv-dot-accent", "White on accent", "accent circle, white figures, emphasis weight"),
    ("pv-dot-accent-regular", "White on accent, regular", "accent circle, white figures, regular"),
    ("pv-dot-muted", "White on muted", "muted-ink circle, white figures, emphasis weight"),
    ("pv-dot-ink", "Inverted", "body-ink circle, background-colour figures, emphasis weight"),
    ("pv-dot-paleaccent", "Accent on pale accent", "accent figures on a 14% accent tint, emphasis weight"),
]

NEW_CSS = """
/* ════ NEW — the candidate styles. Tokens only; each overrides the shipped .v2-nav-pending. ════ */
.side { width: {W}px; }
.side .toc-sidebar { position: static; width: {W}px; height: auto; min-height: 0; }
/* The open state, as `.layout.toc-open .toc-sidebar` gives it in the app (sidebar.css:261);
   the toolbar bleed's negative margin has no toolbar to bleed under here. */
.side .toc-sidebar { visibility: visible; opacity: 1; margin-top: 0; padding-top: var(--bn-space-xl); }
.side .toc-drag-handle { display: none; }

.pv-bare-muted .v2-nav-pending, .pv-bare-muted-bold .v2-nav-pending, .pv-bare-muted-selink .v2-nav-pending,
.pv-bare-ink .v2-nav-pending, .pv-bare-ink-bold .v2-nav-pending {
    background: none; padding: 0; border-radius: 0;
}
.pv-bare-muted .v2-nav-pending, .pv-bare-muted-bold .v2-nav-pending,
.pv-bare-muted-selink .v2-nav-pending { color: var(--bn-colour-muted); }
.pv-bare-muted-selink .v2-nav-row.active .v2-nav-pending { color: var(--bn-colour-text); }
.pv-bare-ink .v2-nav-pending, .pv-bare-ink-bold .v2-nav-pending { color: var(--bn-colour-text); }
.pv-bare-muted-bold .v2-nav-pending, .pv-bare-ink-bold .v2-nav-pending,
.pv-pill-bold .v2-nav-pending { font-weight: var(--bn-weight-emphasis); }

.pv-pill-outline .v2-nav-pending {
    background: none; box-shadow: inset 0 0 0 1px var(--bn-colour-border-hover);
}

/* A circle for one or two figures, a pill beyond: min-width equals the height. */
.pv-dot-accent .v2-nav-pending, .pv-dot-accent-regular .v2-nav-pending,
.pv-dot-muted .v2-nav-pending, .pv-dot-ink .v2-nav-pending, .pv-dot-paleaccent .v2-nav-pending {
    display: inline-flex; align-items: center; justify-content: center; box-sizing: border-box;
    min-width: 1.6em; height: 1.6em; padding: 0 0.45em; line-height: 1;
    font-weight: var(--bn-weight-emphasis);
}
.pv-dot-accent .v2-nav-pending, .pv-dot-accent-regular .v2-nav-pending {
    background: var(--bn-colour-accent); color: #fff;
}
.pv-dot-accent-regular .v2-nav-pending { font-weight: var(--bn-weight-normal); }
.pv-dot-muted .v2-nav-pending { background: var(--bn-colour-muted); color: #fff; }
.pv-dot-ink .v2-nav-pending { background: var(--bn-colour-text); color: var(--bn-colour-bg); }
.pv-dot-paleaccent .v2-nav-pending {
    background: color-mix(in srgb, var(--bn-colour-accent) 14%, transparent); color: var(--bn-colour-accent);
}

/* The owner's rule (24 Nov): outlined pill in ink when the codebook is on; the same at the
   switched-off opacity when it is off, selected or not; white on accent, regular, on the selected row
   when it is on; nothing at zero (shipped: the span is not rendered). */
/* ONE box for every state, matched to the mini switch beside it (26 x 15 px, radius 7.5,
   organisms/codebook-v2.css:153): 15 px high, at least 15 px wide (a circle for one figure, a pill for
   more), regular weight, the switch's radius. A state changes only fill, figure colour and opacity, so
   nothing moves when a row is selected or switched off. The row already centres its children. */
.pv-rule .v2-nav-pending {
    display: inline-flex; align-items: center; justify-content: center; box-sizing: border-box;
    height: 15px; min-width: 15px; padding: 0 4px; border-radius: 7.5px; line-height: 1;
    font-weight: var(--bn-weight-normal);
    background: none; box-shadow: inset 0 0 0 1px var(--bn-colour-border-hover);
    color: var(--bn-colour-text);
}
/* The slot: a fixed width for three figures, the pill set against the switch inside it, so the title's
   width never depends on the number (9 to 12 to 128) and never re-wraps as proposals are reviewed.
   It takes the count's own size, so `ch` is one tabular figure. */
.pv-rule .v2-nav-pending-slot {
    flex-shrink: 0; display: inline-flex; justify-content: flex-end;
    font-size: var(--bn-text-micro); font-variant-numeric: tabular-nums;
    min-width: calc(3ch + 9px);
}
html[data-count-size="caption"] .pv-rule .v2-nav-pending-slot { font-size: var(--bn-text-caption); }
.pv-rule .v2-nav-row.codebook-disabled .v2-nav-pending { opacity: var(--bn-opacity-off); }
/* The theme's own rule for muting readable text (theme/gotchas.md: a colour token, never opacity),
   offered as a switch in the mockup controls: muted figures and the plain border, full opacity. */
.pv-rule.off-muted .v2-nav-row.codebook-disabled .v2-nav-pending {
    opacity: 1; color: var(--bn-colour-muted); box-shadow: inset 0 0 0 1px var(--bn-colour-border);
}
.pv-rule .v2-nav-row.active:not(.codebook-disabled) .v2-nav-pending {
    background: var(--bn-colour-accent); color: #fff;
    box-shadow: inset 0 0 0 1px var(--bn-colour-accent);
}

/* The size toggle in the chrome bar: micro is shipped, caption is one step up. */
html[data-count-size="caption"] .v2-nav-pending { font-size: var(--bn-text-caption); }
""".replace("{W}", str(SIDEBAR_WIDTH))

CHROME_EXTRA = """
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax({W}px, 1fr)); gap: 1.2rem; }
.grid .frame { margin: 0; }
.grid .surface { padding: 0.75rem 0; display: flex; justify-content: center; }
.grid .chrome { display: block; }
.grid .chrome .what { display: block; }
.grid .chrome .delta { display: block; margin: 0.25rem 0 0; color: light-dark(#666, #9a9a9a); }
.delta .low { color: light-dark(#b00020, #ff6b81); font-weight: 700; }
.play { display: flex; flex-wrap: wrap; gap: 1.2rem; align-items: flex-start; }
.play .frame { margin: 0; width: {PW}px; }
.play .surface { padding: 0.75rem 0; display: flex; justify-content: center; }
.play .chrome { display: block; min-height: 11em; box-sizing: border-box; }
.play .chrome .what, .play .chrome .delta { display: block; }
.play .chrome .delta { margin-top: 0.25rem; color: light-dark(#666, #9a9a9a); }
.controls { font: 12px/1.6 ui-monospace, Menlo, monospace; color: light-dark(#444, #bbb); padding: 0.9rem 1.1rem;
  background: light-dark(#f3f4f6, #2a2a2b); border-radius: 10px; min-width: 16rem;
  box-shadow: 0 0 0 1px light-dark(rgb(0 0 0 / 0.12), rgb(255 255 255 / 0.12)); }
.controls h3 { font: 700 11px ui-monospace, Menlo, monospace; letter-spacing: 0.08em; text-transform: uppercase;
  margin: 0 0 0.5rem; color: light-dark(#8a4b00, #f0b45a); }
.controls label { display: flex; justify-content: space-between; gap: 1rem; align-items: center; }
.controls input[type=number] { width: 4.5rem; font: inherit; }
.controls .hint { margin-top: 0.6rem; color: light-dark(#777, #999); max-width: 17rem; }
.controls button { font: inherit; margin-top: 0.6rem; }
/* Measurement only: no colour transitions in the frames, so a palette switch is read at rest. */
.side, .side * { transition: none !important; }
""".replace("{W}", str(SIDEBAR_WIDTH + 40)).replace("{PW}", str(SIDEBAR_WIDTH + 60))

SCRIPT = """
(() => {
  const TENT_ONE = __TENT_ONE__, TENT_OTHER = __TENT_OTHER__;
  const root = document.documentElement;
  const set = (k, v) => { if (v === '') root.removeAttribute(k); else root.setAttribute(k, v); };
  document.getElementById('c-platform').onchange = e => { set('data-platform', e.target.value); later(); };
  document.getElementById('c-palette').onchange = e => { set('data-color-theme', e.target.value); later(); };
  document.getElementById('c-scheme').onchange = e => { set('data-scheme', e.target.value); later(); };
  document.getElementById('c-size').onchange = e => { set('data-count-size', e.target.value); later(); };
  // Resolve any computed colour (rgb(), rgba(), color(srgb …)) to [r, g, b, a] in 0–1.
  const probe = document.createElement('canvas').getContext('2d');
  function rgba(css) {
    probe.clearRect(0, 0, 1, 1); probe.fillStyle = '#000'; probe.fillStyle = css;
    probe.fillRect(0, 0, 1, 1); const d = probe.getImageData(0, 0, 1, 1).data;
    return [d[0] / 255, d[1] / 255, d[2] / 255, d[3] / 255];
  }
  function backdrop(el) {
    // Composite every background from the root down to the element, so a tint over a row counts.
    const chain = []; for (let n = el; n && n.nodeType === 1; n = n.parentElement) chain.unshift(n);
    let c = rgba(getComputedStyle(document.body).backgroundColor);
    for (const n of chain) {
      const b = rgba(getComputedStyle(n).backgroundColor);
      c = [0, 1, 2].map(i => b[i] * b[3] + c[i] * (1 - b[3])).concat([1]);
    }
    return c;
  }
  const lum = c => { const f = v => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  function measure() {
    document.querySelectorAll('.frame.count').forEach(f => {
      const out = [];
      f.querySelectorAll('.v2-nav-pending').forEach(p => {
        const row = p.closest('.v2-nav-row');
        const where = (row.classList.contains('active') ? 'selected' : '') + (row.classList.contains('codebook-disabled') ? (row.classList.contains('active') ? ', off' : 'off') : (row.classList.contains('active') ? '' : 'on'));
        const bg = backdrop(p); const op = parseFloat(getComputedStyle(p).opacity);
        const raw = rgba(getComputedStyle(p).color); const a = raw[3] * op;
        const fg = [0, 1, 2].map(i => raw[i] * a + bg[i] * (1 - a));
        const r = ratio(fg, bg); const pr = p.getBoundingClientRect();
        const sw = row.querySelector('.sw'); const sr = sw ? sw.getBoundingClientRect() : null;
        const dy = sr ? (pr.top + pr.height / 2) - (sr.top + sr.height / 2) : 0;
        const s = where + ' ' + p.textContent + ': ' + r.toFixed(2) + ':1, ' + pr.width.toFixed(1) + '×' + pr.height.toFixed(1) + 'px, centre ' + (dy >= 0 ? '+' : '') + dy.toFixed(1);
        out.push(r < 4.5 ? '<span class="low">' + s + '</span>' : s);
      });
      f.querySelector('.delta').innerHTML = 'contrast, live: ' + out.join(' · ');
    });
  }
  function later() { requestAnimationFrame(() => requestAnimationFrame(measure)); }
  // The playground: two frames, one state. A row click selects it, a switch click turns it on or off,
  // the number fields set each codebook's count (0 removes the count, as shipped).
  const play = document.querySelector('.play');
  if (play) {
    const sides = [...play.querySelectorAll('.side')];
    const rowsOf = id => sides.map(f => f.querySelector('[data-testid="bn-v2-nav-row-' + id + '"]')).filter(Boolean);
    const label = n => (n === 1 ? TENT_ONE : TENT_OTHER).replace('{n}', n);
    const keepSlot = () => document.getElementById('c-zero').value === 'keep';
    function setCount(id, n) {
      rowsOf(id).forEach(row => {
        const slotted = !!row.closest('.pv-rule');
        let span = row.querySelector('.v2-nav-pending');
        // At zero: nothing shows. The rule frame keeps its empty slot unless the control says otherwise,
        // so reviewing the last proposal does not re-wrap the title either.
        if (!(n > 0)) {
          if (span) { if (slotted && keepSlot()) span.remove(); else (slotted ? span.parentElement : span).remove(); }
          return;
        }
        if (!span) {
          span = document.createElement('span'); span.className = 'v2-nav-pending';
          const slot = slotted ? row.querySelector('.v2-nav-pending-slot') : null;
          if (slot) slot.appendChild(span);
          else {
            let host = span;
            if (slotted) { host = document.createElement('span'); host.className = 'v2-nav-pending-slot'; host.appendChild(span); }
            row.insertBefore(host, row.querySelector('.sw'));
          }
        }
        span.textContent = String(n);
        if (span.closest('.pv-rule')) { span.title = label(n); span.setAttribute('aria-label', label(n)); }
      });
      later();
    }
    function act(target) {
      const a = target.closest('.v2-nav-row'); if (!a) return false;
      const id = a.dataset.testid.replace('bn-v2-nav-row-', '');
      if (target.closest('.sw')) {
        const on = a.classList.contains('codebook-disabled');
        rowsOf(id).forEach(r => {
          r.classList.toggle('codebook-disabled', !on);
          const sw = r.querySelector('.sw'); sw.classList.toggle('offstate', !on); sw.setAttribute('aria-checked', String(on));
        });
      } else {
        sides.forEach(f => f.querySelectorAll('.v2-nav-row').forEach(r => { r.classList.remove('active'); r.removeAttribute('aria-current'); }));
        rowsOf(id).forEach(r => { r.classList.add('active'); r.setAttribute('aria-current', 'location'); });
      }
      later(); return true;
    }
    play.addEventListener('click', e => { if (e.target.closest('.v2-nav-row')) { e.preventDefault(); act(e.target); } });
    play.addEventListener('keydown', e => { if ((e.key === ' ' || e.key === 'Enter') && act(e.target)) e.preventDefault(); });
    const inputs = [...play.querySelectorAll('input[data-book]')];
    inputs.forEach(i => i.addEventListener('input', () => setCount(i.dataset.book, parseInt(i.value || '0', 10))));
    document.getElementById('c-reset').onclick = () => location.reload();
    document.getElementById('c-off').onchange = e => { play.querySelector('.pv-rule').classList.toggle('off-muted', e.target.value === 'off-muted'); later(); };
  }
  window.addEventListener('load', measure);
  document.fonts && document.fonts.ready.then(measure);
})();
"""


def sidebar() -> str:
    """The captured sidebar, Nielsen's switched-off row added after Laws of UX, each count labelled."""
    sb = base.UXR["sidebar"]
    yab = re.search(r'<a [^>]*data-testid="bn-v2-nav-row-yablonski".*?</a>', sb, re.S)
    assert yab, "the Laws of UX row is not in the capture"
    return sb[: yab.end()] + NIELSEN + sb[yab.end() :]


def labelled(sb: str) -> str:
    """The proposal: the count says what it is to a pointer and to VoiceOver (shipped key)."""
    def add(m: re.Match[str]) -> str:
        n = int(m.group(1))
        key = "codebook.tentativeCount_one" if n == 1 else "codebook.tentativeCount_other"
        label = E(t(key, count=n))
        return f'<span class="v2-nav-pending" title="{label}" aria-label="{label}">{n}</span>'

    return re.sub(r'<span class="v2-nav-pending">(\d+)</span>', add, sb)


def slotted(sb: str) -> str:
    """The proposal's markup: each count inside a fixed-width slot (`.v2-nav-pending-slot`)."""
    return re.sub(r'(<span class="v2-nav-pending"[^>]*>\d+</span>)', r'<span class="v2-nav-pending-slot">\1</span>', sb)


def frame(cls: str, name: str, what: str, sb: str) -> str:
    return (
        f'<figure class="frame count"><figcaption class="chrome"><span class="tag">{E(name)}</span>'
        f'<span class="what">{E(what)}</span><span class="delta"></span></figcaption>'
        f'<div class="surface"><div class="side {cls}">{sb}</div></div></figure>'
    )


def playground(sb: str) -> str:
    """Shipped beside the owner's rule, one state for both, and the controls to drive it."""
    shipped = (
        '<figure class="frame count"><figcaption class="chrome"><span class="tag">Shipped</span>'
        '<span class="what">grey pill, whatever the row\'s state</span><span class="delta"></span></figcaption>'
        f'<div class="surface"><div class="side pv-shipped">{sb}</div></div></figure>'
    )
    rule = (
        '<figure class="frame count"><figcaption class="chrome"><span class="tag">Your rule</span>'
        '<span class="what">on: outlined pill · off: the same at half opacity, selected or not · selected and on: white on accent</span>'
        '<span class="delta"></span></figcaption>'
        f'<div class="surface"><div class="side pv-rule">{slotted(labelled(sb))}</div></div></figure>'
    )
    books = [("uxr", "Bristlenose UXR Codebook", 9), ("yablonski", "Laws of UX", 5),
             ("nielsen", "10 Usability Heuristics", 128)]
    fields = "".join(
        f'<label>{E(name)} <input type="number" min="0" max="999" value="{n}" data-book="{key}"></label>'
        for key, name, n in books
    )
    controls = (
        '<div class="controls"><h3>Mockup controls</h3>' + fields
        + '<div class="hint">Click a row to select it; click its switch to turn it on or off. Set a count to 0 to '
        "see the row with nothing waiting. Emotional signals and the project's own tags never have proposals.</div>"
        '<label style="margin-top:0.6rem">Off state <select id="c-off"><option value="" selected>half opacity (your rule)</option>'
        '<option value="off-muted">muted ink (theme rule)</option></select></label>'
        '<label>At zero <select id="c-zero"><option value="keep" selected>keep the empty slot</option>'
        '<option value="give">give the title the space</option></select></label>'
        '<button type="button" id="c-reset">Reset</button></div>'
    )
    return f'<div class="play">{shipped}{rule}{controls}</div>'


def build() -> str:
    css = "".join(base.css_block(f) for f in base.CSS_FILES)
    css += "".join(base.css_rule("templates/report.css", s) for s in base.REPORT_RULES)
    sb = sidebar()
    frames = "".join(
        frame(cls, name, what, sb if cls == "pv-shipped" else labelled(sb)) for cls, name, what in VARIANTS
    )
    commentary = base.commentary
    script = SCRIPT.replace("__TENT_ONE__", json.dumps(t("codebook.tentativeCount_one", count="{n}"))).replace(
        "__TENT_OTHER__", json.dumps(t("codebook.tentativeCount_other", count="{n}"))
    )
    play = playground(sb)
    return f"""<!DOCTYPE html>
<html lang="en" data-platform="desktop" data-color-theme="edo">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codebook pending count</title>
<style>
{css}
{NEW_CSS}
{base.CHROME_CSS}
{CHROME_EXTRA}
</style>
</head>
<body class="mock">
<div class="bar">
  <label>platform <select id="c-platform"><option value="desktop" selected>Mac</option><option value="">web</option></select></label>
  <label>palette <select id="c-palette"><option value="edo" selected>edo (Mac default)</option><option value="default">default</option></select></label>
  <label>scheme <select id="c-scheme"><option value="" selected>auto</option><option value="light">light</option><option value="dark">dark</option></select></label>
  <label>count size <select id="c-size"><option value="" selected>micro (shipped)</option><option value="caption">caption</option></select></label>
</div>
<div class="wrap">
<h1 class="mock-title">Codebook sidebar: the pending count, your rule and thirteen styles</h1>
<p class="key">For discussion. <b>Framed panes are the product</b>: the Codebook lens sidebar captured from a running
<code>serve --dev</code> (24 Nov 2026, a private trial run renamed “Demo study”) at shipped CSS and its captured width,
{SIDEBAR_WIDTH} px. Only the count's style changes from frame to frame. One row is added to every frame so each state is
on screen: Nielsen, switched off, with 128 waiting. The real counts are UXR 9 (the selected row) and Laws of UX 5.
<b>Hatched blocks are commentary.</b> Each frame's bar prints the count's contrast, live, against whatever is behind
it (the row, the selection, the sidebar); under 4.5:1 is in red. Generated by <code>codebook-pending-count.gen.py</code>;
regenerate, don't edit.</p>

{commentary("what the count is", '''<p>The number of a codebook's proposals still waiting for review (D10): its
tentative tags. Shipped as a grey pill in the badge colours, micro size, regular weight, between the title and the switch
(<code>organisms/codebook-v2.css:96</code>, <code>CodebookV2Sidebar.tsx:199</code>). It has no tooltip and no spoken
label: VoiceOver reads a stray “9” after the codebook's name. Every frame but the first adds both, from the shipped key
<code>codebook.tentativeCount</code> (“9 tentative”, 21 locales); hover a count to see it. The style is the question
here; the label is owed whichever style wins.</p>''')}

<h2 class="step">1 · Your rule, to play with</h2>
{play}
{commentary("your rule (owner, 24 Nov)", '''<p><b>On:</b> the outlined pill in ink. <b>Off:</b> the same pill at the
switched-off opacity (<code>--bn-opacity-off</code>, 0.5, the card's own knock-back). <b>Selected and on</b> (the codebook whose
page is open): white on accent, regular weight. <b>Selected and off:</b> the off pill, as any switched-off row (owner, 24 Nov). <b>Zero:</b> nothing shows. <b>Nothing jumps</b> (owner, 24 Nov): every state draws the same box, the
switch's 15 px height and radius, at least 15 px wide, regular weight, centred on the switch; only fill, figure colour
and opacity change. And the count sits in a slot sized for three figures, so the title keeps one width from 1 to 999,
and at zero too while the empty slot is kept (measured: 142.1 px for every count on Nielsen's row, the row 67.9 px
throughout). The controls also flip the off state to the theme's own muting rule (muted ink, not opacity:
<code>theme/gotchas.md</code>, “Mute readable text with a colour token, never with <code>opacity</code>”), which
clears 4.5:1 except on the selected row in light mode (4.2:1), and let the title have the slot's space back at zero.
Both frames share one state:
click a row to select it, click a switch to turn it on or off, set the counts on the right; Tab and Space work too.
<b>Read the bars:</b> white on accent clears 4.5:1 only in Edo light (6.9:1); default light is 4.0:1, Edo dark 2.9:1,
default dark 3.7:1. The switched-off pill at half opacity is under 4.5:1 in all four: 3.1:1 Edo light, 4.3:1 Edo dark, 3.3:1
default light, 4.3:1 default dark; selected and off, on the selection's darker capsule, 2.9 to 4.0:1 (the on
pill is 11:1 or more everywhere). WCAG excuses text in a <i>disabled</i>
control, but a switched-off row is still a live link to its page, so the excuse probably does not cover it. Measured
24 Nov at the Mac scale, micro size.</p>''')}

<h2 class="step">2 · Thirteen styles, side by side</h2>
<div class="grid">
{frames}
</div>

{commentary("what to look for (measured 24 Nov, Mac scale, micro size)", '''<p><b>The shipped pill disappears
on the selected row.</b> Its fill is the badge background, and the selected row's capsule is nearly the same colour:
<code>#f3f4f6</code> on <code>#efefef</code> in the default palette, <code>#e8dfc9</code> on <code>#e6ddc9</code> in Edo,
the Mac's default. The figure stays readable; the pill's shape does not, so the selected codebook's count reads as a bare
number and every other row's as a pill.</p>
<p><b>Contrast</b>, the lowest of the three rows, against 4.5:1 (text this small has no large-text allowance):</p>
<table><thead><tr><th>style</th><th>Edo light</th><th>Edo dark</th><th>default light</th><th>default dark</th></tr></thead><tbody>
<tr><td>shipped pill, bold pill, outlined pill</td><td>8.8+</td><td>7.3+</td><td>9.0+</td><td>9.6+</td></tr>
<tr><td>bare, ink (regular or bold)</td><td>11.8</td><td>11.3</td><td>15.1</td><td>11.4</td></tr>
<tr><td>bare, muted (regular or bold)</td><td><b>4.2</b> selected row</td><td>5.5</td><td><b>4.2</b> selected row</td><td>5.6</td></tr>
<tr><td>bare, muted; ink when selected</td><td>5.1</td><td>6.3</td><td>4.6</td><td>6.3</td></tr>
<tr><td>white on accent</td><td>6.9</td><td><b>2.9</b></td><td><b>4.0</b></td><td><b>3.7</b></td></tr>
<tr><td>white on muted</td><td>5.7</td><td><b>2.6</b></td><td>4.8</td><td><b>2.5</b></td></tr>
<tr><td>inverted</td><td>15.4</td><td>13.8</td><td>17.4</td><td>13.8</td></tr>
<tr><td>accent on pale accent</td><td><b>4.2</b></td><td><b>4.1</b></td><td><b>2.9</b></td><td><b>3.3</b></td></tr>
</tbody></table>
<p><b>Muted ink is what the codebook page already uses for a tentative count</b> (the tag rows: accepted in ink,
tentative-only in muted, <code>TagRow.tsx</code>), so a muted bare number says the same thing in the same colour in both
places, but it fails on the selected row in light mode, where the capsule darkens what is behind it. Recent macOS
sidebars (Mail's unread counts, for one) draw a plain grey figure, not a capsule: worth a glance at your own Mail.
<b>White on a coloured circle</b> is the notification badge: it says “unread, act now”, louder than proposals need (they
wait, nothing is lost), and it fails in three of four schemes. <b>Bold</b> helps a bare number hold its own beside the
switch at micro size; try the caption size in the bar too.</p>
<p><b>My pick: bare, muted; ink when selected</b>, with the label. It is the page's tentative colour wherever it passes,
the selected row's ink where muted would not, never a shape that vanishes, and not needy. If one colour everywhere matters
more than matching the page, <b>bare, ink</b> passes in every scheme.</p>''')}
</div>
<script>{script}</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(base.ROOT)}")
