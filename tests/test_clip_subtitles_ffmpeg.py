"""Real FFmpeg round trip for clip subtitles.

Skips when ffmpeg or ffprobe is not installed. Proves two things no mock
can: the subtitle track lands in the file with its cues timed from the
clip's start, and the cut starts on the requested frame rather than the
keyframe before it, which is what keeps those cues in sync.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from bristlenose.server.clip_backend import FFmpegBackend
from bristlenose.server.clip_subtitles import Token, build_cues, to_srt

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)

_FPS = 25


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def _video_source(path: Path) -> Path:
    # 20 s, a keyframe every 5 s, so a cut at 7 s falls between keyframes.
    _run(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate={_FPS}:duration=20",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
        "-c:v", "mpeg4", "-g", str(5 * _FPS), "-c:a", "aac", "-shortest", "-y", str(path),
    )
    return path


def _audio_source(path: Path) -> Path:
    _run(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
        "-c:a", "aac", "-y", str(path),
    )
    return path


def _srt(tmp_path: Path) -> Path:
    tokens = [
        Token("So", 7.5, 7.8, "m1"), Token("why?", 7.9, 8.2, "m1"),
        Token("It", 9.0, 9.2, "p1"), Token("broke.", 9.3, 9.8, "p1"),
    ]
    path = tmp_path / "clip.srt"
    path.write_text(to_srt(build_cues(tokens, 7.0, 12.0, "p1")), encoding="utf-8")
    return path


def _frame_md5s(path: Path) -> list[str]:
    out = _run("ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
               "-map", "0:v", "-f", "framemd5", "-")
    return [line.rsplit(",", 1)[1].strip() for line in out.splitlines()
            if line and not line.startswith("#")]


def test_video_clip_carries_a_mov_text_track_in_sync(tmp_path: Path) -> None:
    source = _video_source(tmp_path / "src.mp4")
    clip = FFmpegBackend().extract_clip(
        source, tmp_path / "clip.mp4", 7.0, 12.0, _srt(tmp_path), "eng",
    )
    assert clip is not None

    codecs = _run("ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
                  "-of", "csv=p=0", str(clip)).split()
    assert "mov_text" in codecs
    # The language tag is what lets a player's "subtitles in my language"
    # setting find the track (measured in QuickTime, 29 Sep 2026).
    lang = _run("ffprobe", "-v", "error", "-select_streams", "s",
                "-show_entries", "stream_tags=language", "-of", "csv=p=0", str(clip))
    assert lang.strip() == "eng"

    # The first frame shown is the source frame at exactly 7.00 s.
    first = _frame_md5s(clip)[0]
    assert _frame_md5s(source).index(first) == 7 * _FPS

    # Cues are timed from the clip's start, both speakers subtitled.
    as_srt = _run("ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(clip),
                  "-map", "0:s", "-f", "srt", "-")
    assert "00:00:00,500 -->" in as_srt
    assert "why?" in as_srt and "broke." in as_srt


def test_audio_only_clip_carries_the_track_too(tmp_path: Path) -> None:
    source = _audio_source(tmp_path / "src.m4a")
    clip = FFmpegBackend().extract_clip(
        source, tmp_path / "clip.m4a", 7.0, 12.0, _srt(tmp_path),
    )
    assert clip is not None
    codecs = _run("ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
                  "-of", "csv=p=0", str(clip)).split()
    assert "mov_text" in codecs


def _black_source(path: Path, size: str) -> Path:
    # A black picture, so any bright pixel is the burned-in text.
    _run(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:size={size}:rate={_FPS}:duration=6",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", "-y", str(path),
    )
    return path


def _grey_frame(video: Path, at: float) -> tuple[int, int, bytes]:
    w, h = (int(x) for x in _run(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video),
    ).strip().split(",")[:2])
    raw = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at}", "-i", str(video),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout
    return w, h, raw


def _bright_columns(frame: tuple[int, int, bytes]) -> list[int]:
    w, h, raw = frame
    return sorted({i % w for i in range(len(raw)) if raw[i] > 180})


def _burn(tmp_path: Path, size: str, lines: tuple[str, ...]) -> Path:
    from bristlenose.server.clip_subtitles import Cue

    backend = FFmpegBackend()
    if not backend.can_burn_subtitles():
        pytest.skip("this ffmpeg has no libass subtitles filter (e.g. Homebrew's)")
    clip = backend.extract_clip(_black_source(tmp_path / "src.mp4", size),
                                tmp_path / "clip.mp4", 0.0, 5.0)
    assert clip is not None
    burned = backend.burn_subtitles(
        clip, [Cue(0.0, 2.0, "p1", "white", lines)], tmp_path / "clip (subtitled).mp4",
    )
    assert burned is not None
    return burned


def test_burned_copy_has_the_text_in_its_pixels(tmp_path: Path) -> None:
    burned = _burn(tmp_path, "320x180", ("Burned in.",))
    during, after = _grey_frame(burned, 1.0), _grey_frame(burned, 3.5)
    lit = _bright_columns(during)
    assert lit, "no text was drawn while the cue was up"
    assert not _bright_columns(after), "text is still there after the cue ended"
    w = during[0]
    assert w * 0.1 < lit[0] and lit[-1] < w * 0.9  # centred, inside the margins


def test_portrait_text_stays_inside_the_frame(tmp_path: Path) -> None:
    """Two full 37-character lines on an upright phone frame: sized from the
    height, they ran off both edges."""
    burned = _burn(tmp_path, "180x320", (
        "I thought the settings page would be", "where I could change the notifications",
    ))
    frame = _grey_frame(burned, 1.0)
    lit = _bright_columns(frame)
    assert lit and lit[0] > 2 and lit[-1] < frame[0] - 3
