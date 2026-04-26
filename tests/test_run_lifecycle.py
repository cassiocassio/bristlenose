"""Tests for bristlenose.run_lifecycle — Slice 2 of Phase 1f.

Covers the context-manager semantics, PID-file management, stranded-run
recovery, concurrent-run refusal, exception categorisation, and signal
handling. Signal-handling tests use subprocesses (pytest's own SIGINT
handler intercepts otherwise).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from bristlenose.events import (
    CauseCategoryEnum,
    KindEnum,
    RunCancelledEvent,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    _now_iso,
    append_event,
    events_path,
    new_run_id,
    read_events,
)
from bristlenose.run_lifecycle import (
    ConcurrentRunError,
    _is_alive_owned,
    _ps_start_time,
    _read_pid_file,
    _restore_signal_handlers,
    categorise_exception,
    pid_file_path,
    run_lifecycle,
)


@pytest.fixture(autouse=True)
def _reset_signal_handlers():
    """Don't leak our SIGINT/SIGTERM handler installation into other tests."""
    yield
    _restore_signal_handlers()


# ---------------------------------------------------------------------------
# Categoriser
# ---------------------------------------------------------------------------


def test_categorise_disk_full():
    err = OSError(28, "No space left on device")
    cause = categorise_exception(err)
    assert cause.category == CauseCategoryEnum.DISK


def test_categorise_missing_dependency():
    cause = categorise_exception(ImportError("No module named 'anthropic'"))
    assert cause.category == CauseCategoryEnum.MISSING_DEP


def test_categorise_filenotfound_is_unknown_not_missing_dep():
    """FileNotFoundError is too broad for MISSING_DEP — pipelines raise it for
    missing input/audio/people files all the time. Should land in UNKNOWN.
    Only ImportError / ModuleNotFoundError signal a missing tool."""
    cause = categorise_exception(FileNotFoundError("ffmpeg"))
    assert cause.category == CauseCategoryEnum.UNKNOWN


def test_categorise_auth():
    cause = categorise_exception(RuntimeError("401 Unauthorized: invalid api key"))
    assert cause.category == CauseCategoryEnum.AUTH


def test_categorise_quota():
    cause = categorise_exception(RuntimeError("Anthropic 429 rate limit exceeded"))
    assert cause.category == CauseCategoryEnum.QUOTA


def test_categorise_network():
    cause = categorise_exception(RuntimeError("Connection refused; DNS lookup failed"))
    assert cause.category == CauseCategoryEnum.NETWORK


def test_categorise_api_server():
    cause = categorise_exception(RuntimeError("503 Service Unavailable"))
    assert cause.category == CauseCategoryEnum.API_SERVER


def test_categorise_unknown_default():
    cause = categorise_exception(ValueError("something broke"))
    assert cause.category == CauseCategoryEnum.UNKNOWN
    assert cause.message == "something broke"


def test_categorise_message_always_populated():
    """Writer rule: message must be non-empty for non-user_signal causes."""
    cause = categorise_exception(Exception())  # empty
    assert cause.message  # falls back to class name


# ---------------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------------


def test_pid_file_path_under_dot_bristlenose(tmp_path: Path):
    p = pid_file_path(tmp_path)
    assert p.parent.name == ".bristlenose"
    assert p.name == "run.pid"


def test_ps_start_time_for_self_returns_string():
    """_ps_start_time should work for our own PID on macOS + Linux."""
    val = _ps_start_time(os.getpid())
    assert val is not None and len(val) > 0


def test_ps_start_time_for_dead_pid_returns_none():
    """Pick a high PID unlikely to exist."""
    val = _ps_start_time(999_999)
    assert val is None


def test_is_alive_owned_self_pid_matches(tmp_path: Path):
    start = _ps_start_time(os.getpid())
    assert _is_alive_owned({"pid": os.getpid(), "start_time": start}) is True


def test_is_alive_owned_pid_dead_returns_false():
    assert _is_alive_owned({"pid": 999_999, "start_time": "any"}) is False


def test_is_alive_owned_start_time_mismatch_returns_false():
    """Defeats PID reuse — same PID, different start_time → not ours."""
    assert _is_alive_owned({"pid": os.getpid(), "start_time": "Wrong Date"}) is False


# ---------------------------------------------------------------------------
# Lifecycle: clean exit
# ---------------------------------------------------------------------------


def test_lifecycle_clean_exit_writes_started_then_completed(tmp_path: Path):
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False) as handle:
        assert pid_file_path(tmp_path).exists()
        assert handle.run_id  # ULID generated
    events = read_events(events_path(tmp_path))
    assert len(events) == 2
    assert isinstance(events[0], RunStartedEvent)
    assert isinstance(events[1], RunCompletedEvent)
    assert events[0].run_id == events[1].run_id == handle.run_id
    # PID file cleaned up.
    assert not pid_file_path(tmp_path).exists()


