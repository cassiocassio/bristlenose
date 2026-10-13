"""Session tapestry: the timeline slice under each row of the Sessions grid.

One project-level read so the grid needs a single fetch. Per session: speaker turns (consecutive
same-speaker transcript segments, with the pipeline's scene colour for each), section flags
(each section's first quote in the session — the anchor the row's User journey chain links to),
and the quotes with sentiment, intensity and their section or theme.

Built from the database, so hidden quotes, quote edits and heading renames apply. Two things are
read from files instead: scene colours, pipeline output (``bristlenose/utils/scene_colour.py``) in
``.bristlenose/intermediate/scene-colours/``, matched to turns by time so a speaker edit made in
serve does not orphan them; and scene strips, serve's own background output
(``server/scene_strips.py``) in ``.bristlenose/intermediate/scene-strips/``.

The hover thumbnail's frames (``utils/turn_frames.py``, serve's too, in ``turn-frames/``) are not
in this response: they are a megabyte an hour of video, and the grid polls this route. Each session
says only ``frames_key``; the grid fetches ``/sessions/{id}/turn-frames`` the first time the
pointer rests on that timeline. The frames are participants' screens, so that route is behind the
bearer token and the HTML export leaves it out.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from bristlenose.output_paths import project_output_dir
from bristlenose.server import speaker_slots
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
)
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.scene_strips import video_sessions
from bristlenose.server.tapestry_turns import (
    frames_dir,
    frames_state,
    participant_turns,
    session_turns,
)
from bristlenose.utils.turn_frames import read_record

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

#: The panel shows four lines and a click opens the transcript, so the full text never needs to travel.
_QUOTE_TEXT_LIMIT = 400


class TapestryTurn(BaseModel):
    t0: float
    t1: float
    #: The transcript's own token for the speaker (``m1``, ``p2``) — the slot code.
    speaker: str
    #: Whether the speaker is a moderator or observer *now*: the slot's role,
    #: which a recode changes while the token keeps its letter
    #: (design-people.md §J7). Read this, never the token's prefix.
    team: bool = False
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


class TapestryStrip(BaseModel):
    """What was on screen, moment by moment (``utils/scene_strip.py``): a 1×n RGB PNG, one
    column per sample at ``fps``, drawn inside the speaker clips; ``edges`` are the seconds at
    which the scene changed, drawn as notches."""
    fps: int
    n: int
    #: Seconds of the first column: the recording's stream start, not always zero.
    t0: float = 0.0
    png: str  # data URL
    edges: list[float]


class TapestrySession(BaseModel):
    session_id: str
    duration_seconds: float
    turns: list[TapestryTurn]
    sections: list[TapestrySection]
    quotes: list[TapestryQuote]
    #: Null until serve's background job has computed it, or when the session has no video.
    strip: TapestryStrip | None = None
    #: Identifies the hover thumbnail's frames when they are ready and current; null otherwise.
    #: A new key means new frames (the turns moved), so the grid caches by it.
    frames_key: str | None = None


class TapestryResponse(BaseModel):
    sessions: list[TapestrySession]
    #: True while serve is computing strips or frames; the grid refetches until it is false.
    strips_pending: bool = False


class TurnFrame(BaseModel):
    t: float
    #: The stretch of the participant turn this frame stands for.
    a: float
    b: float
    #: The stretch begins at a colour change; a click then lands 1 s before it.
    change: bool
    src: str  # data URL


class TurnFramesResponse(BaseModel):
    key: str
    frames: list[TurnFrame]


def _clip(text: str) -> str:
    return text if len(text) <= _QUOTE_TEXT_LIMIT else text[:_QUOTE_TEXT_LIMIT].rstrip() + "…"


def _get_db(request: Request) -> Session:
    db: Session = request.app.state.db_factory()
    return db


def _output_dir(request: Request) -> Path | None:
    project_dir: Path | None = getattr(request.app.state, "project_dir", None)
    return None if project_dir is None else project_output_dir(project_dir)


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


def _scene_strip(output_dir: Path | None, session_id: str) -> TapestryStrip | None:
    """The session's strip, or None when absent or unreadable (serve may be writing it)."""
    if output_dir is None:
        return None
    path = output_dir / ".bristlenose" / "intermediate" / "scene-strips" / f"{session_id}.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        return TapestryStrip(fps=int(rec["fps"]), n=int(rec["n"]), t0=float(rec.get("t0", 0.0)),
                             png="data:image/png;base64," + str(rec["png"]),
                             edges=[float(t) for t in rec.get("edges", [])])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Unreadable scene strip for %s: %s", session_id, exc)
        return None


