#!/usr/bin/env python3
"""Generates docs/mockups/form-layout-four-fixes.html.

Four dialogs that do not yet use the Mac form layout (owner-approved 9 Nov 2026 on the Miro app
tab and the Mac Miro sheet), each drawn BEFORE (today, from its current code) and AFTER (the form
applied). The shipped theme CSS is read from the tree and inlined block by block, each headed by
its path and line range, so the web frames cannot drift from the product: diff a block against
the file. Every string is read from the shipped locale files; the three proposed colon labels are
composed from shipped values and flagged in the frame chrome. The Mac sheets are an HTML stand-in
(hand-rolled `mac-` CSS, not product CSS): SwiftUI measurements beat it.

Run:  .venv/bin/python docs/mockups/form-layout-four-fixes.gen.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "bristlenose" / "theme"
LOCALES = ROOT / "bristlenose" / "locales"
OUT = ROOT / "docs" / "mockups" / "form-layout-four-fixes.html"


# ── Shipped CSS, inlined verbatim, in bristlenose-theme.css order ──────────────────────────────
def block(rel: str, start: int | None = None, end: int | None = None) -> str:
    lines = (THEME / rel).read_text(encoding="utf-8").splitlines()
    a, b = (start or 1), (end or len(lines))
    body = "\n".join(lines[a - 1 : b])
    return f"/* ════ bristlenose/theme/{rel} — lines {a}–{b} ════ */\n{body}\n"


def rule(rel: str, selector_line: str) -> str:
    """One rule, located by a line that STARTS with the selector, to its closing brace."""
    lines = (THEME / rel).read_text(encoding="utf-8").splitlines()
    a = next(i for i, ln in enumerate(lines, 1) if ln.startswith(selector_line))
    b = next(i for i, ln in enumerate(lines, 1) if i > a and ln.startswith("}"))
    return block(rel, a, b)


SHIPPED_CSS = "\n".join(
    [
        block("tokens.css"),
        block("tokens-typography.css"),
        block("colors/palette-default.css"),
        block("colors/palette-edo.css"),
        block("atoms/modal.css"),
        rule("organisms/settings.css", ".bn-locale-select,"),
        rule("templates/report.css", "*,"),
        rule("templates/report.css", "html {"),
        rule("templates/report.css", "body {"),
        rule("templates/report.css", "h1, h2, h3, .description {"),
        rule("templates/report.css", "h2 {"),
        rule("templates/report.css", "hr {"),
    ]
)


# ── Strings: shipped locale values only ────────────────────────────────────────────────────────
def load(lang: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ns in ("common", "settings", "desktop"):
        out[ns] = json.loads((LOCALES / lang / f"{ns}.json").read_text(encoding="utf-8"))
    return out


BUNDLES = {"en": load("en"), "de": load("de")}


def t(lang: str, key: str, **subs: object) -> str:
    """`ns:dotted.key` (ns defaults to common), with {{placeholders}} filled."""
    ns, _, path = key.rpartition(":")
    node: object = BUNDLES[lang][ns or "common"]
    for part in path.split("."):
        node = node[part]  # type: ignore[index]
    text = str(node)
    for k, v in subs.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def e(s: str) -> str:
    return html.escape(s, quote=True)


# The three proposed colon labels. Each is a shipped value plus the locale's colon, or a verbatim
# lift of the Mac's already-translated label, so no word here is invented.
def new_keys(lang: str) -> dict[str, str]:
    return {
        "miro.boardNameFormLabel": t(lang, "desktop:miro.boardNameLabel"),
        "miro.colourByFormLabel": t(lang, "miro.colourByLabel") + ":",
        "export.languageLabel": t(lang, "settings:language.legend") + ":",
    }


SAMPLE_PROJECT = "Talismanic"
SAMPLE_TEAM = "Dev team"
SAMPLE_ACCOUNT = "Sam Taylor · Dev team"
SAMPLE_FLAG = f"sample data: “{SAMPLE_PROJECT}”, “{SAMPLE_ACCOUNT}”"
PROJECT_FLAG = f"sample data: “{SAMPLE_PROJECT}”"


# ── Frame chrome ───────────────────────────────────────────────────────────────────────────────
_uid = [0]


def uid(stem: str) -> str:
    _uid[0] += 1
    return f"{stem}-{_uid[0]}"


def frame(state: str, title: str, flags: list[str], stage: str, kind: str = "web") -> str:
    flag_html = "".join(f"<span>{e(f)}</span>" for f in flags)
    cls = "mk-frame mk-mac" if kind == "mac" else "mk-frame"
    return (
        f'<figure class="{cls}"><figcaption class="mk-chrome">'
        f'<span class="mk-state mk-{state.lower()}">{e(state)}</span> {e(title)}'
        f'<span class="mk-flags">{flag_html}</span></figcaption>{stage}</figure>'
    )


def web_stage(modal_cls: str, inner: str) -> str:
    return f'<div class="mk-stage"><div class="bn-modal {modal_cls}" role="dialog">{inner}</div></div>'


def mac_stage(inner: str) -> str:
    return f'<div class="mac-stage"><div class="mac-sheet">{inner}</div></div>'


# ── Web pieces (the components' own markup) ────────────────────────────────────────────────────
def radios(lang: str, name: str, order: tuple[str, str], checked: str) -> str:
    out = []
    for s in order:
        key = "miro.stickyShapeSquare" if s == "square" else "miro.stickyShapeRectangle"
        on = " checked" if s == checked else ""
        out.append(
            f'<label class="bn-export-checkbox"><input type="radio" name="{name}"{on}>'
            f"<span>{e(t(lang, key))}</span></label>"
        )
    return "".join(out)


def split_checkbox(lang: str) -> str:
    return (
        '<label class="bn-export-checkbox"><input type="checkbox" checked>'
        f'<span>{e(t(lang, "miro.splitLongQuotes"))}</span></label>'
    )


TEXT_INPUT_STYLE = "width:100%;box-sizing:border-box;padding:8px 10px"


def help_btn(lang: str) -> str:
    label = e(t(lang, "nav.help"))
    return f'<a class="bn-help-btn" href="#" aria-label="{label}" title="{label}">?</a>'


def seg(lang: str, selected: str) -> str:
    def b(key: str, on: bool) -> str:
        return f'<button role="tab" aria-selected="{"true" if on else "false"}">{e(t(lang, key))}</button>'

    return (
        '<div class="bn-seg" role="tablist">'
        + b("miro.tabApp", selected == "app")
        + b("miro.tabToken", selected == "token")
        + "</div>"
    )


def miro_notice(lang: str) -> str:
    template = t(lang, "miro.boardDestination")
    head, _, tail = template.partition("{{team}}")
    return f"{e(head)}<strong>{e(SAMPLE_TEAM)}</strong>{e(tail)} {e(t(lang, 'miro.uploadNotice'))}"


def colour_select(lang: str, sel_id: str) -> str:
    return (
        f'<select id="{sel_id}"><option>{e(t(lang, "miro.colourByNone"))}</option>'
        f'<option>{e(t(lang, "miro.colourBySentiment"))}</option></select>'
    )


# 0 · Reference: the shipped Miro app tab (MiroExportPanel.tsx, the app tabpanel)
def web_miro_app(lang: str) -> str:
    shape = uid("ref-shape")
    inner = (
        f'<h2>{e(t(lang, "miro.quotesTitle"))}</h2>{seg(lang, "app")}'
        '<div role="tabpanel"><div class="bn-board-form">'
        f"<span></span>{split_checkbox(lang)}"
        f'<span class="bn-board-form-label">{e(t(lang, "miro.stickyShapeLabel"))}</span>'
        f'<div class="bn-board-form-radios" role="radiogroup">'
        f'{radios(lang, shape, ("rectangle", "square"), "rectangle")}</div>'
        "<hr>"
        f'<span class="bn-board-form-label">{e(t(lang, "miro.appOnce"))}</span>'
        f'<span><a href="#">{e(t(lang, "miro.appAddLink"))}</a></span>'
        f'<span class="bn-board-form-label">{e(t(lang, "miro.appEither"))}</span>'
        f'<span><button type="button" class="bn-btn bn-btn-secondary bn-board-form-button">'
        f'{e(t(lang, "figjam.download"))}</button></span>'
        f'<span class="bn-board-form-label">{e(t(lang, "miro.appOr"))}</span>'
        '<span><button type="button" class="bn-btn bn-btn-primary bn-board-form-button bn-keep-width">'
        f'<span aria-hidden="false">{e(t(lang, "miro.copyBoard"))}</span>'
        f'<span aria-hidden="true">{e(t(lang, "miro.copied"))}</span></button></span>'
        f'<span class="bn-board-form-label">{e(t(lang, "miro.appThen"))}</span>'
        f'<span>{e(t(lang, "miro.appStep3"))}</span>'
        "</div>"
        f'<div class="bn-modal-actions">{help_btn(lang)}'
        f'<button class="bn-btn bn-btn-secondary">{e(t(lang, "miro.done"))}</button></div></div>'
    )
    return web_stage("bn-board-modal", inner)


def miro_token_head(lang: str) -> str:
    return (
        f'<h2>{e(t(lang, "miro.quotesTitle"))}</h2>{seg(lang, "token")}'
        '<div role="tabpanel">'
        f'<p class="bn-modal-subtitle">{e(t(lang, "miro.connected"))} · '
        f'<button class="bn-linkish">{e(t(lang, "miro.disconnect"))}</button></p>'
        f'<p class="bn-export-hint">{e(SAMPLE_ACCOUNT)}</p>'
    )


def miro_token_tail(lang: str) -> str:
    return (
        f'<p class="bn-export-hint" style="margin-top:10px">{miro_notice(lang)}</p>'
        f'<div class="bn-modal-actions">{help_btn(lang)}'
        f'<button class="bn-btn bn-btn-primary">{e(t(lang, "miro.createBoard"))}</button></div></div>'
    )


# 1 · Miro, developer access token tab, configure step
def web_miro_token_before(lang: str) -> str:
    name, col, shape = uid("mt-name"), uid("mt-col"), uid("mt-shape")
    inner = (
        miro_token_head(lang)
        + f'<label class="bn-export-hint" for="{name}">{e(t(lang, "miro.boardNameLabel"))}</label>'
        f'<input id="{name}" type="text" value="{e(SAMPLE_PROJECT)}" '
        f'placeholder="{e(t(lang, "miro.boardNamePlaceholder"))}" style="{TEXT_INPUT_STYLE}">'
        f'<label class="bn-export-hint" style="margin-top:10px" for="{col}">'
        f'{e(t(lang, "miro.colourByLabel"))}</label>'
        + colour_select(lang, col)
        + split_checkbox(lang).replace('class="bn-export-checkbox"', 'class="bn-export-checkbox" style="margin-top:12px"', 1)
        + '<fieldset class="bn-export-radios">'
        f'<legend class="bn-export-hint">{e(t(lang, "miro.stickyShape"))}</legend>'
        f'{radios(lang, shape, ("rectangle", "square"), "rectangle")}</fieldset>'
        + miro_token_tail(lang)
    )
    return web_stage("bn-board-modal", inner)


def web_miro_token_after(lang: str) -> str:
    nk = new_keys(lang)
    name, col, shape = uid("mt-name"), uid("mt-col"), uid("mt-shape")
    inner = (
        miro_token_head(lang)
        + '<div class="bn-board-form">'
        f'<label class="bn-board-form-label" for="{name}">{e(nk["miro.boardNameFormLabel"])}</label>'
        f'<input id="{name}" type="text" value="{e(SAMPLE_PROJECT)}" '
        f'placeholder="{e(t(lang, "miro.boardNamePlaceholder"))}" style="{TEXT_INPUT_STYLE}">'
        f'<label class="bn-board-form-label" for="{col}">{e(nk["miro.colourByFormLabel"])}</label>'
        f"<span>{colour_select(lang, col)}</span>"
        f"<span></span>{split_checkbox(lang)}"
        f'<span class="bn-board-form-label" id="{shape}-l">{e(t(lang, "miro.stickyShapeLabel"))}</span>'
        f'<div class="bn-board-form-radios" role="radiogroup" aria-labelledby="{shape}-l">'
        f'{radios(lang, shape, ("rectangle", "square"), "rectangle")}</div>'
        "</div>"
        + miro_token_tail(lang)
    )
    return web_stage("bn-board-modal", inner)


# 2 · FigJam, web
def figjam_actions(lang: str) -> str:
    return (
        f'<p class="bn-export-hint" style="margin-top:10px">{e(t(lang, "figjam.notice"))}</p>'
        '<div class="bn-modal-actions">'
        f'<button class="bn-btn bn-btn-secondary">{e(t(lang, "miro.cancel"))}</button>'
        f'<button class="bn-btn bn-btn-primary">{e(t(lang, "figjam.download"))}</button></div>'
    )


def web_figjam_before(lang: str) -> str:
    name, shape = uid("fj-name"), uid("fj-shape")
    inner = (
        f'<h2>{e(t(lang, "figjam.title"))}</h2>'
        f'<p class="bn-modal-subtitle">{e(t(lang, "figjam.intro"))}</p>'
        f'<label class="bn-export-hint" for="{name}">{e(t(lang, "miro.boardNameLabel"))}</label>'
        f'<input id="{name}" type="text" value="{e(SAMPLE_PROJECT)}" style="{TEXT_INPUT_STYLE}">'
        + split_checkbox(lang).replace('class="bn-export-checkbox"', 'class="bn-export-checkbox" style="margin-top:12px"', 1)
        + '<fieldset class="bn-export-radios">'
        f'<legend class="bn-export-hint">{e(t(lang, "miro.stickyShape"))}</legend>'
        f'{radios(lang, shape, ("square", "rectangle"), "square")}</fieldset>'
        + figjam_actions(lang)
    )
    return web_stage("bn-board-modal", inner)


def web_figjam_after(lang: str) -> str:
    nk = new_keys(lang)
    name, shape = uid("fj-name"), uid("fj-shape")
    inner = (
        f'<h2>{e(t(lang, "figjam.title"))}</h2>'
        f'<p class="bn-modal-subtitle">{e(t(lang, "figjam.intro"))}</p>'
        '<div class="bn-board-form">'
        f'<label class="bn-board-form-label" for="{name}">{e(nk["miro.boardNameFormLabel"])}</label>'
        f'<input id="{name}" type="text" value="{e(SAMPLE_PROJECT)}" style="{TEXT_INPUT_STYLE}">'
        f"<span></span>{split_checkbox(lang)}"
        f'<span class="bn-board-form-label" id="{shape}-l">{e(t(lang, "miro.stickyShapeLabel"))}</span>'
        f'<div class="bn-board-form-radios" role="radiogroup" aria-labelledby="{shape}-l">'
        f'{radios(lang, shape, ("square", "rectangle"), "square")}</div>'
        "</div>"
        + figjam_actions(lang)
    )
    return web_stage("bn-board-modal", inner)


# 4 · Export report, web
LOCALE_OPTION = {"en": "English", "de": "Deutsch"}  # frontend/src/i18n/localeLabels.ts (endonyms)


def export_checkbox(lang: str) -> str:
    return (
        '<label class="bn-export-checkbox"><input type="checkbox">'
        f'<span>{e(t(lang, "export.anonymise"))}'
        f'<small class="bn-export-hint">{e(t(lang, "export.anonymiseHint"))}</small></span></label>'
    )


def export_actions(lang: str) -> str:
    return (
        '<div class="bn-modal-actions">'
        f'<button class="bn-btn bn-btn-secondary">{e(t(lang, "buttons.cancel"))}</button>'
        f'<button class="bn-btn bn-btn-primary">{e(t(lang, "buttons.export"))}</button></div>'
    )


def locale_select(lang: str, sel_id: str = "") -> str:
    id_attr = f' id="{sel_id}"' if sel_id else ""
    return f'<select class="bn-locale-select"{id_attr}><option>{e(LOCALE_OPTION[lang])}</option></select>'


def web_export_before(lang: str) -> str:
    inner = (
        f'<h2>{e(t(lang, "export.heading"))}</h2>'
        f'<p class="bn-modal-subtitle">{e(t(lang, "export.subtitle"))}</p>'
        f'<label class="bn-export-locale"><span>{e(t(lang, "settings:language.legend"))}</span>'
        f"{locale_select(lang)}</label>"
        + export_checkbox(lang)
        + export_actions(lang)
    )
    return web_stage("bn-export-modal", inner)


def web_export_after(lang: str) -> str:
    nk = new_keys(lang)
    sel = uid("ex-lang")
    inner = (
        f'<h2>{e(t(lang, "export.heading"))}</h2>'
        f'<p class="bn-modal-subtitle">{e(t(lang, "export.subtitle"))}</p>'
        '<div class="bn-board-form">'
        f'<label class="bn-board-form-label" for="{sel}">{e(nk["export.languageLabel"])}</label>'
        f"<span>{locale_select(lang, sel)}</span>"
        f"<span></span>{export_checkbox(lang)}"
        "</div>"
        + export_actions(lang)
    )
    return web_stage("bn-export-modal", inner)


# ── Mac stand-in pieces (SwiftUI drawn in HTML; not product CSS) ───────────────────────────────
CHECK_SVG = (
    '<svg class="mac-ok" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">'
    '<circle cx="8" cy="8" r="6.6" fill="none" stroke="currentColor" stroke-width="1.3"/>'
    '<path d="M5 8.2l2 2 4-4.4" fill="none" stroke="currentColor" stroke-width="1.4" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def mac_toggle(text: str, on: bool) -> str:
    c = " checked" if on else ""
    return f'<label class="mac-check"><input type="checkbox"{c}><span>{e(text)}</span></label>'


def mac_radios(lang: str, name: str, order: tuple[str, str], checked: str) -> str:
    out = []
    for s in order:
        key = "miro.stickyShapeSquare" if s == "square" else "miro.stickyShapeRectangle"
        on = " checked" if s == checked else ""
        out.append(f'<label class="mac-check"><input type="radio" name="{name}"{on}><span>{e(t(lang, key))}</span></label>')
    return '<div class="mac-radios">' + "".join(out) + "</div>"


def mac_label(text: str, secondary: bool = False) -> str:
    cls = "mac-label mac-secondary" if secondary else "mac-label"
    return f'<span class="{cls}">{e(text)}</span>'


# Reference: MiroSheet.swift `configure` (the token tab, connected)
def mac_miro_token(lang: str) -> str:
    shape = uid("mm-shape")
    template = t(lang, "desktop:miro.boardDestination")
    head, _, tail = template.partition("{{team}}")
    notice = f"{e(head)}<b>{e(SAMPLE_TEAM)}</b>{e(tail)} {e(t(lang, 'miro.uploadNotice'))}"
    inner = (
        f'<div class="mac-headline">{e(t(lang, "miro.quotesTitle"))}</div>'
        '<div class="mac-seg"><span>' + e(t(lang, "miro.tabApp")) + '</span><span class="on">'
        + e(t(lang, "miro.tabToken")) + "</span></div>"
        '<div class="mac-grid">'
        + mac_label(t(lang, "desktop:miro.miroStatusLabel"))
        + f'<span class="mac-status">{CHECK_SVG}<span>{e(t(lang, "desktop:miro.connected"))}</span>'
        f'<span class="mac-grow"></span><button class="mac-btn mac-small">{e(t(lang, "miro.disconnect"))}</button></span>'
        + mac_label(t(lang, "desktop:miro.accountLabel"))
        + f"<span>{e(SAMPLE_ACCOUNT)}</span>"
        + mac_label(t(lang, "desktop:miro.boardNameLabel"))
        + f'<input class="mac-field" type="text" value="{e(SAMPLE_PROJECT)}">'
        + mac_label(t(lang, "desktop:miro.stickyColoursLabel"))
        + mac_toggle(t(lang, "miro.colourBySentiment"), False)
        + "<span></span>"
        + mac_toggle(t(lang, "miro.splitLongQuotes"), True)
        + mac_label(t(lang, "miro.stickyShapeLabel"))
        + mac_radios(lang, shape, ("rectangle", "square"), "rectangle")
        + "</div>"
        f'<div class="mac-sub">{notice}</div>'
        '<div class="mac-spacer"></div>'
        '<div class="mac-footer"><span class="mac-help">?</span><span class="mac-grow"></span>'
        f'<button class="mac-btn">{e(t(lang, "miro.cancel"))}</button>'
        f'<button class="mac-btn mac-default">{e(t(lang, "miro.createBoard"))}</button></div>'
    )
    return mac_stage(inner)


# 3 · FigJamSheet.swift `configure`
def mac_figjam(lang: str, secondary: bool, divider: bool) -> str:
    shape = uid("mf-shape")
    rule_html = '<div class="mac-divider"></div>' if divider else ""
    inner = (
        f'<div class="mac-headline">{e(t(lang, "figjam.title"))}</div>'
        f'<div class="mac-callout">{e(t(lang, "figjam.intro"))}</div>'
        '<div class="mac-grid">'
        + mac_label(t(lang, "desktop:miro.boardNameLabel"), secondary)
        + f'<input class="mac-field" type="text" value="{e(SAMPLE_PROJECT)}">'
        + rule_html
        + mac_label(t(lang, "desktop:figjam.stickyShapeLabel"), secondary)
        + mac_radios(lang, shape, ("square", "rectangle"), "square")
        + "<span></span>"
        + mac_toggle(t(lang, "miro.splitLongQuotes"), True)
        + "</div>"
        f'<div class="mac-sub">{e(t(lang, "figjam.notice"))}</div>'
        '<div class="mac-spacer"></div>'
        '<div class="mac-footer"><span class="mac-grow"></span>'
        f'<button class="mac-btn">{e(t(lang, "miro.cancel"))}</button>'
        f'<button class="mac-btn mac-default">{e(t(lang, "desktop:figjam.saveBoardFile"))}</button></div>'
    )
    return mac_stage(inner)


# ── Page ───────────────────────────────────────────────────────────────────────────────────────
CHROME_CSS = """\
/* ════ mockup chrome (not the product) ════ */
:root { color-scheme: light dark; }
body { padding: 0 28px 60px; background: light-dark(#eef0f3, #1c1d20); color: var(--bn-colour-text); }
.mk-bar { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; gap: 18px; align-items: center;
  margin: 0 -28px 18px; padding: 10px 28px; font: 12px/1.4 var(--bn-font-mono);
  background: light-dark(rgb(238 240 243 / .92), rgb(28 29 32 / .92)); backdrop-filter: blur(6px);
  border-bottom: 1px solid light-dark(#d5d8de, #33353a); }
.mk-bar fieldset { border: 0; margin: 0; padding: 0; display: inline-flex; gap: 8px; align-items: center; }
.mk-bar legend { float: left; margin-right: 6px; color: var(--bn-colour-muted); }
.mk-title { font: 600 20px/1.3 var(--bn-font-body); margin: 26px 0 4px; }
.mk-key { font: 12px/1.6 var(--bn-font-mono); color: var(--bn-colour-muted); margin: 0 0 8px; max-width: 1150px; }
.mk-key b { color: var(--bn-colour-text); font-weight: 600; }
.mk-sec { margin: 34px 0 0; }
.mk-h { font: 600 16px/1.3 var(--bn-font-body); margin: 0 0 12px; }
.mk-h small { font: 12px var(--bn-font-mono); color: var(--bn-colour-muted); font-weight: 400; margin-left: 8px; }
.mk-row { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
.mk-frame { flex: none; margin: 0; width: 560px; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgb(0 0 0 / .18); }
.mk-chrome { display: block; font: 11px/1.45 var(--bn-font-mono); padding: 8px 12px;
  background: light-dark(#e2e4e8, #2a2c30); color: light-dark(#444, #b8b8b8); }
.mk-state { font-weight: 700; letter-spacing: .05em; padding: 1px 5px; border-radius: 3px; color: #fff; }
.mk-before { background: #6b7280; } .mk-after { background: #0a7a3d; } .mk-shipped { background: #2563eb; }
.mk-variant { background: #9a5b00; }
.mk-flags { display: block; color: light-dark(#8a0050, #f08ac0); }
.mk-flags span { display: block; }
.mk-stage { padding: 24px; background: var(--bn-overlay-scrim); color: var(--bn-colour-text); }
.mk-stage .bn-modal { position: static; transform: none; opacity: 1; margin: 0 auto; }
/* Mac stand-in: hand-rolled for the frame, NOT product CSS. SwiftUI's own metrics win. */
.mac-stage { --mac-ink: light-dark(rgb(0 0 0 / .85), rgb(255 255 255 / .86));
  --mac-secondary: light-dark(rgb(0 0 0 / .5), rgb(255 255 255 / .55));
  --mac-accent: light-dark(#007aff, #0a84ff);
  padding: 28px 24px; background: light-dark(#c9ccd2, #121214); }
.mac-sheet { width: 460px; min-height: 400px; margin: 0 auto; padding: 20px; box-sizing: border-box;
  display: flex; flex-direction: column; gap: 12px; border-radius: 16px;
  background: light-dark(#f2f2f4, #2b2b2e); color: var(--mac-ink);
  font: 13px/16px -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  box-shadow: 0 0 0 .5px light-dark(rgb(0 0 0 / .22), rgb(255 255 255 / .14)), 0 14px 44px rgb(0 0 0 / .32); }
.mac-headline { font-weight: 700; text-align: center; }
.mac-callout { font-size: 12px; line-height: 15px; color: var(--mac-secondary); }
.mac-sub { font-size: 11px; line-height: 14px; color: var(--mac-secondary); }
.mac-sub b { font-weight: 600; color: var(--mac-ink); }
.mac-grid { display: grid; grid-template-columns: max-content minmax(0, 1fr); column-gap: 8px; row-gap: 12px;
  align-items: baseline; }
.mac-label { text-align: right; }
.mac-secondary { color: var(--mac-secondary); }
.mac-field { font: inherit; height: 22px; padding: 0 6px; box-sizing: border-box; width: 100%; color: inherit;
  border-radius: 5px; border: .5px solid light-dark(rgb(0 0 0 / .2), rgb(255 255 255 / .18));
  background: light-dark(#fff, rgb(255 255 255 / .06)); outline: none; }
.mac-check { display: inline-flex; gap: 6px; align-items: baseline; }
.mac-check input { margin: 0; width: 14px; height: 14px; accent-color: var(--mac-accent); transform: translateY(2px); flex: none; }
.mac-radios { display: flex; flex-wrap: wrap; column-gap: 20px; }
.mac-divider { grid-column: 1 / -1; height: 1px; background: light-dark(rgb(0 0 0 / .1), rgb(255 255 255 / .1)); }
.mac-status { display: flex; align-items: center; gap: 6px; }
.mac-ok { color: #28c840; flex: none; }
.mac-grow { flex: 1; }
.mac-spacer { flex: 1; min-height: 16px; }
.mac-footer { display: flex; align-items: center; gap: 8px; }
.mac-btn { font: inherit; height: 22px; padding: 0 12px; border-radius: 6px; border: 0; color: var(--mac-ink);
  background: light-dark(#fff, rgb(255 255 255 / .2));
  box-shadow: 0 0 0 .5px light-dark(rgb(0 0 0 / .14), rgb(255 255 255 / .06)), 0 .5px 1.5px rgb(0 0 0 / .18); }
.mac-default { background: var(--mac-accent); color: #fff; }
.mac-small { height: 18px; font-size: 11px; padding: 0 8px; }
.mac-help { width: 22px; height: 22px; border-radius: 50%; display: inline-grid; place-items: center; font-weight: 600;
  background: light-dark(#fff, rgb(255 255 255 / .2)); box-shadow: 0 0 0 .5px rgb(0 0 0 / .16), 0 .5px 1.5px rgb(0 0 0 / .18); }
.mac-seg { align-self: center; display: inline-flex; padding: 1px; border-radius: 7px;
  background: light-dark(rgb(0 0 0 / .07), rgb(255 255 255 / .09)); }
.mac-seg span { padding: 2px 11px; border-radius: 6px; }
.mac-seg .on { background: light-dark(#fff, rgb(255 255 255 / .22)); box-shadow: 0 .5px 1.5px rgb(0 0 0 / .2); }
/* Commentary: hatched edge band only, never behind text (owner, 2 Nov 2026). */
.mk-commentary { margin: 18px 0 0; max-width: 1150px; padding: 14px 20px; font: 14px/1.55 var(--bn-font-body);
  color: var(--bn-colour-text);
  border: 7px solid transparent; border-left: 3px solid #b0006b;
  background: linear-gradient(light-dark(#fff, #232428), light-dark(#fff, #232428)) padding-box,
              repeating-linear-gradient(135deg, light-dark(#f0d6e4, #4a2a3a) 0 5px, transparent 5px 10px) border-box; }
.mk-commentary .mk-label { font: 11px var(--bn-font-mono); color: #b0006b; text-transform: uppercase; letter-spacing: .06em; }
.mk-commentary p { margin: 8px 0; }
.mk-commentary table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 8px 0 4px; }
.mk-commentary td, .mk-commentary th { border-bottom: 1px solid var(--bn-colour-border); padding: 5px 6px;
  text-align: left; vertical-align: top; }
.mk-commentary th { font-weight: 600; }
.mk-commentary code { font-family: var(--bn-font-mono); font-size: 12px; }
.mk-commentary ol { padding-left: 1.3em; }
.mk-commentary li { margin: 6px 0; }
"""

SCRIPT = """\
document.querySelectorAll('[name="mk-palette"]').forEach(function (r) {
  r.addEventListener('change', function () { document.documentElement.dataset.colorTheme = r.value; });
});
document.querySelectorAll('[name="mk-scheme"]').forEach(function (r) {
  r.addEventListener('change', function () {
    if (r.value === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = r.value;
  });
});
"""


def commentary(body: str) -> str:
    return f'<section class="mk-commentary"><div class="mk-label">Commentary · not the product</div>{body}</section>'


def section(title: str, sub: str, frames: list[str], notes: str) -> str:
    return (
        f'<section class="mk-sec"><div class="mk-h">{e(title)}<small>{e(sub)}</small></div>'
        f'<div class="mk-row">{"".join(frames)}</div>{commentary(notes)}</section>'
    )


def flag_new(*keys: str) -> str:
    return "new key: " + ", ".join(keys) + " (shipped value + colon; owner-approval needed)"


EN = "en"
NK_EN = new_keys(EN)

ref = section(
    "Reference: the shipped Mac form",
    "owner-approved 9 Nov 2026",
    [
        frame("SHIPPED", "web · Send to Miro · Miro app tab · 460 px", [], web_miro_app(EN)),
        frame(
            "SHIPPED",
            "Mac · MiroSheet · token tab, connected · 460 pt (HTML stand-in)",
            [SAMPLE_FLAG],
            mac_miro_token(EN),
            "mac",
        ),
    ],
    "<p><strong>The pattern the four fixes copy.</strong> Web: <code>frontend/src/components/MiroExportPanel.tsx</code> "
    "651–727, drawn by <code>.bn-board-form</code> in <code>bristlenose/theme/atoms/modal.css</code> 370–402 "
    "(<code>max-content | minmax(0, 1fr)</code>, baseline alignment, labels right-aligned in "
    "<code>--bn-colour-muted</code>, a stand-alone checkbox in the control column behind an empty "
    "<code>&lt;span/&gt;</code>, <code>hr</code> spanning both columns). Mac: "
    "<code>desktop/Bristlenose/Bristlenose/MiroSheet.swift</code> 553–595 and 694–758 (SwiftUI <code>Grid</code>, "
    "<code>.gridColumnAlignment(.trailing)</code>, labels in the body's weight and primary colour, the colon in the "
    "string). Web labels stay muted by owner ruling; Mac labels are primary.</p>"
    "<p>Both web frames on this page are the theme's own CSS (tokens, both palettes, all of "
    "<code>atoms/modal.css</code>, <code>.bn-locale-select</code> from <code>organisms/settings.css</code>, and "
    "the page-level <code>h2</code>/<code>hr</code>/<code>body</code> rules from <code>templates/report.css</code>), "
    "inlined by <code>docs/mockups/form-layout-four-fixes.gen.py</code>. <strong>The Mac frames are an HTML stand-in</strong> "
    "(system font at 13 pt, hand-drawn controls): read them for structure and colour, not for exact metrics. "
    "SwiftUI's own measurements beat this drawing; a Release build is the check.</p>",
)

s1 = section(
    "1 · Send to Miro, Developer access token tab (web)",
    "MiroExportPanel.tsx · configure step",
    [
        frame("BEFORE", "today · labels stacked above fields", [SAMPLE_FLAG], web_miro_token_before(EN)),
        frame(
            "AFTER",
            "the Mac form, as the Miro app tab",
            [flag_new("miro.boardNameFormLabel", "miro.colourByFormLabel"), SAMPLE_FLAG],
            web_miro_token_after(EN),
        ),
    ],
    "<table><tr><th>File, lines</th><td><code>frontend/src/components/MiroExportPanel.tsx</code> 794–899 "
    "(<code>view === \"configure\"</code>); the change is 808–856 (the board-name label to the shape fieldset). "
    "No CSS change: it reuses <code>.bn-board-form</code>, <code>.bn-board-form-label</code>, "
    "<code>.bn-board-form-radios</code>.</td></tr>"
    "<tr><th>What changes</th><td>The two caption-size hint labels above their fields become right-aligned colon "
    "labels (<code>&lt;label class=\"bn-board-form-label\" htmlFor&gt;</code>: they own a field, so a "
    "<code>label</code>, not the app tab's <code>span</code>). The long-quotes checkbox moves to the control "
    "column. The <code>fieldset</code>/<code>legend</code> becomes the app tab's <code>role=\"radiogroup\"</code> "
    "labelled by the shipped <em>Sticky shape:</em>. The Connected line, the account line, the notice and the "
    "action row do not move. The two tabs of one dialog now share one layout.</td></tr>"
    "<tr><th>Keys</th><td>New: <code>miro.boardNameFormLabel</code>, <code>miro.colourByFormLabel</code>. Reused: "
    "<code>miro.stickyShapeLabel</code> (shipped in all 21). Left with no web caller: <code>miro.colourByLabel</code> "
    "(and <code>miro.boardNameLabel</code> once surface 2 lands).</td></tr>"
    "<tr><th>Control mismatch</th><td>The web has <em>Colour stickies by</em> with a drop-down (<em>Single colour "
    "(yellow)</em> | <em>Sentiment</em>, default single colour); the Mac has <em>Sticky colours:</em> with a "
    "<em>Sentiment</em> checkbox, default off. The AFTER keeps the web's drop-down: no control was changed. "
    "This is a question for the owner (below).</td></tr>"
    "<tr><th>Risk</th><td>Low. The label column takes its widest label, so the longest locale sets it: the German "
    "row below measures it. The checkbox label wraps (allowed) and never truncates. The Screens board's "
    "<em>Send to Miro board</em> is the same <code>configure</code> block with no tabs, so it gets the form too. "
    "The clip-link rows are parked (<code>featureFlags.boardClipLinks: false</code>) and not drawn; when they come "
    "back they take an empty label cell, as on the Mac. No vitest queries these two labels by text "
    "(<code>MiroExportPanel.*.test.tsx</code>, grepped).</td></tr></table>",
)

s2 = section(
    "2 · Send to FigJam (web)",
    "FigJamExportPanel.tsx",
    [
        frame("BEFORE", "today · labels stacked above fields", [PROJECT_FLAG], web_figjam_before(EN)),
        frame(
            "AFTER",
            "the Mac form, ported from FigJamSheet",
            [flag_new("miro.boardNameFormLabel"), PROJECT_FLAG],
            web_figjam_after(EN),
        ),
    ],
    "<table><tr><th>File, lines</th><td><code>frontend/src/components/FigJamExportPanel.tsx</code> 127–211 "
    "(<code>view !== \"ready\"</code>); the change is 130–166.</td></tr>"
    "<tr><th>What changes</th><td>The same move as surface 1: <em>Board name:</em> on its colon beside the field, the "
    "checkbox in the control column, the radios on the shipped <em>Sticky shape:</em> label. The intro, the notice "
    "and Cancel / <em>Download board file</em> do not move. The Mac sheet already has this form, so this is the "
    "port.</td></tr>"
    "<tr><th>Keys</th><td>Reuses the new <code>miro.boardNameFormLabel</code> from surface 1 and the shipped "
    "<code>miro.stickyShapeLabel</code>. No key of its own.</td></tr>"
    "<tr><th>Risk</th><td>Low. <code>frontend/src/components/__tests__/FigJamExportPanel.test.tsx</code> lines 61 and 68 "
    "find the field by <code>getByLabelText(i18n.t(\"miro.boardNameLabel\"))</code>; they move to the new key. "
    "Control order is kept as it is today (checkbox, then shape; Square first), which differs from the Mac sheet "
    "(shape, then checkbox). A question below.</td></tr></table>",
)

s3 = section(
    "3 · Send to FigJam (Mac)",
    "FigJamSheet.swift · configure",
    [
        frame("BEFORE", "today · secondary (grey) labels", [PROJECT_FLAG], mac_figjam(EN, True, False), "mac"),
        frame("AFTER", "variant A · primary labels, as MiroSheet", [PROJECT_FLAG], mac_figjam(EN, False, False), "mac"),
        frame(
            "VARIANT",
            "variant B · primary labels + Divider",
            [PROJECT_FLAG, "the divider's place is a proposal: between the name and the sticky options"],
            mac_figjam(EN, False, True),
            "mac",
        ),
    ],
    "<table><tr><th>File, lines</th><td><code>desktop/Bristlenose/Bristlenose/FigJamSheet.swift</code> 252–287 "
    "(the <code>Grid</code>); the change is lines 255 and 261.</td></tr>"
    "<tr><th>What changes</th><td>A: remove <code>.foregroundStyle(.secondary)</code> from <em>Board name:</em> and "
    "<em>Sticky shape:</em>, so they are set like <code>MiroSheet.formLabel</code> (body weight, primary colour). "
    "B adds a bare <code>Divider()</code> between the <em>Board name</em> row and the <em>Sticky shape</em> row: "
    "outside a <code>GridRow</code> a view spans every column, as in <code>MiroSheet.appRoute</code>. It separates "
    "what the board is called from how its stickies are drawn. The token tab of the Miro sheet, the nearest sibling "
    "with the same controls, has no divider.</td></tr>"
    "<tr><th>Keys</th><td>None. The labels already carry their colons (<code>desktop.miro.boardNameLabel</code>, "
    "<code>desktop.figjam.stickyShapeLabel</code>).</td></tr>"
    "<tr><th>Risk</th><td>None for A (two modifiers removed). If B is chosen, the web FigJam dialog takes the same "
    "<code>hr</code>, for parity. Found while drawing: the long-quotes <code>Toggle</code> here has no "
    "<code>.fixedSize(horizontal: false, vertical: true)</code> on its text, which <code>MiroSheet.swift</code> adds "
    "because the grid column would cut it to one line (“Break long quotes into multi…”). In Catalan "
    "(<em>Divideix les cites llargues en diverses notes adhesives</em>) that is the labels-never-truncate rule. "
    "It is a one-line guard, outside this fix's scope: a question below.</td></tr></table>",
)

s4 = section(
    "4 · Export report (web)",
    "ExportDialog.tsx",
    [
        frame("BEFORE", "today · Language left, drop-down pushed right · 420 px", [], web_export_before(EN)),
        frame(
            "AFTER",
            "Language: on its colon, Anonymise in the control column",
            [flag_new("export.languageLabel")],
            web_export_after(EN),
        ),
    ],
    "<table><tr><th>File, lines</th><td><code>frontend/src/components/ExportDialog.tsx</code> 88–115 (the language "
    "<code>label</code> and the anonymise checkbox); <code>bristlenose/theme/atoms/modal.css</code> 234–249 "
    "(<code>.bn-export-locale</code>).</td></tr>"
    "<tr><th>What changes</th><td>The <code>label.bn-export-locale</code> flex row (<code>justify-content: "
    "space-between</code>) becomes a <code>.bn-board-form</code> grid: <em>Language:</em> right-aligned, the "
    "drop-down beside it, then an empty cell and the Anonymise checkbox with its hint, in the control column. "
    "<code>.bn-export-locale</code> then has no caller and goes. Its comment records the opposite intent (“the "
    "governing control sits trailing on its own line”); this reverses it on the owner's 9 Nov form ruling.</td></tr>"
    "<tr><th>Keys</th><td>New: <code>export.languageLabel</code> (<em>Language:</em>). "
    "<code>settings:language.legend</code> stays: the Settings dialog's legend and the Mac Settings picker read it.</td></tr>"
    "<tr><th>Risk</th><td>Low. Tests reach the drop-down by <code>data-testid=\"bn-export-locale-select\"</code>, "
    "which stays. The hint now wraps in a narrower column (the label column is gone from it). The class name "
    "<code>.bn-board-form</code> would then draw a dialog that is not a board: a question below. On the Mac this "
    "dialog does not exist; the save panel's accessory (<code>ExportAccessoryView.swift</code>) has only the "
    "Anonymise toggle.</td></tr></table>",
)

DE = "de"
NK_DE = new_keys(DE)
de_flag = "de strings: shipped de values; the new keys composed the same way, for measurement only"
s5 = section(
    "German: the widest label column",
    "the AFTER frames in de, at the dialogs' real widths",
    [
        frame("AFTER", "1 · Miro token tab · de", [de_flag, SAMPLE_FLAG], web_miro_token_after(DE)),
        frame("AFTER", "2 · FigJam web · de", [de_flag, PROJECT_FLAG], web_figjam_after(DE)),
        frame("AFTER", "3 · FigJam Mac, variant A · de", [PROJECT_FLAG], mac_figjam(DE, False, False), "mac"),
        frame("AFTER", "4 · Export report · de", [de_flag], web_export_after(DE)),
    ],
    "<p><strong>Why German.</strong> A <code>max-content</code> label column is as wide as its longest label, so the "
    "longest locale decides how much room the controls get. German's <em>"
    + e(NK_DE["miro.colourByFormLabel"])
    + "</em> is the widest label on this page. Everything still fits: the checkbox label wraps, and no label or "
    "control is cut. These frames are drawn from the de locale files (<em>"
    + e(NK_DE["miro.boardNameFormLabel"])
    + "</em> is the Mac's shipped string; <em>"
    + e(NK_DE["miro.colourByFormLabel"])
    + "</em> and <em>"
    + e(NK_DE["export.languageLabel"])
    + "</em> are shipped values with a colon added). The e2e label walk "
    "(<code>e2e/tests/button-labels.spec.ts</code>) opens none of these four dialogs today, so nothing checks this "
    "automatically.</p>",
)

STRING_PLAN = (
    "<p><strong>String plan.</strong> Three new keys in <code>bristlenose/locales/&lt;lang&gt;/common.json</code>, "
    "each in all 21 full locales (<code>zh-Hant-HK</code> takes no override): "
    "<strong>63 locale entries</strong>. No copy is invented: each is a shipped value with a colon added, or a "
    "verbatim lift of an already-translated Mac label.</p>"
    "<table><tr><th>New key</th><th>English</th><th>Source of each locale's value</th><th>Used by</th></tr>"
    f"<tr><td><code>miro.boardNameFormLabel</code></td><td>{e(NK_EN['miro.boardNameFormLabel'])}</td>"
    "<td>Verbatim lift of <code>desktop.miro.boardNameLabel</code>, already translated in all 21 (the precedent is "
    "<code>miro.persistWarningKeychain</code>). Needed because the browser does not load the <code>desktop</code> "
    "namespace (<code>frontend/src/i18n/index.ts</code>).</td><td>1, 2</td></tr>"
    f"<tr><td><code>miro.colourByFormLabel</code></td><td>{e(NK_EN['miro.colourByFormLabel'])}</td>"
    "<td><code>miro.colourByLabel</code> plus the locale's colon. Translator check: in a few locales the phrase "
    "ends in a preposition or postposition that wants its noun after it (fi <em>Väritä tarrat perusteella</em>, "
    "de <em>…einfärben nach</em>), which reads less well before a colon than before a drop-down.</td><td>1</td></tr>"
    f"<tr><td><code>export.languageLabel</code></td><td>{e(NK_EN['export.languageLabel'])}</td>"
    "<td><code>settings:language.legend</code> plus the locale's colon.</td><td>4</td></tr></table>"
    "<p><strong>The locale's colon</strong> follows the existing colon labels: French puts a space before it "
    "(<em>Forme des notes :</em>), Traditional Chinese uses the full-width <em>：</em>. Two inconsistencies "
    "already shipped: the French space is a plain space, so the colon can wrap onto its own line (a no-break space "
    "would stop that), and Japanese mixes half-width (<code>miro.stickyShapeLabel</code>) with full-width "
    "(<code>miro.appOnce</code>) colons.</p>"
    "<p><strong>Reused, unchanged:</strong> <code>miro.stickyShapeLabel</code> (web 1, 2), and on the Mac "
    "<code>desktop.miro.boardNameLabel</code> and <code>desktop.figjam.stickyShapeLabel</code> (3). "
    "<strong>No web caller after the change:</strong> <code>miro.boardNameLabel</code> and "
    "<code>miro.colourByLabel</code> (2 × 21 entries to delete, or reword in place instead of adding the two new "
    "Miro keys; see question 4). <code>miro.stickyShape</code> stays: the Mac pickers' accessibility label reads it.</p>"
)

QUESTIONS = (
    "<p><strong>Questions for the owner</strong></p><ol>"
    "<li><strong>The Miro colour control.</strong> Web: <em>Colour stickies by:</em> + a drop-down (<em>Single colour "
    "(yellow)</em> / <em>Sentiment</em>). Mac: <em>Sticky colours:</em> + a <em>Sentiment</em> checkbox. The AFTER "
    "keeps the web drop-down. Should one surface follow the other (a checkbox on the web would retire "
    "<code>miro.colourByNone</code> and need no <code>miro.colourByFormLabel</code>), or do they stay different?</li>"
    "<li><strong>The FigJam Mac divider.</strong> Variant A (no rule, like the Miro token tab) or B (a rule between "
    "the name and the sticky options)? If B, the web FigJam dialog takes the same <code>hr</code>.</li>"
    "<li><strong>Control order in FigJam.</strong> The Mac sheet has shape then long-quotes; the web has long-quotes "
    "then shape (and both Miro surfaces do the same as the web). Should the Mac sheet follow? Both FigJam surfaces "
    "list Square first; both Miro surfaces list Rectangle first, which follows each tool's default.</li>"
    "<li><strong>New keys or rewording in place.</strong> After surfaces 1 and 2, <code>miro.boardNameLabel</code> and "
    "<code>miro.colourByLabel</code> have no caller. Adding the colon to their values (21-file rewords, pins updated) "
    "would leave no orphans and need one new key, not three. The precedent (<code>miro.stickyShapeLabel</code>) "
    "added a key because the colon-less one still had a caller.</li>"
    "<li><strong>The class name.</strong> Surface 4 puts <code>.bn-board-form</code> on a dialog that is not about "
    "a board. Rename it to <code>.bn-form</code> (modal.css and three components), or keep the name?</li>"
    "<li><strong>FigJam Mac wrap guard</strong> (found while drawing). Add MiroSheet's "
    "<code>.fixedSize(horizontal: false, vertical: true)</code> to the long-quotes <code>Toggle</code> text in "
    "FigJamSheet.swift, in the same change?</li>"
    "<li><strong>The e2e label walk.</strong> Add the Miro, FigJam and Export dialogs to "
    "<code>e2e/tests/button-labels.spec.ts</code> when this lands, so a long locale is checked by a test rather "
    "than by this page?</li>"
    "</ol>"
)

final = (
    '<section class="mk-sec"><div class="mk-h">String plan and questions</div>'
    + commentary(STRING_PLAN + QUESTIONS)
    + "</section>"
)

BAR = (
    '<div class="mk-bar">'
    '<fieldset><legend>palette</legend>'
    '<label><input type="radio" name="mk-palette" value="default" checked> default</label>'
    '<label><input type="radio" name="mk-palette" value="edo"> edo</label></fieldset>'
    '<fieldset><legend>scheme</legend>'
    '<label><input type="radio" name="mk-scheme" value="auto" checked> auto</label>'
    '<label><input type="radio" name="mk-scheme" value="light"> light</label>'
    '<label><input type="radio" name="mk-scheme" value="dark"> dark</label></fieldset>'
    "</div>"
)

KEY = (
    '<p class="mk-key"><b>artefact</b> = the framed dialogs: web frames use the shipped theme CSS, inlined from the '
    "tree; Mac frames are an HTML stand-in for SwiftUI. Before / after / variant is marked in each frame's chrome "
    "bar, never inside the UI. Every string inside a frame is a shipped locale value; a "
    '<span style="color:#b0006b">pink line</span> in the chrome bar names any new key or sample data. '
    "<b>commentary</b> = the blocks with the hatched edge.</p>"
)

PAGE = f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Form layout: four fixes</title>
<!-- Generated by docs/mockups/form-layout-four-fixes.gen.py — edit that, not this. -->
<style>
{SHIPPED_CSS}
{CHROME_CSS}
</style>
</head>
<body>
{BAR}
<div class="mk-title">The Mac form layout, applied to four more dialogs</div>
{KEY}
{ref}
{s1}
{s2}
{s3}
{s4}
{s5}
{final}
<script>
{SCRIPT}
</script>
</body>
</html>
"""

OUT.write_text(PAGE, encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)} ({len(PAGE):,} bytes)")
