"""Tests for hidden quotes feature in the HTML report."""

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
from bristlenose.stages.render_html import (
    _JS_FILES,
    _THEME_FILES,
    _TRANSCRIPT_JS_FILES,
    render_html,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_quote(pid: str = "p1", start: float = 10.0) -> ExtractedQuote:
    return ExtractedQuote(
        participant_id=pid,
        start_timecode=start,
        end_timecode=start + 10.0,
        text="Test quote about product quality",
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
                quotes=[_make_quote(), _make_quote("p2", 30.0)],
            ),
        ],
        theme_groups=[
            ThemeGroup(
                theme_label="Trust",
                description="Trust perceptions",
                quotes=[_make_quote("p3", 50.0)],
            ),
        ],
        sessions=[],
        project_name="Hidden Test",
        output_dir=tmp_path,
    )
    return (tmp_path / "bristlenose-hidden-test-report.html").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# File registration
# ---------------------------------------------------------------------------


def test_hidden_js_in_js_files() -> None:
    """hidden.js must be in the report JS file list."""
    assert "js/hidden.js" in _JS_FILES


def test_hidden_js_position() -> None:
    """hidden.js must load after tag-filter.js and before names.js."""
    idx_hidden = _JS_FILES.index("js/hidden.js")
    idx_tag_filter = _JS_FILES.index("js/tag-filter.js")
    idx_names = _JS_FILES.index("js/names.js")
    assert idx_tag_filter < idx_hidden < idx_names


def test_hidden_js_not_in_transcript() -> None:
    """hidden.js must not be in the transcript JS list."""
    assert "js/hidden.js" not in _TRANSCRIPT_JS_FILES


def test_hidden_css_in_theme_files() -> None:
    """hidden-quotes.css must be in the theme CSS list."""
    assert "molecules/hidden-quotes.css" in _THEME_FILES


# ---------------------------------------------------------------------------
# HTML structure — hide button on quotes
# ---------------------------------------------------------------------------


def test_hide_button_rendered(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'class="hide-btn"' in html


def test_hide_button_has_aria_label(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert 'aria-label="Hide this quote"' in html


def test_hide_button_has_svg(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert '<svg width="14" height="14"' in html


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


def test_css_has_bn_hidden_class(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert "blockquote.bn-hidden" in css


def test_css_has_hide_btn(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".hide-btn" in css


def test_css_has_badge_toggle(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".bn-hidden-toggle" in css


def test_css_has_dropdown(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".bn-hidden-dropdown" in css


def test_css_has_preview(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert ".bn-hidden-preview" in css


# ---------------------------------------------------------------------------
# Print CSS
# ---------------------------------------------------------------------------


def test_print_hides_hide_btn(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    # Check print section hides the button.
    print_idx = css.index("@media print")
    print_block = css[print_idx:]
    assert ".hide-btn" in print_block


def test_print_hides_badge(tmp_path: Path) -> None:
    _render_report(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    print_idx = css.index("@media print")
    print_block = css[print_idx:]
    assert ".bn-hidden-badge" in print_block


# ---------------------------------------------------------------------------
# JS bootstrap
# ---------------------------------------------------------------------------


def test_init_hidden_called(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "initHidden" in html


def test_hidden_js_in_report(tmp_path: Path) -> None:
    html = _render_report(tmp_path)
    assert "hidden.js" in html


# ---------------------------------------------------------------------------
# Help overlay
# ---------------------------------------------------------------------------


def test_help_overlay_has_h_shortcut() -> None:
    """The h shortcut must appear in the help overlay."""
    js_path = Path(__file__).parent.parent / "bristlenose" / "theme" / "js" / "focus.js"
    js = js_path.read_text(encoding="utf-8")
    assert "<kbd>h</kbd>" in js
    assert "Hide quote" in js


# ---------------------------------------------------------------------------
# Visibility guards in other modules
# ---------------------------------------------------------------------------


def test_view_switcher_guards_bn_hidden() -> None:
    """view-switcher.js must check for bn-hidden in show functions."""
    js_path = (
        Path(__file__).parent.parent
        / "bristlenose"
        / "theme"
        / "js"
        / "view-switcher.js"
    )
    js = js_path.read_text(encoding="utf-8")
    assert "bn-hidden" in js


def test_search_guards_bn_hidden() -> None:
    """search.js must check for bn-hidden in filter and restore."""
    js_path = (
        Path(__file__).parent.parent / "bristlenose" / "theme" / "js" / "search.js"
    )
    js = js_path.read_text(encoding="utf-8")
    assert "bn-hidden" in js


def test_tag_filter_guards_bn_hidden() -> None:
    """tag-filter.js must check for bn-hidden in apply and restore."""
    js_path = (
        Path(__file__).parent.parent
        / "bristlenose"
        / "theme"
        / "js"
        / "tag-filter.js"
    )
    js = js_path.read_text(encoding="utf-8")
    assert "bn-hidden" in js


def test_csv_export_guards_bn_hidden() -> None:
    """csv-export.js must check for bn-hidden in buildCsv."""
    js_path = (
        Path(__file__).parent.parent
        / "bristlenose"
        / "theme"
        / "js"
        / "csv-export.js"
    )
    js = js_path.read_text(encoding="utf-8")
    assert "bn-hidden" in js


def test_starred_guards_bn_hidden() -> None:
    """starred.js must exclude bn-hidden quotes from reorder."""
    js_path = (
        Path(__file__).parent.parent / "bristlenose" / "theme" / "js" / "starred.js"
    )
    js = js_path.read_text(encoding="utf-8")
    assert "bn-hidden" in js
