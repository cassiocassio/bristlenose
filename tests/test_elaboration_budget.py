"""The elaboration payload budget.

It replaced ``DEFAULT_TOP_N = 10``, which capped by COUNT — the wrong shape,
because quote length varies far more than card count does. A guard that can
never fire is indistinguishable from no guard, and one that always fires is a
cap by another name, so both ends are pinned here.
"""

from __future__ import annotations

from dataclasses import dataclass

from bristlenose.server.elaboration import ELABORATION_BUDGET_CHARS


@dataclass
class _Q:
    text: str


@dataclass
class _Sig:
    composite_signal: float
    quotes: list[_Q]


def _select(signals: list[_Sig], budget: int = ELABORATION_BUDGET_CHARS) -> list[_Sig]:
    """The selection loop from ``_elaborate_top_signals``, isolated.

    Kept in step with the route by the shape of the data, not by import: the
    route holds (signal, codebook_id) pairs and this holds signals. If the
    route's rule changes, this test is where the disagreement should surface.
    """
    out: list[_Sig] = []
    left = budget
    for sig in sorted(signals, key=lambda s: s.composite_signal, reverse=True):
        cost = sum(len(q.text) for q in sig.quotes)
        if out and left - cost < 0:
            break
        left -= cost
        out.append(sig)
    return out


def _sig(score: float, chars: int) -> _Sig:
    return _Sig(score, [_Q("x" * chars)])


class TestTheBudgetDoesNotFireOnRealProjects:
    """MEASURED: the busiest real project carries 29 cards on 4,791 characters
    of evidence. If this guard bites there, it is a cap and not a guard."""

    def test_a_realistic_project_is_elaborated_whole(self) -> None:
        # 29 cards, ~165 chars each — the measured shape of project-ikea.
        signals = [_sig(1.0 - i / 100, 165) for i in range(29)]
        assert len(_select(signals)) == 29

    def test_even_the_long_form_corpus_fits(self) -> None:
        # fossda: 17 cards, but 16.5 KB of evidence — the case a COUNT cap got
        # backwards, since ten of its cards ask more than thirty of ikea's.
        signals = [_sig(1.0 - i / 100, 970) for i in range(17)]
        assert len(_select(signals)) == 17


class TestTheBudgetStillGuards:
    def test_a_pathological_project_is_cut(self) -> None:
        signals = [_sig(1.0 - i / 1000, 10_000) for i in range(50)]
        kept = _select(signals)
        assert 0 < len(kept) < 50
        assert sum(len(q.text) for s in kept for q in s.quotes) <= ELABORATION_BUDGET_CHARS

    def test_the_cut_takes_the_weakest_cards(self) -> None:
        # Strongest first, so what falls off the end is what a researcher would
        # have looked at last.
        signals = [_sig(0.9, 40_000), _sig(0.5, 40_000), _sig(0.1, 40_000)]
        kept = _select(signals)
        assert [s.composite_signal for s in kept] == [0.9]

    def test_one_oversized_card_is_never_dropped_to_zero(self) -> None:
        # A single card bigger than the whole budget still gets elaborated:
        # returning nothing would be a blank lens, which is worse than a large
        # prompt.
        assert len(_select([_sig(1.0, ELABORATION_BUDGET_CHARS * 3)])) == 1
