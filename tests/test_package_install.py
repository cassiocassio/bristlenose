"""Unit tests for bristlenose.utils.package_install."""

from __future__ import annotations

import subprocess
import sys
import threading
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


@pytest.mark.parametrize("method", ["snap", "rpm"])
def test_ensure_spacy_model_refuses_on_a_read_only_package(method: str) -> None:
    """The snap and the RPM install into a read-only prefix. Reproduced on
    0.36.0: `spacy download` there pulled all 400 MB, then died with EROFS
    (snap) or a permission error (RPM). Refuse before the download; stage 7
    takes the user-cache route on these installs instead."""
    fake_spacy = MagicMock()
    fake_spacy.load.side_effect = OSError("[E050] Can't find model")
    with patch.dict(sys.modules, {"spacy": fake_spacy}), \
            patch("bristlenose.doctor_fixes.detect_install_method", return_value=method), \
            patch("bristlenose.utils.package_install.subprocess.run") as run:
        with pytest.raises(PackageInstallError, match="read-only"):
            ensure_spacy_model("en_core_web_lg")
    run.assert_not_called()


class TestEnsureHfModelCtrlC:
    """Measured 14 Oct 2026: one Ctrl+C during a 1.6 GB Whisper download had no
    effect for 50 s — the whole file finished first. ``snapshot_download``
    downloads on worker threads and parks the main thread in a wait with no
    timeout, so the interrupt cannot land until every file is done, and
    huggingface_hub's own abort sits in the worker, which never sees it."""

    def _fake_hf(self, stop: threading.Event) -> MagicMock:
        def snapshot_download(repo_id, **kwargs):
            done = threading.Event()

            def download():
                stop.wait(5.0)  # the transfer, until finished or aborted
                done.set()

            threading.Thread(target=download, daemon=True).start()
            done.wait()  # like hf_thread_map: no timeout
            return "/cache/snapshot"

        fake_hf = MagicMock()
        fake_hf.snapshot_download.side_effect = snapshot_download
        return fake_hf

    def test_ctrl_c_stops_the_download_promptly(self):
        import _thread
        import time

        stop = threading.Event()
        timer = threading.Timer(0.3, _thread.interrupt_main)
        with patch.dict(sys.modules, {"huggingface_hub": self._fake_hf(stop)}), \
                patch(
                    "bristlenose.utils.package_install._abort_hf_transfers",
                    side_effect=stop.set,
                ) as abort:
            t0 = time.monotonic()
            timer.start()
            with pytest.raises(KeyboardInterrupt):
                ensure_hf_model("mlx-community/whisper-large-v3-turbo")
            elapsed = time.monotonic() - t0
        abort.assert_called_once()
        assert elapsed < 2.0, f"Ctrl+C took {elapsed:.1f}s to land"

    def test_a_finished_download_returns_its_path(self):
        stop = threading.Event()
        stop.set()
        with patch.dict(sys.modules, {"huggingface_hub": self._fake_hf(stop)}):
            assert ensure_hf_model("x/y") == "/cache/snapshot"


def test_huggingface_hub_still_exposes_the_abort_we_call():
    """``_abort_hf_transfers`` calls a private huggingface_hub function. If an
    upgrade moves it, Ctrl+C silently goes back to waiting for the whole file."""
    from huggingface_hub.utils._xet import abort_xet_session

    assert callable(abort_xet_session)
