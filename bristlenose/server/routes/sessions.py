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
