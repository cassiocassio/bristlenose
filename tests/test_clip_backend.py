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
        with patch("bristlenose.server.clip_backend.shutil.which", return_value="/usr/bin/ffmpeg"):
            ok, msg = FFmpegBackend().check_available()
            assert ok is True
            assert msg == ""

    def test_not_available(self) -> None:
        with patch("bristlenose.server.clip_backend.shutil.which", return_value=None):
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
            assert args[0] == "ffmpeg"
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
