"""Session tapestry: the timeline slice under each row of the Sessions grid.

One project-level read so the grid needs a single fetch. Per session: speaker turns (consecutive
same-speaker transcript segments, with the pipeline's scene colour for each), section flags
(each section's first quote in the session — the anchor the row's User journey chain links to),
and the quotes with sentiment, intensity and their section or theme.

Built from the database, so hidden quotes, quote edits and heading renames apply. Scene colours are
the one exception: they are pipeline output (``bristlenose/utils/scene_colour.py``) read from
``.bristlenose/intermediate/scene-colours/`` and matched to turns by time, so a speaker edit made
in serve does not orphan them.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.models import (
    ClusterQuote,
    HeadingEdit,
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
    ScreenCluster,
    ThemeGroup,
    ThemeQuote,
    TranscriptSegment,
)
from bristlenose.server.models import Session as SessionModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

#: The panel shows four lines and a click opens the transcript, so the full text never needs to travel.
_QUOTE_TEXT_LIMIT = 400


class TapestryTurn(BaseModel):
    t0: float
    t1: float
    #: The transcript's own token for the speaker (``m1``, ``p2``) — the slot code.
    speaker: str
    #: The scene colour (``#rrggbb``) — what was on screen during the turn — or null when the
    #: session has no video or the pipeline has not computed it.
    colour: str | None = None


class TapestrySection(BaseModel):
    t0: float
    label: str


class TapestryQuote(BaseModel):
    t0: float
    t1: float
    text: str
    sentiment: str | None = None
    intensity: int = 1
    section: str | None = None
    theme: str | None = None


class TapestrySession(BaseModel):
    session_id: str
    duration_seconds: float
    turns: list[TapestryTurn]
    sections: list[TapestrySection]
    quotes: list[TapestryQuote]


class TapestryResponse(BaseModel):
    sessions: list[TapestrySession]


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _output_dir(request: Request) -> Path | None:
    project_dir: Path | None = getattr(request.app.state, "project_dir", None)
    if project_dir is None:
        return None
    out = project_dir / "bristlenose-output"
    return out if out.is_dir() else project_dir


def _scene_colours(output_dir: Path | None, session_id: str) -> list[dict[str, object]]:
    if output_dir is None:
        return []
    path = output_dir / ".bristlenose" / "intermediate" / "scene-colours" / f"{session_id}.json"
    try:
        turns = json.loads(path.read_text(encoding="utf-8")).get("turns", [])
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        logger.warning("Unreadable scene colours for %s: %s", session_id, exc)
        return []
    return [t for t in turns if isinstance(t, dict)]


def _colour_at(colours: list[dict[str, object]], t0: float, t1: float) -> str | None:
    """The scene colour covering the turn's midpoint (pipeline turns may differ from today's)."""
    mid = (t0 + t1) / 2
    for c in colours:
        a, b, col = c.get("t0"), c.get("t1"), c.get("colour")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a <= mid < b:
            return col if isinstance(col, str) else None
    return None


def _turns(segments: list[TranscriptSegment], duration: float) -> list[tuple[float, float, str]]:
    turns: list[tuple[float, float, str]] = []
    for seg in sorted(segments, key=lambda s: s.start_time):
        if turns and turns[-1][2] == seg.speaker_code:
            a, b, code = turns[-1]
            turns[-1] = (a, max(b, seg.end_time), code)
        else:
            turns.append((seg.start_time, seg.end_time, seg.speaker_code))
    # A turn lasts until the next starts; the last runs to the end of the recording.
    out = []
    for i, (a, b, code) in enumerate(turns):
        end = turns[i + 1][0] if i + 1 < len(turns) else max(b, duration)
        out.append((a, max(b, end), code))
    return out


@router.get("/projects/{project_id}/tapestry", response_model=TapestryResponse)
def get_tapestry(
    project_id: int,
    request: Request,
    db: Session = Depends(_get_db),
) -> TapestryResponse:
    """Timeline data for every session of a project."""
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        out_dir = _output_dir(request)
        edits = {he.heading_key: he.edited_text
                 for he in db.query(HeadingEdit).filter_by(project_id=project_id).all()}

        section_of: dict[int, str] = {}
        for cq, cluster in (db.query(ClusterQuote, ScreenCluster)
                            .join(ScreenCluster, ClusterQuote.cluster_id == ScreenCluster.id)
                            .filter(ScreenCluster.project_id == project_id).all()):
            section_of[cq.quote_id] = edits.get(f"section-cluster-{cluster.id}:title") or cluster.screen_label
        theme_of: dict[int, str] = {}
        for tq, theme in (db.query(ThemeQuote, ThemeGroup)
                          .join(ThemeGroup, ThemeQuote.theme_id == ThemeGroup.id)
                          .filter(ThemeGroup.project_id == project_id).all()):
            theme_of[tq.quote_id] = edits.get(f"theme-group-{theme.id}:title") or theme.theme_label

        quotes = db.query(Quote).filter_by(project_id=project_id).all()
        ids = [q.id for q in quotes]
        hidden = {s.quote_id for s in db.query(QuoteState).filter(QuoteState.quote_id.in_(ids)).all() if s.is_hidden}
        edited: dict[int, str] = {}
        for e in db.query(QuoteEdit).filter(QuoteEdit.quote_id.in_(ids)).order_by(QuoteEdit.edited_at).all():
            edited[e.quote_id] = e.edited_text  # latest wins
        by_session: dict[str, list[Quote]] = {}
        for q in quotes:
            if q.id not in hidden:
                by_session.setdefault(q.session_id, []).append(q)

        sessions = (db.query(SessionModel).filter_by(project_id=project_id)
                    .order_by(SessionModel.session_number).all())
        result = []
        for sess in sessions:
            colours = _scene_colours(out_dir, sess.session_id)
            turns = [TapestryTurn(t0=a, t1=b, speaker=code, colour=_colour_at(colours, a, b))
                     for a, b, code in _turns(sess.transcript_segments, sess.duration_seconds)]
            sq = sorted(by_session.get(sess.session_id, []), key=lambda q: q.start_timecode)
            firsts: dict[str, float] = {}
            for q in sq:
                label = section_of.get(q.id)
                if label is not None and label not in firsts:
                    firsts[label] = q.start_timecode
            result.append(TapestrySession(
                session_id=sess.session_id,
                duration_seconds=sess.duration_seconds,
                turns=turns,
                sections=[TapestrySection(t0=t, label=lab) for lab, t in sorted(firsts.items(), key=lambda kv: kv[1])],
                quotes=[TapestryQuote(
                    t0=q.start_timecode, t1=q.end_timecode,
                    text=edited.get(q.id, q.text)[:_QUOTE_TEXT_LIMIT],
                    sentiment=q.sentiment, intensity=q.intensity or 1,
                    section=section_of.get(q.id), theme=theme_of.get(q.id),
                ) for q in sq],
            ))
        return TapestryResponse(sessions=result)
    finally:
        db.close()
