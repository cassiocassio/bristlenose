"""Dashboard API endpoint — stats, featured quotes, nav lists."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    ClusterQuote,
    Person,
    Project,
    Quote,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    ThemeGroup,
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


class DashboardResponse(BaseModel):
    """Full response for the dashboard endpoint."""

    stats: StatsResponse
    sessions: list[DashboardSessionResponse]
    featured_quotes: list[FeaturedQuoteResponse]
    sections: list[NavItem]
    themes: list[NavItem]
    moderator_header: str
    observer_header: str


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


def _derive_journeys(
    db: Session,
    project_id: int,
) -> dict[str, list[str]]:
    """Derive per-participant journey labels from screen clusters."""
    clusters = (
        db.query(ScreenCluster)
        .filter_by(project_id=project_id)
        .order_by(ScreenCluster.display_order)
        .all()
    )

    participant_screens: dict[str, list[str]] = {}
    for cluster in clusters:
        cqs = db.query(ClusterQuote).filter_by(cluster_id=cluster.id).all()
        quote_ids = [cq.quote_id for cq in cqs]
        if not quote_ids:
            continue

        quotes = db.query(Quote).filter(Quote.id.in_(quote_ids)).all()
        pids_in_cluster = {q.participant_id for q in quotes}

        for pid in pids_in_cluster:
            if pid not in participant_screens:
                participant_screens[pid] = []
            if cluster.screen_label not in participant_screens[pid]:
                participant_screens[pid].append(cluster.screen_label)

    return participant_screens


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
        )
    finally:
        db.close()
