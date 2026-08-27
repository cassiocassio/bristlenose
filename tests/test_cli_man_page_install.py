"""`_install_man_page` must not write into a home directory a packager already served.

Bristlenose copies its man page to ``~/.local/share/man/man1/`` on first run, so
that a ``pipx install`` user gets ``man bristlenose``. That is right for pip and
wrong for every packaged install, which ships the page itself:

* ``man`` searches ``~/.local/share/man`` **before** ``/usr/share/man``, so the
  home copy shadows the packaged one;
* no package owns the home copy, so ``dnf remove`` / ``snap remove`` /
  ``brew uninstall`` leave it behind, and ``man bristlenose`` keeps working
  after the tool is gone, rendering whatever version last wrote it.

Snap and Homebrew were already excluded, by their own inline sniffs. The Fedora
RPM was not — found on a real Copr install on 27 Aug 2026, where
``man -w bristlenose`` resolved to ``~/.local/share/man/man1/bristlenose.1``
rather than the packaged, rpm-owned ``/usr/share/man/man1/bristlenose.1.gz``.
The fix routes all three through ``detect_install_method`` instead.

These tests drive the **real detector** rather than patching it. Patching
``detect_install_method`` would make the snap and brew cases pass vacuously
against any implementation that never calls it — including the old one, which
was in fact correct for those two. Setting up the genuine conditions means each
case fails only when the behaviour is actually wrong.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from bristlenose.cli import _install_man_page
from bristlenose.doctor_fixes import INSTALL_MARKER


def _man_target(home: Path) -> Path:
    return home / ".local" / "share" / "man" / "man1" / "bristlenose.1"


def _clean_env() -> dict[str, str]:
    """Environment with SNAP removed, so only the case under test sets it."""
    return {k: v for k, v in os.environ.items() if k != "SNAP"}


@pytest.mark.parametrize("method", ["snap", "rpm", "brew"])
def test_packaged_installs_do_not_write_a_home_man_page(
    method: str, tmp_path: Path
) -> None:
    """Every packaged install ships its own man page — none may add a second."""
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "prefix"
    prefix.mkdir()

    env = _clean_env()
    exe = "/usr/bin/python3"
    if method == "snap":
        env["SNAP"] = "/snap/bristlenose/42"
    elif method == "rpm":
        (prefix / INSTALL_MARKER).write_text("rpm\n", encoding="utf-8")
    elif method == "brew":
        exe = "/opt/homebrew/Cellar/bristlenose/0.27.0/libexec/bin/python3"

    with (
        patch("bristlenose.cli.Path.home", return_value=home),
        patch.dict(os.environ, env, clear=True),
        patch("bristlenose.doctor_fixes.sys.prefix", str(prefix)),
        patch("bristlenose.doctor_fixes.sys.executable", exe),
    ):
        _install_man_page()

    assert not _man_target(home).exists(), (
        f"a {method} install wrote ~/.local/share/man/man1/bristlenose.1. That "
        f"copy shadows the packaged page (man reads ~/.local first) and no "
        f"package owns it, so uninstalling leaves `man bristlenose` working."
    )


def test_pip_install_still_gets_a_man_page(tmp_path: Path) -> None:
    """The case the function exists for must keep working.

    Without this, "skip for packaged installs" could be satisfied by skipping
    for everything — which passes the test above and silently removes
    `man bristlenose` for every pipx user.
    """
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "prefix"
    prefix.mkdir()  # no marker: an ordinary venv

    with (
        patch("bristlenose.cli.Path.home", return_value=home),
        patch.dict(os.environ, _clean_env(), clear=True),
        patch("bristlenose.doctor_fixes.sys.prefix", str(prefix)),
        patch("bristlenose.doctor_fixes.sys.executable", str(prefix / "bin/python")),
    ):
        _install_man_page()

    target = _man_target(home)
    assert target.is_file(), "a pip/pipx install should still get ~/.local man page"
    assert target.stat().st_size > 0
