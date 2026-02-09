"""Stage 12b: Render the research report as styled HTML with external CSS."""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
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
    JourneyStage,
    PeopleFile,
    QuoteIntent,
    ScreenCluster,
    ThemeGroup,
    format_timecode,
)
from bristlenose.utils.markdown import format_finder_date

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default theme CSS — loaded from bristlenose/theme/ (atomic design system)
# ---------------------------------------------------------------------------

_CSS_VERSION = "bristlenose-theme v6"

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
    "organisms/codebook-panel.css",
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
) -> Path:
    """Generate the HTML research report with external CSS stylesheet.

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
        doc_title="Research report",
        meta_right=meta_right,
    ))

    # --- Toolbar ---
    _w('<div class="toolbar">')
    # Search filter (left — margin-right:auto pushes rest right)
    _w(
        '<div class="search-container" id="search-container">'
        '<button class="search-toggle" id="search-toggle"'
        ' aria-label="Search quotes">'
        '<svg width="15" height="15" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="1.5"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="6.5" cy="6.5" r="5.5"/>'
        '<line x1="10.5" y1="10.5" x2="15" y2="15"/>'
        "</svg>"
        "</button>"
        '<div class="search-field">'
        '<input class="search-input" id="search-input" type="text"'
        ' placeholder="Filter quotes\u2026" autocomplete="off">'
        '<button class="search-clear" id="search-clear"'
        ' aria-label="Clear search">'
        '<svg width="12" height="12" viewBox="0 0 12 12"'
        ' fill="none" stroke="currentColor" stroke-width="1.5"'
        ' stroke-linecap="round">'
        '<line x1="2" y1="2" x2="10" y2="10"/>'
        '<line x1="10" y1="2" x2="2" y2="10"/>'
        "</svg>"
        "</button>"
        "</div>"
        "</div>"
    )
    # Codebook (opens in new window)
    _w(
        '<button class="toolbar-btn" id="codebook-btn"'
        ' title="Open codebook in new window">'
        '<svg class="toolbar-icon-svg" width="14" height="14" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="1.5"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="1" y="3" width="11" height="11" rx="1.5"/>'
        '<path d="M9 1h6v6"/>'
        '<path d="M15 1 8 8"/>'
        "</svg>"
        " Codebook"
        "</button>"
    )
    # Tag filter dropdown
    _w(
        '<div class="tag-filter">'
        '<button class="toolbar-btn tag-filter-btn" id="tag-filter-btn"'
        ' aria-haspopup="true" aria-expanded="false">'
        '<svg class="toolbar-icon-svg" width="14" height="14" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="1.5"'
        ' stroke-linecap="round">'
        '<line x1="1" y1="3" x2="15" y2="3"/>'
        '<line x1="3" y1="8" x2="13" y2="8"/>'
        '<line x1="5.5" y1="13" x2="10.5" y2="13"/>'
        "</svg>"
        ' <span class="tag-filter-label">Tags</span>'
        '<svg class="toolbar-arrow" width="10" height="10"'
        ' viewBox="0 0 10 10" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2.5 3.75 5 6.25 7.5 3.75"/></svg>'
        "</button>"
        '<div class="tag-filter-menu" id="tag-filter-menu"></div>'
        "</div>"
    )
    # AI tag toggle — TODO: relocate to future settings/view-controls panel
    # _w(
    #     '<button class="toolbar-btn toolbar-btn-toggle" id="ai-tag-toggle"'
    #     ' aria-label="Toggle AI tags" title="Show/hide AI sentiment tags">'
    #     '<span class="ai-toggle-label">AI tags</span>'
    #     "</button>"
    # )
    # View switcher dropdown
    _w('<div class="view-switcher">')
    _w(
        '<button class="toolbar-btn view-switcher-btn" id="view-switcher-btn"'
        ' aria-haspopup="true" aria-expanded="false">'
        '<span class="view-switcher-label">All quotes </span>'
        '<svg class="toolbar-arrow" width="10" height="10"'
        ' viewBox="0 0 10 10" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2.5 3.75 5 6.25 7.5 3.75"/></svg>'
        "</button>"
    )
    _w('<ul class="view-switcher-menu" id="view-switcher-menu" role="menu">')
    _w(
        '<li role="menuitem" data-view="all" class="active">'
        '<span class="menu-icon">&nbsp;</span> All quotes</li>'
    )
    _w(
        '<li role="menuitem" data-view="starred">'
        '<span class="menu-icon">&#9733;</span> Starred quotes</li>'
    )
    _w("</ul>")
    _w("</div>")
    # Export buttons (right)
    _w(
        '<button class="toolbar-btn" id="export-csv">'
        '<svg class="toolbar-icon-svg" width="14" height="14" viewBox="0 0 16 16"'
        ' fill="none" stroke="currentColor" stroke-width="1.5"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="5" y="1" width="9" height="11" rx="1.5"/>'
        '<path d="M3 5H2.5A1.5 1.5 0 0 0 1 6.5v8A1.5 1.5 0 0 0 2.5 16h8'
        'a1.5 1.5 0 0 0 1.5-1.5V14"/>'
        "</svg>"
        " Copy CSV"
        "</button>"
    )
    _w(
        '<button class="toolbar-btn" id="export-names" style="display:none">'
        '<span class="toolbar-icon">&#9998;</span> Export names'
        "</button>"
    )
    _w("</div>")

    # --- Session Summary (at top for quick reference) ---
    if sessions:
        # Build session_id → sorted speaker codes from people entries.
        _session_codes: dict[str, list[str]] = {}
        if people and people.participants:
            for code, entry in people.participants.items():
                sid_key = entry.computed.session_id
                if sid_key:
                    _session_codes.setdefault(sid_key, []).append(code)
            # Sort each list: m-codes first, then p-codes, then o-codes.
            _prefix_order = {"m": 0, "p": 1, "o": 2}
            for codes in _session_codes.values():
                codes.sort(key=lambda c: (
                    _prefix_order.get(c[0], 3) if c else 3,
                    int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0,
                ))

        _w("<section>")
        _w("<h2>Sessions</h2>")
        _w("<table>")
        _w("<thead><tr>")
        _w(
            "<th>Session</th><th>Speakers</th><th>Start</th>"
            "<th>Duration</th><th>Source file</th>"
        )
        _w("</tr></thead>")
        _w("<tbody>")
        for session in sessions:
            duration = _session_duration(session, people)
            sid = session.session_id
            sid_esc = _esc(sid)
            session_num = sid[1:] if len(sid) > 1 and sid[1:].isdigit() else sid
            start = _esc(format_finder_date(session.session_date, now=now))
            if session.files:
                source_name = _esc(session.files[0].path.name)
                if video_map and sid in video_map:
                    source = (
                        f'<a href="#" class="timecode" '
                        f'data-participant="{_esc(session.participant_id)}" '
                        f'data-seconds="0" data-end-seconds="0">'
                        f'{source_name}</a>'
                    )
                else:
                    file_uri = session.files[0].path.resolve().as_uri()
                    source = f'<a href="{file_uri}">{source_name}</a>'
            else:
                source = "&mdash;"
            _w("<tr>")
            _w(
                f'<td><a href="sessions/transcript_{sid_esc}.html">'
                f"{_esc(session_num)}</a></td>"
            )
            # Speakers column: comma-separated codes with data-participant spans.
            codes = _session_codes.get(sid, [session.participant_id])
            speaker_spans = []
            for code in codes:
                name = _resolve_speaker_name(code, people, display_names)
                speaker_spans.append(
                    f'<span class="speaker-code" '
                    f'data-participant="{_esc(code)}">'
                    f"{_esc(name)}</span>"
                )
            _w(f'<td>{", ".join(speaker_spans)}</td>')
            _w(f"<td>{start}</td>")
            _w(f"<td>{duration}</td>")
            _w(f"<td>{source}</td>")
            _w("</tr>")
        _w("</tbody>")
        _w("</table>")
        _w("</section>")
        _w("<hr>")

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
    if all_quotes and _has_rewatch_quotes(all_quotes):
        chart_toc.append(("friction-points", "Friction points"))
    if all_quotes and sessions:
        chart_toc.append(("user-journeys", "User journeys"))
    if transcripts and all_quotes:
        chart_toc.append(("transcript-coverage", "Transcript coverage"))
    if section_toc or theme_toc or chart_toc:
        _w('<div class="toc-row">')
        if section_toc:
            _w('<nav class="toc">')
            _w("<h2>Sections</h2>")
            _w("<ul>")
            for anchor, label in section_toc:
                a_esc = _esc(anchor)
                l_esc = _esc(label)
                _w(
                    f'<li><a href="#{a_esc}">'
                    f'<span class="editable-text"'
                    f' data-edit-key="{a_esc}:title"'
                    f' data-original="{l_esc}">{l_esc}</span></a>'
                    f' <button class="edit-pencil edit-pencil-inline"'
                    f' aria-label="Edit section title">&#9998;</button></li>'
                )
            _w("</ul>")
            _w("</nav>")
        if theme_toc:
            _w('<nav class="toc">')
            _w("<h2>Themes</h2>")
            _w("<ul>")
            for anchor, label in theme_toc:
                a_esc = _esc(anchor)
                l_esc = _esc(label)
                _w(
                    f'<li><a href="#{a_esc}">'
                    f'<span class="editable-text"'
                    f' data-edit-key="{a_esc}:title"'
                    f' data-original="{l_esc}">{l_esc}</span></a>'
                    f' <button class="edit-pencil edit-pencil-inline"'
                    f' aria-label="Edit theme title">&#9998;</button></li>'
                )
            _w("</ul>")
            _w("</nav>")
        if chart_toc:
            _w('<nav class="toc">')
            _w("<h2>Analysis</h2>")
            _w("<ul>")
            for anchor, label in chart_toc:
                a_esc = _esc(anchor)
                l_esc = _esc(label)
                _w(f'<li><a href="#{a_esc}">{l_esc}</a></li>')
            _w("</ul>")
            _w("</nav>")
        _w("</div>")
        _w("<hr>")

    # --- Sections (screen-specific findings) ---
    if screen_clusters:
        _w("<section>")
        _w("<h2>Sections</h2>")
        for cluster in screen_clusters:
            anchor = f"section-{cluster.screen_label.lower().replace(' ', '-')}"
            label_esc = _esc(cluster.screen_label)
            anchor_esc = _esc(anchor)
            _w(
                f'<h3 id="{anchor_esc}">'
                f'<span class="editable-text"'
                f' data-edit-key="{anchor_esc}:title"'
                f' data-original="{label_esc}">{label_esc}</span>'
                f' <button class="edit-pencil edit-pencil-inline"'
                f' aria-label="Edit section title">&#9998;</button></h3>'
            )
            if cluster.description:
                desc_esc = _esc(cluster.description)
                _w(
                    f'<p class="description">'
                    f'<span class="editable-text"'
                    f' data-edit-key="{anchor_esc}:desc"'
                    f' data-original="{desc_esc}">{desc_esc}</span>'
                    f' <button class="edit-pencil edit-pencil-inline"'
                    f' aria-label="Edit section description">&#9998;</button></p>'
                )
            _w('<div class="quote-group">')
            for quote in cluster.quotes:
                _w(_format_quote_html(quote, video_map))
            _w("</div>")
        _w("</section>")
        _w("<hr>")

    # --- Themes ---
    if theme_groups:
        _w("<section>")
        _w("<h2>Themes</h2>")
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            label_esc = _esc(theme.theme_label)
            anchor_esc = _esc(anchor)
            _w(
                f'<h3 id="{anchor_esc}">'
                f'<span class="editable-text"'
                f' data-edit-key="{anchor_esc}:title"'
                f' data-original="{label_esc}">{label_esc}</span>'
                f' <button class="edit-pencil edit-pencil-inline"'
                f' aria-label="Edit theme title">&#9998;</button></h3>'
            )
            if theme.description:
                desc_esc = _esc(theme.description)
                _w(
                    f'<p class="description">'
                    f'<span class="editable-text"'
                    f' data-edit-key="{anchor_esc}:desc"'
                    f' data-original="{desc_esc}">{desc_esc}</span>'
                    f' <button class="edit-pencil edit-pencil-inline"'
                    f' aria-label="Edit theme description">&#9998;</button></p>'
                )
            _w('<div class="quote-group">')
            for quote in theme.quotes:
                _w(_format_quote_html(quote, video_map))
            _w("</div>")
        _w("</section>")
        _w("<hr>")

    # --- Sentiment ---
    if all_quotes:
        sentiment_html = _build_sentiment_html(all_quotes)
        if sentiment_html:
            _w("<section>")
            _w('<h2 id="sentiment">Sentiment</h2>')
            _w(sentiment_html)
            _w("</section>")
            _w("<hr>")

    # --- Friction Points ---
    if all_quotes:
        rewatch = _build_rewatch_html(all_quotes, video_map)
        if rewatch:
            _w("<section>")
            _w('<h2 id="friction-points">Friction points</h2>')
            _w(
                '<p class="description">Moments flagged for researcher review '
                "&mdash; confusion, frustration, or error-recovery detected.</p>"
            )
            _w(rewatch)
            _w("</section>")
            _w("<hr>")

    # --- User Journeys ---
    if all_quotes and sessions:
        task_html = _build_task_outcome_html(all_quotes, sessions)
        if task_html:
            _w("<section>")
            _w('<h2 id="user-journeys">User journeys</h2>')
            _w(task_html)
            _w("</section>")
            _w("<hr>")

    # --- Coverage ---
    if transcripts and all_quotes:
        coverage = calculate_coverage(transcripts, all_quotes)
        coverage_html = _build_coverage_html(coverage)
        _w(coverage_html)

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

    _w(_get_report_js())
    _w("})();")
    _w("</script>")

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


def _display_name(
    pid: str, display_names: dict[str, str] | None
) -> str:
    """Resolve participant_id to display name."""
    if display_names and pid in display_names:
        return display_names[pid]
    return pid


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
    tc = format_timecode(quote.start_timecode)
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
    # Quote attributions use raw pid (p1, p2) for anonymisation
    parts: list[str] = [
        f'<blockquote id="{quote_id}"'
        f' data-timecode="{_esc(tc)}"'
        f' data-participant="{_esc(quote.participant_id)}"'
        f' data-emotion="{_esc(quote.emotion.value)}"'
        f' data-intent="{_esc(quote.intent.value)}">'
    ]

    if quote.researcher_context:
        parts.append(f'<span class="context">[{_esc(quote.researcher_context)}]</span>')

    if video_map and quote.participant_id in video_map:
        tc_html = (
            f'<a href="#" class="timecode" '
            f'data-participant="{_esc(quote.participant_id)}" '
            f'data-seconds="{quote.start_timecode}" '
            f'data-end-seconds="{quote.end_timecode}">{_tc_brackets(tc)}</a>'
        )
    else:
        tc_html = f'<span class="timecode">{_tc_brackets(tc)}</span>'

    pid_esc = _esc(quote.participant_id)
    sid_esc = _esc(quote.session_id) if quote.session_id else pid_esc
    anchor = f"t-{int(quote.start_timecode)}"
    speaker_link = (
        f'<a href="sessions/transcript_{sid_esc}.html#{anchor}" class="speaker-link">{pid_esc}</a>'
    )
    badges = _quote_badges(quote)
    badge_html = (
        f'<div class="badges">{badges}'
        ' <span class="badge badge-add" aria-label="Add tag">+</span>'
        ' <button class="badge-restore" aria-label="Restore tags"'
        ' title="Restore tags" style="display:none">&#x21A9;</button>'
        "</div>"
    )

    parts.append(
        f'<div class="quote-row">{tc_html}'
        f'<div class="quote-body">'
        f'<span class="quote-text">\u201c{_esc(quote.text)}\u201d</span>&nbsp;'
        f'<span class="speaker">&mdash;&nbsp;{speaker_link}</span>'
        f"{badge_html}"
        f"</div></div>"
    )

    parts.append(
        '<button class="hide-btn" aria-label="Hide this quote">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none"'
        ' stroke="currentColor" stroke-width="2" stroke-linecap="round">'
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8'
        'a18.45 18.45 0 0 1 5.06-5.94"/>'
        '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8'
        'a18.5 18.5 0 0 1-2.16 3.19"/>'
        '<line x1="1" y1="1" x2="23" y2="23"/>'
        "</svg></button>"
    )
    parts.append('<button class="edit-pencil" aria-label="Edit this quote">&#9998;</button>')
    parts.append('<button class="star-btn" aria-label="Star this quote">&#9733;</button>')
    parts.append("</blockquote>")
    return "\n".join(parts)


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

    def _bar(label: str, count: int) -> str:
        width = max(4, int((count / max_count) * max_bar_px))
        colour = colour_map.get(label, "var(--colour-muted)")
        badge_cls = badge_class_map.get(label, "")
        label_cls = f"sentiment-bar-label badge {badge_cls}".strip()
        return (
            f'<div class="sentiment-bar-group">'
            f'<span class="{label_cls}">{_esc(label)}</span>'
            f'<div class="sentiment-bar" style="width:{width}px;background:{colour}"></div>'
            f'<span class="sentiment-bar-count" style="color:{colour}">{count}</span>'
            f"</div>"
        )

    parts: list[str] = ['<div class="sentiment-chart">']
    parts.append('<div class="sentiment-chart-title">AI sentiment</div>')

    # Positive bars first: sorted descending (largest at top)
    pos_sorted = sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)
    for label, count in pos_sorted:
        parts.append(_bar(label, count))

    # Surprise bar (neutral — between positive and negative)
    if surprise_count > 0:
        parts.append(_bar("surprise", surprise_count))

    # Divider
    parts.append('<div class="sentiment-divider"></div>')

    # Negative bars below: sorted ascending (smallest at top, worst near divider)
    neg_sorted = sorted(neg_counts.items(), key=lambda x: x[1])
    for label, count in neg_sorted:
        parts.append(_bar(label, count))

    parts.append("</div>")

    # User-tags chart placeholder (populated by JS)
    parts.append('<div class="sentiment-chart" id="user-tags-chart"></div>')

    return f'<div class="sentiment-row" data-max-count="{max_count}">{"".join(parts)}</div>'


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
        if q.journey_stage == JourneyStage.ERROR_RECOVERY:
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
            or q.journey_stage == JourneyStage.ERROR_RECOVERY
            or q.intensity >= 3
        )
        if is_rewatch:
            flagged.append(q)

    if not flagged:
        return ""

    flagged.sort(key=lambda q: (q.participant_id, q.start_timecode))

    parts: list[str] = []
    current_pid = ""
    for q in flagged:
        if q.participant_id != current_pid:
            current_pid = q.participant_id
            parts.append(
                f'<p class="rewatch-participant">{_esc(current_pid)}</p>'
            )
        tc = format_timecode(q.start_timecode)
        # Determine reason label
        if q.sentiment is not None:
            reason = q.sentiment.value
        elif q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION):
            reason = q.intent.value
        else:
            reason = q.emotion.value
        snippet = q.text[:80] + ("..." if len(q.text) > 80 else "")

        if video_map and q.participant_id in video_map:
            tc_html = (
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(q.participant_id)}" '
                f'data-seconds="{q.start_timecode}" '
                f'data-end-seconds="{q.end_timecode}">{_tc_brackets(tc)}</a>'
            )
        else:
            tc_html = f'<span class="timecode">{_tc_brackets(tc)}</span>'

        parts.append(
            f'<p class="rewatch-item">'
            f"{tc_html} "
            f'<span class="reason">{_esc(reason)}</span> '
            f"&mdash; \u201c{_esc(snippet)}\u201d"
            f"</p>"
        )
    return "\n".join(parts)


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
    player_path.write_text(
        """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bristlenose player</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; background: #111; color: #e5e7eb; font-family: system-ui, sans-serif; }
