"""Build docs/mockups/azure-d4-and-deployment.html from the native proposal renders.

The PNGs come from AzureScenarioRenderTests (d4Label, wrongDeployment), run with
TEST_RUNNER_BN_AZURE_PROPOSAL_VISUAL=1: the real Settings pane, sidebar row and
diagnostic popover, today's words beside the proposed ones, rendered in one run.
"""

from __future__ import annotations

import html
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
OUT = REPO / "docs/mockups/azure-d4-and-deployment.html"
PNG = "../../experiments/azure-scenarios/proposals/"
THEME = ["bristlenose/theme/tokens.css", "bristlenose/theme/tokens-typography.css",
         "bristlenose/theme/colors/palette-default.css"]

D4_CASES = [
    ("deploymentNotFound", "Deployment name wrong (404 DeploymentNotFound)",
     "The case that started D4: the label says the key is bad, the sentence under it says the key is fine."),
    ("wrongURLPasted", "Wrong URL pasted (generic 404)",
     "Same sentence, same contradiction. Azure answers a portal URL, a classic URL and an http endpoint the same way."),
    ("keyRejected", "Key rejected (401)",
     "Included in D4 on purpose: Azure's own 401 says “invalid subscription key or wrong API endpoint”, so the key is never certain."),
    ("noScheme", "Endpoint without https://",
     "Decided before any request is sent; today it is also labelled “Invalid key”."),
    ("unreachable", "Nothing answers (mistyped resource)",
     "Unchanged by D4 as rendered: this is the “Unavailable” status, not “Invalid key”. The design lists host-not-found under D4; see question 2."),
]


def pic(stem: str, cls: str) -> str:
    return (f'<picture><source srcset="{PNG}{stem}-dark.png" media="(prefers-color-scheme: dark)">'
            f'<img class="{cls}" src="{PNG}{stem}-light.png" alt="{html.escape(stem)}"></picture>')


def run_pic(stem: str) -> str:
    return (f'<picture><source srcset="{PNG}{stem}-dark-sidebar.png" media="(prefers-color-scheme: dark)">'
            f'<img class="row" src="{PNG}{stem}-light-sidebar.png" alt="{stem} sidebar"></picture>'
            f'<picture><source srcset="{PNG}{stem}-dark-popover.png" media="(prefers-color-scheme: dark)">'
            f'<img class="pop" src="{PNG}{stem}-light-popover.png" alt="{stem} popover"></picture>')


def frame(caption: str, tag: str, body: str) -> str:
    return (f'<figure class="frame"><figcaption><span class="dots"></span>{html.escape(caption)}'
            f'<span class="tag {tag}">{tag}</span></figcaption>{body}</figure>')


