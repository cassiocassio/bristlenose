"""Build docs/mockups/discussion-selected-column.html — the "you are here" column, options.

The shipped 0.40.0 navigator marks the selected session's cells with a 1.5px accent ring
(`.dl-cell.here`, discussion.css). In the strip (6px cells on an 8px pitch) the ring swallows the
gap and reads as heavy blue lozenges (owner, 18 Oct 2026, screenshots of Talismanic). This page
draws the shipped navigator — shipped theme + discussion.css verbatim, the product's own markup —
and five treatments of the selected column, each scoped by a class on the lens so one markup
draws all five. Session #2 is selected throughout.

    .venv/bin/python experiments/discussion-all-sessions/selected_column.py
"""

from __future__ import annotations

import html
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import build as B  # noqa: E402  (the overnight mockup's study data and helpers)

from bristlenose.stages.s12_render.theme_assets import load_default_css  # noqa: E402

OUT = ROOT / "docs/mockups/discussion-selected-column.html"
e = html.escape
KEY_MEASURE = "Fewer → more quotes"  # "in this study" removed (owner, 18 Oct 2026)


# ── the product's rules, in Python (model.ts: yieldThirds, shadeStep, barShare) ──

def thirds(sessions):
    v = sorted(q for _t, items in B.SECTIONS for it in items for s in sessions
               if s.n in B.asked(it, sessions) and (q := B.yield_of(s, it.id)[0]) > 0)
    if not v:
        return (0, 0, 0)
    n = len(v)
    return (v[math.ceil(n / 3) - 1], v[math.ceil(2 * n / 3) - 1], v[-1])


def step(q, t):
    if q <= 0:
        return 0
    low, mid, mx = t
    if mx == low:
        return 2
    if q >= mx:
        return 3
    return 1 if q <= low else 2 if q <= mid else 3


def bar_pct(q, mx):
    return round(100 * math.log1p(q) / math.log1p(mx)) if q and mx else 0


# ── the navigator, as DiscussionLens.tsx renders it ──

def badge(code, extra=""):
    return (f'<span class="bn-person-badge{extra}"><span class="bn-speaker-badge--split">'
            f'<span class="bn-speaker-badge-code">{e(code)}</span></span></span>')


def key():
    return ('<div class="bn-pipeline-key dl-key" role="note" aria-label="Key">'
            '<div class="bn-pipeline-key-group">'
            '<span class="bn-pipeline-key-item"><span class="dl-mk"><span class="dl-dot"></span></span>Asked as planned</span>'
            '<span class="bn-pipeline-key-item"><span class="dl-mk"><span class="dl-dot hollow"></span></span>Planned, never asked</span>'
            '<span class="bn-pipeline-key-item"><span class="dl-mk">+</span>Not in your guide</span></div>'
            '<div class="bn-pipeline-key-group">'
            '<span class="bn-pipeline-key-item"><span class="dl-cell s0"></span>Not asked</span>'
            '<span class="bn-pipeline-key-item"><span class="dl-cell s1"></span><span class="dl-cell s2"></span>'
            f'<span class="dl-cell s3"></span>{e(KEY_MEASURE)}</span></div>'
            '<div class="bn-pipeline-key-group"><span class="bn-pipeline-key-item dl-key-grey">'
            "Grey: not asked in this session</span></div></div>")


def grid_head(sessions, current):
    heads = "".join(
        f'<span class="dl-slot{" here" if s.n == current else ""}"><span class="dl-head-cell">'
        + (f'<span class="bn-person-badge-here">{badge(str(s.n), " bn-person-badge-compact")}</span>'
           if s.n == current else badge(str(s.n), " bn-person-badge-compact"))
        + "</span></span>" for s in sessions)
    return (f'<div class="dl-grid-head" aria-hidden="true"><span class="dl-grid-head-l">Sessions</span>'
            f'<span class="dl-cells">{heads}</span><span class="dl-head-bar"></span></div>')


