#!/usr/bin/env python3
"""Generate docs/mockups/autocode-review-dialog.html: the AutoCode review dialog after Phase 2.

Phase 2 of docs/design-autocode-landing-plan.md makes the threshold review dialog re-cuttable
(decisions D1-D3, D26, D2 as widened). This page shows it, frame by frame, in the dialog's own
markup and words, drawn with the shipped theme CSS (each block headed with its path), so every
pixel is the product's. Frame 0 is today's dialog; its markup was taken from the shipped
ThresholdReviewModal rendered in the test environment on the same data (23 Nov 2026), and this
generator reproduces it element for element. Every element Phase 2 adds or changes carries a
numbered marker that points to the list of innovations under the frames.

Data: the Talismanic study's UXR run (public test data; participant codes only), with its stored
lines at 0.30 and 0.70. Four decisions are INVENTED to show pinned rows: two accepted by the
researcher, one excluded by the researcher, one "unknown" (a decision from before the record of
who decided existed).

    .venv/bin/python docs/mockups/autocode-review-dialog.gen.py
"""

from __future__ import annotations

import html
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/autocode-review-dialog.html"
THEME = ROOT / "bristlenose/theme"
CSS = [
    "tokens.css",
    "tokens-typography.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "atoms/icon.css",
    "atoms/badge.css",
    "atoms/timecode.css",
    "atoms/modal.css",
    "organisms/codebook-panel.css",
    "molecules/autocode-report.css",
    "molecules/threshold-review.css",
]
PRIVATE_RUNS = ROOT / "trial-runs"  # gitignored
DB = PRIVATE_RUNS / "again" / "bristlenose-output" / ".bristlenose" / "bristlenose.db"
COMMON = json.loads((ROOT / "bristlenose/locales/en/common.json").read_text(encoding="utf-8"))
E = html.escape
STORED = (0.30, 0.70)
BINS = 20


def t(path: str, **values: object) -> str:
    node: object = COMMON
    for part in path.split("."):
        node = node[part]  # type: ignore[index]
    text = str(node)
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def css_blocks() -> str:
    out = []
    for rel in CSS:
        text = (THEME / rel).read_text(encoding="utf-8")
        out.append("/* ════ bristlenose/theme/" + rel + " — lines 1–" + str(text.count("\n") + 1) + " ════ */\n" + text)
    return "\n".join(out)


# ── icons: Lucide paths as the app's <Icon> renders them ──────────────────────────────────────
PATHS = {
    "ai": ['M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z'],
    "close": ["M18 6 6 18", "m6 6 12 12"],
    "check": ["M20 6 9 17l-5-5"],
    "disclose": ["m9 18 6-6-6-6"],
    # NEW (innovation 2): Lucide "Pin", not yet in components/Icon.tsx
    "pin": ["M12 17v5", "M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"],
}
LUCIDE = {"ai": "sparkle", "close": "x", "check": "check", "disclose": "chevron-right", "pin": "pin"}


def icon(name: str) -> str:
    paths = "".join('<path vector-effect="non-scaling-stroke" d="' + d + '"></path>' for d in PATHS[name])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" '
        'class="lucide lucide-' + LUCIDE[name] + " bn-icon bn-icon-" + name + '" focusable="false" aria-hidden="true">'
        + paths + "</svg>"
    )


def mark(n: int) -> str:
    return '<span class="mk" title="Innovation ' + str(n) + '">' + str(n) + "</span>"


