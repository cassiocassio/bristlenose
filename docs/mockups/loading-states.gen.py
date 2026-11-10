#!/usr/bin/env python3
"""Generates docs/mockups/loading-states.html.

The shipped theme CSS is read from the tree and inlined block by block (each headed by its path and
line range), so the page cannot drift from the product: diff a block against the file. Only the
`PROPOSED` block and the `mk-` chrome are new. Brief: docs/design-loading-states-brief.md.

Run:  .venv/bin/python docs/mockups/loading-states.gen.py
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "bristlenose" / "theme"
OUT = ROOT / "docs" / "mockups" / "loading-states.html"


# ── Shipped CSS, inlined verbatim ─────────────────────────────────────────────────────────────
def block(rel: str, start: int | None = None, end: int | None = None) -> str:
    lines = (THEME / rel).read_text(encoding="utf-8").splitlines()
    a, b = (start or 1), (end or len(lines))
    body = "\n".join(lines[a - 1 : b])
    return f"/* ════ bristlenose/theme/{rel} — lines {a}–{b} ════ */\n{body}\n"


def tapestry_preview_block() -> str:
    lines = (THEME / "organisms/session-tapestry.css").read_text(encoding="utf-8").splitlines()
    end = next(i for i, ln in enumerate(lines, 1) if "Open, the timeline is the strip" in ln) + 1
    return block("organisms/session-tapestry.css", 1, end)


SHIPPED_CSS = "\n".join(
    [
        block("tokens.css"),
        block("tokens-typography.css"),
        block("colors/palette-default.css"),
        block("colors/palette-edo.css"),
        block("atoms/badge.css"),
        block("atoms/shimmer.css"),
        block("atoms/thumbnail.css"),
        block("molecules/person-badge.css"),
        block("molecules/sparkline.css"),
        block("organisms/sessions-grid.css"),
        tapestry_preview_block(),
    ]
)

_ts = (ROOT / "frontend/src/utils/tapestryScale.ts").read_text(encoding="utf-8")
GUTTER = int(re.search(r"export const TAPESTRY_GUTTER\s*=\s*(\d+)", _ts).group(1))
RIGHT = int(re.search(r"export const TAPESTRY_RIGHT\s*=\s*(\d+)", _ts).group(1))
TABLE_W = 1000  # a middle rung of the sessions-grid container queries (968 < w <= 1285)
PREVIEW_H = 4.5  # components/TapestryPreview.tsx

# ── PROPOSED: the only new tokens and rules ───────────────────────────────────────────────────
PROPOSED_CSS = """\
:root {
    /* Will exist, not started — a STATIC ghost. Quiet outline, quieter fill. Never moves. */
    --bn-ghost-line: var(--bn-colour-border-hover);
    --bn-ghost-outline: color-mix(in srgb, var(--bn-ghost-line) 45%, transparent);
    --bn-ghost-fill: color-mix(in srgb, var(--bn-colour-badge-bg) 45%, transparent);

    /* Working on it now — a BLOCK skeleton. Same character as the text shimmer (single hue,
       same timing, same band), drawn on a box because background-clip:text has no box to clip.
       Polarity follows the theme: the band moves toward the ink, so it darkens on light and
       lightens on dark. */
    --bn-skeleton-base: var(--bn-colour-badge-bg);
    /* A third of what a block of pixels would take from the text shimmer's 20%: on a big slab
       the same swing reads as a flash. The peak is a translucent ink tint laid OVER whatever
       fill the element already has, so a ghost shape and a skeleton box share one sweep. */
    --bn-skeleton-contrast: 2.7%;
    --bn-skeleton-peak: color-mix(in srgb, var(--bn-colour-text) var(--bn-skeleton-contrast), transparent);
    /* Small shapes (sparkline bars, the 4.5px strip) have too little area for the eye to catch
       a third-contrast sweep: they take the earlier, stronger value. */
    --bn-skeleton-contrast-small: 8%;
    --bn-skeleton-peak-small: color-mix(in srgb, var(--bn-colour-text) var(--bn-skeleton-contrast-small), transparent);
}

/* Ghost: 1px dotted outline (1px dots) + faint fill. Shapes under ~12px on a side (sparkline bars, the 4.5px
   strip) cannot carry a dotted outline: they take the fill alone (.bn-ghost--solid). */
.bn-ghost {
    box-sizing: border-box;
    border: 1px dotted var(--bn-ghost-outline);
    background: var(--bn-ghost-fill);
    border-radius: var(--bn-radius-sm);
    cursor: default;
    pointer-events: none;
}
.bn-ghost--solid { border: none; background: var(--bn-ghost-line); opacity: 0.55; }

/* Skeleton: a solid base fill at rest (so the static fallback still differs from a ghost:
   solid vs dashed), with the sweep on top when both motion gates pass. */
.bn-skeleton {
    box-sizing: border-box;
    background-color: var(--bn-skeleton-base);
    border-radius: var(--bn-radius-sm);
    cursor: default;
    pointer-events: none;
}

