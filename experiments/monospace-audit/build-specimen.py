"""Build docs/mockups/monospace-roles-specimen.html from the shipped theme files."""
import html
import pathlib
import re

R = pathlib.Path(__file__).resolve().parents[2]
T = R / 'bristlenose/theme'

def whole(rel):
    lines = (T / rel).read_text().splitlines()
    return f"/* ════ bristlenose/theme/{rel} — lines 1–{len(lines)} ════ */\n" + "\n".join(lines)

def rule(rel, start):
    lines = (T / rel).read_text().splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(start))
    j = next(n for n in range(i, len(lines)) if lines[n].startswith('}'))
    return f"/* ════ bristlenose/theme/{rel} — lines {i+1}–{j+1} ════ */\n" + "\n".join(lines[i:j+1])

shipped = "\n\n".join([
    whole('tokens.css'), whole('tokens-typography.css'), whole('tokens-desktop.css'),
    whole('colors/palette-default.css'), whole('atoms/badge.css'), whole('atoms/timecode.css'),
    whole('molecules/person-badge.css'), rule('atoms/footer.css', '.footer-keyboard-hint kbd'),
])
assert '.footer-keyboard-hint kbd' in shipped and '--bn-font-mono' in shipped

PROPOSED_STACK = 'ui-monospace, Menlo, Consolas, "DejaVu Sans Mono", monospace'

