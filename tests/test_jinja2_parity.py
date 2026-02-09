"""Tests for Jinja2 template parity with the _w() renderer.

Phase 0: Infrastructure — verify structural assertions that any Jinja2
replacement must also satisfy.  Phase 1+: each migrated section gets a
parity test here.
"""

from __future__ import annotations

from pathlib import Path

from bristlenose.models import (
    ExtractedQuote,
    QuoteType,
    ScreenCluster,
    Sentiment,
    ThemeGroup,
)
from bristlenose.stages.render_html import render_html

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_quote(
    pid: str = "p1",
    start: float = 10.0,
    sentiment: Sentiment | None = Sentiment.FRUSTRATION,
) -> ExtractedQuote:
    return ExtractedQuote(
        participant_id=pid,
        start_timecode=start,
        end_timecode=start + 10.0,
        text="Test quote about product quality",
        topic_label="Topic",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        sentiment=sentiment,
    )


def _render_full_report(tmp_path: Path) -> str:
    """Render a report with sections and themes, return HTML."""
    render_html(
        screen_clusters=[
            ScreenCluster(
                screen_label="Homepage",
                description="Landing page with navigation",
                display_order=1,
                quotes=[_make_quote(), _make_quote("p2", 30.0)],
            ),
        ],
        theme_groups=[
            ThemeGroup(
                theme_label="Trust signals",
                description="Users respond to trust cues",
                quotes=[
                    _make_quote("p3", 50.0, sentiment=Sentiment.CONFIDENCE),
                ],
            ),
        ],
        sessions=[],
        project_name="Parity Test",
        output_dir=tmp_path,
    )
    return (tmp_path / "bristlenose-parity-test-report.html").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Phase 0: structural assertions the Jinja2 renderer must also satisfy
# ---------------------------------------------------------------------------


def test_render_produces_valid_html(tmp_path: Path) -> None:
    """Complete HTML document with doctype and closing tag."""
    html = _render_full_report(tmp_path)
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_document_head(tmp_path: Path) -> None:
    """Head contains required meta tags and title."""
    html = _render_full_report(tmp_path)
    assert '<meta name="color-scheme"' in html
    assert "<title>" in html
    assert 'rel="stylesheet"' in html


def test_report_header(tmp_path: Path) -> None:
    html = _render_full_report(tmp_path)
    assert 'class="report-header"' in html


def test_toolbar(tmp_path: Path) -> None:
    html = _render_full_report(tmp_path)
    assert 'class="toolbar"' in html


def test_sections(tmp_path: Path) -> None:
    """Screen clusters render as sections with anchored headings."""
    html = _render_full_report(tmp_path)
    assert 'id="section-homepage"' in html
    assert "Homepage" in html


def test_themes(tmp_path: Path) -> None:
    """Theme groups render with anchored headings."""
    html = _render_full_report(tmp_path)
    assert 'id="theme-trust-signals"' in html
    assert "Trust signals" in html


def test_quotes_present(tmp_path: Path) -> None:
    """Quotes render as blockquote elements with metadata."""
    html = _render_full_report(tmp_path)
    assert "<blockquote" in html
    assert "Test quote about product quality" in html


def test_footer(tmp_path: Path) -> None:
    html = _render_full_report(tmp_path)
    assert 'class="report-footer"' in html


def test_javascript_bootstrap(tmp_path: Path) -> None:
    """Embedded JS IIFE wraps all modules."""
    html = _render_full_report(tmp_path)
    assert "<script>" in html
    assert "})();" in html


def test_codebook_page_generated(tmp_path: Path) -> None:
    """Codebook page is generated alongside the report."""
    _render_full_report(tmp_path)
    codebook = tmp_path / "codebook.html"
    assert codebook.exists()
    html = codebook.read_text(encoding="utf-8")
    assert "Codebook" in html


def test_css_written(tmp_path: Path) -> None:
    """Theme CSS is written to assets directory."""
    _render_full_report(tmp_path)
    css = tmp_path / "assets" / "bristlenose-theme.css"
    assert css.exists()
    assert "--bn-" in css.read_text(encoding="utf-8")


def test_jinja2_importable() -> None:
    """Jinja2 is available as a dependency."""
    import jinja2

    assert jinja2.__version__
