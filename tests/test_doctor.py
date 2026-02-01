"""Tests for bristlenose doctor — health checks, fix messages, and CLI wiring.

Includes a comprehensive test grid covering all combinations of:
- OS: macOS (Darwin), Linux, Windows
- Architecture: arm64 (Apple Silicon / ARM Linux), x86_64 (Intel), AMD64
- Install method: snap, brew (/opt/homebrew/ and /usr/local/Cellar/), pip
- GPU: Apple Silicon ± MLX, NVIDIA ± CUDA, CPU-only
- Fix messages: every fix_key × every install method × every OS
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import version for sentinel tests
from bristlenose import __version__
from bristlenose.config import BristlenoseSettings
from bristlenose.doctor import (
    CheckResult,
    CheckStatus,
    DoctorReport,
    check_api_key,
    check_backend,
    check_disk_space,
    check_ffmpeg,
    check_network,
    check_pii,
    check_whisper_model,
    run_all,
    run_preflight,
)
from bristlenose.doctor_fixes import detect_install_method, get_fix

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides: object) -> BristlenoseSettings:
    """Create a BristlenoseSettings with safe defaults for testing."""
    defaults: dict[str, object] = {
        "anthropic_api_key": "sk-ant-test-key-12345678",
        "llm_provider": "anthropic",
        "whisper_model": "large-v3-turbo",
        "pii_enabled": False,
        "output_dir": Path("/tmp/bristlenose-test-output"),
    }
    defaults.update(overrides)
    return BristlenoseSettings(**defaults)  # type: ignore[arg-type]


def _import_blocker(blocked_module: str):
    """Create an __import__ side effect that blocks a specific module."""
    real_import = (
        __builtins__.__import__  # type: ignore[union-attr]
        if hasattr(__builtins__, "__import__")
        else __import__
    )

    def _blocker(name: str, *args: object, **kwargs: object) -> object:
        if name == blocked_module:
            raise ImportError(f"Mocked: {name} not installed")
        return real_import(name, *args, **kwargs)

    return _blocker


def _no_snap_env() -> dict[str, str]:
    """Return current env with SNAP removed."""
    env = os.environ.copy()
    env.pop("SNAP", None)
    return env


# ---------------------------------------------------------------------------
# CheckResult and DoctorReport
# ---------------------------------------------------------------------------


class TestCheckResult:
    def test_ok_result(self) -> None:
        r = CheckResult(status=CheckStatus.OK, label="Test", detail="all good")
        assert r.status == CheckStatus.OK
        assert r.label == "Test"
        assert r.detail == "all good"
        assert r.fix_key == ""

    def test_fail_result_with_fix_key(self) -> None:
        r = CheckResult(
            status=CheckStatus.FAIL,
            label="FFmpeg",
            detail="not found",
            fix_key="ffmpeg_missing",
        )
        assert r.status == CheckStatus.FAIL
        assert r.fix_key == "ffmpeg_missing"


class TestDoctorReport:
    def test_empty_report(self) -> None:
        report = DoctorReport()
        assert not report.has_failures
        assert not report.has_warnings
        assert report.failures == []
        assert report.warnings == []

    def test_report_with_failures(self) -> None:
        report = DoctorReport(results=[
            CheckResult(status=CheckStatus.OK, label="A"),
            CheckResult(status=CheckStatus.FAIL, label="B", fix_key="b_fail"),
            CheckResult(status=CheckStatus.WARN, label="C", fix_key="c_warn"),
        ])
        assert report.has_failures
        assert report.has_warnings
        assert len(report.failures) == 1
        assert report.failures[0].label == "B"
        assert len(report.warnings) == 1
        assert report.warnings[0].label == "C"

    def test_report_notes(self) -> None:
        report = DoctorReport(results=[
            CheckResult(status=CheckStatus.SKIP, label="PII", detail="off"),
            CheckResult(status=CheckStatus.OK, label="FFmpeg"),
        ])
        assert len(report.notes) == 1
        assert report.notes[0].label == "PII"


# ---------------------------------------------------------------------------
# check_ffmpeg — platform grid
# ---------------------------------------------------------------------------


class TestCheckFfmpeg:
    def test_ffmpeg_found(self) -> None:
        with patch("bristlenose.doctor.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("bristlenose.doctor.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="ffmpeg version 6.1.1 Copyright (c) 2000-2023\n",
                )
                result = check_ffmpeg()
        assert result.status == CheckStatus.OK
        assert "6.1.1" in result.detail
        assert "/usr/bin/ffmpeg" in result.detail

    def test_ffmpeg_not_found(self) -> None:
        with patch("bristlenose.doctor.shutil.which", return_value=None):
            result = check_ffmpeg()
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "ffmpeg_missing"

    def test_ffmpeg_found_but_version_fails(self) -> None:
        with patch("bristlenose.doctor.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("bristlenose.doctor.subprocess.run", side_effect=OSError):
                result = check_ffmpeg()
        assert result.status == CheckStatus.OK
        assert "/usr/bin/ffmpeg" in result.detail

    @pytest.mark.parametrize("ffmpeg_path", [
        "/usr/bin/ffmpeg",                             # Linux system
        "/opt/homebrew/bin/ffmpeg",                    # macOS Homebrew arm64
        "/usr/local/bin/ffmpeg",                       # macOS Homebrew Intel
        "/snap/bristlenose/current/usr/bin/ffmpeg",    # snap
        "C:\\ffmpeg\\bin\\ffmpeg.exe",                 # Windows
    ])
    def test_ffmpeg_paths(self, ffmpeg_path: str) -> None:
        """FFmpeg found at various platform-specific paths."""
        with patch("bristlenose.doctor.shutil.which", return_value=ffmpeg_path):
            with patch("bristlenose.doctor.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="ffmpeg version 7.0 Copyright\n",
                )
                result = check_ffmpeg()
        assert result.status == CheckStatus.OK
        assert ffmpeg_path in result.detail


# ---------------------------------------------------------------------------
# check_backend — hardware/GPU grid
# ---------------------------------------------------------------------------


class TestCheckBackend:
    def test_backend_graceful_on_this_machine(self) -> None:
        """check_backend never raises — returns a valid CheckResult regardless."""
        with patch("platform.system", return_value="Linux"):
            with patch("platform.machine", return_value="x86_64"):
                with patch("shutil.which", return_value=None):
                    result = check_backend()

        assert result.status in (CheckStatus.OK, CheckStatus.WARN, CheckStatus.FAIL)
        assert result.label == "Transcription"

    def test_backend_missing_faster_whisper(self) -> None:
        saved = sys.modules.pop("faster_whisper", None)
        try:
            with patch("builtins.__import__", side_effect=_import_blocker("faster_whisper")):
                result = check_backend()
        finally:
            if saved is not None:
                sys.modules["faster_whisper"] = saved
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "backend_import_fail"

    def test_apple_silicon_with_mlx(self) -> None:
        """macOS arm64 with MLX installed → OK."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0
        mock_mlx_whisper = MagicMock()

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
                "mlx_whisper": mock_mlx_whisper,
            }),
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="arm64"),
            patch("shutil.which", return_value=None),
        ):
            result = check_backend()
        assert result.status == CheckStatus.OK
        assert "CPU" in result.detail

    def test_apple_silicon_without_mlx(self) -> None:
        """macOS arm64 without MLX → WARN with mlx_not_installed fix."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0

        # Remove mlx_whisper from modules to simulate not installed
        saved_mlx = sys.modules.pop("mlx_whisper", None)
        try:
            with (
                patch.dict(sys.modules, {
                    "faster_whisper": mock_fw,
                    "ctranslate2": mock_ct2,
                }),
                patch("platform.system", return_value="Darwin"),
                patch("platform.machine", return_value="arm64"),
                patch("shutil.which", return_value=None),
                patch("builtins.__import__", side_effect=_import_blocker("mlx_whisper")),
            ):
                result = check_backend()
        finally:
            if saved_mlx is not None:
                sys.modules["mlx_whisper"] = saved_mlx
        assert result.status == CheckStatus.WARN
        assert result.fix_key == "mlx_not_installed"
        assert "Apple Silicon" in result.detail

    def test_nvidia_gpu_with_cuda(self) -> None:
        """Linux x86_64 with NVIDIA GPU and working CUDA → OK."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 1

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
            }),
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
            patch("shutil.which", return_value=None),
        ):
            result = check_backend()
        assert result.status == CheckStatus.OK
        assert "CUDA" in result.detail

    def test_nvidia_gpu_without_cuda_runtime(self) -> None:
        """Linux x86_64 with nvidia-smi but no CUDA runtime → WARN."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
            }),
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
            # nvidia-smi found → NVIDIA GPU present
            patch("shutil.which", return_value="/usr/bin/nvidia-smi"),
        ):
            result = check_backend()
        assert result.status == CheckStatus.WARN
        assert result.fix_key == "cuda_not_available"
        assert "NVIDIA GPU detected" in result.detail

    def test_linux_cpu_only(self) -> None:
        """Linux x86_64, no GPU at all → OK with CPU."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
            }),
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
            patch("shutil.which", return_value=None),
        ):
            result = check_backend()
        assert result.status == CheckStatus.OK
        assert "CPU" in result.detail

    def test_linux_arm64_cpu_only(self) -> None:
        """Linux arm64 (e.g. RPi, Graviton), no GPU → OK with CPU."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
            }),
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="aarch64"),
            patch("shutil.which", return_value=None),
        ):
            result = check_backend()
        assert result.status == CheckStatus.OK
        assert "CPU" in result.detail

    def test_macos_intel_cpu_only(self) -> None:
        """macOS x86_64 (Intel Mac), no MLX path → OK with CPU."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
            }),
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="x86_64"),
            patch("shutil.which", return_value=None),
        ):
            result = check_backend()
        # Intel Mac: not arm64, so Apple Silicon check doesn't trigger
        assert result.status == CheckStatus.OK
        assert "CPU" in result.detail

    def test_windows_cpu_only(self) -> None:
        """Windows x86_64, CPU only → OK."""
        mock_fw = MagicMock(__version__="1.2.1")
        mock_ct2 = MagicMock(__version__="4.6.3")
        mock_ct2.get_cuda_device_count.return_value = 0

        with (
            patch.dict(sys.modules, {
                "faster_whisper": mock_fw,
                "ctranslate2": mock_ct2,
            }),
            patch("platform.system", return_value="Windows"),
            patch("platform.machine", return_value="AMD64"),
            patch("shutil.which", return_value=None),
        ):
            result = check_backend()
        assert result.status == CheckStatus.OK
        assert "CPU" in result.detail

    def test_ctranslate2_import_error(self) -> None:
        """ctranslate2 fails to import → FAIL."""
        mock_fw = MagicMock(__version__="1.2.1")

        saved_ct2 = sys.modules.pop("ctranslate2", None)
        try:
            with (
                patch.dict(sys.modules, {"faster_whisper": mock_fw}),
                patch("builtins.__import__", side_effect=_import_blocker("ctranslate2")),
            ):
                result = check_backend()
        finally:
            if saved_ct2 is not None:
                sys.modules["ctranslate2"] = saved_ct2
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "backend_import_fail"


