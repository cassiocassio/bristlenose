"""One page with every component, type role and state, in the real theme CSS.

Served by `workbench.py serve` at /everything and offered in the lab's page picker, so a
palette nudge is judged against the whole vocabulary at once, not only the page you happened
to open. Three sources, none of them a copy of the colours:

  * the real stylesheets, linked in the order the report loads them (`_THEME_FILES`);
  * the 30 hand-built specimens in docs/design-system/compliance-specimens.json;
  * the control/state/type sections below, written against real class names.

States are real, not drawn: a script clones every :hover / :focus / :active rule as
.ps-hover / .ps-focus / .ps-active, so `class="toolbar-btn ps-hover"` renders the app's own
hover style. Add a component below and it is in every iteration for free. The coverage
section at the foot lists theme files with no specimen, so gaps are visible.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from bristlenose.stages.s12_render.theme_assets import _THEME_FILES  # noqa: E402

SPECIMENS = REPO / "docs/design-system/compliance-specimens.json"


def cell(label: str, markup: str, wide: bool = False) -> str:
    return f'<figure class="st{" wide" if wide else ""}"><div class="stage">{markup}</div><figcaption>{label}</figcaption></figure>'


def row(title: str, *cells: str) -> str:
    return f'<div class="strow"><h4>{title}</h4><div class="stcells">{"".join(cells)}</div></div>'


def states(title: str, tpl: str, which: list[tuple[str, str]]) -> str:
    """tpl has {cls} and {attr}; which = [(label, "cls|attr"), ...]."""
    out = []
    for label, spec in which:
        cls, _, attr = spec.partition("|")
        out.append(cell(label, tpl.format(cls=cls, attr=attr)))
    return row(title, *out)


QUOTE = ('<blockquote class="quote-card {cls}" style="max-width:21rem;margin:0"><span class="context">Checkout · friction</span>'
         '<div class="quote-row"><span class="timecode">[08:03]</span><span class="quote-body">“It said my card was declined '
         'but then charged me twice.”</span></div><span class="speaker">— P7</span>'
         '<div class="badges"><span class="badge badge-frustration">frustration</span></div></blockquote>')

TYPE = f'''
<div class="typeblock">
  <div class="section-heading"><h1>Page title: Research report</h1></div>
  <div class="section-heading"><h2>Section heading: Themes</h2><span class="section-heading-action">action</span></div>
  <h3>Subsection heading: Onboarding friction</h3>
  <p class="bn-lead-para"><span class="bn-lead-claim">Lead claim in the report voice.</span> <span class="bn-lead-rest">The rest of the lead paragraph carries the evidence a researcher reads first, at reading length, so line length and colour both get judged.</span></p>
  <p>Body text. Participants described the checkout as <strong>fast but opaque</strong>: they could finish it, but not explain afterwards what had happened to their money. <a href="#" style="color:var(--bn-colour-accent)">A link inside body text</a> sits next to <em>emphasis</em>, a <code>code span</code> and a <kbd>⌘K</kbd> key.</p>
  <p style="color:var(--bn-colour-muted)">Muted text: the secondary tier. Timestamps, captions, counts, “6 quotes · 3 participants”.</p>
  <p style="font-size:.85em;color:var(--bn-colour-muted)">Small muted: footnotes and metadata at the smallest size the app uses.</p>
  <div class="transcript-like" style="background:var(--bn-colour-paper);padding:.8rem 1rem;border-radius:6px;max-width:44rem">
    <p style="margin:.2rem 0"><span class="timecode">[00:14:32]</span> <b>P7</b> I couldn't find where the export lived, so I just screenshotted it, and then I felt a bit silly because it was right there in the menu the whole time.</p>
    <p style="margin:.2rem 0"><span class="timecode">[00:14:51]</span> <b style="color:var(--bn-colour-muted)">Moderator</b> <span class="moderator-question">What did you expect to see?</span></p>
  </div>
</div>'''

CONTROLS = "".join([
    states("Toolbar button", '<button class="toolbar-btn {cls}" {attr}>Export</button>',
           [("rest", "|"), ("hover", "ps-hover|"), ("focus", "ps-focus|"), ("disabled", "|disabled")]),
    states("Primary button", '<button class="bn-btn bn-btn-primary {cls}" {attr}>Save</button>',
           [("rest", "|"), ("hover", "ps-hover|"), ("focus", "ps-focus|"), ("disabled", "|disabled")]),
    states("Secondary button", '<button class="bn-btn bn-btn-secondary {cls}" {attr}>Cancel</button>',
           [("rest", "|"), ("hover", "ps-hover|"), ("focus", "ps-focus|"), ("disabled", "|disabled")]),
    states("Danger button", '<button class="bn-btn bn-btn-danger {cls}" {attr}>Delete</button>',
           [("rest", "|"), ("hover", "ps-hover|"), ("focus", "ps-focus|"), ("disabled", "|disabled")]),
    states("Checkbox", '<input type="checkbox" class="bn-checkbox {cls}" {attr}>',
           [("off", "|"), ("hover", "ps-hover|"), ("on", "|checked"), ("on, hover", "ps-hover|checked")]),
    states("Toggle button", '<button class="toolbar-btn toolbar-btn-toggle {cls}">Names</button>',
           [("inactive", "|"), ("active", "active|"), ("hover", "ps-hover|")]),
    states("Star and hide", '<button class="star-btn {cls}">★</button> <button class="hide-btn {cls}">hide</button>',
           [("rest", "|"), ("hover", "ps-hover|")]),
    states("Search field", '<div class="search-container expanded {cls}"><span class="search-field"><input class="search-input" placeholder="Search quotes" value="{attr}"></span></div>',
           [("empty", "|"), ("focused", "ps-focus|"), ("with text", "|checkout")]),
    states("Tag input", '<span class="tag-input-box {cls}"><input class="tag-input" placeholder="add tag"></span>',
           [("rest", "|"), ("focus", "ps-focus|")]),
    states("Global nav tab", '<nav class="bn-global-nav" style="position:static"><a class="bn-tab {cls}" {attr}>Quotes</a></nav>',
           [("rest", "|"), ("hover", "ps-hover|"), ("active", "active|"), ("disabled", "|aria-disabled=\"true\"")]),
    states("Rail and inspector tab", '<button class="rail-btn {cls}">≡</button> <span class="inspector-tab {cls}">Signals</span>',
           [("rest", "|"), ("hover", "ps-hover|"), ("focus", "ps-focus|"), ("active", "active|")]),
    states("Menu item", '<ul class="view-switcher-menu open" style="position:static;display:block"><li class="{cls}">Sessions grid</li></ul>',
           [("rest", "|"), ("hover", "ps-hover|"), ("active", "active|")]),
    states("Tag filter item", '<label class="tag-filter-item {cls}"><input type="checkbox" {attr}> frustration <span class="tag-filter-count">12</span></label>',
           [("rest", "|"), ("hover", "ps-hover|"), ("checked", "|checked")]),
    states("Tooltip", '<span class="bn-tooltip-wrap {cls}" style="padding:1.6rem .6rem">Hover me<span class="bn-tooltip">Open in player <kbd>⌘K</kbd></span></span>',
           [("hidden", "|"), ("shown", "ps-hover|")]),
    states("Quote card", QUOTE,
           [("rest", "|"), ("hover", "ps-hover|"), ("focused", "bn-focused|"), ("selected", "bn-selected|"),
            ("focused + selected", "bn-focused bn-selected|")]),
    '<div class="bn-window-inactive" style="display:contents">' + states("Quote card, window inactive", QUOTE,
           [("focused", "bn-focused|"), ("selected", "bn-selected|")]) + '</div>',
])

SIGNALS = row("Sentiment badges", *[cell(s, f'<span class="badge badge-{s}">{s}</span>')
              for s in ("frustration", "confusion", "doubt", "surprise", "satisfaction", "delight", "confidence")]) + \
    row("Badges", cell("ai", '<span class="badge badge-ai">ai tag</span>'), cell("user", '<span class="badge badge-user">user tag</span>'),
        cell("add", '<span class="badge badge-add">+ add</span>'), cell("proposed", '<span class="badge badge-proposed">proposed</span>')) + \
    row("Signal colours", cell("negative", '<span style="color:var(--bn-colour-negative);font-weight:600">Delete 2 recordings</span>'),
        cell("positive", '<span style="background:var(--bn-colour-active-bg);color:var(--bn-colour-positive);padding:2px 8px;border-radius:5px">Analysis complete</span>'),
        cell("caution", '<span style="background:var(--bn-colour-crop-bg);box-shadow:inset 0 0 0 1px var(--bn-colour-warning);padding:2px 8px;border-radius:5px">Partial: 2 skipped</span>'),
        cell("highlight", '<mark style="background:var(--bn-colour-highlight);color:inherit;padding:0 3px">search match</mark>'),
        cell("selection", '<span style="background:var(--bn-selection-bg);box-shadow:inset 0 0 0 1px var(--bn-selection-border);padding:2px 8px;border-radius:5px">selected</span>'),
        cell("selection, inactive", '<span style="background:var(--bn-selection-bg-inactive);box-shadow:inset 0 0 0 1px var(--bn-selection-border-inactive);padding:2px 8px;border-radius:5px">inactive</span>')) + \
    row("Toasts", *[cell(k, f'<div class="clipboard-toast show has-kind" style="position:static;opacity:1;transform:none;display:flex"><span class="toast-glyph toast-glyph--{k}">●</span><div class="toast-body"><div class="toast-title">{k.capitalize()}</div>Something happened to your report.</div></div>', True)
                    for k in ("success", "error", "warning", "info")]) + \
    row("Modal", cell("dialog", '<div class="bn-modal" style="position:static;transform:none;opacity:1"><h2>Export report</h2><p class="bn-modal-subtitle">Choose what to include.</p>'
                      '<div class="bn-modal-footer"><div class="bn-modal-actions"><button class="bn-btn bn-btn-cancel">Cancel</button><button class="bn-btn bn-btn-primary">Export</button></div></div></div>', True))

SURFACES = row("Surface stack", *[cell(n, f'<div style="background:var(--bn-colour-{t});color:var(--bn-colour-text);padding:.7rem .9rem;border:1px solid var(--bn-colour-border);border-radius:6px;min-width:8.5rem">{n}<div style="color:var(--bn-colour-muted);font-size:.85em">muted on {n}</div><a href="#" style="color:var(--bn-colour-accent)">link</a></div>')
              for n, t in (("page", "bg"), ("paper", "paper"), ("quote card", "quote-bg"), ("sheet", "sheet"), ("inspector", "inspector-bg"))])


def swatches() -> str:
    names = ["bg", "paper", "quote-bg", "sheet", "inspector-bg", "text", "muted", "border", "accent", "hover", "negative", "positive", "warning"]
    return "".join(f'<span class="sw"><i style="background:var(--bn-colour-{n})"></i>{n}</span>' for n in names)


def specimen_sections() -> tuple[str, list[str]]:
    spec = json.loads(SPECIMENS.read_text(encoding="utf-8"))
    out = []
    for f, v in spec.items():
        out.append(f'<section class="spec"><h4>{html.escape(f)}</h4><div class="stage specimen">{"".join(v["specimens"])}</div></section>')
    have = set(spec)
    missing = []
    for t in _THEME_FILES:
        if t.startswith(("atoms/", "molecules/", "organisms/", "templates/")) and t not in have:
            missing.append(t)
    return "".join(out), missing


PS_SCRIPT = r"""
// Clone every :hover/:focus/:active rule as .ps-hover/.ps-focus/.ps-active so real states render side by side.
function pseudoCss(rules){let out="";for(const r of rules){
  if(r.type===1){const s=r.selectorText||""; if(/:(hover|focus-visible|focus-within|focus|active)\b/.test(s)){
    const t=s.replace(/:hover/g,".ps-hover").replace(/:focus-visible|:focus-within|:focus/g,".ps-focus").replace(/:active/g,".ps-active");
    out+=t+"{"+r.style.cssText+"}\n";}}
  else if((r.type===4||r.type===12)&&r.cssRules){const inner=pseudoCss(r.cssRules); if(inner) out+="@"+(r.type===4?"media ":"supports ")+r.conditionText+"{"+inner+"}\n";}}
  return out}
