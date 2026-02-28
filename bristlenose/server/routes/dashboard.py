"""Dashboard API endpoint — stats, featured quotes, nav lists, coverage."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    Person,
    Project,
    Quote,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    ThemeGroup,
    TranscriptSegment,
)
from bristlenose.server.models import Session as SessionModel

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Sentiment constants (mirrors render_html.py)
# ---------------------------------------------------------------------------

_NEGATIVE_SENTIMENTS = {"frustration", "confusion", "doubt"}
_POSITIVE_SENTIMENTS = {"satisfaction", "confidence", "delight"}

# Sentiment order for the sparkline (positive → negative, matching render_html)
_SENTIMENT_ORDER = [
    "satisfaction", "delight", "confidence", "surprise",
    "doubt", "confusion", "frustration",
]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class StatsResponse(BaseModel):
    """Dashboard stat card counts."""

    session_count: int
    total_duration_seconds: float
    total_duration_human: str
    total_words: int
    quotes_count: int
    sections_count: int
    themes_count: int
    ai_tags_count: int
    user_tags_count: int


class DashboardSpeakerResponse(BaseModel):
    """A speaker in a dashboard session row."""

    speaker_code: str
    name: str
    role: str


class DashboardSessionResponse(BaseModel):
    """A compact session row for the dashboard table."""

    session_id: str
    session_number: int
    session_date: str | None
    duration_seconds: float
    duration_human: str
    speakers: list[DashboardSpeakerResponse]
    source_filename: str
    has_media: bool
    sentiment_counts: dict[str, int]


class FeaturedQuoteResponse(BaseModel):
    """A featured quote for the dashboard carousel."""

    dom_id: str
    text: str
    participant_id: str
    session_id: str
    speaker_name: str
    start_timecode: float
    end_timecode: float
    sentiment: str | None
    intensity: int
    researcher_context: str | None
    rank: int
    has_media: bool
    is_starred: bool
    is_hidden: bool


class NavItem(BaseModel):
    """A section or theme navigation entry."""

    label: str
    anchor: str


class OmittedSegmentResponse(BaseModel):
    """A transcript segment that wasn't extracted as a quote."""

    speaker_code: str
    start_time: float
    text: str
    session_id: str  # string session ID for navigateToSession()


class SessionOmittedResponse(BaseModel):
    """Omitted content for one session."""

    session_number: int
    session_id: str
    full_segments: list[OmittedSegmentResponse]
    fragments_html: str  # pre-formatted "Okay. (4×), Yeah. (2×)"


class CoverageResponse(BaseModel):
    """Transcript coverage statistics for the dashboard."""

    pct_in_report: int
    pct_moderator: int
    pct_omitted: int
    omitted_by_session: list[SessionOmittedResponse]


class DashboardResponse(BaseModel):
    """Full response for the dashboard endpoint."""

    stats: StatsResponse
    sessions: list[DashboardSessionResponse]
    featured_quotes: list[FeaturedQuoteResponse]
    sections: list[NavItem]
    themes: list[NavItem]
    moderator_header: str
    observer_header: str
    coverage: CoverageResponse | None


