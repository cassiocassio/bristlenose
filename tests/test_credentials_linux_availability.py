"""``configure`` on Linux picks the store that can work (N202).

``_is_secret_service_available`` treated *any* exit within two seconds as "the
keyring is there". ``secret-tool`` with no session bus (SSH, WSL, a headless
box) exits 1 at once with a D-Bus error on stderr, so the keyring was chosen,
every write failed, and ``configure`` said "Not saved" for ever, although the
config-file store it falls back to everywhere else would have worked. A healthy
keyring also exits 1 when the key is simply not there, but says nothing
(libsecret prints only real errors), so the stderr is what tells them apart.

The fake ``secret-tool`` is a real script on ``PATH``: the probe and the store
choice run as they would on a Linux box.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

from bristlenose.credentials import FileCredentialStore
from bristlenose.credentials_linux import (
    LinuxCredentialStore,
    _is_secret_service_available,
    get_linux_store,
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake tool is a shell script")


def _secret_tool(tmp_path: Path, monkeypatch, body: str) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool = bin_dir / "secret-tool"
    tool.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def test_no_session_bus_falls_back_to_the_file_store(tmp_path: Path, monkeypatch) -> None:
    _secret_tool(
        tmp_path, monkeypatch,
        'echo "secret-tool: Cannot autolaunch D-Bus without X11 \\$DISPLAY" >&2; exit 1',
    )

    assert _is_secret_service_available() is False
    assert isinstance(get_linux_store(), FileCredentialStore)


def test_a_healthy_keyring_that_lacks_the_key_is_still_the_keyring(
    tmp_path: Path, monkeypatch,
) -> None:
    """libsecret exits 1 and prints nothing for a key that is not stored."""
    _secret_tool(tmp_path, monkeypatch, "exit 1")

    assert _is_secret_service_available() is True
    assert isinstance(get_linux_store(), LinuxCredentialStore)


def test_a_keyring_that_answers_is_the_keyring(tmp_path: Path, monkeypatch) -> None:
    _secret_tool(tmp_path, monkeypatch, "echo found; exit 0")

    assert isinstance(get_linux_store(), LinuxCredentialStore)


def test_the_label_names_the_store_that_will_be_used(tmp_path: Path, monkeypatch) -> None:
    from bristlenose.credentials import get_credential_store_label

    monkeypatch.setattr(sys, "platform", "linux")
    _secret_tool(tmp_path, monkeypatch, 'echo "no bus" >&2; exit 1')
    assert get_credential_store_label() == "config file"
