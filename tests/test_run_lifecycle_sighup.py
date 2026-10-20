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


def test_a_stopped_run_whose_unwind_then_fails_is_still_a_cancel(tmp_path: Path) -> None:
    """Closing the terminal makes the next write to it fail (EIO), which replaces
    the stop with an OSError mid-unwind; the run ended because it was stopped."""
    sentinel = tmp_path / "ready"
    body = f"""
        import signal
        Path({str(sentinel)!r}).write_text("ready")
        try:
            signal.pause()
        finally:
            raise OSError(5, "Input/output error")
    """
    proc = _spawn_lifecycle_subprocess(tmp_path, body)
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


def test_a_signal_from_before_the_run_does_not_make_its_failure_a_cancel(
    tmp_path: Path, monkeypatch,
) -> None:
    """`_caught_signal` is module state: one left by an earlier run in the same
    process (or a stray SIGINT while the handler was installed) must not turn
    this run's failure into a cancel. Found by the full suite's order."""
    import bristlenose.run_lifecycle as rl
    from bristlenose.events import KindEnum, RunFailedEvent

    monkeypatch.setattr(rl, "_caught_signal", signal.SIGINT)
    with pytest.raises(RuntimeError):
        with rl.run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise RuntimeError("boom")
    assert isinstance(read_events(events_path(tmp_path))[-1], RunFailedEvent)


def test_the_suite_puts_the_run_handlers_back_after_each_test() -> None:
    """conftest's `no_run_signal_handlers_left_behind`: a CLI test installs the
    handlers for good, and a hung suite then could not be ended with SIGTERM."""
    import bristlenose.run_lifecycle as rl
    from tests.conftest import no_run_signal_handlers_left_behind

    teardown = no_run_signal_handlers_left_behind.__wrapped__()
    next(teardown)
    rl._install_signal_handlers()
    assert signal.getsignal(signal.SIGTERM) is rl._signal_handler
    with pytest.raises(StopIteration):
        next(teardown)
    assert signal.getsignal(signal.SIGTERM) is not rl._signal_handler
