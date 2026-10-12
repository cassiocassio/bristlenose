"""Build the side-by-side page for a batch of style-prompt trials.

Reads ``<root>/manifest.json`` and ``<root>/trials/*.json`` (from
``trial_prompts.py``) and writes ``<root>/compare.html``: per language, per
recording, no prompt against the prompt in 30-second blocks, with the measured
numbers above each pair. The transcript typography is the shipped CSS, copied
from ``docs/mockups/transcript-paragraph-capitalisation.html``.

The page holds interview transcripts, so it is written into the gitignored
trial folder and never into the repo.

    .venv/bin/python experiments/transcript-readability/compare_prompts.py \
        trial-runs/whisper-prompt-samples
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSS_SOURCE = REPO / "docs/mockups/transcript-paragraph-capitalisation.html"
LANG_NAMES = {"es": "Spanish", "fr": "French", "de": "German", "it": "Italian",
              "pt": "Portuguese"}
#: Trial conditions, in order, with the label the page shows.
CONDITIONS = {"none": "No prompt (today)", "prompt": "Prompt v1", "prompt-v2": "Prompt v2"}
METRICS = [
    ("words", "Words", "higher is not always better; a big drop means speech was lost"),
    ("sentences", "Sentence ends", "higher is better"),
    ("words_per_sentence", "Words per sentence", "lower is easier to read"),
    ("longest_unpunctuated", "Longest unpunctuated run", "lower is better"),
    ("lowercase_after_sentence_end", "Lower-case after a full stop", "lower is better"),
    ("commas", "Commas", ""),
    ("fillers", "Fillers kept", "verbatim wants them kept"),
    ("inverted_marks", "¿ ¡ marks", "Spanish only"),
]


def shipped_css() -> str:
    lines = CSS_SOURCE.read_text(encoding="utf-8").split("\n")
    start = lines.index("<style>")
    end = start + lines[start:].index("</style>")
    return "\n".join(lines[start:end + 1])


def script_json(data: object) -> str:
    return (json.dumps(data, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def main(root: str) -> int:
    base = Path(root)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    samples = []
    for sid, item in manifest.items():
        conds = {}
        for cond in CONDITIONS:
            path = base / "trials" / f"{sid}.{cond}.json"
            if path.exists():
                r = json.loads(path.read_text(encoding="utf-8"))
                conds[cond] = {"prompt": r.get("prompt"), "detected": r["detected"],
                               "metrics": r["metrics"], "segs": r["segments"]}
        if "none" in conds and len(conds) > 1:
            samples.append({
                "id": sid, "lang": item["lang"], "licence": item["licence"],
                "audio": str(Path(item["wav"]).relative_to(base)),
                "source": item["licence_url"], "minutes": round(item["duration_s"] / 60, 1),
                "conds": conds,
            })
    data = {"samples": samples, "names": LANG_NAMES, "metrics": METRICS,
            "condNames": CONDITIONS}
    page = PAGE.replace("{{CSS}}", shipped_css()).replace("{{DATA}}", script_json(data))
    out = base / "compare.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(samples)} recordings)")
    return 0


PAGE = r"""<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Style prompts, batch 1</title>
{{CSS}}
<style>
/* MOCKUP CHROME, not the product. Prefixed m-. */
html { color-scheme: light; }
body { padding: 0; }
.m-wrap { max-width: 1440px; margin: 0 auto; padding: 1.5rem clamp(1rem, 3vw, 2rem) 5rem;
  display: flex; flex-direction: column; gap: 1.2rem; }
.m-title { font-size: var(--bn-text-display); font-weight: var(--bn-weight-strong); margin: 0; }
.m-lede { color: var(--bn-colour-muted); max-width: 95ch; margin: .3rem 0 0; }
.m-toolbar { position: sticky; top: 0; z-index: 300; display: flex; flex-wrap: wrap; gap: .7rem 1.4rem;
  align-items: center; padding: .55rem .9rem; background: var(--bn-colour-bg);
  border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md);
  box-shadow: 0 2px 8px var(--bn-colour-shadow); font-size: var(--bn-text-caption); }
