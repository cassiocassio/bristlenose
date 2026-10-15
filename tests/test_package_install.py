"""Unit tests for bristlenose.utils.package_install."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch

import pytest

from bristlenose.utils.package_install import (
    FrozenSidecarError,
    PackageInstallError,
    _abort_hf_transfers,
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
        # User Ctrl+C during download must propagate so the caller can exit cleanly.
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
    effect for 50 s — the whole file finished first. The interrupt itself
    lands promptly; what holds it is ``hf_thread_map``'s ``with
    ThreadPoolExecutor``, whose exit waits for the worker still downloading.
    huggingface_hub's own abort sits in that worker, which never sees the
    interrupt. The fake below has the same shape: worker threads behind an
    executor, a metadata phase before any hf_xet session exists (an abort then
    has nothing to stop), and a real SIGINT aimed at the main thread."""

    def _fake(self, *, metadata_s: float):
        from concurrent.futures import ThreadPoolExecutor

        session = threading.Event()  # an hf_xet session exists
        stopped = threading.Event()  # the transfer was aborted

        def snapshot_download(repo_id, **kwargs):
            def download():
                time.sleep(metadata_s)  # repo info, HEAD requests: no session yet
                session.set()
                stopped.wait(5.0)  # the transfer, until finished or aborted

            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(download).result()
            return "/cache/snapshot"

        def abort() -> bool:
            if session.is_set():  # like abort_xet_session: no session, no-op
                stopped.set()
            return True  # the call itself succeeded

        fake_hf = MagicMock()
        fake_hf.snapshot_download.side_effect = snapshot_download
        return fake_hf, abort, stopped

    def _interrupt_after(self, seconds: float) -> threading.Timer:
        main = threading.main_thread().ident
        timer = threading.Timer(seconds, signal.pthread_kill, (main, signal.SIGINT))
        timer.start()
        return timer

    @pytest.mark.parametrize("metadata_s", [0.0, 0.6], ids=["mid-transfer", "before-transfer"])
    def test_ctrl_c_stops_the_download_promptly(self, metadata_s: float):
        fake_hf, abort, stopped = self._fake(metadata_s=metadata_s)
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}), \
                patch("bristlenose.utils.package_install._abort_hf_transfers", side_effect=abort):
            t0 = time.monotonic()
            self._interrupt_after(0.2)
            with pytest.raises(KeyboardInterrupt):
                ensure_hf_model("mlx-community/whisper-large-v3-turbo")
            elapsed = time.monotonic() - t0
        assert stopped.is_set(), "Ctrl+C returned while the transfer was still running"
        assert elapsed < 2.5, f"Ctrl+C took {elapsed:.1f}s to land"

    def test_a_finished_download_returns_its_path(self):
        fake_hf, _abort, _stopped = self._fake(metadata_s=0.0)
        _stopped.set()
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            assert ensure_hf_model("x/y") == "/cache/snapshot"

    def test_tqdm_class_reaches_snapshot_download(self):
        """The Whisper preflight closes the bars through this class; dropped,
        they redraw over the run after it."""
        fake_hf = MagicMock()
        fake_hf.snapshot_download.return_value = "/p"
        bar_class = type("Bar", (), {})
        with patch.dict(sys.modules, {"huggingface_hub": fake_hf}):
            ensure_hf_model("x/y", tqdm_class=bar_class)
        fake_hf.snapshot_download.assert_called_once_with("x/y", tqdm_class=bar_class)


class TestAbortHfTransfers:
    def _xet_module(self, **attrs) -> types.ModuleType:
        module = types.ModuleType("huggingface_hub.utils._xet")
        module.__dict__.update(attrs)
        return module

    def test_calls_huggingface_hubs_abort(self):
        abort = MagicMock()
        with patch.dict(
            sys.modules, {"huggingface_hub.utils._xet": self._xet_module(abort_xet_session=abort)}
        ):
            assert _abort_hf_transfers() is True
        abort.assert_called_once_with()

    def test_a_renamed_abort_does_not_turn_ctrl_c_into_a_crash(self, caplog):
        """If an upgrade keeps the module and renames the function, the
        AttributeError must not replace the user's Ctrl+C (a cancel would read
        as a failed run)."""
        with patch.dict(sys.modules, {"huggingface_hub.utils._xet": self._xet_module()}), \
                caplog.at_level("WARNING", logger="bristlenose.utils.package_install"):
            assert _abort_hf_transfers() is False
        assert "could not stop" in caplog.text


def test_huggingface_hub_still_exposes_the_abort_we_call():
    """``_abort_hf_transfers`` calls a private huggingface_hub function. If an
    upgrade moves it, Ctrl+C silently goes back to waiting for the whole file."""
    from huggingface_hub.utils._xet import abort_xet_session

    assert callable(abort_xet_session)
