#!/usr/bin/env python3
"""Generate docs/mockups/tooltip-gallery-v2.html.

Iteration 2 of the tooltip gallery (`tooltip-gallery.html`, which chose variant D for the
system-wide tooltip). That page settled one floating surface; this one looks at all of them in the
React SPA, because a bug in one showed the system has no rule for the rest:

1. The person picker opened from a speaker badge on the project dashboard is clipped by the pane
   it sits in. Three frames draw the same shipped markup and CSS: as shipped, with the one property
   that clips it turned off, and with the picker moved to the floating layer (a stand-in for a
   portal). The page measures each in the browser it is opened in.
2. Every floating surface in the theme, read from the tree by this script: where it is placed,
   its z-index and its shadow, with the file and line of the rule.
3. Every distinct floating shadow, drawn on one box in light and dark side by side.
4. The z-index ladder as the tree has it.
5. The decisions it asks for, and 6. the token values, drawn on the real picker. The owner
   chose the shadow, the layering and the notification token on 26 Nov 2026.

The CSS in the frames is the shipped theme, inlined from the tree with each block headed by its
path and line range. The picker's markup is transcribed from `PersonPicker.tsx` (the participant
view) and the row from `Dashboard.tsx` (`CompactSessionRow`); every word in a frame is a shipped
`en` string. No product code changes with this page.

    .venv/bin/python docs/mockups/tooltip-gallery-v2.gen.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/mockups/tooltip-gallery-v2.html"
THEME = ROOT / "bristlenose/theme"
COMMON = json.loads((ROOT / "bristlenose/locales/en/common.json").read_text(encoding="utf-8"))
E = html.escape

# Whole files, in the theme's own order (`_THEME_FILES` in stages/s12_render/theme_assets.py).
CSS_FILES = [
    "tokens.css",
    "tokens-typography.css",
    "colors/palette-default.css",
    "colors/palette-edo.css",
    "atoms/badge.css",
    "atoms/icon.css",
    "molecules/person-badge.css",
    "organisms/sessions-grid.css",
    "organisms/global-nav.css",
    "organisms/person-picker.css",
    "organisms/inspector.css",
]
# Rules lifted out of templates/report.css by the line their selector starts on (the whole file
# would lay this page out as a report).
REPORT_RULES = [
    "table {", "th {", "td {", "td a {",
    ".bn-session-table {", ".bn-session-table tr {", ".bn-session-table tr:last-child {",
    ".bn-session-table td {", ".bn-session-table tbody tr[data-session] {",
    ".bn-session-moderators {", ".bn-session-speakers {", ".bn-session-meta {",
    ".bn-session-id {", ".bn-session-duration {",
]

CHECK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" class="lucide lucide-check bn-icon" aria-hidden="true">'
    '<path d="M20 6 9 17l-5-5" vector-effect="non-scaling-stroke"></path></svg>'
)

# Every floating surface the theme draws: (surface, family, file, selector line, placement).
# "in flow" = absolutely positioned inside its trigger's ancestors, so any ancestor that clips,
# contains paint or scrolls can cut it. "portal" = rendered into <body> by React's createPortal.
SURFACES = [
    ("Export menu; the person picker reuses its box", "menu",
     "bristlenose/theme/organisms/global-nav.css", ".export-dropdown-menu {", "in flow"),
    ("View switcher", "menu", "bristlenose/theme/organisms/toolbar.css",
     ".view-switcher-menu {", "in flow"),
    ("Tag filter", "menu", "bristlenose/theme/molecules/tag-filter.css",
     ".tag-filter-menu {", "in flow"),
    ("Search tokens and suggestions", "menu", "bristlenose/theme/molecules/search.css",
     ".search-listbox {", "in flow"),
    ("Tag suggestions", "menu", "bristlenose/theme/molecules/tag-input.css",
     ".tag-suggest {", "in flow"),
    ("Hidden quotes", "menu", "bristlenose/theme/molecules/hidden-quotes.css",
     ".bn-hidden-dropdown {", "in flow"),
    ("Transcript selector", "menu", "bristlenose/theme/templates/transcript.css",
     ".bn-selector__menu {", "in flow"),
    ("Screens menu", "menu", "frontend/src/islands/screens/screens.css",
     ".screens-menu {", "in flow"),
    ("Codebook group confirm", "popover", "bristlenose/theme/organisms/codebook-panel.css",
     ".codebook-group .confirm-dialog {", "in flow"),
    ("Session tapestry popover", "popover", "bristlenose/theme/organisms/session-tapestry.css",
     ".bn-tp-popover {", "in flow"),
    ("Shortcut tooltip", "tooltip", "bristlenose/theme/atoms/tooltip.css",
     ".bn-tooltip {", "in flow"),
    ("Rationale tooltip", "tooltip", "bristlenose/theme/molecules/autocode-report.css",
     ".has-tooltip .tooltip {", "in flow"),
    ("Heatmap cell tooltip", "tooltip", "bristlenose/theme/organisms/signals.css",
     ".cell-tooltip {", "in flow"),
    ("Moderator question pill", "tooltip", "bristlenose/theme/atoms/moderator-question.css",
     ".moderator-pill {", "in flow"),
    ("Tapestry hover frame", "tooltip", "bristlenose/theme/organisms/session-tapestry.css",
     ".bn-tp-thumb {", "portal"),
    ("Transcript gutter frame (hot)", "tooltip",
     "frontend/src/islands/transcript/transcript-gutter.css",
     ".segment-side .bn-gutter-entry.is-hot .bn-gutter-thumb {", "in flow"),
    ("Clipboard toast", "notification", "bristlenose/theme/atoms/toast.css",
     ".clipboard-toast {", "portal"),
    ("Activity chip", "notification", "bristlenose/theme/atoms/activity-chip.css",
     ".activity-chip {", "portal"),
    ("AutoCode toast", "notification", "bristlenose/theme/atoms/autocode-toast.css",
     ".autocode-toast {", "fixed"),
    ("Contents overlay", "overlay", "bristlenose/theme/organisms/sidebar.css",
     ".layout.toc-overlay .toc-sidebar {", "fixed"),
    ("Dialog", "overlay", "bristlenose/theme/atoms/modal.css", ".bn-modal {", "portal"),
    ("Drag ghost", "drag", "bristlenose/theme/organisms/codebook-panel.css",
     ".drag-ghost {", "fixed"),
]

# What we already do about clipping, case by case.
WORKAROUNDS = [
    ("bristlenose/theme/molecules/tag-input.css", ".quote-card:has(.tag-suggest) {",
     "raise the card with an open suggestion list over its siblings"),
    ("bristlenose/theme/molecules/tag-input.css", ".quote-group .quote-card:has(.tag-suggest) {",
     "turn off the card's content-visibility (paint containment) while it is open"),
    ("frontend/src/islands/discussion/discussion.css",
     ".dl-lens[data-all=\"true\"] .dl-content .dl-group:has(.tag-suggest, .bn-hidden-dropdown) {",
     "the same for a Discussion block"),
]


def t(path: str, **values: object) -> str:
    node: object = COMMON
    for part in path.split("."):
        node = node[part]  # type: ignore[index]
    text = str(node)
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", str(value))
    return text


def rule_at(rel: str, starts: str) -> tuple[int, int, str]:
    """The rule whose selector line starts with `starts`: (first line, last line, text)."""
    lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith(starts):
            depth = 0
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0 and "}" in lines[j]:
                    return i + 1, j + 1, "\n".join(lines[i : j + 1])
    raise SystemExit(f"rule {starts!r} not found in {rel}")


def decl(body: str, prop: str) -> str:
    """One declaration's value from a rule body, comments stripped; '' if absent."""
    clean = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    m = re.search(r"(?:^|[;{\s])" + re.escape(prop) + r"\s*:\s*([^;]+);", clean)
    return " ".join(m.group(1).split()) if m else ""


