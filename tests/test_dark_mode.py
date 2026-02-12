"""Tests for dark mode support: CSS tokens, HTML attributes, and logo switching."""

from __future__ import annotations

from pathlib import Path

from bristlenose.config import BristlenoseSettings
from bristlenose.stages.render_html import render_html

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_minimal(tmp_path: Path, color_scheme: str = "auto") -> str:
    """Render a minimal report and return the HTML as a string."""
    project_name = "Dark Mode Test"
    render_html(
        screen_clusters=[],
        theme_groups=[],
        sessions=[],
        project_name=project_name,
        output_dir=tmp_path,
        color_scheme=color_scheme,
    )
    # New layout: bristlenose-{slug}-report.html
    return (tmp_path / "bristlenose-dark-mode-test-report.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_color_scheme_default() -> None:
    settings = BristlenoseSettings()
    assert settings.color_scheme == "auto"


def test_config_color_scheme_override() -> None:
    settings = BristlenoseSettings(color_scheme="dark")
    assert settings.color_scheme == "dark"


# ---------------------------------------------------------------------------
# HTML meta tag
# ---------------------------------------------------------------------------

def test_html_has_color_scheme_meta(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path)
    assert '<meta name="color-scheme" content="light dark">' in html


# ---------------------------------------------------------------------------
# data-theme attribute
# ---------------------------------------------------------------------------

def test_html_auto_no_data_theme(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path, color_scheme="auto")
    assert '<html lang="en">' in html
    assert "data-theme" not in html


def test_html_light_data_theme(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path, color_scheme="light")
    assert '<html lang="en" data-theme="light">' in html


def test_html_dark_data_theme(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path, color_scheme="dark")
    assert '<html lang="en" data-theme="dark">' in html


def test_html_unknown_scheme_falls_back_to_auto(tmp_path: Path) -> None:
    """Unrecognised values should behave like 'auto' (no data-theme)."""
    html = _render_minimal(tmp_path, color_scheme="sepia")
    assert '<html lang="en">' in html
    assert "data-theme" not in html


# ---------------------------------------------------------------------------
# CSS: light-dark() tokens
# ---------------------------------------------------------------------------

def test_css_has_color_scheme_property(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert "color-scheme: light dark;" in css


def test_css_has_light_dark_tokens(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert "light-dark(#ffffff, #111111)" in css  # --bn-colour-bg
    assert "light-dark(#1a1a1a, #e5e7eb)" in css  # --bn-colour-text


def test_css_has_supports_block(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert "@supports (color: light-dark(#000, #fff))" in css


def test_css_has_data_theme_overrides(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    assert '[data-theme="light"]:root' in css
    assert '[data-theme="dark"]:root' in css


def test_css_light_fallback_preserved(tmp_path: Path) -> None:
    """The plain :root block with light-only values must remain as fallback."""
    _render_minimal(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    # The original :root block should contain the plain value (no light-dark)
    # Find content before the @supports block
    supports_idx = css.index("@supports")
    before_supports = css[:supports_idx]
    assert "--bn-colour-bg: #ffffff;" in before_supports


def test_css_print_forces_light(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    css = (tmp_path / "assets" / "bristlenose-theme.css").read_text(encoding="utf-8")
    # Inside @media print, color-scheme should be forced to light
    assert "color-scheme: light;" in css


# ---------------------------------------------------------------------------
# Logo: <picture> element with dark variant
# ---------------------------------------------------------------------------

def test_logo_dark_file_copied(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    assert (tmp_path / "assets" / "bristlenose-logo-dark.png").exists()


def test_logo_picture_element(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path)
    assert "<picture>" in html
    assert 'media="(prefers-color-scheme: dark)"' in html
    # New layout: assets/bristlenose-logo-dark.png
    assert 'srcset="assets/bristlenose-logo-dark.png"' in html


def test_logo_light_still_default(tmp_path: Path) -> None:
    """The <img> fallback inside <picture> should still be the light logo."""
    html = _render_minimal(tmp_path)
    # New layout: assets/bristlenose-logo.png
    assert 'src="assets/bristlenose-logo.png"' in html


# ---------------------------------------------------------------------------
# Histogram JS: no hard-coded colours
# ---------------------------------------------------------------------------

def test_histogram_js_no_hardcoded_colours(tmp_path: Path) -> None:
    _render_minimal(tmp_path)
    html = _render_minimal(tmp_path)
    # The JS is embedded in the HTML in a <script> block
    assert "#9ca3af" not in html, "histogram bar still has hard-coded #9ca3af"
    assert "var(--bn-colour-muted)" in html


# ---------------------------------------------------------------------------
# Settings panel: appearance radio buttons
# ---------------------------------------------------------------------------

def test_settings_panel_has_appearance_radios(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path)
    assert 'name="bn-appearance"' in html
    assert 'value="auto"' in html
    assert 'value="light"' in html
    assert 'value="dark"' in html


def test_settings_panel_auto_is_default(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path)
    assert 'value="auto" checked' in html


def test_settings_panel_has_legend(tmp_path: Path) -> None:
    html = _render_minimal(tmp_path)
    assert "<legend>Application appearance</legend>" in html


def test_settings_js_avoids_data_theme_literal(tmp_path: Path) -> None:
    """settings.js must use split-string pattern so auto-mode test still passes."""
    html = _render_minimal(tmp_path, color_scheme="auto")
    assert "data-theme" not in html
