"""Windows: a Visual C++ runtime inside this environment counts.

ctranslate2, spaCy's thinc and the voice pass are C++ and need ``msvcp140.dll``.
A clean Windows has none (the VirtualBox walk, 28 Nov 2026), and uv's Python and
python.org's bring only the C runtime. Windows looks for it in System32 and beside
the base ``python.exe``, never in a venv. When the DLLs sit at ``sys.prefix``
(PyPI's ``msvc-runtime`` puts them there), naming that folder lets the engines
load with no administrator rights. Proven on that VM: without the call the
engines still fail; with it they load.
"""

from __future__ import annotations

import os
import sys
from typing import Any


def name_runtime_in_prefix() -> Any:
    """Add ``sys.prefix`` to Windows' DLL search when the runtime is there.

    Returns the handle (keep it: closing it removes the folder again), or None:
    not Windows, the frozen build (which carries its own runtime), or no
    ``msvcp140.dll`` at ``sys.prefix``.
    """
    if sys.platform != "win32" or getattr(sys, "frozen", False):
        return None
    if not os.path.exists(os.path.join(sys.prefix, "msvcp140.dll")):
        return None
    return os.add_dll_directory(sys.prefix)  # type: ignore[attr-defined,unused-ignore]
