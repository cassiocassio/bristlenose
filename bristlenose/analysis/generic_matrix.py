"""Generic matrix builder — works with any row × column dimensions.

The pipeline-specific builders in ``matrix.py`` are coupled to Pydantic models
(``ExtractedQuote``, ``ScreenCluster``).  This module provides the same maths
over a flat list of ``QuoteContribution`` tuples, letting serve-mode build
matrices from database rows without importing pipeline models.

.. note::

   When a quote has tags in multiple codebook groups, it produces one
   ``QuoteContribution`` per group.  This inflates ``grand_total`` relative to
   the number of unique quotes — the trade-off is documented and the signal
   maths remains internally consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from bristlenose.analysis.models import Matrix, MatrixCell


@dataclass
class QuoteContribution:
    """One quote's contribution to a single cell of a matrix.

    The caller creates one instance per (row, column) combination the quote
    participates in.  ``weight`` defaults to 1.0 for confirmed tags; pending
    proposed tags use the LLM confidence score (0.0–1.0).
    """

    row_label: str
    col_label: str
    participant_id: str
    intensity: int
    weight: float = 1.0


def build_matrix_from_contributions(
    contributions: list[QuoteContribution],
    row_labels: list[str],
    col_labels: list[str],
) -> Matrix:
    """Build a row × column contingency table from flat contributions.

    This is the generic equivalent of ``build_section_matrix`` /
    ``build_theme_matrix`` in ``matrix.py``.  The caller is responsible for
    producing the contributions list — this function only counts.
    """
    matrix = Matrix(row_labels=list(row_labels))
    for row in row_labels:
        matrix.row_totals[row] = 0
    for col in col_labels:
        matrix.col_totals[col] = 0
    for row in row_labels:
        for col in col_labels:
            matrix.cells[f"{row}|{col}"] = MatrixCell()

    for c in contributions:
        key = f"{c.row_label}|{c.col_label}"
        cell = matrix.cells.get(key)
        if cell is None:
            continue
        cell.count += 1
        cell.weighted_count += c.weight
        cell.participants[c.participant_id] = (
            cell.participants.get(c.participant_id, 0) + 1
        )
        cell.intensities.append(c.intensity)
        matrix.row_totals[c.row_label] = matrix.row_totals.get(c.row_label, 0) + 1
        matrix.col_totals[c.col_label] = matrix.col_totals.get(c.col_label, 0) + 1
        matrix.grand_total += 1

    return matrix