def nav(sessions, current, tier):
    t = thirds(sessions)
    row_totals = {it.id: sum(B.yield_of(s, it.id)[0] for s in sessions if s.n in B.asked(it, sessions))
                  for _t, items in B.SECTIONS for it in items}
    mx = max(row_totals.values()) or 1
    parts = [key()]
    if tier == "grid":
        parts.append(grid_head(sessions, current))
    for title, items in B.SECTIONS:
        rows = []
        for it in items:
            sids = B.asked(it, sessions)
            cls = ["toc-link", "dl-row"]
            if not sids:
                cls.append("dim")
            elif current not in sids:
                cls.append("ghost")
            if it.mark == "hollow":
                cls.append("unasked")
            mk = "+" if it.mark == "plus" else f'<span class="dl-dot{" hollow" if it.mark == "hollow" else ""}"></span>'
            cells = ""
            if tier != "bar":
                cells = '<span class="dl-cells">' + "".join(
                    f'<span class="dl-slot{" here" if s.n == current else ""}">'
                    f'<button type="button" tabindex="-1" class="dl-cell s{step(B.yield_of(s, it.id)[0] if s.n in sids else 0, t)}'
                    f'{" here" if s.n == current else ""}"'
                    f'{"" if s.n in sids else " aria-disabled=\"true\""}></button></span>'
                    for s in sessions) + "</span>"
            total = row_totals[it.id]
            bar = (f'<span class="tag-micro-bar" style="width:{bar_pct(total, mx)}%;background-color:var(--dl-bar)"></span>'
                   if total else "")
            rows.append(
                f'<div class="{" ".join(cls)}"><button type="button" class="dl-row-btn"><span class="dl-mk">{mk}</span>'
                f'<span class="dl-tx">{e(it.text)}</span></button><span class="dl-measure">{cells}'
                f'<span class="tag-bar-area"><span class="dl-bar-box">{bar}</span>'
                f'<span class="tag-count">{total}</span></span></span></div>')
        parts.append(f'<div role="group"><h2 class="toc-heading">{e(title)}</h2>{"".join(rows)}</div>')
    return f'<nav class="dl-nav toc-sidebar-body">{"".join(parts)}</nav>'


VARIANTS = [
    ("a", "A — today: the accent ring",
     "The shipped rule. In the strip the 1.5px ring plus its 1px offset is wider than the 2px gap, so it "
     "touches the neighbouring cells and the column reads as a chain of blue lozenges."),
    ("b", "B — a pale wash behind the column",
     "A pale accent band behind the selected session's slot, the full height of every row, so the column reads "
     "as one vertical stripe (broken at section headings). The cells are untouched, so the shading reads exactly "
     "as in All. Costs a slot wrapper round each cell in the product."),
    ("c", "C — the column's cells tinted grey-blue",
     "No ring, no wash: the selected column's own cells take a blue-grey version of the ramp (and a blue-grey "
     "keyline when empty). The quietest change; the column is found by colour alone, so it leans on the head "
     "badge (grid) and the session bar."),
    ("d", "D — a lighter wash and a lighter tint",
     "B and C together, each at half strength: the band says where, the tint ties the cells to it."),
    ("e", "E — nothing on the column",
     "No column treatment at all: the session bar says which session is open, the grid's head badge is lit, and "
     "rows that session never asked are already grey. The lightest; the strip has no column marker."),
]

