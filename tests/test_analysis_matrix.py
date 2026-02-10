"""Tests for bristlenose.analysis.matrix — matrix building from grouped quotes."""

from __future__ import annotations

from bristlenose.analysis.matrix import SENTIMENTS, build_section_matrix, build_theme_matrix
from bristlenose.models import ExtractedQuote, QuoteType, ScreenCluster, Sentiment, ThemeGroup


def _quote(
    sentiment: Sentiment | None = Sentiment.FRUSTRATION,
    participant_id: str = "p1",
    intensity: int = 2,
    session_id: str = "s1",
    start: float = 10.0,
) -> ExtractedQuote:
    """Helper to build a minimal quote for testing."""
    return ExtractedQuote(
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start,
        end_timecode=start + 5.0,
        text="Test quote",
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
# build_section_matrix
# ---------------------------------------------------------------------------


class TestBuildSectionMatrix:

    def test_empty_clusters(self) -> None:
        m = build_section_matrix([])
        assert m.row_labels == []
        assert m.grand_total == 0

    def test_single_cluster_single_sentiment(self) -> None:
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        m = build_section_matrix([_cluster("Checkout", 1, quotes)])
        assert m.row_labels == ["Checkout"]
        assert m.grand_total == 2
        assert m.row_totals["Checkout"] == 2
        assert m.col_totals["frustration"] == 2
        cell = m.cells["Checkout|frustration"]
        assert cell.count == 2
        assert cell.participants == {"p1": 1, "p2": 1}

    def test_single_cluster_multiple_sentiments(self) -> None:
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p1"),
            _quote(Sentiment.FRUSTRATION, "p2"),
            _quote(Sentiment.DELIGHT, "p3"),
        ]
        m = build_section_matrix([_cluster("Search", 1, quotes)])
        assert m.grand_total == 3
        assert m.row_totals["Search"] == 3
        assert m.col_totals["frustration"] == 2
        assert m.col_totals["delight"] == 1
        assert m.cells["Search|frustration"].count == 2
        assert m.cells["Search|delight"].count == 1

    def test_multiple_clusters(self) -> None:
        c1 = _cluster("Checkout", 1, [_quote(Sentiment.FRUSTRATION, "p1")])
        c2 = _cluster("Search", 2, [_quote(Sentiment.CONFUSION, "p2")])
        m = build_section_matrix([c2, c1])  # out of order to test sorting
        assert m.row_labels == ["Checkout", "Search"]  # sorted by display_order
        assert m.grand_total == 2
        assert m.row_totals["Checkout"] == 1
        assert m.row_totals["Search"] == 1

    def test_none_sentiment_excluded(self) -> None:
        quotes = [_quote(None), _quote(Sentiment.FRUSTRATION, "p2")]
        m = build_section_matrix([_cluster("Checkout", 1, quotes)])
        assert m.grand_total == 1
        assert m.cells["Checkout|frustration"].count == 1

    def test_participant_counting(self) -> None:
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p1"),
            _quote(Sentiment.FRUSTRATION, "p1"),
            _quote(Sentiment.FRUSTRATION, "p2"),
        ]
        m = build_section_matrix([_cluster("Checkout", 1, quotes)])
        cell = m.cells["Checkout|frustration"]
        assert cell.participants == {"p1": 2, "p2": 1}
        assert cell.count == 3

    def test_intensity_tracking(self) -> None:
        quotes = [
            _quote(Sentiment.FRUSTRATION, intensity=1),
            _quote(Sentiment.FRUSTRATION, intensity=3),
            _quote(Sentiment.FRUSTRATION, intensity=2),
        ]
        m = build_section_matrix([_cluster("Checkout", 1, quotes)])
        assert m.cells["Checkout|frustration"].intensities == [1, 3, 2]

    def test_all_sentiments_initialised(self) -> None:
        m = build_section_matrix([_cluster("Checkout", 1, [])])
        for sent in SENTIMENTS:
            assert f"Checkout|{sent}" in m.cells
            assert m.cells[f"Checkout|{sent}"].count == 0


# ---------------------------------------------------------------------------
# build_theme_matrix
# ---------------------------------------------------------------------------


class TestBuildThemeMatrix:

    def test_empty_themes(self) -> None:
        m = build_theme_matrix([])
        assert m.row_labels == []
        assert m.grand_total == 0

    def test_single_theme(self) -> None:
        quotes = [
            _quote(Sentiment.DOUBT, "p1"),
            _quote(Sentiment.DOUBT, "p2"),
        ]
        m = build_theme_matrix([_theme("Trust", quotes)])
        assert m.row_labels == ["Trust"]
        assert m.grand_total == 2
        assert m.cells["Trust|doubt"].count == 2

    def test_multiple_themes(self) -> None:
        t1 = _theme("Trust", [_quote(Sentiment.DOUBT, "p1")])
        t2 = _theme("Performance", [_quote(Sentiment.FRUSTRATION, "p2")])
        m = build_theme_matrix([t1, t2])
        assert m.row_labels == ["Trust", "Performance"]
        assert m.grand_total == 2
        assert m.row_totals["Trust"] == 1
        assert m.row_totals["Performance"] == 1

    def test_theme_row_labels_preserve_order(self) -> None:
        """Theme matrix preserves input order (themes have no display_order)."""
        t1 = _theme("Zebra", [_quote(Sentiment.FRUSTRATION)])
        t2 = _theme("Alpha", [_quote(Sentiment.FRUSTRATION)])
        m = build_theme_matrix([t1, t2])
        assert m.row_labels == ["Zebra", "Alpha"]
