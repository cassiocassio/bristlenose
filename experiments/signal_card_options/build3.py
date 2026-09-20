"""Design A — a true fused stack of whole cards.

    .venv/bin/python experiments/signal_card_options/build3.py

Each card is a complete signal: headline, claim, evidence, quotes, footer,
participant grid. Cards at one location are fused — the seam is a card's own
border, so it runs edge to edge. Which cards survive is the marginal-value
rule: strongest first, then admit one only if it brings quotes the kept cards
have not shown.

Decisions carried: 1=C chip · 2=V1 + H-c heading · 3=F1 fused · 4=Q2 cap 4
5=W1 floated hero · 6=earned-words · 7=G4 flag prefix · 8=S2 vocabulary
("Mixed sentiments") · chip flush right at every level.
"""
import collections, glob, html, json, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
e = html.escape
CAP = 4

GROUP_BG = {"ux": "--bn-group-ux", "emo": "--bn-group-emo", "task": "--bn-group-task",
            "trust": "--bn-group-trust", "opp": "--bn-group-opp",
            "sentiment": "--bn-group-sentiment"}
SLOTS = {"ux": 5, "emo": 6, "task": 5, "trust": 5, "opp": 5, "sentiment": 7}
VALENCE = {"frustration": "neg", "confusion": "neg", "doubt": "neg", "surprise": "neu",
           "satisfaction": "pos", "delight": "pos", "confidence": "pos"}

# Junk codebooks from the trial machine are excluded — `Chocolate`, `Booze`,
# `New group` are someone testing the builder, and they were what made the
# earlier worst-case example unbelievable.
REAL = {"Sentiment"}
for f in glob.glob(str(ROOT / "bristlenose/server/codebook/*.yaml")):
    for g in (yaml.safe_load(open(f)).get("groups") or []):
        if isinstance(g, dict) and g.get("name"):
            REAL.add(g["name"])

CARDS = [c for c in json.load(open(HERE / "cards.json"))
         if c["group"] in REAL and c["group"] != "Uncategorised"]

gbg = lambda cs: f"var({GROUP_BG[cs]})" if cs in GROUP_BG else "var(--bn-group-none)"
tbg = lambda cs, i: (f"var(--bn-{cs}-{(i % SLOTS[cs]) + 1}-bg)" if cs in SLOTS
                     else "var(--bn-custom-bg)")


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


def split_lead(t):
    if "||" in t:
        lead, _, rest = t.partition("||")
    elif " — " in t:
        lead, _, rest = t.partition(" — ")
    else:
        lead, rest = t, ""
    lead = lead.strip().rstrip("—-").strip()
    rest = rest.strip().lstrip("—-").strip()
    if lead and lead[-1] not in ".!?":
        lead += "."
    return lead, (rest[0].upper() + rest[1:] if rest else "")


def label_for(card):
    """Decision 8 — a single value stays itself; several become
    Positive / Negative / Mixed sentiments. Never a count."""
    if card["group"] != "Sentiment":
        return card["group"]
    vals = {q["sentiment"] for q in card["quotes"] if q["sentiment"]}
    if not vals:
        return "Sentiment"
    if len(vals) == 1:
        return next(iter(vals))
    vs = {VALENCE.get(v) for v in vals} - {None}
    return ("Positive" if vs == {"pos"} else "Negative" if vs == {"neg"}
            else "Mixed sentiments")


def quote(q, cs):
    tags = "".join(f'<span class="badge signal-quote-tag" style="background:{tbg(cs,i)}">{e(t)}</span>'
                   for i, t in enumerate(q["tags"]))
    pid = (f'<span class="speaker"><span class="bn-person-badge"><span class="bn-speaker-badge--split">'
           f'<span class="bn-speaker-badge-code">{e(q["pid"])}</span></span></span></span>'
           if q["pid"] else "")
    return (f'<blockquote><div class="quote-row"><a class="timecode">'
            f'<span class="timecode-bracket">[</span>{tc(q["t"])}'
            f'<span class="timecode-bracket">]</span></a><span class="quote-body">'
            f'<span class="quote-text">{e(q["text"])}</span> {pid}{tags}</span>'
            f'{dots(q["intensity"])}</div></blockquote>')


def chip(label, score, cs="", flag=None):
    sent = label.lower() in VALENCE
    cls = f'badge signal-card-hero mk-h-c{" badge-" + label.lower() if sent else ""}'
    style = "" if sent else f' style="background:{gbg(cs)}"'
    pre = f'<span class="mk-chip-flag">{e(flag)}:</span>' if flag else ""
    return (f'<button class="{cls}"{style}>{pre}'
            f'<span class="signal-card-hero-label">{e(label)}</span>'
            f'<span class="signal-card-hero-score">{score:.2f}</span>'
            f'<span class="signal-card-hero-caret">▾</span></button>')