# ── data ──────────────────────────────────────────────────────────────────────────────────────
def load() -> list[dict]:
    db = sqlite3.connect("file:" + str(DB) + "?mode=ro", uri=True)
    job = db.execute("select id from autocode_jobs where framework_id='uxr' order by id desc").fetchone()[0]
    rows = db.execute(
        "select p.id, q.session_id, q.participant_id, q.start_timecode, q.text, t.name, g.colour_set, "
        "(select count(*) from tag_definitions t2 where t2.codebook_group_id = t.codebook_group_id and t2.id < t.id), "
        "p.confidence from proposed_tags p join quotes q on q.id = p.quote_id "
        "join tag_definitions t on t.id = p.tag_definition_id join codebook_groups g on g.id = t.codebook_group_id "
        "where p.job_id = ? order by p.confidence desc",
        (job,),
    ).fetchall()
    props = []
    for pid, sid, part, tc, text, tag, cset, idx, conf in rows:
        c = round(conf, 2)
        st = "accepted" if c >= STORED[1] else ("denied" if c < STORED[0] else "pending")
        props.append({"id": pid, "s": sid, "p": part, "tc": int(tc), "text": text, "tag": tag, "set": cset,
                      "idx": idx, "c": c, "status": st, "by": "threshold" if st != "pending" else None})
    pend = [x for x in props if x["status"] == "pending"]
    pend[3].update(status="accepted", by="researcher")
    pend[9].update(status="accepted", by="researcher")
    acc = [x for x in props if x["status"] == "accepted" and x["by"] == "threshold"]
    acc[2].update(status="denied", by="researcher")
    acc[-2].update(by="unknown")
    return props


SLOTS = {"ux": 5, "emo": 6, "task": 5, "trust": 5, "opp": 5}


def zone(c: float, lines: tuple[float, float]) -> str:
    return "accepted" if c >= lines[1] else ("excluded" if c < lines[0] else "tentative")


def where(p: dict, lines: tuple[float, float]) -> str:
    """Where Apply would leave a proposal: pinned decisions stay; others follow D26."""
    if p["by"] in ("researcher", "unknown"):
        return "accepted" if p["status"] == "accepted" else ("excluded" if p["status"] == "denied" else "tentative")
    old, new = zone(p["c"], STORED), zone(p["c"], lines)
    if old == new:
        return {"accepted": "accepted", "denied": "excluded", "pending": "tentative"}[p["status"]]
    return new


# ── the dialog, element for element ───────────────────────────────────────────────────────────
def header(subtitle: str, sparkle: bool = False) -> str:
    # Phase 2: the sparkle leaves the title (owner, 23 Nov 2026; innovation 7). Frame 0 keeps it: that is today.
    lead = (icon("ai") + " ") if sparkle else ""
    return (
        '<div class="codebook-modal-header"><div><div class="codebook-modal-title" id="bn-threshold-title">'
        + lead + E(t("autocode.review.title")) + " — Bristlenose UXR Codebook" + ("" if sparkle else mark(7)) + "</div>"
        '<div class="codebook-modal-subtitle">' + subtitle + "</div>"
        '<p class="threshold-instruction">' + E(t("autocode.review.dragInstruction")) + "</p></div>"
        '<button class="codebook-modal-close" aria-label="' + E(t("autocode.close")) + '">' + icon("close") + "</button></div>"
    )


def subtitle(props: list[dict], shown_pending: int, total: int) -> str:
    acc = sum(p["status"] == "accepted" for p in props)
    exc = sum(p["status"] == "denied" for p in props)
    s = E(t("autocode.review.remaining", pending=shown_pending, total=total))
    parts = []
    if acc:
        parts.append(E(t("autocode.review.accepted", count=acc)))
    if exc:
        parts.append(E(t("autocode.review.excluded", count=exc)))
    return s + (" (" + ", ".join(parts) + ")" if parts else "")


def histogram(items: list[dict], lines: tuple[float, float]) -> str:
    bins = [0] * BINS
    for p in items:
        bins[min(BINS - 1, int(p["c"] * BINS))] += 1
    top = max(1, max(bins))
    cells = []
    for i, n in enumerate(bins):
        mid = (i + 0.5) / BINS
        colour = "green" if mid >= lines[1] else ("grey" if mid < lines[0] else "amber")
        bar = ""
        if n:
            bar = ('<div class="threshold-histogram-bar threshold-histogram-bar--' + colour + '" style="height: '
                   + str(n / top * 100) + '%;" title="' + str(n) + (" proposal" if n == 1 else " proposals") + '"></div>')
        cells.append('<div class="threshold-histogram-bin">' + bar + "</div>")
    axis = "".join("<span>" + v + "</span>" for v in ("0.0", "0.2", "0.4", "0.6", "0.8", "1.0"))
    return ('<div class="threshold-histogram">' + "".join(cells) + '</div><div class="threshold-histogram-axis">'
            + axis + "</div>")


