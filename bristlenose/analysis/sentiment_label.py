"""What the sentiment chip says.

**The goal, before the mechanism: the chip must never say "Sentiment".** That
is the framework's name, and naming the framework tells a researcher nothing —
they know they are reading sentiment. What they need is *which* sentiment, or,
when no single one is honest, which direction. So the label resolves to one of
the seven values, or ``Positive`` / ``Negative`` / ``Mixed sentiments``, and to
nothing else.

Fitted to 27 judgements a researcher made on real cards with the label hidden
(``docs/mockups/sentiment-calibration.html``). The reasoning, the measurements
and what is *not* settled are in ``docs/design-signal-card.md`` §5.

PROVENANCE MARKERS. Every constant carries one. Do not silently promote a
GUESS to a fact by using it for a while.

  MEASURED  the judgements separate on this, and it survived a confound check
  STATED    asserted directly by the researcher; this corpus cannot test it
  GUESS     neither; a placeholder that has to be revisited

**The one measured finding is that VOLUME decides whether a card commits to a
name, and RATIO does not.** Two cases carry it: 3:1 on six units of feeling was
judged mixed, 60/40 on thirty units was named by its feeling.

**The seven values are settled and literature-grounded.** Nothing here reasons
about what they mean or whether any are interchangeable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

#: The seven, and their direction. `surprise` is NEUTRAL — it is neither good
#: nor bad, and a card carrying only praise and one surprised remark is a
#: positive card. MEASURED: four cards were labelled mixed on a neutral quote
#: alone, one of them 76 units of positive weight against 4 of neutral.
VALENCE: dict[str, str] = {
    "frustration": "neg",
    "confusion": "neg",
    "doubt": "neg",
    "surprise": "neu",
    "satisfaction": "pos",
    "delight": "pos",
    "confidence": "pos",
}

#: The two summary labels and the hedge. Not members of the sentiment
#: vocabulary — they are this design's own strings, and they need their own
#: locale keys (see ``docs/design-signal-card.md`` §9, item J).
POSITIVE = "Positive"
NEGATIVE = "Negative"
MIXED = "Mixed sentiments"

#: STATED, and NOT VISIBLE IN THE JUDGEMENTS. "Close to 50/50
#: frustration/confusion is Negative; 65/35 is definitely frustration." No
#: judgement in the calibration set turns on it — cards naming their leading
#: feeling at 42–47% of their own side are common, and one names it where the
#: leader beats the runner-up 32 to 30. It therefore fires only on a near-tie,
#: and is kept because it was asserted, not because anything measured it.
VALUE_DOMINANCE = 0.60

#: GUESS, and the one that must not be mistaken for settled. Total emotional
#: weight below which a card pulling both ways refuses to name a feeling.
#: Fitted to 12 negative cases (11 of 12 correct at 7).
#:
#: IT DOES NOT SCALE, and on real data it is never binding. weight is
#: count x intensity, so a bigger study clears any fixed bar everywhere — the
#: same defect ``docs/design-signal-strength.md`` §4 found in the composite.
#: MEASURED: on the one substantial real study in the corpus (136k words, 9
#: participants) only 18% of cards fall below it, and the rule never returns
#: MIXED at all; on the short fixtures 84–94% fall below it. Twenty of the 27
#: judgements were made in the fixture regime. §5a is the record.
MIN_WEIGHT = 7.0


@dataclass(frozen=True)
class Label:
    """What the chip says, and why — the reason is for the run inspector."""

    text: str
    kind: str  # "value" | "valence" | "mixed"
    why: str


def _sentiments_of(q) -> list[str]:
    """The sentiment values a quote carries.

    **Two shapes, and the one that renders is the second.** A quote from the
    `/analysis/sentiment` lens carries a single `sentiment`. A quote on the
    CODEBOOK path — which is what the analysis lens actually draws — carries no
    such field at all: the sentiment framework's *tags* ARE the seven values,
    so they arrive in `tag_names`.

    A quote may carry more than one. It contributes its full intensity to each,
    because it genuinely expressed both: splitting the weight would make a
    quote saying two things count for less than one saying one.
    """
    if isinstance(q, dict):
        direct, tags = q.get("sentiment"), q.get("tag_names") or q.get("tagNames") or []
    else:
        direct, tags = getattr(q, "sentiment", None), getattr(q, "tag_names", None) or []
    if direct in VALENCE:
        return [direct]
    return [t for t in tags if t in VALENCE]


def _weights(quotes) -> tuple[Counter, Counter, float]:
    """Count x intensity, by value and by direction.

    Intensity is the whole point: a weak dissenting voice must not weigh the
    same as a forceful one, and "amount of feeling" is what the judgements
    turned out to be deciding on.
    """
    by_value: Counter = Counter()
    by_valence: Counter = Counter()
    for q in quotes:
        w = (q.get("intensity") if isinstance(q, dict) else getattr(q, "intensity", None)) or 1
        for v in _sentiments_of(q):
            by_value[v] += w
            by_valence[VALENCE[v]] += w
    return by_value, by_valence, sum(by_value.values())


def sentiment_label(quotes) -> Label | None:
    """The chip label for a location's sentiment quotes, or None if it has none.

    Three rungs, and the shape the judgements took: **name the leading feeling
    unless the card is both pulling both ways AND thin.** There is no dominance
    test in the data — naming beats hedging almost everywhere, because
    ``Mixed sentiments`` on its own tells a researcher nothing, and it has to
    earn its place by meaning *inconsistent responses, worth investigating*
    rather than *the numbers were close*.
    """
    by_value, by_valence, total = _weights(quotes)
    if not total:
        return None

    pos, neg = by_valence["pos"], by_valence["neg"]
    lead, lead_w = by_value.most_common(1)[0]

    # 1. Nothing opposing. MEASURED: 5 of 5 such cards were named by their
    #    leading feeling. A neutral quote does not count as opposition.
    if not (pos and neg):
        runner = ([w for _, w in by_value.most_common()] + [0])[1]
        if runner and lead_w / (lead_w + runner) < VALUE_DOMINANCE:  # STATED
            return Label(POSITIVE if pos else NEGATIVE, "valence", "no leading feeling")
        return Label(lead, "value", "nothing opposing")

    # 2. Both directions, and enough material to commit. MEASURED: 10 of 10
    #    named, both directions. Ratio is deliberately not consulted here.
    if total >= MIN_WEIGHT:  # GUESS
        return Label(lead, "value", "clashing, but enough feeling to call it")

    # 3. Both directions, thin. THE ONLY UNCERTAIN RUNG — 12 cases, 8 mixed,
    #    2 naming a direction, 2 naming a feeling, and nothing this corpus can
    #    see separates them.
    return Label(MIXED, "mixed", f"only {total:g} units of feeling, pulling both ways")
