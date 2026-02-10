"""Tests for bristlenose.analysis.metrics — pure math functions."""

from __future__ import annotations

import pytest

from bristlenose.analysis.metrics import (
    adjusted_residual,
    composite_signal,
    concentration_ratio,
    mean_intensity,
    simpsons_neff,
)

# ---------------------------------------------------------------------------
# concentration_ratio
# ---------------------------------------------------------------------------


class TestConcentrationRatio:
    """concentration_ratio(cell_count, row_total, col_total, grand_total)."""

    def test_exactly_expected(self) -> None:
        """If a section has the same sentiment rate as the study, ratio = 1.0."""
        # 10 quotes in section, 2 are frustration; 100 total, 20 are frustration
        # observed = 2/10 = 0.2, expected = 20/100 = 0.2 → ratio = 1.0
        assert concentration_ratio(2, 10, 20, 100) == pytest.approx(1.0)

    def test_overrepresented(self) -> None:
        """Ratio > 1 when sentiment appears more than expected."""
        # 5 of 10 are frustration; overall only 10 of 100
        # observed = 0.5, expected = 0.1 → ratio = 5.0
        assert concentration_ratio(5, 10, 10, 100) == pytest.approx(5.0)

    def test_underrepresented(self) -> None:
        """Ratio < 1 when sentiment appears less than expected."""
        # 1 of 10 are frustration; overall 50 of 100
        # observed = 0.1, expected = 0.5 → ratio = 0.2
        assert concentration_ratio(1, 10, 50, 100) == pytest.approx(0.2)

    def test_grand_total_zero(self) -> None:
        assert concentration_ratio(5, 10, 20, 0) == 0.0

    def test_row_total_zero(self) -> None:
        assert concentration_ratio(0, 0, 20, 100) == 0.0

    def test_col_total_zero(self) -> None:
        assert concentration_ratio(0, 10, 0, 100) == 0.0

    def test_all_zeros(self) -> None:
        assert concentration_ratio(0, 0, 0, 0) == 0.0


# ---------------------------------------------------------------------------
# simpsons_neff
# ---------------------------------------------------------------------------


class TestSimpsonsNeff:
    """simpsons_neff(participant_counts)."""

    def test_perfect_diversity(self) -> None:
        """9 quotes from 9 different participants → N_eff = 9."""
        assert simpsons_neff([1, 1, 1, 1, 1, 1, 1, 1, 1]) == pytest.approx(9.0)

    def test_single_participant(self) -> None:
        """All quotes from one person → N_eff = 1."""
        assert simpsons_neff([9]) == pytest.approx(1.0)

    def test_two_equal(self) -> None:
        """Two participants with equal counts → N_eff ≈ 2.25 (unbiased form)."""
        # N=10, Σni(ni-1) = 20+20 = 40, N*(N-1)/40 = 90/40 = 2.25
        assert simpsons_neff([5, 5]) == pytest.approx(2.25)

    def test_skewed(self) -> None:
        """One dominant participant — N_eff should be low."""
        # 7 from p1, 1 from p2, 1 from p3 — total 9
        # N*(N-1) = 72, Σni(ni-1) = 42+0+0 = 42 → 72/42 ≈ 1.714
        assert simpsons_neff([7, 1, 1]) == pytest.approx(72 / 42)

    def test_empty(self) -> None:
        """Empty list → 0."""
        assert simpsons_neff([]) == pytest.approx(0.0)

    def test_single_quote(self) -> None:
        """One quote total → N_eff = 1."""
        assert simpsons_neff([1]) == pytest.approx(1.0)

    def test_three_unequal(self) -> None:
        """3 participants: [4, 3, 2] — total 9."""
        # N*(N-1) = 72, Σni(ni-1) = 12+6+2 = 20 → 72/20 = 3.6
        assert simpsons_neff([4, 3, 2]) == pytest.approx(3.6)


# ---------------------------------------------------------------------------
# mean_intensity
# ---------------------------------------------------------------------------


class TestMeanIntensity:
    """mean_intensity(intensities)."""

    def test_uniform(self) -> None:
        assert mean_intensity([2, 2, 2]) == pytest.approx(2.0)

    def test_mixed(self) -> None:
        assert mean_intensity([1, 2, 3]) == pytest.approx(2.0)

    def test_all_max(self) -> None:
        assert mean_intensity([3, 3, 3, 3]) == pytest.approx(3.0)

    def test_single(self) -> None:
        assert mean_intensity([1]) == pytest.approx(1.0)

    def test_empty(self) -> None:
        assert mean_intensity([]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# composite_signal
# ---------------------------------------------------------------------------


class TestCompositeSignal:
    """composite_signal(conc_ratio, n_eff, total_participants, m_intensity)."""

    def test_perfect_everything(self) -> None:
        """Max concentration, full diversity, max intensity → conc * 1.0 * 1.0."""
        # conc=5.0, neff=10, total=10, intensity=3
        # → 5.0 * (10/10) * (3/3) = 5.0
        assert composite_signal(5.0, 10.0, 10, 3.0) == pytest.approx(5.0)

    def test_half_diversity(self) -> None:
        # conc=2.0, neff=5, total=10, intensity=2
        # → 2.0 * 0.5 * (2/3) ≈ 0.667
        assert composite_signal(2.0, 5.0, 10, 2.0) == pytest.approx(2.0 * 0.5 * (2 / 3))

    def test_zero_participants(self) -> None:
        assert composite_signal(2.0, 5.0, 0, 2.0) == 0.0

    def test_zero_intensity(self) -> None:
        assert composite_signal(2.0, 5.0, 10, 0.0) == pytest.approx(0.0)

    def test_zero_neff(self) -> None:
        assert composite_signal(2.0, 0.0, 10, 2.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# adjusted_residual
# ---------------------------------------------------------------------------


class TestAdjustedResidual:
    """adjusted_residual(observed, row_total, col_total, grand_total)."""

    def test_exactly_expected(self) -> None:
        """Cell matches independence → residual ≈ 0."""
        # row=50, col=40, grand=100 → expected=20, observed=20
        assert adjusted_residual(20, 50, 40, 100) == pytest.approx(0.0)

    def test_positive_residual(self) -> None:
        """More than expected → positive residual."""
        # row=50, col=40, grand=100 → expected=20, observed=30
        expected = 20.0
        import math

        denom = math.sqrt(expected * (1 - 50 / 100) * (1 - 40 / 100))
        want = (30 - expected) / denom
        assert adjusted_residual(30, 50, 40, 100) == pytest.approx(want)
        assert adjusted_residual(30, 50, 40, 100) > 0

    def test_negative_residual(self) -> None:
        """Less than expected → negative residual."""
        # row=50, col=40, grand=100 → expected=20, observed=10
        assert adjusted_residual(10, 50, 40, 100) < 0

    def test_grand_total_zero(self) -> None:
        assert adjusted_residual(5, 10, 20, 0) == 0.0

    def test_row_total_zero(self) -> None:
        assert adjusted_residual(0, 0, 20, 100) == 0.0

    def test_col_total_zero(self) -> None:
        assert adjusted_residual(0, 10, 0, 100) == 0.0

    def test_row_equals_grand(self) -> None:
        """When row_total == grand_total, denom factor (1 - row/grand) = 0 → 0."""
        assert adjusted_residual(10, 100, 20, 100) == 0.0

    def test_col_equals_grand(self) -> None:
        """When col_total == grand_total, denom factor (1 - col/grand) = 0 → 0."""
        assert adjusted_residual(10, 20, 100, 100) == 0.0
