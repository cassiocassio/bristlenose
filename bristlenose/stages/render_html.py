"""Stage 12b: Render the research report as styled HTML with external CSS."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

import jinja2

from bristlenose.coverage import CoverageStats, calculate_coverage
from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    FileType,
    FullTranscript,
    InputSession,
    PeopleFile,
    QuoteIntent,
    ScreenCluster,
    Sentiment,
    ThemeGroup,
    format_timecode,
)
from bristlenose.utils.markdown import format_finder_date, format_finder_filename
from bristlenose.utils.timecodes import format_duration_human

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default theme CSS — loaded from bristlenose/theme/ (atomic design system)
# ---------------------------------------------------------------------------

_CSS_VERSION = "bristlenose-theme v6"

# Feature flag: show thumbnail placeholders for all sessions (even VTT-only).
# Set BRISTLENOSE_FAKE_THUMBNAILS=1 to enable — useful for layout testing.
_FAKE_THUMBNAILS = os.environ.get("BRISTLENOSE_FAKE_THUMBNAILS", "") == "1"

_THEME_DIR = Path(__file__).resolve().parent.parent / "theme"
_LOGO_PATH = _THEME_DIR / "images" / "bristlenose.png"
_LOGO_DARK_PATH = _THEME_DIR / "images" / "bristlenose-dark.png"
_LOGO_FILENAME = "bristlenose-logo.png"
_LOGO_DARK_FILENAME = "bristlenose-logo-dark.png"

# Files concatenated in atomic-design order.
_THEME_FILES: list[str] = [
    "tokens.css",
    "atoms/badge.css",
    "atoms/button.css",
    "atoms/input.css",
    "atoms/toast.css",
    "atoms/timecode.css",
    "atoms/bar.css",
    "atoms/logo.css",
    "atoms/footer.css",
    "atoms/interactive.css",
    "atoms/span-bar.css",
    "atoms/modal.css",
    "molecules/person-id.css",
    "molecules/badge-row.css",
    "molecules/bar-group.css",
    "molecules/quote-actions.css",
    "molecules/tag-input.css",
    "molecules/name-edit.css",
    "molecules/search.css",
    "molecules/tag-filter.css",
    "molecules/hidden-quotes.css",
    "molecules/help-overlay.css",
    "molecules/feedback.css",
    "organisms/blockquote.css",
    "organisms/coverage.css",
    "organisms/sentiment-chart.css",
    "organisms/toolbar.css",
    "organisms/toc.css",
    "organisms/global-nav.css",
    "organisms/codebook-panel.css",
    "organisms/analysis.css",
    "organisms/settings.css",
    "templates/report.css",
    "molecules/transcript-annotations.css",
    "templates/transcript.css",
    "templates/print.css",
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
# Public API
# ---------------------------------------------------------------------------


def render_html(
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    all_quotes: list[ExtractedQuote] | None = None,
    color_scheme: str = "auto",
    display_names: dict[str, str] | None = None,
    people: PeopleFile | None = None,
    transcripts: list[FullTranscript] | None = None,
    analysis: object | None = None,
    serve_mode: bool = False,
) -> Path:
    """Generate the HTML research report with external CSS stylesheet.

    Args:
        serve_mode: When True, render React island mount points instead of
            Jinja2 session tables. The Sessions tab gets
            ``<div id="bn-sessions-table-root" data-project-id="1">``
            and the React SessionsTable component takes over rendering.
            The static export path (serve_mode=False) stays unchanged.

    Output layout (v2):
        output/
        ├── bristlenose-{slug}-report.html   # Main report
        ├── assets/                           # Static assets
        │   ├── bristlenose-theme.css
        │   ├── bristlenose-logo.png
        │   ├── bristlenose-logo-dark.png
        │   └── bristlenose-player.html
        └── sessions/                         # Transcript pages
            └── transcript_{session_id}.html

    Returns:
        Path to the written HTML file.
    """
    from bristlenose.output_paths import OutputPaths

    paths = OutputPaths(output_dir, project_name)

    # Create directories
    output_dir.mkdir(parents=True, exist_ok=True)
    paths.assets_dir.mkdir(parents=True, exist_ok=True)
    paths.sessions_dir.mkdir(parents=True, exist_ok=True)

    # Always write CSS — keeps the stylesheet in sync with the renderer
    paths.css_file.write_text(_get_default_css(), encoding="utf-8")
    logger.info("Wrote theme: %s", paths.css_file)

    # Copy logo images to assets/
    if _LOGO_PATH.exists():
        shutil.copy2(_LOGO_PATH, paths.logo_file)
    if _LOGO_DARK_PATH.exists():
        shutil.copy2(_LOGO_DARK_PATH, paths.logo_dark_file)

    # Build video/audio map for clickable timecodes
    video_map = _build_video_map(sessions)
    has_media = bool(video_map)

    # Write popout player page when media files exist
    if has_media:
        _write_player_html(paths.assets_dir, paths.player_file)

    html_path = paths.html_report

    parts: list[str] = []
    _w = parts.append

    # --- Document shell ---
    _w(_document_shell_open(
        title=_esc(project_name),
        css_href="assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    # --- Header ---
    now = datetime.now()
    if people and people.participants:
        n_participants = sum(1 for k in people.participants if k.startswith("p"))
    else:
        n_participants = len(sessions)
    n_sessions = len(sessions)
    meta_date = format_finder_date(now, now=now)

    meta_right = (
        f'<span class="header-meta">'
        f"{n_sessions}\u00a0session{'s' if n_sessions != 1 else ''}, "
        f"{n_participants}\u00a0participant{'s' if n_participants != 1 else ''}, "
        f"{_esc(meta_date)}"
        f"</span>"
    )
    _w(_report_header_html(
        assets_prefix="assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Research Report",
        meta_right=meta_right,
    ))

    # --- Global Navigation ---
    _w(_jinja_env.get_template("global_nav.html").render())

    # --- Project tab ---
    _w('<div class="bn-tab-panel active" data-tab="project" id="panel-project" role="tabpanel" aria-label="Project">')
    _w(_render_project_tab(
        project_name=project_name,
        sessions=sessions,
        screen_clusters=screen_clusters,
        theme_groups=theme_groups,
        all_quotes=all_quotes,
        people=people,
        display_names=display_names,
        video_map=video_map,
        transcripts=transcripts,
        now=now,
    ))
    _w("</div>")

    # --- Sessions tab ---
    _w('<div class="bn-tab-panel" data-tab="sessions" id="panel-sessions" role="tabpanel" aria-label="Sessions">')
    _w('<div class="bn-session-subnav" style="display:none">')
    _w('<button class="bn-session-back">&larr; All sessions</button>')
    _w('<span class="bn-session-label"></span>')
    _w("</div>")
    _w('<div class="bn-session-grid">')

    # --- Session Summary (at top for quick reference) ---
    if serve_mode:
        # React island mount point — SessionsTable component will render here
        _w('<div id="bn-sessions-table-root" data-project-id="1"></div>')
    elif sessions:
        session_rows, moderator_header, observer_header = _build_session_rows(
            sessions, people, display_names, video_map, now,
            screen_clusters=screen_clusters,
            all_quotes=all_quotes,
        )
        _w(_jinja_env.get_template("session_table.html").render(
            rows=session_rows,
            moderator_header=moderator_header,
            observer_header=observer_header,
        ).rstrip("\n"))

    # Close session grid
    _w("</div>")  # .bn-session-grid

    # Inline transcripts (rendered as hidden divs, shown via JS drill-down)
    inline_transcripts = _render_inline_transcripts(
        sessions=sessions,
        project_name=project_name,
        output_dir=output_dir,
        video_map=video_map,
        people=people,
        display_names=display_names,
        transcripts=transcripts,
        all_quotes=all_quotes,
        screen_clusters=screen_clusters,
        theme_groups=theme_groups,
    )
    for t_html in inline_transcripts:
        _w(t_html)

    _w("</div>")  # .bn-tab-panel[sessions]

    # --- Quotes tab ---
    _w('<div class="bn-tab-panel" data-tab="quotes" id="panel-quotes" role="tabpanel" aria-label="Quotes">')

    # --- Toolbar ---
    _w(_jinja_env.get_template("toolbar.html").render())

    # --- Table of Contents ---
    section_toc: list[tuple[str, str]] = []
    theme_toc: list[tuple[str, str]] = []
    chart_toc: list[tuple[str, str]] = []
    if screen_clusters:
        for cluster in screen_clusters:
            anchor = f"section-{cluster.screen_label.lower().replace(' ', '-')}"
            section_toc.append((anchor, cluster.screen_label))
    if theme_groups:
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            theme_toc.append((anchor, theme.theme_label))
    if all_quotes:
        chart_toc.append(("sentiment", "Sentiment"))
        chart_toc.append(("user-tags-chart", "Tags"))
    if screen_clusters:
        chart_toc.append(("user-journeys", "User journeys"))
    if transcripts and all_quotes:
        chart_toc.append(("transcript-coverage", "Transcript coverage"))
    if section_toc or theme_toc or chart_toc:
        # Pre-escape TOC entries for template
        esc_section_toc = [(_esc(a), _esc(lbl)) for a, lbl in section_toc]
        esc_theme_toc = [(_esc(a), _esc(lbl)) for a, lbl in theme_toc]
        esc_chart_toc = [(_esc(a), _esc(lbl)) for a, lbl in chart_toc]
        _w(_jinja_env.get_template("toc.html").render(
            section_toc=esc_section_toc,
            theme_toc=esc_theme_toc,
            chart_toc=esc_chart_toc,
        ).rstrip("\n"))

    # --- Sections (screen-specific findings) ---
    _content_tmpl = _jinja_env.get_template("content_section.html")
    if screen_clusters:
        groups = []
        for cluster in screen_clusters:
            anchor = f"section-{cluster.screen_label.lower().replace(' ', '-')}"
            quotes_html = "\n".join(
                _format_quote_html(q, video_map) for q in cluster.quotes
            )
            groups.append({
                "anchor": _esc(anchor), "label": _esc(cluster.screen_label),
                "description": _esc(cluster.description) if cluster.description else "",
                "quotes_html": quotes_html,
            })
        _w(_content_tmpl.render(
            heading="Sections", item_type="section", groups=groups,
        ).rstrip("\n"))

    # --- Themes ---
    if theme_groups:
        groups = []
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            quotes_html = "\n".join(
                _format_quote_html(q, video_map) for q in theme.quotes
            )
            groups.append({
                "anchor": _esc(anchor), "label": _esc(theme.theme_label),
                "description": _esc(theme.description) if theme.description else "",
                "quotes_html": quotes_html,
            })
        _w(_content_tmpl.render(
            heading="Themes", item_type="theme", groups=groups,
        ).rstrip("\n"))

    # --- Sentiment (includes friction points) ---
    if all_quotes:
        sentiment_html = _build_sentiment_html(all_quotes)
        rewatch = _build_rewatch_html(all_quotes, video_map)
        if sentiment_html or rewatch:
            _w("<section>")
            _w('<h2 id="sentiment">Sentiment</h2>')
            _w(
                '<p class="description">Joy, frustration, surprise or doubt '
                "detected.</p>"
            )
            if sentiment_html:
                _w(sentiment_html)
            if rewatch:
                _w(rewatch)
            _w("</section>")
            _w("<hr>")

    # --- User Journeys ---
    if screen_clusters:
        task_html = _build_task_outcome_html(
            screen_clusters, all_quotes or [], display_names,
        )
        if task_html:
            _w("<section>")
            _w('<h2 id="user-journeys">User journeys</h2>')
            _w(
                '<p class="description">Each participant\u2019s path through the product '
                "&mdash; which report sections contain their quotes, in logical order.</p>"
            )
            _w(task_html)
            _w("</section>")
            _w("<hr>")

    # --- Coverage ---
    if transcripts and all_quotes:
        coverage = calculate_coverage(transcripts, all_quotes)
        coverage_html = _build_coverage_html(coverage)
        _w(coverage_html)

    _w("</div>")  # .bn-tab-panel[quotes]

    # --- Codebook tab ---
    _w('<div class="bn-tab-panel" data-tab="codebook" id="panel-codebook" role="tabpanel" aria-label="Codebook">')
    _w('<h1>Codebook</h1>')
    _w('<p class="codebook-description">Drag tags between groups to '
       "reorganise. Click a tag to rename it. Changes are saved automatically "
       "and sync across all open windows.</p>")
    _w('<div class="codebook-grid" id="codebook-grid"></div>')
    _w("</div>")  # .bn-tab-panel[codebook]

    # --- Analysis tab ---
    _w('<div class="bn-tab-panel" data-tab="analysis" id="panel-analysis" role="tabpanel" aria-label="Analysis">')
    if analysis is not None:
        _w(_jinja_env.get_template("analysis.html").render())
    else:
        _w("<h2>Analysis</h2>")
        _w('<p class="description">No analysis data available.'
           " Run the full pipeline to generate analysis.</p>")
    _w("</div>")  # .bn-tab-panel[analysis]

    # --- Settings tab ---
    _w('<div class="bn-tab-panel" data-tab="settings" id="panel-settings"'
       ' role="tabpanel" aria-label="Settings">')
    _w("<h2>Settings</h2>")
    _w('<fieldset class="bn-setting-group">')
    _w("<legend>Application appearance</legend>")
    _w('<label class="bn-radio-label">'
       '<input type="radio" name="bn-appearance" value="auto" checked> '
       "Use system appearance</label>")
    _w('<label class="bn-radio-label">'
       '<input type="radio" name="bn-appearance" value="light"> '
       "Light</label>")
    _w('<label class="bn-radio-label">'
       '<input type="radio" name="bn-appearance" value="dark"> '
       "Dark</label>")
    _w("</fieldset>")
    _w("</div>")  # .bn-tab-panel[settings]

    # --- About tab ---
    from bristlenose import __version__ as _ver
    _w('<div class="bn-tab-panel" data-tab="about" id="panel-about" role="tabpanel" aria-label="About">')
    _w('<div class="bn-about">')
    _w("<h2>About Bristlenose</h2>")
    _w(f'<p>Version {_esc(_ver)} &middot; '
       '<a href="https://github.com/cassiocassio/bristlenose" '
       'target="_blank" rel="noopener">GitHub</a></p>')
    _w('<h3>Keyboard Shortcuts</h3>')
    _w('<div class="help-columns">')
    _w('  <div class="help-section">')
    _w('    <h3>Navigation</h3>')
    _w("    <dl>")
    _w("      <dt><kbd>j</kbd> / <kbd>&darr;</kbd></dt><dd>Next quote</dd>")
    _w("      <dt><kbd>k</kbd> / <kbd>&uarr;</kbd></dt><dd>Previous quote</dd>")
    _w("    </dl>")
    _w("  </div>")
    _w('  <div class="help-section">')
    _w('    <h3>Selection</h3>')
    _w("    <dl>")
    _w("      <dt><kbd>x</kbd></dt><dd>Toggle select</dd>")
    _w("      <dt><kbd>Shift</kbd>+<kbd>j</kbd>/<kbd>k</kbd></dt><dd>Extend</dd>")
    _w("    </dl>")
    _w("  </div>")
    _w('  <div class="help-section">')
    _w('    <h3>Actions</h3>')
    _w("    <dl>")
    _w("      <dt><kbd>s</kbd></dt><dd>Star quote(s)</dd>")
    _w("      <dt><kbd>h</kbd></dt><dd>Hide quote(s)</dd>")
    _w("      <dt><kbd>t</kbd></dt><dd>Add tag(s)</dd>")
    _w("      <dt><kbd>Enter</kbd></dt><dd>Play in video</dd>")
    _w("    </dl>")
    _w("  </div>")
    _w('  <div class="help-section">')
    _w('    <h3>Global</h3>')
    _w("    <dl>")
    _w("      <dt><kbd>/</kbd></dt><dd>Search</dd>")
    _w("      <dt><kbd>?</kbd></dt><dd>This help</dd>")
    _w("      <dt><kbd>Esc</kbd></dt><dd>Close / clear</dd>")
    _w("    </dl>")
    _w("  </div>")
    _w("</div>")
    _w("<hr>")
    _w("<h3>Feedback</h3>")
    _w('<p><a href="https://github.com/cassiocassio/bristlenose/issues/new" '
       'target="_blank" rel="noopener">Report a bug</a></p>')
    _w("<!-- /bn-about -->")
    _w("</div>")  # .bn-about
    _w("</div>")  # .bn-tab-panel[about]

    # --- Close ---
    _w("</article>")
    _w(_footer_html())

    # --- Embed JavaScript ---
    _w("<script>")
    _w("(function() {")
    if has_media:
        _w(f"var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};")
    else:
        _w("var BRISTLENOSE_VIDEO_MAP = {};")

    # Participant data for JS name editing and reconciliation.
    participant_data: dict[str, dict[str, str]] = {}
    if people:
        for _pid, _entry in people.participants.items():
            participant_data[_pid] = {
                "full_name": _entry.editable.full_name,
                "short_name": _entry.editable.short_name,
                "role": _entry.editable.role,
            }
    _w(f"var BN_PARTICIPANTS = {json.dumps(participant_data)};")

    # Feedback feature flag — set to true to enable the feedback widget.
    _w("var BRISTLENOSE_FEEDBACK = true;")
    _w("var BRISTLENOSE_FEEDBACK_URL = 'https://cassiocassio.co.uk/feedback.php';")

    # Quote annotation data for inline transcript pages (transcript-annotations.js).
    # Build a combined quote map for all sessions.
    _all_quote_map = _build_transcript_quote_map(
        all_quotes, screen_clusters, theme_groups
    )
    _combined_qmap: dict[str, dict[str, object]] = {}
    for _sid_key, _anns in _all_quote_map.items():
        for _ann in _anns:
            _combined_qmap[_ann.quote_id] = {
                "label": _ann.label,
                "type": _ann.label_type,
                "sentiment": _ann.sentiment,
                "pid": _ann.participant_id,
            }
    _w(f"var BRISTLENOSE_QUOTE_MAP = {json.dumps(_combined_qmap)};")
    _w("var BRISTLENOSE_REPORT_URL = '';")

    # Analysis data for inline rendering in the Analysis tab.
    if analysis is not None:
        _w(f"var BRISTLENOSE_ANALYSIS = {_serialize_analysis(analysis)};")
        _w(f"var BRISTLENOSE_REPORT_FILENAME = '{paths.html_report.name}';")

    # Player popup URL.
    _w("var BRISTLENOSE_PLAYER_URL = 'assets/bristlenose-player.html';")

    _w(_get_report_js())
    _w("})();")
    _w("</script>")

    # React islands mount point — empty and invisible when no React bundle is loaded.
    # When bristlenose serve is running, the React app mounts components here.
    _w('<div id="bn-react-root"></div>')

    _w("</body>")
    _w("</html>")

    html_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Wrote HTML report: %s", html_path)

    # --- Generate per-participant transcript pages ---
    render_transcript_pages(
        sessions=sessions,
        project_name=project_name,
        output_dir=output_dir,
        video_map=video_map,
        color_scheme=color_scheme,
        display_names=display_names,
        people=people,
        transcripts=transcripts,
        all_quotes=all_quotes,
        screen_clusters=screen_clusters,
        theme_groups=theme_groups,
    )

    # --- Generate codebook page ---
    _render_codebook_page(
        project_name=project_name,
        output_dir=output_dir,
        color_scheme=color_scheme,
    )

    # --- Generate analysis page ---
    if analysis is not None:
        _render_analysis_page(
            project_name=project_name,
            output_dir=output_dir,
            analysis=analysis,
            color_scheme=color_scheme,
        )

    return html_path


# ---------------------------------------------------------------------------
# Transcript pages
# ---------------------------------------------------------------------------

_TRANSCRIPT_JS_FILES: list[str] = [
    "js/storage.js",
    "js/badge-utils.js",
    "js/player.js",
    "js/transcript-names.js",
    "js/transcript-annotations.js",
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


def _resolve_speaker_name(
    pid: str,
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
) -> str:
    """Resolve speaker name for transcript segments.

    Priority: short_name → full_name → pid.
    """
    if people and pid in people.participants:
        entry = people.participants[pid]
        if entry.editable.short_name:
            return entry.editable.short_name
        if entry.editable.full_name:
            return entry.editable.full_name
    return pid


class _QuoteAnnotation:
    """Annotation data for a single quote mapped to transcript segments."""

    __slots__ = (
        "quote_id", "participant_id", "start_tc", "end_tc",
        "verbatim_excerpt", "label", "label_type", "sentiment",
    )

    def __init__(
        self,
        quote_id: str,
        participant_id: str,
        start_tc: float,
        end_tc: float,
        verbatim_excerpt: str,
        label: str,
        label_type: str,
        sentiment: str,
    ) -> None:
        self.quote_id = quote_id
        self.participant_id = participant_id
        self.start_tc = start_tc
        self.end_tc = end_tc
        self.verbatim_excerpt = verbatim_excerpt
        self.label = label
        self.label_type = label_type
        self.sentiment = sentiment


# ---------------------------------------------------------------------------
# Project tab (dashboard)
# ---------------------------------------------------------------------------


# Sparkline bar order: positive → neutral → negative (left to right).
_SPARKLINE_ORDER = [
    "satisfaction", "delight", "confidence",
    "surprise",
    "doubt", "confusion", "frustration",
]
_SPARKLINE_MAX_H = 20  # px
_SPARKLINE_MIN_H = 2   # px — non-zero counts are always visible
_SPARKLINE_BAR_W = 5   # px
_SPARKLINE_GAP = 2     # px
_SPARKLINE_RADIUS = 1  # px (top corners only)
_SPARKLINE_OPACITY = 0.8


def _render_sentiment_sparkline(counts: dict[str, int]) -> str:
    """Return HTML for a tiny sentiment bar chart, or &mdash; if empty."""
    max_val = max((counts.get(s, 0) for s in _SPARKLINE_ORDER), default=0)
    if max_val == 0:
        return "&mdash;"
    bars: list[str] = []
    for s in _SPARKLINE_ORDER:
        c = counts.get(s, 0)
        if c > 0:
            h = max(round(c / max_val * _SPARKLINE_MAX_H), _SPARKLINE_MIN_H)
        else:
            h = 0
        bars.append(
            f'<span class="bn-sparkline-bar" style="'
            f"height:{h}px;"
            f"background:var(--bn-sentiment-{s});"
            f'opacity:{_SPARKLINE_OPACITY}">'
            f"</span>"
        )
    return (
        f'<div class="bn-sparkline" style="'
        f"gap:{_SPARKLINE_GAP}px"
        f'">'
        + "".join(bars)
        + "</div>"
    )


def _build_session_rows(
    sessions: list[InputSession],
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
    video_map: dict[str, str] | None,
    now: datetime,
    screen_clusters: list[ScreenCluster] | None = None,
    all_quotes: list[ExtractedQuote] | None = None,
) -> tuple[list[dict[str, object]], str, str]:
    """Build session-table row dicts, moderator header HTML, and observer header HTML.

    Returns (rows, moderator_header_html, observer_header_html).
    """
    # Build session_id → sorted speaker codes from people entries.
    session_codes: dict[str, list[str]] = {}
    all_moderator_codes: list[str] = []
    all_observer_codes: list[str] = []
    if people and people.participants:
        for code, entry in people.participants.items():
            sid_key = entry.computed.session_id
            if sid_key:
                session_codes.setdefault(sid_key, []).append(code)
            if code.startswith("m") and code not in all_moderator_codes:
                all_moderator_codes.append(code)
            elif code.startswith("o") and code not in all_observer_codes:
                all_observer_codes.append(code)
        prefix_order = {"m": 0, "p": 1, "o": 2}
        for codes in session_codes.values():
            codes.sort(key=lambda c: (
                prefix_order.get(c[0], 3) if c else 3,
                int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0,
            ))
    # Sort moderator and observer codes naturally.
    all_moderator_codes.sort(key=lambda c: (
        int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0,
    ))
    all_observer_codes.sort(key=lambda c: (
        int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0,
    ))

    # If only 1 moderator, omit from per-row speaker lists (shown in header).
    omit_moderators_from_rows = len(all_moderator_codes) == 1

    # Build moderator header HTML.
    moderator_parts: list[str] = []
    for code in all_moderator_codes:
        name = _resolve_speaker_name(code, people, display_names)
        name_html = f" {_esc(name)}" if name != code else ""
        moderator_parts.append(
            f'<span class="bn-person-id">'
            f'<span class="badge">{_esc(code)}</span>{name_html}'
            f'</span>'
        )
    if moderator_parts:
        moderator_header = "Moderated by " + _oxford_list_html(moderator_parts)
    else:
        moderator_header = ""

    # Build observer header HTML (only if observers present).
    observer_parts: list[str] = []
    for code in all_observer_codes:
        name = _resolve_speaker_name(code, people, display_names)
        name_html = f" {_esc(name)}" if name != code else ""
        observer_parts.append(
            f'<span class="bn-person-id">'
            f'<span class="badge">{_esc(code)}</span>{name_html}'
            f'</span>'
        )
    if observer_parts:
        noun = "Observer" if len(observer_parts) == 1 else "Observers"
        observer_header = f"{noun}: " + _oxford_list_html(observer_parts)
    else:
        observer_header = ""

    # Derive journey data from screen clusters.
    participant_screens: dict[str, list[str]] = {}
    if screen_clusters and all_quotes:
        participant_screens_raw, _ = _derive_journeys(
            screen_clusters, all_quotes,
        )
        participant_screens = participant_screens_raw

    # Aggregate sentiment counts by session_id for sparklines.
    sentiment_by_session: dict[str, dict[str, int]] = {}
    for q in all_quotes or []:
        if q.sentiment is not None:
            sid_key = q.session_id
            if sid_key not in sentiment_by_session:
                sentiment_by_session[sid_key] = {}
            val = q.sentiment.value
            sentiment_by_session[sid_key][val] = (
                sentiment_by_session[sid_key].get(val, 0) + 1
            )

    # Compute source folder URI (from first session's first file).
    source_folder_uri = ""
    for session in sessions:
        if session.files:
            source_folder_uri = session.files[0].path.resolve().parent.as_uri()
            break

    rows: list[dict[str, object]] = []
    for session in sessions:
        duration = _session_duration(session, people)
        sid = session.session_id
        sid_esc = _esc(sid)
        session_num = sid[1:] if len(sid) > 1 and sid[1:].isdigit() else sid
        start = _esc(format_finder_date(session.session_date, now=now))

        # Source file link.
        has_media = bool(_FAKE_THUMBNAILS and session.files)
        if session.files:
            full_name = session.files[0].path.name
            display_fname = format_finder_filename(full_name)
            title_attr = f' title="{_esc(full_name)}"' if display_fname != full_name else ""
            esc_display = _esc(display_fname)
            if video_map and sid in video_map:
                has_media = True
                source = (
                    f'<a href="#" class="timecode" '
                    f'data-participant="{_esc(session.participant_id)}" '
                    f'data-seconds="0" data-end-seconds="0"'
                    f'{title_attr}>'
                    f'{esc_display}</a>'
                )
            else:
                file_uri = session.files[0].path.resolve().as_uri()
                source = f'<a href="{file_uri}"{title_attr}>{esc_display}</a>'
        else:
            source = "&mdash;"

        # Speaker list (structured for template iteration).
        codes = session_codes.get(sid, [session.participant_id])
        speakers_list: list[dict[str, str]] = []
        for code in codes:
            if omit_moderators_from_rows and code.startswith("m"):
                continue
            name = _resolve_speaker_name(code, people, display_names)
            display = _esc(name) if name != code else ""
            speakers_list.append({"code": _esc(code), "name": display})

        # Journey: merge all participants' screen labels for this session.
        session_pids = [c for c in codes if c.startswith("p")]
        journey_labels: list[str] = []
        for pid in session_pids:
            for label in participant_screens.get(pid, []):
                if label not in journey_labels:
                    journey_labels.append(label)
        journey = " &rarr; ".join(journey_labels) if journey_labels else ""

        sparkline = _render_sentiment_sparkline(sentiment_by_session.get(sid, {}))

        rows.append({
            "sid": sid_esc,
            "num": _esc(session_num),
            "speakers_list": speakers_list,
            "start": start,
            "duration": duration,
            "source": source,
            "journey": journey,
            "sentiment_sparkline": sparkline,
            "has_media": has_media,
            "source_folder_uri": source_folder_uri,
        })
    return rows, moderator_header, observer_header


def _oxford_list_html(parts: list[str]) -> str:
    """Join HTML fragments with Oxford commas (no escaping — parts are pre-escaped)."""
    if len(parts) <= 1:
        return parts[0] if parts else ""
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


# Sentiment polarity buckets for diversity mixing.
_POSITIVE_SENTIMENTS = frozenset({
    Sentiment.SATISFACTION, Sentiment.DELIGHT, Sentiment.CONFIDENCE,
})
_NEGATIVE_SENTIMENTS = frozenset({
    Sentiment.FRUSTRATION, Sentiment.CONFUSION, Sentiment.DOUBT,
})


def _pick_featured_quotes(
    all_quotes: list[ExtractedQuote],
    n: int = 3,
) -> list[ExtractedQuote]:
    """Select the N most interesting quotes for the dashboard.

    Word-count filtering
    ────────────────────
    Quotes between 12–33 words are preferred (concise, readable in a card).
    When fewer than *n* match the preferred range, the pool is padded with
    longer (≥ 12-word) quotes so we always have enough candidates.  Falls
    back to all quotes only if nothing reaches 12 words.

    Scoring algorithm
    ─────────────────
    Each quote gets a numeric score based on available server-side data:

      • Intensity:  +3 strong (intensity=3), +2 moderate (2), +1 mild (1)
      • Sentiment:  +2 for friction sentiments (frustration, confusion, doubt)
                    +2 for delight or surprise
                    +1 for satisfaction or confidence
      • Context:    +1 if researcher_context is present (editorial enrichment)
      • Length:     penalty for quotes > 33 words (up to −2)

    After scoring, the top candidates are diversified:
      1. Must be from different participants (rotate through participants).
      2. Prefer a mix of sentiment polarities (positive / negative / surprise).
      3. If fewer than n qualify after filters, return whatever we have.

    Client-side JS will further adjust: boost starred quotes, swap out hidden
    ones for the next-best alternative.
    """
    if not all_quotes:
        return []

    # Filter: prefer quotes between 12–33 words (concise, readable in a card).
    # If fewer than n match the preferred range, pad with longer quotes so we
    # always have enough candidates to fill the requested slots.
    preferred = [q for q in all_quotes if 12 <= len(q.text.split()) <= 33]
    if len(preferred) >= n:
        candidates = preferred
    else:
        # Pad with ≥ 12-word quotes not already in the preferred set.
        longer = [q for q in all_quotes
                  if len(q.text.split()) >= 12 and q not in preferred]
        candidates = preferred + longer
    if not candidates:
        candidates = list(all_quotes)  # fall back to all if none qualify

    def _score(q: ExtractedQuote) -> float:
        s = 0.0
        # Intensity bonus.
        s += min(q.intensity, 3)
        # Sentiment bonus.
        if q.sentiment in _NEGATIVE_SENTIMENTS:
            s += 2
        elif q.sentiment == Sentiment.SURPRISE:
            s += 2
        elif q.sentiment == Sentiment.DELIGHT:
            s += 2
        elif q.sentiment in _POSITIVE_SENTIMENTS:
            s += 1
        # Researcher context.
        if q.researcher_context:
            s += 1
        # Length: sweet spot is 12–33 words; penalise longer quotes.
        word_count = len(q.text.split())
        if word_count > 33:
            s -= min((word_count - 33) / 10, 2.0)
        return s

    # Sort by score descending, then by timecode for stability.
    scored = sorted(
        candidates,
        key=lambda q: (-_score(q), q.start_timecode),
    )

    # Diversify: pick from different participants and sentiment polarities.
    picked: list[ExtractedQuote] = []
    used_pids: set[str] = set()
    used_polarities: set[str] = set()  # "positive", "negative", "surprise"

    def _polarity(q: ExtractedQuote) -> str:
        if q.sentiment in _POSITIVE_SENTIMENTS:
            return "positive"
        if q.sentiment in _NEGATIVE_SENTIMENTS:
            return "negative"
        if q.sentiment == Sentiment.SURPRISE:
            return "surprise"
        return "neutral"

    # Pass 1: pick one quote per participant, preferring different polarities.
    for q in scored:
        if len(picked) >= n:
            break
        pid = q.participant_id
        pol = _polarity(q)
        if pid not in used_pids and pol not in used_polarities:
            picked.append(q)
            used_pids.add(pid)
            used_polarities.add(pol)

    # Pass 2: relax polarity constraint — still require different participants.
    if len(picked) < n:
        for q in scored:
            if len(picked) >= n:
                break
            if q in picked:
                continue
            if q.participant_id not in used_pids:
                picked.append(q)
                used_pids.add(q.participant_id)

    # Pass 3: relax all constraints — just pick highest-scoring remaining.
    if len(picked) < n:
        for q in scored:
            if len(picked) >= n:
                break
            if q not in picked:
                picked.append(q)

    return picked[:n]


def _render_featured_quote(
    quote: ExtractedQuote,
    video_map: dict[str, str] | None,
    display_names: dict[str, str] | None,
    people: PeopleFile | None,
    rank: int,
) -> str:
    """Render a single featured quote card for the dashboard."""
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
    tc_html = _timecode_html(quote, video_map)

    # Speaker code lozenge → navigates to Sessions tab on card click.
    pid_esc, sid_esc, anchor = _session_anchor(quote)
    speaker_badge = (
        f'<a href="#" class="badge speaker-link" data-nav-session="{sid_esc}"'
        f' data-nav-anchor="{anchor}">{pid_esc}</a>'
    )

    # AI badge (sentiment only — lightweight).
    badge_html = ""
    if quote.sentiment is not None:
        css_class = f"badge badge-ai badge-{quote.sentiment.value}"
        badge_html = (
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.sentiment.value)}</span>"
        )

    # Context prefix.
    ctx = ""
    if quote.researcher_context:
        ctx = f'<span class="context">[{_esc(quote.researcher_context)}]</span>'

    hidden = ' style="display:none"' if rank >= 3 else ""
    return (
        f'<div class="bn-featured-quote" data-quote-id="{quote_id}"'
        f' data-rank="{rank}"{hidden}>'
        f"{ctx}"
        f'<span class="quote-text">\u201c{_esc(quote.text)}\u201d</span>'
        f'<div class="bn-featured-footer">'
        f"{tc_html}"
        f"{speaker_badge}"
        f"{badge_html}"
        f"</div>"
        f"</div>"
    )


def _render_project_tab(
    project_name: str,
    sessions: list[InputSession],
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    all_quotes: list[ExtractedQuote] | None,
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
    video_map: dict[str, str] | None,
    transcripts: list[FullTranscript] | None,
    now: datetime,
) -> str:
    """Render the Project tab as a dashboard with tessellated panes."""
    parts: list[str] = []
    _w = parts.append

    # --- Compute dashboard metrics ---
    n_quotes = len(all_quotes) if all_quotes else 0
    n_sections = len(screen_clusters)
    n_themes = len(theme_groups)

    # Total duration (seconds) across all sessions.
    total_duration_s = 0.0
    if people and people.participants:
        # Use max duration per session (avoids double-counting multi-speaker).
        _dur_by_session: dict[str, float] = {}
        for entry in people.participants.values():
            sid = entry.computed.session_id
            if sid and entry.computed.duration_seconds > 0:
                _dur_by_session[sid] = max(
                    _dur_by_session.get(sid, 0), entry.computed.duration_seconds,
                )
        total_duration_s = sum(_dur_by_session.values())
    if total_duration_s == 0:
        for s in sessions:
            for f in s.files:
                if f.duration_seconds is not None:
                    total_duration_s += f.duration_seconds

    # Total words across all participants.
    total_words = 0
    if people and people.participants:
        total_words = sum(
            e.computed.words_spoken for e in people.participants.values()
        )

    # AI-tagged quotes (quotes with a non-null sentiment).
    n_ai_tagged = 0
    if all_quotes:
        n_ai_tagged = sum(1 for q in all_quotes if q.sentiment is not None)

    # Pick up to 9 featured-quote candidates so JS can swap hidden/unstarred.
    featured_pool = _pick_featured_quotes(all_quotes or [], n=9)

    _w('<div class="bn-dashboard">')

    # --- 1. Stats row (full width) ---
    _w('<div class="bn-dashboard-full">')
    _w('<div class="bn-project-stats">')

    # Session count — first stat card.
    n_sessions = len(sessions)
    _w(f'<div class="bn-project-stat" data-stat-link="sessions">'
       f'<span class="bn-project-stat-value">{n_sessions}</span>'
       f'<span class="bn-project-stat-label">'
       f"session{'s' if n_sessions != 1 else ''}"
       f'</span></div>')

    # Determine input-type label: "of video", "of audio", "of transcripts",
    # or "of sessions" when the project mixes source types.
    _has_video = any(s.has_video for s in sessions)
    _has_audio = any(s.has_audio and not s.has_video for s in sessions)
    _has_transcript = any(
        not s.has_video and not s.has_audio for s in sessions
    )
    _kind_count = sum([_has_video, _has_audio, _has_transcript])
    if _kind_count > 1:
        _duration_label = "of sessions"
    elif _has_video:
        _duration_label = "of video"
    elif _has_audio:
        _duration_label = "of audio"
    else:
        _duration_label = "of transcripts"

    # Duration + words — combined borderless pair.
    if total_duration_s > 0 or total_words > 0:
        _w('<div class="bn-project-stat bn-project-stat--pair">')
        if total_duration_s > 0:
            _w(f'<div class="bn-project-stat--pair-half" data-stat-link="sessions">'
               f'<span class="bn-project-stat-value">'
               f'{format_duration_human(total_duration_s)}</span>'
               f'<span class="bn-project-stat-label">{_duration_label}</span></div>')
        if total_words > 0:
            _w(f'<div class="bn-project-stat--pair-half" data-stat-link="sessions">'
               f'<span class="bn-project-stat-value">'
               f'{total_words:,}</span>'
               f'<span class="bn-project-stat-label">words</span></div>')
        _w('</div>')

    # Quotes + themes — paired card.
    _w('<div class="bn-project-stat bn-project-stat--pair">')
    _w(f'<div class="bn-project-stat--pair-half" data-stat-link="quotes">'
       f'<span class="bn-project-stat-value">{n_quotes}</span>'
       f'<span class="bn-project-stat-label">'
       f"quote{'s' if n_quotes != 1 else ''}"
       f'</span></div>')
    if n_themes:
        _w(f'<div class="bn-project-stat--pair-half"'
           f' data-stat-link="quotes:themes">'
           f'<span class="bn-project-stat-value">{n_themes}</span>'
           f'<span class="bn-project-stat-label">'
           f"theme{'s' if n_themes != 1 else ''}"
           f'</span></div>')
    _w('</div>')
    # Sections — standalone card (only if present).
    if n_sections:
        _w(f'<div class="bn-project-stat" data-stat-link="quotes:sections">'
           f'<span class="bn-project-stat-value">{n_sections}</span>'
           f'<span class="bn-project-stat-label">'
           f"section{'s' if n_sections != 1 else ''}"
           f'</span></div>')

    # AI-tagged + user tags — paired card.
    _w('<div class="bn-project-stat bn-project-stat--pair">')
    if n_ai_tagged:
        _w(f'<div class="bn-project-stat--pair-half"'
           f' data-stat-link="analysis:section-x-sentiment">'
           f'<span class="bn-project-stat-value">{n_ai_tagged}</span>'
           f'<span class="bn-project-stat-label">AI tags</span></div>')
    # User tags — JS-populated from localStorage.
    _w('<div class="bn-project-stat--pair-half" id="dashboard-user-tags-stat"'
       ' data-stat-link="codebook" style="display:none">')
    _w('<span class="bn-project-stat-value" id="dashboard-user-tags-value"></span>')
    _w('<span class="bn-project-stat-label" id="dashboard-user-tags-label"></span>')
    _w("</div>")
    _w("</div>")

    _w("</div>")  # .bn-project-stats
    _w("</div>")  # .bn-dashboard-pane (stats)

    # --- 2. Sessions (full width) ---
    if sessions:
        session_rows, moderator_header, observer_header = _build_session_rows(
            sessions, people, display_names, video_map, now,
            screen_clusters=screen_clusters,
            all_quotes=all_quotes,
        )
        _w('<div class="bn-dashboard-pane bn-dashboard-full">')
        _w(_jinja_env.get_template("dashboard_session_table.html").render(
            rows=session_rows,
            moderator_header=moderator_header,
            observer_header=observer_header,
        ).rstrip("\n"))
        _w("</div>")

    # --- 3. Featured quotes (3 × 1/3 width) ---
    if featured_pool:
        _w('<div class="bn-featured-row bn-dashboard-full"'
           ' data-visible-count="3">')
        for rank, fq in enumerate(featured_pool):
            _w(_render_featured_quote(
                fq, video_map, display_names, people, rank,
            ))
        _w("</div>")

    # --- 4. Sections + Themes row (1/2 + 1/2) ---
    if screen_clusters:
        _w('<div class="bn-dashboard-pane">')
        _w('<nav class="bn-dashboard-nav">')
        _w("<h3>Sections</h3>")
        _w("<ul>")
        for cluster in screen_clusters:
            anchor = f"section-{cluster.screen_label.lower().replace(' ', '-')}"
            _w(f'<li><a href="#{_esc(anchor)}">'
               f'{_esc(cluster.screen_label)}</a></li>')
        _w("</ul></nav>")
        _w("</div>")

    if theme_groups:
        _w('<div class="bn-dashboard-pane">')
        _w('<nav class="bn-dashboard-nav">')
        _w("<h3>Themes</h3>")
        _w("<ul>")
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            _w(f'<li><a href="#{_esc(anchor)}">'
               f'{_esc(theme.theme_label)}</a></li>')
        _w("</ul></nav>")
        _w("</div>")

    _w("</div>")  # .bn-dashboard

    return "\n".join(parts)


# Keyed by session_id, contains list of annotations for that session.
_QuoteMap = dict[str, list["_QuoteAnnotation"]]


def _build_transcript_quote_map(
    all_quotes: list[ExtractedQuote] | None,
    screen_clusters: list[ScreenCluster] | None,
    theme_groups: list[ThemeGroup] | None,
) -> _QuoteMap:
    """Build a mapping of quotes to their section/theme assignments.

    Returns a dict keyed by session_id, each value a list of
    _QuoteAnnotation objects for quotes in that session.
    """
    if not all_quotes:
        return {}

    # Build quote_id → (label, label_type) lookup from clusters/themes
    assignment: dict[str, tuple[str, str]] = {}
    for cluster in screen_clusters or []:
        for q in cluster.quotes:
            qid = f"q-{q.participant_id}-{int(q.start_timecode)}"
            assignment[qid] = (cluster.screen_label, "section")
    for theme in theme_groups or []:
        for q in theme.quotes:
            qid = f"q-{q.participant_id}-{int(q.start_timecode)}"
            assignment[qid] = (theme.theme_label, "theme")

    result: _QuoteMap = {}
    for q in all_quotes:
        qid = f"q-{q.participant_id}-{int(q.start_timecode)}"
        label, label_type = assignment.get(qid, ("", ""))
        ann = _QuoteAnnotation(
            quote_id=qid,
            participant_id=q.participant_id,
            start_tc=q.start_timecode,
            end_tc=q.end_timecode,
            verbatim_excerpt=q.verbatim_excerpt,
            label=label,
            label_type=label_type,
            sentiment=q.sentiment.value if q.sentiment else "",
        )
        result.setdefault(q.session_id, []).append(ann)
    return result


def render_transcript_pages(
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None = None,
    color_scheme: str = "auto",
    display_names: dict[str, str] | None = None,
    people: PeopleFile | None = None,
    transcripts: list[FullTranscript] | None = None,
    all_quotes: list[ExtractedQuote] | None = None,
    screen_clusters: list[ScreenCluster] | None = None,
    theme_groups: list[ThemeGroup] | None = None,
) -> list[Path]:
    """Generate per-participant transcript HTML pages in sessions/.

    If ``transcripts`` is provided, uses those directly. Otherwise reads
    transcript segments from ``transcripts-cooked/`` (if present) or
    ``transcripts-raw/``.

    Returns the list of written file paths.
    """
    from bristlenose.output_paths import OutputPaths

    paths_helper = OutputPaths(output_dir, project_name)
    paths_helper.sessions_dir.mkdir(parents=True, exist_ok=True)

    # Use provided transcripts, or load from disk
    if transcripts is None:
        from bristlenose.pipeline import load_transcripts_from_dir

        # Prefer cooked (PII-redacted) transcripts, fall back to raw
        cooked_dir = paths_helper.transcripts_cooked_dir
        raw_dir = paths_helper.transcripts_raw_dir
        if cooked_dir.is_dir() and any(cooked_dir.glob("*.txt")):
            transcripts_dir = cooked_dir
        elif raw_dir.is_dir() and any(raw_dir.glob("*.txt")):
            transcripts_dir = raw_dir
        else:
            logger.info("No transcript files found — skipping transcript pages")
            return []

        transcripts = load_transcripts_from_dir(transcripts_dir)

    if not transcripts:
        return []

    # Build quote annotation data for transcript pages
    quote_map = _build_transcript_quote_map(
        all_quotes, screen_clusters, theme_groups
    )

    paths: list[Path] = []
    for transcript in transcripts:
        page_path = _render_transcript_page(
            transcript=transcript,
            project_name=project_name,
            output_dir=output_dir,
            video_map=video_map,
            color_scheme=color_scheme,
            people=people,
            quote_map=quote_map,
        )
        paths.append(page_path)
        logger.info("Wrote transcript page: %s", page_path)

    return paths


def _render_transcript_page(
    transcript: object,  # FullTranscript or PiiCleanTranscript (avoid circular import)
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None = None,
    color_scheme: str = "auto",
    people: PeopleFile | None = None,
    quote_map: _QuoteMap | None = None,
) -> Path:
    """Render a single participant transcript as an HTML page in sessions/."""
    from bristlenose.models import FullTranscript
    from bristlenose.output_paths import OutputPaths
    from bristlenose.utils.text import slugify

    assert isinstance(transcript, FullTranscript)
    pid = transcript.participant_id
    sid = transcript.session_id

    # Set up paths (session pages are in sessions/ subdirectory)
    paths = OutputPaths(output_dir, project_name)
    slug = slugify(project_name)

    # Collect all speaker codes present in the transcript (stable insertion order)
    seen_codes: dict[str, None] = {}
    for seg in transcript.segments:
        code = seg.speaker_code or pid
        if code not in seen_codes:
            seen_codes[code] = None
    speaker_codes = list(seen_codes)

    # Sort: m-codes first, then p-codes, then o-codes
    def _code_sort_key(c: str) -> tuple[int, int]:
        prefix_order = {"m": 0, "p": 1, "o": 2}
        order = prefix_order.get(c[0], 3) if c else 3
        num = int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        return (order, num)

    speaker_codes.sort(key=_code_sort_key)

    # Build heading: "Session 1: m1, p1, p2" or with names
    # Extract session number — "s1" → "1", legacy "p1" → "1"
    session_num = sid[1:] if len(sid) > 1 and sid[0] in "sp" and sid[1:].isdigit() else sid

    # Plain-text labels for <title>: "m1 Sarah Chen, p5 Maya, o1"
    code_labels: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        if name != code:
            code_labels.append(f"{code} {name}")
        else:
            code_labels.append(code)

    # HTML spans for <h1> — each code gets its own data-participant span
    code_spans: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        if name != code:
            label = f"{_esc(code)} {_esc(name)}"
        else:
            label = _esc(code)
        code_spans.append(
            f'<span class="heading-speaker" data-participant="{_esc(code)}">'
            f"{label}</span>"
        )

    # Build HTML
    parts: list[str] = []
    _w = parts.append

    title = f"Session {_esc(session_num)}: {', '.join(_esc(lb) for lb in code_labels)}"
    _w(_document_shell_open(
        title=f"{title} \u2014 {_esc(project_name)}",
        css_href="../assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    # Header (same layout as report) — logos at ../assets/
    meta_parts: list[str] = []
    if transcript.source_file:
        meta_parts.append(_esc(transcript.source_file))
    if transcript.duration_seconds > 0:
        meta_parts.append(format_timecode(transcript.duration_seconds))
    t_meta_right = (
        f'<span class="header-meta">'
        f"{' &middot; '.join(meta_parts)}"
        f"</span>"
    ) if meta_parts else None
    _w(_report_header_html(
        assets_prefix="../assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Session transcript",
        meta_right=t_meta_right,
    ))

    # Back link + participant heading — report is at ../bristlenose-{slug}-report.html
    _w('<nav class="transcript-back">')
    report_filename = f"bristlenose-{slug}-report.html"
    _w(
        f'<a href="../{report_filename}">'
        f"&larr; {_esc(project_name)} Research Report</a>"
    )
    _w("</nav>")
    heading_html = f"Session {_esc(session_num)}: {', '.join(code_spans)}"
    _w(f"<h1>{heading_html}</h1>")

    # Transcript segments
    _w('<section class="transcript-body">')
    has_media = video_map is not None and sid in (video_map or {})

    # Build quote coverage lookup for this session
    session_annotations = (quote_map or {}).get(sid, [])

    for seg in transcript.segments:
        tc = format_timecode(seg.start_time)
        anchor = f"t-{int(seg.start_time)}"
        code = seg.speaker_code or pid
        is_moderator = code.startswith("m")

        # Check if this segment is covered by any quote (timecode range overlap)
        seg_quotes = [
            a for a in session_annotations
            if a.start_tc <= seg.start_time <= a.end_tc
            and a.participant_id == code
        ]
        is_quoted = bool(seg_quotes) and not is_moderator

        # Build CSS classes
        classes = ["transcript-segment"]
        if is_moderator:
            classes.append("segment-moderator")
        if is_quoted:
            classes.append("segment-quoted")
        cls_str = " ".join(classes)

        # Data attributes for glow sync (player.js) and annotation JS
        data_attrs = (
            f' data-participant="{_esc(code)}"'
            f' data-start-seconds="{seg.start_time}"'
            f' data-end-seconds="{seg.end_time}"'
        )
        if is_quoted:
            qids = " ".join(a.quote_id for a in seg_quotes)
            data_attrs += f' data-quote-ids="{_esc(qids)}"'

        _w(f'<div class="{cls_str}" id="{anchor}"{data_attrs}>')
        if has_media:
            _w(
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(pid)}" '
                f'data-seconds="{seg.start_time}">{_tc_brackets(tc)}</a>'
            )
        else:
            _w(f'<span class="timecode">{_tc_brackets(tc)}</span>')
        _w('<div class="segment-body">')
        _w(
            f'<span class="segment-speaker" data-participant="{_esc(code)}">'
            f"{_esc(code)}:</span>"
        )

        # Render segment text with inline quote highlights
        seg_text = seg.text
        if is_quoted:
            seg_text = _highlight_quoted_text(seg_text, seg_quotes)
            _w(f" {seg_text}")  # already HTML-escaped inside _highlight_quoted_text
        else:
            _w(f" {_esc(seg_text)}")

        _w("</div></div>")
    _w("</section>")

    _w("</article>")
    _w(_footer_html(assets_prefix="../assets"))

    # JavaScript (player + name propagation + annotations)
    _w("<script>")
    _w("(function() {")
    _w("var BRISTLENOSE_PLAYER_URL = '../assets/bristlenose-player.html';")
    if has_media:
        _w(f"var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};")
    else:
        _w("var BRISTLENOSE_VIDEO_MAP = {};")

    # Quote annotation data for margin rendering (Phase 2/3)
    report_filename = f"bristlenose-{slug}-report.html"
    _w(f"var BRISTLENOSE_REPORT_URL = '../{report_filename}';")
    if session_annotations:
        qmap: dict[str, dict[str, object]] = {}
        for ann in session_annotations:
            qmap[ann.quote_id] = {
                "label": ann.label,
                "type": ann.label_type,
                "sentiment": ann.sentiment,
                "pid": ann.participant_id,
            }
        _w(f"var BRISTLENOSE_QUOTE_MAP = {json.dumps(qmap)};")
    else:
        _w("var BRISTLENOSE_QUOTE_MAP = {};")

    _w(_get_transcript_js())
    _w("initPlayer();")
    _w("initTranscriptNames();")
    if session_annotations:
        _w("initTranscriptAnnotations();")
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    # Write to sessions/ subdirectory
    page_path = paths.transcript_page(transcript.session_id)
    page_path.write_text("\n".join(parts), encoding="utf-8")
    return page_path


# ---------------------------------------------------------------------------
# Codebook page
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


def _render_codebook_page(
    project_name: str,
    output_dir: Path,
    color_scheme: str = "auto",
) -> Path:
    """Render the codebook page as a standalone HTML file.

    The codebook page sits at the output root (same level as the report),
    opened in a new window via the toolbar Codebook button.
    """
    from bristlenose.output_paths import OutputPaths
    from bristlenose.utils.text import slugify

    paths = OutputPaths(output_dir, project_name)
    slug = slugify(project_name)

    parts: list[str] = []
    _w = parts.append

    _w(_document_shell_open(
        title=f"Codebook \u2014 {_esc(project_name)}",
        css_href="assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    # Header (same layout as report — logos at assets/)
    _w(_report_header_html(
        assets_prefix="assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Codebook",
    ))

    # Back link to report
    report_filename = f"bristlenose-{slug}-report.html"
    _w('<nav class="transcript-back">')
    _w(f'<a href="{report_filename}">')
    _w(f"&larr; {_esc(project_name)} Research Report</a>")
    _w("</nav>")

    _w("<h1>Codebook</h1>")

    # Description and interactive grid container (populated by codebook.js)
    _w('<p class="codebook-description">')
    _w("Drag tags between groups to reclassify. ")
    _w("Drag onto another tag to merge. Sorted by frequency.")
    _w("</p>")
    _w('<div class="codebook-grid" id="codebook-grid"></div>')

    _w("</article>")
    _w(_footer_html())

    # JavaScript — codebook data model + modal + storage for cross-window sync
    _w("<script>")
    _w("(function() {")
    _w(_get_codebook_js())
    _w("initCodebook();")
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    page_path = paths.codebook_file
    page_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Wrote codebook page: %s", page_path)
    return page_path


# ---------------------------------------------------------------------------
# Analysis page
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


def _serialize_matrix(matrix: object) -> dict:
    """Convert a Matrix dataclass to a JSON-friendly dict."""
    cells_dict: dict[str, dict] = {}
    for key, cell in matrix.cells.items():  # type: ignore[attr-defined]
        cells_dict[key] = {
            "count": cell.count,
            "participants": cell.participants,
            "intensities": cell.intensities,
        }
    return {
        "cells": cells_dict,
        "rowTotals": matrix.row_totals,  # type: ignore[attr-defined]
        "colTotals": matrix.col_totals,  # type: ignore[attr-defined]
        "grandTotal": matrix.grand_total,  # type: ignore[attr-defined]
        "rowLabels": matrix.row_labels,  # type: ignore[attr-defined]
    }


def _serialize_analysis(analysis: object) -> str:
    """Serialize AnalysisResult for JS injection."""
    # Collect all participant IDs across all signals
    all_pids: set[str] = set()
    for s in analysis.signals:  # type: ignore[attr-defined]
        all_pids.update(s.participants)
    # Sort participant IDs naturally (p1, p2, ..., p10)
    sorted_pids = sorted(all_pids, key=lambda p: (p[0], int(p[1:]) if p[1:].isdigit() else 0))

    data = {
        "signals": [
            {
                "location": s.location,
                "sourceType": s.source_type,
                "sentiment": s.sentiment,
                "count": s.count,
                "participants": s.participants,
                "nEff": round(s.n_eff, 2),
                "meanIntensity": round(s.mean_intensity, 2),
                "concentration": round(s.concentration, 2),
                "compositeSignal": round(s.composite_signal, 4),
                "confidence": s.confidence,
                "quotes": [
                    {
                        "text": q.text,
                        "pid": q.participant_id,
                        "sessionId": q.session_id,
                        "startSeconds": q.start_seconds,
                        "intensity": q.intensity,
                    }
                    for q in s.quotes
                ],
            }
            for s in analysis.signals  # type: ignore[attr-defined]
        ],
        "sectionMatrix": _serialize_matrix(analysis.section_matrix),  # type: ignore[attr-defined]
        "themeMatrix": _serialize_matrix(analysis.theme_matrix),  # type: ignore[attr-defined]
        "totalParticipants": analysis.total_participants,  # type: ignore[attr-defined]
        "sentiments": analysis.sentiments,  # type: ignore[attr-defined]
        "participantIds": sorted_pids,
    }
    return json.dumps(data, separators=(",", ":"))


def _render_analysis_page(
    project_name: str,
    output_dir: Path,
    analysis: object,
    color_scheme: str = "auto",
) -> Path:
    """Render the analysis page as a standalone HTML file.

    The analysis page sits at the output root (same level as the report),
    opened in a new window via the toolbar Analysis button.
    """
    from bristlenose.output_paths import OutputPaths
    from bristlenose.utils.text import slugify

    paths = OutputPaths(output_dir, project_name)
    slug = slugify(project_name)

    parts: list[str] = []
    _w = parts.append

    _w(_document_shell_open(
        title=f"Analysis \u2014 {_esc(project_name)}",
        css_href="assets/bristlenose-theme.css",
        color_scheme=color_scheme,
    ))

    _w(_report_header_html(
        assets_prefix="assets",
        has_logo=paths.logo_file.exists(),
        has_dark_logo=paths.logo_dark_file.exists(),
        project_name=_esc(project_name),
        doc_title="Analysis",
    ))

    # Back link to report
    report_filename = f"bristlenose-{slug}-report.html"
    _w('<nav class="transcript-back">')
    _w(f'<a href="{report_filename}">')
    _w(f"&larr; {_esc(project_name)} Research Report</a>")
    _w("</nav>")

    # Template body
    _w(_jinja_env.get_template("analysis.html").render())

    _w("</article>")
    _w(_footer_html())

    # JavaScript with injected data
    _w("<script>")
    _w("(function() {")
    _w(f"var BRISTLENOSE_ANALYSIS = {_serialize_analysis(analysis)};")
    report_fn_js = report_filename.replace("'", "\\'")
    _w(f"var BRISTLENOSE_REPORT_FILENAME = '{report_fn_js}';")
    _w(_get_analysis_js())
    _w("initAnalysis();")
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    page_path = paths.analysis_file
    page_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Wrote analysis page: %s", page_path)
    return page_path


# ---------------------------------------------------------------------------
# Transcript highlighting
# ---------------------------------------------------------------------------


def _highlight_quoted_text(
    segment_text: str,
    annotations: list[_QuoteAnnotation],
) -> str:
    """Wrap quoted portions of segment text in <mark> tags.

    Uses verbatim_excerpt from each annotation to find the exact substring
    in the raw segment text.  Falls back to highlighting the entire segment
    if no verbatim_excerpt is available or the substring isn't found.

    Returns HTML-safe string (all text is escaped, <mark> tags are injected).
    """
    if not annotations:
        return _esc(segment_text)

    # Collect all (start, end, quote_id) ranges to highlight
    ranges: list[tuple[int, int, str]] = []
    has_any_match = False

    for ann in annotations:
        excerpt = ann.verbatim_excerpt
        if not excerpt:
            continue
        # Simple case-insensitive substring search
        idx = segment_text.lower().find(excerpt.lower())
        if idx >= 0:
            ranges.append((idx, idx + len(excerpt), ann.quote_id))
            has_any_match = True

    if not has_any_match:
        # No verbatim excerpts matched — highlight entire segment as fallback
        qid = annotations[0].quote_id
        return (
            f'<mark class="bn-cited" data-quote-id="{_esc(qid)}">'
            f"{_esc(segment_text)}</mark>"
        )

    # Sort ranges by start position, merge overlaps
    ranges.sort(key=lambda r: r[0])
    merged: list[tuple[int, int, str]] = []
    for start, end, qid in ranges:
        if merged and start <= merged[-1][1]:
            # Overlapping — extend the previous range
            prev_start, prev_end, prev_qid = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), prev_qid)
        else:
            merged.append((start, end, qid))

    # Build output with <mark> tags around matched ranges
    parts: list[str] = []
    pos = 0
    for start, end, qid in merged:
        if pos < start:
            parts.append(_esc(segment_text[pos:start]))
        parts.append(
            f'<mark class="bn-cited" data-quote-id="{_esc(qid)}">'
            f"{_esc(segment_text[start:end])}</mark>"
        )
        pos = end
    if pos < len(segment_text):
        parts.append(_esc(segment_text[pos:]))

    return "".join(parts)


# ---------------------------------------------------------------------------
# Inline transcript rendering (for Sessions tab)
# ---------------------------------------------------------------------------


def _render_inline_transcripts(
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None,
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
    transcripts: list[FullTranscript] | None,
    all_quotes: list[ExtractedQuote] | None,
    screen_clusters: list[ScreenCluster] | None,
    theme_groups: list[ThemeGroup] | None,
) -> list[str]:
    """Render transcript content as inline divs for the Sessions tab panel.

    Returns a list of HTML strings (one per transcript) to be appended
    inside the Sessions tab panel, after the session grid.
    """
    if not transcripts:
        return []

    quote_map = _build_transcript_quote_map(all_quotes, screen_clusters, theme_groups)
    parts: list[str] = []

    for transcript in transcripts:
        html = _render_inline_transcript(
            transcript=transcript,
            video_map=video_map,
            people=people,
            quote_map=quote_map,
        )
        parts.append(html)

    return parts


def _render_inline_transcript(
    transcript: FullTranscript,
    video_map: dict[str, str] | None,
    people: PeopleFile | None,
    quote_map: _QuoteMap | None,
) -> str:
    """Render a single transcript as an inline HTML div (not a standalone page)."""
    pid = transcript.participant_id
    sid = transcript.session_id

    # Collect speaker codes
    seen_codes: dict[str, None] = {}
    for seg in transcript.segments:
        code = seg.speaker_code or pid
        if code not in seen_codes:
            seen_codes[code] = None
    speaker_codes = list(seen_codes)

    def _code_sort_key(c: str) -> tuple[int, int]:
        prefix_order = {"m": 0, "p": 1, "o": 2}
        order = prefix_order.get(c[0], 3) if c else 3
        num = int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
        return (order, num)

    speaker_codes.sort(key=_code_sort_key)

    session_num = sid[1:] if len(sid) > 1 and sid[0] in "sp" and sid[1:].isdigit() else sid

    # Build label for sub-nav
    code_labels: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        if name != code:
            code_labels.append(f"{code} {name}")
        else:
            code_labels.append(code)
    session_label = f"Session {_esc(session_num)}: {', '.join(_esc(lb) for lb in code_labels)}"

    # HTML spans for heading
    code_spans: list[str] = []
    for code in speaker_codes:
        name = _resolve_speaker_name(code, people, None)
        label = f"{_esc(code)} {_esc(name)}" if name != code else _esc(code)
        code_spans.append(
            f'<span class="heading-speaker" data-participant="{_esc(code)}">'
            f"{label}</span>"
        )

    p: list[str] = []
    w = p.append

    heading_html = f"Session {_esc(session_num)}: {', '.join(code_spans)}"
    w(
        f'<div class="bn-session-page" data-session="{_esc(sid)}" '
        f'data-session-label="{_esc(session_label)}" style="display:none">'
    )
    w(f"<h1>{heading_html}</h1>")

    # Transcript segments
    w('<section class="transcript-body">')
    has_media = video_map is not None and sid in (video_map or {})
    session_annotations = (quote_map or {}).get(sid, [])

    for seg in transcript.segments:
        tc = format_timecode(seg.start_time)
        anchor = f"t-{sid}-{int(seg.start_time)}"
        code = seg.speaker_code or pid
        is_moderator = code.startswith("m")

        seg_quotes = [
            a for a in session_annotations
            if a.start_tc <= seg.start_time <= a.end_tc
            and a.participant_id == code
        ]
        is_quoted = bool(seg_quotes) and not is_moderator

        classes = ["transcript-segment"]
        if is_moderator:
            classes.append("segment-moderator")
        if is_quoted:
            classes.append("segment-quoted")
        cls_str = " ".join(classes)

        data_attrs = (
            f' data-participant="{_esc(code)}"'
            f' data-start-seconds="{seg.start_time}"'
            f' data-end-seconds="{seg.end_time}"'
        )
        if is_quoted:
            qids = " ".join(a.quote_id for a in seg_quotes)
            data_attrs += f' data-quote-ids="{_esc(qids)}"'

        w(f'<div class="{cls_str}" id="{anchor}"{data_attrs}>')
        if has_media:
            w(
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(pid)}" '
                f'data-seconds="{seg.start_time}">{_tc_brackets(tc)}</a>'
            )
        else:
            w(f'<span class="timecode">{_tc_brackets(tc)}</span>')
        w('<div class="segment-body">')
        w(
            f'<span class="segment-speaker" data-participant="{_esc(code)}">'
            f"{_esc(code)}:</span>"
        )

        seg_text = seg.text
        if is_quoted:
            seg_text = _highlight_quoted_text(seg_text, seg_quotes)
            w(f" {seg_text}")
        else:
            w(f" {_esc(seg_text)}")

        w("</div></div>")

    w("</section>")
    w("</div>")  # .bn-session-page
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _document_shell_open(
    title: str, css_href: str, color_scheme: str = "auto"
) -> str:
    """Return the opening document shell (DOCTYPE through <article>)."""
    data_theme = color_scheme if color_scheme in ("light", "dark") else ""
    tmpl = _jinja_env.get_template("document_shell_open.html")
    return tmpl.render(title=title, css_href=css_href, data_theme=data_theme)


def _report_header_html(
    *,
    assets_prefix: str,
    has_logo: bool,
    has_dark_logo: bool,
    project_name: str,
    doc_title: str,
    meta_right: str | None = None,
) -> str:
    """Return the report header block (logo, title, doc type, meta)."""
    tmpl = _jinja_env.get_template("report_header.html")
    return tmpl.render(
        assets_prefix=assets_prefix,
        has_logo=has_logo,
        has_dark_logo=has_dark_logo,
        project_name=project_name,
        doc_title=doc_title,
        meta_right=meta_right,
    )


def _footer_html(assets_prefix: str = "assets") -> str:
    """Return the page footer with logo, version, feedback links, and keyboard hint.

    Args:
        assets_prefix: Path prefix for logo images. Use ``"assets"`` for pages
            at the output root (report, codebook) and ``"../assets"`` for pages
            in subdirectories (transcript pages in ``sessions/``).
    """
    from bristlenose import __version__

    tmpl = _jinja_env.get_template("footer.html")
    return tmpl.render(version=__version__, assets_prefix=assets_prefix)


def _esc(text: str) -> str:
    """HTML-escape user-supplied text."""
    return escape(text)


def _tc_brackets(tc: str) -> str:
    """Wrap timecode digits in muted-bracket markup: [00:42]."""
    return f'<span class="timecode-bracket">[</span>{tc}<span class="timecode-bracket">]</span>'


def _timecode_html(
    quote: ExtractedQuote,
    video_map: dict[str, str] | None,
) -> str:
    """Build timecode HTML — clickable link if video exists, plain span otherwise."""
    tc = format_timecode(quote.start_timecode)
    if video_map and quote.participant_id in video_map:
        return (
            f'<a href="#" class="timecode" '
            f'data-participant="{_esc(quote.participant_id)}" '
            f'data-seconds="{quote.start_timecode}" '
            f'data-end-seconds="{quote.end_timecode}">{_tc_brackets(tc)}</a>'
        )
    return f'<span class="timecode">{_tc_brackets(tc)}</span>'


def _session_anchor(quote: ExtractedQuote) -> tuple[str, str, str]:
    """Return (pid_esc, sid_esc, anchor) for a quote's session navigation."""
    pid_esc = _esc(quote.participant_id)
    sid_esc = _esc(quote.session_id) if quote.session_id else pid_esc
    anchor = f"t-{sid_esc}-{int(quote.start_timecode)}"
    return pid_esc, sid_esc, anchor


