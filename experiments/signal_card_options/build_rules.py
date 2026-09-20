"""Every rule, firing, on real data — with what it would have done otherwise.

    .venv/bin/python experiments/signal_card_options/build_rules.py

The review artefact: each rule stated formally, a real card where it fires, the
counterfactual beside it, and how often it fires across the corpus. Chip labels
go through en/enums.json, so they read `Frustration`, not the raw value.
"""
import collections, glob, html, json, pathlib, sys, yaml
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from label_rule import sentiment_label, VALENCE as VAL, MIN_WEIGHT

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
e = html.escape
CAP = 4

ENUMS = json.load(open(ROOT / "bristlenose/locales/en/enums.json")).get("sentiment", {})
display = lambda s: ENUMS.get(s, s)          # the i18n path the live card misses

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
    return ('<span class="intensity-dots"><svg class="intensity-dots-svg" width="40" height="12" '
            'viewBox="0 0 40 12">' + "".join(
        f'<circle cx="{7+i*16}" cy="6" r="5" ' +
        ('fill="var(--dot-colour, var(--bn-colour-muted))" opacity="0.7"/>' if (v or 0)>i else
         'fill="none" stroke="var(--dot-colour, var(--bn-colour-muted))" stroke-width="1.2" opacity="0.35"/>')
        for i in range(3)) + "</svg></span>")
def quote(q, cs, mark=""):
    tags="".join(f'<span class="badge signal-quote-tag" style="background:{tbg(cs,i)}">{e(t)}</span>'
                 for i,t in enumerate(q["tags"]))
    pid=(f'<span class="speaker"><span class="bn-person-badge"><span class="bn-speaker-badge--split">'
         f'<span class="bn-speaker-badge-code">{e(q["pid"])}</span></span></span></span>' if q["pid"] else "")
    return (f'<blockquote class="{mark}"><div class="quote-row"><a class="timecode">'
            f'<span class="timecode-bracket">[</span>{tc(q["t"])}<span class="timecode-bracket">]</span></a>'
            f'<span class="quote-body"><span class="quote-text">{e(q["text"])}</span> {pid}{tags}</span>'
            f'{dots(q["intensity"])}</div></blockquote>')
def grid(c):
    pres={q["pid"] for q in c["quotes"]}; allp=c["all_participants"] or sorted(pres)
    return (f'<span class="participant-grid"><span class="participant-count">{len(pres)}/{len(allp)}</span>'
            +"".join(f'<span class="p-box{" p-present" if p in pres else ""}">{e(p)}</span>' for p in allp)+"</span>")
def split_lead(t):
    if "||" in t: a,_,b=t.partition("||")
    elif " — " in t: a,_,b=t.partition(" — ")
    else: a,b=t,""
    a=a.strip().rstrip("—-").strip(); b=b.strip().lstrip("—-").strip()
    if a and a[-1] not in ".!?": a+="."
    return a,(b[0].upper()+b[1:] if b else "")

def chip_label(c):
    if c["group"] != "Sentiment": return c["group"], None
    qs=[q for q in c["quotes"] if q["sentiment"] in VAL]
    l=sentiment_label(qs)
    if not l: return c["group"], None
    return (display(l.text) if l.kind=="value" else l.text), l

def editorial(c, lab):
    qs=c["quotes"]
    if len(qs)<=CAP: return sorted(qs,key=lambda q:(q["pid"],q["t"])), set()
    want=({k for k in VAL if display(k)==lab} or
          ({v for v,s in VAL.items() if s==("pos" if lab=="Positive" else "neg")}
           if lab in ("Positive","Negative") else set()))
    supp=[q for q in qs if q.get("sentiment") in want] or qs
    other=[q for q in qs if q not in supp]
    supp=sorted(supp,key=lambda q:-(q["intensity"] or 1))
    diss=sorted(other,key=lambda q:-(q["intensity"] or 1))
    pick=supp[:CAP-1]; dis=set()
    if diss and (diss[0]["intensity"] or 1)>=2:
        pick.append(diss[0]); dis={diss[0]["id"]}
    pick=(pick+supp[CAP-1:])[:CAP]
    return sorted(pick,key=lambda q:(q["pid"],q["t"])), dis