def card_html(c, score, flag=None, *, dimmed=False, reason=None):
    """A WHOLE card. Every part a signal card has, nothing borrowed.

    W1: `.signal-card-right` is emitted first so the float catches the title
    AND the elaboration. The chip is flush to the card's right padding edge.
    """
    cs = c["colour_set"]
    name, elab = (c["elab"][0], c["elab"][2]) if c["elab"] else (None, None)
    head = f'<div class="signal-card-location">{e(name or c["location"])}</div>'
    if elab:
        a, b = split_lead(elab)
        head += f'<p class="signal-elaboration bn-lead-para bn-lead-claim">{e(a)}</p>'
        if b:
            head += f'<p class="signal-elaboration bn-lead-para bn-lead-rest">{e(b)}</p>'
    qs = c["quotes"][:CAP]
    more = len(c["quotes"]) - len(qs)
    foot = (f'<button class="signal-card-link signal-card-toggle">Show all '
            f'{len(c["quotes"])} quotes →</button>' if more > 0
            else '<button class="signal-card-link signal-card-toggle">Hide</button>')
    present = {q["pid"] for q in c["quotes"]}
    allp = c["all_participants"] or sorted(present)
    grid = (f'<span class="participant-grid"><span class="participant-count">'
            f'{len(present)}/{len(allp)}</span>' +
            "".join(f'<span class="p-box{" p-present" if p in present else ""}">{e(p)}</span>'
                    for p in allp) + "</span>")
    note = f'<div class="mk-reject">{e(reason)}</div>' if reason else ""
    return (f'<div class="signal-card mk-v3{" mk-dim" if dimmed else ""}" '
            f'style="--card-accent:{gbg(cs)}">{note}'
            f'<div class="signal-card-top">'
            f'<div class="signal-card-right">{chip(label_for(c), score, cs, flag)}</div>'
            f'<div class="signal-card-identity">{head}</div></div>'
            f'<div class="signal-card-quotes">{"".join(quote(q, cs) for q in qs)}</div>'
            f'<div class="signal-card-footer">{foot}{grid}</div></div>')


# ── the marginal-value rule ────────────────────────────────────────────────
def rank_key(c):
    """Stand-in for composite_signal.

    The real score is under revision (docs/design-signal-strength.md is an
    open spike), and it is not in the harvest — so ordering is by evidence
    volume: elaborated first, then quotes, then voices. What this page is
    showing is the FILTER'S BEHAVIOUR, not the ranking's exact order.
    """
    return (0 if c["elab"] else 1, -len(c["quotes"]), -len(c["participants"]), c["group"])


def admit(cards):
    """Strongest first; a later card is admitted only if it brings a quote no
    kept card already carries — your test 2. Rejections carry their reason."""
    kept, rejected, covered = [], [], set()
    for c in sorted(cards, key=rank_key):
        new = {q["id"] for q in c["quotes"]} - covered
        if not kept or new:
            kept.append(c)
            covered |= {q["id"] for q in c["quotes"]}
        else:
            rejected.append((c, f"every quote already shown by "
                                f"{', '.join(label_for(k) for k in kept)}"))
    return kept, rejected


BYLOC = collections.defaultdict(list)
for c in CARDS:
    BYLOC[(c["project"], c["axis"], c["location"])].append(c)

STATS = {"in": 0, "kept": 0, "cut": 0}
for k, v in BYLOC.items():
    kept, rej = admit(v)
    STATS["in"] += len(v); STATS["kept"] += len(kept); STATS["cut"] += len(rej)

OUT = []
def sec(n, t, why): OUT.append(f'<section class="mk-sec"><h2 id="s{n}">{n}. {t}</h2><p class="mk-why">{why}</p>')
def note(t): OUT.append(f'<p class="mk-why">{t}</p>')
def opt(tag, name, n=""): OUT.append(f'<div class="mk-opt"><div class="mk-optlabel"><b>{tag}</b> {name}{" — <i>"+n+"</i>" if n else ""}</div>')
def end(): OUT.append("</div>")
def ends(): OUT.append("</section>")
def head(l): return f'<div class="analysis-codebook-heading">{e(l)}</div>'
def loc(p, l): return BYLOC[next(k for k in BYLOC if k[0] == p and k[2] == l)]


def stack(cards, scores=None, rejected=None):
    """A fused run. The seam is each card's own top border, so it reaches
    both edges — it is a boundary between objects, not a rule inside one."""
    scores = scores or [0.61 - i * 0.14 for i in range(len(cards))]
    h = '<div class="signal-cards mk-fused-v3 mk-narrow">'
    h += "".join(card_html(c, s) for c, s in zip(cards, scores))
    h += "</div>"
    if rejected:
        h += '<div class="mk-cutblock"><div class="mk-cutlabel">cut by the rule</div>'
        h += '<div class="signal-cards mk-narrow">'
        h += "".join(card_html(c, 0.11, dimmed=True, reason=r) for c, r in rejected)
        h += "</div></div>"
    return h


# ── 1 ──────────────────────────────────────────────────────────────────────
one = [c for c in CARDS if c["elab"] and len(c["quotes"]) >= 2]
one.sort(key=lambda c: -len(c["elab"][2]))
c1 = one[0]
sec(1, "One whole card",
    "Every part a signal has and nothing borrowed: its own headline, its own claim and evidence, "
    "its own quotes, its own footer and participant grid. The chip is flush to the right padding "
    "edge and the text wraps under it (<b>W1</b>). Claim and evidence are two paragraphs, which "
    "is what <code>signal-elaboration.md</code> has always specified and the renderer never did.")
