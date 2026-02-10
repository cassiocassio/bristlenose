"""Low-level statistical functions for the analysis page.

Ported from the JS implementations in docs/mockups/mockup-analysis.html.
These are pure arithmetic — no I/O, no LLM calls, no Pydantic models.
Higher-level code (matrix builder, signal detector) calls these.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


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
    """Effective number of voices (Simpson's diversity index).

    Measures how evenly quotes are distributed across participants.
    9 quotes from 9 people → N_eff ≈ 9 (broad agreement).
    9 quotes from 1 person → N_eff = 1 (one person's rant).

    Uses the unbiased form: N*(N-1) / Σ ni*(ni-1).
    """
    n = 0
    sum_ni_ni_minus_1 = 0
    for ni in participant_counts:
        n += ni
        sum_ni_ni_minus_1 += ni * (ni - 1)
    if n <= 1:
        return float(n)
    if sum_ni_ni_minus_1 == 0:
        return float(n)  # perfect diversity — every quote from a different person
    return (n * (n - 1)) / sum_ni_ni_minus_1


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