page_css = r"""
/* ════ specimen chrome — this page only, not a proposal ════ */
:root { color-scheme: light dark; }
body { margin: 0; padding: 32px 24px 64px; background: var(--bn-colour-bg); color: var(--bn-colour-text);
       font-family: var(--bn-font-body); font-size: var(--bn-text-label); line-height: var(--bn-text-label-lh); }
.page { max-width: 1240px; margin: 0 auto; }
h1 { font-size: var(--bn-text-title); line-height: var(--bn-text-title-lh); font-weight: var(--bn-weight-strong); margin: 0 0 4px; }
h2 { font-size: var(--bn-text-heading); line-height: var(--bn-text-heading-lh); font-weight: var(--bn-weight-emphasis); margin: 40px 0 12px; }
.lede { color: var(--bn-colour-muted); max-width: 70ch; margin: 0 0 16px; }
.key { display: flex; gap: 16px; flex-wrap: wrap; margin: 12px 0 8px; font-size: var(--bn-text-caption); color: var(--bn-colour-muted); }
.key span::before { content: ""; display: inline-block; width: 14px; height: 10px; margin-right: 6px; vertical-align: -1px; border-radius: 2px; }
.key .k-art::before { border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); }
.key .k-com::before { background: repeating-linear-gradient(135deg, var(--bn-colour-hover) 0 3px, transparent 3px 6px); border: 1px solid var(--bn-colour-border); }

.frame { border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md); overflow: hidden; margin: 0 0 16px; background: var(--bn-colour-bg); color: var(--bn-colour-text); }
.bar { display: flex; justify-content: space-between; gap: 12px; padding: 6px 12px; border-bottom: 1px solid var(--bn-colour-border);
       background: var(--bn-colour-hover); font-size: var(--bn-text-micro); line-height: var(--bn-text-micro-lh); color: var(--bn-colour-muted); font-family: var(--bn-font-body); }
.cols { display: grid; grid-template-columns: repeat(var(--n, 3), minmax(0, 1fr)); }
.col { padding: 14px 16px 16px; min-width: 0; }
.col + .col { border-left: 1px solid var(--bn-colour-border); }
.colhead { font-family: var(--bn-font-body); font-size: var(--bn-text-micro); line-height: var(--bn-text-micro-lh); color: var(--bn-colour-muted); margin: 0 0 10px; }
.colhead b { font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-text); }
.face { font-family: var(--bn-font-body); font-size: var(--bn-text-micro); color: var(--bn-colour-muted); }
.face output { color: var(--bn-colour-text); font-weight: var(--bn-weight-emphasis); }
.line { margin: 0 0 8px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.mono { font-family: var(--bn-font-mono); }
.prose { font-family: var(--bn-font-body); font-size: var(--bn-text-body); line-height: var(--bn-text-body-lh); font-weight: var(--bn-weight-normal); }
.meta { font-family: var(--bn-font-body); font-size: var(--bn-text-caption); color: var(--bn-colour-muted); }
.strip { margin-top: 10px; display: grid; grid-template-columns: max-content 1fr; column-gap: 10px; row-gap: 2px; align-items: baseline; }
.strip .w { font-family: var(--bn-font-body); font-size: var(--bn-text-micro); color: var(--bn-colour-muted); text-align: right; }
.strip .s { font-family: var(--bn-font-mono); font-size: var(--bn-text-label); white-space: nowrap; overflow: hidden; text-overflow: clip; }
.path { font-family: var(--bn-font-mono); font-size: var(--bn-text-caption); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.figs { font-family: var(--bn-font-mono); font-size: var(--bn-text-label); display: inline-grid; grid-template-columns: repeat(3, 4ch); gap: 2px 8px; text-align: right; }
.figs span { padding: 2px 4px; border-radius: var(--bn-radius-sm); background: var(--bn-colour-hover); }

/* The two "today, without the download" columns: the shipped stacks with "SF Mono" removed,
   which is what a Mac without Apple's developer font package resolves them to. */
.nodl-web  { --bn-font-mono: "Fira Code", "Consolas", monospace; }
.nodl-desk { --bn-font-mono: ui-monospace, monospace; }

.commentary { margin: 0 0 24px; padding: 12px 16px; border-left: 3px solid var(--bn-colour-border-hover);
  background: repeating-linear-gradient(135deg, var(--bn-colour-hover) 0 3px, transparent 3px 9px);
  font-size: var(--bn-text-caption); line-height: var(--bn-text-caption-lh); color: var(--bn-colour-text); }
.commentary .lbl { font-family: var(--bn-font-mono); font-size: var(--bn-text-micro); color: var(--bn-colour-muted); letter-spacing: .04em; text-transform: uppercase; display: block; margin-bottom: 4px; }
.commentary p { margin: 0 0 6px; max-width: 90ch; }
.commentary table { border-collapse: collapse; margin: 8px 0; font-variant-numeric: tabular-nums; background: var(--bn-colour-bg); }
.commentary th, .commentary td { border: 1px solid var(--bn-colour-border); padding: 3px 8px; text-align: right; font-size: var(--bn-text-micro); }
.commentary th:first-child, .commentary td:first-child { text-align: left; }
.commentary code { font-size: 0.95em; }
.commentary .tbl { overflow-x: auto; }
.rgrid { display: grid; grid-template-columns: 15rem repeat(3, minmax(0, 1fr)); }
.rgrid > div { padding: 8px 12px; border-top: 1px solid var(--bn-colour-border); min-width: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rgrid > .rk-head, .rgrid > .colhead { border-top: 0; margin: 0; }
.rgrid > .rc + .rc { border-left: 1px solid var(--bn-colour-border); }
.rk { flex-direction: column; align-items: flex-start !important; gap: 1px !important; background: var(--bn-colour-hover);
      font-family: var(--bn-font-body); font-size: var(--bn-text-micro); line-height: var(--bn-text-micro-lh); color: var(--bn-colour-muted); }
.rk b { color: var(--bn-colour-text); font-weight: var(--bn-weight-emphasis); font-size: var(--bn-text-caption); }
.rk .wt { color: var(--bn-colour-text); font-variant-numeric: tabular-nums; }
.rk .wt s { color: var(--bn-colour-muted); }
.rk .how { font-style: italic; }
.rk-head { font-weight: var(--bn-weight-emphasis); }
@media (max-width: 760px) {
  body { padding: 20px 16px 48px; }
  .rgrid { grid-template-columns: minmax(0, 1fr); }
  .rgrid > .rc + .rc { border-left: 0; }
  .cols { grid-template-columns: minmax(0, 1fr); }
  .col + .col { border-left: 0; border-top: 1px solid var(--bn-colour-border); }
  .bar { flex-direction: column; gap: 2px; }
}
"""

# Proposal: mockup-local declarations of the tokens the audit proposes. Not shipped.
proposal_css = f"""
/* ════ PROPOSAL — mockup-local; what the audit proposes, nothing here ships ════ */
.prop {{
    --bn-font-mono: {PROPOSED_STACK};
    --bn-weight-mono: 400;            /* Regular  — every mono role at rest */
    --bn-weight-mono-emphasis: 520;   /* first weight above 500: Bold where the face has only Regular and Bold */
    --bn-weight-mono-refine: 500;     /* Medium on SF Mono; Regular in Menlo and Consolas: app-only refinements */
}}
.prop .badge, .prop .badge-user, .prop .bn-speaker-badge-code {{ font-weight: var(--bn-weight-mono); }}
.prop .footer-keyboard-hint kbd {{ font-size: var(--bn-text-micro); font-weight: var(--bn-weight-mono-refine); }}
.prop .tc-compact {{ font-size: var(--bn-text-caption); }}
.prop .path.is-subject {{ font-weight: var(--bn-weight-mono-emphasis); }}
.prop .figs {{ font-family: var(--bn-font-body); font-variant-numeric: tabular-nums; font-weight: var(--bn-weight-emphasis); }}
"""