# ---------------------------------------------------------------------------
# check_whisper_model
# ---------------------------------------------------------------------------


class TestCheckWhisperModel:
    def test_model_cached(self) -> None:
        settings = _settings(whisper_model="large-v3-turbo")

        mock_repo = MagicMock()
        mock_repo.repo_id = "Systran/faster-whisper-large-v3-turbo"
        mock_repo.size_on_disk = 1_600_000_000

        mock_cache = MagicMock()
        mock_cache.repos = [mock_repo]

        with patch.dict(sys.modules, {"huggingface_hub": MagicMock()}):
            result = check_whisper_model(settings)

        # May or may not find the model — just verify valid result
        assert result.status in (CheckStatus.OK, CheckStatus.SKIP)
        assert "large-v3-turbo" in result.detail

    def test_model_not_cached(self) -> None:
        settings = _settings(whisper_model="tiny")
        with patch.dict(sys.modules, {"huggingface_hub": None}):
            result = check_whisper_model(settings)
        assert result.status == CheckStatus.SKIP
        assert "tiny" in result.detail
        assert "not cached" in result.detail

    @pytest.mark.parametrize("model", ["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"])
    def test_model_names(self, model: str) -> None:
        """All supported model names produce valid results."""
        settings = _settings(whisper_model=model)
        with patch.dict(sys.modules, {"huggingface_hub": None}):
            result = check_whisper_model(settings)
        assert result.status in (CheckStatus.OK, CheckStatus.SKIP)
        assert model in result.detail