def css_block(rel: str) -> str:
    text = (THEME / rel).read_text(encoding="utf-8")
    n = text.count("\n") + 1
    return f"/* ════ bristlenose/theme/{rel} — lines 1–{n} ════ */\n{text}\n"


def report_rules() -> str:
    out = []
    for starts in REPORT_RULES:
        a, b, body = rule_at("bristlenose/theme/templates/report.css", starts)
        out.append(f"/* ════ bristlenose/theme/templates/report.css — lines {a}–{b} ════ */\n{body}\n")
    return "".join(out)


# ── The artefact: the dashboard's Sessions pane with the picker open ──────────────────────────

SESSIONS = [
    ("s1", 1, [("m1", "moderator", "Alex"), ("p1", "participant", "Sarah")], "12 Mar 2026", "48m"),
    ("s2", 2, [("m1", "moderator", "Alex"), ("p2", "participant", "Tom")], "13 Mar 2026", "52m"),
    ("s3", 3, [("m1", "moderator", "Alex"), ("p3", "participant", "Ana")], "14 Mar 2026", "41m"),
]
OPEN_ON = ("s3", "p3")
KNOWN = [("p1", "Sarah"), ("p2", "Tom"), ("p3", "Ana")]


def badge(code: str, name: str) -> str:
    return (
        '<span class="bn-person-badge"><span class="bn-speaker-badge--split">'
        f'<span class="bn-speaker-badge-code">{E(code)}</span>'
        f'<span class="bn-speaker-badge-name">{E(name)}</span></span></span>'
    )


def picker(own: str) -> str:
    roles = "".join(
        f'<button type="button" class="dimension-btn{" active" if r == "participant" else ""}" '
        f'role="radio" aria-checked="{"true" if r == "participant" else "false"}" tabindex="-1">'
        f"{E(t('sessions.speakerPlaceholder.' + r))}</button>"
        for r in ("moderator", "participant", "observer")
    )
    rows = "".join(
        '<li class="export-dropdown-item export-dropdown-scope" role="menuitemradio" '
        f'aria-checked="{"true" if code == own else "false"}" tabindex="-1">'
        f'<span class="export-dropdown-check" aria-hidden="true">{CHECK if code == own else ""}</span>'
        f"{badge(code, name)}</li>"
        for code, name in KNOWN
    )
    new_prompt = t("sessions.picker.newNameFor", code="p4")
    new = (
        '<li class="export-dropdown-item export-dropdown-scope bn-picker-new" role="none">'
        '<span class="export-dropdown-check" aria-hidden="true"></span>'
        '<span class="bn-person-badge"><span class="bn-speaker-badge--split">'
        '<span class="bn-speaker-badge-code">p4</span>'
        f'<span class="bn-speaker-badge-name bn-picker-new-name"><span aria-hidden="true">{E(new_prompt)}'
        f'</span><input placeholder="{E(new_prompt)}" aria-label="{E(new_prompt)}"></span>'
        "</span></span></li>"
    )
    return (
        '<ul class="export-dropdown-menu bn-person-picker" role="menu" '
        f'aria-label="{E(t("sessions.editName", code=own))}" tabindex="-1">'
        f'<li class="bn-picker-head" role="none"><span class="dimension-toggle" role="radiogroup" '
        f'aria-label="{E(t("sessions.picker.role"))}">{roles}</span></li>{rows}{new}</ul>'
    )


