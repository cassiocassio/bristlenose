"""Tests for FFmpeg clip extraction backend — mocked subprocess."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.server.clip_backend import ClipBackend, FFmpegBackend


class TestFFmpegBackendProtocol:
    def test_implements_protocol(self) -> None:
        assert isinstance(FFmpegBackend(), ClipBackend)


class TestCheckAvailable:
    def test_available(self) -> None:
        with patch(
            "bristlenose.server.clip_backend.bundled_binary_path",
            return_value="/usr/bin/ffmpeg",
        ):
            ok, msg = FFmpegBackend().check_available()
            assert ok is True
            assert msg == ""

    def test_not_available(self) -> None:
        with patch(
            "bristlenose.server.clip_backend.bundled_binary_path",
            return_value=None,
        ):
            ok, msg = FFmpegBackend().check_available()
            assert ok is False
            assert "not found" in msg.lower()


class TestExtractClip:
    def test_success(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake video")
        output = tmp_path / "clips" / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            # Create the output file to simulate FFmpeg writing it
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake clip data")

            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result == output

    def test_ffmpeg_command_args(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result) as mock_run:
            output.write_bytes(b"clip")
            FFmpegBackend().extract_clip(source, output, 10.5, 25.3)

            args = mock_run.call_args[0][0]
            assert args[0].endswith("ffmpeg")
            assert "-ss" in args
            assert "-to" in args
            assert "-c" in args
            assert "copy" in args
            assert "-y" in args
            assert str(source) in args
            assert str(output) in args

    def test_nonzero_exit_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=1, stderr="Error: corrupt file")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_timeout_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        import subprocess
        with patch(
            "bristlenose.server.clip_backend.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120),
        ):
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_ffmpeg_not_found_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        with patch(
            "bristlenose.server.clip_backend.subprocess.run",
            side_effect=FileNotFoundError("ffmpeg not found"),
        ):
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_empty_output_returns_none(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            # Don't create the output file — simulates FFmpeg silently failing
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result is None

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "deep" / "nested" / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"clip")
            result = FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert result == output

    @pytest.mark.parametrize("timeout", [120])
    def test_timeout_value(self, tmp_path: Path, timeout: int) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"

        mock_result = MagicMock(returncode=0, stderr="")
        with patch("bristlenose.server.clip_backend.subprocess.run", return_value=mock_result) as mock_run:
            output.write_bytes(b"clip")
            FFmpegBackend().extract_clip(source, output, 10.0, 20.0)
            assert mock_run.call_args[1]["timeout"] == timeout


class TestSubtitleMux:
    def _run(self, tmp_path: Path, subtitles: Path | None) -> list[str]:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"
        output.write_bytes(b"clip")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch(
            "bristlenose.server.clip_backend.subprocess.run", return_value=mock_result,
        ) as mock_run:
            FFmpegBackend().extract_clip(source, output, 10.0, 20.0, subtitles)
        return list(mock_run.call_args[0][0])

    def test_without_subtitles_first_video_and_audio_only(self, tmp_path: Path) -> None:
        args = self._run(tmp_path, None)
        assert args[1:] == [
            "-ss", "10.000", "-to", "20.000", "-i", str(tmp_path / "source.mp4"),
            "-map", "0:v:0?", "-map", "0:a:0?",
            "-c", "copy", "-y", str(tmp_path / "clip.mp4"),
        ]

    def test_subtitles_are_a_second_input_muxed_as_mov_text(self, tmp_path: Path) -> None:
        srt = tmp_path / "clip.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        args = self._run(tmp_path, srt)
        joined = " ".join(args)
        assert f"-i {srt}" in joined
        # The same first video and audio as a plain cut, plus the subtitles:
        # every-stream mapping let a second audio track fail the mux.
        assert "-map 0:v:0? -map 0:a:0? -map 1:0" in joined
        assert "-c copy -c:s mov_text" in joined
        # Untagged (und), QuickTime's "subtitles in my language" can't find it.
        assert "-metadata:s:s:0 language=und" in joined
        # The seek stays an input option on the source, before its -i.
        assert args.index("-ss") < args.index(str(tmp_path / "source.mp4"))

    def test_subtitle_track_carries_the_language(self, tmp_path: Path) -> None:
        source = tmp_path / "source.mp4"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.mp4"
        output.write_bytes(b"clip")
        srt = tmp_path / "clip.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch(
            "bristlenose.server.clip_backend.subprocess.run", return_value=mock_result,
        ) as mock_run:
            FFmpegBackend().extract_clip(source, output, 1.0, 2.0, srt, "jpn")
        assert "-metadata:s:s:0 language=jpn" in " ".join(mock_run.call_args[0][0])

    def test_audio_clip_takes_no_video(self, tmp_path: Path) -> None:
        source = tmp_path / "source.m4a"
        source.write_bytes(b"fake")
        output = tmp_path / "clip.m4a"
        output.write_bytes(b"clip")
        mock_result = MagicMock(returncode=0, stderr="")
        with patch(
            "bristlenose.server.clip_backend.subprocess.run", return_value=mock_result,
        ) as mock_run:
            FFmpegBackend().extract_clip(source, output, 1.0, 2.0)
        args = list(mock_run.call_args[0][0])
        assert "0:v:0?" not in args and "0:a:0?" in args
