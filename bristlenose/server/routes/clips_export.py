"""Video clip extraction endpoints — async FFmpeg stream-copy.

POST /projects/{id}/export/clips  — start extraction job
GET  /projects/{id}/export/clips/status — poll progress
POST /projects/{id}/export/clips/reveal — open clips folder in Finder
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from bristlenose.server.clip_backend import FFmpegBackend
from bristlenose.server.clip_manifest import (
    ClipSpec,
    _QuoteLike,
    build_clip_filename,
    build_clip_manifest,
    merge_adjacent_clips,
)
from bristlenose.server.clip_subtitles import (
    Correction,
    Cue,
    SegmentInput,
    WordTiming,
    apply_correction,
    build_cues,
    to_srt,
    to_webvtt,
    tokens_for_segment,
)
from bristlenose.server.export_core import pick_featured_quotes
from bristlenose.server.models import (
    Person,
    Project,
    Quote,
    QuoteEdit,
    QuoteState,
    SessionSpeaker,
    TranscriptSegment,
)
from bristlenose.server.models import Session as SessionModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Job state (module-level, ephemeral — lost on server restart)
# ---------------------------------------------------------------------------

_jobs: dict[int, dict[str, Any]] = {}  # project_id → job state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.db_factory()


def _check_project(db, project_id: int) -> Project:  # type: ignore[no-untyped-def]
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _resolve_output_dir(project_dir: Path | None) -> Path | None:
    """Derive the bristlenose-output directory from the project dir."""
    if project_dir is None:
        return None
    output_dir = project_dir / "bristlenose-output"
    if output_dir.is_dir():
        return output_dir
    return project_dir


def _load_speaker_names(
    db, project_id: int,
) -> dict[tuple[str, str], str]:
    """Map (session_id, speaker_code) → display_name."""
    rows = (
        db.query(
            SessionModel.session_id,
            SessionSpeaker.speaker_code,
            Person.short_name,
            Person.full_name,
        )
        .join(SessionSpeaker, SessionSpeaker.session_id == SessionModel.id)
        .join(Person, Person.id == SessionSpeaker.person_id)
        .filter(SessionModel.project_id == project_id)
        .all()
    )
    return {
        (sid, code): (short or full or "")
        for sid, code, short, full in rows
    }


def _load_session_media(
    db, project_id: int, project_dir: Path,
) -> tuple[dict[str, tuple[Path, bool]], dict[str, float]]:
    """Load session media paths and durations.

    Returns (session_media, session_durations).
    session_media: session_id → (absolute_path, is_audio_only)
    session_durations: session_id → duration_seconds
    """
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.project_id == project_id, SessionModel.has_media == True)  # noqa: E712
        .all()
    )

    session_media: dict[str, tuple[Path, bool]] = {}
    session_durations: dict[str, float] = {}

    for sess in sessions:
        session_durations[sess.session_id] = sess.duration_seconds

        # Find first video or audio source file
        video_file = None
        audio_file = None
        for sf in sess.source_files:
            if sf.file_type == "video" and video_file is None:
                video_file = sf
            elif sf.file_type == "audio" and audio_file is None:
                audio_file = sf

        source_file = video_file or audio_file
        if source_file is None:
            continue

        sf_path = Path(source_file.path)
        if sf_path.is_absolute():
            abs_path = sf_path
        else:
            # Try joining with project_dir first; if that doesn't exist,
            # the stored path may already include the project_dir prefix
            # (e.g. "trial-runs/project/interviews/file.mov") — resolve from CWD.
            candidate = (project_dir / sf_path).resolve()
            if candidate.exists():
                abs_path = candidate
            else:
                abs_path = sf_path.resolve()
        is_audio_only = video_file is None
        session_media[sess.session_id] = (abs_path, is_audio_only)

    return session_media, session_durations


def _load_starred_quotes(db, project_id: int) -> list[Quote]:  # type: ignore[no-untyped-def]
    """Load all starred quotes for a project."""
    return (
        db.query(Quote)
        .join(QuoteState, QuoteState.quote_id == Quote.id)
        .filter(
            Quote.project_id == project_id,
            QuoteState.is_starred == True,  # noqa: E712
        )
        .all()
    )


def _quotes_to_quotelike(
    quotes: list[Quote],
    starred_ids: set[int],
    hero_ids: set[int],
) -> list[_QuoteLike]:
    """Convert ORM Quote rows to the _QuoteLike interface for manifest building."""
    result: list[_QuoteLike] = []
    for q in quotes:
        dom_id = f"q-{q.participant_id}-{int(q.start_timecode)}"
        result.append(_QuoteLike(
            quote_id=dom_id,
            participant_id=q.participant_id,
            session_id=q.session_id,
            start_timecode=q.start_timecode,
            end_timecode=q.end_timecode,
            text=q.text,
            is_starred=q.id in starred_ids,
            is_hero=q.id in hero_ids,
        ))
    return result


def _load_segments(
    db: DbSession, project_id: int, session_id: str, start: float, end: float,
) -> list[SegmentInput]:
    """Transcript segments overlapping ``[start, end]`` for one session."""
    rows = (
        db.query(TranscriptSegment)
        .join(SessionModel, SessionModel.id == TranscriptSegment.session_id)
        .filter(
            SessionModel.project_id == project_id,
            SessionModel.session_id == session_id,
            TranscriptSegment.end_time > start,
            TranscriptSegment.start_time < end,
        )
        .order_by(TranscriptSegment.start_time)
        .all()
    )
    segments: list[SegmentInput] = []
    for row in rows:
        words: tuple[WordTiming, ...] | None = None
        if row.words_json:
            try:
                words = tuple(
                    WordTiming(text=w["t"], start=float(w["s"]), end=float(w["e"]))
                    for w in json.loads(row.words_json)
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                words = None
        segments.append(SegmentInput(
            speaker_code=row.speaker_code,
            start=row.start_time,
            end=row.end_time,
            text=row.text,
            words=words or None,
        ))
    return segments


def _load_corrections(
    db: DbSession, project_id: int, session_id: str, start: float, end: float,
) -> list[Correction]:
    """The researcher's latest edit of each quote overlapping ``[start, end]``."""
    rows = (
        db.query(Quote, QuoteEdit.edited_text)
        .join(QuoteEdit, QuoteEdit.quote_id == Quote.id)
        .filter(
            Quote.project_id == project_id,
            Quote.session_id == session_id,
            Quote.end_timecode > start,
            Quote.start_timecode < end,
        )
        .order_by(QuoteEdit.edited_at.desc())
        .all()
    )
    latest: dict[int, Correction] = {}
    for quote, edited in rows:
        if quote.id in latest or edited == quote.text:
            continue
        latest[quote.id] = Correction(
            speaker_code=quote.participant_id,
            start=quote.start_timecode,
            end=quote.end_timecode,
            original=quote.text,
            corrected=edited,
        )
    return sorted(latest.values(), key=lambda c: c.start)


