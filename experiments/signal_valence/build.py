#!/usr/bin/env python3
"""Generate docs/mockups/signal-card-valence.html from the real trial corpus."""
import json, html, os, collections

SP = os.path.dirname(os.path.abspath(__file__))  # run from the repo root
CARDS = json.load(open(os.path.join(SP, "cards.json")))
OUT = "docs/mockups/signal-card-valence.html"
E = lambda s: html.escape(str(s or ""))
by_name = {c["name"]: c for c in CARDS}

SHOWCASE = ["Community Delight Strength", "Homepage Orientation Gap",
            "Fear-Confidence Tension", "Career Friction Recovery"]
WALL = ["Fear-Confidence Tension", "Community Delight Strength", "Creative Flow Tension",
        "Homepage Orientation Gap", "Outdoor Transition Tension", "Entry Point Delight",
        "Inclusion Doubt Tension", "Career Friction Recovery", "Risk Confidence Tension",
        "Destination Delight", "Systemic Frustration", "Project Creation Delight"]

GROUP_VAR = {"Sentiment": "--bn-group-sentiment"}
def group_bg(g): return f"var({GROUP_VAR.get(g, '--bn-group-ux')})"

def score(c):
    """A plausible, stable composite for the mockup — not the product's maths."""
    return round(0.18 + (len(c["quotes"]) * 0.031) + (c["voices"] * 0.026), 2)

def vseq(c):     return [q["val"] for q in c["quotes"]]
def counts(c):
    v = vseq(c)
    return v.count(1), v.count(-1), v.count(0)

# ── valence channel renderers ───────────────────────────────────────────────
def t_withdrawn(c):
    return (f'<span class="pattern-label pattern-{c["pattern"]}">{c["pattern"].upper()}</span>')

def t_named(c):  return ""
def t_caption(c):
    return f'<span class="v-caption">{E(c["pattern"])}</span>'

GLYPH = {"success": "✓", "gap": "!", "tension": "↔", "recovery": "↗"}
def t_glyph(c):
    return (f'<span class="v-glyph v-{c["pattern"]}" title="{E(c["pattern"])}" '
            f'aria-label="{E(c["pattern"])}">{GLYPH[c["pattern"]]}</span>')

def t_tally(c):
    p, n, _ = counts(c)
    return f'<span class="v-tally"><b class="v-pos">{p}+</b> <b class="v-neg">{n}−</b></span>'

def t_strip(c):
    cells = "".join(
        f'<i class="v-cell v-cell-{ {1:"pos",-1:"neg",0:"neu"}[v] }"></i>' for v in vseq(c))
    return f'<span class="v-strip" aria-hidden="true">{cells}</span>'

def t_share(c):
    p, n, o = counts(c); tot = max(p + n + o, 1)
    pct = round(p / tot * 100)
    return (f'<span class="v-share" title="{p} of {tot} quotes meet the tag\'s ideal">'
            f'<i class="v-share-fill" style="width:{pct}%"></i></span>'
            f'<span class="v-share-num">{p}/{tot}</span>')

def t_stack(c):
    p, n, o = counts(c); tot = max(p + n + o, 1)
    seg = lambda k, cls: (f'<i class="v-seg-{cls}" style="width:{k/tot*100:.4f}%"></i>' if k else "")
    return (f'<span class="v-stack" title="{p} met, {n} fell short, {o} neither">'
            f'{seg(p,"pos")}{seg(o,"neu")}{seg(n,"neg")}</span>'
            f'<span class="v-share-num">{p}/{tot}</span>')

def t_score(c):
    return f'<span class="v-score v-{c["pattern"]}">{score(c):.2f}</span>'

def t_filter(c):  return ""
def t_split(c):
    w = {"success": "met", "gap": "unmet", "tension": "mixed", "recovery": "mixed"}[c["pattern"]]
    seq = ' <span class="v-seq" title="negative then positive">↗</span>' if c["pattern"] == "recovery" else ""
    return f'<span class="v-caption">{w}</span>{seq}'