def _display_name(
    pid: str, display_names: dict[str, str] | None
) -> str:
    """Resolve participant_id to display name."""
    if display_names and pid in display_names:
        return display_names[pid]
    return pid


def _oxford_list(names: list[str]) -> str:
    """Join names with Oxford commas: 'A', 'A and B', 'A, B, and C'."""
    if len(names) <= 1:
        return names[0] if names else ""
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _participant_range(sessions: list[InputSession]) -> str:
    if not sessions:
        return "none"
    ids = [s.participant_id for s in sessions]
    if len(ids) == 1:
        return ids[0]
    return f"{ids[0]}\u2013{ids[-1]}"


def _session_duration(
    session: InputSession,
    people: PeopleFile | None = None,
) -> str:
    # Prefer PersonComputed.duration_seconds (works for VTT — derived
    # from last segment end_time in merge_transcript.py).
    if people and people.participants:
        for entry in people.participants.values():
            if (entry.computed.session_id == session.session_id
                    and entry.computed.duration_seconds > 0):
                return format_timecode(entry.computed.duration_seconds)
    # Fallback: InputFile.duration_seconds (audio/video with real timecodes).
    for f in session.files:
        if f.duration_seconds is not None:
            return format_timecode(f.duration_seconds)
    return "&mdash;"


