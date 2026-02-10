"""Tests for search-as-you-type filtering in the HTML report."""

from __future__ import annotations

from pathlib import Path

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    QuoteIntent,
    QuoteType,
    ScreenCluster,
    ThemeGroup,
)
from bristlenose.stages.render_html import render_html

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quote(pid: str = "p1") -> ExtractedQuote:
    return ExtractedQuote(
        participant_id=pid,
        start_timecode=10.0,
        end_timecode=20.0,
        text="Test quote text",
        topic_label="Topic",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL,
    )


def _render_report(tmp_path: Path) -> str:
    render_html(
        screen_clusters=[
            ScreenCluster(
                screen_label="Homepage",
                description="Landing page",
                display_order=1,
                quotes=[_make_quote()],
            ),
        ],
        theme_groups=[
            ThemeGroup(
                theme_label="Trust",
                description="Trust perceptions",
                quotes=[_make_quote()],
            ),
        ],
        sessions=[],
        project_name="Search Test",
        output_dir=tmp_path,
    )
    return (tmp_path / "bristlenose-search-test-report.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# HTML structure
# ---------------------------------------------------------------------------

def test_toolbar_has_search_container(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'id="search-container"' in html


def test_toolbar_has_search_toggle(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'id="search-toggle"' in html


def test_toolbar_has_search_input(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'id="search-input"' in html


def test_search_input_has_placeholder(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'placeholder="Filter quotes' in html


def test_search_toggle_has_aria_label(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'aria-label="Search quotes"' in html


def test_search_toggle_has_svg_icon(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert '<circle cx="6.5" cy="6.5"' in html


# ---------------------------------------------------------------------------
# Clear button
# ---------------------------------------------------------------------------

def test_toolbar_has_search_clear_button(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'id="search-clear"' in html


def test_search_clear_has_aria_label(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'aria-label="Clear search"' in html


# ---------------------------------------------------------------------------
# Field wrapper
# ---------------------------------------------------------------------------

def test_toolbar_has_search_field_wrapper(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'class="search-field"' in html


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def test_css_has_search_container(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-container" in css


def test_css_has_search_input(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-input" in css


def test_css_has_search_toggle(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-toggle" in css


def test_css_has_search_clear(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-clear" in css


def test_css_has_query_shows_clear(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-container.has-query .search-clear" in css


def test_css_has_search_field(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-field" in css


def test_css_has_highlight_token(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert "--bn-colour-highlight" in css


def test_css_has_search_mark(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".search-mark" in css


# ---------------------------------------------------------------------------
# JS bootstrap
# ---------------------------------------------------------------------------

def test_init_search_filter_called(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "initSearchFilter" in html


def test_search_js_in_report(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "search.js" in html


# ---------------------------------------------------------------------------
# Transcript pages exclude search
# ---------------------------------------------------------------------------

def test_transcript_js_excludes_search() -> None:
    """search.js must not be in the transcript JS list."""
    from bristlenose.stages.render_html import _TRANSCRIPT_JS_FILES

    assert "js/search.js" not in _TRANSCRIPT_JS_FILES
