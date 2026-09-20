"""v2 — the decisions applied, and what they collide with.

    .venv/bin/python experiments/signal_card_options/build2.py

Decisions carried in: 1=C, 2=V1, 3=F1, 4=Q2, 5=W1, 6=earned-words,
7=G4 chip, 8=S2 + Positive/Negative/Divided vocabulary, 10=M1.
Real data throughout; CSS baked from bristlenose/theme.
"""
import collections, html, json, pathlib
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
from ribbon import ribbon, CSS as RIBBON_CSS

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
CARDS = json.load(open(HERE / "cards.json"))
e = html.escape

GROUP_BG = {"ux": "--bn-group-ux", "emo": "--bn-group-emo", "task": "--bn-group-task",
            "trust": "--bn-group-trust", "opp": "--bn-group-opp",
            "sentiment": "--bn-group-sentiment"}
SLOTS = {"ux": 5, "emo": 6, "task": 5, "trust": 5, "opp": 5, "sentiment": 7}
VALENCE = {"frustration": "neg", "confusion": "neg", "doubt": "neg", "surprise": "neu",
           "satisfaction": "pos", "delight": "pos", "confidence": "pos"}
CAP = 4                       # decision 4 — Q2

gbg = lambda cs: f"var({GROUP_BG[cs]})" if cs in GROUP_BG else "var(--bn-group-none)"
tbg = lambda cs, i: (f"var(--bn-{cs}-{(i % SLOTS[cs]) + 1}-bg)" if cs in SLOTS
                     else "var(--bn-custom-bg)")