def _format_quote_html(
    quote: ExtractedQuote,
    video_map: dict[str, str] | None = None,
) -> str:
    """Render a single quote as an HTML blockquote."""
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
    tc_html = _timecode_html(quote, video_map)
    tc = format_timecode(quote.start_timecode)

    # Speaker link navigates to Sessions tab → session drill-down → timecode
    pid_esc, sid_esc, anchor = _session_anchor(quote)
    speaker_link = (
        f'<a href="#" class="speaker-link" data-nav-session="{sid_esc}"'
        f' data-nav-anchor="{anchor}">{pid_esc}</a>'
    )

    tmpl = _jinja_env.get_template("quote_card.html")
    return tmpl.render(
        quote_id=quote_id,
        timecode=_esc(tc),
        participant_id=_esc(quote.participant_id),
        emotion=_esc(quote.emotion.value),
        intent=_esc(quote.intent.value),
        researcher_context=_esc(quote.researcher_context) if quote.researcher_context else "",
        tc_html=tc_html,
        quote_text=_esc(quote.text),
        speaker_link=speaker_link,
        badges=_quote_badges(quote),
    ).rstrip("\n")


def _quote_badges(quote: ExtractedQuote) -> str:
    """Build HTML badge span for the quote's sentiment (if any).

    Uses the new sentiment field (v0.7+). Falls back to deprecated
    intent/emotion fields for backward compatibility with old intermediate JSON.
    """

    # New sentiment field takes priority
    if quote.sentiment is not None:
        css_class = f"badge badge-ai badge-{quote.sentiment.value}"
        return (
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.sentiment.value)}</span>"
        )

    # Backward compatibility: fall back to deprecated intent/emotion fields
    badges: list[str] = []
    if quote.intent != QuoteIntent.NARRATION:
        css_class = f"badge badge-ai badge-{quote.intent.value}"
        badges.append(
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.intent.value)}</span>"
        )
    if quote.emotion != EmotionalTone.NEUTRAL:
        css_class = f"badge badge-ai badge-{quote.emotion.value}"
        badges.append(
            f'<span class="{css_class}" data-badge-type="ai">'
            f"{_esc(quote.emotion.value)}</span>"
        )
    # Note: intensity badges removed — intensity is stored but not displayed
    return " ".join(badges)