/* Same two gates as atoms/shimmer.css: reduced-motion, and the app's animation toggle. */
@media (prefers-reduced-motion: no-preference) {
    :root:not([data-analysis-animation="off"]) :is(.bn-skeleton, .is-working) {
        background-image: linear-gradient(
            var(--bn-shimmer-angle),
            transparent 0%,
            transparent calc(50% - var(--bn-shimmer-band) / 6),
            var(--bn-skeleton-peak) 50%,
            transparent calc(50% + var(--bn-shimmer-band) / 6),
            transparent 100%
        );
        background-size: 300% 100%;
        background-repeat: no-repeat;
        animation: bn-skeleton-sweep var(--bn-shimmer-period) var(--bn-shimmer-easing) infinite;
        /* Independent phase, so neighbours read as individual organisms, not a strobe. */
        animation-delay: var(--bn-skeleton-phase, 0ms);
    }
}
@keyframes bn-skeleton-sweep {
    0%     { background-position: 100% 50%; }
    66.67% { background-position: 0% 50%; }
    100%   { background-position: 0% 50%; }
}

/* The principle: working is the SAME element as the ghost, started. It keeps its shape and
   position; the dotted outline (the "not started" mark) goes, the fill firms up, the sweep runs.
   Shapes with no outline (sparkline bars) firm up by opacity. */
.bn-ghost:not(.bn-ghost--solid).is-working { border-color: transparent; background-color: var(--bn-skeleton-base); }
.bn-ghost--solid.is-working { opacity: 0.8; }
.bn-ghost--solid.is-working, .bn-tapestry-preview .is-working { --bn-skeleton-peak: var(--bn-skeleton-peak-small); }

/* A thumbnail slot that is not (yet) a thumbnail: no pointer, no play icon. */
.bn-video-thumb.bn-ghost, .bn-video-thumb.bn-skeleton { cursor: default; }

/* The strip's placeholder lives in the strip's own box, so nothing moves when it resolves. */
.bn-tapestry-preview.is-placeholder { cursor: default; pointer-events: none; }
"""

# ── Mockup chrome (not product) ───────────────────────────────────────────────────────────────
CHROME_CSS = """\
body { background: var(--bn-colour-bg); color: var(--bn-colour-text); font-family: var(--bn-font-body);
       margin: 0; }
.mk-page { max-width: 1064px; margin: 0 auto; padding: 24px 16px 80px; }
.mk-page h1 { font-size: var(--bn-text-title); margin: 0 0 4px; }
.mk-page h2 { font-size: var(--bn-text-heading); margin: 44px 0 6px; }
.mk-page h3 { font-size: var(--bn-text-body); margin: 22px 0 6px; }
.mk-lede { color: var(--bn-colour-muted); max-width: 70ch; margin: 0 0 14px; }
.mk-mono { font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); }

.mk-bar { position: sticky; top: 0; z-index: 20; display: flex; flex-wrap: wrap; gap: 14px;
          align-items: center; padding: 8px 16px; margin: 0 -16px 8px;
          background: var(--bn-colour-bg); border-bottom: 1px solid var(--bn-colour-border);
          font-size: var(--bn-text-caption); }
.mk-seg { display: inline-flex; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md);
          overflow: hidden; }
.mk-seg button { all: unset; cursor: pointer; padding: 3px 10px; color: var(--bn-colour-muted); }
.mk-seg button[aria-pressed="true"] { background: var(--bn-colour-accent); color: #fff; }
.mk-seg button:focus-visible { outline: 2px solid var(--bn-colour-accent); outline-offset: -2px; }

.mk-key { display: flex; flex-wrap: wrap; gap: 18px; font-size: var(--bn-text-caption);
          color: var(--bn-colour-muted); margin: 6px 0 14px; }
.mk-key i { display: inline-block; width: 14px; height: 14px; vertical-align: -3px; margin-right: 6px;
            border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); }
.mk-key i.note { border: 3px solid transparent; border-left: 2px solid var(--bn-colour-muted);
  background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
    repeating-linear-gradient(135deg, color-mix(in srgb, var(--bn-colour-muted) 40%, transparent) 0 3px, transparent 3px 6px) border-box; }

/* Artefact zone: the real pixels in a clean frame, chrome bar names the moment, never the UI. */
.mk-frame { border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md);
            background: var(--bn-colour-bg); overflow: hidden; margin: 10px 0; }
.mk-frame-bar { display: flex; justify-content: space-between; gap: 12px; padding: 5px 12px;
                background: var(--bn-colour-badge-bg); border-bottom: 1px solid var(--bn-colour-border);
                font-family: var(--bn-font-mono); font-size: var(--bn-text-micro); color: var(--bn-colour-muted); }
.mk-frame-body { padding: 10px 12px; overflow-x: auto; }
.mk-frame-body > .bn-session-table { width: 1000px; }

/* Commentary zone: hatched edge band only, never behind text. */
.mk-note { border: 7px solid transparent; border-left: 3px solid var(--bn-colour-muted);
  background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
    repeating-linear-gradient(135deg, color-mix(in srgb, var(--bn-colour-muted) 35%, transparent) 0 5px, transparent 5px 10px) border-box;
  padding: 6px 12px; margin: 8px 0; font-size: var(--bn-text-label); max-width: 80ch; }
.mk-note::before { content: "Commentary"; display: block; font-family: var(--bn-font-mono);
  font-size: var(--bn-text-micro); color: var(--bn-colour-muted); text-transform: uppercase;
  letter-spacing: .06em; margin-bottom: 2px; }
.mk-note p { margin: 4px 0; }
.mk-note ul { margin: 4px 0; padding-left: 1.2em; }

