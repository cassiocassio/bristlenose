"""Build docs/mockups/quote-card-layout-lab.html.

The lab compares the shipped quote card with rearrangements of the same parts,
to find layouts that give back width so a card can sit beside a screengrab on
the Screens lens without starving it.

Every theme rule in the page is lifted from bristlenose/theme/ (and the Screens
card overrides from frontend/src/islands/screens/screens.css) by reading the
files, never by hand. Each block is headed with its source path and line range
so a reader can diff it against the tree. The lab's own rules are in a second
<style> block: chrome classes are prefixed `m-`, variant rules are scoped under
`.lab-v<name>` so the shipped rules stay untouched.

Every card is drawn from one data table (QUOTES) with the markup QuoteCard.tsx
renders, so every frame shows the same cast. Quotes, codes and names are
invented.

Run:  .venv/bin/python experiments/quote-card-layout-lab/build.py
"""

from __future__ import annotations

import html
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "bristlenose" / "theme"
SCREENS_CSS = ROOT / "frontend" / "src" / "islands" / "screens" / "screens.css"
OUT = ROOT / "docs" / "mockups" / "quote-card-layout-lab.html"

# ── CSS extraction ──────────────────────────────────────────────────────────

# In _THEME_FILES order (stages/s12_render/theme_assets.py). Only what a quote
# card draws with.
WHOLE_FILES = [
    "tokens.css",
    "tokens-typography.css",
    "tokens-desktop.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "atoms/badge.css",
    "atoms/toggle.css",
    "atoms/input.css",
    "atoms/timecode.css",
    "atoms/interactive.css",
    "molecules/person-badge.css",
    "molecules/badge-row.css",
    "molecules/editable-text.css",
    "molecules/quote-actions.css",
    "molecules/tag-input.css",
    "organisms/blockquote.css",
    "organisms/responsive-grid.css",
]


def whole(path: Path, label: str) -> str:
    text = path.read_text(encoding="utf-8").rstrip("\n")
    n = text.count("\n") + 1
    return f"/* ════ {label} — whole file, lines 1–{n} ════ */\n{text}\n"


