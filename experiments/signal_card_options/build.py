"""Build docs/mockups/signal-card-options.html — labelled options, real data.

    .venv/bin/python experiments/signal_card_options/harvest.py
    .venv/bin/python experiments/signal_card_options/build.py

Every quote, elaboration, signal name and tag on the page is real, harvested
from trial-runs/. CSS is baked from bristlenose/theme by harvest-time sibling
(theme.css) plus page.css for mockup chrome only. Nothing here is proposing —
each block is an option with a label, for choosing between.
"""
import html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
CARDS = json.load(open(HERE / "cards.json"))

GROUP_BG = {"ux": "--bn-group-ux", "emo": "--bn-group-emo", "task": "--bn-group-task",
            "trust": "--bn-group-trust", "opp": "--bn-group-opp",
            "sentiment": "--bn-group-sentiment"}
SLOTS = {"ux": 5, "emo": 6, "task": 5, "trust": 5, "opp": 5, "sentiment": 7}
VALENCE = {"frustration": "neg", "confusion": "neg", "doubt": "neg", "surprise": "neu",
           "satisfaction": "pos", "delight": "pos", "confidence": "pos"}

e = html.escape


def find(project, location, group=None, axis=None):
    for c in CARDS:
        if c["project"] == project and c["location"] == location:
            if group and c["group"] != group:
                continue
            if axis and c["axis"] != axis:
                continue
            return c
    return None


def at(project, location):
    return [c for c in CARDS if c["project"] == project and c["location"] == location]


def group_bg(cs):
    return f"var({GROUP_BG[cs]})" if cs in GROUP_BG else "var(--bn-group-none)"


def tag_bg(cs, i):
    return f"var(--bn-{cs}-{(i % SLOTS[cs]) + 1}-bg)" if cs in SLOTS else "var(--bn-custom-bg)"


def tc(sec):
    sec = int(sec or 0)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def dots(v):
    out = []
    for i in range(3):
        f = ('fill="var(--dot-colour, var(--bn-colour-muted))" opacity="0.7"'
             if (v or 0) >= i + 1 else
             'fill="none" stroke="var(--dot-colour, var(--bn-colour-muted))" '
             'stroke-width="1.2" opacity="0.35"')
        out.append(f'<circle cx="{7 + i * 16}" cy="6" r="5" {f}/>')
    return ('<span class="intensity-dots"><svg class="intensity-dots-svg" width="40" '
            f'height="12" viewBox="0 0 40 12">{"".join(out)}</svg></span>')


def split_lead(text):
    """Claim / evidence, as two paragraphs.

    `||` is the author's marker and always wins. The cached corpus predates
    prompt v0.2.0, so some entries join the halves with an em dash instead and
    some carry BOTH — a `||` followed by a dash. The dash is punctuation for a
    run-on and has no job once the halves are separate paragraphs, so it is
    stripped either way.
    """
    if "||" in text:
        lead, _, rest = text.partition("||")
    elif " \u2014 " in text:
        lead, _, rest = text.partition(" \u2014 ")
    else:
        lead, rest = text, ""
    lead = lead.strip().rstrip("\u2014-").strip()
    rest = rest.strip().lstrip("\u2014-").strip()
    if lead and lead[-1] not in ".!?":
        lead += "."
    if rest:
        rest = rest[0].upper() + rest[1:]
    return lead, rest


def quote(q, card, show_tags=True, show_pid=True):
    tags = ""
    if show_tags:
        for i, t in enumerate(q["tags"]):
            tags += (f'<span class="badge signal-quote-tag" '
                     f'style="background:{tag_bg(card["colour_set"], i)}">{e(t)}</span>')
    pid = (f'<span class="speaker"><span class="bn-person-badge">'
           f'<span class="bn-speaker-badge--split">'
           f'<span class="bn-speaker-badge-code">{e(q["pid"])}</span>'
           f'</span></span></span>'
           if show_pid and q["pid"] else "")
    return (f'<blockquote><div class="quote-row">'
            f'<a class="timecode"><span class="timecode-bracket">[</span>{tc(q["t"])}'
            f'<span class="timecode-bracket">]</span></a>'
            f'<span class="quote-body"><span class="quote-text">{e(q["text"])}</span> '
            f'{pid}{tags}</span>{dots(q["intensity"])}</div></blockquote>')