.m-group { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.m-group > b { font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); }
.m-seg { display: inline-flex; flex-wrap: wrap; border: 1px solid var(--bn-colour-border);
  border-radius: var(--bn-radius-md); overflow: hidden; }
.m-seg button { all: unset; cursor: pointer; padding: .25rem .6rem; color: var(--bn-colour-text); }
.m-seg button + button { border-left: 1px solid var(--bn-colour-border); }
.m-seg button[aria-pressed="true"] { background: var(--bn-colour-accent); color: #fff; }
.m-seg button:focus-visible { outline: 2px solid var(--bn-colour-accent); outline-offset: -2px; }
.m-sample { border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg);
  background: var(--bn-colour-bg); overflow: hidden; }
.m-head { padding: .7rem 1rem; border-bottom: 1px solid var(--bn-colour-border);
  background: var(--bn-colour-hover); font-size: var(--bn-text-label); }
.m-head h2 { font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 0 0 .2rem; }
.m-head .m-sub { color: var(--bn-colour-muted); }
.m-head code { font-family: var(--bn-font-mono); font-size: .92em; }
.m-table { border-collapse: collapse; font-size: var(--bn-text-caption); margin: .6rem 0 0; }
.m-table th, .m-table td { padding: .2rem .7rem .2rem 0; text-align: left; }
.m-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
.m-table th { color: var(--bn-colour-muted); font-weight: var(--bn-weight-emphasis); }
.m-better { color: var(--bn-positive, green); }
.m-cols { display: grid; grid-template-columns: 1fr 1fr; }
.m-col { padding: .2rem 1rem 1rem; min-width: 0; }
.m-col + .m-col { border-left: 1px solid var(--bn-colour-border); }
.m-col h3 { font-family: var(--bn-font-mono); font-size: var(--bn-text-badge); color: var(--bn-colour-muted);
  text-transform: uppercase; letter-spacing: .06em; margin: .6rem 0 0; font-weight: var(--bn-weight-normal); }
.m-col .transcript-body { grid-template-columns: 4.5rem 1fr; margin-top: .3rem; }
.m-col .transcript-segment .segment-body { opacity: 1; }
.m-mark .m-pw { background: color-mix(in srgb, var(--bn-colour-accent) 22%, transparent); border-radius: 2px; }
.m-note a, .m-note { }
.m-note { font-size: var(--bn-text-caption); color: var(--bn-colour-muted); }
@media (max-width: 900px) { .m-cols { grid-template-columns: 1fr; }
  .m-col + .m-col { border-left: 0; border-top: 1px solid var(--bn-colour-border); } }
</style>
</head>
<body>
<div class="m-wrap">
<header>
  <h1 class="m-title">Style prompts: no prompt against the prompt</h1>
  <p class="m-lede">Each recording transcribed twice through the shipped code path (mlx-whisper,
  large-v3-turbo, seeded), once with no style prompt and once with the candidate prompt for its
  language. Text is shown in 30-second blocks so the two columns stay aligned in time. Speakers
  are not identified. Highlighting marks words that also appear in the prompt, the sign of a
  prompt leaking into speech it could not hear.</p>
