#!/usr/bin/env python3
"""Generates docs/mockups/form-layout-v2.html: the Send to Miro and Send to FigJam forms, before
and after the 19 Nov 2026 triage (Gruber + HIG review items 1-8, 11, 12; Q1 = radios), on top of
the four form fixes in form-layout-four-fixes.html.

Mac frames are REAL AppKit renders, made by form-layout-v2/render.sh from SwiftUI that copies
each sheet's shipped modifier chain (BEFORE) or the proposal (AFTER), shown at 1 pt = 1 CSS px.
Web frames are the shipped theme CSS, inlined block by block as in the first page; the AFTER web
frames add only the CSS the proposal changes, in a block headed PROPOSED.

Run:  docs/mockups/form-layout-v2/render.sh   (only when the Mac sheets or strings change)
      .venv/bin/python docs/mockups/form-layout-v2.gen.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "bristlenose" / "theme"
LOCALES = ROOT / "bristlenose" / "locales"
OUT = ROOT / "docs" / "mockups" / "form-layout-v2.html"
RENDERS = ROOT / "docs" / "mockups" / "form-layout-v2"


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


BUNDLES = {"en": load("en"), "de": load("de"), "ca": load("ca")}


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
        # Reworded in place to the Mac's translated value (Q4, reviewers' lean).
        "miro.boardNameLabel": t(lang, "desktop:miro.boardNameLabel"),
        # New: a verbatim lift of the Mac's translated label (Q1 radios want a noun, not "by").
        "miro.stickyColoursLabel": t(lang, "desktop:miro.stickyColoursLabel"),
        "export.languageLabel": t(lang, "settings:language.legend") + ":",
    }


# English copy the proposal rewrites (item 5: no em dash in UI copy, no "we"). Owner-to-approve.
REWORDS = {
    "miro.uploadNotice": "Uploads all quotes in this project to Miro. Hidden quotes are excluded.",
    "miro.screensUploadNotice": "Uploads one screenshot of each screen in this project to Miro, with "
    "everything participants said about it. Hidden quotes are excluded.",
    "miro.connectIntro": "Push your quotes onto a new Miro board as sticky notes, grouped by section and "
    "theme. Connect once. Bristlenose never changes your existing boards.",
    "miro.connectError": "Could not connect. Check the token and try again.",
    "miro.errNoQuotesSelected": "No quotes match the current selection, so there is nothing to send.",
    "miro.boardReady_one": "Board ready. {{count}} quote sticky placed.",
    "miro.boardReady_other": "Board ready. {{count}} quote stickies placed.",
    "miro.persistWarningKeychain": "Connected, but couldn’t save the token to your Keychain. You may need "
    "to reconnect after restarting.",
    "miro.persistWarningKeyring": "Connected, but couldn’t save the token to your keyring (GNOME Keyring or "
    "KDE Wallet). You may need to reconnect after restarting.",
    "miro.persistWarningFile": "Connected, but couldn’t save the token to the Bristlenose settings file. You "
    "may need to reconnect after restarting.",
    "desktop:miro.connectPersistWarning": "Connected, but couldn’t save the token to your Keychain. You may "
    "need to reconnect after restarting.",
}
# Mac-only overrides for item 2 (one casing for Mac buttons). The segment pair is inference.
MAC_CASING = {
    "desktop.miro.copyBoard": ("miro.copyBoard", "Copy Board Data"),
    "desktop.miro.createBoard": ("miro.createBoard", "Create Board"),
    "desktop.miro.tabApp": ("miro.tabApp", "Miro App"),
    "desktop.miro.tabToken": ("miro.tabToken", "Developer Access Token"),
}


def after_t(lang: str, key: str) -> str:
    return REWORDS[key] if lang == "en" and key in REWORDS else t(lang, key)


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


def web_stage(modal_cls: str, inner: str, after: bool = False) -> str:
    """`after` puts the frame under the PROPOSED CSS block (scoped to .mk-proposed)."""
    cls = "mk-stage mk-proposed" if after else "mk-stage"
    return f'<div class="{cls}"><div class="bn-modal {modal_cls}" role="dialog">{inner}</div></div>'


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


def miro_notice_after(lang: str) -> str:
    template = t(lang, "miro.boardDestination")
    head, _, tail = template.partition("{{team}}")
    return f"{e(head)}<strong>{e(SAMPLE_TEAM)}</strong>{e(tail)} {e(after_t(lang, 'miro.uploadNotice'))}"


def colour_radios(lang: str, name: str) -> str:
    return (
        f'<label class="bn-export-checkbox"><input type="radio" name="{name}" checked>'
        f'<span>{e(t(lang, "miro.colourByNone"))}</span></label>'
        f'<label class="bn-export-checkbox"><input type="radio" name="{name}">'
        f'<span>{e(t(lang, "miro.colourBySentiment"))}</span></label>'
    )


# ── Web: the shipped Miro app tab (MiroExportPanel.tsx, the app tabpanel) ──────────────────────
def web_miro_app(lang: str, after: bool = False) -> str:
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
    return web_stage("bn-board-modal", inner, after)


def miro_token_head(lang: str) -> str:
    return (
        f'<h2>{e(t(lang, "miro.quotesTitle"))}</h2>{seg(lang, "token")}'
        '<div role="tabpanel">'
        f'<p class="bn-modal-subtitle">{e(t(lang, "miro.connected"))} · '
        f'<button class="bn-linkish">{e(t(lang, "miro.disconnect"))}</button></p>'
        f'<p class="bn-export-hint">{e(SAMPLE_ACCOUNT)}</p>'
    )


def miro_token_tail(lang: str, after: bool) -> str:
    notice = miro_notice_after(lang) if after else miro_notice(lang)
    return (
        f'<p class="bn-export-hint" style="margin-top:10px">{notice}</p>'
        f'<div class="bn-modal-actions">{help_btn(lang)}'
        f'<button class="bn-btn bn-btn-primary">{e(t(lang, "miro.createBoard"))}</button></div></div>'
    )


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
        + miro_token_tail(lang, False)
    )
    return web_stage("bn-board-modal", inner)


def web_miro_token_after(lang: str) -> str:
    nk = new_keys(lang)
    name, col, shape = uid("mt-name"), uid("mt-col"), uid("mt-shape")
    inner = (
        miro_token_head(lang)
        + '<div class="bn-board-form">'
        f'<label class="bn-board-form-label" for="{name}">{e(nk["miro.boardNameLabel"])}</label>'
        f'<input id="{name}" type="text" value="{e(SAMPLE_PROJECT)}" '
        f'placeholder="{e(t(lang, "miro.boardNamePlaceholder"))}" style="{TEXT_INPUT_STYLE}">'
        f'<span class="bn-board-form-label" id="{col}-l">{e(nk["miro.stickyColoursLabel"])}</span>'
        f'<div class="bn-board-form-radios" role="radiogroup" aria-labelledby="{col}-l">'
        f"{colour_radios(lang, col)}</div>"
        f'<span class="bn-board-form-label" id="{shape}-l">{e(t(lang, "miro.stickyShapeLabel"))}</span>'
        f'<div class="bn-board-form-radios" role="radiogroup" aria-labelledby="{shape}-l">'
        f'{radios(lang, shape, ("rectangle", "square"), "rectangle")}</div>'
        f"<span></span>{split_checkbox(lang)}"
        "</div>"
        + miro_token_tail(lang, True)
    )
    return web_stage("bn-board-modal", inner, True)


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
        f'<label class="bn-board-form-label" for="{name}">{e(nk["miro.boardNameLabel"])}</label>'
        f'<input id="{name}" type="text" value="{e(SAMPLE_PROJECT)}" style="{TEXT_INPUT_STYLE}">'
        f'<span class="bn-board-form-label" id="{shape}-l">{e(t(lang, "miro.stickyShapeLabel"))}</span>'
        f'<div class="bn-board-form-radios" role="radiogroup" aria-labelledby="{shape}-l">'
        f'{radios(lang, shape, ("square", "rectangle"), "square")}</div>'
        f"<span></span>{split_checkbox(lang)}"
        "</div>"
        + figjam_actions(lang)
    )
    return web_stage("bn-board-modal", inner, True)


# Export report, web (unchanged from the first page except the row gap)
LOCALE_OPTION = {"en": "English", "de": "Deutsch"}


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
    return web_stage("bn-export-modal", inner, True)


# ── Mac: real renders ──────────────────────────────────────────────────────────────────────────
def manifest() -> tuple[str, dict[str, tuple[int, int]]]:
    lines = (RENDERS / "manifest.txt").read_text(encoding="utf-8").splitlines()
    sizes: dict[str, tuple[int, int]] = {}
    for ln in lines[1:]:
        name, wh, _ = ln.split(" ")
        w, h = wh.split("x")
        sizes[name] = (int(w), int(h))
    return lines[0], sizes


RENDERED_ON, SIZES = manifest()


def mac_img(stem: str, lang: str = "en") -> str:
    """A render at 1 pt = 1 CSS px; its dark twin, when one was rendered, swaps with the scheme."""
    light = f"{stem}-{lang}-light"
    dark = f"{stem}-{lang}-dark"
    w, h = SIZES[light]
    alt = f"{stem} ({lang})"
    if dark in SIZES:
        imgs = (
            f'<img class="mk-l" src="form-layout-v2/{light}.png" width="{w}" height="{h}" alt="{e(alt)}">'
            f'<img class="mk-d" src="form-layout-v2/{dark}.png" width="{w}" height="{h}" alt="{e(alt)}, dark">'
        )
    else:
        imgs = f'<img src="form-layout-v2/{light}.png" width="{w}" height="{h}" alt="{e(alt)}">'
    return f'<div class="mac-stage"><div class="mac-sheet">{imgs}</div></div>'


def size_of(stem: str, lang: str = "en") -> str:
    w, h = SIZES[f"{stem}-{lang}-light"]
    return f"{w} × {h} pt"


# ── Page ───────────────────────────────────────────────────────────────────────────────────────
PROPOSED_CSS = """\
/* ════ PROPOSED (item 7): bristlenose/theme/atoms/modal.css .bn-board-form, row-gap ════
   was var(--bn-space-sm) = 0.35rem (about 6 px) between rows, so between the stacked bezelled
   Download and Copy buttons; the HIG asks for about 12 pt round a bezelled control. */
