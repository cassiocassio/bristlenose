"""Transcript page API endpoint — full transcript with quote annotations."""

from __future__ import annotations

import html
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    ClusterQuote,
    CodebookGroup,
    DeletedBadge,
    Person,
    Project,
    Quote,
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
    name: str
    codebook_group: str
    colour_set: str
    colour_index: int


class TranscriptSpeakerResponse(BaseModel):
    code: str
    name: str
    role: str


class TranscriptSegmentResponse(BaseModel):
    speaker_code: str
    start_time: float
    end_time: float
    text: str
    html_text: str | None
    is_moderator: bool
    is_quoted: bool
    quote_ids: list[str]


class QuoteAnnotationResponse(BaseModel):
    label: str
    label_type: str
    sentiment: str
    participant_id: str
    start_timecode: float
    end_timecode: float
    verbatim_excerpt: str
    tags: list[TagResponse]
    deleted_badges: list[str]


class TranscriptPageResponse(BaseModel):
    session_id: str
    session_number: int
    duration_seconds: float
    has_media: bool
    project_name: str
    report_filename: str
    speakers: list[TranscriptSpeakerResponse]
    segments: list[TranscriptSegmentResponse]
    annotations: dict[str, QuoteAnnotationResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    return request.app.state.db_factory()


def _check_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _highlight_quoted_text(
    segment_text: str,
    annotations: list[tuple[str, str]],
) -> str | None:
    """Apply <mark class="bn-cited"> to quoted portions of segment text.

    annotations is a list of (quote_dom_id, verbatim_excerpt) tuples.
    Returns HTML string, or None if no highlights apply.
    """
    ranges: list[tuple[int, int, str]] = []
    has_any_match = False

    for qid, excerpt in annotations:
        if not excerpt:
            continue
        idx = segment_text.lower().find(excerpt.lower())
        if idx >= 0:
            ranges.append((idx, idx + len(excerpt), qid))
            has_any_match = True

    if not has_any_match:
        if annotations:
            qid = annotations[0][0]
            return (
                f'<mark class="bn-cited" data-quote-id="{_esc(qid)}">'
                f"{_esc(segment_text)}</mark>"
            )
        return None

    ranges.sort(key=lambda r: r[0])
    merged: list[tuple[int, int, str]] = []
    for start, end, qid in ranges:
        if merged and start <= merged[-1][1]:
            prev_start, prev_end, prev_qid = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), prev_qid)
        else:
            merged.append((start, end, qid))

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


def _quote_dom_id(q: Quote) -> str:
    return f"q-{q.participant_id}-{int(q.start_timecode)}"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/transcripts/{session_id}")
