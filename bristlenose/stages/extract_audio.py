"""Stage 2: Extract audio from video files via ffmpeg."""

from __future__ import annotations

import logging
from pathlib import Path

from bristlenose.models import FileType, InputSession
from bristlenose.utils.audio import extract_audio_from_video, has_audio_stream

logger = logging.getLogger(__name__)


def extract_audio_for_sessions(
    sessions: list[InputSession],
    temp_dir: Path,
) -> list[InputSession]:
    """Extract audio from video files in sessions that need it.

    For each session:
    - If it has a video file and no standalone audio file, extract audio.
    - Sets session.audio_path to the extracted or existing audio file.
    - Skips sessions that already have an audio file.
    - Skips sessions with existing transcripts (docx/srt) unless audio is
      needed for timecode alignment.

    Args:
        sessions: List of InputSession objects.
        temp_dir: Directory to write extracted audio files.

    Returns:
        Updated list of sessions with audio_path set where applicable.
    """
    temp_dir.mkdir(parents=True, exist_ok=True)

    for session in sessions:
        # If session already has an audio file, use it
        audio_files = [f for f in session.files if f.file_type == FileType.AUDIO]
        if audio_files:
            session.audio_path = audio_files[0].path
            logger.info(
                "%s: Using existing audio file: %s",
                session.participant_id,
                audio_files[0].path.name,
            )
            continue

        # If session has a video file, extract audio
        video_files = [f for f in session.files if f.file_type == FileType.VIDEO]
        if video_files:
            video_path = video_files[0].path

            # Check the video actually has an audio stream
            if not has_audio_stream(video_path):
                logger.warning(
                    "%s: Video file %s has no audio stream, skipping.",
                    session.participant_id,
                    video_path.name,
                )
                continue

            output_path = temp_dir / f"{session.participant_id}_extracted.wav"
            try:
                extracted = extract_audio_from_video(video_path, output_path)
                session.audio_path = extracted
                logger.info(
                    "%s: Extracted audio from %s",
                    session.participant_id,
                    video_path.name,
                )
            except RuntimeError as exc:
                logger.error(
                    "%s: Failed to extract audio from %s: %s",
                    session.participant_id,
                    video_path.name,
                    exc,
                )
                continue

        # No audio or video — session must rely on subtitle/docx transcripts
        if session.audio_path is None and not session.has_existing_transcript:
            logger.warning(
                "%s: No audio, video, or transcript files found.",
                session.participant_id,
            )

    return sessions