.mk-proposed .bn-board-form { row-gap: var(--bn-space-md); }
"""

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
.mk-bar a { color: inherit; }
.mk-title { font: 600 20px/1.3 var(--bn-font-body); margin: 26px 0 4px; }
.mk-key { font: 12px/1.6 var(--bn-font-mono); color: var(--bn-colour-muted); margin: 0 0 8px; max-width: 1150px; }
.mk-key b { color: var(--bn-colour-text); font-weight: 600; }
.mk-part { font: 600 13px var(--bn-font-mono); letter-spacing: .08em; text-transform: uppercase;
  color: var(--bn-colour-muted); margin: 48px 0 0; padding-top: 10px; border-top: 1px solid var(--bn-colour-border); }
.mk-sec { margin: 30px 0 0; }
.mk-h { font: 600 16px/1.3 var(--bn-font-body); margin: 0 0 12px; }
.mk-h small { font: 12px var(--bn-font-mono); color: var(--bn-colour-muted); font-weight: 400; margin-left: 8px; }
.mk-row { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
.mk-frame { flex: none; margin: 0; width: 540px; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgb(0 0 0 / .18); }
.mk-chrome { display: block; font: 11px/1.45 var(--bn-font-mono); padding: 8px 12px;
  background: light-dark(#e2e4e8, #2a2c30); color: light-dark(#444, #b8b8b8); }
.mk-state { font-weight: 700; letter-spacing: .05em; padding: 1px 5px; border-radius: 3px; color: #fff; }
.mk-before { background: #6b7280; } .mk-after { background: #0a7a3d; } .mk-shipped { background: #2563eb; }
.mk-variant { background: #9a5b00; } .mk-rejected { background: #b42318; }
.mk-flags { display: block; color: light-dark(#8a0050, #f08ac0); }
.mk-flags span { display: block; }
.mk-stage { padding: 24px; background: var(--bn-overlay-scrim); color: var(--bn-colour-text); }
.mk-stage .bn-modal { position: static; transform: none; opacity: 1; margin: 0 auto; }
/* Mac: real AppKit renders at 1 pt = 1 CSS px. The sheet's own corner and shadow are not drawn. */
.mac-stage { padding: 28px 40px; background: light-dark(#c9ccd2, #121214); }
.mac-sheet { width: max-content; margin: 0 auto; line-height: 0;
  box-shadow: 0 0 0 .5px light-dark(rgb(0 0 0 / .25), rgb(255 255 255 / .16)), 0 14px 44px rgb(0 0 0 / .32); }
.mac-sheet img { display: block; }
.mk-d { display: none !important; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .mk-l { display: none !important; }
  :root:not([data-theme="light"]) .mk-d { display: block !important; }
}
:root[data-theme="dark"] .mk-l { display: none !important; }
:root[data-theme="dark"] .mk-d { display: block !important; }
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
.mk-commentary ol, .mk-commentary ul { padding-left: 1.3em; }
.mk-commentary li { margin: 6px 0; }
.mk-commentary del { color: var(--bn-colour-muted); }
.mk-commentary ins { text-decoration: none; background: light-dark(#e3f5ea, #163322); }
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


def part(title: str) -> str:
    return f'<div class="mk-part">{e(title)}</div>'


def owner_copy(*keys: str) -> str:
    return "owner-written copy: " + ", ".join(keys) + " (proposal; not shipped)"


EN, DE = "en", "de"
DE_DRAFT = "de: shipped strings, except the reworded notice and button casing, drafted only to measure length"
SAMPLE = f"sample data: “{SAMPLE_PROJECT}”, “{SAMPLE_ACCOUNT}”"

# ── Mac sections ───────────────────────────────────────────────────────────────────────────────
m1 = section(
    "Send to Miro · Miro app tab",
    "MiroSheet.swift · appRoute",
    [
        frame("BEFORE", f"Mac · shipped · {size_of('miro-app-before')}", [], mac_img("miro-app-before"), "mac"),
        frame(
            "AFTER",
            f"Mac · one button casing · {size_of('miro-app-after')}",
            ["new Mac keys: desktop.miro.copyBoard, desktop.miro.tabApp, desktop.miro.tabToken"],
            mac_img("miro-app-after"),
            "mac",
        ),
        frame("AFTER", f"Mac · de · {size_of('miro-app-after', 'de')}", [DE_DRAFT], mac_img("miro-app-after", "de"), "mac"),
    ],
    "<table>"
    "<tr><th>Item 2</th><td><strong>Copy board data</strong> stacked under <strong>Save Board File…</strong> mixed "
    "sentence and title case in one pair. AFTER: <em>Copy Board Data</em>, through a <code>desktop.miro.copyBoard</code> "
    "override (the browser keeps <code>miro.copyBoard</code> in sentence case, as every web button is). "
    "The writing page's rule is one style per element type.</td></tr>"
    "<tr><th>Segments</th><td>Title case too (<em>Miro App · Developer Access Token</em>). This one is Gruber's "
    "inference from Pages' Export sheet: the local HIG copy has no segmented-control page. Easy to leave out.</td></tr>"
    "<tr><th>Found by rendering</th><td>This tab is <strong>418 pt</strong> tall (434 pt in German), the token tab "
    "400 pt, so the sheet changes height when you switch tabs, although the code comment says it keeps one size. "
    "Not in the triaged items; noted, not acted on.</td></tr>"
    "</table>",
)

m2 = section(
    "Send to Miro · Developer access token tab · configure",
    "MiroSheet.swift · configure",
    [
        frame("BEFORE", f"Mac · shipped · {size_of('miro-configure-before')}", [SAMPLE], mac_img("miro-configure-before"), "mac"),
        frame(
            "AFTER",
            f"Mac · colours as radios, stacked · {size_of('miro-configure-after')}",
            [SAMPLE, owner_copy("miro.uploadNotice"), "new Mac key: desktop.miro.createBoard"],
            mac_img("miro-configure-after"),
            "mac",
        ),
        frame(
            "AFTER",
            f"Mac · de · {size_of('miro-configure-after', 'de')}",
            [SAMPLE, DE_DRAFT],
            mac_img("miro-configure-after", "de"),
            "mac",
        ),
    ],
    "<table>"
    "<tr><th>Q1 radios</th><td><em>Sticky colours:</em> becomes two named radios, <em>Single colour (yellow)</em> "
    "and <em>Sentiment</em>, both shipped strings (<code>miro.colourByNone</code>, "
    "<code>miro.colourBySentiment</code>). The checkbox left the off state unnamed.</td></tr>"
    "<tr><th>Why stacked</th><td>Side by side, the first radio <strong>truncates in English</strong> "
    "(“Single colour…”) as well as German: see the two evidence frames below. Stacking is the radio group's own "
    "default layout, so it is the stock primitive, not a fix. <em>Sticky shape</em> stays side by side because "
    "its two words fit in every locale; the frame below it shows both rows stacked, if you'd rather they match.</td></tr>"
    "<tr><th>Item 12</th><td>The long-quotes checkbox moves under <em>Sticky shape</em>, so it no longer reads as a "
    "colour option. Same order on all four surfaces: name, colours, shape, checkbox.</td></tr>"
    "<tr><th>Item 2</th><td><em>Create board</em> → <em>Create Board</em> (a <code>desktop.miro.createBoard</code> "
    "override), beside <em>Cancel</em>.</td></tr>"
    "<tr><th>Item 5</th><td>The notice loses its em dash: “…to Miro. Hidden quotes are excluded.”</td></tr>"
    "<tr><th>Item 3</th><td>Not visible: the board-name field is announced as <em>Board name</em>, not by its "
    "placeholder, and <em>Sentiment</em> is now read inside the labelled <em>Sticky colours</em> group.</td></tr>"
    "<tr><th>Height</th><td>400 → 416 pt (438 with both rows stacked). The sheet's minimum is 400, so it grows; "
    "nothing is cut.</td></tr>"
    "</table>",
)

m2b = section(
    "Evidence · the colour radios laid out three ways",
    "rendered, not argued",
    [
        frame("REJECTED", f"side by side · en · {size_of('miro-configure-sidebyside')}", ["truncates: “Single colour…”"],
              mac_img("miro-configure-sidebyside"), "mac"),
        frame("REJECTED", "side by side · de", ["truncates: “Eine Farbe (g…”"],
              mac_img("miro-configure-sidebyside", "de"), "mac"),
        frame("VARIANT", f"both rows stacked · en · {size_of('miro-configure-bothstacked')}", [],
              mac_img("miro-configure-bothstacked"), "mac"),
    ],
    "<p>The horizontal radio group does not wrap: it ellipsises its label, which breaks the "
    "labels-never-truncate rule (<code>docs/design-control-labels.md</code>). Neither reviewer could see this "
    "from the code. The proposal is the AFTER above (colours stacked, shape side by side); the VARIANT stacks "
    "both, 22 pt taller, for a uniform column. Your choice.</p>",
)

m3 = section(
    "Send to Miro · Developer access token tab · connect",
    "MiroSheet.swift · connect",
    [
        frame("BEFORE", "Mac · shipped", [], mac_img("miro-connect-before"), "mac"),
        frame("AFTER", "Mac · no em dash, no “we”", [owner_copy("miro.connectIntro")], mac_img("miro-connect-after"), "mac"),
    ],
    "<p><strong>Item 5.</strong> “Connect once — we never touch your existing boards.” becomes “Connect once. "
    "Bristlenose never changes your existing boards.” The HIG's writing page asks apps to avoid “we”, since it is "
    "unclear who that is. The same string is the web connect step's subtitle.</p>",
)

m4 = section(
    "Send to Miro · done",
    "MiroSheet.swift · done",
    [
        frame("BEFORE", "Mac · shipped", ["sample data: 29 stickies"], mac_img("miro-done-before"), "mac"),
        frame("AFTER", "Mac · no em dash", ["sample data: 29 stickies", owner_copy("miro.boardReady_*")],
              mac_img("miro-done-after"), "mac"),
    ],
    "<p><strong>Item 5.</strong> “Board ready — 29 quote stickies placed.” becomes “Board ready. 29 quote stickies "
    "placed.” Same string on the web's done step.</p>",
)

m5 = section(
    "Send to FigJam",
    "FigJamSheet.swift · configure",
    [
        frame("BEFORE", f"Mac · shipped · grey labels · {size_of('figjam-before')}", [PROJECT_FLAG], mac_img("figjam-before"), "mac"),
        frame("AFTER", f"Mac · primary labels · {size_of('figjam-after')}", [PROJECT_FLAG], mac_img("figjam-after"), "mac"),
    ],
    "<table>"
    "<tr><th>Labels</th><td>The four-fix proposal's surface 3, variant A (no divider, Q2 reviewers' lean): "
    "<em>Board name:</em> and <em>Sticky shape:</em> lose <code>.foregroundStyle(.secondary)</code> and match the "
    "Miro sheet. Order was already name, shape, checkbox.</td></tr>"
    "<tr><th>Item 1</th><td><strong>Does not reproduce.</strong> Both reviewers read the bare <code>Toggle</code> as "
    "truncating in German and Catalan. Rendered, it wraps in both (frames below), at this sheet's width. The "
    "AFTER still adds MiroSheet's <code>.fixedSize(horizontal: false, vertical: true)</code> so the two sheets match "
    "and a longer string later cannot cut it; the pixels are identical today.</td></tr>"
    "<tr><th>Item 3</th><td>Not visible: the name field and the shape radios get real accessibility names "
    "(<em>Board name</em>, <em>Sticky shape</em>), where VoiceOver reads nothing today.</td></tr>"
    "<tr><th>Items 4, 6</th><td>Not visible: Escape closes the done step (as Miro's does), and Cancel or Escape "
    "while the file is being made stops it, so no save panel can open after the sheet has gone.</td></tr>"
    "</table>",
)

m5b = section(
    "Send to FigJam · German and Catalan",
    "the long-quotes label at the narrowest control column",
    [
        frame("BEFORE", "Mac · de · shipped", [PROJECT_FLAG], mac_img("figjam-before", "de"), "mac"),
        frame("AFTER", "Mac · de", [PROJECT_FLAG], mac_img("figjam-after", "de"), "mac"),
        frame("BEFORE", "Mac · ca · shipped", [PROJECT_FLAG], mac_img("figjam-before", "ca"), "mac"),
        frame("AFTER", "Mac · ca", [PROJECT_FLAG], mac_img("figjam-after", "ca"), "mac"),
    ],
    "<p>Both BEFORE frames wrap <em>Lange Zitate auf mehrere Haftnotizen aufteilen</em> and <em>Divideix les "
    "cites llargues en diverses notes adhesives</em> onto two lines. Nothing is cut.</p>",
)

# ── Web sections ───────────────────────────────────────────────────────────────────────────────
DE_WEB = "de: shipped strings; the reworded board-name label is the Mac's shipped de value"
w1 = section(
    "Send to Miro · Miro app tab",
    "MiroExportPanel.tsx · .bn-board-form",
    [
        frame("BEFORE", "web · shipped · rows 0.35rem apart", [], web_miro_app(EN)),
        frame("AFTER", "web · rows 0.75rem apart", ["proposed CSS: .bn-board-form row-gap"], web_miro_app(EN, True)),
    ],
    "<p><strong>Item 7.</strong> <code>.bn-board-form</code> sets <code>row-gap: var(--bn-space-sm)</code> "
    "(0.35rem, about 6 px), so the stacked <em>Download board file</em> and <em>Copy board data</em> buttons nearly "
    "touch. The HIG's accessibility page asks for about 12 pt round a bezelled control. AFTER: "
    "<code>var(--bn-space-md)</code> (0.75rem). One line in <code>atoms/modal.css</code>; every form on this page "
    "takes it, so each AFTER below is drawn with it.</p>"
    "<p><strong>Item 8</strong> (not visible): Return presses the dialog's primary button, here <em>Copy board "
    "data</em>, unless focus is in a field that needs Return.</p>",
)

w2 = section(
    "Send to Miro · Developer access token tab",
    "MiroExportPanel.tsx · configure",
    [
        frame("BEFORE", "web · shipped · labels stacked above fields", [SAMPLE], web_miro_token_before(EN)),
        frame(
            "AFTER",
            "web · the Mac form, colours as radios",
            [SAMPLE, "new key: miro.stickyColoursLabel (lift of the Mac's)", "reworded: miro.boardNameLabel",
             owner_copy("miro.uploadNotice")],
            web_miro_token_after(EN),
        ),
        frame("AFTER", "web · de", [SAMPLE, DE_WEB], web_miro_token_after(DE)),
    ],
    "<table>"
    "<tr><th>Form</th><td>The four-fix proposal's surface 1: right-aligned colon labels, controls beside them.</td></tr>"
    "<tr><th>Q1 radios</th><td>The drop-down becomes the Mac's two radios with the Mac's label, <em>Sticky "
    "colours:</em>. On the web the radio row wraps by itself (<code>flex-wrap</code>), so it never truncates; in "
    "English both fit on one line.</td></tr>"
    "<tr><th>Item 12</th><td>Order: name, colours, shape, then the checkbox, under the row it modifies.</td></tr>"
    "<tr><th>Item 5</th><td>The notice loses its em dash.</td></tr>"
    "<tr><th>Not changed</th><td>The <em>Connected · Disconnect</em> and account lines stay prose above the form "
    "(Gruber's item 13, not triaged).</td></tr>"
    "</table>",
)

w3 = section(
    "Send to FigJam",
    "FigJamExportPanel.tsx",
    [
        frame("BEFORE", "web · shipped · labels stacked above fields", [PROJECT_FLAG], web_figjam_before(EN)),
        frame("AFTER", "web · the Mac form", [PROJECT_FLAG, "reworded: miro.boardNameLabel"], web_figjam_after(EN)),
        frame("AFTER", "web · de", [PROJECT_FLAG, DE_WEB], web_figjam_after(DE)),
    ],
    "<p>The four-fix proposal's surface 2, now in the Mac sheet's order (name, shape, checkbox: item 12). Square "
    "stays first, as on the Mac sheet; both Miro surfaces list Rectangle first, after each tool's default.</p>",
)

w4 = section(
    "Export report",
    "ExportDialog.tsx",
    [
        frame("BEFORE", "web · shipped", [], web_export_before(EN)),
        frame("AFTER", "web · Language: on its colon", ["new key: export.languageLabel"], web_export_after(EN)),
    ],
    "<p>The four-fix proposal's surface 4, unchanged from the first page except the row gap.</p>",
)

# ── Commentary-only sections ───────────────────────────────────────────────────────────────────
INVISIBLE = (
    "<table><tr><th>Item</th><th>Change</th><th>Where</th><th>How it is checked</th></tr>"
    "<tr><td>3</td><td>Accessibility names on FigJam's field and radio group, and on the Miro token tab's name "
    "field (today read by its placeholder)</td><td><code>FigJamSheet.swift</code> 257, 262; "
    "<code>MiroSheet.swift</code> 720</td><td>VoiceOver by hand (VO-Right across the form); a Swift test that the "
    "titles are the label keys</td></tr>"
    "<tr><td>4</td><td>Escape closes FigJam's done step</td><td><code>FigJamSheet.swift</code> 321</td>"
    "<td>By hand: save a file, press Escape</td></tr>"
    "<tr><td>6</td><td>Cancel stops the board-file build, so no save panel opens after the sheet has gone</td>"
    "<td><code>FigJamSheet.swift</code> 297–298 (keep the task, cancel it in <code>.onDisappear</code>, as "
    "<code>MiroSheet</code> 528 does)</td><td>A model test: cancel mid-build, assert no save is offered</td></tr>"
    "<tr><td>8</td><td>Return presses the dialog's primary button on the web</td><td><code>Dialog.tsx</code> "
    "105–127</td><td>vitest: Enter on the dialog clicks primary; Enter in a text field does not</td></tr>"
    "<tr><td>11</td><td>The first page's paragraph on colons is out of date: French and Japanese colons were made "
    "consistent on 12 Nov (<code>f8c2f1612</code>). Not carried over.</td><td>this page</td><td>n/a</td></tr>"
    "</table>"
)

STRINGS = (
    "<p><strong>English rewords (item 5).</strong> These are your copy to approve; nothing here is shipped. Each "
    "is a 21-locale reword, done once alongside the colon labels.</p>"
    "<table><tr><th>Key</th><th>Shipped</th><th>Proposed</th></tr>"
    + "".join(
        f"<tr><td><code>{e(k)}</code></td><td><del>{e(t('en', k))}</del></td><td><ins>{e(v)}</ins></td></tr>"
        for k, v in REWORDS.items()
    )
    + "</table>"
    "<p><strong>Mac button casing (item 2).</strong> Mac-only overrides, so the browser stays in sentence case:</p>"
    "<table><tr><th>New Mac key</th><th>Shared value today</th><th>Mac value</th></tr>"
    + "".join(
        f"<tr><td><code>{e(k)}</code></td><td>{e(t('en', src))}</td><td>{e(v)}</td></tr>"
        for k, (src, v) in MAC_CASING.items()
    )
    + "</table>"
    "<p><strong>Form labels.</strong> <code>miro.boardNameLabel</code> is reworded in place to the Mac's translated "
    "value (Q4, reviewers' lean: no orphan key). New: <code>miro.stickyColoursLabel</code>, a verbatim lift of "
    "<code>desktop.miro.stickyColoursLabel</code>, and <code>export.languageLabel</code>. "
    "<code>miro.colourByLabel</code> then has no caller and goes.</p>"
    "<p><strong>Left alone:</strong> <code>miro.boardTitle</code> (“Talismanic — research board (29 quotes)”) "
    "keeps its dash: it names the board inside Miro, not our UI. Say if you want it changed too.</p>"
)

OPEN = (
    "<ol>"
    "<li><strong>Colour radios:</strong> colours stacked and shape side by side (AFTER), or both stacked "
    "(VARIANT)?</li>"
    "<li><strong>Segment casing:</strong> keep <em>Miro App · Developer Access Token</em> in title case, or leave "
    "the segments as they are? (Inference, not HIG.)</li>"
    "<li><strong>Item 1:</strong> keep the FigJam wrap guard for parity, though it changes nothing today?</li>"
    "<li><strong>The rewords above</strong>, as written or with your edits.</li>"
    "<li><strong>Still unanswered from the first page:</strong> Q2 FigJam divider (drawn as A, no divider), Q4 "
    "reword in place (drawn that way), Q5 rename <code>.bn-board-form</code> to <code>.bn-form</code>, Q7 add these "
    "dialogs to the e2e label walk.</li>"
    "</ol>"
)

final = (
    part("Notes")
    + '<section class="mk-sec"><div class="mk-h">Changes you can\'t see<small>items 3, 4, 6, 8, 11</small></div>'
    + commentary(INVISIBLE)
    + "</section>"
    + '<section class="mk-sec"><div class="mk-h">Strings<small>item 2, item 5, the form labels</small></div>'
    + commentary(STRINGS)
    + "</section>"
    + '<section class="mk-sec"><div class="mk-h">For you to decide</div>'
    + commentary(OPEN)
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
    '<span><a href="#mac">Mac</a> · <a href="#web">web</a> · <a href="#notes">notes</a></span>'
    "</div>"
)

KEY = (
    '<p class="mk-key"><b>Mac frames are real AppKit pixels</b>, not drawings: '
    "<code>form-layout-v2/render.swift</code> copies each sheet's SwiftUI (BEFORE from the shipped files, AFTER "
    "the proposal), and renders it in a key window with the system's own controls, fonts and metrics, light and "
    "dark. Each is shown at 1 pt = 1 CSS px, its real size on a Mac at default scaling; the size is in the frame's "
    "bar. The sheet's corner and shadow are the system's and are not drawn. "
    f"{e(RENDERED_ON)}. "
    "<b>Web frames</b> are the shipped theme CSS inlined from the tree; AFTER frames add only the one proposed "
    "rule. Before / after / variant is in each frame's bar, never inside the UI; a "
    '<span style="color:#b0006b">pink line</span> names new keys, proposed copy or sample data. '
    "<b>Commentary</b> = the blocks with the hatched edge. Builds on "
    '<a href="form-layout-four-fixes.html">form-layout-four-fixes.html</a>.</p>'
)

PAGE = f"""<!DOCTYPE html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Miro and FigJam forms</title>
<!-- Generated by docs/mockups/form-layout-v2.gen.py — edit that, not this. -->
<style>
{SHIPPED_CSS}
{PROPOSED_CSS}
{CHROME_CSS}
</style>
</head>
<body>
{BAR}
<div class="mk-title">Send to Miro and Send to FigJam: before and after the 19 Nov review</div>
{KEY}
<div id="mac"></div>{part("Mac")}
{m1}
{m2}
{m2b}
{m3}
{m4}
{m5}
{m5b}
<div id="web"></div>{part("Web (and the Mac app's web view)")}
{w1}
{w2}
{w3}
{w4}
<div id="notes"></div>{final}
<script>
{SCRIPT}
</script>
</body>
</html>
"""

OUT.write_text(PAGE, encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)} ({len(PAGE):,} bytes)")