let css=""; for(const sh of document.styleSheets){try{css+=pseudoCss(sh.cssRules)}catch(e){}}
const st=document.createElement("style"); st.id="pseudo-states"; st.textContent=css; document.head.appendChild(st);
"""


def build() -> str:
    specs, missing = specimen_sections()
    links = "\n".join(f'<link rel="stylesheet" href="/theme/{t}">' for t in _THEME_FILES)
    miss = "".join(f"<li>{m}</li>" for m in missing)
    return f"""<!doctype html><html lang="en" data-color-theme="edo"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Everything</title>
{links}
<style>
body{{margin:0;padding:1.2rem 1.4rem 4rem;background:var(--bn-colour-bg);color:var(--bn-colour-text);font-family:var(--bn-font-body,system-ui,sans-serif)}}
h2.band{{margin:2.2rem 0 .6rem;padding-bottom:.3rem;border-bottom:1px solid var(--bn-colour-border);font-size:1.05rem;letter-spacing:.02em;text-transform:uppercase;color:var(--bn-colour-muted)}}
.strow{{display:grid;grid-template-columns:9.5rem 1fr;gap:.6rem;align-items:start;padding:.55rem 0;border-bottom:1px dashed var(--bn-colour-border)}}
.strow h4{{margin:.3rem 0 0;font-size:.8rem;font-weight:600;color:var(--bn-colour-muted)}}
.stcells{{display:flex;flex-wrap:wrap;gap:.7rem 1.1rem;align-items:flex-start}}
figure.st{{margin:0;display:flex;flex-direction:column;gap:.25rem;align-items:flex-start}} figcaption{{font-size:.7rem;color:var(--bn-colour-muted)}}
.stage{{display:flex;align-items:center;gap:.5rem;min-height:1.8rem;transform:translateZ(0)}} .specimen{{display:block;padding:.6rem 0}}
.sw{{display:inline-flex;align-items:center;gap:.35rem;margin:0 .8rem .4rem 0;font-size:.72rem;color:var(--bn-colour-muted)}} .sw i{{width:1.5rem;height:1.5rem;border-radius:5px;border:1px solid var(--bn-colour-border)}}
.spec h4{{font:.72rem ui-monospace,Menlo,monospace;color:var(--bn-colour-muted);margin:1rem 0 .2rem}} .typeblock{{max-width:46rem}}
.cov{{font:.72rem ui-monospace,Menlo,monospace;color:var(--bn-colour-muted);columns:3}}
</style></head><body>
<h2 class="band" style="margin-top:0">Colour roles</h2><div>{swatches()}</div>
{SURFACES}
<h2 class="band">Type hierarchy, in reading context</h2>{TYPE}
<h2 class="band">Controls and their states</h2>{CONTROLS}
<h2 class="band">Signals, badges, toasts, dialogs</h2>{SIGNALS}
<h2 class="band">Every component specimen ({len(specs.split('<section'))-1} files)</h2>{specs}
<h2 class="band">Coverage: theme files with no specimen yet</h2><ul class="cov">{miss}</ul>
<script>{PS_SCRIPT}</script></body></html>"""
