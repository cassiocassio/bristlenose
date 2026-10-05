"""Windows portability, tested from any platform.

The run path once named ``os.O_NOFOLLOW`` directly. Windows has no such
attribute, so the first event write of every run raised ``AttributeError``
there. These tests remove the attribute the way Windows lacks it and drive real
call sites, and a source gate stops a sixth site from naming it again.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import bristlenose

_PKG = Path(bristlenose.__file__).parent


@pytest.fixture
def no_nofollow(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``os`` module as Windows has it: no ``O_NOFOLLOW``."""
    monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)


def test_no_module_names_o_nofollow_directly() -> None:
    """Only ``open_private`` may reach for the flag, and only via ``getattr``."""
    offenders = [
        f"{path.relative_to(_PKG)}:{n}"
        for path in _PKG.rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bos\.O_NOFOLLOW\b", line)
    ]
    assert offenders == [], f"use utils.fs.open_private instead: {offenders}"


def test_pid_file_writes_without_o_nofollow(no_nofollow: None, tmp_path: Path) -> None:
    from bristlenose.run_lifecycle import _read_pid_file, _write_pid_file

    _write_pid_file(tmp_path, "run-1", "start")
    assert _read_pid_file(tmp_path) == {
        "pid": os.getpid(), "start_time": "start", "run_id": "run-1",
    }


def test_shoal_feed_writes_without_o_nofollow(no_nofollow: None, tmp_path: Path) -> None:
    from bristlenose.shoal_feed import _write

    path = tmp_path / ".bristlenose" / "feed.jsonl"
    _write(path, line='{"a": 1}')
    _write(path, line='{"b": 2}')
    # Bytes, not text: a text-mode open on Windows would write \r\n here.
    assert path.read_bytes() == b'{"a": 1}\n{"b": 2}\n'


def test_backup_append_without_o_nofollow(no_nofollow: None, tmp_path: Path) -> None:
    from bristlenose.utils.output_backup import _append_onto

    src, dest = tmp_path / "src.jsonl", tmp_path / "dest.jsonl"
    src.write_bytes(b"two\n")
    dest.write_bytes(b"one\n")
    assert _append_onto(src, dest)
    assert dest.read_bytes() == b"one\ntwo\n"


def test_open_private_is_owner_only(tmp_path: Path) -> None:
    from bristlenose.utils.fs import open_private

    path = tmp_path / "f"
    os.close(open_private(path, os.O_WRONLY | os.O_CREAT))
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(os.name != "posix", reason="symlink refusal is POSIX-only")
def test_open_private_still_refuses_a_symlink(tmp_path: Path) -> None:
    from bristlenose.utils.fs import open_private

    target = tmp_path / "elsewhere"
    target.write_text("x")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        open_private(link, os.O_WRONLY | os.O_APPEND)


def test_manifest_rewrites_over_itself(tmp_path: Path) -> None:
    """Every stage rewrites the manifest; the second write must not fail.

    It was ``tmp.rename(path)``, which overwrites on POSIX and raises
    FileExistsError on Windows, so a Windows run died at its second stage. The
    first Windows CI run found it (5 Oct 2026); ``transcribe`` writes no
    manifest, so the smoke run could not.
    """
    from bristlenose.manifest import PipelineManifest, load_manifest, write_manifest

    def manifest(updated: str) -> PipelineManifest:
        return PipelineManifest(
            project_name="p", pipeline_version="0", created_at="t0", updated_at=updated,
        )

    write_manifest(manifest("t1"), tmp_path)
    write_manifest(manifest("t2"), tmp_path)
    loaded = load_manifest(tmp_path)
    assert loaded is not None and loaded.updated_at == "t2"


def test_start_time_tracks_a_live_process() -> None:
    """A live run reads as live, and a finished one as gone — on every platform.

    ``_ps_start_time`` reads libproc on macOS, ``ps`` on Linux and
    ``GetProcessTimes`` on Windows, so the windows-latest CI job is where the
    Windows reader meets a real process. Without one, every live run read as
    dead there, and a second run on the same folder was not refused. No skip:
    each platform proves its own reader.
    """
    from bristlenose.run_lifecycle import _is_alive_owned, _ps_start_time

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        first = _ps_start_time(child.pid)
        assert first, "no start time for a running process"
        assert _ps_start_time(child.pid) == first, "start time is not stable"
        assert _is_alive_owned({"pid": child.pid, "start_time": first})
        assert not _is_alive_owned({"pid": child.pid, "start_time": "0.0"})
    finally:
        child.kill()
        child.wait()
    # On Windows, Popen still holds a handle, so OpenProcess succeeds; the
    # exit-code check is what has to say "gone".
    assert _ps_start_time(child.pid) is None
    assert _ps_start_time(os.getpid()), "this process has no start time"


class TestWindowsFixText:
    """Doctor advice a Windows user can actually type."""

    @pytest.fixture(autouse=True)
    def _windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import platform
        import sys

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(platform, "system", lambda: "Windows")

    def test_ffmpeg_offers_winget(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        text = get_fix("ffmpeg_missing", "pip")
        assert "winget install FFmpeg" in text
        assert "new terminal" in text

    def test_azure_and_proxy_use_setx_not_export(self) -> None:
        from bristlenose.doctor_fixes import get_fix

        for key in ("api_key_missing_azure", "network_unreachable"):
            text = get_fix(key, "pip")
            assert "setx " in text, key
            assert "export " not in text, key

    def test_key_hint_names_the_real_file(self) -> None:
        from bristlenose.credentials import user_config_env_path
        from bristlenose.doctor_fixes import _credential_store_hint

        assert str(user_config_env_path()) in _credential_store_hint()
