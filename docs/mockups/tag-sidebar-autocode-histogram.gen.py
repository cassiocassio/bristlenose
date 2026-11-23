#!/usr/bin/env python3
"""Generate docs/mockups/tag-sidebar-autocode-histogram.html.

A small AutoCode confidence histogram at the top of the tag sidebar, opened from
the "N tags across M frameworks" line by a disclosure chevron, with a Review link
that opens the existing threshold dialog. Owner's idea, 23 Nov 2026, from the
landing lab (experiments/autocode-landing/).

Shipped CSS is read from the tree, each block headed with its path and line range.
Shipped words are read by key from the en locale. The one new element, the
overview block itself, has its own hand-written CSS under a "NEW" heading, using
tokens only. Proposals and confidences are the Talismanic UXR run (public test
data, codes only); the second codebook in frame 5 is an invented shape, and says so.

    .venv/bin/python docs/mockups/tag-sidebar-autocode-histogram.gen.py [--db <bristlenose.db>]
"""

from __future__ import annotations

import argparse
import html
import json
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/tag-sidebar-autocode-histogram.html"
THEME = ROOT / "bristlenose/theme"
CSS = [
    "tokens.css",
    "tokens-typography.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "atoms/badge.css",
    "atoms/checkbox.css",
    "molecules/tag-filter.css",
    "molecules/threshold-review.css",
    "organisms/codebook-panel.css",
    "organisms/sidebar.css",
    "organisms/sidebar-tags.css",
]
PRIVATE_RUNS = ROOT / "trial-runs"  # gitignored
DEFAULT_DB = PRIVATE_RUNS / "again" / "bristlenose-output" / ".bristlenose" / "bristlenose.db"
COMMON = json.loads((ROOT / "bristlenose/locales/en/common.json").read_text(encoding="utf-8"))
SLOTS = {"ux": 5, "emo": 6, "task": 5, "trust": 5, "opp": 5}
UPPER, LOWER = 0.70, 0.30
E = html.escape


def t(path: str, **values: object) -> str:
    node: object = COMMON
    for part in path.split("."):
        node = node[part]  # type: ignore[index]
    text = str(node)
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", str(value))
    return text


def css_blocks() -> str:
    out = []
    for rel in CSS:
        text = (THEME / rel).read_text(encoding="utf-8")
        last = text.count("\n") + 1
        out.append("/* ════ bristlenose/theme/" + rel + " — lines 1–" + str(last) + " ════ */\n" + text)
    return "\n".join(out)


def read_run(db_path: Path) -> dict:
    db = sqlite3.connect("file:" + str(db_path) + "?mode=ro", uri=True)
    groups = db.execute(
        "select id, name, subtitle, colour_set from codebook_groups where framework_id='uxr' "
        "order by sort_order"
    ).fetchall()
    tags = []
    for gid, gname, gsub, cset in groups:
        rows = db.execute(
            "select id, name from tag_definitions where codebook_group_id=? order by id", (gid,)
        ).fetchall()
        for idx, (tid, tname) in enumerate(rows):
            tags.append({"id": tid, "name": tname, "group": gname, "sub": gsub, "set": cset, "idx": idx})
    job = db.execute("select id from autocode_jobs where framework_id='uxr' order by id desc").fetchone()
    props = db.execute(
        "select p.quote_id, p.tag_definition_id, p.confidence from proposed_tags p "
        "where p.job_id=? order by p.quote_id",
        (job[0],),
    ).fetchall()
    quotes = db.execute("select count(*) from quotes").fetchone()[0]
    return {"groups": groups, "tags": tags, "props": props, "quotes": quotes}


def zone(conf: float, lo: float = LOWER, hi: float = UPPER) -> str:
    if conf >= hi:
        return "acc"
    if conf < lo:
        return "exc"
    return "ten"


# A proposal as drawn: (confidence, its codebook's exclude line, its codebook's accept line).
# Each codebook keeps its own lines (stored on its AutoCode job when applied), so a merged
# chart colours every proposal by its own codebook's cut.
Item = tuple[float, float, float]


def items_of(confs: list[float], lines: tuple[float, float]) -> list[Item]:
    return [(c, lines[0], lines[1]) for c in confs]


def bins_of(items: list[Item]) -> list[dict]:
    bins = [{"acc": 0, "ten": 0, "exc": 0} for _ in range(20)]
    for c, lo, hi in items:
        bins[min(19, int(c * 20))][zone(c, lo, hi)] += 1
    return bins


