#!/usr/bin/env python3
"""Generate docs/mockups/codebook-applied-slot.html.

The codebook pages' top-right slot (AutoCode → AutoCoding… → Applied) on the catalogue card and
the codebook page, its alignment against the title, the page's counts (shipped kept), and the
catalogue's own heading row. Owner's decisions of 24 Nov 2026, built on the 6c marker chosen
24 Oct (docs/mockups/codebook-catalogue-install-on-page.html).

Shipped CSS is read from the tree, each block headed with its path and line range. The markup is
the shipped markup, captured from a running `serve --dev` on 24 Nov 2026 into
docs/mockups/codebook-page-increments/*.json (a private trial run; its name is replaced with
"Demo study"), and edited here only where the proposal changes it. Every new rule sits under one
"NEW" heading and uses tokens only. Shipped words come from the en locale by key; the words that
are not shipped yet are listed in the page's string table and marked in each frame's chrome.

    .venv/bin/python docs/mockups/codebook-applied-slot.gen.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/codebook-applied-slot.html"
CAPTURES = ROOT / "docs/mockups/codebook-page-increments"
THEME = ROOT / "bristlenose/theme"
CSS_FILES = [
    "tokens.css",
    "tokens-typography.css",
    "tokens-desktop.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "atoms/badge.css",
    "atoms/icon.css",
    "atoms/bar.css",
    "atoms/lead-paragraph.css",
    "atoms/modal.css",
    "atoms/section-heading.css",
    "atoms/shimmer.css",
    "organisms/codebook-panel.css",
    "organisms/sidebar.css",
    "organisms/codebook-v2.css",
]
# Rules lifted out of templates/report.css by the line their selector starts on (the whole file
# would lay the mockup's own page out as a report).
REPORT_RULES = ["*,", "h1, h2, h3, .description {", "h1 {"]
COMMON = json.loads((ROOT / "bristlenose/locales/en/common.json").read_text(encoding="utf-8"))
E = html.escape

CHECK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" class="lucide lucide-check bn-icon" aria-hidden="true">'
    '<path d="M20 6 9 17l-5-5" vector-effect="non-scaling-stroke"></path></svg>'
)

# Words that are not shipped. Each one is drawn where it would sit and listed in the table.
W_ACT = "AutoCode"
W_RUN = "AutoCoding"
W_DONE = "Applied"


def t(path: str, **values: object) -> str:
    node: object = COMMON
    for part in path.split("."):
        node = node[part]  # type: ignore[index]
    text = str(node)
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", str(value))
    return text


def css_block(rel: str) -> str:
    text = (THEME / rel).read_text(encoding="utf-8")
    n = text.count("\n") + 1
    return f"/* ════ bristlenose/theme/{rel} — lines 1–{n} ════ */\n{text}\n"


def css_rule(rel: str, starts: str) -> str:
    lines = (THEME / rel).read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith(starts):
            j = i
            while not lines[j].startswith("}"):
                j += 1
            body = "\n".join(lines[i : j + 1])
            return f"/* ════ bristlenose/theme/{rel} — lines {i + 1}–{j + 1} ════ */\n{body}\n"
    raise SystemExit(f"rule {starts!r} not found in {rel}")


def capture(name: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((CAPTURES / name).read_text(encoding="utf-8"))
    return data


UXR = capture("capture-page-uxr.json")
GARRETT = capture("capture-page-garrett.json")
BROWSE = capture("capture-browse.json")


# ── The slot's three states ─────────────────────────────────────────────────────────────────


def slot_act(variant: str = "primary") -> str:
    return f'<button class="bn-btn bn-btn-{variant} bn-btn-sm cb-act">{W_ACT}</button>'


def slot_run(colour: str = "muted", dots: bool = False) -> str:
    tail = (
        '<span class="cb-dots" aria-hidden="true"><i>.</i><i>.</i><i>.</i></span>'
        if dots
        else "…"
    )
    return f'<span class="cb-running bn-thinking-shimmer run-{colour}">{W_RUN}{tail}</span>'


def slot_done() -> str:
    return f'<span class="cb-applied">{CHECK}<span>{W_DONE}</span></span>'


def slot(state: str, **kw: object) -> str:
    if state == "act":
        return slot_act(str(kw.get("variant", "primary")))
    if state == "run":
        return slot_run(str(kw.get("colour", "muted")), bool(kw.get("dots", True)))
    return slot_done()


def slotbox(inner: str) -> str:
    # The centred variant wraps the slot in a box one title line tall; the others ignore it.
    return f'<span class="cb-slotbox">{inner}</span>'


# ── Cards ───────────────────────────────────────────────────────────────────────────────────

CARD_RE = re.compile(
    r'<div class="picker-card[^"]*" role="button" tabindex="0" data-testid="bn-v2-card-([a-z-]+)">'
    r'(.*?)</div></div>(?=<div class="picker-card|</div></div></div>)',
    re.S,
)


def browse_cards() -> dict[str, str]:
    cards = {}
    for m in CARD_RE.finditer(BROWSE["section"]):
        cards[m.group(1)] = m.group(2) + "</div>"
    return cards


CARDS = browse_cards()


def card(book: str, state: str | None, off: bool = False, title: str | None = None,
         status: str | None = None, **kw: object) -> str:
    """A shipped card with its footrow button removed and the slot in a title row."""
    inner = CARDS[book]
    if status is not None:
        inner = re.sub(r'<span class="picker-card-status">.*?</span>',
                       f'<span class="picker-card-status">{E(status)}</span>', inner, count=1, flags=re.S)
    inner = re.sub(r"<button[^>]*>[^<]*</button>", "", inner)  # no Install / Uninstall on cards
    tm = re.match(r'<div class="picker-card-title">(.*?)</div>', inner, re.S)
    assert tm, book
    name = title if title is not None else tm.group(1)
    rest = inner[tm.end() :]
    s = slotbox(slot(state, **kw)) if state else ""
    head = (
        f'<div class="picker-card-titlerow"><div class="picker-card-title">{name}</div>{s}</div>'
    )
    cls = "picker-card off2" if off else "picker-card"
    return f'<div class="{cls}" role="button" tabindex="0">{head}{rest}</div>'


def shipped_card(book: str) -> str:
    return (
        f'<div class="picker-card" role="button" tabindex="0">{CARDS[book]}</div>'
    )


# ── The codebook page head ──────────────────────────────────────────────────────────────────


def garrett_head() -> str:
    s = GARRETT["section"]
    a = s.find('<div class="pg-head">')
    b = s.find('<div class="v2-groups"')
    return s[a:b]


def garrett_groups(n: int = 3) -> str:
    s = GARRETT["section"]
    a = s.find('<div class="v2-groups"')
    groups = s[a:]
    # keep the first n groups
    parts = groups.split('<div class="codebook-group"')
    return parts[0] + "".join('<div class="codebook-group"' + p for p in parts[1 : n + 1])


GHEAD = garrett_head()


def review_row(meta: str, tentative: int | None, review: bool | str, uninstall: bool) -> str:
    und = f'<span class="undec"> · {E(t("codebook.tentativeCount_other", count=tentative))}</span>' if tentative else ""
    btns = ""
    if review:
        dis = " disabled" if review == "disabled" else ""
        btns += f'<button class="bn-btn bn-btn-secondary bn-btn-sm"{dis}>{E(t("codebook.reviewProposals"))}</button>'
    if uninstall:
        btns += f'<button class="bn-btn bn-btn-secondary bn-btn-sm">{E(t("codebook.removeFromCodebook"))}</button>'
    return f'<div class="pg-review-row"><span class="pg-review-meta">{E(meta)}{und}</span>{btns}</div>'


def page_head(state: str | None, row: str, title: str | None = None, author: str | None = None,
              off: bool = False, brief: bool = True, **kw: object) -> str:
    h = GHEAD
    h = re.sub(r'<div class="pg-titleaction">.*?</div>', "", h, count=1, flags=re.S)
    if title is not None:
        h = h.replace(
            '<div class="pg-title">The Elements of User Experience</div>',
            f'<div class="pg-title">{E(title)}</div>',
        )
    if author is not None:
        h = h.replace('<div class="pg-author">Jesse James Garrett</div>',
                      f'<div class="pg-author">{E(author)}</div>')
    s = slotbox(slot(state, **kw)) if state else ""
    # The title row is <titlerow><titletext><title/><author/></titletext></titlerow>: the slot goes
    # after the titletext's close, inside the row.
    h = re.sub(r'(<div class="pg-titlerow">.*?</div></div>)', lambda m: m.group(1) + s, h, count=1, flags=re.S)
    h = re.sub(r'<div class="pg-stat">.*?</div>', row, h, count=1, flags=re.S)
    if brief:
        # Title row and meta line only; the side gutter stays (empty) so the title has its real width.
        h = re.sub(r'<div class="pg-desc.*?</div>', "", h, count=1, flags=re.S)
        a = h.find('<div class="pg-side">')
        h = h[:a] + '<div class="pg-side"></div></div>'
    cls = ' class="pageoff"' if off else ""
    return f'<div{cls} data-testid="bn-v2-page">{h}</div>'


def page_section(head: str, groups: str = "") -> str:
    return f'<div class="v2-layout"><div class="v2-main">{head}{groups}</div></div>'


# ── Counts (§4) ─────────────────────────────────────────────────────────────────────────────

ROW_RE = re.compile(
    r'(<span class="tag-bar-area[^"]*"[^>]*>)(.*?)<span class="tag-count">(\d+)</span></span>', re.S
)


def no_zeros(groups_html: str) -> str:
    def fix(m: re.Match[str]) -> str:
        bar = m.group(2)
        accepted = int(m.group(3))
        tm = re.search(r'title="(\d+) tentative \+ (\d+) accepted"', bar)
        tentative = int(tm.group(1)) if tm else 0
        if accepted > 0:
            count = f'<span class="tag-count is-accepted">{accepted}</span>'
        elif tentative > 0:
            count = f'<span class="tag-count is-tentative">{tentative}</span>'
        else:
            count = '<span class="tag-count"></span>'
        return f"{m.group(1)}{bar}{count}</span>"

    return ROW_RE.sub(fix, groups_html)


def uxr_groups(n: int) -> str:
    s = UXR["section"]
    a = s.find('<div class="v2-groups"')
    parts = s[a:].split('<div class="codebook-group"')
    return parts[0] + "".join('<div class="codebook-group"' + p for p in parts[1 : n + 1]) + "</div>"


# ── Catalogue chrome (§5) ───────────────────────────────────────────────────────────────────


def sidebar(active: bool) -> str:
    sb = UXR["sidebar"]
    if not active:
        # On the library: no codebook is current, and the sidebar's own Browse button stays,
        # disabled (the shipped `.bn-btn:disabled`), since the library is what it opens.
        sb = sb.replace("v2-nav-row active", "v2-nav-row").replace(' aria-current="location"', "")
        sb = sb.replace('data-testid="bn-v2-nav-browse">', 'data-testid="bn-v2-nav-browse" disabled>')
    return sb


def heading(text: str, action: bool) -> str:
    act = (
        '<div class="section-heading-action"><button class="bn-btn bn-btn-secondary bn-btn-lg">'
        f'{E(t("codebook.browseCodebooksButton"))}</button></div>'
        if action
        else ""
    )
    return f'<div class="section-heading"><h1>{E(text)}</h1>{act}</div>'


def app(side: str, main: str, width: int = 1132) -> str:
    return (
        f'<div class="app" style="width:{width}px"><div class="app-side">{side}</div>'
        f'<div class="app-main"><section>{main}</section></div></div>'
    )


# ── Frames ──────────────────────────────────────────────────────────────────────────────────


def frame(tag: str, note: str, body: str, cls: str = "", owner: bool = False) -> str:
    own = '<span class="own">new words, decided 24 Nov, not yet keys: AutoCode · AutoCoding… · Applied</span>' if owner else ""
    return (
        f'<figure class="frame {cls}"><figcaption class="chrome"><span class="tag">{E(tag)}</span>'
        f"<span>{E(note)}</span>{own}<span class=\"delta\"></span></figcaption>"
        f'<div class="surface">{body}</div></figure>'
    )


def specimen() -> str:
    rows = []
    for label, cls in (("Card or page", "card"),):
        cells = []
        for state, kw, cap in (
            ("act", {"variant": "primary"}, "button · primary (chosen for now, 24 Nov)"),
            ("act", {"variant": "secondary"}, "button · secondary"),
            ("run", {}, "running · plain text"),
            ("done", {}, "applied · on"),
            ("done", {}, "applied · switched off"),
        ):
            off = cap.endswith("off")
            inner = slot(state, **kw)
            wrap = f'<span class="{"spec-off" if off else ""}">{inner}</span>'
            cells.append(f'<td><div class="spec-cell spec-{cls}" data-measure="{E(cap)}">{wrap}</div><div class="spec-cap">{E(cap)}</div></td>')
        rows.append(f'<tr><th>{label}</th>{"".join(cells)}</tr>')
    # Inside .v2-layout: the shipped small size is scoped there (codebook-v2.css).
    return f'<div class="v2-layout"><table class="spec">{"".join(rows)}</table></div>'


def running_options() -> str:
    rows = []
    for colour, name in (("muted", "muted ink"), ("text", "body ink"), ("accent", "accent"), ("green", "system green")):
        cells = []
        for dots, cap in ((False, "shimmer"), (True, "shimmer + growing ellipsis")):
            c = card("garrett", "run", colour=colour, dots=dots)
            if colour == "muted" and dots:
                cap += " (chosen 24 Nov)"
            cells.append(f'<td><div class="v2-layout al-base"><div class="v2-card-grid one">{c}</div></div><div class="spec-cap">{E(cap)}</div></td>')
        rows.append(f'<tr><th>{E(name)}</th>{"".join(cells)}</tr>')
    return f'<table class="spec runs">{"".join(rows)}</table>'


LONG = "10 Usability Heuristics for User Interface Design"


def alignment() -> str:
    out = []
    for al, name in (("al-top", "A, not chosen — as built for 6c: card marker at the card's top-right inset; page button top-flush"),
                     ("al-base", "B, chosen 24 Nov — the slot's words on the title's first baseline"),
                     ("al-centre", "C, not chosen — the slot centred on the title's first line")):
        cards = (
            f'<div class="v2-card-grid three">{card("nielsen", "act")}'
            f'{card("nielsen", "done")}{card("yablonski", "run")}</div>'
        )
        pages = (
            page_section(page_head("act", '<div class="pg-stat">24 tags · not installed</div>',
                                   title="Laws of UX", author="Jon Yablonski"))
            + page_section(page_head("done", review_row("34 tags · applied to 12 quotes in Demo study", 7, True, True),
                                     title=LONG, author="Jakob Nielsen"))
        )
        out.append(frame(name.split(" — ")[0], name.split(" — ")[1],
                         f'<div class="v2-layout {al}">{cards}</div><div class="v2-layout {al} pages">{pages}</div>',
                         cls="align", owner=True))
    return "".join(out)


EXPLAIN = ("AutoCode proposes one of these 18 tags for each of the 24 quotes in Demo study and applies the most "
           "confident. The rest wait for your review.")


def sequence() -> str:
    moments = [
        ("1 · before", "nothing installed; the explainer line corrected", "act",
         "18 tags · not installed", None, False, False, False),
        ("2 · running", "Review present, inactive (D17); Uninstall hidden while the run spends (decided)", "run",
         "18 tags · applied to 4 quotes in Demo study", 3, "disabled", False, False),
        ("3 · done", "proposals to review", "done",
         "18 tags · applied to 12 quotes in Demo study", 7, True, True, False),
        ("4 · done, nothing tentative", "Review still opens the whole run (D39)", "done",
         "18 tags · applied to 19 quotes in Demo study", None, True, True, False),
        ("5 · switched off", "shipped knock-back; the cartouche goes neutral", "done",
         "18 tags · applied to 19 quotes in Demo study", None, True, True, True),
        ("6 · stopped, failed, or never started", "installed, not applied: the button again, to resume (decided)", "act",
         "18 tags · applied to 6 quotes in Demo study", 2, True, True, False),
    ]
    out = []
    for tag, note, state, meta, tent, review, uninst, off in moments:
        row = (f'<div class="pg-stat">{E(meta)}</div><div class="pg-stat">{E(EXPLAIN)}</div>' if tag.startswith("1")
               else review_row(meta, tent, review, uninst))
        c = card("garrett", state, off=off, status=meta.replace(" · not installed", ""))
        p = page_section(page_head(state, row, off=off, brief=not tag.startswith("3")))
        body = (f'<div class="seq"><div class="v2-layout al-base"><div class="v2-card-grid one">{c}</div></div>'
                f'<div class="v2-layout al-base">{p}</div></div>')
        out.append(frame(tag, note, body, cls="seqf", owner=True))
    return "".join(out)


def counts() -> str:
    before = f'<div class="v2-layout"><div class="v2-main">{uxr_groups(3)}</div></div>'
    after = f'<div class="v2-layout"><div class="v2-main">{no_zeros(uxr_groups(3))}</div></div>'
    return (frame("Shipped, chosen 24 Nov", "a zero on every row; pale bars beside a 0", before, cls="counts")
            + frame("Proposed, not chosen", "the tag sidebar's rule: accepted in ink, tentative-only muted, else blank", after, cls="counts"))


def catalogue() -> str:
    shipped_cards = "".join(shipped_card(b) for b in ("sentiment", "uxr", "cli-ux", "garrett", "morville", "nielsen"))
    before = app(sidebar(True), heading("Codebooks", True)
                 + f'<div class="v2-layout"><div class="v2-main"><div class="v2-card-grid">{shipped_cards}</div></div></div>')
    cards = (card("sentiment", "done") + card("uxr", "done") + card("cli-ux", "act") + card("garrett", "run", status="18 tags · applied to 4 quotes in Demo study")
             + card("morville", "act") + card("nielsen", "act"))
    after = app(sidebar(False), heading(t("codebook.browseCodebooks"), False)
                + f'<div class="v2-layout al-base"><div class="v2-main"><div class="v2-card-grid">{cards}</div></div></div>')
    return (frame("Shipped, not chosen", "Browse button on the catalogue itself; UXR still current in the sidebar", before, cls="wide")
            + frame("Proposed, chosen 24 Nov", "heading “Codebook Library” (shipped key), no action; the sidebar’s Browse disabled, nothing current; the slot on each card", after, cls="wide", owner=True))


# ── The page ────────────────────────────────────────────────────────────────────────────────

NEW_CSS = """
/* ════ NEW: the slot, its title rows, and the page's counts (hand-written; tokens only) ════ */
/* macOS system green, as 6c (24 Oct): sampled NSColor.systemGreen on macOS 27, and WebKit's live
   colour where it exists. Not a theme token yet: --bn-colour-positive is a Tailwind green. */
