"""Tests for bristlenose.preflight.whisper."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from bristlenose.config import BristlenoseSettings
from bristlenose.preflight.whisper import (
    WHISPER_SIZE_HUMAN,
    WhisperPreflightAbortedError,
    _resolve_repo_id,
    cache_state,
    preflight_whisper,
)


def _settings(**kwargs) -> BristlenoseSettings:
    base = {
        "whisper_backend": "mlx",
        "whisper_model": "large-v3-turbo",
        "no_fetch": False,
    }
    base.update(kwargs)
    return BristlenoseSettings(**base)


# ---------------------------------------------------------------------------
# Repo resolution
# ---------------------------------------------------------------------------


class TestResolveRepoId:
    def test_mlx_backend_picks_mlx_community(self):
        with patch("bristlenose.utils.hardware.detect_hardware"):
            with patch(
                "bristlenose.stages.s05_transcribe._resolve_backend", return_value="mlx"
            ):
                assert (
                    _resolve_repo_id(_settings(whisper_model="large-v3-turbo"))
                    == "mlx-community/whisper-large-v3-turbo"
                )

    def test_faster_whisper_picks_systran(self):
        with patch("bristlenose.utils.hardware.detect_hardware"):
            with patch(
                "bristlenose.stages.s05_transcribe._resolve_backend",
                return_value="faster-whisper",
            ):
                assert (
                    _resolve_repo_id(_settings(whisper_model="large-v3-turbo"))
                    == "Systran/faster-whisper-large-v3"
                )

    def test_unknown_model_passes_through(self):
        with patch("bristlenose.utils.hardware.detect_hardware"):
            with patch(
                "bristlenose.stages.s05_transcribe._resolve_backend", return_value="mlx"
            ):
                assert (
                    _resolve_repo_id(_settings(whisper_model="custom/repo-name"))
                    == "custom/repo-name"
                )


# ---------------------------------------------------------------------------
# Cache-state detection
# ---------------------------------------------------------------------------


class TestCacheState:
    def test_cached_when_heavy_blob_present_and_no_partials(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        # The .incomplete scan looks at the real cache dir; no partials present here.
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.return_value = str(
            tmp_path / "models--x" / "snapshots" / "abc" / "model.bin"
        )
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert cache_state("Systran/faster-whisper-large-v3") == "cached"
        # Verify probe used the heavy blob, not config.json
        kwargs = fake_hf.try_to_load_from_cache.call_args.kwargs
        assert kwargs["filename"] == "model.bin"

    def test_mlx_repo_probes_weights_npz(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.return_value = "/cache/weights.npz"
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            cache_state("mlx-community/whisper-large-v3-turbo")
        assert (
            fake_hf.try_to_load_from_cache.call_args.kwargs["filename"]
            == "weights.npz"
        )

    def test_partial_when_incomplete_blobs_exist(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        blobs = tmp_path / "models--openai--whisper-large-v3-turbo" / "blobs"
        blobs.mkdir(parents=True)
        (blobs / "abc123.incomplete").write_text("partial")
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.return_value = None
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert cache_state("openai/whisper-large-v3-turbo") == "partial"

    def test_missing_when_neither(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.return_value = None
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert cache_state("openai/whisper-large-v3-turbo") == "missing"


# ---------------------------------------------------------------------------
# preflight_whisper orchestration
# ---------------------------------------------------------------------------


class TestPreflightWhisper:
    def test_cached_path_is_silent(self, capsys):
        console = Console(force_terminal=False, no_color=True)
        with patch("bristlenose.preflight.whisper.cache_state", return_value="cached"):
            with patch(
                "bristlenose.preflight.whisper._resolve_repo_id",
                return_value="mlx-community/whisper-large-v3-turbo",
            ):
                with patch(
                    "bristlenose.utils.package_install.ensure_hf_model"
                ) as fetch:
                    preflight_whisper(
                        settings=_settings(),
                        console=console,
                        status=None,
                        allow_fetch=True,
                    )
        fetch.assert_not_called()
        # No banner output on the silent path.
        assert "Bristlenose needs" not in capsys.readouterr().out

    def test_missing_with_allow_fetch_prints_banner_and_downloads(self, capsys):
        console = Console(force_terminal=False, no_color=True, width=80)
        with patch("bristlenose.preflight.whisper.cache_state", return_value="missing"):
            with patch(
                "bristlenose.preflight.whisper._resolve_repo_id",
                return_value="mlx-community/whisper-large-v3-turbo",
            ):
                with patch(
                    "bristlenose.utils.package_install.ensure_hf_model",
                    return_value="/cache/path",
                ) as fetch:
                    preflight_whisper(
                        settings=_settings(),
                        console=console,
                        status=None,
                        allow_fetch=True,
                    )
        fetch.assert_called_once_with("mlx-community/whisper-large-v3-turbo")
        out = capsys.readouterr().out
        assert "Bristlenose needs the Whisper transcription model" in out
        assert WHISPER_SIZE_HUMAN in out
        assert "Downloading" in out
        assert "Resuming" not in out
        assert "Cancellable with Ctrl+C; resumes cleanly next run." in out
        assert "Whisper model ready" in out

    def test_partial_says_resuming_not_downloading(self, capsys):
        console = Console(force_terminal=False, no_color=True, width=80)
        with patch("bristlenose.preflight.whisper.cache_state", return_value="partial"):
            with patch(
                "bristlenose.preflight.whisper._resolve_repo_id",
                return_value="mlx-community/whisper-large-v3-turbo",
            ):
                with patch(
                    "bristlenose.utils.package_install.ensure_hf_model",
                    return_value="/cache/path",
                ):
                    preflight_whisper(
                        settings=_settings(),
                        console=console,
                        status=None,
                        allow_fetch=True,
                    )
        out = capsys.readouterr().out
        assert "Resuming download" in out

    def test_no_fetch_with_missing_model_aborts(self):
        console = Console(force_terminal=False, no_color=True)
        with patch("bristlenose.preflight.whisper.cache_state", return_value="missing"):
            with patch(
                "bristlenose.preflight.whisper._resolve_repo_id",
                return_value="mlx-community/whisper-large-v3-turbo",
            ):
                with patch(
                    "bristlenose.utils.package_install.ensure_hf_model"
                ) as fetch:
                    with pytest.raises(WhisperPreflightAbortedError, match="--no-fetch"):
                        preflight_whisper(
                            settings=_settings(),
                            console=console,
                            status=None,
                            allow_fetch=False,
                        )
        fetch.assert_not_called()

    def test_no_fetch_with_cached_model_is_silent(self):
        # --no-fetch must not raise when the model is already cached.
        console = Console(force_terminal=False, no_color=True)
        with patch("bristlenose.preflight.whisper.cache_state", return_value="cached"):
            with patch(
                "bristlenose.preflight.whisper._resolve_repo_id",
                return_value="mlx-community/whisper-large-v3-turbo",
            ):
                preflight_whisper(
                    settings=_settings(),
                    console=console,
                    status=None,
                    allow_fetch=False,
                )

    def test_status_is_stopped_and_restarted_around_fetch(self):
        console = Console(force_terminal=False, no_color=True)
        status = MagicMock()
        with patch("bristlenose.preflight.whisper.cache_state", return_value="missing"):
            with patch(
                "bristlenose.preflight.whisper._resolve_repo_id",
                return_value="mlx-community/whisper-large-v3-turbo",
            ):
                with patch(
                    "bristlenose.utils.package_install.ensure_hf_model",
                    return_value="/cache/path",
                ):
                    preflight_whisper(
                        settings=_settings(),
                        console=console,
                        status=status,
                        allow_fetch=True,
                    )
        status.stop.assert_called_once()
        status.start.assert_called_once()
