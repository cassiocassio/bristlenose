"""Stage 12b: Render the research report as styled HTML with external CSS.

This is the orchestrator for the static HTML render path (deprecated).
Use ``bristlenose serve`` for the full interactive experience.
"""

from __future__ import annotations

import json
import logging
import shutil
import warnings
from datetime import datetime
from pathlib import Path

from bristlenose.coverage import calculate_coverage
from bristlenose.models import (
    ExtractedQuote,
    FullTranscript,
    InputSession,
    PeopleFile,
    ScreenCluster,
    ThemeGroup,
)
from bristlenose.stages.s12_render.dashboard import (
    _build_coverage_html,
    _build_session_rows,
    _build_task_outcome_html,
    _render_project_tab,
)
from bristlenose.stages.s12_render.html_helpers import (
    _build_video_map,
    _document_shell_open,
    _esc,
    _footer_html,
    _report_header_html,
    _write_player_html,
)
from bristlenose.stages.s12_render.quote_format import _format_quote_html
from bristlenose.stages.s12_render.sentiment import (
    _build_rewatch_html,
    _build_sentiment_html,
)
from bristlenose.stages.s12_render.standalone_pages import (
    _render_analysis_page,
    _render_codebook_page,
    _serialize_analysis,
)
from bristlenose.stages.s12_render.theme_assets import (
    _LOGO_DARK_PATH,
    _LOGO_PATH,
    _get_default_css,
    _get_report_js,
    _jinja_env,
)
from bristlenose.stages.s12_render.transcript_pages import (
    _build_transcript_quote_map,
    _render_inline_transcripts,
    render_transcript_pages,
)
from bristlenose.utils.markdown import format_finder_date