TREATMENTS = [
    ("V0", "WITHDRAWN", t_withdrawn, "colour",
     "The shipped chip, 13 Sep. All-caps, tinted, top right, beside the score.",
     "Shouts. Reads as a taxonomy label, not a judgement. Raw hex inside light-dark(), "
     "not tokens. On 6 of 91 cards it contradicts the name two centimetres to its left."),
    ("V1", "NAMED", t_named, "words",
     "Nothing is drawn. The elaborated name carries it — Step 4 of the prompt already asks for this.",
     "Costs no pixels and no colour budget. Measured: 46% of names already contain the literal "
     "pattern word, 82% say it in name or claim. The gap is prompt reliability, not presentation."),
    ("V2", "CAPTION", t_caption, "words",
     "The word, lower case, muted, set as a caption in the metric row. Not a chip.",
     "Keeps the datum, drops the shout. Still nominal, still competes for the top right, "
     "and still says 'tension' on half the cards."),
    ("V3", "GLYPH", t_glyph, "symbols",
     "A mark instead of a word: ✓ ! ↔ ↗.",
     "Nominal shapes for nominal categories — correct by Bertin/Mackinlay. But ✓/! are borrowed "
     "from status and warning vocabularies that mean 'the system is fine / the system is broken', "
     "and these are judgements about the product under study, not about Bristlenose."),
    ("V4", "TALLY", t_tally, "symbols",
     "The counts the classification was computed from: how many quotes met the tag's ideal, how many fell short.",
     "Deadpan and auditable. Turns a nominal label into a quantity, so 5+/1− and 3+/3− stop "
     "being the same card. Needs the per-quote verdict Step 2 computes and throws away."),
    ("V5", "STRIP", t_strip, "symbols",
     "A Tufte dataword: one cell per quote, in the order the model read them.",
     "Shows the working rather than the verdict. Fails for the reason §3 gives — the order is "
     "participant-ID order, so the picture asserts a sequence that is not in the data."),
    ("V6", "SHARE", t_share, "symbols",
     "One ordinal quantity: the share of quotes that meet the tag's ideal. gap = 0, success = all.",
     "The proposal. Not a category, so nothing has to be nominal; not a sequence, so nothing "
     "false is claimed; ordered, so one channel is legitimate."),
    ("V6b", "STACKED", t_stack, "symbols",
     "The same quantity as a 100% stacked bar — met, neither, fell short. The track is never empty.",
     "Fixes V6's one real flaw: a gap card renders 0/2 as an EMPTY track, which reads as 'no data' "
     "rather than 'nothing met the ideal'. Always-full means the mark is present on every card and "
     "its shape, not its length, carries the reading. Costs a second hue."),
    ("V7", "SCORE", t_score, "colour",
     "No new mark — the score the card already carries takes the valence colour.",
     "Zero new objects. But it overloads a number that means attention-worthiness with a "
     "second meaning, and a coloured number is the weakest place to put a hue."),
    ("V8", "ABSENT", t_filter, "absence",
     "Nothing on the card. Valence is a filter and a sort in the view menu only.",
     "Honest about how little the chip was worth per-card, and it is where a researcher hunting "
     "'show me what is broken' actually wants it. Loses it entirely when scanning."),
    ("V9", "SPLIT", t_split, "words",
     "Two channels: valence as a word (met / unmet / mixed), sequence as a separate mark.",
     "The answer to the trap if recovery were real. §3 shows it is not, so the second channel "
     "has nothing to carry and this collapses into V2."),
]

# ── card rendering ──────────────────────────────────────────────────────────
def card(c, fn, note=None, quotes=3):
    ch = fn(c)
    q = "".join(
        f'<div class="mk-quote"><p>{E(qq["text"][:210])}{"…" if len(qq["text"])>210 else ""}</p>'
        f'<span class="mk-attr">{E(qq["pid"])}'
        f'<i class="mk-sent mk-sent-{ {1:"pos",-1:"neg",0:"neu"}[qq["val"]] }">{E(qq["sent"])}</i>'
        f'</span></div>' for qq in c["quotes"][:quotes])
    ann = f'<p class="mk-ann">{note}</p>' if note else ""
    return f'''<article class="signal-card mk-card">
  <div class="signal-card-top">
    <div class="signal-card-identity">
      <span class="signal-card-source">{E("Section" if c["kind"]=="section" else "Theme")}</span>
      <div class="signal-card-location">{E(c["name"])}</div>
      <p class="signal-elaboration bn-lead-para">{E(c["claim"])}</p>
      <p class="mk-evidence">{E(c["evidence"])}</p>
    </div>
    <div class="signal-card-right">
      <div class="mk-hero" style="background:{group_bg(c["group"])}">
        <span class="mk-hero-name">{E(c["group"])}</span>
        <span class="mk-hero-score">{score(c):.2f}</span>
      </div>
      <div class="mk-valence">{ch}</div>
    </div>
  </div>
  <div class="signal-card-quotes">{q}</div>
  <div class="mk-foot">{E(c["location"])} · {c["voices"]} participants · {len(c["quotes"])} quotes</div>
  {ann}
</article>'''