VARIANT_CSS = r"""
/* ════ PROPOSED — options for the selected column. .dl-slot wraps each cell (and each grid head) on the
   pitch; only B and D need it in the product. Each variant is scoped by .m-v-<x> on the lens. ════ */
.dl-slot { display: flex; align-items: center; justify-content: center; align-self: stretch; }
/* A slot fills its row's height, through the row's own vertical padding, so a wash is one band. */
.dl-nav .dl-row .dl-measure { align-self: stretch; align-items: stretch; }
.dl-nav .dl-row .dl-measure .tag-bar-area { align-self: center; }
.dl-nav .dl-row .dl-cells { align-items: stretch; }
.dl-nav .dl-row .dl-slot { margin-block: -0.2rem; padding-block: 0.2rem; }
.dl-grid-head .dl-cells { align-items: stretch; }
.dl-grid-head .dl-slot { margin-block: calc(-1 * var(--bn-space-xs)); padding-block: var(--bn-space-xs); }

/* A — today (shipped): nothing to override. */

/* B — the wash; the ring goes. */
.m-v-b .dl-cell.here, .m-v-c .dl-cell.here, .m-v-d .dl-cell.here, .m-v-e .dl-cell.here { outline: none; }
.m-v-b .dl-slot.here { background: color-mix(in srgb, var(--bn-colour-accent) 16%, var(--bn-colour-inspector-bg)); }

/* C — tinted cells (blue-grey ramp), keyline tinted when empty. */
.m-v-c .dl-cell.here.s0 { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--bn-colour-accent) 55%, var(--bn-colour-inspector-bg)); }
.m-v-c .dl-cell.here.s1 { background: color-mix(in srgb, var(--bn-colour-accent) 45%, var(--bn-colour-muted)); }
.m-v-c .dl-cell.here.s2 { background: color-mix(in srgb, var(--bn-colour-accent) 45%, color-mix(in srgb, var(--bn-colour-text) 50%, var(--bn-colour-muted))); }
.m-v-c .dl-cell.here.s3 { background: color-mix(in srgb, var(--bn-colour-accent) 45%, var(--bn-colour-text)); }

/* D — half of each. */
.m-v-d .dl-slot.here { background: color-mix(in srgb, var(--bn-colour-accent) 10%, var(--bn-colour-inspector-bg)); }
.m-v-d .dl-cell.here.s0 { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--bn-colour-accent) 30%, color-mix(in srgb, var(--bn-colour-muted) 50%, var(--bn-colour-inspector-bg))); }
.m-v-d .dl-cell.here.s1 { background: color-mix(in srgb, var(--bn-colour-accent) 25%, var(--bn-colour-muted)); }
.m-v-d .dl-cell.here.s2 { background: color-mix(in srgb, var(--bn-colour-accent) 25%, color-mix(in srgb, var(--bn-colour-text) 50%, var(--bn-colour-muted))); }
.m-v-d .dl-cell.here.s3 { background: color-mix(in srgb, var(--bn-colour-accent) 25%, var(--bn-colour-text)); }

/* E — nothing on the column (the head badge, grid only, stays lit as shipped). */

/* Window in the background: the accent goes to ink, as the rows already do. */
.bn-window-inactive .m-v-b .dl-slot.here { background: color-mix(in srgb, var(--bn-colour-muted) 14%, var(--bn-colour-inspector-bg)); }
.bn-window-inactive .m-v-d .dl-slot.here { background: color-mix(in srgb, var(--bn-colour-muted) 10%, var(--bn-colour-inspector-bg)); }
.bn-window-inactive .m-v-c .dl-cell.here.s1, .bn-window-inactive .m-v-d .dl-cell.here.s1 { background: var(--bn-colour-muted); }
.bn-window-inactive .m-v-c .dl-cell.here.s2, .bn-window-inactive .m-v-d .dl-cell.here.s2 { background: color-mix(in srgb, var(--bn-colour-text) 50%, var(--bn-colour-muted)); }
.bn-window-inactive .m-v-c .dl-cell.here.s3, .bn-window-inactive .m-v-d .dl-cell.here.s3 { background: var(--bn-colour-text); }
.bn-window-inactive .m-v-a .dl-cell.here { outline-color: var(--bn-colour-muted); }
"""