def histogram(items: list[Item], scale: int, variant: str, lines: tuple[float, float] | None) -> str:
    bins = bins_of(items)
    tally = {"acc": 0, "ten": 0, "exc": 0}
    for b in bins:
        for k in tally:
            tally[k] += b[k]
    label = tally_text(tally)
    cols = []
    for b in bins:
        segs = ""
        for k in ("exc", "ten", "acc"):
            if b[k]:
                pct = str(round(b[k] / scale * 100, 1))
                segs += '<i class="ov-seg ov-' + k + '" style="height:' + pct + '%"></i>'
        cols.append('<span class="ov-bin">' + segs + "</span>")
    # No ticks on a merged chart: its codebooks' lines can differ, so no one pair is true.
    ticks = "" if lines is None else (
        '<span class="ov-tick" style="left:' + str(round(lines[0] * 100, 2)) + '%"></span>'
        '<span class="ov-tick" style="left:' + str(round(lines[1] * 100, 2)) + '%"></span>'
    )
    return (
        '<div class="ov-hist ov-' + variant + '" role="img" aria-label="' + E(label) + '">'
        + "".join(cols) + ticks + "</div>"
    )


def tally_text(tally: dict) -> str:
    # Left to right, as the chart reads (owner, 23 Nov 2026).
    return " · ".join(
        [
            t("autocode.review.zoneExcluded") + " " + str(tally["exc"]),
            t("autocode.review.zoneTentative") + " " + str(tally["ten"]),
            t("autocode.review.zoneAccepted") + " " + str(tally["acc"]),
        ]
    )


def tally_html(tally: dict) -> str:
    # The number takes its zone's colour; the word stays muted (owner, 23 Nov 2026).
    parts = []
    for word_key, k in (("zoneExcluded", "exc"), ("zoneTentative", "ten"), ("zoneAccepted", "acc")):
        parts.append(E(t("autocode.review." + word_key)) + ' <b class="ov-n ov-n-' + k + '">' + str(tally[k]) + "</b>")
    return " · ".join(parts)


def tally_of(items: list[Item]) -> dict:
    out = {"acc": 0, "ten": 0, "exc": 0}
    for c, lo, hi in items:
        out[zone(c, lo, hi)] += 1
    return out


CHEVRON = (
    '<svg class="codebook-disclosure ov-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="m9 18 6-6-6-6"/></svg>'
)
EYE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
)


def review_link(state: str) -> str:
    if state == "hidden":
        return ""
    word = E(t("codebook.reviewProposals"))
    sep = '<span class="tag-filter-separator" aria-hidden="true">|</span>'
    if state == "inactive":
        return '<span class="ov-rv">' + sep + '<button type="button" class="tag-filter-action ov-review" aria-disabled="true">' + word + "</button></span>"
    return '<span class="ov-rv">' + sep + '<button type="button" class="tag-filter-action ov-review">' + word + "</button></span>"


# Owner-written, 23 Nov 2026: replaces tags.summary ("{{count}} tags across {{frameworks}} frameworks").
# Not yet a locale key; the plural forms ("1 codebook") need i18next count keys.
# Sentiment is not counted (owner, 23 Nov 2026): it is machine-applied on every run and never
# reviewed, so the sentence names only the codebooks a researcher chose. Talismanic: UXR alone.
SUMMARY = "{{count}} tags from {{codebooks}} codebooks"
SUMMARY_ONE = "{{count}} tags from 1 codebook"


def invented(seed: int, n: int, a: float, b: float) -> list[float]:
    """A made-up confidence spread for a codebook this study never ran. Labelled INVENTED in its frame."""
    rng = random.Random(seed)
    return [round(rng.betavariate(a, b), 3) for _ in range(n)]


def block(
    title: str | None, items: list[Item], scale: int, variant: str, lines: tuple[float, float] | None,
    review: str = "hidden",
) -> str:
    # Split view: each codebook has its own Review, on its name's baseline (owner, 23 Nov 2026).
    name = '<div class="ov-fw"><span>' + E(title) + "</span>" + review_link(review) + "</div>" if title else ""
    return (
        '<div class="ov-block">' + name + histogram(items, scale, variant, lines)
        + '<div class="ov-meta"><span class="ov-tally">' + tally_html(tally_of(items)) + "</span></div></div>"
    )


