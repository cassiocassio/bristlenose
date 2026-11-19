"""Render the Azure scenario page from capture files.

    .venv/bin/python experiments/azure-scenarios/render.py baseline [final]

Writes ``docs/mockups/azure-scenarios.html``. With two labels, every scenario whose
captured output differs shows a before/after pair.

Every word in a frame comes from a capture (the CLI's own output, the server's own
refusal) or from a locale key read in ``capture.py``. The one literal path is
``new()``, which wraps text in a visible NEW marker; nothing calls it today.
Mac frames are drawn from those strings in a native-looking frame and say so in their
chrome; ``screenshots/`` (from the Tart guest walk), when present, replaces them.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.text import Text

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "docs/mockups/azure-scenarios.html"
THEME = ["bristlenose/theme/tokens.css", "bristlenose/theme/tokens-typography.css",
         "bristlenose/theme/colors/palette-default.css"]

# Mac pane cells, from the Swift statechart (read 19 Nov 2026 at 9be56fe6f). Each is
# (status key, sentence key or None, where the code picks it). Text comes from the keys.
MAC = {
    "online": ("llmSettings.status.online", "llmSettings.lastVerified", "LLMValidator.swift:293"),
    "key-rejected": ("llmSettings.status.invalid", "llmSettings.validation.keyRejected", "LLMValidator.swift:295-298"),
    "not-found": ("llmSettings.status.invalid", "llmSettings.validation.azureNotFound", "LLMValidator.swift:329-336 (every 404; body not read)"),
    "no-endpoint": ("llmSettings.status.unavailable", "llmSettings.validation.azureEndpointMissing", "LLMValidator.swift:58-62"),
    "no-deployment": ("llmSettings.status.notSetUp", None, "LLMValidator.swift:64-69 (no sentence)"),
    "no-scheme": ("llmSettings.status.invalid", "llmSettings.validation.azureEndpointScheme", "LLMValidator.swift:72-82"),
    "rate": ("llmSettings.status.unavailable", "llmSettings.validation.rateLimited", "LLMValidator.swift:321-327"),
    "http-status": ("llmSettings.status.unavailable", "llmSettings.validation.httpStatus", "LLMValidator.swift:356-363 (400, 5xx, 3xx)"),
    "timeout": ("llmSettings.status.unavailable", "llmSettings.validation.timedOut", "LLMValidator.swift:113-114"),
    "offline": ("llmSettings.status.unavailable", "llmSettings.validation.offline", "LLMValidator.swift:115-119"),
    "unreachable": ("llmSettings.status.unavailable", "llmSettings.validation.unreachable", "LLMValidator.swift:120-121"),
    "http-endpoint": ("llmSettings.status.unavailable", "llmSettings.validation.networkError", "LLMValidator.swift:73 accepts http; ATS -1022 lands in default: :122"),
    "relaunch-invalid": ("llmSettings.status.invalid", "llmSettings.revalidating", "LLMSettingsView.swift:1020-1025 (painted though no check runs)"),
}
MAC_RUN = {
    "auth": ("pipeline.failure.auth", "FailureMessage, auth"),
    "model": ("pipeline.failure.modelUnavailable", "FailureMessage, modelUnavailable (DeploymentNotFound)"),
    "request": ("pipeline.failure.apiRequest", "FailureMessage, apiRequest (a 400)"),
    "notsetup": ("pipeline.failure.providerNotSetUp", "FailureMessage, providerNotSetUp"),
}

# Scenario rows: (title, cli capture id, mac cell, mac run cell, server capture id).
ROWS = [
    ("Everything right", "doctor-ok", "online", None, "server-complete"),
    ("Key rejected (401)", "doctor-bad-key", "key-rejected", "auth", None),
    ("Deployment name wrong (404 DeploymentNotFound)", "doctor-deployment-not-found", "not-found", "model", None),
    ("Wrong URL pasted: portal or classic URL (generic 404)", "doctor-other-404", "not-found", None, None),
    ("Deployment's output limit below 64000 (400, retried)", "doctor-cap", "online", "request", None),
    ("Azure throttling (429)", "doctor-429", "rate", None, None),
    ("Azure outage (503)", "doctor-5xx", "http-status", None, None),
    ("Endpoint redirects (302)", "doctor-redirect", "http-status", None, None),
    ("Nothing answers (offline or mistyped resource)", "doctor-network", "unreachable", None, None),
    ("Key saved, no endpoint", "doctor-no-endpoint", "no-endpoint", "notsetup", "server-key-no-endpoint"),
    ("Key and endpoint, no deployment", "doctor-no-deployment", "no-deployment", "notsetup", "server-key-and-endpoint-no-deployment"),
    ("No key", "doctor-no-key", None, None, "server-no-key"),
    ("Run with a rejected key", "run-refused-bad-key", None, "auth", None),
    ("Run with a wrong deployment", "run-refused-deployment", None, "model", None),
    ("Key revoked while a run is going", "run-key-revoked-mid-run", None, "auth", None),
    ("Storing a key: configure azure", "configure-azure", None, None, None),
]
STATUS = {"doctor-429": "429", "doctor-5xx": "503", "doctor-redirect": "302", "doctor-deployment-not-found": "404", "doctor-other-404": "404"}
MAC_ONLY = [("Relaunch after a rejected check", "relaunch-invalid"), ("Offline while checking", "offline"),
            ("Check timed out", "timeout"), ("Endpoint without https://", "no-scheme"),
            ("An http:// endpoint", "http-endpoint")]
# Native renders (desktop/Bristlenose/BristlenoseTests/AzureScenarioRenderTests.swift):
# the real SwiftUI pane and AppKit sidebar/popover, from AzureScenarioFixture/AzureRunScenario.
NATIVE = HERE / "native"
NATIVE_SETTINGS = {"online": "online", "key-rejected": "keyRejected", "not-found": None,
                   "rate": "throttled", "unreachable": "unreachable", "no-endpoint": "noEndpoint",
                   "no-deployment": "noDeployment", "relaunch-invalid": "relaunchAfterRejection",
                   "offline": "offlineWithGoodCheck", "timeout": "timedOut", "no-scheme": "noScheme",
                   "http-endpoint": "httpEndpoint"}
# Rows whose settings cell is ambiguous by cell name alone, keyed by CLI capture id.
NATIVE_SETTINGS_BY_ROW = {"doctor-deployment-not-found": "deploymentNotFound", "doctor-other-404": "wrongURLPasted",
                          "doctor-5xx": "outage", "doctor-redirect": "redirect", "doctor-no-key": "noKey"}
NATIVE_RUN_BY_ROW = {"doctor-bad-key": "azure_run_refused_bad_key", "run-refused-bad-key": "azure_run_refused_bad_key",
                     "doctor-deployment-not-found": "azure_run_refused_deployment",
                     "run-refused-deployment": "azure_run_refused_deployment",
                     "run-key-revoked-mid-run": "azure_run_key_revoked_mid_run"}


def _pic(light: str, dark: str, cls: str) -> str:
    """The light render, swapped for the dark one when the reader's system is dark."""
    base = "../../experiments/azure-scenarios/native/"
    return (f'<picture><source srcset="{base}{dark}.png" media="(prefers-color-scheme: dark)">'
            f'<img class="{cls}" src="{base}{light}.png" alt="{html.escape(light)}"></picture>')