def slider(lines: tuple[float, float]) -> str:
    lo, hi = lines
    return (
        '<div class="threshold-slider"><div class="threshold-slider-track">'
        '<div class="threshold-slider-segment threshold-slider-segment--grey" style="left: 0px; width: ' + str(lo * 100) + '%;"></div>'
        '<div class="threshold-slider-segment threshold-slider-segment--amber" style="left: ' + str(lo * 100) + "%; width: " + str((hi - lo) * 100) + '%;"></div>'
        '<div class="threshold-slider-segment threshold-slider-segment--green" style="left: ' + str(hi * 100) + "%; width: " + str((1 - hi) * 100) + '%;"></div></div>'
        '<div class="threshold-slider-thumb" style="left: ' + str(lo * 100) + '%;" role="slider" aria-label="Lower threshold"><span class="threshold-slider-label">' + f"{lo:.2f}" + "</span></div>"
        '<div class="threshold-slider-thumb" style="left: ' + str(hi * 100) + '%;" role="slider" aria-label="Upper threshold"><span class="threshold-slider-label">' + f"{hi:.2f}" + "</span></div></div>"
    )


def counters(n_exc: int, n_ten: int, n_acc: int, marker: str = "") -> str:
    return (
        '<div class="threshold-zone-counters">'
        '<span class="threshold-zone-counter threshold-zone-counter--exclude">' + E(t("autocode.review.zoneExclude")) + ' <span class="threshold-zone-counter-count">' + str(n_exc) + "</span></span>"
        '<span class="threshold-zone-counter threshold-zone-counter--tentative">' + E(t("autocode.review.zoneTentative")) + ' <span class="threshold-zone-counter-count">' + str(n_ten) + "</span></span>"
        '<span class="threshold-zone-counter threshold-zone-counter--accept">' + E(t("autocode.review.zoneAccept")) + ' <span class="threshold-zone-counter-count">' + str(n_acc) + "</span></span>"
        + marker + "</div>"
    )


ZONE_KEY = {"accepted": "zoneAccepted", "tentative": "zoneTentative", "excluded": "zoneExcluded"}


def row(p: dict, z: str, phase2: bool) -> str:
    m, s = divmod(p["tc"], 60)
    hh, mm = divmod(m, 60)
    tc = (f"{hh}:{mm:02d}:{s:02d}" if hh else f"{mm:02d}:{s:02d}")
    bg = "var(--bn-" + p["set"] + "-" + str(p["idx"] % SLOTS.get(p["set"], 5) + 1) + "-bg)"
    pinned = phase2 and p["by"] in ("researcher", "unknown")
    pin = ('<span class="pinmark" title="Your decision">' + icon("pin") + "</span>" + mark(2)) if pinned else ""
    acts = ""
    ok = '<button class="threshold-action-btn threshold-action-accept" title="' + E(t("autocode.accept")) + '">' + icon("check") + "</button>"
    no = '<button class="threshold-action-btn threshold-action-deny" title="' + E(t("autocode.deny")) + '">' + icon("close") + "</button>"
    if z == "accepted":
        acts = no
    elif z == "tentative":
        acts = ok + no
    else:
        acts = ok
    return (
        '<tr class="report-row' + (" pinned" if pinned else "") + '"><td class="report-timecode"><a class="timecode" href="#">'
        '<span class="timecode-bracket">[</span>' + tc + '<span class="timecode-bracket">]</span></a></td>'
        '<td class="report-speaker"><a class="badge" href="#">' + E(p["p"]) + "</a></td>"
        '<td class="report-quote" title="' + E(p["text"]) + '">' + E(p["text"]) + "</td>"
        '<td class="report-tag"><span class="badge" style="background-color: ' + bg + ';">' + E(p["tag"]) + "</span></td>"
        '<td class="threshold-confidence">' + f"{p['c']:.2f}" + pin + "</td>"
        '<td class="threshold-actions">' + acts + "</td></tr>"
    )


