"""The sentiment chip label — formalised, with provenance on every constant.

Derived from 27 human judgements on real cards (19 Sep 2026); the working is
in calibrate_fit.py and the cards in sentiment-calibration.html.

PROVENANCE MARKERS — every parameter carries one. Do not silently promote a
GUESS to a fact by using it for a while.

  MEASURED  the judgements separate on this, and it survived a confound check
  STATED    the user asserted it directly; this corpus cannot test it
  GUESS     neither; a placeholder that has to be revisited

THE ONE THING THAT IS MEASURED is that VOLUME decides whether a card commits
to naming a feeling, and RATIO does not. Two cases carry it: 3:1 on weight 6
was judged Mixed, 60/40 on weight 30 was judged by its feeling. At weight >= 7
every card was named, both valences, 10 of 10.

THE SEVEN SENTIMENT VALUES ARE SETTLED and literature-grounded. Nothing here
reasons about what they mean or whether any are interchangeable.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

VALENCE = {"frustration": "neg", "confusion": "neg", "doubt": "neg",
           "surprise": "neu",
           "satisfaction": "pos", "delight": "pos", "confidence": "pos"}

# ── parameters ────────────────────────────────────────────────────────────

#: STATED, and NOT VISIBLE IN THE JUDGEMENTS. "Close to 50/50
#: frustration/confusion is Negative; 65/35 is definitely frustration." No
#: judgement in the calibration set turns on it — cases 20, 23 and 24 name the
#: leading feeling at 42-47% of its own side, and case 23's leader beats the
#: runner-up 32 to 30. So this fires only on a near-exact tie, and is kept
#: because it was asserted, not because anything measured it.
VALUE_DOMINANCE = 0.60

#: GUESS, and the one that must not ship as an absolute. Total emotional
#: weight below which a clashing card refuses to name a feeling. Fitted to 12
#: negative cases (11 of 12 correct at 7); one positive case sits below the
#: line, so the corpus cannot say whether positives behave the same way.
#:
#: IT DOES NOT SCALE. weight is count x intensity, so a 20-participant study
#: clears any fixed bar everywhere and the rule stops discriminating — the same
#: defect docs/design-signal-strength.md §4 found in the composite. It needs
#: normalising before it ships: per participant, or against the study's own
#: median location. The SHAPE (volume, not ratio) is what is evidenced.
MIN_WEIGHT = 7.0


@dataclass(frozen=True)
class Label:
    text: str                 # what the chip says
    kind: str                 # "value" | "valence" | "mixed"
    why: str                  # the rung that fired, for the inspector


def _weights(quotes) -> tuple[Counter, Counter, float]:
    """Count x intensity, by value and by valence. Intensity is the whole
    point: a weak outlier must not count as much as a forceful one."""
    by_value, by_valence = Counter(), Counter()
    for q in quotes:
        v = q.get("sentiment")
        if v not in VALENCE:
            continue
        w = q.get("intensity") or 1
        by_value[v] += w
        by_valence[VALENCE[v]] += w
    return by_value, by_valence, sum(by_value.values())


def sentiment_label(quotes) -> Label | None:
    """The chip label for a location's sentiment quotes.

    Three rungs. The shape the judgements actually took: **name the leading
    feeling unless the card is both clashing AND thin.** There is no dominance
    test in the data — naming beats hedging almost everywhere, because `Mixed`
    on its own tells a researcher nothing.
    """
    by_value, by_valence, total = _weights(quotes)
    if not total:
        return None

    pos, neg = by_valence["pos"], by_valence["neg"]
    lead, lead_w = by_value.most_common(1)[0]

    # 1. Nothing opposing. `surprise` is NEUTRAL and never makes a card mixed —
    #    measured, 4 cards were called Mixed on a neutral quote alone, one of
    #    them 76 units of positive weight against 4 of neutral.
    #    MEASURED: 5 of 5 such cards were named by their leading feeling.
    if not (pos and neg):
        runner = ([w for v, w in by_value.most_common()] + [0])[1]
        if runner and lead_w / (lead_w + runner) < VALUE_DOMINANCE:
            return Label("Positive" if pos else "Negative", "valence",
                         "no leading feeling")                    # near-tie only
        return Label(lead, "value", "nothing opposing")

    # 2. Both directions, enough material. MEASURED: 10 of 10 named, both
    #    valences. Ratio is deliberately not consulted — 3:1 on weight 6 was
    #    hedged, 60/40 on weight 30 was named.
    if total >= MIN_WEIGHT:
        return Label(lead, "value", "clashing, but enough feeling to call it")

    # 3. Both directions, thin. THE ONLY UNCERTAIN RUNG — 12 cases, 8 Mixed,
    #    2 named a direction, 2 named a feeling, and nothing separates them
    #    that this corpus can see.
    return Label("Mixed sentiments", "mixed",
                 f"only {total:g} units of feeling, pulling both ways")
