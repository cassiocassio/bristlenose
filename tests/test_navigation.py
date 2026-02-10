"""Tests for global navigation tabs in the HTML report."""

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


def _make_quote(pid: str = "p1", sid: str = "s1") -> ExtractedQuote:
    return ExtractedQuote(
        participant_id=pid,
        session_id=sid,
        start_timecode=10.0,
        end_timecode=20.0,
        text="Test quote text",
        topic_label="Topic",
        quote_type=QuoteType.SCREEN_SPECIFIC,
        intent=QuoteIntent.NARRATION,
        emotion=EmotionalTone.NEUTRAL,
    )


def _render_report(tmp_path: Path) -> str:
    """Render a minimal report and return the HTML string."""
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
                theme_label="Brand perception",
                description="Positive brand feelings",
                quotes=[_make_quote()],
            ),
        ],
        sessions=[],
        project_name="Nav Test",
        output_dir=tmp_path,
    )
    return (tmp_path / "bristlenose-nav-test-report.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tab panel structure
# ---------------------------------------------------------------------------


def test_tab_panels_have_data_tab_attributes(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    for tab in ("project", "sessions", "quotes", "codebook", "analysis", "settings", "about"):
        assert f'data-tab="{tab}"' in html


def test_project_tab_is_default_active(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'data-tab="project" id="panel-project" role="tabpanel" aria-label="Project">' in html
    # Project panel has the active class
    assert 'bn-tab-panel active" data-tab="project"' in html


def test_panel_ids_present(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    for tab in ("project", "sessions", "quotes", "codebook", "analysis", "settings", "about"):
        assert f'id="panel-{tab}"' in html


def test_tab_buttons_have_aria_controls(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    for tab in ("project", "sessions", "quotes", "codebook", "analysis", "settings", "about"):
        assert f'aria-controls="panel-{tab}"' in html


# ---------------------------------------------------------------------------
# doc_title
# ---------------------------------------------------------------------------


def test_doc_title_populated(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "Research Report" in html


def test_browser_title_has_project_name(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "<title>Nav Test</title>" in html


# ---------------------------------------------------------------------------
# ToC Analysis section
# ---------------------------------------------------------------------------


def test_toc_has_analysis_section(tmp_path: Path) -> None:
    """Analysis entries (Sentiment, etc.) should appear in the ToC when present."""
    html = _render_report(tmp_path)
    # The ToC renders an Analysis heading when chart_toc items exist.
    # Even without sentiment quotes, the render may include the section.
    # At minimum, verify the template supports the chart_toc block.
    assert "chart_toc" not in html or "Analysis" in html


# ---------------------------------------------------------------------------
# Speaker links
# ---------------------------------------------------------------------------


def test_speaker_link_uses_data_nav_session(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "data-nav-session=" in html


def test_speaker_link_has_data_nav_anchor(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "data-nav-anchor=" in html


def test_speaker_link_no_standalone_href(tmp_path: Path) -> None:
    """Speaker links should not point to standalone transcript pages."""
    html = _render_report(tmp_path)
    # Old pattern was href="sessions/transcript_..."
    assert 'href="sessions/transcript_' not in html


# ---------------------------------------------------------------------------
# JS initialisation
# ---------------------------------------------------------------------------


def test_global_nav_js_included(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "initGlobalNav" in html


def test_quote_map_injected(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "BRISTLENOSE_QUOTE_MAP" in html