def tc(s):
    s = int(s or 0)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}" if s >= 3600 else f"{(s%3600)//60:02d}:{s%60:02d}"


def dots(v):
    o = "".join(
        f'<circle cx="{7+i*16}" cy="6" r="5" ' +
        ('fill="var(--dot-colour, var(--bn-colour-muted))" opacity="0.7"/>' if (v or 0) > i else
         'fill="none" stroke="var(--dot-colour, var(--bn-colour-muted))" stroke-width="1.2" opacity="0.35"/>')
        for i in range(3))
    return (f'<span class="intensity-dots"><svg class="intensity-dots-svg" width="40" height="12" '
            f'viewBox="0 0 40 12">{o}</svg></span>')


def split_lead(t):
    """Decision: claim and evidence are two paragraphs. Strip the legacy dash."""
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


def quote(q, cs):
    tags = "".join(f'<span class="badge signal-quote-tag" style="background:{tbg(cs,i)}">{e(t)}</span>'
                   for i, t in enumerate(q["tags"]))
    pid = (f'<span class="speaker"><span class="bn-person-badge"><span class="bn-speaker-badge--split">'
           f'<span class="bn-speaker-badge-code">{e(q["pid"])}</span></span></span></span>'
           if q["pid"] else "")
    return (f'<blockquote><div class="quote-row"><a class="timecode">'
            f'<span class="timecode-bracket">[</span>{tc(q["t"])}'
            f'<span class="timecode-bracket">]</span></a><span class="quote-body">'
            f'<span class="quote-text">{e(q["text"])}</span> {pid}{tags}</span>{dots(q["intensity"])}</div></blockquote>')


def chip(label, score, cs="", flag=None):
    """Decision 1=C (mk-h-c), 7=G4 (flag: label score), 8 (Positive/Negative/Divided)."""
    sent = label.lower() in VALENCE
    cls = f'badge signal-card-hero mk-h-c{" badge-" + label.lower() if sent else ""}'
    style = "" if sent else f' style="background:{gbg(cs)}"'
    pre = f'<span class="mk-chip-flag">{e(flag)}:</span> ' if flag else ""
    return (f'<button class="{cls}"{style}>{pre}'
            f'<span class="signal-card-hero-label">{e(label)}</span>'
            f'<span class="signal-card-hero-score">{score:.2f}</span>'
            f'<span class="signal-card-hero-caret">▾</span></button>')


def pgrid(present, allp):
    return (f'<span class="participant-grid"><span class="participant-count">'
            f'{len(present)}/{len(allp)}</span>' +
            "".join(f'<span class="p-box{" p-present" if p in present else ""}">{e(p)}</span>'
                    for p in allp) + "</span>")


def sentiment_chip(quotes):
    """Decision 8 — one value, else Positive / Negative / Divided sentiments. No counts."""
    vals = {q["sentiment"] for q in quotes if q["sentiment"]}
    if not vals:
        return None
    if len(vals) == 1:
        return next(iter(vals))
    vs = {VALENCE.get(v) for v in vals} - {None}
    if vs == {"pos"}:
        return "Positive"
    if vs == {"neg"}:
        return "Negative"
    return "Divided sentiments"


# ── merged locations (decision 10 — M1) ────────────────────────────────────
def merge():
    loc = collections.defaultdict(lambda: {"facets": [], "quotes": {}})
    for c in CARDS:
        k = (c["project"], c["axis"], c["location"])
        m = loc[k]
        m["facets"].append(c)
        for q in c["quotes"]:
            qq = m["quotes"].setdefault(q["id"], dict(q, tags=[], groups=[]))
            for t in q["tags"]:
                if t not in qq["tags"]:
                    qq["tags"].append(t)
            if c["group"] not in qq["groups"]:
                qq["groups"].append(c["group"])
    for k, m in loc.items():
        m["facets"].sort(key=lambda c: (-len(c["quotes"]), c["group"]))
        m["quotes"] = sorted(m["quotes"].values(), key=lambda q: (q["pid"], q["t"]))
        m["all"] = m["facets"][0]["all_participants"]
    return loc

MERGED = merge()


def headline(m):
    for c in m["facets"]:
        if c["elab"]:
            return c["elab"][0], c["elab"][2]
    return None, None


def card(m, *, mode="flat", score=0.42, flag=None):
    """mode: flat = one quote list · facets = groups fused inside the card."""
    lead_name, elab = headline(m)
    top = m["facets"][0]
    cs = top["colour_set"]
    lab = (sentiment_chip(m["quotes"]) if top["group"] == "Sentiment" else top["group"])
    head = f'<div class="signal-card-location">{e(lead_name or m["facets"][0]["location"])}</div>'
    if elab:
        a, b = split_lead(elab)
        head += f'<p class="signal-elaboration bn-lead-para bn-lead-claim">{e(a)}</p>'
        if b:
            head += f'<p class="signal-elaboration bn-lead-para bn-lead-rest">{e(b)}</p>'

    if mode == "flat":
        qs = m["quotes"][:CAP]
        body = "".join(quote(q, cs) for q in qs)
        more = len(m["quotes"]) - len(qs)
    else:
        body, more = "", 0
        for f in m["facets"]:
            fq = f["quotes"][:CAP]
            more += len(f["quotes"]) - len(fq)
            flab = sentiment_chip(f["quotes"]) if f["group"] == "Sentiment" else f["group"]
            fname = f["elab"][0] if f["elab"] else None
            body += (f'<div class="mk-facet"><div class="mk-facet-head">'
                     f'{chip(flab or f["group"], 0.30, f["colour_set"])}'
                     + (f'<span class="mk-facet-name">{e(fname)}</span>' if fname else "")
                     + "</div>" + "".join(quote(q, f["colour_set"]) for q in fq) + "</div>")

    foot = (f'<button class="signal-card-link signal-card-toggle">Show all '
            f'{len(m["quotes"])} quotes →</button>' if more > 0
            else '<button class="signal-card-link signal-card-toggle">Hide</button>')
    return (f'<div class="signal-card mk-v2 {"mk-facets" if mode=="facets" else ""}" '
            f'style="--card-accent:{gbg(cs)}">'
            f'<div class="signal-card-top"><div class="signal-card-right">'
            f'{chip(lab, score, cs, flag)}</div>'
            f'<div class="signal-card-identity">{head}</div></div>'
            f'<div class="signal-card-quotes">{body}</div>'
            f'<div class="signal-card-footer">{foot}'
            f'{pgrid({q["pid"] for q in m["quotes"]}, m["all"])}</div></div>')


OUT = []
def sec(n, t, why): OUT.append(f'<section class="mk-sec"><h2 id="s{n}">{n}. {t}</h2><p class="mk-why">{why}</p>')
def opt(tag, name, note=""): OUT.append(f'<div class="mk-opt"><div class="mk-optlabel"><b>{tag}</b> {name}{" — <i>"+note+"</i>" if note else ""}</div>')
def end(): OUT.append("</div>")
def ends(): OUT.append("</section>")
def head(loc): return f'<div class="analysis-codebook-heading">{e(loc)}</div>'
def pick(proj, loc): return MERGED[next(k for k in MERGED if k[0]==proj and k[2]==loc)]

ng = collections.Counter(len({f["group"] for f in m["facets"]}) for m in MERGED.values())
one_grp = sum(v for k, v in ng.items() if k == 1)

# ── 1. the decided card ────────────────────────────────────────────────────
sec(1, "The decided card",
    f"Every decision applied: <b>C</b> chip, <b>V1</b> no eyebrow, <b>Q2</b> capped at {CAP}, "
    "<b>W1</b> floated hero with the text wrapping under it, claim and evidence as two "
    "paragraphs. Real card. <b>This is the 80% case</b> — "
    f"{one_grp} of {len(MERGED)} merged locations carry a single group, so the merge changes "
    "nothing for them.")
m = pick("IKEA with uxfriends", "IKEA.co.uk Homepage")
OUT.append(head(m["facets"][0]["location"]) + '<div class="signal-cards mk-narrow">' + card(m) + "</div>")
ends()

# ── 2. the collision ───────────────────────────────────────────────────────
sec(2, "M1 and F1 collide",
    "<b>F1 fuses the cards at a location. M1 leaves one card per location.</b> "
    f"There is nothing left to fuse — {one_grp} of {len(MERGED)} locations were already one card, "
    "and M1 makes the other "
    f"{len(MERGED)-one_grp} into one too. The seam has no job unless it moves <i>inside</i> the card.")
m = pick("project-ikea", "Search & Sort Results")
opt("X0", "M1 as drawn", "four groups flattened into one quote list — the binding is gone")
OUT.append(head("Search & Sort Results") + '<div class="signal-cards mk-narrow">' + card(m, score=0.61) + "</div>")
end()
opt("X1", "the seam moves inside", "groups become fused facets — F1's hairline, one card")
OUT.append(head("Search & Sort Results") + '<div class="signal-cards mk-narrow">' + card(m, mode="facets", score=0.61) + "</div>")
end()
ends()

# ── 3. the binding ─────────────────────────────────────────────────────────
sec(3, "What X0 costs, on a real card",
    "<code>Recognition over recall</code> is what makes <code>visible options</code> and "
    "<code>memory burden</code> one finding — <i>“does the interface minimise memory load?”</i>. "
    "Flattened, the two sit in a list with nothing saying why they belong together.")
cand = [m for m in MERGED.values() if any(len(f["tags"]) > 1 and f["group"] != "Sentiment" for f in m["facets"])]
if cand:
    m = max(cand, key=lambda m: len({f["group"] for f in m["facets"]}))
    opt("X0", "flattened", "the group name appears nowhere")
    OUT.append(head(m["facets"][0]["location"]) + '<div class="signal-cards mk-narrow">' + card(m, score=0.55) + "</div>")
    end()
    opt("X1", "facets kept", "each group keeps its chip and its binding")
    OUT.append(head(m["facets"][0]["location"]) + '<div class="signal-cards mk-narrow">' + card(m, mode="facets", score=0.55) + "</div>")
    end()
ends()

# ── 4. worst case ──────────────────────────────────────────────────────────
worst = max(MERGED.values(), key=lambda m: len({f["group"] for f in m["facets"]}))
sec(4, "The worst case",
    f'<code>{e(worst["facets"][0]["project"])} · {e(worst["facets"][0]["location"])}</code> — '
    f'<b>{len({f["group"] for f in worst["facets"]})} groups over '
    f'{len(worst["quotes"])} distinct quotes.</b> X1 gives every group a facet, so a card with '
    "more groups than quotes draws more chrome than content.")
opt("X0", "flattened", "reads fine — the groups were the problem, not the quotes")
OUT.append(head(worst["facets"][0]["location"]) + '<div class="signal-cards mk-narrow">' + card(worst, score=0.30) + "</div>")
end()
opt("X1", "facets kept", "seven facets, two quotes")
OUT.append(head(worst["facets"][0]["location"]) + '<div class="signal-cards mk-narrow">' + card(worst, mode="facets", score=0.30) + "</div>")
end()
ends()

# ── 5. chip trial (decision 7 + 8) ─────────────────────────────────────────
sec(5, "The chip — decision 7 and 8 together",
    "<b>G4</b> is your <code>Problem: frustration 0.42</code>. Decision 8's vocabulary supplies "
    "the label when a card carries several feelings: a single value stays itself, one valence "
    "becomes <code>Positive</code>/<code>Negative</code>, mixed becomes "
    "<code>Divided sentiments</code>. No counts.")
for tag, key, flag in [("G4a", ("Rockclimbing", "Safety, Risk Management, and Close Calls"), "Problem"),
                       ("G4b", ("project-ikea", "Shopping Bag"), "Niggle"),
                       ("G4c", ("IKEA with uxfriends", "Kitchenware Category"), "Win")]:
    try:
        m = pick(*key)
    except StopIteration:
        continue
    lab = sentiment_chip(m["quotes"]) or "—"
    opt(tag, f"<code>{flag}: {e(lab)}</code>", f'{e(key[1])}')
    OUT.append('<div class="signal-cards mk-narrow">' + card(m, score=0.42, flag=flag) + "</div>")
    end()
ends()

# ── 6. the tail under Q2 ───────────────────────────────────────────────────
qn = [len(m["quotes"]) for m in MERGED.values()]
over = sum(1 for x in qn if x > CAP)
big = max(MERGED.values(), key=lambda m: len(m["quotes"]))
sec(6, "Q2's cap after the merge",
    f"Merged cards run min 1 / median 3 / max <b>{max(qn)}</b> quotes. "
    f"<b>{over} of {len(qn)} ({100*over//len(qn)}%)</b> exceed the cap of {CAP}, so the "
    "“Show all” control is the exception, not the rule. Worst case below.")
OUT.append(head(big["facets"][0]["location"]) + '<div class="signal-cards mk-narrow">' + card(big, score=0.33) + "</div>")
ends()

# ── 7. the heading typography ──────────────────────────────────────────────
sec(7, "The heading, against the navigator",
    "Decision 2 put the location in the heading and took it off the cards. The two already "
    "agree on weight (<code>--bn-weight-emphasis</code>, 490) and colour "
    "(<code>--bn-colour-text</code>) and differ in exactly one property: <b>size</b>. "
    "<code>.toc-sub-heading</code> is <code>--bn-text-caption</code> (0.75rem) with "
    "<code>--bn-text-caption-lh</code>; <code>.analysis-codebook-heading</code> is "
    "<code>--bn-text-label</code> (0.8125rem) and sets no line-height at all. "
    "<b>Decided: H-c</b> \u2014 the analysis heading takes the Quotes lens's own token, so the "
    "location reads identically in the lens that names it and the lens it links to. "
    "Applied as the base everywhere on this page; H-a and H-b are scoped overrides kept "
    "only as the record of what was rejected.")
m = pick("project-ikea", "Shopping Bag")
opt("H-a", "rejected \u2014 shipped", "--bn-text-label 0.8125rem, bottom rule")
OUT.append('<div class="mk-head-a">' + head("Shopping Bag") +
           '<div class="signal-cards mk-narrow">' + card(m, score=0.60) + "</div></div>")
end()
opt("H-b", "rejected \u2014 the navigator", "--bn-text-caption 0.75rem + --bn-text-caption-lh 1.4")
OUT.append('<div class="mk-head-b">' + head("Shopping Bag") +
           '<div class="signal-cards mk-narrow">' + card(m, score=0.60) + "</div></div>")
end()
opt("H-c", "<b>DECIDED</b> \u2014 matches the Quotes lens",
    "--bn-text-heading 1.125rem, no bottom rule \u2014 the same object, in the lens this one links to")
OUT.append('<div class="mk-head-c">' + head("Shopping Bag") +
           '<div class="signal-cards mk-narrow">' + card(m, score=0.60) + "</div></div>")
end()
OUT.append('<p class="mk-why">All three already agree on weight '
           '(<code>--bn-weight-emphasis</code> 490) and colour. The only question is which '
           'step of the scale, and whether the location reads as <b>navigation</b> (H-b, the '
           'sidebar) or as <b>content</b> (H-c, the Quotes lens). V1 made it content.</p>')
ends()

nav = "".join(f'<a href="#s{i}">{i}</a>' for i in range(1, 8))
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal card v2</title>
<style>{(HERE/'theme.css').read_text()}</style><style>{(HERE/'page.css').read_text()}</style>
<style>{(HERE/'v2.css').read_text()}</style><style>{RIBBON_CSS}</style></head><body><div class="mk-page">{ribbon("v2")}
<header class="mk-head"><h1>Signal card &mdash; v2, decisions applied</h1>
<p><b>Carried in:</b> 1=C chip &middot; 2=V1 no eyebrow &middot; 3=F1 fused &middot;
4=Q2 capped at {CAP} &middot; 5=W1 floated hero &middot; 6=earned-words headline &middot;
7=G4 chip &middot; 8=S2 + Positive/Negative/Divided &middot; 10=M1 merged.
Real data throughout. <b>The open question is &sect;2</b> &mdash; M1 leaves F1 nothing to fuse.</p>
<nav class="mk-nav">{nav}</nav></header>{''.join(OUT)}
<footer class="mk-foot">{len(MERGED)} merged locations from {len(CARDS)} cards.</footer>
</div></body></html>"""
(ROOT / "docs/mockups/signal-card-v2.html").write_text(page)
print(f"wrote docs/mockups/signal-card-v2.html ({len(page):,} bytes) · "
      f"{len(MERGED)} merged locations · {one_grp} single-group")
