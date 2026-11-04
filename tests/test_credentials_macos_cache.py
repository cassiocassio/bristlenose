"""The macOS store keeps a Keychain read for a few seconds.

``security`` is one subprocess per key (about 22 ms), ``load_settings()`` reads five, and a
``serve`` start calls it three times: 15 spawns, 360 ms (measured 4 Nov 2026). A write from
this process must still be seen at once, and an old read must expire.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from bristlenose import credentials_macos
from bristlenose.credentials_macos import MacOSCredentialStore


class _Spawns:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.value = "sk-one"

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if argv[1] == "find-generic-password":
            return subprocess.CompletedProcess(argv, 0, stdout=self.value + "\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def reads(self) -> int:
        return sum(1 for c in self.calls if c[1] == "find-generic-password")


@pytest.fixture
def spawns(monkeypatch: pytest.MonkeyPatch) -> _Spawns:
    s = _Spawns()
    monkeypatch.setattr(subprocess, "run", s)
    return s


def test_a_second_read_inside_the_window_spawns_nothing(spawns: _Spawns) -> None:
    store = MacOSCredentialStore()
    assert store.get("anthropic") == "sk-one"
    assert MacOSCredentialStore().get("anthropic") == "sk-one"  # a new instance, as the code makes
    assert spawns.reads() == 1


def test_each_key_is_read_once(spawns: _Spawns) -> None:
    store = MacOSCredentialStore()
    for key in ("anthropic", "openai", "azure"):
        store.get(key)
        store.get(key)
    assert spawns.reads() == 3


def test_a_read_expires(spawns: _Spawns, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr(credentials_macos, "_clock", lambda: now[0])
    store = MacOSCredentialStore()
    store.get("anthropic")
    now[0] += credentials_macos._CACHE_TTL_S - 0.1
    store.get("anthropic")
    assert spawns.reads() == 1
    now[0] += 0.2
    spawns.value = "sk-two"
    assert store.get("anthropic") == "sk-two"
    assert spawns.reads() == 2


def test_a_write_from_this_process_is_seen_at_once(spawns: _Spawns) -> None:
    store = MacOSCredentialStore()
    assert store.get("anthropic") == "sk-one"
    spawns.value = "sk-two"
    store.set("anthropic", "sk-two")
    assert store.get("anthropic") == "sk-two"


def test_a_delete_from_this_process_is_seen_at_once(spawns: _Spawns) -> None:
    store = MacOSCredentialStore()
    store.get("anthropic")
    store.delete("anthropic")
    store.get("anthropic")
    assert spawns.reads() == 2


def test_an_absent_key_is_kept_too(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def _missing(argv: list[str], **_kw: Any) -> Any:
        calls.append(1)
        raise subprocess.CalledProcessError(44, argv)

    monkeypatch.setattr(subprocess, "run", _missing)
    store = MacOSCredentialStore()
    assert store.get("miro") is None
    assert store.get("miro") is None
    assert len(calls) == 1
