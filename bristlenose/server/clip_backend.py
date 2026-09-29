"""Clip extraction backends: Protocol + FFmpeg implementation.

The Protocol defines the contract that both FFmpeg (CLI/serve) and
future AVFoundation (macOS desktop) backends implement.
"""

from __future__ import annotations

import functools
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from bristlenose.utils.bundled_binary import bundled_binary_path
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

if TYPE_CHECKING:
    from bristlenose.server.clip_subtitles import Cue

logger = logging.getLogger(__name__)

#: The face burned-in subtitles are drawn in (Inter Medium, SIL OFL 1.1 —
#: licence beside it). Bundled so the pixels come out the same on every
#: channel and never depend on what fonts the machine has.
BURN_FONT = Path(__file__).resolve().parent.parent / "data" / "fonts" / "Inter-Medium.otf"
#: A burn re-encodes the whole clip; a merged clip can run for minutes.
_BURN_TIMEOUT_SECONDS = 600
#: Paths passed inside an ffmpeg filter graph must not need escaping.
_FILTER_SAFE_PATH = re.compile(r"^[\w/.\-]+$")


@functools.lru_cache(maxsize=4)
def _can_burn(ffmpeg: str) -> bool:
    """Whether this ffmpeg can burn subtitles: libass's filter and x264.

    Homebrew's ffmpeg has neither the ``subtitles`` filter nor libass
    (measured 29 Sep 2026); the macOS app's bundled build and Linux distro
    builds have both.
    """
    try:
        filters = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30,
        ).stdout
        encoders = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    has_filter = re.search(r"^\s*\S*\s+subtitles\s", filters, flags=re.M) is not None
    has_x264 = re.search(r"\slibx264\s", encoders) is not None
    return has_filter and has_x264


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

    def can_burn_subtitles(self) -> bool:
        """Whether this backend can draw subtitles into a clip's pixels."""
        ...

    def burn_subtitles(self, clip: Path, cues: list[Cue], output: Path) -> Path | None:
        """Write a copy of ``clip`` with ``cues`` drawn into the picture."""
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

    def can_burn_subtitles(self) -> bool:
        """Whether the ffmpeg in use has libass's filter and the x264 encoder."""
        ffmpeg = bundled_binary_path("ffmpeg")
        return ffmpeg is not None and _can_burn(str(ffmpeg))

    def burn_subtitles(self, clip: Path, cues: list[Cue], output: Path) -> Path | None:
        """Write a copy of ``clip`` with ``cues`` drawn into the picture.

        The "for slides" export: text in the pixels plays anywhere, including
        PowerPoint, Keynote and a Teams screen share, where a subtitle track is
        ignored or needs a manual step. Re-encodes the video with x264 (CRF 18)
        and copies the audio. The ``.ass`` file and the bundled font go in a
        private temp folder, so no path that needs escaping reaches the filter
        graph and nothing is left in the researcher's clips folder.
        """
        from bristlenose.server.clip_subtitles import to_ass

        ffmpeg = bundled_binary_path("ffmpeg") or "ffmpeg"
        ffprobe = bundled_binary_path("ffprobe") or "ffprobe"
        try:
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0", str(clip)],
                capture_output=True, text=True, timeout=60,
            )
            width, height = (int(x) for x in probe.stdout.strip().split(",")[:2])
        except (OSError, subprocess.TimeoutExpired, ValueError):
            logger.warning("Could not read the frame size of %s; not burning", clip.name)
            return None

        tmp = Path(tempfile.mkdtemp(prefix="bn-burn-"))
        try:
            if not _FILTER_SAFE_PATH.match(str(tmp)):
                logger.warning("Temp path %s is not filter-safe; not burning", tmp)
                return None
            shutil.copy2(BURN_FONT, tmp / BURN_FONT.name)
            ass = tmp / "subtitles.ass"
            ass.write_text(to_ass(cues, width, height), encoding="utf-8")
            result = subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error",
                    "-i", str(clip),
                    "-vf", f"subtitles={ass}:fontsdir={tmp}",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-movflags", "+faststart",
                    "-y", str(output),
                ],
                capture_output=True, text=True, timeout=_BURN_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                logger.warning(
                    "Burning subtitles into %s failed (exit %d): %s",
                    clip.name, result.returncode, result.stderr[-500:],
                )
                return None
        except subprocess.TimeoutExpired:
            logger.warning("Burning subtitles into %s timed out", clip.name)
            return None
        except OSError:
            logger.warning("Burning subtitles into %s failed", clip.name, exc_info=True)
            return None
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        if output.exists() and output.stat().st_size > 0:
            return output
        return None
