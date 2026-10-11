"""Where downloaded model files live on this machine.

One directory for every model Bristlenose fetches itself (the voice model, and
the PII model on read-only packages), so they are found, and cleared, together.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def model_cache_dir() -> Path:
    """The directory fetched models are kept in.

    In the Mac app: ``~/Library/Caches`` — the container's, since HOME is the
    container under the sandbox — which Time Machine skips and macOS may
    purge; a purged model is simply fetched again. On the CLI: the snap's
    common area, ``$XDG_CACHE_HOME``, or ``~/.cache``.
    """
    from bristlenose.config import hosted_by_desktop

    snap_common = os.environ.get("SNAP_USER_COMMON")
    if sys.platform == "darwin" and hosted_by_desktop():
        return Path.home() / "Library" / "Caches" / "bristlenose" / "models"
    if snap_common:
        return Path(snap_common) / "models"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (Path(xdg) if xdg else Path.home() / ".cache") / "bristlenose" / "models"
