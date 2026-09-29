"""Clip extraction backends: Protocol + FFmpeg implementation.

The Protocol defines the contract that both FFmpeg (CLI/serve) and
future AVFoundation (macOS desktop) backends implement.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from bristlenose.utils.bundled_binary import bundled_binary_path
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)


@runtime_checkable
class ClipBackend(Protocol):
    """Interface for clip extraction backends."""

    def extract_clip(
        self, source: Path, output: Path, start: float, end: float,
        subtitles: Path | None = None, subtitle_language: str = "und",
    ) -> Path | None:
        """Extract a clip. Returns output path on success, None on failure.

        ``subtitles`` (an SRT file, timed from the clip's start) is muxed in
        as a soft subtitle track when given, tagged ``subtitle_language``
        (ISO 639-2).
        """
        ...

    def check_available(self) -> tuple[bool, str]:
        """Check if this backend is available. Returns (ok, message)."""
        ...


class FFmpegBackend:
    """FFmpeg stream-copy backend for clip extraction."""

    def check_available(self) -> tuple[bool, str]:
        """Check if ffmpeg is reachable (PATH, env var, or bundled)."""
        if bundled_binary_path("ffmpeg") is None:
            return (False, "FFmpeg not found")
        return (True, "")

    def extract_clip(
        self, source: Path, output: Path, start: float, end: float,
        subtitles: Path | None = None, subtitle_language: str = "und",
    ) -> Path | None:
        """Extract a clip using FFmpeg stream-copy into .mp4 container.

        Uses ``-ss`` before ``-i`` (input seeking) for speed.
        Stream-copy (``-c copy``) preserves codec without re-encoding.

        With ``subtitles``, the file is a second input muxed as a ``mov_text``
        track (MPEG-4 Timed Text), still without re-encoding the video. Only
        the source's first video and first audio stream are mapped, with or
        without subtitles, so a data, timecode or extra audio track in a Zoom
        or Teams file can't break the cut. The cut starts on the
        requested frame, not the keyframe before it — ffmpeg writes an edit
        list — so subtitles timed from ``start`` stay in sync (measured
        frame-exact, 29 Sep 2026). The track carries ``subtitle_language``:
        untagged (``und``), QuickTime's *Subtitles ▸ On* finds no track in
        the viewer's language and shows nothing.
        """
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Fetch first if the source is a cloud placeholder. This is the most
            # likely site of the three to hit it in real use: cutting clips is
            # the "go back to an old study" operation, which is exactly when a
            # provider has evicted the sources. Without this the download runs
            # inside the 120s budget below and the researcher is told the clip
            # failed, with no hint that waiting would have fixed it.
            ensure_materialised(source)
        except CloudFetchTimeoutError as exc:
            logger.warning("Clip extraction skipped for %s: %s", source.name, exc)
            return None

        ffmpeg = bundled_binary_path("ffmpeg") or "ffmpeg"
        cmd = [ffmpeg, "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(source)]
        if subtitles is not None:
            cmd += ["-i", str(subtitles)]
        # The same streams with or without subtitles: the first video and the
        # first audio track only. Mapping every stream let a second audio
        # track (or a data track) fail the mux — measured: a second PCM track
        # into .m4a exits 234 — and made a subtitled clip carry different
        # tracks from a plain one. An audio clip takes no video, so an
        # embedded cover image can't be copied into the .m4a.
        if output.suffix.lower() != ".m4a":
            cmd += ["-map", "0:v:0?"]
        cmd += ["-map", "0:a:0?"]
        if subtitles is not None:
            cmd += [
                "-map", "1:0", "-c", "copy", "-c:s", "mov_text",
                "-metadata:s:s:0", f"language={subtitle_language}",
            ]
        else:
            cmd += ["-c", "copy"]
        cmd += ["-y", str(output)]
        try:
            result = subprocess.run(
                cmd,
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