OUT.append(head(c1["location"]) + stack([c1], [0.61]))
ends()

# ── 2 ──────────────────────────────────────────────────────────────────────
sec(2, "A fused run",
    "Two whole cards at one location. <b>The seam is each card's own top border, so it reaches "
    "both edges</b> — it is a boundary between objects, not a rule inside one. That is the "
    "difference from the hybrid: nothing here is a section of something else.")
tgt = max((k for k in BYLOC if len(admit(BYLOC[k])[0]) >= 2),
          key=lambda k: sum(1 for c in BYLOC[k] if c["elab"]))
kept, rej = admit(BYLOC[tgt])
OUT.append(head(tgt[2]) + stack(kept[:2]))
ends()

# ── 3 ──────────────────────────────────────────────────────────────────────
sec(3, "The single-card location",
    f"<b>{sum(1 for v in BYLOC.values() if len(admit(v)[0]) == 1)} of {len(BYLOC)} locations</b> "
    "keep exactly one card after the rule. An only child is both first and last, so it takes all "
    "four corners with no special case — the common case needs no rule at all.")
solo = next(k for k in BYLOC if len(admit(BYLOC[k])[0]) == 1 and BYLOC[k][0]["elab"])
OUT.append(head(solo[2]) + stack(admit(BYLOC[solo])[0]))
ends()

# ── 4 ──────────────────────────────────────────────────────────────────────
sec(4, "The rule, working",
    f"Strongest first; a later card is admitted only if it brings a quote no kept card has shown. "
    f"Across the corpus: <b>{STATS['in']} cards in, {STATS['kept']} kept, {STATS['cut']} cut</b>. "
    "Cut cards are drawn below each run with the reason, so you can judge the rule rather than "
    "trust it.")
worst = max(BYLOC, key=lambda k: len(admit(BYLOC[k])[1]))
kept, rej = admit(BYLOC[worst])
note(f'<code>{e(worst[0])} · {e(worst[2])}</code> — '
     f'{len(BYLOC[worst])} cards in, {len(kept)} kept, {len(rej)} cut.')
OUT.append(head(worst[2]) + stack(kept, rejected=rej))
ends()

# ── 5 ──────────────────────────────────────────────────────────────────────
sec(5, "The chip vocabulary",
    "A single sentiment value stays itself and takes its own <code>badge-</code> colour. Several "
    "values collapse to <code>Positive</code> / <code>Negative</code> / "
    "<code>Mixed sentiments</code> — <b>never a count</b>; the tags are right there to "
    "eyeball. <b>G4</b> puts the flag in front as a prefix rather than a second chip.")
shown = set()
for c in sorted(CARDS, key=rank_key):
    if c["group"] != "Sentiment":
        continue
    lab = label_for(c)
    if lab in shown or not c["elab"]:
        continue
    shown.add(lab)
    flag = {"Negative": "Problem", "Mixed sentiments": "Niggle",
            "Positive": "Win"}.get(lab, "Win")
    opt(lab, f'<code>{e(flag)}: {e(lab)}</code>', e(f'{c["project"]} · {c["location"]}'))
    OUT.append('<div class="signal-cards mk-fused-v3 mk-narrow">' +
               card_html(c, 0.42, flag) + "</div>")
    end()
    if len(shown) >= 4:
        break
ends()

nav = "".join(f'<a href="#s{i}">{i}</a>' for i in range(1, 6))
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal card — design A</title>
<style>{(HERE/'theme.css').read_text()}</style><style>{(HERE/'page.css').read_text()}</style>
<style>{(HERE/'v3.css').read_text()}</style></head><body><div class="mk-page">
<header class="mk-head"><h1>Signal card &mdash; design A</h1>
<p>A true fused stack: whole cards, each a complete signal, joined by a seam that runs edge to
edge. Which cards survive is the marginal-value rule. Real data throughout; junk codebooks from
the trial machine (<code>Chocolate</code>, <code>Booze</code>, <code>New group</code>) excluded,
along with <code>Uncategorised</code>.</p>
<p><b>Carried in:</b> 1=C chip &middot; 2=V1 + H-c heading &middot; 3=F1 fused &middot;
4=Q2 cap {CAP} &middot; 5=W1 floated hero &middot; 6=earned-words &middot; 7=G4 flag prefix
&middot; 8=Positive / Negative / Mixed sentiments &middot; chip flush right at every level.</p>
<nav class="mk-nav">{nav}</nav></header>{''.join(OUT)}
<footer class="mk-foot">{len(CARDS)} real-framework cards &middot; {len(BYLOC)} locations &middot;
{STATS['kept']} kept, {STATS['cut']} cut by the rule.</footer>
</div></body></html>"""
(ROOT / "docs/mockups/signal-card-design-a.html").write_text(page)
print(f"wrote docs/mockups/signal-card-design-a.html ({len(page):,} bytes)")
print(f"  {STATS['in']} cards in · {STATS['kept']} kept · {STATS['cut']} cut "
      f"· {len(BYLOC)} locations")