def strip(weights=(300, 370, 400, 420, 490, 500, 520, 600, 700)):
    rows = "".join(f'<span class="w">{w}</span><span class="s" style="font-weight:{w}">p03 [00:14:32] Login.tsx</span>' for w in weights)
    return f'<div class="strip">{rows}</div>'

def timecode(compact=False):
    cls = 'timecode tc-compact' if compact else 'timecode'
    return f'<a class="{cls}" href="#"><span class="timecode-bracket">[</span>00:14:32<span class="timecode-bracket">]</span></a>'

TC = '<a class="timecode" href="#"><span class="timecode-bracket">[</span>00:14:32<span class="timecode-bracket">]</span></a>'
TC_CAP_NOW = '<span class="timecode" style="font-size:var(--bn-text-caption)"><span class="timecode-bracket">[</span>00:14:32<span class="timecode-bracket">]</span></span>'
TC_CAP_PROP = '<a class="timecode tc-compact" href="#"><span class="timecode-bracket">[</span>00:14:32<span class="timecode-bracket">]</span></a>'
SPK = '<span class="bn-person-badge"><span class="bn-speaker-badge--split"><span class="bn-speaker-badge-code">p03</span><span class="bn-speaker-badge-name">Ana</span></span></span> <span class="bn-person-badge"><span class="bn-speaker-badge--split"><span class="bn-speaker-badge-code">m1</span></span></span>'
KBD = '<span class="footer-keyboard-hint" style="font-size:var(--bn-text-badge)"><kbd>j</kbd><kbd>k</kbd><kbd>⌘F</kbd></span>'
FIGS = '<span class="figs"{w}><span>0.42</span><span>1.07</span><span>12</span><span>3.9</span><span>0.08</span><span>140</span></span>'

# (role, where, size token, today, proposed, how the proposed weight renders, today html, proposed html)
ROWS = [
  ("Timecode", "beside a quote", "label", "400", "400",
   "Regular everywhere", TC + ' <span class="prose">“I couldn’t find the basket total.”</span>', None),
  ("Timecode", "in a metadata row", "caption", "400", "400",
   "Regular everywhere", '<span class="meta">Session 4 · 42 min</span> ' + TC_CAP_NOW, '<span class="meta">Session 4 · 42 min</span> ' + TC_CAP_PROP),
  ("Tag", "sentiment chip", "badge", "370", "400",
   "Regular everywhere", '<span class="badge badge-frustration">frustration</span> <span class="badge badge-delight">delight</span>', None),
  ("Tag", "codebook tag", "badge", "420 (490 in dark)", "400",
   "Regular everywhere", '<span class="badge badge-user" style="background:var(--bn-emo-1-bg, var(--bn-colour-user-tag-bg))">basket total</span> <span class="badge badge-user" style="background:var(--bn-ux-1-bg, var(--bn-colour-user-tag-bg))">findability</span>', None),
  ("Code", "speaker code", "badge", "400", "400",
   "Regular everywhere", SPK, None),
  ("Path", "names the screen", "caption", "490", "520",
   "SF Mono +21% (about Medium) · Menlo, Consolas: Bold", '<span class="path is-subject" style="font-weight:var(--bn-weight-emphasis)">checkout-flow/Basket summary.png</span>', '<span class="path is-subject">checkout-flow/Basket summary.png</span>'),
  ("Path", "plain", "caption", "400", "400",
   "Regular everywhere", '<span class="path" style="color:var(--bn-colour-muted)">interviews/session-04/screens/Basket summary.png</span>', None),
  ("Keycap", "footer hints", "0.85em → micro", "400", "500",
   "SF Mono Medium (+18%) · Menlo, Consolas: Regular", KBD, None),
  ("Figures", "heatmap, metrics", "label", "490 mono", "490 body",
   "body face, tabular figures: the body ladder", FIGS.format(w=' style="font-weight:var(--bn-weight-emphasis)"'), FIGS.format(w='')),
]

