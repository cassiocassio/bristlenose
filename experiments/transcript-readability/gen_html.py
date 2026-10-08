import json, re
SRC='/Users/cassio/Code/bristlenose/docs/mockups/transcript-paragraph-capitalisation.html'
OUT='/Users/cassio/Code/bristlenose/docs/mockups/transcript-readability-versions.html'
L=open(SRC).read().split('\n')
# shipped CSS: first <style> (lines 7..3551) and the transcript.css 176–255 block (3617..3699), verbatim
i0=L.index('<style>'); i1=i0+L[i0:].index('</style>')
shipped='\n'.join(L[i0:i1+1])
j0=[k for k,l in enumerate(L) if 'transcript.css — lines 176–255' in l][0]-1
j1=j0+L[j0:].index('</style>')
shipped2='\n'.join(L[j0:j1+1])
assert shipped.count('════ bristlenose/theme/templates/transcript.css')==1
V=json.load(open('mock_data.json'))
PASSAGES=[
 dict(id='a',a=75,b=166,title='A question lands in the answer',note='1:15–2:46. Today the moderator\'s "okay what is it" sits at the end of the participant\'s paragraph.'),
 dict(id='b',a=166,b=247,title='A run-on answer',note='2:46–4:07. Lower case, no full stops, "i" for "I".'),
 dict(id='c',a=247,b=367,title='The long paragraph',note='4:07–6:07. Today one paragraph runs 92 seconds and 307 words.'),
 dict(id='d',a=431,b=495,title='The think-aloud prompt',note='7:11–8:15. Today the moderator\'s instructions are labelled as the participant. The stretch where the 2.4 setting leaked its prompt.'),
]
def pick(paras,a,b):
    return [dict(tc=f"{int(p['s']//60):02d}:{int(p['s']%60):02d}",code=p['code'],text=p['text'],cont=p.get('cont',False))
            for p in paras if a<=p['s']<b or (p['s']<a and p['e']>a+(b-a)/2)]
data={'today':{},'v1':{},'v2':{},'v3':{},'v4':{},'v5':{}}
for k in data:
    for P in PASSAGES:
        if k=='v4' and P['a']>=360: data[k][P['id']]=None; continue
        data[k][P['id']]=pick(V[k],P['a'],P['b'])