def card(c, *, sel="editorial", lead_break=True, eyebrow=False, score=0.42,
         flag=None, dim=False, note=""):
    cs=c["colour_set"]; name,elab=(c["elab"][0],c["elab"][2]) if c["elab"] else (None,None)
    lab,_ = chip_label(c)
    head = f'<span class="signal-card-source">{e(c["location"])}</span>' if eyebrow else ""
    head += f'<div class="signal-card-location">{e(name or c["location"])}</div>'
    if elab:
        a,b = split_lead(elab)
        if lead_break:
            head += f'<p class="signal-elaboration bn-lead-para bn-lead-claim">{e(a)}</p>'
            if b: head += f'<p class="signal-elaboration bn-lead-para bn-lead-rest">{e(b)}</p>'
        else:
            head += (f'<p class="signal-elaboration bn-lead-para mk-legacy">'
                     f'<strong>{e(a)}</strong> {e(b)}</p>')
    if sel=="editorial":   shown,dis = editorial(c, lab)
    elif sel=="chrono":    shown,dis = sorted(c["quotes"],key=lambda q:(q["pid"],q["t"]))[:CAP], set()
    else:                  shown,dis = sorted(c["quotes"],key=lambda q:(q["pid"],q["t"]))[:1], set()
    more=len(c["quotes"])-len(shown)
    foot=(f'<button class="signal-card-link signal-card-toggle">Show all {len(c["quotes"])} quotes →</button>'
          if more>0 else '<button class="signal-card-link signal-card-toggle">Hide</button>')
    pre=f'<span class="mk-chip-flag">{e(flag)}:</span>' if flag else ""
    chip=(f'<div class="signal-card-right"><button class="badge signal-card-hero mk-h-c" '
          f'style="background:{gbg(cs)}">{pre}<span class="signal-card-hero-label">{e(lab)}</span>'
          f'<span class="signal-card-hero-score">{score:.2f}</span>'
          f'<span class="signal-card-hero-caret">▾</span></button></div>')
    n=f'<div class="mk-note">{note}</div>' if note else ""
    return (f'<div class="signal-card mk-v3{" mk-dim" if dim else ""}" style="--card-accent:{gbg(cs)}">{n}'
            f'<div class="signal-card-top">{chip}<div class="signal-card-identity">{head}</div></div>'
            f'<div class="signal-card-quotes">'
            + "".join(quote(q,cs,"mk-dissent" if q["id"] in dis else "") for q in shown)
            + f'</div><div class="signal-card-footer">{foot}{grid(c)}</div></div>')

BYLOC=collections.defaultdict(list)
for c in CARDS: BYLOC[(c["project"],c["axis"],c["location"])].append(c)
def admit(cards):
    kept,cut,seen=[],[],set()
    for c in sorted(cards,key=lambda c:(0 if c["elab"] else 1,-len(c["quotes"]),c["group"])):
        new={q["id"] for q in c["quotes"]}-seen
        if not kept or new: kept.append(c); seen|={q["id"] for q in c["quotes"]}
        else: cut.append(c)
    return kept,cut

OUT=[]
def rule(n, name, formal, freq):
    OUT.append(f'<section class="mk-sec" id="r{n}"><div class="mk-rulehead">'
               f'<span class="mk-rulenum">{n}</span><h2>{name}</h2></div>'
               f'<pre class="mk-formal">{formal}</pre>'
               f'<p class="mk-freq">{freq}</p>')
def pair(a_t, a_h, b_t, b_h):
    OUT.append(f'<div class="mk-pair"><div class="mk-col"><div class="mk-coltag mk-was">{a_t}</div>{a_h}</div>'
               f'<div class="mk-col"><div class="mk-coltag">{b_t}</div>{b_h}</div></div>')
def one(h): OUT.append(f'<div class="mk-single">{h}</div>')
def ends(): OUT.append("</section>")
def pick(p,l): return next(k for k in BYLOC if k[0]==p and k[2]==l)
def find(p,l,g): return next(c for c in BYLOC[pick(p,l)] if c["group"]==g)

# ── rule 1 — the label ladder ─────────────────────────────────────────────
sent=[c for c in CARDS if c["group"]=="Sentiment" and
      any(q["sentiment"] in VAL for q in c["quotes"])]
byrung=collections.defaultdict(list)
for c in sent:
    l=sentiment_label([q for q in c["quotes"] if q["sentiment"] in VAL])
    byrung[l.why].append(c)
counts=collections.Counter(sentiment_label([q for q in c["quotes"] if q["sentiment"] in VAL]).kind
                           for c in sent)
