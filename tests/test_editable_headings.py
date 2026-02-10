"""Tests for editable section/theme titles and descriptions in the HTML report."""

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


def _render_with_sections_and_themes(tmp_path: Path) -> str:
    """Render a report with one section and one theme, return HTML string."""
    project_name = "Editable Test"
    render_html(
        screen_clusters=[
            ScreenCluster(
                screen_label="Homepage",
                description="Initial landing page with navigation",
                display_order=1,
                quotes=[_make_quote()],
            ),
        ],
        theme_groups=[
            ThemeGroup(
                theme_label="Brand perception",
                description="Participants share positive feelings about the brand",
                quotes=[_make_quote()],
            ),
        ],
        sessions=[],
        project_name=project_name,
        output_dir=tmp_path,
    )
    # New layout: bristlenose-{slug}-report.html
    return (tmp_path / "bristlenose-editable-test-report.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Section title
# ---------------------------------------------------------------------------

def test_section_title_has_editable_span(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert '<span class="editable-text"' in html
    assert 'data-edit-key="section-homepage:title"' in html


def test_section_title_has_data_original(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'data-original="Homepage"' in html


def test_section_title_has_inline_pencil(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'class="edit-pencil edit-pencil-inline"' in html
    assert 'aria-label="Edit section title"' in html


# ---------------------------------------------------------------------------
# Section description
# ---------------------------------------------------------------------------

def test_section_description_has_editable_span(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'data-edit-key="section-homepage:desc"' in html


def test_section_description_has_data_original(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'data-original="Initial landing page with navigation"' in html


def test_section_description_has_inline_pencil(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'aria-label="Edit section description"' in html


# ---------------------------------------------------------------------------
# Theme title
# ---------------------------------------------------------------------------

def test_theme_title_has_editable_span(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'data-edit-key="theme-brand-perception:title"' in html


def test_theme_title_has_data_original(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'data-original="Brand perception"' in html


def test_theme_title_has_inline_pencil(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'aria-label="Edit theme title"' in html


# ---------------------------------------------------------------------------
# Theme description
# ---------------------------------------------------------------------------

def test_theme_description_has_editable_span(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'data-edit-key="theme-brand-perception:desc"' in html


def test_theme_description_has_data_original(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert (
        'data-original="Participants share positive feelings about the brand"'
        in html
    )


def test_theme_description_has_inline_pencil(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert 'aria-label="Edit theme description"' in html


# ---------------------------------------------------------------------------
# JS bootstrap
# ---------------------------------------------------------------------------

def test_init_inline_editing_called(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert "initInlineEditing" in html


# ---------------------------------------------------------------------------
# CSS loaded
# ---------------------------------------------------------------------------

def test_css_has_editable_text_rules(tmp_path: Path) -> None:
    _render_with_sections_and_themes(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".editable-text.editing" in css
    assert ".editable-text.edited" in css


def test_css_has_inline_pencil_rules(tmp_path: Path) -> None:
    _render_with_sections_and_themes(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".edit-pencil-inline" in css


# ---------------------------------------------------------------------------
# ToC entries — editable for sections and themes, not for sentiment/friction
# ---------------------------------------------------------------------------

def test_toc_section_entry_is_editable(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    # The ToC section entry should have an editable span with the same key.
    assert (
        '<a href="#section-homepage">'
        '<span class="editable-text" data-edit-key="section-homepage:title"'
        in html
    )


def test_toc_theme_entry_is_editable(tmp_path: Path) -> None:
    html = _render_with_sections_and_themes(tmp_path)
    assert (
        '<a href="#theme-brand-perception">'
        '<span class="editable-text" data-edit-key="theme-brand-perception:title"'
        in html
    )


def test_toc_sentiment_not_editable(tmp_path: Path) -> None:
    """Analysis chart headings should NOT have editable data-edit-key attributes.

    The Analysis column was removed from the TOC (navigation branch).
    This test verifies the sentiment heading never gets edit keys.
    """
    html = _render_with_sections_and_themes(tmp_path)
    # Sentiment heading should never have edit keys
    assert 'data-edit-key="sentiment:title"' not in html


def test_toc_section_entry_has_pencil(tmp_path: Path) -> None:
    """Each editable ToC entry should have an inline pencil button."""
    html = _render_with_sections_and_themes(tmp_path)
    # Count pencil buttons — there should be at least 2 in the ToC
    # (one for section, one for theme) beyond the heading pencils.
    import re
    toc_match = re.search(r'<div class="toc-row">(.+?)</div>\s*<hr>', html, re.DOTALL)
    assert toc_match
    toc_html = toc_match.group(1)
    assert 'edit-pencil-inline' in toc_html
