"""Tests for CLI output formatting helpers and hardware label."""

from __future__ import annotations

from bristlenose.pipeline import _format_duration
from bristlenose.utils.hardware import AcceleratorType, HardwareInfo

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