CHROME_CSS = r"""
body.m-page { margin: 0; padding: 28px 24px 80px; background: light-dark(#e9e9ec, #0d0d0f);
  font-family: var(--bn-font-body); color: var(--bn-colour-text); }
.m-title { font-size: 22px; margin: 0 0 4px; }
.m-sub { color: var(--bn-colour-muted); margin: 0 0 20px; max-width: 980px; }
.m-variant { margin: 0 0 34px; }
.m-variant h2 { font: 600 15px var(--bn-font-body); margin: 0 0 10px; padding-top: 12px; border-top: 2px solid light-dark(#c9c9ce, #333); }
.m-row { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-start; }
.m-frame { margin: 0; }
.m-chrome { font: 11px var(--bn-font-mono); padding: 5px 9px; background: light-dark(#dcdce0, #26262a);
  color: light-dark(#444, #bbb); border-radius: 8px 8px 0 0; }
.m-window { background: var(--bn-colour-inspector-bg); color: var(--bn-colour-text);
  border: 1px solid light-dark(#cfcfd4, #333); border-top: 0; border-radius: 0 0 8px 8px; }
.m-dark { color-scheme: dark; } .m-dark .m-window, .m-dark .dl-lens { color: var(--bn-colour-text); }
.m-light { color-scheme: light; } .m-light .m-window, .m-light .dl-lens { color: var(--bn-colour-text); }
.m-note { max-width: 1100px; margin: 10px 0 0; padding: 9px 13px; font-size: 13px; line-height: 1.5;
  background: repeating-linear-gradient(135deg, light-dark(#fff8e1,#2a2618) 0 8px, light-dark(#fff3cd,#302a1a) 8px 16px);
  border-left: 3px solid #d4a017; color: light-dark(#3a3000, #eadfb8); }
.m-note b { font-weight: 600; }
/* frame plumbing: the navigator alone, laid out in flow (the lens grid and sticky panes are not needed) */
.m-window .dl-lens { display: block; margin: 0; }
.m-window .dl-lens .dl-nav { position: static; height: auto; overflow: visible; border-right: 0; padding: 10px 12px 14px; }
.m-window .dl-lens .dl-grid-head { position: static; }
"""


def frame(label, sessions, tier, variant, width, scheme="light", inactive=False):
    lens = (f'<div class="dl-lens dl-m-{tier} m-v-{variant}" style="--dl-pitch:23px">'
            f'{nav(sessions, 2, tier)}</div>')
    win = f'<div class="m-window" style="width:{width}px">{lens}</div>'
    if inactive:
        win = f'<div class="bn-window-inactive">{win}</div>'
    return (f'<figure class="m-frame m-{scheme}"><figcaption class="m-chrome">{e(label)}</figcaption>'
            f"{win}</figure>")


def build() -> str:
    theme = load_default_css()
    disc = (ROOT / "frontend/src/islands/discussion/discussion.css").read_text(encoding="utf-8")
    body = []
    for v, title, note in VARIANTS:
        frames = [
            frame("strip · 3 sessions (Talismanic)", B.THREE, "strip", v, 330),
            frame("strip · 8 sessions", B.EIGHT, "strip", v, 360),
            frame("grid · 8 sessions", B.EIGHT, "grid", v, 470),
            frame("grid · 8 sessions · dark", B.EIGHT, "grid", v, 470, "dark"),
            frame("strip · 3 · dark", B.THREE, "strip", v, 330, "dark"),
            frame("strip · 8 · window in background", B.EIGHT, "strip", v, 360, inactive=True),
        ]
        body.append(f'<section class="m-variant"><h2>{e(title)}</h2><div class="m-row">{"".join(frames)}</div>'
                    f'<p class="m-note">{note}</p></section>')
    return f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop" style="color-scheme: light dark">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Discussion · selected column · Bristlenose mockups</title>
<style>
/* ════ SHIPPED: bristlenose/theme via load_default_css() ════ */
{theme}
/* ════ SHIPPED: frontend/src/islands/discussion/discussion.css — verbatim ════ */
{disc}
</style>
<style>{VARIANT_CSS}</style>
<style>{CHROME_CSS}</style>
</head>
<body class="m-page">
<h1 class="m-title">Discussion lens · the selected column, five ways</h1>
<p class="m-sub">Session #2 selected in every frame. The navigator as shipped in 0.40.0 (theme and discussion.css
inlined verbatim, the product's own markup); only the selected column's treatment changes. The key's legend
now reads “{e(KEY_MEASURE)}”. Generated by <code>experiments/discussion-all-sessions/selected_column.py</code>.</p>
{"".join(body)}
</body></html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
