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


class TestTheFlagOnThePathThatRenders:
    """`_serialize_signal` re-classifies, and its denominator is the STUDY's.

    Every other test in this file calls `classify_flag` directly, so the one
    call site a researcher's browser actually reaches was unasserted. It was
    also wrong: it passed the card's own participant count, and `n_eff` is
    bounded above by that same number, so `breadth` sat near 1 on every card
    and `FLAG_BREADTH` could never bind. The broad/narrow split — the whole
    reason the vocabulary has six words rather than two — was collapsed.
    """

    @staticmethod
    def _signal(**over):
        from bristlenose.analysis.models import Signal, SignalQuote

        base = dict(
            location="Shopping bag", source_type="section", sentiment="Sentiment",
            count=3, participants=["p1", "p2", "p3"],
            n_eff=2.5, mean_intensity=2.5, concentration=1.0,
            composite_signal=0.05, confidence="moderate",
            quotes=[
                SignalQuote(text="t", participant_id=f"p{i}", session_id="s1",
                            start_seconds=0.0, intensity=3, tag_names=["satisfaction"])
                for i in (1, 2, 3)
            ],
        )
        base.update(over)
        return Signal(**base)

    def test_breadth_is_measured_against_the_study_not_the_card(self) -> None:
        """Three of twenty is narrow. Three of three is not a measurement.

        n_eff 2.5 over the card's own 3 participants is 0.83 — above
        FLAG_BREADTH — so the old code called this a Win. Against the study's
        20 it is 0.125, which is what "how much of the room said this" means.
        """
        from bristlenose.server.routes.analysis import _serialize_signal

        out = _serialize_signal(self._signal(), {}, 20)

        assert out.label_kind == "value", "fixture must reach the classify branch"
        assert out.flag == "Success", (
            f"breadth was measured against the card, not the study: {out.flag}"
        )

    def test_the_same_card_in_a_small_study_is_a_win(self) -> None:
        """The flag is a claim about the room, so the room has to be able to change it."""
        from bristlenose.server.routes.analysis import _serialize_signal

        assert _serialize_signal(self._signal(), {}, 4).flag == "Win"

    def test_a_negative_card_narrow_in_the_study_is_a_niggle_not_a_problem(self) -> None:
        """The same collapse on the other valence, where it matters more.

        "Problem" tells a researcher the room has one. At intensity 2.5 with
        the card's own denominator every negative card cleared FLAG_INTENSITY
        and FLAG_BREADTH together, so Niggle was unreachable here.
        """
        from bristlenose.analysis.models import SignalQuote
        from bristlenose.server.routes.analysis import _serialize_signal

        s = self._signal(quotes=[
            SignalQuote(text="t", participant_id=f"p{i}", session_id="s1",
                        start_seconds=0.0, intensity=3, tag_names=["frustration"])
            for i in (1, 2, 3)
        ])
        assert _serialize_signal(s, {}, 20).flag == "Niggle"
        assert _serialize_signal(s, {}, 4).flag == "Problem"
