"""Ownership identifiers are stable, private and fail closed."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from bristlenose.utils import machine_identity as identity


@pytest.fixture(autouse=True)
def _fresh_identity_cache(monkeypatch):
    """machine_id() keeps a good answer per process; each test starts without one."""
    monkeypatch.setattr(identity, "_cached", None)


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


def test_friendly_name_uses_apple_display_name_not_hostname(monkeypatch):
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    calls = []

    def scutil(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout="Cassio’s Mac Studio\n")

    monkeypatch.setattr(identity.subprocess, "run", scutil)
    assert identity.friendly_machine_name() == "Cassio’s Mac Studio"
    assert calls == [["/usr/sbin/scutil", "--get", "ComputerName"]]


@pytest.mark.parametrize("name", ["", "a" * 257, "Office\nMac", "Office\x00Mac"])
def test_unusable_friendly_name_is_omitted(monkeypatch, name):
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=name))
    assert identity.friendly_machine_name() is None


def test_unavailable_display_name_never_falls_back_to_dns(monkeypatch):
    monkeypatch.setattr(identity.sys, "platform", "darwin")

    def unavailable(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "scutil")

    monkeypatch.setattr(identity.subprocess, "run", unavailable)
    assert identity.friendly_machine_name() is None


def test_hash_derivation_is_pinned_by_a_golden_vector(monkeypatch):
    """A change to the namespace or the hex form would make every stored marker foreign."""
    monkeypatch.setattr(identity.sys, "platform", "linux")
    monkeypatch.setattr(identity.Path, "read_text", lambda *a, **k: "12345678123456781234567812345678\n")
    assert identity.machine_id() == (
        "8cf13ccc8f0bd1f5428cb9b27a58a8c14980bcb9356ea4d44d35d29c30824ed6"
    )

    monkeypatch.setattr(identity, "_cached", None)
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout='"IOPlatformUUID" = "12345678-1234-5678-1234-567812345678"'))
    assert identity.machine_id() == (
        "8cf13ccc8f0bd1f5428cb9b27a58a8c14980bcb9356ea4d44d35d29c30824ed6"
    )


def test_one_failed_read_is_retried_and_a_failure_is_never_kept(monkeypatch):
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    outcomes = [subprocess.TimeoutExpired("ioreg", 2), None]

    def flaky(*args, **kwargs):
        outcome = outcomes.pop(0) if outcomes else None
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(stdout='"IOPlatformUUID" = "12345678-1234-5678-1234-567812345678"')

    monkeypatch.setattr(identity.subprocess, "run", flaky)
    first = identity.machine_id()
    assert first is not None and len(first) == 64
    # Kept for the process: a later failure cannot change the answer.
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert identity.machine_id() == first


def test_two_failed_reads_give_unknown_and_are_not_cached(monkeypatch):
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert identity.machine_id() is None
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout='"IOPlatformUUID" = "12345678-1234-5678-1234-567812345678"'))
    assert identity.machine_id() is not None


@pytest.mark.parametrize("name", ["Mac\u202eevil", "Mac\u200bStudio", "Mac\x07", "Mac\x7f"])
def test_a_display_name_with_invisible_or_control_characters_is_refused(monkeypatch, name):
    assert identity.has_unsafe_display_character(name)
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    monkeypatch.setattr(identity.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=name + "\n"))
    assert identity.friendly_machine_name() is None
    assert not identity.has_unsafe_display_character("Cassio’s Mac Studio")


@pytest.mark.parametrize("name", ["👨\u200d👩\u200d👧 Mac", "ایران\u200cمک"])
def test_joiners_in_a_real_name_are_kept(name):
    """Family emoji and Persian spelling need the joiners; refusing them blanks real names."""
    assert not identity.has_unsafe_display_character(name)
