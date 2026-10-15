"""Install helpers for runtime-fetched spaCy models and HF model weights.

Two helpers, one per install verb. Each install command has its own resume /
error / target-dir semantics that don't reduce cleanly to a shared interface.

The spaCy helper is CLI-only: when running inside the desktop sidecar bundle,
:func:`ensure_spacy_model` raises :class:`FrozenSidecarError` because PyInstaller's
read-only ``site-packages`` cannot accept new installs. The desktop sidecar bundles
spaCy at build time instead. :func:`ensure_hf_model` is safe in the bundle because
HF Hub writes into the user-writable cache directory.

(An ``ensure_wheel`` pip-install helper used to live here; deleted in the post-Slice-H
clean-up pass because no caller existed and the "uv migration is one-line" argument
was speculative — the migration touches whichever function exists when it lands.)
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
import threading
from typing import Any

logger = logging.getLogger(__name__)


class PackageInstallError(RuntimeError):
    """Raised when an install command fails (network, permissions, pip resolution)."""


class FrozenSidecarError(PackageInstallError):
    """Raised when an install is attempted from inside the read-only desktop sidecar."""


def _is_frozen_sidecar() -> bool:
    # PyInstaller sets ``sys.frozen``; the desktop host also sets an explicit sentinel
    # so a non-PyInstaller build (or a Nuitka swap) keeps the guard.
    return bool(getattr(sys, "frozen", False)) or os.environ.get(
        "_BRISTLENOSE_HOSTED_BY_DESKTOP"
    ) == "1"


def ensure_spacy_model(model_name: str) -> None:
    """Ensure a spaCy model is loadable; download via ``python -m spacy download`` if not.

    Idempotent: probes ``spacy.load(model_name)`` first and returns immediately on
    success. Only invokes the downloader on :class:`OSError` (spaCy's "model not
    installed" signal). The downloader handles resume via pip's wheel cache.

    Raises:
        FrozenSidecarError: when called from inside the desktop sidecar bundle.
            Desktop ships the model in the PyInstaller datas list.
        PackageInstallError: when ``spacy download`` exits non-zero.
    """
    import spacy

    try:
        spacy.load(model_name)
        return
    except OSError:
        pass

    from bristlenose.doctor_fixes import detect_install_method

    if detect_install_method() in ("snap", "rpm"):
        # Read-only prefix: pip would download all 400 MB and then fail writing
        # it (EROFS on the snap's squashfs, EACCES in the RPM's root-owned venv).
        # Stage 7 fetches into the user cache on these installs instead
        # (`s07_pii_removal.fetch_spacy_model`), so this is never its route.
        raise PackageInstallError(
            f"cannot install spaCy model {model_name!r} into this read-only "
            "package; it is fetched into the user's model cache instead"
        )

    if _is_frozen_sidecar():
        if sys.platform == "win32":
            # The Windows installer build cannot download a model into itself, and
            # the build does not carry one (docs/design-winget.md, PII in v1).
            raise FrozenSidecarError(
                "PII redaction is not available in the Windows installer build yet. "
                "To use --redact-pii, install Bristlenose with uv instead "
                "(see INSTALL.md, Windows)."
            )
        raise FrozenSidecarError(
            f"spaCy model {model_name!r} is missing from the desktop sidecar bundle; "
            "add it to the PyInstaller datas list at build time."
        )

    logger.info("ensure_spacy_model: downloading %s", model_name)
    try:
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise PackageInstallError(
            f"spacy download {model_name!r} failed (exit {exc.returncode})"
        ) from exc


def ensure_hf_model(repo_id: str, *, tqdm_class: type | None = None) -> str:
    """Ensure a Hugging Face model repo is present in the local cache; fetch if not.

    Idempotent, and safe to interrupt: Ctrl+C stops an hf_xet transfer within
    about 2 s and hf_xet removes its partial file (measured 15 Oct 2026). A
    plain-HTTP download (no hf_xet) stops at its next chunk instead, through
    the bar class, and its partial file is gone afterwards too (measured). It does not resume — through hf_xet (huggingface_hub 1.x) a
    re-run downloads the file again from the start, measured 14 Oct 2026. Safe
    inside the desktop sidecar — the cache lives under the user's HF home, not
    site-packages.

    ``tqdm_class`` is handed to ``snapshot_download`` for every progress bar it
    draws (the Whisper preflight passes one that it can close afterwards).

    Returns:
        Absolute path to the snapshot directory in the local cache.

    Raises:
        PackageInstallError: when the download fails for any reason except a
            user-initiated Ctrl+C (``KeyboardInterrupt`` propagates unchanged so
            the caller can exit cleanly).
    """
    from huggingface_hub import snapshot_download

    logger.info("ensure_hf_model: snapshot_download %s", repo_id)
    paths: list[str] = []
    errors: list[BaseException] = []
    finished = threading.Event()
    cancelled = threading.Event()
    bar_class = _cancellable_bar_class(tqdm_class, cancelled)

    def fetch() -> None:
        try:
            if bar_class is None:
                paths.append(snapshot_download(repo_id))
            else:
                paths.append(snapshot_download(repo_id, tqdm_class=bar_class))
        except BaseException as exc:  # handed back to the main thread below
            errors.append(exc)
        finally:
            finished.set()

    # Called directly, one Ctrl+C did nothing until every file had finished
    # (50 s on a 1.6 GB model, measured 14 Oct 2026). The interrupt lands, but
    # ``snapshot_download``'s ``with ThreadPoolExecutor`` waits on exit for the
    # worker still downloading, and huggingface_hub's own abort sits in that
    # worker, which never sees the interrupt. So the fetch runs on its own
    # thread, and on Ctrl+C this thread does the aborting — on every slice
    # until the download has stopped, because an abort sent before the hf_xet
    # session exists (repo info, HEAD requests) stops nothing.
    #
    # A plain-HTTP download (no hf_xet) has no abort at all. It does call the
    # bar's ``update()`` on every chunk, so ``cancelled`` makes the bar class
    # raise there, and each download thread stops at its next chunk.
    #
    # ``finished``, not ``is_alive()``: once a Ctrl+C has interrupted a
    # ``join``, CPython 3.12 can report the thread stopped while it still runs.
    worker = threading.Thread(target=fetch, name="hf-model-fetch", daemon=True)
    worker.start()
    try:
        finished.wait()
    except KeyboardInterrupt:
        cancelled.set()
        can_abort = True
        while not finished.wait(0.2):
            if can_abort:
                can_abort = _abort_hf_transfers()
        raise

    if errors:
        error = errors[0]
        if isinstance(error, Exception):
            raise PackageInstallError(
                f"huggingface_hub snapshot_download {repo_id!r} failed: {error}"
            ) from error
        raise error  # KeyboardInterrupt, SystemExit: unchanged
    return paths[0]


class _DownloadCancelled(BaseException):
    """Raised from a progress bar's ``update()`` to stop a download thread.

    A ``BaseException`` so that no ``except Exception`` on the way out — a
    retry wrapper, a cleanup handler — can swallow it and carry on downloading.
    """


def _cancellable_bar_class(base: type | None, cancelled: threading.Event) -> type | None:
    """``base`` (or huggingface_hub's own bar), raising once ``cancelled`` is set.

    Subclassing keeps everything the bar class decides — HF's TTY detection and
    its global switches, the preflight's bar closing. Returns ``base`` unchanged
    if HF's bar class cannot be imported, which loses only the cancel.
    """
    if base is None:
        try:
            base = importlib.import_module("huggingface_hub.utils.tqdm").tqdm
        except (ImportError, AttributeError):
            return None

    class _CancellableBar(base):  # type: ignore[misc, valid-type]
        def update(self, n: float | None = 1) -> bool | None:
            if cancelled.is_set() and _on_python_worker_thread():
                raise _DownloadCancelled
            return super().update(n)  # type: ignore[no-any-return]

    return _CancellableBar


# Python's stand-in for a thread it did not start. hf_xet calls the progress
# callback from its own Rust threads, and an exception raised there is printed
# as a traceback rather than stopping anything (measured 15 Oct 2026: 29 of 39
# updates on the hf_xet path, none on plain HTTP). hf_xet has its own abort, so
# the bar only raises on the download threads Python started. If the private
# name ever goes, this degrades to that stray traceback, never to a hang.
_FOREIGN_THREAD = getattr(threading, "_DummyThread", ())


def _on_python_worker_thread() -> bool:
    thread = threading.current_thread()
    return thread is not threading.main_thread() and not isinstance(thread, _FOREIGN_THREAD)


def _abort_hf_transfers() -> bool:
    """Stop huggingface_hub's in-flight hf_xet downloads.

    The same call huggingface_hub makes when a ``KeyboardInterrupt`` reaches
    the thread doing the download, which in ``snapshot_download`` it never
    does. A private module, so ``tests/test_package_install.py`` pins it: if an
    upgrade moves it, Ctrl+C goes back to waiting for the whole file.

    Returns False when the abort itself failed, so the caller stops retrying.
    """
    try:
        xet: Any = importlib.import_module("huggingface_hub.utils._xet")
        xet.abort_xet_session()
    except Exception as exc:  # never let the abort replace the user's Ctrl+C
        logger.warning("ensure_hf_model: could not stop the download: %s", exc)
        return False
    return True
