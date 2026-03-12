"""Dashboard / Project tab — session table, featured quotes, journeys, coverage."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from bristlenose.coverage import CoverageStats
from bristlenose.models import (
    ExtractedQuote,
    FullTranscript,
    InputSession,
    PeopleFile,
    ScreenCluster,
    Sentiment,
    ThemeGroup,
)
from bristlenose.stages.render.html_helpers import (
    _display_name,
    _esc,
    _resolve_speaker_name,
    _session_anchor,
    _session_duration,
    _session_sort_key,
    _split_badge_html,
    _timecode_html,
)
from bristlenose.stages.render.sentiment import _render_sentiment_sparkline
from bristlenose.stages.render.theme_assets import _jinja_env
from bristlenose.utils.markdown import format_finder_date, format_finder_filename
from bristlenose.utils.timecodes import format_duration_human

logger = logging.getLogger(__name__)

# Feature flag: show thumbnail placeholders for all sessions (even VTT-only).
# Set BRISTLENOSE_FAKE_THUMBNAILS=1 to enable — useful for layout testing.
_FAKE_THUMBNAILS = os.environ.get("BRISTLENOSE_FAKE_THUMBNAILS", "") == "1"


# ---------------------------------------------------------------------------
# Session table rows
# ---------------------------------------------------------------------------


def _build_session_rows(
    sessions: list[InputSession],
    people: PeopleFile | None,
    display_names: dict[str, str] | None,
    video_map: dict[str, str] | None,
    now: datetime,
    screen_clusters: list[ScreenCluster] | None = None,
    all_quotes: list[ExtractedQuote] | None = None,
    thumbnail_map: dict[str, str] | None = None,
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
        moderator_parts.append(
            _split_badge_html(code, name if name != code else None)
        )
    if moderator_parts:
        moderator_header = "Moderated by " + _oxford_list_html(moderator_parts)
    else:
        moderator_header = ""

    # Build observer header HTML (only if observers present).
    observer_parts: list[str] = []
    for code in all_observer_codes:
        name = _resolve_speaker_name(code, people, display_names)
        observer_parts.append(
            _split_badge_html(code, name if name != code else None)
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
            "thumbnail_url": (thumbnail_map or {}).get(sid, ""),
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


# ---------------------------------------------------------------------------
# Featured quotes
# ---------------------------------------------------------------------------

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

    # Speaker badge → navigates to Sessions tab on card click.
    pid_esc, sid_esc, anchor = _session_anchor(quote)
    name = _display_name(quote.participant_id, display_names)
    speaker_badge = _split_badge_html(
        quote.participant_id,
        name if name != quote.participant_id else None,
        nav_session=sid_esc,
        nav_anchor=anchor,
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


# ---------------------------------------------------------------------------
# Project tab (dashboard)
# ---------------------------------------------------------------------------


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

    _w('<!-- bn-dashboard -->')
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
    _w('<!-- /bn-dashboard -->')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# User journeys
# ---------------------------------------------------------------------------


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
            "pid": _split_badge_html(pid, name if name != pid else None),
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
