"""Stage 12b: Render the research report as styled HTML with external CSS."""

from __future__ import annotations

import json
import logging
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
    QuoteIntent,
    ScreenCluster,
    ThemeGroup,
    format_timecode,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default theme CSS — written once, never overwritten
# ---------------------------------------------------------------------------

_CSS_VERSION = "bristlenose-theme v5"

DEFAULT_CSS = (
    f"/* {_CSS_VERSION} — default research report theme */\n"
    "/* Edit freely; Bristlenose will not overwrite this file once created. */\n"
) + """\

:root {
    --font-body: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
    --font-mono: "SF Mono", "Fira Code", "Consolas", monospace;
    --colour-bg: #ffffff;
    --colour-text: #1a1a1a;
    --colour-muted: #6b7280;
    --colour-border: #e5e7eb;
    --colour-accent: #2563eb;
    --colour-quote-bg: #f9fafb;
    --colour-badge-bg: #f3f4f6;
    --colour-badge-text: #374151;
    --colour-confusion: #dc2626;
    --colour-frustration: #ea580c;
    --colour-delight: #16a34a;
    --colour-suggestion: #2563eb;
    --max-width: 52rem;
}

*,
*::before,
*::after {
    box-sizing: border-box;
}

html {
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
}

body {
    font-family: var(--font-body);
    color: var(--colour-text);
    background: var(--colour-bg);
    line-height: 1.6;
    margin: 0;
    padding: 2rem 1.5rem;
}

article {
    max-width: var(--max-width);
    margin: 0 auto;
}

h1 {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.5rem;
    letter-spacing: -0.01em;
}

h2 {
    font-size: 1.35rem;
    font-weight: 600;
    margin: 2.5rem 0 1rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid var(--colour-border);
}

h3 {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 1.8rem 0 0.6rem;
}

.meta {
    color: var(--colour-muted);
    font-size: 0.9rem;
    margin-bottom: 2rem;
}

.meta p {
    margin: 0.15rem 0;
}

hr {
    border: none;
    border-top: 1px solid var(--colour-border);
    margin: 2rem 0;
}

/* --- Table of Contents --- */

.toc-row {
    display: flex;
    gap: 3rem;
    flex-wrap: wrap;
}

.toc-row > nav {
    flex: 1;
    min-width: 12rem;
}

.toc h2 {
    font-size: 1.1rem;
    margin-bottom: 0.5rem;
}

.toc ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.toc li {
    margin: 0.2rem 0;
    font-size: 0.9rem;
    break-inside: avoid;
}

.toc a {
    color: var(--colour-accent);
    text-decoration: none;
}

.toc a:hover {
    text-decoration: underline;
}

/* --- Quotes --- */

blockquote {
    background: var(--colour-quote-bg);
    border-left: 1px solid var(--colour-border);
    margin: 0.8rem 0;
    padding: 0.75rem 1rem;
    border-radius: 0 6px 6px 0;
}

blockquote .context {
    display: block;
    color: var(--colour-muted);
    font-size: 0.85rem;
    margin-bottom: 0.3rem;
}

blockquote .timecode {
    color: var(--colour-muted);
    font-family: var(--font-mono);
    font-size: 0.8rem;
}

blockquote .speaker {
    color: var(--colour-muted);
    font-size: 0.9rem;
}

blockquote .badges {
    display: flex;
    gap: 0.35rem;
    margin-top: 0.4rem;
    flex-wrap: wrap;
}

.badge {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    background: var(--colour-badge-bg);
    color: var(--colour-badge-text);
}

.badge-confusion { background: #fef2f2; color: var(--colour-confusion); }
.badge-frustration { background: #fff7ed; color: var(--colour-frustration); }
.badge-delight { background: #f0fdf4; color: var(--colour-delight); }
.badge-suggestion { background: #eff6ff; color: var(--colour-suggestion); }

/* --- Description text --- */

.description {
    color: var(--colour-muted);
    margin-bottom: 1rem;
}

/* --- Tables --- */

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    margin: 1rem 0;
}

th {
    text-align: left;
    font-weight: 600;
    padding: 0.6rem 0.75rem;
    border-bottom: 2px solid var(--colour-border);
    white-space: nowrap;
}

td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--colour-border);
    vertical-align: top;
}

tr:last-child td {
    border-bottom: none;
}

/* --- Rewatch list --- */

.rewatch-participant {
    font-weight: 600;
    margin-top: 1rem;
    margin-bottom: 0.25rem;
}

.rewatch-item {
    margin: 0.2rem 0 0.2rem 1.2rem;
    font-size: 0.9rem;
}

.rewatch-item .timecode {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--colour-muted);
}

.rewatch-item .reason {
    font-style: italic;
    color: var(--colour-frustration);
}

/* --- Source file links --- */

td a {
    color: var(--colour-accent);
    text-decoration: none;
}

td a:hover {
    text-decoration: underline;
}

/* --- Clickable timecodes --- */

a.timecode {
    color: var(--colour-accent);
    font-family: var(--font-mono);
    font-size: 0.8rem;
    text-decoration: none;
    cursor: pointer;
}

a.timecode:hover {
    text-decoration: underline;
}

.rewatch-item a.timecode {
    color: var(--colour-muted);
}

.rewatch-item a.timecode:hover {
    color: var(--colour-accent);
}

/* --- Sentiment histogram --- */

.sentiment-chart {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 0;
    margin: 1.5rem 0;
    min-height: 160px;
}

.sentiment-bar-group {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 3.5rem;
    flex: 0 1 5rem;
}

.sentiment-bar {
    width: 70%;
    border-radius: 3px 3px 0 0;
    min-height: 2px;
}

.sentiment-bar-label {
    font-size: 0.7rem;
    color: var(--colour-muted);
    margin-top: 0.3rem;
    text-align: center;
    line-height: 1.2;
}

.sentiment-bar-count {
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.2rem;
}

.sentiment-divider {
    width: 1px;
    background: var(--colour-border);
    align-self: stretch;
    margin: 0 0.25rem;
}

/* --- Active quote highlight (bidirectional sync) --- */

blockquote.quote-active {
    border-left-color: var(--colour-delight);
    background: #f0fdf4;
    transition: background 0.3s ease, border-left-color 0.3s ease;
}

/* --- Favourite quotes --- */

.quote-group {
    display: flex;
    flex-direction: column;
}

.quote-group blockquote {
    position: relative;
    padding-right: 3rem;
}

.fav-star {
    position: absolute;
    top: 0.65rem;
    right: 0.65rem;
    background: none;
    border: none;
    font-size: 0.8rem;
    color: #e5e7eb;
    cursor: pointer;
    padding: 0.15rem;
    line-height: 1;
    transition: color 0.2s ease;
}

.fav-star:hover {
    color: var(--colour-accent);
}

blockquote.favourited .fav-star {
    color: #999;
}

blockquote.favourited {
    font-weight: 600;
    border-left-color: #999;
}

blockquote.favourited .context,
blockquote.favourited .timecode,
blockquote.favourited .speaker,
blockquote.favourited .badges {
    font-weight: 400;
}

.edit-pencil {
    position: absolute;
    top: 0.65rem;
    right: 2rem;
    background: none;
    border: none;
    font-size: 0.8rem;
    color: #e5e7eb;
    cursor: pointer;
    padding: 0.15rem;
    line-height: 1;
    transition: color 0.2s ease;
}

.edit-pencil:hover {
    color: var(--colour-accent);
}

blockquote.editing .edit-pencil {
    color: var(--colour-accent);
}

blockquote.editing .quote-text {
    background: #fffbe6;
    outline: 1px solid #e5e0c0;
    border-radius: 3px;
    padding: 0.15rem 0.3rem;
    min-width: 10rem;
    cursor: text;
}

.quote-text.edited {
    border-bottom: 1px dashed var(--colour-muted);
}

blockquote.fav-animating {
    transition: transform 0.2s ease;
    z-index: 1;
}

/* --- Toolbar --- */

.toolbar {
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 0.5rem 0;
    background: var(--colour-bg);
    border-bottom: 1px solid var(--colour-border);
    margin-bottom: 0.5rem;
}

.toolbar-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--colour-bg);
    border: 1px solid var(--colour-border);
    border-radius: 6px;
    padding: 0.4rem 0.85rem;
    font-family: var(--font-body);
    font-size: 0.82rem;
    color: var(--colour-text);
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
}

.toolbar-btn:hover {
    background: var(--colour-quote-bg);
    border-color: var(--colour-muted);
}

.toolbar-btn .toolbar-icon {
    font-size: 0.95rem;
    color: var(--colour-muted);
}

/* --- Clipboard toast --- */

.clipboard-toast {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    background: var(--colour-text);
    color: var(--colour-bg);
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    font-size: 0.85rem;
    opacity: 0;
    transform: translateY(0.5rem);
    transition: opacity 0.25s ease, transform 0.25s ease;
    z-index: 200;
    pointer-events: none;
}

.clipboard-toast.show {
    opacity: 1;
    transform: translateY(0);
}

/* --- Print --- */

@media print {
    body { padding: 0; font-size: 11pt; }
    article { max-width: none; }
    h2 { break-before: page; }
    blockquote { break-inside: avoid; }
    table { break-inside: avoid; }
    a.timecode { color: var(--colour-muted); text-decoration: none; cursor: default; }
    .toolbar { display: none; }
    .fav-star { display: none; }
    .edit-pencil { display: none; }
}
"""


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
) -> Path:
    """Generate research_report.html with an external CSS stylesheet.

    Writes ``bristlenose-theme.css`` only if it does not already exist so that
    user customisations are preserved across re-runs.

    Returns:
        Path to the written HTML file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write default CSS on first run, or upgrade if auto-generated v1
    css_path = output_dir / "bristlenose-theme.css"
    _write_css = False
    if not css_path.exists():
        _write_css = True
    else:
        existing = css_path.read_text(encoding="utf-8")
        if _CSS_VERSION not in existing and "bristlenose-theme" in existing:
            # Auto-generated older version — safe to upgrade
            _write_css = True
    if _write_css:
        css_path.write_text(DEFAULT_CSS, encoding="utf-8")
        logger.info("Wrote default theme: %s", css_path)

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
    _w('<html lang="en">')
    _w("<head>")
    _w('<meta charset="utf-8">')
    _w('<meta name="viewport" content="width=device-width, initial-scale=1">')
    _w(f"<title>{_esc(project_name)}</title>")
    _w('<link rel="stylesheet" href="bristlenose-theme.css">')
    _w("</head>")
    _w("<body>")
    _w("<article>")

    # --- Header ---
    _w(f"<h1>{_esc(project_name)}</h1>")
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
        _w("<th>ID</th><th>Session date</th><th>Duration</th><th>Source file</th>")
        _w("</tr></thead>")
        _w("<tbody>")
        for session in sessions:
            duration = _session_duration(session)
            if session.files:
                source_name = _esc(session.files[0].path.name)
                pid = _esc(session.participant_id)
                if video_map and session.participant_id in video_map:
                    source = (
                        f'<a href="#" class="timecode" '
                        f'data-participant="{pid}" '
                        f'data-seconds="0" data-end-seconds="0">'
                        f'{source_name}</a>'
                    )
                else:
                    file_uri = session.files[0].path.resolve().as_uri()
                    source = f'<a href="{file_uri}">{source_name}</a>'
            else:
                source = "&mdash;"
            _w("<tr>")
            _w(f"<td>{_esc(session.participant_id)}</td>")
            _w(f"<td>{session.session_date.strftime('%Y-%m-%d')}</td>")
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
            _w(f'<h3 id="{_esc(anchor)}">{_esc(theme.theme_label)}</h3>')
            if theme.description:
                _w(f'<p class="description">{_esc(theme.description)}</p>')
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
            _w("<h2>User journeys</h2>")
            _w(task_html)
            _w("</section>")
            _w("<hr>")

    # --- Close ---
    _w("</article>")

    # --- Embed JavaScript ---
    _w("<script>")
    if has_media:
        _w(f"var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};")
    else:
        _w("var BRISTLENOSE_VIDEO_MAP = {};")
    _w(_REPORT_JS)
    _w("</script>")

    _w("</body>")
    _w("</html>")

    html_path.write_text("\n".join(parts), encoding="utf-8")
    logger.info("Wrote HTML report: %s", html_path)
    return html_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """HTML-escape user-supplied text."""
    return escape(text)


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
) -> str:
    """Render a single quote as an HTML blockquote."""
    tc = format_timecode(quote.start_timecode)
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
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

    parts.append(
        f"{tc_html} "
        f'<span class="quote-text">\u201c{_esc(quote.text)}\u201d</span> '
        f'<span class="speaker">&mdash; {_esc(quote.participant_id)}</span>'
    )

    badges = _quote_badges(quote)
    if badges:
        parts.append(f'<div class="badges">{badges}</div>')

    parts.append('<button class="edit-pencil" aria-label="Edit this quote">&#9998;</button>')
    parts.append('<button class="fav-star" aria-label="Favourite this quote">&#9733;</button>')
    parts.append("</blockquote>")
    return "\n".join(parts)


def _quote_badges(quote: ExtractedQuote) -> str:
    """Build HTML badge spans for non-default quote metadata."""
    badges: list[str] = []
    if quote.intent != QuoteIntent.NARRATION:
        css_class = f"badge badge-{quote.intent.value}"
        badges.append(f'<span class="{css_class}">{_esc(quote.intent.value)}</span>')
    if quote.emotion != EmotionalTone.NEUTRAL:
        css_class = f"badge badge-{quote.emotion.value}"
        badges.append(f'<span class="{css_class}">{_esc(quote.emotion.value)}</span>')
    if quote.intensity >= 2:
        label = "moderate" if quote.intensity == 2 else "strong"
        badges.append(f'<span class="badge">intensity:{label}</span>')
    return " ".join(badges)


def _build_sentiment_html(quotes: list[ExtractedQuote]) -> str:
    """Build a mirror-reflection sentiment histogram.

    Negative sentiments fan out to the left, positive to the right,
    with the highest counts nearest the centre.
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

    # Colours matching the badge CSS
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
    max_bar_px = 120

    def _bar(label: str, count: int) -> str:
        height = max(4, int((count / max_count) * max_bar_px))
        colour = colour_map.get(label, "var(--colour-muted)")
        return (
            f'<div class="sentiment-bar-group">'
            f'<span class="sentiment-bar-count" style="color:{colour}">{count}</span>'
            f'<div class="sentiment-bar" style="height:{height}px;background:{colour}"></div>'
            f'<span class="sentiment-bar-label">{_esc(label)}</span>'
            f'</div>'
        )

    parts: list[str] = []

    # Negative bars: sorted ascending (smallest at left edge, largest near centre)
    neg_sorted = sorted(neg_counts.items(), key=lambda x: x[1])
    for label, count in neg_sorted:
        parts.append(_bar(label, count))

    # Divider
    parts.append('<div class="sentiment-divider"></div>')

    # Positive bars: sorted descending (largest near centre, smallest at right edge)
    pos_sorted = sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)
    for label, count in pos_sorted:
        parts.append(_bar(label, count))

    return f'<div class="sentiment-chart">{"".join(parts)}</div>'


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
            parts.append(f'<p class="rewatch-participant">{_esc(current_pid)}</p>')
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


