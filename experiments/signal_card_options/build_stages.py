"""What the build buys, staged. Same real locations, rendered three ways.

    .venv/bin/python experiments/signal_card_options/build_stages.py

  SHIPPED   what HEAD renders today (verified against the code 20 Sep 2026)
  TIER 1    design-signal-card.md §9 tier 1 — frontend only, no open questions
  TIER 2    + the marginal-value rule, editorial quote selection, label rule
"""
import collections, glob, html, json, pathlib, sys, yaml
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from label_rule import sentiment_label, VALENCE as VAL

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
e = html.escape
CAP = 4

REAL = {"Sentiment"}
for f in glob.glob(str(ROOT / "bristlenose/server/codebook/*.yaml")):
    for g in (yaml.safe_load(open(f)).get("groups") or []):
        if isinstance(g, dict) and g.get("name"):
            REAL.add(g["name"])
CARDS = [c for c in json.load(open(HERE / "cards.json"))
         if c["group"] in REAL and c["group"] != "Uncategorised"]
GB = {"ux":"--bn-group-ux","emo":"--bn-group-emo","task":"--bn-group-task","trust":"--bn-group-trust",
      "opp":"--bn-group-opp","sentiment":"--bn-group-sentiment"}
SL = {"ux":5,"emo":6,"task":5,"trust":5,"opp":5,"sentiment":7}
gbg = lambda cs: f"var({GB[cs]})" if cs in GB else "var(--bn-group-none)"
tbg = lambda cs,i: f"var(--bn-{cs}-{(i%SL[cs])+1}-bg)" if cs in SL else "var(--bn-custom-bg)"