rule(1,"The label ladder",
"""1.  nothing opposing          →  name the leading feeling     MEASURED 5/5
2.  both directions,
    total weight ≥ 7          →  name the leading feeling     MEASURED 10/10
3.  both directions, thin     →  "Mixed sentiments"           12 cases, 8 / 2 / 2

    weight = Σ (count × intensity).  `surprise` is NEUTRAL and never
    makes a card mixed.""",
f"Over {len(sent)} real sentiment locations: <b>{counts['value']} name a feeling</b> "
f"({100*counts['value']//len(sent)}%), {counts['valence']} name a direction, "
f"{counts['mixed']} say <code>Mixed sentiments</code>.")
for why, title in [("nothing opposing","RUNG 1 — nothing opposing"),
                   ("clashing, but enough feeling to call it","RUNG 2 — clashing, weight ≥ 7"),
                   (None,"RUNG 3 — clashing, thin")]:
    pool = byrung[why] if why else [c for c in sent if
        sentiment_label([q for q in c["quotes"] if q["sentiment"] in VAL]).kind=="mixed"]
    if not pool: continue
    c = max(pool, key=lambda c: len(c["quotes"]))
    qs=[q for q in c["quotes"] if q["sentiment"] in VAL]
    w=sum(q["intensity"] or 1 for q in qs)
    comp=" · ".join(f"{k} {v}" for k,v in
        collections.Counter((q["sentiment"],q["intensity"]) for q in qs).items()) if False else \
        " · ".join(f"{k} {v}" for k,v in sorted(
            collections.Counter({s:sum(q["intensity"] or 1 for q in qs if q["sentiment"]==s)
                                 for s in {q["sentiment"] for q in qs}}).items(),
            key=lambda kv:-kv[1]))
    one(f'<div class="mk-coltag">{title}</div>'
        f'<div class="mk-note">weight {w} &middot; {e(comp)}</div>'
        f'<div class="analysis-codebook-heading">{e(c["location"])}</div>'
        f'<div class="signal-cards mk-fused-v3">{card(c, score=0.38)}</div>')
ends()

# ── rule 2 — surprise is neutral ──────────────────────────────────────────
neu=[c for c in sent if any(VAL.get(q["sentiment"])=="neu" for q in c["quotes"])
     and not ({VAL.get(q["sentiment"]) for q in c["quotes"]} >= {"pos","neg"})]
rule(2,"<code>surprise</code> is neutral, and never makes a card mixed",
"""mixed  requires  positive AND negative present.
       a neutral quote alone does not qualify.""",
f"MEASURED: <b>4 cards</b> were labelled <code>Mixed sentiments</code> on a neutral quote alone. "
"The worst carried 76 units of positive weight against 4 of neutral.")
if neu:
    c=max(neu,key=lambda c: sum(q["intensity"] or 1 for q in c["quotes"]))
    lab,_=chip_label(c)
    comp=" · ".join(f"{s} {sum(q['intensity'] or 1 for q in c['quotes'] if q['sentiment']==s)}"
                    for s in sorted({q["sentiment"] for q in c["quotes"] if q["sentiment"] in VAL}))
    pair("WITHOUT THE RULE — “Mixed sentiments”",
         f'<div class="mk-note">{e(comp)}</div><div class="signal-cards mk-fused-v3">'
         + card(c,score=0.47).replace(f'>{e(lab)}<', '>Mixed sentiments<') + "</div>",
         f"WITH — “{e(lab)}”",
         f'<div class="mk-note">{e(comp)}</div><div class="signal-cards mk-fused-v3">'
         + card(c,score=0.47) + "</div>")
ends()

# ── rule 3 — the marginal-value rule ──────────────────────────────────────
tot=sum(len(v) for v in BYLOC.values())
kept_n=sum(len(admit(v)[0]) for v in BYLOC.values())
rule(3,"The marginal-value rule",
"""strongest first;  admit a later card only if it brings a quote
no kept card has already shown.""",
f"MEASURED: <b>{tot} cards in, {kept_n} kept, {tot-kept_n} cut</b> across {len(BYLOC)} locations.")
k=pick("project-ikea","Top Navigation"); kept,cut=admit(BYLOC[k])
OUT.append(f'<div class="mk-pair"><div class="mk-col"><div class="mk-coltag mk-was">'
           f'WITHOUT — {len(BYLOC[k])} cards</div>'
           f'<div class="analysis-codebook-heading">{e(k[2])}</div>'
           f'<div class="signal-cards mk-fused-v3">'
           + "".join(card(c,score=0.30-i*0.03) for i,c in enumerate(
               sorted(BYLOC[k],key=lambda c:(0 if c["elab"] else 1,-len(c["quotes"]),c["group"]))))
           + '</div></div><div class="mk-col"><div class="mk-coltag">'
           f'WITH — {len(kept)} kept</div>'
           f'<div class="analysis-codebook-heading">{e(k[2])}</div>'
           f'<div class="signal-cards mk-fused-v3">'
           + "".join(card(c,score=0.30-i*0.03) for i,c in enumerate(kept)) + "</div>"
           f'<div class="mk-cutnote">cut, every quote already shown: '
           + ", ".join(e(c["group"]) for c in cut) + "</div></div></div>")