def roles_frame(scale_attr, title, nodl_cls, nodl_head):
    head = ('<div class="rk rk-head"><span>role · size</span><span>weight today → proposed</span></div>'
            f'<div class="rc colhead"><b>Today</b> — as shipped, on this Mac</div>'
            f'<div class="rc colhead {nodl_cls}"><b>Today</b> — {nodl_head}</div>'
            '<div class="rc colhead prop"><b>Proposed</b></div>')
    body = ""
    for role, where, size, now, prop, how, cur, newhtml in ROWS:
        wt = (f'<span class="wt"><b>{prop}</b>, unchanged</span>' if now == prop
              else f'<span class="wt"><s>{now}</s> → <b>{prop}</b></span>')
        body += (f'<div class="rk"><b>{role}</b> <span>{where} · {size}</span>{wt}<span class="how">{how}</span></div>'
                 f'<div class="rc">{cur}</div><div class="rc {nodl_cls}">{cur}</div><div class="rc prop">{newhtml or cur}</div>')
    return f"""
  <div class="frame" {scale_attr}>
    <div class="bar"><span>{title}</span><span>left column: weights, not product · synthetic content</span></div>
    <div class="rgrid">{head}{body}</div>
  </div>"""

def face_frame(scale_attr, title, nodl_cls, nodl_head):
    return f"""
  <div class="frame" {scale_attr}>
    <div class="bar"><span>{title}</span><span>weights 300–700 in each column's face · synthetic content</span></div>
    <div class="cols" style="--n:3">
      <div class="col"><p class="colhead"><b>Today</b> — the shipped token, on this Mac</p><p class="face">drawn in <output data-face></output></p>{strip()}</div>
      <div class="col {nodl_cls}"><p class="colhead"><b>Today</b> — {nodl_head}</p><p class="face">drawn in <output data-face></output></p>{strip()}</div>
      <div class="col prop"><p class="colhead"><b>Proposed</b> — one stack for both scales</p><p class="face">drawn in <output data-face></output></p>{strip()}</div>
    </div>
  </div>"""

commentary_face = (R / 'docs/design-monospace-roles.md').exists()

body = f"""
<div class="page">
  <h1>Monospace roles</h1>
  <p class="lede">Every monospace face in the report, on both type scales, as it renders today and as the audit proposes.
  Open it in the Mac app's webview or Safari and in Chrome. Today's columns differ by browser and by whether the Mac has Apple's SF Mono download; the proposed column differs only by browser (system SF Mono in WebKit, Menlo in Chrome).
  Reasoning and measurements: <code>docs/design-monospace-roles.md</code>.</p>
  <div class="key"><span class="k-art">Artefact — real tokens and real component CSS</span><span class="k-com">Commentary — not the product</span></div>

  <h2>1 · Which face draws the mono</h2>
  {face_frame('', 'Web · Inter scale (browser, HTML export, the Mac app with Typography ▸ Inter)', 'nodl-web', 'a Mac without the SF Mono download')}
  {face_frame('data-platform="desktop"', 'Desktop · SF Pro scale (the Mac app default)', 'nodl-desk', 'a Mac without the SF Mono download')}
  <div class="commentary"><span class="lbl">Commentary</span>
    <p><b>“SF Mono” by name exists only on Macs with Apple's developer font package</b> (<code>com.apple.pkg.SFMonoFonts</code>, installed here). The system's own mono is the hidden <code>.SF NS Mono</code>, reachable from CSS only as <code>ui-monospace</code>, and only in WebKit. So the left column is the developer's view, and the middle column is what a researcher's Mac shows.</p>
    <p>Ink relative to 400, measured 15 Oct 2026 from DOM screenshots at 2×, in a <code>lang="en"</code> page like the report (the language matters: without it WebKit's generic <code>monospace</code> is Courier, with it Menlo). WebKit means Playwright WebKit and a sandboxed WKWebView, which agree to the pixel; each figure holds within ±0.5 points from 9.6 to 15 px.</p>
    <div class="tbl"><table>
      <tr><th>face (how it is reached)</th><th>300</th><th>370</th><th>420</th><th>490</th><th>500</th><th>520</th><th>600</th><th>700</th></tr>
      <tr><td>SF Mono download, static — both engines, by name</td><td>−21%</td><td>−21%</td><td>+15%</td><td>+15%</td><td>+15%</td><td>+30%</td><td>+30%</td><td>+50%</td></tr>
      <tr><td>system SF Mono — WebKit, via <code>ui-monospace</code></td><td>−20%</td><td>−5%</td><td>+4%</td><td>+16%</td><td>+18%</td><td>+21%</td><td>+35%</td><td>+53%</td></tr>
      <tr><td>Menlo — WebKit's generic <code>monospace</code>; Chromium by name</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td colspan="3">Bold, +33 to +39% (varies with the string)</td></tr>
      <tr><td>Courier — Chromium's generic <code>monospace</code> (its own font API says so)</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td colspan="3">Bold, +37 to +38%</td></tr>
    </table></div>
    <p>Given the same face, WebKit and Chromium draw the same ink at every weight. They differ only in which face they find. At the named instances (400, 500, 600, 700), the download and the system font agree within 2–5% and have identical advances. The off-instance weights (370, 420, 490, 520) are where the developer's Mac and a researcher's Mac part company. <b>600 is the one emphasis weight that reads about the same on every path</b> (+30–39%). 500 is Medium in WebKit and Regular wherever the face has only Regular and Bold.</p>
  </div>

  <h2>2 · The roles</h2>
  {roles_frame('', 'Web · Inter scale', 'nodl-web', 'a Mac without the download')}
  {roles_frame('data-platform="desktop"', 'Desktop · SF Pro scale', 'nodl-desk', 'a Mac without the download')}
  <div class="commentary"><span class="lbl">Commentary</span>
    <p><b>Regular (400) is the resting weight of every monospace role.</b> Monospace marks <i>kind</i>, not importance: the face says "this is a time, a code, a path", and colour, size and the chip carry everything else.</p>
    <p><b>Tags are one weight.</b> Today sentiment chips are 370 and codebook tags 420 (490 in dark mode). On this Mac that is Light against Medium, a visible two-step gap; on a researcher's Mac in the app it is −5% against +4%; in Chrome both are Regular. Colour already separates the two families. If light chips are the intent, 300 for both draws Light on every Mac.</p>
    <p><b>Two emphasis values, by job.</b> 520 is the first weight above 500: about Medium on SF Mono (+21%), Bold wherever the face has only Regular and Bold (Menlo, Consolas, DejaVu). It is for emphasis that must survive in a browser, today only the Screens path that names the screen. 500 is Medium on SF Mono and plain Regular in Menlo: for refinements that can be app-only, such as keycaps, which in Chrome would be too heavy in Bold. No mono role is Semibold or Bold.</p>
    <p><b>Figures</b> leave monospace for the body face with tabular figures, keeping 490, where the body ladder works.</p>
    <p>Proposed stack: <code>{html.escape(PROPOSED_STACK)}</code>. WebKit draws the system SF Mono on every Mac, download or not; Chromium on a Mac draws Menlo (it has no <code>ui-monospace</code>) instead of today's Courier; Windows Consolas; Linux DejaVu Sans Mono. Menlo and Consolas carry only Regular and Bold.</p>
  </div>
</div>
"""