def test_lifecycle_writes_pid_file_with_our_pid_and_start_time(tmp_path: Path):
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        data = _read_pid_file(tmp_path)
        assert data is not None
        assert data["pid"] == os.getpid()
        assert data["run_id"]
        assert data["start_time"]


def test_lifecycle_started_event_includes_process_envelope(tmp_path: Path):
    with run_lifecycle(tmp_path, KindEnum.ANALYZE, install_signal_handlers=False):
        pass
    events = read_events(events_path(tmp_path))
    started = events[0]
    assert isinstance(started, RunStartedEvent)
    assert started.process.pid == os.getpid()
    assert started.process.python_version
    assert started.process.os
    assert started.kind == KindEnum.ANALYZE


# ---------------------------------------------------------------------------
# Lifecycle: exception paths
# ---------------------------------------------------------------------------


def test_lifecycle_arbitrary_exception_writes_run_failed(tmp_path: Path):
    with pytest.raises(RuntimeError, match="boom"):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise RuntimeError("boom: 401 Unauthorized")
    events = read_events(events_path(tmp_path))
    assert isinstance(events[-1], RunFailedEvent)
    assert events[-1].cause.category == CauseCategoryEnum.AUTH
    assert "Unauthorized" in events[-1].cause.message


def test_lifecycle_keyboard_interrupt_writes_run_cancelled(tmp_path: Path):
    with pytest.raises(KeyboardInterrupt):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise KeyboardInterrupt()
    events = read_events(events_path(tmp_path))
    assert isinstance(events[-1], RunCancelledEvent)
    assert events[-1].cause.category == CauseCategoryEnum.USER_SIGNAL
    # signal defaults to SIGINT when no handler captured one.
    assert events[-1].cause.signal_name in ("SIGINT", "SIGTERM")


def test_lifecycle_systemexit_zero_writes_completed(tmp_path: Path):
    with pytest.raises(SystemExit):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise SystemExit(0)
    events = read_events(events_path(tmp_path))
    assert isinstance(events[-1], RunCompletedEvent)


def test_lifecycle_systemexit_nonzero_writes_failed(tmp_path: Path):
    with pytest.raises(SystemExit):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            raise SystemExit(2)
    events = read_events(events_path(tmp_path))
    assert isinstance(events[-1], RunFailedEvent)
    assert events[-1].cause.exit_code == 2


def test_lifecycle_pid_file_removed_even_on_exception(tmp_path: Path):
    with pytest.raises(RuntimeError):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            assert pid_file_path(tmp_path).exists()
            raise RuntimeError("boom")
    assert not pid_file_path(tmp_path).exists()


# ---------------------------------------------------------------------------
# Stranded-run reconciliation
# ---------------------------------------------------------------------------


def test_stranded_run_started_synthesises_failed_on_next_start(tmp_path: Path):
    """A prior run that crashed without a terminus → synthesised run_failed appended."""
    # Simulate a crashed prior run: one run_started, no terminus.
    f = events_path(tmp_path)
    from bristlenose.events import Process

    started = RunStartedEvent(
        ts=_now_iso(),
        run_id=new_run_id(),
        kind=KindEnum.RUN,
        started_at=_now_iso(),
        process=Process(
            pid=99999, start_time="never", hostname="h", user="u",
            bristlenose_version="0", python_version="3", os="x",
        ),
    )
    append_event(f, started)

    # No PID file from the prior crash. Next lifecycle should reconcile.
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        pass

    events = read_events(f)
    # Expect: prior_started, synth_failed, new_started, new_completed.
    assert len(events) == 4
    assert isinstance(events[0], RunStartedEvent)
    assert isinstance(events[1], RunFailedEvent)
    assert events[1].run_id == started.run_id  # synth correlated
    assert events[1].cause.category == CauseCategoryEnum.UNKNOWN
    assert isinstance(events[2], RunStartedEvent)
    assert isinstance(events[3], RunCompletedEvent)


def test_no_reconciliation_when_log_ends_in_terminus(tmp_path: Path):
    """If prior run terminated cleanly, no synthesised event."""
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        pass
    n_after_first = len(read_events(events_path(tmp_path)))
    assert n_after_first == 2  # started + completed
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        pass
    events = read_events(events_path(tmp_path))
    assert len(events) == 4  # +started +completed, no synth


def test_stale_pid_file_with_dead_pid_does_not_refuse(tmp_path: Path):
    """PID file from a long-dead process should not block a new run."""
    pid_file_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    pid_file_path(tmp_path).write_text(json.dumps({
        "pid": 999_999, "start_time": "Stale", "run_id": "OLD",
    }))
    # Should run cleanly — no ConcurrentRunError.
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        pass