def rule_span(path: Path, label: str, start: str, end: str) -> str:
    """From the line that STARTS with `start` through the close of the rule whose
    first line starts with `end` (brace-balanced)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    i0 = next(i for i, ln in enumerate(lines) if ln.startswith(start))
    i1 = next(i for i, ln in enumerate(lines) if i >= i0 and ln.startswith(end))
    depth = 0
    j = i1
    while True:
        depth += lines[j].count("{") - lines[j].count("}")
        if depth == 0 and "}" in lines[j]:
            break
        j += 1
    body = "\n".join(lines[i0 : j + 1])
    return f"/* ════ {label} — lines {i0 + 1}–{j + 1} ════ */\n{body}\n"


def theme_css() -> str:
    parts = [whole(THEME / f, f"bristlenose/theme/{f}") for f in WHOLE_FILES]
    # report.css base: box-sizing, html, body. Placed before organisms would be
    # wrong by index order (templates load last), so it goes at the end.
    parts.append(
        rule_span(
            THEME / "templates/report.css",
            "bristlenose/theme/templates/report.css",
            "*,",
            "body {",
        )
    )
    return "\n".join(parts)


def screens_css() -> str:
    return rule_span(
        SCREENS_CSS,
        "frontend/src/islands/screens/screens.css (Screens card overrides)",
        ".screens-card { position: relative; }",
        ".screens-stage .screens-card .hide-btn",
    )


# ── The cast ────────────────────────────────────────────────────────────────

# Invented text, codes and names. Tags use the codebook group tints the SPA
# resolves through getTagBg (utils/colours.ts): var(--bn-<set>-<n>-bg).
QUOTES = [
    {
        "key": "short",
        "label": "short",
        "tc": "00:42",
        "code": "p2",
        "name": "Rowan",
        "text": "I'd just search for it.",
        "ai": None,
        "tags": [],
        "starred": False,
    },
    {
        "key": "long",
        "label": "long",
        "tc": "03:17",
        "code": "p4",
        "name": "Ines",
        "text": (
            "I scrolled right past the delivery options the first time because they "
            "looked like an advert, and by the time I found the cheaper one I'd already "
            "typed my card number in, so I just went with the fast one and paid extra."
        ),
        "ai": "frustration",
        "tags": [],
        "starred": False,
    },
    {
        "key": "tags",
        "label": "two tags",
        "tc": "12:05",
        "code": "p7",
        "name": "Dev",
        "text": (
            "The filter remembered my size, which was nice, but then it hid the "
            "things I'd actually come back for."
        ),
        "ai": None,
        "tags": [("saved filters", "--bn-ux-1-bg"), ("return visit", "--bn-task-2-bg")],
        "starred": False,
    },
    {
        "key": "starred",
        "label": "starred",
        "tc": "1:04:38",
        "code": "p1",
        "name": "Tamsin",
        "text": (
            "Honestly that's the first checkout this year that didn't make me feel "
            "like I'd done something wrong."
        ),
        "ai": "delight",
        "tags": [],
        "starred": True,
    },
    {
        "key": "longname",
        "label": "long name",
        "tc": "27:51",
        "code": "p12",
        "name": "Maximiliana Oyelaran-Whitcombe",
        "text": "Where's the button to go back? I thought that was it.",
        "ai": "confusion",
        "tags": [("navigation", "--bn-ux-3-bg")],
        "starred": False,
    },
]

HIDE_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round">'
    '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />'
    '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />'
    '<line x1="1" y1="1" x2="23" y2="23" /></svg>'
)

# Shipped locale strings (bristlenose/locales/en/common.json, quotes.*).
ARIA = {
    "hide": "Hide this quote",
    "star": "Star this quote",
    "add": "Add tag",
    "undo": "Revert to original",
}


def tc_secs(tc: str) -> int:
    parts = [int(p) for p in tc.split(":")]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def timecode(q: dict) -> str:
    return (
        f'<a class="timecode" href="#t={tc_secs(q["tc"])}" data-participant="{q["code"]}">'
        f'<span class="timecode-bracket">[</span>{q["tc"]}'
        f'<span class="timecode-bracket">]</span></a>'
    )


def speaker(q: dict) -> str:
    return (
        '<span class="speaker"><a href="#" class="speaker-link">'
        '<span class="bn-person-badge"><span class="bn-speaker-badge--split">'
        f'<span class="bn-speaker-badge-code">{q["code"]}</span>'
        f'<span class="bn-speaker-badge-name">{html.escape(q["name"])}</span>'
        "</span></span></a></span>"
    )


def quote_text(q: dict, state: str) -> str:
    t = html.escape(q["text"])
    if state == "editing":
        inner = (
            '<span class="crop-handle bracket-visible" data-handle="start">[</span>'
            '<span class="crop-editable" role="textbox" aria-multiline="false" '
            f'tabindex="0" contenteditable="true">{t}</span>'
            '<span class="crop-handle bracket-visible" data-handle="end">]</span>'
        )
        return f'<span class="quote-text">{inner}</span>'
    return f'<span class="quote-text" style="cursor: text">{t}</span>'


def badges(q: dict, state: str, extra_before: str = "", extra_after: str = "") -> str:
    out = [extra_before]
    if q["ai"]:
        out.append(
            f'<span class="badge badge-ai badge-{q["ai"]}" role="button" tabindex="0">'
            f'{q["ai"]}</span>'
        )
    for name, var in q["tags"]:
        out.append(
            f'<span class="badge badge-user" style="background-color: var({var})">'
            f'{html.escape(name)}<button class="badge-delete" '
            f'aria-label="Delete {html.escape(name)}">&times;</button></span>'
        )
    if state == "taginput":
        out.append(
            '<span class="tag-input-wrap"><span class="tag-input-box" style="width: 7.2rem">'
            '<input class="tag-input" type="text" placeholder="tag" value="ret">'
            '<span class="tag-ghost-layer"><span class="tag-ghost-spacer">ret</span>'
            '<span class="tag-ghost">urn visit</span></span></span>'
            '<span class="tag-sizer"></span>'
            '<div class="tag-suggest">'
            '<div class="tag-suggest-header">Task</div>'
            '<div class="tag-suggest-item active"><span class="tag-suggest-pill" '
            'style="background: var(--bn-task-2-bg)">return visit</span></div>'
            '<div class="tag-suggest-item"><span class="tag-suggest-pill" '
            'style="background: var(--bn-task-3-bg)">returns policy</span></div>'
            "</div></span>"
        )
    else:
        out.append(
            f'<span class="badge badge-add" role="button" tabindex="0" '
            f'aria-label="{ARIA["add"]}">+</span>'
        )
    out.append(extra_after)
    return '<div class="badges">' + "".join(out) + "</div>"


def toggles(q: dict) -> str:
    star_cls = "star-btn starred" if q["starred"] else "star-btn"
    return (
        f'<button class="hide-btn" aria-label="{ARIA["hide"]}" aria-pressed="false">'
        f"{HIDE_SVG}</button>"
        f'<button class="action-btn undo-btn" aria-label="{ARIA["undo"]}" '
        f'title="{ARIA["undo"]}">&#x21A9;</button>'
        f'<button class="{star_cls}" aria-label="{ARIA["star"]}" '
        f'aria-pressed="{"true" if q["starred"] else "false"}">&#9733;</button>'
    )


STATE_CLASS = {
    "rest": "",
    "hover": " m-hover",
    "focused": " bn-focused",
    "selected": " bn-selected",
    "focusedselected": " bn-focused bn-selected",
    "editing": " editing",
    "taginput": "",
}


def card(q: dict, variant: str, state: str = "rest") -> str:
    cls = "quote-card"
    if q["starred"]:
        cls += " starred"
    cls += STATE_CLASS[state]
    text_wrap = (
        '<span class="quote-text-wrapper"><span class="smart-quote">“</span>'
        f'{quote_text(q, state)}<span class="smart-quote">”</span></span>'
    )
    if variant == "D2":
        # DOM change: the timecode and the three buttons move into the badge row.
        row = (
            '<div class="quote-row"><div class="quote-body">'
            f"{text_wrap} {speaker(q)}"
            f"{badges(q, state, extra_before=timecode(q), extra_after=toggles(q))}"
            "</div></div>"
        )
        tail = ""
    else:
        row = (
            f'<div class="quote-row">{timecode(q)}<div class="quote-body">'
            f"{text_wrap} {speaker(q)}{badges(q, state)}</div></div>"
        )
        tail = toggles(q)
    return (
        f'<blockquote class="{cls}" data-q="{q["key"]}" data-timecode="{q["tc"]}" '
        f'data-participant="{q["code"]}">{row}{tail}</blockquote>'
    )


# ── Variants ───────────────────────────────────────────────────────────────

VARIANTS = [
    {
        "id": "ctl",
        "name": "Control",
        "sub": "Shipped list card (Quotes lens)",
        "dom": "shipped",
    },
    {
        "id": "scr",
        "name": "Control S",
        "sub": "Shipped Screens card today (screens.css overrides, 13px words)",
        "dom": "shipped",
    },
    {
        "id": "A",
        "name": "A",
        "sub": "Timecode on a top row with the eye and star; words full width; left padding halved",
        "dom": "CSS only",
    },
    {
        "id": "B",
        "name": "B",
        "sub": "A with the left padding kept at 1rem",
        "dom": "CSS only",
    },
    {
        "id": "C",
        "name": "C",
        "sub": "Top row: timecode and participant badge left, eye and star right; tags under the words",
        "dom": "CSS only (plus name truncation)",
    },
    {
        "id": "D1",
        "name": "D1",
        "sub": "Timecode runs in at the start of the first line; the first line alone leaves room for eye and star",
        "dom": "CSS only",
    },
    {
        "id": "D2",
        "name": "D2",
        "sub": "Words first, full width; timecode, tags, eye and star share the one row beneath",
        "dom": "DOM change",
    },
]

WIDTHS = [270, 320, 380]
STATES = [
    ("rest", "rest"),
    ("hover", "hover (simulated)"),
    ("focused", ".bn-focused"),
    ("selected", ".bn-selected"),
    ("focusedselected", "focused + selected"),
    ("editing", "editing (crop/text)"),
    ("taginput", "tag input open"),
]


def cards_block(variant: str, width: int, quotes=QUOTES, state: str = "rest") -> str:
    inner = "".join(card(q, variant, state) for q in quotes)
    if variant == "scr":
        inner = "".join(
            f'<div class="screens-card">{card(q, variant, state)}</div>' for q in quotes
        )
        return (
            f'<div class="screens-stage"><div class="screens-col m-scr-col" '
            f'style="width:{width}px">{inner}</div></div>'
        )
    return f'<div class="quote-group" style="width:{width}px">{inner}</div>'


def frame(variant: dict, width: int, body: str, extra_label: str = "", cls: str = "") -> str:
    label = f"{variant['name']} · {width}px{(' · ' + extra_label) if extra_label else ''}"
    return (
        f'<figure class="m-frame {cls}" data-variant="{variant["id"]}" data-width="{width}">'
        f'<figcaption class="m-chrome"><span class="m-chrome-label">{html.escape(label)}</span>'
        f'<span class="m-meas" aria-live="off"></span></figcaption>'
        f'<div class="m-art lab-v{variant["id"]}">{body}</div></figure>'
    )


def matrix() -> str:
    rows = []
    for v in VARIANTS:
        frames = "".join(frame(v, w, cards_block(v["id"], w)) for w in WIDTHS)
        rows.append(
            f'<div class="m-row" id="row-{v["id"]}">'
            f'<div class="m-row-head"><b>{v["name"]}</b> <span class="m-dom">{v["dom"]}</span>'
            f'<span class="m-sub">{html.escape(v["sub"])}</span></div>'
            f'<div class="m-row-frames">{frames}</div></div>'
        )
    return "".join(rows)


def states_grid() -> str:
    # Every variant's states are emitted; the picker shows one at a time (plus the
    # control alongside, for comparison).
    q_by = {q["key"]: q for q in QUOTES}
    blocks = []
    for v in VARIANTS:
        rows = []
        for sid, slabel in STATES:
            q = q_by["tags"] if sid != "editing" else q_by["tags"]
            cells = []
            for scheme in ("light", "dark"):
                body = cards_block(v["id"], 320, [q], sid)
                cells.append(
                    f'<div class="m-scheme m-force-{scheme}" data-scheme="{scheme}">'
                    f'{frame(v, 320, body, f"{slabel} · {scheme}", "m-state-frame")}</div>'
                )
            rows.append(
                f'<div class="m-state-row"><div class="m-state-name">{slabel}</div>'
                f'{"".join(cells)}</div>'
            )
        blocks.append(
            f'<div class="m-states" data-variant="{v["id"]}" hidden>{"".join(rows)}</div>'
        )
    return "".join(blocks)


def sandbox() -> str:
    q_by = {q["key"]: q for q in QUOTES}
    qs = [q_by["long"], q_by["tags"], q_by["longname"]]
    return "".join(
        f'<div class="m-sbx-col">{frame(v, 320, cards_block(v["id"], 320, qs), cls="m-sbx")}</div>'
        for v in VARIANTS
    )


# ── Page ───────────────────────────────────────────────────────────────────

LAB_CSS = r"""
/* ── Lab chrome (never inside a frame's artefact) ─────────────────────── */
body.m-page { padding: 1.5rem 1.5rem 4rem; max-width: none; }
.m-page h1 { font-size: var(--bn-text-title); line-height: var(--bn-text-title-lh); font-weight: var(--bn-weight-emphasis); margin: 0 0 .25rem; }
.m-page h2 { font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 2.5rem 0 .5rem; }
.m-page p.m-lede { color: var(--bn-colour-muted); max-width: 52rem; margin: 0 0 1rem; }
.m-key { display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: var(--bn-text-caption); color: var(--bn-colour-muted); margin-bottom: 1rem; }
.m-key span::before { content: ""; display: inline-block; width: 12px; height: 12px; vertical-align: -2px; margin-right: 6px; border-radius: 2px; }
.m-key .k-art::before { border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); }
.m-key .k-com::before { background: repeating-linear-gradient(45deg, var(--m-hatch) 0 3px, transparent 3px 7px); border-left: 3px solid var(--m-rule); }
.m-controls { position: sticky; top: 0; z-index: 100; display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; align-items: center;
  padding: .5rem .75rem; margin: 0 -.75rem 1rem; background: color-mix(in srgb, var(--bn-colour-bg) 92%, transparent);
  -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); border-bottom: 1px solid var(--bn-colour-border); font-size: var(--bn-text-caption); }
