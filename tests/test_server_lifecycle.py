"""Tests for sidecar lifecycle: structured exit logging + parent-death watcher."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

# Module under test reads/writes module-level state, so each test must reset
# it explicitly. Tests in this file run in the same Python process; tests
# in subprocesses (the parent-death integration test) get a fresh module.
import bristlenose.server.lifecycle as lifecycle


@pytest.fixture(autouse=True)
def _reset_lifecycle_state() -> None:
    """Reset module-level state between tests."""
    lifecycle._state["exit_reason"] = lifecycle._INITIAL_REASON
    lifecycle._state["exc_type"] = None
    lifecycle._state["installed"] = False
    lifecycle._state["watcher_started"] = False
    lifecycle._state["original_ppid"] = os.getppid()
    lifecycle._state["started_at"] = time.monotonic()


def test_set_reason_first_writer_wins() -> None:
    lifecycle._set_reason("sigterm")
    lifecycle._set_reason("parent_death")  # ignored — sigterm was first
    assert lifecycle._state["exit_reason"] == "sigterm"


def test_set_reason_records_exception_type() -> None:
    lifecycle._set_reason("uncaught_exception", exc_type="ImportError")
    assert lifecycle._state["exit_reason"] == "uncaught_exception"
    assert lifecycle._state["exc_type"] == "ImportError"


def test_log_exit_format(caplog: pytest.LogCaptureFixture) -> None:
    lifecycle._set_reason("parent_death")
    with caplog.at_level(logging.INFO, logger="bristlenose.server.lifecycle"):
        lifecycle._log_exit()

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    msg = messages[0]
    assert msg.startswith("sidecar_exit ")
    assert "reason=parent_death" in msg
    assert "uptime_sec=" in msg
    assert "original_ppid=" in msg
    assert "current_ppid=" in msg


def test_log_exit_includes_exception_type(caplog: pytest.LogCaptureFixture) -> None:
    lifecycle._set_reason("uncaught_exception", exc_type="ValueError")
    with caplog.at_level(logging.INFO, logger="bristlenose.server.lifecycle"):
        lifecycle._log_exit()
    assert "exc=ValueError" in caplog.records[0].getMessage()


def test_install_exit_logger_is_idempotent() -> None:
    lifecycle.install_exit_logger()
    assert lifecycle._state["installed"] is True
    # Second call should be a no-op (no double-registration of atexit/signal).
    lifecycle.install_exit_logger()
    assert lifecycle._state["installed"] is True


def test_install_parent_death_watcher_is_idempotent() -> None:
    lifecycle.install_parent_death_watcher(poll_interval_sec=60.0)
    assert lifecycle._state["watcher_started"] is True
    # Second call should be a no-op (no second thread).
    import threading

    watcher_threads_before = sum(
        1 for t in threading.enumerate() if t.name == "parent-death-watcher"
    )
    lifecycle.install_parent_death_watcher(poll_interval_sec=60.0)
    watcher_threads_after = sum(
        1 for t in threading.enumerate() if t.name == "parent-death-watcher"
    )
    assert watcher_threads_after == watcher_threads_before


def test_parent_death_watcher_sigterms_self_when_ppid_changes(tmp_path: Path) -> None:
    """The watcher SIGTERMs its own process the moment getppid() changes.

    Spawned in a subprocess so we can verify SIGTERM delivery via exit
    code without taking down the test runner. The subprocess pre-seeds
    the watcher's "original_ppid" with a fake value that never matches
    the real ppid — so the very first poll fires and the process exits.

    This decouples the test from macOS subprocess-reparenting timing
    (which is finicky inside pytest's process-group setup). The unit
    tests above cover the polling+signaling logic; this confirms the
    SIGTERM path actually delivers.
    """
    script = textwrap.dedent(
        f"""
        import os
        import sys
        import time
        from pathlib import Path

        sys.path.insert(0, {str(Path(__file__).parent.parent)!r})

        import bristlenose.server.lifecycle as lifecycle

        # Pretend our original parent had a PID that doesn't exist now.
        # First poll inside the watcher will see getppid() != this fake
        # value and SIGTERM us.
        lifecycle._state["original_ppid"] = 999999

        lifecycle.install_parent_death_watcher(poll_interval_sec=0.1)

        # Spin briefly; the watcher should kill us within ~200ms.
        for _ in range(50):
            time.sleep(0.1)
        # If we got here, the watcher never fired — exit non-zero.
        sys.exit(2)
        """
    ).strip()

    script_path = tmp_path / "watcher_smoke.py"
    script_path.write_text(script)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        timeout=10,
        capture_output=True,
    )
    # SIGTERM = signal 15 → exit code -15 on POSIX.
    assert result.returncode == -15, (
        f"expected SIGTERM (-15), got {result.returncode}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
