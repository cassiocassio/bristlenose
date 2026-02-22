"""Video thumbnail extraction: keyframe selection heuristic and FFmpeg wrapper."""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bristlenose.models import FullTranscript, InputSession

logger = logging.getLogger(__name__)

# Heuristic constants
_WINDOW_SECONDS = 180.0  # First 3 minutes
_FALLBACK_SECONDS = 60.0  # If no participant found, grab frame at 1 min

# FFmpeg output settings — 4× display width (96 px CSS) for retina.
_THUMB_WIDTH = 384
_THUMB_QUALITY = 5  # JPEG quality scale: 2 = best, 31 = worst


def choose_thumbnail_time(
    transcript: FullTranscript,
    *,
    window_seconds: float = _WINDOW_SECONDS,
    fallback_seconds: float = _FALLBACK_SECONDS,
) -> float:
    """Choose the best timestamp for a thumbnail frame.

    Heuristic:
    1. Find the first PARTICIPANT segment within the first *window_seconds*.
    2. Use its *end_time* — the boundary between segments where the
       participant's mouth is likely closed (better still frame).
    3. If no participant segment found, return *fallback_seconds*.
    4. If the video is shorter than *fallback_seconds*, return 0.0.

    Args:
        transcript: Full transcript with speaker roles assigned.
        window_seconds: Only consider segments within this many seconds.
        fallback_seconds: Default timestamp when no participant found.

    Returns:
        Timestamp in seconds for the keyframe.
    """
    from bristlenose.models import SpeakerRole

    for seg in transcript.segments:
        if seg.start_time > window_seconds:
            break
        if seg.speaker_role == SpeakerRole.PARTICIPANT:
            return seg.end_time

    # Fallback: no participant in the window.
    if transcript.duration_seconds < fallback_seconds:
        return 0.0
    return fallback_seconds


def extract_thumbnail(
    video_path: Path,
    output_path: Path,
    timestamp: float,
    *,
    width: int = _THUMB_WIDTH,
    quality: int = _THUMB_QUALITY,
) -> Path | None:
    """Extract a single JPEG frame from a video file.

    Uses FFmpeg's ``-ss`` (input seeking) for fast keyframe-based seeking,
    then scales to *width* pixels (preserving aspect ratio).

    Args:
        video_path: Path to the source video file.
        output_path: Where to write the JPEG thumbnail.
        timestamp: Time in seconds to seek to.
        width: Target width in pixels (height auto-scaled to preserve ratio).
        quality: JPEG quality (2 = best, 31 = worst).

    Returns:
        Path to the written thumbnail, or ``None`` if extraction failed.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    hwaccel = ["-hwaccel", "videotoolbox"] if platform.system() == "Darwin" else []

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                *hwaccel,
                "-ss", str(timestamp),
                "-i", str(video_path),
                "-frames:v", "1",
                "-vf", f"scale={width}:-1",
                "-q:v", str(quality),
                "-y",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "Thumbnail extraction failed for %s: %s",
                video_path.name,
                result.stderr[:200],
            )
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Could not extract thumbnail from %s: %s", video_path.name, exc)
        return None

    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info("Extracted thumbnail: %s @ %.1fs", video_path.name, timestamp)
        return output_path

    return None


def extract_thumbnails(
    sessions: list[InputSession],
    transcripts: list[FullTranscript],
    thumbnails_dir: Path,
) -> dict[str, Path]:
    """Extract thumbnail frames for all video sessions.

    Skips sessions without video files and sessions where the thumbnail
    already exists on disk (cache-friendly for resume).

    Args:
        sessions: All input sessions (for video file paths).
        transcripts: All transcripts (for speaker role heuristic).
        thumbnails_dir: Directory to write thumbnails into.

    Returns:
        Mapping of session_id to path of the thumbnail JPEG.
    """
    from bristlenose.models import FileType

    # Build transcript lookup.
    transcript_by_sid: dict[str, FullTranscript] = {
        t.session_id: t for t in transcripts
    }

    thumbnail_map: dict[str, Path] = {}

    for session in sessions:
        if not session.has_video:
            continue

        sid = session.session_id
        output_path = thumbnails_dir / f"{sid}.jpg"

        # Cache: skip if already extracted.
        if output_path.exists() and output_path.stat().st_size > 0:
            thumbnail_map[sid] = output_path
            continue

        # Find the video file.
        video_file = next(
            (f for f in session.files if f.file_type == FileType.VIDEO),
            None,
        )
        if video_file is None or not video_file.path.exists():
            continue

        # Choose timestamp from transcript heuristic.
        transcript = transcript_by_sid.get(sid)
        if transcript:
            timestamp = choose_thumbnail_time(transcript)
        else:
            timestamp = _FALLBACK_SECONDS

        # Extract.
        result = extract_thumbnail(video_file.path, output_path, timestamp)
        if result is not None:
            thumbnail_map[sid] = result

    return thumbnail_map