def mini(c, fn):
    return (f'<div class="mk-mini"><span class="mk-mini-name">{E(c["name"])}</span>'
            f'<span class="mk-mini-v">{fn(c)}</span></div>')

# ── page ────────────────────────────────────────────────────────────────────
dist = collections.Counter(c["pattern"] for c in CARDS)

def sec(n, title, body): return f'<section id="s{n}"><h2><span>{n}</span>{title}</h2>{body}</section>'

treat_html = []
for code, nm, fn, axis, what, verdict in TREATMENTS:
    cards = "".join(card(by_name[n], fn, quotes=2) for n in SHOWCASE if n in by_name)
    treat_html.append(f'''<div class="mk-treatment" id="{code}">
  <div class="mk-treat-head">
    <h3><b>{code}</b> {nm}<em class="mk-axis">{axis}</em></h3>
    <p class="mk-what">{what}</p>
    <p class="mk-verdict">{verdict}</p>
  </div>
  <div class="mk-grid">{cards}</div>
</div>''')

WALL_T = [("V0","WITHDRAWN",t_withdrawn),("V2","CAPTION",t_caption),
          ("V4","TALLY",t_tally),("V6b","STACKED",t_stack),("V8","ABSENT",t_filter)]
wall = "".join(
    f'<div class="mk-wallcol"><h4><b>{c}</b> {n}</h4>'
    + "".join(mini(by_name[w], f) for w in WALL if w in by_name) + '</div>'
    for c, n, f in WALL_T)

HEAD = open("docs/mockups/signal-card-valence.head.html").read() if os.path.exists(
    "docs/mockups/signal-card-valence.head.html") else ""

body = f'''<header class="mk-header">
  <p class="mk-kicker">Bristlenose · Analysis lens · mockup</p>
  <h1>The valence of a signal card</h1>
  <p class="mk-lede">Every elaborated card is classified <code>success</code> / <code>gap</code> /
    <code>tension</code> / <code>recovery</code> against the tag's own definition. The classification
    is sound; the presentation — an all-caps coloured chip — was withdrawn on 13 Sep 2026.
    This page is the search for a better one.</p>
  <p class="mk-meta"><b>Status: exploration.</b> No product code has moved. Cards below are real:
    <b>91</b> elaborated cards were read from nine trial projects via
    <code>elaboration_caches</code>; every number on this page is measured over all 91. The
    {len(CARDS)} that could also be resolved back to their own quotes are what gets drawn. Scores are plausible stand-ins, not the product's maths.
    Theme is the real baked <code>bristlenose/theme</code>. 13 Sep 2026.</p>
</header>'''