logger = logging.getLogger(__name__)


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

    .. deprecated::
        Static HTML rendering is deprecated. Use ``bristlenose serve`` for the
        full interactive experience, or ``bristlenose serve --export`` for a
        self-contained HTML download.

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
    warnings.warn(
        "Static HTML rendering is deprecated. "
        "Use 'bristlenose serve' for the full experience.",
        DeprecationWarning,
        stacklevel=2,
    )

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

    # Extract video thumbnails (skips cached, audio-only, and failed).
    thumbnail_map: dict[str, str] = {}
    if has_media and transcripts:
        from bristlenose.utils.video import extract_thumbnails

        thumb_paths = extract_thumbnails(sessions, transcripts, paths.thumbnails_dir)
        for sid in thumb_paths:
            thumbnail_map[sid] = f"assets/thumbnails/{sid}.jpg"

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
    _w("<!-- bn-app -->")
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
    _w("<!-- bn-session-subnav -->")
    _w('<div class="bn-session-subnav" style="display:none">')
    _w('<button class="bn-session-back">&larr; All sessions</button>')
    _w('<span class="bn-session-label"></span>')
    _w("</div>")
    _w("<!-- /bn-session-subnav -->")
    _w('<div class="bn-session-grid">')

    # --- Session Summary (at top for quick reference) ---
    _w("<!-- bn-session-table -->")
    if serve_mode:
        # React island mount point — SessionsTable component will render here
        _w('<div id="bn-sessions-table-root" data-project-id="1"></div>')
    elif sessions:
        session_rows, moderator_header, observer_header = _build_session_rows(
            sessions, people, display_names, video_map, now,
            screen_clusters=screen_clusters,
            all_quotes=all_quotes,
            thumbnail_map=thumbnail_map,
        )
        _w(_jinja_env.get_template("session_table.html").render(
            rows=session_rows,
            moderator_header=moderator_header,
            observer_header=observer_header,
        ).rstrip("\n"))
    _w("<!-- /bn-session-table -->")

    # Close session grid
    _w("</div>")  # .bn-session-grid

    # Inline transcripts (rendered as hidden divs, shown via JS drill-down).
    _w("<!-- bn-inline-transcripts -->")
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
    _w("<!-- /bn-inline-transcripts -->")

    _w("</div>")  # .bn-tab-panel[sessions]

    # --- Quotes tab ---
    _w('<div class="bn-tab-panel" data-tab="quotes" id="panel-quotes" role="tabpanel" aria-label="Quotes">')

    # --- Toolbar ---
    _w("<!-- bn-toolbar -->")
    _w(_jinja_env.get_template("toolbar.html").render())
    _w("<!-- /bn-toolbar -->")

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
    _w("<!-- bn-quote-sections -->")
    if screen_clusters:
        groups = []
        for cluster in screen_clusters:
            anchor = f"section-{cluster.screen_label.lower().replace(' ', '-')}"
            quotes_html = "\n".join(
                _format_quote_html(q, video_map, display_names)
                for q in cluster.quotes
            )
            groups.append({
                "anchor": _esc(anchor), "label": _esc(cluster.screen_label),
                "description": _esc(cluster.description) if cluster.description else "",
                "quotes_html": quotes_html,
            })
        _w(_content_tmpl.render(
            heading="Sections", item_type="section", groups=groups,
        ).rstrip("\n"))
    _w("<!-- /bn-quote-sections -->")

    # --- Themes ---
    _w("<!-- bn-quote-themes -->")
    if theme_groups:
        groups = []
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            quotes_html = "\n".join(
                _format_quote_html(q, video_map, display_names)
                for q in theme.quotes
            )
            groups.append({
                "anchor": _esc(anchor), "label": _esc(theme.theme_label),
                "description": _esc(theme.description) if theme.description else "",
                "quotes_html": quotes_html,
            })
        _w(_content_tmpl.render(
            heading="Themes", item_type="theme", groups=groups,
        ).rstrip("\n"))
    _w("<!-- /bn-quote-themes -->")

    # --- Sentiment (includes friction points) ---
    if all_quotes:
        sentiment_html = _build_sentiment_html(all_quotes)
        rewatch = _build_rewatch_html(all_quotes, video_map, display_names)
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
            _w("<!-- bn-user-journeys -->")
            _w("<section>")
            _w('<h2 id="user-journeys">User journeys</h2>')
            _w(
                '<p class="description">Each participant\u2019s path through the product '
                "&mdash; which report sections contain their quotes, in logical order.</p>"
            )
            _w(task_html)
            _w("</section>")
            _w("<hr>")
            _w("<!-- /bn-user-journeys -->")

    # --- Coverage ---
    if transcripts and all_quotes:
        coverage = calculate_coverage(transcripts, all_quotes)
        coverage_html = _build_coverage_html(coverage)
        _w(coverage_html)

    _w("</div>")  # .bn-tab-panel[quotes]

    # --- Codebook tab ---
    _w("<!-- bn-codebook -->")
    _w('<div class="bn-tab-panel" data-tab="codebook" id="panel-codebook" role="tabpanel" aria-label="Codebook">')
    _w('<h1>Codebook</h1>')
    _w('<p class="codebook-description">Drag tags between groups to '
       "reorganise. Click a tag to rename it. Changes are saved automatically "
       "and sync across all open windows.</p>")
    _w('<div class="codebook-grid" id="codebook-grid"></div>')
    _w("</div>")  # .bn-tab-panel[codebook]
    _w("<!-- /bn-codebook -->")

    # --- Analysis tab ---
    _w("<!-- bn-analysis -->")
    _w('<div class="bn-tab-panel" data-tab="analysis" id="panel-analysis" role="tabpanel" aria-label="Analysis">')
    if analysis is not None:
        _w(_jinja_env.get_template("analysis.html").render())
    else:
        _w("<h2>Analysis</h2>")
        _w('<p class="description">No analysis data available.'
           " Run the full pipeline to generate analysis.</p>")
    _w("</div>")  # .bn-tab-panel[analysis]
    _w("<!-- /bn-analysis -->")

    # --- Settings tab ---
    _w("<!-- bn-settings -->")
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
    _w('<fieldset class="bn-setting-group">')
    _w("<legend>Show participants as</legend>")
    _w('<label class="bn-radio-label">'
       '<input type="radio" name="bn-person-display" value="code-and-name" checked> '
       "Code and name</label>")
    _w('<label class="bn-radio-label">'
       '<input type="radio" name="bn-person-display" value="code"> '
       "Code only</label>")
    _w("</fieldset>")
    _w("</div>")  # .bn-tab-panel[settings]
    _w("<!-- /bn-settings -->")

    # --- About tab ---
    from bristlenose import __version__ as _ver
    _w("<!-- bn-about -->")
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
    _w("</div>")  # .bn-about
    _w("</div>")  # .bn-tab-panel[about]
    _w("<!-- /bn-about -->")
    _w("<!-- /bn-app -->")

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
        _w(f"window.BRISTLENOSE_ANALYSIS = {_serialize_analysis(analysis)};")
        _w(f"var BRISTLENOSE_REPORT_FILENAME = '{paths.html_report.name}';")

    # Player popup URL.
    _w("var BRISTLENOSE_PLAYER_URL = 'assets/bristlenose-player.html';")

    # Expose globals for React (PlayerContext reads from window.*).
    _w("window.BRISTLENOSE_VIDEO_MAP = BRISTLENOSE_VIDEO_MAP;")
    _w("window.BRISTLENOSE_PLAYER_URL = BRISTLENOSE_PLAYER_URL;")

    _w(_get_report_js())
    _w("})();")
    _w("</script>")

    # React islands mount point — empty and invisible when no React bundle is loaded.
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
