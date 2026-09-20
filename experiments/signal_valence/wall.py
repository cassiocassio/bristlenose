#!/usr/bin/env python3
"""Build docs/mockups/signal-card-valence-wall.html — the density wall on its own.

An extract from the §5 wall of the big page, kept separate for one reason: the
full mockup is ~570 KB and the wall is the part you actually want to *look* at,
at the real chip size. Every mark here is at --bn-text-badge (11.5px), so this
is a sizing test, not an illustration.

    .venv/bin/python experiments/signal_valence/wall.py    # from the repo root

Shares cards.json and theme.css with build.py; both are gitignored (participant
quotes), so this rebuilds only on a machine that has the trial projects.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "signal_card_options"))
from ribbon import CSS as RIBBON_CSS  # noqa: E402
from ribbon import ribbon  # noqa: E402

OUT = "docs/mockups/signal-card-valence-wall.html"
BALLS = ["○", "◔", "◑", "◕", "●"]

#: the twelve cards, chosen to sit at the corpus proportions (48 / 26 / 18 / 8)
WALL = [
    "Fear-Confidence Tension", "Community Delight Strength", "Creative Flow Tension",
    "Homepage Orientation Gap", "Outdoor Transition Tension", "Entry Point Delight",
    "Inclusion Doubt Tension", "Career Friction Recovery", "Risk Confidence Tension",
    "Destination Delight", "Systemic Frustration", "Project Creation Delight",
]

#: only what this page draws — pulled out of the real baked theme, never retyped
TOKENS = [
    "--bn-colour-bg", "--bn-colour-text", "--bn-colour-muted", "--bn-colour-border",
    "--bn-colour-hover", "--bn-colour-positive", "--bn-colour-negative",
    "--bn-colour-error-text", "--bn-text-badge", "--bn-text-badge-lh", "--bn-text-label",
    "--bn-text-caption", "--bn-font-mono", "--bn-radius-pill", "--bn-radius-sm",
    "--bn-radius-md", "--bn-space-xs", "--bn-space-sm", "--bn-space-md", "--bn-space-lg",
    "--bn-weight-emphasis",
]


def ball(x: float) -> str:
    """Five stops. 0 and 1 are their own stops so ○ and ● mean exactly none and all."""
    if x <= 0:
        return BALLS[0]
    if x >= 1:
        return BALLS[4]
    if x < 0.375:
        return BALLS[1]
    if x < 0.625:
        return BALLS[2]
    return BALLS[3]


def main() -> None:
    cards = {c["name"]: c for c in json.load(open(os.path.join(HERE, "cards.json")))}
    theme = open(os.path.join(HERE, "theme.css")).read()

    tok = []
    for name in TOKENS:
        m = re.search(rf"^\s*{re.escape(name)}:\s*([^;]+);", theme, re.M)
        if m:
            tok.append(f"    {name}: {m.group(1).strip()};")
    missing = len(TOKENS) - len(tok)
    if missing:
        print(f"WARNING: {missing} token(s) did not resolve from the theme", file=sys.stderr)

    rows = []
    for name in WALL:
        c = cards[name]
        v = [q["val"] for q in c["quotes"]]
        pos, neg, tot = v.count(1), v.count(-1), len(v)
        rows.append((name, c["pattern"], pos, neg, tot, pos / tot, ball(pos / tot)))

    def column(title, fn):
        cells = "".join(
            f'<div class=m><span class=n>{r[0]}</span><span class=v>{fn(r)}</span></div>'
            for r in rows)
        return f"<div class=c><h4>{title}</h4>{cells}</div>"

    # the shipped chip, verbatim, as the control
    v0 = lambda r: f'<span class="pl pl-{r[1]}">{r[1].upper()}</span>'          # noqa: E731
    v2 = lambda r: f'<span class=cap>{r[1]}</span>'                             # noqa: E731
    v6b = lambda r: (                                                           # noqa: E731
        '<span class=st>'
        + (f'<i class=sp style=width:{r[2] / r[4] * 100:.3f}%></i>' if r[2] else "")
        + (f'<i class=sn style=width:{r[3] / r[4] * 100:.3f}%></i>' if r[3] else "")
        + '</span>')
    v10 = lambda r: f'<span class=hb>{r[6]}</span>'                             # noqa: E731
    v10b = lambda r: (f'<span class=hc style="--pct:{r[5] * 360:.1f}deg"></span>'  # noqa: E731
                      f'<span class=num>{r[2]}/{r[4]}</span>')
    v8 = lambda r: ""                                                           # noqa: E731

    stops = "".join(
        f'<div><i class=s3>{b}</i><i class=s2>{b}</i><i class=s1>{b}</i><u>{lab}</u></div>'
        for b, lab in zip(BALLS, ["0", "&lt;⅜", "½", "&lt;1", "all"]))

    html = f"""<meta charset=utf-8><title>Harvey balls at 11.5px</title><style>
