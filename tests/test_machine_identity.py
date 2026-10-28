"""Ownership identifiers are stable, private and fail closed."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from bristlenose.utils import machine_identity as identity


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_stable_namespaced_identity(monkeypatch, platform):
    raw = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(identity.sys, "platform", platform)
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout=f'"IOPlatformUUID" = "{raw}"'))
    monkeypatch.setattr(identity.Path, "read_text", lambda *a, **k: raw.replace("-", "")+'\n')
    first = identity.machine_id()
    assert first is not None and len(first) == 64
    assert raw.replace("-", "") not in first
    assert identity.machine_id() == first


@pytest.mark.parametrize("value", ["", "not-an-id", "0" * 32])
@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_invalid_identity_is_unknown(monkeypatch, platform, value):
    monkeypatch.setattr(identity.sys, "platform", platform)
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout=f'"IOPlatformUUID" = "{value}"'))
    monkeypatch.setattr(identity.Path, "read_text", lambda *a, **k: value)
    assert identity.machine_id() is None


@pytest.mark.parametrize("error", [OSError(), subprocess.TimeoutExpired("ioreg", 2)])
def test_unavailable_identity_is_unknown(monkeypatch, error):
    monkeypatch.setattr(identity.sys, "platform", "darwin")

    def unavailable(*args, **kwargs):
        raise error

    monkeypatch.setattr(identity.subprocess, "run", unavailable)
    assert identity.machine_id() is None


@pytest.mark.parametrize("guid", ["12345678-1234-5678-1234-567812345678", 123, None, "invalid"])
def test_windows_guid_uses_same_private_contract(monkeypatch, guid):
    import sys
    from contextlib import nullcontext

    fake = SimpleNamespace(
        HKEY_LOCAL_MACHINE=1, KEY_READ=2, KEY_WOW64_64KEY=4,
        OpenKey=lambda *args: nullcontext("key"),
        QueryValueEx=lambda *args: (guid, 1),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    monkeypatch.setattr(identity.sys, "platform", "win32")
    value = identity.machine_id()
    if guid == "12345678-1234-5678-1234-567812345678":
        assert value is not None and len(value) == 64
    else:
        assert value is None


def test_unsupported_os_is_unknown(monkeypatch):
    monkeypatch.setattr(identity.sys, "platform", "unsupported")
    assert identity.machine_id() is None