face_js = r"""
// Which face did this column get? Line-box height at line-height:normal differs between
// SF Mono, Menlo, Courier and Consolas; compare against references. Same DOM path as the
// specimen (not canvas, which in WebKit ignores user-installed fonts).
(function () {
  const refs = [["SF Mono", "'SF Mono'"], ["system SF Mono", "ui-monospace"], ["Menlo", "Menlo"], ["Courier", "Courier"],
                ["Courier New", "'Courier New'"], ["Consolas", "Consolas"], ["DejaVu Sans Mono", "'DejaVu Sans Mono'"]];
  function sig(family, host) {
    const s = document.createElement("span");
    s.textContent = "Hxgjp 0O1l";
    s.style.cssText = "position:absolute;visibility:hidden;font-size:100px;line-height:normal;white-space:nowrap;font-weight:400;font-family:" + family;
    (host || document.body).appendChild(s);
    const r = s.getBoundingClientRect(); s.remove();
    return r.height.toFixed(2) + "x" + r.width.toFixed(2);
  }
  const fallback = sig("'bn-no-such-font-7c2e'");
  const table = refs.map(([name, fam]) => [name, sig(fam)]).filter(([, k]) => k !== fallback);
  document.querySelectorAll("[data-face]").forEach((out) => {
    const col = out.closest(".col");
    const fam = getComputedStyle(col.querySelector(".strip .s")).fontFamily;
    const k = sig(fam, col);
    const hits = table.filter(([, kk]) => kk === k).map(([n]) => n);
    out.textContent = hits.length ? hits.join(" / ") : "an unlisted face";
  });
})();
"""

doc = f"""<!doctype html>
<html lang="en" data-color-theme="default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monospace roles</title>
<!-- Generated from the shipped theme files; each inlined block names its source and lines.
     Synthetic content only. Companion doc: docs/design-monospace-roles.md -->
<style>
{shipped}
</style>
<style>
{page_css}
</style>
<style>
{proposal_css}
</style>
</head>
<body>
{body}
<script>
{face_js}
</script>
</body>
</html>
"""
out = R / 'docs/mockups/monospace-roles-specimen.html'
out.write_text(doc)
print(out, len(doc))