</header>
<div class="m-toolbar" role="group" aria-label="Page switches">
  <div class="m-group"><b>Language</b><span class="m-seg" id="m-langs"></span></div>
  <div class="m-group"><b>Left</b><span class="m-seg">
    <button data-left="none" aria-pressed="true">No prompt</button><button data-left="prompt" aria-pressed="false">v1</button><button data-left="prompt-v2" aria-pressed="false">v2</button></span></div>
  <div class="m-group"><b>Right</b><span class="m-seg">
    <button data-right="best" aria-pressed="true">Latest</button><button data-right="prompt" aria-pressed="false">v1</button><button data-right="prompt-v2" aria-pressed="false">v2</button></span></div>
  <div class="m-group"><b>Show</b><span class="m-seg">
    <button data-span="360" aria-pressed="true">First 6 min</button><button data-span="99999" aria-pressed="false">Whole file</button></span></div>
  <div class="m-group"><b>Prompt words</b><span class="m-seg">
    <button data-mark="on" aria-pressed="true">Highlight</button><button data-mark="off" aria-pressed="false">Plain</button></span></div>
  <div class="m-group"><b>Appearance</b><span class="m-seg">
    <button data-scheme="light" aria-pressed="true">Light</button><button data-scheme="dark" aria-pressed="false">Dark</button></span></div>
