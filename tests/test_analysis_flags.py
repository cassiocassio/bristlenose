"""Tests for classify_flag — finding flag classification."""

from __future__ import annotations

from bristlenose.analysis.metrics import (
    FLAG_INTENSITY,
    FLAG_MIN_SIGNAL,
    FLAG_SMALL_SIGNAL,
    SENTIMENT_VALENCE,
    classify_flag,
)

# ---------------------------------------------------------------------------
# Valence map completeness
# ---------------------------------------------------------------------------


class TestSentimentValence:
    """SENTIMENT_VALENCE covers all 7 canonical sentiments."""

    def test_all_sentiments_present(self) -> None:
        expected = {
            "frustration", "confusion", "doubt",
            "surprise",
            "satisfaction", "delight", "confidence",
        }
        assert set(SENTIMENT_VALENCE.keys()) == expected

    def test_negative_sentiments(self) -> None:
        for s in ("frustration", "confusion", "doubt"):
            assert SENTIMENT_VALENCE[s] == "negative"

    def test_positive_sentiments(self) -> None:
        for s in ("satisfaction", "delight", "confidence"):
            assert SENTIMENT_VALENCE[s] == "positive"

    def test_neutral_sentiments(self) -> None:
        assert SENTIMENT_VALENCE["surprise"] == "neutral"


# ---------------------------------------------------------------------------
# classify_flag
# ---------------------------------------------------------------------------