def _build_sentiment_html(quotes: list[ExtractedQuote]) -> str:
    """Build a horizontal-bar sentiment histogram.

    Positive sentiments on top (largest first), divider, negative below
    (smallest at top so the worst clusters near the divider).
    Each label is styled as a badge tag.  The chart is placed inside
    a ``sentiment-row`` wrapper together with a JS-rendered user-tags chart.

    Uses the new sentiment field (v0.7+). Falls back to deprecated
    intent/emotion fields for backward compatibility with old intermediate JSON.
    """
    from collections import Counter

    from bristlenose.models import Sentiment

    # New sentiment categories (v0.7+)
    negative_sentiments = {
        Sentiment.FRUSTRATION,
        Sentiment.CONFUSION,
        Sentiment.DOUBT,
    }
    positive_sentiments = {
        Sentiment.SATISFACTION,
        Sentiment.DELIGHT,
        Sentiment.CONFIDENCE,
    }
    # Sentiment.SURPRISE is neutral — not counted in histogram

    # Deprecated emotion/intent mappings (backward compat)
    negative_labels_legacy = {
        EmotionalTone.CONFUSED: "confused",
        EmotionalTone.FRUSTRATED: "frustrated",
        EmotionalTone.CRITICAL: "critical",
        EmotionalTone.SARCASTIC: "sarcastic",
    }
    positive_labels_legacy = {
        EmotionalTone.DELIGHTED: "delighted",
        EmotionalTone.AMUSED: "amused",
        QuoteIntent.DELIGHT: "delight",
    }

    neg_counts: Counter[str] = Counter()
    pos_counts: Counter[str] = Counter()
    surprise_count = 0

    for q in quotes:
        # New sentiment field takes priority
        if q.sentiment is not None:
            if q.sentiment in negative_sentiments:
                neg_counts[q.sentiment.value] += 1
            elif q.sentiment in positive_sentiments:
                pos_counts[q.sentiment.value] += 1
            elif q.sentiment == Sentiment.SURPRISE:
                surprise_count += 1
            continue

        # Backward compat: fall back to deprecated fields
        if q.emotion in negative_labels_legacy:
            neg_counts[negative_labels_legacy[q.emotion]] += 1
        if q.emotion in positive_labels_legacy:
            pos_counts[positive_labels_legacy[q.emotion]] += 1
        if q.intent == QuoteIntent.DELIGHT and q.emotion != EmotionalTone.DELIGHTED:
            pos_counts["delight"] += 1
        if q.intent == QuoteIntent.CONFUSION and q.emotion != EmotionalTone.CONFUSED:
            neg_counts["confused"] += 1
        if q.intent == QuoteIntent.FRUSTRATION and q.emotion != EmotionalTone.FRUSTRATED:
            neg_counts["frustrated"] += 1

    if not neg_counts and not pos_counts and surprise_count == 0:
        return ""

    # Badge-colour CSS class mapping
    badge_class_map: dict[str, str] = {
        # New sentiments (v0.7+)
        "frustration": "badge-frustration",
        "confusion": "badge-confusion",
        "doubt": "badge-doubt",
        "surprise": "badge-surprise",
        "satisfaction": "badge-satisfaction",
        "delight": "badge-delight",
        "confidence": "badge-confidence",
        # Deprecated (backward compat)
        "confused": "badge-confusion",
        "frustrated": "badge-frustration",
        "critical": "badge-frustration",
        "sarcastic": "",
        "delighted": "badge-delight",
        "amused": "badge-delight",
    }

    # Bar colour mapping
    colour_map = {
        # New sentiments (v0.7+)
        "frustration": "var(--bn-sentiment-frustration)",
        "confusion": "var(--bn-sentiment-confusion)",
        "doubt": "var(--bn-sentiment-doubt)",
        "surprise": "var(--bn-sentiment-surprise)",
        "satisfaction": "var(--bn-sentiment-satisfaction)",
        "delight": "var(--bn-sentiment-delight)",
        "confidence": "var(--bn-sentiment-confidence)",
        # Deprecated (backward compat) — use old token names
        "confused": "var(--colour-confusion)",
        "frustrated": "var(--colour-frustration)",
        "critical": "var(--colour-frustration)",
        "sarcastic": "var(--colour-muted)",
        "delighted": "var(--colour-delight)",
        "amused": "var(--colour-delight)",
    }

    all_counts = list(neg_counts.values()) + list(pos_counts.values())
    max_count = max(all_counts) if all_counts else 1
    max_bar_px = 180

    def _make_bar(label: str, count: int) -> dict[str, str | int]:
        width = max(4, int((count / max_count) * max_bar_px))
        colour = colour_map.get(label, "var(--colour-muted)")
        badge_cls = badge_class_map.get(label, "")
        label_cls = f"sentiment-bar-label badge {badge_cls}".strip()
        return {
            "label": _esc(label), "count": count,
            "width": width, "colour": colour, "label_cls": label_cls,
        }

    # Positive bars: sorted descending (largest at top)
    pos_bars = [_make_bar(lbl, c) for lbl, c in
                sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)]

    # Surprise bar (neutral — between positive and negative)
    surprise_bar = _make_bar("surprise", surprise_count) if surprise_count > 0 else None

    # Negative bars: sorted ascending (smallest at top, worst near divider)
    neg_bars = [_make_bar(lbl, c) for lbl, c in
                sorted(neg_counts.items(), key=lambda x: x[1])]

    tmpl = _jinja_env.get_template("sentiment_chart.html")
    return tmpl.render(
        max_count=max_count,
        pos_bars=pos_bars,
        surprise_bar=surprise_bar,
        neg_bars=neg_bars,
    ).rstrip("\n")