def pgrid(card):
    allp = card["all_participants"] or card["participants"]
    present = set(card["participants"])
    boxes = "".join(f'<span class="p-box{" p-present" if p in present else ""}">{e(p)}</span>'
                    for p in allp)
    return (f'<span class="participant-grid"><span class="participant-count">'
            f'{len(present)}/{len(allp)}</span>{boxes}</span>')


def hero(card, score=None, size="", label=None, flag=None):
    cs = card["colour_set"]
    lab = label if label is not None else card["group"]
    sent = lab.lower() in VALENCE
    cls = f'badge signal-card-hero{" mk-h-" + size if size else ""}'
    if sent:
        cls += f" badge-{lab.lower()}"
        style = ""
    else:
        style = f' style="background:{group_bg(cs)}"'
    sc = (f'<span class="signal-card-hero-score">{score:.2f}</span>'
          if score is not None else "")
    flagchip = (f'<span class="mk-flag mk-flag-{flag.lower()}">{e(flag)}</span>'
                if flag else "")
    return (f'<div class="signal-card-right"><button class="{cls}"{style}>'
            f'<span class="signal-card-hero-label">{e(lab)}</span>{sc}'
            f'<span class="signal-card-hero-caret">▾</span></button>{flagchip}</div>')


def card_html(card, *, eyebrow=True, title=None, score=0.0, quotes="all", chip=None,
              hero_size="", flag=None, show_tags=True, extra_class=""):
    """One signal card. Every switch is a mockup option, not a proposal."""
    cs = card["colour_set"]
    accent = group_bg(cs) if cs else "var(--bn-colour-accent)"
    name, elab = None, None
    if card["elab"]:
        name, _pattern, elab = card["elab"]
    head = ""
    if eyebrow:
        head += f'<span class="signal-card-source">{e(card["location"])}</span>'
    t = title if title is not None else (name or card["location"])
    head += f'<div class="signal-card-location">{e(t)}</div>'
    if elab:
        lead, rest = split_lead(elab)
        head += f'<p class="signal-elaboration bn-lead-para bn-lead-claim">{e(lead)}</p>'
        if rest:
            head += f'<p class="signal-elaboration bn-lead-para bn-lead-rest">{e(rest)}</p>'
    qs = card["quotes"]
    shown = qs[:1] if quotes == "one" else (qs[:4] if quotes == "cap4" else qs)
    hidden = len(qs) - len(shown)
    body = "".join(quote(q, card, show_tags=show_tags) for q in shown)
    foot = (f'<button class="signal-card-link signal-card-toggle">'
            f'{"Show all %d quotes →" % len(qs) if hidden else "Hide"}</button>')
    return (f'<div class="signal-card {extra_class}" style="--card-accent:{accent}">'
            f'<div class="signal-card-top"><div class="signal-card-identity">{head}</div>'
            f'{hero(card, score, hero_size, chip, flag)}</div>'
            f'<div class="signal-card-quotes">{body}</div>'
            f'<div class="signal-card-footer">{foot}{pgrid(card)}</div></div>')


# ── page ──────────────────────────────────────────────────────────────────
OUT = []


def section(n, title, why):
    OUT.append(f'<section class="mk-sec"><h2 id="s{n}">{n}. {title}</h2>'
               f'<p class="mk-why">{why}</p>')


def opt(tag, name, note=""):
    OUT.append(f'<div class="mk-opt"><div class="mk-optlabel"><b>{tag}</b> {name}'
               f'{" — <i>" + note + "</i>" if note else ""}</div>')


def endopt():
    OUT.append("</div>")


