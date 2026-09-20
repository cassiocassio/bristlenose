"""A status ribbon, so a mockup says what it is when you open it.

`docs/mockups/STATUS.md` is the register and `docs/design-signal-card.md` §0 is
the lineage, but neither is in front of you when you double-click an HTML file.
Four of these mockups were made within 36 hours of each other and two are
superseded; opening the wrong one is the easy mistake. The ribbon is the fix.

One entry per page, below. Change it here, not in the page templates.
"""

DOC = "docs/design-signal-card.md"

#: page id → (generation, date, state, one line, what to open instead)
PAGES = {
    "options": (4, "19 Sep 2026", "SUPERSEDED",
                "The options menu — 29 labelled alternatives over real data. Kept because "
                "it is the record of what was <i>rejected</i>.",
                "signal-card-design-a.html"),
    "v2": (4, "19 Sep 2026", "SUPERSEDED",
           "First pass at applying the decisions. Built a hybrid that was neither a fused "
           "stack nor a merged card — the failure is the value, and it is why design B "
           "needs a location-level elaboration before it can exist.",
           "signal-card-design-a.html"),
    "design-a": (4, "20 Sep 2026", "CURRENT",
                 "<b>The shape.</b> Whole cards fused by their own borders. Spec for "
                 "&sect;3 of the design doc.", None),
    "rules": (4, "20 Sep 2026", "CURRENT",
              "<b>The review artefact.</b> Each rule stated formally, firing on a real card, "
              "with the counterfactual beside it. Read alongside design A, not instead.", None),
    "stages": (4, "20 Sep 2026", "CURRENT",
               "<b>What the build buys.</b> The same locations rendered as shipped, after "
               "tier 1, and after tier 2. Spec for &sect;9.", None),
    "valence": (3, "13 Sep 2026", "PARKED",
                "A side branch off generation 3: eleven candidate treatments for a card's "
                "<b>valence</b>, over 34 real elaborated cards. <b>Deferred, not rejected</b> — "
                "generation 4 fixed the card's own problems first, and <code>signal.pattern</code> "
                "still arrives on the wire, so nothing needs regenerating when it is picked up. "
                "Two sections have since been overtaken and are kept as the 13 Sep record, "
                "<i>not</i> as advice: <b>&sect;7</b> argued for deleting "
                "<code>classify_flag</code>, and decision 7 revived it as a chip prefix "
                "(<code>Problem: frustration 0.42</code>); <b>&sect;8</b>'s V1 <i>NAMED</i> "
                "proposed letting the headline carry valence, and decision 6 forbids it "
                "(no word may be the group name or the pattern word).",
                None),
    "calibration": (4, "19 Sep 2026", "INSTRUMENT",
                    "The labelling study behind <code>label_rule.py</code>. Its 27 judgements "
                    "are the entire evidence base for &sect;5 — and &sect;5a records that "
                    "they were made in the wrong volume regime.", None),
}

CSS = """
.mk-ribbon { display:flex; align-items:baseline; gap:var(--bn-space-sm); flex-wrap:wrap;
  padding:var(--bn-space-sm) var(--bn-space-md); margin-bottom:var(--bn-space-lg);
  border:1px solid var(--bn-colour-border); border-radius:var(--bn-radius-md);
  background:var(--bn-colour-hover); font-size:var(--bn-text-label); }
.mk-ribbon-state { font-family:var(--bn-font-mono); font-size:var(--bn-text-badge);
  letter-spacing:.06em; padding:2px 7px; border-radius:var(--bn-radius-sm);
  background:var(--bn-colour-text); color:var(--bn-colour-bg); flex:0 0 auto; }
.mk-ribbon-superseded .mk-ribbon-state { background:none; color:var(--bn-colour-muted);
  border:1px dashed var(--bn-colour-border); }
.mk-ribbon-superseded { opacity:.85; }
.mk-ribbon-gen { font-family:var(--bn-font-mono); font-size:var(--bn-text-badge);
  color:var(--bn-colour-muted); flex:0 0 auto; }
.mk-ribbon-body { flex:1 1 22rem; min-width:0; color:var(--bn-colour-muted);
  line-height:1.45; }
.mk-ribbon-body b { color:var(--bn-colour-text); }
"""


def ribbon(page_id: str) -> str:
    gen, date, state, line, instead = PAGES[page_id]
    # the dashed chip reads "not the page you want today" — true of PARKED too
    sup = " mk-ribbon-superseded" if state in ("SUPERSEDED", "PARKED") else ""
    go = (f' <b>Open <code>{instead}</code> instead.</b>' if instead else "")
    return (f'<div class="mk-ribbon{sup}">'
            f'<span class="mk-ribbon-state">{state}</span>'
            f'<span class="mk-ribbon-gen">generation {gen} · {date}</span>'
            f'<span class="mk-ribbon-body">{line}{go} '
            f'Lineage: <code>{DOC}</code> §0.</span></div>')
