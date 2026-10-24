"""Import onnxruntime with its import-time stderr kept out of the terminal.

onnxruntime 1.30 looks for GPUs when its module initialises and logs each
failure at WARNING to ``std::cerr``. Under the strict snap's AppArmor that is
"GPU device discovery failed … Permission denied" for ``/sys/class/drm`` and
``/sys/bus/pci/devices``; on a Hyper-V or Azure guest it is "Skipping
pci_bus_id". CPU is the right answer every time, but a researcher reads
"Permission denied" as breakage. The logger is created with a hard-coded
WARNING inside the pybind module init (``onnxruntime_pybind_module.cc``), so
nothing in Python runs early enough to quieten it: ``set_default_logger_severity``
needs the module, and no environment variable is read (upstream PR
microsoft/onnxruntime#27645 would add ``ORT_LOGGING_LEVEL``). So the first
import runs with fd 2 pointed at a temporary file, and whatever landed there
goes to the log, one INFO line each.
"""

from __future__ import annotations

import importlib
import logging
import os
import re
import sys
import tempfile
import threading
from types import ModuleType

logger = logging.getLogger(__name__)

# The snap's warning is yellow: an ANSI colour code the log should not keep.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# Two first imports at once would each save the other's capture as "stderr".
_lock = threading.Lock()


def import_onnxruntime() -> ModuleType:
    """onnxruntime, imported for the first time with fd 2 captured.

    Import errors still raise, after fd 2 is back. A second call, or a
    process that already holds the module, is a plain return. fd 2 is
    process-wide: for the length of the one import, another thread's
    stderr (a terminal WARNING, a serve access line) goes to the log as
    INFO too. Rich draws on stdout, so its display is untouched.
    """
    return _import_quietly("onnxruntime")


def _flush_stderr() -> None:
    flush = getattr(sys.stderr, "flush", None)
    if flush is not None:
        try:
            flush()
        except (OSError, ValueError):
            pass


def _import_quietly(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    with _lock:
        return _capture_import(name)


def _capture_import(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    try:
        saved = os.dup(2)
    except OSError:  # no fd 2 to capture (pythonw, a closed stderr)
        return importlib.import_module(name)
    try:
        # A file, never a pipe: a pipe nobody reads blocks a writer that fills it.
        sink = tempfile.TemporaryFile()
    except OSError:  # no writable temp dir: a noisy import beats a failed one
        os.close(saved)
        return importlib.import_module(name)
    with sink:
        _flush_stderr()
        os.dup2(sink.fileno(), 2)
        try:
            return importlib.import_module(name)
        finally:
            _flush_stderr()
            os.dup2(saved, 2)
            os.close(saved)
            sink.seek(0)
            text = _ANSI.sub("", sink.read().decode("utf-8", "replace"))
            for line in text.splitlines():
                if line.strip():
                    logger.info("%s import: %s", name, line.strip())