def endsec():
    OUT.append("</section>")


def heading(loc):
    return f'<div class="analysis-codebook-heading">{e(loc)}</div>'

# ══ 1. HERO CHIP SIZE ══════════════════════════════════════════════════════
surface = find("project-ikea", "Search & Sort Results", "Surface")
sent_ss = find("project-ikea", "Search & Sort Results", "Sentiment")

section(1, "Hero chip — steps down the ladder",
        "Same card, same real elaboration, five chip sizes. Everything else held constant. "
        "<b>A</b> is what ships today.")
for tag, size, note in [("A", "", "shipped — --bn-text-body, --bn-space-sm"),
                        ("B", "b", "one step: --bn-text-label"),
                        ("C", "c", "two steps: label + tighter padding"),
                        ("D", "d", "three: --bn-text-badge, mono score only"),
                        ("E", "e", "four: badge scale, score and caret only on hover")]:
    opt(tag, f"chip size {tag}", note)
    OUT.append(f'<div class="signal-cards mk-narrow">'
               f'{card_html(surface, score=0.61, hero_size=size, quotes="all")}</div>')
    endopt()
endsec()

# ══ 2. THE LOCATION HEADING ════════════════════════════════════════════════
section(2, "Where the location lives",
        "Real cards from <code>project-ikea · Search &amp; Sort Results</code>. "
        "Today the location is printed three times in one viewport: once as the heading, "
        "once per card as the eyebrow.")
ss = [c for c in at("project-ikea", "Search & Sort Results") if c["elab"]][:2]
opt("V0", "shipped", "heading + eyebrow on every card")
OUT.append(heading("Search & Sort Results") +
           '<div class="signal-cards mk-narrow">' +
           "".join(card_html(c, eyebrow=True, score=s) for c, s in zip(ss, (0.61, 0.30))) +
           "</div>")
endopt()
opt("V1", "heading owns it", "eyebrow removed — the heading is the only statement of place")
OUT.append(heading("Search & Sort Results") +
           '<div class="signal-cards mk-narrow">' +
           "".join(card_html(c, eyebrow=False, score=s) for c, s in zip(ss, (0.61, 0.30))) +
           "</div>")
endopt()
endsec()

# ══ 3. FUSION ══════════════════════════════════════════════════════════════
section(3, "Fusing a location's cards",
        "Outer radius on the first and last card only, hairline between. "
        "<b>A single-card location needs no rule</b> — an only child is both first and last, "
        "so it keeps all four corners. 69% of section locations are that case.")
opt("F0", "separate cards", "shipped — gap, own corners, hover shadow")
OUT.append(heading("Search & Sort Results") + '<div class="signal-cards mk-narrow">' +
           "".join(card_html(c, eyebrow=False, score=s) for c, s in zip(ss, (0.61, 0.30))) +
           "</div>")
endopt()
opt("F1", "fused stack", "hairline seam, outer corners only, no shadow")
OUT.append(heading("Search & Sort Results") + '<div class="signal-cards mk-fused mk-narrow">' +
           "".join(card_html(c, eyebrow=False, score=s) for c, s in zip(ss, (0.61, 0.30))) +
           "</div>")
endopt()
opt("F2", "fused, single card", "the 69% case — nothing special needed")
OUT.append(heading("IKEA.co.uk Homepage") + '<div class="signal-cards mk-fused mk-narrow">' +
           card_html(find("IKEA with uxfriends", "IKEA.co.uk Homepage"),
                     eyebrow=False, score=0.44) + "</div>")
endopt()
endsec()

# ══ 4. QUOTE DISCLOSURE ════════════════════════════════════════════════════
big = max(CARDS, key=lambda c: len(c["quotes"]))
section(4, "How many quotes are open",
        f"Median card carries 4 quotes; the longest in the corpus carries "
        f"<b>{len(big['quotes'])}</b> (<code>{e(big['project'])} · {e(big['location'])}</code>). "
        "Q2 is shown truncated below so the page stays readable — in the app it would be "
        f"{len(big['quotes'])} blockquotes under one heading.")