def overview(
    run: dict, *, open_: bool, done: int | None = None, review: str = "live", variant: str = "zone",
    coded: int = 1, split: bool = False, codebooks: int = 1, count: int = 34, show: bool = True,
) -> str:
    sentence = SUMMARY_ONE if codebooks == 1 else SUMMARY
    summary_text = E(sentence.replace("{{count}}", str(count)).replace("{{codebooks}}", str(codebooks)))
    if not show:
        return '<div class="tag-sidebar-subtitle">' + summary_text + "</div>"
    confs_all = [p[2] for p in run["props"]]
    confs = confs_all if done is None else [p[2] for p in run["props"] if p[0] <= done]
    uxr_lines = (LOWER, UPPER)
    books = [("Bristlenose UXR Codebook", items_of(confs, uxr_lines), items_of(confs_all, uxr_lines), uxr_lines)]
    if coded > 1:
        # Invented, and each re-cut differently, as researchers will (owner, 23 Nov 2026).
        n_lines, g_lines = (0.25, 0.60), (0.40, 0.80)
        norman = items_of(invented(5, 70, 3.2, 2.0), n_lines)
        garrett = items_of(invented(11, 55, 2.0, 2.4), g_lines)
        books += [("Norman's Design Principles", norman, norman, n_lines),
                  ("Garrett's Elements of UX", garrett, garrett, g_lines)]
    expanded = "true" if open_ else "false"
    if coded > 1:
        # "3 codebooks" is its own link, so the disclosure target becomes "41 tags from".
        lead, _, tail = summary_text.partition(" " + str(codebooks) + " ")
        tail_text = str(codebooks) + " " + tail
        head = (
            '<div class="ov-line"><button type="button" class="ov-summary" aria-expanded="' + expanded + '">'
            + CHEVRON + "<span>" + lead + "</span></button>"
            '<button type="button" class="tag-filter-action ov-splitlink' + (" tag-filter-action-active" if split else "")
            + '" aria-pressed="' + ("true" if split else "false") + '">' + tail_text + "</button>"
            # No Review here with two or more coded codebooks (owner, 23 Nov 2026): accepting and
            # excluding across codebooks at once is not a sane act, and nothing builds it. Each
            # codebook's own Review is in the split view, so the line is the same in both views.
            + "</div>"
        )
    else:
        head = (
            '<div class="ov-line"><button type="button" class="ov-summary" aria-expanded="' + expanded + '">'
            + CHEVRON + "<span>" + summary_text + "</span></button>" + review_link(review) + "</div>"
        )
    # Always drawn, hidden when closed, so every frame's line can be clicked open and shut.
    body = '<div class="ov-body"' + ("" if open_ else " hidden") + ">"
    if coded == 1:
        scale = max(5, max(sum(b.values()) for b in bins_of(books[0][2])))
        return head + body + block(None, books[0][1], scale, variant, uxr_lines) + "</div>"
    # Merged (the default): every codebook's proposals in one chart, each judged by its own lines.
    merged_now = [it for _, now, _, _ in books for it in now]
    merged_all = [it for _, _, full, _ in books for it in full]
    m_scale = max(5, max(sum(b.values()) for b in bins_of(merged_all)))
    # Split: one chart per codebook, all on one shared scale so their sizes compare.
    s_scale = max(5, max(max(sum(b.values()) for b in bins_of(full)) for _, _, full, _ in books))
    merged = (
        '<div class="ov-merged"' + (" hidden" if split else "") + ">"
        + block(None, merged_now, m_scale, variant, None) + "</div>"
    )
    parts = "".join(block(title, now, s_scale, variant, lines, review) for title, now, _, lines in books)
    separate = '<div class="ov-separate"' + ("" if split else " hidden") + ">" + parts + "</div>"
    return head + body + merged + separate + "</div>"