.m-controls fieldset { border: 0; padding: 0; margin: 0; display: flex; gap: .25rem; align-items: center; }
.m-controls legend { float: left; margin-right: .35rem; color: var(--bn-colour-muted); }
.m-controls button { font: inherit; padding: 2px 8px; border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); color: var(--bn-colour-text); border-radius: var(--bn-radius-sm); cursor: pointer; }
.m-controls button[aria-pressed="true"] { border-color: var(--bn-colour-accent); color: var(--bn-colour-accent); }
.m-controls input[type=range] { width: 12rem; }
.m-controls output { font-family: var(--bn-font-mono); min-width: 3.5em; display: inline-block; }

.m-row { margin: 0 0 1.75rem; }
.m-row-head { font-size: var(--bn-text-label); margin-bottom: .4rem; display: flex; gap: .5rem; align-items: baseline; flex-wrap: wrap; }
.m-row-head .m-sub { color: var(--bn-colour-muted); }
.m-dom { font-family: var(--bn-font-mono); font-size: var(--bn-text-micro); border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-pill); padding: 0 6px; color: var(--bn-colour-muted); }
.m-row-frames { display: flex; gap: 1.25rem; align-items: flex-start; flex-wrap: wrap; }
.m-frame { margin: 0; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md); overflow: visible; background: var(--bn-colour-bg); }
.m-chrome { display: flex; justify-content: space-between; gap: .75rem; flex-wrap: wrap; font-family: var(--bn-font-mono); font-size: var(--bn-text-micro);
  line-height: var(--bn-text-micro-lh); color: var(--bn-colour-muted); padding: 4px 8px; border-bottom: 1px solid var(--bn-colour-border);
  background: color-mix(in srgb, var(--bn-colour-muted) 8%, var(--bn-colour-bg)); border-radius: var(--bn-radius-md) var(--bn-radius-md) 0 0; }