opt("Q0", "one visible", "shipped — lead quote plus 'Show all N'")
OUT.append('<div class="signal-cards mk-narrow">' +
           card_html(sent_ss, eyebrow=False, score=0.56, quotes="one") + "</div>")
endopt()
opt("Q1", "all open", "your preference — works at the median")
OUT.append('<div class="signal-cards mk-narrow">' +
           card_html(sent_ss, eyebrow=False, score=0.56, quotes="all") + "</div>")
endopt()
opt("Q2", "open, capped at 4", "the tail case — cap plus a real count")
OUT.append('<div class="signal-cards mk-narrow">' +
           card_html(big, eyebrow=False, score=0.33, quotes="cap4") + "</div>")
endopt()
endsec()

# ══ 5. ELABORATION WRAP ════════════════════════════════════════════════════
long_elab = max((c for c in CARDS if c["elab"]), key=lambda c: len(c["elab"][2]))
section(5, "The elaboration gutter",
        "<b>Shipped bug.</b> <code>.signal-card-top</code> is a flex row; the elaboration sits "
        "inside <code>.signal-card-identity</code>, its left child. It therefore <i>cannot</i> "
        "reach the space under the hero — the gutter is unreachable by construction. "
        f"Real card, {len(long_elab['elab'][2])}-character elaboration.")
opt("W0", "shipped", "elaboration trapped in the left flex column")
OUT.append('<div class="signal-cards mk-narrow">' +
           card_html(long_elab, eyebrow=False, score=0.47, quotes="cap4") + "</div>")
endopt()
opt("W1", "hero floated right", "text runs beside the chip, then wraps under it — full width")
OUT.append('<div class="signal-cards mk-narrow mk-wrap-float">' +
           card_html(long_elab, eyebrow=False, score=0.47, quotes="cap4") + "</div>")
endopt()
opt("W2", "elaboration below the row", "full width, but the space beside the chip stays empty")
OUT.append('<div class="signal-cards mk-narrow mk-wrap-below">' +
           card_html(long_elab, eyebrow=False, score=0.47, quotes="cap4") + "</div>")
endopt()
endsec()

# ══ 6. THE TITLE ═══════════════════════════════════════════════════════════
def earned(name, group):
    gw = {w.lower() for w in group.split()}
    pw = {"success", "gap", "tension", "recovery", "strength", "mix", "signal"}
    words = name.split()
    return sum(1 for w in words if w.lower() not in gw and w.lower() not in pw), len(words)

named = [c for c in CARDS if c["elab"]]
scored = sorted(named, key=lambda c: earned(c["elab"][0], c["group"])[0] / max(1, earned(c["elab"][0], c["group"])[1]))
section(6, "What the headline spends its words on",
        "Every name below is real. The rule under test: <b>no word may be the group name or "
        "the pattern word</b>, because both are already on the card. Scored as "
        "earned-words / total-words.")
OUT.append('<table class="mk-tbl"><tr><th>group chip</th><th>headline</th>'
           '<th>earned</th><th>what a reader learns from the headline alone</th></tr>')
for c in scored[:6] + scored[-6:]:
    n = c["elab"][0]
    k, tot = earned(n, c["group"])
    cls = "mk-bad" if k / tot < 0.5 else ("mk-ok" if k / tot < 1 else "mk-good")
    lead = c["elab"][2].split("||")[0].strip()
    OUT.append(f'<tr class="{cls}"><td><code>{e(c["group"])}</code></td><td><b>{e(n)}</b></td>'
               f'<td>{k}/{tot}</td><td class="mk-lead">{e(lead[:110])}</td></tr>')
OUT.append("</table>")
OUT.append('<p class="mk-why">The bottom rows spend every word on the chip beside them. '
           'The top rows tell you something. Same prompt, same run.</p>')
endsec()

