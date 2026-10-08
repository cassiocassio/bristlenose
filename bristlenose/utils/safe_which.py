"""Find an executable without ever finding one in the current directory.

On Windows, CPython's ``shutil.which`` looks in the current directory before
PATH and honours PATHEXT, and ``CreateProcess`` does the same for a bare
command name. A researcher who unzips a client's folder and runs
``bristlenose run .`` from inside it would run whatever ``ffmpeg.exe``,
``.bat`` or ``.cmd`` the folder holds. So on Windows only ``<name>.exe`` on an
absolute PATH entry counts: empty and relative entries (``.``) name the
current directory and are skipped. Elsewhere ``shutil.which`` is already safe:
exec searches PATH, not the current directory.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def safe_which(name: str) -> str | None:
    """Absolute path to ``name``, or None — never from the current directory."""
    if sys.platform != "win32":
        return shutil.which(name)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry or not os.path.isabs(entry):
            continue
        candidate = Path(entry) / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    return None
