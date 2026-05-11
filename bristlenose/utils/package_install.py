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

import logging
import os
import subprocess
import sys

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

    if _is_frozen_sidecar():
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


def ensure_hf_model(repo_id: str) -> str:
    """Ensure a Hugging Face model repo is present in the local cache; fetch if not.

    Idempotent and resumable: ``huggingface_hub.snapshot_download`` writes
    ``.incomplete`` files during download and resumes from the last byte on a
    subsequent run after Ctrl+C or a dropped connection. Safe inside the desktop
    sidecar — the cache lives under the user's HF home, not site-packages.

    Returns:
        Absolute path to the snapshot directory in the local cache.

    Raises:
        PackageInstallError: when the download fails for any reason except a
            user-initiated Ctrl+C (``KeyboardInterrupt`` propagates unchanged so
            the caller can keep the partial cache and exit cleanly).
    """
    from huggingface_hub import snapshot_download

    logger.info("ensure_hf_model: snapshot_download %s", repo_id)
    try:
        return snapshot_download(repo_id)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        raise PackageInstallError(
            f"huggingface_hub snapshot_download {repo_id!r} failed: {exc}"
        ) from exc
