"""Data structures for analysis page computation.

These are plain dataclasses (not Pydantic) — they're ephemeral, computed from
existing pipeline data, and never persisted to intermediate JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MatrixCell:
    """One cell in the section/theme x sentiment matrix."""

    count: int = 0
    participants: dict[str, int] = field(default_factory=dict)  # pid -> count
    intensities: list[int] = field(default_factory=list)
    weighted_count: float = 0.0  # confidence-weighted count (tag analysis only)


@dataclass
class Matrix:
    """A row x column contingency table with sentiment columns."""

    cells: dict[str, MatrixCell] = field(default_factory=dict)  # "row|sentiment" -> cell
    row_totals: dict[str, int] = field(default_factory=dict)
    col_totals: dict[str, int] = field(default_factory=dict)
    grand_total: int = 0
    row_labels: list[str] = field(default_factory=list)


@dataclass
class SignalQuote:
    """A quote associated with a signal card."""

    text: str
    participant_id: str
    session_id: str
    start_seconds: float
    intensity: int
    tag_names: list[str] = field(default_factory=list)  # specific tags from the group
    segment_index: int = -1  # 0-based ordinal in the session transcript (-1 = unknown)


@dataclass
class Signal:
    """A notable pattern detected in the data."""

    location: str  # section or theme label
    source_type: str  # "section" or "theme"
    sentiment: str  # e.g. "frustration"
    count: int
    participants: list[str]  # unique pids present
    n_eff: float
    mean_intensity: float
    concentration: float
    composite_signal: float
    confidence: str  # "strong", "moderate", "emerging"
    quotes: list[SignalQuote] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis computation results, passed to the renderer."""

    section_matrix: Matrix
    theme_matrix: Matrix
    signals: list[Signal]  # merged and sorted by composite_signal desc
    total_participants: int
    sentiments: list[str]  # canonical order
