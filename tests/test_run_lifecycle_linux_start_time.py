"""On Linux a live run's identity does not move with the clock (N201).

The token in ``run.pid`` used to be the text of ``ps -o lstart=``: local
wall-clock time, in the reader's time zone and language, recomputed from the boot
time on every read. A second ``run`` or a serve started under another ``TZ`` (an
SSH session, a cron job) or after the wall clock was stepped took the live run
for dead, let the second run in and reconciled the first as stranded. The token
is now the process's start time in clock ticks since boot (``/proc/<pid>/stat``)
with the boot id: nothing about it depends on a time zone, a language or the
wall clock.

A fake ``/proc`` tree and a fake ``ps`` stand in, so these run on any platform.
The fake ``ps`` prints a time that moves with ``TZ`` and with a stepped clock, as
the real one does.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bristlenose import run_lifecycle
from bristlenose.run_lifecycle import _is_alive_owned, _ps_start_time

PID = 4242
BOOT_ID = "6c1d4f0e-0000-4000-8000-000000000001"


def _write_proc(root: Path, pid: int = PID, *, starttime: int = 987654,
                comm: str = "python3", boot_id: str = BOOT_ID) -> None:
    (root / str(pid)).mkdir(parents=True, exist_ok=True)
    # Fields 3..21 are filler; starttime is field 22.
    filler = " ".join(["0"] * 18)
    (root / str(pid) / "stat").write_text(
        f"{pid} ({comm}) S {filler} {starttime} 0 0\n", encoding="utf-8",
    )
    (root / "self").mkdir(exist_ok=True)
    (root / "self" / "stat").write_text("1 (self) S 0\n", encoding="utf-8")
    boot = root / "sys" / "kernel" / "random"
    boot.mkdir(parents=True, exist_ok=True)
    (boot / "boot_id").write_text(boot_id + "\n", encoding="utf-8")


@pytest.fixture()
def linux(tmp_path: Path, monkeypatch):
    proc = tmp_path / "proc"
    proc.mkdir()
    monkeypatch.setattr(run_lifecycle.sys, "platform", "linux")
    monkeypatch.setattr(run_lifecycle, "_PROC_ROOT", proc, raising=False)
    ps_calls: list[list[str]] = []
    ps_state = {"offset_hours": 0}

    def fake_run(cmd, *a, **k):
        ps_calls.append(list(cmd))
        # Wall-clock text that moves with TZ and with a stepped clock.
        import os

        zone = {"Europe/London": 0, "America/New_York": -4}.get(os.environ.get("TZ", ""), 0)
        hour = 10 + zone + ps_state["offset_hours"]
        return SimpleNamespace(returncode=0, stdout=f"Sun Oct 25 {hour:02d}:32:42 2026\n")

    monkeypatch.setattr(run_lifecycle.subprocess, "run", fake_run)
    return SimpleNamespace(proc=proc, ps_calls=ps_calls, ps_state=ps_state)


def test_the_token_is_the_same_in_every_time_zone(linux, monkeypatch) -> None:
    _write_proc(linux.proc)
    monkeypatch.setenv("TZ", "Europe/London")
    recorded = _ps_start_time(PID)

    monkeypatch.setenv("TZ", "America/New_York")
    assert _ps_start_time(PID) == recorded
    assert _is_alive_owned({"pid": PID, "start_time": recorded}) is True
    assert linux.ps_calls == [], "ps is the fallback, not the source"


def test_a_stepped_wall_clock_does_not_change_the_token(linux) -> None:
    _write_proc(linux.proc)
    before = _ps_start_time(PID)
    linux.ps_state["offset_hours"] = 3  # what lstart does when the clock is stepped
    assert _ps_start_time(PID) == before


def test_a_comm_with_spaces_and_parentheses_still_parses(linux) -> None:
    _write_proc(linux.proc, comm="my (weird) name", starttime=555)
    other = _ps_start_time(PID)
    _write_proc(linux.proc, comm="plain", starttime=555)
    assert _ps_start_time(PID) == other, "the token is the start time, not the name"
    _write_proc(linux.proc, comm="plain", starttime=556)
    assert _ps_start_time(PID) != other


def test_a_reused_pid_is_not_the_recorded_run(linux) -> None:
    _write_proc(linux.proc, starttime=100)
    recorded = _ps_start_time(PID)
    _write_proc(linux.proc, starttime=200)  # same pid, started later
    assert _is_alive_owned({"pid": PID, "start_time": recorded}) is False


def test_the_same_ticks_after_a_reboot_are_not_the_recorded_run(linux) -> None:
    _write_proc(linux.proc, starttime=100)
    recorded = _ps_start_time(PID)
    _write_proc(linux.proc, starttime=100, boot_id="aaaaaaaa-0000-4000-8000-000000000002")
    assert _is_alive_owned({"pid": PID, "start_time": recorded}) is False


def test_a_dead_pid_is_none(linux) -> None:
    _write_proc(linux.proc, pid=PID)
    assert _ps_start_time(PID + 1) is None
    assert linux.ps_calls == []


def test_without_proc_it_falls_back_to_ps(linux) -> None:
    """A Linux with no /proc mounted (a stripped container) still has ps."""
    token = _ps_start_time(PID)
    assert token == "Sun Oct 25 10:32:42 2026"
    assert linux.ps_calls and linux.ps_calls[0][0].endswith("ps")


def test_a_run_pid_written_by_the_old_build_is_still_read_as_before(linux) -> None:
    """The old token is ps's text. A run that was live across the upgrade must
    still read as live, and a different text still as someone else's."""
    _write_proc(linux.proc)
    assert _is_alive_owned({"pid": PID, "start_time": "Sun Oct 25 10:32:42 2026"}) is True
    assert _is_alive_owned({"pid": PID, "start_time": "Sun Oct 25 11:11:11 2026"}) is False


def test_a_missing_or_non_string_token_is_not_alive(linux) -> None:
    _write_proc(linux.proc)
    assert _is_alive_owned({"pid": PID}) is False
    assert _is_alive_owned({"pid": PID, "start_time": 12345}) is False


def test_the_real_proc_gives_one_token_per_process() -> None:
    """On a Linux box the real /proc is read; elsewhere this is the ps/libproc token."""
    import os

    a = _ps_start_time(os.getpid())
    assert a is not None and a == _ps_start_time(os.getpid())
    child = subprocess.Popen(["sleep", "5"])
    try:
        assert _ps_start_time(child.pid) != a
    finally:
        child.kill()
        child.wait()