def _build_clip_cues(db: DbSession, project_id: int, spec: ClipSpec) -> list[Cue]:
    """Subtitle cues for one clip: everyone audible, with corrections applied.

    Never carries a speaker's name: speakers are told apart by colour only.
    """
    segments = _load_segments(db, project_id, spec.session_id, spec.start, spec.end)
    tokens = [tok for seg in segments for tok in tokens_for_segment(seg)]
    for corr in _load_corrections(db, project_id, spec.session_id, spec.start, spec.end):
        tokens, fell_back = apply_correction(tokens, corr)
        if fell_back:
            logger.info(
                "Clip subtitles: correction at %.1fs in %s spread evenly "
                "(could not be placed word by word)",
                corr.start, spec.session_id,
            )
    return build_cues(tokens, spec.start, spec.end, spec.participant_id)


# ---------------------------------------------------------------------------
# Async job runner
# ---------------------------------------------------------------------------


async def _run_clip_extraction(
    project_id: int,
    clips: list[ClipSpec],
    clips_dir: Path,
    participant_count: int,
    use_hours: bool,
    anonymise: bool,
    cues_by_clip: dict[int, list[Cue]] | None = None,
) -> None:
    """Extract clips in background. Updates module-level _jobs state.

    Each clip with transcript text gets a ``.vtt`` beside it and the same
    cues muxed in as a soft subtitle track. A clip whose subtitle mux fails
    is cut again without subtitles rather than lost.
    """
    backend = FFmpegBackend()
    job = _jobs.get(project_id)
    if job is None:
        return

    manifest_entries: list[dict[str, Any]] = []

    for i, spec in enumerate(clips):
        if _jobs.get(project_id, {}).get("status") == "cancelled":
            break

        filename = build_clip_filename(
            spec, participant_count, use_hours, anonymise=anonymise,
        )
        output_path = clips_dir / filename

        job["progress"] = i
        job["current_clip"] = filename.rsplit(".", 1)[0]  # strip extension

        cues = (cues_by_clip or {}).get(i) or []
        stem = filename.rsplit(".", 1)[0]
        srt_path = clips_dir / f".{stem}.srt.tmp"
        result = None
        try:
            if cues:
                srt_path.write_text(to_srt(cues), encoding="utf-8")
                # Run FFmpeg in a thread to avoid blocking the event loop
                result = await asyncio.to_thread(
                    backend.extract_clip, spec.source_path, output_path,
                    spec.start, spec.end, srt_path,
                )
                if result is None:
                    logger.warning(
                        "Subtitle track failed for %s; cutting without it", filename,
                    )
            if result is None:
                result = await asyncio.to_thread(
                    backend.extract_clip, spec.source_path, output_path,
                    spec.start, spec.end,
                )
        finally:
            srt_path.unlink(missing_ok=True)

        if result is not None:
            job["completed_count"] = job.get("completed_count", 0) + 1
            vtt_name: str | None = None
            if cues:
                vtt_name = f"{stem}.vtt"
                (clips_dir / vtt_name).write_text(to_webvtt(cues), encoding="utf-8")
            manifest_entries.append({
                "quote_id": spec.quote_id,
                "participant_id": spec.participant_id,
                "session_id": spec.session_id,
                "filename": filename,
                "subtitles": vtt_name,
                "start": spec.start,
                "end": spec.end,
            })
        else:
            job["skipped_count"] = job.get("skipped_count", 0) + 1
            logger.warning("Skipped clip %s (extraction failed)", filename)

    # Write clips_manifest.json
    manifest = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "total": len(clips),
        "completed": job.get("completed_count", 0),
        "skipped": job.get("skipped_count", 0),
        "anonymised": anonymise,
        "clips": manifest_entries,
    }
    manifest_path = clips_dir / "clips_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True))

    # A cancelled job broke out of the loop early — record that, don't overwrite
    # it with "completed". Clips written before the break stay on disk (a partial
    # folder is honest and usable), so output_dir is set either way.
    cancelled = _jobs.get(project_id, {}).get("status") == "cancelled"
    job["status"] = "cancelled" if cancelled else "completed"
    if not cancelled:
        job["progress"] = len(clips)
    job["output_dir"] = str(clips_dir)
    job["current_clip"] = ""


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class ClipStartRequest(BaseModel):
    anonymise: bool = False
    # DOM-style quote ids (q-{participant}-{int(start)}) to clip. When present,
    # exactly these quotes are cut — this is the scope picker (Selected/Starred/
    # All) handing over its chosen set. When None (legacy no-scope caller, e.g.
    # the native menu until its submenu lands), fall back to the historical
    # starred ∪ featured union below.
    ids: list[str] | None = None