class TestClassifyFlag:
    """classify_flag(sentiment, composite, n_eff, total_participants, mean_int)."""

    # -- Non-sentiment columns return None -----------------------------------

    def test_codebook_group_returns_none(self) -> None:
        """Column labels that aren't sentiments get no flag."""
        assert classify_flag("Usability", 0.5, 5.0, 10, 2.5) is None

    def test_empty_string_returns_none(self) -> None:
        assert classify_flag("", 0.5, 5.0, 10, 2.5) is None

    # -- Too weak to flag ----------------------------------------------------

    def test_below_small_signal_returns_none(self) -> None:
        """Composite below FLAG_SMALL_SIGNAL → no flag at all."""
        tiny = FLAG_SMALL_SIGNAL * 0.5
        assert classify_flag("frustration", tiny, 1.0, 10, 2.0) is None

    def test_exactly_at_small_signal_gets_flag(self) -> None:
        """At the threshold, a flag is assigned."""
        result = classify_flag("frustration", FLAG_SMALL_SIGNAL, 1.0, 10, 2.0)
        assert result is not None

    # -- Surprising (neutral) ------------------------------------------------

    def test_surprise_strong_signal(self) -> None:
        """Surprise with strong composite → Surprising."""
        assert classify_flag("surprise", FLAG_MIN_SIGNAL, 3.0, 10, 2.0) == "Surprising"

    def test_surprise_weak_signal(self) -> None:
        """Surprise below MIN_SIGNAL but above SMALL_SIGNAL → None."""
        mid = (FLAG_SMALL_SIGNAL + FLAG_MIN_SIGNAL) / 2
        assert classify_flag("surprise", mid, 1.0, 10, 1.0) is None

    def test_surprise_very_weak(self) -> None:
        """Surprise below SMALL_SIGNAL → None."""
        assert classify_flag("surprise", FLAG_SMALL_SIGNAL * 0.5, 1.0, 10, 1.0) is None

    # -- Win (broad positive) ------------------------------------------------

    def test_win_broad_positive(self) -> None:
        """Positive sentiment, strong signal, broad agreement → Win."""
        # n_eff=4, total=10 → breadth=0.4 >= 0.3
        assert classify_flag("satisfaction", 0.1, 4.0, 10, 2.0) == "Win"

    def test_win_delight(self) -> None:
        assert classify_flag("delight", 0.1, 5.0, 10, 2.5) == "Win"

    def test_win_confidence(self) -> None:
        assert classify_flag("confidence", 0.1, 3.0, 10, 1.5) == "Win"

    # -- Success (narrow positive) -------------------------------------------

    def test_success_narrow_positive(self) -> None:
        """Positive sentiment, strong signal, narrow agreement → Success."""
        # n_eff=2, total=10 → breadth=0.2 < 0.3
        assert classify_flag("satisfaction", 0.1, 2.0, 10, 2.0) == "Success"

    def test_success_weak_positive(self) -> None:
        """Positive sentiment, below MIN_SIGNAL but above SMALL → Success."""
        mid = (FLAG_SMALL_SIGNAL + FLAG_MIN_SIGNAL) / 2
        assert classify_flag("delight", mid, 1.0, 10, 1.0) == "Success"

    # -- Problem (broad negative, high intensity) ----------------------------

    def test_problem_broad_negative_intense(self) -> None:
        """Negative sentiment, broad, high intensity → Problem."""
        # n_eff=4, total=10, intensity=2.5
        assert classify_flag("frustration", 0.1, 4.0, 10, 2.5) == "Problem"

    def test_problem_at_intensity_threshold(self) -> None:
        """Exactly at FLAG_INTENSITY threshold → Problem."""
        assert classify_flag("confusion", 0.1, 4.0, 10, FLAG_INTENSITY) == "Problem"

    # -- Niggle (narrow negative, or broad but low intensity) ----------------

    def test_niggle_narrow_negative(self) -> None:
        """Negative sentiment, narrow → Niggle regardless of intensity."""
        assert classify_flag("frustration", 0.1, 2.0, 10, 3.0) == "Niggle"

    def test_niggle_broad_but_low_intensity(self) -> None:
        """Negative sentiment, broad but low intensity → Niggle."""
        assert classify_flag("doubt", 0.1, 4.0, 10, 1.5) == "Niggle"

    def test_niggle_weak_negative(self) -> None:
        """Negative sentiment, below MIN_SIGNAL → Niggle."""
        mid = (FLAG_SMALL_SIGNAL + FLAG_MIN_SIGNAL) / 2
        assert classify_flag("confusion", mid, 1.0, 10, 1.0) == "Niggle"

    # -- Edge cases ----------------------------------------------------------

    def test_zero_participants(self) -> None:
        """Zero total participants → breadth=0 → narrow flag or None."""
        result = classify_flag("satisfaction", 0.1, 0.0, 0, 2.0)
        # breadth=0, positive → Success (narrow)
        assert result == "Success"

    def test_breadth_exactly_at_threshold(self) -> None:
        """Breadth exactly at FLAG_BREADTH → broad."""
        # n_eff=3, total=10 → breadth=0.3 == threshold
        assert classify_flag("satisfaction", 0.1, 3.0, 10, 2.0) == "Win"

    def test_breadth_just_below_threshold(self) -> None:
        """Breadth just below FLAG_BREADTH → narrow."""
        # n_eff=2.9, total=10 → breadth=0.29 < 0.3
        assert classify_flag("satisfaction", 0.1, 2.9, 10, 2.0) == "Success"

    def test_all_flags_are_valid_strings(self) -> None:
        """Every possible non-None return is one of the six defined flags."""
        valid_flags = {"Win", "Problem", "Pattern", "Niggle", "Success", "Surprising"}
        for sentiment in SENTIMENT_VALENCE:
            for comp in (FLAG_SMALL_SIGNAL, FLAG_MIN_SIGNAL, 0.1, 0.5):
                for n_eff in (1.0, 3.0, 5.0):
                    result = classify_flag(sentiment, comp, n_eff, 10, 2.5)
                    if result is not None:
                        assert result in valid_flags, (
                            f"Unexpected flag {result!r} for "
                            f"{sentiment}, comp={comp}, n_eff={n_eff}"
                        )


# ---------------------------------------------------------------------------
# Integration: flag field flows through Signal dataclass
# ---------------------------------------------------------------------------


class TestSignalFlagField:
    """Signal dataclass has the flag field with correct default."""

    def test_default_is_none(self) -> None:
        from bristlenose.analysis.models import Signal

        s = Signal(
            location="Dashboard",
            source_type="section",
            sentiment="frustration",
            count=5,
            participants=["p1", "p2"],
            n_eff=2.0,
            mean_intensity=2.0,
            concentration=1.5,
            composite_signal=0.1,
            confidence="moderate",
        )
        assert s.flag is None

    def test_flag_can_be_set(self) -> None:
        from bristlenose.analysis.models import Signal

        s = Signal(
            location="Dashboard",
            source_type="section",
            sentiment="frustration",
            count=5,
            participants=["p1", "p2"],
            n_eff=2.0,
            mean_intensity=2.0,
            concentration=1.5,
            composite_signal=0.1,
            confidence="moderate",
            flag="Problem",
        )
        assert s.flag == "Problem"