s1 = sec(1, "What the corpus says", f'''
<p>Everything below is measured over <b>91 elaborated cards</b> from nine trial projects
(<code>trial-runs/*/bristlenose-output/.bristlenose/bristlenose.db</code>). Four facts decide the design.</p>

<div class="mk-facts">
  <div class="mk-fact"><b>48%</b><span>of all cards are <code>tension</code>. A marker present on every
    card whose modal value covers half of them is close to no marker at all.</span></div>
  <div class="mk-fact"><b>82%</b><span>already state the pattern in prose — the name, the claim, or both.
    46% of names contain the literal pattern word.</span></div>
  <div class="mk-fact"><b>6</b><span>cards where the chip contradicts the name beside it.
    <i>Mentorship Delight <u>Gap</u></i> wears a <code>TENSION</code> chip.</span></div>
  <div class="mk-fact"><b>1.12</b><span>bits of marginal information, at most, once you have read the
    prose. H(pattern) is 1.74 of a possible 2.00.</span></div>
</div>

<table class="mk-table">
  <thead><tr><th>pattern</th><th>n</th><th>share</th><th>name says it</th><th>prose says it</th></tr></thead>
  <tbody>
    <tr><td><code>tension</code></td><td>44</td><td>48.4%</td><td>55%</td><td>73%</td></tr>
    <tr><td><code>success</code></td><td>24</td><td>26.4%</td><td>25%</td><td>67%</td></tr>
    <tr><td><code>gap</code></td><td>16</td><td>17.6%</td><td>44%</td><td>75%</td></tr>
    <tr><td><code>recovery</code></td><td>7</td><td>7.7%</td><td>71%</td><td>86%</td></tr>
  </tbody>
</table>
<p class="mk-caveat"><b>Read the 1.12 bits carefully.</b> It is an <i>upper</i> bound. The conditional
entropy was computed against a regex reading of the prose; a person reads prose far better than a regex,
so the chip's real marginal information is lower than this, not higher. The honest summary is that the
chip is <i>not</i> worthless — it is worth about a bit, on cards that already cost the reader two sentences.</p>

<h3>The contradictions, in full</h3>
<table class="mk-table mk-table-tight"><thead><tr><th>chip said</th><th>name said</th><th>name</th></tr></thead><tbody>
<tr><td><code>tension</code></td><td>gap</td><td>Mentorship Delight Gap</td></tr>
<tr><td><code>tension</code></td><td>gap</td><td>Checkout Clarity Gap</td></tr>
<tr><td><code>tension</code></td><td>gap</td><td>Internship Culture Gap</td></tr>
<tr><td><code>tension</code></td><td>gap</td><td>Linen Wayfinding Gap</td></tr>
<tr><td><code>recovery</code></td><td>gap</td><td>Navigation feedback gap</td></tr>
<tr><td><code>tension</code></td><td>recovery</td><td>Self-directed Error Recovery</td></tr>
</tbody></table>
<p>Six is small. It is also unanswerable: a researcher who sees a card contradict itself has no way to
tell which half is wrong, because the evidence for the chip was computed and discarded. That is the real
charge against it — <b>it is a verdict with no working</b>, on a card whose hero chip was just made
<i>the control that opens the working</i> (13 Sep).</p>''')

s2 = sec(2, "The trap — and where it goes", '''
<p>The brief names it: this is not a valence scale. <code>success</code> is positive, <code>gap</code>
is negative, <code>tension</code> is <i>both at once</i>, <code>recovery</code> is <i>temporal</i>.
Two dimensions squashed into four nominal labels, so a single diverging ramp cannot carry it —
<code>tension</code> lands on the midpoint looking like "neutral", which is the opposite of what it means,
and <code>recovery</code> has nowhere to sit.</p>

<div class="mk-demo">
  <div class="mk-ramp"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
  <p><b>Why the ramp fails.</b> A diverging scale is two sequential scales joined at a neutral midpoint,
  and the midpoint has to be anchored to a real value — it is where "no deviation" lives.
  <code>tension</code> is maximum deviation in both directions at once. Putting it at the pale centre
  says the opposite of what the card means, and the failure is silent: the card still renders, it just lies.</p>
</div>

<h3>But <code>recovery</code> is not a second dimension. It is a sort key.</h3>
<p>Step 3 defines <code>recovery</code> as "negative followed by positive <b>sequence</b>". Follow what
the model is actually given:</p>
<pre class="mk-code">bristlenose/analysis/signals.py:96
    raw_quotes_sorted = sorted(raw_quotes, key=lambda q: (q.participant_id, q.start_timecode))

bristlenose/analysis/generic_signals.py:104
    raw_quotes_sorted = sorted(raw_quotes, key=lambda q: (q.participant_id, q.start_seconds))

bristlenose/server/elaboration.py:129
    lines.append(f"- [{q.participant_id}] \\"{q.text}\\"{tag_suffix}")</pre>
<p>Quotes are sorted <b>by participant id first</b>, and <b>no timecode reaches the prompt at all</b>.
So the "sequence" the model reads is: everything p1 said, then everything p2 said, in alphabetical order
of participant. Across several people there is no shared timeline for a sequence to be a sequence
<i>on</i>. Measured: <b>3 of the 7 recovery cards provably span 3–5 different participants</b>
(the other four could not be resolved to their location, so they are unknown, not single-participant).
<b>44% of all 91 cards span more than one participant.</b></p>
<p class="mk-punch">A multi-participant <code>recovery</code> finding is an artefact of alphabetising
participant ids. It is <code>tension</code> wearing a story.</p>

<h3>What that does to the trap</h3>
<p>Remove the false dimension and the remaining three are not nominal at all. <code>gap</code>,
<code>tension</code> and <code>success</code> are three bands of one quantity — <b>the share of quotes
that meet the tag's ideal</b>: none, some, all. That is ordinal, it has a real zero and a real one, and
it is legitimately one channel. The trap dissolves not by finding a cleverer encoding for four
categories, but by noticing there were never four.</p>
<p class="mk-caveat">This is a claim about <code>recovery</code>'s <i>evidence</i>, not about whether
recovery is an interesting thing to look for. A within-participant recovery arc is real and worth
surfacing. It would need the quotes ordered by time and the times shown — a prompt and a sort change,
not a badge.</p>''')