.m-chrome .m-meas { color: var(--bn-colour-text); }
.m-art { padding: 14px; }
.m-art .quote-group { content-visibility: visible; }
.m-art .quote-group .quote-card { content-visibility: visible; }
.m-scr-col .screens-card + .screens-card { margin-top: 1.25rem; }

/* Forced scheme columns. `color` is re-declared on the forced container
   because an inherited colour is already resolved (theme/CLAUDE.md, "Showing
   light and dark side by side"). */
.m-force-light { color-scheme: light; color: var(--bn-colour-text); }
.m-force-dark  { color-scheme: dark;  color: var(--bn-colour-text); }
.m-force-light .m-frame, .m-force-dark .m-frame { background: var(--bn-colour-bg); }
/* Mirrors badge.css's dark user-tag rule, which keys on the page's scheme and
   so cannot follow a forced column. Mockup-only. */
.m-page .m-force-dark .badge-user.badge-user { color: #ffffff; font-weight: var(--bn-weight-emphasis); }
.m-page .m-force-light .badge-user.badge-user { color: var(--bn-colour-text); font-weight: var(--bn-weight-normal); }

/* Simulated hover — the same declarations the :hover rules make
   (toggle.css, badge-row.css, editable-text.css). Live hover works too. */
.quote-card.m-hover .hide-btn { opacity: 1; }
.quote-card.m-hover .badges { opacity: 1; }

.m-states-pick { display: flex; gap: .25rem; flex-wrap: wrap; margin-bottom: .75rem; font-size: var(--bn-text-caption); }
.m-states-pick button { font: inherit; padding: 2px 10px; border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); color: var(--bn-colour-text); border-radius: var(--bn-radius-sm); cursor: pointer; }
.m-states-pick button[aria-pressed="true"] { border-color: var(--bn-colour-accent); color: var(--bn-colour-accent); }
.m-state-row { display: grid; grid-template-columns: 9rem auto auto; gap: 1rem; align-items: start; margin-bottom: 1rem; }
.m-state-name { font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); color: var(--bn-colour-muted); padding-top: 6px; }
.m-scheme { padding: 0; }
.m-state-row:has(.tag-suggest) { margin-bottom: 6rem; }

.m-sandbox { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: flex-start; }

table.m-sum { border-collapse: collapse; font-size: var(--bn-text-caption); font-variant-numeric: tabular-nums; margin: .5rem 0 1rem; }
table.m-sum th, table.m-sum td { border-bottom: 1px solid var(--bn-colour-border); padding: 4px 10px; text-align: right; white-space: nowrap; }
table.m-sum th:first-child, table.m-sum td:first-child { text-align: left; }
table.m-sum thead th { color: var(--bn-colour-muted); font-weight: var(--bn-weight-emphasis); }
table.m-sum td.good { color: var(--bn-colour-accent); }
table.m-sum tr.m-ctl td { color: var(--bn-colour-muted); }

/* Commentary zone — deliberately not-the-product. */
:root { --m-hatch: color-mix(in srgb, var(--bn-colour-muted) 10%, transparent); --m-rule: color-mix(in srgb, var(--bn-colour-muted) 45%, transparent); }
.m-com { position: relative; margin: 1rem 0 2rem; padding: 1rem 1.25rem 1rem 1.25rem; border-left: 3px solid var(--m-rule);
  background: repeating-linear-gradient(45deg, var(--m-hatch) 0 3px, transparent 3px 9px); font-size: var(--bn-text-label); max-width: 64rem; }
.m-com::before { content: "Commentary"; position: absolute; top: -.6rem; left: .75rem; font-family: var(--bn-font-mono); font-size: var(--bn-text-micro);
  text-transform: uppercase; letter-spacing: .08em; color: var(--bn-colour-muted); background: var(--bn-colour-bg); padding: 0 6px; }
.m-com h3 { font-size: var(--bn-text-label); font-weight: var(--bn-weight-emphasis); margin: 1rem 0 .35rem; }
.m-com h3:first-child { margin-top: 0; }
.m-com p, .m-com li { max-width: 60rem; }
.m-com code { font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); }
.m-com table { border-collapse: collapse; margin: .5rem 0; }
.m-com td, .m-com th { border-bottom: 1px solid var(--bn-colour-border); padding: 4px 10px 4px 0; vertical-align: top; text-align: left; }
.m-com th { font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); }
.m-com .ok { color: var(--bn-colour-accent); }
.m-com .warn { color: var(--bn-colour-error-text); }

/* ── Variant rules: the proposals. Shipped DOM unless the row says otherwise. ── */

/* A and B: the timecode leaves the hanging gutter and takes the top line, where
   the eye and star already sit (toggle.css top: 0.65rem). With nothing beside
   the words, the 4.5rem right reserve that `.quote-group .quote-card` keeps
   for the toggles is no longer needed: the card's own 1rem returns. */
.lab-vA blockquote.quote-card,
.lab-vB blockquote.quote-card { padding: var(--bn-space-md) 1rem var(--bn-space-md) 0.5rem; }
.lab-vB blockquote.quote-card { padding-left: 1rem; }
.lab-vA blockquote .quote-row,
.lab-vB blockquote .quote-row { flex-direction: column; align-items: flex-start; gap: var(--bn-space-xs); }
.lab-vA blockquote .quote-body,
.lab-vB blockquote .quote-body { align-self: stretch; }

