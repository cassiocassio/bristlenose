"""Build row x column contingency matrices from grouped quotes."""

from __future__ import annotations

from bristlenose.analysis.models import Matrix, MatrixCell
from bristlenose.models import ExtractedQuote, ScreenCluster, Sentiment, ThemeGroup

SENTIMENTS = [s.value for s in Sentiment]


def build_section_matrix(screen_clusters: list[ScreenCluster]) -> Matrix:
    """Build a matrix with sections as rows and sentiments as columns."""
    row_labels = [c.screen_label for c in sorted(screen_clusters, key=lambda c: c.display_order)]
    matrix = _init_matrix(row_labels, SENTIMENTS)
    for cluster in screen_clusters:
        for q in cluster.quotes:
            _add_quote(matrix, cluster.screen_label, q)
    return matrix


def build_theme_matrix(theme_groups: list[ThemeGroup]) -> Matrix:
    """Build a matrix with themes as rows and sentiments as columns."""
    row_labels = [t.theme_label for t in theme_groups]
    matrix = _init_matrix(row_labels, SENTIMENTS)
    for theme in theme_groups:
        for q in theme.quotes:
            _add_quote(matrix, theme.theme_label, q)
    return matrix


def _init_matrix(row_labels: list[str], sentiments: list[str]) -> Matrix:
    """Create an empty matrix with zeroed cells."""
    matrix = Matrix(row_labels=list(row_labels))
    for row in row_labels:
        matrix.row_totals[row] = 0
    for sent in sentiments:
        matrix.col_totals[sent] = 0
    for row in row_labels:
        for sent in sentiments:
            matrix.cells[f"{row}|{sent}"] = MatrixCell()
    return matrix


def _add_quote(matrix: Matrix, row_label: str, quote: ExtractedQuote) -> None:
    """Add a single quote to the matrix, updating cell, row, and column totals."""
    if quote.sentiment is None:
        return
    sent = quote.sentiment.value
    key = f"{row_label}|{sent}"
    cell = matrix.cells.get(key)
    if cell is None:
        return
    cell.count += 1
    cell.participants[quote.participant_id] = (
        cell.participants.get(quote.participant_id, 0) + 1
    )
    cell.intensities.append(quote.intensity)
    matrix.row_totals[row_label] = matrix.row_totals.get(row_label, 0) + 1
    matrix.col_totals[sent] = matrix.col_totals.get(sent, 0) + 1
    matrix.grand_total += 1