.mk-table { width: 100%; border-collapse: collapse; font-size: var(--bn-text-label); }
.mk-table th, .mk-table td { text-align: left; vertical-align: top; padding: 8px 10px;
                              border-bottom: 1px solid var(--bn-colour-border); }
.mk-table th { font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); }
.mk-specimen td.cell { vertical-align: middle; }

.mk-pre { background: var(--bn-colour-quote-bg); border: 1px solid var(--bn-colour-border);
          border-radius: var(--bn-radius-md); padding: 10px 12px; overflow-x: auto;
          font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); line-height: 1.5;
          white-space: pre; }

/* Stand-ins (flagged in the frame bar): a "frame" for a thumbnail, clip colours, quote text. */
.mk-standin { width: 100%; height: 100%; border-radius: var(--bn-radius-sm);
  background: linear-gradient(135deg, var(--a, #8aa4b8), var(--b, #c9b79c)); }
.mk-thumb-slot { width: 96px; height: 54px; }
.mk-badge-slot { display: inline-block; width: 3.6rem; height: 1.45rem; }
.mk-line { height: .8rem; border-radius: var(--bn-radius-sm); margin: .35rem 0; }

/* Generic card used where the real component is not the argument (flagged in the bar). */
.mk-card { background: var(--bn-colour-quote-bg); border: 1px solid var(--bn-colour-border);
           border-radius: var(--bn-radius-md); padding: 10px 12px; font-size: var(--bn-text-label); }
.mk-card.is-ghost { background: transparent; }
.mk-cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.mk-row-gap { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }

/* The resolve moment. */
.mk-arrive { position: relative; width: 96px; height: 54px; }
.mk-arrive > * { position: absolute; inset: 0; transition: opacity var(--bn-transition-fast); }
.mk-arrive .real { opacity: 0; }
.mk-arrive.arrived .real { opacity: 1; }
.mk-arrive.arrived .ghost { opacity: 0; }
@media (prefers-reduced-motion: reduce) { .mk-arrive > * { transition: none; } }
.mk-btn { all: unset; cursor: pointer; font-size: var(--bn-text-caption); color: var(--bn-colour-accent); }
.mk-btn:hover { text-decoration: underline; }
"""

# ── Markup helpers ────────────────────────────────────────────────────────────────────────────
PLAY = (
    '<span class="bn-play-icon"><svg class="bn-icon" viewBox="0 0 24 24" width="14" height="14" '
    'stroke="currentColor" stroke-width="2" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/>'
    "</svg></span>"
)

SENT = ["frustration", "confusion", "doubt", "surprise", "satisfaction", "delight"]


def phase(i: int) -> str:
    return f' style="--bn-skeleton-phase: -{(i * 733) % 2700}ms"'


def thumb(state: str, i: int = 0, a: str = "#8aa4b8", b: str = "#c9b79c") -> str:
    if state == "none":
        return ""
    if state == "play":  # today's fallback when a readable row has no thumbnail_url
        return f'<div class="bn-video-thumb">{PLAY}</div>'
    if state == "done":
        return f'<div class="bn-video-thumb"><div class="mk-standin" style="--a:{a};--b:{b}"></div></div>'
    if state == "ghost":
        return '<div class="bn-video-thumb bn-ghost" aria-hidden="true"></div>'
    if state == "working":
        return f'<div class="bn-video-thumb bn-ghost is-working" aria-hidden="true"{phase(i)}></div>'
    raise ValueError(state)


def badge(code: str, name: str) -> str:
    return (
        f'<div class="bn-session-speaker-entry"><span class="bn-person-badge"><span class="bn-speaker-badge--split">'
        f'<span class="bn-speaker-badge-code">{code}</span><span class="bn-speaker-badge-name">{name}</span>'
        f"</span></span></div>"
    )


def speakers(state: str, who: tuple[tuple[str, str], ...] = ()) -> str:
    if state == "done":
        return "".join(badge(c, n) for c, n in who)
    if state == "ghost":
        return '<div><span class="bn-ghost mk-badge-slot" aria-hidden="true"></span></div>'
    return ""


def sparkline(state: str, heights: tuple[int, ...] = ()) -> str:
    if state == "dash":
        return "—"  # today: no quotes with a sentiment yet
    if state in ("ghost", "working"):
        cls = "bn-ghost--solid is-working" if state == "working" else "bn-ghost--solid"
        bars = "".join(
            f'<div class="bn-sparkline-bar {cls}" style="height:{h}px;--bn-skeleton-phase:-{k * 311}ms"></div>'
            for k, h in enumerate((8, 14, 10, 6, 12, 9))
        )
        return f'<div class="bn-sparkline" style="gap:2px" aria-hidden="true">{bars}</div>'
    bars = "".join(
        f'<div class="bn-sparkline-bar" style="height:{h}px;background:var(--bn-sentiment-{SENT[k]});opacity:.8"></div>'
        for k, h in enumerate(heights)
    )
    return f'<div class="bn-sparkline" style="gap:2px">{bars}</div>'


def strip_svg(width: int, seed: int) -> str:
    usable = width - GUTTER - RIGHT
    spans = [(0.02, 0.07), (0.11, 0.2), (0.27, 0.33), (0.38, 0.55), (0.6, 0.64), (0.7, 0.86), (0.9, 0.97)]
    hues = [28, 200, 120, 330, 48, 260, 170]
    rects = []
    for k, (a, b) in enumerate(spans):
        x0 = GUTTER + a * usable
        w = (b - a) * usable
        fill = f"hsl({(hues[(k + seed) % 7])} 28% 52%)"
        rects.append(
            f'<g><rect class="bn-tp-pv-clip" x="{x0 + .5:.1f}" y="0" width="{w - 1:.1f}" height="{PREVIEW_H}" rx="1" '
            f'style="fill:{fill}"/><rect class="bn-tp-pv-edge" x="{x0 + .5:.1f}" y="0" width="{w - 1:.1f}" '
            f'height="{PREVIEW_H}" rx="1"/></g>'
        )
    return (
        f'<div class="bn-tapestry-preview" aria-hidden="true"><svg class="bn-tapestry-preview-svg" width="{width}" '
        f'height="{PREVIEW_H + 4}"><g transform="translate(0,2)"><rect class="bn-tp-pv-track" x="{GUTTER}" y="0" '
        f'width="{usable}" height="{PREVIEW_H}" rx="1.5"/><g class="bn-tp-pv-clips">{"".join(rects)}</g></g></svg></div>'
    )


def strip_placeholder(state: str, variant: str = "A", i: int = 0) -> str:
    """Placeholder in the strip's own box (same margin, padding, track extent)."""
    track_cls = "bn-ghost is-working" if state == "working" else "bn-ghost"
    inner = ""
    if variant == "B":  # generic dim clip shapes on the track: promises "clips", not content
        spans = [(0.02, 0.07), (0.11, 0.2), (0.27, 0.33), (0.38, 0.55), (0.6, 0.64), (0.7, 0.86), (0.9, 0.97)]
        working = state == "working"
        cls_attr = ' class="is-working"' if working else ""
        inner = "".join(
            f'<span{cls_attr} style="position:absolute;top:0;bottom:0;left:{a * 100:.1f}%;'
            f'width:{(b - a) * 100:.1f}%;border-radius:1px;background:var(--bn-ghost-line);opacity:.5;'
            f'--bn-skeleton-phase:-{k * 311 if working else 0}ms"></span>'
            for k, (a, b) in enumerate(spans)
        )
    phase_css = f"--bn-skeleton-phase:-{(i * 733) % 2700}ms;" if state == "working" else ""
    style = (
        f"position:relative;height:{PREVIEW_H}px;margin:2px {RIGHT}px 0 {GUTTER}px;"
        f"border-radius:1.5px;{phase_css}"
    )
    return (
        f'<div class="bn-tapestry-preview is-placeholder" aria-hidden="true">'
        f'<div class="{track_cls}" style="{style}">{inner}</div></div>'
    )


def row(
    n: int,
    state: str,
    *,
    th: str,
    sp: str,
    sent: str,
    strip: str = "",
    date: str,
    dur: str,
    fname: str,
    processing: bool = False,
) -> str:
    readable = state == "readable"
    attrs = f' data-session="s{n}"' if readable else ' aria-disabled="true" aria-busy="true"'
    idcell = f'<a href="#">#{n}</a>' if readable else f"<span>#{n}</span>"
    if readable:
        src = f'<a href="#" class="timecode">{fname}</a>'
    elif processing:
        src = f'<span class="bn-thinking-shimmer">{fname}</span>'
    else:
        src = f"<span>{fname}</span>"
    return (
        f'<div class="bn-sessions-row"{attrs}>'
        f'<div class="bn-sessions-cell bn-cell-id bn-session-id">{idcell}</div>'
        f'<div class="bn-sessions-cell bn-cell-thumb">{th}</div>'
        f'<div class="bn-sessions-cell bn-cell-speakers bn-session-speakers">{sp}</div>'
        f'<div class="bn-sessions-cell bn-cell-start"><div>{date}</div></div>'
        f'<div class="bn-sessions-cell bn-cell-sentiment bn-session-sentiment">{sent}</div>'
        f'<div class="bn-sessions-cell bn-cell-duration bn-session-duration">{dur}</div>'
        f'<div class="bn-sessions-cell bn-cell-file">{src}</div>'
        f"{strip}</div>"
    )


HEAD = (
    '<div class="bn-sessions-row bn-sessions-head">'
    '<div class="bn-sessions-cell bn-cell-id">ID</div><div class="bn-sessions-cell bn-cell-thumb"></div>'
    '<div class="bn-sessions-cell bn-cell-speakers">Speakers</div>'
    '<div class="bn-sessions-cell bn-cell-start"><span class="bn-sessions-h1">Start</span>'
    '<span class="bn-sessions-h2">User journey</span></div>'
    '<div class="bn-sessions-cell bn-cell-sentiment">Sentiment</div>'
    '<div class="bn-sessions-cell bn-cell-duration">Duration</div>'
    '<div class="bn-sessions-cell bn-cell-file">Interviews</div></div>'
)


def grid(rows: list[str]) -> str:
    return f'<div class="bn-session-table"><div class="bn-sessions-grid">{HEAD}{"".join(rows)}</div></div>'


def frame(bar_left: str, bar_right: str, body: str) -> str:
    return (
        f'<div class="mk-frame"><div class="mk-frame-bar"><span>{bar_left}</span><span>{bar_right}</span></div>'
        f'<div class="mk-frame-body">{body}</div></div>'
    )


def note(inner: str) -> str:
    return f'<div class="mk-note">{inner}</div>'


WHO1 = (("m1", "Jo"), ("p1", "Amir"))
WHO2 = (("m1", "Jo"), ("p2", "Lena"))
WHO3 = (("m1", "Jo"), ("p3", "Sam"))
H1, H2, H3 = (14, 20, 9, 5, 12, 8), (6, 12, 18, 10, 7, 14), (10, 8, 16, 12, 5, 9)
COMMON = {
    1: {"date": "12 Oct 2026", "dur": "52m", "fname": "interview-01.mov"},
    2: {"date": "13 Oct 2026", "dur": "1h 04m", "fname": "interview-02.mov"},
    3: {"date": "14 Oct 2026", "dur": "38m", "fname": "interview-03.mov"},
}
PAIRS = {1: ("#8aa4b8", "#c9b79c"), 2: ("#a89cc8", "#d6b8a2"), 3: ("#8fb59c", "#c4c18f")}

# ── Area 1: the Sessions grid, three moments ──────────────────────────────────────────────────
TODAY = grid(
    [
        row(1, "readable", th=thumb("play"), sp=speakers("done", WHO1), sent=sparkline("dash"), **COMMON[1]),
        row(2, "waiting", th="", sp="", sent=sparkline("dash"), processing=True, **COMMON[2]),
        row(3, "waiting", th="", sp="", sent=sparkline("dash"), **COMMON[3]),
    ]
)
MID = grid(
    [
        row(1, "readable", th=thumb("play"), sp=speakers("done", WHO1), sent=sparkline("ghost"),
            strip=strip_svg(TABLE_W, 0), **COMMON[1]),
        row(2, "waiting", th=thumb("ghost"), sp=speakers("ghost"), sent=sparkline("ghost"), processing=True,
            **COMMON[2]),
        row(3, "waiting", th=thumb("ghost"), sp=speakers("ghost"), sent=sparkline("ghost"), **COMMON[3]),
    ]
)
STRIPS = grid(
    [
        row(1, "readable", th=thumb("done", 0, *PAIRS[1]), sp=speakers("done", WHO1), sent=sparkline("done", H1),
            strip=strip_svg(TABLE_W, 0), **COMMON[1]),
        row(2, "readable", th=thumb("done", 0, *PAIRS[2]), sp=speakers("done", WHO2), sent=sparkline("done", H2),
            strip=strip_placeholder("working", "A", 1), **COMMON[2]),
        row(3, "readable", th=thumb("done", 0, *PAIRS[3]), sp=speakers("done", WHO3), sent=sparkline("done", H3),
            strip=strip_placeholder("ghost", "A"), **COMMON[3]),
    ]
)

# ── Specimen: the three states on four shapes ─────────────────────────────────────────────────
def specimen() -> str:
    def cell(x: str) -> str:
        return f'<td class="cell"><div class="mk-frame" style="margin:0"><div class="mk-frame-body">{x}</div></div></td>'

    strip_done = strip_svg(420, 2)
    # strips inside the specimen sit in a div, not a grid: reuse the same box
    quote_done = (
        '<div class="mk-card">The export button was where I expected it, but I wasn’t sure it had worked.'
        '<div class="mk-row-gap"><span class="badge">export</span><span class="badge">feedback</span></div></div>'
    )
    quote_ghost = (
        '<div class="mk-card is-ghost bn-ghost" style="border-radius:var(--bn-radius-md)"><div class="mk-line"></div>'
        '<div class="mk-line" style="width:70%"></div><div class="mk-row-gap"><span class="bn-ghost" '
        'style="width:3.4rem;height:1.3rem"></span></div></div>'
    )
    quote_work = quote_ghost.replace('bn-ghost"', 'bn-ghost is-working"').replace(
        'class="bn-ghost" ', 'class="bn-ghost is-working" '
    )
    text_done = '<a href="#" class="timecode">interview-02.mov</a>'
    text_work = (
        '<span class="bn-thinking-shimmer" style="--bn-shimmer-base:var(--bn-colour-muted);'
        '--bn-shimmer-peak:var(--bn-colour-text);--bn-shimmer-contrast:20%">interview-02.mov</span>'
    )
    text_ghost = '<span class="bn-ghost" style="display:inline-block;width:8.5rem;height:1rem"></span>'
    chart_work = sparkline("working")
    rows = [
        ('Thumbnail<br><span class="mk-mono">96 × 54</span>', thumb("done"), thumb("working"), thumb("ghost")),
        (
            'Strip<br><span class="mk-mono">4.5 px</span>',
            strip_done,
            strip_placeholder("working"),
            strip_placeholder("ghost"),
        ),
        ('Text that exists<br><span class="mk-mono">a filename</span>', text_done, text_work, text_ghost),
        (
            'Chart cell<br><span class="mk-mono">sparkline bars</span>',
            sparkline("done", H2),
            chart_work,
            sparkline("ghost"),
        ),
        ("Card", quote_done, quote_work, quote_ghost),
    ]
    body = "".join(
        f"<tr><td>{label}</td>{cell(d)}{cell(w)}{cell(g)}</tr>" for label, d, w, g in rows
    )
    return (
        '<table class="mk-table mk-specimen"><thead><tr><th>Shape</th><th>Done</th><th>Working on it now</th>'
        f"<th>Will exist, not started</th></tr></thead><tbody>{body}</tbody></table>"
    )


# ── Area 2: Themes arriving at the barrier (three moments of one section) ─────────────────────
def themes_triplet() -> str:
    def sec(head: str, cards: str) -> str:
        return f'<div>{head}<div style="display:grid;gap:8px;margin-top:8px">{cards}</div></div>'

    ghost_card = '<div class="bn-ghost" style="height:46px;border-radius:var(--bn-radius-md)"></div>'
    done_card = (
        '<div class="mk-card">Confusion about where saved items live'
        '<div class="mk-row-gap"><span class="badge">navigation</span></div></div>'
    )
    a = sec('<div class="bn-ghost" style="height:1.2rem;width:48%"></div>', ghost_card * 3)
    b = sec('<div class="bn-skeleton" style="height:1.2rem;width:48%"' + phase(0) + "></div>", ghost_card * 3)
    c = sec('<div style="font-weight:var(--bn-weight-emphasis);font-size:var(--bn-text-body)">Finding saved items</div>',
            done_card * 3)
    return (
        '<div class="mk-cards">'
        + frame("1 · sessions still being read", "stand-in text", a)
        + frame("2 · grouping into themes now", "one shimmer", b)
        + frame("3 · themes arrived", "stand-in text", c)
        + "</div>"
    )


# ── Area 3 (a second family): tags applied progressively, one moment, three states ────────────
def autocode() -> str:
    def card(tags: str) -> str:
        return (
            '<div class="mk-card">Search kept returning old results until I refreshed.'
            f'<div class="mk-row-gap">{tags}</div></div>'
        )

    done = card('<span class="badge" style="background:var(--bn-emo-1-bg)">frustration</span><span class="badge">search</span>')
    working = card('<span class="bn-skeleton" style="width:5.2rem;height:1.3rem"' + phase(0) + '></span>')
    ghost = card('<span class="bn-ghost" style="width:5.2rem;height:1.3rem"></span>')
    return (
        '<div class="mk-cards">'
        + frame("tags done", "stand-in text", done)
        + frame("tagging this one now", "stand-in text", working)
        + frame("queued", "stand-in text", ghost)
        + "</div>"
    )


# ── Unhappy paths and the resolve moment ──────────────────────────────────────────────────────
def unhappy() -> str:
    def pair(before: str, after: str) -> str:
        return (
            '<div style="display:flex;align-items:center;gap:12px">'
            f'<div class="mk-frame" style="margin:0"><div class="mk-frame-body">{before}</div></div>'
            '<span aria-hidden="true">→</span>'
            f'<div class="mk-frame" style="margin:0;min-width:110px"><div class="mk-frame-body" '
            f'style="min-height:54px">{after}</div></div></div>'
        )

    arrive = (
        '<div class="mk-arrive" id="arrive"><div class="ghost"><div class="bn-video-thumb bn-ghost"></div></div>'
        '<div class="real"><div class="bn-video-thumb"><div class="mk-standin"></div></div></div></div>'
    )
    rows = [
        ("Stop, or a cancelled run", "Every ghost and skeleton goes. Nothing is left promising work that stopped.",
         pair(thumb("ghost"), '<span class="mk-mono" style="color:var(--bn-colour-muted)">(empty cell)</span>')),
        ("The frame can't be made (decode failed)",
         "Resolves to today's play-icon box. The media is still playable, so the fallback is honest.",
         pair(thumb("working"), thumb("play"))),
        ("Audio-only session", "Never gets a placeholder: the probe says no video stream, so nothing is promised.",
         pair('<span class="mk-mono" style="color:var(--bn-colour-muted)">(no thumbnail slot)</span>',
              '<span class="mk-mono" style="color:var(--bn-colour-muted)">(no thumbnail slot)</span>')),
        ("Arrival", "A 150 ms cross-fade (--bn-transition-fast) in the same box, so nothing reflows. "
                    "Instant under reduced motion.",
         f'<div style="display:flex;align-items:center;gap:14px">{arrive}'
         '<button class="mk-btn" type="button" id="replay">Replay arrival</button></div>'),
    ]
    out = ['<table class="mk-table"><thead><tr><th>Case</th><th>What it does</th><th>Shown</th></tr></thead><tbody>']
    for a, b, c in rows:
        out.append(f"<tr><td><strong>{a}</strong></td><td>{b}</td><td>{c}</td></tr>")
    out.append("</tbody></table>")
    return "".join(out)


# ── Page ──────────────────────────────────────────────────────────────────────────────────────
JS = """\
(function () {
  var root = document.documentElement;
  function press(group, btn) {
    group.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', b === btn); });
  }
  document.querySelectorAll('.mk-seg').forEach(function (g) {
    g.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      press(g, b);
      var k = g.dataset.k, v = b.dataset.v;
      if (k === 'palette') root.setAttribute('data-color-theme', v);
      if (k === 'scheme') root.style.colorScheme = v === 'auto' ? 'light dark' : v;
      if (k === 'motion') { if (v === 'off') root.setAttribute('data-analysis-animation', 'off');
                            else root.removeAttribute('data-analysis-animation'); }
    });
  });
  var a = document.getElementById('arrive'), r = document.getElementById('replay');
  if (r && a) r.addEventListener('click', function () {
    a.classList.remove('arrived'); void a.offsetWidth; setTimeout(function () { a.classList.add('arrived'); }, 400);
  });
  var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  var n = document.getElementById('rm'); if (n) n.hidden = !mq.matches;
})();
"""


def seg(k: str, opts: list[tuple[str, str]], on: str) -> str:
    return (
        f'<span class="mk-seg" data-k="{k}" role="group" aria-label="{k}">'
        + "".join(f'<button type="button" data-v="{v}" aria-pressed="{str(v == on).lower()}">{t}</button>' for v, t in opts)
        + "</span>"
    )


BODY = f"""
<div class="mk-page">
<div class="mk-bar">
  <span>Palette</span>{seg("palette", [("default", "Default"), ("edo", "Edo")], "default")}
  <span>Scheme</span>{seg("scheme", [("auto", "Auto"), ("light", "Light"), ("dark", "Dark")], "auto")}
  <span>Motion</span>{seg("motion", [("on", "On"), ("off", "Off (static fallback)")], "on")}
  <span id="rm" hidden style="color:var(--bn-colour-muted)">Your system asks for reduced motion, so nothing moves here whatever this says.</span>
</div>

<h1>Loading states: done, working, will exist</h1>
<p class="mk-lede">A proposal for one vocabulary across the report, for review before anything is built.
Real theme CSS is inlined from the tree; only the <span class="mk-mono">bn-ghost</span> and
<span class="mk-mono">bn-skeleton</span> rules and the page chrome are new. Brief:
<span class="mk-mono">docs/design-loading-states-brief.md</span>.</p>

<div class="mk-key"><span><i></i>Artefact: real pixels, as they would ship</span>
<span><i class="note"></i>Commentary: not the product</span></div>

{note('''<p><strong>Why.</strong> In testing, progressive display read as broken: people did not see that analysis was still
running, and never discovered that the bars under a session are a scrubbable timeline, because they only appear once
frames exist. Today the one loading cue is the text shimmer. <em>Skeleton and ghost are not defined anywhere in the
system</em>, and <span class="mk-mono">design-progressive-lenses.md</span> §2 says &ldquo;never a skeleton&rdquo; and
&ldquo;a waiting row shows no thumbnail placeholder&rdquo;. This page proposes reversing both.</p>''')}

<h2>1 · The vocabulary</h2>
<p class="mk-lede">Three states, five shapes. Switch to <em>Off</em> above to see the static fallback: the working
state must still differ from the ghost without motion, so a skeleton is a solid fill and a ghost is a dotted outline.</p>
{frame("Specimen", "stand-in image, strip clips and text", specimen())}
{note('''<ul>
<li><strong>Working is the ghost, started.</strong> The same element keeps its shape and position: the dotted
outline goes, the fill firms up, the sweep runs. Nothing is swapped in. The sweep is a translucent ink tint laid over
whatever fill is there, at a third of the text shimmer&rsquo;s contrast (2.7% against 20%), because a big slab of
pixels turns the same swing into a flash.</li>
<li><strong>Text that exists keeps the shipped shimmer.</strong> A box with no ghost of its own takes the skeleton. That
split keeps §4.7.1 intact and gives block shapes their own rule.</li>
<li><strong>Ghost below about 12 px on a side takes fill only</strong> (sparkline bars, the 4.5 px strip). A dotted
outline turns to noise at that size.</li>
<li><strong>Static fallback needs no new gate:</strong> the skeleton uses the same two gates as the text shimmer
(reduced motion, and the &ldquo;Show animation while analysing&rdquo; toggle).</li>
</ul>''')}

<h2>2 · Sessions grid, three moments</h2>
<p class="mk-lede">The same grid at three points in one run. Facts known at ingest stay as they are.</p>
{frame("Today · mid-run", "stand-in names, dates, filenames", TODAY)}
{note('''<p>Row 1 is readable, row 2 is being worked on (filename shimmers), row 3 waits. Everything not yet known is
simply absent, and a sparkline cell shows a dash. Nothing says &ldquo;more is coming&rdquo; except one faint shimmer.
The play box on row 1 is today&rsquo;s fallback when a thumbnail does not exist, which reads as playable.</p>''')}
{frame("Proposed · mid-run", "stand-in names, dates, filenames", MID)}
{note('''<ul>
<li><strong>A readable row is not a placeholder.</strong> Row 1 keeps today&rsquo;s play box and its closed strip,
which draws as soon as the row is readable. Only rows still waiting for ingest carry ghosts.</li>
<li><strong>One shimmer per row, as now.</strong> The filename is the &ldquo;working&rdquo; cue; the other cells wait as
ghosts. Nothing else moves.</li>
<li><strong>Speaker count is unknown, so one ghost badge,</strong> not two.</li>
<li><strong>A waiting row is not a disabled one.</strong> Muted text stays; the dotted ghosts say &ldquo;reserved&rdquo;.</li>
<li>The ghost badge and sparkline bars are cell-level and cost nothing to reverse.</li>
</ul>''')}
{frame("Proposed · run finished, strips being drawn", "stand-in frames and clips", STRIPS)}
{note('''<ul>
<li>Row 1 done. Row 2&rsquo;s strip is the one being drawn now, so it is the only strip that sweeps. Row 3&rsquo;s is
queued, so it is a static ghost.</li>
<li>The state machine is real: <em>ghost</em> = scheduled, <em>skeleton</em> = the job is on this session,
<em>done</em> = it landed.</li>
<li>The placeholder lives in the strip&rsquo;s own box (same gutter, same track), so when it resolves nothing moves.</li>
</ul>''')}

<h2>3 · How long would a placeholder actually be on screen?</h2>
<table class="mk-table"><thead><tr><th>Thing</th><th>When it is produced today</th><th>So the placeholder is up for</th></tr></thead><tbody>
<tr><td>Thumbnail</td><td>At render (<span class="mk-mono">s12_render/report.py</span>). The design doc plans a grab right after
ingest, not built. Measured when it is built: 0.14 s per frame, about 1.5 s for ten files.</td>
<td><strong>The whole run</strong> today: minutes. A skeleton here would shimmer for minutes, which is wrong; a static
ghost is right. If extraction moves to ingest, it is seconds and may not need a placeholder at all.</td></tr>
<tr><td>Closed strip</td><td>Needs the session&rsquo;s turns and scene colours. Scene colours are computed per session in
the chain (about 1.5 s per hour of video). The closed strip draws as soon as the row is readable, so it needs no
placeholder on a readable row.</td>
<td>None once readable. A waiting row has no strip yet.</td></tr>
<tr><td>Hover frames and scene strip</td><td>A background job in serve after the report is readable. It decodes at 4 fps,
defers while a run is in progress, and works through sessions one at a time (<span class="mk-mono">server/scene_strips.py</span>).</td>
<td>Per session, a real wait on long recordings: this is the one place a working shimmer is earned. <em>Decode time
per hour of video is not measured; do that before choosing.</em></td></tr>
</tbody></table>

<h2>4 · The vocabulary outside the Sessions grid</h2>
<h3>Themes arriving at the barrier</h3>
<p class="mk-lede">One section across three moments. Static while sessions are read, shimmering only while the grouping
runs, then real. A ghost heading, no words.</p>
{themes_triplet()}
{note('''<p>Words (&ldquo;appears when every session is read&rdquo;) would be new copy, so none are drawn.
<strong>Decision 2:</strong> silent ghost, or one plain line.</p>''')}
<h3>Tags applied progressively (a second family)</h3>
<p class="mk-lede">One moment, three cards in three states. The same two rules, a different feature.</p>
{autocode()}

<h2>5 · The unhappy paths</h2>
{unhappy()}

<h2>6 · Proposed tokens</h2>
<p class="mk-lede">Defined in this page only; <span class="mk-mono">tokens.css</span> is untouched. Timing is reused from the
shimmer tokens, not copied.</p>
<pre class="mk-pre">{html.escape(PROPOSED_CSS)}</pre>

<h2>7 · Principles</h2>
{note('''<ul>
<li><strong>Three states, always the same three.</strong> Done; working now; will exist.</li>
<li><strong>Shimmer is for something happening to this element now.</strong> At most one per row or section; independent
phase; never on a thing that is only queued.</li>
<li><strong>A ghost only for something we know will arrive.</strong> Probe-confirmed video, yes; audio-only, never; a
cloud file not downloaded, never.</li>
<li><strong>Every placeholder has an exit.</strong> Stop removes them; failure resolves to the fallback; nothing shimmers
forever.</li>
<li><strong>Text that exists keeps the text shimmer; a box with nothing in it gets a skeleton.</strong></li>
<li><strong>Not clickable, not focusable, hidden from assistive tech.</strong> The region carries
<span class="mk-mono">aria-busy</span> while work is under way.</li>
<li><strong>No words by default.</strong> The shape says &ldquo;coming&rdquo;.</li>
<li><strong>Reserve the real size.</strong> A placeholder occupies the box the content will, so arrival never reflows.</li>
</ul>''')}

<h2>8 · Decisions wanted</h2>
{note('''<ol>
<li><strong>The deferred scene strip and hover frames:</strong> the closed strip is already real on a readable row, so
the open question is only whether the later frames earn a placeholder (track alone, or dim generic segments).</li>
<li><strong>Themes ghost: silent, or one plain line of copy?</strong></li>
<li><strong>Thumbnails:</strong> extract in the readable chain, as the design doc plans (seconds, so a readable row
never needs a thumbnail ghost). Leaving it at render would mean a minutes-long ghost, which I would not ship.</li>
<li><strong>Measure the strip job per hour of video</strong> before deciding whether a per-session working shimmer is
earned or just noise.</li>
<li><strong>Reverse the 12 Oct rulings</strong> (&ldquo;never a skeleton&rdquo;, &ldquo;no waiting-row placeholder&rdquo;) in
<span class="mk-mono">design-progressive-lenses.md</span> §2.</li>
<li><strong>Contrast of the ghost outline</strong> (<span class="mk-mono">--bn-colour-border-hover</span>) is deliberately low;
confirm it is visible enough on your screens in both palettes.</li>
</ol>''')}
</div>
"""

PAGE = f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default" style="color-scheme: light dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loading states: done, working, will exist</title>
<!-- Generated by docs/mockups/loading-states.gen.py. Shipped CSS blocks are verbatim from bristlenose/theme/. -->
<style>
{SHIPPED_CSS}
/* ════ PROPOSED — new in this mockup ════ */
{PROPOSED_CSS}
/* ════ Mockup chrome — not product ════ */
{CHROME_CSS}
</style>
</head>
<body>
{BODY}
<script>
{JS}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    OUT.write_text(PAGE, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(PAGE):,} bytes)")