/* C: a header row — timecode, participant badge, then the toggles. The words
   take the width; the tags stay under them. A long name must truncate (the
   code half never does), or it runs under the toggles. */
.lab-vC blockquote.quote-card { padding: var(--bn-space-md) 1rem var(--bn-space-md) 0.5rem; }
.lab-vC blockquote .quote-row {
  display: grid; grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas: "tc spk" "text text" "tags tags";
  column-gap: 0.5rem; row-gap: var(--bn-space-xs); align-items: center;
}
.lab-vC blockquote .quote-row > .timecode { grid-area: tc; }
.lab-vC blockquote .quote-body { display: contents; }
.lab-vC blockquote .quote-text-wrapper { grid-area: text; }
.lab-vC blockquote .speaker { grid-area: spk; display: flex; min-width: 0; margin-right: 2.6rem; }
.lab-vC blockquote .badges { grid-area: tags; }
.lab-vC blockquote .speaker-link,
.lab-vC blockquote .bn-person-badge,
.lab-vC blockquote .bn-speaker-badge--split { display: inline-flex; min-width: 0; max-width: 100%; }
.lab-vC blockquote .bn-speaker-badge-code { flex: none; }
.lab-vC blockquote .bn-speaker-badge-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; }

/* D1: the timecode runs in, like a line number in a transcript. A float on the
   first line keeps the eye and star clear; every later line is full width. */
.lab-vD1 blockquote.quote-card { padding: var(--bn-space-md) 1rem var(--bn-space-md) 0.5rem; }
.lab-vD1 blockquote .quote-row { display: block; }
.lab-vD1 blockquote .quote-row::before { content: ""; float: right; width: 2.4rem; height: 1em; }
.lab-vD1 blockquote .quote-row > .timecode { margin-right: 0.35em; }
.lab-vD1 blockquote .quote-body { display: inline; }

/* D2 (DOM change): the timecode and the three toggles move into .badges, so
   the row that already exists for "+" carries them. Toggles in flow. */