def _colour_at(colours: list[dict[str, object]], t0: float, t1: float) -> str | None:
    """The scene colour in force at the turn's midpoint: the latest pipeline turn starting at or
    before it. Pipeline turns may differ from today's, and the pipeline's last turn ends at the
    last speech while this route's runs on to the end of the recording."""
    mid = (t0 + t1) / 2
    best: tuple[float, str] | None = None
    for c in colours:
        a, col = c.get("t0"), c.get("colour")
        if isinstance(a, (int, float)) and isinstance(col, str) and a <= mid and (best is None or a >= best[0]):
            best = (float(a), col)
    return best[1] if best else None


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

        quotes = speaker_slots.evidence_quotes(db, project_id)
        slots = speaker_slots.slot_map(db, project_id)
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
                    .options(selectinload(SessionModel.transcript_segments))
                    .order_by(SessionModel.session_number).all())
        # Read before the strip files, so a job finishing between the two cannot answer
        # "not pending" while a strip it just wrote is missing from this response.
        job = getattr(request.app.state, "scene_strips", None)
        strips_pending = bool(job is not None and job.running)
        frames_owed = False
        # Only a session the job can reach is owed a pass: a strip left from a recording that has
        # since gone would otherwise ask for one on every poll, and the pass could never answer.
        with_video = set(video_sessions(db)) if job is not None else set()
        result = []
        for sess in sessions:
            colours = _scene_colours(out_dir, sess.session_id)
            spans = session_turns(sess, slots)
            turns = [TapestryTurn(t0=a, t1=b, speaker=code, colour=_colour_at(colours, a, b), team=team)
                     for a, b, code, team in spans]
            frames_key, owed = (frames_state(out_dir, sess.session_id, participant_turns(spans))
                                if out_dir is not None else (None, False))
            frames_owed = frames_owed or (owed and sess.session_id in with_video)
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
                strip=_scene_strip(out_dir, sess.session_id),
                frames_key=frames_key,
                sections=[TapestrySection(t0=t, label=lab) for lab, t in sorted(firsts.items(), key=lambda kv: kv[1])],
                quotes=[TapestryQuote(
                    t0=q.start_timecode, t1=q.end_timecode,
                    text=_clip(edited.get(q.id, q.text)),
                    sentiment=q.sentiment, intensity=q.intensity or 1,
                    section=section_of.get(q.id), theme=theme_of.get(q.id),
                ) for q in sq],
            ))
        # Frames taken for other turns (a paragraph split or moved, a speaker recoded since):
        # ask the job for a pass. It defers during a run and goes round again if busy.
        if frames_owed and job is not None and not strips_pending:
            job.start()
            strips_pending = bool(job.running)
        return TapestryResponse(sessions=result, strips_pending=strips_pending)
    finally:
        db.close()


@router.get("/projects/{project_id}/sessions/{session_id}/turn-frames", response_model=TurnFramesResponse)
def get_turn_frames(
    project_id: int,
    session_id: str,
    request: Request,
    db: Session = Depends(_get_db),
) -> TurnFramesResponse:
    """The hover thumbnail's frames for one session: what was on the participant's screen."""
    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        if not db.query(SessionModel).filter_by(project_id=project_id, session_id=session_id).first():
            raise HTTPException(status_code=404, detail="Session not found")
    finally:
        db.close()
    out_dir = _output_dir(request)
    rec = read_record(frames_dir(out_dir) / f"{session_id}.json") if out_dir is not None else None
    frames = rec.get("frames") if rec else None
    if not rec or not isinstance(frames, list) or not frames:
        raise HTTPException(status_code=404, detail="No frames")
    try:
        return TurnFramesResponse(key=str(rec.get("key")), frames=[
            TurnFrame(t=f["t"], a=f["a"], b=f["b"], change=bool(f["change"]),
                      src="data:image/jpeg;base64," + str(f["jpg"]))
            for f in frames
        ])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Unreadable turn frames for %s: %s", session_id, exc)
        raise HTTPException(status_code=404, detail="No frames") from exc


@router.get("/projects/{project_id}/transcription-quality")
def get_transcription_quality(
    project_id: int,
    request: Request,
    db: Session = Depends(_get_db),
) -> dict[str, dict[str, object]]:
    """Each session's transcription-quality record, for the diagnostics block in its slice.

    Numbers only (``bristlenose/transcription_quality.py``). Fetched only when the
    researcher's diagnostics preference is on, and left out of the HTML export: it
    describes how this machine's Whisper heard the recording, not the findings.
    A session transcribed from a platform file, or before this record existed, is absent.
    """
    from bristlenose.transcription_quality import read_records

    try:
        if not db.get(Project, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        out_dir = _output_dir(request)
        if out_dir is None:
            return {"sessions": {}}
        known = {s.session_id for s in db.query(SessionModel).filter_by(project_id=project_id)}
        records = read_records(out_dir)
        return {"sessions": {sid: rec for sid, rec in records.items() if sid in known}}
    finally:
        db.close()
