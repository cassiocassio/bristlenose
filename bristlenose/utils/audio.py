"""Audio file utilities: probing duration, format detection, ffmpeg wrappers."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bristlenose.models import MediaTimeMeta
from bristlenose.utils.bundled_binary import bundled_binary_path
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised
from bristlenose.utils.timecodes import parse_iso_lenient

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


class MediaFileDamagedError(AudioToolError):
    """ffprobe *ran correctly* and reported that this particular file is unusable.

    A subclass of :class:`AudioToolError` so existing fail-loud handlers keep
    working unchanged, but distinguishable by callers that can sensibly carry
    on: one participant's truncated upload is not a broken toolchain, and it
    must not take the other ninety-nine recordings down with it.

    The distinction is deliberately conservative — see
    :func:`_looks_like_toolchain_failure`. When the failure cannot be
    confidently attributed to the file, it is reported as a toolchain failure,
    because under-reporting a broken tool is the more dangerous error.
    """


# Signatures of a *tool* that could not run, as opposed to a *file* it refused.
# A dynamic-linker failure also exits non-zero (the snap's missing libblas.so.3
# is the recorded case), so exit status alone cannot separate the two.
_TOOLCHAIN_FAILURE_MARKERS = (
    "error while loading shared libraries",
    "cannot open shared object",
    "library not loaded",
    "image not found",
    "symbol not found",
    "bad cpu type",
    "command not found",
    "permission denied",
    "segmentation fault",
    "illegal instruction",
    "killed",
)


def _looks_like_toolchain_failure(stderr: str) -> bool:
    """True if *stderr* reads as "ffprobe could not run", not "this file is bad".

    Defaults to True on empty output: ffprobe run with ``-v error`` always says
    something about a file it dislikes, so silence means the process never got
    far enough to form an opinion.
    """
    text = stderr.strip().lower()
    if not text:
        return True
    return any(marker in text for marker in _TOOLCHAIN_FAILURE_MARKERS)


_MAX_TAG_CHARS = 256   # device/writer identifiers; bounds retained memory per file


def _tags(block: dict[str, Any] | None) -> dict[str, str]:
    """Lower-cased, string-coerced, length-bounded tag map for one ffprobe block.

    Bounded HERE, at the dict layer, never with a Pydantic ``max_length``: a
    validator *rejects*, and a rejection inside the probe would re-create the
    whole-scan abort this file was reviewed for. A 200 KB tag becomes 256 chars
    and the file keeps its other fields.
    """
    return {k.lower(): str(v)[:_MAX_TAG_CHARS] for k, v in ((block or {}).get("tags") or {}).items()}


def time_meta_from_ffprobe(data: dict[str, Any]) -> MediaTimeMeta | None:
    """Build a ``MediaTimeMeta`` from ffprobe's JSON. Pure; tested without
    ffprobe. ``None`` when the container carries nothing at all.

    Format tags and stream tags are kept APART. ``encoder`` is read from the
    format block only — on MOV/MP4 the video stream carries the codec (``HEVC``)
    under the same key Matroska uses for the muxer, and § 5.2's writer table
    keys on the muxer. Time falls back to the first stream, because some
    writers stamp only there.

    The named ``.get()`` calls below are an ALLOWLIST and a privacy boundary:
    the same dictionaries carry ``com.apple.quicktime.location.ISO6709`` (GPS)
    on every iPhone recording, and it is deliberately not read. Widening this
    to "all tags" is a consent-gradient decision, not a convenience.
    """
    fmt = _tags(data.get("format"))
    streams = [_tags(st) for st in (data.get("streams") or [])]
    stream_first = streams[0] if streams else {}
    if not fmt and not any(streams):
        return None

    creation_utc: datetime | None = None
    raw_utc = fmt.get("creation_time") or stream_first.get("creation_time")
    if raw_utc:
        dt = parse_iso_lenient(raw_utc)
        if dt is not None:
            creation_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    creation_local: datetime | None = None
    offset_minutes: int | None = None
    raw_local = fmt.get("com.apple.quicktime.creationdate")
    if raw_local:
        dt = parse_iso_lenient(raw_local)
        if dt is not None and dt.tzinfo is not None:
            creation_local = dt
            off = dt.utcoffset()
            offset_minutes = int(off.total_seconds() // 60) if off is not None else None
            if creation_utc is None:
                creation_utc = dt.astimezone(timezone.utc)
        elif dt is not None:
            # A naive creationdate is the room's wall clock with the zone
            # missing. Relabelling it UTC would manufacture a confident wrong
            # instant that § 5.4 would trust. Say so and leave both unset.
            logger.warning("time_value_naive | key=creationdate | zone unknown, not stamped | raw=%r", raw_local[:64])

    meta = MediaTimeMeta(
        creation_utc=creation_utc,
        creation_local=creation_local,
        offset_minutes=offset_minutes,
        make=fmt.get("com.apple.quicktime.make"),
        model=fmt.get("com.apple.quicktime.model"),
        software=fmt.get("com.apple.quicktime.software"),
        encoder=fmt.get("encoder"),
        author=fmt.get("com.apple.quicktime.author"),
    )
    if all(getattr(meta, f) is None for f in MediaTimeMeta.model_fields):
        return None
    return meta


def probe_media(file_path: Path) -> tuple[float | None, MediaTimeMeta | None]:
    """One ffprobe call: the duration and the container's time metadata.

    Was two calls (~30 ms each, spawn-bound — a 1.25 GB file costs the same as
    16 MB) on the blocking pre-spinner ingest path, kept separate "to preserve
    the mock seam"; the seam was three monkeypatch sites. One call now.

    Materialises a cloud placeholder first (``ensure_materialised``), because
    the blocking read is the trigger and a slow fetch must not be reported as
    a broken file. The caller gates on ``is_dataless`` so a scan does not
    download; that rule lives at the call site, not here.

    Three degradations, three different messages, because they mean three
    different things: the tool did not run → ``Could not probe``; ffprobe
    refused the file → its own stderr; the file read fine but a tag did not
    parse → the duration is KEPT and only the meta is ``None``. Folding the
    last case under the first would have cost a file its duration for one bad
    date tag.
    """
    ffprobe = bundled_binary_path("ffprobe") or "ffprobe"
    try:
        ensure_materialised(file_path)
    except CloudFetchTimeoutError as exc:
        logger.warning("Could not probe %s: %s", file_path, exc)
        return None, None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json",
             "-show_entries", "format:stream_tags", "--", str(file_path)],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("Could not probe %s: %s", file_path, exc)
        return None, None
    if result.returncode != 0:
        logger.warning("ffprobe refused %s: %s", file_path, (result.stderr or "").strip()[:200])
        return None, None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("Could not probe %s: %s", file_path, exc)
        return None, None

    duration: float | None = None
    raw = (data.get("format") or {}).get("duration")
    if raw:
        try:
            duration = float(raw)
        except (TypeError, ValueError):
            duration = None
    try:
        meta = time_meta_from_ffprobe(data)
    except Exception as exc:  # a parser bug must never cost the scan, or the duration
        logger.warning("container_tags_unparseable | file=%s | %s: %s", file_path.name, type(exc).__name__, exc)
        meta = None
    return duration, meta


def probe_duration(file_path: Path) -> float | None:
    """Duration in seconds, or None. Thin wrapper over ``probe_media`` — the
    ingest path calls that directly; this stays for other callers and tests."""
    return probe_media(file_path)[0]


def probe_time_meta(file_path: Path) -> MediaTimeMeta | None:
    """Container time metadata, or None. Thin wrapper over ``probe_media``."""
    return probe_media(file_path)[1]


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
        detail = result.stderr.strip()
        message = (
            f"ffprobe failed to probe {file_path.name} "
            f"(exit {result.returncode}): {detail}"
        )
        if _looks_like_toolchain_failure(detail):
            raise AudioToolError(message)
        raise MediaFileDamagedError(message)

    return "audio" in result.stdout
