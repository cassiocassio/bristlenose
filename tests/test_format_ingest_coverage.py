"""Format-ingest coverage — every extension we advertise, at the cheapest layer.

We claim 16 input formats (README / manual). All 16 collapse to **4 decode
paths** by suffix (`classify_file`) — so proving "`.flac` ingests" does NOT need
a full Whisper+LLM pipeline run; that would re-test a suffix table and a codec at
the cost of minutes and (for the analysis leg) real money, ten times over. This
is the right layer instead:

  1. `classify_file` routes every advertised extension to the correct `FileType`
     (pure function, instant).
  2. For every media container, ffmpeg can **produce and decode** it — the real
     container/codec path, exercised at test-time with no committed binaries.

The genuine *format-parity* question (does Google Meet's real `.docx` shape parse
against the Teams-shaped parser?) is a different test and lives in
`test_no_fake_success_acceptance.py` with a real export — a synthetic docx parses
by construction and proves nothing, so it is deliberately NOT covered here.

Per the acceptance philosophy: a format that ffmpeg cannot produce on this build
**skips with a visible reason** (a declared gap), never a silent pass.

See docs/testing/coverage-inventory.md §1.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from bristlenose.models import (
    AUDIO_EXTENSIONS,
    DOCX_EXTENSIONS,
    SUBTITLE_SRT_EXTENSIONS,
    SUBTITLE_VTT_EXTENSIONS,
    VIDEO_EXTENSIONS,
    FileType,
    classify_file,
)

# ---------------------------------------------------------------------------
# 1. classify_file — every advertised extension routes correctly (pure, instant)
# ---------------------------------------------------------------------------

_EXPECTED: list[tuple[str, FileType]] = (
    [(ext, FileType.AUDIO) for ext in AUDIO_EXTENSIONS]
    + [(ext, FileType.VIDEO) for ext in VIDEO_EXTENSIONS]
    + [(ext, FileType.SUBTITLE_SRT) for ext in SUBTITLE_SRT_EXTENSIONS]
    + [(ext, FileType.SUBTITLE_VTT) for ext in SUBTITLE_VTT_EXTENSIONS]
    + [(ext, FileType.DOCX) for ext in DOCX_EXTENSIONS]
)


@pytest.mark.parametrize("ext,expected", _EXPECTED, ids=[e for e, _ in _EXPECTED])
def test_classify_routes_every_advertised_extension(ext: str, expected: FileType) -> None:
    assert classify_file(Path(f"interview{ext}")) == expected
    # Case-insensitive: uppercase suffixes (camera cards, Windows) route the same.
    assert classify_file(Path(f"INTERVIEW{ext.upper()}")) == expected


def test_classify_rejects_unsupported() -> None:
    for ext in (".txt", ".pdf", ".json", ".zip", ".exe", ""):
        assert classify_file(Path(f"x{ext}")) is None


def test_advertised_count_is_sixteen() -> None:
    """Pin the claim: 16 formats. If this changes, README/manual + the coverage
    inventory must change with it (this test is the tripwire)."""
    total = (
        len(AUDIO_EXTENSIONS)
        + len(VIDEO_EXTENSIONS)
        + len(SUBTITLE_SRT_EXTENSIONS)
        + len(SUBTITLE_VTT_EXTENSIONS)
        + len(DOCX_EXTENSIONS)
    )
    assert total == 16


# ---------------------------------------------------------------------------
# 2. ffmpeg can produce + decode every media container (the real codec path)
# ---------------------------------------------------------------------------

_FFMPEG = shutil.which("ffmpeg")
_needs_ffmpeg = pytest.mark.skipif(_FFMPEG is None, reason="ffmpeg not on PATH")

# Sorted for stable test ordering / ids.
_AUDIO = sorted(AUDIO_EXTENSIONS)
_VIDEO = sorted(VIDEO_EXTENSIONS)


def _ffmpeg(*args: str) -> subprocess.CompletedProcess[str]:
    assert _FFMPEG is not None
    return subprocess.run(
        [_FFMPEG, "-hide_banner", "-y", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _generate(ext: str, dest: Path, *, video: bool) -> subprocess.CompletedProcess[str]:
    """Produce a ~0.5s clip in `ext`, letting ffmpeg pick the container's default
    codec (mp4→h264/aac, webm→vp9/opus, ogg→vorbis, flac→flac, …) — the codec a
    real file of this type would carry, not a `-c copy` remux that tests nothing."""
    sine = "sine=frequency=440:duration=0.5"
    if video:
        return _ffmpeg(
            "-f", "lavfi", "-i", "testsrc=duration=0.5:size=128x96:rate=10",
            "-f", "lavfi", "-i", sine,
            "-shortest", str(dest),
        )
    return _ffmpeg("-f", "lavfi", "-i", sine, str(dest))


def _assert_produce_and_decode(ext: str, tmp_path: Path, *, video: bool) -> None:
    dest = tmp_path / f"clip{ext}"
    gen = _generate(ext, dest, video=video)
    if gen.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        # Declared gap: this ffmpeg build has no encoder/muxer for the container.
        # Visible skip with the real reason — never a silent pass.
        tail = gen.stderr.strip().splitlines()[-1] if gen.stderr.strip() else "no output"
        pytest.skip(f"ffmpeg on this build cannot produce {ext}: {tail}")

    # classify still routes the real file we just made.
    assert classify_file(dest) == (FileType.VIDEO if video else FileType.AUDIO)

    # The decode path the pipeline relies on: read the whole stream to null.
    decode = _ffmpeg("-v", "error", "-i", str(dest), "-f", "null", "-")
    assert decode.returncode == 0, f"ffmpeg failed to decode {ext}: {decode.stderr.strip()}"


@_needs_ffmpeg
@pytest.mark.parametrize("ext", _AUDIO, ids=_AUDIO)
def test_audio_container_produces_and_decodes(ext: str, tmp_path: Path) -> None:
    _assert_produce_and_decode(ext, tmp_path, video=False)


@_needs_ffmpeg
@pytest.mark.parametrize("ext", _VIDEO, ids=_VIDEO)
def test_video_container_produces_and_decodes(ext: str, tmp_path: Path) -> None:
    _assert_produce_and_decode(ext, tmp_path, video=True)


# ---------------------------------------------------------------------------
# 3. Subtitle shapes: .srt and .vtt both classify (parse coverage lives in the
#    subtitle-parser tests; this pins the second subtitle shape the plan flagged)
# ---------------------------------------------------------------------------


def test_srt_and_vtt_are_distinct_subtitle_types() -> None:
    assert classify_file(Path("a.srt")) == FileType.SUBTITLE_SRT
    assert classify_file(Path("a.vtt")) == FileType.SUBTITLE_VTT