VERSIONS = [
 dict(id='v1', name='1 · Recommended', flag='re-transcribe · new paragraph rule · display layer',
  caps=True, dim=True,
  table=[
   ['Whisper prompt','A short punctuated prompt on every 30 s window','Whisper copies the prompt\'s style. Without it, each window picks its own style, and filler-heavy speech often comes out lower case with no punctuation.'],
   ['Prompt text','“Hmm, okay. Well, yes, I suppose so, um, and then? Right.”','Hesitation and assent only, nothing a moderator would say. It contains “um”, so fillers are kept: quotes need verbatim input.'],
   ['Prompt language','The session\'s language, decided before transcribing','An English prompt on Japanese audio produced English loops. No prompt if the language has no reviewed one.'],
   ['condition_on_previous_text','False (unchanged)','True locks a bad style in for the rest of the file and brings back repetition loops.'],
   ['compression_ratio_threshold','1.8 (unchanged)','It caught the prompt-leak at 7:23 that 2.4 let through (version 5). Costs some repeatability: 23 of 159 segments re-decoded by sampling.'],
   ['Paragraph break','Speaker change, or a gap over 2 s (unchanged)','Every tool breaks at turns; the gap rule is today\'s.'],
   ['Length rule','Once a paragraph reaches 60 words, end it at the next sentence end, inside a Whisper segment too (timed from the word timings)','About four sentences for this speaker; human-paragraphed talks average 4.4. Never cuts mid-sentence.'],
   ['Which text is drawn','The transcript text, Whisper\'s own spelling','One transcription, so the text and the word timings agree.'],
   ['First letter','Capital where a sentence begins (capitalisation mockup, option C)','A new turn or a new sentence starts with a capital; a mid-sentence continuation does not.'],
   ['Fillers','um, uh, er, erm, hmm drawn in the muted colour (proposed style)','Kept in full for verbatim, de-emphasised for scanning. Ambiguous ones (“like”, “you know”) left alone.'],
   ['Stored text changed?','Only by re-transcribing; the display layer changes nothing','Exports and the agent read the stored text.'],
   ['Applies to','Sessions transcribed after the change','Existing projects keep their transcripts and their splits.'],
   ['Measured on s1 (18 min)','277 sentences (today 72) · longest unpunctuated run 24 words (today 681) · no prompt leak · 52 s to transcribe (today 84 s)','Local runs on an M2 Max, large-v3-turbo. Two runs of the same setting gave the same counts within two words.'],
  ],
  pros=['Reads as sentences, with capitals and full stops, and keeps every word.','Questions come out as their own lines, so the moderator gets them back.','Paragraphs are short enough to scan (longest here: 80 words).'],
  cons=['Needs re-transcription, so it only reaches new sessions.','A small patch to mlx-whisper that has to be re-checked on every upgrade.','Fillers are now written out (“Um,” “uh,”); dimming is what keeps them quiet.']),
 dict(id='v2', name='2 · Whisper fix only', flag='re-transcribe · today\'s paragraph rule · no display layer',
  caps=False, dim=False,
  table=[
   ['Whisper prompt','As version 1','—'],
   ['Prompt text','As version 1','—'],
   ['compression_ratio_threshold','1.8 (unchanged)','—'],
   ['Paragraph break','Speaker change, or a gap over 2 s (today\'s rule, nothing added)','Shows what the Whisper fix does on its own.'],
   ['Length rule','None','—'],
   ['Which text is drawn','The transcript text','—'],
   ['First letter','As transcribed','—'],
   ['Fillers','As transcribed, full strength','—'],
   ['Measured on s1','25 paragraphs; the longest is 692 words','Punctuated segments are longer, so the 2 s merge swallows more of them.'],
  ],
  pros=['Smallest change: stage 5 only.','Text is punctuated and cased.'],
  cons=['Paragraphs get longer, not shorter: the whole answer becomes one block.','Fillers at full strength now that they are written out.']),
 dict(id='v3', name='3 · Display only, no re-transcription', flag='today\'s transcript · display layer only',
  caps=True, dim=True,
  table=[
   ['Whisper','Not re-run','What an existing project could get without re-transcribing.'],
   ['Which text is drawn','The stored text instead of Whisper\'s word list','In this project the two come from different Whisper runs; the stored text is usually the better punctuated of the two.'],
   ['Length rule','A visual break at a sentence end every ~60 words, inside one paragraph: no new timecode or badge','Display only, so splits and quotes are untouched.'],
   ['First letter','Capital where a sentence begins (option C)','As version 1.'],
   ['Fillers','Dimmed, as version 1','As version 1.'],
   ['Stored text changed?','No','—'],
   ['Measured on s1','48 drawn blocks; the longest is still 300 words','Where the stored text has no full stops there is nothing to break at.'],
  ],
  pros=['Works on every existing project, now.','No change to the pipeline or to splits.'],
  cons=['Cannot fix what the text never had: unpunctuated stretches stay one block, in lower case.','Wrong speaker edges stay wrong (7:11 is still the participant).','The “(Speaker A)” label in the stored text shows where a paragraph has no word timings.']),
 dict(id='v4', name='4 · Prompt without fillers', flag='re-transcribe · fillers dropped by Whisper · 1:00–6:00 only',
  caps=True, dim=True,
  table=[
   ['Prompt text','“Hello. Welcome, everyone. Let\'s begin.”','A clean prompt, no fillers.'],
   ['compression_ratio_threshold','1.8','As version 1.'],
   ['Length rule','60 words, at a sentence end, between Whisper segments only','This run kept no word timings, so it cannot break inside a segment.'],
   ['First letter / fillers','As version 1','—'],
   ['Measured on the 1:00–6:00 excerpt','737 words against 864 with a prompt that contains fillers; 65 sentences','Whisper drops fillers, and some other words with them.'],
  ],
  pros=['Reads cleanest of all.','Shortest sentences.'],
  cons=['It is no longer verbatim: Whisper decides what to drop, and nobody can see what it dropped.','Quotes lose their “...” for hesitations, which carry meaning (Clark & Fox Tree).','Only run on 1:00–6:00, so the last passage is empty.']),
 dict(id='v5', name='5 · Faster, threshold 2.4', flag='re-transcribe · 2.4 threshold · shows the prompt leak',
  caps=True, dim=True,
  table=[
   ['Prompt text','“Okay, so, um, tell me about it. Well, I think it\'s good, you know? Yeah.”','The first prompt tried. It contains an interview phrase.'],
   ['compression_ratio_threshold','2.4 (Whisper\'s default)','No fallback sampling: deterministic, and 35 s instead of 52 s.'],
   ['Length rule / first letter / fillers','As version 1','—'],
   ['Measured on s1','282 sentences; one segment replaced the moderator\'s words with “Tell me about it.” four times (7:23)','At 2.4 nothing re-decodes a looping window.'],
  ],
  pros=['Fastest and fully repeatable.'],
  cons=['The prompt leaked into the transcript, replacing real speech: see 7:23.','Heard “IKEA.com” as “our kid at com”.']),
]
DATA=json.dumps(dict(passages=PASSAGES,data=data,versions=VERSIONS),ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
page=f'''<!DOCTYPE html>
<html lang="en" data-color-theme="default" data-platform="desktop">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcript readability versions</title>
{shipped}
<style>
/* ============================================================================
   MOCKUP CHROME — not the product. Prefixed `m-` throughout.
   The shipped CSS above is copied verbatim from transcript-paragraph-
   capitalisation.html, whose generator inlined it from the tree on 6 Oct 2026.
   ========================================================================= */
html {{ color-scheme: light; }}
body {{ padding: 0; }}
.m-wrap {{ max-width: 1440px; margin: 0 auto; padding: 2rem clamp(1rem, 3vw, 2rem) 6rem; display: flex; flex-direction: column; gap: 1.6rem; }}
.m-title {{ font-size: var(--bn-text-display); font-weight: var(--bn-weight-strong); margin: 0; }}
.m-lede {{ color: var(--bn-colour-muted); max-width: 90ch; margin: .4rem 0 0; }}
.m-h2 {{ font-size: var(--bn-text-heading); font-weight: var(--bn-weight-emphasis); margin: 0 0 .2rem; }}
.m-h2 small {{ font-weight: var(--bn-weight-normal); color: var(--bn-colour-muted); font-size: var(--bn-text-label); margin-left: .5rem; }}
.m-toolbar {{ position: sticky; top: 0; z-index: 300; display: flex; flex-wrap: wrap; gap: .8rem 1.6rem; align-items: center;
  padding: .55rem .9rem; background: var(--bn-colour-bg); border: 1px solid var(--bn-colour-border);
  border-radius: var(--bn-radius-md); box-shadow: 0 2px 8px var(--bn-colour-shadow); font-size: var(--bn-text-caption); }}
.m-group {{ display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }}
.m-group > b {{ font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); }}
.m-seg {{ display: inline-flex; flex-wrap: wrap; border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-md); overflow: hidden; }}
.m-seg button {{ all: unset; cursor: pointer; padding: .25rem .6rem; color: var(--bn-colour-text); }}
.m-seg button + button {{ border-left: 1px solid var(--bn-colour-border); }}
.m-seg button[aria-pressed="true"] {{ background: var(--bn-colour-accent); color: #fff; }}
.m-seg button:focus-visible {{ outline: 2px solid var(--bn-colour-accent); outline-offset: -2px; }}
.m-key {{ display: flex; flex-wrap: wrap; gap: 1rem; font-size: var(--bn-text-caption); color: var(--bn-colour-muted); }}
.m-key span {{ display: inline-flex; align-items: center; gap: .4rem; }}
.m-key i {{ width: 18px; height: 12px; border-radius: 3px; display: inline-block; }}
.m-key .k-art {{ border: 1px solid var(--bn-colour-border); background: var(--bn-colour-bg); }}
.m-key .k-com {{ background: repeating-linear-gradient(135deg, var(--bn-colour-hover) 0 4px, transparent 4px 8px); border-left: 2px solid var(--bn-colour-muted); }}
.m-pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; align-items: start; }}
@media (max-width: 900px) {{ .m-pair {{ grid-template-columns: 1fr; }} }}
.m-frame {{ border: 1px solid var(--bn-colour-border); border-radius: var(--bn-radius-lg); overflow: hidden; background: var(--bn-colour-bg); }}
.m-chrome {{ display: flex; justify-content: space-between; gap: .5rem; align-items: baseline; padding: .4rem .75rem;
  font-family: var(--bn-font-mono); font-size: var(--bn-text-badge); color: var(--bn-colour-muted);
  background: var(--bn-colour-hover); border-bottom: 1px solid var(--bn-colour-border); }}
.m-chrome b {{ color: var(--bn-colour-text); font-weight: var(--bn-weight-emphasis); }}
.m-stage {{ padding: .4rem 1.1rem 1rem; }}
.m-empty {{ color: var(--bn-colour-muted); font-size: var(--bn-text-label); padding: 1rem 0; }}
/* The margin-annotation column only exists at full page width; a half-width frame drops it. */
.m-stage .transcript-body {{ grid-template-columns: 4.5rem 2.2rem 1fr; margin-top: var(--bn-space-sm); }}
.m-commentary {{ background: repeating-linear-gradient(135deg, var(--bn-colour-hover) 0 4px, transparent 4px 8px);
  border-left: 3px solid var(--bn-colour-muted); border-radius: var(--bn-radius-md); padding: 1rem 1.2rem;
  font-size: var(--bn-text-label); line-height: 1.55; }}
.m-commentary > .m-label {{ font-family: var(--bn-font-mono); font-size: var(--bn-text-badge); text-transform: uppercase;
  letter-spacing: .08em; color: var(--bn-colour-muted); margin: 0 0 .5rem; display: block; }}
.m-commentary p {{ margin: 0 0 .6rem; max-width: 100ch; }}
.m-commentary ul {{ margin: 0 0 .6rem; padding-left: 1.2rem; }}
.m-commentary code {{ font-family: var(--bn-font-mono); font-size: .92em; }}
.m-note {{ color: var(--bn-colour-muted); font-size: var(--bn-text-label); margin: 0 0 .5rem; }}
.m-table {{ width: 100%; border-collapse: collapse; background: var(--bn-colour-bg); font-size: var(--bn-text-label); }}
.m-table th, .m-table td {{ text-align: left; vertical-align: top; padding: .45rem .6rem; border-bottom: 1px solid var(--bn-colour-border); }}
.m-table th {{ font-weight: var(--bn-weight-emphasis); color: var(--bn-colour-muted); font-size: var(--bn-text-caption); }}
.m-table td:first-child {{ font-weight: var(--bn-weight-emphasis); width: 18%; }}
.m-table td:nth-child(2) {{ width: 34%; }}
.m-pc {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: .9rem; }}
.m-pc h3 {{ font-size: var(--bn-text-label); font-weight: var(--bn-weight-emphasis); margin: 0 0 .3rem; }}
.m-showchanges .m-changed {{ text-decoration: underline dotted var(--bn-colour-accent); text-underline-offset: 3px;
  background: color-mix(in srgb, var(--bn-colour-accent) 14%, transparent); }}
/* PROPOSED, not shipped: a filler drawn in the muted text colour. */
.m-filler {{ color: var(--bn-colour-muted); }}
.m-nofill .m-filler {{ color: inherit; }}
</style>
</head>
<body>
<div class="m-wrap">
<header>
  <h1 class="m-title">Transcript readability: today against the proposed versions</h1>
  <p class="m-lede">IKEA with uxfriends, s1. Left: what the transcript page draws today. Right: the same stretches, re-transcribed locally with the proposed Whisper settings, then put through the version's paragraph and display rules. Pick a version at the top. The research is in <code>docs/design-transcript-readability.md</code>.</p>
</header>
<div class="m-toolbar" role="group" aria-label="Mockup switches">
  <div class="m-group"><b>Version</b><span class="m-seg" id="m-versions"></span></div>
  <div class="m-group"><b>Appearance</b><span class="m-seg"><button data-scheme="light" aria-pressed="true">Light</button><button data-scheme="dark" aria-pressed="false">Dark</button></span></div>
  <div class="m-group"><b>Type</b><span class="m-seg"><button data-platform="desktop" aria-pressed="true">Mac app (SF)</button><button data-platform="web" aria-pressed="false">Browser (Inter)</button></span></div>
  <div class="m-group"><b>Changed letters</b><span class="m-seg"><button data-show="on" aria-pressed="false">Show</button><button data-show="off" aria-pressed="true">Hide</button></span></div>
</div>
<div class="m-key"><span><i class="k-art"></i>Artefact: the transcript as drawn</span><span><i class="k-com"></i>Commentary: not the product</span></div>
<div id="m-passages"></div>
<aside class="m-commentary" id="m-why"></aside>
<aside class="m-commentary"><span class="m-label">How this was made</span>
<p><b>Left column.</b> The project's paragraphs from its database, with word timings joined by time exactly as the importer does (<code>_enrich_words_from_intermediate</code>), so a paragraph shows Whisper's word list when the words pass the 0.9 match and its stored text when they do not. In this project the stored text comes from a 16 Jul Whisper run and the words from a 27 Aug one. Where the stored text is drawn it carries its “(Speaker A)” label; I found nothing that strips it on the page.</p>
<p><b>Right column.</b> Fresh local transcriptions of the same audio (mlx-whisper 0.4.3, large-v3-turbo, M2 Max, 6 Oct 2026; no paid calls). <b>Speaker badges are borrowed</b>: speaker identification was not re-run (its pass may call an LLM), so each new sentence takes the speaker of today's paragraph it overlaps most. Where today's speakers are wrong, the borrowed ones can be too.</p>
<p><b>Shown at full strength.</b> The page draws participant paragraphs with no quote in them at 60% opacity. Every paragraph here is drawn as quoted, so the text is comparable. The dimmed filler style is the one new style on the page, and is a proposal.</p>
</aside>
</div>
<script>
const M = {DATA};
const FILL = /^(um+|uh+|er|erm|hmm+|mm+)([,.?!…]*)$/i;
const esc = s => s.replace(/[&<>"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]);
const badge = code => `<span class="bn-person-badge"><span class="bn-speaker-badge--split"><span class="bn-speaker-badge-code">${{code}}</span></span></span>`;
function body(text, v, startsSentence) {{
  let words = text.split(/\\s+/);
  let first = true, out = [];
  for (let w of words) {{
    let h = esc(w);
    if (v && v.dim && FILL.test(w)) h = `<span class="m-filler">${{h}}</span>`;
    if (first && v && v.caps && startsSentence) {{
      const up = w.charAt(0).toLocaleUpperCase("en");
      if (up !== w.charAt(0)) h = `<span class="m-changed">${{esc(up)}}</span>` + h.replace(/^(<span class="m-filler">)?./, "$1");
    }}
    first = false; out.push(h);
  }}
  return out.join(" ");
}}
function transcript(paras, v) {{
  return paras.map((p, i) => {{
    const prev = paras[i-1];
    const starts = !prev || prev.code !== p.code || /[.?!…]["”’)]?$/.test(prev.text);
    const mod = p.code.startsWith("m");
    const tc = p.cont ? "" : `<span class="timecode-bracket">[</span>${{p.tc}}<span class="timecode-bracket">]</span>`;
    return `<div class="transcript-segment segment-quoted${{mod ? " segment-moderator" : ""}}">` +
      `<span class="timecode">${{tc}}</span><span class="segment-speaker">${{p.cont ? "" : badge(p.code)}}</span>` +
      `<div class="segment-body">${{body(p.text, v, starts && !p.cont)}}</div></div>`;
  }}).join("");
}}
function frame(title, flag, paras, v) {{
  const inner = paras === null ? `<div class="m-empty">Not transcribed with this setting: this run covered 1:00–6:00 only.</div>`
    : `<div class="transcript-body">${{transcript(paras, v)}}</div>`;
  return `<div class="m-frame"><div class="m-chrome"><span><b>${{title}}</b></span><span>${{flag}}</span></div><div class="m-stage">${{inner}}</div></div>`;
}}
let current = "v1";
function render() {{
  const v = M.versions.find(x => x.id === current);
  document.getElementById("m-passages").innerHTML = M.passages.map(P =>
    `<section><h2 class="m-h2">${{P.title}}<small>${{P.note}}</small></h2><div class="m-pair">` +
    frame("Today", "as the page draws it", M.data.today[P.id], null) +
    frame(v.name, v.flag, M.data[v.id][P.id], v) + `</div></section>`).join("");
  const rows = v.table.map(r => `<tr><td>${{esc(r[0])}}</td><td>${{esc(r[1])}}</td><td>${{esc(r[2])}}</td></tr>`).join("");
  document.getElementById("m-why").innerHTML = `<span class="m-label">Commentary · ${{esc(v.name)}}</span>` +
    `<table class="m-table"><thead><tr><th>Choice</th><th>Value</th><th>Rationale</th></tr></thead><tbody>${{rows}}</tbody></table>` +
    `<div class="m-pc"><div><h3>For</h3><ul>${{v.pros.map(x=>`<li>${{esc(x)}}</li>`).join("")}}</ul></div>` +
    `<div><h3>Against</h3><ul>${{v.cons.map(x=>`<li>${{esc(x)}}</li>`).join("")}}</ul></div></div>`;
}}
const vs = document.getElementById("m-versions");
vs.innerHTML = M.versions.map(v => `<button data-v="${{v.id}}" aria-pressed="${{v.id===current}}">${{esc(v.name)}}</button>`).join("");
function wire(sel, key, apply) {{
  const btns = document.querySelectorAll(sel);
  btns.forEach(b => b.addEventListener("click", () => {{
    btns.forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false")); apply(b.dataset[key]); }}));
}}
const root = document.documentElement;
wire("[data-v]", "v", id => {{ current = id; render(); }});
wire("[data-scheme]", "scheme", s => {{ root.style.colorScheme = s; }});
wire("[data-platform]", "platform", p => {{ p === "desktop" ? root.setAttribute("data-platform", "desktop") : root.removeAttribute("data-platform"); }});
wire("[data-show]", "show", s => {{ document.body.classList.toggle("m-showchanges", s === "on"); }});
render();
</script>
</body>
</html>
'''
open(OUT,'w').write(page)
print(len(page))
