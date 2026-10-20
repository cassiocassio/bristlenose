"""A hosted run that cannot unwind is ended by a backstop, with one terminus (R19).

Once a hosted run is stopping, further signals are ignored (R19), so a quit
whose unwind blocks, for instance a thread pool joining a stalled first-run
Whisper download, waited out huggingface_hub's own timeouts. The first hosted
signal now arms a timer: if the process is still alive at the deadline it
writes run_cancelled (unless a terminus is already written) and exits. A lock
around every terminus write means the timer and the normal path never both
write one.
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

import pytest

from bristlenose.events import (
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    events_path,
    read_events,
)
from tests.test_run_lifecycle import (
    _spawn_lifecycle_subprocess,
    _wait_for_ready,
    _wait_for_run_started,
)

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")

HOSTED = {"_BRISTLENOSE_HOSTED_BY_DESKTOP": "1"}
GRACE = "import bristlenose.run_lifecycle as _r\n_r._HOSTED_STOP_GRACE_S = {grace}"


def _termini(f: Path) -> list[object]:
    return [
        e for e in read_events(f)
        if isinstance(e, (RunCancelledEvent, RunCompletedEvent, RunFailedEvent))
    ]


def _stuck_body(sentinel: Path) -> str:
    """Pause, then never finish unwinding, as a pool joining a stalled download."""
    return f"""
        import signal, threading
        Path({str(sentinel)!r}).write_text("ready")
        try:
            signal.pause()
        finally:
            threading.Event().wait()
    """


def _wait_exit(proc, timeout: float) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return proc.returncode
        time.sleep(0.05)
    return None


def test_a_stuck_hosted_stop_is_ended_and_recorded_cancelled(tmp_path: Path) -> None:
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _stuck_body(sentinel), preamble=GRACE.format(grace=1.0), env=HOSTED,
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code
    (terminus,) = _termini(f)
    assert isinstance(terminus, RunCancelledEvent)
    assert terminus.cause.signal_name == "SIGINT"


def test_a_stop_that_wrote_its_terminus_and_then_hung_writes_no_second(tmp_path: Path) -> None:
    """The normal path writes run_cancelled; the exit then hangs (an atexit join);
    the timer ends the process and finds the terminus already there."""
    sentinel = tmp_path / "ready"
    preamble = GRACE.format(grace=1.0) + (
        "\nimport atexit, threading\natexit.register(lambda: threading.Event().wait())"
    )
    body = f"""
        import signal
        Path({str(sentinel)!r}).write_text("ready")
        signal.pause()
    """
    proc = _spawn_lifecycle_subprocess(tmp_path, body, preamble=preamble, env=HOSTED)
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code
    (terminus,) = _termini(f)
    assert isinstance(terminus, RunCancelledEvent)


def test_a_cli_run_is_not_cut_short(tmp_path: Path) -> None:
    """The CLI keeps a second Ctrl-C as the user's force; no timer decides for them."""
    sentinel = tmp_path / "ready"
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _stuck_body(sentinel), preamble=GRACE.format(grace=0.5),
        env={"_BRISTLENOSE_HOSTED_BY_DESKTOP": ""},
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        assert _wait_exit(proc, 3.0) is None, "a CLI run was ended by the hosted backstop"
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_a_finished_run_leaves_nothing_to_arm(tmp_path: Path) -> None:
    """A hosted signal outside a live run must never arm a timer that ends the process."""
    import bristlenose.run_lifecycle as rl
    from bristlenose.events import KindEnum

    with rl.run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        assert rl._hosted_backstop is not None
    assert rl._hosted_backstop is None


def test_a_backstop_that_cannot_write_still_exits_and_says_why(
    monkeypatch, caplog: pytest.LogCaptureFixture,
) -> None:
    import logging
    import threading

    import bristlenose.run_lifecycle as rl

    exited = threading.Event()
    codes: list[int] = []

    def _fake_exit(code: int) -> None:
        codes.append(code)
        exited.set()

    def _broken(_signum: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(rl, "_HOSTED_STOP_GRACE_S", 0.01)
    monkeypatch.setattr(rl, "_hosted_backstop", _broken)
    monkeypatch.setattr(rl.os, "_exit", _fake_exit)
    with caplog.at_level(logging.ERROR, logger="bristlenose"):
        rl._arm_hosted_backstop(signal.SIGINT)
        assert exited.wait(5)
    assert codes == [128 + signal.SIGINT]
    assert any("backstop" in r.getMessage() for r in caplog.records)


def test_a_writer_stuck_holding_the_lock_does_not_hold_the_exit(tmp_path: Path) -> None:
    """The main thread stuck inside a terminus write (a stalled disk) holds the
    lock; the backstop gives up on writing and still ends the process."""
    sentinel = tmp_path / "ready"
    preamble = GRACE.format(grace=0.5) + (
        "\n_r._BACKSTOP_LOCK_TIMEOUT_S = 0.5\n_r._terminus_lock.acquire()"
    )
    proc = _spawn_lifecycle_subprocess(
        tmp_path, _stuck_body(sentinel), preamble=preamble, env=HOSTED,
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        _wait_for_ready(sentinel)
        proc.send_signal(signal.SIGINT)
        code = _wait_exit(proc, 30.0)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert code == 128 + signal.SIGINT, code
