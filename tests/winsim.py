"""Opt-in pytest plugin: three of Windows' defaults, on any OS.

    .venv/bin/python -m pytest -p tests.winsim tests/test_cli_unsuitable_input.py

- ``Path.read_text()`` / ``write_text()`` without ``encoding=`` use cp1252, the
  codepage of a Western Windows install, not UTF-8.
- ``Path.home()`` and ``expanduser("~")`` read ``USERPROFILE``, never ``HOME``.
- ``os.kill`` on a pid that does not exist raises a plain ``OSError`` (WinError
  87 there), not ``ProcessLookupError``.

Each is a habit a test written on a Mac assumed, and each reddened CI's
windows-latest job at 0.43.0 (24 Oct 2026). This reproduced every one of them
locally. It is a simulator, not Windows: path separators, forbidden file-name
characters, file locking and line endings are untouched, so windows-latest
stays the authority.
"""

from __future__ import annotations

import errno
import os
import posixpath
from pathlib import Path

import pytest

_mp = pytest.MonkeyPatch()


def pytest_configure(config: pytest.Config) -> None:
    real_read, real_write = Path.read_text, Path.write_text
    real_expanduser, real_kill = posixpath.expanduser, os.kill
    # With no USERPROFILE, Windows still finds the runner's own profile.
    profile = real_expanduser("~")

    def read_text(self, encoding=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        return real_read(self, encoding or "cp1252", *args, **kwargs)

    def write_text(self, data, encoding=None, *args, **kwargs):  # type: ignore[no-untyped-def]
        return real_write(self, data, encoding or "cp1252", *args, **kwargs)

    def expanduser(path):  # type: ignore[no-untyped-def]
        p = os.fspath(path)
        if isinstance(p, str) and (p == "~" or p.startswith("~/")):
            return os.environ.get("USERPROFILE", profile) + p[1:]
        return real_expanduser(path)

    def kill(pid: int, sig: int) -> None:
        try:
            real_kill(pid, sig)
        except ProcessLookupError:
            raise OSError(errno.EINVAL, "The parameter is incorrect") from None

    _mp.setattr(Path, "read_text", read_text)
    _mp.setattr(Path, "write_text", write_text)
    _mp.setattr(posixpath, "expanduser", expanduser)  # Path.home() and os.path both
    _mp.setattr(os, "kill", kill)


def pytest_unconfigure(config: pytest.Config) -> None:
    _mp.undo()
