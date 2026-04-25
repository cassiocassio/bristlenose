"""Run lifecycle — wires the events log into CLI commands (Slice 2 of Phase 1f).

Provides ``run_lifecycle()``, a context manager that wraps a CLI command
body so that:

- A ``RunStartedEvent`` is appended on entry, with a process diagnostics
  envelope and a Python-side PID file at ``<output_dir>/.bristlenose/run.pid``.
- Stranded ``run_started`` events from prior crashed runs are reconciled
  by appending a synthesised ``RunFailedEvent`` (cause.category=unknown).
- A live concurrent run is refused with a clear error.
- A clean exit appends ``RunCompletedEvent``.
- ``KeyboardInterrupt`` (SIGINT/SIGTERM via the installed handler) appends
  ``RunCancelledEvent`` with ``cause.category=user_signal``.
- Other exceptions append ``RunFailedEvent`` with a categorised cause.

The signal handler **records** the signal number and re-raises
``KeyboardInterrupt`` — it does not write from the handler. The wrapper
catches the resulting exception at the outer scope and writes the event
from there. This is the "flag-and-flush" pattern from the design doc,
in its minimal form. A future slice may push checkpoint-based
cancellation into the pipeline itself for finer-grained mid-stage stop.

See ``docs/design-pipeline-resilience.md`` §"Run outcomes and intent"
and §"Open decisions".
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import platform
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from bristlenose import __version__ as _bristlenose_version
from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    Process,
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

PID_FILENAME = "run.pid"

log = logging.getLogger("bristlenose")


# ---------------------------------------------------------------------------
# Module-level signal-tracking state
# ---------------------------------------------------------------------------
# The signal handler records the most recent caught signal so the wrapper
# can stamp the right `signal` / `signal_name` on the cancel event. Module
# state is fine — there is one CLI process per run.

_caught_signal: int | None = None
_prev_handlers: dict[int, object] = {}


def _signal_handler(signum: int, frame: object) -> None:  # noqa: ARG001
    """Record the signal and re-raise KeyboardInterrupt for the main loop.

    Keeps the existing fast-cancel UX (Whisper / asyncio loops break on
    KeyboardInterrupt). Also satisfies the design-doc rule that we don't
    write from the handler — the wrapper handles that on the way out.
    """
    global _caught_signal
    _caught_signal = signum
    raise KeyboardInterrupt()


def _install_signal_handlers() -> None:
    """Install our SIGINT / SIGTERM handlers. Idempotent."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        if sig not in _prev_handlers:
            _prev_handlers[sig] = signal.signal(sig, _signal_handler)


def _restore_signal_handlers() -> None:
    """Restore previous handlers (used in tests; harmless in CLI)."""
    global _caught_signal
    for sig, prev in list(_prev_handlers.items()):
        try:
            signal.signal(sig, prev)  # type: ignore[arg-type]
        except (ValueError, OSError):
            pass
    _prev_handlers.clear()
    _caught_signal = None


# ---------------------------------------------------------------------------
# PID file helpers
# ---------------------------------------------------------------------------


def pid_file_path(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / PID_FILENAME


def _ps_start_time(pid: int) -> str | None:
    """Return the OS-reported process start time for `pid`, or None.

    Uses ``ps -o lstart=`` which works on macOS BSD and Linux GNU. The
    output format is human-readable (e.g. ``Fri Apr 25 09:00:00 2026``).
    We treat the string as opaque — equality comparison only.
    """
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    val = out.stdout.strip()
    return val or None


def _write_pid_file(output_dir: Path, run_id: str, start_time: str) -> Path:
    """Atomic-write ``run.pid`` with our (pid, start_time, run_id)."""
    path = pid_file_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "start_time": start_time,
        "run_id": run_id,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)
    return path