.lab-vD2 blockquote.quote-card { padding: var(--bn-space-md) 1rem var(--bn-space-md) 0.5rem; }
.lab-vD2 blockquote .badges { align-items: center; }
.lab-vD2 blockquote .badges .hide-btn,
.lab-vD2 blockquote .badges .undo-btn,
.lab-vD2 blockquote .badges .star-btn { position: static; }
.lab-vD2 blockquote .badges .hide-btn { margin-left: auto; }
.lab-vD2 blockquote .badges .undo-btn:not(.visible) { display: none; }
"""

JS = r"""
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const html = document.documentElement;

  // ── controls ─────────────────────────────────────────────────────────
  function pressGroup(groupSel, btn) {
    $$(groupSel + " button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  }
  $$("#m-palette button").forEach((b) => b.addEventListener("click", () => {
    html.setAttribute("data-color-theme", b.dataset.v); pressGroup("#m-palette", b); measureAll();
  }));
  $$("#m-scheme button").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.v === "auto") html.removeAttribute("data-theme"); else html.setAttribute("data-theme", b.dataset.v);
    pressGroup("#m-scheme", b); measureAll();
  }));
  $$("#m-type button").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.v === "desktop") html.setAttribute("data-platform", "desktop"); else html.removeAttribute("data-platform");
    pressGroup("#m-type", b); measureAll();
  }));
  const slider = $("#m-width"), out = $("#m-width-out");
  function setSandbox(w) {
    out.textContent = w + "px";
    $$(".m-sbx, .m-state-frame").forEach((f) => {
      f.dataset.width = w;
      const lab = f.querySelector(".m-chrome-label");
      lab.textContent = lab.textContent.replace(/· \d+px/, "· " + w + "px");
      f.querySelectorAll(".quote-group, .m-scr-col").forEach((g) => (g.style.width = w + "px"));
    });
    measureAll();
  }
  slider.addEventListener("input", () => setSandbox(+slider.value));
  $$("#m-states-pick button").forEach((b) => b.addEventListener("click", () => {
    $$(".m-states").forEach((s) => (s.hidden = s.dataset.variant !== b.dataset.v));
    pressGroup("#m-states-pick", b); measureAll();
  }));

  // ── measurement ──────────────────────────────────────────────────────
  // The text column: the first ancestor of the words that lays out as a box
  // (in C the wrapper itself is a grid item; in D1 the words flow in the row).
  function columnOf(wrapper) {
    let el = wrapper;
    while (el) {
      const d = getComputedStyle(el).display;
      if (d !== "inline" && d !== "contents") break;
      el = el.parentElement;
    }
    const cs = getComputedStyle(el);
    return el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
  }
  // Words per line from the rendered line boxes of the quote's own text.
  function lines(textEl) {
    const node = [...textEl.childNodes].find((n) => n.nodeType === 3);
    if (!node) return null;
    const s = node.data, r = document.createRange();
    const tops = [];
    const re = /\S+/g; let m;
    while ((m = re.exec(s))) {
      r.setStart(node, m.index); r.setEnd(node, m.index + m[0].length);
      const rect = r.getClientRects()[0];
      if (!rect) continue;
      const top = Math.round(rect.top);
      const hit = tops.find((t) => Math.abs(t.top - top) < 4);
      if (hit) hit.n++; else tops.push({ top, n: 1 });
    }
    return tops.map((t) => t.n);
  }
  function hitTargets(card) {
    const star = card.querySelector(".star-btn"), hide = card.querySelector(".hide-btn");
    if (!star || !hide) return null;
    const a = star.getBoundingClientRect(), b = hide.getBoundingClientRect();
    const d = Math.hypot((a.left + a.width / 2) - (b.left + b.width / 2), (a.top + a.height / 2) - (b.top + b.height / 2));
    return { star: [a.width, a.height], hide: [b.width, b.height], gap: d };
  }
  function measureCard(card) {
    const wrap = card.querySelector(".quote-text-wrapper");
    const text = card.querySelector(".quote-text");
    const ls = text ? lines(text) : null;
    return {
      measure: columnOf(wrap),
      height: card.getBoundingClientRect().height,
      lines: ls ? ls.length : 0,
      words: ls ? ls.reduce((a, b) => a + b, 0) : 0,
      full: ls && ls.length > 1 ? ls.slice(0, -1) : (ls || []),
      hit: hitTargets(card),
    };
  }
  const RESULTS = {};
  function measureFrame(f) {
    const cards = $$("blockquote.quote-card", f);
    if (!cards.length) return null;
    const ms = cards.map(measureCard);
    // The measure that carries the paragraph: the long quote's (D1's first line
    // is shorter by design; later lines get the full column).
    const long = ms[cards.findIndex((c) => c.dataset.q === "long")] || ms[0];
    const full = ms.flatMap((m) => m.full);
    const wpl = full.length ? full.reduce((a, b) => a + b, 0) / full.length : 0;
    const height = cards.reduce((a, c) => a + c.getBoundingClientRect().height, 0);
    const w = +f.dataset.width;
    const r = { measure: long.measure, wpl, height, lines: ms.reduce((a, m) => a + m.lines, 0), w, hit: ms[0].hit, n: cards.length };
    const hit = r.hit ? ` · ☆/eye ${r.hit.star.map(Math.round).join("×")}, ${r.hit.hide.map(Math.round).join("×")}, ${Math.round(r.hit.gap)}px apart` : "";
    const words = r.lines ? `${wpl.toFixed(1)} w/l · ${r.lines} lines` : "words in edit mode, not counted";
    $(".m-meas", f).textContent = `measure ${Math.round(r.measure)}px · ${words} · ${Math.round(height)}px` + (f.classList.contains("m-state-frame") ? hit : "");
    return r;
  }
  function measureAll() {
    requestAnimationFrame(() => {
      $$(".m-frame").forEach((f) => {
        if (f.closest("[hidden]")) return;
        const r = measureFrame(f);
        if (r && !f.classList.contains("m-sbx") && !f.classList.contains("m-state-frame")) {
          (RESULTS[f.dataset.variant] ||= {})[f.dataset.width] = r;
        }
      });
      summary();
      window.__labResults = RESULTS;
    });
  }
  function summary() {
    const tb = $("#m-sum tbody"); if (!tb) return;
    const ctl = RESULTS.ctl; if (!ctl) return;
    const names = { ctl: "Control (list)", scr: "Control S (Screens)", A: "A", B: "B", C: "C", D1: "D1", D2: "D2" };
    const order = ["ctl", "scr", "A", "B", "C", "D1", "D2"];
    // Overhead = card width − measure. The list card's reading measure is the
    // control at --bn-quote-max-width (23rem = 368px); "width for list measure"
    // is the card a variant needs to give that measure.
    const listMeasure = 368 - (ctl[270].w - ctl[270].measure);
    tb.innerHTML = order.filter((k) => RESULTS[k]).map((k) => {
      const row = RESULTS[k];
      const over = row[270].w - row[270].measure;
      const cells = [270, 320, 380].map((w) => {
        const r = row[w], c = ctl[w];
        const d = r.measure - c.measure;
        return `<td>${Math.round(r.measure)}</td><td class="${d > 0 ? "good" : ""}">${d > 0 ? "+" : ""}${Math.round(d)}</td><td>${r.wpl.toFixed(1)}</td><td>${Math.round(r.height)}</td>`;
      }).join("");
      return `<tr class="${k === "ctl" ? "m-ctl" : ""}"><td>${names[k]}</td>${cells}<td>${Math.round(over)}</td><td>${Math.round(listMeasure + over)}</td></tr>`;
    }).join("");
    $("#m-sum-note").textContent = `List measure = the control at 23rem (368px): ${Math.round(listMeasure)}px of words. Font: ${getComputedStyle($(".quote-body")).fontFamily.split(",")[0]} ${getComputedStyle($(".quote-body")).fontSize}.`;
  }
  document.fonts.ready.then(measureAll);
  window.addEventListener("load", measureAll);
  window.addEventListener("resize", measureAll);
  // Width readouts for the sandbox and states frames.
  setSandbox(+slider.value);
})();
"""


def git_head() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


COMMENTARY_VARIANTS = """
<div class="m-com">
<h3>What each variant buys and costs</h3>
<table>
<tr><th>Variant</th><th>Buys</th><th>Costs</th></tr>
<tr><td>Control</td><td>The hanging timecode column lets the eye run down the timecodes of a list; the words start at one edge.</td>
<td>Measured overhead 153px of every card width: the 1px keyline, 16px left padding, the timecode column (~56px plus an 8px gap) and the right reserve for the eye and star (4.5rem, 72px — <code>.quote-group .quote-card</code>). At 270px the words get 117px, under half the card. At 270px a long name runs past the card's right edge (<code>blockquote .speaker</code> is <code>nowrap</code>) — Control S too.</td></tr>
<tr><td>Control S</td><td>Screens already trims: 12px timecode, 13px words, right reserve 2rem.</td>
<td>The words drop to 13px (label size), which is chrome size, not the participant's voice. Overhead is still 103px because the timecode column and a 2rem right reserve remain.</td></tr>
<tr><td>A</td><td>The whole width minus 8px + 16px goes to the words. Same parts, same order of meaning (when, then what was said, who, tags). Pure CSS on the shipped DOM.</td>
<td>One extra row per card for the top line: about 21px (five cards at 380px: 704px against D2's 598px). The timecodes no longer form a column you can scan in a list. 8px of gutter against the left keyline.</td></tr>
<tr><td>B</td><td>Isolates the gutter: everything A gives except 8px.</td><td>8px narrower than A; same extra row.</td></tr>
<tr><td>C</td><td>A's measure, and the participant badge leaves the end of the quote, so the last line of words often ends sooner — about the same height as A. Reads like a message header: when, who, then what.</td>
<td>A long name is truncated with an ellipsis (the code never is). Attribution moves from after the words to before them — a change in how a quote reads, not only where. Needs four small rules beyond the move.</td></tr>
<tr><td>D1</td><td>No extra row: five cards at 380px are 620px against A's 704px. Every line after the first gets A's full width.</td>
<td>The first line loses the timecode and the toggle space, so a short quote gains little. The timecode sits in the words' line at a different size and face; a run-in reads busier than a header.</td></tr>
<tr><td>D2</td><td>No extra row, and the first line is full width too: the most words per card height. The timecode joins a row that already exists for "+".</td>
<td>The only variant that changes the DOM. The star (a state mark, not only a control) moves to the bottom right, far from where the eye starts on a long quote. The timecode is read last.</td></tr>
</table>

<h3>Keyboard and accessibility, per variant</h3>
<table>
<tr><th></th><th>Reading order (DOM)</th><th>Focus order vs what you see</th><th>Hit targets</th></tr>
<tr><td>Control</td><td>timecode · words · participant · tags · + · eye · star</td>
<td>Tab reaches the eye and star last, but they are drawn first-line right. Existing mismatch.</td>
<td>Measured in the states frames: about 18×18 (star) and 19×19 (eye), centres about 22px apart — under the 24px of WCAG 2.5.8 in size and in spacing. Unchanged by A, B, C, D1.</td></tr>
<tr><td>A, B</td><td>unchanged</td><td>Same mismatch, now more visible: the eye and star share the timecode's row, and Tab goes timecode → participant → tags → + → back up to the eye. Fix in the DOM: render the hide and star toggles straight after the timecode.</td>
<td>Same buttons. The top row has room to move the eye left by 2px (<code>right: 2.15rem</code>) and clear 24px spacing — free in A/B/C, impossible in the control where the words sit under them.</td></tr>
<tr><td>C</td><td>unchanged</td><td>Visual order is timecode, participant, eye, star, words, tags; DOM order is timecode, words, participant, tags, eye, star. The largest mismatch of all: worth a DOM change if C wins.</td><td>As A.</td></tr>
<tr><td>D1</td><td>unchanged</td><td>As the control: the toggles are drawn at the end of line 1 and reached last.</td><td>As the control.</td></tr>
<tr><td>D2</td><td>words · participant · timecode · tags · + · eye · star</td><td>Matches: the toggles come after the tags in both.</td><td>In flow, so spacing follows <code>.badges</code>'s gap (0.35rem): centres measured 24px apart; the size is unchanged.</td></tr>
</table>
<p>Screen readers hear the same content in every variant except D2, where the timecode comes after the words. The blockquote has no accessible name of its own, so the order of its children is the order a reader hears.</p>
</div>
"""

COMMENTARY_IMPL = """
<div class="m-com" id="m-impl">
<h3>Implementing the winner in QuoteCard.tsx and the theme</h3>
<p>Written for A (the owner's first idea, CSS only), with what changes for C or D2. Nothing here is implemented.</p>
<ul>
<li><b>organisms/blockquote.css</b> — <code>blockquote .quote-row</code> (<code>display: flex; gap: 0.5rem; align-items: baseline</code>) becomes a column: <code>flex-direction: column; align-items: flex-start; gap: var(--bn-space-xs)</code>, and <code>blockquote .quote-body</code> gains <code>align-self: stretch</code>. The comment "Hanging-indent layout: timecode in left gutter" goes. <code>.quote-group .quote-card { padding-right: 4.5rem }</code> goes (the base <code>blockquote.quote-card</code> padding <code>var(--bn-space-md) 1rem</code> becomes <code>… 1rem … 0.5rem</code> on the left for A, unchanged for B).</li>
<li><b>atoms/toggle.css</b> — <code>.star-btn</code> and <code>.hide-btn</code> keep <code>top: 0.65rem</code>; they already sit on what becomes the top row. Optional: <code>.hide-btn { right: 2.15rem }</code> to clear 24px spacing.</li>
<li><b>molecules/editable-text.css</b> — <code>.undo-btn { right: 3.35rem }</code> and <b>atoms/button.css</b> <code>.edit-pencil { right: 3.35rem }</code> sit on the same top row; they still fit at 270px (the timecode is ~4rem). No change needed.</li>
<li><b>QuoteCard.tsx</b> — for A, none required. To fix the focus order, render the hide <code>Toggle</code>, the undo button and the star <code>Toggle</code> straight after the timecode element instead of after <code>.quote-row</code>; the positions don't change because they are absolute. The parked moderator-question row (<code>.moderator-question-row</code>) keeps an invisible timecode as a hanging spacer — with the gutter gone that spacer should go too, or that row stays indented. The parked <code>ExpandableTimecode</code> wraps the timecode and inherits the top-row position.</li>
<li><b>frontend/src/islands/screens/screens.css</b> (the other session's file — listed, not touched) — <code>.screens-stage .screens-card > blockquote.quote-card</code> padding (<code>sm 2rem sm md</code>) and the 13px words would need retuning to match; <code>.screens-stage .screens-card .star-btn / .hide-btn</code> tops; and two things that depend on the hanging gutter: <code>.screens-grip-side</code> ("the margin under the timecode", <code>left: 0; top: 2.2rem; width: 3.6rem</code>) would lie over the words, and the top row itself becomes the obvious grip (a title bar). <code>.screens-seq</code> sits on the top edge at <code>left: var(--bn-space-lg)</code> and would crowd the timecode once it is on the top row.</li>
<li><b>Other surfaces</b> — the card is shared: the Quotes lens, the dashboard's featured quotes, the HTML export, focus mode (<code>templates/focus-mode.css</code> restyles <code>blockquote.quote-card</code>) and print (<code>templates/print.css</code>). The owner wants one card everywhere, so changing <code>blockquote.css</code> changes all of them at once; that is the intent, and the place to check each by eye. The sealed static renderer shares the CSS but its markup (<code>theme/templates/quote_card.html</code>) has the same shape, so it follows.</li>
<li><b>For C</b>, add the grid rules (<code>grid-template-areas: "tc spk" "text text" "tags tags"</code>, <code>.quote-body { display: contents }</code>) and the name truncation on <code>.bn-speaker-badge-name</code>, scoped to the card so the Sessions grid's badges are untouched. Better done in the DOM: move <code>.speaker</code> next to the timecode.</li>
<li><b>For D2</b>, QuoteCard.tsx moves the timecode element into <code>.badges</code> as its first child and the three toggles to its end; <code>atoms/toggle.css</code> loses <code>position: absolute</code> for the card's toggles; <code>.undo-btn</code> needs <code>display: none</code> when not visible.</li>
</ul>

<h3>Trade-offs with editing, trimming, tag input and focus</h3>
<ul>
<li><b>Editing and trimming</b> (crop/text mode, <code>.quote-card.editing</code>): the brackets replace the smart quotes inside <code>.quote-text-wrapper</code>, so every variant edits the same way. A, B, C and D2 give the bracket handles a wider column, which makes dragging them easier. D1 puts the timecode link immediately before the opening bracket: a click a few pixels left of <code>[</code> plays the clip instead of starting a drag. <code>.quote-card.editing .quote-text { min-width: 10rem }</code> holds in all.</li>
<li><b>Tag input</b>: opens in place of "+" inside <code>.badges</code> and its suggestion list is absolutely placed. Unaffected in A–D1. In D2 the row also holds the timecode and toggles, so at 270px the input wraps onto its own line sooner.</li>
<li><b>Focus and selection</b> (<code>.bn-focused</code>, <code>.bn-selected</code>): both paint the card's background, shadow and left keyline (<code>atoms/interactive.css</code>), so they are layout-neutral and hold in every variant. With A's 8px gutter the selection keyline and the first letter are close; B's 16px is the same as today. Focus shows the eye (<code>.quote-card.bn-focused .hide-btn</code>); in A–C that now lands on the timecode's row.</li>
<li><b>Starred</b>: the words take <code>--bn-weight-starred</code> (520), slightly wider; the starred column in the matrix shows it costs no extra lines at these widths.</li>
</ul>
</div>
"""


def page() -> str:
    head = git_head()
    return f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quote card layout lab · Bristlenose mockups</title>
<style>
/* ============================================================================
   Quote card layout lab — real pixels.

   Every rule between the markers below is read from the tree at {head} by
   experiments/quote-card-layout-lab/build.py, each block headed by its source
   path and line range. Nothing in it is edited. The lab's own rules are the
   second <style> block: chrome is `m-`, proposals are `.lab-v<variant>`.
   ========================================================================= */
/* ── BEGIN verbatim theme CSS ── */
{theme_css()}
{screens_css()}
/* ── END verbatim theme CSS ── */
</style>
<style>{LAB_CSS}</style>
</head>
<body class="m-page">
<h1>Quote card layout lab</h1>
<p class="m-lede">The same card parts, rearranged to give width back to the words, so a card can sit beside a
screengrab on the Screens lens at one width everywhere. Every frame draws the same five invented quotes with
the markup <code>QuoteCard.tsx</code> renders. Measurements are taken live in this browser.</p>
<div class="m-key"><span class="k-art">Artefact — real classes, real pixels</span><span class="k-com">Commentary — not the product</span></div>

<div class="m-controls" role="toolbar" aria-label="Lab controls">
  <fieldset id="m-palette"><legend>Palette</legend>
    <button data-v="default" aria-pressed="true">Default</button><button data-v="edo" aria-pressed="false">Edo</button></fieldset>
  <fieldset id="m-scheme"><legend>Scheme</legend>
    <button data-v="auto" aria-pressed="true">System</button><button data-v="light" aria-pressed="false">Light</button><button data-v="dark" aria-pressed="false">Dark</button></fieldset>
  <fieldset id="m-type"><legend>Type</legend>
    <button data-v="web" aria-pressed="true">Web (Inter)</button><button data-v="desktop" aria-pressed="false">Mac app (SF)</button></fieldset>
  <label>Sandbox + states width <input id="m-width" type="range" min="220" max="480" step="2" value="320"> <output id="m-width-out">320px</output></label>
</div>

<h2>1 · Measure: every variant at 270, 320 and 380px</h2>
<table class="m-sum" id="m-sum">
<thead><tr><th rowspan="2">Variant</th><th colspan="4">270px</th><th colspan="4">320px</th><th colspan="4">380px</th><th rowspan="2">overhead<br>(card − measure)</th><th rowspan="2">card width for<br>the list measure</th></tr>
<tr><th>measure</th><th>Δ</th><th>w/line</th><th>height</th><th>measure</th><th>Δ</th><th>w/line</th><th>height</th><th>measure</th><th>Δ</th><th>w/line</th><th>height</th></tr></thead>
<tbody></tbody></table>
<p class="m-lede" id="m-sum-note"></p>
<p class="m-lede">Measure is the width of the column the long quote's words flow in. Words per line averages every full line of all five quotes (last lines excluded). Height is the five cards' total, without gaps.</p>
{matrix()}
{COMMENTARY_VARIANTS}

<h2>2 · States, light and dark</h2>
<div class="m-states-pick" id="m-states-pick" role="toolbar" aria-label="Variant">
{"".join(f'<button data-v="{v["id"]}" aria-pressed="{"true" if v["id"] == "A" else "false"}">{v["name"]}</button>' for v in VARIANTS)}
</div>
{states_grid()}

<h2>3 · Sandbox: drag the width</h2>
<p class="m-lede">The long quote, the tagged quote and the long name, in every variant at the slider's width.</p>
<div class="m-sandbox">{sandbox()}</div>

<h2>4 · Implementation and trade-offs</h2>
{COMMENTARY_IMPL}
<script>{JS}
document.querySelector('.m-states[data-variant="A"]').hidden = false;
</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(page(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
