"""Generate codebook-author-links.html: every codebook's author card, current vs proposed links.

Run: .venv/bin/python docs/mockups/codebook-author-links.gen.py

The CSS is read from the theme at generation time, each block headed by its path
and line range, so the card wraps the way the app wraps it. Author names, bios and
current links are read from the codebook YAML; only the proposed labels live here.
"""

from __future__ import annotations

import html
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "bristlenose" / "theme"
CODEBOOKS = ROOT / "bristlenose" / "server" / "codebook"
OUT = Path(__file__).with_suffix("").with_suffix(".html")

# Order: the six codebooks that carry author links, as the library lists them.
IDS = ["garrett", "morville", "nielsen", "norman", "plato", "yablonski"]

# Labels shipped in the YAML. A label not taken from a domain, retailer or book
# title is owner-written copy; the commentary lists them.
PROPOSED: dict[str, list[tuple[str, str]]] = {}

# "Current" shows each codebook's labels as they were before the 24 Nov 2026
# shortening: Yablonski's changed in 44fe0ace7, Nielsen's and Morville's in the
# commit after 31646c294 (the mockup's own commit, whose tree predates them).
BEFORE_REV = {
    "yablonski": "44fe0ace7^",
    "nielsen": "31646c294",
    "morville": "31646c294",
}

EXTERNAL_SVG = (
    '<svg class="bn-icon bn-icon-external" xmlns="http://www.w3.org/2000/svg" '
    'width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M15 3h6v6" vector-effect="non-scaling-stroke"/>'
    '<path d="M10 14 21 3" vector-effect="non-scaling-stroke"/>'
    '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" '
    'vector-effect="non-scaling-stroke"/></svg>'
)


def whole(rel: str) -> str:
    text = (THEME / rel).read_text(encoding="utf-8")
    n = text.count("\n") + 1
    return f"/* ════ bristlenose/theme/{rel} — lines 1–{n} ════ */\n{text}\n"


def rule(rel: str, selector: str) -> str:
    """One rule, located by a line that STARTS with the selector, to its closing brace."""
    lines = (THEME / rel).read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(selector))
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("}"))
    body = "\n".join(lines[start : end + 1])
    return f"/* ════ bristlenose/theme/{rel} — lines {start + 1}–{end + 1} ════ */\n{body}\n"


def load(cid: str, rev: str | None = None) -> dict:
    rel = f"bristlenose/server/codebook/{cid}.yaml"
    if rev:
        src = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{rev}:{rel}"],
            check=True, capture_output=True, text=True,
        ).stdout
    else:
        src = (ROOT / rel).read_text(encoding="utf-8")
    return yaml.safe_load(src)


def card(cid: str, author: str, bio: str, links: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<a href="{html.escape(u)}" target="_blank" rel="noopener noreferrer">'
        f"{html.escape(lbl)} {EXTERNAL_SVG}</a>"
        for lbl, u in links
    )
    return (
        f'<div class="pg-side" data-cb="{cid}"><div class="preview-author">'
        f'<div class="preview-author-name">{html.escape(author)}</div>'
        f'<div class="preview-author-bio">{html.escape(bio)}</div>'
        f'<div class="preview-author-links">{items}</div></div></div>'
    )


def frame(cid: str, title: str, inner: str, changed: bool) -> str:
    tag = "changed" if changed else "unchanged"
    return (
        f'<figure class="mk-frame"><figcaption class="mk-bar"><span>{html.escape(title)}</span>'
        f'<span class="mk-tag mk-{tag}">{tag}</span></figcaption>'
        f'<div class="mk-stage">{inner}</div></figure>'
    )