body { display: flex; flex-direction: column; }
#status { padding: 0.4rem 0.75rem; font-size: 0.8rem; color: #9ca3af;
           font-family: "SF Mono", "Fira Code", "Consolas", monospace;
           border-bottom: 1px solid #333; flex-shrink: 0; min-height: 1.8rem; }
#status.error { color: #ef4444; }
video { flex: 1; width: 100%; min-height: 0; background: #000; }
</style>
</head>
<body>
<div id="status">No video loaded</div>
<video id="bristlenose-video" controls preload="none"></video>
<script>
(function() {
  var video = document.getElementById('bristlenose-video');
  var status = document.getElementById('status');
  var currentUri = null;
  var currentPid = null;

  function fmtTC(s) {
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = Math.floor(s % 60);
    var mm = (m < 10 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
    return h ? (h < 10 ? '0' : '') + h + ':' + mm : mm;
  }

  function loadAndSeek(pid, fileUri, seconds) {
    currentPid = pid;
    if (fileUri !== currentUri) {
      currentUri = fileUri;
      video.src = fileUri;
      video.addEventListener('loadeddata', function onLoad() {
        video.removeEventListener('loadeddata', onLoad);
        video.currentTime = seconds;
        video.play().catch(function() {});
      });
      video.load();
    } else {
      video.currentTime = seconds;
      video.play().catch(function() {});
    }
    status.className = '';
    status.textContent = pid + ' @ ' + fmtTC(seconds);
  }

  // Called by the report window to load + seek
  window.bristlenose_seekTo = function(pid, fileUri, seconds) {
    loadAndSeek(pid, fileUri, seconds);
  };

  // Read video source and seek time from URL hash
  function handleHash() {
    var hash = window.location.hash.substring(1);
    if (!hash) return;
    var params = {};
    hash.split('&').forEach(function(part) {
      var kv = part.split('=');
      if (kv.length === 2) params[kv[0]] = decodeURIComponent(kv[1]);
    });
    if (params.src) {
      loadAndSeek(params.pid || '', params.src, parseFloat(params.t) || 0);
    }
  }

  // Listen for postMessage from the report window
  window.addEventListener('message', function(e) {
    var d = e.data;
    if (d && d.type === 'bristlenose-seek' && d.src) {
      loadAndSeek(d.pid || '', d.src, parseFloat(d.t) || 0);
    }
  });

  // Handle initial load from URL hash
  handleHash();

  // Post messages back to the opener window for playback-synced glow.
  // Uses postMessage (not window.opener function calls) because browsers
  // block window.opener access for file:// URIs.
  function _notify(type, extra) {
    if (!window.opener) return;
    var msg = { type: type, pid: currentPid };
    if (extra) { for (var k in extra) { msg[k] = extra[k]; } }
    try { window.opener.postMessage(msg, '*'); } catch(e) {}
  }

  video.addEventListener('timeupdate', function() {
    if (currentPid) {
      status.textContent = currentPid + ' @ ' + fmtTC(video.currentTime);
      _notify('bristlenose-timeupdate', { seconds: video.currentTime, playing: !video.paused });
    }
  });

  video.addEventListener('play', function() {
    _notify('bristlenose-playstate', { playing: true });
  });

  video.addEventListener('pause', function() {
    _notify('bristlenose-playstate', { playing: false });
  });

  video.addEventListener('error', function() {
    status.className = 'error';
    status.textContent = 'Cannot play this format \\u2014 try converting to .mp4';
  });
})();
</script>
</body>
</html>
""",
        encoding="utf-8",
    )
    logger.info("Wrote video player: %s", player_path)
    return player_path


def _build_task_outcome_html(
    quotes: list[ExtractedQuote],
    sessions: list[InputSession],
) -> str:
    """Build the task outcome summary as an HTML table."""
    stage_order = [
        JourneyStage.LANDING,
        JourneyStage.BROWSE,
        JourneyStage.SEARCH,
        JourneyStage.PRODUCT_DETAIL,
        JourneyStage.CART,
        JourneyStage.CHECKOUT,
    ]

    by_participant: dict[str, list[ExtractedQuote]] = {}
    for q in quotes:
        by_participant.setdefault(q.participant_id, []).append(q)

    if not by_participant:
        return ""

    rows: list[str] = []
    rows.append("<table>")
    rows.append("<thead><tr>")
    rows.append(
        "<th>Participant</th>"
        "<th>Stages</th>"
        "<th>Friction points</th>"
    )
    rows.append("</tr></thead>")
    rows.append("<tbody>")

    for pid in sorted(by_participant.keys()):
        pq = by_participant[pid]
        stage_counts = Counter(q.journey_stage for q in pq)

        observed = [s for s in stage_order if stage_counts.get(s, 0) > 0]
        observed_str = " &rarr; ".join(s.value for s in observed) if observed else "other"

        friction = sum(
            1
            for q in pq
            if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
        )

        rows.append("<tr>")
        rows.append(f"<td>{_esc(pid)}</td>")
        rows.append(f"<td>{observed_str}</td>")
        rows.append(f"<td>{friction}</td>")
        rows.append("</tr>")

    rows.append("</tbody>")
    rows.append("</table>")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Coverage section builder
# ---------------------------------------------------------------------------


def _build_coverage_html(coverage: CoverageStats) -> str:
    """Build the coverage disclosure section as HTML.

    Shows transcript coverage percentages and omitted content per session.
    Collapsed by default; expands to show what wasn't extracted.
    """
    parts: list[str] = []

    # Section with heading (same level as User Journeys)
    parts.append("<section>")
    parts.append('<h2 id="transcript-coverage">Transcript coverage</h2>')

    # Summary percentages as content
    summary = (
        f"{coverage.pct_in_report}% in report · "
        f"{coverage.pct_moderator}% moderator · "
        f"{coverage.pct_omitted}% omitted"
    )
    parts.append(f'<p class="coverage-summary">{summary}</p>')

    # Handle 0% omitted case
    if coverage.pct_omitted == 0:
        parts.append(
            '<p class="coverage-empty">'
            "Nothing omitted — all participant speech is in the report."
            "</p>"
        )
    else:
        # Disclosure triangle for session details
        parts.append('<details class="coverage-details">')
        parts.append("<summary>Show omitted segments</summary>")
        parts.append('<div class="coverage-body">')

        # Show per-session omitted content
        for session_id, omitted in coverage.omitted_by_session.items():
            # Skip sessions with nothing omitted
            if not omitted.full_segments and not omitted.fragment_counts:
                continue

            # Extract session number from "s1" -> "1"
            session_num = session_id[1:] if session_id.startswith("s") else session_id

            parts.append('<div class="coverage-session">')
            parts.append(f'<p class="coverage-session-title">Session {session_num}</p>')

            # Full segments (>3 words)
            for seg in omitted.full_segments:
                tc_esc = _esc(seg.timecode)
                code_esc = _esc(seg.speaker_code)
                text_esc = _esc(seg.text)
                anchor = f"t-{seg.timecode_seconds}"
                parts.append(
                    f'<p class="coverage-segment">'
                    f'<a href="sessions/transcript_{session_id}.html#{anchor}" class="timecode">'
                    f"[{code_esc} {tc_esc}]</a> "
                    f"{text_esc}</p>"
                )

            # Fragment summary (≤3 words)
            if omitted.fragment_counts:
                fragment_strs: list[str] = []
                for text, count in omitted.fragment_counts:
                    text_esc = _esc(text)
                    if count > 1:
                        fragment_strs.append(
                            f'<span class="verbatim">{text_esc} ({count}×)</span>'
                        )
                    else:
                        fragment_strs.append(f'<span class="verbatim">{text_esc}</span>')

                # Use "Also omitted:" only if there were full segments
                if omitted.full_segments:
                    prefix = '<span class="label">Also omitted:</span> '
                else:
                    prefix = ""

                parts.append(
                    f'<p class="coverage-fragments">{prefix}{", ".join(fragment_strs)}</p>'
                )

            parts.append("</div>")

        parts.append("</div>")
        parts.append("</details>")

    parts.append("</section>")
    parts.append("<hr>")

    return "\n".join(parts)
