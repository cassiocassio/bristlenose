"""Tests for CLI output formatting helpers and hardware label."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from bristlenose.cli import _COMMANDS, _maybe_inject_run
from bristlenose.pipeline import _format_duration
from bristlenose.utils.hardware import AcceleratorType, HardwareInfo

# ---------------------------------------------------------------------------
# _maybe_inject_run (default command)
# ---------------------------------------------------------------------------


class TestMaybeInjectRun:
    def test_injects_run_for_directory(self, tmp_path: Path) -> None:
        """A bare directory argument gets 'run' injected."""
        test_dir = tmp_path / "interviews"
        test_dir.mkdir()
        with patch.object(sys, "argv", ["bristlenose", str(test_dir)]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "run", str(test_dir)]

    def test_no_injection_for_known_command(self, tmp_path: Path) -> None:
        """Known commands are not treated as directories."""
        # Even if a directory named 'doctor' exists, the command takes precedence
        (tmp_path / "doctor").mkdir()
        with patch.object(sys, "argv", ["bristlenose", "doctor"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "doctor"]

    def test_no_injection_for_flags(self) -> None:
        """Flags like --version are passed through."""
        with patch.object(sys, "argv", ["bristlenose", "--version"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "--version"]

    def test_no_injection_for_nonexistent_path(self) -> None:
        """Non-existent paths are passed through (let Typer handle the error)."""
        with patch.object(sys, "argv", ["bristlenose", "nonexistent-folder"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose", "nonexistent-folder"]

    def test_no_injection_with_no_args(self) -> None:
        """No arguments means show help — don't inject anything."""
        with patch.object(sys, "argv", ["bristlenose"]):
            _maybe_inject_run()
            assert sys.argv == ["bristlenose"]

    def test_all_commands_in_set(self) -> None:
        """Sanity check: all expected commands are in _COMMANDS."""
        expected = {"run", "transcribe", "analyze", "analyse", "render", "doctor", "help", "configure", "serve"}
        assert _COMMANDS == expected

# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_sub_second(self) -> None:
        assert _format_duration(0.1) == "0.1s"

    def test_seconds(self) -> None:
        assert _format_duration(42.7) == "42.7s"

    def test_exactly_one_minute(self) -> None:
        assert _format_duration(60) == "1m 00s"

    def test_minutes_and_seconds(self) -> None:
        assert _format_duration(125) == "2m 05s"

    def test_large_duration(self) -> None:
        assert _format_duration(3599) == "59m 59s"

    def test_zero(self) -> None:
        assert _format_duration(0.0) == "0.0s"

    def test_just_under_one_minute(self) -> None:
        assert _format_duration(59.9) == "59.9s"


# ---------------------------------------------------------------------------
# HardwareInfo.label
# ---------------------------------------------------------------------------


class TestHardwareLabel:
    def test_apple_silicon_mlx(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            chip_name="Apple M2 Max",
            mlx_available=True,
        )
        assert hw.label == "Apple M2 Max · MLX"

    def test_apple_silicon_no_mlx(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            chip_name="Apple M1",
            mlx_available=False,
        )
        assert hw.label == "Apple M1 · CPU"

    def test_cuda(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.CUDA,
            chip_name="NVIDIA RTX 4090",
            cuda_available=True,
        )
        assert hw.label == "NVIDIA RTX 4090 · CUDA"

    def test_cpu_fallback(self) -> None:
        hw = HardwareInfo(accelerator=AcceleratorType.CPU)
        assert hw.label == "cpu · CPU"

    def test_cuda_no_chip_name(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.CUDA,
            cuda_available=True,
        )
        assert hw.label == "cuda · CUDA"

    def test_apple_silicon_no_chip_name(self) -> None:
        hw = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            mlx_available=True,
        )
        assert hw.label == "apple_silicon · MLX"