:root {{ color-scheme: light dark;
{chr(10).join(tok)}
}}
body {{ background:var(--bn-colour-bg); color:var(--bn-colour-text);
  font:var(--bn-text-label)/1.45 Inter,-apple-system,system-ui,sans-serif; margin:0; padding:28px; }}
h1 {{ font-size:18px; margin:0 0 4px; font-weight:600; }}
p.l {{ color:var(--bn-colour-muted); font-size:12px; margin:0 0 22px; max-width:70ch; }}
.w {{ display:flex; gap:14px; align-items:flex-start; flex-wrap:wrap; }}
.c {{ flex:1 1 158px; min-width:150px; }}
h4 {{ font-size:11.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--bn-colour-muted);
  margin:0 0 6px; padding-bottom:3px; border-bottom:1px solid var(--bn-colour-border); font-weight:600; }}
.m {{ display:flex; justify-content:space-between; align-items:center; gap:6px; min-height:34px;
  padding:5px 4px; border-bottom:1px solid var(--bn-colour-border); }}
.n {{ font-size:11.5px; line-height:1.3; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.v {{ flex:0 0 auto; display:flex; align-items:center; gap:4px; }}
.pl {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); font-weight:520;
  text-transform:uppercase; letter-spacing:.06em; padding:var(--bn-space-xs) .45rem;
  border-radius:var(--bn-radius-sm); opacity:.9; }}
.pl-success {{ background:light-dark(#dcfce7,#14532d); color:light-dark(#166534,#86efac); }}
.pl-tension {{ background:light-dark(#fef3c7,#451a03); color:light-dark(#92400e,#fcd34d); }}
.pl-gap {{ background:light-dark(#fee2e2,#450a0a); color:light-dark(#991b1b,#fca5a5); }}
.pl-recovery {{ background:light-dark(#e0f2fe,#0c4a6e); color:light-dark(#075985,#7dd3fc); }}
.cap {{ font-size:var(--bn-text-badge); color:var(--bn-colour-muted); }}
.st {{ display:inline-flex; width:56px; height:5px; border-radius:var(--bn-radius-pill);
  overflow:hidden; background:var(--bn-colour-border); }}
.sp {{ background:var(--bn-colour-positive); }} .sn {{ background:var(--bn-colour-negative); }}
.hb {{ font-size:var(--bn-text-badge); line-height:1; color:var(--bn-colour-text); }}
.hc {{ display:inline-block; width:9px; height:9px; border-radius:50%; vertical-align:-1px;
  border:1px solid var(--bn-colour-text);
  background:conic-gradient(var(--bn-colour-text) 0 var(--pct), transparent var(--pct) 360deg); }}
.num {{ font-family:var(--bn-font-mono); font-size:var(--bn-text-badge); color:var(--bn-colour-muted); }}
.z {{ margin-top:26px; padding-top:14px; border-top:1px solid var(--bn-colour-border); }}
.z b {{ font-size:11.5px; }}
.zz {{ display:flex; gap:26px; margin-top:8px; align-items:flex-end; }}
.zz div {{ text-align:center; }}
.zz i {{ font-style:normal; display:block; }}
.s1 {{ font-size:11.5px; }} .s2 {{ font-size:23px; }} .s3 {{ font-size:46px; }}
.zz u {{ text-decoration:none; font-size:9.6px; color:var(--bn-colour-muted);
  font-family:var(--bn-font-mono); }}
{RIBBON_CSS}</style>
{ribbon('valence')}
<h1>Harvey balls at real size, in the wall</h1>
<p class=l>Twelve real cards at the corpus proportions (48 / 26 / 18 / 8). Every mark is at
<code>--bn-text-badge</code> = 11.5&thinsp;px, the real chip size. V10 is the bare glyph
(&#x25CB;&#x25D4;&#x25D1;&#x25D5;&#x25CF;); V10b is the same ball drawn in CSS with the count.
Shares come from <code>quotes.sentiment</code>, a stand-in for the model's per-quote verdict.</p>
<div class=w>
{column("V0 withdrawn", v0)}{column("V2 caption", v2)}{column("V6b stacked", v6b)}
{column("V10 harvey", v10)}{column("V10b harvey+", v10b)}{column("V8 absent", v8)}
</div>
<div class=z><b>The five stops, at 11.5&thinsp;px / 23&thinsp;px / 46&thinsp;px</b>
<div class=zz>{stops}</div></div>
"""
    head = ("<!-- Density wall extract from signal-card-valence.html — every mark at the real\n"
            "     11.5px chip size. Built by experiments/signal_valence/wall.py. 13 Sep 2026. -->\n")
    open(OUT, "w").write(head + html)
    print(f"wrote {OUT}  ({len(html) // 1024} KB, {len(rows)} cards)")


if __name__ == "__main__":
    main()