class ClipStartResponse(BaseModel):
    status: str
    total: int
    pii_warning: bool = False


class ClipStatusResponse(BaseModel):
    status: str
    progress: int
    total: int
    completed_count: int
    skipped_count: int
    current_clip: str
    output_dir: str | None


# ---------------------------------------------------------------------------
# POST /projects/{id}/export/clips — start extraction
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/export/clips")
async def start_clip_extraction(
    request: Request,
    project_id: int,
    body: ClipStartRequest | None = None,
) -> ClipStartResponse:
    """Start async clip extraction.

    Clips the quotes named in ``body.ids`` (the Selected/Starred/All scope
    picker). With no ids, falls back to the legacy starred ∪ featured union.
    """
    anonymise = body.anonymise if body else False

    # Check FFmpeg availability
    backend = FFmpegBackend()
    ok, msg = backend.check_available()
    if not ok:
        raise HTTPException(status_code=422, detail=msg)

    # Check no concurrent job
    existing = _jobs.get(project_id)
    if existing and existing.get("status") in ("pending", "running"):
        raise HTTPException(status_code=409, detail="Clip extraction already in progress")

    db = _get_db(request)
    try:
        _check_project(db, project_id)
        project_dir = request.app.state.project_dir
        output_dir = _resolve_output_dir(project_dir)

        if output_dir is None:
            raise HTTPException(status_code=400, detail="No project directory configured")

        # is_starred flag still drives filename/dedup priority in the manifest
        # builder, so load it regardless of how the clip set is chosen.
        starred_quotes = _load_starred_quotes(db, project_id)
        starred_ids = {q.id for q in starred_quotes}

        all_quotes = db.query(Quote).filter(Quote.project_id == project_id).all()

        if body is not None and body.ids is not None:
            # Scoped export — clip exactly the quotes the picker handed over.
            requested = set(body.ids)
            combined_quotes = [
                q for q in all_quotes
                if f"q-{q.participant_id}-{int(q.start_timecode)}" in requested
            ]
            hero_ids: set[int] = set()
        else:
            # Legacy no-scope caller — historical starred ∪ featured union.
            hero_quotes = pick_featured_quotes(all_quotes, n=9)
            hero_ids = {q.id for q in hero_quotes}
            combined_ids = starred_ids | hero_ids
            combined_quotes = [q for q in all_quotes if q.id in combined_ids]

        # Build manifest
        speaker_map = _load_speaker_names(db, project_id)
        session_media, session_durations = _load_session_media(
            db, project_id, project_dir,
        )

        quote_likes = _quotes_to_quotelike(combined_quotes, starred_ids, hero_ids)
        specs = build_clip_manifest(
            quote_likes, speaker_map, session_media, session_durations,
            anonymise=anonymise,
        )
        specs = merge_adjacent_clips(specs)

        if not specs:
            return ClipStartResponse(status="no_clips", total=0)

        # Determine timecode format
        max_duration = max(session_durations.values()) if session_durations else 0
        use_hours = max_duration >= 3600

        # Count unique participants for zero-padding
        participant_ids = {s.participant_id for s in specs}
        participant_count = len(participant_ids)

        # Subtitles are built now, while the DB session is open; the job
        # runs after this request returns.
        cues_by_clip = {
            i: _build_clip_cues(db, project_id, spec) for i, spec in enumerate(specs)
        }

        # Create clips directory
        clips_dir = output_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        # Initialise job state
        _jobs[project_id] = {
            "status": "running",
            "progress": 0,
            "total": len(specs),
            "completed_count": 0,
            "skipped_count": 0,
            "current_clip": "",
            "output_dir": None,
        }

        # Spawn background task
        asyncio.create_task(
            _run_clip_extraction(
                project_id, specs, clips_dir, participant_count,
                use_hours, anonymise, cues_by_clip,
            )
        )

        return ClipStartResponse(
            status="started",
            total=len(specs),
            pii_warning=anonymise,
        )

    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /projects/{id}/export/clips/status — poll progress
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/export/clips/status")
async def get_clip_status(
    project_id: int,
) -> ClipStatusResponse:
    """Poll clip extraction progress."""
    job = _jobs.get(project_id)
    if job is None:
        return ClipStatusResponse(
            status="idle",
            progress=0,
            total=0,
            completed_count=0,
            skipped_count=0,
            current_clip="",
            output_dir=None,
        )

    return ClipStatusResponse(
        status=job.get("status", "idle"),
        progress=job.get("progress", 0),
        total=job.get("total", 0),
        completed_count=job.get("completed_count", 0),
        skipped_count=job.get("skipped_count", 0),
        current_clip=job.get("current_clip", ""),
        output_dir=job.get("output_dir"),
    )