def test_pid_file_with_reused_pid_but_mismatched_start_time_does_not_refuse(tmp_path: Path):
    """PID belongs to a live unrelated process; start_time mismatches → not ours."""
    pid_file_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    pid_file_path(tmp_path).write_text(json.dumps({
        "pid": os.getpid(),  # real, alive
        "start_time": "Definitely Not Our Start Time",
        "run_id": "X",
    }))
    with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
        pass


# ---------------------------------------------------------------------------
# Concurrent-run refusal
# ---------------------------------------------------------------------------


def test_concurrent_run_refused_when_pid_file_alive(tmp_path: Path):
    """If a live process owns the PID file, second lifecycle refuses."""
    # Write PID file pointing at our own live PID with our real start_time.
    real_start = _ps_start_time(os.getpid())
    pid_file_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    pid_file_path(tmp_path).write_text(json.dumps({
        "pid": os.getpid(), "start_time": real_start, "run_id": "OTHER",
    }))
    with pytest.raises(ConcurrentRunError, match="already in progress"):
        with run_lifecycle(tmp_path, KindEnum.RUN, install_signal_handlers=False):
            pass


# ---------------------------------------------------------------------------
# Signal handling — subprocess tests (pytest intercepts in-process SIGINT)
# ---------------------------------------------------------------------------


def _spawn_lifecycle_subprocess(tmp_path: Path, body: str) -> subprocess.Popen:
    """Spawn a Python subprocess that enters run_lifecycle, then runs `body`."""
    repo_root = Path(__file__).parent.parent
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(repo_root)!r})
        from pathlib import Path
        from bristlenose.events import KindEnum
        from bristlenose.run_lifecycle import run_lifecycle

        with run_lifecycle(Path({str(tmp_path)!r}), KindEnum.RUN):
            {body}
    """)
    return subprocess.Popen(
        [sys.executable, "-c", script],
        env={**os.environ},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _wait_for_event(
    events_file: Path,
    predicate,
    *,
    timeout: float = 30.0,
) -> bool:
    """Poll the events file until `predicate(event)` matches, or timeout.

    Generous deadline because:
    - The subprocess pays cold-import cost (Pydantic, pricing, etc.) before
      installing handlers — slow CI runners take a few seconds even idle.
    - After SIGINT/SIGTERM, the lifecycle wrapper has to catch
      KeyboardInterrupt, build the Cause, and fsync the line. On Python
      3.10 + Linux ubuntu-latest under full-matrix load this can exceed
      the 15s `proc.wait` timeout we used to use.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if events_file.exists():
            for event in read_events(events_file):
                if predicate(event):
                    return True
        time.sleep(0.05)
    return False


def _wait_for_run_started(events_file: Path, *, timeout: float = 30.0) -> None:
    if not _wait_for_event(
        events_file, lambda e: isinstance(e, RunStartedEvent), timeout=timeout,
    ):
        raise AssertionError(
            f"Subprocess never wrote run_started within {timeout}s — likely "
            "import-time crash before handler install.",
        )


def test_subprocess_sigint_writes_run_cancelled(tmp_path: Path):
    proc = _spawn_lifecycle_subprocess(
        tmp_path,
        body="import time\n            time.sleep(60)",
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        proc.send_signal(signal.SIGINT)
        # Poll the events file rather than wait for proc exit — proc cleanup
        # can take longer than the cancel-event flush on slow CI runners
        # (ubuntu-latest + Python 3.10 has been observed > 15s under load).
        landed = _wait_for_event(
            f,
            lambda e: (
                isinstance(e, RunCancelledEvent)
                and e.cause.category == CauseCategoryEnum.USER_SIGNAL
                and e.cause.signal == int(signal.SIGINT)
                and e.cause.signal_name == "SIGINT"
            ),
            timeout=30.0,
        )
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert landed, (
        "RunCancelledEvent (SIGINT) never landed within 30s of sending the signal"
    )


def test_subprocess_clean_exit_writes_run_completed(tmp_path: Path):
    proc = _spawn_lifecycle_subprocess(tmp_path, body="pass")
    proc.wait(timeout=30)
    assert proc.returncode == 0
    events = read_events(events_path(tmp_path))
    assert any(isinstance(e, RunCompletedEvent) for e in events)


def test_subprocess_sigterm_writes_run_cancelled(tmp_path: Path):
    proc = _spawn_lifecycle_subprocess(
        tmp_path,
        body="import time\n            time.sleep(60)",
    )
    f = events_path(tmp_path)
    try:
        _wait_for_run_started(f)
        proc.send_signal(signal.SIGTERM)
        landed = _wait_for_event(
            f,
            lambda e: (
                isinstance(e, RunCancelledEvent)
                and e.cause.signal_name == "SIGTERM"
            ),
            timeout=30.0,
        )
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    assert landed, (
        "RunCancelledEvent (SIGTERM) never landed within 30s of sending the signal"
    )
