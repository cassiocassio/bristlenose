"""Sessions API endpoint."""

from __future__ import annotations

from pathlib import Path as _Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bristlenose.server.journey import derive_journeys
from bristlenose.server.models import (
    Person,
    Project,
    Quote,
    SessionSpeaker,
    SourceFile,
)
from bristlenose.server.models import (
    Session as SessionModel,
)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SpeakerResponse(BaseModel):
    """A speaker in a session."""

    speaker_code: str
    name: str
    role: str


class SourceFileResponse(BaseModel):
    """A source file linked to a session."""

    path: str
    file_type: str
    filename: str


class SessionResponse(BaseModel):
    """A single session row for the sessions table."""

    session_id: str
    session_number: int
    session_date: str | None
    duration_seconds: float
    has_media: bool
    has_video: bool
    thumbnail_url: str | None = None
    speakers: list[SpeakerResponse]
    journey_labels: list[str]
    sentiment_counts: dict[str, int]
    source_files: list[SourceFileResponse]


class SessionsListResponse(BaseModel):
    """Full response for the sessions endpoint."""

    sessions: list[SessionResponse]
    moderator_names: list[str]
    observer_names: list[str]
    source_folder_uri: str


class VideoMapResponse(BaseModel):
    """Video/audio map for the popout player."""

    video_map: dict[str, str]
    player_url: str


# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------


def _get_db(request: Request) -> Session:
    """Get the database session from app state."""
    return request.app.state.db_factory()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/sessions", response_model=SessionsListResponse)
def get_sessions(
    project_id: int,
    db: Session = Depends(_get_db),  # type: ignore[assignment]
) -> SessionsListResponse:
    """Return all sessions for a project with full data for the sessions table."""
    try:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        sessions = (
            db.query(SessionModel)
            .filter_by(project_id=project_id)
            .order_by(SessionModel.session_number)
            .all()
        )

        # --- Build journey labels per participant ---
        participant_screens = derive_journeys(db, project_id)

        # --- Build sentiment counts per session ---
        sentiment_by_session = _aggregate_sentiments(db, project_id)

        # --- Collect moderator/observer names ---
        all_moderator_names: list[str] = []
        all_observer_names: list[str] = []

        rows: list[SessionResponse] = []
        for sess in sessions:
            # Speakers
            speakers_data: list[SpeakerResponse] = []
            for sp in sorted(sess.session_speakers, key=_speaker_sort_key):
                person = db.get(Person, sp.person_id)
                name = ""
                if person:
                    name = person.short_name or person.full_name or ""

                speakers_data.append(
                    SpeakerResponse(
                        speaker_code=sp.speaker_code,
                        name=name,
                        role=sp.speaker_role,
                    )
                )

                # Track moderators/observers
                if sp.speaker_role == "researcher" and name:
                    if name not in all_moderator_names:
                        all_moderator_names.append(name)
                elif sp.speaker_role == "observer" and name:
                    if name not in all_observer_names:
                        all_observer_names.append(name)

            # Source files
            source_files: list[SourceFileResponse] = []
            for sf in sess.source_files:
                filename = _Path(sf.path).name
                source_files.append(
                    SourceFileResponse(
                        path=sf.path,
                        file_type=sf.file_type,
                        filename=filename,
                    )
                )

            # Journey: merge all participants' screen labels for this session
            session_pids = [
                sp.speaker_code for sp in sess.session_speakers
                if sp.speaker_code.startswith("p")
            ]
            journey_labels: list[str] = []
            for pid in session_pids:
                for label in participant_screens.get(pid, []):
                    if label not in journey_labels:
                        journey_labels.append(label)

            # Sentiment counts
            sentiment_counts = sentiment_by_session.get(sess.session_id, {})

            # Thumbnail URL (relative path served by StaticFiles mount).
            thumbnail_url: str | None = None
            if sess.thumbnail_path:
                thumbnail_url = f"/report/{sess.thumbnail_path}"

            rows.append(
                SessionResponse(
                    session_id=sess.session_id,
                    session_number=sess.session_number,
                    session_date=(
                        sess.session_date.isoformat() if sess.session_date else None
                    ),
                    duration_seconds=sess.duration_seconds,
                    has_media=sess.has_media,
                    has_video=sess.has_video,
                    thumbnail_url=thumbnail_url,
                    speakers=speakers_data,
                    journey_labels=journey_labels,
                    sentiment_counts=sentiment_counts,
                    source_files=source_files,
                )
            )

        # Source folder URI (from first session's first source file).
        source_folder_uri = ""
        for sess in sessions:
            if sess.source_files:
                p = _Path(sess.source_files[0].path).parent.resolve()
                source_folder_uri = p.as_uri()
                break

        return SessionsListResponse(
            sessions=rows,
            moderator_names=all_moderator_names,
            observer_names=all_observer_names,
            source_folder_uri=source_folder_uri,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Aggregate sentiment counts by session_id.

    Returns session_id → {sentiment: count}.
    """
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


@router.get("/projects/{project_id}/video-map", response_model=VideoMapResponse)
def get_video_map(
    project_id: int,
    request: Request,
    db: Session = Depends(_get_db),  # type: ignore[assignment]
) -> VideoMapResponse:
    """Return the video/audio map and player URL for a project.

    Maps session IDs and participant speaker codes to ``/media/`` HTTP paths.
    Mirrors the logic in ``render_html._build_video_map()`` — prefers video
    files over audio.
    """
    try:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        project_dir: _Path | None = getattr(request.app.state, "project_dir", None)

        sessions = (
            db.query(SessionModel)
            .filter_by(project_id=project_id)
            .all()
        )

        video_map: dict[str, str] = {}
        for sess in sessions:
            # Prefer video over audio (same heuristic as _build_video_map)
            chosen: SourceFile | None = None
            for ftype in ("video", "audio"):
                for sf in sess.source_files:
                    if sf.file_type == ftype:
                        chosen = sf
                        break
                if chosen is not None:
                    break

            if chosen is None:
                continue

            media_uri = _file_to_media_uri(chosen.path, project_dir)
            video_map[sess.session_id] = media_uri
            # Also key by participant speaker codes (for quote-level lookups)
            for sp in sess.session_speakers:
                if sp.speaker_code.startswith("p"):
                    video_map[sp.speaker_code] = media_uri

        return VideoMapResponse(
            video_map=video_map,
            player_url="/report/assets/bristlenose-player.html",
        )
    finally:
        db.close()


def _file_to_media_uri(file_path: str, project_dir: _Path | None) -> str:
    """Convert an absolute file path to a ``/media/`` HTTP URI.

    Strips the ``project_dir`` prefix so the remainder is a relative path
    under ``/media/``.  Returns an **unencoded** path — the caller (or the
    browser / JS ``encodeURIComponent``) is responsible for percent-encoding
    when placing it in a URL.  Returning a raw path avoids the double-encoding
    bug where Python encodes and then JS encodes again.
    """
    p = _Path(file_path)
    if project_dir is not None:
        try:
            rel = p.resolve().relative_to(project_dir.resolve())
            return "/media/" + str(rel)
        except ValueError:
            pass
    return "/media/" + p.name