def session_row(sid: str, num: int, speakers: list[tuple[str, str, str]], date: str, dur: str,
                with_picker: bool) -> str:
    cells = []
    for code, _role, name in speakers:
        is_open = with_picker and (sid, code) == OPEN_ON
        cells.append(
            '<span class="bn-person-picker-anchor">'
            '<button type="button" class="bn-person-picker-trigger" aria-haspopup="menu" '
            f'aria-expanded="{"true" if is_open else "false"}"'
            f'{" data-open-trigger" if is_open else ""}>{badge(code, name)}</button>'
            f'{picker(code) if is_open else ""}</span>'
        )
    return (
        f'<tr data-session="{sid}"><td class="bn-session-id"><a href="#">#{num}</a></td>'
        f'<td class="bn-session-speakers">{"".join(cells)}</td>'
        f'<td class="bn-session-meta"><div>{E(date)}</div></td>'
        f'<td class="bn-session-duration">{E(dur)}</td><td><a href="#">interview-{num}.mp4</a></td></tr>'
    )


def sessions_pane(with_picker: bool) -> str:
    head = "".join(
        f'<th{cls}>{E(t("dashboard." + k))}</th>'
        for k, cls in (
            ("colId", ""), ("colParticipants", ""), ("colStart", ""),
            ("colDuration", ' class="bn-session-duration"'), ("colInterviews", ""),
        )
    )
    rows = "".join(session_row(*s, with_picker=with_picker) for s in SESSIONS)
    mods = E(t("sessions.moderatedBy", names="Alex"))
    return (
        '<div class="bn-dashboard-pane bn-dashboard-full" data-probe="pane">'
        f'<section class="bn-session-table" data-probe="section"><p class="bn-session-moderators">{mods}</p>'
        f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></section></div>"
    )


def dashboard(variant: str) -> str:
    # The pane that follows the Sessions pane on the shipped dashboard: the featured quotes.
    after = (
        '<div class="bn-dashboard-pane bn-dashboard-full" aria-hidden="true">'
        '<div style="height:7rem"></div></div>'
    )
    return (
        f'<div class="frame-app" data-variant="{variant}"><div class="bn-dashboard">'
        f"{sessions_pane(True)}{after}</div></div>"
    )


def frame(tag: str, title: str, body: str, probe: str) -> str:
    return (
        f'<figure class="frame"><div class="frame-bar"><span class="frame-tag">{E(tag)}</span>'
        f'<span>{E(title)}</span></div>{body}</figure>'
        f'<div class="probe" data-probe-for="{probe}"><span class="probe-label">Measured here</span>'
        '<span class="probe-out">…</span></div>'
    )


def commentary(inner: str) -> str:
    return f'<aside class="com"><span class="com-label">Commentary</span>{inner}</aside>'


# ── The audit, read from the tree ──────────────────────────────────────────────────────────────

def surfaces() -> list[dict[str, str]]:
    out = []
    for name, family, rel, starts, placement in SURFACES:
        a, _b, body = rule_at(rel, starts)
        out.append({
            "name": name, "family": family, "where": f"{rel}:{a}", "placement": placement,
            "position": decl(body, "position"), "z": decl(body, "z-index"),
            "shadow": decl(body, "box-shadow"), "radius": decl(body, "border-radius"),
            "border": decl(body, "border"),
        })
    return out


def tokenised(shadow: str) -> str:
    if not shadow:
        return "none"
    if "light-dark(" in shadow:
        return "own dark"
    if "var(--bn-" in shadow and not re.search(r"rgba?\(|#[0-9a-f]{3}", shadow):
        return "token"
    if "var(--bn-" in shadow:
        return "mixed"
    return "literal"


def inventory_table(rows: list[dict[str, str]]) -> str:
    body = []
    for r in rows:
        body.append(
            f'<tr><td>{E(r["name"])}</td><td>{E(r["family"])}</td>'
            f'<td class="mono">{E(r["where"])}</td>'
            f'<td class="{"warn" if r["placement"] == "in flow" else ""}">{E(r["placement"])}</td>'
            f'<td class="mono">{E(r["z"] or "—")}</td>'
            f'<td class="mono">{E(r["shadow"] or "—")}</td>'
            f'<td class="{tokenised(r["shadow"]).replace(" ", "-")}">{tokenised(r["shadow"])}</td></tr>'
        )
    return (
        '<table class="audit"><thead><tr><th>Surface</th><th>Family</th><th>Rule</th>'
        "<th>Placed</th><th>z-index</th><th>box-shadow</th><th>Shadow is</th></tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table>'
    )


def workaround_list() -> str:
    items = []
    for rel, starts, what in WORKAROUNDS:
        a, _b, _body = rule_at(rel, starts)
        items.append(f'<li><code>{E(rel)}:{a}</code>: {E(what)}.</li>')
    return f'<ul>{"".join(items)}</ul>'


def shadow_specimens(rows: list[dict[str, str]]) -> tuple[str, int]:
    groups: dict[str, list[str]] = {}
    for r in rows:
        if r["shadow"] and r["shadow"] != "none":
            groups.setdefault(r["shadow"], []).append(r["name"])
    cards = []
    for i, (shadow, users) in enumerate(groups.items(), 1):
        box = f'<div class="sp-box" style="box-shadow:{E(shadow)}"></div>'
        cards.append(
            f'<div class="sp"><div class="sp-pair"><div class="sp-col sp-light">{box}</div>'
            f'<div class="sp-col sp-dark">{box}</div></div>'
            f'<div class="sp-cap"><span class="sp-n">S{i}</span> <code>{E(shadow)}</code>'
            f'<span class="sp-users">{E("; ".join(users))}</span></div></div>'
        )
    return f'<div class="sp-grid">{"".join(cards)}</div>', len(groups)


def z_ladder(rows: list[dict[str, str]]) -> str:
    extra = [
        ("Dialog backdrop (--bn-overlay-z)", "1000"),
        ("Toast (--bn-toast-z)", "1100"),
        ("Toolbar, sticky", decl(rule_at("bristlenose/theme/organisms/toolbar.css", ".toolbar {")[2],
                                 "z-index") or "?"),
    ]
    # A var() value is one of the two tokens, listed once in `extra`.
    items = [(r["name"], r["z"]) for r in rows if r["z"] and "var(" not in r["z"]] + extra
    resolved = []
    for name, z in items:
        m = re.match(r"^\d+$", z)
        resolved.append((int(z) if m else -1, name, z))
    resolved.sort(reverse=True)
    li = "".join(
        f'<li><span class="z-v mono">{E(z)}</span><span>{E(name)}</span></li>' for _n, name, z in resolved
    )
    return f'<ol class="z-ladder">{li}</ol>'


