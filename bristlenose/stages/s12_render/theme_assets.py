"""Theme asset loading — CSS, JS, and Jinja2 template environment.

Consolidates all theme file lists, lazy-loaded caches, and the shared
Jinja2 environment that were previously at module level in the old render_html.py monolith.
"""

from __future__ import annotations

from pathlib import Path

import jinja2

# ---------------------------------------------------------------------------
# Paths — relative to this file's location (stages/render/)
# ---------------------------------------------------------------------------

_THEME_DIR = Path(__file__).resolve().parent.parent.parent / "theme"
_LOGO_PATH = _THEME_DIR / "images" / "bristlenose.png"
_LOGO_DARK_PATH = _THEME_DIR / "images" / "bristlenose-dark.png"
_LOGO_FILENAME = "bristlenose-logo.png"
_LOGO_DARK_FILENAME = "bristlenose-logo-dark.png"

# ---------------------------------------------------------------------------
# Default theme CSS — loaded from bristlenose/theme/ (atomic design system)
# ---------------------------------------------------------------------------

_CSS_VERSION = "bristlenose-theme v6"

# Files concatenated in atomic-design order.
_THEME_FILES: list[str] = [
    "tokens.css",
    "atoms/badge.css",
    "atoms/button.css",
    "atoms/toggle.css",
    "atoms/input.css",
    "atoms/toast.css",
    "atoms/timecode.css",
    "atoms/bar.css",
    "atoms/logo.css",
    "atoms/footer.css",
    "atoms/interactive.css",
    "atoms/checkbox.css",
    "atoms/span-bar.css",
    "atoms/modal.css",
    "atoms/tooltip.css",
    "atoms/thumbnail.css",
    "atoms/activity-chip.css",
    "atoms/journey-label.css",
    "atoms/moderator-question.css",
    "atoms/context-expansion.css",
    "molecules/person-badge.css",
    "molecules/badge-row.css",
    "molecules/bar-group.css",
    "molecules/editable-text.css",
    "molecules/quote-actions.css",
    "molecules/tag-input.css",
    "molecules/sparkline.css",
    "molecules/name-edit.css",
    "molecules/search.css",
    "molecules/tag-filter.css",
    "molecules/hidden-quotes.css",
    "molecules/help-overlay.css",
    "molecules/feedback.css",
    "molecules/autocode-report.css",
    "molecules/threshold-review.css",
    "organisms/blockquote.css",
    "organisms/responsive-grid.css",
    "organisms/coverage.css",
    "organisms/sentiment-chart.css",
    "organisms/toolbar.css",
    "organisms/toc.css",
    "organisms/global-nav.css",
    "organisms/codebook-panel.css",
    "organisms/sidebar.css",
    "organisms/minimap.css",
    "organisms/sidebar-tags.css",
    "organisms/analysis.css",
    "organisms/settings.css",
    "organisms/modal-nav.css",
    "organisms/settings-modal.css",
    "templates/report.css",
    "molecules/transcript-annotations.css",
    "templates/transcript.css",
    "templates/print.css",
    "templates/export.css",
]


def _load_default_css() -> str:
    """Read and concatenate all theme CSS files into a single stylesheet."""
    header = (
        f"/* {_CSS_VERSION} — default research report theme */\n"
        "/* Auto-generated from bristlenose/theme/ — "
        "edits will be overwritten on the next run. */\n\n"
    )
    parts: list[str] = [header]
    for name in _THEME_FILES:
        path = _THEME_DIR / name
        parts.append(f"/* --- {name} --- */\n")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("\n\n")
    return "".join(parts)


# Lazy-loaded cache so the file I/O only happens once per process.
_default_css_cache: str | None = None


def _get_default_css() -> str:
    global _default_css_cache  # noqa: PLW0603
    if _default_css_cache is None:
        _default_css_cache = _load_default_css()
    return _default_css_cache


# ---------------------------------------------------------------------------
# Report JavaScript — loaded from bristlenose/theme/js/
# ---------------------------------------------------------------------------

