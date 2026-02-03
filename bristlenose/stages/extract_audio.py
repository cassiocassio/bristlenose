"""Stage 2: Extract audio from video files via ffmpeg."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from bristlenose.models import FileType, InputSession
from bristlenose.utils.audio import extract_audio_from_video, has_audio_stream

logger = logging.getLogger(__name__)

# Max concurrent FFmpeg processes.  Kept modest — each process is I/O-heavy
# and (on macOS) may share the hardware media engine.
_DEFAULT_CONCURRENCY = 4


async def extract_audio_for_sessions(
    sessions: list[InputSession],
    temp_dir: Path,
    concurrency: int = _DEFAULT_CONCURRENCY,
) -> list[InputSession]:
    """Extract audio from video files in sessions that need it.

    For each session:
    - If it has a video file and no standalone audio file, extract audio.
    - Sets session.audio_path to the extracted or existing audio file.
    - Skips sessions that already have an audio file.
    - Skips sessions with existing transcripts (docx/srt) unless audio is
      needed for timecode alignment.

    Video extractions run concurrently (up to *concurrency* FFmpeg processes).

    Args:
        sessions: List of InputSession objects.
        temp_dir: Directory to write extracted audio files.
        concurrency: Max concurrent FFmpeg processes (default 4).

    Returns:
        Updated list of sessions with audio_path set where applicable.
    """
    temp_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(concurrency)
    tasks: list[asyncio.Task[None]] = []

    for session in sessions:
        # If session already has an audio file, use it (no extraction needed)
        audio_files = [f for f in session.files if f.file_type == FileType.AUDIO]
        if audio_files:
            session.audio_path = audio_files[0].path
            logger.info(
                "%s: Using existing audio file: %s",
                session.session_id,
                audio_files[0].path.name,
            )
            continue

        # If session already has a platform transcript, skip extraction — the
        # pipeline will use the parsed transcript and never call Whisper.
        if session.has_existing_transcript:
            logger.info(
                "%s: Has platform transcript, skipping audio extraction",
                session.session_id,
            )
            continue

        # If session has a video file, schedule extraction
        video_files = [f for f in session.files if f.file_type == FileType.VIDEO]
        if video_files:
            video_path = video_files[0].path
            output_path = temp_dir / f"{session.session_id}_extracted.wav"
            tasks.append(
                asyncio.create_task(
                    _extract_one(session, video_path, output_path, semaphore)
                )
            )
            continue

        # No audio or video — session must rely on subtitle/docx transcripts
        if session.audio_path is None and not session.has_existing_transcript:
            logger.warning(
                "%s: No audio, video, or transcript files found.",
                session.session_id,
            )

    if tasks:
        await asyncio.gather(*tasks)

    return sessions


async def _extract_one(
    session: InputSession,
    video_path: Path,
    output_path: Path,
    semaphore: asyncio.Semaphore,
) -> None:
    """Extract audio for a single session, bounded by *semaphore*."""
    async with semaphore:
        # has_audio_stream and extract_audio_from_video are blocking
        # (subprocess.run) — run in the default thread-pool executor.
        has_audio = await asyncio.to_thread(has_audio_stream, video_path)
        if not has_audio:
            logger.warning(
                "%s: Video file %s has no audio stream, skipping.",
                session.session_id,
                video_path.name,
            )
            return

        try:
            extracted = await asyncio.to_thread(
                extract_audio_from_video, video_path, output_path
            )
            session.audio_path = extracted
            logger.info(
                "%s: Extracted audio from %s",
                session.session_id,
                video_path.name,
            )
        except RuntimeError as exc:
            logger.error(
                "%s: Failed to extract audio from %s: %s",
                session.session_id,
                video_path.name,
                exc,
            )
