"""Audio file utilities: probing duration, format detection, ffmpeg wrappers."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def probe_duration(file_path: Path) -> float | None:
    """Probe the duration of an audio or video file using ffprobe.

    Returns duration in seconds, or None if probing fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("ffprobe failed for %s: %s", file_path, result.stderr)
            return None
        data = json.loads(result.stdout)
        duration_str = data.get("format", {}).get("duration")
        if duration_str:
            return float(duration_str)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning("Could not probe %s: %s", file_path, exc)
    return None


def extract_audio_from_video(
    video_path: Path,
    output_path: Path,
    sample_rate: int = 16000,
) -> Path:
    """Extract audio from a video file as 16kHz mono WAV.

    Args:
        video_path: Path to the video file.
        output_path: Where to write the extracted WAV.
        sample_rate: Target sample rate (default 16000 for Whisper).

    Returns:
        Path to the extracted WAV file.

    Raises:
        RuntimeError: If ffmpeg fails.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",                    # no video
            "-acodec", "pcm_s16le",   # 16-bit PCM
            "-ar", str(sample_rate),  # sample rate
            "-ac", "1",               # mono
            "-y",                     # overwrite
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=600,  # 10 minutes max
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed to extract audio from {video_path}: {result.stderr}"
        )

    logger.info("Extracted audio: %s -> %s", video_path.name, output_path.name)
    return output_path


def has_audio_stream(file_path: Path) -> bool:
    """Check if a video file contains an audio stream."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return "audio" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