# ══ 7. THE FLAG CHIP ═══════════════════════════════════════════════════════
section(7, "Where <code>Win / Problem / Niggle / Success / Surprising</code> goes",
        "Already computed for every sentiment signal (<code>classify_flag</code>), already on "
        "the wire, rendered nowhere. Note this corner is where the <code>pattern</code> chip "
        "failed on 13 Sep — <i>“competed with the score for this exact corner.”</i>")
pol = find("Rockclimbing", "Safety, Risk Management, and Close Calls", "Sentiment")
for tag, name, note, flag, lab in [
        ("G0", "no flag", "shipped", None, None),
        ("G1", "stacked under the chip", "your suggestion", "Problem", None),
        ("G2", "flag replaces the group", "the flag IS the judgement", None, None),
        ("G3", "flag as the chip, value beneath", "verdict first", "confidence", "Problem")]:
    opt(tag, name, note)
    OUT.append('<div class="signal-cards mk-narrow">' +
               card_html(pol, eyebrow=False, score=0.42, quotes="cap4",
                         chip=lab if tag == "G3" else ("Problem" if tag == "G2" else None),
                         flag=flag if tag == "G1" else (lab and "confidence" if tag == "G3" else None)) +
               "</div>")
    endopt()
endsec()

# ══ 8. SENTIMENT CARD SHAPES ═══════════════════════════════════════════════
def shape(c):
    s = [q["sentiment"] for q in c["quotes"] if q["sentiment"]]
    if not s:
        return None
    vals = {x for x in s}
    pos = {q["pid"] for q in c["quotes"] if VALENCE.get(q["sentiment"]) == "pos"}
    neg = {q["pid"] for q in c["quotes"] if VALENCE.get(q["sentiment"]) == "neg"}
    if pos - neg and neg - pos:
        return "polarised"
    if pos and neg:
        return "ambivalent"
    return "one value" if len(vals) == 1 else "one valence"

sent_cards = [c for c in CARDS if c["group"] == "Sentiment" and c["quotes"]]
buckets = {}
for c in sent_cards:
    sh = shape(c)
    if sh and (sh not in buckets or (c["elab"] and not buckets[sh]["elab"])):
        buckets[sh] = c
counts = {k: sum(1 for c in sent_cards if shape(c) == k) for k in buckets}

section(8, "The four sentiment card shapes",
        "Once the Sentiment <i>group</i> card is retired and sentiment <i>values</i> become "
        "labels again, a location's sentiment falls into one of four shapes. "
        "Real cards, one of each. Counts are over all "
        f"{len(sent_cards)} sentiment cards in the corpus.")
for name in ("one value", "one valence", "ambivalent", "polarised"):
    c = buckets.get(name)
    if not c:
        continue
    vals = sorted({q["sentiment"] for q in c["quotes"] if q["sentiment"]})
    why = {"one value": "every quote the same feeling — the strongest claim",
           "one valence": "different feelings, same direction — one story",
           "ambivalent": "the same person feels both ways — the product is mixed",
           "polarised": "different people, opposed — <b>the users differ</b>"}[name]
    opt(f"S{'  ' and list('1234')[('one value','one valence','ambivalent','polarised').index(name)]}",
        name, f"{counts[name]} of {len(sent_cards)} cards · {', '.join(vals)} · {why}")
    OUT.append(f'{heading(c["location"])}<div class="signal-cards mk-narrow mk-fused">' +
               card_html(c, eyebrow=False, score=0.38, quotes="cap4",
                         chip=vals[0] if len(vals) == 1 else None) + "</div>")
    endopt()
endsec()

# ══ 9. THE POLARISED CHIP ══════════════════════════════════════════════════
section(9, "The chip when a card has two feelings",
        "A polarised card has no single value, so “the value goes in the chip” breaks exactly "
        "here. Real card: <code>Rockclimbing · Safety, Risk Management</code> — "
        "p2 frustrated at intensity 3, p3/p5/p9 confident at intensity 2.")