def zone_list(z: str, items: list[dict], open_: bool, phase2: bool, limit: int = 6, marker: str = "") -> str:
    if not items:
        return ""
    head = (
        '<div class="threshold-zone-list-header"><span class="threshold-zone-list-chevron'
        + (" threshold-zone-list-chevron--open" if open_ else "") + '">' + icon("disclose") + "</span>"
        "<span>" + E(t("autocode.review." + ZONE_KEY[z])) + '</span><span class="threshold-zone-list-count">(' + str(len(items)) + ")</span>" + marker + "</div>"
    )
    body = ""
    if open_:
        by_s: dict[str, list[dict]] = {}
        for p in sorted(items, key=lambda x: -x["c"]):
            by_s.setdefault(p["s"], []).append(p)
        rows = []
        shown = 0
        for sid in sorted(by_s):
            if shown >= limit:
                break
            rows.append('<tr><td colspan="6" class="report-session-header">' + E(t("autocode.sessionLabel", id=sid[1:])) + "</td></tr>")
            for p in by_s[sid]:
                if shown >= limit:
                    break
                rows.append(row(p, z, phase2))
                shown += 1
        more = len(items) - shown
        tail = ('<tr><td colspan="6" class="more">… ' + str(more) + " more rows in the real dialog</td></tr>") if more > 0 else ""
        body = ('<div class="threshold-zone-list-body threshold-zone-list-body--open"><table class="threshold-proposal-table"><tbody>'
                + "".join(rows) + tail + "</tbody></table></div>")
    return '<div class="threshold-zone-list">' + head + body + "</div>"


def footer(apply_enabled: bool, marker: str = "") -> str:
    return (
        '<div class="threshold-footer"><button class="bn-btn">' + E(t("autocode.close")) + "</button>"
        '<button class="bn-btn bn-btn-primary"' + ("" if apply_enabled else " disabled") + ">" + E(t("autocode.review.apply")) + "</button>" + marker + "</div>"
    )


def dialog(inner_header: str, body: str, foot: str) -> str:
    return (
        '<div class="frame-stage"><div class="bn-modal codebook-modal" role="dialog" aria-labelledby="bn-threshold-title">'
        + inner_header + '<div class="codebook-modal-body" style="padding: 1.5rem;"><div>' + body + "</div></div>" + foot + "</div></div>"
    )


def frame(title: str, note: str, content: str) -> str:
    return ('<figure><div class="chrome"><span>' + E(title) + "</span><span>" + E(note) + "</span></div>" + content + "</figure>")


def build() -> str:
    props = load()
    total = len(props)
    pending = [p for p in props if p["status"] == "pending"]

    # Frame 0 · today: only pending proposals load; zones by the sliders.
    lines = STORED
    z0 = {z: [p for p in pending if zone(p["c"], lines) == z] for z in ("accepted", "tentative", "excluded")}
    f0 = dialog(
        header(subtitle(props, len(pending), total), sparkle=True),
        histogram(pending, lines) + slider(lines) + counters(len(z0["excluded"]), len(z0["tentative"]), len(z0["accepted"]))
        + zone_list("accepted", z0["accepted"], False, False) + zone_list("tentative", z0["tentative"], True, False)
        + zone_list("excluded", z0["excluded"], False, False),
        footer(True),
    )

    def phase2_body(lines: tuple[float, float], open_acc: bool, open_exc: bool) -> tuple[str, dict]:
        zs = {z: [p for p in props if where(p, lines) == z] for z in ("accepted", "tentative", "excluded")}
        body = (
            histogram(props, lines) + mark(1) + slider(lines)
            + counters(len(zs["excluded"]), len(zs["tentative"]), len(zs["accepted"]), mark(3))
            + zone_list("accepted", zs["accepted"], open_acc, True, limit=7, marker=mark(4))
            + zone_list("tentative", zs["tentative"], True, True, limit=5)
            + zone_list("excluded", zs["excluded"], open_exc, True, limit=5, marker=mark(4))
        )
        return body, zs

    b1, _ = phase2_body(STORED, True, True)
    f1 = dialog(header(subtitle(props, len(pending), total)), b1, footer(False, mark(5)))

    moved = (0.30, 0.80)
    b2, zs2 = phase2_body(moved, True, False)
    f2 = dialog(header(subtitle(props, len(pending), total)), b2, footer(True, mark(5)))
    moved_n = sum(1 for p in props if p["by"] == "threshold" and where(p, moved) != where(p, STORED))

    # Frame 3 · nothing pending: every proposal decided (pending ones accepted for the frame).
    done = [dict(p, status="accepted" if p["status"] == "pending" else p["status"],
                 by="threshold" if p["status"] == "pending" else p["by"]) for p in props]
    zs3 = {z: [p for p in done if where(p, STORED) == z] for z in ("accepted", "tentative", "excluded")}
    b3 = (histogram(done, STORED) + slider(STORED) + counters(len(zs3["excluded"]), 0, len(zs3["accepted"]))
          + zone_list("accepted", zs3["accepted"], False, True) + zone_list("excluded", zs3["excluded"], True, True, limit=4))
    f3 = dialog(header(subtitle(done, 0, total) + mark(6)), b3, footer(False))

    frames = [
        frame("0 · Today, reopened after an Apply", "shipped: only the 53 still pending load", f0),
        frame("1 · Phase 2, reopened", "the whole run of 109; stored lines 0.30 / 0.70; Apply off until a line moves", f1),
        frame("2 · Phase 2, accept line dragged to 0.80", str(moved_n) + " threshold accepts move to Tentative; pinned rows stay", f2),
        frame("3 · Phase 2, nothing pending", "today this dialog shows an empty chart and lists", f3),
    ]
    return PAGE.replace("/*CSS*/", css_blocks()).replace("<!--FRAMES-->", "".join(frames))


