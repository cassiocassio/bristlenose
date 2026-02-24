"""Quotes API endpoint — quotes grouped by section and theme."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    AutoCodeJob,
    ClusterQuote,
    CodebookGroup,
    DeletedBadge,
    Person,
    Project,
    ProposedTag,
    Quote,
    QuoteEdit,
    QuoteState,
    QuoteTag,
    ScreenCluster,
    SessionSpeaker,
    TagDefinition,
    ThemeGroup,
    ThemeQuote,
    TranscriptSegment,
)
from bristlenose.server.models import Session as SessionModel

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TagResponse(BaseModel):
    """A user-defined tag on a quote."""

    name: str
    codebook_group: str
    colour_set: str
    colour_index: int


class ProposedTagBrief(BaseModel):
    """A pending AutoCode tag proposal on a quote."""

    id: int
    tag_name: str
    group_name: str
    colour_set: str
    colour_index: int
    confidence: float
    rationale: str


class QuoteResponse(BaseModel):
    """A single quote with all metadata and researcher state."""

    dom_id: str
    text: str
    verbatim_excerpt: str
    participant_id: str
    session_id: str
    speaker_name: str
    start_timecode: float
    end_timecode: float
    sentiment: str | None
    intensity: int
    researcher_context: str | None
    quote_type: str
    topic_label: str
    is_starred: bool
    is_hidden: bool
    edited_text: str | None
    tags: list[TagResponse]
    deleted_badges: list[str]
    proposed_tags: list[ProposedTagBrief]
    segment_index: int = -1


class SectionResponse(BaseModel):
    """A screen cluster (section) with its quotes."""

    cluster_id: int
    screen_label: str
    description: str
    display_order: int
    quotes: list[QuoteResponse]


class ThemeResponse(BaseModel):
    """A theme group with its quotes."""

    theme_id: int
    theme_label: str
    description: str
    quotes: list[QuoteResponse]


class QuotesListResponse(BaseModel):
    """Full response for the quotes endpoint."""

    sections: list[SectionResponse]
    themes: list[ThemeResponse]
    total_quotes: int
    total_hidden: int
    total_starred: int
    has_moderator: bool


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


def _resolve_speaker_names(
    db: Session, project_id: int,
) -> dict[tuple[str, str], str]:
    """Build (session_id_str, speaker_code) -> display name map.

    Falls back to speaker_code if no name is set.
    """
    sessions = db.query(SessionModel).filter_by(project_id=project_id).all()
    result: dict[tuple[str, str], str] = {}
    for sess in sessions:
        speakers = (
            db.query(SessionSpeaker).filter_by(session_id=sess.id).all()
        )
        for sp in speakers:
            person = db.get(Person, sp.person_id)
            name = ""
            if person:
                name = person.short_name or person.full_name or ""
            result[(sess.session_id, sp.speaker_code)] = name or sp.speaker_code
    return result


def _load_researcher_state(
    db: Session, project_id: int, quote_ids: list[int],
) -> tuple[
    dict[int, QuoteState],
    dict[int, str],
    dict[int, list[TagResponse]],
    dict[int, list[str]],
    dict[int, list[ProposedTagBrief]],
]:
    """Load all researcher state for the given quote IDs.

    Returns (state_map, edit_map, tags_map, badges_map, proposed_map).
    """
    if not quote_ids:
        return {}, {}, {}, {}, {}

    # QuoteState (hidden/starred)
    states = db.query(QuoteState).filter(QuoteState.quote_id.in_(quote_ids)).all()
    state_map: dict[int, QuoteState] = {s.quote_id: s for s in states}

    # QuoteEdit (most recent per quote)
    edits = db.query(QuoteEdit).filter(QuoteEdit.quote_id.in_(quote_ids)).all()
    edit_map: dict[int, str] = {}
    for e in edits:
        # If multiple edits for the same quote, last one wins
        edit_map[e.quote_id] = e.edited_text

    # QuoteTag + TagDefinition + CodebookGroup
    tag_rows = (
        db.query(
            QuoteTag,
            TagDefinition.name,
            TagDefinition.id,
            TagDefinition.codebook_group_id,
            CodebookGroup.name,
            CodebookGroup.colour_set,
        )
        .join(TagDefinition, QuoteTag.tag_definition_id == TagDefinition.id)
        .join(CodebookGroup, TagDefinition.codebook_group_id == CodebookGroup.id)
        .filter(QuoteTag.quote_id.in_(quote_ids))
        .all()
    )
    # Build colour_index lookup: position of each tag within its group
    tag_group_ids = {row[3] for row in tag_rows}  # codebook_group_id
    tag_group_td_order: dict[int, list[int]] = {}
    for gid in tag_group_ids:
        tds = (
            db.query(TagDefinition.id)
            .filter_by(codebook_group_id=gid)
            .order_by(TagDefinition.id)
            .all()
        )
        tag_group_td_order[gid] = [td_id for (td_id,) in tds]

    tags_map: dict[int, list[TagResponse]] = {}
    for qt, tag_name, td_id, group_id, group_name, colour_set in tag_rows:
        td_ids = tag_group_td_order.get(group_id, [])
        cidx = td_ids.index(td_id) if td_id in td_ids else 0
        tags_map.setdefault(qt.quote_id, []).append(
            TagResponse(
                name=tag_name,
                codebook_group=group_name,
                colour_set=colour_set,
                colour_index=cidx,
            )
        )

    # DeletedBadge
    badges = (
        db.query(DeletedBadge).filter(DeletedBadge.quote_id.in_(quote_ids)).all()
    )
    badges_map: dict[int, list[str]] = {}
    for b in badges:
        badges_map.setdefault(b.quote_id, []).append(b.sentiment)

    # ProposedTag — pending proposals from completed AutoCode jobs
    proposed_map: dict[int, list[ProposedTagBrief]] = {}
    completed_jobs = (
        db.query(AutoCodeJob)
        .filter_by(project_id=project_id, status="completed")
        .all()
    )
    if completed_jobs:
        job_ids = [j.id for j in completed_jobs]
        proposed_rows = (
            db.query(
                ProposedTag,
                TagDefinition.name,
                TagDefinition.id,
                TagDefinition.codebook_group_id,
                CodebookGroup.name,
                CodebookGroup.colour_set,
            )
            .join(TagDefinition, ProposedTag.tag_definition_id == TagDefinition.id)
            .join(
                CodebookGroup,
                TagDefinition.codebook_group_id == CodebookGroup.id,
            )
            .filter(
                ProposedTag.job_id.in_(job_ids),
                ProposedTag.quote_id.in_(quote_ids),
                ProposedTag.status == "pending",
            )
            .all()
        )
        # Build colour_index lookup: position of each tag within its group
        group_ids = {row[3] for row in proposed_rows}  # codebook_group_id
        group_td_order: dict[int, list[int]] = {}
        for gid in group_ids:
            tds = (
                db.query(TagDefinition.id)
                .filter_by(codebook_group_id=gid)
                .order_by(TagDefinition.id)
                .all()
            )
            group_td_order[gid] = [td_id for (td_id,) in tds]

        for pt, tag_name, td_id, group_id, group_name, colour_set in proposed_rows:
            td_ids = group_td_order.get(group_id, [])
            cidx = td_ids.index(td_id) if td_id in td_ids else 0
            proposed_map.setdefault(pt.quote_id, []).append(
                ProposedTagBrief(
                    id=pt.id,
                    tag_name=tag_name,
                    group_name=group_name,
                    colour_set=colour_set,
                    colour_index=cidx,
                    confidence=pt.confidence,
                    rationale=pt.rationale,
                )
            )

    return state_map, edit_map, tags_map, badges_map, proposed_map


def _build_quote_response(
    quote: Quote,
    state_map: dict[int, QuoteState],
    edit_map: dict[int, str],
    tags_map: dict[int, list[TagResponse]],
    badges_map: dict[int, list[str]],
    proposed_map: dict[int, list[ProposedTagBrief]],
    speaker_map: dict[tuple[str, str], str],
) -> QuoteResponse:
    """Build a QuoteResponse from a Quote row and pre-loaded state maps."""
    state = state_map.get(quote.id)
    return QuoteResponse(
        dom_id=_quote_dom_id(quote),
        text=quote.text,
        verbatim_excerpt=quote.verbatim_excerpt,
        participant_id=quote.participant_id,
        session_id=quote.session_id,
        speaker_name=speaker_map.get(
            (quote.session_id, quote.participant_id), quote.participant_id,
        ),
        start_timecode=quote.start_timecode,
        end_timecode=quote.end_timecode,
        sentiment=quote.sentiment,
        intensity=quote.intensity,
        researcher_context=quote.researcher_context,
        quote_type=quote.quote_type,
        topic_label=quote.topic_label,
        is_starred=state.is_starred if state else False,
        is_hidden=state.is_hidden if state else False,
        edited_text=edit_map.get(quote.id),
        tags=tags_map.get(quote.id, []),
        deleted_badges=badges_map.get(quote.id, []),
        proposed_tags=proposed_map.get(quote.id, []),
        segment_index=quote.segment_index,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/quotes", response_model=QuotesListResponse)
def get_quotes(
    project_id: int,
    request: Request,
) -> QuotesListResponse:
    """Return all quotes for a project grouped by section and theme."""
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Load all quotes
        all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote_by_id: dict[int, Quote] = {q.id: q for q in all_quotes}
        quote_ids = list(quote_by_id.keys())

        # Load grouping joins
        cluster_quotes = (
            db.query(ClusterQuote).filter(ClusterQuote.quote_id.in_(quote_ids)).all()
            if quote_ids else []
        )
        cluster_to_quotes: dict[int, list[int]] = {}
        for cq in cluster_quotes:
            cluster_to_quotes.setdefault(cq.cluster_id, []).append(cq.quote_id)

        theme_quotes = (
            db.query(ThemeQuote).filter(ThemeQuote.quote_id.in_(quote_ids)).all()
            if quote_ids else []
        )
        theme_to_quotes: dict[int, list[int]] = {}
        for tq in theme_quotes:
            theme_to_quotes.setdefault(tq.theme_id, []).append(tq.quote_id)

        # Load researcher state
        state_map, edit_map, tags_map, badges_map, proposed_map = (
            _load_researcher_state(db, project_id, quote_ids)
        )

        # Resolve speaker names
        speaker_map = _resolve_speaker_names(db, project_id)

        # Build sections (screen clusters ordered by display_order)
        clusters = (
            db.query(ScreenCluster)
            .filter_by(project_id=project_id)
            .order_by(ScreenCluster.display_order)
            .all()
        )
        sections: list[SectionResponse] = []
        for cluster in clusters:
            qids = cluster_to_quotes.get(cluster.id, [])
            quotes = [quote_by_id[qid] for qid in qids if qid in quote_by_id]
            quotes.sort(key=lambda q: q.start_timecode)
            sections.append(SectionResponse(
                cluster_id=cluster.id,
                screen_label=cluster.screen_label,
                description=cluster.description,
                display_order=cluster.display_order,
                quotes=[
                    _build_quote_response(
                        q, state_map, edit_map, tags_map, badges_map,
                        proposed_map, speaker_map,
                    )
                    for q in quotes
                ],
            ))

        # Build themes
        themes_db = (
            db.query(ThemeGroup).filter_by(project_id=project_id).all()
        )
        themes: list[ThemeResponse] = []
        for theme in themes_db:
            qids = theme_to_quotes.get(theme.id, [])
            quotes = [quote_by_id[qid] for qid in qids if qid in quote_by_id]
            quotes.sort(key=lambda q: (q.session_id, q.start_timecode))
            themes.append(ThemeResponse(
                theme_id=theme.id,
                theme_label=theme.theme_label,
                description=theme.description,
                quotes=[
                    _build_quote_response(
                        q, state_map, edit_map, tags_map, badges_map,
                        proposed_map, speaker_map,
                    )
                    for q in quotes
                ],
            ))

        # Summary counts
        total_hidden = sum(
            1 for s in state_map.values() if s.is_hidden
        )
        total_starred = sum(
            1 for s in state_map.values() if s.is_starred
        )

        # Check if any session has a moderator speaker (speaker_code starting
        # with "m").  Solo sessions (no moderator) shouldn't offer the
        # "Question?" pill on quotes.
        has_moderator = db.query(
            db.query(TranscriptSegment)
            .join(SessionModel, TranscriptSegment.session_id == SessionModel.id)
            .filter(
                SessionModel.project_id == project_id,
                TranscriptSegment.speaker_code.like("m%"),
            )
            .exists()
        ).scalar() or False

        return QuotesListResponse(
            sections=sections,
            themes=themes,
            total_quotes=len(all_quotes),
            total_hidden=total_hidden,
            total_starred=total_starred,
            has_moderator=has_moderator,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Moderator question endpoint
# ---------------------------------------------------------------------------


class ModeratorQuestionResponse(BaseModel):
    """The preceding moderator utterance for a quote."""

    text: str
    speaker_code: str
    start_time: float
    end_time: float
    segment_index: int


@router.get(
    "/projects/{project_id}/quotes/{dom_id}/moderator-question",
    response_model=ModeratorQuestionResponse,
)
def get_moderator_question(
    project_id: int,
    dom_id: str,
    request: Request,
) -> ModeratorQuestionResponse:
    """Return the preceding moderator utterance for a quote.

    Finds the last transcript segment spoken by a moderator (speaker_code
    starting with "m") before the quote's segment_index in the same session.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)

        # Find the quote by dom_id (format: "q-{participant_id}-{int(start_timecode)}")
        all_quotes = db.query(Quote).filter_by(project_id=project_id).all()
        quote = next(
            (q for q in all_quotes if _quote_dom_id(q) == dom_id),
            None,
        )
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")

        if quote.segment_index < 1:
            raise HTTPException(
                status_code=404,
                detail="No segment index available for this quote",
            )

        # Find the session's DB row to get its primary key.
        session = (
            db.query(SessionModel)
            .filter_by(project_id=project_id, session_id=quote.session_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Find the last moderator segment before this quote's segment.
        segment = (
            db.query(TranscriptSegment)
            .filter(
                TranscriptSegment.session_id == session.id,
                TranscriptSegment.speaker_code.like("m%"),
                TranscriptSegment.segment_index < quote.segment_index,
            )
            .order_by(TranscriptSegment.segment_index.desc())
            .first()
        )
        if not segment:
            raise HTTPException(
                status_code=404,
                detail="No preceding moderator segment found",
            )

        return ModeratorQuestionResponse(
            text=segment.text,
            speaker_code=segment.speaker_code,
            start_time=segment.start_time,
            end_time=segment.end_time,
            segment_index=segment.segment_index,
        )
    finally:
        db.close()
