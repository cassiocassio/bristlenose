"""Tests for bristlenose.analysis.signals — signal detection from matrices."""

from __future__ import annotations

from bristlenose.analysis.matrix import build_section_matrix, build_theme_matrix
from bristlenose.analysis.signals import detect_signals
from bristlenose.models import ExtractedQuote, QuoteType, ScreenCluster, Sentiment, ThemeGroup


def _quote(
    sentiment: Sentiment | None = Sentiment.FRUSTRATION,
    participant_id: str = "p1",
    intensity: int = 2,
    session_id: str = "s1",
    start: float = 10.0,
) -> ExtractedQuote:
    return ExtractedQuote(
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start,
        end_timecode=start + 5.0,
        text=f"Quote from {participant_id}",
        topic_label="Test",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        sentiment=sentiment,
        intensity=intensity,
    )


def _cluster(label: str, order: int, quotes: list[ExtractedQuote]) -> ScreenCluster:
    return ScreenCluster(
        screen_label=label, description="", display_order=order, quotes=quotes,
    )


def _theme(label: str, quotes: list[ExtractedQuote]) -> ThemeGroup:
    return ThemeGroup(theme_label=label, description="", quotes=quotes)


# ---------------------------------------------------------------------------
# detect_signals
# ---------------------------------------------------------------------------


class TestDetectSignals:

    def test_min_two_quotes(self) -> None:
        """Cells with fewer than 2 quotes produce no signals."""
        clusters = [_cluster("Checkout", 1, [_quote(Sentiment.FRUSTRATION, "p1")])]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5)
        assert result.signals == []

    def test_two_quotes_produces_signal(self) -> None:
        """Two quotes in the same cell produces a signal."""
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p1", start=10.0),
            _quote(Sentiment.FRUSTRATION, "p2", start=20.0),
        ]
        clusters = [_cluster("Checkout", 1, quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5)
        assert len(result.signals) == 1
        sig = result.signals[0]
        assert sig.location == "Checkout"
        assert sig.source_type == "section"
        assert sig.sentiment == "frustration"
        assert sig.count == 2
        assert sorted(sig.participants) == ["p1", "p2"]

    def test_sorted_by_composite_signal_desc(self) -> None:
        """Signals are sorted by composite_signal in descending order."""
        # Strong signal: many quotes, many participants
        strong_quotes = [_quote(Sentiment.FRUSTRATION, f"p{i}", intensity=3) for i in range(1, 7)]
        # Weak signal: few quotes, few participants
        weak_quotes = [_quote(Sentiment.CONFUSION, "p1"), _quote(Sentiment.CONFUSION, "p1")]
        clusters = [
            _cluster("Checkout", 1, strong_quotes),
            _cluster("Search", 2, weak_quotes),
        ]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=10)
        assert len(result.signals) == 2
        assert result.signals[0].composite_signal >= result.signals[1].composite_signal

    def test_top_n_limiting(self) -> None:
        """Only top_n signals are returned."""
        clusters = []
        for i in range(5):
            quotes = [
                _quote(Sentiment.FRUSTRATION, "p1", start=float(i * 10)),
                _quote(Sentiment.FRUSTRATION, "p2", start=float(i * 10 + 5)),
            ]
            clusters.append(_cluster(f"Section{i}", i, quotes))
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5, top_n=3)
        assert len(result.signals) == 3

    def test_merged_section_and_theme_signals(self) -> None:
        """Section and theme signals are merged together."""
        section_quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        theme_quotes = [_quote(Sentiment.DOUBT, "p3"), _quote(Sentiment.DOUBT, "p4")]
        clusters = [_cluster("Checkout", 1, section_quotes)]
        themes = [_theme("Trust", theme_quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix(themes)
        result = detect_signals(sm, tm, clusters, themes, total_participants=5)
        source_types = {s.source_type for s in result.signals}
        assert source_types == {"section", "theme"}

    def test_quote_ordering(self) -> None:
        """Signal quotes are sorted by participant, then timecode."""
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p2", start=5.0),
            _quote(Sentiment.FRUSTRATION, "p1", start=20.0),
            _quote(Sentiment.FRUSTRATION, "p1", start=10.0),
            _quote(Sentiment.FRUSTRATION, "p2", start=15.0),
        ]
        clusters = [_cluster("Checkout", 1, quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5)
        assert len(result.signals) == 1
        pids = [q.participant_id for q in result.signals[0].quotes]
        starts = [q.start_seconds for q in result.signals[0].quotes]
        assert pids == ["p1", "p1", "p2", "p2"]
        assert starts == [10.0, 20.0, 5.0, 15.0]

    def test_no_sentiment_data(self) -> None:
        """Quotes with no sentiment produce no signals."""
        quotes = [_quote(None, "p1"), _quote(None, "p2")]
        clusters = [_cluster("Checkout", 1, quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5)
        assert result.signals == []

    def test_result_metadata(self) -> None:
        """AnalysisResult carries correct metadata."""
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        clusters = [_cluster("Checkout", 1, quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=8)
        assert result.total_participants == 8
        assert result.sentiments == [s.value for s in Sentiment]
        assert result.section_matrix is sm
        assert result.theme_matrix is tm


class TestConfidenceClassification:

    def test_strong_signal(self) -> None:
        """Strong: concentration > 2, >= 5 unique participants, >= 6 quotes."""
        # Checkout: 6 frustration quotes from 5 participants
        frust_quotes = [_quote(Sentiment.FRUSTRATION, f"p{i}", intensity=3) for i in range(1, 6)]
        frust_quotes.append(_quote(Sentiment.FRUSTRATION, "p5", intensity=3, start=99.0))
        # Other sections have mostly satisfaction — frustration is concentrated in Checkout
        other_section_quotes = [
            _quote(Sentiment.SATISFACTION, f"p{i}") for i in range(1, 16)
        ] + [
            _quote(Sentiment.FRUSTRATION, "p8", start=200.0),
        ]
        clusters = [
            _cluster("Checkout", 1, frust_quotes),
            _cluster("Search", 2, other_section_quotes),
        ]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=15)
        frust_signal = next(
            (s for s in result.signals
             if s.sentiment == "frustration" and s.location == "Checkout"),
            None,
        )
        assert frust_signal is not None
        assert frust_signal.concentration > 2
        assert frust_signal.confidence == "strong"

    def test_moderate_signal(self) -> None:
        """Moderate: concentration > 1.5, >= 3 unique participants, >= 4 quotes."""
        # Checkout: 4 frustration quotes from 4 participants
        frust_quotes = [_quote(Sentiment.FRUSTRATION, f"p{i}", intensity=2) for i in range(1, 5)]
        # Other section dilutes frustration across the study
        other_section_quotes = [
            _quote(Sentiment.SATISFACTION, f"p{i}") for i in range(1, 11)
        ] + [
            _quote(Sentiment.FRUSTRATION, "p7", start=200.0),
        ]
        clusters = [
            _cluster("Checkout", 1, frust_quotes),
            _cluster("Search", 2, other_section_quotes),
        ]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=10)
        frust_signal = next(
            (s for s in result.signals
             if s.sentiment == "frustration" and s.location == "Checkout"),
            None,
        )
        assert frust_signal is not None
        assert frust_signal.confidence in ("strong", "moderate")

    def test_emerging_signal(self) -> None:
        """Emerging: 2 quotes, below strong/moderate thresholds."""
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        clusters = [_cluster("Checkout", 1, quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=10)
        assert len(result.signals) == 1
        assert result.signals[0].confidence == "emerging"