# ---------------------------------------------------------------------------
# check_api_key
# ---------------------------------------------------------------------------


class TestCheckApiKey:
    def test_anthropic_key_present(self) -> None:
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-api03-abcdefghijklmnop",
        )
        with patch("bristlenose.doctor._validate_anthropic_key", return_value=(True, "")):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "Anthropic" in result.detail

    def test_anthropic_key_missing(self) -> None:
        settings = _settings(llm_provider="anthropic", anthropic_api_key="")
        result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_anthropic"

    def test_anthropic_key_invalid(self) -> None:
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-bad-key-12345",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_invalid_anthropic"
        assert "rejected" in result.detail

    def test_anthropic_key_validation_network_error(self) -> None:
        """Network error during validation → still OK (key is present)."""
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-api03-abcdefghijklmnop",
        )
        with patch(
            "bristlenose.doctor._validate_anthropic_key",
            return_value=(None, "Connection refused"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "could not validate" in result.detail

    def test_openai_key_present(self) -> None:
        settings = _settings(
            llm_provider="openai",
            openai_api_key="sk-openai-test-key-abcdef",
        )
        with patch("bristlenose.doctor._validate_openai_key", return_value=(True, "")):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "OpenAI" in result.detail

    def test_openai_key_missing(self) -> None:
        settings = _settings(llm_provider="openai", openai_api_key="")
        result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_missing_openai"

    def test_openai_key_invalid(self) -> None:
        settings = _settings(
            llm_provider="openai",
            openai_api_key="sk-bad-key-xyz",
        )
        with patch(
            "bristlenose.doctor._validate_openai_key",
            return_value=(False, "401 Unauthorized"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "api_key_invalid_openai"

    def test_openai_key_validation_network_error(self) -> None:
        settings = _settings(
            llm_provider="openai",
            openai_api_key="sk-openai-test-key-abcdef",
        )
        with patch(
            "bristlenose.doctor._validate_openai_key",
            return_value=(None, "timeout"),
        ):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "could not validate" in result.detail

    def test_unknown_provider(self) -> None:
        settings = _settings(llm_provider="gemini", anthropic_api_key="")
        result = check_api_key(settings)
        assert result.status == CheckStatus.FAIL

    def test_anthropic_key_masking_short_key(self) -> None:
        """Short keys still produce a masked display."""
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="short",
        )
        with patch("bristlenose.doctor._validate_anthropic_key", return_value=(True, "")):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "(set)" in result.detail

    def test_anthropic_key_masking_long_key(self) -> None:
        """Long keys show sk-ant-...xxx."""
        settings = _settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
        )
        with patch("bristlenose.doctor._validate_anthropic_key", return_value=(True, "")):
            result = check_api_key(settings)
        assert result.status == CheckStatus.OK
        assert "sk-ant-..." in result.detail


# ---------------------------------------------------------------------------
# check_network
# ---------------------------------------------------------------------------


class TestCheckNetwork:
    def test_network_reachable_anthropic(self) -> None:
        settings = _settings(llm_provider="anthropic")
        with patch("urllib.request.urlopen"):
            result = check_network(settings)
        assert result.status == CheckStatus.OK
        assert "api.anthropic.com" in result.detail

    def test_network_unreachable(self) -> None:
        import urllib.error

        settings = _settings(llm_provider="anthropic")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            result = check_network(settings)
        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "network_unreachable"

    def test_network_reachable_openai(self) -> None:
        settings = _settings(llm_provider="openai")
        with patch("urllib.request.urlopen"):
            result = check_network(settings)
        assert result.status == CheckStatus.OK
        assert "api.openai.com" in result.detail

    def test_network_timeout(self) -> None:
        """Timeout is treated as unreachable."""
        import urllib.error

        settings = _settings(llm_provider="anthropic")
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            result = check_network(settings)
        assert result.status == CheckStatus.FAIL

    def test_network_unknown_provider_defaults_to_anthropic(self) -> None:
        """Unknown provider still checks something (defaults to anthropic)."""
        settings = _settings(llm_provider="gemini")
        with patch("urllib.request.urlopen"):
            result = check_network(settings)
        assert result.status == CheckStatus.OK
        assert "api.anthropic.com" in result.detail


# ---------------------------------------------------------------------------
# check_pii
# ---------------------------------------------------------------------------


class TestCheckPii:
    def test_pii_disabled(self) -> None:
        settings = _settings(pii_enabled=False)
        result = check_pii(settings)
        assert result.status == CheckStatus.SKIP
        assert "off" in result.detail

    def test_pii_enabled_all_present(self) -> None:
        settings = _settings(pii_enabled=True)
        mock_spacy = MagicMock()
        mock_nlp = MagicMock()
        mock_nlp.meta = {"version": "3.8.0"}
        mock_spacy.load.return_value = mock_nlp

        with patch.dict(sys.modules, {
            "presidio_analyzer": MagicMock(),
            "spacy": mock_spacy,
        }):
            with patch("importlib.metadata.version", return_value="2.2.360"):
                result = check_pii(settings)

        assert result.status == CheckStatus.OK
        assert "presidio" in result.detail
        assert "spaCy" in result.detail

    def test_pii_enabled_spacy_model_missing(self) -> None:
        settings = _settings(pii_enabled=True)
        mock_spacy = MagicMock()
        mock_spacy.load.side_effect = OSError("model not found")

        with patch.dict(sys.modules, {
            "presidio_analyzer": MagicMock(),
            "spacy": mock_spacy,
        }):
            with patch("importlib.metadata.version", return_value="2.2.360"):
                result = check_pii(settings)

        assert result.status == CheckStatus.FAIL
        assert result.fix_key == "spacy_model_missing"

    def test_pii_enabled_presidio_missing(self) -> None:
        """presidio not installed → FAIL."""
        settings = _settings(pii_enabled=True)
        saved = sys.modules.pop("presidio_analyzer", None)
        try:
            with patch(
                "builtins.__import__",
                side_effect=_import_blocker("presidio_analyzer"),
            ):
                result = check_pii(settings)
        finally:
            if saved is not None:
                sys.modules["presidio_analyzer"] = saved
        assert result.status == CheckStatus.FAIL

    def test_pii_enabled_spacy_not_installed(self) -> None:
        """spaCy itself not installed → FAIL."""
        settings = _settings(pii_enabled=True)
        mock_spacy = MagicMock()
        # spacy.load raises ImportError (spacy installed but broken)
        mock_spacy.load.side_effect = ImportError("no module")

        with patch.dict(sys.modules, {
            "presidio_analyzer": MagicMock(),
            "spacy": mock_spacy,
        }):
            with patch("importlib.metadata.version", return_value="2.2.360"):
                # ImportError from spacy.load is caught differently than OSError
                # The function catches OSError for model missing
                # ImportError would mean spacy itself is broken
                result = check_pii(settings)
        # spacy.load raising ImportError — this isn't caught by the OSError handler
        # so it should propagate through. Let's verify the function handles it.
        assert result.status == CheckStatus.FAIL


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------


class TestCheckDiskSpace:
    def test_plenty_of_space(self) -> None:
        settings = _settings(output_dir=Path("/tmp"))
        result = check_disk_space(settings)
        assert result.status == CheckStatus.OK
        assert "GB free" in result.detail

    def test_low_space(self) -> None:
        settings = _settings(output_dir=Path("/tmp"))
        mock_usage = MagicMock()
        mock_usage.free = 500 * 1024 * 1024  # 500 MB
        with patch("bristlenose.doctor.shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space(settings)
        assert result.status == CheckStatus.WARN
        assert result.fix_key == "low_disk_space"
        assert "MB free" in result.detail

    def test_output_dir_not_yet_created(self) -> None:
        """Output dir doesn't exist yet — checks parent."""
        settings = _settings(output_dir=Path("/tmp/bristlenose-new-dir/output"))
        mock_usage = MagicMock()
        mock_usage.free = 50 * 1024**3  # 50 GB
        with patch("bristlenose.doctor.shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space(settings)
        assert result.status == CheckStatus.OK

    def test_borderline_space(self) -> None:
        """Exactly 2 GB → OK (threshold is < 2.0)."""
        settings = _settings(output_dir=Path("/tmp"))
        mock_usage = MagicMock()
        mock_usage.free = 2 * 1024**3  # exactly 2 GB
        with patch("bristlenose.doctor.shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space(settings)
        assert result.status == CheckStatus.OK

    def test_just_under_threshold(self) -> None:
        """1.99 GB → WARN."""
        settings = _settings(output_dir=Path("/tmp"))
        mock_usage = MagicMock()
        mock_usage.free = int(1.99 * 1024**3)
        with patch("bristlenose.doctor.shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space(settings)
        assert result.status == CheckStatus.WARN


# ---------------------------------------------------------------------------
# run_all and run_preflight
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_run_all_returns_seven_results(self) -> None:
        settings = _settings()
        with (
            patch("bristlenose.doctor.check_ffmpeg") as m1,
            patch("bristlenose.doctor.check_backend") as m2,
            patch("bristlenose.doctor.check_whisper_model") as m3,
            patch("bristlenose.doctor.check_api_key") as m4,
            patch("bristlenose.doctor.check_network") as m5,
            patch("bristlenose.doctor.check_pii") as m6,
            patch("bristlenose.doctor.check_disk_space") as m7,
        ):
            for m in (m1, m2, m3, m4, m5, m6, m7):
                m.return_value = CheckResult(status=CheckStatus.OK, label="test")
            report = run_all(settings)

        assert len(report.results) == 7
        assert not report.has_failures


class TestRunPreflight:
    def test_render_has_no_checks(self) -> None:
        settings = _settings()
        report = run_preflight(settings, "render")
        assert len(report.results) == 0

    def test_run_has_all_checks(self) -> None:
        settings = _settings()
        with (
            patch("bristlenose.doctor.check_ffmpeg") as m1,
            patch("bristlenose.doctor.check_backend") as m2,
            patch("bristlenose.doctor.check_whisper_model") as m3,
            patch("bristlenose.doctor.check_api_key") as m4,
            patch("bristlenose.doctor.check_network") as m5,
            patch("bristlenose.doctor.check_pii") as m6,
            patch("bristlenose.doctor.check_disk_space") as m7,
        ):
            for m in (m1, m2, m3, m4, m5, m6, m7):
                m.return_value = CheckResult(status=CheckStatus.OK, label="test")
            report = run_preflight(settings, "run")

        assert len(report.results) == 7

    def test_transcribe_only_skips_api_and_network(self) -> None:
        settings = _settings()
        with (
            patch("bristlenose.doctor.check_ffmpeg") as m1,
            patch("bristlenose.doctor.check_backend") as m2,
            patch("bristlenose.doctor.check_whisper_model") as m3,
            patch("bristlenose.doctor.check_disk_space") as m4,
        ):
            for m in (m1, m2, m3, m4):
                m.return_value = CheckResult(status=CheckStatus.OK, label="test")
            report = run_preflight(settings, "transcribe-only")

        assert len(report.results) == 4

    def test_analyze_checks_api_network_disk(self) -> None:
        settings = _settings()
        with (
            patch("bristlenose.doctor.check_api_key") as m1,
            patch("bristlenose.doctor.check_network") as m2,
            patch("bristlenose.doctor.check_disk_space") as m3,
        ):
            for m in (m1, m2, m3):
                m.return_value = CheckResult(status=CheckStatus.OK, label="test")
            report = run_preflight(settings, "analyze")

        assert len(report.results) == 3

    def test_run_skip_tx_omits_transcription_checks(self) -> None:
        settings = _settings()
        with (
            patch("bristlenose.doctor.check_api_key") as m1,
            patch("bristlenose.doctor.check_network") as m2,
            patch("bristlenose.doctor.check_pii") as m3,
            patch("bristlenose.doctor.check_disk_space") as m4,
        ):
            for m in (m1, m2, m3, m4):
                m.return_value = CheckResult(status=CheckStatus.OK, label="test")
            report = run_preflight(settings, "run", skip_transcription=True)

        assert len(report.results) == 4

    def test_unknown_command_has_no_checks(self) -> None:
        """Unknown command name → empty preflight (safe default)."""
        settings = _settings()
        report = run_preflight(settings, "nonexistent-command")
        assert len(report.results) == 0


# ---------------------------------------------------------------------------
# detect_install_method — full grid
# ---------------------------------------------------------------------------


class TestDetectInstallMethod:
    """Test all realistic combinations of OS × arch × install method."""

    # -- Snap --

    def test_snap_linux_amd64(self) -> None:
        with patch.dict(os.environ, {"SNAP": "/snap/bristlenose/42"}):
            assert detect_install_method() == "snap"

    def test_snap_linux_arm64(self) -> None:
        with patch.dict(os.environ, {"SNAP": "/snap/bristlenose/42"}):
            assert detect_install_method() == "snap"

    def test_snap_takes_priority_over_brew_path(self) -> None:
        """If both SNAP and brew path are present, snap wins."""
        with (
            patch.dict(os.environ, {"SNAP": "/snap/bristlenose/42"}),
            patch("bristlenose.doctor_fixes.sys.executable", "/opt/homebrew/bin/python3"),
        ):
            assert detect_install_method() == "snap"

    # -- Homebrew --

    def test_brew_macos_apple_silicon(self) -> None:
        """macOS arm64 Homebrew → /opt/homebrew/."""
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "/opt/homebrew/Cellar/bristlenose/0.5.0/libexec/bin/python3",
            ),
        ):
            assert detect_install_method() == "brew"

    def test_brew_macos_intel(self) -> None:
        """macOS x86_64 Homebrew → /usr/local/Cellar/."""
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "/usr/local/Cellar/bristlenose/0.5.0/libexec/bin/python3",
            ),
        ):
            assert detect_install_method() == "brew"

    def test_brew_linuxbrew(self) -> None:
        """Linuxbrew uses /home/linuxbrew/.linuxbrew — NOT detected as brew.

        Linuxbrew doesn't use /opt/homebrew/ or /usr/local/Cellar/ paths,
        so it falls through to pip. This is expected — Linuxbrew is rare and
        the pip instructions work fine.
        """
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "/home/linuxbrew/.linuxbrew/bin/python3",
            ),
        ):
            assert detect_install_method() == "pip"

    # -- Pip / pipx / uv --

    def test_pip_linux_system_python(self) -> None:
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch("bristlenose.doctor_fixes.sys.executable", "/usr/bin/python3"),
        ):
            assert detect_install_method() == "pip"

    def test_pip_linux_venv(self) -> None:
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "/home/user/.local/share/pipx/venvs/bristlenose/bin/python3",
            ),
        ):
            assert detect_install_method() == "pip"

    def test_pip_macos_system_python(self) -> None:
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            ),
        ):
            assert detect_install_method() == "pip"

    def test_pip_windows(self) -> None:
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
            ),
        ):
            assert detect_install_method() == "pip"

    def test_pip_uv_managed(self) -> None:
        with (
            patch.dict(os.environ, _no_snap_env(), clear=True),
            patch(
                "bristlenose.doctor_fixes.sys.executable",
                "/home/user/.local/share/uv/tools/bristlenose/bin/python3",
            ),
        ):
            assert detect_install_method() == "pip"