s3 = sec(3, "The colour budget, checked rather than assumed", '''
<p>The brief's second constraint: the hero chip is already tinted by <i>either</i> a sentiment colour
<i>or</i> a codebook group colour, so valence colour would be a third colour language on one card.
Worth testing rather than assuming — and the test has a surprising result.</p>
<p><b>Valence is not a third language. It is the second one, reused.</b> The product already has
<code>--bn-colour-positive</code> and <code>--bn-colour-negative</code> as semantic tokens, and every
quote under the card already wears its sentiment. On a Sentiment card — <b>60% of the corpus</b> — a
valence mark drawn in those tokens is <i>literally the same colours already running down the card</i>.
On a codebook card it sits beside a group hue, which is exactly the pairing that already happens between
the group chip and the sentiment-tagged quotes below it.</p>
<p>So the colour argument does not rule colour out. What rules it out is weaker and still sufficient:
red/green as the sole channel fails 8% of men, the convention inverts in Chinese, Japanese, Korean and
Taiwanese markets — and Bristlenose ships in 22 locales including all four — and a hue carrying a
judgement is exactly the thing a researcher should be able to audit rather than absorb.</p>
<p class="mk-punch">Use the existing valence tokens, but never as the only channel, and never as the
first one a reader meets.</p>''')

s4 = sec(4, "Ten treatments, same four real cards", f'''
<p>One <code>success</code>, one <code>gap</code>, one <code>tension</code>, one <code>recovery</code>
— real cards, real quotes, real elaborations. Only the valence channel changes between blocks. The card
is drawn to the 13 Sep decision (hero chip top right carrying the group name and the score, metrics
minimised), not to the currently shipped four-metric block.</p>
<p class="mk-caveat"><b>All four showcase cards are Sentiment-group cards.</b> That is 60% of the
corpus and it is what the quote join could resolve — but it means the hero chip is the same pale
<code>--bn-group-sentiment</code> on all four, so the colour-budget question of §3 is under-shown here.
On a codebook card the hero carries one of six group hues instead, and the valence mark sits beside it
rather than beside a near-neutral.</p>
{"".join(treat_html)}''')

s5 = sec(5, "The density wall", f'''
<p>Four cards flatter every treatment. The lens is a wall, and the corpus proportions are
<b>48 / 26 / 18 / 8</b>. Twelve real cards at roughly those proportions, five treatments, same order.</p>
<div class="mk-wall">{wall}</div>
<p class="mk-punch">This is the view that kills V0. Repeat a word eleven times in a colour that means
"caution" and the twelfth stops being read — the same desensitisation that makes 80–99% of
non-actionable clinical alarms get filtered out of conscious awareness. V6b survives it because no two
cards look the same: the mark varies continuously, so the eye is reading a quantity rather than
re-reading a label.</p>''')

