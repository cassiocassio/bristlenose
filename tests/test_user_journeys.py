"""Tests for user journey derivation from screen clusters."""

from __future__ import annotations

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    QuoteIntent,
    QuoteType,
    ScreenCluster,
    Sentiment,
)
from bristlenose.stages.render_html import _build_task_outcome_html
from bristlenose.stages.render_output import _build_task_outcome_summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quote(
    participant_id: str = "p1",
    sentiment: Sentiment | None = None,
    intent: QuoteIntent = QuoteIntent.NARRATION,
    emotion: EmotionalTone = EmotionalTone.NEUTRAL,
    session_id: str = "s1",
    start: float = 10.0,
    text: str = "Test quote",
) -> ExtractedQuote:
    return ExtractedQuote(
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start,
        end_timecode=start + 5.0,
        text=text,
        topic_label="Test",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        sentiment=sentiment,
        intent=intent,
        emotion=emotion,
    )


def _cluster(
    label: str,
    order: int,
    quotes: list[ExtractedQuote],
) -> ScreenCluster:
    return ScreenCluster(
        screen_label=label,
        description="",
        display_order=order,
        quotes=quotes,
    )


# ---------------------------------------------------------------------------
# _build_task_outcome_html
# ---------------------------------------------------------------------------


class TestBuildTaskOutcomeHtml:
    """Tests for the HTML user journey table builder."""

    def test_basic_journey_two_participants(self) -> None:
        """p1 visits clusters 1+3, p2 visits all three."""
        q_p1_a = _quote("p1", start=10.0)
        q_p1_c = _quote("p1", start=30.0)
        q_p2_a = _quote("p2", start=5.0)
        q_p2_b = _quote("p2", start=15.0)
        q_p2_c = _quote("p2", start=25.0)

        clusters = [
            _cluster("Homepage", 1, [q_p1_a, q_p2_a]),
            _cluster("Search results", 2, [q_p2_b]),
            _cluster("Product page", 3, [q_p1_c, q_p2_c]),
        ]
        all_quotes = [q_p1_a, q_p1_c, q_p2_a, q_p2_b, q_p2_c]

        html = _build_task_outcome_html(clusters, all_quotes)

        # p1 skipped Search results
        assert "Homepage &rarr; Product page" in html
        # p2 visited all three
        assert "Homepage &rarr; Search results &rarr; Product page" in html

    def test_display_order_respected(self) -> None:
        """Clusters passed out of order still render in display_order sequence."""
        q1 = _quote("p1", start=10.0)
        q2 = _quote("p1", start=20.0)
        q3 = _quote("p1", start=30.0)

        # Passed in wrong order
        clusters = [
            _cluster("Checkout", 3, [q3]),
            _cluster("Homepage", 1, [q1]),
            _cluster("Cart", 2, [q2]),
        ]

        html = _build_task_outcome_html(clusters, [q1, q2, q3])

        assert "Homepage &rarr; Cart &rarr; Checkout" in html

    def test_empty_clusters_returns_empty(self) -> None:
        """No screen clusters means no table."""
        assert _build_task_outcome_html([], []) == ""

    def test_display_names(self) -> None:
        """Participant IDs resolved via display_names."""
        q = _quote("p1")
        clusters = [_cluster("Page A", 1, [q])]

        html = _build_task_outcome_html(
            clusters, [q], display_names={"p1": "Alice"},
        )

        assert "Alice" in html
        # session_id "s1" is displayed as "1", so "p1" may appear as part of
        # other strings — check that the participant cell shows a split badge
        # with both code and name.
        assert '<span class="bn-speaker-badge-code">p1</span>' in html
        assert '<span class="bn-speaker-badge-name">Alice</span>' in html

    def test_single_cluster_no_arrow(self) -> None:
        """One cluster means no arrow in the journey string."""
        q = _quote("p1")
        clusters = [_cluster("Homepage", 1, [q])]

        html = _build_task_outcome_html(clusters, [q])

        assert "Homepage" in html
        assert "&rarr;" not in html

    def test_general_context_only_participant_excluded(self) -> None:
        """Participant with only general_context quotes (not in any cluster) is excluded."""
        q_screen = _quote("p1")
        q_general = _quote("p2")  # not added to any cluster

        clusters = [_cluster("Page A", 1, [q_screen])]
        all_quotes = [q_screen, q_general]

        html = _build_task_outcome_html(clusters, all_quotes)

        # p1 IS in the cluster so should appear as a split badge
        assert '<span class="bn-speaker-badge-code">p1</span>' in html
        # p2 has no screen cluster membership — should be absent
        assert "p2" not in html

    def test_session_column_present(self) -> None:
        """HTML table includes a Session column."""
        q = _quote("p1", session_id="s3")
        clusters = [_cluster("Page A", 1, [q])]

        html = _build_task_outcome_html(clusters, [q])

        assert "Session" in html
        # Session number without "s" prefix
        assert "<td>3</td>" in html

    def test_sorted_by_session_number(self) -> None:
        """Rows are sorted by session number, not alphabetically."""
        q1 = _quote("p1", session_id="s2", start=10.0)
        q2 = _quote("p2", session_id="s10", start=20.0)
        q3 = _quote("p3", session_id="s1", start=30.0)

        clusters = [_cluster("Page A", 1, [q1, q2, q3])]

        html = _build_task_outcome_html(clusters, [q1, q2, q3])

        # Find row order by looking at session numbers in the output
        idx_s1 = html.index("<td>1</td>")
        idx_s2 = html.index("<td>2</td>")
        idx_s10 = html.index("<td>10</td>")
        assert idx_s1 < idx_s2 < idx_s10

    def test_sortable_header_classes(self) -> None:
        """Session header has sortable CSS classes."""
        q = _quote("p1")
        clusters = [_cluster("Page A", 1, [q])]

        html = _build_task_outcome_html(clusters, [q])

        assert "bn-sortable" in html
        assert "bn-sorted-asc" in html


