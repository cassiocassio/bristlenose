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
import shutil
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


#: Free space asked of the cache's volume over the model itself. The download peaks at
#: its final size and no more (1,539 MiB for the default model, hf_xet cache empty,
#: measured 30 Oct 2026), so this is only room for the filesystem and what else is
#: writing, not scratch space.
_DISK_HEADROOM_BYTES = 1_000_000_000


def _cache_volume_free_bytes() -> tuple[int, Path] | None:
    """Free bytes on the volume the model will be written to, and the path asked."""
    path = _hf_cache_root()
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return shutil.disk_usage(path).free, path
    except OSError as exc:
        logger.warning("ensure_disk_room: cannot read free space at %s: %s", path, exc)
        return None


def _download_lock_held(repo_id: str, blob: Path) -> bool:
    """Whether another process is mid-download of ``blob``, by Hugging Face's own lock.

    huggingface_hub holds ``<hub>/.locks/<repo dir>/<etag>.lock`` (a ``filelock.FileLock``:
    ``flock`` on POSIX, a byte-range lock on Windows) for the whole of a file's download. A
    file's mtime is a poor witness of that: a writer whose connection has stalled (hf_xet rides
    out ~15 s of it) or that is SIGSTOPped or asleep touches nothing, and a sweep that took
    silence for death unlinked a live writer's file (found in review).

    The probe is the same ``FileLock`` the Hub takes, tried once, so it answers on every
    platform the Hub downloads on. Until 2 Nov 2026 it was a raw ``fcntl.flock`` that
    answered "not held" wherever ``fcntl`` is missing, i.e. on Windows, where the age rule
    alone then decided and a stalled writer's partial could go.
    """
    repo_dir = _repo_cache_dir(repo_id)
    lock = repo_dir.parent / ".locks" / repo_dir.name / f"{blob.name.split('.', 1)[0]}.lock"
    if not lock.is_file():
        return False  # no lock file: nobody holds one (and the probe must not create one)
    try:
        import filelock

        lock_descriptor = filelock.lock_descriptor
        unlock_descriptor = filelock.unlock_descriptor
    except (ImportError, AttributeError):  # an older filelock: probe through FileLock below
        lock_descriptor = unlock_descriptor = None  # type: ignore[assignment]
    if lock_descriptor is not None and unlock_descriptor is not None:
        # The same one-byte native lock FileLock takes, on a descriptor we open ourselves:
        # it never creates, truncates, unlinks or falls back to a soft lock, so probing a
        # live writer's lock cannot disturb it. Anything we cannot answer keeps the partial
        # (a filesystem without flock raises ENOSYS; an unreadable file fails to open).
        try:
            fd = os.open(lock, os.O_RDWR)
        except OSError:
            return True
        try:
            try:
                got = lock_descriptor(fd, blocking=False)
            except OSError:
                return True
            if got:
                unlock_descriptor(fd)
                return False
            return True
        finally:
            os.close(fd)
    from filelock import FileLock, SoftFileLock, Timeout  # older filelock: the path lock

    probe = FileLock(str(lock), timeout=0)
    if isinstance(probe, SoftFileLock):
        return True  # a lock that IS the file's existence: the file being there is the answer
    try:
        probe.acquire()
    except Timeout:
        return True
    except OSError:
        return True
    probe.release()
    return False


#: A partial this long untouched is nobody's: hf_xet writes a fresh ``.incomplete`` and
#: renames it when the file is whole, and a writer touches it many times a second.
_STALE_PARTIAL_S = 120.0


#: After a fetch has SUCCEEDED the repo is whole, so a partial still lying there is nobody's:
#: the shorter wait only has to clear a concurrent writer, which touches its file many times a
#: second. Without this sweep an orphan younger than ``_STALE_PARTIAL_S`` when the retry began
#: stayed for good, because the model was cached and no later fetch ever looked (measured on
#: macOS 15 and 26 guests, 30 Oct 2026: 1,949 MB on disk for a 1,543 MB model).
_SETTLED_PARTIAL_S = 20.0


