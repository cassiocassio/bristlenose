"""Detect signals from matrices with arbitrary column labels.

The pipeline-specific ``signals.py`` is hardwired to the ``SENTIMENTS`` list.
This module provides the same signal detection logic parameterised on
*col_labels*, so serve-mode can detect signals for codebook groups, individual
tags, or any other categorical dimension.
"""

from __future__ import annotations

from dataclasses import dataclass

from bristlenose.analysis.metrics import (
    composite_signal,
    concentration_ratio,
    mean_intensity,
    simpsons_neff,
)
from bristlenose.analysis.models import Matrix, Signal, SignalQuote

DEFAULT_TOP_N = 12
MIN_QUOTES_PER_CELL = 2


@dataclass
class QuoteRecord:
    """Minimal quote data needed for signal quote attachment."""

    text: str
    participant_id: str
    session_id: str
    start_seconds: float
    intensity: int
    tag_names: list[str] | None = None  # specific tags from the group (passthrough)


def detect_signals_generic(
    section_matrix: Matrix,
    theme_matrix: Matrix,
    col_labels: list[str],
    total_participants: int,
    section_quote_lookup: dict[str, list[QuoteRecord]],
    theme_quote_lookup: dict[str, list[QuoteRecord]],
    *,
    top_n: int = DEFAULT_TOP_N,
) -> tuple[list[Signal], Matrix, Matrix]:
    """Run signal detection on matrices with arbitrary columns.

    Returns ``(signals, section_matrix, theme_matrix)``.  The
    ``Signal.sentiment`` field carries the column label (e.g. a codebook
    group name) — the field name is a historical artifact from the
    sentiment-only analysis module.
    """
    section_signals = _compute_signals(
        section_matrix, col_labels, total_participants, "section",
        section_quote_lookup,
    )
    theme_signals = _compute_signals(
        theme_matrix, col_labels, total_participants, "theme",
        theme_quote_lookup,
    )
    all_signals = section_signals + theme_signals
    all_signals.sort(key=lambda s: s.composite_signal, reverse=True)
    return all_signals[:top_n], section_matrix, theme_matrix


def _compute_signals(
    matrix: Matrix,
    col_labels: list[str],
    total_participants: int,
    source_type: str,
    quote_lookup: dict[str, list[QuoteRecord]],
) -> list[Signal]:
    """Find signals in a single matrix."""
    signals: list[Signal] = []
    for row in matrix.row_labels:
        for col in col_labels:
            cell = matrix.cells.get(f"{row}|{col}")
            if not cell or cell.count < MIN_QUOTES_PER_CELL:
                continue

            p_counts = list(cell.participants.values())
            n_eff = simpsons_neff(p_counts)
            m_int = mean_intensity(cell.intensities)
            conc = concentration_ratio(
                cell.count,
                matrix.row_totals[row],
                matrix.col_totals[col],
                matrix.grand_total,
            )
            comp = composite_signal(conc, n_eff, total_participants, m_int)
            unique_pids = sorted(cell.participants.keys())

            # Confidence classification — same thresholds as signals.py
            if conc > 2 and len(unique_pids) >= 5 and cell.count >= 6:
                confidence = "strong"
            elif conc > 1.5 and len(unique_pids) >= 3 and cell.count >= 4:
                confidence = "moderate"
            else:
                confidence = "emerging"

            raw_quotes = quote_lookup.get(f"{row}|{col}", [])
            raw_quotes_sorted = sorted(
                raw_quotes, key=lambda q: (q.participant_id, q.start_seconds),
            )
            signal_quotes = [
                SignalQuote(
                    text=q.text,
                    participant_id=q.participant_id,
                    session_id=q.session_id,
                    start_seconds=q.start_seconds,
                    intensity=q.intensity,
                    tag_names=list(q.tag_names) if q.tag_names else [],
                )
                for q in raw_quotes_sorted
            ]

            signals.append(
                Signal(
                    location=row,
                    source_type=source_type,
                    sentiment=col,  # carries column label (e.g. group name)
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