# ---------------------------------------------------------------------------
# _build_task_outcome_summary (markdown)
# ---------------------------------------------------------------------------


class TestBuildTaskOutcomeSummary:
    """Tests for the markdown user journey table builder."""

    def test_basic_journey_markdown(self) -> None:
        """Journey arrows use Unicode arrow in markdown output."""
        q1 = _quote("p1", start=10.0)
        q2 = _quote("p1", start=20.0)

        clusters = [
            _cluster("Homepage", 1, [q1]),
            _cluster("Search", 2, [q2]),
        ]

        lines = _build_task_outcome_summary(clusters, [q1, q2])

        joined = "\n".join(lines)
        assert "Homepage \u2192 Search" in joined
        assert "| Journey |" in joined

    def test_empty_clusters_returns_empty_list(self) -> None:
        assert _build_task_outcome_summary([], []) == []

    def test_display_names_markdown(self) -> None:
        q = _quote("p1")
        clusters = [_cluster("Page A", 1, [q])]

        lines = _build_task_outcome_summary(
            clusters, [q], display_names={"p1": "Bob"},
        )
        joined = "\n".join(lines)

        assert "Bob" in joined

    def test_session_column_in_markdown(self) -> None:
        """Markdown table includes Session column."""
        q = _quote("p1", session_id="s5")
        clusters = [_cluster("Page A", 1, [q])]

        lines = _build_task_outcome_summary(clusters, [q])
        joined = "\n".join(lines)

        assert "| Session |" in joined
        assert "| 5 |" in joined

    def test_sorted_by_session_in_markdown(self) -> None:
        """Markdown rows sorted by session number."""
        q1 = _quote("p1", session_id="s3")
        q2 = _quote("p2", session_id="s1")

        clusters = [_cluster("Page A", 1, [q1, q2])]

        lines = _build_task_outcome_summary(clusters, [q1, q2])
        joined = "\n".join(lines)

        # s1 (p2) should appear before s3 (p1)
        assert joined.index("p2") < joined.index("p1")
