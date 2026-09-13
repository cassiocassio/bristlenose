"""The proposed signal-strength metric — see docs/design-signal-strength.md.

Nothing here is wired into the product.  It exists so the note's numbers can
be re-measured rather than re-argued.
"""
from __future__ import annotations

import math

WEIGHTS = {"voices": 0.50, "surprise": 0.35, "heat": 0.15}


def voices(participant_counts: list[int]) -> float:
    """Effective number of voices — Hill number of order 2, ``1 / sum(p^2)``.

    Bounded above by the number of participants who actually spoke, which
    ``metrics.simpsons_neff`` (the unbiased population estimator) is not: it
    reads 10.00 for ``[2, 1, 1, 1]`` in an eight-participant study.
    """
    n = sum(participant_counts)
    if n == 0:
        return 0.0
    return 1.0 / sum((c / n) ** 2 for c in participant_counts)


def _lcomb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def surprise(k: int, K_r: int, n_c: int, K_all: int) -> float:
    """Mid-p left tail of Hypergeometric(K_all, n_c, K_r) at k.

    0.5 == exactly what this study produces here anyway; -> 1 notably
    concentrated; -> 0 notably absent.  Returns the null value 0.5 when there
    is no variation to see (the group covers every quote, or the location is
    the whole study).

    Computed in log space: the exact big-integer form costs 1.2 s at 20k
    quotes, this costs 1.1 ms and agrees to 1.6e-13 across the corpus.
    """
    if K_all <= 0 or K_r <= 0 or n_c <= 0 or n_c >= K_all or K_r >= K_all:
        return 0.5
    den = _lcomb(K_all, K_r)

    def pmf(i: int) -> float:
        return math.exp(_lcomb(n_c, i) + _lcomb(K_all - n_c, K_r - i) - den)

    lo = max(0, K_r + n_c - K_all)
    return sum(pmf(i) for i in range(lo, k)) + 0.5 * pmf(k)


def heat(cell_mean: float, label_mean: float) -> float:
    """How hot this cell is *for this label*, 0.5 == this label's own average.

    The naive form (``cell_mean / 3``) is structurally higher for sentiment
    labels than for codebook groups, because a sentiment label selects quotes
    BY their emotional content and a codebook group selects by topic.
    MEASURED across the three projects carrying both kinds, the naive form's
    median differs by +0.333 between them; this form differs by -0.007.
    """
    r = (cell_mean / label_mean) if label_mean else 1.0
    return r / (1 + r)


def strength(
    participant_counts: list[int],
    mean_intensity: float,
    label_mean_intensity: float,
    k: int,
    K_r: int,
    n_c: int,
    K_all: int,
    P: int,
) -> tuple[float, float, float, float]:
    """Signal strength 0-100, plus its three factors.

    Every argument is counted in *study quotes* — unique quotes on the axis —
    never in matrix contributions.  That is the whole change.

    A *label* is a sentiment value (`frustration`) or a codebook group
    (`Structure`) — the arithmetic cannot tell them apart, which is the point.

    k                     quotes at this location carrying this label
    K_r                   all quotes at this location
    n_c                   all quotes in the study carrying this label
    K_all                 all quotes in the study, on this axis
    P                     participants in the study
    label_mean_intensity  mean intensity of every quote carrying this label
    """
    v = min(1.0, voices(participant_counts) / P) if P else 0.0
    s = surprise(k, K_r, n_c, K_all)
    h = heat(mean_intensity, label_mean_intensity) if mean_intensity else 0.5
    parts = {"voices": max(1e-6, v), "surprise": max(1e-6, s), "heat": max(1e-6, h)}
    g = math.exp(sum(w * math.log(parts[name]) for name, w in WEIGHTS.items()))
    return 100.0 * g, v, s, h


def ceiling(K_r: int, n_c: int, K_all: int, P: int, label_mean: float) -> float:
    """The best a card at this location for this label COULD have been.

    The label fills the location, one quote per participant, every quote at
    intensity 3.  Used to express a score as a share of what the study was
    capable of showing, rather than as an absolute claim.
    """
    k_hi = min(K_r, n_c)
    if k_hi < 1 or P < 1:
        return 0.0
    v = min(k_hi, P) / P
    s = surprise(k_hi, K_r, n_c, K_all)
    h = heat(3.0, label_mean)
    return 100.0 * math.exp(
        WEIGHTS["voices"] * math.log(max(1e-6, v))
        + WEIGHTS["surprise"] * math.log(max(1e-6, s))
        + WEIGHTS["heat"] * math.log(max(1e-6, h)))
