"""Tests for bristlenose.analysis.generic_signals — generic signal detection."""

from __future__ import annotations

from bristlenose.analysis.generic_matrix import QuoteContribution, build_matrix_from_contributions
from bristlenose.analysis.generic_signals import (
    DEFAULT_TOP_N,
    QuoteRecord,
    detect_signals_generic,
)


def _contrib(
    row: str = "Checkout",
    col: str = "Friction",
    pid: str = "p1",
    intensity: int = 2,
) -> QuoteContribution:
    return QuoteContribution(row_label=row, col_label=col, participant_id=pid, intensity=intensity)


def _qr(
    pid: str = "p1",
    session_id: str = "s1",
    start: float = 10.0,
    intensity: int = 2,
) -> QuoteRecord:
    return QuoteRecord(
        text=f"Quote from {pid}",
        participant_id=pid,
        session_id=session_id,
        start_seconds=start,
        intensity=intensity,
    )


def _build_and_detect(
    section_contribs: list[QuoteContribution],
    theme_contribs: list[QuoteContribution],
    section_row_labels: list[str],
    theme_row_labels: list[str],
    col_labels: list[str],
    total_participants: int,
    section_quote_lookup: dict[str, list[QuoteRecord]] | None = None,
    theme_quote_lookup: dict[str, list[QuoteRecord]] | None = None,
    top_n: int = DEFAULT_TOP_N,
):
    sm = build_matrix_from_contributions(section_contribs, section_row_labels, col_labels)
    tm = build_matrix_from_contributions(theme_contribs, theme_row_labels, col_labels)
    return detect_signals_generic(
        sm, tm, col_labels, total_participants,
        section_quote_lookup or {},
        theme_quote_lookup or {},
        top_n=top_n,
    )


# ---------------------------------------------------------------------------
# detect_signals_generic
# ---------------------------------------------------------------------------


