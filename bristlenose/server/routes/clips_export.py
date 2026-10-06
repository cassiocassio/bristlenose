"""Video clip extraction endpoints — async FFmpeg stream-copy.

POST /projects/{id}/export/clips  — start extraction job
GET  /projects/{id}/export/clips/status — poll progress
POST /projects/{id}/export/clips/reveal — open clips folder in Finder
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from bristlenose.i18n import get_locale
from bristlenose.server import speaker_slots
from bristlenose.server.clip_backend import FFmpegBackend
from bristlenose.server.clip_manifest import (
    ClipSpec,
    _QuoteLike,
    build_clip_filename,
    build_clip_manifest,
    merge_adjacent_clips,
)
from bristlenose.server.clip_subtitles import (
    CORRECTION_TAIL_SECONDS,
    UNPLACED,
    Correction,
    Cue,
    SegmentInput,
    WordTiming,
    apply_correction,
    build_cues,
    iso639_2,
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
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

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
    """Map (session_id, speaker_code) → display_name.

    Keyed by the transcript's slot code. An outer join to Person: an
    unidentified moderator (route C) maps to ``""`` rather than vanishing.
    """
    rows = (
        db.query(
            SessionModel.session_id,
            SessionSpeaker.speaker_code,
            Person.short_name,
            Person.full_name,
        )
        .join(SessionSpeaker, SessionSpeaker.session_id == SessionModel.id)
        .outerjoin(Person, Person.id == SessionSpeaker.person_id)
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
    """Load all starred quotes for a project that count as evidence."""
    out = speaker_slots.evidence_out(db, project_id)
    return [q for q in (
        db.query(Quote)
        .join(QuoteState, QuoteState.quote_id == Quote.id)
        .filter(
            Quote.project_id == project_id,
            QuoteState.is_starred == True,  # noqa: E712
        )
        .all()
    ) if speaker_slots.counts(q, out)]


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
    """Transcript segments overlapping ``[start, end]`` for one session.

    A segment whose word timings can't be read is still subtitled, with its
    words spread across the segment — and the loss of sync is logged, once
    per call, rather than passing silently.
    """
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
    unreadable = 0
    for row in rows:
        words: tuple[WordTiming, ...] | None = None
        if row.words_json:
            try:
                parsed = []
                for w in json.loads(row.words_json):
                    if not isinstance(w["t"], str):
                        raise TypeError("word text is not a string")
                    parsed.append(WordTiming(text=w["t"], start=float(w["s"]), end=float(w["e"])))
                words = tuple(parsed)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                unreadable += 1
                words = None
        segments.append(SegmentInput(
            speaker_code=row.speaker_code,
            start=row.start_time,
            end=row.end_time,
            text=row.text,
            words=words or None,
        ))
    if unreadable:
        logger.warning(
            "Clip subtitles: %d segment(s) in %s had unreadable word timings; "
            "their words are spread across the segment instead",
            unreadable, session_id,
        )
    return segments


def _load_corrections(
    db: DbSession, project_id: int, session_id: str, start: float, end: float,
) -> list[Correction]:
    """The researcher's latest edit of each quote near ``[start, end]``.

    Widened by ``CORRECTION_TAIL_SECONDS``: a quote's recorded end can fall
    before its last words, so a quote ending just before the clip may still
    have corrected words inside it.
    """
    rows = (
        db.query(Quote, QuoteEdit.edited_text)
        .join(QuoteEdit, QuoteEdit.quote_id == Quote.id)
        .filter(
            Quote.project_id == project_id,
            Quote.session_id == session_id,
            Quote.end_timecode > start - CORRECTION_TAIL_SECONDS,
            Quote.start_timecode < end,
        )
        .order_by(QuoteEdit.edited_at.desc())
        .all()
    )
    seen: set[int] = set()
    latest: list[Correction] = []
    for quote, edited in rows:
        # Mark seen before the no-op check, so an older edit can never stand
        # in for a newest one that reverts the quote to its original text.
        if quote.id in seen:
            continue
        seen.add(quote.id)
        if edited == quote.text:
            continue
        latest.append(Correction(
            speaker_code=quote.participant_id,
            start=quote.start_timecode,
            end=quote.end_timecode,
            original=quote.text,
            corrected=edited,
            quote_ref=f"q-{quote.participant_id}-{int(quote.start_timecode)}",
        ))
    return sorted(latest, key=lambda c: c.start)


def _build_clip_cues(db: DbSession, project_id: int, spec: ClipSpec) -> list[Cue]:
    """Subtitle cues for one clip: everyone audible, with corrections applied.

    Never carries a speaker's name: speakers are told apart by colour only.
    A correction that can't be placed word by word is left out and logged:
    the transcript's own words stand rather than a guess.
    """
    segments = _load_segments(db, project_id, spec.session_id, spec.start, spec.end)
    tokens = [tok for seg in segments for tok in tokens_for_segment(seg)]
    for corr in _load_corrections(db, project_id, spec.session_id, spec.start, spec.end):
        tokens, outcome = apply_correction(tokens, corr)
        if outcome == UNPLACED:
            logger.warning(
                "Clip subtitles: the researcher's correction to %s could not be "
                "placed word by word, so the transcript's wording is used",
                corr.quote_ref,
            )
    return build_cues(tokens, spec.start, spec.end, spec.participant_id)


def _safe_clip_cues(db: DbSession, project_id: int, spec: ClipSpec) -> list[Cue]:
    """``_build_clip_cues``, but a failure costs this clip its subtitles only.

    Subtitles are additive: an error building them must never fail the export.
    """
    try:
        return _build_clip_cues(db, project_id, spec)
    except Exception:
        logger.warning(
            "Clip subtitles skipped for %s at %.1fs: could not build them",
            spec.session_id, spec.start, exc_info=True,
        )
        return []


def session_cues(db: DbSession, project_id: int, session_id: str) -> list[Cue]:
    """Subtitle cues for a whole session, for the popout player.

    The same cues an exported clip gets — everyone audible, corrections
    applied, BBC colours — over the whole recording. The session's primary
    participant (the ``p`` code with the most words) takes white.
    """
    segments = _load_segments(db, project_id, session_id, 0.0, float("inf"))
    tokens = [tok for seg in segments for tok in tokens_for_segment(seg)]
    for corr in _load_corrections(db, project_id, session_id, 0.0, float("inf")):
        tokens, _outcome = apply_correction(tokens, corr)
    # A participant's tag recoded as the moderator (§J7 R2) is not primary.
    out = {tag for sid, tag in speaker_slots.evidence_out(db, project_id) if sid == session_id}
    words: dict[str, int] = {}
    for tok in tokens:
        if tok.speaker_code.startswith("p") and tok.speaker_code not in out:
            words[tok.speaker_code] = words.get(tok.speaker_code, 0) + 1
    primary = max(words, key=lambda c: words[c]) if words else ""
    end = max((tok.end for tok in tokens), default=0.0)
    return build_cues(tokens, 0.0, end, primary)


@router.get("/projects/{project_id}/sessions/{session_id}/subtitles.vtt")
def get_session_subtitles(
    request: Request, project_id: int, session_id: str,
) -> Response:
    """WebVTT for a whole session, for the popout player's subtitle track.

    A plain ``def``, so FastAPI runs it in its threadpool: building a whole
    session's cues takes 100–250 ms (measured on FOSSDA) and would otherwise
    hold the event loop on every popout open.

    Fetched by the report with the bearer token and handed to the player as
    text: a ``<track src>`` cannot send the header, and the player page is
    served without one.
    """
    db = _get_db(request)
    try:
        _check_project(db, project_id)
        row = (
            db.query(SessionModel.language)
            .filter(SessionModel.project_id == project_id,
                    SessionModel.session_id == session_id)
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        vtt = to_webvtt(session_cues(db, project_id, session_id))
        # The player labels its track with this (``srclang``); the same
        # detected-else-app-language rule the clip export uses.
        language = row[0] or get_locale()
    finally:
        db.close()
    return Response(vtt, media_type="text/vtt; charset=utf-8",
                    headers={"Cache-Control": "no-store", "Content-Language": language})


# ---------------------------------------------------------------------------
# Async job runner
# ---------------------------------------------------------------------------


def _subtitle_languages(db: DbSession, project_id: int) -> dict[str, str]:
    """Session id → ISO 639-2 code for its subtitle track.

    The language Whisper detected, where the transcript recorded one;
    otherwise the app's language, because a track tagged ``und`` is hidden
    by every "subtitles in my language" setting — a slightly wrong label is
    better than subtitles that never appear.
    """
    fallback = iso639_2(get_locale())
    rows = (
        db.query(SessionModel.session_id, SessionModel.language)
        .filter(SessionModel.project_id == project_id)
        .all()
    )
    return {sid: iso639_2(lang) if lang else fallback for sid, lang in rows}


async def _cut_clip(
    backend: FFmpegBackend, spec: ClipSpec, output_path: Path, cues: list[Cue],
    language: str = "und",
) -> tuple[Path | None, bool]:
    """Cut one clip, with its subtitle track when there are cues.

    Returns the clip path (None if it could not be cut) and whether the
    subtitle track made it in. The SRT lives in the system temp directory,
    never in the researcher's clips folder, and is removed afterwards.
    """
    if cues:
        fd, tmp = tempfile.mkstemp(suffix=".srt")
        srt_path = Path(tmp)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(to_srt(cues))
            # Run FFmpeg in a thread to avoid blocking the event loop
            result = await asyncio.to_thread(
                backend.extract_clip, spec.source_path, output_path,
                spec.start, spec.end, srt_path, language,
            )
            if result is not None:
                return result, True
            logger.warning(
                "Clip %s failed with its subtitle track; retrying without it",
                output_path.name,
            )
        except OSError:
            logger.warning(
                "Could not write the subtitle track for %s; cutting without it",
                output_path.name, exc_info=True,
            )
        finally:
            srt_path.unlink(missing_ok=True)
    result = await asyncio.to_thread(
        backend.extract_clip, spec.source_path, output_path, spec.start, spec.end,
    )
    return result, False


async def _run_clip_extraction(
    project_id: int,
    clips: list[ClipSpec],
    clips_dir: Path,
    participant_count: int,
    use_hours: bool,
    anonymise: bool,
    cues_by_clip: dict[int, list[Cue]] | None = None,
    languages: dict[str, str] | None = None,
    burn: bool = False,
) -> None:
    """Extract clips in background. Updates module-level _jobs state.

    Each clip with transcript text gets a ``.vtt`` beside it and the same
    cues muxed in as a soft subtitle track. A clip whose subtitle mux fails
    is cut again without subtitles rather than lost. With ``burn``, a video
    clip with cues also gets a copy with the subtitles in its pixels, beside
    it as ``<name> (subtitled).mp4`` — the clean clip is never replaced. Any unexpected error
    marks the job failed rather than leaving it "running", which would
    refuse every later export until the server restarts.
    """
    backend = FFmpegBackend()
    job = _jobs.get(project_id)
    if job is None:
        return

    try:
        manifest_entries: list[dict[str, Any]] = []

        for i, spec in enumerate(clips):
            # Stop if cancelled, or if a newer job has replaced this one
            # (cancel, then start again, while this clip was being cut).
            if job.get("status") == "cancelled" or _jobs.get(project_id) is not job:
                break

            filename = build_clip_filename(
                spec, participant_count, use_hours, anonymise=anonymise,
            )
            output_path = clips_dir / filename
            stem = filename.rsplit(".", 1)[0]

            job["progress"] = i
            job["current_clip"] = stem

            # Fetch an evicted cloud source once, before either attempt, so a
            # source that never arrives costs one wait and is not retried.
            try:
                await asyncio.to_thread(ensure_materialised, spec.source_path)
            except CloudFetchTimeoutError as exc:
                job["skipped_count"] = job.get("skipped_count", 0) + 1
                logger.warning("Skipped clip %s: %s", filename, exc)
                continue

            cues = (cues_by_clip or {}).get(i) or []
            result, with_track = await _cut_clip(
                backend, spec, output_path, cues,
                (languages or {}).get(spec.session_id, "und"),
            )

            vtt_path = clips_dir / f"{stem}.vtt"
            vtt_name: str | None = None
            burned_path = clips_dir / f"{stem} (subtitled).mp4"
            burned_name: str | None = None
            if result is not None:
                job["completed_count"] = job.get("completed_count", 0) + 1
                if cues:
                    try:
                        vtt_path.write_text(to_webvtt(cues), encoding="utf-8")
                        vtt_name = vtt_path.name
                    except OSError:
                        logger.warning(
                            "Could not write %s", vtt_path.name, exc_info=True,
                        )
                if burn and cues and not spec.is_audio_only:
                    job["current_clip"] = burned_path.stem
                    job["burn_attempted"] = job.get("burn_attempted", 0) + 1
                    try:
                        burned = await asyncio.to_thread(
                            backend.burn_subtitles, output_path, cues, burned_path,
                        )
                    except Exception:
                        # The subtitled copy is optional: an unexpected error
                        # costs that copy, never the clean clips already made.
                        logger.warning(
                            "Burning subtitles into %s failed", filename, exc_info=True,
                        )
                        burned = None
                    if burned is not None:
                        burned_name = burned_path.name
                        job["burned_count"] = job.get("burned_count", 0) + 1
                manifest_entries.append({
                    "quote_id": spec.quote_id,
                    "participant_id": spec.participant_id,
                    "session_id": spec.session_id,
                    "filename": filename,
                    "subtitles": vtt_name,
                    "burned": burned_name,
                    "start": spec.start,
                    "end": spec.end,
                })
            else:
                job["skipped_count"] = job.get("skipped_count", 0) + 1
                logger.warning("Skipped clip %s (extraction failed)", filename)
            if vtt_name is None:
                # A .vtt left by an earlier export must not sit beside a clip
                # that no longer has one.
                vtt_path.unlink(missing_ok=True)
            if burned_name is None:
                # Nor a burned copy: its pixels may predate a correction (a
                # name redacted to "[her]"), and nothing would say it is stale.
                burned_path.unlink(missing_ok=True)

        # Write clips_manifest.json
        manifest = {
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "total": len(clips),
            "completed": job.get("completed_count", 0),
            "skipped": job.get("skipped_count", 0),
            "burned": job.get("burned_count", 0),
            "anonymised": anonymise,
            "clips": manifest_entries,
        }
        manifest_path = clips_dir / "clips_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")

        # A cancelled job broke out of the loop early — record that, don't
        # overwrite it with "completed". Clips written before the break stay on
        # disk (a partial folder is honest and usable), so output_dir is set.
        cancelled = job.get("status") == "cancelled"
        job["status"] = "cancelled" if cancelled else "completed"
        if not cancelled:
            job["progress"] = len(clips)
    except Exception:
        logger.exception("Clip extraction failed")
        job["status"] = "failed"
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
    # Also write a copy of each video clip with the subtitles in its pixels
    # ("for slides"). Off by default; the checkbox is the whole of the UI.
    burn_subtitles: bool = False


class ClipStartResponse(BaseModel):
    status: str
    total: int
    pii_warning: bool = False
    # Burn-in was asked for but this ffmpeg can't do it (no libass/x264 —
    # Homebrew's build). The clips and their .vtt files are still made.
    burn_unavailable: bool = False


class ClipStatusResponse(BaseModel):
    status: str
    progress: int
    total: int
    completed_count: int
    skipped_count: int
    current_clip: str
    output_dir: str | None
    burned_count: int = 0
    #: Clips a subtitled copy was attempted for; more than ``burned_count``
    #: means some copies failed, which the report says rather than "Done".
    burn_attempted: int = 0


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
    burn_requested = body.burn_subtitles if body else False

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

        all_quotes = speaker_slots.evidence_quotes(db, project_id)

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
            i: _safe_clip_cues(db, project_id, spec) for i, spec in enumerate(specs)
        }
        languages = _subtitle_languages(db, project_id)
        # Burning is asked for per export; whether this ffmpeg can do it is
        # checked once here, so the researcher hears about it at the start.
        burn = burn_requested and await asyncio.to_thread(backend.can_burn_subtitles)

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
                use_hours, anonymise, cues_by_clip, languages, burn,
            )
        )

        return ClipStartResponse(
            status="started",
            total=len(specs),
            pii_warning=anonymise,
            burn_unavailable=burn_requested and not burn,
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
        burn_attempted=job.get("burn_attempted", 0),
        burned_count=job.get("burned_count", 0),
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