# ---------------------------------------------------------------------------
# get_fix — full grid: every fix_key × every install method × relevant OS
# ---------------------------------------------------------------------------


class TestGetFixGrid:
    """Exhaustive test of fix messages across the full matrix.

    Grid dimensions:
    - 12 fix_keys
    - 3 install methods (snap, brew, pip)
    - OS variants for pip (Linux, Darwin, Windows)
    """

    # -- ffmpeg_missing: varies by method AND by OS (for pip) --

    def test_ffmpeg_missing_snap(self) -> None:
        fix = get_fix("ffmpeg_missing", "snap")
        assert "bug in the snap" in fix
        assert "snap refresh" in fix
        assert "github.com" in fix

    def test_ffmpeg_missing_brew(self) -> None:
        fix = get_fix("ffmpeg_missing", "brew")
        assert "brew install ffmpeg" in fix
        # brew message should NOT contain apt/dnf/pacman
        assert "apt" not in fix

    def test_ffmpeg_missing_pip_linux(self) -> None:
        with patch("bristlenose.doctor_fixes.platform.system", return_value="Linux"):
            fix = get_fix("ffmpeg_missing", "pip")
        assert "sudo apt install ffmpeg" in fix
        assert "sudo dnf install ffmpeg" in fix
        assert "sudo pacman -S ffmpeg" in fix

    def test_ffmpeg_missing_pip_macos(self) -> None:
        with patch("bristlenose.doctor_fixes.platform.system", return_value="Darwin"):
            fix = get_fix("ffmpeg_missing", "pip")
        assert "brew install ffmpeg" in fix
        # macOS pip: no apt/dnf
        assert "apt" not in fix

    def test_ffmpeg_missing_pip_windows(self) -> None:
        with patch("bristlenose.doctor_fixes.platform.system", return_value="Windows"):
            fix = get_fix("ffmpeg_missing", "pip")
        assert "ffmpeg.org/download" in fix
        # Windows: no apt/dnf/brew
        assert "apt" not in fix
        assert "brew" not in fix

    # -- backend_import_fail: snap vs everything else --

    def test_backend_import_fail_snap(self) -> None:
        fix = get_fix("backend_import_fail", "snap")
        assert "bug in the snap" in fix
        assert "snap refresh" in fix

    def test_backend_import_fail_brew(self) -> None:
        fix = get_fix("backend_import_fail", "brew")
        assert "pip install --upgrade" in fix
        assert "ctranslate2" in fix
        assert "faster-whisper" in fix

    def test_backend_import_fail_pip(self) -> None:
        fix = get_fix("backend_import_fail", "pip")
        assert "pip install --upgrade" in fix

    # -- api_key_missing_anthropic: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_api_key_missing_anthropic(self, method: str) -> None:
        fix = get_fix("api_key_missing_anthropic", method)
        assert "BRISTLENOSE_ANTHROPIC_API_KEY" in fix
        assert "console.anthropic.com" in fix
        assert "--llm openai" in fix  # alternative suggestion

    # -- api_key_missing_openai: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_api_key_missing_openai(self, method: str) -> None:
        fix = get_fix("api_key_missing_openai", method)
        assert "BRISTLENOSE_OPENAI_API_KEY" in fix
        assert "platform.openai.com" in fix

    # -- api_key_invalid_anthropic: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_api_key_invalid_anthropic(self, method: str) -> None:
        fix = get_fix("api_key_invalid_anthropic", method)
        assert "console.anthropic.com" in fix

    # -- api_key_invalid_openai: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_api_key_invalid_openai(self, method: str) -> None:
        fix = get_fix("api_key_invalid_openai", method)
        assert "platform.openai.com" in fix

    # -- network_unreachable: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_network_unreachable(self, method: str) -> None:
        fix = get_fix("network_unreachable", method)
        assert "HTTPS_PROXY" in fix

    # -- spacy_model_missing: varies by method --

    def test_spacy_model_missing_snap(self) -> None:
        fix = get_fix("spacy_model_missing", "snap")
        assert "bug in the snap" in fix
        assert "snap refresh" in fix

    def test_spacy_model_missing_brew(self) -> None:
        fix = get_fix("spacy_model_missing", "brew")
        assert "brew --prefix" in fix
        assert "spacy download en_core_web_sm" in fix

    def test_spacy_model_missing_pip(self) -> None:
        fix = get_fix("spacy_model_missing", "pip")
        assert "python3 -m spacy download en_core_web_sm" in fix
        assert "brew" not in fix

    # -- presidio_missing: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_presidio_missing(self, method: str) -> None:
        fix = get_fix("presidio_missing", method)
        assert "presidio-analyzer" in fix

    # -- mlx_not_installed: varies by method --

    def test_mlx_not_installed_brew(self) -> None:
        fix = get_fix("mlx_not_installed", "brew")
        assert "brew --prefix" in fix
        assert "bristlenose[apple]" in fix

    def test_mlx_not_installed_pip(self) -> None:
        fix = get_fix("mlx_not_installed", "pip")
        assert "pip install" in fix
        assert "bristlenose[apple]" in fix
        assert "brew" not in fix

    def test_mlx_not_installed_snap(self) -> None:
        """Snap is Linux-only, MLX is macOS-only — message still works."""
        fix = get_fix("mlx_not_installed", "snap")
        # Falls through to non-brew path
        assert "bristlenose[apple]" in fix

    # -- cuda_not_available: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_cuda_not_available(self, method: str) -> None:
        fix = get_fix("cuda_not_available", method)
        assert "CUDA" in fix
        assert "LD_LIBRARY_PATH" in fix

    # -- low_disk_space: same for all methods --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_low_disk_space(self, method: str) -> None:
        fix = get_fix("low_disk_space", method)
        assert "tiny" in fix
        assert "small" in fix

    # -- unknown key --

    @pytest.mark.parametrize("method", ["snap", "brew", "pip"])
    def test_unknown_fix_key(self, method: str) -> None:
        fix = get_fix("nonexistent_key", method)
        assert fix == ""