def build() -> str:
    css = "".join([
        whole("tokens.css"),
        whole("tokens-typography.css"),
        whole("tokens-desktop.css"),
        whole("colors/palette-default.css"),
        whole("colors/palette-edo.css"),
        whole("atoms/icon.css"),
        rule("organisms/codebook-panel.css", ".preview-author {"),
        rule("organisms/codebook-panel.css", ".preview-author-name {"),
        rule("organisms/codebook-panel.css", ".preview-author-bio {"),
        rule("organisms/codebook-panel.css", ".preview-author-links {"),
        rule("organisms/codebook-panel.css", ".preview-author-links a {"),
        rule("organisms/codebook-panel.css", ".preview-author-links a:hover {"),
        rule("organisms/codebook-v2.css", ".pg-side {"),
        rule("organisms/codebook-v2.css", ".pg-side .preview-author {"),
        rule("organisms/codebook-v2.css", ".pg-side .preview-author-links {"),
    ])

    after, before = [], []
    for cid in IDS:
        now = load(cid)
        old = load(cid, BEFORE_REV.get(cid))
        cur_links = [(ln["label"], ln["url"]) for ln in old.get("author_links") or []]
        new_links = PROPOSED.get(cid) or [
            (ln["label"], ln["url"]) for ln in now.get("author_links") or []
        ]
        changed = new_links != cur_links
        before.append(frame(cid, now["title"], card(cid, old["author"], old["author_bio"],
                                                    cur_links), False))
        after.append(frame(cid, now["title"], card(cid, now["author"], now["author_bio"],
                                                   new_links), changed))
    return PAGE.replace("/*THEME*/", css).replace(
        "<!--AFTER-->", "".join(after)).replace("<!--BEFORE-->", "".join(before))