# Files concatenated in dependency order (later files may reference
# globals defined by earlier ones).
_JS_FILES: list[str] = [
    "js/storage.js",
    "js/api-client.js",
    "js/badge-utils.js",
    "js/modal.js",
    "js/codebook.js",
    "js/player.js",
    "js/starred.js",
    "js/editing.js",
    "js/tags.js",
    "js/histogram.js",
    "js/csv-export.js",
    "js/view-switcher.js",
    "js/search.js",
    "js/tag-filter.js",
    "js/hidden.js",
    "js/names.js",
    "js/focus.js",
    "js/feedback.js",
    "js/global-nav.js",
    "js/transcript-names.js",
    "js/transcript-annotations.js",
    "js/journey-sort.js",
    "js/analysis.js",
    "js/settings.js",
    "js/person-display.js",
    "js/main.js",
]


def _load_report_js() -> str:
    """Read and concatenate all report JS modules into a single script."""
    parts: list[str] = [
        "/* bristlenose report.js — auto-generated from bristlenose/theme/js/ */\n\n"
    ]
    for name in _JS_FILES:
        path = _THEME_DIR / name
        parts.append(f"// --- {name} ---\n")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("\n\n")
    return "".join(parts)


# Lazy-loaded cache so the file I/O only happens once per process.
_report_js_cache: str | None = None


def _get_report_js() -> str:
    global _report_js_cache  # noqa: PLW0603
    if _report_js_cache is None:
        _report_js_cache = _load_report_js()
    return _report_js_cache


# ---------------------------------------------------------------------------
# Jinja2 template environment
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = _THEME_DIR / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,  # We manage escaping via _esc(); switch later
    keep_trailing_newline=True,
)


# ---------------------------------------------------------------------------
# Transcript page JavaScript
# ---------------------------------------------------------------------------

_TRANSCRIPT_JS_FILES: list[str] = [
    "js/storage.js",
    "js/badge-utils.js",
    "js/player.js",
    "js/transcript-names.js",
    "js/transcript-annotations.js",
    "js/settings.js",
]


def _load_transcript_js() -> str:
    """Read and concatenate only the JS modules needed for transcript pages."""
    parts: list[str] = []
    for name in _TRANSCRIPT_JS_FILES:
        path = _THEME_DIR / name
        parts.append(f"// --- {name} ---\n")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("\n\n")
    return "".join(parts)


_transcript_js_cache: str | None = None


def _get_transcript_js() -> str:
    global _transcript_js_cache  # noqa: PLW0603
    if _transcript_js_cache is None:
        _transcript_js_cache = _load_transcript_js()
    return _transcript_js_cache


# ---------------------------------------------------------------------------
# Codebook page JavaScript
# ---------------------------------------------------------------------------

_CODEBOOK_JS_FILES: list[str] = [
    "js/storage.js",
    "js/badge-utils.js",
    "js/modal.js",
    "js/codebook.js",
]


def _load_codebook_js() -> str:
    """Read and concatenate only the JS modules needed for the codebook page."""
    parts: list[str] = []
    for name in _CODEBOOK_JS_FILES:
        path = _THEME_DIR / name
        parts.append(f"// --- {name} ---\n")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("\n\n")
    return "".join(parts)


_codebook_js_cache: str | None = None


def _get_codebook_js() -> str:
    global _codebook_js_cache  # noqa: PLW0603
    if _codebook_js_cache is None:
        _codebook_js_cache = _load_codebook_js()
    return _codebook_js_cache


# ---------------------------------------------------------------------------
# Analysis page JavaScript
# ---------------------------------------------------------------------------

_ANALYSIS_JS_FILES: list[str] = [
    "js/storage.js",
    "js/badge-utils.js",
    "js/analysis.js",
]


def _load_analysis_js() -> str:
    """Read and concatenate only the JS modules needed for the analysis page."""
    parts: list[str] = []
    for name in _ANALYSIS_JS_FILES:
        path = _THEME_DIR / name
        parts.append(f"// --- {name} ---\n")
        parts.append(path.read_text(encoding="utf-8").strip())
        parts.append("\n\n")
    return "".join(parts)


_analysis_js_cache: str | None = None


def _get_analysis_js() -> str:
    global _analysis_js_cache  # noqa: PLW0603
    if _analysis_js_cache is None:
        _analysis_js_cache = _load_analysis_js()
    return _analysis_js_cache