PAGE = """<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AutoCode review dialog, Phase 2</title>
<style>
/*CSS*/

/* ════ NEW (innovation 2): the pinned mark, tokens only ════ */
.pinmark { display: inline-flex; margin-left: 0.35rem; color: var(--bn-colour-muted); vertical-align: -0.1em; }

/* ════ mockup chrome (not product) ════ */
:root { color-scheme: light dark; }
body { margin: 0; background: var(--bn-colour-bg); color: var(--bn-colour-text); font-family: var(--bn-font-body);
  font-size: var(--bn-text-label); }
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 20px 80px; }
.bar { position: sticky; top: 0; z-index: 20; display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
  padding: 8px 20px; background: var(--bn-colour-badge-bg); border-bottom: 1px solid var(--bn-colour-border);
  font-family: var(--bn-font-mono); font-size: 11px; }
.bar select { font: inherit; }
h1 { font-size: var(--bn-text-title); font-weight: var(--bn-weight-emphasis); margin: 22px 0 4px; }
.lede { color: var(--bn-colour-muted); max-width: 80ch; margin: 0 0 14px; }
figure { margin: 0 0 26px; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; }
.chrome { display: flex; justify-content: space-between; gap: .6rem; padding: .3rem .6rem; background: var(--bn-colour-badge-bg);
  color: var(--bn-colour-badge-text); font-family: var(--bn-font-mono); font-size: var(--bn-text-micro);
  border-bottom: 1px solid var(--bn-colour-border); }
.frame-stage { background: color-mix(in srgb, var(--bn-colour-text) 18%, transparent); padding: 24px; }
.frame-stage .bn-modal { position: static; transform: none; margin: 0 auto; max-height: none; opacity: 1; visibility: visible; }
.more { color: var(--bn-colour-muted); font-style: italic; padding: 6px 8px; }
.mk { display: inline-grid; place-items: center; width: 17px; height: 17px; margin-left: 6px; border-radius: 50%;
  background: #d92d20; color: #fff; font: 700 10px/1 ui-monospace, Menlo, monospace; vertical-align: middle; }
.commentary { margin-top: 10px; padding: 14px 18px; border: 7px solid transparent; border-left: 3px solid var(--bn-colour-muted);
  background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
  repeating-linear-gradient(135deg, var(--bn-colour-badge-bg) 0 5px, transparent 5px 10px) border-box; }
.commentary .lab { font-family: var(--bn-font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; color: var(--bn-colour-muted); }
.commentary ol { padding-left: 1.4rem; } .commentary li { margin: 0 0 10px; line-height: 1.5; max-width: 90ch; }
.commentary b { font-weight: var(--bn-weight-emphasis); }
</style>
</head>
<body>
<div class="bar"><span>autocode-review-dialog (Phase 2)</span>
  <label>Palette <select id="pal"><option value="default">default</option><option value="edo">edo</option></select></label>
  <label>Scheme <select id="sch"><option value="">auto</option><option value="light">light</option><option value="dark">dark</option></select></label></div>
<div class="wrap">
<h1>AutoCode review dialog, after Phase 2</h1>
<p class="lede">The shipped dialog's markup, words and CSS. Frame 0 is today. Red numbers mark what Phase 2 adds or changes;
the list below says what each is and why. Talismanic UXR run, 109 proposals, lines stored at 0.30 and 0.70; four hand
decisions are invented to show pinned rows. Long lists are cut after a few rows.</p>
<!--FRAMES-->
<section class="commentary"><div class="lab">Commentary · the innovations, and why</div>
<ol>
<li><b>The whole run loads, not only what is pending.</b> Today the dialog drops every proposal that has been decided
(<code>ThresholdReviewModal.tsx:87</code>), so after one Apply you can only narrow what is left, and an exclusion can never be
undone here. Now the chart, the counters and the lists cover all 109. Why: D1, the ratchet the owner found on 23 Nov.
The chart's bars stay coloured by position against the sliders, as today; a pinned decision is counted in its bar but not
drawn differently there.</li>
<li><b>A pin on a decision a person made.</b> A proposal the researcher accepted or excluded by hand, here or on a quote card,
or an older decision whose maker was not recorded ("unknown"), carries a pin after its confidence and does not move with the
sliders. Why: D2, a person's reading of a quote outranks the cut-off. New: the Lucide <i>Pin</i> icon joins
<code>components/Icon.tsx</code>, and its tooltip and spoken label need new words (drawn here as "Your decision", which is
not a shipped string: <b>owner to word</b>, then 21 locales).</li>
<li><b>The counters say what Apply will do.</b> Exclude / Tentative / Accept now count the outcome over the whole run, pinned
decisions included where they sit. Same words, same place; only what they count changes.</li>
<li><b>Accepted and Excluded list decided rows, with their ✗ and ✓.</b> Today those lists only show pending proposals that the
sliders would move there. Now they also list what is already accepted or excluded, so a row can be overridden: ✗ on an
accepted row excludes it, ✓ on an excluded row accepts it. Either makes it a pinned decision of the researcher's. Same buttons
and words as today; what is new is that the server allows changing a decided proposal (today it refuses with "already
reviewed").</li>
<li><b>Apply only when a line has moved.</b> Today Apply is off only when nothing is pending. Now it is off until a line moves
from its stored place, because pressing it with the lines unmoved would change nothing (D26). In frame 2 it is on: moving the
accept line from 0.70 to 0.80 sends the threshold accepts between them back to Tentative; the two pinned accepts in that band
stay. No warning on removing tags (D3).</li>
<li><b>It opens when nothing is pending.</b> Today, reopened with nothing pending, the chart and the lists are empty. Now they
show the whole run, so a finished run can still be re-cut. The subtitle keeps its shipped words ("0 of 109 proposals
remaining (…)"); whether "remaining" still reads right for a whole-run view is a wording call for the owner.</li>
<li><b>No sparkle in the title.</b> The title reads "AutoCode Review — Bristlenose UXR Codebook" with no icon before it
(owner, 23 Nov 2026). The sparkle stays wherever else the app uses it.</li>
</ol>
<p><b>Unchanged:</b> the title's words, the instruction, the chart's colours and axis, the sliders and their 0.05 steps, the zone names,
the session headings and rows, the timecodes and speaker links, Close, and the words on every button.</p>
</section>
</div>
<script>
const root = document.documentElement;
document.getElementById("pal").onchange = e => root.dataset.colorTheme = e.target.value;
document.getElementById("sch").onchange = e => { if (e.target.value) root.dataset.theme = e.target.value; else delete root.dataset.theme; };
</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("wrote " + str(OUT.relative_to(ROOT)))