class TestDetectSignalsGeneric:

    def test_min_quotes_per_cell(self) -> None:
        """Cells with fewer than MIN_QUOTES_PER_CELL produce no signals."""
        contribs = [_contrib("Checkout", "Friction", "p1")]
        signals, _, _ = _build_and_detect(
            contribs, [], ["Checkout"], [], ["Friction"], total_participants=5,
        )
        assert signals == []

    def test_two_quotes_produces_signal(self) -> None:
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p2"),
        ]
        lookup = {
            "Checkout|Friction": [_qr("p1", start=10.0), _qr("p2", start=20.0)],
        }
        signals, _, _ = _build_and_detect(
            contribs, [], ["Checkout"], [], ["Friction"],
            total_participants=5,
            section_quote_lookup=lookup,
        )
        assert len(signals) == 1
        sig = signals[0]
        assert sig.location == "Checkout"
        assert sig.source_type == "section"
        assert sig.sentiment == "Friction"  # group name in sentiment field
        assert sig.count == 2
        assert sorted(sig.participants) == ["p1", "p2"]

    def test_arbitrary_column_names(self) -> None:
        """Column labels can be any string — not limited to sentiment values."""
        contribs = [
            _contrib("Home", "Prior Experience", "p1"),
            _contrib("Home", "Prior Experience", "p2"),
        ]
        signals, _, _ = _build_and_detect(
            contribs, [], ["Home"], [], ["Prior Experience"],
            total_participants=5,
        )
        assert len(signals) == 1
        assert signals[0].sentiment == "Prior Experience"

    def test_sorted_by_composite_signal_desc(self) -> None:
        # Strong signal: many quotes, many participants
        strong = [_contrib("Checkout", "Friction", f"p{i}", intensity=3) for i in range(1, 7)]
        # Weak signal: few quotes, same participant
        weak = [
            _contrib("Checkout", "Emotions", "p1"),
            _contrib("Checkout", "Emotions", "p1"),
        ]
        signals, _, _ = _build_and_detect(
            strong + weak, [], ["Checkout"], [],
            ["Friction", "Emotions"], total_participants=10,
        )
        assert len(signals) == 2
        assert signals[0].sentiment == "Friction"
        assert signals[1].sentiment == "Emotions"
        assert signals[0].composite_signal >= signals[1].composite_signal

    def test_top_n_limits_signals(self) -> None:
        # Create more signals than top_n=1
        contribs = [
            _contrib("Checkout", "A", "p1"), _contrib("Checkout", "A", "p2"),
            _contrib("Checkout", "B", "p1"), _contrib("Checkout", "B", "p2"),
        ]
        signals, _, _ = _build_and_detect(
            contribs, [], ["Checkout"], [], ["A", "B"],
            total_participants=5, top_n=1,
        )
        assert len(signals) == 1

    def test_theme_signals_included(self) -> None:
        theme_contribs = [
            _contrib("Navigation issues", "Friction", "p1"),
            _contrib("Navigation issues", "Friction", "p2"),
        ]
        signals, _, _ = _build_and_detect(
            [], theme_contribs, [], ["Navigation issues"], ["Friction"],
            total_participants=5,
        )
        assert len(signals) == 1
        assert signals[0].source_type == "theme"
        assert signals[0].location == "Navigation issues"

    def test_section_and_theme_signals_merged(self) -> None:
        sec = [_contrib("Checkout", "Friction", "p1"), _contrib("Checkout", "Friction", "p2")]
        thm = [_contrib("Perf issues", "Friction", "p3"), _contrib("Perf issues", "Friction", "p4")]
        signals, _, _ = _build_and_detect(
            sec, thm, ["Checkout"], ["Perf issues"], ["Friction"],
            total_participants=5,
        )
        assert len(signals) == 2
        types = {s.source_type for s in signals}
        assert types == {"section", "theme"}

    def test_quotes_attached_to_signal(self) -> None:
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p2"),
        ]
        lookup = {
            "Checkout|Friction": [
                _qr("p2", start=20.0),
                _qr("p1", start=10.0),
            ],
        }
        signals, _, _ = _build_and_detect(
            contribs, [], ["Checkout"], [], ["Friction"],
            total_participants=5,
            section_quote_lookup=lookup,
        )
        assert len(signals) == 1
        qs = signals[0].quotes
        assert len(qs) == 2
        # Should be sorted by participant_id then start_seconds
        assert qs[0].participant_id == "p1"
        assert qs[1].participant_id == "p2"

    def test_confidence_emerging(self) -> None:
        """Two quotes, two participants → emerging confidence."""
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p2"),
        ]
        signals, _, _ = _build_and_detect(
            contribs, [], ["Checkout"], [], ["Friction"],
            total_participants=5,
        )
        assert signals[0].confidence == "emerging"

    def test_confidence_moderate(self) -> None:
        """4+ quotes, 3+ participants, concentration > 1.5 → moderate."""
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p2"),
            _contrib("Checkout", "Friction", "p3"),
            _contrib("Checkout", "Friction", "p4"),
        ]
        signals, _, _ = _build_and_detect(
            contribs, [], ["Checkout"], [], ["Friction"],
            total_participants=5,
        )
        # Concentration = (4/4) / (4/4) = 1.0 — only one column, so conc = 1.0
        # Need multiple columns to get conc > 1.5
        # With only one column, conc is always 1.0, so "moderate" can't trigger
        # Let's add a second column with fewer quotes to boost Friction's concentration
        contribs2 = contribs + [_contrib("Checkout", "Delight", "p5")]
        signals2, _, _ = _build_and_detect(
            contribs2, [], ["Checkout"], [], ["Friction", "Delight"],
            total_participants=5,
        )
        # conc = (4/5) / (4/5) = 1.0 — still 1.0 because row only has one section
        # Actually: observed = 4/5 (in row Checkout), expected = 4/5 (overall)
        # So conc = 1.0. To get higher conc, need multiple rows.
        # Let's use a different setup:
        multi_row = [
            # Checkout: 4 Friction, 0 Delight
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p2"),
            _contrib("Checkout", "Friction", "p3"),
            _contrib("Checkout", "Friction", "p4"),
            # Search: 0 Friction, 4 Delight
            _contrib("Search", "Delight", "p5"),
            _contrib("Search", "Delight", "p6"),
            _contrib("Search", "Delight", "p7"),
            _contrib("Search", "Delight", "p8"),
        ]
        signals3, _, _ = _build_and_detect(
            multi_row, [], ["Checkout", "Search"], [],
            ["Friction", "Delight"],
            total_participants=8,
        )
        friction_sig3 = next(s for s in signals3 if s.sentiment == "Friction" and s.location == "Checkout")
        # observed = 4/4 = 1.0, expected = 4/8 = 0.5, conc = 2.0
        # 4 quotes, 4 pids but need >=3 for moderate — and conc > 1.5 ✓
        assert friction_sig3.confidence == "moderate"

    def test_matrices_returned(self) -> None:
        contribs = [_contrib("Checkout", "Friction", "p1"), _contrib("Checkout", "Friction", "p2")]
        _, sm, tm = _build_and_detect(
            contribs, [], ["Checkout"], [], ["Friction"],
            total_participants=5,
        )
        assert sm.grand_total == 2
        assert tm.grand_total == 0
