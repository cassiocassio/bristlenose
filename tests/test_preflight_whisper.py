"""Tests for bristlenose.preflight.whisper."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from bristlenose.config import BristlenoseSettings
from bristlenose.preflight.whisper import (
    _DOWNLOAD_MB,
    _FASTER_WHISPER_REPO_FOR_MODEL,
    WhisperPreflightAbortedError,
    _format_mb,
    _heavy_blob_candidates,
    _resolve_repo_id,
    cache_state,
    download_size_human,
    preflight_whisper,
)
from bristlenose.stages.s05_transcribe import MLX_REPO_FOR_MODEL


@pytest.fixture(autouse=True)
def _allow_preflight(monkeypatch):
    """Opt out of the global ``BRISTLENOSE_SKIP_PREFLIGHT=1`` set in
    ``tests/conftest.py`` — this file tests the preflight itself."""
    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)


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

    def test_faster_whisper_turbo_picks_the_repo_faster_whisper_opens(self):
        # Was Systran/faster-whisper-large-v3 — a different, 3 GB model that
        # stage 5 never opens, so it downloaded turbo again with no banner.
        with patch("bristlenose.utils.hardware.detect_hardware"):
            with patch(
                "bristlenose.stages.s05_transcribe._resolve_backend",
                return_value="faster-whisper",
            ):
                assert (
                    _resolve_repo_id(_settings(whisper_model="large-v3-turbo"))
                    == "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
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


def _advertised_model_names() -> set[str]:
    """Every name ``--whisper-model`` advertises, plus every MLX short name.

    Read from the CLI's own help strings so a name added there without a table
    entry fails here rather than as a 401 from the Hub on a user's machine.
    """
    import re
    from pathlib import Path

    import bristlenose.cli as cli_module

    src = Path(cli_module.__file__).read_text()
    names: set[str] = set()
    for listing in re.findall(r"Whisper model size: ([a-z0-9., -]+?)\.\s", src):
        names.update(n.strip() for n in listing.split(","))
    for listing in re.findall(r"--whisper-model\s+([a-z0-9.| -]+)\"", src):
        names.update(n.strip() for n in listing.split("|"))
    assert {"tiny", "small", "large-v3-turbo"} <= names, names  # the regexes still bite
    return names | set(MLX_REPO_FOR_MODEL)


_ADVERTISED = sorted(_advertised_model_names())


class TestEveryModelNameResolves:
    """The 4 Oct 2026 snap crash: ``-w small`` on faster-whisper fell through
    the table as the bare repo id ``small`` and the Hub answered 401."""

    @pytest.mark.parametrize("backend", ["mlx", "faster-whisper"])
    @pytest.mark.parametrize("model", _ADVERTISED)
    def test_resolves_to_a_measured_org_repo(self, model: str, backend: str):
        with patch("bristlenose.utils.hardware.detect_hardware"):
            with patch(
                "bristlenose.stages.s05_transcribe._resolve_backend",
                return_value=backend,
            ):
                repo = _resolve_repo_id(_settings(whisper_model=model))
        assert "/" in repo, f"{model!r} on {backend} fell through as {repo!r}"
        assert download_size_human(repo) is not None, f"no measured size for {repo}"

    @pytest.mark.parametrize("model", _ADVERTISED)
    def test_mlx_resolution_is_stage_5s(self, model: str):
        from bristlenose.stages.s05_transcribe import _mlx_model_name

        with patch("bristlenose.utils.hardware.detect_hardware"):
            with patch(
                "bristlenose.stages.s05_transcribe._resolve_backend", return_value="mlx"
            ):
                assert _resolve_repo_id(_settings(whisper_model=model)) == _mlx_model_name(
                    model
                )

    def test_faster_whisper_table_is_faster_whispers_own(self):
        utils = pytest.importorskip("faster_whisper.utils")
        assert _FASTER_WHISPER_REPO_FOR_MODEL == utils._MODELS

    def test_every_table_repo_has_a_size(self):
        repos = set(_FASTER_WHISPER_REPO_FOR_MODEL.values()) | set(MLX_REPO_FOR_MODEL.values())
        assert repos - set(_DOWNLOAD_MB) == set()

    def test_ct2_repos_probe_model_bin(self):
        for repo in _FASTER_WHISPER_REPO_FOR_MODEL.values():
            assert _heavy_blob_candidates(repo) == ("model.bin",), repo

    @pytest.mark.parametrize(
        ("mb", "human"),
        [(1614, "~1.6 GB"), (3091, "~3.1 GB"), (486, "~490 MB"), (78, "~78 MB")],
    )
    def test_size_formatting(self, mb: int, human: str):
        assert _format_mb(mb) == human

    def test_unmeasured_repo_has_no_size(self):
        assert download_size_human("custom/repo-name") is None


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

    def test_mlx_repo_cached_via_safetensors_only(self, monkeypatch, tmp_path):
        """Real mlx-community repos ship ``weights.safetensors``, not ``weights.npz``.

        Regression: probing only weights.npz reported "missing" on fully-cached
        machines, so every run printed the download banner + a no-op 0s fetch.
        """
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.side_effect = lambda repo_id, filename: (
            "/cache/weights.safetensors" if filename == "weights.safetensors" else None
        )
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert cache_state("mlx-community/whisper-large-v3-turbo") == "cached"

    def test_mlx_repo_cached_via_legacy_npz(self, monkeypatch, tmp_path):
        """Older mlx-community conversions ship ``weights.npz`` — still counts."""
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.side_effect = lambda repo_id, filename: (
            "/cache/weights.npz" if filename == "weights.npz" else None
        )
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert cache_state("mlx-community/whisper-large-v3-turbo") == "cached"

    def test_mlx_repo_missing_when_no_weights_file(self, monkeypatch, tmp_path):
        """Neither safetensors nor npz cached (e.g. config.json-only) → missing."""
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
        fake_hf = MagicMock()
        fake_hf.try_to_load_from_cache.return_value = None
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert cache_state("mlx-community/whisper-large-v3-turbo") == "missing"
        probed = {
            c.kwargs["filename"] for c in fake_hf.try_to_load_from_cache.call_args_list
        }
        assert probed == {"weights.safetensors", "weights.npz"}

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
        assert "(~1.6 GB)" in out  # turbo on MLX: 1614 MB
        assert "Downloading" in out
        assert "Resuming" not in out
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


# ---------------------------------------------------------------------------
# Progress-bar suppression (regression for 12 May 2026 leak: `Fetching N files:`
# and `Download complete: : 0.00B` lines escaping past existing suppression.)
# ---------------------------------------------------------------------------


class TestProgressBarSuppression:
    def test_env_vars_set_at_bristlenose_import_time(self):
        """After `import bristlenose`, the suppression env vars must be in os.environ.

        Both vars are read by their respective libraries at first-import time
        (huggingface_hub.constants captures HF_HUB_DISABLE_PROGRESS_BARS into a
        module constant; tqdm reads TQDM_DISABLE on each instantiation). If
        either is set later (e.g. inside pipeline.py), a preflight that imports
        huggingface_hub before pipeline loads will freeze HF_HUB_DISABLE_PROGRESS_BARS
        as None and the env var has no effect.
        """
        import os

        import bristlenose  # noqa: F401 — import is the point

        assert os.environ.get("TQDM_DISABLE") == "1"
        assert os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS") == "1"

    def test_hf_constant_is_true_after_full_preflight_chain(self):
        """After the import chain that triggered the original leak, the HF
        constant must read True.

        Sequence: bristlenose → doctor (imports huggingface_hub via
        `_check_whisper_model`) → pipeline → preflight_whisper. The original
        bug was that pipeline.py set the env vars too late — huggingface_hub
        had already been imported by the doctor preflight, freezing the
        constant as None.
        """
        import bristlenose  # noqa: F401
        from bristlenose.config import load_settings
        from bristlenose.doctor import run_preflight

        run_preflight(load_settings(), "run")

        from huggingface_hub.constants import HF_HUB_DISABLE_PROGRESS_BARS

        import bristlenose.pipeline  # noqa: F401

        assert HF_HUB_DISABLE_PROGRESS_BARS is True

    def test_hf_tqdm_instance_is_disabled_after_import_chain(self):
        """An hf_tqdm bar instantiated post-import-chain has `disable=True`.

        This is the direct check: even if env-var suppression failed silently
        (constant=False, but hf_tqdm decides on its own), the bar must still
        not print. Catches regressions where huggingface_hub.utils.tqdm
        changes its disable logic.
        """
        import bristlenose  # noqa: F401
        from bristlenose.config import load_settings
        from bristlenose.doctor import run_preflight

        run_preflight(load_settings(), "run")

        from huggingface_hub.utils import are_progress_bars_disabled
        from huggingface_hub.utils import tqdm as hf_tqdm

        assert are_progress_bars_disabled() is True
        bar = hf_tqdm(total=4, desc="Fetching 4 files")
        try:
            assert bar.disable is True, (
                "hf_tqdm bar should be disabled after bristlenose import + "
                "doctor preflight. If this fails, `Fetching N files:` and "
                "`Download complete: : 0.00B` lines will leak past "
                "suppression. See `bristlenose/__init__.py` env-var setup "
                "and `bristlenose/preflight/whisper.py` programmatic disable."
            )
        finally:
            bar.close()