def native_frames(settings: str | None, run: str | None) -> str:
    out = []
    if settings and (NATIVE / f"settings-{settings}-light.png").exists():
        out.append('<figure class="frame native"><figcaption><span class="dots"></span>Settings ▸ LLM Provider (Mac)'
                   f'<span class="drawn">native render · AzureScenarioFixture.{settings}</span></figcaption>'
                   + _pic(f"settings-{settings}-light", f"settings-{settings}-dark", "pane") + "</figure>")
    if run and (NATIVE / f"{run}-light-sidebar.png").exists():
        out.append('<figure class="frame native"><figcaption><span class="dots"></span>Sidebar row and its popover (Mac)'
                   f'<span class="drawn">native render · {run}</span></figcaption>'
                   + _pic(f"{run}-light-sidebar", f"{run}-dark-sidebar", "row")
                   + _pic(f"{run}-light-popover", f"{run}-dark-popover", "pop")
                   + "</figure>")
    return "".join(out)


HELP = ["help-run", "help-analyze", "help-doctor", "help-configure", "help-use"]


_ANSI = r"(?:\x1b\[[0-9;]*m)*"
_FAKE_HOST = re.compile(r"(?:http://)?" + _ANSI + r"127" + _ANSI + r"\." + _ANSI + r"0" + _ANSI + r"\." + _ANSI
                        + r"0" + _ANSI + r"\." + _ANSI + r"1" + _ANSI + r":" + _ANSI + r"\d+")


