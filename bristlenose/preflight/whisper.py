"""Whisper-model preflight — banner + native HF Hub progress before stage 5.

Why this exists: the friendly-CTO call on 9 May 2026 showed that on a fresh
machine the very first transcription run sat silent for several minutes while
``mlx_whisper`` (or ``faster_whisper``) downloaded the ~1.5 GB Whisper weights
without any UI signal. The user thought Bristlenose had hung. This preflight
runs the same fetch *before* stage 5 starts, behind a framed banner that
explains what's happening and that Ctrl+C is safe.

Per ``docs/design-cli-just-works.md`` Debate 1 / Option B: we don't try to
re-render HF Hub's progress bar inside Rich. We stop the spinner, let HF Hub
print natively (tqdm to stderr), then restart the spinner with a ✓ done line.

Cache detection is deliberately filesystem-based:
- ``try_to_load_from_cache(repo_id, "config.json")`` — canonical "fully cached" probe
- ``blobs/*.incomplete`` scan — distinguishes "never started" from "partially done"

This is finding 21 in ``docs/private/reviews/cli-just-works.md``: HF Hub's
``snapshot_download`` already handles resume correctly; we just need to detect
the in-progress state so the banner says "Resuming download…" instead of
"Downloading…" (the difference is the difference between "this will take a
while" and "this might be done in seconds").
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from bristlenose.i18n import t
from bristlenose.preflight import PreflightAbortedError
from bristlenose.ui_kinds import MessageKind, cli_prefix

if TYPE_CHECKING:
    from rich.console import Console
    from rich.status import Status

    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

WHISPER_SIZE_HUMAN = "~1.5 GB"

# Hardcoded per finding 3 — calling ``model_info()`` to fetch the real size adds
# a network round-trip on a happy path that's already fast and removes Option B's
# offline-friendly property.

_MLX_REPO_FOR_MODEL: dict[str, str] = {
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3": "mlx-community/whisper-large-v3",
}

_FASTER_WHISPER_REPO_FOR_MODEL: dict[str, str] = {
    "large-v3-turbo": "Systran/faster-whisper-large-v3",
    "turbo": "Systran/faster-whisper-large-v3",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v2": "Systran/faster-whisper-large-v2",
}



# Back-compat alias — original three-classes-for-one-shape pattern was unified
# in the post-Slice-H clean-up (review log Finding 17). Existing call sites and
# tests can continue to import this name; new code should use
# ``PreflightAbortedError`` directly.
WhisperPreflightAbortedError = PreflightAbortedError


def _resolve_repo_id(settings: BristlenoseSettings) -> str:
    """Pick the HF repo for the active backend + model.

    Mirrors :func:`bristlenose.stages.s05_transcribe._mlx_model_name` for the
    MLX path; adds the Systran ``faster-whisper-*`` mapping for the CT2 path.
    """
    from bristlenose.stages.s05_transcribe import _resolve_backend
    from bristlenose.utils.hardware import detect_hardware

    hw = detect_hardware()
    backend = _resolve_backend(settings.whisper_backend, hw)
    mapping = (
        _MLX_REPO_FOR_MODEL if backend == "mlx" else _FASTER_WHISPER_REPO_FOR_MODEL
    )
    return mapping.get(settings.whisper_model, settings.whisper_model)


def _hf_cache_root() -> Path:
    """Resolve the active HF Hub cache root.

    Respects ``HF_HUB_CACHE`` > ``HF_HOME`` > ``~/.cache/huggingface``, matching
    huggingface_hub's own precedence.
    """
    if (cache := os.environ.get("HF_HUB_CACHE")):
        return Path(cache)
    if (home := os.environ.get("HF_HOME")):
        return Path(home) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _repo_cache_dir(repo_id: str) -> Path:
    safe = repo_id.replace("/", "--")
    return _hf_cache_root() / f"models--{safe}"


def _has_partial_blobs(repo_id: str) -> bool:
    """True if HF Hub left ``.incomplete`` blob files from an interrupted download."""
    blobs = _repo_cache_dir(repo_id) / "blobs"
    if not blobs.exists():
        return False
    return any(blobs.glob("*.incomplete"))


def _heavy_blob_for(repo_id: str) -> str:
    """Pick the "model is really here" probe filename for this backend's repo layout.

    Both backends ship ``config.json`` as a tiny first-downloaded file (<1 KB),
    so probing config.json alone reports "cached" for interrupted downloads
    where only the metadata landed. Probe the heavy payload file instead:
    - ct2 (``Systran/faster-whisper-*``): ``model.bin`` (~1.5 GB)
    - mlx (``mlx-community/whisper-*``): ``weights.npz``
    - Unknown layout: fall back to ``config.json`` (best we can do).
    """
    if repo_id.startswith("Systran/"):
        return "model.bin"
    if repo_id.startswith("mlx-community/"):
        return "weights.npz"
    return "config.json"


def _is_fully_cached(repo_id: str) -> bool:
    """True if the backend's heavy payload file is in cache.

    Probes a payload file, not ``config.json``, so a download interrupted after
    config.json but before the model weights is correctly reported as not
    cached (otherwise stage 5 hangs re-fetching with no banner).
    """
    from huggingface_hub import try_to_load_from_cache

    result = try_to_load_from_cache(
        repo_id=repo_id, filename=_heavy_blob_for(repo_id),
    )
    # try_to_load_from_cache returns: None (not cached) | _CACHED_NO_EXIST | str path
    return isinstance(result, str)


def cache_state(repo_id: str) -> str:
    """Return one of ``"cached"`` / ``"partial"`` / ``"missing"``."""
    if _is_fully_cached(repo_id) and not _has_partial_blobs(repo_id):
        return "cached"
    if _has_partial_blobs(repo_id):
        return "partial"
    return "missing"


def _print_banner(
    console: Console, repo_id: str, state: str
) -> None:

    verb = (
        t("preflight.whisper.verb_resuming")
        if state == "partial"
        else t("preflight.whisper.verb_downloading")
    )
    console.print()
    console.print(
        "  " + t("preflight.whisper.banner_intro", size=WHISPER_SIZE_HUMAN)
    )
    console.print("  " + t("preflight.whisper.reassurance"))
    console.print()
    console.print(
        "  " + t(
            "preflight.whisper.fetching",
            verb=verb, repo_id=f"[bold]{repo_id}[/bold]",
        )
    )
    console.print()


def preflight_whisper(
    *,
    settings: BristlenoseSettings,
    console: Console,
    status: Status | None,
    allow_fetch: bool,
) -> None:
    """Run the Whisper-model preflight.

    Behaviour:
    - **``BRISTLENOSE_SKIP_PREFLIGHT=1``**: explicit escape hatch, skip silently.
      Defence-in-depth for spoofed-TTY CI runners and the pytest suite
      (set in ``tests/conftest.py``).
    - **Fully cached**: silent, return immediately.
    - **Missing or partial**: print the framed banner; if ``allow_fetch`` is
      False raise :class:`WhisperPreflightAbortedError`; otherwise stop the Rich
      spinner, call ``snapshot_download`` (HF Hub prints natively), restart
      the spinner, print the ✓ done line.

    Callers gate on ``needs_transcription`` themselves (finding 39) — a folder
    of all-platform-transcripts should never trigger this code path.

    Raises:
        WhisperPreflightAbortedError: when ``--no-fetch`` is active and the model
            is not fully cached.
        PackageInstallError: when the download itself fails (propagated from
            :func:`bristlenose.utils.package_install.ensure_hf_model`).
    """
    if os.environ.get("BRISTLENOSE_SKIP_PREFLIGHT") == "1":
        return
    from bristlenose.utils.package_install import ensure_hf_model

    # Defence-in-depth against the env-var suppression in
    # `bristlenose/__init__.py`: when `bristlenose.doctor._check_whisper_model`
    # imports `huggingface_hub` (which it does during the doctor preflight),
    # `HF_HUB_DISABLE_PROGRESS_BARS` gets read into a module-level constant —
    # so if the env var is somehow unset by the time HF is first imported,
    # the programmatic call still suppresses `Fetching N files:` and the
    # trailing `Download complete: : 0.00B` summary line.
    try:
        from huggingface_hub.utils import disable_progress_bars
        disable_progress_bars()
    except ImportError:
        pass

    repo_id = _resolve_repo_id(settings)
    state = cache_state(repo_id)
    if state == "cached":
        logger.info("preflight_whisper: %s already cached", repo_id)
        return

    if not allow_fetch:
        raise WhisperPreflightAbortedError(
            t("preflight.whisper.aborted_no_fetch", repo_id=repo_id)
        )

    _print_banner(console, repo_id, state)

    # Option B: step aside, let HF Hub print natively.
    if status is not None:
        status.stop()
    t0 = time.perf_counter()
    try:
        ensure_hf_model(repo_id)
    finally:
        if status is not None:
            status.start()

    elapsed = time.perf_counter() - t0
    console.print(
        f"  {cli_prefix(MessageKind.SUCCESS)} "
        + t("preflight.whisper.ready")
        + f" [{elapsed:.0f}s]"
    )
    console.print()
