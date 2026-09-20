"""Low-level statistical functions for the analysis page.

Ported from the JS implementations in docs/mockups/mockup-analysis.html.
These are pure arithmetic — no I/O, no LLM calls, no Pydantic models.
Higher-level code (matrix builder, signal detector) calls these.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Finding flags — sentiment valence and signal classification
# ---------------------------------------------------------------------------

# Maps sentiment names to valence direction.
SENTIMENT_VALENCE: dict[str, str] = {
    "frustration": "negative",
    "confusion": "negative",
    "doubt": "negative",
    "surprise": "neutral",
    "satisfaction": "positive",
    "delight": "positive",
    "confidence": "positive",
}

# Tunable thresholds — starting guesses, calibrate with real data via HUD.
# Minimum composite signal to flag at all.
FLAG_MIN_SIGNAL: float = 0.02
# Minimum composite signal for narrow flags (Success / Niggle).
FLAG_SMALL_SIGNAL: float = 0.01
# Breadth ratio (n_eff / total_participants) for broad flags (Win / Problem).
FLAG_BREADTH: float = 0.3
# Mean intensity threshold for Problem (vs Niggle).
FLAG_INTENSITY: float = 2.0


def classify_flag(
    sentiment: str,
    composite: float,
    n_eff: float,
    total_participants: int,
    mean_int: float,
) -> str | None:
    """Classify a sentiment-based signal into a finding flag.

    Returns one of "Win", "Problem", "Niggle", "Success", "Surprising", or
    None if the signal is too weak to flag.

    **"Pattern" is documented in the design and unreachable here.** It was in
    this list until 20 Sep 2026, when the truing pass measured that no branch
    below can return it — the only occurrence of the string in this module was
    the docstring advertising it. `docs/design-finding-weight.md` predicted
    exactly that ("Pattern won't fire") when the scheme was written, and
    `docs/design-signal-card.md` §7.5 named the docstring as the surviving
    claim. Removed rather than implemented, because nothing has yet needed a
    sixth word and inventing a branch to satisfy a comment is the wrong
    direction of fit.

    Only meaningful for sentiment-based signals where *sentiment* is one of the
    seven canonical sentiment names.  For codebook-group signals, returns None.
    """
    valence = SENTIMENT_VALENCE.get(sentiment)
    if valence is None:
        return None  # not a sentiment column (e.g. codebook group name)

    if composite < FLAG_SMALL_SIGNAL:
        return None  # too weak to claim anything

    breadth = n_eff / total_participants if total_participants > 0 else 0.0

    if valence == "neutral":
        # Surprise — only flag if signal is strong enough
        return "Surprising" if composite >= FLAG_MIN_SIGNAL else None

    if composite < FLAG_MIN_SIGNAL:
        # Below the broad-flag threshold — check if strong enough for narrow flags
        if valence == "positive":
            return "Success"
        return "Niggle"

    if valence == "positive":
        return "Win" if breadth >= FLAG_BREADTH else "Success"

    # valence == "negative"
    if breadth >= FLAG_BREADTH and mean_int >= FLAG_INTENSITY:
        return "Problem"
    return "Niggle"


def concentration_ratio(
    cell_count: int,
    row_total: int,
    col_total: int,
    grand_total: int,
) -> float:
    """How overrepresented a sentiment is within a section vs the study overall.

    Returns observed/expected where:
      expected = col_total / grand_total  (overall rate of this sentiment)
      observed = cell_count / row_total   (rate within this section)

    Result: 1.0 = expected, >1 = overrepresented, <1 = underrepresented.
    """
    if grand_total == 0 or row_total == 0 or col_total == 0:
        return 0.0
    expected = col_total / grand_total
    observed = cell_count / row_total
    return 0.0 if expected == 0 else observed / expected


def simpsons_neff(participant_counts: Sequence[int]) -> float:
    """Effective number of voices — the inverse Simpson index, 1 / Σ pᵢ².

    Measures how evenly quotes are distributed across participants.
    9 quotes from 9 people → N_eff = 9 (broad agreement).
    9 quotes from 1 person → N_eff = 1 (one person's rant).

    **Bounded above by the number of people who actually spoke**, which is what
    the card claims: the figure is rendered as "Agree. N" under the tooltip
    "effective number of voices", and a number of voices cannot exceed the
    voices there were.

    This used to be the *unbiased* form, ``N*(N-1) / Σ nᵢ*(nᵢ-1)`` — an
    estimator of the diversity of the population the quotes were drawn from,
    which is a different question and is not bounded by the sample's richness.
    It agreed with the two cases named above and diverged everywhere between
    them: ``[2,1,1,1]`` — four people — read **10.00**, and on an
    eight-participant study that is more effective voices than the study had
    participants.  Measured 13 Sep 2026 across the trial corpus, 14 of 103
    shipped cards overstated, 7 of them reading breadth 1.00 ("every
    participant") on fewer people than that, and one pushing the breadth factor
    of ``composite_signal`` above 1.0 — a term that is supposed to be a share.
    The ``Math.min(100, ...)`` clamp on the card's bar (``agreePct`` in
    ``AnalysisPage.tsx``) exists because the overflow was noticed there and
    papered over rather than fixed here.
    """
    n = sum(participant_counts)
    if n <= 0:
        return 0.0
    return (n * n) / sum(ni * ni for ni in participant_counts)


def mean_intensity(intensities: Sequence[int]) -> float:
    """Arithmetic mean of intensity values (1–3 scale).

    Returns 0 for an empty sequence.
    """
    if not intensities:
        return 0.0
    return sum(intensities) / len(intensities)


def composite_signal(
    conc_ratio: float,
    n_eff: float,
    total_participants: int,
    m_intensity: float,
) -> float:
    """Single "signal strength" score combining all three metrics.

    Each component is normalised to 0–1 before multiplication:
      conc_ratio   — used as-is (already a ratio)
      n_eff        — divided by total_participants
      m_intensity  — divided by 3 (max intensity)
    """
    if total_participants == 0:
        return 0.0
    return conc_ratio * (n_eff / total_participants) * (m_intensity / 3)


def adjusted_residual(
    observed: int,
    row_total: int,
    col_total: int,
    grand_total: int,
) -> float:
    """Adjusted standardised residual for heatmap cell colouring.

    Measures how much a cell deviates from statistical independence.
    Values > 2 indicate notable concentration; < -2 indicate depletion.
    """
    if grand_total == 0 or row_total == 0 or col_total == 0:
        return 0.0
    expected = (row_total * col_total) / grand_total
    if expected == 0:
        return 0.0
    denom = math.sqrt(
        expected * (1 - row_total / grand_total) * (1 - col_total / grand_total)
    )
    return 0.0 if denom == 0 else (observed - expected) / denom
