"""Stage 12b: Render the research report as styled HTML with external CSS."""

from __future__ import annotations

import json
import logging
import shutil
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

from bristlenose.models import (
    EmotionalTone,
    ExtractedQuote,
    FileType,
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
    "molecules/badge-row.css",
    "molecules/bar-group.css",
    "molecules/quote-actions.css",
    "molecules/tag-input.css",
    "organisms/blockquote.css",
    "organisms/sentiment-chart.css",
    "organisms/toolbar.css",
    "organisms/toc.css",
    "templates/report.css",
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
    "js/player.js",
    "js/favourites.js",
    "js/editing.js",
    "js/tags.js",
    "js/histogram.js",
    "js/csv-export.js",
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
) -> Path:
    """Generate research_report.html with an external CSS stylesheet.

    Always writes ``bristlenose-theme.css`` so that code changes are
    picked up without manual intervention.

    Returns:
        Path to the written HTML file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Always write CSS — keeps the stylesheet in sync with the renderer
    css_path = output_dir / "bristlenose-theme.css"
    css_path.write_text(_get_default_css(), encoding="utf-8")
    logger.info("Wrote theme: %s", css_path)

    # Copy logo images alongside the report
    logo_dest = output_dir / _LOGO_FILENAME
    if _LOGO_PATH.exists():
        shutil.copy2(_LOGO_PATH, logo_dest)
    logo_dark_dest = output_dir / _LOGO_DARK_FILENAME
    if _LOGO_DARK_PATH.exists():
        shutil.copy2(_LOGO_DARK_PATH, logo_dark_dest)

    # Build video/audio map for clickable timecodes
    video_map = _build_video_map(sessions)
    has_media = bool(video_map)

    # Write popout player page when media files exist
    if has_media:
        _write_player_html(output_dir)

    html_path = output_dir / "research_report.html"

    parts: list[str] = []
    _w = parts.append

    # --- Document shell ---
    _w("<!DOCTYPE html>")
    if color_scheme in ("light", "dark"):
        _w(f'<html lang="en" data-theme="{color_scheme}">')
    else:
        _w('<html lang="en">')
    _w("<head>")
    _w('<meta charset="utf-8">')
    _w('<meta name="viewport" content="width=device-width, initial-scale=1">')
    _w('<meta name="color-scheme" content="light dark">')
    _w(f"<title>{_esc(project_name)}</title>")
    _w('<link rel="stylesheet" href="bristlenose-theme.css">')
    _w("</head>")
    _w("<body>")
    _w("<article>")

    # --- Header ---
    _w('<div class="report-header">')
    _w(f"<h1>{_esc(project_name)}</h1>")
    if logo_dest.exists():
        if logo_dark_dest.exists():
            _w("<picture>")
            _w(
                f'<source srcset="{_LOGO_DARK_FILENAME}" '
                f'media="(prefers-color-scheme: dark)">'
            )
            _w(
                f'<img class="report-logo" src="{_LOGO_FILENAME}" '
                f'alt="Bristlenose logo">'
            )
            _w("</picture>")
        else:
            _w(
                f'<img class="report-logo" src="{_LOGO_FILENAME}" '
                f'alt="Bristlenose logo">'
            )
    _w("</div>")
    _w('<div class="toolbar">')
    _w(
        '<button class="toolbar-btn" id="export-favourites">'
        '<span class="toolbar-icon">&#9733;</span> Export favourites'
        "</button>"
    )
    _w(
        '<button class="toolbar-btn" id="export-all">'
        '<span class="toolbar-icon">&#9776;</span> Export all'
        "</button>"
    )
    _w("</div>")
    _w('<div class="meta">')
    _w(f"<p>Generated: {datetime.now().strftime('%Y-%m-%d')}</p>")
    _w(f"<p>Participants: {len(sessions)} ({_esc(_participant_range(sessions))})</p>")
    _w(f"<p>Sessions processed: {len(sessions)}</p>")
    _w("</div>")

    # --- Participant Summary (at top for quick reference) ---
    if sessions:
        _w("<section>")
        _w("<h2>Participants</h2>")
        _w("<table>")
        _w("<thead><tr>")
        if people and people.participants:
            _w(
                "<th>ID</th><th>Name</th><th>Role</th><th>Start</th>"
                "<th>Duration</th><th>Words</th><th>Source file</th>"
            )
        else:
            _w("<th>ID</th><th>Start</th>"
               "<th>Duration</th><th>Source file</th>")
        _w("</tr></thead>")
        _w("<tbody>")
        now = datetime.now()
        for session in sessions:
            duration = _session_duration(session)
            pid = session.participant_id
            pid_esc = _esc(pid)
            start = _esc(format_finder_date(session.session_date, now=now))
            if session.files:
                source_name = _esc(session.files[0].path.name)
                if video_map and pid in video_map:
                    source = (
                        f'<a href="#" class="timecode" '
                        f'data-participant="{pid_esc}" '
                        f'data-seconds="0" data-end-seconds="0">'
                        f'{source_name}</a>'
                    )
                else:
                    file_uri = session.files[0].path.resolve().as_uri()
                    source = f'<a href="{file_uri}">{source_name}</a>'
            else:
                source = "&mdash;"
            _w("<tr>")
            if people and people.participants:
                entry = people.participants.get(pid)
                _unnamed = (
                    '<span style="color:var(--bn-colour-muted);'
                    'font-style:italic">Unnamed</span>'
                )
                if entry:
                    words = str(entry.computed.words_spoken)
                    full_name = (
                        _esc(entry.editable.full_name)
                        if entry.editable.full_name else _unnamed
                    )
                    role = _esc(entry.editable.role) if entry.editable.role else "&mdash;"
                else:
                    words = "&mdash;"
                    full_name = _unnamed
                    role = "&mdash;"
                _w(f'<td><a href="transcript_{pid_esc}.html">{pid_esc}</a></td>')
                _w(f"<td>{full_name}</td>")
                _w(f"<td>{role}</td>")
                _w(f"<td>{start}</td>")
                _w(f"<td>{duration}</td>")
                _w(f"<td>{words}</td>")
                _w(f"<td>{source}</td>")
            else:
                _w(f'<td><a href="transcript_{pid_esc}.html">{pid_esc}</a></td>')
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
    if screen_clusters:
        for cluster in screen_clusters:
            anchor = f"section-{cluster.screen_label.lower().replace(' ', '-')}"
            section_toc.append((anchor, cluster.screen_label))
    if theme_groups:
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            theme_toc.append((anchor, theme.theme_label))
    if all_quotes:
        theme_toc.append(("sentiment", "Sentiment"))
    if all_quotes and _has_rewatch_quotes(all_quotes):
        theme_toc.append(("friction-points", "Friction points"))
    if section_toc or theme_toc:
        _w('<div class="toc-row">')
        if section_toc:
            _w('<nav class="toc">')
            _w("<h2>Sections</h2>")
            _w("<ul>")
            for anchor, label in section_toc:
                _w(f'<li><a href="#{_esc(anchor)}">{_esc(label)}</a></li>')
            _w("</ul>")
            _w("</nav>")
        if theme_toc:
            _w('<nav class="toc">')
            _w("<h2>Themes</h2>")
            _w("<ul>")
            for anchor, label in theme_toc:
                _w(f'<li><a href="#{_esc(anchor)}">{_esc(label)}</a></li>')
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
            _w(f'<h3 id="{_esc(anchor)}">{_esc(cluster.screen_label)}</h3>')
            if cluster.description:
                _w(f'<p class="description">{_esc(cluster.description)}</p>')
            _w('<div class="quote-group">')
            for quote in cluster.quotes:
                _w(_format_quote_html(quote, video_map, display_names))
            _w("</div>")
        _w("</section>")
        _w("<hr>")

    # --- Themes ---
    if theme_groups:
        _w("<section>")
        _w("<h2>Themes</h2>")
        for theme in theme_groups:
            anchor = f"theme-{theme.theme_label.lower().replace(' ', '-')}"
            _w(f'<h3 id="{_esc(anchor)}">{_esc(theme.theme_label)}</h3>')
            if theme.description:
                _w(f'<p class="description">{_esc(theme.description)}</p>')
            _w('<div class="quote-group">')
            for quote in theme.quotes:
                _w(_format_quote_html(quote, video_map, display_names))
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
        rewatch = _build_rewatch_html(all_quotes, video_map, display_names)
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
        task_html = _build_task_outcome_html(all_quotes, sessions, display_names)
        if task_html:
            _w("<section>")
            _w("<h2>User journeys</h2>")
            _w(task_html)
            _w("</section>")
            _w("<hr>")

    # --- Close ---
    _w("</article>")

    # --- Embed JavaScript ---
    _w("<script>")
    _w("(function() {")
    if has_media:
        _w(f"var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};")
    else:
        _w("var BRISTLENOSE_VIDEO_MAP = {};")
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
    )

    return html_path


# ---------------------------------------------------------------------------
# Transcript pages
# ---------------------------------------------------------------------------

_TRANSCRIPT_JS_FILES: list[str] = [
    "js/storage.js",
    "js/player.js",
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


def render_transcript_pages(
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None = None,
    color_scheme: str = "auto",
    display_names: dict[str, str] | None = None,
    people: PeopleFile | None = None,
) -> list[Path]:
    """Generate per-participant transcript HTML pages.

    Reads transcript segments from ``cooked_transcripts/`` (if present) or
    ``raw_transcripts/``, renders one HTML page per participant, and returns
    the list of written file paths.
    """
    from bristlenose.pipeline import load_transcripts_from_dir

    # Prefer cooked (PII-redacted) transcripts, fall back to raw
    cooked_dir = output_dir / "cooked_transcripts"
    raw_dir = output_dir / "raw_transcripts"
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

    paths: list[Path] = []
    for transcript in transcripts:
        page_path = _render_transcript_page(
            transcript=transcript,
            project_name=project_name,
            output_dir=output_dir,
            video_map=video_map,
            color_scheme=color_scheme,
            people=people,
        )
        paths.append(page_path)
        logger.info("Wrote transcript page: %s", page_path)

    return paths


def _render_transcript_page(
    transcript: object,  # PiiCleanTranscript (avoid circular import at module level)
    project_name: str,
    output_dir: Path,
    video_map: dict[str, str] | None = None,
    color_scheme: str = "auto",
    people: PeopleFile | None = None,
) -> Path:
    """Render a single participant transcript as an HTML page."""
    from bristlenose.models import PiiCleanTranscript

    assert isinstance(transcript, PiiCleanTranscript)
    pid = transcript.participant_id

    # Resolve names
    speaker_name = _resolve_speaker_name(pid, people, None)
    full_name = ""
    if people and pid in people.participants:
        full_name = people.participants[pid].editable.full_name

    # Page heading: "p1 Sarah Jones" or just "p1"
    heading = f"{_esc(pid)} {_esc(full_name)}" if full_name else _esc(pid)

    # Build HTML
    parts: list[str] = []
    _w = parts.append

    _w("<!DOCTYPE html>")
    theme_attr = ""
    if color_scheme in ("light", "dark"):
        theme_attr = f' data-theme="{color_scheme}"'
    _w(f'<html lang="en"{theme_attr}>')
    _w("<head>")
    _w('<meta charset="utf-8">')
    _w('<meta name="viewport" content="width=device-width, initial-scale=1">')
    _w('<meta name="color-scheme" content="light dark">')
    title = f"{pid} {full_name}".strip() if full_name else pid
    _w(f"<title>{_esc(title)} \u2014 {_esc(project_name)}</title>")
    _w('<link rel="stylesheet" href="bristlenose-theme.css">')
    _w("</head>")
    _w("<body>")
    _w("<article>")

    # Back button
    _w('<nav class="transcript-back">')
    _w(f'<a href="research_report.html">&larr; {_esc(project_name)} Research Report</a>')
    _w("</nav>")

    # Header
    _w('<div class="transcript-header">')
    _w(f"<h1>{heading}</h1>")

    # Meta line
    meta_parts: list[str] = []
    if transcript.source_file:
        meta_parts.append(f"Source: {_esc(transcript.source_file)}")
    if transcript.duration_seconds > 0:
        meta_parts.append(f"Duration: {format_timecode(transcript.duration_seconds)}")
    if meta_parts:
        _w(f'<p class="transcript-meta">{" &middot; ".join(meta_parts)}</p>')
    _w("</div>")
    _w("<hr>")

    # Transcript segments
    _w('<section class="transcript-body">')
    has_media = video_map is not None and pid in (video_map or {})
    for seg in transcript.segments:
        tc = format_timecode(seg.start_time)
        anchor = f"t-{int(seg.start_time)}"
        _w(f'<div class="transcript-segment" id="{anchor}">')
        if has_media:
            _w(
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(pid)}" '
                f'data-seconds="{seg.start_time}">[{tc}]</a>'
            )
        else:
            _w(f'<span class="timecode">[{tc}]</span>')
        _w(f' <span class="segment-speaker">{_esc(speaker_name)}:</span>')
        _w(f" {_esc(seg.text)}")
        _w("</div>")
    _w("</section>")

    _w("</article>")

    # JavaScript (player only)
    _w("<script>")
    _w("(function() {")
    if has_media:
        _w(f"var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};")
    else:
        _w("var BRISTLENOSE_VIDEO_MAP = {};")
    _w(_get_transcript_js())
    _w("initPlayer();")
    _w("})();")
    _w("</script>")

    _w("</body>")
    _w("</html>")

    page_path = output_dir / f"transcript_{pid}.html"
    page_path.write_text("\n".join(parts), encoding="utf-8")
    return page_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """HTML-escape user-supplied text."""
    return escape(text)


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


def _session_duration(session: InputSession) -> str:
    for f in session.files:
        if f.duration_seconds is not None:
            return format_timecode(f.duration_seconds)
    return "&mdash;"


def _format_quote_html(
    quote: ExtractedQuote,
    video_map: dict[str, str] | None = None,
    display_names: dict[str, str] | None = None,
) -> str:
    """Render a single quote as an HTML blockquote."""
    tc = format_timecode(quote.start_timecode)
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
    # data-participant keeps canonical ID for JS; visible text uses display name
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
            f'data-end-seconds="{quote.end_timecode}">[{tc}]</a>'
        )
    else:
        tc_html = f'<span class="timecode">[{tc}]</span>'

    name = _esc(_display_name(quote.participant_id, display_names))
    pid_esc = _esc(quote.participant_id)
    anchor = f"t-{int(quote.start_timecode)}"
    speaker_link = (
        f'<a href="transcript_{pid_esc}.html#{anchor}" class="speaker-link">{name}</a>'
    )
    parts.append(
        f"{tc_html} "
        f'<span class="quote-text">\u201c{_esc(quote.text)}\u201d</span> '
        f'<span class="speaker">&mdash; {speaker_link}</span>'
    )

    badges = _quote_badges(quote)
    parts.append(
        f'<div class="badges">{badges}'
        ' <span class="badge badge-add" aria-label="Add tag">+</span>'
        ' <button class="badge-restore" aria-label="Restore tags"'
        ' title="Restore tags" style="display:none">&#x21A9;</button>'
        "</div>"
    )

    parts.append('<button class="edit-pencil" aria-label="Edit this quote">&#9998;</button>')
    parts.append('<button class="fav-star" aria-label="Favourite this quote">&#9733;</button>')
    parts.append("</blockquote>")
    return "\n".join(parts)


def _quote_badges(quote: ExtractedQuote) -> str:
    """Build HTML badge spans for non-default quote metadata."""
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
    if quote.intensity >= 2:
        label = "moderate" if quote.intensity == 2 else "strong"
        badges.append(
            f'<span class="badge badge-ai" data-badge-type="ai">'
            f"intensity:{label}</span>"
        )
    return " ".join(badges)


def _build_sentiment_html(quotes: list[ExtractedQuote]) -> str:
    """Build a horizontal-bar sentiment histogram.

    Positive sentiments on top (largest first), divider, negative below
    (smallest at top so the worst clusters near the divider).
    Each label is styled as a badge tag.  The chart is placed inside
    a ``sentiment-row`` wrapper together with a JS-rendered user-tags chart.
    """
    from collections import Counter

    # Map emotions and intents to positive/negative buckets
    negative_labels = {
        EmotionalTone.CONFUSED: "confused",
        EmotionalTone.FRUSTRATED: "frustrated",
        EmotionalTone.CRITICAL: "critical",
        EmotionalTone.SARCASTIC: "sarcastic",
    }
    positive_labels = {
        EmotionalTone.DELIGHTED: "delighted",
        EmotionalTone.AMUSED: "amused",
        QuoteIntent.DELIGHT: "delight",
    }

    neg_counts: Counter[str] = Counter()
    pos_counts: Counter[str] = Counter()

    for q in quotes:
        if q.emotion in negative_labels:
            neg_counts[negative_labels[q.emotion]] += 1
        if q.emotion in positive_labels:
            pos_counts[positive_labels[q.emotion]] += 1
        # Intent-based (delight intent may differ from delighted emotion)
        if q.intent == QuoteIntent.DELIGHT and q.emotion != EmotionalTone.DELIGHTED:
            pos_counts["delight"] += 1
        if q.intent == QuoteIntent.CONFUSION and q.emotion != EmotionalTone.CONFUSED:
            neg_counts["confused"] += 1
        if q.intent == QuoteIntent.FRUSTRATION and q.emotion != EmotionalTone.FRUSTRATED:
            neg_counts["frustrated"] += 1

    if not neg_counts and not pos_counts:
        return ""

    # Badge-colour CSS class mapping (reuse existing badge-* classes)
    badge_class_map: dict[str, str] = {
        "confused": "badge-confusion",
        "frustrated": "badge-frustration",
        "critical": "badge-frustration",
        "sarcastic": "",
        "delighted": "badge-delight",
        "amused": "badge-delight",
        "delight": "badge-delight",
    }

    # Bar colour mapping
    colour_map = {
        "confused": "var(--colour-confusion)",
        "frustrated": "var(--colour-frustration)",
        "critical": "var(--colour-frustration)",
        "sarcastic": "var(--colour-muted)",
        "delighted": "var(--colour-delight)",
        "amused": "var(--colour-delight)",
        "delight": "var(--colour-delight)",
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
    """Check if any quotes would appear in the rewatch list."""
    return any(
        q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
        or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
        or q.journey_stage == JourneyStage.ERROR_RECOVERY
        or q.intensity >= 3
        for q in quotes
    )


def _build_rewatch_html(
    quotes: list[ExtractedQuote],
    video_map: dict[str, str] | None = None,
    display_names: dict[str, str] | None = None,
) -> str:
    """Build the rewatch list as HTML."""
    flagged: list[ExtractedQuote] = []
    for q in quotes:
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
                f'<p class="rewatch-participant">'
                f'{_esc(_display_name(current_pid, display_names))}</p>'
            )
        tc = format_timecode(q.start_timecode)
        reason = (
            q.intent.value
            if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            else q.emotion.value
        )
        snippet = q.text[:80] + ("..." if len(q.text) > 80 else "")

        if video_map and q.participant_id in video_map:
            tc_html = (
                f'<a href="#" class="timecode" '
                f'data-participant="{_esc(q.participant_id)}" '
                f'data-seconds="{q.start_timecode}" '
                f'data-end-seconds="{q.end_timecode}">[{tc}]</a>'
            )
        else:
            tc_html = f'<span class="timecode">[{tc}]</span>'

        parts.append(
            f'<p class="rewatch-item">'
            f"{tc_html} "
            f'<span class="reason">{_esc(reason)}</span> '
            f"&mdash; \u201c{_esc(snippet)}\u201d"
            f"</p>"
        )
    return "\n".join(parts)


def _build_video_map(sessions: list[InputSession]) -> dict[str, str]:
    """Map participant_id → file:// URI of their video (or audio) file."""
    video_map: dict[str, str] = {}
    for session in sessions:
        # Prefer video, fall back to audio
        for ftype in (FileType.VIDEO, FileType.AUDIO):
            for f in session.files:
                if f.file_type == ftype:
                    video_map[session.participant_id] = f.path.resolve().as_uri()
                    break
            if session.participant_id in video_map:
                break
    return video_map


def _write_player_html(output_dir: Path) -> Path:
    """Write the popout video player page."""
    player_path = output_dir / "bristlenose-player.html"
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

  video.addEventListener('timeupdate', function() {
    if (currentPid) {
      status.textContent = currentPid + ' @ ' + fmtTC(video.currentTime);
      if (window.opener && window.opener.bristlenose_onTimeUpdate) {
        try { window.opener.bristlenose_onTimeUpdate(currentPid, video.currentTime); }
        catch(e) {}
      }
    }
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
    display_names: dict[str, str] | None = None,
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
        rows.append(f"<td>{_esc(_display_name(pid, display_names))}</td>")
        rows.append(f"<td>{observed_str}</td>")
        rows.append(f"<td>{friction}</td>")
        rows.append("</tr>")

    rows.append("</tbody>")
    rows.append("</table>")
    return "\n".join(rows)
