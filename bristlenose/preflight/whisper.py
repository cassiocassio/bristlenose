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

# Short model names to the CTranslate2 repos faster-whisper itself downloads —
# a verbatim copy of ``faster_whisper.utils._MODELS`` (faster-whisper 1.2.1).
# Stage 5 hands the bare name to ``WhisperModel``, which resolves it through
# that table, so the preflight must resolve it the same way or it fetches a
# repo stage 5 never opens. Copied rather than imported because importing
# ``faster_whisper`` pulls in ctranslate2 and PyAV on every doctor run, and the
# name is private. ``tests/test_preflight_whisper.py`` fails on any drift.
_FASTER_WHISPER_REPO_FOR_MODEL: dict[str, str] = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "tiny": "Systran/faster-whisper-tiny",
    "base.en": "Systran/faster-whisper-base.en",
    "base": "Systran/faster-whisper-base",
    "small.en": "Systran/faster-whisper-small.en",
    "small": "Systran/faster-whisper-small",
    "medium.en": "Systran/faster-whisper-medium.en",
    "medium": "Systran/faster-whisper-medium",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "distil-large-v3.5": "distil-whisper/distil-large-v3.5-ct2",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

# Download size per repo, in MB: the sum of every file ``snapshot_download``
# fetches, measured from the Hub API (``/api/models/<repo>?blobs=true``) on
# 4 Oct 2026. Hardcoded per finding 3 — calling ``model_info()`` at run time
# adds a network round-trip to a happy path that's already fast and removes
# Option B's offline-friendly property. A repo missing here gets no size
# rather than a wrong one.
_DOWNLOAD_MB: dict[str, int] = {
    "Systran/faster-distil-whisper-large-v2": 1516,
    "Systran/faster-distil-whisper-large-v3": 1516,
    "Systran/faster-distil-whisper-medium.en": 792,
    "Systran/faster-distil-whisper-small.en": 336,
    "Systran/faster-whisper-base": 148,
    "Systran/faster-whisper-base.en": 148,
    "Systran/faster-whisper-large-v1": 3090,
    "Systran/faster-whisper-large-v2": 3090,
    "Systran/faster-whisper-large-v3": 3091,
    "Systran/faster-whisper-medium": 1531,
    "Systran/faster-whisper-medium.en": 1530,
    "Systran/faster-whisper-small": 486,
    "Systran/faster-whisper-small.en": 486,
    "Systran/faster-whisper-tiny": 78,
    "Systran/faster-whisper-tiny.en": 78,
    "distil-whisper/distil-large-v3.5-ct2": 1516,
    "mobiuslabsgmbh/faster-whisper-large-v3-turbo": 1622,
    "mlx-community/whisper-base-mlx": 144,
    "mlx-community/whisper-base.en-mlx": 144,
    "mlx-community/whisper-large-v2-mlx": 3083,
    "mlx-community/whisper-large-v3-mlx": 3084,
    "mlx-community/whisper-large-v3-turbo": 1614,
    "mlx-community/whisper-medium-mlx": 1525,
    "mlx-community/whisper-medium.en-mlx": 1525,
    "mlx-community/whisper-small-mlx": 481,
    "mlx-community/whisper-small.en-mlx": 481,
    "mlx-community/whisper-tiny-mlx": 74,
    "mlx-community/whisper-tiny.en-mlx": 74,
}


def _format_mb(mb: int) -> str:
    """``1614`` → ``"~1.6 GB"``; ``486`` → ``"~490 MB"``; ``78`` → ``"~78 MB"``."""
    if mb >= 1000:
        return f"~{mb / 1000:.1f} GB"
    return f"~{int(float(f'{mb:.2g}'))} MB"


def download_size_human(repo_id: str) -> str | None:
    """Human download size for ``repo_id``, or ``None`` when we never measured it."""
    mb = _DOWNLOAD_MB.get(repo_id)
    return _format_mb(mb) if mb is not None else None


# The default model's size (``large-v3-turbo``: 1.61 GB on MLX, 1.62 GB on
# faster-whisper), for help text written before any settings are known.
WHISPER_SIZE_HUMAN = _format_mb(
    _DOWNLOAD_MB[_FASTER_WHISPER_REPO_FOR_MODEL["large-v3-turbo"]]
)


# Back-compat alias — original three-classes-for-one-shape pattern was unified
# in the post-Slice-H clean-up (review log Finding 17). Existing call sites and
# tests can continue to import this name; new code should use
# ``PreflightAbortedError`` directly.
WhisperPreflightAbortedError = PreflightAbortedError


def _resolve_repo_id(settings: BristlenoseSettings) -> str:
    """Pick the HF repo for the active backend + model.

    Resolves exactly as stage 5 will: the MLX path through
    :func:`bristlenose.stages.s05_transcribe._mlx_model_name`, the CT2 path
    through faster-whisper's own name table. A name in neither passes through
    as a repo id (``--whisper-model org/repo``).
    """
    from bristlenose.stages.s05_transcribe import _mlx_model_name, _resolve_backend
    from bristlenose.utils.hardware import detect_hardware

    hw = detect_hardware()
    backend = _resolve_backend(settings.whisper_backend, hw)
    if backend == "mlx":
        return _mlx_model_name(settings.whisper_model)
    return _FASTER_WHISPER_REPO_FOR_MODEL.get(settings.whisper_model, settings.whisper_model)


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


def _heavy_blob_candidates(repo_id: str) -> tuple[str, ...]:
    """Pick the "model is really here" probe filenames for this backend's repo layout.

    Both backends ship ``config.json`` as a tiny first-downloaded file (<1 KB),
    so probing config.json alone reports "cached" for interrupted downloads
    where only the metadata landed. Probe the heavy payload file instead:
    - ct2 (``Systran/faster-whisper-*`` and the other repos faster-whisper
      names, e.g. ``mobiuslabsgmbh/faster-whisper-large-v3-turbo``): ``model.bin``
    - mlx (``mlx-community/whisper-*``): ``weights.safetensors`` (current
      conversions) or ``weights.npz`` (older conversions) — either counts.
      Probing ``weights.npz`` alone reported "missing" on fully-cached
      machines (the turbo repo ships safetensors only), so every run printed
      the download banner followed by a no-op 0s fetch.
    - Unknown layout: fall back to ``config.json`` (best we can do).
    """
    if repo_id.startswith("Systran/") or repo_id in _FASTER_WHISPER_REPO_FOR_MODEL.values():
        return ("model.bin",)
    if repo_id.startswith("mlx-community/"):
        return ("weights.safetensors", "weights.npz")
    return ("config.json",)


def _is_fully_cached(repo_id: str) -> bool:
    """True if any of the backend's heavy payload files is in cache.

    Probes payload files, not ``config.json``, so a download interrupted after
    config.json but before the model weights is correctly reported as not
    cached (otherwise stage 5 hangs re-fetching with no banner).
    """
    from huggingface_hub import try_to_load_from_cache

    for filename in _heavy_blob_candidates(repo_id):
        result = try_to_load_from_cache(repo_id=repo_id, filename=filename)
        # try_to_load_from_cache returns: None (not cached) | _CACHED_NO_EXIST | str path
        if isinstance(result, str):
            return True
    return False


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
    # An unmeasured repo (a custom ``org/repo``) names itself instead of
    # guessing a size.
    size = download_size_human(repo_id) or repo_id
    console.print("  " + t("preflight.whisper.banner_intro", size=size))
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
