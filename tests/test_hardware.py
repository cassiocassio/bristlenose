"""Tests for hardware detection and caching."""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
        # No chip name: the header said "cpu · CPU" (seen on Windows and Linux).
        info = HardwareInfo(accelerator=AcceleratorType.CPU)
        assert info.label == "CPU"

    def test_label_named_chip_on_cpu(self):
        info = HardwareInfo(accelerator=AcceleratorType.CPU, chip_name="Intel Xeon 8488C")
        assert info.label == "Intel Xeon 8488C · CPU"

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
        cache_file.write_text(json.dumps(expired_data), encoding="utf-8")
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
        cache_file.write_text(json.dumps(fresh_data), encoding="utf-8")
        with (
            patch("bristlenose.utils.hardware._CACHE_DIR", tmp_path),
            patch("bristlenose.utils.hardware._CACHE_FILE", cache_file),
        ):
            result = _load_hardware_cache()
            assert result is not None
            assert result["chip_name"] == "Apple M2"

    def test_load_returns_none_on_corrupt_json(self, tmp_path: Path):
        cache_file = tmp_path / ".hardware-cache.json"
        cache_file.write_text("not json{{{", encoding="utf-8")
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
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

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
        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        assert saved["chip_name"] == "Apple M2"
        assert saved["gpu_cores"] == 10
        assert saved["memory_gb"] == 16.0


class TestModuleInstalled:
    """`module_installed` answers from the import system without importing.

    Importing mlx creates the Metal device; where that fails the process dies on a
    native abort no `except` catches (clean macOS 15 guest, 30 Oct 2026).
    """

    def test_finds_an_installed_module_without_importing_it(self) -> None:
        import sys

        from bristlenose.utils.hardware import module_installed

        sys.modules.pop("json.tool", None)
        assert module_installed("json.tool") is True
        assert "json.tool" not in sys.modules

    def test_missing_module_is_false(self) -> None:
        from bristlenose.utils.hardware import module_installed

        assert module_installed("definitely_not_a_module_xyz") is False

    def test_check_mlx_available_does_not_import_mlx(self) -> None:
        import builtins
        from unittest.mock import patch

        from bristlenose.utils.hardware import _check_mlx_available

        real_import = builtins.__import__

        def guard(name: str, *args: object, **kwargs: object) -> object:
            if name.split(".")[0] in {"mlx", "mlx_whisper"}:
                raise AssertionError(f"imported {name}")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        with patch("builtins.__import__", side_effect=guard):
            assert isinstance(_check_mlx_available(), bool)


class TestProbeMlxStarts:
    """The question "can MLX start" goes to a child: where it cannot, the process dies on a
    native abort that no except can catch (macOS 15 guest, 30 Oct 2026)."""

    @staticmethod
    def _run(returncode: int = 0, stderr: str = "", raises: Exception | None = None):
        import subprocess
        from unittest.mock import patch

        from bristlenose.utils.hardware import probe_mlx_starts

        def fake(cmd, **kwargs):
            if raises is not None:
                raise raises
            return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

        with patch("bristlenose.utils.hardware.subprocess.run", side_effect=fake) as run:
            return probe_mlx_starts(timeout=5), run

    def test_a_clean_exit_is_a_yes(self) -> None:
        probe, run = self._run(0)
        assert probe.ok
        assert run.call_args.args[0][-2:] == ["doctor", "--mlx-probe"]

    def test_death_by_signal_is_a_no_that_names_the_signal(self) -> None:
        probe, _ = self._run(-5)  # SIGTRAP: Metal device creation aborted
        assert not probe.ok
        assert "signal 5" in probe.detail

    def test_a_python_error_is_a_no_with_its_last_line(self) -> None:
        probe, _ = self._run(1, stderr="Traceback...\nRuntimeError: no Metal device\n")
        assert not probe.ok
        assert probe.detail == "RuntimeError: no Metal device"

    def test_a_timeout_is_inconclusive_not_a_no(self) -> None:
        """A cold first launch took 25 s to start the sidecar at all: slow is not broken."""
        import subprocess

        probe, _ = self._run(raises=subprocess.TimeoutExpired("x", 5))
        assert probe.ok

    def test_a_probe_that_cannot_launch_is_inconclusive(self) -> None:
        probe, _ = self._run(raises=OSError("exec format error"))
        assert probe.ok

    def test_the_frozen_sidecar_reruns_itself_and_anything_else_runs_the_module(
        self, monkeypatch
    ) -> None:
        import sys

        from bristlenose.utils.hardware import _self_command

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        assert _self_command() == [sys.executable]
        monkeypatch.delattr(sys, "frozen", raising=False)
        assert _self_command() == [sys.executable, "-m", "bristlenose"]

    @staticmethod
    def _probe_with_stub_mlx(tmp_path: Path, core_py: str) -> subprocess.CompletedProcess[str]:
        """Run `doctor --mlx-probe` in a child whose `mlx.core` is the stub given.

        A stub on PYTHONPATH shadows any real mlx, so this runs the same on a Linux CI
        box and on the Mac: the flag's wiring is under test, not Metal.
        """
        pkg = tmp_path / "mlx"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "core.py").write_text(core_py, encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(tmp_path)}
        return subprocess.run(
            [sys.executable, "-m", "bristlenose", "doctor", "--mlx-probe"],
            capture_output=True, text=True, timeout=120, env=env,
        )

    def test_the_probe_flag_imports_mlx_core_runs_one_op_and_answers(self, tmp_path: Path) -> None:
        """`doctor --mlx-probe` exists, imports mlx.core, evaluates one op and prints its line."""
        done = self._probe_with_stub_mlx(
            tmp_path, "def arange(n):\n    return n\n\ndef eval(*args):\n    pass\n"
        )
        assert done.returncode == 0, done.stderr
        assert "@mlx-probe ok" in done.stdout

    def test_the_probe_flag_dies_with_mlx_rather_than_answering(self, tmp_path: Path) -> None:
        """Where MLX cannot start the child dies: no ok line, and a non-zero exit.

        The stub dies by SIGKILL, not `os.abort()`: SIGABRT makes macOS raise a "Python quit
        unexpectedly" Problem Report dialog on every run of the suite. SIGKILL is the same
        shape for the parent (killed by a signal, no output) and files no crash report.
        """
        done = self._probe_with_stub_mlx(
            tmp_path,
            "import os, signal\n\ndef arange(n):\n    return n\n\n"
            "def eval(*args):\n    os.kill(os.getpid(), signal.SIGKILL)\n",
        )
        assert done.returncode != 0
        assert "@mlx-probe ok" not in done.stdout