def tc(s):
    s=int(s or 0)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}" if s>=3600 else f"{(s%3600)//60:02d}:{s%60:02d}"
def dots(v):
    o="".join(f'<circle cx="{7+i*16}" cy="6" r="5" '+
      ('fill="var(--dot-colour, var(--bn-colour-muted))" opacity="0.7"/>' if (v or 0)>i else
       'fill="none" stroke="var(--dot-colour, var(--bn-colour-muted))" stroke-width="1.2" opacity="0.35"/>')
      for i in range(3))
    return f'<span class="intensity-dots"><svg class="intensity-dots-svg" width="40" height="12" viewBox="0 0 40 12">{o}</svg></span>'
def quote(q,cs):
    tags="".join(f'<span class="badge signal-quote-tag" style="background:{tbg(cs,i)}">{e(t)}</span>'
                 for i,t in enumerate(q["tags"]))
    pid=(f'<span class="speaker"><span class="bn-person-badge"><span class="bn-speaker-badge--split">'
         f'<span class="bn-speaker-badge-code">{e(q["pid"])}</span></span></span></span>' if q["pid"] else "")
    return (f'<blockquote><div class="quote-row"><a class="timecode"><span class="timecode-bracket">[</span>'
            f'{tc(q["t"])}<span class="timecode-bracket">]</span></a><span class="quote-body">'
            f'<span class="quote-text">{e(q["text"])}</span> {pid}{tags}</span>{dots(q["intensity"])}</div></blockquote>')
def grid(c):
    pres={q["pid"] for q in c["quotes"]}; allp=c["all_participants"] or sorted(pres)
    return (f'<span class="participant-grid"><span class="participant-count">{len(pres)}/{len(allp)}</span>'
            + "".join(f'<span class="p-box{" p-present" if p in pres else ""}">{e(p)}</span>' for p in allp)
            + "</span>")
def split_lead(t):
    if "||" in t: a,_,b=t.partition("||")
    elif " — " in t: a,_,b=t.partition(" — ")
    else: a,b=t,""
    a=a.strip().rstrip("—-").strip(); b=b.strip().lstrip("—-").strip()
    if a and a[-1] not in ".!?": a+="."
    return a,(b[0].upper()+b[1:] if b else "")

def label_of(c):
    if c["group"]!="Sentiment": return c["group"]
    qs=[q for q in c["quotes"] if q["sentiment"] in VAL]
    l=sentiment_label(qs)
    return l.text if l else c["group"]

def editorial(c, lab):
    qs=c["quotes"]
    if len(qs)<=CAP: return sorted(qs,key=lambda q:(q["pid"],q["t"]))
    want=({lab} if lab in VAL else
          {v for v,s in VAL.items() if s==("pos" if lab=="Positive" else "neg")}
          if lab in ("Positive","Negative") else set())
    supp=[q for q in qs if q.get("sentiment") in want] or qs
    other=[q for q in qs if q not in supp]
    supp=sorted(supp,key=lambda q:-(q["intensity"] or 1))
    diss=sorted(other,key=lambda q:-(q["intensity"] or 1))
    pick=supp[:CAP-1]
    if diss and (diss[0]["intensity"] or 1)>=2: pick.append(diss[0])
    pick=(pick+supp[CAP-1:])[:CAP]
    return sorted(pick,key=lambda q:(q["pid"],q["t"]))


def card(c, stage, score):
    """stage: 'shipped' | 't1' | 't2'."""
    cs=c["colour_set"]; name,elab=(c["elab"][0],c["elab"][2]) if c["elab"] else (None,None)
    lab = label_of(c) if stage=="t2" else c["group"]
    size = "" if stage=="shipped" else " mk-h-c"

    # ── identity ──
    head=""
    if stage=="shipped":                       # eyebrow on BOTH branches
        head += (f'<span class="signal-card-source">{e(c["location"])}</span>' if name
                 else f'<span class="signal-card-source">{"Section" if c["axis"]=="section" else "Theme"}</span>')
    head += f'<div class="signal-card-location">{e(name or c["location"])}</div>'
    if elab:
        if stage=="shipped":                   # one paragraph, run together
            a,b=split_lead(elab)
            joined = f"{a} {b}" if b else a
            head += (f'<p class="signal-elaboration bn-lead-para mk-legacy">'
                     f'<strong>{e(a)}</strong> {e(b)}</p>' if b
                     else f'<p class="signal-elaboration bn-lead-para mk-legacy">{e(joined)}</p>')
        else:                                  # claim + evidence, two paragraphs
            a,b=split_lead(elab)
            head += f'<p class="signal-elaboration bn-lead-para bn-lead-claim">{e(a)}</p>'
            if b: head += f'<p class="signal-elaboration bn-lead-para bn-lead-rest">{e(b)}</p>'

    # ── quotes ──
    if stage=="shipped":  shown=sorted(c["quotes"],key=lambda q:(q["pid"],q["t"]))[:1]
    elif stage=="t1":     shown=sorted(c["quotes"],key=lambda q:(q["pid"],q["t"]))[:CAP]
    else:                 shown=editorial(c,lab)
    more=len(c["quotes"])-len(shown)
    foot=(f'<button class="signal-card-link signal-card-toggle">Show all {len(c["quotes"])} quotes →</button>'
          if more>0 else '<button class="signal-card-link signal-card-toggle">Hide</button>')

    chip=(f'<div class="signal-card-right"><button class="badge signal-card-hero{size}" '
          f'style="background:{gbg(cs)}"><span class="signal-card-hero-label">{e(lab)}</span>'
          f'<span class="signal-card-hero-score">{score:.2f}</span>'
          f'<span class="signal-card-hero-caret">▾</span></button></div>')
    ident=f'<div class="signal-card-identity">{head}</div>'
    top = (f'<div class="signal-card-top">{ident}{chip}</div>' if stage=="shipped"
           else f'<div class="signal-card-top">{chip}{ident}</div>')   # hero first → float
    return (f'<div class="signal-card mk-{stage}" style="--card-accent:{gbg(cs)}">{top}'
            f'<div class="signal-card-quotes">{"".join(quote(q,cs) for q in shown)}</div>'
            f'<div class="signal-card-footer">{foot}{grid(c)}</div></div>')


def admit(cards):
    kept,cut,seen=[],[],set()
    for c in sorted(cards,key=lambda c:(0 if c["elab"] else 1,-len(c["quotes"]),c["group"])):
        new={q["id"] for q in c["quotes"]}-seen
        if not kept or new: kept.append(c); seen|={q["id"] for q in c["quotes"]}
        else: cut.append(c)
    return kept,cut

BYLOC=collections.defaultdict(list)
for c in CARDS: BYLOC[(c["project"],c["axis"],c["location"])].append(c)

OUT=[]
def run(key, blurb):
    cards=BYLOC[key]
    kept,cut=admit(cards)
    order=sorted(cards,key=lambda c:(0 if c["elab"] else 1,-len(c["quotes"]),c["group"]))
    sc=lambda i:0.61-i*0.11
    OUT.append(f'<section class="mk-sec"><h2>{e(key[2])}</h2><p class="mk-why">'
               f'<code>{e(key[0])}</code> · {len(cards)} cards, '
               f'{sum(len(c["quotes"]) for c in cards)} quote slots over '
               f'{len({q["id"] for c in cards for q in c["quotes"]})} distinct quotes. {blurb}</p>'
               f'<div class="mk-three">')
    for stage,title,note in [
        ("shipped","SHIPPED","eyebrow on every card · one quote · grid · elaboration trapped left"),
        ("t1","TIER 1","chip C · no eyebrow · fused · 4 quotes · float · claim + evidence"),
        ("t2","TIER 2","+ marginal-value rule · editorial quotes · sentiment label")]:
        show = order if stage!="t2" else kept
        cls  = "signal-cards" if stage=="shipped" else "signal-cards mk-fused-v3"
        OUT.append(f'<div class="mk-col"><div class="mk-coltag">{title}</div>'
                   f'<div class="mk-colnote">{note}</div>'
                   f'<div class="analysis-codebook-heading">{e(key[2])}</div>'
                   f'<div class="{cls}">'
                   + "".join(card(c,stage,sc(i)) for i,c in enumerate(show)) + "</div>")
        if stage=="t2" and cut:
            OUT.append(f'<div class="mk-cutnote">{len(cut)} cut: '
                       + ", ".join(e(c["group"]) for c in cut) + "</div>")
        OUT.append("</div>")
    OUT.append("</div></section>")

pick=lambda p,l: next(k for k in BYLOC if k[0]==p and k[2]==l)
run(pick("project-ikea","Search & Sort Results"),
    "Four groups over four quotes — the redundancy case.")
run(pick("project-ikea","Top Navigation"),
    "Six groups over two quotes — the worst in the corpus.")
run(pick("fossda-opensource","Open source project creation and development"),
    "A real study’s card: 46 quotes, weight 94. The tail Q2 has to absorb.")
run(pick("IKEA with uxfriends","IKEA.co.uk Homepage"),
    "The 80% case — one card, all four corners, no rule needed.")

page=f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal card — what the build buys</title>
<style>{(HERE/'theme.css').read_text()}</style><style>{(HERE/'page.css').read_text()}</style>
<style>{(HERE/'v3.css').read_text()}</style><style>
.mk-three {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:var(--bn-space-lg);
  align-items:start; }}
