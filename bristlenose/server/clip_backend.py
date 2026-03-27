"""Clip extraction backends: Protocol + FFmpeg implementation.

The Protocol defines the contract that both FFmpeg (CLI/serve) and
future AVFoundation (macOS desktop) backends implement.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class ClipBackend(Protocol):
    """Interface for clip extraction backends."""

    def extract_clip(
        self, source: Path, output: Path, start: float, end: float,
    ) -> Path | None:
        """Extract a clip. Returns output path on success, None on failure."""
        ...

    def check_available(self) -> tuple[bool, str]:
        """Check if this backend is available. Returns (ok, message)."""
        ...


class FFmpegBackend:
    """FFmpeg stream-copy backend for clip extraction."""

    def check_available(self) -> tuple[bool, str]:
        """Check if ffmpeg is on PATH."""
        if shutil.which("ffmpeg") is None:
            return (False, "FFmpeg not found on PATH")
        return (True, "")

    def extract_clip(
        self, source: Path, output: Path, start: float, end: float,
    ) -> Path | None:
        """Extract a clip using FFmpeg stream-copy into .mp4 container.

        Uses ``-ss`` before ``-i`` (input seeking) for speed.
        Stream-copy (``-c copy``) preserves codec without re-encoding.
        """
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-ss", f"{start:.3f}",
                    "-to", f"{end:.3f}",
                    "-i", str(source),
                    "-c", "copy",
                    "-y",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning(
                    "Clip extraction failed for %s (exit %d): %s",
                    source.name,
                    result.returncode,
                    result.stderr[-500:],
                )
                return None
        except subprocess.TimeoutExpired:
            logger.warning("Clip extraction timed out for %s", source.name)
            return None
        except FileNotFoundError:
            logger.warning("FFmpeg not found when extracting clip from %s", source.name)
            return None

        if output.exists() and output.stat().st_size > 0:
            return output

        return None