class ProjectInfoResponse(BaseModel):
    """Lightweight project info for the report header."""

    project_name: str
    session_count: int
    participant_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    """Get the database session from app state."""
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    """Return the project or raise 404."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _quote_dom_id(quote: Quote) -> str:
    """Build the DOM ID for a quote (matches render_html.py format)."""
    return f"q-{quote.participant_id}-{int(quote.start_timecode)}"


def _format_duration_human(seconds: float) -> str:
    """Format seconds as a human-readable duration (e.g. '1h 23m', '4m')."""
    if seconds <= 0:
        return "0m"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m" if m > 0 else f"{h}h"
    return f"{m}m" if m > 0 else "<1m"


def _speaker_sort_key(sp: SessionSpeaker) -> tuple[int, int]:
    """Sort speakers: moderators first, then participants, then observers."""
    prefix_order = {"m": 0, "p": 1, "o": 2}
    code = sp.speaker_code
    prefix = prefix_order.get(code[0], 3) if code else 3
    num = int(code[1:]) if len(code) > 1 and code[1:].isdigit() else 0
    return (prefix, num)


def _aggregate_sentiments(
    db: Session,
    project_id: int,
) -> dict[str, dict[str, int]]:
    """Aggregate sentiment counts by session_id."""
    quotes = db.query(Quote).filter_by(project_id=project_id).all()
    result: dict[str, dict[str, int]] = {}
    for q in quotes:
        if q.sentiment:
            if q.session_id not in result:
                result[q.session_id] = {}
            result[q.session_id][q.sentiment] = (
                result[q.session_id].get(q.sentiment, 0) + 1
            )
    return result


def _resolve_speaker_names(
    db: Session, project_id: int,
) -> dict[tuple[str, str], str]:
    """Build (session_id_str, speaker_code) -> display name map."""
    sessions = (
        db.query(SessionModel)
        .filter_by(project_id=project_id)
        .all()
    )
    result: dict[tuple[str, str], str] = {}
    for sess in sessions:
        for sp in sess.session_speakers:
            person = db.get(Person, sp.person_id)
            name = ""
            if person:
                name = person.short_name or person.full_name or ""
            result[(sess.session_id, sp.speaker_code)] = name
    return result


def _pick_featured_quotes(
    all_quotes: list[Quote],
    n: int = 9,
) -> list[Quote]:
    """Select the most interesting quotes for the dashboard.

    Port of _pick_featured_quotes() from render_html.py.
    Word-count filter → score → diversify by participant and polarity.
    """
    if not all_quotes:
        return []

    # Filter: prefer quotes between 12–33 words.
    preferred = [q for q in all_quotes if 12 <= len(q.text.split()) <= 33]
    if len(preferred) >= n:
        candidates = preferred
    else:
        longer = [
            q for q in all_quotes
            if len(q.text.split()) >= 12 and q not in preferred
        ]
        candidates = preferred + longer
    if not candidates:
        candidates = list(all_quotes)

    def _score(q: Quote) -> float:
        s = 0.0
        s += min(q.intensity, 3)
        if q.sentiment in _NEGATIVE_SENTIMENTS:
            s += 2
        elif q.sentiment == "surprise":
            s += 2
        elif q.sentiment == "delight":
            s += 2
        elif q.sentiment in _POSITIVE_SENTIMENTS:
            s += 1
        if q.researcher_context:
            s += 1
        word_count = len(q.text.split())
        if word_count > 33:
            s -= min((word_count - 33) / 10, 2.0)
        return s

    scored = sorted(
        candidates,
        key=lambda q: (-_score(q), q.start_timecode),
    )

    picked: list[Quote] = []
    used_pids: set[str] = set()
    used_polarities: set[str] = set()

    def _polarity(q: Quote) -> str:
        if q.sentiment in _POSITIVE_SENTIMENTS:
            return "positive"
        if q.sentiment in _NEGATIVE_SENTIMENTS:
            return "negative"
        if q.sentiment == "surprise":
            return "surprise"
        return "neutral"

    # Pass 1: one per participant, different polarities.
    for q in scored:
        if len(picked) >= n:
            break
        pid = q.participant_id
        pol = _polarity(q)
        if pid not in used_pids and pol not in used_polarities:
            picked.append(q)
            used_pids.add(pid)
            used_polarities.add(pol)

    # Pass 2: relax polarity, still different participants.
    if len(picked) < n:
        for q in scored:
            if len(picked) >= n:
                break
            if q in picked:
                continue
            if q.participant_id not in used_pids:
                picked.append(q)
                used_pids.add(q.participant_id)

    # Pass 3: relax all constraints.
    if len(picked) < n:
        for q in scored:
            if len(picked) >= n:
                break
            if q not in picked:
                picked.append(q)

    return picked[:n]


# ---------------------------------------------------------------------------
# Coverage calculation
# ---------------------------------------------------------------------------

# Segments with this many words or fewer are collapsed into fragment summaries.
# Matches FRAGMENT_THRESHOLD in bristlenose/coverage.py.
_FRAGMENT_THRESHOLD = 3


def _is_moderator_code(code: str) -> bool:
    """Check if a speaker code is moderator or observer (not participant)."""
    return code.startswith("m") or code.startswith("o")


def _format_fragments_html(fragment_counts: list[tuple[str, int]]) -> str:
    """Format fragment counts as HTML for the frontend.

    Returns e.g. '<span class="label">Also omitted: </span><span class="verbatim">Okay.</span>
    (4×), <span class="verbatim">Yeah.</span> (2×)'
    """
    if not fragment_counts:
        return ""
    parts: list[str] = []
    for text, count in fragment_counts:
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if count > 1:
            parts.append(f'<span class="verbatim">{escaped}</span> ({count}×)')
        else:
            parts.append(f'<span class="verbatim">{escaped}</span>')
    joined = ", ".join(parts)
    return f'<span class="label">Also omitted: </span>{joined}'


def _calculate_coverage(
    db: Session,
    project_id: int,
    sessions: list[SessionModel],
) -> CoverageResponse | None:
    """Calculate transcript coverage from the database.

    Mirrors the algorithm in bristlenose/coverage.py but operates on
    SQLAlchemy models instead of pipeline dataclasses.
    """
    if not sessions:
        return None

    # Build session lookup: int PK → (string session_id, session_number)
    session_map: dict[int, tuple[str, int]] = {
        s.id: (s.session_id, s.session_number) for s in sessions
    }
    session_pks = list(session_map.keys())

    # Load all transcript segments for this project
    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.session_id.in_(session_pks))
        .order_by(TranscriptSegment.session_id, TranscriptSegment.start_time)
        .all()
    )
    if not segments:
        return None

    # Load all quotes and build coverage ranges: string_session_id → [(start, end)]
    quotes = db.query(Quote).filter_by(project_id=project_id).all()
    quote_ranges: dict[str, list[tuple[float, float]]] = {}
    for q in quotes:
        quote_ranges.setdefault(q.session_id, []).append(
            (q.start_timecode, q.end_timecode)
        )

    # Walk segments
    participant_words_total = 0
    participant_words_in_quotes = 0
    moderator_words_total = 0
    # string_session_id → list of (speaker_code, start_time, text, word_count)
    omitted_raw: dict[str, list[tuple[str, float, str, int]]] = {}

    for seg in segments:
        info = session_map.get(seg.session_id)
        if not info:
            continue
        str_sid = info[0]
        code = seg.speaker_code
        text = seg.text
        wc = len(text.split())

        if _is_moderator_code(code):
            moderator_words_total += wc
        else:
            # Participant (or unknown code — treat as participant)
            participant_words_total += wc
            ranges = quote_ranges.get(str_sid, [])
            is_covered = any(
                start <= seg.start_time <= end for start, end in ranges
            )
            if is_covered:
                participant_words_in_quotes += wc
            else:
                omitted_raw.setdefault(str_sid, []).append(
                    (code, seg.start_time, text, wc)
                )

    # Percentages
    total_words = participant_words_total + moderator_words_total
    if total_words > 0:
        pct_in_report = round(100 * participant_words_in_quotes / total_words)
        pct_moderator = round(100 * moderator_words_total / total_words)
        pct_omitted = round(
            100 * (participant_words_total - participant_words_in_quotes) / total_words
        )
    else:
        pct_in_report = 0
        pct_moderator = 0
        pct_omitted = 0

    # Build per-session omitted with fragment collapsing
    # Sort by session number for stable output
    str_sid_to_num: dict[str, int] = {
        s.session_id: s.session_number for s in sessions
    }
    sorted_sids = sorted(
        omitted_raw.keys(),
        key=lambda sid: str_sid_to_num.get(sid, 0),
    )

    omitted_sessions: list[SessionOmittedResponse] = []
    for str_sid in sorted_sids:
        raw = omitted_raw[str_sid]
        full_segs: list[OmittedSegmentResponse] = []
        fragments: list[str] = []

        for code, start_time, text, wc in raw:
            if wc > _FRAGMENT_THRESHOLD:
                full_segs.append(OmittedSegmentResponse(
                    speaker_code=code,
                    start_time=start_time,
                    text=text,
                    session_id=str_sid,
                ))
            else:
                fragments.append(text)

        fragment_counts = Counter(fragments).most_common()
        frags_html = _format_fragments_html(fragment_counts)

        # Skip sessions with nothing omitted
        if not full_segs and not fragment_counts:
            continue

        # Prepend "Also omitted:" label only when there are full segments above
        if full_segs and fragment_counts:
            pass  # _format_fragments_html already includes the label
        elif not full_segs and fragment_counts:
            # Fragments only — no "Also omitted:" prefix, just the verbatim list
            parts: list[str] = []
            for text_frag, count in fragment_counts:
                escaped = (
                    text_frag.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                if count > 1:
                    parts.append(
                        f'<span class="verbatim">{escaped}</span> ({count}×)'
                    )
                else:
                    parts.append(f'<span class="verbatim">{escaped}</span>')
            frags_html = ", ".join(parts)

        omitted_sessions.append(SessionOmittedResponse(
            session_number=str_sid_to_num.get(str_sid, 0),
            session_id=str_sid,
            full_segments=full_segs,
            fragments_html=frags_html,
        ))

    return CoverageResponse(
        pct_in_report=pct_in_report,
        pct_moderator=pct_moderator,
        pct_omitted=pct_omitted,
        omitted_by_session=omitted_sessions,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/dashboard", response_model=DashboardResponse,
)
def get_dashboard(
    project_id: int,
    request: Request,
) -> DashboardResponse:
    """Return all data needed by the Project tab dashboard."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # --- Sessions ---
        sessions = (
            db.query(SessionModel)
            .filter_by(project_id=project_id)
            .order_by(SessionModel.session_number)
            .all()
        )

        sentiment_by_session = _aggregate_sentiments(db, project_id)

        # --- Build session rows ---
        all_moderator_names: list[str] = []
        all_observer_names: list[str] = []

        session_rows: list[DashboardSessionResponse] = []
        total_duration_s = 0.0
        total_words = 0

        for sess in sessions:
            total_duration_s += sess.duration_seconds

            speakers_data: list[DashboardSpeakerResponse] = []
            for sp in sorted(sess.session_speakers, key=_speaker_sort_key):
                person = db.get(Person, sp.person_id)
                name = ""
                if person:
                    name = person.short_name or person.full_name or ""

                speakers_data.append(
                    DashboardSpeakerResponse(
                        speaker_code=sp.speaker_code,
                        name=name,
                        role=sp.speaker_role,
                    )
                )

                total_words += sp.words_spoken

                if sp.speaker_role == "researcher" and name:
                    if name not in all_moderator_names:
                        all_moderator_names.append(name)
                elif sp.speaker_role == "observer" and name:
                    if name not in all_observer_names:
                        all_observer_names.append(name)

            # Source filename: first source file's name, or empty.
            source_filename = ""
            if sess.source_files:
                from pathlib import Path as _Path
                source_filename = _Path(sess.source_files[0].path).name

            sentiment_counts = sentiment_by_session.get(sess.session_id, {})

            session_rows.append(
                DashboardSessionResponse(
                    session_id=sess.session_id,
                    session_number=sess.session_number,
                    session_date=(
                        sess.session_date.isoformat() if sess.session_date else None
                    ),
                    duration_seconds=sess.duration_seconds,
                    duration_human=_format_duration_human(sess.duration_seconds),
                    speakers=speakers_data,
                    source_filename=source_filename,
                    has_media=sess.has_media,
                    sentiment_counts=sentiment_counts,
                )
            )

        # --- Quotes (all, for stats + featured selection) ---
        all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
        n_quotes = len(all_quotes)
        n_ai_tagged = sum(1 for q in all_quotes if q.sentiment is not None)

        # User tags count.
        n_user_tags = (
            db.query(QuoteTag)
            .join(Quote, QuoteTag.quote_id == Quote.id)
            .filter(Quote.project_id == project_id)
            .count()
        )

        # --- Featured quotes ---
        featured = _pick_featured_quotes(all_quotes, n=9)
        speaker_names = _resolve_speaker_names(db, project_id)

        # Batch load starred/hidden state for featured quotes.
        featured_ids = [q.id for q in featured]
        states = (
            db.query(QuoteState)
            .filter(QuoteState.quote_id.in_(featured_ids))
            .all()
        ) if featured_ids else []
        state_by_qid: dict[int, QuoteState] = {s.quote_id: s for s in states}

        featured_responses: list[FeaturedQuoteResponse] = []
        for rank, q in enumerate(featured):
            state = state_by_qid.get(q.id)
            display_name = speaker_names.get((q.session_id, q.participant_id), "")
            if not display_name:
                display_name = q.participant_id

            featured_responses.append(
                FeaturedQuoteResponse(
                    dom_id=_quote_dom_id(q),
                    text=q.text,
                    participant_id=q.participant_id,
                    session_id=q.session_id,
                    speaker_name=display_name,
                    start_timecode=q.start_timecode,
                    end_timecode=q.end_timecode,
                    sentiment=q.sentiment,
                    intensity=q.intensity,
                    researcher_context=q.researcher_context,
                    rank=rank,
                    has_media=any(
                        s.has_media
                        for s in sessions
                        if s.session_id == q.session_id
                    ),
                    is_starred=bool(state and state.is_starred),
                    is_hidden=bool(state and state.is_hidden),
                )
            )

        # --- Sections and themes (nav items) ---
        screen_clusters = (
            db.query(ScreenCluster)
            .filter_by(project_id=project_id)
            .order_by(ScreenCluster.display_order)
            .all()
        )
        theme_groups = (
            db.query(ThemeGroup)
            .filter_by(project_id=project_id)
            .order_by(ThemeGroup.id)
            .all()
        )

        sections = [
            NavItem(
                label=c.screen_label,
                anchor=f"section-{c.screen_label.lower().replace(' ', '-')}",
            )
            for c in screen_clusters
        ]
        themes = [
            NavItem(
                label=t.theme_label,
                anchor=f"theme-{t.theme_label.lower().replace(' ', '-')}",
            )
            for t in theme_groups
        ]

        # --- Moderator/observer headers ---
        mod_header = ""
        if all_moderator_names:
            names_str = ", ".join(all_moderator_names)
            mod_header = f"Moderated by {names_str}"
        obs_header = ""
        if all_observer_names:
            names_str = ", ".join(all_observer_names)
            label = "Observer" if len(all_observer_names) == 1 else "Observers"
            obs_header = f"{label}: {names_str}"

        # --- Coverage ---
        coverage = _calculate_coverage(db, project_id, sessions)

        return DashboardResponse(
            stats=StatsResponse(
                session_count=len(sessions),
                total_duration_seconds=total_duration_s,
                total_duration_human=_format_duration_human(total_duration_s),
                total_words=total_words,
                quotes_count=n_quotes,
                sections_count=len(screen_clusters),
                themes_count=len(theme_groups),
                ai_tags_count=n_ai_tagged,
                user_tags_count=n_user_tags,
            ),
            sessions=session_rows,
            featured_quotes=featured_responses,
            sections=sections,
            themes=themes,
            moderator_header=mod_header,
            observer_header=obs_header,
            coverage=coverage,
        )
    finally:
        db.close()


@router.get(
    "/projects/{project_id}/info", response_model=ProjectInfoResponse,
)
def get_project_info(
    project_id: int,
    request: Request,
) -> ProjectInfoResponse:
    """Return lightweight project metadata for the report header."""
    db = _get_db(request)
    try:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        session_count = (
            db.query(SessionModel).filter_by(project_id=project_id).count()
        )
        # Count distinct participant speaker codes (p1, p2, ...)
        participant_codes = (
            db.query(SessionSpeaker.speaker_code)
            .join(SessionModel, SessionSpeaker.session_id == SessionModel.id)
            .filter(
                SessionModel.project_id == project_id,
                SessionSpeaker.speaker_code.startswith("p"),
            )
            .distinct()
            .count()
        )

        return ProjectInfoResponse(
            project_name=project.name,
            session_count=session_count,
            participant_count=participant_codes,
        )
    finally:
        db.close()