def tag_rows(run: dict, groups: int) -> str:
    acc: dict[int, int] = {}
    ten: dict[int, int] = {}
    for _qid, tid, conf in run["props"]:
        z = zone(conf)
        if z == "acc":
            acc[tid] = acc.get(tid, 0) + 1
        elif z == "ten":
            ten[tid] = ten.get(tid, 0) + 1
    max_count = max(1, *(acc.get(x["id"], 0) + ten.get(x["id"], 0) for x in run["tags"]))
    out = []
    for _gid, gname, gsub, cset in run["groups"][:groups]:
        rows = []
        for tag in [x for x in run["tags"] if x["group"] == gname]:
            a, tt = acc.get(tag["id"], 0), ten.get(tag["id"], 0)
            bg = "var(--bn-" + cset + "-" + str(tag["idx"] % SLOTS.get(cset, 5) + 1) + "-bg)"
            bar = ""
            if a + tt:
                total = round((a + tt) / max_count * 100)
                a_share = round(a / (a + tt) * 100)
                colour = "background-color:var(--bn-bar-" + cset + ")"
                bar = '<span class="tag-micro-bar-stack" style="width:' + str(total) + '%">'
                if tt:
                    bar += '<span class="tag-micro-bar-tentative" style="width:' + str(100 - a_share) + "%;" + colour + '"></span>'
                if a:
                    bar += '<span class="tag-micro-bar-accepted" style="width:' + str(a_share) + "%;" + colour + '"></span>'
                bar += "</span>"
            shown = a if a else tt
            kind = " is-accepted" if a else (" is-tentative" if tt else "")
            rows.append(
                '<div class="tag-row"><span class="tag-name-area"><label class="tag-checkbox-label">'
                '<input type="checkbox" class="bn-checkbox" checked aria-label="' + E(tag["name"]) + '"></label>'
                '<span class="badge" style="background-color:' + bg + '" data-truncates="user-content">'
                + E(tag["name"]) + "</span></span>"
                '<span class="tag-bar-area">' + bar + '<span class="tag-count' + kind + '">'
                + (str(shown) if shown else "") + "</span></span></div>"
            )
        out.append(
            '<div class="tag-filter-group" style="background:var(--bn-group-' + cset + ')">'
            '<div class="tag-filter-group-header-row"><div class="tag-filter-group-info">'
            '<div class="tag-filter-group-name">' + E(gname) + "</div>"
            '<div class="tag-filter-group-subtitle">' + E(gsub) + "</div></div>"
            '<button class="group-eye" aria-label="' + E(t("tags.hideGroup", group=gname)) + '">' + EYE + "</button></div>"
            '<div class="tag-filter-group-tags">' + "".join(rows) + "</div></div>"
        )
    return "".join(out)


def sidebar(run: dict, top: str, *, groups: int = 1, width: int = 280, export: bool = False) -> str:
    actions = (
        '<div class="tag-sidebar-actions">'
        '<button type="button" class="tag-filter-action">' + E(t("tags.selectAll")) + "</button>"
        '<span class="tag-filter-separator">|</span>'
        '<button type="button" class="tag-filter-action">' + E(t("tags.clear")) + "</button>"
        '<span class="tag-filter-separator">|</span>'
        '<button type="button" class="tag-filter-action">' + E(t("tags.used")) + "</button></div>"
    )
    framework = (
        '<details class="codebook-framework" open><summary>'
        + CHEVRON.replace(" ov-chev", "")
        + '<div class="codebook-info"><div class="codebook-title">Bristlenose UXR Codebook</div></div>'
        '<button class="codebook-eye" aria-label="' + E(t("tags.hideFramework", framework="Bristlenose UXR Codebook"))
        + '">' + EYE + "</button></summary>"
        '<div class="codebook-body">' + tag_rows(run, groups) + "</div></details>"
    )
    return (
        '<div class="tag-sidebar mock-sidebar' + (" mock-export" if export else "") + '" style="width:' + str(width) + 'px">'
        '<div class="sidebar-header tag-sidebar-header"><span class="sidebar-title">' + E(t("tags.tags")) + "</span></div>"
        + top + actions
        + '<div class="tag-search-container"><input type="text" class="tag-search-input" placeholder="'
        + E(t("tags.searchPlaceholder")) + '"></div>'
        '<div class="tag-sidebar-body">' + framework + "</div></div>"
    )


def frame(title: str, note: str, body: str, flag: bool = False) -> str:
    return (
        '<figure><div class="chrome"><span>' + E(title) + '</span><span class="' + ("flag" if flag else "")
        + '">' + E(note) + "</span></div><div class=\"art\">" + body + "</div></figure>"
    )