s6 = sec(6, "Rationale, and what was abandoned", '''
<h3>Kept in view</h3>
<ul class="mk-list">
<li><b>The name is already the channel.</b> Step 4 of <code>signal-elaboration.md</code> says
"combine the pattern type with specificity" and gives <i>Discoverability tension</i> / <i>Discoverability
gap</i> as examples. It works 46% of the time. Making it work 100% is a prompt edit, not a component.</li>
<li><b>Redundant encoding earns its keep between five and eight categories.</b> There are three or four
here, which is under the band where doubling up on colour and shape measurably helps. Belt and braces
for four categories is just braces.</li>
<li><b>A dataword beats a label when the label is a summary of something small.</b> Six quotes is small.
Tufte's case for word-sized graphics is exactly this: the summary and the evidence cost the same space.</li>
</ul>

<h3>Abandoned, with reasons</h3>
<ul class="mk-list mk-abandoned">
<li><b>A diverging colour ramp.</b> §2 — <code>tension</code> lands on the neutral midpoint meaning the
opposite of neutral. Dead on arrival, and silently.</li>
<li><b>Four semantically-resonant hues.</b> Semantic resonance is measurably faster for chart reading,
but it needs a shared referent — "ocean is blue". <code>tension</code> has no colour anybody agrees on,
and the two that do (green good, red bad) invert across four of the locales Bristlenose ships in.</li>
<li><b>ISO-7010-style pictograms.</b> The standard's own lesson is that shape and colour are only
reliable because they are <i>registered and learned</i>, and it still recommends supplementary text.
An in-house glyph set has the memorisation cost of a standard and none of the recognition.</li>
<li><b>✓ / ⚠ / ✕ status icons.</b> They read as claims about <i>Bristlenose</i> — job succeeded, job
warned — when they are claims about the product under study. Wrong speaker.</li>
<li><b>A four-colour chip using tokens instead of the raw hex.</b> Fixes the house-discipline breach and
none of the design ones. The problem was never that the greens were unofficial.</li>
<li><b>Tinting the whole card.</b> Content owns colour; a tinted card makes the container shout on behalf
of its contents, and stacks badly when half the wall is one colour.</li>
<li><b>The per-quote valence strip in reading order (V5).</b> Abandoned for cause, not taste: the order
is participant-ID order, so the picture asserts a sequence that is not in the data. It is the most
attractive option on this page and it is wrong.</li>
<li><b>Deriving valence from <code>quotes.sentiment</code> (97.8% populated, free today).</b> Tempting
and a different construct. A quote tagged <i>Discoverability</i> with sentiment <i>satisfaction</i> can
still violate the discoverability ideal. Measured on Sentiment cards, the naive derivation agrees with
the model 67% of the time — and disagrees on <i>every</i> recovery card, because a set of sentiment
labels has no order.</li>
</ul>''')

s7 = sec(7, "The second vocabulary: <code>classify_flag</code>", '''
<p><code>classify_flag</code> in <code>bristlenose/analysis/metrics.py</code> returns
<b>Win / Problem / Niggle / Success / Surprising</b>. Traced end to end:</p>
<ul class="mk-list">
<li>Called at <code>signals.py:111</code> and <code>generic_signals.py:121</code>; lands on
<code>Signal.flag</code>.</li>
<li>Serialised onto the API at <code>server/routes/analysis.py:238</code> and <code>:437</code>.</li>
<li>Read by <b>nothing</b> — no React component, no Swift type, no static renderer. It crosses the wire
and is dropped.</li>
<li>Its docstring promises a sixth value, <code>"Pattern"</code>, that no branch returns.</li>
</ul>
<p>It is also not the same idea as <code>pattern</code>, which is why "merge them" is the wrong move.
<code>pattern</code> asks <i>did the evidence meet the tag's ideal</i>. <code>classify_flag</code> asks
<i>is this positive or negative, and is it broad and intense enough to matter</i> — it folds valence
together with breadth and intensity, returns <code>None</code> for every codebook group, and the
breadth-and-intensity half is precisely what the signal score exists to carry as a number.</p>
<p class="mk-punch">It goes. Delete <code>classify_flag</code>, the four <code>FLAG_*</code> thresholds,
<code>Signal.flag</code>, the two serialisation sites and
<code>tests/test_analysis_flags.py</code>. Nothing renders differently. Keeping a dead second vocabulary
alive is how the next session builds on it by mistake.</p>''')