def display(text: str) -> str:
    """The fake server's address as the placeholder resource: Rich colours an IP, so the
    capture's plain-text swap misses it when the colour codes sit inside the address."""
    return _FAKE_HOST.sub("contoso-research.openai.azure.com", text)


def meaningful(text: str) -> str:
    """What a before/after comparison should see: no colour, no sha, ports, timings,
    disk space or spinner frames, which change on every capture."""
    t = re.sub(r"\x1b\[[0-9;]*[mK]", "", display(text))
    t = re.sub(r"[0-9a-f]{9}(-dirty)?", "<sha>", t)
    t = re.sub(r"\(\d+ms\)|\d+ GB free|\d+(\.\d+)?s\b", "<n>", t)
    lines = [ln for ln in t.splitlines() if not re.match(r"^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]", ln) and "llm_call_failed" not in ln]
    return "\n".join(ln.rstrip() for ln in lines if ln.strip())


def new(text: str) -> str:
    return f'<mark class="new">NEW: {html.escape(text)}</mark>'


def ansi_html(text: str) -> str:
    c = Console(record=True, width=80, file=open("/dev/null", "w"), color_system="truecolor")
    c.print(Text.from_ansi(display(text)), soft_wrap=True)
    return "<pre>" + c.export_html(inline_styles=True, code_format="{code}") + "</pre>"


def fill(value: str, status: str = "401") -> str:
    return (value.replace("{{status}}", status).replace("{{endpoint}}", "contoso-research.openai.azure.com").replace("{{provider}}", "Azure OpenAI").replace("{{platform}}", "Azure OpenAI")
            .replace("%@", "today at 00:21").replace("%d", "400").replace("%lld", "400"))


def term(cap: dict[str, Any], tag: str = "") -> str:
    return (f'<figure class="frame term"><figcaption><span class="dots"></span>'
            f'<code>$ {html.escape(cap["command"])}</code><span class="exit">exit {cap["exit"]}</span>{tag}</figcaption>'
            f'<div class="screen">{ansi_html(cap["text"])}</div></figure>')


def mac_frame(strings: dict[str, str], cell: str | None, run: str | None, status: str = "401") -> str:
    if not cell and not run:
        return ""
    parts = []
    if cell:
        st, sent, src = MAC[cell]
        label = strings["desktop." + st]
        sentence = fill(strings["desktop." + sent], status) if sent else ""
        dot = {"online": "on", "invalid": "bad", "notSetUp": "off"}.get(st.rsplit(".", 1)[1], "warn")
        parts.append(
            f'<div class="pane"><div class="pane-row"><span class="dot {dot}"></span><b>Azure OpenAI</b>'
            f'<span class="status">{html.escape(label)}</span></div>'
            f'<div class="field"><label>{html.escape(strings["desktop.llmSettings.azureEndpoint"])}</label><span class="tf">https://contoso-research.openai.azure.com</span></div>'
            f'<div class="field"><label>{html.escape(strings["desktop.llmSettings.azureDeployment"])}</label><span class="tf">research-gpt41mini</span></div>'
            + (f'<p class="sentence">{html.escape(sentence)}</p>' if sentence else '<p class="sentence none">(no sentence)</p>')
            + f'<p class="src">{html.escape(src)}</p></div>')
    if run:
        key, src = MAC_RUN[run]
        parts.append(f'<div class="runfail"><span class="glyph">⚠</span>{html.escape(fill(strings["desktop." + key]))}'
                     f'<p class="src">sidebar row, run failure: {html.escape(src)}</p></div>')
    return ('<figure class="frame mac"><figcaption><span class="dots"></span>Settings ▸ AI (Mac)'
            '<span class="drawn">drawn from source; not a screenshot</span></figcaption>' + "".join(parts) + "</figure>")