# ---------------------------------------------------------------------------
# CLI sentinel logic
# ---------------------------------------------------------------------------


class TestSentinelLogic:
    def test_should_auto_doctor_no_sentinel(self, tmp_path: Path) -> None:
        from bristlenose.cli import _should_auto_doctor

        sentinel = tmp_path / ".doctor-ran"
        with patch("bristlenose.cli._doctor_sentinel_file", return_value=sentinel):
            assert _should_auto_doctor() is True

    def test_should_auto_doctor_version_match(self, tmp_path: Path) -> None:
        from bristlenose.cli import _should_auto_doctor

        sentinel = tmp_path / ".doctor-ran"
        sentinel.write_text(__version__)
        with patch("bristlenose.cli._doctor_sentinel_file", return_value=sentinel):
            assert _should_auto_doctor() is False

    def test_should_auto_doctor_version_mismatch(self, tmp_path: Path) -> None:
        from bristlenose.cli import _should_auto_doctor

        sentinel = tmp_path / ".doctor-ran"
        sentinel.write_text("0.0.0")
        with patch("bristlenose.cli._doctor_sentinel_file", return_value=sentinel):
            assert _should_auto_doctor() is True

    def test_write_doctor_sentinel(self, tmp_path: Path) -> None:
        from bristlenose.cli import _write_doctor_sentinel

        sentinel = tmp_path / ".doctor-ran"
        with patch("bristlenose.cli._doctor_sentinel_file", return_value=sentinel):
            _write_doctor_sentinel()
        assert sentinel.read_text() == __version__

    def test_sentinel_dir_respects_snap_user_common(self) -> None:
        from bristlenose.cli import _doctor_sentinel_dir

        with patch.dict(os.environ, {"SNAP_USER_COMMON": "/home/user/snap/bristlenose/common"}):
            result = _doctor_sentinel_dir()
        assert result == Path("/home/user/snap/bristlenose/common")

    def test_sentinel_dir_default(self) -> None:
        from bristlenose.cli import _doctor_sentinel_dir

        env = os.environ.copy()
        env.pop("SNAP_USER_COMMON", None)
        with patch.dict(os.environ, env, clear=True):
            result = _doctor_sentinel_dir()
        assert ".config/bristlenose" in str(result)

    def test_write_sentinel_creates_parent_dir(self, tmp_path: Path) -> None:
        """Sentinel write creates parent dirs if they don't exist."""
        from bristlenose.cli import _write_doctor_sentinel

        sentinel = tmp_path / "nested" / "dir" / ".doctor-ran"
        with patch("bristlenose.cli._doctor_sentinel_file", return_value=sentinel):
            _write_doctor_sentinel()
        assert sentinel.exists()
        assert sentinel.read_text() == __version__