s8 = sec(8, "Recommendation", '''
<p class="mk-rec"><b>V6b — STACKED</b>, with <b>V1 — NAMED</b> underneath it. Draw one ordinal quantity:
the share of the card's quotes that meet the tag's ideal. Let the words keep carrying the judgement,
and make the prompt do that reliably instead of 46% of the time.</p>

<h3>What it is, concretely</h3>
<ul class="mk-list">
<li>A short 100%-stacked track under the hero chip with a <code>4/7</code> read-out.
All-green = <code>success</code>, all-red = <code>gap</code>, split = <code>tension</code>, and the reader sees
<i>how</i> mixed rather than a word that treats 6-of-7 and 3-of-7 as the same card.</li>
<li>Drawn in <code>--bn-colour-positive</code> / <code>--bn-colour-negative</code> on
<code>--bn-colour-border</code> — existing tokens,
the same language the quotes below already speak. The number is the non-colour channel, so it clears
WCAG 1.4.1 without the colour doing the work.</li>
<li>Clicking it opens the per-quote verdicts — the same "chip is the control that opens the working"
move the score chip made on 13 Sep. The verdict stops being unfalsifiable.</li>
<li>Step 3 of the prompt keeps returning <code>pattern</code> for the filter and the sort; it just stops
being drawn as a word. Nothing in <code>elaboration_caches</code> is invalidated.</li>
</ul>

<h3>What it costs</h3>
<ul class="mk-list mk-cost">
<li><b>One new field, and it is the whole cost.</b> Step 2 already judges every quote + or − against the
tag definition and discards it. The elaboration response needs to carry that array, and
<code>elaboration_caches</code> needs a column. Until then the share is unavailable on the 40% of cards
that are codebook cards — <code>quotes.sentiment</code> is not a substitute, for the reason in §6.</li>
<li><b>Existing cached elaborations have no array.</b> They keep working — the card falls back to V1,
the name alone — but the share only appears on re-elaboration. That is a real staleness edge and the
first thing to check in a build.</li>
<li><b>A prompt edit to Step 4</b> to make the name carry valence every time, plus examples for the
cases it currently misses (<code>success</code> names manage it only 25% of the time).</li>
<li><b>The six contradictions get louder before they get quieter.</b> Showing 4/7 next to a name that
says "Gap" makes the disagreement legible instead of hiding it in a chip. That is the point, and it is
still a worse first impression than a chip that quietly lied.</li>
</ul>

<h3>What it cannot do</h3>
<ul class="mk-list mk-cannot">
<li><b>It cannot show a recovery arc</b>, and neither could the chip — §2. If recovery is wanted as a
real finding, it needs quotes ordered by time with times in the prompt, and it is only ever a
within-participant claim. That is a separate piece of work and should not be smuggled in as a glyph.</li>
<li><b>It cannot carry intensity.</b> Four mild misses and four furious ones both read 0/4. The card
already has a mean-intensity metric; this is not it.</li>
<li><b>Three segments is the ceiling.</b> Met / neither / fell short is the most the track can
carry before it becomes a chart. Anything finer — how strongly each quote met the ideal, which tag
each verdict was against — belongs in the panel the mark opens, not on it.</li>
<li><b>It is not a measurement.</b> Same standing as the signal score: an ordering and orienting device
built on a model's judgement, not a fact about the study.</li>
</ul>

<h3>If you would rather not pay for the field</h3>
<p><b>V1 alone.</b> Delete the chip, change nothing else, tighten Step 4. It is free, it is defensible on
the 82% measurement, and it is strictly better than what shipped. The thing it gives up is scannability:
a researcher looking for "what is broken here" has to read, and V8's filter becomes load-bearing.</p>''')

THEME = open(os.path.join(SP,"theme.css")).read()
page = f'''<style id="bn-theme">{THEME}</style>
<style id="mk-page-chrome">{open(os.path.join(SP,"page.css")).read()}</style>
<div class="mk-page">
{body}
<nav class="mk-toc"><b>On this page</b>
  <a href="#s1">1 · Corpus</a><a href="#s2">2 · The trap</a><a href="#s3">3 · Colour budget</a>
  <a href="#s4">4 · Treatments</a><a href="#s5">5 · Density wall</a><a href="#s6">6 · Rationale</a>
  <a href="#s7">7 · classify_flag</a><a href="#s8">8 · Recommendation</a></nav>
{s1}{s2}{s3}{s4}{s5}{s6}{s7}{s8}
<footer class="mk-footer">
  <p>Corpus: 91 elaborated cards, nine trial projects, read from <code>elaboration_caches</code> on
  13 Sep 2026. Measurement scripts in the session scratchpad; every number on this page is reproducible
  from the trial databases. Theme baked from <code>bristlenose/theme</code> via
  <code>load_default_css()</code>. No product code has moved.</p>
</footer>
</div>'''

open(OUT, "w").write(
    "<!-- Signal-card valence exploration — see docs/design-decisions.md, 13 Sep 2026.\n"
    "     Generated; regenerate with experiments/signal_valence/build.py (see its README). -->\n" + page)
print(f"wrote {OUT}  ({len(page.splitlines())} lines, {len(page)//1024} KB)")
