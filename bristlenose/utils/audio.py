"""Audio file utilities: probing duration, format detection, ffmpeg wrappers."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from pathlib import Path

from bristlenose.utils.bundled_binary import bundled_binary_path
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)


class AudioToolError(RuntimeError):
    """The ffprobe/ffmpeg toolchain failed to *run*.

    Raised on a non-zero exit, a missing binary, a shared-library load failure
    (e.g. ``error while loading shared libraries: libblas.so.3``), a timeout, or
    an unreadable/corrupt input file.

    This is deliberately distinct from a video that *genuinely contains no audio
    stream* (a valid, non-fatal condition — a silent screen recording). Callers
    must fail loud on this rather than treating it as "no audio" and silently
    skipping transcription: a broken tool must never be mislabelled as "your
    interview has no audio" and reported as a successful, empty report.
    """


def probe_duration(file_path: Path) -> float | None:
    """Probe the duration of an audio or video file using ffprobe.

    Returns duration in seconds, or None if probing fails.
    """
    ffprobe = bundled_binary_path("ffprobe") or "ffprobe"
    try:
        # Fetch first if this is a cloud placeholder. The 30s budget below is
        # for a corrupt file, not a download — see ensure_materialised.
        ensure_materialised(file_path)
    except CloudFetchTimeoutError as exc:
        logger.warning("Could not probe %s: %s", file_path, exc)
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
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
        AudioToolError: If ffmpeg fails to run or exits non-zero.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Fetch first if this is a cloud placeholder. The 600s budget below is
        # generous, but a large recording on a domestic uplink can outlast it —
        # and when it does, ffmpeg's timeout reads as "your video is broken".
        # Same reasoning as has_audio_stream; see docs/design-project-storage.md.
        ensure_materialised(video_path)
    except CloudFetchTimeoutError as exc:
        raise AudioToolError(str(exc)) from exc

    # Use hardware video decode on macOS (VideoToolbox / Media Engine).
    # Harmless no-op for audio-only inputs; ignored if unsupported.
    hwaccel = ["-hwaccel", "videotoolbox"] if platform.system() == "Darwin" else []

    ffmpeg = bundled_binary_path("ffmpeg") or "ffmpeg"
    result = subprocess.run(
        [
            ffmpeg,
            *hwaccel,
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
        raise AudioToolError(
            f"ffmpeg failed to extract audio from {video_path.name} "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )

    logger.info("Extracted audio: %s -> %s", video_path.name, output_path.name)
    return output_path


def has_audio_stream(file_path: Path) -> bool:
    """Return True if *file_path* contains at least one audio stream.

    A clean ffprobe run that finds no audio streams returns ``False`` — a valid,
    non-fatal condition (e.g. a silent screen recording).

    Raises:
        AudioToolError: if ffprobe fails to *run* — non-zero exit (broken
            toolchain, corrupt/unreadable file), missing binary, or timeout.
            The caller MUST NOT interpret this as "no audio stream": a broken
            tool must fail loud, not silently skip transcription. Uses
            ``-v error`` (not ``-v quiet``) so the failure reason survives in
            stderr for the exception message.
    """
    ffprobe = bundled_binary_path("ffprobe") or "ffprobe"
    try:
        # Fetch first if this is a cloud placeholder. Without this the download
        # happens *inside* the 30s timeout below and surfaces as "ffprobe timed
        # out", which reads as "your video is broken" — the opposite of what
        # happened. Reproduced 29 Jul 2026; see docs/design-project-storage.md.
        ensure_materialised(file_path)
    except CloudFetchTimeoutError as exc:
        raise AudioToolError(str(exc)) from exc
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise AudioToolError(
            f"ffprobe binary not found ({ffprobe!r}); cannot probe {file_path.name}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioToolError(
            f"ffprobe timed out after 30s probing {file_path.name}"
        ) from exc

    if result.returncode != 0:
        raise AudioToolError(
            f"ffprobe failed to probe {file_path.name} "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )

    return "audio" in result.stdout