:root { --cb-green: light-dark(#34C759, #30D158); }
@supports (color: -apple-system-green) { :root { --cb-green: -apple-system-green; } }

/* A card's title and its slot share one row: the review's ask (no fixed padding-right). */
.picker-card-titlerow { display: flex; justify-content: space-between; gap: var(--bn-space-sm); }
.picker-card-titlerow .picker-card-title { min-width: 0; }
.picker-card-titlerow > .cb-slotbox { flex-shrink: 0; }
.pg-titlerow > .cb-slotbox { flex-shrink: 0; }

/* Alignment variants. A: top edges flush. B: first baselines. C: centred in one title line. */
.al-top .picker-card-titlerow, .al-top .pg-titlerow { align-items: flex-start; }
/* A on a card is the 6c construction as built 24 Oct: the marker absolutely at the card's top-right
   inset (.cat-corner: top/right var(--bn-space-md)), the title cleared by padding. */
.al-top .picker-card-titlerow { padding-right: 7em; }
.al-top .picker-card-titlerow > .cb-slotbox { position: absolute; top: var(--bn-space-md); right: var(--bn-space-md); }
.al-base .picker-card-titlerow, .al-base .pg-titlerow { align-items: baseline; }
.al-centre .picker-card-titlerow, .al-centre .pg-titlerow { align-items: flex-start; }
.cb-slotbox { display: inline-flex; }
.al-centre .cb-slotbox { align-items: center; height: 1lh; }
.al-centre .picker-card-titlerow > .cb-slotbox { font-size: var(--bn-text-label); }
.al-centre .pg-titlerow > .cb-slotbox { font-size: var(--bn-text-title); line-height: 1.2; }

/* Button: the shipped small button; nothing new but the class hook. */
.cb-act { white-space: nowrap; }

/* Running: plain words. Not a control: no box, no hover, the arrow cursor. */
.cb-running {
    font-size: var(--bn-text-caption);
    font-weight: var(--bn-weight-emphasis);
    white-space: nowrap;
    cursor: default;
    --bn-shimmer-base: var(--bn-colour-muted);
    color: var(--bn-shimmer-base);
}
.cb-running.run-text   { --bn-shimmer-base: var(--bn-colour-text); }
.cb-running.run-accent { --bn-shimmer-base: var(--bn-colour-accent); }
.cb-running.run-green  { --bn-shimmer-base: var(--cb-green); }
.cb-dots i { font-style: normal; }
/* The ellipsis grows ". .. ..." and repeats. Dots fade by opacity, never display, so the
   slot's width holds still. Frozen (animation off, reduced motion) it reads as a plain "...". */
@media (prefers-reduced-motion: no-preference) {
    :root:not([data-analysis-animation="off"]) .cb-dots i:nth-child(2) { animation: cb-dot2 1.5s steps(1, end) infinite; }
    :root:not([data-analysis-animation="off"]) .cb-dots i:nth-child(3) { animation: cb-dot3 1.5s steps(1, end) infinite; }
}
@keyframes cb-dot2 { 0% { opacity: 0; } 33.33%, 100% { opacity: 1; } }
@keyframes cb-dot3 { 0% { opacity: 0; } 66.67%, 100% { opacity: 1; } }

/* Applied: the 6c cartouche. A status badge: no hover, no focus. Body font, never the tag
   pill's mono, so it cannot read as a tag called "Applied". */
.cb-applied {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3em;
    font-size: var(--bn-text-caption);
    font-weight: var(--bn-weight-emphasis);
    color: var(--bn-colour-text);
    padding: 0.15em 0.55em;
    border-radius: var(--bn-radius-pill);
    background: color-mix(in srgb, var(--cb-green) 8%, transparent);
    white-space: nowrap;
    cursor: default;
}
.cb-applied .bn-icon { align-self: center; color: var(--cb-green); font-size: 1.15em; --bn-icon-stem: var(--bn-icon-stem-strong); }
.off2 .cb-applied, .pageoff .cb-applied, .spec-off .cb-applied { background: var(--bn-colour-badge-bg); }
.off2 .cb-applied .bn-icon, .pageoff .cb-applied .bn-icon, .spec-off .cb-applied .bn-icon { color: var(--bn-colour-muted); }

/* Counts: the tag sidebar's rule (organisms/sidebar-tags.css `.tag-sidebar .tag-count.is-accepted`)
   on the codebook page. Muted by default already; only the accepted count takes ink. */
.v2-groups .tag-count.is-accepted { color: var(--bn-colour-text); }

/* Uninstall beside Review: the shipped row already gaps its children. */
"""

CHROME_CSS = """
/* ════ Mockup chrome — not the product ════ */
html { color-scheme: light dark; }
html[data-scheme="light"] { color-scheme: light; }
html[data-scheme="dark"] { color-scheme: dark; }
body.mock { margin: 0; padding: 0 0 4rem; font-family: var(--bn-font-body); font-size: var(--bn-text-label);
  color: var(--bn-colour-text); background: light-dark(#eceef1, #161617); }
.bar { position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap; gap: 1rem; align-items: center;
  padding: 0.6rem 2rem; background: light-dark(#e2e5e9, #222); border-bottom: 1px solid light-dark(#cfd3d8, #333);
  font: 12px/1.3 ui-monospace, Menlo, monospace; }
.bar label { display: inline-flex; gap: 0.3rem; align-items: center; }
.bar select { font: inherit; }
.wrap { max-width: 1240px; margin: 0 auto; padding: 0 2rem; }
h1.mock-title { font: 600 1.6rem/1.2 var(--bn-font-body); margin: 2rem 0 0.4rem; max-width: none; }
h2.step { font: 600 1.05rem/1.3 var(--bn-font-body); margin: 3rem 0 0.8rem; max-width: none; }
.key { font: 12px/1.5 ui-monospace, Menlo, monospace; color: light-dark(#555, #aaa); max-width: 60rem; }
.frame { margin: 0 0 1.2rem; background: var(--bn-colour-bg); border-radius: 10px; overflow: hidden;
  box-shadow: 0 0 0 1px light-dark(rgb(0 0 0 / 0.12), rgb(255 255 255 / 0.12)), 0 6px 20px rgb(0 0 0 / 0.08);
  color: var(--bn-colour-text); }
.chrome { display: flex; gap: 0.8rem; align-items: baseline; flex-wrap: wrap; padding: 0.45rem 0.9rem;
  font: 11.5px/1.4 ui-monospace, Menlo, monospace; color: light-dark(#555, #aaa);
  background: light-dark(#f3f4f6, #2a2a2b); border-bottom: 1px solid light-dark(#e2e4e8, #3a3a3a); }
.chrome .tag { font-weight: 700; color: light-dark(#222, #eee); }
.chrome .own { color: light-dark(#8a4b00, #f0b45a); }
.chrome .delta { margin-left: auto; }
.surface { padding: 1.5rem; }
.app { display: flex; min-height: 0; }
.app-side { flex: 0 0 240px; }
.app-side .toc-sidebar { position: static; height: auto; min-height: 100%; }
.app-main { flex: 1; min-width: 0; padding: 0 0.5rem 1.5rem 2rem; }
.wide .surface { padding: 0; overflow-x: auto; }
.v2-card-grid.one { grid-template-columns: minmax(0, 330px); }
.v2-card-grid.three { grid-template-columns: repeat(3, minmax(0, 300px)); margin-bottom: 1.5rem; }
.pages .v2-layout + .v2-layout { margin-top: 1.5rem; }
.pages { width: 892px; }
.seq { display: grid; grid-template-columns: 330px; gap: 1.2rem; }
.seq > .v2-layout:last-child { width: 892px; }  /* the lens's measured width with the sidebar open (1280px window) */
.seq .pg-head { margin-bottom: 0; }
.counts .surface { max-width: 900px; }
table.spec { border-collapse: separate; border-spacing: 1.2rem 0.6rem; background: var(--bn-colour-bg);
  border-radius: 10px; padding: 0.5rem; }
table.spec th { font: 600 12px ui-monospace, Menlo, monospace; text-align: right; color: light-dark(#555, #aaa); }
.spec-cell { display: flex; align-items: center; min-height: 2.2rem; }
.spec-page { font-size: var(--bn-text-title); }
.spec-off { opacity: var(--bn-opacity-off); }  /* the card's shipped knock-back (.off2), drawn on the specimen */
.spec-cap { font: 11px ui-monospace, Menlo, monospace; color: light-dark(#777, #999); }
table.runs td { vertical-align: top; }
.guides .baseline-guide { position: absolute; left: 0; right: 0; height: 0;
  border-top: 1px solid light-dark(rgb(255 0 80 / 0.6), rgb(255 90 140 / 0.7)); pointer-events: none; }
.guides .align .picker-card, .guides .align .pg-head { position: relative; }
.commentary { margin: 1rem 0 2rem; padding: 1rem 1.3rem; max-width: 62rem; font: 14px/1.55 var(--bn-font-body);
  border: 7px solid transparent; border-left: 3px solid light-dark(#b0763a, #d49a5c);
  background: linear-gradient(light-dark(#eceef1, #161617), light-dark(#eceef1, #161617)) padding-box,
    repeating-linear-gradient(135deg, light-dark(#d9c7b2, #4a3a2a) 0 5px, transparent 5px 10px) border-box; }
.commentary .lbl { font: 700 11px ui-monospace, Menlo, monospace; letter-spacing: 0.08em; text-transform: uppercase;
  color: light-dark(#8a4b00, #f0b45a); }
.commentary table { border-collapse: collapse; margin: 0.6rem 0; font-size: 13px; }
.commentary td, .commentary th { border-bottom: 1px solid light-dark(#d6d6d6, #3a3a3a); padding: 0.3rem 0.7rem 0.3rem 0;
  text-align: left; vertical-align: top; }
.commentary code { font: 12px ui-monospace, Menlo, monospace; }
.rm-note { display: none; color: light-dark(#8a4b00, #f0b45a); }
@media (prefers-reduced-motion: reduce) { .rm-note { display: inline; } }
"""

SCRIPT = """
(() => {
  const root = document.documentElement;
  const set = (k, v) => { if (v === '') root.removeAttribute(k); else root.setAttribute(k, v); };
  document.getElementById('c-platform').onchange = e => set('data-platform', e.target.value);
  document.getElementById('c-palette').onchange = e => set('data-color-theme', e.target.value);
  document.getElementById('c-scheme').onchange = e => set('data-scheme', e.target.value);
  document.getElementById('c-motion').onchange = e => set('data-analysis-animation', e.target.checked ? '' : 'off');
  const guides = document.getElementById('c-guides');
  function baselineOf(el) {
    const p = document.createElement('span');
    p.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
    el.insertBefore(p, el.firstChild);
    const y = p.getBoundingClientRect().top; p.remove(); return y;
  }
  function slotBaseline(box) {
    const words = box.querySelector('.cb-applied > span:last-child, .cb-running, .cb-act');
    const probe = document.createElement('span');
    probe.style.cssText = 'display:inline-block;width:0;height:0;vertical-align:baseline';
    words.appendChild(probe); const y = probe.getBoundingClientRect().top; probe.remove(); return y;
  }
  function measure() {
    document.querySelectorAll('.baseline-guide').forEach(g => g.remove());
    document.querySelectorAll('.frame.align').forEach(f => {
      const ds = [];
      f.querySelectorAll('.picker-card-titlerow, .pg-titlerow').forEach(row => {
        const title = row.querySelector('.picker-card-title, .pg-title');
        const box = row.querySelector('.cb-slotbox'); if (!title || !box) return;
        const tb = baselineOf(title), sb = slotBaseline(box);
        ds.push((sb - tb));
        if (guides.checked) {
          const host = row.closest('.picker-card, .pg-head');
          const g = document.createElement('div'); g.className = 'baseline-guide';
          g.style.top = (tb - host.getBoundingClientRect().top) + 'px'; host.appendChild(g);
        }
      });
      const fmt = d => (d > 0 ? '+' : '') + d.toFixed(1);
      f.querySelector('.delta').textContent = 'slot baseline − title baseline (px, live): ' + ds.map(fmt).join(' · ');
    });
    const w = document.getElementById('widths');
    if (w) {
      w.innerHTML = '';
      document.querySelectorAll('.spec-cell').forEach(c => {
        const el = c.firstElementChild.firstElementChild;
        const r = el.getBoundingClientRect();
        const tr = document.createElement('tr');
        tr.innerHTML = '<td>' + (c.classList.contains('spec-page') ? 'page' : 'card') + '</td><td>' +
          c.dataset.measure + '</td><td>' + r.width.toFixed(1) + ' × ' + r.height.toFixed(1) + '</td>';
        w.appendChild(tr);
      });
    }
  }
  guides.onchange = () => { document.body.classList.toggle('guides', guides.checked); measure(); };
  ['c-platform','c-palette','c-scheme'].forEach(id => document.getElementById(id).addEventListener('change', () => setTimeout(measure, 50)));
  window.addEventListener('load', measure);
  document.fonts && document.fonts.ready.then(measure);
})();
"""


def commentary(title: str, body: str) -> str:
    return f'<div class="commentary"><div class="lbl">Commentary · {E(title)}</div>{body}</div>'


def build() -> str:
    css = "".join(css_block(f) for f in CSS_FILES)
    css += "".join(css_rule("templates/report.css", r) for r in REPORT_RULES)
    css += NEW_CSS + CHROME_CSS

    strings = (
        "<table><tr><th>Where</th><th>Words drawn</th><th>Status</th></tr>"
        f"<tr><td>Slot, before</td><td>{W_ACT}</td><td>new key (owner, 24 Nov), replaces the shipped “{E(t('codebook.importCodebook'))}” (<code>codebook.importCodebook</code>) on this button</td></tr>"
        f"<tr><td>Slot, running</td><td>{W_RUN}…</td><td>new key; spelled as the shipped toast “{E(t('autocode.toast.progress', processed='N', total='M'))}”</td></tr>"
        f"<tr><td>Slot, done</td><td>{W_DONE}</td><td>new key (owner, 24 Nov), replaces the 6c “Installed”</td></tr>"
        f"<tr><td>Catalogue heading</td><td>{E(t('codebook.browseCodebooks'))}</td><td>shipped key <code>codebook.browseCodebooks</code>, 21 locales</td></tr>"
        f"<tr><td>Explainer, before</td><td>{E(EXPLAIN)}</td><td>owner-written, replaces the 6c draft’s “Nothing is applied until you review the proposals” (untrue since the default cut); pluralised on both counts; no cost warning</td></tr>"
        "<tr><td>Codebook page heading</td><td>Codebook</td><td>new key; each locale's value is the <code>Codebook</code> row of <code>locales/glossary.csv</code> (today a hard-coded English literal)</td></tr>"
        f"<tr><td>Meta line</td><td>“{E(t('codebook.notInstalled'))}”, “{E(t('codebook.tentativeCount_other', count=7))}”, {E(t('codebook.reviewProposals'))}, {E(t('codebook.removeFromCodebook'))}</td><td>shipped keys</td></tr>"
        "</table>"
    )

    body = f"""
<div class="bar">
  <label>platform <select id="c-platform"><option value="desktop" selected>Mac (SF Pro, HIG scale)</option><option value="">web (Inter)</option></select></label>
  <label>palette <select id="c-palette"><option value="edo" selected>edo (Mac default)</option><option value="default">default</option></select></label>
  <label>scheme <select id="c-scheme"><option value="" selected>auto</option><option value="light">light</option><option value="dark">dark</option></select></label>
  <label><input type="checkbox" id="c-motion" checked> motion</label>
  <label><input type="checkbox" id="c-guides"> title-baseline guides</label>
  <span class="rm-note">your system's reduced motion freezes the shimmer whatever the toggle says</span>
</div>
<div class="wrap">
<h1 class="mock-title">Codebook pages: the Applied slot, its alignment, counts, the catalogue</h1>
<p class="key">For discussion, not a decision. <b>Framed panes are the product</b>: shipped markup captured from a running
<code>serve --dev</code> (24 Nov 2026, a private trial run renamed “Demo study”) at shipped CSS, edited only where the
proposal changes it. Words marked <span style="color:#b06a00">owner-written</span> in a frame's bar are not shipped yet.
<b>Hatched blocks are commentary.</b> Builds on the 6c marker chosen 24 Oct
(<code>docs/mockups/codebook-catalogue-install-on-page.html</code>). Generated by <code>codebook-applied-slot.gen.py</code>; regenerate, don't edit.</p>

{commentary("the decisions this page draws (owner, 24 Nov 2026)", '''
<ol>
<li>One top-right slot on the catalogue card <i>and</i> the codebook page, always in the same state: a button → plain
shimmering words while AutoCode runs → the green “Applied” cartouche when the run completes.</li>
<li>The button is our regular button, one size down (<code>bn-btn-sm</code>, the button radius). The cartouche is a
status badge (pill radius, not interactive). The running words have no box and are not clickable.</li>
<li>The AutoCode button is primary, small, for now (owner, 24 Nov).</li>
<li>A run that completes says Applied however little it applied, none included. A run that ends with a failure, whole or partial (some batches failed), brings the button back, to resume (owner, 24 Nov).</li>
<li>Sentiment shows Applied and never a button: the pipeline applies it (D20; confirmed by the owner, 24 Nov).</li>
<li>No Uninstall on cards. On the page, Uninstall is a small secondary button beside Review.</li>
<li>Installed but not applied (stopped, failed, refused): the button comes back, to resume. Uninstall is hidden while a run goes; switching a codebook off mid-run stops the run. Review shows whenever there are tags (D39). The explainer says the most confident proposals are applied; no cost warning.</li>
<li>The codebook page's counts stay as shipped, zeros included (§4).</li>
<li>The catalogue is headed “Codebook Library” (the shipped key), with no Browse button in its heading; the sidebar keeps its Browse button, disabled, and has no current row (§5).</li>
<li>The slot's words sit on the title's first baseline (alignment B, §2), on card and page alike.</li>
<li>While it runs, the words are muted ink with the shimmer and an ellipsis that grows “. .. ...” and repeats (§1b).</li>
<li>The words: AutoCode → AutoCoding… → Applied (decided 24 Nov; “Install” was the browser-extension model, and what the researcher cares about is whether the tags are applied). Parked: animating the swap, if it jars.</li>
</ol>''')}

<h2 class="step">1 · The three states, at real size</h2>
{specimen()}
{commentary("widths, measured live in your browser", '''<p>The slot changes width twice. Measured here, per platform
and palette you pick above (the table updates when you switch):</p><table><tbody id="widths"></tbody></table>
<p>Measured 24 Nov on the Mac scale: button 80.5 × 24.5, running words 78.5 × 14.5, cartouche 74.8 × 18.1 px. The widths differ by about 6 px; the height changes most, and under alignment B (§2) the words stay on the title's baseline through all three, so the swap may not need animating at all.</p>
<p>One row, because the slot is the same size on a card and on a page: its type is the caption size in both (same
state, same look). The switched-off cartouche is drawn at the card's shipped half opacity. In the Edo palette the muted
ink is a blue-grey (<code>#4a698a</code>), which is why the running words read bluish there; switch to the default palette to
see a neutral grey.</p>''')}

<h2 class="step">1b · The running words: four colours, with and without a growing ellipsis</h2>
{running_options()}
{commentary("running", '''<p>The shimmer is the house “working” motion (<code>atoms/shimmer.css</code>, the same as
“Picking up Signals…” and the Mac row's “AutoCode · N of M”). The growing ellipsis (one dot, two, three, again) is a second
motion on one word, and nothing shipped animates an ellipsis today, so it is a new pattern. Both freeze under the app's animation switch and system reduced motion (try the
<b>motion</b> toggle). <b>Muted ink</b> reads as “not yours to press” and matches the Mac row; <b>green</b> previews the
cartouche it becomes but looks like a status that has already arrived; <b>accent</b> reads as a link. <b>Chosen (owner, 24 Nov): muted ink, shimmer and the growing ellipsis</b>; every other running
slot on this page draws it. The dots fade rather than appear, so the width holds still.</p>''')}

<h2 class="step">2 · Alignment against the title (tick the guides above)</h2>
{alignment()}
{commentary("alignment", '''<p>The bar of each frame prints the live distance from the title's first baseline to the
slot's words: negative means the slot sits higher. <b>A</b> is the 6c construction (top edges flush), which is what makes
the slot read higher than the headline: the button's box starts at the title's ascender line, so its words sit above the
title's baseline. <b>B</b> puts the words on the title's baseline, on a 13px card title and a 22px page title alike, and
holds when the title wraps (flexbox aligns <i>first</i> baselines). <b>C</b> centres the slot in the title's first line box,
which is optically closest on the page (big title, small slot) but leaves the words off the baseline. <b>Chosen (owner, 24 Nov): B</b>, which is
also the one the running words and the cartouche need no special case for. A and C stay drawn for the record.</p>''')}

<h2 class="step">3 · One codebook through the run: card and page side by side</h2>
{sequence()}
{commentary("the run (owner, 24 Nov: 1, 2, 3, 4 and 6 decided)", '''<p>All frames use alignment B.
<b>1, before:</b> the explainer line is corrected. The 6c draft said “Nothing is applied until you review the proposals”,
untrue since the default cut accepts the most confident proposals at the end of a first run (about the top 30%, never
below 0.70; under 0.30 is excluded; the band between waits for review: <code>autocode.py:945</code>). No cost warning
(owner). <b>2, running:</b> Review stays where it will be but inactive (D17; the server refuses a re-cut mid-run, D49).
Uninstall is hidden while the run goes (decided). Owed on the server: nothing stops an uninstall mid-run today, the job
row is deleted and the run keeps calling the model (<code>remove_framework</code>, <code>codebook.py:844</code>; the
run's stop check reads only <code>cancelled</code>, <code>autocode.py:646</code>). Switching the codebook off mid-run
stops the run (decided; today it does not). <b>4:</b> the Review door shows whenever the codebook has tags (D39),
accepted: Uninstall always has Review beside it once anything is applied. <b>5:</b> the card's shipped knock-back is
half opacity on the whole card, so the neutral cartouche is faint too. <b>6, installed but not applied</b> (a start
refused for want of a key, a Stop, a failure such as out of credit): the button again, meaning “resume” (decided). It
needs a start-only action: today Install would be answered 409. The failure itself is said where it happens, not in the
slot: a refused start is a toast on both platforms (<code>CodebookV2.tsx</code> <code>reportStartError</code>); a run that
fails or stops ends its AutoCode toast as failed or stopped, and on the Mac with the AppKit sidebar the toast is hidden
and the project row's line says it. Once the toast is gone, the button coming back is the only lasting sign.</p>
<p><b>Stopping a run, as shipped</b> (checked in code, 24 Nov). <b>Browser:</b> Cancel on the AutoCode toast
(<code>AppLayout.tsx</code>, hidden only while the last tags land). <b>Mac, default sidebar</b> (SwiftUI): the same toast
and its Cancel (the report hides it only when <code>BristlenoseAppKitSidebar</code> is on, <code>WebView.swift:173</code>),
plus <b>Project ▸ Stop AutoCode</b> in the menu bar, which does not depend on the sidebar (<code>MenuCommands.swift:1515</code>;
no ⌘. for AutoCode, by design). <b>Mac, AppKit sidebar</b> (flag on): the toast is hidden; the row's ring hover ×, its
context menu Stop AutoCode, and the same menu-bar item. <b>The catch-up has no Cancel, and that is fine for v1</b> (owner, 24 Nov): the
“recoding” toast after a codebook is switched back on, and the silent passes for an unhidden quote, new sessions or a
newly saved key, are work the researcher expects to just happen and to cost what it costs, as Signals' catch-up does.
Switching the codebook off stops one at its next batch.</p>''')}

<h2 class="step">4 · Counts: shipped kept</h2>
{counts()}
{commentary("counts", '''<p>The tag sidebar already does this (<code>frontend/src/components/TagRow.tsx</code>: “one
digit per row, and never a zero”). The page does not (<code>CodebookAuthoring.tsx</code> prints <code>tag.count</code>
always), so “friction” and “exploration” show a pale bar beside a 0. Proposed: the same rule, so the two surfaces agree.
The group's Total row already hides at zero. <b>Chosen (owner, 24 Nov): shipped</b>, a zero on every row; the proposal stays drawn for the record.</p>''')}

<h2 class="step">5 · The catalogue's own chrome: proposed chosen</h2>
{catalogue()}
{commentary("catalogue", '''<p>The heading's “Browse Codebooks” on the catalogue goes nowhere, so it is not shown; the export already
leaves the action slot empty and keeps the row's height (Q14). The sidebar's own Browse button stays where it always is,
disabled (owner, 24 Nov): the library is what it opens, and a button that vanishes moves the rows under it. On the
catalogue no codebook is current, so the sidebar shows none. The
heading becomes the shipped “Codebook Library”, the name the reinstall sentences already send people to. Sentiment's card
carries “Applied” too: it is applied by the pipeline and has no button (D20). <b>Chosen (owner, 24 Nov): proposed</b>, the “Codebook Library” heading included.</p>''')}

<h2 class="step">Strings</h2>
{commentary("what is shipped and what is new", strings)}
</div>
"""
    return (
        '<!DOCTYPE html>\n<html lang="en" data-platform="desktop" data-color-theme="edo">\n<head>\n'
        '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Codebook Applied slot</title>\n"
        "<!-- bn-accurate. Generated by docs/mockups/codebook-applied-slot.gen.py: shipped CSS from the theme "
        "files named in the block headers, markup captured from a running serve. Regenerate rather than edit. -->\n"
        f"<style>\n{css}</style>\n</head>\n<body class=\"mock\">\n{body}\n<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