PAGE = """<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codebook author links</title>
<!-- Generated by codebook-author-links.gen.py; edit that, not this. -->
<style>
/*THEME*/

/* ════ mockup chrome (not the product) ════ */
html { font-size: 16px; -webkit-font-smoothing: antialiased; color-scheme: light dark; }
body { margin: 0; padding: 24px; font-family: var(--bn-font-body); font-size: var(--bn-text-label);
       line-height: var(--bn-text-label-lh); color: var(--bn-colour-text); background: var(--bn-colour-bg); }
.mk-controls { position: sticky; top: 0; z-index: 2; display: flex; gap: 16px; flex-wrap: wrap;
       padding: 8px 12px; margin: -24px -24px 20px; background: light-dark(#f3f3f3, #222);
       border-bottom: 1px solid var(--bn-colour-border); font: 12px/1.4 ui-monospace, Menlo, monospace; }
.mk-controls label { display: inline-flex; gap: 4px; align-items: center; }
.mk-key { font: 12px/1.5 ui-monospace, Menlo, monospace; color: var(--bn-colour-muted); margin: 0 0 16px; }
h2.mk-h { font: 600 13px/1.4 ui-monospace, Menlo, monospace; letter-spacing: .04em; text-transform: uppercase;
       color: var(--bn-colour-muted); margin: 28px 0 10px; }
.mk-row { display: flex; gap: 20px; align-items: flex-start; overflow-x: auto; padding-bottom: 8px; }
.mk-frame { margin: 0; flex: none; border: 1px solid var(--bn-colour-border); border-radius: 8px;
       background: var(--bn-colour-bg); overflow: hidden; }
.mk-bar { display: flex; justify-content: space-between; gap: 8px; padding: 5px 10px;
       font: 11px/1.4 ui-monospace, Menlo, monospace; color: var(--bn-colour-muted);
       background: light-dark(#f6f6f6, #2a2a2a); border-bottom: 1px solid var(--bn-colour-border); }
.mk-bar span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 170px; }
.mk-tag { padding: 0 6px; border-radius: 4px; }
.mk-changed { background: light-dark(#dbeafe, #1e3a5f); color: light-dark(#1e40af, #bfdbfe); }
/* The frame stands in for .pg-head (display:flex), the parent that gives .pg-side
   its 240px flex-basis; padding goes on the frame so the gutter stays 240px. */
.mk-stage { display: flex; padding: 16px; }
.mk-note { margin-top: 36px; max-width: 900px; border: 7px solid transparent;
       border-left: 3px solid var(--bn-colour-muted);
       background: linear-gradient(var(--bn-colour-bg), var(--bn-colour-bg)) padding-box,
                   repeating-linear-gradient(135deg, light-dark(#e2e2e2, #3a3a3a) 0 5px, transparent 5px 10px) border-box;
       padding: 12px 16px; font-size: 13px; line-height: 1.5; }
.mk-note .mk-label { font: 11px ui-monospace, Menlo, monospace; text-transform: uppercase; color: var(--bn-colour-muted); }
.mk-note table { border-collapse: collapse; margin: 8px 0; font-size: 12px; }
.mk-note td, .mk-note th { text-align: left; padding: 2px 12px 2px 0; vertical-align: top; }
.mk-note .wrap { color: light-dark(#b45309, #fbbf24); font-weight: 600; }
</style>
</head>
<body>
<div class="mk-controls">
  <label>Typography <select id="plat"><option value="desktop">Mac app (SF Pro)</option><option value="web">Web (Inter)</option></select></label>
  <label>Palette <select id="pal"><option>default</option><option>edo</option></select></label>
  <label>Scheme <select id="sch"><option value="light dark">auto</option><option>light</option><option>dark</option></select></label>
</div>
<p class="mk-key">Frames = the shipped author card (.pg-side 240px gutter + .preview-author), theme CSS inlined from the tree. Grey bar = mockup chrome. Hatched block = commentary.</p>

<h2 class="mk-h">Shipped (24 Nov 2026)</h2>
<div class="mk-row"><!--AFTER--></div>

<h2 class="mk-h">Before (labels as of 23 Nov 2026)</h2>
<div class="mk-row"><!--BEFORE--></div>

<section class="mk-note">
  <div class="mk-label">Commentary</div>
  <p>Rule applied: the page already names the book, so a link names only where it goes — the author's
  domain, then retailers. A title stays only where the author has two books (Morville).
  Garrett, Norman and Plato are already in that shape and are unchanged.</p>
  <p>Owner-written labels (not a domain, retailer or title): <b>Honeycomb essay (2004)</b>, <b>CHI 1994 paper</b>,
  <b>Posters — Jon's store</b>, <b>Amazon DE — German edition</b>.</p>
  <p>Lines per link, measured live in the frames above (amber = wraps). The card's text column is
  192px (240px gutter less 24px padding each side). Switch Typography to re-measure in Inter.</p>
  <table id="mk-lines"><thead><tr><th>Codebook</th><th>Proposed</th><th>Current</th></tr></thead><tbody></tbody></table>
</section>

<script>
const root = document.documentElement;
// A link in the column-flex list is a blockified flex item: one client rect however
// many lines it wraps to, so count lines by height over the computed line-height.
function lines(a) {
  const lh = parseFloat(getComputedStyle(a).lineHeight);
  return Math.round(a.getBoundingClientRect().height / lh);
}
function measure() {
  const rows = document.querySelectorAll('.mk-row');
  const body = document.querySelector('#mk-lines tbody'); body.innerHTML = '';
  const cell = (frame) => [...frame.querySelectorAll('.preview-author-links a')].map(a => {
    const n = lines(a); const t = a.textContent.trim();
    if (n > 1) return '<span class="wrap">' + t + ' (' + n + ' lines)</span>';
    const r = document.createRange(); r.selectNodeContents(a);
    const spare = Math.round(a.parentElement.getBoundingClientRect().width - r.getBoundingClientRect().width);
    return t + ' (1 line, ' + spare + 'px spare)';
  }).join('<br>');
  const after = rows[0].querySelectorAll('.mk-frame'), before = rows[1].querySelectorAll('.mk-frame');
  after.forEach((f, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td>' + f.querySelector('.mk-bar span').textContent + '</td><td>' + cell(f) + '</td><td>' + cell(before[i]) + '</td>';
    body.appendChild(tr);
  });
}
document.getElementById('plat').onchange = e => {
  if (e.target.value === 'desktop') root.dataset.platform = 'desktop'; else delete root.dataset.platform;
  requestAnimationFrame(measure);
};
document.getElementById('pal').onchange = e => { root.dataset.colorTheme = e.target.value; };
document.getElementById('sch').onchange = e => { root.style.colorScheme = e.target.value; };
document.fonts.ready.then(measure);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
