"""Generate sidebar-failure-labels.html: every sidebar status line and the failed-analysis pane.

The page shows each state three times: before this session, as built in f319cedb1, and as
proposed in the sidebar status audit. Every shipped word is read from
bristlenose/locales/{en,de}/desktop.json. Words that do not ship yet are marked NEW in the
frame and listed in the string plan. Glyphs are real SF Symbols rendered from AppKit by
sidebar-failure-labels.syms.swift into sidebar-failure-labels.syms.json.

Run:  .venv/bin/python docs/mockups/sidebar-failure-labels.gen.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "sidebar-failure-labels.html"


def flat(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            full = prefix + "." + key
            if isinstance(value, dict):
                walk(value, full)
            else:
                out[full] = value

    walk(data, "desktop")
    return out


EN = flat(ROOT / "bristlenose/locales/en/desktop.json")
DE = flat(ROOT / "bristlenose/locales/de/desktop.json")
SYMS = json.loads((HERE / "sidebar-failure-labels.syms.json").read_text(encoding="utf-8"))


def t(key: str, table: dict[str, str] | None = None, **values: str) -> str:
    text = (table or EN)[key]
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    return text


def esc(text: str) -> str:
    return html.escape(text, quote=True)


# ---- glyph CSS: each SF Symbol as a mask, tinted by currentColor -------------
glyph_css = []
for name, (w, h, b64) in SYMS.items():
    cls = "s-" + name.replace(".", "-")
    url = "url(data:image/png;base64," + b64 + ")"
    glyph_css.append(
        "." + cls + "{-webkit-mask-image:" + url + ";mask-image:" + url
        + ";aspect-ratio:" + str(w) + "/" + str(h) + ";}"
    )
GLYPH_CSS = "\n".join(glyph_css)

KIND = {
    "err": ("xmark.circle.fill", "k-err"),
    "warn": ("exclamationmark.triangle.fill", "k-warn"),
    "info": ("info.circle", "k-info"),
    "drive": ("externaldrive.badge.xmark", "k-mute"),
    "net": ("network.slash", "k-mute"),
    "none": (None, ""),
}


def glyph(symbol: str, cls: str = "", size: int = 10) -> str:
    return (
        '<span class="g s-' + symbol.replace(".", "-") + " " + cls
        + '" style="height:' + str(size) + 'px" aria-hidden="true"></span>'
    )


def row(name: str, kind: str, text: str | None, new: bool = False, sel: bool = False) -> str:
    """One sidebar row: folder icon, name, and the status line under it."""
    sym, cls = KIND[kind]
    status = ""
    if text is not None:
        g = glyph(sym, cls) if sym else ""
        mark = '<span class="new">NEW</span>' if new else ""
        status = '<div class="st">' + g + '<span class="stx">' + esc(text) + "</span>" + mark + "</div>"
    one = "" if text is not None else " one"
    selected = " sel" if sel else ""
    return (
        '<div class="r' + one + selected + '"><div class="ico">'
        + glyph("folder", "k-folder", 13)
        + '</div><div class="stack"><div class="nm">' + esc(name) + "</div>" + status
        + "</div></div>"
    )


def cell(name: str, kind: str, text: str | None, new: bool = False) -> str:
    return '<div class="sb">' + row(name, kind, text, new) + "</div>"


# ---- the state table ---------------------------------------------------------
# (number from the audit, scenario, project, before, built, proposed)
# each of before/built/proposed is (glyph kind, text or None, is_new)
G = "Gemini"
CAT = "desktop.pipeline.category."
RUN_FAILED = t("desktop.pipeline.diagnostic.header.failed")


def cat(leaf: str, table: dict[str, str] | None = None) -> str:
    return t(CAT + leaf, table)


STATES = [
    ("Failures", [
        ("1", "Key rejected, provider known", "auth",
         ("err", RUN_FAILED, False),
         ("err", t("desktop.pipeline.diagnostic.header.failedAuth", provider=G), False),
         ("err", t("desktop.pipeline.diagnostic.header.failedAuth", provider=G), False)),
        ("1g", "Key rejected, read back after a relaunch (no provider on record)", "auth",
         ("err", RUN_FAILED, False),
         ("err", t("desktop.pipeline.diagnostic.header.failedAuthGeneric"), False),
         ("err", t("desktop.pipeline.diagnostic.header.failedAuthGeneric"), False)),
        ("2", "Out of credit", "outOfCredit",
         ("err", RUN_FAILED, False), ("err", cat("outOfCredit"), False),
         ("err", G + " out of credit", True)),
        ("3", "Network", "network",
         ("err", RUN_FAILED, False), ("err", cat("network"), False),
         ("err", "Couldn’t reach " + G, True)),
        ("4", "Rate limit", "quota",
         ("err", RUN_FAILED, False), ("err", cat("quota"), False), ("err", cat("quota"), False)),
        ("5", "Model unavailable", "modelUnavailable",
         ("err", RUN_FAILED, False), ("err", cat("modelUnavailable"), False),
         ("err", cat("modelUnavailable"), False)),
        ("6", "Provider server down", "apiServer",
         ("err", RUN_FAILED, False), ("err", cat("apiServer"), False),
         ("err", G + " unavailable", True)),
        ("7", "Request rejected (likely our bug)", "apiRequest",
         ("err", RUN_FAILED, False), ("err", cat("apiRequest"), False),
         ("err", "Request rejected", True)),
        ("8", "No provider set up", "providerNotSetUp",
         ("err", RUN_FAILED, False), ("err", cat("providerNotSetUp"), False),
         ("err", "No AI provider set up", True)),
        ("9", "Output truncated", "outputTruncated",
         ("err", RUN_FAILED, False), ("err", cat("outputTruncated"), False),
         ("err", cat("outputTruncated"), False)),
        ("10", "Disk full", "disk",
         ("err", RUN_FAILED, False), ("err", cat("disk"), False), ("err", "Disk full", True)),
        ("11", "Whisper didn’t load", "whisper",
         ("err", RUN_FAILED, False), ("err", cat("whisper"), False), ("err", cat("whisper"), False)),
        ("12", "Missing dependency", "missingDep",
         ("err", RUN_FAILED, False), ("err", cat("missingDep"), False),
         ("err", cat("missingDep"), False)),
        ("13", "No interviews found", "missingInput",
         ("err", RUN_FAILED, False), ("err", cat("missingInput"), False),
         ("err", "No interviews found", True)),
        ("14", "FFmpeg missing", "missingBinary",
         ("err", RUN_FAILED, False), ("err", cat("missingBinary"), False),
         ("err", "FFmpeg missing", True)),
        ("15", "Output already exists", "outputExists",
         ("err", RUN_FAILED, False), ("err", cat("outputExists"), False),
         ("info", cat("outputExists"), False)),
        ("16", "Unusable input (run-level)", "unusableInput",
         ("err", RUN_FAILED, False), ("err", cat("unusableInput"), False),
         ("err", "Files not analysed", True)),
        ("17", "Stopped, filed as a failure", "userSignal",
         ("err", RUN_FAILED, False), ("err", cat("userSignal"), False),
         ("none", t("desktop.chrome.pipeline.stopped"), False)),
        ("18", "Unknown cause", "unknown",
         ("err", RUN_FAILED, False), ("err", RUN_FAILED, False), ("err", RUN_FAILED, False)),
        ("19", "The app couldn’t launch the analysis", "unknown",
         ("err", RUN_FAILED, False), ("err", RUN_FAILED, False),
         ("err", "Couldn’t start", True)),
        ("22", "Stranded: no final event, process gone", "unknown",
         ("err", RUN_FAILED, False), ("err", RUN_FAILED, False),
         ("warn", "Interrupted", True)),
        ("24", "Folder there, contents unreadable", None,
         ("err", t("desktop.chrome.pipeline.unreachable.unreadable"), False),
         ("err", t("desktop.chrome.pipeline.unreachable.unreadable"), False),
         ("err", "No access to folder", True)),
        ("27", "The report server couldn’t start", None,
         ("none", None, False), ("none", None, False),
         ("err", "Couldn’t open", True)),
    ]),
    ("Warnings", [
        ("29", "Partial, count unknown", None,
         ("warn", t("desktop.pipeline.diagnostic.header.completed_partial"), False),
         ("warn", t("desktop.pipeline.diagnostic.header.completed_partial"), False),
         ("warn", "Some steps failed", True)),
        ("34", "Volume unmounted", None,
         ("drive", "Interviews SSD · " + t("desktop.availability.missing"), False),
         ("drive", "Interviews SSD · " + t("desktop.availability.missing"), False),
         ("drive", "Interviews SSD not connected", True)),
        ("36", "Folder moved, bookmark lost", None,
         ("warn", t("desktop.availability.missing"), False),
         ("warn", t("desktop.availability.missing"), False),
         ("warn", t("desktop.chrome.pipeline.unreachable.folderMissing"), False)),
        ("39", "Source files missing", None,
         ("warn", t("desktop.chrome.missingSubtitle_other").replace("{{count}}", "2"), False),
         ("warn", t("desktop.chrome.missingSubtitle_other").replace("{{count}}", "2"), False),
         ("warn", "2 files missing", True)),
    ]),
    ("No glyph", [
        ("42", "Stopped because the app quit", None,
         ("none", t("desktop.chrome.pipeline.stopped"), False),
         ("none", t("desktop.chrome.pipeline.stopped"), False),
         ("warn", "Interrupted", True)),
    ]),
]

# German as built today, for the widest real locale on the row budget.
DE_BUILT = {
    "auth": t("desktop.pipeline.diagnostic.header.failedAuth", DE, provider=G),
}


def de_built(leaf: str | None, built_text: str | None) -> str | None:
    if leaf is None or built_text is None:
        return None
    if leaf == "auth":
        return DE_BUILT["auth"]
    if leaf == "unknown":
        return t("desktop.pipeline.diagnostic.header.failed", DE)
    return cat(leaf, DE)


def state_rows() -> str:
    out = []
    for group, items in STATES:
        out.append('<tr class="grp"><th colspan="5">' + esc(group) + "</th></tr>")
        for num, scen, leaf, before, built, proposed in items:
            german = de_built(leaf, built[1])
            if num == "1g":
                german = t("desktop.pipeline.diagnostic.header.failedAuthGeneric", DE)
            de_cell = (
                cell("Onboarding study", built[0], german) if german
                else '<span class="dash">not drawn here</span>'
            )
            out.append(
                "<tr><td class='num'>" + esc(num) + "</td><td class='scen'>" + esc(scen) + "</td>"
                + "<td>" + cell("Onboarding study", *before) + "</td>"
                + "<td>" + cell("Onboarding study", *built) + "</td>"
                + "<td>" + cell("Onboarding study", *proposed) + "</td>"
                + "<td class='de'>" + de_cell + "</td></tr>"
            )
    return "\n".join(out)


# ---- the failure pane --------------------------------------------------------
RECORD = "\n".join([
    "Bristlenose 0.46.0 (6528) on Version 27.0",
    "Project: Onboarding study",
    "Outcome: Run failed (no terminus event)",
    "Category: auth",
    "Cause: 400 API key not valid. Please pass a valid API key.",
    "",
    "Last output:",
    "✓ Ingested 6 sessions                                    0.4s",
    "✓ Transcribed 6 sessions                                 3m 12s",
    "✗ Topic segmentation: 400 API key not valid. Please pass a valid API key.",
])


def pane(expanded: bool, layout: str) -> str:
    title = t("desktop.chrome.failedTitle")
    sentence = t("desktop.pipeline.failure.auth", provider=G)
    remedy = t("desktop.pipeline.diagnostic.action.setUpProvider")
    toggle = t("desktop.boot.hideDetails") if expanded else t("desktop.boot.showDetails")
    buttons = (
        '<div class="btns"><span class="pbtn def">' + esc(remedy) + '</span><span class="pbtn">'
        + esc(toggle) + "</span></div>"
    )
    box = '<pre class="rec ' + layout + '">' + esc(RECORD) + "</pre>" if expanded else ""
    actions = (
        '<div class="act-' + layout + '">' + buttons + box + "</div>"
    )
    return (
        '<div class="pane"><div class="cuv">'
        + glyph("exclamationmark.triangle", "k-pane", 40)
        + '<div class="cuv-t">' + esc(title) + '</div><div class="cuv-d">' + esc(sentence)
        + "</div>" + actions + "</div></div>"
    )


def serve_pane() -> str:
    return (
        '<div class="pane"><div class="cuv">'
        + glyph("exclamationmark.triangle", "k-pane", 40)
        + '<div class="cuv-t">' + esc(t("desktop.boot.failedTitle")) + '</div><div class="cuv-d">'
        + esc(t("desktop.boot.failure.startTimeout")) + "</div>"
        + '<div class="act-under"><div class="btns"><span class="pbtn def">'
        + esc(t("desktop.boot.retry")) + '</span><span class="pbtn">'
        + esc(t("desktop.boot.showDetails")) + "</span></div></div></div></div>"
    )


def window(sidebar_rows: str, detail: str, bar: str) -> str:
    return (
        '<div class="frame"><div class="fbar">' + esc(bar) + '</div><div class="win">'
        + '<div class="side">' + sidebar_rows + '</div><div class="detail">' + detail
        + "</div></div></div>"
    )


SIDEBAR_BEFORE = (
    row("Pilot interviews", "none", None)
    + row("Onboarding study", "err", RUN_FAILED, sel=True)
    + row("Checkout research", "none", None)
)
SIDEBAR_BUILT = (
    row("Pilot interviews", "none", None)
    + row("Onboarding study", "err", t("desktop.pipeline.diagnostic.header.failedAuth", provider=G),
          sel=True)
    + row("Checkout research", "none", None)
)
SIDEBAR_SERVE = (
    row("Pilot interviews", "none", None)
    + row("Onboarding study", "err", "Couldn’t open", new=True, sel=True)
    + row("Checkout research", "none", None)
)

# ---- the string plan ---------------------------------------------------------
NEW_STRINGS = [
    ("2", "out of credit, provider known", G + " out of credit", "{{provider}} out of credit"),
    ("3", "network, provider known", "Couldn’t reach " + G, "Couldn’t reach {{provider}}"),
    ("3", "network, no provider", "No connection", "No connection"),
    ("6", "provider server down, provider known", G + " unavailable", "{{provider}} unavailable"),
    ("7", "request rejected", "Request rejected", "Request rejected"),
    ("8", "no provider set up", "No AI provider set up", "No AI provider set up"),
    ("10", "disk full", "Disk full", "Disk full"),
    ("13", "no interviews found", "No interviews found", "No interviews found"),
    ("14", "FFmpeg missing", "FFmpeg missing", "FFmpeg missing"),
    ("16", "files not analysed", "Files not analysed", "Files not analysed"),
    ("19", "launch failed", "Couldn’t start", "Couldn’t start"),
    ("22, 42", "stranded / quit mid-run", "Interrupted", "Interrupted"),
    ("24", "folder unreadable", "No access to folder", "No access to folder"),
    ("27", "report server couldn’t start", "Couldn’t open", "Couldn’t open"),
    ("29", "partial, count unknown", "Some steps failed", "Some steps failed"),
    ("34", "volume unmounted", "Interviews SSD not connected", "{{volume}} not connected"),
    ("39", "files missing", "2 files missing", "{{count}} files missing (plural)"),
]


def string_plan() -> str:
    out = []
    for num, what, example, value in NEW_STRINGS:
        n = len(example)
        flag = " over" if n > 22 else ""
        out.append(
            "<tr><td>" + esc(num) + "</td><td>" + esc(what) + "</td><td><code>" + esc(value)
            + "</code></td><td class='n" + flag + "'>" + str(n) + "</td></tr>"
        )
    return "\n".join(out)


CSS = """
:root{
  --sf:-apple-system,"SF Pro Text",system-ui,sans-serif;
  --mono:ui-monospace,Menlo,"Cascadia Mono",Consolas,"DejaVu Sans Mono",monospace;
  --orange:#FF9F0A;--red:#FF3B30;--blue:#0A84FF;
  --sb-bg:#f2f2f4;--sb-sel:rgba(0,0,0,0.07);
  --sb-1:rgba(0,0,0,0.85);--sb-2:rgba(0,0,0,0.5);--sb-3:rgba(0,0,0,0.32);
  --detail:#ffffff;--label:rgba(0,0,0,0.85);--secondary:rgba(0,0,0,0.5);
  --btn:#ffffff;--btn-border:rgba(0,0,0,0.14);--rec:rgba(0,0,0,0.03);
}
body.dark{
  --sb-bg:#232325;--sb-sel:rgba(255,255,255,0.10);
  --sb-1:rgba(255,255,255,0.92);--sb-2:rgba(255,255,255,0.55);--sb-3:rgba(255,255,255,0.34);
  --detail:#1e1e1e;--label:rgba(255,255,255,0.92);--secondary:rgba(255,255,255,0.55);
  --btn:rgba(255,255,255,0.16);--btn-border:rgba(255,255,255,0.1);--rec:rgba(255,255,255,0.05);
}
*{box-sizing:border-box;}
html,body{margin:0;}
body{font-family:var(--sf);color:#fff;-webkit-font-smoothing:antialiased;padding:28px 24px 90px;
  background:radial-gradient(120% 120% at 20% 0%,#6a86b8,#3a4a6b 60%,#232a3d);}
body.dark{background:radial-gradient(120% 120% at 20% 0%,#2b3340,#1a1d24 60%,#0e1014);}
h1{font-size:19px;font-weight:600;margin:0 0 4px;}
h2{font-size:15px;font-weight:600;margin:40px 0 6px;}
.sub{font-size:12.5px;line-height:1.55;color:rgba(255,255,255,0.78);max-width:82ch;margin:0 0 8px;}
.chrome{display:flex;gap:8px;margin:14px 0 10px;}
.chrome button{font:12px/1 var(--sf);padding:6px 11px;border-radius:7px;border:0.5px solid rgba(255,255,255,0.35);
  background:rgba(255,255,255,0.14);color:#fff;cursor:pointer;}
.chrome button.on{background:#fff;color:#1d1d1f;}
.key{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:rgba(255,255,255,0.75);margin:0 0 10px;}
.key i{display:inline-block;width:24px;height:14px;border-radius:3px;vertical-align:-2px;margin-right:6px;}
.key i.art{background:rgba(255,255,255,0.9);}
.key i.com{border:3px solid transparent;border-left:3px solid rgba(255,255,255,.6);
  background:linear-gradient(#3a4a6b,#3a4a6b) padding-box,
  repeating-linear-gradient(135deg,rgba(255,255,255,.3) 0 3px,transparent 3px 6px) border-box;}
.key .new{margin-left:0;}

.g{display:inline-block;-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;
  mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center;background-color:currentColor;flex:none;}
.k-err{color:var(--red);} .k-warn{color:var(--orange);} .k-info{color:var(--blue);}
.k-mute{color:var(--sb-2);} .k-folder{color:var(--blue);} .k-pane{color:var(--secondary);}

/* sidebar rows: ProjectCellSpec metrics, 32pt single / 46pt two-line */
.sb{width:220px;background:var(--sb-bg);border-radius:8px;padding:4px 0;box-shadow:0 4px 14px rgba(0,0,0,0.22);}
.r{display:grid;grid-template-columns:20px 1fr;column-gap:6px;align-items:start;padding:7px 8px 0 12px;height:46px;}
.r.one{height:32px;align-items:center;padding-top:0;}
.r.sel{background:var(--sb-sel);border-radius:6px;margin:0 6px;padding-left:6px;}
.ico{width:20px;height:16px;display:flex;align-items:center;justify-content:center;}
.stack{min-width:0;}
.nm{font-size:13px;line-height:16px;color:var(--sb-1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.st{display:flex;align-items:center;gap:4px;margin-top:1px;height:13px;min-width:0;}
.stx{font-size:10px;line-height:13px;color:var(--sb-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;}
.new{font:600 8px/1 var(--mono);letter-spacing:.06em;color:#fff;background:#b0306a;border-radius:3px;
  padding:2px 3px;margin-left:4px;flex:none;}

/* state table */
table.states{border-collapse:separate;border-spacing:0 6px;margin-top:6px;}
table.states th{font:600 10px/1.2 var(--mono);letter-spacing:.07em;text-transform:uppercase;
  color:rgba(255,255,255,0.65);text-align:left;padding:0 14px 0 0;}
table.states tr.grp th{padding-top:18px;font-size:11px;color:#fff;}
table.states td{vertical-align:middle;padding:0 14px 0 0;}
td.num{font:11px var(--mono);color:rgba(255,255,255,0.6);width:28px;}
td.scen{font-size:12px;color:rgba(255,255,255,0.85);width:200px;line-height:1.35;}
.dash{font-size:11px;color:rgba(255,255,255,0.45);}

/* window frames */
.frame{display:inline-block;margin:10px 18px 10px 0;vertical-align:top;}
.fbar{font:10px var(--mono);letter-spacing:.07em;text-transform:uppercase;color:rgba(255,255,255,0.65);margin:0 0 6px;}
.win{display:flex;width:960px;height:430px;border-radius:10px;overflow:hidden;box-shadow:0 12px 34px rgba(0,0,0,0.35);}
.side{width:230px;background:var(--sb-bg);padding:10px 0;flex:none;}
.detail{flex:1;background:var(--detail);display:flex;}
.pane{flex:1;display:flex;align-items:center;justify-content:center;color:var(--label);}
.cuv{display:flex;flex-direction:column;align-items:center;text-align:center;max-width:100%;}
.cuv-t{font-size:22px;font-weight:700;margin:14px 0 6px;}
.cuv-d{font-size:13px;color:var(--secondary);margin:0 0 16px;}
.btns{display:flex;gap:12px;justify-content:center;}
.pbtn{font:13px/1 var(--sf);padding:5px 12px;border-radius:6px;background:var(--btn);border:0.5px solid var(--btn-border);
  box-shadow:0 0.5px 1px rgba(0,0,0,0.12);color:var(--label);white-space:nowrap;}
.pbtn.def{background:var(--blue);color:#fff;border-color:transparent;}
.act-under{display:flex;flex-direction:column;align-items:center;gap:12px;}
.act-beside{display:flex;flex-direction:row;align-items:center;gap:12px;}
pre.rec{font:10px/1.35 var(--mono);color:var(--secondary);background:var(--rec);border-radius:6px;padding:8px;
  margin:0;text-align:left;white-space:pre-wrap;overflow:auto;max-height:140px;}
pre.rec.under{width:calc(80ch + 16px + 15px);}
pre.rec.beside{width:240px;}

/* commentary */
.note{border:7px solid transparent;border-left:3px solid rgba(255,255,255,.55);
  background:linear-gradient(#34425f,#34425f) padding-box,
  repeating-linear-gradient(135deg,rgba(255,255,255,.14) 0 5px,transparent 5px 10px) border-box;
  padding:12px 16px;margin:14px 0 0;border-radius:0 6px 6px 0;max-width:1000px;}
body.dark .note{background:linear-gradient(#1b1f27,#1b1f27) padding-box,
  repeating-linear-gradient(135deg,rgba(255,255,255,.10) 0 5px,transparent 5px 10px) border-box;}
.note .tag{font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,0.6);display:block;margin-bottom:6px;}
.note p,.note li{font-size:12.5px;line-height:1.55;color:rgba(255,255,255,0.85);max-width:84ch;}
.note p{margin:6px 0;} .note ul{margin:6px 0;padding-left:18px;}
.note code,table.plan code{font:11.5px var(--mono);background:rgba(255,255,255,0.12);padding:1px 4px;border-radius:4px;}
table.plan{border-collapse:collapse;font-size:12px;margin:8px 0;}
table.plan th,table.plan td{text-align:left;padding:5px 14px 5px 0;border-bottom:1px solid rgba(255,255,255,0.14);color:rgba(255,255,255,0.85);}
table.plan th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#fff;}
table.plan td.n{font-family:var(--mono);} table.plan td.over{color:#ffb4b4;}
"""

JS = """
for (const b of document.querySelectorAll('[data-scheme]')) {
  b.addEventListener('click', () => {
    document.body.classList.toggle('dark', b.dataset.scheme === 'dark');
    for (const o of document.querySelectorAll('[data-scheme]')) o.classList.toggle('on', o === b);
  });
}
"""

COMMENT_PANE = """
<div class="note"><span class="tag">Commentary</span>
<p><b>Built in bbd9d675d.</b> The details open under the buttons, so the buttons stay where they
were clicked. The box is 80 columns of the record's own font wide, plus padding and a scroll bar,
because the record is CLI output written for an 80-column terminal. No Send Feedback: a rejected key
is a real error with a fix, not a fault that would help us improve Bristlenose.</p>
<p>The record's last-output lines are sample data. The <code>Outcome: Run failed (no terminus
event)</code> line is what ships today, and it is wrong for runs that did end properly (audit, other
inconsistencies).</p>
</div>"""

COMMENT_STATES = """
<div class="note"><span class="tag">Commentary</span>
<p><b>Built</b> (f319cedb1): the row is keyed on the failure category and reads the existing
<code>desktop.pipeline.category.*</code> label, translated in all 21 locales. The auth rows read
<code>failedAuth</code> / <code>failedAuthGeneric</code>, added that commit. Unknown still reads
"Run failed".</p>
<p><b>Proposed</b>: every cell marked NEW is a string that does not exist yet. Nothing in the
Proposed column is built. Three glyph changes are proposed as well, not just wording:</p>
<ul>
<li><b>15 Already analysed</b>: info glyph instead of red ✕. The code calls it "not a real failure".
The glyph here is my pick; the audit only says "not a red ✕".</li>
<li><b>17 Stopped</b>: no glyph, matching row 41 ("Stopped by the researcher").</li>
<li><b>22 and 42 Interrupted</b>: warning instead of ✕ (22) or no glyph (42), because Resume
Analysis fixes it.</li>
</ul>
<p><b>German</b> shows the Built column in a long locale. At this 220pt cell every built German
label fits, the longest being "Transkription fehlgeschlagen". The one proposal that truncates is row
34, "Interviews SSD not connected", because the disk's name is the researcher's and has no length
limit; hover shows the whole line.</p>
<p><b>Row 27</b> has no status line today. The proposal adds one.</p>
</div>"""


def build() -> str:
    states_head = (
        "<tr><th></th><th>Scenario</th><th>Before this session</th><th>Built (f319cedb1)</th>"
        "<th>Proposed</th><th>German, as built</th></tr>"
    )
    parts = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Sidebar failure labels</title><style>", CSS, GLYPH_CSS, "</style></head><body>",
        "<h1>Sidebar failure labels and the failed-analysis pane</h1>",
        "<p class='sub'>Every sidebar status line from the 14 Nov audit, three times: before this "
        "session, as built, and as proposed. Shipped words come from <code>bristlenose/locales/"
        "{en,de}/desktop.json</code> (generated by <code>sidebar-failure-labels.gen.py</code>). "
        "Glyphs are real SF Symbols rendered from AppKit.</p>",
        "<div class='chrome'><button data-scheme='light' class='on'>Light</button>"
        "<button data-scheme='dark'>Dark</button></div>",
        "<div class='key'><span><i class='art'></i>Artefact: what ships</span>"
        "<span><i class='com'></i>Commentary</span>"
        "<span><span class='new'>NEW</span> a string that does not ship yet</span></div>",
        "<h2>1 · The failed-analysis pane, Show Details open</h2>",
        window(SIDEBAR_BEFORE, pane(True, "beside"), "Before: details beside the buttons"),
        window(SIDEBAR_BUILT, pane(True, "under"), "Built: details underneath, 80 columns"),
        COMMENT_PANE,
        "<h2>2 · Every sidebar status line</h2>",
        "<table class='states'>", states_head, state_rows(), "</table>",
        COMMENT_STATES,
        "<h2>3 · Row 27, proposed: the report server couldn’t start</h2>",
        window(SIDEBAR_SERVE, serve_pane(), "Proposed: the row says what the pane says"),
        "<h2>4 · String plan</h2>",
        "<div class='note'><span class='tag'>Commentary</span>"
        "<p>The new strings the Proposed column needs. Each goes into all 21 locales. The count is the "
        "English example's length; the row budget is about 22 characters, and red means over it.</p>"
        "<table class='plan'><tr><th>Row</th><th>Case</th><th>English value</th><th>Chars</th></tr>",
        string_plan(),
        "</table><p>Already in the tree and reused: every <code>desktop.pipeline.category.*</code> label, "
        "<code>failedAuth</code>, <code>failedAuthGeneric</code>, and <code>desktop.chrome.pipeline."
        "unreachable.folderMissing</code> (row 36).</p></div>",
        "<script>", JS, "</script></body></html>",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))