def _has_rewatch_quotes(quotes: list[ExtractedQuote]) -> bool:
    """Check if any quotes would appear in the rewatch list (friction points)."""
    from bristlenose.models import Sentiment

    for q in quotes:
        # New sentiment field (v0.7+)
        if q.sentiment in (Sentiment.FRUSTRATION, Sentiment.CONFUSION, Sentiment.DOUBT):
            return True
        # Backward compat: deprecated fields
        if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION):
            return True
        if q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED):
            return True
        if q.intensity >= 3:
            return True
    return False


def _build_rewatch_html(
    quotes: list[ExtractedQuote],
    video_map: dict[str, str] | None = None,
) -> str:
    """Build the rewatch list (friction points) as HTML."""
    from bristlenose.models import Sentiment

    flagged: list[ExtractedQuote] = []
    for q in quotes:
        # New sentiment field (v0.7+)
        if q.sentiment in (Sentiment.FRUSTRATION, Sentiment.CONFUSION, Sentiment.DOUBT):
            flagged.append(q)
            continue
        # Backward compat: deprecated fields
        is_rewatch = (
            q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
            or q.intensity >= 3
        )
        if is_rewatch:
            flagged.append(q)

    if not flagged:
        return ""

    flagged.sort(key=lambda q: (_session_sort_key(q.session_id), q.start_timecode))

    # Group items by participant_id for template rendering
    groups: list[dict[str, object]] = []
    current_pid = ""
    current_items: list[dict[str, str]] = []
    for q in flagged:
        if q.participant_id != current_pid:
            if current_pid:
                groups.append({"pid": _esc(current_pid), "entries": current_items})
            current_pid = q.participant_id
            current_items = []
        tc = format_timecode(q.start_timecode)
        # Determine reason label
        if q.sentiment is not None:
            reason = q.sentiment.value
        elif q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION):
            reason = q.intent.value
        else:
            reason = q.emotion.value
        snippet = q.text[:80] + ("\u2026" if len(q.text) > 80 else "")

        if video_map and q.participant_id in video_map:
            tc_html = (
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(q.participant_id)}" '
                f'data-seconds="{q.start_timecode}" '
                f'data-end-seconds="{q.end_timecode}">{_tc_brackets(tc)}</a>'
            )
        else:
            tc_html = f'<span class="timecode">{_tc_brackets(tc)}</span>'

        # Snippet links to transcript page with yellow flash highlight
        sid_esc = _esc(q.session_id) if q.session_id else _esc(q.participant_id)
        anchor = f"t-{sid_esc}-{int(q.start_timecode)}"
        snippet_html = (
            f'<a href="#" class="speaker-link" '
            f'data-nav-session="{sid_esc}" '
            f'data-nav-anchor="{anchor}">'
            f'&ldquo;{_esc(snippet)}&rdquo;</a>'
        )

        current_items.append({
            "tc_html": tc_html, "reason": reason, "snippet_html": snippet_html,
        })
    if current_pid:
        groups.append({"pid": _esc(current_pid), "entries": current_items})

    tmpl = _jinja_env.get_template("friction_points.html")
    return tmpl.render(groups=groups).strip("\n")


