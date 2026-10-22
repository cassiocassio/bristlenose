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
HF's bars are off everywhere else in the process (``bristlenose/__init__.py``),
so :func:`_native_download_progress` turns them on for this one call only.

Cache detection is deliberately filesystem-based:
- ``try_to_load_from_cache(repo_id, "config.json")`` — canonical "fully cached" probe
- ``blobs/*.incomplete`` scan — distinguishes "never started" from "partially done"

Finding 21 in the cli-just-works review assumed ``snapshot_download`` resumes
an interrupted download, so the banner said "Resuming download…". Measured 14
Oct 2026, it does not: huggingface_hub 1.x fetches through hf_xet (a hard
dependency on every architecture we ship), and a re-run after Ctrl+C downloads
the whole file again into a fresh ``.incomplete``. The partial state therefore
says "Restarting download…", and the banner promises only that Ctrl+C is safe.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


def _active_backend(settings: BristlenoseSettings) -> str:
    """``"mlx"`` or ``"faster-whisper"`` — the backend stage 5 will pick."""
    from bristlenose.stages.s05_transcribe import _resolve_backend
    from bristlenose.utils.hardware import detect_hardware

    return _resolve_backend(settings.whisper_backend, detect_hardware())


def _model_table(backend: str) -> dict[str, str]:
    from bristlenose.stages.s05_transcribe import MLX_REPO_FOR_MODEL

    return MLX_REPO_FOR_MODEL if backend == "mlx" else _FASTER_WHISPER_REPO_FOR_MODEL


def _resolve_repo_id(settings: BristlenoseSettings) -> str:
    """Pick the HF repo for the active backend + model.

    Resolves exactly as stage 5 will: the MLX path through
    :func:`bristlenose.stages.s05_transcribe._mlx_model_name` (whose table this
    reads), the CT2 path through faster-whisper's own name table. A name in
    neither passes through as a repo id (``--whisper-model org/repo``).
    """
    name = settings.whisper_model
    return _model_table(_active_backend(settings)).get(name, name)


def unknown_model_message(settings: BristlenoseSettings) -> str | None:
    """The refusal for a model name the active backend does not know, else ``None``.

    A bare name outside the table is sent to the Hub as a repo id and comes
    back as a 401 "Repository Not Found" from deep inside ``snapshot_download``
    — the answer ``-w smal`` used to get. Still allowed through: anything with
    a ``/`` (an ``org/repo`` id, or a path), an existing directory (both
    backends load a local model dir), and a name the desktop app bundles under
    ``BRISTLENOSE_WHISPER_MODEL_DIR``.
    """
    import difflib

    name = settings.whisper_model
    backend = _active_backend(settings)
    table = _model_table(backend)
    if name in table or "/" in name or os.sep in name or os.path.isdir(name):
        return None
    bundled = os.environ.get("BRISTLENOSE_WHISPER_MODEL_DIR")
    if bundled and os.path.isdir(os.path.join(bundled, name)):
        return None
    parts = [t("preflight.whisper.unknown_model", model=name)]
    if close := difflib.get_close_matches(name, list(table), n=1):
        parts.append(t("preflight.whisper.did_you_mean", suggestion=close[0]))
    parts.append(t("preflight.whisper.choose_model", models=", ".join(table)))
    return " ".join(parts)


def _hf_cache_root() -> Path:
    """Resolve the active HF Hub cache root, exactly as huggingface_hub does.

    ``HF_HUB_CACHE`` > ``HUGGINGFACE_HUB_CACHE`` (legacy) > ``HF_HOME``/hub >
    ``$XDG_CACHE_HOME``/huggingface/hub > ``~/.cache/huggingface/hub``, with
    ``~`` and ``$VARS`` expanded (``huggingface_hub/constants.py``). Read from
    the environment at call time rather than from ``huggingface_hub.constants``,
    which freezes at import. Missing ``XDG_CACHE_HOME`` and the expansion until
    15 Oct 2026 put the banner's path and the partial-download check in a
    different directory from the one HF downloads into.
    ``test_cache_root_is_huggingface_hubs_own`` asks the library itself.
    """
    def expand(value: str) -> str:
        return os.path.expandvars(os.path.expanduser(value))

    home = expand(os.environ.get(
        "HF_HOME",
        os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "huggingface"),
    ))
    legacy = os.environ.get("HUGGINGFACE_HUB_CACHE", os.path.join(home, "hub"))
    return Path(expand(os.environ.get("HF_HUB_CACHE", legacy)))


def _repo_cache_dir(repo_id: str) -> Path:
    safe = repo_id.replace("/", "--")
    return _hf_cache_root() / f"models--{safe}"


def _has_partial_blobs(repo_id: str) -> bool:
    """True if HF Hub left ``.incomplete`` blob files from an interrupted download.

    A partial whose blob has since finished does not count. With hf_xet a
    re-run does not pick up the old partial: it downloads into a new
    ``<sha>.<random>.incomplete``, finishes as ``<sha>``, and leaves the first
    one behind for good (measured 14 Oct 2026, huggingface_hub 1.33). Counting
    it put the download banner on every later run.
    """
    blobs = _repo_cache_dir(repo_id) / "blobs"
    if not blobs.exists():
        return False
    return any(
        not (blobs / partial.name.split(".", 1)[0]).exists()
        for partial in blobs.glob("*.incomplete")
    )


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


# Above this, the banner also says where the download lands — the "> 500 MB"
# row of the fetch-size table in ``docs/design-cli-just-works.md``. A repo we
# never measured (a custom ``org/repo``) gets the line too: its size is unknown,
# not small.
_CACHE_PATH_CALLOUT_MB = 500


def _cache_root_display() -> str:
    """The HF cache root as a researcher would type it: ``~/.cache/huggingface/hub``."""
    root = _hf_cache_root()
    try:
        return os.path.join("~", root.relative_to(Path.home()))
    except ValueError:
        return str(root)


def _stderr_is_tty() -> bool:
    """True when stderr is a terminal — where tqdm draws, and the only place a bar reads."""
    try:
        return sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


@contextmanager
def _native_download_progress() -> Iterator[type | None]:
    """Let Hugging Face draw its own download bars for the duration of the block.

    Yields the ``tqdm_class`` to hand to ``snapshot_download``, or ``None`` when
    the bars should stay off.

    ``bristlenose/__init__.py`` sets ``HF_HUB_DISABLE_PROGRESS_BARS=1`` so that
    stray ``Fetching N files:`` bars stay out of every other code path, and
    huggingface_hub freezes that into ``huggingface_hub.utils.tqdm`` at import.
    The frozen value outranks ``enable_progress_bars()``, which refuses with a
    warning and leaves the bars off — that is how a ~1.6 GB first download went
    silent for minutes. So the block lifts the frozen value, enables, and puts
    both back in ``finally``.

    ``snapshot_download`` leaves its two byte bars open, with the cursor parked
    on the first, and tqdm redraws open bars when they are collected — at exit,
    after the whole run. So the block also closes every bar it opened before
    the caller restarts its spinner: a bar redrawn under a live Rich status
    scrolls rather than overwrites (``docs/design-pipeline-resilience.md``,
    "Progress Bar Dead Ends").

    Only on a terminal: off one, a bar is a log of carriage returns.
    """
    if not _stderr_is_tty():
        yield None
        return
    try:
        # By module path: ``huggingface_hub.utils.tqdm`` as an attribute is the
        # re-exported class, not the module that holds the frozen flag.
        hf_tqdm: Any = importlib.import_module("huggingface_hub.utils.tqdm")
    except ImportError:
        yield None
        return

    opened: list[Any] = []

    # A subclass of HF's own bar, so HF still applies its TTY detection and
    # group switches to it; the only addition is remembering it to close.
    class _ClosableBar(hf_tqdm.tqdm):  # type: ignore[misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            opened.append(self)

    frozen = hf_tqdm.HF_HUB_DISABLE_PROGRESS_BARS
    hf_tqdm.HF_HUB_DISABLE_PROGRESS_BARS = None
    hf_tqdm.enable_progress_bars()
    try:
        yield _ClosableBar
    finally:
        for bar in opened:
            bar.close()
        hf_tqdm.HF_HUB_DISABLE_PROGRESS_BARS = frozen
        hf_tqdm.disable_progress_bars()


def _print_banner(
    console: Console, repo_id: str, state: str
) -> None:
    from rich.markup import escape

    verb = (
        t("preflight.whisper.verb_restarting")
        if state == "partial"
        else t("preflight.whisper.verb_downloading")
    )
    console.print()
    # An unmeasured repo (a custom ``org/repo``) names itself instead of
    # guessing a size.
    size = download_size_human(repo_id) or repo_id
    console.print("  " + t("preflight.whisper.banner_intro", size=size))
    mb = _DOWNLOAD_MB.get(repo_id)
    if mb is None or mb > _CACHE_PATH_CALLOUT_MB:
        console.print(
            "  " + t("preflight.whisper.downloads_to", path=escape(_cache_root_display()))
        )
    console.print("  " + t("preflight.whisper.ctrl_c_safe"))
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
    on_download_progress: Callable[[int, int], None] | None = None,
) -> None:
    """Run the Whisper-model preflight.

    Behaviour:
    - **``BRISTLENOSE_SKIP_PREFLIGHT=1``**: explicit escape hatch, skip silently.
      Defence-in-depth for spoofed-TTY CI runners and the pytest suite
      (set in ``tests/conftest.py``).
    - **Fully cached**: silent, return immediately.
    - **Missing or partial**: print the framed banner; if ``allow_fetch`` is
      False raise :class:`WhisperPreflightAbortedError`; otherwise stop the Rich
      spinner, call ``snapshot_download`` with HF Hub's own progress bars on
      (on a terminal only — :func:`_native_download_progress`), restart the
      spinner, print the ✓ done line.

    ``on_download_progress(done_bytes, total_bytes)`` is for a host that draws
    its own progress (the Mac app reads it from ``run_progress``). Off a
    terminal, where HF's bars draw nothing, the fetch then counts bytes the way
    :func:`fetch_with_progress_lines` does; ``total_bytes`` is 0 when the Hub
    gave no sizes. Without it, a first run in the app spent the whole ~1.6 GB
    download under a ring timed for the analysis alone, which sat near full and
    read as hung (R32, 20 Oct 2026).

    Callers gate on ``needs_transcription`` themselves (finding 39) — a folder
    of all-platform-transcripts should never trigger this code path.

    Raises:
        WhisperPreflightAbortedError: when the model name is not one the active
            backend knows (:func:`unknown_model_message`), or when
            ``--no-fetch`` is active and the model is not fully cached.
        PackageInstallError: when the download itself fails (propagated from
            :func:`bristlenose.utils.package_install.ensure_hf_model`).
    """
    if os.environ.get("BRISTLENOSE_SKIP_PREFLIGHT") == "1":
        return
    from bristlenose.utils.package_install import ensure_hf_model

    # Defence-in-depth against the env-var suppression in
    # `bristlenose/__init__.py`: when `bristlenose.doctor.check_whisper_model`
    # imports `huggingface_hub` (which it does during the doctor preflight),
    # `HF_HUB_DISABLE_PROGRESS_BARS` gets read into a module-level constant —
    # so if the env var is somehow unset by the time HF is first imported,
    # the programmatic call still suppresses `Fetching N files:` and the
    # trailing `Download complete: : 0.00B` summary line.
    try:
        # The defining module: ``huggingface_hub.utils`` re-exports it implicitly,
        # which strict mypy does not count as an export.
        from huggingface_hub.utils.tqdm import disable_progress_bars
        disable_progress_bars()
    except ImportError:
        pass

    if (refusal := unknown_model_message(settings)) is not None:
        raise WhisperPreflightAbortedError(refusal)

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

    # The Mac app is already fetching this model in the background (it starts
    # at launch): wait on that download instead of writing a second partial of
    # the same repo, and pass its bytes on so the run's row and ring follow it.
    host_pid = _host_fetch_pid()
    if host_pid is not None:
        if status is not None:
            status.stop()
        try:
            ready = _wait_for_host_fetch(repo_id, host_pid, on_download_progress)
        finally:
            if status is not None:
                status.start()
        if ready:
            logger.info("preflight_whisper: %s arrived via the app's download", repo_id)
            return
        logger.info("preflight_whisper: the app's download ended without %s; fetching", repo_id)

    # Option B: step aside, let HF Hub print natively.
    if status is not None:
        status.stop()
    t0 = time.perf_counter()
    try:
        if on_download_progress is not None and not _stderr_is_tty():
            fetch_with_progress_lines(
                settings,
                write=_progress_line_reader(
                    on_download_progress, already=_bytes_on_disk(repo_id)
                ),
            )
        else:
            with _native_download_progress() as bar_class:
                ensure_hf_model(repo_id, tqdm_class=bar_class)
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


# ---------------------------------------------------------------------------
# Machine-readable progress, for the Mac app's download job
# ---------------------------------------------------------------------------

#: Lines ``bristlenose doctor --fetch --progress-lines`` prints to stdout, for
#: the Mac app's ``WhisperDownloadModel`` (docs/design-apple-first-transcription.md
#: §3 D). One line each, space-separated, never localised:
#:
#:   @download-start <repo_id> <total_bytes>   (0 when the server gave no sizes)
#:   @download <done_bytes> <total_bytes>      (at most every PROGRESS_INTERVAL_S)
#:   @download-done <elapsed_s>
#:
#: A failure exits non-zero with an ordinary message on stderr, and no
#: ``@download-done``. Already on disk: start and done at once.
PROGRESS_INTERVAL_S = 0.25


def _server_total_bytes(repo_id: str) -> int:
    """The repo's size as the Hub reports it, or 0 when it cannot be asked.

    The sizes come from the server, not from ``_DOWNLOAD_MB`` (measured once,
    drifts with every re-upload), and not from the download's own bars: their
    total grows as files are queued ("incomplete total"), so a bar built on it
    reads 100% on the first 262-byte file (measured 18 Oct 2026).
    """
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repo_id, files_metadata=True)
        return int(sum((s.size or 0) for s in (info.siblings or [])))
    except Exception:  # noqa: BLE001 — a missing total is shown as unknown
        logger.info("could not read %s's size from the Hub", repo_id, exc_info=True)
        return 0


#: The Mac app's own download job sets this on a run it starts while that job
#: runs (``WhisperDownloadModel.whisperFetchEnvironment``).
_HOST_FETCH_PID_ENV = "_BRISTLENOSE_WHISPER_FETCH_PID"
#: How long a wait that cannot see the app's job sees no bytes move before it
#: stops trusting it (only when the process cannot be asked: see
#: :func:`_host_fetch_alive`).
_HOST_FETCH_STALL_S = 600.0
_HOST_FETCH_POLL_S = 0.5


def _host_fetch_pid() -> int | None:
    raw = os.environ.get(_HOST_FETCH_PID_ENV, "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def _host_fetch_alive(pid: int) -> bool | None:
    """Whether the app's download process still exists: True, False, or None
    when the system will not say (another user's process, a sandbox)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return None
    return True


def _bytes_in_flight(repo_id: str) -> int:
    """Finished blobs plus the newest partial: what a download in another
    process has written so far (hf_xet writes each file into a fresh
    ``.incomplete`` and renames it when done)."""
    blobs = _repo_cache_dir(repo_id) / "blobs"
    try:
        partials = [
            f for f in blobs.iterdir() if f.is_file() and f.name.endswith(".incomplete")
        ]
        newest = max(partials, key=lambda f: f.stat().st_mtime, default=None)
        in_flight = newest.stat().st_size if newest is not None else 0
    except OSError:
        in_flight = 0
    return _bytes_on_disk(repo_id) + in_flight


def _wait_for_host_fetch(
    repo_id: str,
    pid: int,
    on_progress: Callable[[int, int], None] | None,
    *,
    clock: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> bool:
    """Wait on the app's download of ``repo_id``. True once it is cached;
    False when the app's job has gone without it (the run then fetches it
    itself). A job known to be alive is waited on for as long as it runs: the
    researcher can stop it from the app. Only when the process cannot be asked
    does a wait with no bytes moving for ``_HOST_FETCH_STALL_S`` give up, since
    the size of a partial file is not a trustworthy sign of progress under
    hf_xet (docs/design-apple-first-transcription.md)."""
    # Looked up at call time, so a patched ``time`` reaches them.
    clock = clock or time.monotonic
    sleep = sleep or time.sleep
    total = _server_total_bytes(repo_id) if on_progress is not None else 0
    last_bytes = -1
    last_change = clock()
    while True:
        if cache_state(repo_id) == "cached":
            return True
        alive = _host_fetch_alive(pid)
        if alive is False:
            return cache_state(repo_id) == "cached"
        done = _bytes_in_flight(repo_id)
        if done != last_bytes:
            last_bytes, last_change = done, clock()
        elif alive is None and clock() - last_change > _HOST_FETCH_STALL_S:
            logger.info("preflight_whisper: the app's download of %s stalled", repo_id)
            return False
        if on_progress is not None:
            on_progress(min(done, total) if total else done, total)
        sleep(_HOST_FETCH_POLL_S)


def _bytes_on_disk(repo_id: str) -> int:
    """Size of the repo's finished blobs in the cache (partials left out)."""
    blobs = _repo_cache_dir(repo_id) / "blobs"
    try:
        return sum(
            f.stat().st_size for f in blobs.iterdir()
            if f.is_file() and not f.name.endswith(".incomplete")
        )
    except OSError:
        return 0


def whisper_status_line(settings: BristlenoseSettings) -> str:
    """``@whisper-status <cached|partial|missing> <repo_id> <bytes>`` for the Mac app.

    ``bytes`` is the finished payload on disk, for "On this Mac · 1.6 GB";
    0 when nothing is there.
    """
    repo_id = _resolve_repo_id(settings)
    state = cache_state(repo_id)
    size = _bytes_on_disk(repo_id) if state == "cached" else 0
    return f"@whisper-status {state} {repo_id} {size}"


def fetch_with_progress_lines(
    settings: BristlenoseSettings,
    write: Any = None,
    *,
    clock: Any = time.monotonic,
) -> None:
    """Fetch the Whisper model, printing the ``@download`` lines above.

    Bytes done are the bytes hf_xet has written into the cache (its
    "Reconstructing" bar), or, on a plain-HTTP fetch, the sum of the per-file
    bars; the wire-bytes bar is only a floor, because with hf_xet's
    deduplication it can finish below the file sizes.

    Raises:
        PreflightAbortedError: for a model name the backend does not know.
        PackageInstallError: when the download fails.
    """
    from bristlenose.utils.package_install import ensure_hf_model

    out = write or (lambda line: (sys.stdout.write(line + "\n"), sys.stdout.flush()))
    if (refusal := unknown_model_message(settings)) is not None:
        raise PreflightAbortedError(refusal)
    repo_id = _resolve_repo_id(settings)
    t0 = clock()
    if cache_state(repo_id) == "cached":
        out(f"@download-start {repo_id} 0")
        out("@download-done 0")
        return
    total = _server_total_bytes(repo_id)
    out(f"@download-start {repo_id} {total}")

    hf_tqdm: Any = importlib.import_module("huggingface_hub.utils.tqdm")
    bars: dict[int, Any] = {}
    last = [0.0]

    def done_bytes() -> int:
        wire = recon = per_file = 0
        for bar in list(bars.values()):
            if getattr(bar, "unit", "") != "B":
                continue
            desc = str(getattr(bar, "desc", "") or "")
            n = int(getattr(bar, "n", 0) or 0)
            if desc.startswith("Downloading bytes"):
                wire = max(wire, n)
            elif desc.startswith("Reconstruct"):
                recon = max(recon, n)
            else:
                per_file += n
        return max(wire, recon, per_file)

    def report(force: bool = False) -> None:
        now = clock()
        if force or now - last[0] >= PROGRESS_INTERVAL_S:
            last[0] = now
            done = done_bytes()
            out(f"@download {min(done, total) if total else done} {total}")

    # Off a terminal the bars draw nothing; HF's frozen "bars disabled" flag
    # is lifted so they still count (see `_native_download_progress`).
    class _CountingBar(hf_tqdm.tqdm):  # type: ignore[misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            kwargs["disable"] = False
            kwargs["file"] = _NullStream()
            super().__init__(*args, **kwargs)
            bars[id(self)] = self

        def update(self, n: float | None = 1) -> bool | None:
            result = super().update(n)
            report()
            return result  # type: ignore[no-any-return]

    frozen = hf_tqdm.HF_HUB_DISABLE_PROGRESS_BARS
    hf_tqdm.HF_HUB_DISABLE_PROGRESS_BARS = None
    hf_tqdm.enable_progress_bars()
    try:
        ensure_hf_model(repo_id, tqdm_class=_CountingBar)
    finally:
        for bar in list(bars.values()):
            bar.close()
        hf_tqdm.HF_HUB_DISABLE_PROGRESS_BARS = frozen
        hf_tqdm.disable_progress_bars()
    report(force=True)
    # Done means the run will find it: the same probe the run asks.
    if cache_state(repo_id) != "cached":
        from bristlenose.utils.package_install import PackageInstallError

        raise PackageInstallError(f"{repo_id} is not complete in the cache after the download")
    out(f"@download-done {clock() - t0:.1f}")


def _progress_line_reader(
    on_progress: Callable[[int, int], None], already: int = 0
) -> Callable[[str], None]:
    """Turn the ``@download`` lines back into ``on_progress(done, total)`` calls.

    ``already`` is what a partial cache held before the fetch: Hugging Face
    skips finished files, so the lines count only this run's bytes against the
    whole repo's size. A progress fault is logged once and the forwarding stops;
    it must never fail the download (on hf_xet it would vanish into a Rust thread,
    on plain HTTP surface as a failed model download).
    """
    broken = [False]

    def read(line: str) -> None:
        if broken[0]:
            return
        parts = line.split()
        try:
            if parts and parts[0] == "@download-start" and len(parts) == 3:
                total = int(parts[2])
                on_progress(min(already, total) if total else 0, total)
            elif parts and parts[0] == "@download" and len(parts) == 3:
                total = int(parts[2])
                done = int(parts[1]) + already
                on_progress(min(done, total) if total else done, total)
        except Exception:  # noqa: BLE001 — progress is advisory; the download is not
            broken[0] = True
            logger.warning("model download progress stopped reporting", exc_info=True)

    return read


class _NullStream:
    """A file object tqdm can draw to that keeps nothing."""

    def write(self, _s: str) -> int:
        return 0

    def flush(self) -> None:
        return None
