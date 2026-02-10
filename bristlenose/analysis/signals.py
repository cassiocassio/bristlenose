"""Detect notable patterns (signals) from analysis matrices."""

from __future__ import annotations

from bristlenose.analysis.matrix import SENTIMENTS
from bristlenose.analysis.metrics import (
    composite_signal,
    concentration_ratio,
    mean_intensity,
    simpsons_neff,
)
from bristlenose.analysis.models import AnalysisResult, Matrix, Signal, SignalQuote
from bristlenose.models import ExtractedQuote, ScreenCluster, ThemeGroup

DEFAULT_TOP_N = 12
MIN_QUOTES_PER_CELL = 2


def detect_signals(
    section_matrix: Matrix,
    theme_matrix: Matrix,
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    total_participants: int,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> AnalysisResult:
    """Run full signal detection and return results ready for rendering.

    Merges section and theme signals, sorts by composite signal descending,
    and takes the top *top_n*.
    """
    section_signals = _compute_signals(
        section_matrix,
        total_participants,
        "section",
        _build_quote_lookup_sections(screen_clusters),
    )
    theme_signals = _compute_signals(
        theme_matrix,
        total_participants,
        "theme",
        _build_quote_lookup_themes(theme_groups),
    )

    all_signals = section_signals + theme_signals
    all_signals.sort(key=lambda s: s.composite_signal, reverse=True)
    all_signals = all_signals[:top_n]

    return AnalysisResult(
        section_matrix=section_matrix,
        theme_matrix=theme_matrix,
        signals=all_signals,
        total_participants=total_participants,
        sentiments=list(SENTIMENTS),
    )


def _compute_signals(
    matrix: Matrix,
    total_participants: int,
    source_type: str,
    quote_lookup: dict[str, list[ExtractedQuote]],
) -> list[Signal]:
    """Find signals in a single matrix (section or theme)."""
    signals: list[Signal] = []
    for row in matrix.row_labels:
        for sent in SENTIMENTS:
            cell = matrix.cells.get(f"{row}|{sent}")
            if not cell or cell.count < MIN_QUOTES_PER_CELL:
                continue

            p_counts = list(cell.participants.values())
            n_eff = simpsons_neff(p_counts)
            m_int = mean_intensity(cell.intensities)
            conc = concentration_ratio(
                cell.count,
                matrix.row_totals[row],
                matrix.col_totals[sent],
                matrix.grand_total,
            )
            comp = composite_signal(conc, n_eff, total_participants, m_int)
            unique_pids = sorted(cell.participants.keys())

            # Confidence classification (computed, hidden from UI for now)
            if conc > 2 and len(unique_pids) >= 5 and cell.count >= 6:
                confidence = "strong"
            elif conc > 1.5 and len(unique_pids) >= 3 and cell.count >= 4:
                confidence = "moderate"
            else:
                confidence = "emerging"

            # Attach actual quotes sorted by participant then timecode
            raw_quotes = quote_lookup.get(f"{row}|{sent}", [])
            raw_quotes_sorted = sorted(
                raw_quotes, key=lambda q: (q.participant_id, q.start_timecode)
            )
            signal_quotes = [
                SignalQuote(
                    text=q.text,
                    participant_id=q.participant_id,
                    session_id=q.session_id,
                    start_seconds=q.start_timecode,
                    intensity=q.intensity,
                )
                for q in raw_quotes_sorted
            ]

            signals.append(
                Signal(
                    location=row,
                    source_type=source_type,
                    sentiment=sent,
                    count=cell.count,
                    participants=unique_pids,
                    n_eff=n_eff,
                    mean_intensity=m_int,
                    concentration=conc,
                    composite_signal=comp,
                    confidence=confidence,
                    quotes=signal_quotes,
                )
            )
    return signals


def _build_quote_lookup_sections(
    clusters: list[ScreenCluster],
) -> dict[str, list[ExtractedQuote]]:
    """Map ``"section_label|sentiment"`` to list of quotes."""
    lookup: dict[str, list[ExtractedQuote]] = {}
    for cluster in clusters:
        for q in cluster.quotes:
            if q.sentiment is None:
                continue
            key = f"{cluster.screen_label}|{q.sentiment.value}"
            lookup.setdefault(key, []).append(q)
    return lookup


def _build_quote_lookup_themes(
    themes: list[ThemeGroup],
) -> dict[str, list[ExtractedQuote]]:
    """Map ``"theme_label|sentiment"`` to list of quotes."""
    lookup: dict[str, list[ExtractedQuote]] = {}
    for theme in themes:
        for q in theme.quotes:
            if q.sentiment is None:
                continue
            key = f"{theme.theme_label}|{q.sentiment.value}"
            lookup.setdefault(key, []).append(q)
    return lookup
