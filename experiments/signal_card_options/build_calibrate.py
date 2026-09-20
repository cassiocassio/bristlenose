"""Calibration set — real cards, no label, for a human to judge.

    .venv/bin/python experiments/signal_card_options/build_calibrate.py

Sampled across the weighted-dominance range so the answers are informative:
dense where the threshold decision lives (50-90%), with pure anchors at each
end. The chip is blank on purpose — judging should come from the evidence,
not from the arithmetic, so the working sits BELOW the card.
"""
import collections, html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
e = html.escape
VAL = {"frustration": "neg", "confusion": "neg", "doubt": "neg", "surprise": "neu",
       "satisfaction": "pos", "delight": "pos", "confidence": "pos"}
SHOW = 6   # quotes drawn per case; the working always covers all of them

C = [c for c in json.load(open(HERE / "cards.json")) if c["group"] == "Sentiment"]

rows = []
for c in C:
    qs = [q for q in c["quotes"] if q["sentiment"] in VAL]
    if len(qs) < 2:
        continue
    wv, wl = collections.Counter(), collections.Counter()
    for q in qs:
        w = q["intensity"] or 1
        wv[q["sentiment"]] += w
        wl[VAL[q["sentiment"]]] += w
    tot = sum(wv.values())
    top, tw = wv.most_common(1)[0]
    pos, neg, neu = wl.get("pos", 0), wl.get("neg", 0), wl.get("neu", 0)
    d = pos + neg
    rows.append(dict(c=c, qs=sorted(qs, key=lambda q: (q["pid"], q["t"])),
                     wv=wv, n=len(qs), tot=tot, top=top, vshare=tw / tot,
                     pos=pos, neg=neg, neu=neu,
                     lshare=(max(pos, neg) / d if d else 1.0),
                     lean=("Positive" if pos > neg else "Negative") if d else
                          ("Positive" if pos else "Negative" if neg else "—"),
                     clash=bool(pos and neg)))

# stratified: every clashing case in the contested band, plus anchors
band = lambda r: min(int(r["lshare"] * 10) * 10, 90)
picked, seen = [], collections.Counter()
for r in sorted([r for r in rows if r["clash"]], key=lambda r: r["lshare"]):
    if seen[band(r)] < 6:
        picked.append(r); seen[band(r)] += 1