def _build_video_map(sessions: list[InputSession]) -> dict[str, str]:
    """Map session_id → file:// URI of their video (or audio) file.

    Also adds entries keyed by participant_id for quote-level lookups.
    """
    video_map: dict[str, str] = {}
    for session in sessions:
        # Prefer video, fall back to audio
        for ftype in (FileType.VIDEO, FileType.AUDIO):
            for f in session.files:
                if f.file_type == ftype:
                    uri = f.path.resolve().as_uri()
                    video_map[session.session_id] = uri
                    video_map[session.participant_id] = uri
                    break
            if session.session_id in video_map:
                break
    return video_map


def _write_player_html(assets_dir: Path, player_path: Path) -> Path:
    """Write the popout video player page to assets/."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    tmpl = _jinja_env.get_template("player.html")
    player_path.write_text(tmpl.render(), encoding="utf-8")
    logger.info("Wrote video player: %s", player_path)
    return player_path


def _session_sort_key(sid: str) -> tuple[int, str]:
    """Sort key that orders session IDs numerically (s1 < s2 < s10)."""
    import re

    m = re.search(r"\d+", sid)
    return (int(m.group()) if m else 0, sid)


def _derive_journeys(
    screen_clusters: list[ScreenCluster],
    all_quotes: list[ExtractedQuote],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Derive per-participant journey data from screen clusters.

    Returns:
        (participant_screens, participant_session) where
        participant_screens maps pid → ordered list of screen labels,
        participant_session maps pid → session_id (first seen).
    """
    ordered = sorted(screen_clusters, key=lambda c: c.display_order)

    participant_screens: dict[str, list[str]] = {}
    participant_session: dict[str, str] = {}
    for cluster in ordered:
        for q in cluster.quotes:
            pid = q.participant_id
            if pid not in participant_screens:
                participant_screens[pid] = []
            if pid not in participant_session:
                participant_session[pid] = q.session_id
        pids_in_cluster = {q.participant_id for q in cluster.quotes}
        for pid in pids_in_cluster:
            if cluster.screen_label not in participant_screens[pid]:
                participant_screens[pid].append(cluster.screen_label)

    return participant_screens, participant_session