def _read_pid_file(output_dir: Path) -> dict | None:
    path = pid_file_path(output_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _remove_pid_file(output_dir: Path) -> None:
    try:
        pid_file_path(output_dir).unlink()
    except FileNotFoundError:
        pass


def _is_alive_owned(pid_file: dict) -> bool:
    """True iff the recorded (pid, start_time) matches a live process."""
    pid = pid_file.get("pid")
    recorded_start = pid_file.get("start_time")
    if not isinstance(pid, int) or not isinstance(recorded_start, str):
        return False
    actual_start = _ps_start_time(pid)
    if actual_start is None:
        return False  # PID dead.
    return actual_start == recorded_start


# ---------------------------------------------------------------------------
# Exception → Cause categoriser
# ---------------------------------------------------------------------------


def categorise_exception(exc: BaseException) -> Cause:
    """Best-effort mapping of an exception to a structured Cause.

    Conservative: most things land in ``unknown`` with ``str(exc)`` as the
    message. Refine as new failure modes warrant. Provider-specific HTTP
    status codes deserve their own categoriser pass — out of scope here.
    """
    msg = str(exc) or exc.__class__.__name__
    name = exc.__class__.__name__.lower()
    haystack = f"{name} {msg}".lower()

    # Disk space.
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:  # ENOSPC
        return Cause(category=CauseCategoryEnum.DISK, message=msg)

    # Missing dependency.
    if isinstance(exc, (ImportError, ModuleNotFoundError, FileNotFoundError)):
        # FileNotFoundError on a binary lookup (ffmpeg, whisper) is also missing-dep.
        return Cause(category=CauseCategoryEnum.MISSING_DEP, message=msg)

    # Auth-shaped errors.
    if any(tok in haystack for tok in ("unauthorized", "401", "invalid api key", "authentication")):
        return Cause(category=CauseCategoryEnum.AUTH, message=msg)

    # Quota / rate limit.
    if any(tok in haystack for tok in ("rate limit", "quota", "429", "credit")):
        return Cause(category=CauseCategoryEnum.QUOTA, message=msg)

    # Network.
    if any(tok in haystack for tok in ("connection", "timeout", "dns", "unreachable")):
        return Cause(category=CauseCategoryEnum.NETWORK, message=msg)

    # 5xx-ish.
    if any(tok in haystack for tok in ("internal server", "500", "502", "503", "504")):
        return Cause(category=CauseCategoryEnum.API_SERVER, message=msg)

    return Cause(category=CauseCategoryEnum.UNKNOWN, message=msg)


# ---------------------------------------------------------------------------
# Public API: run_lifecycle context manager
# ---------------------------------------------------------------------------


class ConcurrentRunError(RuntimeError):
    """Raised when another live run already owns the project's PID file."""


def _process_envelope(start_time: str) -> Process:
    return Process(
        pid=os.getpid(),
        start_time=start_time,
        hostname=socket.gethostname(),
        user=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
        bristlenose_version=_bristlenose_version,
        python_version=sys.version.split()[0],
        os=f"{platform.system().lower()}-{platform.machine().lower()}",
    )


def _reconcile_stranded_run(events_file: Path) -> None:
    """If the events log tail is a stranded run_started, append synthesised run_failed.

    Append-only — never rewrites. Preserves prior run_id / kind / started_at
    so the synthesised terminus correlates back to its start.
    """
    events = read_events(events_file)
    if not events:
        return
    tail = events[-1]
    if not isinstance(tail, RunStartedEvent):
        return
    now = _now_iso()
    synth = RunFailedEvent(
        ts=now,
        run_id=tail.run_id,
        kind=tail.kind,
        started_at=tail.started_at,
        ended_at=now,
        cause=Cause(
            category=CauseCategoryEnum.UNKNOWN,
            message="Process exited without writing a terminus event",
        ),
    )
    append_event(events_file, synth)
    log.info(
        "events.recover_stranded run_id=%s kind=%s",
        tail.run_id, tail.kind.value,
    )


@contextmanager
def run_lifecycle(
    output_dir: Path,
    kind: KindEnum,
    *,
    install_signal_handlers: bool = True,
) -> Iterator[str]:
    """Wrap a CLI command body with run-level event-log discipline.

    Yields the run_id (for callers that want to log it).

    Behaviour summary:
        - Refuses if another live run owns the project (PID file +
          start-time match). Raises ``ConcurrentRunError``.
        - Reconciles a stranded prior ``run_started`` (PID dead or
          start-time mismatch) by appending a synthesised ``run_failed``
          before starting the new run.
        - Appends ``run_started`` and writes the PID file.
        - On clean exit: appends ``run_completed``, removes PID file.
        - On ``KeyboardInterrupt`` / ``SystemExit(0)``: cancelled or
          completed as appropriate, removes PID file.
        - On other exceptions: appends ``run_failed`` with categorised
          cause, removes PID file, re-raises.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".bristlenose").mkdir(parents=True, exist_ok=True)

    events_file = events_path(output_dir)

    # --- Concurrent-run check.
    existing = _read_pid_file(output_dir)
    if existing is not None and _is_alive_owned(existing):
        raise ConcurrentRunError(
            f"Another run is already in progress for this project "
            f"(pid={existing.get('pid')}, run_id={existing.get('run_id')}). "
            f"Delete {pid_file_path(output_dir)} if you are sure no run is active.",
        )

    # --- Stranded prior run reconciliation.
    _reconcile_stranded_run(events_file)
    if existing is not None:
        # Stale PID file — clean up before writing our own.
        _remove_pid_file(output_dir)

    # --- Start.
    if install_signal_handlers:
        _install_signal_handlers()

    run_id = new_run_id()
    started_at = _now_iso()
    proc_start_time = _ps_start_time(os.getpid()) or started_at
    proc = _process_envelope(proc_start_time)

    started_event = RunStartedEvent(
        ts=started_at,
        run_id=run_id,
        kind=kind,
        started_at=started_at,
        process=proc,
    )
    append_event(events_file, started_event)
    _write_pid_file(output_dir, run_id, proc_start_time)

    # Best-effort cleanup at interpreter exit (defence in depth).
    atexit.register(_remove_pid_file, output_dir)

    log.info("run_started run_id=%s kind=%s", run_id, kind.value)

    try:
        yield run_id
    except KeyboardInterrupt as exc:
        sig = _caught_signal or signal.SIGINT
        ended = _now_iso()
        cancel_cause = Cause(
            category=CauseCategoryEnum.USER_SIGNAL,
            signal=int(sig),
            signal_name=signal.Signals(sig).name,
            message=str(exc) or None,
        )
        append_event(events_file, RunCancelledEvent(
            ts=ended, run_id=run_id, kind=kind, started_at=started_at,
            ended_at=ended, cause=cancel_cause,
        ))
        log.info("run_cancelled run_id=%s signal=%s", run_id, cancel_cause.signal_name)
        _remove_pid_file(output_dir)
        raise
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
        ended = _now_iso()
        if code == 0:
            append_event(events_file, RunCompletedEvent(
                ts=ended, run_id=run_id, kind=kind, started_at=started_at,
                ended_at=ended,
            ))
            log.info("run_completed run_id=%s exit_code=0", run_id)
        else:
            append_event(events_file, RunFailedEvent(
                ts=ended, run_id=run_id, kind=kind, started_at=started_at,
                ended_at=ended,
                cause=Cause(
                    category=CauseCategoryEnum.UNKNOWN,
                    message=f"CLI exited with code {code}",
                    exit_code=code,
                ),
            ))
            log.info("run_failed run_id=%s exit_code=%s", run_id, code)
        _remove_pid_file(output_dir)
        raise
    except BaseException as exc:
        ended = _now_iso()
        cause = categorise_exception(exc)
        append_event(events_file, RunFailedEvent(
            ts=ended, run_id=run_id, kind=kind, started_at=started_at,
            ended_at=ended, cause=cause,
        ))
        log.info("run_failed run_id=%s category=%s", run_id, cause.category.value)
        _remove_pid_file(output_dir)
        raise
    else:
        ended = _now_iso()
        append_event(events_file, RunCompletedEvent(
            ts=ended, run_id=run_id, kind=kind, started_at=started_at,
            ended_at=ended,
        ))
        log.info("run_completed run_id=%s", run_id)
        _remove_pid_file(output_dir)
