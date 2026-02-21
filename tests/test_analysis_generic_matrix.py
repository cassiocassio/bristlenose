"""Tests for bristlenose.analysis.generic_matrix — generic matrix building."""

from __future__ import annotations

from bristlenose.analysis.generic_matrix import QuoteContribution, build_matrix_from_contributions


def _contrib(
    row: str = "Checkout",
    col: str = "Friction",
    pid: str = "p1",
    intensity: int = 2,
) -> QuoteContribution:
    return QuoteContribution(row_label=row, col_label=col, participant_id=pid, intensity=intensity)


# ---------------------------------------------------------------------------
# build_matrix_from_contributions
# ---------------------------------------------------------------------------


class TestBuildMatrixFromContributions:

    def test_empty_contributions(self) -> None:
        m = build_matrix_from_contributions([], ["A"], ["X"])
        assert m.grand_total == 0
        assert m.cells["A|X"].count == 0
        assert m.row_totals["A"] == 0
        assert m.col_totals["X"] == 0

    def test_empty_labels(self) -> None:
        m = build_matrix_from_contributions([], [], [])
        assert m.grand_total == 0
        assert m.row_labels == []
        assert m.cells == {}

    def test_single_cell(self) -> None:
        contribs = [_contrib("Checkout", "Friction", "p1"), _contrib("Checkout", "Friction", "p2")]
        m = build_matrix_from_contributions(contribs, ["Checkout"], ["Friction"])
        assert m.grand_total == 2
        assert m.row_totals["Checkout"] == 2
        assert m.col_totals["Friction"] == 2
        cell = m.cells["Checkout|Friction"]
        assert cell.count == 2
        assert cell.participants == {"p1": 1, "p2": 1}

    def test_multiple_rows_and_columns(self) -> None:
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Delight", "p2"),
            _contrib("Search", "Friction", "p3"),
        ]
        m = build_matrix_from_contributions(
            contribs, ["Checkout", "Search"], ["Friction", "Delight"],
        )
        assert m.grand_total == 3
        assert m.row_totals["Checkout"] == 2
        assert m.row_totals["Search"] == 1
        assert m.col_totals["Friction"] == 2
        assert m.col_totals["Delight"] == 1
        assert m.cells["Checkout|Friction"].count == 1
        assert m.cells["Checkout|Delight"].count == 1
        assert m.cells["Search|Friction"].count == 1
        assert m.cells["Search|Delight"].count == 0

    def test_multi_group_counting_inflates_grand_total(self) -> None:
        """One quote in two groups → two contributions → grand_total = 2, not 1."""
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Emotions", "p1"),
        ]
        m = build_matrix_from_contributions(
            contribs, ["Checkout"], ["Friction", "Emotions"],
        )
        assert m.grand_total == 2  # inflated: one quote counted twice
        assert m.row_totals["Checkout"] == 2
        assert m.col_totals["Friction"] == 1
        assert m.col_totals["Emotions"] == 1

    def test_participant_counting(self) -> None:
        contribs = [
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p1"),
            _contrib("Checkout", "Friction", "p2"),
        ]
        m = build_matrix_from_contributions(contribs, ["Checkout"], ["Friction"])
        cell = m.cells["Checkout|Friction"]
        assert cell.participants == {"p1": 2, "p2": 1}
        assert cell.count == 3

    def test_intensity_tracking(self) -> None:
        contribs = [
            _contrib("Checkout", "Friction", intensity=1),
            _contrib("Checkout", "Friction", intensity=3),
            _contrib("Checkout", "Friction", intensity=2),
        ]
        m = build_matrix_from_contributions(contribs, ["Checkout"], ["Friction"])
        assert m.cells["Checkout|Friction"].intensities == [1, 3, 2]

    def test_all_cells_initialised(self) -> None:
        m = build_matrix_from_contributions([], ["A", "B"], ["X", "Y"])
        for row in ["A", "B"]:
            for col in ["X", "Y"]:
                assert f"{row}|{col}" in m.cells
                assert m.cells[f"{row}|{col}"].count == 0

    def test_contribution_to_unknown_cell_ignored(self) -> None:
        """Contributions with row/col not in labels are silently skipped."""
        contribs = [_contrib("Unknown", "Missing", "p1")]
        m = build_matrix_from_contributions(contribs, ["Checkout"], ["Friction"])
        assert m.grand_total == 0

    def test_row_labels_preserved(self) -> None:
        m = build_matrix_from_contributions([], ["Zebra", "Alpha"], ["X"])
        assert m.row_labels == ["Zebra", "Alpha"]