ends()

# ── rule 4 — editorial quote selection ────────────────────────────────────
rule(4,"Editorial quote selection",
"""supporting = quotes whose sentiment supports the label
pick       = strongest 3 supporting
if the strongest dissenter has intensity ≥ 2:  pick.append(it)
return sorted(pick, key=(participant, time))     ← ordering unchanged""",
"MEASURED over the 20 cards where selection matters: cards showing <b>no supporting quote</b> "
"fall 3 → <b>0</b>, and cards showing a dissenter <i>rise</i> 13 → <b>16</b>. "
"The highlighted quote is the reserved dissenter.")
c=find("fossda-opensource","Corporate career transitions and workplace dynamics","Sentiment")
lab,_=chip_label(c)
pair("CHRONOLOGICAL — (participant, time)",
     f'<div class="mk-note">chip says <b>{e(lab)}</b>; none of the four support it</div>'
     f'<div class="signal-cards mk-fused-v3">{card(c, sel="chrono", score=0.55)}</div>',
     "EDITORIAL",
     f'<div class="mk-note">thesis grounded, dissenter kept and marked</div>'
     f'<div class="signal-cards mk-fused-v3">{card(c, score=0.55)}</div>')
ends()

# ── rule 5 — claim and evidence ───────────────────────────────────────────
lng=max((c for c in CARDS if c["elab"]), key=lambda c: len(c["elab"][2]))
rule(5,"Claim and evidence are two paragraphs",
"""`||`  is a paragraph break, not a syntactic pause.
      claim in full ink · blank line · evidence in a tint
      a legacy em dash joining the halves is stripped.""",
f"The prompt has specified this since v0.2.0 and <code>renderLead</code> has never rendered it — "
f"it emits <code>&lt;strong&gt;{{lead}}&lt;/strong&gt; {{rest}}</code>, a single space. "
f"Real card, {len(lng['elab'][2])}-character elaboration.")
pair("SHIPPED — one paragraph, run together",
     f'<div class="signal-cards mk-fused-v3">{card(lng, lead_break=False, score=0.47)}</div>',
     "WITH THE BREAK",
     f'<div class="signal-cards mk-fused-v3">{card(lng, score=0.47)}</div>')
ends()

# ── rule 6 — the fused stack ──────────────────────────────────────────────
solo=sum(1 for v in BYLOC.values() if len(admit(v)[0])==1)
rule(6,"Fusing, and the case that needs no rule",
""".signal-card:first-child  → top corners
.signal-card:last-child   → bottom corners
.signal-card:not(:first-child) { border-top: none }

an only child is BOTH first and last, so it keeps all four.""",
f"MEASURED: <b>{solo} of {len(BYLOC)} locations</b> ({100*solo//len(BYLOC)}%) keep exactly one "
"card after the rule — the common case is the one with no rule written for it.")
k2=pick("project-ikea","Search & Sort Results"); kept2,_=admit(BYLOC[k2])
pair("A RUN — seam is each card's own border",
     f'<div class="analysis-codebook-heading">{e(k2[2])}</div>'
     f'<div class="signal-cards mk-fused-v3">'
     + "".join(card(c,score=0.61-i*0.14) for i,c in enumerate(kept2[:2])) + "</div>",
     "ONE CARD — all four corners, no special case",
     f'<div class="analysis-codebook-heading">IKEA.co.uk Homepage</div>'
     f'<div class="signal-cards mk-fused-v3">'
     + card(find("IKEA with uxfriends","IKEA.co.uk Homepage","Sentiment"),score=0.44) + "</div>")
ends()