def server_frame(cap: dict[str, Any]) -> str:
    a = cap["autocode"]
    if a.get("status") == "starts":
        body = '<p>AutoCode starts. Chat lens: ready.</p>'
    else:
        body = (f'<div class="msg err">{html.escape(a["spa_text"] or "")}</div>'
                f'<p class="src">AutoCode refusal {a["status"]} <code>{html.escape(a["reason"])}</code>, '
                f'SPA key <code>{html.escape(a["spa_key"] or "")}</code></p>'
                f'<p class="src">Chat lens (lab page, raw): “{html.escape(cap["chat_lens"]["detail"])}”</p>')
    return f'<figure class="frame web"><figcaption><span class="dots"></span>Report ▸ Codebook (web)</figcaption>{body}</figure>'


def main() -> None:
    labels = sys.argv[1:] or ["baseline"]
    caps = [json.loads((HERE / f"captures-{lab}.json").read_text(encoding="utf-8")) for lab in labels]
    cur = caps[-1]
    before = caps[0] if len(caps) > 1 else None
    cli = {c["id"]: c for c in cur["cli"]}
    cli0 = {c["id"]: c for c in before["cli"]} if before else {}
    srv = {s["id"]: s for s in cur["server"]}
    strings = {m["key"]: m["value"] for m in cur["mac"]}
    shots = HERE / "screenshots"

    css = "\n".join(f"/* ════ {p} ════ */\n" + (REPO / p).read_text(encoding="utf-8") for p in THEME)
    toc, body = [], []
    for i, (title, cid, cell, run, sid) in enumerate(ROWS, 1):
        anchor = f"s{i}"
        toc.append(f'<li><a href="#{anchor}">{html.escape(title)}</a></li>')
        c = cli[cid]
        frames = []
        if before and cid in cli0 and meaningful(cli0[cid]["text"]) != meaningful(c["text"]):
            frames.append(term(cli0[cid], '<span class="tag before">before</span>'))
            frames.append(term(c, '<span class="tag after">after</span>'))
        else:
            frames.append(term(c))
        nat_s = NATIVE_SETTINGS_BY_ROW.get(cid) or NATIVE_SETTINGS.get(cell or "")
        nat_r = NATIVE_RUN_BY_ROW.get(cid)
        native = native_frames(nat_s, nat_r)
        # A drawn frame stays only for what has no native render yet.
        frames.append(native + mac_frame(strings, None if nat_s else cell, None if nat_r else run,
                                         STATUS.get(cid, "401")))
        if sid:
            frames.append(server_frame(srv[sid]))
        body.append(f'<section id="{anchor}"><h2>{i}. {html.escape(title)}</h2>'
                    f'<p class="trigger">Trigger: {html.escape(c["trigger"])}</p>'
                    f'<div class="row">{"".join(f for f in frames if f)}</div></section>')
    n = len(ROWS)
    for j, (title, cell) in enumerate(MAC_ONLY, n + 1):
        toc.append(f'<li><a href="#s{j}">{html.escape(title)} (Mac only)</a></li>')
        body.append(f'<section id="s{j}"><h2>{j}. {html.escape(title)}</h2><p class="trigger">Mac only: the CLI has no equivalent state.</p>'
                    f'<div class="row">{native_frames(NATIVE_SETTINGS.get(cell), None) or mac_frame(strings, cell, None)}</div></section>')
    k = n + len(MAC_ONLY) + 1
    toc.append(f'<li><a href="#s{k}">Help text</a></li>')
    body.append(f'<section id="s{k}"><h2>{k}. Help text</h2><div class="row">' + "".join(term(cli[h]) for h in HELP) + "</div></section>")

    pngs = sorted(shots.glob("*.png")) if shots.exists() else []
    shots_html = ""
    if pngs:
        figs = "".join(
            f'<figure class="frame shot"><figcaption><span class="dots"></span>{html.escape(p.stem)}'
            f'<span class="drawn">screenshot · shipped 0.46.0 in a macOS 27 guest</span></figcaption>'
            f'<img src="../../experiments/azure-scenarios/screenshots/{html.escape(p.name)}" alt="{html.escape(p.stem)}"></figure>'
            for p in pngs)
        shots_html = ('<section id="real"><h2>Real pixels: the shipped Azure pane (0.46.0)</h2>'
                      '<p class="trigger">Taken in a throwaway macOS 27 guest from the 0.46.0 release app, no key entered. '
                      'Tonight\'s build could not be staged (the staging build notarises), so these show 0.46.0, not this sha.</p>'
                      f'<div class="row">{figs}</div></section>')
    shot_note = (f"Guest screenshots present: {len(list(shots.glob('*.png')))}." if shots.exists()
                 else "No guest screenshots: every Mac frame here is drawn from the source strings.")
    page = f"""<!doctype html>
<html lang="en" data-color-theme="default"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Azure scenarios</title>
<style>
{css}
/* ════ page chrome (not product) ════ */
:root {{ color-scheme: light dark; }}
body {{ margin:0; padding:24px; font-family:var(--bn-font-body); background:var(--bn-colour-bg); color:var(--bn-colour-text); }}
header, .key, .commentary {{ max-width:1100px; }}
.key {{ font-family:var(--bn-font-mono); font-size:12px; color:var(--bn-colour-muted); }}
.commentary {{ border-left:3px solid var(--bn-colour-border); padding:8px 16px; margin:16px 0;
  background:repeating-linear-gradient(135deg, transparent 0 8px, color-mix(in srgb, var(--bn-colour-border) 25%, transparent) 8px 9px); }}
.commentary::before {{ content:"Commentary"; display:block; font-family:var(--bn-font-mono); font-size:11px; color:var(--bn-colour-muted); }}
section {{ margin:32px 0; border-top:1px solid var(--bn-colour-border); padding-top:12px; }}
h2 {{ font-size:var(--bn-text-heading); font-weight:var(--bn-weight-emphasis); margin:0 0 4px; }}
.trigger {{ color:var(--bn-colour-muted); margin:0 0 12px; }}
.row {{ display:flex; flex-wrap:wrap; gap:16px; align-items:flex-start; }}
.frame {{ margin:0; border:1px solid var(--bn-colour-border); border-radius:10px; overflow:hidden; background:var(--bn-colour-bg); box-shadow:0 1px 3px var(--bn-colour-shadow); }}
.frame figcaption {{ display:flex; gap:8px; align-items:center; padding:6px 10px; font-size:12px; background:var(--bn-colour-hover); border-bottom:1px solid var(--bn-colour-border); }}
.dots {{ width:34px; height:10px; background:radial-gradient(circle at 5px 5px,#ff5f57 4px,transparent 5px),radial-gradient(circle at 17px 5px,#febc2e 4px,transparent 5px),radial-gradient(circle at 29px 5px,#28c840 4px,transparent 5px); }}
.native img.pane {{ width:440px; display:block; }} .native img.row {{ width:290px; display:block; }}
.native img.pop {{ width:360px; display:block; border-top:1px solid var(--bn-colour-border); }}
@media (max-width: 700px) {{ .native img.pane, .native img.row, .native img.pop {{ width:100%; }} }}
.exit, .drawn, .tag {{ margin-left:auto; font-family:var(--bn-font-mono); font-size:11px; color:var(--bn-colour-muted); }}
.tag.before {{ color:#b25000; }} .tag.after {{ color:#1a7f37; }}
.term .screen {{ background:#1e1e1e; color:#e6e6e6; padding:10px 12px; width:80ch; max-width:calc(100vw - 80px); overflow-x:auto; }}
.term .screen pre, .term .screen code {{ font-family:var(--bn-font-mono); font-size:12px; line-height:1.35; margin:0; white-space:pre; }}
.mac {{ width:360px; font-family:-apple-system, BlinkMacSystemFont, var(--bn-font-body); font-size:13px; }}
.pane, .runfail {{ padding:12px; }}
.pane-row {{ display:flex; align-items:center; gap:8px; }}
.status {{ margin-left:auto; color:var(--bn-colour-muted); }}
.dot {{ width:8px; height:8px; border-radius:50%; background:var(--bn-off-track); }}
.dot.on {{ background:#28c840; }} .dot.bad {{ background:#ff3b30; }} .dot.warn {{ background:#ffcc00; }}
.field {{ display:flex; gap:8px; align-items:center; margin:6px 0; }}
.field label {{ width:110px; text-align:right; color:var(--bn-colour-muted); }}
.tf {{ flex:1; border:1px solid var(--bn-colour-border); border-radius:5px; padding:2px 6px; font-size:12px; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }}
.sentence {{ margin:8px 0 0; }} .sentence.none {{ color:var(--bn-colour-muted); font-style:italic; }}
.runfail {{ border-top:1px solid var(--bn-colour-border); }}
.glyph {{ color:#e6a700; margin-right:6px; }}
.src {{ font-family:var(--bn-font-mono); font-size:10.5px; color:var(--bn-colour-muted); margin:6px 0 0; }}
.shot img {{ display:block; width:520px; max-width:calc(100vw - 64px); height:auto; }}
.web {{ width:340px; }} .web > *:not(figcaption) {{ margin:10px 12px; }}
.msg.err {{ border-left:3px solid #d1242f; padding:6px 10px; background:color-mix(in srgb, #d1242f 8%, transparent); }}
mark.new {{ background:#ffe08a; }}
ol.toc {{ columns:2; }}
@media (max-width: 700px) {{ body {{ padding:16px; }} ol.toc {{ columns:1; }} .mac, .web {{ width:100%; }} }}
</style></head><body>
<header><h1>Azure scenarios: what a researcher sees</h1>
<p class="key">Captured from the running code at {html.escape(cur["sha"])}{" (before: " + html.escape(before["sha"]) + ")" if before else ""}. Key: framed boxes are the product; hatched boxes are commentary. {html.escape(shot_note)}</p></header>
<div class="commentary"><p>CLI frames are the CLI's own output (Rich colours kept) against a fake Azure on this machine that answers with bodies Azure really sent. The fake's address is shown as a placeholder resource URL and the home folder as ~. Mac frames marked <b>native render</b> are the app's own views (the real Settings pane, the real AppKit sidebar row and diagnostic popover) drawn off-screen by <code>AzureScenarioRenderTests</code>: the pane shows a fake configuration and the verdict the real validator gave against a recorded Azure body, and each run row is the recorded run output passed through the Mac's own failure path. They follow your light or dark setting. The sidebar row is drawn unselected, because a view bitmap cannot draw the selection material. Frames marked <b>drawn from source</b> remain only where no native render exists yet; they place the shipped strings by locale key. Web frames are the refusal the server raises and the sentence the SPA shows for its reason.</p></div>
{shots_html}
<nav><ol class="toc">{"".join(toc)}</ol></nav>
{"".join(body)}
</body></html>"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {len(ROWS)} rows + {len(MAC_ONLY)} Mac-only + help")


if __name__ == "__main__":
    main()