# ---------------------------------------------------------------------------
# POST /projects/{id}/export/clips/cancel — stop a running job
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/export/clips/cancel")
async def cancel_clip_extraction(project_id: int) -> dict[str, Any]:
    """Signal a running clip-extraction job to stop after the current clip.

    The background loop polls the job's status each iteration and breaks when it
    sees ``cancelled``. Clips already written stay on disk. No-op-safe: 404 when
    nothing is in flight.
    """
    job = _jobs.get(project_id)
    if job is None or job.get("status") not in ("pending", "running"):
        raise HTTPException(status_code=404, detail="No clip extraction in progress")
    job["status"] = "cancelled"
    return {"cancelled": True}


# ---------------------------------------------------------------------------
# POST /projects/{id}/export/clips/reveal — open in Finder
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/export/clips/reveal")
async def reveal_clips(
    request: Request,
    project_id: int,
) -> dict[str, Any]:
    """Open the clips directory in the system file manager."""
    job = _jobs.get(project_id)
    if job is None or job.get("output_dir") is None:
        raise HTTPException(status_code=404, detail="No completed clip extraction")

    clips_dir = Path(job["output_dir"])
    project_dir = request.app.state.project_dir
    output_dir = _resolve_output_dir(project_dir)

    # Path validation: clips dir must be inside output dir
    if output_dir is None:
        raise HTTPException(status_code=400, detail="No project directory configured")

    resolved_clips = clips_dir.resolve()
    resolved_output = output_dir.resolve()
    if not resolved_clips.is_relative_to(resolved_output):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not resolved_clips.is_dir():
        raise HTTPException(status_code=404, detail="Clips directory not found")

    # Find first clip file to reveal
    clip_files = sorted(resolved_clips.glob("*.mp4")) + sorted(resolved_clips.glob("*.m4a"))
    reveal_path = clip_files[0] if clip_files else resolved_clips

    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", "-R", str(reveal_path)], check=False)
    elif system == "Linux":
        subprocess.run(["xdg-open", str(resolved_clips)], check=False)
    else:
        # Windows or unknown — return the path for the caller to handle
        return {"revealed": False, "path": str(resolved_clips)}

    return {"revealed": True, "path": str(reveal_path)}