_REPORT_JS = """\
(function() {
  // --- Video player ---
  var playerWin = null;

  function seekTo(pid, seconds) {
    var uri = BRISTLENOSE_VIDEO_MAP[pid];
    if (!uri) return;
    var msg = { type: 'bristlenose-seek', pid: pid, src: uri, t: seconds };
    var hash = '#src=' + encodeURIComponent(uri) + '&t=' + seconds
             + '&pid=' + encodeURIComponent(pid);
    if (!playerWin || playerWin.closed) {
      playerWin = window.open('bristlenose-player.html' + hash, 'bristlenose-player',
        'width=720,height=480,resizable=yes,scrollbars=no');
    } else {
      playerWin.postMessage(msg, '*');
      playerWin.focus();
    }
  }

  document.addEventListener('click', function(e) {
    var link = e.target.closest('a.timecode');
    if (!link) return;
    e.preventDefault();
    var pid = link.dataset.participant;
    var seconds = parseFloat(link.dataset.seconds);
    if (pid && !isNaN(seconds)) seekTo(pid, seconds);
  });

  window.bristlenose_onTimeUpdate = function(pid, seconds) {};
  window.bristlenose_scrollToQuote = function(pid, seconds) {};

  // --- Favourite quotes ---
  var FAV_KEY = 'bristlenose-favourites';

  function getFavourites() {
    try { var s = localStorage.getItem(FAV_KEY); return s ? JSON.parse(s) : {}; }
    catch(e) { return {}; }
  }
  function saveFavourites(f) {
    try { localStorage.setItem(FAV_KEY, JSON.stringify(f)); } catch(e) {}
  }

  var favourites = getFavourites();

  // Store original DOM order per group so unfavourited quotes return home
  var originalOrder = {};
  var allGroups = document.querySelectorAll('.quote-group');
  for (var g = 0; g < allGroups.length; g++) {
    var bqs = Array.prototype.slice.call(allGroups[g].querySelectorAll('blockquote'));
    bqs.forEach(function(bq, idx) { originalOrder[bq.id] = idx; });
  }

  function reorderGroup(group, animate) {
    var quotes = Array.prototype.slice.call(group.querySelectorAll('blockquote'));
    if (!quotes.length) return;

    // FIRST — record positions
    var rects = {};
    if (animate) {
      quotes.forEach(function(bq) { rects[bq.id] = bq.getBoundingClientRect(); });
    }

    // Partition: favourited first, non-favourited in original order
    var favs = [], rest = [];
    quotes.forEach(function(bq) {
      (bq.classList.contains('favourited') ? favs : rest).push(bq);
    });
    rest.sort(function(a, b) {
      return (originalOrder[a.id] || 0) - (originalOrder[b.id] || 0);
    });
    favs.concat(rest).forEach(function(bq) { group.appendChild(bq); });

    if (!animate) return;

    // INVERT
    quotes.forEach(function(bq) {
      var old = rects[bq.id];
      var cur = bq.getBoundingClientRect();
      var dy = old.top - cur.top;
      if (Math.abs(dy) < 1) return;
      bq.style.transform = 'translateY(' + dy + 'px)';
      bq.style.transition = 'none';
    });

    // PLAY
    requestAnimationFrame(function() {
      requestAnimationFrame(function() {
        quotes.forEach(function(bq) {
          bq.classList.add('fav-animating');
          bq.style.transform = '';
          bq.style.transition = '';
        });
        setTimeout(function() {
          quotes.forEach(function(bq) { bq.classList.remove('fav-animating'); });
        }, 250);
      });
    });
  }

  // Restore on load
  Object.keys(favourites).forEach(function(qid) {
    var bq = document.getElementById(qid);
    if (bq) bq.classList.add('favourited');
  });
  var groups = document.querySelectorAll('.quote-group');
  for (var i = 0; i < groups.length; i++) reorderGroup(groups[i], false);

  // Star click
  document.addEventListener('click', function(e) {
    var star = e.target.closest('.fav-star');
    if (!star) return;
    e.preventDefault();
    var bq = star.closest('blockquote');
    if (!bq || !bq.id) return;
    var isFav = bq.classList.toggle('favourited');
    if (isFav) { favourites[bq.id] = true; }
    else { delete favourites[bq.id]; }
    saveFavourites(favourites);
    var group = bq.closest('.quote-group');
    if (group) reorderGroup(group, true);
  });

  // --- Inline quote editing ---
  var EDITS_KEY = 'bristlenose-edits';

  function getEdits() {
    try { var s = localStorage.getItem(EDITS_KEY); return s ? JSON.parse(s) : {}; }
    catch(e) { return {}; }
  }
  function saveEdits(edits) {
    try { localStorage.setItem(EDITS_KEY, JSON.stringify(edits)); } catch(e) {}
  }

  var edits = getEdits();

  // Restore edits on load
  Object.keys(edits).forEach(function(qid) {
    var bq = document.getElementById(qid);
    if (!bq) return;
    var span = bq.querySelector('.quote-text');
    if (!span) return;
    span.textContent = '\\u201c' + edits[qid] + '\\u201d';
    span.classList.add('edited');
  });

  var activeEdit = null; // { bq, span, original }

  function startEdit(bq) {
    if (activeEdit) cancelEdit();
    var span = bq.querySelector('.quote-text');
    if (!span) return;
    var raw = span.textContent.replace(/^[\\u201c\\u201d"]+|[\\u201c\\u201d"]+$/g, '').trim();
    activeEdit = { bq: bq, span: span, original: raw };
    bq.classList.add('editing');
    span.setAttribute('contenteditable', 'true');
    span.textContent = raw;
    span.focus();
    // Select all text
    var range = document.createRange();
    range.selectNodeContents(span);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function cancelEdit() {
    if (!activeEdit) return;
    var ae = activeEdit;
    activeEdit = null;
    ae.bq.classList.remove('editing');
    ae.span.removeAttribute('contenteditable');
    // Restore: if there was a saved edit use that, otherwise the original
    var qid = ae.bq.id;
    var saved = edits[qid];
    var text = saved !== undefined ? saved : ae.original;
    ae.span.textContent = '\\u201c' + text + '\\u201d';
    if (saved !== undefined) ae.span.classList.add('edited');
  }

  function acceptEdit() {
    if (!activeEdit) return;
    var ae = activeEdit;
    activeEdit = null;
    ae.bq.classList.remove('editing');
    ae.span.removeAttribute('contenteditable');
    var newText = ae.span.textContent.trim();
    ae.span.textContent = '\\u201c' + newText + '\\u201d';
    if (newText !== ae.original) {
      edits[ae.bq.id] = newText;
      ae.span.classList.add('edited');
      saveEdits(edits);
    }
  }

  // Pencil click
  document.addEventListener('click', function(e) {
    var pencil = e.target.closest('.edit-pencil');
    if (!pencil) return;
    e.preventDefault();
    var bq = pencil.closest('blockquote');
    if (!bq) return;
    if (bq.classList.contains('editing')) {
      cancelEdit();
    } else {
      startEdit(bq);
    }
  });

  // Keyboard: Enter to accept, Esc to cancel
  document.addEventListener('keydown', function(e) {
    if (!activeEdit) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelEdit();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      acceptEdit();
    }
  });

  // Click outside to accept
  document.addEventListener('click', function(e) {
    if (!activeEdit) return;
    if (!activeEdit.bq.contains(e.target)) {
      acceptEdit();
    }
  });

  // --- CSV export ---
  function getSection(bq) {
    var el = bq.closest('.quote-group');
    while (el) {
      el = el.previousElementSibling;
      if (el && el.tagName === 'H3') return el.textContent.trim();
    }
    return '';
  }

  function getQuoteText(bq) {
    var span = bq.querySelector('.quote-text');
    if (span) {
      return span.textContent.replace(/^[\\u201c\\u201d"]+|[\\u201c\\u201d"]+$/g, '').trim();
    }
    var clone = bq.cloneNode(true);
    var rm = clone.querySelectorAll('.context, .timecode, a.timecode, .speaker, .badges, .fav-star, .edit-pencil');
    for (var i = 0; i < rm.length; i++) rm[i].remove();
    var t = clone.textContent.trim();
    return t.replace(/^[\\u201c\\u201d"]+|[\\u201c\\u201d"]+$/g, '').trim();
  }

  function csvEsc(v) {
    v = String(v);
    if (v.indexOf('"') !== -1 || v.indexOf(',') !== -1 || v.indexOf('\\n') !== -1) {
      return '"' + v.replace(/"/g, '""') + '"';
    }
    return v;
  }

  function buildCsv(onlyFavs) {
    var rows = ['Timecode,Quote,Participant,Section,Emotion,Intent'];
    var bqs = document.querySelectorAll('.quote-group blockquote');
    for (var i = 0; i < bqs.length; i++) {
      var bq = bqs[i];
      if (onlyFavs && !bq.classList.contains('favourited')) continue;
      rows.push([
        csvEsc(bq.getAttribute('data-timecode') || ''),
        csvEsc(getQuoteText(bq)),
        csvEsc(bq.getAttribute('data-participant') || ''),
        csvEsc(getSection(bq)),
        csvEsc(bq.getAttribute('data-emotion') || ''),
        csvEsc(bq.getAttribute('data-intent') || '')
      ].join(','));
    }
    return rows.join('\\n');
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    return ok ? Promise.resolve() : Promise.reject();
  }

  function showToast(msg) {
    var old = document.querySelector('.clipboard-toast');
    if (old) old.remove();
    var t = document.createElement('div');
    t.className = 'clipboard-toast';
    t.textContent = msg;
    document.body.appendChild(t);
    t.offsetHeight;
    t.classList.add('show');
    setTimeout(function() {
      t.classList.remove('show');
      setTimeout(function() { t.remove(); }, 300);
    }, 2000);
  }

  document.addEventListener('click', function(e) {
    var btn = e.target.closest('#export-favourites');
    if (btn) {
      var csv = buildCsv(true);
      var n = csv.split('\\n').length - 1;
      if (n === 0) { showToast('No favourites to export'); return; }
      copyToClipboard(csv).then(
        function() { showToast(n + ' favourite' + (n !== 1 ? 's' : '') + ' copied as CSV'); },
        function() { showToast('Could not copy to clipboard'); }
      );
      return;
    }
    btn = e.target.closest('#export-all');
    if (btn) {
      var csv = buildCsv(false);
      var n = csv.split('\\n').length - 1;
      copyToClipboard(csv).then(
        function() { showToast(n + ' quote' + (n !== 1 ? 's' : '') + ' copied as CSV'); },
        function() { showToast('Could not copy to clipboard'); }
      );
    }
  });
})();
"""


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