</div>
<div id="m-out"></div>
</div>
<script>
const D = {{DATA}};
const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]);
const norm = w => w.toLocaleLowerCase().replace(/[^\p{L}\p{N}']/gu, "");
let lang = D.samples.length ? D.samples[0].lang : "es", span = 360;
const tc = s => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function blocks(segs, promptWords) {
  const out = new Map();
  for (const s of segs) {
    if (s.start >= span) continue;
    const k = Math.floor(s.start / 30) * 30;
    const words = s.text.split(/\s+/).map(w => promptWords.has(norm(w)) ? `<span class="m-pw">${esc(w)}</span>` : esc(w));
    out.set(k, (out.get(k) || []).concat(words.join(" ")));
  }
  return out;
}
function column(title, segs, promptWords) {
  const b = blocks(segs, promptWords);
  const keys = [...b.keys()].sort((x, y) => x - y);
  return `<div class="m-col"><h3>${title}</h3><div class="transcript-body">` + keys.map(k =>
    `<div class="transcript-segment"><span class="timecode" data-t="${k}" style="cursor:pointer"><span class="timecode-bracket">[</span>${tc(k)}<span class="timecode-bracket">]</span></span>` +
    `<div class="segment-body">${b.get(k).join(" ")}</div></div>`).join("") + `</div></div>`;
}
function better(key, a, b) {
  if (["sentences", "commas", "inverted_marks"].includes(key)) return b > a;
  if (["words_per_sentence", "longest_unpunctuated", "lowercase_after_sentence_end"].includes(key)) return b < a;
  return false;
}
let left = "none", right = "best";
function render() {
  const rows = D.samples.filter(s => s.lang === lang);
  document.getElementById("m-out").innerHTML = rows.map(s => {
    const keys = Object.keys(D.condNames).filter(k => s.conds[k]);
    const R = right === "best" ? keys[keys.length - 1] : (s.conds[right] ? right : keys[keys.length - 1]);
    const L = s.conds[left] ? left : "none";
    const pwOf = k => new Set((s.conds[k].prompt || "").split(/\s+/).map(norm).filter(Boolean));
    const head = `<tr><th></th>${keys.map(k => `<th>${esc(D.condNames[k])}</th>`).join("")}<th></th></tr>`;
    const table = D.metrics.filter(([k]) => k !== "inverted_marks" || s.lang === "es").map(([m, label, hint]) =>
      `<tr><th>${label}</th>` + keys.map(k => {
        const a = s.conds.none.metrics[m], b = s.conds[k].metrics[m];
        return `<td class="num ${k !== "none" && better(m, a, b) ? "m-better" : ""}">${b}</td>`;
      }).join("") + `<td class="m-note">${hint}</td></tr>`).join("");
    const perBlock = segs => segs.reduce((acc, x) => { const b = Math.floor(x.start / 30);
      acc.set(b, (acc.get(b) || 0) + x.text.split(/\s+/).length); return acc; }, new Map());
    const base = perBlock(s.conds.none.segs);
    const lostOf = k => { const pb = perBlock(s.conds[k].segs);
      return [...base].filter(([b, n]) => n >= 20 && (pb.get(b) || 0) < n / 4).map(([b]) => tc(b * 30)); };
    const lostRow = `<tr><th>Blocks where speech vanished</th>` + keys.map(k => {
      if (k === "none") return `<td class="num">—</td>`;
      const l = lostOf(k); return `<td class="num" title="${l.join(", ")}">${l.length}</td>`;
    }).join("") + `<td class="m-note">30-s blocks where the prompt run kept under a quarter of the words; hover for times</td></tr>`;
    const leakRow = `<tr><th>Prompt words per 100 words</th>` + keys.map(k => {
      if (k === "none") return `<td class="num">—</td>`;
      const pw = pwOf(k), c = s.conds.none.segs.concat([]).reduce((n, x) => n + x.text.split(/\s+/).filter(w => pw.has(norm(w))).length, 0);
      const d = s.conds[k].segs.reduce((n, x) => n + x.text.split(/\s+/).filter(w => pw.has(norm(w))).length, 0);
      return `<td class="num">${(100 * c / Math.max(1, s.conds.none.metrics.words)).toFixed(1)} → ${(100 * d / Math.max(1, s.conds[k].metrics.words)).toFixed(1)}</td>`;
    }).join("") + `<td class="m-note">no prompt → prompt; a big rise means the prompt is leaking into the text</td></tr>`;
    const lostR = R === "none" ? [] : lostOf(R);
    const prompts = keys.filter(k => s.conds[k].prompt).map(k => `${esc(D.condNames[k])}: <code>${esc(s.conds[k].prompt)}</code>`).join("<br>");
    return `<section class="m-sample"><div class="m-head"><h2>${esc(s.id)}</h2>` +
      `<div class="m-sub">${s.minutes} min · ${esc(s.licence)} · <a href="${esc(s.source)}">source</a> · detected ${esc(keys.map(k => s.conds[k].detected).join(" / "))}</div>` +
      `<div class="m-sub">${prompts}</div>` +
      `<table class="m-table">${head}${table}${leakRow}${lostRow}</table>` +
      (lostR.length ? `<div class="m-note">Vanished in ${esc(D.condNames[R])}: ${lostR.map(t => `<span class="timecode" data-t="${Number(t.slice(0,2))*60+Number(t.slice(3))}" style="cursor:pointer">[${t}]</span>`).join(" ")}</div>` : "") +
      `<audio controls preload="none" src="${esc(s.audio)}" style="width:100%;margin-top:.6rem"></audio></div>` +
      `<div class="m-cols">${column(D.condNames[L], s.conds[L].segs, L === "none" ? new Set() : pwOf(L))}` +
      `${column(D.condNames[R], s.conds[R].segs, R === "none" ? new Set() : pwOf(R))}</div></section>`;
  }).join("") || `<p class="m-note">No trials for this language yet.</p>`;
}
const langs = [...new Set(D.samples.map(s => s.lang))];
document.getElementById("m-langs").innerHTML = langs.map(l =>
  `<button data-lang="${l}" aria-pressed="${l === lang}">${esc(D.names[l] || l)}</button>`).join("");
function wire(sel, key, apply) {
  const btns = document.querySelectorAll(sel);
  btns.forEach(b => b.addEventListener("click", () => {
    btns.forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false")); apply(b.dataset[key]); }));
}
wire("[data-lang]", "lang", v => { lang = v; render(); });
document.addEventListener("click", e => {
  const t = e.target.closest("[data-t]"), sec = t && t.closest(".m-sample");
  if (!t || !sec) return;
  const a = sec.querySelector("audio"); a.currentTime = Number(t.dataset.t); a.play();
});
wire("[data-span]", "span", v => { span = Number(v); render(); });
wire("[data-left]", "left", v => { left = v; render(); });
wire("[data-right]", "right", v => { right = v; render(); });
wire("[data-mark]", "mark", v => document.body.classList.toggle("m-mark", v === "on"));
wire("[data-scheme]", "scheme", v => { document.documentElement.style.colorScheme = v; });
document.body.classList.add("m-mark");
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