def _build_task_outcome_html(
    screen_clusters: list[ScreenCluster],
    all_quotes: list[ExtractedQuote],
    display_names: dict[str, str] | None = None,
) -> str:
    """Build the user journey summary as an HTML table.

    Derives each participant's journey from screen cluster membership —
    which report sections contain their quotes, ordered by the product's
    logical flow (display_order).  Default sort is by session number.
    """
    if not screen_clusters:
        return ""

    participant_screens, participant_session = _derive_journeys(
        screen_clusters, all_quotes,
    )

    if not participant_screens:
        return ""

    # Sort by session number (default)
    sorted_pids = sorted(
        participant_screens.keys(),
        key=lambda pid: _session_sort_key(participant_session.get(pid, "")),
    )

    row_data: list[dict[str, str]] = []
    for pid in sorted_pids:
        name = display_names.get(pid, pid) if display_names else pid
        sid = participant_session.get(pid, "")
        # Display session number without "s" prefix (e.g. "s1" -> "1")
        session_num = sid[1:] if sid.startswith("s") else sid
        journey_str = " &rarr; ".join(participant_screens[pid])
        row_data.append({
            "session": _esc(session_num),
            "pid": _esc(name),
            "stages": journey_str,
        })

    tmpl = _jinja_env.get_template("user_journeys.html")
    return tmpl.render(rows=row_data).rstrip("\n")


