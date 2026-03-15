"""Tests for hardware detection and caching."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from bristlenose.utils.hardware import (
    _CACHE_TTL_SECONDS,
    AcceleratorType,
    HardwareInfo,
    _load_hardware_cache,
    _save_hardware_cache,
    detect_hardware,
)

# ---------------------------------------------------------------------------
# HardwareInfo unit tests
# ---------------------------------------------------------------------------


class TestHardwareInfo:
    def test_recommended_backend_apple_mlx(self):
        info = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON, mlx_available=True
        )
        assert info.recommended_whisper_backend == "mlx"

    def test_recommended_backend_apple_no_mlx(self):
        info = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON, mlx_available=False
        )
        assert info.recommended_whisper_backend == "faster-whisper"

    def test_recommended_backend_cuda(self):
        info = HardwareInfo(accelerator=AcceleratorType.CUDA, cuda_available=True)
        assert info.recommended_whisper_backend == "faster-whisper"

    def test_recommended_model_large(self):
        info = HardwareInfo(accelerator=AcceleratorType.CPU, memory_gb=64.0)
        assert info.recommended_whisper_model == "large-v3"

    def test_recommended_model_medium(self):
        info = HardwareInfo(accelerator=AcceleratorType.CPU, memory_gb=8.0)
        assert info.recommended_whisper_model == "medium"

    def test_recommended_model_small(self):
        info = HardwareInfo(accelerator=AcceleratorType.CPU, memory_gb=4.0)
        assert info.recommended_whisper_model == "small"

    def test_recommended_model_no_memory(self):
        info = HardwareInfo(accelerator=AcceleratorType.CPU)
        assert info.recommended_whisper_model == "small"

    def test_label_apple_mlx(self):
        info = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            chip_name="Apple M2 Max",
            mlx_available=True,
        )
        assert info.label == "Apple M2 Max · MLX"

    def test_label_cpu(self):
        info = HardwareInfo(accelerator=AcceleratorType.CPU)
        assert info.label == "cpu · CPU"

    def test_summary(self):
        info = HardwareInfo(
            accelerator=AcceleratorType.APPLE_SILICON,
            chip_name="Apple M2 Max",
            memory_gb=32.0,
            mlx_available=True,
        )
        s = info.summary()
        assert "Apple M2 Max" in s
        assert "32GB" in s


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


class TestHardwareCache:
    def test_save_and_load(self, tmp_path: Path):
        cache_file = tmp_path / ".hardware-cache.json"
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            _save_hardware_cache("Apple M2 Max", 38, 32.0)
            result = _load_hardware_cache()

        assert result is not None
        assert result["chip_name"] == "Apple M2 Max"
        assert result["gpu_cores"] == 38
        assert result["memory_gb"] == 32.0

    def test_load_returns_none_when_no_cache(self, tmp_path: Path):
        cache_file = tmp_path / ".hardware-cache.json"
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            assert _load_hardware_cache() is None

    def test_load_returns_none_when_expired(self, tmp_path: Path):
        cache_file = tmp_path / ".hardware-cache.json"
        expired_data = {
            "chip_name": "Apple M2",
            "gpu_cores": 10,
            "memory_gb": 16.0,
            "timestamp": time.time() - _CACHE_TTL_SECONDS - 1,
        }
        cache_file.write_text(json.dumps(expired_data))
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            assert _load_hardware_cache() is None

    def test_load_returns_data_when_fresh(self, tmp_path: Path):
        cache_file = tmp_path / ".hardware-cache.json"
        fresh_data = {
            "chip_name": "Apple M2",
            "gpu_cores": 10,
            "memory_gb": 16.0,
            "timestamp": time.time(),
        }
        cache_file.write_text(json.dumps(fresh_data))
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            result = _load_hardware_cache()
            assert result is not None
            assert result["chip_name"] == "Apple M2"

    def test_load_returns_none_on_corrupt_json(self, tmp_path: Path):
        cache_file = tmp_path / ".hardware-cache.json"
        cache_file.write_text("not json{{{")
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            assert _load_hardware_cache() is None

    def test_save_creates_directory(self, tmp_path: Path):
        nested = tmp_path / "a" / "b"
        cache_file = nested / ".hardware-cache.json"
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", nested),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            _save_hardware_cache("Apple M1", 8, 16.0)
        assert cache_file.exists()


# ---------------------------------------------------------------------------
# detect_hardware integration (all subprocesses mocked)
# ---------------------------------------------------------------------------


class TestDetectHardware:
    def test_cpu_fallback(self):
        """Non-Apple, non-CUDA → CPU fallback."""
        with (
            patch("bristlenose.utils.hardware._is_apple_silicon", return_value=False),
            patch("bristlenose.utils.hardware._check_cuda_available", return_value=False),
            patch("bristlenose.utils.hardware._get_system_memory_gb", return_value=16.0),
        ):
            info = detect_hardware()
        assert info.accelerator == AcceleratorType.CPU
        assert info.memory_gb == 16.0

    def test_apple_silicon_uses_cache(self, tmp_path: Path):
        """When cache is fresh, detect_hardware skips subprocess calls."""
        cache_file = tmp_path / ".hardware-cache.json"
        cache_data = {
            "chip_name": "Apple M3 Pro",
            "gpu_cores": 18,
            "memory_gb": 36.0,
            "timestamp": time.time(),
        }
        cache_file.write_text(json.dumps(cache_data))

        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
            patch("bristlenose.utils.hardware._is_apple_silicon", return_value=True),
            patch("bristlenose.utils.hardware._check_mlx_available", return_value=False),
            patch("bristlenose.utils.hardware._get_apple_chip_name") as mock_chip,
            patch("bristlenose.utils.hardware._get_apple_gpu_cores") as mock_gpu,
            patch("bristlenose.utils.hardware._get_system_memory_gb") as mock_mem,
        ):
            info = detect_hardware()

        # subprocess helpers should NOT have been called
        mock_chip.assert_not_called()
        mock_gpu.assert_not_called()
        mock_mem.assert_not_called()

        assert info.chip_name == "Apple M3 Pro"
        assert info.gpu_cores == 18
        assert info.memory_gb == 36.0

    def test_apple_silicon_populates_cache(self, tmp_path: Path):
        """When no cache exists, detect_hardware writes one."""
        cache_file = tmp_path / ".hardware-cache.json"

        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
            patch("bristlenose.utils.hardware._is_apple_silicon", return_value=True),
            patch("bristlenose.utils.hardware._get_apple_chip_name", return_value="Apple M2"),
            patch("bristlenose.utils.hardware._get_apple_gpu_cores", return_value=10),
            patch("bristlenose.utils.hardware._get_system_memory_gb", return_value=16.0),
            patch("bristlenose.utils.hardware._check_mlx_available", return_value=False),
        ):
            info = detect_hardware()

        assert info.chip_name == "Apple M2"
        assert cache_file.exists()
        saved = json.loads(cache_file.read_text())
        assert saved["chip_name"] == "Apple M2"
        assert saved["gpu_cores"] == 10
        assert saved["memory_gb"] == 16.0
