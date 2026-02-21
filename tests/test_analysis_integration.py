"""Integration tests for the analysis pipeline: _compute_analysis, serialization, and render.

Tests the full data flow from pipeline-level computation through JSON serialization
to HTML output. Proves that data gets everywhere it needs to be.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bristlenose.analysis.matrix import build_section_matrix, build_theme_matrix
from bristlenose.analysis.models import AnalysisResult, Matrix, MatrixCell, Signal
from bristlenose.analysis.signals import detect_signals
from bristlenose.models import (
    ExtractedQuote,
    FileType,
    InputFile,
    InputSession,
    QuoteType,
    ScreenCluster,
    Sentiment,
    ThemeGroup,
)
from bristlenose.pipeline import _compute_analysis
from bristlenose.stages.render_html import (
    _serialize_analysis,
    _serialize_matrix,
    render_html,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quote(
    sentiment: Sentiment | None = Sentiment.FRUSTRATION,
    participant_id: str = "p1",
    intensity: int = 2,
    session_id: str = "s1",
    start: float = 10.0,
    text: str = "",
) -> ExtractedQuote:
    return ExtractedQuote(
        session_id=session_id,
        participant_id=participant_id,
        start_timecode=start,
        end_timecode=start + 5.0,
        text=text or f"Quote from {participant_id} [{sentiment}] @{start}",
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


def _session(session_id: str, participant_id: str) -> InputSession:
    return InputSession(
        session_id=session_id,
        session_number=int(session_id[1:]),
        participant_id=participant_id,
        participant_number=int(participant_id[1:]) if participant_id.startswith("p") else 0,
        files=[
            InputFile(
                path=Path(f"/tmp/{session_id}.mp4"),
                file_type=FileType.VIDEO,
                created_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
                size_bytes=100_000,
            )
        ],
        session_date=datetime(2026, 1, 10, tzinfo=timezone.utc),
    )


def _realistic_data(
    n_participants: int = 6,
) -> tuple[list[ScreenCluster], list[ThemeGroup], list[ExtractedQuote], list[InputSession]]:
    """Build a realistic multi-section, multi-participant dataset.

    Returns (clusters, themes, all_quotes, sessions).
    """
    # Checkout: frustration concentrated here (all 6 participants)
    checkout_quotes = [
        _quote(Sentiment.FRUSTRATION, f"p{i}", intensity=3, session_id=f"s{i}", start=float(i * 10))
        for i in range(1, n_participants + 1)
    ]
    # Search: mostly satisfaction
    search_quotes = [
        _quote(Sentiment.SATISFACTION, f"p{i}", intensity=2, session_id=f"s{i}", start=float(i * 10 + 100))
        for i in range(1, n_participants + 1)
    ]
    # Add some confusion to search (2 participants)
    search_quotes.extend([
        _quote(Sentiment.CONFUSION, "p1", intensity=1, session_id="s1", start=150.0),
        _quote(Sentiment.CONFUSION, "p2", intensity=2, session_id="s2", start=160.0),
    ])

    clusters = [
        _cluster("Checkout", 1, checkout_quotes),
        _cluster("Search", 2, search_quotes),
    ]

    # Theme: "Trust issues" with doubt quotes
    trust_quotes = [
        _quote(Sentiment.DOUBT, f"p{i}", intensity=2, session_id=f"s{i}", start=float(200 + i * 10))
        for i in range(1, 4)
    ]
    themes = [_theme("Trust Issues", trust_quotes)]

    all_quotes = checkout_quotes + search_quotes + trust_quotes

    sessions = [_session(f"s{i}", f"p{i}") for i in range(1, n_participants + 1)]

    return clusters, themes, all_quotes, sessions


# ===========================================================================
# _compute_analysis
# ===========================================================================


class TestComputeAnalysis:

    def test_returns_none_when_no_clusters_or_themes(self) -> None:
        result = _compute_analysis([], [], [_quote()])
        assert result is None

    def test_returns_none_when_no_sentiment_data(self) -> None:
        """Quotes without sentiment → None (no analysis possible)."""
        quotes = [_quote(sentiment=None), _quote(sentiment=None)]
        clusters = [_cluster("Checkout", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes)
        assert result is None

    def test_returns_analysis_with_sentiments(self) -> None:
        """Quotes with sentiments → AnalysisResult."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        assert hasattr(result, "signals")
        assert hasattr(result, "section_matrix")
        assert hasattr(result, "theme_matrix")

    def test_participant_count_from_sessions(self) -> None:
        """When sessions are provided, count participants from sessions."""
        clusters, themes, all_quotes, sessions = _realistic_data(n_participants=6)
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        assert result.total_participants == 6

    def test_participant_count_excludes_moderators(self) -> None:
        """Moderator sessions (m1, m2) are not counted as participants."""
        clusters, themes, all_quotes, sessions = _realistic_data(n_participants=4)
        # Add a moderator session
        sessions.append(_session("s99", "m1"))
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        # Only p1-p4 count, not m1
        assert result.total_participants == 4

    def test_participant_count_fallback_to_quotes(self) -> None:
        """When no sessions provided, count unique PIDs from quotes."""
        clusters, themes, all_quotes, _ = _realistic_data(n_participants=5)
        result = _compute_analysis(clusters, themes, all_quotes, sessions=None)
        assert result is not None
        assert result.total_participants == 5

    def test_participant_count_fallback_excludes_moderators(self) -> None:
        """Quote-based participant counting also excludes moderator codes."""
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p1"),
            _quote(Sentiment.FRUSTRATION, "p2"),
            _quote(Sentiment.FRUSTRATION, "m1"),  # moderator quote
        ]
        clusters = [_cluster("Checkout", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes, sessions=None)
        assert result is not None
        # m1 should not be counted
        assert result.total_participants == 2

    def test_signals_are_produced(self) -> None:
        """Full pipeline produces actual signals."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        assert len(result.signals) > 0

    def test_mixed_sentiment_and_none(self) -> None:
        """Quotes with None sentiment are skipped, those with sentiment are analysed."""
        quotes_with = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        quotes_without = [_quote(None, "p3"), _quote(None, "p4")]
        clusters = [_cluster("Checkout", 1, quotes_with + quotes_without)]
        result = _compute_analysis(clusters, [], quotes_with + quotes_without)
        assert result is not None
        assert len(result.signals) >= 1

    def test_only_themes_no_clusters(self) -> None:
        """Themes without clusters still produce analysis."""
        quotes = [_quote(Sentiment.DOUBT, "p1"), _quote(Sentiment.DOUBT, "p2")]
        themes = [_theme("Trust", quotes)]
        # Clusters empty but themes present
        result = _compute_analysis([], themes, quotes)
        assert result is not None
        assert len(result.signals) >= 1

    def test_only_clusters_no_themes(self) -> None:
        """Clusters without themes still produce analysis."""
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        clusters = [_cluster("Checkout", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes)
        assert result is not None
        assert len(result.signals) >= 1


# ===========================================================================
# Confidence threshold boundaries
# ===========================================================================


class TestConfidenceBoundaries:
    """Test exact boundary conditions for strong/moderate/emerging classification.

    The code uses strict > (not >=) for concentration thresholds:
      strong:   conc > 2   AND >= 5 unique pids AND >= 6 quotes
      moderate: conc > 1.5 AND >= 3 unique pids AND >= 4 quotes
      emerging: everything else that passed MIN_QUOTES_PER_CELL (2)
    """

    def _signal_from_cell(
        self,
        n_quotes_in_cell: int,
        n_unique_pids: int,
        total_study_quotes: int,
        col_total: int,
    ) -> Signal:
        """Build a signal by constructing a realistic matrix cell.

        Creates a cluster with the specified quotes, plus dilution quotes in another
        section to control the concentration ratio.
        """
        # Target cell: n_quotes_in_cell quotes from n_unique_pids participants
        cell_quotes: list[ExtractedQuote] = []
        quotes_per_pid = n_quotes_in_cell // n_unique_pids
        remainder = n_quotes_in_cell % n_unique_pids
        for i in range(1, n_unique_pids + 1):
            count = quotes_per_pid + (1 if i <= remainder else 0)
            for j in range(count):
                cell_quotes.append(
                    _quote(Sentiment.FRUSTRATION, f"p{i}", intensity=2, start=float(i * 100 + j))
                )

        # Dilution section: fill with satisfaction to reach total_study_quotes
        # and control col_total (total frustration in study)
        frustration_in_other = col_total - n_quotes_in_cell
        satisfaction_in_other = total_study_quotes - n_quotes_in_cell - max(0, frustration_in_other)
        other_quotes: list[ExtractedQuote] = []
        for i in range(max(0, frustration_in_other)):
            other_quotes.append(
                _quote(Sentiment.FRUSTRATION, f"p{20 + i}", intensity=1, start=float(500 + i))
            )
        for i in range(max(0, satisfaction_in_other)):
            other_quotes.append(
                _quote(Sentiment.SATISFACTION, f"p{30 + i}", intensity=1, start=float(600 + i))
            )

        clusters = [
            _cluster("Target", 1, cell_quotes),
            _cluster("Other", 2, other_quotes),
        ]
        sm = build_section_matrix(clusters)
        total_participants = max(n_unique_pids, 15)
        result = detect_signals(sm, build_theme_matrix([]), clusters, [], total_participants)
        # Find the Target|frustration signal
        for s in result.signals:
            if s.location == "Target" and s.sentiment == "frustration":
                return s
        pytest.fail("Expected a Target|frustration signal but none found")

    def test_strong_boundary_conc_exactly_2_is_not_strong(self) -> None:
        """conc == 2.0 exactly should NOT be strong (code uses > 2, not >= 2).

        We verify the principle: if concentration is not strictly above 2, it's moderate or emerging.
        """
        # 6 frustration quotes from 5 PIDs in target, with dilution to make conc ≈ 2.0
        # row_total = 6, grand_total needs to be chosen so conc = (6/6) / (col_total/grand_total) = 2.0
        # observed = 6/6 = 1.0, expected = col_total/grand_total
        # conc = 1.0 / expected = 2.0 → expected = 0.5 → col_total/grand_total = 0.5
        # If grand_total=20, col_total=10 → expected=0.5 → conc=2.0 exactly
        signal = self._signal_from_cell(
            n_quotes_in_cell=6, n_unique_pids=5,
            total_study_quotes=20, col_total=10,
        )
        # conc should be ≈ 2.0
        assert signal.concentration == pytest.approx(2.0, abs=0.01)
        # strictly > 2 fails → not strong
        assert signal.confidence != "strong"

    def test_strong_boundary_conc_just_above_2(self) -> None:
        """conc just above 2.0 with enough pids and quotes → strong."""
        # 6 frustration quotes from 5 PIDs, dilution to push conc > 2.0
        # grand_total=22, col_total=11 → expected=0.5 → conc=2.0. Need less expected.
        # grand_total=24, col_total=11 → expected=11/24=0.458 → observed=1.0 → conc=2.18
        signal = self._signal_from_cell(
            n_quotes_in_cell=6, n_unique_pids=5,
            total_study_quotes=24, col_total=11,
        )
        assert signal.concentration > 2.0
        assert len(signal.participants) >= 5
        assert signal.count >= 6
        assert signal.confidence == "strong"

    def test_moderate_with_4_quotes_3_pids(self) -> None:
        """Moderate: 4 quotes from 3 PIDs, conc > 1.5."""
        # 4 frustration in target, grand=20, col_total=8 → expected=8/20=0.4
        # observed=4/4=1.0 → conc=2.5 (> 1.5 ✓). But only 3 pids < 5 and 4 quotes < 6 → not strong
        signal = self._signal_from_cell(
            n_quotes_in_cell=4, n_unique_pids=3,
            total_study_quotes=20, col_total=8,
        )
        assert signal.concentration > 1.5
        assert len(signal.participants) >= 3
        assert signal.count >= 4
        # Not strong (< 5 PIDs and < 6 quotes)
        assert signal.confidence == "moderate"

    def test_emerging_with_2_quotes(self) -> None:
        """2 quotes from 2 PIDs → emerging regardless of concentration."""
        signal = self._signal_from_cell(
            n_quotes_in_cell=2, n_unique_pids=2,
            total_study_quotes=20, col_total=10,
        )
        assert signal.count == 2
        assert signal.confidence == "emerging"

    def test_moderate_boundary_conc_exactly_1_5_is_emerging(self) -> None:
        """conc == 1.5 exactly should NOT be moderate (code uses > 1.5)."""
        # 4 quotes in cell, need conc = 1.5
        # observed = 4/4 = 1.0, expected = col_total/grand_total
        # conc = 1.0/expected = 1.5 → expected = 2/3 → col_total/grand_total = 2/3
        # grand_total = 12, col_total = 8 → expected = 8/12 = 0.667 → conc = 1.5
        signal = self._signal_from_cell(
            n_quotes_in_cell=4, n_unique_pids=3,
            total_study_quotes=12, col_total=8,
        )
        assert signal.concentration == pytest.approx(1.5, abs=0.01)
        # > 1.5 fails at exactly 1.5
        assert signal.confidence == "emerging"


# ===========================================================================
# Quote lookup consistency
# ===========================================================================


class TestQuoteLookupConsistency:
    """Verify that signal quotes match exactly what's in the matrix cells."""

    def test_signal_quotes_match_matrix_cell_count(self) -> None:
        """Number of quotes attached to a signal == cell count in matrix."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        for signal in result.signals:
            assert len(signal.quotes) == signal.count, (
                f"Signal {signal.location}|{signal.sentiment}: "
                f"{len(signal.quotes)} quotes but count={signal.count}"
            )

    def test_signal_participants_match_quote_pids(self) -> None:
        """Signal.participants should be the unique PIDs from its quotes."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        for signal in result.signals:
            quote_pids = sorted({q.participant_id for q in signal.quotes})
            assert signal.participants == quote_pids, (
                f"Signal {signal.location}|{signal.sentiment}: "
                f"participants={signal.participants} but quote PIDs={quote_pids}"
            )

    def test_signal_quotes_have_correct_sentiment(self) -> None:
        """All quotes on a signal card should have the signal's sentiment.

        This tests that the lookup keys match correctly — if a section label
        or sentiment value is mismatched, wrong quotes would appear.
        """
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        # Build a reverse lookup: text → original quote
        text_to_quote = {q.text: q for q in all_quotes}
        for signal in result.signals:
            for sq in signal.quotes:
                orig = text_to_quote.get(sq.text)
                assert orig is not None, f"Signal quote not found in originals: {sq.text!r}"
                assert orig.sentiment is not None
                assert orig.sentiment.value == signal.sentiment, (
                    f"Quote sentiment {orig.sentiment.value} != signal sentiment {signal.sentiment}"
                )

    def test_duplicate_section_labels_merge(self) -> None:
        """Two clusters with the same screen_label should merge into one row."""
        quotes_a = [_quote(Sentiment.FRUSTRATION, "p1", start=10.0)]
        quotes_b = [_quote(Sentiment.FRUSTRATION, "p2", start=20.0)]
        # Same label, different display_order (first one wins for sorting)
        clusters = [
            _cluster("Checkout", 1, quotes_a),
            _cluster("Checkout", 2, quotes_b),
        ]
        sm = build_section_matrix(clusters)
        # Both quotes land in the same "Checkout|frustration" cell
        cell = sm.cells["Checkout|frustration"]
        assert cell.count == 2
        assert sm.grand_total == 2
        # But row_labels has duplicate — this is worth knowing about
        assert sm.row_labels.count("Checkout") == 2


# ===========================================================================
# _serialize_matrix
# ===========================================================================


class TestSerializeMatrix:

    def test_basic_structure(self) -> None:
        """Serialized matrix has all expected keys."""
        matrix = Matrix(
            cells={"Row|sent": MatrixCell(count=3, participants={"p1": 2, "p2": 1}, intensities=[1, 2, 3])},
            row_totals={"Row": 3},
            col_totals={"sent": 3},
            grand_total=3,
            row_labels=["Row"],
        )
        result = _serialize_matrix(matrix)
        assert set(result.keys()) == {"cells", "rowTotals", "colTotals", "grandTotal", "rowLabels"}

    def test_camel_case_keys(self) -> None:
        """JS convention: camelCase keys, not snake_case."""
        matrix = Matrix(row_labels=["A"])
        result = _serialize_matrix(matrix)
        assert "rowTotals" in result
        assert "colTotals" in result
        assert "grandTotal" in result
        assert "rowLabels" in result
        # No snake_case keys
        assert "row_totals" not in result
        assert "col_totals" not in result

    def test_cell_data_preserved(self) -> None:
        """Cell counts, participants, and intensities survive serialization."""
        cell = MatrixCell(count=5, participants={"p1": 3, "p2": 2}, intensities=[1, 2, 3, 2, 1])
        matrix = Matrix(
            cells={"Checkout|frustration": cell},
            row_totals={"Checkout": 5},
            col_totals={"frustration": 5},
            grand_total=5,
            row_labels=["Checkout"],
        )
        result = _serialize_matrix(matrix)
        serialized_cell = result["cells"]["Checkout|frustration"]
        assert serialized_cell["count"] == 5
        assert serialized_cell["participants"] == {"p1": 3, "p2": 2}
        assert serialized_cell["intensities"] == [1, 2, 3, 2, 1]

    def test_empty_matrix(self) -> None:
        """Empty matrix serializes without error."""
        matrix = Matrix()
        result = _serialize_matrix(matrix)
        assert result["cells"] == {}
        assert result["grandTotal"] == 0
        assert result["rowLabels"] == []


# ===========================================================================
# _serialize_analysis
# ===========================================================================


class TestSerializeAnalysis:

    def _make_analysis(
        self,
        n_participants: int = 6,
    ) -> AnalysisResult:
        clusters, themes, all_quotes, sessions = _realistic_data(n_participants)
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        return result

    def test_returns_valid_json(self) -> None:
        """Serialized output is valid JSON."""
        analysis = self._make_analysis()
        json_str = _serialize_analysis(analysis)
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_top_level_keys(self) -> None:
        """JSON has all required top-level keys."""
        analysis = self._make_analysis()
        data = json.loads(_serialize_analysis(analysis))
        expected_keys = {
            "signals", "sectionMatrix", "themeMatrix",
            "totalParticipants", "sentiments", "participantIds",
        }
        assert set(data.keys()) == expected_keys

    def test_signal_keys(self) -> None:
        """Each signal object has all expected keys."""
        analysis = self._make_analysis()
        data = json.loads(_serialize_analysis(analysis))
        assert len(data["signals"]) > 0
        signal = data["signals"][0]
        expected_keys = {
            "location", "sourceType", "sentiment", "count", "participants",
            "nEff", "meanIntensity", "concentration", "compositeSignal",
            "confidence", "quotes",
        }
        assert set(signal.keys()) == expected_keys

    def test_signal_quote_keys(self) -> None:
        """Each quote in a signal has all expected keys."""
        analysis = self._make_analysis()
        data = json.loads(_serialize_analysis(analysis))
        # Find a signal with quotes
        signal_with_quotes = next(s for s in data["signals"] if len(s["quotes"]) > 0)
        quote = signal_with_quotes["quotes"][0]
        expected_keys = {"text", "pid", "sessionId", "startSeconds", "intensity", "segmentIndex"}
        assert set(quote.keys()) == expected_keys

    def test_float_rounding(self) -> None:
        """Float metrics are rounded for compact JSON."""
        analysis = self._make_analysis()
        data = json.loads(_serialize_analysis(analysis))
        for signal in data["signals"]:
            # nEff: 2 decimal places
            n_eff_str = str(signal["nEff"])
            if "." in n_eff_str:
                assert len(n_eff_str.split(".")[1]) <= 2
            # meanIntensity: 2 decimal places
            mi_str = str(signal["meanIntensity"])
            if "." in mi_str:
                assert len(mi_str.split(".")[1]) <= 2
            # concentration: 2 decimal places
            conc_str = str(signal["concentration"])
            if "." in conc_str:
                assert len(conc_str.split(".")[1]) <= 2
            # compositeSignal: 4 decimal places
            cs_str = str(signal["compositeSignal"])
            if "." in cs_str:
                assert len(cs_str.split(".")[1]) <= 4

    def test_participant_ids_naturally_sorted(self) -> None:
        """Participant IDs are sorted numerically: p1, p2, ..., p10 (not p1, p10, p2)."""
        # Use 12 participants to get a p10+ case
        clusters = [
            _cluster("Checkout", 1, [
                _quote(Sentiment.FRUSTRATION, f"p{i}", session_id=f"s{i}", start=float(i * 10))
                for i in range(1, 13)
            ]),
        ]
        themes: list[ThemeGroup] = []
        all_quotes = clusters[0].quotes
        sessions = [_session(f"s{i}", f"p{i}") for i in range(1, 13)]
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None
        data = json.loads(_serialize_analysis(result))
        pids = data["participantIds"]
        # Should be p1, p2, ..., p12 — not p1, p10, p11, p12, p2, ...
        expected = [f"p{i}" for i in range(1, 13)]
        assert pids == expected

    def test_non_ascii_text_preserved(self) -> None:
        """Non-ASCII characters in quote text survive JSON round-trip."""
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p1", text="C'est très frustrant — ça ne marche pas!"),
            _quote(Sentiment.FRUSTRATION, "p2", text="Das ist wirklich ärgerlich für mich."),
        ]
        clusters = [_cluster("Checkout", 1, quotes)]
        all_quotes = quotes
        result = _compute_analysis(clusters, [], all_quotes)
        assert result is not None
        data = json.loads(_serialize_analysis(result))
        texts = [q["text"] for s in data["signals"] for q in s["quotes"]]
        assert any("très" in t for t in texts)
        assert any("ärgerlich" in t for t in texts)

    def test_empty_signals(self) -> None:
        """Analysis with no signals (all sub-threshold) serializes cleanly."""
        # 1 quote per cell — below MIN_QUOTES_PER_CELL
        clusters = [_cluster("A", 1, [_quote(Sentiment.FRUSTRATION, "p1")])]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=5)
        assert len(result.signals) == 0
        data = json.loads(_serialize_analysis(result))
        assert data["signals"] == []
        assert data["participantIds"] == []

    def test_total_participants_preserved(self) -> None:
        """totalParticipants in JSON matches the AnalysisResult."""
        analysis = self._make_analysis(n_participants=8)
        data = json.loads(_serialize_analysis(analysis))
        assert data["totalParticipants"] == 8

    def test_sentiments_canonical_order(self) -> None:
        """Sentiments list matches the Sentiment enum order."""
        analysis = self._make_analysis()
        data = json.loads(_serialize_analysis(analysis))
        expected = [s.value for s in Sentiment]
        assert data["sentiments"] == expected

    def test_matrices_present_in_json(self) -> None:
        """Both section and theme matrices are included."""
        analysis = self._make_analysis()
        data = json.loads(_serialize_analysis(analysis))
        assert "cells" in data["sectionMatrix"]
        assert "cells" in data["themeMatrix"]
        assert len(data["sectionMatrix"]["rowLabels"]) > 0
        assert len(data["themeMatrix"]["rowLabels"]) > 0