def build(run: dict) -> str:
    third = run["props"][len(run["props"]) * 4 // 10][0]  # about 40% of the run landed
    frames = [
        frame("1 · No AutoCode run yet", "summary wording owner-written (new key); no chevron, no Review",
              sidebar(run, overview(run, open_=False, show=False))),
        frame("2 · After a run, closed", "Review reachable without opening",
              sidebar(run, overview(run, open_=False))),
        frame("3 · After a run, open", "zone colours, as the dialog (threshold-review.css)",
              sidebar(run, overview(run, open_=True))),
        frame("4 · During a run", "Review present, inactive until the run ends",
              sidebar(run, overview(run, open_=True, done=third, review="inactive"))),
        frame("5a · Three codebooks coded: merged (the default)", "no ticks: the three cuts differ; no Review; two shapes INVENTED",
              sidebar(run, overview(run, open_=True, coded=3, codebooks=3, count=96)), flag=True),
        frame("5b · Three codebooks coded: split", "each chart its own cut and Review; pushes the tags down",
              sidebar(run, overview(run, open_=True, coded=3, split=True, codebooks=3, count=96)), flag=True),
        frame("6 · Narrowest sidebar, 200 px", "the line wraps; nothing is cut",
              sidebar(run, overview(run, open_=True), width=200)),
        frame("7 · HTML export (read-only)", "as today: proposals are server-only (routes/export.py)",
              sidebar(run, overview(run, open_=False, show=False), export=True)),
    ]
    page = PAGE.replace("/*CSS*/", css_blocks()).replace("<!--FRAMES-->", "".join(frames))
    return page.replace("<!--N-->", str(len(run["props"])))


PAGE = """<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tag sidebar AutoCode histogram</title>
<style>
/*CSS*/

/* ════ NEW: the overview block (hand-written; tokens only) ════ */
.ov-line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 0.4rem; padding: 0 0.6rem 0.25rem 0.55rem; }
.ov-rv { display: inline-flex; align-items: baseline; gap: 0.4rem; white-space: nowrap; }
/* The whole phrase is the target, chevron and words, not the 12px chevron alone (owner,
   23 Nov 2026). Padding grows the hit box to 24px tall (WCAG 2.2 target size); the matching
   negative margin keeps the layout.
   One baseline for the line (owner, 23 Nov 2026): the button is an inline-block, not a flex
   box, so its baseline is its text's, and the chevron sits in the line as an inline glyph.
   A flex button took its baseline from the chevron, which has none, and dropped the words. */
.ov-summary { display: inline-block; text-align: left; line-height: var(--bn-text-badge-lh);
  background: none; border: 0; cursor: pointer; font: inherit; font-size: var(--bn-text-badge);
  color: var(--bn-colour-muted); padding: 5px 4px; margin: -5px -4px; border-radius: var(--bn-radius-sm); }
.ov-summary:hover { color: var(--bn-colour-text); }
.ov-summary:focus-visible { outline: 2px solid var(--bn-colour-accent); outline-offset: 0; }
.ov-summary .ov-chev { display: inline-block; width: 0.75rem; height: 0.75rem; margin: 0 0.15rem 0 0;
  vertical-align: -0.1em; }
.ov-summary[aria-expanded="true"] .ov-chev { transform: rotate(90deg); }
.ov-body { padding: 0.15rem 0.75rem 0.45rem 0.85rem; }
.ov-block + .ov-block { margin-top: 0.55rem; }
.ov-splitlink { white-space: nowrap; }
.ov-fw { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 0.4rem; font-size: var(--bn-text-badge);
  color: var(--bn-colour-text); margin-bottom: 0.2rem; }
.ov-hist { position: relative; height: 34px; display: grid; grid-template-columns: repeat(20, 1fr); gap: 1px;
  align-items: end; border-bottom: 1px solid var(--bn-colour-border); }
.ov-bin { display: flex; flex-direction: column-reverse; height: 100%; }
.ov-seg { display: block; width: 100%; }
.ov-zone .ov-acc { background: var(--bn-colour-positive); }
.ov-zone .ov-ten { background: var(--bn-colour-warning); }
.ov-zone .ov-exc { background: var(--bn-colour-muted); opacity: 0.5; }
.ov-n { font-weight: var(--bn-weight-emphasis); font-variant-numeric: tabular-nums; }
/* Text shades: the bar tokens fall under 4.5:1 as 11.5px text in light mode (3.3 and 2.2).
   These are about 4.8:1 on the inspector tint; dark keeps palette-default's dark values.
   A shipped version needs tokens (no positive-text / warning-text exists yet). */
.ov-n-acc { color: light-dark(#15803d, #22c55e); }
.ov-n-ten { color: light-dark(#b45309, #fbbf24); }
.ov-n-exc { color: var(--bn-colour-muted); }
.ov-tick { position: absolute; top: -2px; bottom: -3px; width: 1px; background: var(--bn-colour-accent); }
.ov-meta { margin-top: 0.25rem; font-size: var(--bn-text-badge); color: var(--bn-colour-muted); }
.ov-review[aria-disabled="true"] { color: var(--bn-colour-muted); cursor: default; text-decoration: none; }

/* ════ mockup chrome (not product) ════ */
:root { color-scheme: light dark; }
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text);
  font-family: var(--bn-font-body); font-size: var(--bn-text-label); }
.tag-sidebar.mock-sidebar { visibility: visible; opacity: 1; position: static; grid-column: auto; height: auto;
  margin: 0; padding-top: 0.5rem; max-height: 560px; overflow: hidden; border-left: 1px solid var(--bn-colour-border); }
.wrap { max-width: 1240px; margin: 0 auto; padding: 0 20px 60px; }
.bar { position: sticky; top: 0; z-index: 10; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
  padding: 8px 20px; background: var(--bn-colour-badge-bg); border-bottom: 1px solid var(--bn-colour-border);
  font-family: var(--bn-font-mono); font-size: 11px; }
.bar select { font: inherit; }
h1 { font-size: var(--bn-text-title); font-weight: var(--bn-weight-emphasis); margin: 22px 0 4px; }
.lede { color: var(--bn-colour-muted); max-width: 74ch; margin: 0 0 18px; }
.grid { display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start; }
figure { margin: 0; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; }
.chrome { display: flex; flex-direction: column; gap: 2px; padding: .3rem .6rem; max-width: 282px;
  background: var(--bn-colour-badge-bg); color: var(--bn-colour-badge-text); font-family: var(--bn-font-mono);
  font-size: var(--bn-text-micro); border-bottom: 1px solid var(--bn-colour-border); }
.chrome .flag { color: #d92d20; }
.art { display: flex; justify-content: flex-end; background: var(--bn-colour-bg); }
</style>
</head>
<body>
<div class="bar">
  <span>tag-sidebar-autocode-histogram</span>
  <label>Palette <select id="pal"><option value="default">default</option><option value="edo">edo</option></select></label>
  <label>Scheme <select id="sch"><option value="">auto</option><option value="light">light</option><option value="dark">dark</option></select></label>
</div>
<div class="wrap">
<h1>AutoCode at the top of the tag sidebar</h1>
<p class="lede">A small confidence histogram, opened from the tag count line, with a Review link to the existing
threshold dialog. Talismanic run, <!--N--> proposals, lines at 0.30 and 0.70. Generated by
<code>tag-sidebar-autocode-histogram.gen.py</code>: shipped CSS and words; the overview block is the one new
element. Discussion is in the conversation, not on this page.</p>
<div class="grid"><!--FRAMES--></div>
</div>
<script>
const root = document.documentElement;
document.getElementById("pal").onchange = e => root.dataset.colorTheme = e.target.value;
document.getElementById("sch").onchange = e => { if (e.target.value) root.dataset.theme = e.target.value; else delete root.dataset.theme; };
document.querySelectorAll(".ov-summary").forEach(b => b.addEventListener("click", () => {
  const open = b.getAttribute("aria-expanded") === "true";
  b.setAttribute("aria-expanded", String(!open));
  const body = b.closest(".ov-line").nextElementSibling;
  if (body && body.classList.contains("ov-body")) body.hidden = open;
}));
// "3 codebooks" splits the merged chart into one per codebook, and merges them back.
// Clicked while closed, it opens the overview in the split view.
document.querySelectorAll(".ov-splitlink").forEach(l => l.addEventListener("click", () => {
  const line = l.closest(".ov-line"), body = line.nextElementSibling, sum = line.querySelector(".ov-summary");
  const wasOpen = !body.hidden;
  const split = wasOpen ? l.getAttribute("aria-pressed") !== "true" : true;
  l.setAttribute("aria-pressed", String(split));
  l.classList.toggle("tag-filter-action-active", split);
  body.hidden = false; sum.setAttribute("aria-expanded", "true");
  body.querySelector(".ov-merged").hidden = split;
  body.querySelector(".ov-separate").hidden = !split;
}));
</script>
</body>
</html>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    OUT.write_text(build(read_run(args.db)), encoding="utf-8")
    print("wrote " + str(OUT.relative_to(ROOT)))