# ── Section 6: proposed tokens, drawn on the real picker ───────────────────────────────────────

# DECIDED by the owner on 26 Nov 2026 (B, above dialogs, notification token), not yet shipped.
# Named after the house pattern (--bn-modal-shadow, --bn-overlay-z): the thing first, then
# -shadow or -z. Built only from colour tokens that already exist.
PROPOSED = {
    "--bn-popover-shadow": (
        "0 0 0 1px var(--bn-modal-hairline), 0 4px 16px var(--bn-colour-shadow), "
        "0 1px 4px var(--bn-colour-shadow)"
    ),
    "--bn-notification-shadow": "0 4px 20px var(--bn-modal-shadow-colour)",
    "--bn-sticky-z": "100",
    "--bn-popover-z": "1050",
}
PROPOSED_CSS = (
    "/* ════ DECIDED tokens (26 Nov 2026), not yet in the tree (section 6) ════ */\n:root {\n"
    + "".join(f"    {k}: {v};\n" for k, v in PROPOSED.items())
    + "}\n"
)

# Three panes, one variable moved at a time: today, the shadow token, the token plus the dialog's
# hairline in place of the border.
POPOVER_VARIANTS = [
    ("today", "0 4px 12px var(--bn-colour-shadow)", "Shipped: every menu, the picker included"),
    ("A", "0 4px 16px var(--bn-colour-shadow), 0 1px 4px var(--bn-colour-shadow)",
     "Not chosen: the two-layer shadow alone, border as today"),
    ("B", "var(--bn-popover-shadow)",
     "Chosen: --bn-popover-shadow, the shadow plus the dialog's hairline in place of the border"),
]
NOTIFICATION_VARIANTS = [
    ("today", "0 4px 20px rgba(0, 0, 0, 0.25)", "Shipped: activity chip, AutoCode toast"),
    ("chosen", "var(--bn-notification-shadow)", "--bn-notification-shadow"),
]


def popover_specimens() -> str:
    cols = []
    for tag, shadow, cap in POPOVER_VARIANTS:
        ring = ' data-ring=""' if tag == "B" else ""
        cells = "".join(
            f'<div class="pv-cell sp-{scheme}"><div class="pv-host"{ring} '
            f'style="--pv-shadow:{E(shadow)}">{picker("p3")}</div></div>'
            for scheme in ("light", "dark")
        )
        cols.append(
            f'<figure class="frame pv-frame"><div class="frame-bar"><span class="frame-tag">{E(tag)}'
            f'</span><span class="mono">{E(cap)}</span></div><div class="pv-pair">{cells}</div></figure>'
        )
    return f'<div class="pv-grid">{"".join(cols)}</div>'


def notification_specimens() -> str:
    cards = []
    for tag, shadow, cap in NOTIFICATION_VARIANTS:
        box = f'<div class="sp-box nt-box" style="box-shadow:{E(shadow)}"></div>'
        cards.append(
            f'<div class="sp"><div class="sp-pair"><div class="sp-col sp-light">{box}</div>'
            f'<div class="sp-col sp-dark">{box}</div></div>'
            f'<div class="sp-cap"><span class="sp-n">{E(tag)}</span> <code>{E(cap)}</code></div></div>'
        )
    return f'<div class="sp-grid">{"".join(cards)}</div>'


FAMILY_TOKENS = {
    "menu": ("--bn-popover-shadow", "--bn-popover-z"),
    "popover": ("--bn-popover-shadow", "--bn-popover-z"),
    "tooltip": ("--bn-popover-shadow", "--bn-popover-z"),
    "drag": ("--bn-popover-shadow", "--bn-popover-z"),
    "notification": ("--bn-notification-shadow", "--bn-toast-z"),
    "overlay": ("unchanged (--bn-overlay-shadow / --bn-modal-shadow)", "--bn-overlay-z"),
}