# ---------------------------------------------------------------------------
# Coverage section builder
# ---------------------------------------------------------------------------


def _build_coverage_html(coverage: CoverageStats) -> str:
    """Build the coverage disclosure section as HTML.

    Shows transcript coverage percentages and omitted content per session.
    Collapsed by default; expands to show what wasn't extracted.
    """
    summary = (
        f"{coverage.pct_in_report}% in report \u00b7 "
        f"{coverage.pct_moderator}% moderator \u00b7 "
        f"{coverage.pct_omitted}% omitted"
    )

    # Prepare per-session data for template
    session_data: list[dict[str, object]] = []
    if coverage.pct_omitted > 0:
        for session_id, omitted in coverage.omitted_by_session.items():
            if not omitted.full_segments and not omitted.fragment_counts:
                continue

            session_num = session_id[1:] if session_id.startswith("s") else session_id
            seg_data = []
            for seg in omitted.full_segments:
                seg_data.append({
                    "anchor": f"t-{seg.timecode_seconds}",
                    "code": _esc(seg.speaker_code),
                    "tc": _esc(seg.timecode),
                    "text": _esc(seg.text),
                })

            # Build fragments HTML string
            fragments_html = ""
            if omitted.fragment_counts:
                fragment_strs: list[str] = []
                for text, count in omitted.fragment_counts:
                    text_esc = _esc(text)
                    if count > 1:
                        fragment_strs.append(
                            f'<span class="verbatim">{text_esc} ({count}\u00d7)</span>'
                        )
                    else:
                        fragment_strs.append(f'<span class="verbatim">{text_esc}</span>')
                prefix = '<span class="label">Also omitted:</span> ' if omitted.full_segments else ""
                fragments_html = f"{prefix}{', '.join(fragment_strs)}"

            session_data.append({
                "id": session_id, "num": session_num,
                "full_segments": seg_data, "fragments_html": fragments_html,
            })

    tmpl = _jinja_env.get_template("coverage.html")
    return tmpl.render(
        summary=summary,
        pct_omitted=coverage.pct_omitted,
        sessions=session_data,
    ).rstrip("\n")
