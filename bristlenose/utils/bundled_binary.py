"""Bundled CLI binary discovery for ffmpeg / ffprobe.

Resolves a binary by name across three runtime modes:

1. Sandboxed macOS sidecar (`.app` distribution) — Swift host sets
   ``BRISTLENOSE_FFMPEG`` / ``BRISTLENOSE_FFPROBE`` env vars at spawn time,
   pointing at the absolute paths inside ``Bristlenose.app/Contents/Resources/``.
   PATH is stripped to ``/usr/bin:/bin:/usr/sbin:/sbin`` under App Sandbox so
   ``shutil.which()`` cannot find Homebrew binaries.

2. Bundled but env var unset (defensive) — when running from inside the
   PyInstaller bundle (``_BRISTLENOSE_HOSTED_BY_DESKTOP=1``), look at
   ``Contents/Resources/<name>`` relative to the sidecar binary's parent.
   Layout matches ``desktop/scripts/fetch-ffmpeg.sh`` and the Xcode "Copy
   Sidecar Resources" build phase.

3. CLI / non-bundled — ``safe_which(name)`` against the inherited PATH
   (``shutil.which`` off Windows; on Windows, absolute PATH entries only, never
   the current directory). This is the only path that runs in CI and on
   Homebrew/Snap/pip installs.

Returns ``None`` when not found by any branch; callers preserve their
existing "raise on missing" behaviour, so error messages on the CLI are
unchanged from the bare ``"ffmpeg"`` argv form.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from bristlenose.utils.safe_which import safe_which

_ENV_VAR_PREFIX = "BRISTLENOSE_"
_HOST_SENTINEL = "_BRISTLENOSE_HOSTED_BY_DESKTOP"


def bundled_binary_path(name: str) -> str | None:
    """Resolve a CLI binary path, preferring host-injected env var.

    Args:
        name: Binary name (``"ffmpeg"`` or ``"ffprobe"``). Case-insensitive
            for env-var lookup but used as-is for filesystem and PATH lookups.

    Returns:
        Absolute path string, or ``None`` if not found by any resolution
        branch. Caller decides how to surface the missing-binary case.
    """
    # Empty string is treated as unset — falls through to the next branch.
    env_key = _ENV_VAR_PREFIX + name.upper()
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value

    if _is_frozen_windows():
        # Ours or nothing. Falling through to which() would run an FFmpeg we did
        # not ship, and on Windows which() searches the current directory first,
        # so a damaged install (antivirus quarantining tools\ffmpeg.exe) would
        # run whatever ffmpeg.exe sat in the researcher's project folder. None
        # makes the preflight and doctor say FFmpeg is missing instead.
        candidate = Path(sys.executable).parent / "tools" / f"{name}.exe"
        return str(candidate) if candidate.is_file() else None

    if os.environ.get(_HOST_SENTINEL) == "1":
        bundle_path = _bundle_relative_path(name)
        if bundle_path is not None:
            return bundle_path

    return safe_which(name)


def binary_command(name: str) -> str:
    """What to put in argv[0] to run ``name``.

    The resolved path when there is one. Otherwise the bare name off Windows,
    where exec searches PATH only and a missing binary fails as it always did;
    on Windows a bare name would be looked up in the current directory first,
    so this raises ``FileNotFoundError`` instead — the error subprocess would
    have raised for a missing binary, so callers' handling is unchanged.
    """
    found = bundled_binary_path(name)
    if found is not None:
        return found
    if sys.platform == "win32":
        raise FileNotFoundError(f"{name} not found")
    return name


def bundled_binaries_dir() -> Path | None:
    """Directory containing bundled ffmpeg/ffprobe, or ``None`` outside the bundle.

    Resolution order matches ``bundled_binary_path`` but skips the
    ``shutil.which`` fallback — the system PATH is already searched for
    bare-name lookups, so prepending it gains nothing and adds confusion.

    Used by ``_prepend_bundled_binaries_to_path`` so subpackages that shell
    out to bare ``"ffmpeg"`` (mlx_whisper, faster_whisper) resolve to the
    bundled binary under macOS App Sandbox where Homebrew paths are unreachable.
    """
    env_value = os.environ.get(_ENV_VAR_PREFIX + "FFMPEG") or os.environ.get(
        _ENV_VAR_PREFIX + "FFPROBE"
    )
    if env_value:
        parent = Path(env_value).parent
        if parent.is_dir():
            return parent

    tools = _frozen_windows_tools_dir()
    if tools is not None:
        return tools

    if os.environ.get(_HOST_SENTINEL) == "1":
        sidecar = Path(sys.executable).resolve()
        candidate = sidecar.parent.parent
        if candidate.is_dir():
            return candidate

    return None


def _frozen_windows_tools_dir() -> Path | None:
    """``tools\\`` beside ``bristlenose.exe`` in the frozen Windows build.

    The installer puts the app folder on the user's PATH; FFmpeg lives one level
    down so it neither shadows nor is shadowed by an FFmpeg the user installed
    themselves, and our lookup still finds ours first (docs/design-winget.md).
    """
    if not _is_frozen_windows():
        return None
    tools = Path(sys.executable).parent / "tools"
    return tools if tools.is_dir() else None


def prepend_bundled_to_path() -> None:
    """Prepend the bundled binaries directory to ``$PATH`` (idempotent).

    Subpackages like ``mlx_whisper.audio.load_audio`` shell out via
    ``subprocess.run(["ffmpeg", …])`` — a bare-name lookup that bypasses
    our ``bundled_binary_path`` helper. Under macOS App Sandbox, Homebrew
    paths aren't on PATH, so the bare lookup fails with ``ENOENT``.

    Prepending the bundled directory to PATH is a one-line fix that covers
    every transitive shell-out without having to monkey-patch each upstream
    caller. Outside the bundle this is a no-op.
    """
    bin_dir = bundled_binaries_dir()
    if bin_dir is None:
        return
    bin_str = str(bin_dir)
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if parts and parts[0] == bin_str:
        return
    os.environ["PATH"] = os.pathsep.join([bin_str, *parts]) if parts else bin_str


def _bundle_relative_path(name: str) -> str | None:
    """Path to ``Contents/Resources/<name>`` relative to the PyInstaller binary.

    PyInstaller onedir layout under the .app:
        Contents/Resources/bristlenose-sidecar/bristlenose-sidecar  (sys.executable)
        Contents/Resources/ffmpeg                                   (target)
        Contents/Resources/ffprobe                                  (target)

    Returns ``None`` when the candidate path doesn't exist or isn't executable —
    the caller falls through to ``shutil.which()``.
    """
    sidecar = Path(sys.executable).resolve()
    candidate = sidecar.parent.parent / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def _is_frozen_windows() -> bool:
    """The PyInstaller build the winget installer ships."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))