# ── rule 7 — the chip ─────────────────────────────────────────────────────
rule(7,"The chip — one patch of colour",
"""ONE button, one background.  flag is a <span> prefix, not a second chip.
label goes through en/enums.json  →  `Frustration`, not `frustration`.
a null flag renders nothing — no gap, no placeholder.""",
"Two chips was rejected: <i>“too complex visually, adds confusion — the eye will jump to a single "
"patch of colour.”</i> The flag is <b>null on every card that renders today</b>; it lights up when "
"the label rule lands. Casing note: the badge below still reads lowercase — "
"<code>design-signal-card.md</code> §5c, deliberately not blocking.")
cf=find("Rockclimbing","Safety, Risk Management, and Close Calls","Sentiment")
pair("TODAY — no flag",
     f'<div class="signal-cards mk-fused-v3">{card(cf,score=0.42)}</div>',
     "WITH THE FLAG PREFIX",
     f'<div class="signal-cards mk-fused-v3">{card(cf,score=0.42,flag="Problem")}</div>')
ends()

nav="".join(f'<a href="#r{i}">{i}</a>' for i in range(1,8))
page=f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal card — the rules, firing</title>
<style>{(HERE/'theme.css').read_text()}</style><style>{(HERE/'page.css').read_text()}</style>
<style>{(HERE/'v3.css').read_text()}</style><style>
.mk-rulehead {{ display:flex; align-items:baseline; gap:var(--bn-space-sm); }}
.mk-rulenum {{ display:grid; place-items:center; width:1.8rem; height:1.8rem; flex:0 0 auto;
  background:var(--bn-colour-text); color:var(--bn-colour-bg); border-radius:var(--bn-radius-sm);
  font-family:var(--bn-font-mono); font-size:var(--bn-text-label); }}
.mk-formal {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-label);
  background:var(--bn-colour-hover); padding:var(--bn-space-md); border-radius:var(--bn-radius-md);
  overflow-x:auto; margin:var(--bn-space-sm) 0; line-height:1.5; }}
.mk-freq {{ font-size:var(--bn-text-label); color:var(--bn-colour-muted); max-width:78ch;
  margin:0 0 var(--bn-space-lg); }}
.mk-pair {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:var(--bn-space-xl);
  align-items:start; }}
.mk-single {{ max-width:680px; margin-bottom:var(--bn-space-xl); }}
.mk-col {{ min-width:0; }}
.mk-coltag {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); letter-spacing:.05em;
  background:var(--bn-colour-text); color:var(--bn-colour-bg); display:inline-block;
  padding:2px 7px; border-radius:var(--bn-radius-sm); margin-bottom:var(--bn-space-sm); }}
.mk-coltag.mk-was {{ background:none; color:var(--bn-colour-muted);
  border:1px dashed var(--bn-colour-border); }}
.mk-note {{ font-size:var(--bn-text-badge); color:var(--bn-colour-muted);
  margin-bottom:var(--bn-space-sm); font-family:var(--bn-font-mono); }}
.mk-cutnote {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge);
  color:var(--bn-colour-muted); margin-top:var(--bn-space-sm); }}
.mk-legacy {{ color:var(--bn-lead-rest-colour); margin:0; }}
.mk-legacy strong {{ color:var(--bn-lead-colour); font-weight:var(--bn-lead-weight); }}
blockquote.mk-dissent {{ box-shadow:inset 3px 0 0 var(--bn-colour-accent); padding-left:var(--bn-space-sm); }}
@media (max-width:1180px) {{ .mk-pair {{ grid-template-columns:1fr; }} }}
</style></head><body><div class="mk-page">
<header class="mk-head"><h1>Signal card &mdash; the rules, firing</h1>
<p>Every rule stated formally, a real card where it fires, and the counterfactual beside it.
Frequencies are over the corpus. Chip labels go through <code>en/enums.json</code>, so they read
<code>Frustration</code> rather than the raw value &mdash; which the shipped card does not, because
the translation is gated on a path it never takes.</p>
<nav class="mk-nav">{nav}</nav></header>{''.join(OUT)}
<footer class="mk-foot">Real data. Junk codebooks and <code>Uncategorised</code> excluded.
<code>MIN_WEIGHT = {MIN_WEIGHT:g}</code> &mdash; a GUESS, see &sect;5a.</footer>
</div></body></html>"""
(ROOT/"docs/mockups/signal-card-rules.html").write_text(page)
print(f"wrote docs/mockups/signal-card-rules.html ({len(page):,} bytes)")
