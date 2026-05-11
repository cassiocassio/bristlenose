"""Unit tests for bristlenose.utils.package_install."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.utils.package_install import (
    FrozenSidecarError,
    PackageInstallError,
    ensure_hf_model,
    ensure_spacy_model,
)

# ---------------------------------------------------------------------------
# ensure_spacy_model
# ---------------------------------------------------------------------------


class TestEnsureSpacyModel:
    def test_already_installed_short_circuits(self, monkeypatch):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        fake_spacy = MagicMock()
        fake_spacy.load.return_value = MagicMock()
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch("bristlenose.utils.package_install.subprocess.run") as run:
                ensure_spacy_model("en_core_web_sm")
        run.assert_not_called()
        fake_spacy.load.assert_called_once_with("en_core_web_sm")

    def test_fresh_install_invokes_spacy_download(self, monkeypatch):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("no model")
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch("bristlenose.utils.package_install.subprocess.run") as run:
                ensure_spacy_model("en_core_web_sm")
        run.assert_called_once_with(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
            check=True,
        )

    def test_download_failure_raises(self, monkeypatch):
        monkeypatch.delenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", raising=False)
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("no model")
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch("bristlenose.utils.package_install.subprocess.run") as run:
                run.side_effect = subprocess.CalledProcessError(1, "spacy")
                with pytest.raises(PackageInstallError):
                    ensure_spacy_model("en_core_web_sm")

    def test_frozen_sidecar_blocks_download(self, monkeypatch):
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        fake_spacy = MagicMock()
        fake_spacy.load.side_effect = OSError("no model")
        with patch.dict(sys.modules, {"spacy": fake_spacy}):
            with patch("bristlenose.utils.package_install.subprocess.run") as run:
                with pytest.raises(FrozenSidecarError):
                    ensure_spacy_model("en_core_web_sm")
        run.assert_not_called()


# ---------------------------------------------------------------------------
# ensure_hf_model
# ---------------------------------------------------------------------------


class TestEnsureHfModel:
    def test_returns_snapshot_path(self, monkeypatch):
        fake_hf = MagicMock()
        fake_hf.snapshot_download.return_value = "/cache/models/openai-whisper-large-v3-turbo"
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            path = ensure_hf_model("openai/whisper-large-v3-turbo")
        assert path == "/cache/models/openai-whisper-large-v3-turbo"
        fake_hf.snapshot_download.assert_called_once_with("openai/whisper-large-v3-turbo")

    def test_keyboard_interrupt_propagates(self):
        # User Ctrl+C during download must propagate so the caller can exit cleanly
        # and the HF cache keeps its .incomplete partials for the next resume.
        fake_hf = MagicMock()
        fake_hf.snapshot_download.side_effect = KeyboardInterrupt
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            with pytest.raises(KeyboardInterrupt):
                ensure_hf_model("openai/whisper-large-v3-turbo")

    def test_other_failure_wraps_in_package_install_error(self):
        fake_hf = MagicMock()
        fake_hf.snapshot_download.side_effect = RuntimeError("connection reset")
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            with pytest.raises(PackageInstallError, match="connection reset"):
                ensure_hf_model("openai/whisper-large-v3-turbo")

    def test_safe_in_frozen_sidecar(self, monkeypatch):
        # HF cache lives in user-writable HF home, so the bundle guard does NOT apply.
        monkeypatch.setenv("_BRISTLENOSE_HOSTED_BY_DESKTOP", "1")
        fake_hf = MagicMock()
        fake_hf.snapshot_download.return_value = "/user/hf-cache/whisper"
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert ensure_hf_model("openai/whisper-large-v3-turbo") == "/user/hf-cache/whisper"