anchors = [r for r in rows if not r["clash"]]
anchors.sort(key=lambda r: -r["vshare"])
picked += anchors[:3] + anchors[len(anchors)//2:len(anchors)//2 + 2]
picked.sort(key=lambda r: r["lshare"])

GROUP_BG = {"sentiment": "--bn-group-sentiment"}
def tc(s):
    s = int(s or 0)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}" if s >= 3600 else f"{(s%3600)//60:02d}:{s%60:02d}"
def dots(v):
    o = "".join(f'<circle cx="{7+i*16}" cy="6" r="5" ' +
        ('fill="var(--dot-colour, var(--bn-colour-muted))" opacity="0.7"/>' if (v or 0) > i
         else 'fill="none" stroke="var(--dot-colour, var(--bn-colour-muted))" '
              'stroke-width="1.2" opacity="0.35"/>') for i in range(3))
    return (f'<span class="intensity-dots"><svg class="intensity-dots-svg" width="40" height="12" '
            f'viewBox="0 0 40 12">{o}</svg></span>')
def quote(q):
    return (f'<blockquote><div class="quote-row"><a class="timecode">'
            f'<span class="timecode-bracket">[</span>{tc(q["t"])}'
            f'<span class="timecode-bracket">]</span></a><span class="quote-body">'
            f'<span class="quote-text">{e(q["text"])}</span> '
            f'<span class="speaker"><span class="bn-person-badge"><span class="bn-speaker-badge--split">'
            f'<span class="bn-speaker-badge-code">{e(q["pid"])}</span></span></span></span>'
            f'<span class="badge signal-quote-tag badge-{q["sentiment"]}">{e(q["sentiment"])}</span>'
            f'</span>{dots(q["intensity"])}</div></blockquote>')


OUT = []
for i, r in enumerate(picked, 1):
    c = r["c"]
    qs = r["qs"][:SHOW]
    trunc = r["n"] - len(qs)
    comp = " · ".join(f'<span class="cal-w badge-{v}">{e(v)} {w}</span>'
                           for v, w in r["wv"].most_common())
    opts = [("A", r["top"], f'the dominant feeling — {r["vshare"]*100:.0f}% of the weight'),
            ("B", r["lean"], f'the direction — {r["lshare"]*100:.0f}% of pos/neg weight'),
            ("C", "Mixed sentiments", "no summary is safe; say it is mixed")]
    if not r["clash"]:
        opts[1] = ("B", r["lean"], "the direction — nothing opposing present")
    OUT.append(f'''<div class="cal-case" id="c{i}">
<div class="cal-num">{i}</div>
<div class="cal-meta"><code>{e(c["project"])} · {e(c["location"])}</code>
&nbsp;—&nbsp; {r["n"]} sentiment quotes{f", {trunc} not drawn" if trunc else ""}</div>
<div class="signal-cards mk-narrow"><div class="signal-card mk-v3"
 style="--card-accent:var(--bn-group-sentiment)">
 <div class="signal-card-top">
  <div class="signal-card-right"><button class="badge signal-card-hero mk-h-c cal-blank">
   <span class="signal-card-hero-label">?</span></button></div>
  <div class="signal-card-identity">
   <div class="signal-card-location">{e(c["location"])}</div></div></div>
 <div class="signal-card-quotes">{"".join(quote(q) for q in qs)}</div></div></div>
<div class="cal-work"><b>weight (count × intensity):</b> {comp}
 &nbsp;—&nbsp; positive {r["pos"]}, negative {r["neg"]}{f", neutral {r['neu']}" if r["neu"] else ""}</div>
<ol class="cal-opts">{"".join(f'<li><b>{k}</b> <code>{e(str(lab))}</code> <i>{n}</i></li>' for k, lab, n in opts)}</ol>
</div>''')

nav = " ".join(f'<a href="#c{i}">{i}</a>' for i in range(1, len(picked) + 1))
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sentiment label calibration</title>
<style>{(HERE/'theme.css').read_text()}</style><style>{(HERE/'page.css').read_text()}</style>
<style>{(HERE/'v3.css').read_text()}</style>
<style>
.cal-case {{ margin: 0 0 var(--bn-space-xl); padding-top: var(--bn-space-lg);
  border-top: 2px solid var(--bn-colour-border); position: relative; }}
.cal-num {{ position:absolute; top: var(--bn-space-lg); left:-2.4rem; width:1.8rem; height:1.8rem;
  display:grid; place-items:center; background: var(--bn-colour-text); color: var(--bn-colour-bg);
  border-radius: var(--bn-radius-sm); font-family: var(--bn-font-mono);
  font-size: var(--bn-text-label); }}
.cal-meta {{ font-size: var(--bn-text-label); color: var(--bn-colour-muted);
  margin-bottom: var(--bn-space-sm); }}
.cal-blank {{ background: var(--bn-colour-hover) !important; min-width: 3.5rem;
  justify-content: center; color: var(--bn-colour-muted); }}
.cal-work {{ font-size: var(--bn-text-label); color: var(--bn-colour-muted);
  margin: var(--bn-space-sm) 0; max-width: 640px; }}
.cal-w {{ padding: 1px 6px; border-radius: var(--bn-radius-sm); }}
.cal-opts {{ list-style:none; padding:0; margin:0; max-width:640px;
  font-size: var(--bn-text-label); }}
.cal-opts li {{ padding: var(--bn-space-xs) 0; }}
.cal-opts b {{ display:inline-grid; place-items:center; width:1.4rem; height:1.4rem;
  border:1px solid var(--bn-colour-border); border-radius: var(--bn-radius-sm);
  margin-right:.5rem; font-family: var(--bn-font-mono); }}
.cal-nav a {{ margin-right:.45rem; font-family: var(--bn-font-mono);
  font-size: var(--bn-text-label); }}
</style></head><body><div class="mk-page">
<header class="mk-head"><h1>Sentiment label &mdash; calibration</h1>
<p>{len(picked)} real cards, sampled across the weighted-dominance range, dense where the
threshold decision actually lives. <b>The chip is blank on purpose</b> &mdash; judge from the
quotes, then look at the working underneath. Reply with a list, e.g.
<code>1=C 2=A 3=B &hellip;</code>; where none of the three is right, say what it should be.</p>
<p class="mk-why">Weight is count &times; intensity. <b>A</b> names the dominant feeling,
<b>B</b> names the direction, <b>C</b> refuses to summarise. The answers set the two thresholds:
how dominant a single feeling must be before the chip names it, and how dominant a direction
must be before the chip leans.</p>
<nav class="cal-nav">{nav}</nav></header>
{''.join(OUT)}
<footer class="mk-foot">Sampled from {len(rows)} sentiment locations carrying 2+ sentiment
quotes, across {len({r['c']['project'] for r in rows})} projects.</footer>
</div></body></html>"""
(ROOT / "docs/mockups/sentiment-calibration.html").write_text(page)
print(f"wrote docs/mockups/sentiment-calibration.html ({len(page):,} bytes) · {len(picked)} cases")
print("\n  spread of valence dominance across the set:")
h = collections.Counter(min(int(r["lshare"]*10)*10, 100) for r in picked)
for k in sorted(h):
    print(f"    {k}–{k+9}%  {'#'*h[k]} ({h[k]})")