def discard_stale_partials(
    repo_id: str, *, now: float | None = None, min_age_s: float | None = None
) -> int:
    """Delete the ``.incomplete`` blobs a dead download left behind; return bytes freed.

    A restart does not resume and does not reclaim: killed at 635 MB, the next fetch
    peaked at 2,174 MiB (the 1,539 MiB model plus the orphan) and the orphan stayed
    (measured 30 Oct 2026). Each crashed or killed attempt therefore cost up to a model's
    worth of disk, and Retry on a flaky line stacked them. Only files untouched for
    :data:`_STALE_PARTIAL_S` go, so a fetch running in another process is left alone.
    """
    blobs = _repo_cache_dir(repo_id) / "blobs"
    cutoff = (time.time() if now is None else now) - (
        _STALE_PARTIAL_S if min_age_s is None else min_age_s
    )
    freed = 0
    try:
        for f in blobs.iterdir():
            if not (f.is_file() and f.name.endswith(".incomplete")):
                continue
            try:
                st = f.stat()
                if st.st_mtime < cutoff and not _download_lock_held(repo_id, f):
                    f.unlink()
                    freed += st.st_size
            except OSError as exc:
                logger.warning("discard_stale_partials: could not remove %s: %s", f.name, exc)
    except OSError:
        return 0
    if freed:
        logger.info("discard_stale_partials: removed %d MB left by an earlier download", freed // 1_000_000)
    return freed


def ensure_disk_room(repo_id: str) -> None:
    """Refuse a fetch the cache's volume cannot hold, before a byte is written.

    Without this a full disk surfaced mid-download as hf_xet's own error, after the
    time was spent. A repo we never measured gets no check rather than a wrong one,
    and a volume that will not say is not an obstacle.

    Raises:
        PreflightAbortedError: ``Disk full: …`` (the Mac app classifies that wording
            as a disk failure).
    """
    mb = _DOWNLOAD_MB.get(repo_id)
    asked = _cache_volume_free_bytes()
    if mb is None or asked is None:
        return
    free, _volume_path = asked
    need = mb * 1_000_000 + _DISK_HEADROOM_BYTES
    if free < need:
        need_s, free_s = _format_mb(need // 1_000_000), _format_mb(free // 1_000_000)
        if need_s == free_s:  # "needs ~2.6 GB and only ~2.6 GB is free" tells nobody anything
            need_s, free_s = f"{need / 1e9:.2f} GB", f"{free / 1e9:.2f} GB"
        raise PreflightAbortedError(
            t("preflight.whisper.disk_full", need=need_s, free=free_s, where=_cache_root_display())
        )


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

    # Ours to fetch (not the app's): the volume must hold it. After the wait above,
    # because while the app is fetching, free space is already net of its partial file.
    discard_stale_partials(repo_id)
    ensure_disk_room(repo_id)

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
                _fetch_retrying_network_loss(
                    lambda: ensure_hf_model(repo_id, tqdm_class=bar_class),
                    repo_id,
                    on_restart=lambda _attempt: console.print(
                        f"  {cli_prefix(MessageKind.WARNING)} " + t("preflight.whisper.network_wait")
                    ),
                    on_answered=lambda _total: console.print(
                        f"  {cli_prefix(MessageKind.INFO)} " + t("preflight.whisper.network_back")
                    ),
                )
    finally:
        if status is not None:
            status.start()

    discard_stale_partials(repo_id, min_age_s=_SETTLED_PARTIAL_S)
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


#: A question to the Hub that gets no answer in this long is "no". huggingface_hub's own default
#: is NO timeout at all, so a network that drops packets instead of refusing them (a VPN split
#: tunnel, a captive portal that completes TCP and never replies) held the call for as long as
#: macOS's connect timeout, about 75 s, per try (found in review, 30 Oct 2026).
_HUB_ASK_TIMEOUT_S = 10.0


def _server_total_bytes(repo_id: str, *, log_failure: bool = True) -> int:
    """The repo's size as the Hub reports it, or 0 when it cannot be asked.

    The sizes come from the server, not from ``_DOWNLOAD_MB`` (measured once,
    drifts with every re-upload), and not from the download's own bars: their
    total grows as files are queued ("incomplete total"), so a bar built on it
    reads 100% on the first 262-byte file (measured 18 Oct 2026).
    """
    try:
        from huggingface_hub import HfApi

        info = HfApi().model_info(repo_id, files_metadata=True, timeout=_HUB_ASK_TIMEOUT_S)
        return int(sum((s.size or 0) for s in (info.siblings or [])))
    except Exception:  # noqa: BLE001 — a missing total is shown as unknown
        if log_failure:
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


# ── a network that comes back is not a failed download ──────────────────────────────────
#
# hf_xet does not resume, and a download dies when the connection does: an outage of about
# 15 s (12 s survived, 18 s did not; macOS 15 and 26 guests, 30 Oct 2026) ended a 1.6 GB
# fetch at whatever byte it had reached, and Retry started again from zero. A laptop that
# changes Wi-Fi, wakes, or reconnects a VPN does that routinely. So the download job waits for
# the Hub to answer and starts again by itself, quietly, a bounded number of times.

#: Failures a returning network can cure, matched against the lowercased exception text.
_NETWORK_FAILURE_MARKERS = (
    "nodename nor servname", "name or service not known", "temporary failure in name resolution",
    "network is unreachable", "network is down", "no route to host", "host is down",
    "connection reset", "connection aborted", "connecttimeout", "readtimeout", "readerror",
    "remoteprotocolerror", "incompleteread", "timed out", "broken pipe", "cached snapshot",
    # A stream cut mid-transfer on the plain-HTTP path reads "[SSL: UNEXPECTED_EOF_WHILE_READING]":
    # an outage in SSL's clothes, unlike a certificate failure, which "certificate" excludes.
    "unexpected_eof", "eof occurred in violation",
    "[errno 8]", "[errno 50]", "[errno 51]", "[errno 54]", "[errno 57]", "[errno 60]", "[errno 65]",
    # hf_xet is Rust: its failures read differently from Python's, and OS errors arrive as
    # "(os error 54)", never "[Errno 54]" (strings of hf_xet.abi3.so; found in review).
    "connection closed before", "error decoding response body", "error sending request",
    "dns error", "failed to lookup address", "operation timed out",
    "(os error 50)", "(os error 51)", "(os error 54)", "(os error 57)", "(os error 60)",
    "(os error 65)",
    # The Hub itself having a bad minute: also cured by waiting. Words, not status digits,
    # which would match a byte count or a hash in the text.
    "too many requests", "service unavailable", "bad gateway", "gateway timeout",
    "internal server error",
)
#: Waiting cures none of these, so they are never retried even when a network word is also in
#: the text (a certificate failure arrives as "ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED]",
#: and hf_xet's as "error sending request ... invalid peer certificate").
_NOT_NETWORK_MARKERS = (
    # A refused connection is an answer, not an outage: a dead proxy or a firewall says it at
    # once and waiting will not change it (a dead proxy waited 5 minutes before this was added).
    "connection refused", "[errno 61]", "(os error 61)",
    "certificate", "invalid peer", "permission denied", "[errno 13]", "no space left",
    "[errno 28]", "disk full", "read-only file system", "[errno 30]", "unauthorized", "forbidden",
)
_NETWORK_RETRY_ATTEMPTS = 5
#: How long the job waits for the Hub to answer again before it gives the failure to the user.
_NETWORK_WAIT_S = 300.0
_NETWORK_POLL_S = 5.0
_retry_sleep: Callable[[float], None] = time.sleep
_retry_clock: Callable[[], float] = time.monotonic


def is_network_failure(exc: BaseException) -> bool:
    """Whether ``exc`` is a failure a network that comes back would cure."""
    if os.environ.get("HF_HUB_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on"):
        return False  # offline on purpose: "cached snapshot ... incomplete" is the answer, not an outage
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(m in text for m in _NOT_NETWORK_MARKERS):
        return False
    return any(m in text for m in _NETWORK_FAILURE_MARKERS)


def _wait_until_reachable(repo_id: str, *, wait_s: float = _NETWORK_WAIT_S) -> int:
    """Poll the Hub until it answers; return its size for the repo (bytes), or 0 if it never did.

    Bounded by the clock, not by counting sleeps: each question can itself take up to
    ``_HUB_ASK_TIMEOUT_S``. The gap between questions grows (5 s, then 7.5, 11 ... up to 30 s),
    so a Hub that is answering "slow down" is asked a dozen times in five minutes, not sixty.
    """
    deadline = _retry_clock() + wait_s
    gap = _NETWORK_POLL_S
    while True:
        total = _server_total_bytes(repo_id, log_failure=False)
        if total > 0:
            return total
        if _retry_clock() >= deadline:
            return 0
        _retry_sleep(gap)
        gap = min(30.0, gap * 1.5)


def _fetch_retrying_network_loss(
    fetch: Callable[[], object],
    repo_id: str,
    *,
    on_restart: Callable[[int], None] = lambda _attempt: None,
    on_answered: Callable[[int], None] = lambda _total: None,
) -> None:
    """Run ``fetch``; when it dies of a network failure, wait for the Hub and run it again.

    Bounded: ``_NETWORK_RETRY_ATTEMPTS`` restarts, each after a wait of at most
    ``_NETWORK_WAIT_S`` for the Hub to answer. Anything a returning network cannot cure is raised
    at once. ``KeyboardInterrupt`` (the app's Stop) is not an ``Exception`` here and passes
    through, including out of the waits.
    """
    from bristlenose.utils.package_install import PackageInstallError

    attempt = 0
    while True:
        try:
            fetch()
            return
        except PackageInstallError as exc:
            if attempt >= _NETWORK_RETRY_ATTEMPTS or not is_network_failure(exc):
                raise
            attempt += 1
            logger.warning(
                "fetch: network failure (attempt %d of %d): %s",
                attempt, _NETWORK_RETRY_ATTEMPTS, exc,
            )
            on_restart(attempt)
            # Before the wait, not after: a Hub that is up but refusing (429) answers the wait's
            # first question, so the spacing has to come first.
            _retry_sleep(5.0 * attempt)
            answered = _wait_until_reachable(repo_id)
            if not answered:
                raise
            on_answered(answered)


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
    discard_stale_partials(repo_id)
    ensure_disk_room(repo_id)
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
    def _restart(_attempt: int) -> None:
        # Back to zero on screen too: the bytes of the dead attempt are gone from disk, and a
        # pill that kept claiming them would be lying.
        for bar in list(bars.values()):
            bar.close()
        bars.clear()
        out(f"@download 0 {total}")

    def _answered(new_total: int) -> None:
        # The size the Hub just gave, which an offline start never had.
        nonlocal total
        total = new_total

    try:
        _fetch_retrying_network_loss(
            lambda: ensure_hf_model(repo_id, tqdm_class=_CountingBar),
            repo_id, on_restart=_restart, on_answered=_answered,
        )
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
    discard_stale_partials(repo_id, min_age_s=_SETTLED_PARTIAL_S)
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
