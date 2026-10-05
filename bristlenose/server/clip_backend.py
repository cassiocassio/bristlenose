"""Clip extraction backends: Protocol + FFmpeg implementation.

The Protocol defines the contract that both FFmpeg (CLI/serve) and
future AVFoundation (macOS desktop) backends implement.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

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
    builds have both. A probe that fails to run raises rather than returning
    False, so ``lru_cache`` keeps only real answers — one slow start must not
    read as "can't burn" until the server restarts.
    """
    runs = [
        subprocess.run([ffmpeg, "-hide_banner", flag], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        for flag in ("-filters", "-encoders")
    ]
    for run in runs:
        # A binary that didn't run properly (a sandbox-signed ffmpeg started
        # outside the sandbox exits 133 with no output) has told us nothing.
        if run.returncode != 0:
            raise OSError(f"{ffmpeg} exited {run.returncode}")
    filters, encoders = runs[0].stdout, runs[1].stdout
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


def display_size(probe: dict[str, Any]) -> tuple[int, int]:
    """The upright, square-pixel frame size of ffprobe's first video stream,
    rounded to even numbers.

    The stored size is not what is shown: a portrait phone recording is
    stored landscape with a 90° rotation, and an HDV or AVCHD file has
    non-square pixels. ``probe`` is ffprobe's JSON for ``width``, ``height``,
    ``sample_aspect_ratio``, the ``rotate`` tag (older files) and the
    ``rotation`` side data.
    """
    stream = probe["streams"][0]
    width: float = int(stream["width"])
    height: float = int(stream["height"])
    sar = str(stream.get("sample_aspect_ratio") or "1:1")
    num, _, den = sar.partition(":")
    if num.isdigit() and den.isdigit() and int(num) > 0 and int(den) > 0:
        width = width * int(num) / int(den)
    rotation = stream.get("tags", {}).get("rotate")
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = side["rotation"]
    if rotation is not None and abs(round(float(rotation))) % 180 == 90:
        width, height = height, width
    return _even(width), _even(height)


def _even(n: float) -> int:
    return max(2, int(round(n / 2)) * 2)


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
                text=True, encoding="utf-8", errors="replace",
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
        if ffmpeg is None:
            return False
        try:
            return _can_burn(str(ffmpeg))
        except (OSError, subprocess.TimeoutExpired):
            logger.warning("Could not ask %s whether it can burn subtitles", ffmpeg, exc_info=True)
            return False

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
                 "-show_entries",
                 "stream=width,height,sample_aspect_ratio:stream_tags=rotate"
                 ":stream_side_data=rotation",
                 "-of", "json", str(clip)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            width, height = display_size(json.loads(probe.stdout))
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, IndexError):
            logger.warning("Could not read the frame size of %s; not burning", clip.name)
            return None

        try:
            tmp = Path(tempfile.mkdtemp(prefix="bn-burn-"))
        except OSError:
            logger.warning("Could not make a temp folder to burn %s", clip.name, exc_info=True)
            return None
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
                    # ffmpeg turns a rotated phone video upright before the
                    # filters; scaling to the display size then gives square
                    # pixels (an anamorphic source's text isn't stretched) and
                    # even sides, which yuv420p needs — an odd-sized screen
                    # capture otherwise fails to open the encoder.
                    "-vf",
                    f"scale={width}:{height},setsar=1,subtitles={ass}:fontsdir={tmp}",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-movflags", "+faststart",
                    "-y", str(output),
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_BURN_TIMEOUT_SECONDS,
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