.mk-col {{ min-width:0; }}
.mk-coltag {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); letter-spacing:.06em;
  background:var(--bn-colour-text); color:var(--bn-colour-bg); display:inline-block;
  padding:2px 7px; border-radius:var(--bn-radius-sm); }}
.mk-colnote {{ font-size:var(--bn-text-badge); color:var(--bn-colour-muted);
  margin:var(--bn-space-xs) 0 var(--bn-space-sm); min-height:2.6em; }}
.mk-cutnote {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge);
  color:var(--bn-colour-muted); margin-top:var(--bn-space-sm); }}
.mk-shipped .signal-card-top {{ display:flex; justify-content:space-between;
  align-items:flex-start; gap:var(--bn-space-lg); }}
.mk-shipped .signal-elaboration.mk-legacy {{ color:var(--bn-lead-rest-colour); margin:0; }}
.mk-shipped .signal-elaboration.mk-legacy strong {{ color:var(--bn-lead-colour);
  font-weight:var(--bn-lead-weight); }}
.mk-t1 .signal-card-top, .mk-t2 .signal-card-top {{ display:block; }}
.mk-t1 .signal-card-right, .mk-t2 .signal-card-right {{ float:right;
  margin:0 0 var(--bn-space-sm) var(--bn-space-lg); }}
.mk-t1 .signal-card-quotes, .mk-t2 .signal-card-quotes {{ clear:both; }}
@media (max-width:1100px) {{ .mk-three {{ grid-template-columns:1fr; }} }}
</style></head><body><div class="mk-page">
<header class="mk-head"><h1>Signal card &mdash; what the build buys</h1>
<p>The same real location rendered three ways. <b>SHIPPED</b> is what HEAD renders today,
verified against the code. <b>TIER 1</b> is <code>design-signal-card.md</code> &sect;9 tier 1 &mdash;
frontend only, no open questions. <b>TIER 2</b> adds the marginal-value rule, editorial quote
selection and the sentiment label.</p></header>{''.join(OUT)}
<footer class="mk-foot">Real data. Junk codebooks and <code>Uncategorised</code> excluded.</footer>
</div></body></html>"""
(ROOT/"docs/mockups/signal-card-build-stages.html").write_text(page)
print(f"wrote docs/mockups/signal-card-build-stages.html ({len(page):,} bytes)")
