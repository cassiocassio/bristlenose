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

3. CLI / non-bundled — ``shutil.which(name)`` against the inherited PATH.
   This is the only path that runs in CI and on Homebrew/Snap/pip installs.

Returns ``None`` when not found by any branch; callers preserve their
existing "raise on missing" behaviour, so error messages on the CLI are
unchanged from the bare ``"ffmpeg"`` argv form.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

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
    env_key = _ENV_VAR_PREFIX + name.upper()
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value

    if os.environ.get(_HOST_SENTINEL) == "1":
        bundle_path = _bundle_relative_path(name)
        if bundle_path is not None:
            return bundle_path

    return shutil.which(name)


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