# ===========================================================================
# End-to-end: render_html → analysis.html
# ===========================================================================


class TestRenderAnalysisPage:
    """Test that _render_analysis_page produces correct HTML with injected data."""

    def _render_with_analysis(self, tmp_path: Path) -> tuple[str, str]:
        """Render a full report with analysis and return (report_html, analysis_html)."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None

        render_html(
            screen_clusters=clusters,
            theme_groups=themes,
            sessions=sessions,
            project_name="QA Test",
            output_dir=tmp_path,
            all_quotes=all_quotes,
            analysis=result,
        )

        report_path = tmp_path / "bristlenose-qa-test-report.html"
        analysis_path = tmp_path / "analysis.html"
        return (
            report_path.read_text(encoding="utf-8"),
            analysis_path.read_text(encoding="utf-8"),
        )

    def test_analysis_file_created(self, tmp_path: Path) -> None:
        """analysis.html is written to the output directory."""
        self._render_with_analysis(tmp_path)
        assert (tmp_path / "analysis.html").exists()

    def test_analysis_not_created_when_none(self, tmp_path: Path) -> None:
        """No analysis.html when analysis=None."""
        render_html(
            screen_clusters=[],
            theme_groups=[],
            sessions=[],
            project_name="No Analysis",
            output_dir=tmp_path,
        )
        assert not (tmp_path / "analysis.html").exists()

    def test_analysis_page_has_injected_json(self, tmp_path: Path) -> None:
        """The analysis page contains the BRISTLENOSE_ANALYSIS JSON global."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert "BRISTLENOSE_ANALYSIS" in analysis_html

    def test_analysis_json_is_parseable(self, tmp_path: Path) -> None:
        """The injected JSON can be extracted and parsed."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        # Extract JSON between "var BRISTLENOSE_ANALYSIS = " and ";"
        marker = "var BRISTLENOSE_ANALYSIS = "
        start = analysis_html.index(marker) + len(marker)
        end = analysis_html.index(";", start)
        json_str = analysis_html[start:end]
        data = json.loads(json_str)
        assert "signals" in data
        assert "sectionMatrix" in data
        assert "totalParticipants" in data

    def test_analysis_page_has_report_filename(self, tmp_path: Path) -> None:
        """The analysis page has the back-link report filename."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert "BRISTLENOSE_REPORT_FILENAME" in analysis_html
        assert "bristlenose-qa-test-report.html" in analysis_html

    def test_analysis_page_has_back_link(self, tmp_path: Path) -> None:
        """The analysis page has a navigation back link to the report."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert "bristlenose-qa-test-report.html" in analysis_html
        assert "QA Test Research Report" in analysis_html

    def test_analysis_page_has_css_link(self, tmp_path: Path) -> None:
        """The analysis page links to the shared theme CSS."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert "assets/bristlenose-theme.css" in analysis_html

    def test_analysis_page_has_init_call(self, tmp_path: Path) -> None:
        """The analysis page calls initAnalysis()."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert "initAnalysis();" in analysis_html

    def test_analysis_page_has_template_placeholders(self, tmp_path: Path) -> None:
        """The analysis page has the div containers from the template."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert 'id="signal-cards"' in analysis_html
        assert 'id="heatmap-section-container"' in analysis_html
        assert 'id="heatmap-theme-container"' in analysis_html

    def test_analysis_page_has_project_name_in_title(self, tmp_path: Path) -> None:
        """The page title includes the project name."""
        _, analysis_html = self._render_with_analysis(tmp_path)
        assert "<title>" in analysis_html
        assert "QA Test" in analysis_html

    def test_report_has_inline_analysis(self, tmp_path: Path) -> None:
        """The main report embeds analysis data and containers inline."""
        report_html, _ = self._render_with_analysis(tmp_path)
        assert "BRISTLENOSE_ANALYSIS" in report_html
        assert 'id="signal-cards"' in report_html

    def test_analysis_data_matches_computation(self, tmp_path: Path) -> None:
        """The JSON injected in HTML matches what _compute_analysis produced."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None

        render_html(
            screen_clusters=clusters,
            theme_groups=themes,
            sessions=sessions,
            project_name="Match Test",
            output_dir=tmp_path,
            all_quotes=all_quotes,
            analysis=result,
        )

        analysis_html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
        marker = "var BRISTLENOSE_ANALYSIS = "
        start = analysis_html.index(marker) + len(marker)
        end = analysis_html.index(";", start)
        data = json.loads(analysis_html[start:end])

        # Signal count should match
        assert len(data["signals"]) == len(result.signals)

        # Total participants should match
        assert data["totalParticipants"] == result.total_participants

        # Signal locations and sentiments should match in order
        for json_sig, py_sig in zip(data["signals"], result.signals):
            assert json_sig["location"] == py_sig.location
            assert json_sig["sentiment"] == py_sig.sentiment
            assert json_sig["count"] == py_sig.count
            assert json_sig["confidence"] == py_sig.confidence
            assert len(json_sig["quotes"]) == len(py_sig.quotes)

    def test_analysis_page_color_scheme_propagated(self, tmp_path: Path) -> None:
        """Color scheme setting propagates to the analysis page."""
        clusters, themes, all_quotes, sessions = _realistic_data()
        result = _compute_analysis(clusters, themes, all_quotes, sessions)
        assert result is not None

        render_html(
            screen_clusters=clusters,
            theme_groups=themes,
            sessions=sessions,
            project_name="Dark Test",
            output_dir=tmp_path,
            all_quotes=all_quotes,
            analysis=result,
            color_scheme="dark",
        )

        analysis_html = (tmp_path / "analysis.html").read_text(encoding="utf-8")
        assert 'data-theme="dark"' in analysis_html


# ===========================================================================
# Edge cases: data shapes the pipeline might encounter
# ===========================================================================


class TestAnalysisEdgeCases:

    def test_single_participant_all_quotes(self) -> None:
        """All quotes from one person — n_eff should be low, signals still work."""
        quotes = [_quote(Sentiment.FRUSTRATION, "p1", start=float(i)) for i in range(5)]
        clusters = [_cluster("Checkout", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes)
        assert result is not None
        assert len(result.signals) == 1
        sig = result.signals[0]
        assert sig.n_eff == pytest.approx(1.0)
        assert sig.participants == ["p1"]

    def test_all_sentiments_same(self) -> None:
        """Every quote has the same sentiment — concentration ratio = 1.0."""
        quotes = [
            _quote(Sentiment.FRUSTRATION, f"p{i}", session_id=f"s{i}", start=float(i * 10))
            for i in range(1, 5)
        ]
        clusters = [_cluster("Checkout", 1, quotes[:2]), _cluster("Search", 2, quotes[2:])]
        result = _compute_analysis(clusters, [], quotes)
        assert result is not None
        for sig in result.signals:
            assert sig.concentration == pytest.approx(1.0)

    def test_many_sections_few_quotes(self) -> None:
        """10 sections with 1 quote each — all below MIN_QUOTES_PER_CELL, no signals."""
        clusters = [
            _cluster(f"Section{i}", i, [_quote(Sentiment.FRUSTRATION, f"p{i}")])
            for i in range(10)
        ]
        all_quotes = [q for c in clusters for q in c.quotes]
        result = _compute_analysis(clusters, [], all_quotes)
        assert result is not None
        assert result.signals == []

    def test_high_intensity_all_3(self) -> None:
        """All intensity=3 — mean_intensity should be 3.0."""
        quotes = [_quote(Sentiment.FRUSTRATION, f"p{i}", intensity=3) for i in range(1, 4)]
        clusters = [_cluster("Checkout", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes)
        assert result is not None
        assert result.signals[0].mean_intensity == pytest.approx(3.0)

    def test_mixed_intensity(self) -> None:
        """Mixed intensity values — verify mean is correct."""
        quotes = [
            _quote(Sentiment.FRUSTRATION, "p1", intensity=1),
            _quote(Sentiment.FRUSTRATION, "p2", intensity=2),
            _quote(Sentiment.FRUSTRATION, "p3", intensity=3),
        ]
        clusters = [_cluster("Checkout", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes)
        assert result is not None
        assert result.signals[0].mean_intensity == pytest.approx(2.0)

    def test_section_and_theme_signals_have_correct_source_type(self) -> None:
        """Section signals say 'section', theme signals say 'theme'."""
        section_quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        theme_quotes = [_quote(Sentiment.DOUBT, "p3"), _quote(Sentiment.DOUBT, "p4")]
        clusters = [_cluster("Checkout", 1, section_quotes)]
        themes = [_theme("Trust", theme_quotes)]
        all_quotes = section_quotes + theme_quotes
        result = _compute_analysis(clusters, themes, all_quotes)
        assert result is not None
        source_types = {s.source_type for s in result.signals}
        assert source_types == {"section", "theme"}
        for sig in result.signals:
            if sig.location == "Checkout":
                assert sig.source_type == "section"
            elif sig.location == "Trust":
                assert sig.source_type == "theme"

    def test_special_characters_in_labels(self) -> None:
        """Labels with special characters (HTML entities, pipes) don't break."""
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        # Pipe in label would break the cell key format if not handled
        clusters = [_cluster("Checkout & Payment", 1, quotes)]
        result = _compute_analysis(clusters, [], quotes)
        assert result is not None
        assert len(result.signals) == 1
        assert result.signals[0].location == "Checkout & Payment"

    def test_pipe_in_label_breaks_key_format(self) -> None:
        """A pipe character in a label would break cell key lookups.

        This documents the current behaviour — keys use 'label|sentiment' format,
        so a label containing '|' would create ambiguous keys.
        """
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        clusters = [_cluster("Screen | Detail", 1, quotes)]
        sm = build_section_matrix(clusters)
        # The key becomes "Screen | Detail|frustration" which is ambiguous
        # but currently works because lookup is exact-match, not split
        cell = sm.cells.get("Screen | Detail|frustration")
        assert cell is not None
        assert cell.count == 2

    def test_zero_total_participants_edge(self) -> None:
        """total_participants=0 shouldn't crash (composite_signal handles it)."""
        # This can't happen via _compute_analysis (it counts from data),
        # but test detect_signals directly with 0
        quotes = [_quote(Sentiment.FRUSTRATION, "p1"), _quote(Sentiment.FRUSTRATION, "p2")]
        clusters = [_cluster("Checkout", 1, quotes)]
        sm = build_section_matrix(clusters)
        tm = build_theme_matrix([])
        result = detect_signals(sm, tm, clusters, [], total_participants=0)
        # Should produce signals but with composite_signal=0
        for sig in result.signals:
            assert sig.composite_signal == 0.0

    def test_large_dataset_top_n_capping(self) -> None:
        """With many cells producing signals, only top 12 survive."""
        clusters = []
        for i in range(20):
            quotes = [
                _quote(Sentiment.FRUSTRATION, f"p{j}", session_id=f"s{j}", start=float(i * 100 + j))
                for j in range(1, 4)
            ]
            clusters.append(_cluster(f"Section{i}", i, quotes))
        all_quotes = [q for c in clusters for q in c.quotes]
        result = _compute_analysis(clusters, [], all_quotes)
        assert result is not None
        assert len(result.signals) <= 12  # DEFAULT_TOP_N