for tag, name, chip, note in [
        ("P1", "both values, opposed", "confidence ⇄ frustration",
         "honest, instant, wants width"),
        ("P2", "verdict plus count", "Divided · 4 people",
         "compact, hides which feelings"),
        ("P3", "dominant plus split marker", "confidence · 3‑1",
         "one chip, buries the interesting half")]:
    opt(tag, name, note)
    OUT.append('<div class="signal-cards mk-narrow">' +
               card_html(pol, eyebrow=False, score=0.42, quotes="cap4", chip=chip) + "</div>")
    endopt()
endsec()

# ══ 10. MERGE ══════════════════════════════════════════════════════════════
topnav = at("project-ikea", "Top Navigation")
section(10, "Six cards, or one",
        f"<code>project-ikea · Top Navigation</code> draws <b>{len(topnav)} cards</b> from "
        f"<b>{len({q['id'] for c in topnav for q in c['quotes']})} distinct quotes</b>. "
        f"{sum(1 for c in topnav if not c['elab'])} of the {len(topnav)} carry no elaboration, "
        "so they print the location as their headline.")
opt("M0", "shipped", "every group its own card")
OUT.append(heading("Top Navigation") + '<div class="signal-cards mk-narrow">' +
           "".join(card_html(c, score=0.3 - i * 0.03, quotes="all")
                   for i, c in enumerate(topnav)) + "</div>")
endopt()

merged = dict(topnav[0])
seen, qs = set(), []
for c in topnav:
    for q in c["quotes"]:
        if q["id"] not in seen:
            seen.add(q["id"])
            qq = dict(q)
            qq["tags"] = sorted({t for c2 in topnav for q2 in c2["quotes"]
                                 if q2["id"] == q["id"] for t in q2["tags"]})
            qs.append(qq)
merged["quotes"] = sorted(qs, key=lambda q: (q["pid"], q["t"]))
merged["participants"] = sorted({q["pid"] for q in qs})
opt("M1", "merged to the location", "one card, every quote once, carrying all its tags")
OUT.append(heading("Top Navigation") + '<div class="signal-cards mk-narrow mk-fused">' +
           card_html(merged, eyebrow=False, score=0.30, quotes="all",
                     title="Navigation Reliability Tension") + "</div>")
endopt()
OUT.append('<p class="mk-why"><b>The cost of M1:</b> the group binding is lost. '
           '<code>Recognition over recall</code> is what makes <code>visible options</code> '
           'and <code>memory burden</code> one finding; merged, they sit next to a sentiment '
           'quote with nothing saying why they belong together.</p>')
endsec()

# ── write ──────────────────────────────────────────────────────────────────
nav = "".join(f'<a href="#s{i}">{i}</a>' for i in range(1, 11))
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Signal card options</title>
<style>{(HERE / "theme.css").read_text()}</style>
<style>{(HERE / "page.css").read_text()}</style>
</head><body><div class="mk-page">
<header class="mk-head"><h1>Signal card &mdash; options</h1>
<p>Every quote, elaboration, signal name, tag and count on this page is real, harvested from
<code>trial-runs/</code>. CSS is baked from <code>bristlenose/theme</code>; only the mockup
chrome and the lettered variants are new. <b>Nothing here is a proposal</b> &mdash; each block
is a labelled option to choose between or reject.</p>
<nav class="mk-nav">{nav}</nav></header>
{''.join(OUT)}
<footer class="mk-foot">Built {__import__('datetime').date.today():%-d %b %Y} from
{len(CARDS)} cards / {len({(c['project'], c['axis'], c['location']) for c in CARDS})} locations /
{sum(1 for c in CARDS if c['elab'])} real elaborations.</footer>
</div></body></html>"""

dst = ROOT / "docs/mockups"
(dst / "signal-card-options.html").write_text(page)
print(f"wrote docs/mockups/signal-card-options.html  ({len(page):,} bytes)")