def get_transcript(
    request: Request, project_id: int, session_id: str,
) -> TranscriptPageResponse:
    db = _get_db(request)
    try:
        project = _check_project(db, project_id)

        # Find the session
        sess = (
            db.query(SessionModel)
            .filter_by(project_id=project_id, session_id=session_id)
            .first()
        )
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")

        # Speakers
        sp_rows = (
            db.query(SessionSpeaker, Person)
            .join(Person, SessionSpeaker.person_id == Person.id)
            .filter(SessionSpeaker.session_id == sess.id)
            .all()
        )
        # Sort: m-codes first, p-codes next, o-codes last
        def _code_sort_key(row: tuple[SessionSpeaker, Person]) -> tuple[int, int]:
            c = row[0].speaker_code
            prefix_order = {"m": 0, "p": 1, "o": 2}
            order = prefix_order.get(c[0], 3) if c else 3
            num = int(c[1:]) if len(c) > 1 and c[1:].isdigit() else 0
            return (order, num)

        sp_rows.sort(key=_code_sort_key)

        speakers = [
            TranscriptSpeakerResponse(
                code=sp.speaker_code,
                name=(p.short_name or p.full_name or sp.speaker_code),
                role=sp.speaker_role,
            )
            for sp, p in sp_rows
        ]

        # Transcript segments ordered by start_time
        segments = (
            db.query(TranscriptSegment)
            .filter_by(session_id=sess.id)
            .order_by(TranscriptSegment.start_time)
            .all()
        )

        # Quotes for this session + their cluster/theme assignments
        quotes = (
            db.query(Quote)
            .filter_by(project_id=project_id, session_id=session_id)
            .all()
        )
        quote_ids = [q.id for q in quotes]

        # Build assignment lookup: quote_id -> (label, label_type)
        assignment: dict[int, tuple[str, str]] = {}
        if quote_ids:
            cluster_rows = (
                db.query(ClusterQuote, ScreenCluster)
                .join(ScreenCluster, ClusterQuote.cluster_id == ScreenCluster.id)
                .filter(ClusterQuote.quote_id.in_(quote_ids))
                .all()
            )
            for cq, sc in cluster_rows:
                assignment[cq.quote_id] = (sc.screen_label, "section")

            theme_rows = (
                db.query(ThemeQuote, ThemeGroup)
                .join(ThemeGroup, ThemeQuote.theme_id == ThemeGroup.id)
                .filter(ThemeQuote.quote_id.in_(quote_ids))
                .all()
            )
            for tq, tg in theme_rows:
                assignment[tq.quote_id] = (tg.theme_label, "theme")

        # Tags and deleted badges per quote
        tags_map: dict[int, list[TagResponse]] = {}
        badges_map: dict[int, list[str]] = {}
        if quote_ids:
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
                .join(
                    CodebookGroup,
                    TagDefinition.codebook_group_id == CodebookGroup.id,
                )
                .filter(QuoteTag.quote_id.in_(quote_ids))
                .all()
            )
            # Build colour_index lookup
            t_group_ids = {row[3] for row in tag_rows}
            t_group_td_order: dict[int, list[int]] = {}
            for gid in t_group_ids:
                tds = (
                    db.query(TagDefinition.id)
                    .filter_by(codebook_group_id=gid)
                    .order_by(TagDefinition.id)
                    .all()
                )
                t_group_td_order[gid] = [td_id for (td_id,) in tds]

            for qt, tag_name, td_id, group_id, group_name, colour_set in tag_rows:
                td_ids = t_group_td_order.get(group_id, [])
                cidx = td_ids.index(td_id) if td_id in td_ids else 0
                tags_map.setdefault(qt.quote_id, []).append(
                    TagResponse(
                        name=tag_name,
                        codebook_group=group_name,
                        colour_set=colour_set,
                        colour_index=cidx,
                    )
                )

            badge_rows = (
                db.query(DeletedBadge)
                .filter(DeletedBadge.quote_id.in_(quote_ids))
                .all()
            )
            for b in badge_rows:
                badges_map.setdefault(b.quote_id, []).append(b.sentiment)

        # Build annotations dict keyed by quote DOM ID
        annotations: dict[str, QuoteAnnotationResponse] = {}
        # Also build a lookup for segment-quote matching
        # quote_data: list of (dom_id, participant_id, start_tc, end_tc, verbatim)
        quote_data: list[tuple[str, str, float, float, str, Quote]] = []
        for q in quotes:
            dom_id = _quote_dom_id(q)
            label, label_type = assignment.get(q.id, ("", ""))
            annotations[dom_id] = QuoteAnnotationResponse(
                label=label,
                label_type=label_type,
                sentiment=q.sentiment or "",
                participant_id=q.participant_id,
                start_timecode=q.start_timecode,
                end_timecode=q.end_timecode,
                verbatim_excerpt=q.verbatim_excerpt,
                tags=tags_map.get(q.id, []),
                deleted_badges=badges_map.get(q.id, []),
            )
            quote_data.append(
                (dom_id, q.participant_id, q.start_timecode, q.end_timecode,
                 q.verbatim_excerpt, q)
            )

        # Build segment responses with quote overlap detection
        seg_responses: list[TranscriptSegmentResponse] = []
        for seg in segments:
            is_moderator = seg.speaker_code.startswith("m")

            # Find overlapping quotes (same logic as render_html.py)
            seg_quotes = [
                (dom_id, pid, s_tc, e_tc, excerpt, q)
                for dom_id, pid, s_tc, e_tc, excerpt, q in quote_data
                if s_tc <= seg.start_time <= e_tc and pid == seg.speaker_code
            ]
            is_quoted = bool(seg_quotes) and not is_moderator

            qids = [dom_id for dom_id, *_ in seg_quotes] if is_quoted else []

            # Pre-render HTML text with <mark> highlights
            html_text: str | None = None
            if is_quoted:
                mark_data = [(dom_id, excerpt) for dom_id, _, _, _, excerpt, _ in seg_quotes]
                html_text = _highlight_quoted_text(seg.text, mark_data)

            seg_responses.append(TranscriptSegmentResponse(
                speaker_code=seg.speaker_code,
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                html_text=html_text,
                is_moderator=is_moderator,
                is_quoted=is_quoted,
                quote_ids=qids,
            ))

        # Report filename for back link
        slug = re.sub(r"[^a-z0-9]+", "-", project.name.lower()).strip("-")[:50]
        report_filename = f"bristlenose-{slug}-report.html"

        return TranscriptPageResponse(
            session_id=session_id,
            session_number=sess.session_number,
            duration_seconds=sess.duration_seconds,
            has_media=sess.has_media,
            project_name=project.name,
            report_filename=report_filename,
            speakers=speakers,
            segments=seg_responses,
            annotations=annotations,
        )
    finally:
        db.close()
