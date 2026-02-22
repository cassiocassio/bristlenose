"""Unit tests for dashboard coverage calculation helper."""

from __future__ import annotations

from bristlenose.server.routes.dashboard import (
    _calculate_coverage,
    _format_fragments_html,
    _is_moderator_code,
)

# ---------------------------------------------------------------------------
# _is_moderator_code
# ---------------------------------------------------------------------------


class TestIsModeratorCode:
    def test_moderator(self) -> None:
        assert _is_moderator_code("m1") is True

    def test_observer(self) -> None:
        assert _is_moderator_code("o1") is True

    def test_participant(self) -> None:
        assert _is_moderator_code("p1") is False

    def test_empty(self) -> None:
        assert _is_moderator_code("") is False


# ---------------------------------------------------------------------------
# _format_fragments_html
# ---------------------------------------------------------------------------


class TestFormatFragmentsHtml:
    def test_empty(self) -> None:
        assert _format_fragments_html([]) == ""

    def test_single_with_count_1(self) -> None:
        result = _format_fragments_html([("Okay.", 1)])
        assert '<span class="verbatim">Okay.</span>' in result
        assert "Also omitted:" in result
        assert "×" not in result

    def test_single_with_count_gt_1(self) -> None:
        result = _format_fragments_html([("Yeah.", 3)])
        assert '<span class="verbatim">Yeah.</span> (3×)' in result

    def test_multiple_fragments(self) -> None:
        result = _format_fragments_html([("Okay.", 4), ("Yeah.", 2)])
        assert "Okay." in result
        assert "Yeah." in result
        assert "(4×)" in result
        assert "(2×)" in result
        assert ", " in result

    def test_html_escaping(self) -> None:
        result = _format_fragments_html([("<script>", 1)])
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


# ---------------------------------------------------------------------------
# _calculate_coverage (requires DB — tested via integration in
# test_serve_dashboard_api.py; here we test the pure helper contract)
# ---------------------------------------------------------------------------


class TestCalculateCoverageContract:
    def test_returns_none_for_empty_sessions(self) -> None:
        """No sessions → None."""
        # Pass an empty sessions list; db won't be queried.
        result = _calculate_coverage(None, 1, [])  # type: ignore[arg-type]
        assert result is None
