"""Closing the terminal mid-run is a cancel, not a crash (R122).

Closing a terminal tab sends SIGHUP. The lifecycle handled SIGINT and SIGTERM
only, so SIGHUP killed the run with no terminus written, and the next reader
reconciled the stranded `run_started` as failed: the Mac sidebar said
"stopped unexpectedly". Under `nohup` SIGHUP is ignored, and must stay so:
the run is meant to outlive the terminal.
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

import pytest

from bristlenose.events import CauseCategoryEnum, RunCancelledEvent, events_path, read_events
from tests.test_run_lifecycle import (
    _paused_body,
    _spawn_lifecycle_subprocess,
    _wait_for_event,
    _wait_for_ready,
    _wait_for_run_started,
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGHUP")


def _cancelled_by(name: str):
    return lambda e: (
        isinstance(e, RunCancelledEvent)
        and e.cause.category == CauseCategoryEnum.USER_SIGNAL
        and e.cause.signal_name == name
    )


def test_sighup_writes_run_cancelled(tmp_path: Path) -> None:
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(tmp_path, _paused_body(sentinel))
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGHUP)
        landed = _wait_for_event(f, _cancelled_by("SIGHUP"), timeout=60.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert landed, [type(e).__name__ for e in read_events(f)] if f.exists() else "no events"


def test_a_nohup_run_keeps_ignoring_sighup(tmp_path: Path) -> None:
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _paused_body(sentinel),
        preamble="import signal\nsignal.signal(signal.SIGHUP, signal.SIG_IGN)",
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGHUP)
        time.sleep(1.0)
        assert proc.poll() is None, "a nohup run ended on SIGHUP"
        assert not any(isinstance(e, RunCancelledEvent) for e in read_events(f))
        proc.send_signal(signal.SIGINT)
        landed = _wait_for_event(f, _cancelled_by("SIGINT"), timeout=60.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert landed
