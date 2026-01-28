"""Stage 12b: Render the research report as styled HTML with external CSS."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

from gourani.models import (
    EmotionalTone,
    ExtractedQuote,
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

DEFAULT_CSS = """\
/* gourani-theme.css — default research report theme */
/* Edit freely; Gourani will not overwrite this file once created. */

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

/* --- Quotes --- */

blockquote {
    background: var(--colour-quote-bg);
    border-left: 3px solid var(--colour-accent);
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
    font-style: italic;
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

/* --- Print --- */

@media print {
    body { padding: 0; font-size: 11pt; }
    article { max-width: none; }
    h2 { break-before: page; }
    blockquote { break-inside: avoid; }
    table { break-inside: avoid; }
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
    """Generate research_quotes.html with an external CSS stylesheet.

    Writes ``gourani-theme.css`` only if it does not already exist so that
    user customisations are preserved across re-runs.

    Returns:
        Path to the written HTML file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write default CSS only on first run
    css_path = output_dir / "gourani-theme.css"
    if not css_path.exists():
        css_path.write_text(DEFAULT_CSS, encoding="utf-8")
        logger.info("Wrote default theme: %s", css_path)

    html_path = output_dir / "research_quotes.html"

    parts: list[str] = []
    _w = parts.append

    # --- Document shell ---
    _w("<!DOCTYPE html>")
    _w('<html lang="en">')
    _w("<head>")
    _w('<meta charset="utf-8">')
    _w('<meta name="viewport" content="width=device-width, initial-scale=1">')
    _w(f"<title>Research Quotes: {_esc(project_name)}</title>")
    _w('<link rel="stylesheet" href="gourani-theme.css">')
    _w("</head>")
    _w("<body>")
    _w("<article>")

    # --- Header ---
    _w(f"<h1>Research Quotes: {_esc(project_name)}</h1>")
    _w('<div class="meta">')
    _w(f"<p>Generated: {datetime.now().strftime('%Y-%m-%d')}</p>")
    _w(f"<p>Participants: {len(sessions)} ({_esc(_participant_range(sessions))})</p>")
    _w(f"<p>Sessions processed: {len(sessions)}</p>")
    _w("</div>")

    # --- Screen-Specific Findings ---
    if screen_clusters:
        _w("<section>")
        _w("<h2>Screen-Specific Findings</h2>")
        for i, cluster in enumerate(screen_clusters, start=1):
            _w(f"<h3>{i}. {_esc(cluster.screen_label)}</h3>")
            if cluster.description:
                _w(f'<p class="description">{_esc(cluster.description)}</p>')
            for quote in cluster.quotes:
                _w(_format_quote_html(quote))
        _w("</section>")
        _w("<hr>")

    # --- Contextual Themes ---
    if theme_groups:
        _w("<section>")
        _w("<h2>Contextual Themes</h2>")
        for theme in theme_groups:
            _w(f"<h3>Theme: {_esc(theme.theme_label)}</h3>")
            if theme.description:
                _w(f'<p class="description">{_esc(theme.description)}</p>')
            for quote in theme.quotes:
                _w(_format_quote_html(quote))
        _w("</section>")
        _w("<hr>")

    # --- Rewatch List ---
    if all_quotes:
        rewatch = _build_rewatch_html(all_quotes)
        if rewatch:
            _w("<section>")
            _w("<h2>Rewatch List</h2>")
            _w(
                '<p class="description">Moments flagged for researcher review '
                "&mdash; confusion, frustration, or error-recovery detected.</p>"
            )
            _w(rewatch)
            _w("</section>")
            _w("<hr>")

    # --- Task Outcome Summary ---
    if all_quotes and sessions:
        task_html = _build_task_outcome_html(all_quotes, sessions)
        if task_html:
            _w("<section>")
            _w("<h2>Task Outcome Summary</h2>")
            _w(task_html)
            _w("</section>")
            _w("<hr>")

    # --- Appendix: Participant Summary ---
    _w("<section>")
    _w("<h2>Appendix: Participant Summary</h2>")
    _w("<table>")
    _w("<thead><tr>")
    _w("<th>ID</th><th>Session Date</th><th>Duration</th><th>Source File</th>")
    _w("</tr></thead>")
    _w("<tbody>")
    for session in sessions:
        duration = _session_duration(session)
        source = _esc(session.files[0].path.name) if session.files else "&mdash;"
        _w("<tr>")
        _w(f"<td>{_esc(session.participant_id)}</td>")
        _w(f"<td>{session.session_date.strftime('%Y-%m-%d')}</td>")
        _w(f"<td>{duration}</td>")
        _w(f"<td>{source}</td>")
        _w("</tr>")
    _w("</tbody>")
    _w("</table>")
    _w("</section>")

    # --- Close ---
    _w("</article>")
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


def _format_quote_html(quote: ExtractedQuote) -> str:
    """Render a single quote as an HTML blockquote."""
    tc = format_timecode(quote.start_timecode)
    parts: list[str] = ["<blockquote>"]

    if quote.researcher_context:
        parts.append(f'<span class="context">[{_esc(quote.researcher_context)}]</span>')

    parts.append(
        f'<span class="timecode">[{tc}]</span> '
        f"\u201c{_esc(quote.text)}\u201d "
        f'<span class="speaker">&mdash; {_esc(quote.participant_id)}</span>'
    )

    badges = _quote_badges(quote)
    if badges:
        parts.append(f'<div class="badges">{badges}</div>')

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


def _build_rewatch_html(quotes: list[ExtractedQuote]) -> str:
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
        parts.append(
            f'<p class="rewatch-item">'
            f'<span class="timecode">[{tc}]</span> '
            f'<span class="reason">{_esc(reason)}</span> '
            f"&mdash; \u201c{_esc(snippet)}\u201d"
            f"</p>"
        )
    return "\n".join(parts)


def _build_task_outcome_html(
    quotes: list[ExtractedQuote],
    sessions: list[InputSession],
) -> str:
    """Build the task outcome summary as an HTML table."""
    STAGE_ORDER = [
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
        "<th>Journey Stages Observed</th>"
        "<th>Furthest Stage</th>"
        "<th>Friction Points</th>"
    )
    rows.append("</tr></thead>")
    rows.append("<tbody>")

    for pid in sorted(by_participant.keys()):
        pq = by_participant[pid]
        stage_counts = Counter(q.journey_stage for q in pq)

        observed = [s for s in STAGE_ORDER if stage_counts.get(s, 0) > 0]
        if not observed:
            observed_str = "other"
            furthest = "&mdash;"
        else:
            observed_str = " &rarr; ".join(s.value for s in observed)
            furthest = observed[-1].value

        friction = sum(
            1
            for q in pq
            if q.intent in (QuoteIntent.CONFUSION, QuoteIntent.FRUSTRATION)
            or q.emotion in (EmotionalTone.FRUSTRATED, EmotionalTone.CONFUSED)
        )

        rows.append("<tr>")
        rows.append(f"<td>{_esc(pid)}</td>")
        rows.append(f"<td>{observed_str}</td>")
        rows.append(f"<td>{furthest}</td>")
        rows.append(f"<td>{friction}</td>")
        rows.append("</tr>")

    rows.append("</tbody>")
    rows.append("</table>")
    return "\n".join(rows)