def main() -> None:
    css = "\n".join(f"/* ════ {p} ════ */\n" + (REPO / p).read_text(encoding="utf-8") for p in THEME)
    d4 = []
    for stem, title, note in D4_CASES:
        d4.append(
            f'<section><h3>{html.escape(title)}</h3><div class="row">'
            + frame("Settings ▸ LLM Provider (Mac)", "today", pic(f"today-{stem}", "pane"))
            + frame("Settings ▸ LLM Provider (Mac)", "proposed", pic(f"d4-{stem}", "pane"))
            + f'</div><div class="commentary"><p>{html.escape(note)}</p></div></section>')
    deploy = ('<div class="row">'
              + frame("Sidebar row and its popover (Mac)", "today", run_pic("deploy-today"))
              + frame("Option A: shipped words", "proposed", run_pic("deploy-a"))
              + frame("Option B: an Azure sentence (S2)", "proposed", run_pic("deploy-b"))
              + "</div>")
    page = f"""<!doctype html>
<html lang="en" data-color-theme="default"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Azure D4 and wrong deployment</title>
<style>
{css}
/* ════ page chrome (not product) ════ */
:root {{ color-scheme: light dark; }}
body {{ margin:0; padding:24px; font-family:var(--bn-font-body); background:var(--bn-colour-bg); color:var(--bn-colour-text); }}
header, .key, .commentary, table {{ max-width:1100px; }}
.key {{ font-family:var(--bn-font-mono); font-size:12px; color:var(--bn-colour-muted); }}
.commentary {{ border-left:3px solid var(--bn-colour-border); padding:8px 16px; margin:12px 0;
  background:repeating-linear-gradient(135deg, transparent 0 8px, color-mix(in srgb, var(--bn-colour-border) 25%, transparent) 8px 9px); }}
.commentary::before {{ content:"Commentary"; display:block; font-family:var(--bn-font-mono); font-size:11px; color:var(--bn-colour-muted); }}
.commentary p, .commentary li {{ margin:4px 0; }}
h2 {{ font-size:var(--bn-text-title); font-weight:var(--bn-weight-emphasis); margin:40px 0 4px; border-top:1px solid var(--bn-colour-border); padding-top:16px; }}
h3 {{ font-size:var(--bn-text-heading); font-weight:var(--bn-weight-emphasis); margin:24px 0 8px; }}
.row {{ display:flex; flex-wrap:wrap; gap:16px; align-items:flex-start; }}
.frame {{ margin:0; border:1px solid var(--bn-colour-border); border-radius:10px; overflow:hidden; background:var(--bn-colour-bg); box-shadow:0 1px 3px var(--bn-colour-shadow); }}
.frame figcaption {{ display:flex; gap:8px; align-items:center; padding:6px 10px; font-size:12px; background:var(--bn-colour-hover); border-bottom:1px solid var(--bn-colour-border); }}
.dots {{ width:34px; height:10px; background:radial-gradient(circle at 5px 5px,#ff5f57 4px,transparent 5px),radial-gradient(circle at 17px 5px,#febc2e 4px,transparent 5px),radial-gradient(circle at 29px 5px,#28c840 4px,transparent 5px); }}
.tag {{ margin-left:auto; font-family:var(--bn-font-mono); font-size:11px; }}
.tag.today {{ color:var(--bn-colour-muted); }} .tag.proposed {{ color:#b25000; }}
img {{ display:block; }} img.pane {{ width:440px; }} img.row {{ width:290px; }}
img.pop {{ width:360px; border-top:1px solid var(--bn-colour-border); }}
table {{ border-collapse:collapse; font-size:13px; margin:8px 0; }}
td, th {{ border:1px solid var(--bn-colour-border); padding:6px 8px; text-align:left; vertical-align:top; }}
code {{ font-family:var(--bn-font-mono); font-size:12px; }}
@media (max-width: 700px) {{ body {{ padding:16px; }} img.pane, img.row, img.pop {{ width:100%; }} }}
</style></head><body>
<header><h1>Azure: D4 and the wrong-deployment run</h1>
<p class="key">Framed boxes are the app's own views, rendered off-screen by AzureScenarioRenderTests
(d4Label, wrongDeployment) with fake settings; only the words differ between today and proposed.
Hatched boxes are commentary. Follows your light or dark setting. Nothing here is built; both are owner calls.</p></header>

<h2>1. D4: the Azure status label</h2>
<div class="commentary">
<p><b>Proposal</b> (<code>docs/design-azure-connection.md</code> §6, L1): on any Azure failure the label reads
<b>Not connected</b> instead of <b>Invalid key</b>. It is chosen from the failure's sentence key, so <code>ProviderStatus</code>
gains no case, the red dot stays, and other providers keep “Invalid key”. VoiceOver must speak the same label
(<code>ValidationAnnouncement</code> builds it from the status alone today).</p>
<p><b>Cost:</b> one new key in 21 locales (frames here patch the English value for the render only).</p>
</div>
{"".join(d4)}

<h2>2. A run with a wrong deployment name</h2>
{deploy}
<div class="commentary">
<p><b>Why it says “Something went wrong” today.</b> The pre-run check stops the run before its events log opens,
so the Mac sorts the failure from the printed output. The line reads <code>Azure OpenAI rejected (Deployment
'research-gpt41mini' not found)</code>, the terminal wraps it after <code>not</code>, and no pattern in
<code>PipelineRunner.categoriseFailure</code> matches either form. A rejected key at the same check is already right
(“Your Azure OpenAI key was rejected.”).</p>
<p><b>Option A, no new words.</b> One pattern, <code>deployment '[^']*' not\\s+found</code>, sends it to Model unavailable.
The sentence is true but its remedy is for other providers: “Choose another” model, where Azure's fix is the
deployment name. It does point at the right Settings pane.</p>
<p><b>Option B, an Azure sentence.</b> The same pattern, plus an Azure leaf at <code>FailureMessage</code>'s
extension point using the design's sentence S2, with the name read from the line. One new key in 21 locales;
pairs with D4's string batch.</p>
<p>Either way the sidebar row still reads “Run failed” and the category under the sentence becomes
“Model unavailable”. Neither needs Python changes. The fuller fix, the pre-run check writing a structured cause
the Mac reads instead of the text, is a larger change and not drawn.</p>
</div>

<h2>Questions</h2>
<div class="commentary"><ol>
<li><b>D4:</b> “Not connected” on every Azure failure, 401 included? (Design recommends yes.)</li>
<li><b>Host not found and timeouts</b> show “Unavailable” (orange). Leave them, or bring them under “Not connected” too?
Throttling and outages share that status, so this would need the label chosen per sentence there as well.</li>
<li><b>Wrong deployment:</b> A now (no new words, fits the reliability phase), B with the D4 strings, or both in sequence?</li>
</ol>
<table><tr><th>Key</th><th>English</th><th>Needed by</th></tr>
<tr><td><code>desktop.llmSettings.status.azureNotConnected</code> (proposed name)</td><td>Not connected</td><td>D4</td></tr>
<tr><td><code>desktop.pipeline.failure.azureDeploymentNotFound</code> (proposed name)</td><td>No deployment named “{{{{name}}}}” on this resource. Key and endpoint are fine; check the name.</td><td>Option B</td></tr>
</table></div>
</body></html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