def mapping_table(rows: list[dict[str, str]]) -> str:
    body = "".join(
        f'<tr><td>{E(r["name"])}</td><td class="mono">{E(r["shadow"] or "—")}</td>'
        f'<td class="mono nw">{E(FAMILY_TOKENS[r["family"]][0])}</td>'
        f'<td class="mono">{E(r["z"] or "—")}</td>'
        f'<td class="mono nw">{E(FAMILY_TOKENS[r["family"]][1])}</td></tr>'
        for r in rows
    )
    return (
        '<table class="audit"><thead><tr><th>Surface</th><th>Shadow today</th><th>Proposed</th>'
        "<th>z today</th><th>Proposed</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def proposed_ladder() -> str:
    tiers = [
        ("—", "Content", "auto, or a local 1–2 inside one component; nothing floats here"),
        ("100", "--bn-sticky-z (new)", "the toolbar (100 today), the transcript header (10) and the other sticky bars"),
        ("1000", "--bn-overlay-z (exists)", "dialog backdrop and dialog, contents overlay"),
        ("1050", "--bn-popover-z (new)", "every menu, picker, popover, tooltip, drag ghost, in the floating layer"),
        ("1100", "--bn-toast-z (exists)", "toast, activity chip, AutoCode toast"),
    ]
    li = "".join(
        f'<li><span class="z-v mono">{E(v)}</span><span class="mono">{E(n)}</span><span>{E(w)}</span></li>'
        for v, n, w in reversed(tiers)
    )
    return f'<ol class="z-ladder z-prop">{li}</ol>'


CHROME_CSS = """
/* ════ mockup chrome — not shipped ════ */
html { color-scheme: light dark; }
body.mk { margin: 0; padding: 28px 32px 80px; background: light-dark(#f3f3f4, #1b1b1d);
  color: var(--bn-colour-text); font-family: var(--bn-font-body); font-size: 14px; line-height: 1.5; }
.mk h1 { font-size: 22px; margin: 0 0 4px; } .mk h2 { font-size: 17px; margin: 48px 0 8px; }
.mk .lede { max-width: 62rem; color: light-dark(#444, #bbb); margin: 0 0 18px; }
.mk code, .mk .mono { font-family: var(--bn-font-mono); font-size: 12px; }
.bar { position: sticky; top: 0; z-index: 2000; display: flex; gap: 18px; align-items: center;
  padding: 8px 12px; margin: 0 -12px 18px; background: light-dark(#f3f3f4ee, #1b1b1dee);
  border-bottom: 1px solid light-dark(#ddd, #333); font-size: 12px; }
.key { display: flex; gap: 18px; font-size: 12px; }
.key .sw-a { display: inline-block; width: 14px; height: 14px; border: 1px solid #999;
  background: var(--bn-colour-bg); vertical-align: -2px; margin-right: 6px; }
.key .sw-c { display: inline-block; width: 14px; height: 14px; vertical-align: -2px; margin-right: 6px;
  background: repeating-linear-gradient(135deg, light-dark(#c9ccd3, #444) 0 3px, transparent 3px 6px); }
.frame { margin: 18px 0 0; width: 900px; border: 1px solid light-dark(#cfcfd4, #3a3a3e);
  border-radius: 8px; overflow: visible; background: var(--bn-colour-bg); }
.frame-bar { display: flex; gap: 10px; align-items: center; padding: 6px 10px; font-size: 12px;
  background: light-dark(#e9e9ec, #2a2a2d); border-bottom: 1px solid light-dark(#d5d5da, #3a3a3e);
  border-radius: 8px 8px 0 0; color: light-dark(#333, #ccc); }
.frame-tag { font-family: var(--bn-font-mono); font-size: 11px; padding: 1px 6px; border-radius: 4px;
  background: light-dark(#fff, #1b1b1d); border: 1px solid light-dark(#ccc, #444); }
.frame-app { padding: var(--bn-space-lg); }
.probe { width: 900px; margin: 6px 0 0; font-size: 12px; display: flex; gap: 10px; }
.probe-label { font-family: var(--bn-font-mono); font-size: 11px; color: light-dark(#666, #999);
  white-space: nowrap; }
.probe-out b.bad { color: light-dark(#b42318, #ff8a80); } .probe-out b.ok { color: light-dark(#067647, #7ee2a8); }
.com { display: block; max-width: 900px; box-sizing: border-box; margin: 14px 0 0; padding: 8px 14px;
  border: 7px solid transparent; border-left: 3px solid light-dark(#8a93a6, #6b7385);
  background: linear-gradient(light-dark(#f3f3f4, #1b1b1d), light-dark(#f3f3f4, #1b1b1d)) padding-box,
    repeating-linear-gradient(135deg, light-dark(#c9ccd3, #3d3d44) 0 5px, transparent 5px 10px) border-box;
  color: light-dark(#333, #ccc); }
.com-label { display: block; font-family: var(--bn-font-mono); font-size: 10.5px; letter-spacing: .04em;
  text-transform: uppercase; color: light-dark(#667, #99a); margin-bottom: 4px; }
.com p { margin: 6px 0; } .com ol, .com ul { margin: 6px 0; padding-left: 1.3rem; }
table.audit { border-collapse: collapse; font-size: 12px; margin-top: 12px; max-width: 1200px; }
table.audit th, table.audit td { text-align: left; vertical-align: top; padding: 4px 8px;
  border-bottom: 1px solid light-dark(#ddd, #333); }
table.audit td.warn { color: light-dark(#b54708, #fdb022); }
table.audit td.literal { color: light-dark(#b42318, #ff8a80); }
table.audit td.mixed, table.audit td.own-dark { color: light-dark(#b54708, #fdb022); }
table.audit td.token { color: light-dark(#067647, #7ee2a8); }
.sp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 18px;
  max-width: 1200px; margin-top: 12px; }
.sp-pair { display: grid; grid-template-columns: 1fr 1fr; border-radius: 8px; overflow: hidden;
  border: 1px solid light-dark(#d5d5da, #3a3a3e); }
.sp-col { padding: 26px 22px 30px; background: var(--bn-colour-bg); color: var(--bn-colour-text); }
.sp-light { color-scheme: light; } .sp-dark { color-scheme: dark; }
.sp-box { height: 54px; border-radius: var(--bn-radius-md); background: var(--bn-colour-bg);
  border: 1px solid var(--bn-colour-border); }
.sp-cap { font-size: 12px; margin-top: 6px; } .sp-n { font-family: var(--bn-font-mono); font-weight: 700; }
.sp-users { display: block; color: light-dark(#555, #aaa); }
.z-ladder { list-style: none; padding: 0; margin: 12px 0 0; max-width: 620px; font-size: 12.5px; }
.z-ladder li { display: flex; gap: 12px; padding: 2px 0; border-bottom: 1px solid light-dark(#e2e2e6, #2e2e32); }
.z-v { width: 4rem; text-align: right; }
table.dec { border-collapse: collapse; font-size: 12.5px; max-width: 900px; }
table.dec td, table.dec th { text-align: left; vertical-align: top; padding: 4px 8px;
  border-bottom: 1px solid light-dark(#ddd, #333); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
/* Frame 2's one variable: the pane's overflow-x: auto (organisms/global-nav.css) taken out. */
.frame-app[data-variant="visible"] .bn-dashboard-pane { overflow: visible; }
/* Section 6: the shipped picker drawn in place (static), its shadow the only variable. */
.pv-grid { display: grid; gap: 4px; }
.pv-pair { display: grid; grid-template-columns: 1fr 1fr; border-radius: 0 0 8px 8px; overflow: hidden; }
.pv-cell { padding: 22px 28px 36px; background: var(--bn-colour-bg); color: var(--bn-colour-text); }
.pv-host .export-dropdown-menu { position: static; display: block; width: max-content;
  box-shadow: var(--pv-shadow); }
.pv-host[data-ring] .export-dropdown-menu { border-color: transparent; }
.nt-box { height: 40px; border-radius: var(--bn-radius-pill); }
.z-prop li { display: grid; grid-template-columns: 4rem 15rem 1fr; }
table.audit td.nw { white-space: nowrap; }
"""

PROBE_JS = """
(() => {
  const clipBox = (el) => {
    for (let a = el.parentElement; a; a = a.parentElement) {
      const cs = getComputedStyle(a);
      const paint = /paint|strict|content/.test(cs.contain) || cs.contentVisibility === 'auto';
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible' || paint) return a;
    }
    return null;
  };
  const name = (el) => '.' + [...el.classList].slice(0, 2).join('.');
  const run = () => {
    document.querySelectorAll('.probe').forEach((p) => {
      const v = p.dataset.probeFor;
      const app = document.querySelector('.frame-app[data-variant="' + v + '"]');
      const menu = v === 'portal' ? document.querySelector('ul[data-portal]')
        : app.querySelector('.bn-person-picker');
      const pane = app.querySelector('[data-probe="pane"]');
      const section = app.querySelector('[data-probe="section"]');
      const m = menu.getBoundingClientRect();
      const box = clipBox(menu);
      let shown = m.height;
      if (box && box !== document.documentElement && box !== document.body) {
        const b = box.getBoundingClientRect();
        shown = Math.max(0, Math.min(m.bottom, b.bottom) - Math.max(m.top, b.top));
      }
      const hidden = Math.round(m.height - shown);
      const pcs = getComputedStyle(pane);
      const out = [];
      out.push(hidden > 0
        ? '<b class="bad">' + hidden + ' of ' + Math.round(m.height) + ' px of the picker hidden</b> by <code>'
          + name(box) + '</code>'
        : '<b class="ok">the whole picker shows</b> (' + Math.round(m.height) + ' px)');
      out.push('pane computes <code>overflow-x: ' + pcs.overflowX + '; overflow-y: ' + pcs.overflowY + '</code>');
      if (pcs.overflowY !== 'visible') out.push('pane scrolls '
        + (pane.scrollHeight - pane.clientHeight) + ' px vertically');
      out.push('<code>.bn-session-table</code> is <code>container-type: '
        + getComputedStyle(section).containerType + '</code>');
      p.querySelector('.probe-out').innerHTML = out.join(' · ');
    });
    // Does the section's container-type trap a position:fixed child (layout containment)?
    const fx = document.getElementById('fixed-probe');
    if (fx) {
      const r = fx.getBoundingClientRect();
      const s = fx.parentElement.getBoundingClientRect();
      const trapped = Math.abs(r.top - s.top) < 1 && Math.abs(r.left - s.left) < 1;
      document.getElementById('fixed-probe-out').innerHTML = trapped
        ? '<b class="bad">trapped</b>: a <code>position: fixed</code> child of <code>.bn-session-table</code> is placed against the section, not the viewport'
        : '<b class="ok">not trapped</b>: a <code>position: fixed</code> child of <code>.bn-session-table</code> is placed against the viewport (top ' + Math.round(r.top) + ', left ' + Math.round(r.left) + ')';
    }
  };
  // The portal stand-in: the same <ul>, moved to <body>, placed from its badge's rect.
  const place = () => {
    const ul = document.querySelector('ul[data-portal]');
    const trig = document.querySelector('.frame-app[data-variant="portal"] [data-open-trigger]');
    if (!ul || !trig) return;
    const r = trig.getBoundingClientRect();
    ul.style.top = r.bottom + 'px';
    ul.style.left = r.left + 'px';
  };
  const portal = () => {
    const app = document.querySelector('.frame-app[data-variant="portal"]');
    const ul = app.querySelector('.bn-person-picker');
    ul.setAttribute('data-portal', '');
    ul.style.position = 'fixed';
    ul.style.right = 'auto';
    document.body.appendChild(ul);
    place();
  };
  const fixedProbe = () => {
    const sec = document.querySelector('.frame-app[data-variant="shipped"] [data-probe="section"]');
    const d = document.createElement('div');
    d.id = 'fixed-probe';
    d.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;pointer-events:none';
    sec.appendChild(d);
  };
  document.getElementById('pal').addEventListener('change', (e) => {
    document.documentElement.dataset.colorTheme = e.target.value; run();
  });
  document.getElementById('sch').addEventListener('change', (e) => {
    if (e.target.value === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = e.target.value;
  });
  window.addEventListener('scroll', place, { passive: true });
  window.addEventListener('resize', () => { place(); run(); });
  portal(); fixedProbe(); run();
  document.fonts && document.fonts.ready.then(() => { place(); run(); });
})();
"""


def build() -> str:
    css = "".join(css_block(f) for f in CSS_FILES) + report_rules()
    rows = surfaces()
    specimens, n_shadows = shadow_specimens(rows)
    in_flow = sum(1 for r in rows if r["placement"] == "in flow")
    literal = sum(1 for r in rows if tokenised(r["shadow"]) == "literal")

    clip = (
        frame("1 · shipped", "Project dashboard, Sessions pane, picker open on p3 (web, 900 px)",
              dashboard("shipped"), "shipped")
        + commentary(
            "<p>The picker is an absolutely positioned <code>&lt;ul&gt;</code> inside its badge's "
            "<code>.bn-person-picker-anchor</code> (<code>SpeakerPickerTrigger.tsx</code>). The pane it "
            "opens in, <code>.bn-dashboard-pane</code>, sets <code>overflow-x: auto</code> so a wide table "
            "scrolls sideways. CSS cannot scroll one axis and leave the other visible: when one axis is "
            "not <code>visible</code>, a <code>visible</code> on the other <em>computes to</em> "
            "<code>auto</code>. So the pane is a scroll box in both directions, and the part of the "
            "picker that hangs below the last row is inside it, behind a scrollbar. The probe line under "
            "each frame reads this from the engine you have this page open in.</p>"
            "<p>The Mac app is fine because it never draws this <code>&lt;ul&gt;</code>: "
            "<code>openNativePicker</code> hands the same model to an AppKit popover, which is a window "
            "of its own.</p>")
        + frame("2 · one variable", "Same, with the pane's overflow-x: auto taken out",
                dashboard("visible"), "visible")
        + commentary(
            "<p>Proof of cause, not a fix. Taking the overflow away lets the picker float, but the pane "
            "is there to scroll a wide table sideways at narrow widths, and every other control inside "
            "it would now be one rule away from the same bug. <code>overflow-x: clip</code> would not "
            "help either: it keeps the other axis visible, but it cuts a wide table instead of scrolling "
            "it, and it still cuts a picker that hangs off the pane's right edge.</p>")
        + frame("3 · floating layer", "Same, with the picker moved to <body> and placed from its badge",
                dashboard("portal"), "portal")
        + commentary(
            "<p>The picker is the same element with the same classes, moved to the end of "
            "<code>&lt;body&gt;</code> and given <code>position: fixed</code> at its badge's bottom-left "
            "corner (this page's script, standing in for <code>createPortal</code>). No ancestor can cut "
            "it, because it has none but <code>&lt;body&gt;</code>. The app already does this for one "
            "floating surface: <code>TapestryThumb.tsx</code> portals the tapestry's hover frame and "
            "places it from a measured rect. Dialogs and toasts portal too.</p>"
            '<p>Measured here: <span id="fixed-probe-out">…</span>. That decides whether the in-place '
            "shortcut (leave the picker where it is, make it <code>position: fixed</code>) is available: "
            "layout containment, which <code>container-type</code> can bring with it, makes the "
            "container the containing block for fixed children, and then they are cut like "
            "absolute ones. Even where it is not trapped, the shortcut is fragile: any ancestor "
            "that later gains a <code>transform</code>, <code>filter</code> or "
            "<code>will-change</code> (an animation, say) traps it again, and it needs the same "
            "measured placement a portal does. The portal costs the same and has nothing to "
            "go wrong under it.</p>")
    )

    decisions = [
        ("1", "Floating layer rule",
         "Anything that floats over content (menu, dropdown, picker, popover, tooltip) renders in a "
         "floating layer at the end of <code>&lt;body&gt;</code>, never in flow. One shared primitive "
         "does the portal, the placement from the trigger's rect, flipping above when there is no room "
         "below, and repositioning on scroll and resize. The picker is the first user; the others move "
         "as they are touched. Owner call: one primitive now, or the picker alone first."),
        ("2", "Placement engine",
         "Hand-rolled (as TapestryThumb does) or the platform's <code>popover</code> attribute and CSS "
         "anchor positioning, which put the surface in the top layer and need no portal. Browser and "
         "WKWebView support for anchor positioning has to be measured on the Mac targets before it is "
         "chosen; this page has not measured it."),
        ("3", "Elevation tokens",
         "Two new shadow tokens, <code>--bn-popover-shadow</code> (every menu, picker, popover, "
         "tooltip, one value, as macOS draws menus and popovers alike) and "
         "<code>--bn-notification-shadow</code> (toast, chip), built only from colour tokens that "
         "exist, beside <code>--bn-overlay-shadow</code> and <code>--bn-modal-shadow</code>. "
         "<code>--bn-control-raised-shadow</code> is a control, not a floating surface, and stays. "
         "<b>Decided 26 Nov 2026 (owner): B</b>, the shadow plus the dialog's hairline in place of "
         "the border, and <code>--bn-notification-shadow</code> for toasts and the chip."),
        ("4", "z-index ladder",
         "Two new layers, <code>--bn-sticky-z</code> and <code>--bn-popover-z</code>, beside "
         "<code>--bn-overlay-z</code> and <code>--bn-toast-z</code>. With a floating layer the "
         "per-component values (the 1, 2, 10 and 20 that lift one card over its sibling) stop being "
         "needed. <b>Decided 26 Nov 2026 (owner): menus above dialogs</b>, "
         "<code>--bn-popover-z: 1050</code>."),
        ("5", "Where the rule lives",
         "Promote the tooltip spec in <code>bristlenose/theme/CLAUDE.md</code> to a floating-surfaces "
         "spec (layer, shadow token, radius, border, motion), and replace its literal shadow with the "
         "token. That spec is the only written rule today and it covers tooltips alone."),
    ]
    dec_rows = "".join(f"<tr><td>{n}</td><td><b>{h}</b></td><td>{b}</td></tr>" for n, h, b in decisions)

    com_surfaces = commentary(
        f"<p>{len(rows)} surfaces. <b>{in_flow} are placed in flow</b>: absolutely positioned inside "
        "the element that opens them, so each is exposed to the same bug wherever an ancestor "
        "scrolls, clips or contains paint. The house has already patched this three times, one host "
        "at a time:</p>"
        + workaround_list()
        + "<p>Each patch fixes one host for one surface. The picker on the dashboard is the fourth "
        "host, and it cannot be patched the same way, because the pane's overflow has a job.</p>"
    )
    com_shadows = commentary(
        f"<p><b>{n_shadows} distinct shadows</b> for what is, at most, four levels (raised, floating, "
        f"notification, modal). {literal} are written as fixed colours, so they ignore the palette "
        "and stay the same in dark, where a 4–12% black shadow on a near-black page draws nothing: "
        "compare the right-hand box of each pair. One writes its own dark value with "
        "<code>light-dark()</code>. Those built on <code>--bn-colour-shadow</code> (10% black in "
        "light, 40% in dark, tinted per palette) are the only ones that still show a faint edge in "
        "dark, and even there the 1px border is doing most of the work. The tooltip spec in <code>theme/CLAUDE.md</code> writes its shadow as a literal, so "
        "the written rule is itself one of the dark-mode misses. The tapestry popover borrows "
        "<code>--bn-focus-shadow</code>, a focus token, for elevation.</p>"
    )
    com_z = commentary(
        "<p>Two values are tokens (<code>--bn-overlay-z</code>, <code>--bn-toast-z</code>); the rest "
        "are numbers chosen file by file. Menus sit at 200, tooltips at 300 and 400, and the Screens "
        "menu at 1000, level with the dialog backdrop. A floating layer makes most of these moot, "
        "since a portalled surface competes only with other portalled surfaces.</p>"
    )
    com_prop = commentary(
        "<p><b>Decided by the owner on 26 Nov 2026: B, menus above dialogs, and the notification "
        "token.</b> Decisions 1, 2 and 5 are still open. The tokens are in a block headed "
        "<code>DECIDED</code> at the end of this page's theme CSS; nothing in the tree has them "
        "yet. Each frame below is the shipped picker on the "
        "dashboard pane's background, light on the left and dark on the right, with its shadow the "
        "only thing that changes. <b>A</b> is the two-layer geometry the tooltip spec already "
        "writes (<code>0 4px 16px</code> plus <code>0 1px 4px</code>, the Screens menu's value), "
        "coloured by <code>--bn-colour-shadow</code> instead of fixed black, so it follows the "
        "palette and deepens to 40% in dark. <b>B</b> moves a second variable: it borrows the "
        "dialog's <code>--bn-modal-hairline</code> (10% black in light, 14% <em>white</em> in dark) "
        "as a ring in place of the 1px border, which is how the dialog already keeps its edge in "
        "dark, and how macOS draws a menu's edge on a dark desktop.</p>"
    )
    com_prop_b = commentary(
        "<p>What to look for: in light, A and B are close to today, a touch deeper. In dark, a "
        "black shadow on the near-black page barely registers whatever its strength, so the edge "
        "has to come from something lighter than the page: B's white hairline does that, A's "
        "border (<code>#2d2d2d</code> on <code>#1c1c1c</code> in the default palette) only "
        "faintly. B touches one more rule per surface (the border colour), so it is the larger "
        "change. Switch Palette to Edo to see both follow the warm shadow colour in light.</p>"
    )
    com_ladder = commentary(
        "<p>Menus above dialogs, below toasts. No menu opens inside a dialog today (the one "
        "candidate, <code>TagInput</code> in <code>CodebookAuthoring.tsx</code>, is outside its "
        "<code>ConfirmDialog</code>s), so this is a rule for the next one, not a fix. A floating "
        "surface opened from a dialog must draw over it, as a macOS popover over a sheet does; "
        "a page menu is closed by the click that opens a dialog, so putting the layer above the "
        "dialog costs nothing. A toast stays on top of everything, as "
        "<code>--bn-toast-z</code> already says. The 200, 300, 400 and the Screens menu's 1000 all "
        "become <code>--bn-popover-z</code>; the small local values that lift one card over its "
        "sibling go once their surface moves to the floating layer.</p>"
    )
    com_dec = commentary(
        "<p>Nothing here is built. The decisions, in the order they unblock the picker fix:</p>"
        '<table class="dec"><tbody>' + dec_rows + "</tbody></table>"
    )

    return f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Floating surfaces — tooltip gallery, iteration 2</title>
<style>
/* Generated by docs/mockups/tooltip-gallery-v2.gen.py. SHIPPED CSS, inlined verbatim from the
   tree in theme order, each block headed by its path and line range. Nothing above the chrome
   block is written for the mockup. */
{css}
{PROPOSED_CSS}
{CHROME_CSS}
</style>
</head>
<body class="mk">
<div class="bar">
  <div class="key"><span><span class="sw-a"></span>Artefact: shipped CSS and markup</span>
  <span><span class="sw-c"></span>Commentary: not the product</span></div>
  <label>Palette <select id="pal"><option value="default">Default</option><option value="edo">Edo</option></select></label>
  <label>Scheme <select id="sch"><option value="auto">Auto</option><option value="light">Light</option><option value="dark">Dark</option></select></label>
</div>
<h1>Floating surfaces in the browser report</h1>
<p class="lede">Iteration 2 of <a href="tooltip-gallery.html">the tooltip gallery</a>. That page chose
one tooltip; this one starts from a bug (the speaker picker cut off on the project dashboard) and
audits every menu, picker, popover, tooltip and toast the theme draws: where it is placed, its
shadow, its z-index. An investigation: nothing in the product changes with it. Generated
from the tree by <code>tooltip-gallery-v2.gen.py</code>; rerun it after a theme change.</p>

<h2>1. The person picker on the dashboard</h2>
{clip}

<h2>2. Every floating surface</h2>
{com_surfaces}
{inventory_table(rows)}

<h2>3. Every floating shadow, light and dark</h2>
{com_shadows}
{specimens}

<h2>4. The z-index ladder</h2>
{com_z}
{z_ladder(rows)}

<h2>5. Decisions this asks for</h2>
{com_dec}

<h2>6. Token values (decided 26 Nov 2026)</h2>
{com_prop}
{popover_specimens()}
{com_prop_b}
<h3>Notifications</h3>
{notification_specimens()}
<h3>The ladder</h3>
{proposed_ladder()}
{com_ladder}
<h3>Every surface, today and proposed</h3>
{mapping_table(rows)}

<script>{PROBE_JS}</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
