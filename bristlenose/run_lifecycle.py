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

import ctypes
import ctypes.util
import json
import logging
import os
import platform
import re
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from bristlenose import __version__ as _bristlenose_version
from bristlenose.cost import RunCost
from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    PipelineAbandonedError,
    PipelineSummary,
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
from bristlenose.llm import telemetry

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


# struct proc_bsdinfo from <sys/proc_info.h>. Only the start_t* fields at the
# tail are read, but the layout up to that point must match exactly.
class _ProcBsdInfo(ctypes.Structure):
    _fields_ = [
        ("pbi_flags", ctypes.c_uint32),
        ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32),
        ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32),
        ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32),
        ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32),
        ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32),
        ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16),
        ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32),
        ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32),
        ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32),
        ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64),
        ("pbi_start_tvusec", ctypes.c_uint64),
    ]


_PROC_PIDTBSDINFO = 3  # from <sys/proc_info.h>
_libproc: ctypes.CDLL | None = None


def _load_libproc() -> ctypes.CDLL | None:
    global _libproc
    if _libproc is not None:
        return _libproc
    path = ctypes.util.find_library("proc")
    if path is None:
        return None
    lib = ctypes.CDLL(path, use_errno=True)
    lib.proc_pidinfo.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
        ctypes.c_void_p, ctypes.c_int,
    ]
    lib.proc_pidinfo.restype = ctypes.c_int
    _libproc = lib
    return lib


def _ps_start_time(pid: int) -> str | None:
    """Return an opaque, stable-per-PID start-time token, or None.

    On macOS, queries libproc ``proc_pidinfo(PROC_PIDTBSDINFO)`` for
    ``pbi_start_tvsec.pbi_start_tvusec`` — the same value Activity
    Monitor reads. Avoids ``/bin/ps``, which is blocked under macOS
    App Sandbox at exec time (the bundled desktop sidecar runs sandboxed).

    On Linux, falls back to ``ps -o lstart=`` — POSIX-portable, no
    sandbox concerns there.

    Caller contract: the string is opaque and only ever compared for
    equality across two reads of the same PID. Format is **not** stable
    across platforms; callers must never parse it.

    Returns None if the PID is dead, libproc isn't loadable, or the
    syscall fails.
    """
    if sys.platform == "darwin":
        lib = _load_libproc()
        if lib is None:
            return None
        info = _ProcBsdInfo()
        n = lib.proc_pidinfo(
            pid, _PROC_PIDTBSDINFO, 0,
            ctypes.byref(info), ctypes.sizeof(info),
        )
        if n != ctypes.sizeof(info):
            return None
        return f"{info.pbi_start_tvsec}.{info.pbi_start_tvusec}"

    # Non-Darwin (Linux, etc.) — keep the legacy /bin/ps subprocess. No
    # sandbox blocker on these platforms, and parsing /proc/<pid>/stat
    # field 22 is a separate code path that's only worth its weight if
    # we ever ship a sandboxed Linux build.
    try:
        out = subprocess.run(
            ["/bin/ps", "-o", "lstart=", "-p", str(pid)],
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
    """Atomic-write ``run.pid`` with our (pid, start_time, run_id).

    Mode 0o600 + O_NOFOLLOW + O_TRUNC: refuses to follow a symlink-attacked
    target and limits readability to the project's owner. Defensive default
    even though the project dir lives inside the user's interview folder.
    """
    path = pid_file_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "start_time": start_time,
        "run_id": run_id,
    }
    tmp = path.with_suffix(".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        os.write(fd, json.dumps(payload).encode("utf-8"))
    finally:
        os.close(fd)
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


_AUTH_RE = re.compile(r"\b(unauthorized|401|invalid api key|authentication)\b")
_QUOTA_RE = re.compile(r"\b(rate limit|quota|429|credit)\b")
_NETWORK_RE = re.compile(r"\b(connection|timeout|dns|unreachable)\b")
_API_SERVER_RE = re.compile(r"\b(internal server|500|502|503|504)\b")

# Filesystem path token — any run of non-whitespace, non-quote characters
# that starts with `/` and has at least one more `/` so we don't eat an
# isolated leading slash. Matches both POSIX absolute paths and the
# embedded-in-quoted-message variants (`'/Users/.../jane.wav'`). Replaced
# wholesale by `<path>` before building the Cause — the events log is a
# re-identification key (see CLAUDE.md alongside `pii_summary.txt`,
# `llm-calls.jsonl`); category + class name + session_id retain the
# diagnostic value without persisting filenames that may carry participant
# names.
_PATH_RE = re.compile(r"/[^\s'\"<>]*/[^\s'\"<>]*")


def _sanitise_message(msg: str) -> str:
    """Replace absolute filesystem paths in ``msg`` with a literal ``<path>``.

    Run on every exception message before it lands in a ``Cause`` so audio
    filenames (often participant-bearing — `interview-jane-doe.wav`) don't
    leak into ``pipeline-events.jsonl``.
    """
    return _PATH_RE.sub("<path>", msg)


def categorise_exception(exc: BaseException) -> Cause:
    """Best-effort mapping of an exception to a structured Cause.

    Conservative: most things land in ``unknown`` with ``str(exc)`` as the
    message. Refine as new failure modes warrant. Provider-specific HTTP
    status codes deserve their own categoriser pass — out of scope here.

    Substring matchers are anchored with `\\b` word boundaries to avoid
    false positives — `"credit"` must not match `"credentials"`,
    `"authentication"` must not match an unrelated `OSError` quoting it.

    The message is run through ``_sanitise_message`` before being attached
    to the Cause so absolute filesystem paths never reach the events log.
    Categorisation runs on the *raw* message so `[Errno 2] '/usr/bin/foo'`
    still carries the slash needed for the MISSING_BINARY path-presence
    check; the sanitised string only feeds the persisted ``cause.message``.
    """
    raw_msg = str(exc) or exc.__class__.__name__
    msg = _sanitise_message(raw_msg)
    name = exc.__class__.__name__.lower()
    haystack = f"{name} {raw_msg}".lower()

    # Disk space.
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:  # ENOSPC
        return Cause(category=CauseCategoryEnum.DISK, message=msg)

    # Missing dependency — Python import failure only. FileNotFoundError is
    # NOT a missing dep: pipelines raise it for missing input/audio/people
    # files all the time (would mislead the user with "tool not installed").
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return Cause(category=CauseCategoryEnum.MISSING_DEP, message=msg)

    # Missing binary — bare-name shellout failure. Filename without a path
    # separator means the caller passed a bare name and PATH resolution
    # failed (today's ffmpeg-under-sandbox bug). Slash-containing filenames
    # are different (file genuinely missing on disk) and fall through.
    if isinstance(exc, FileNotFoundError):
        fn = exc.filename
        if isinstance(fn, str) and fn and "/" not in fn:
            return Cause(category=CauseCategoryEnum.MISSING_BINARY, message=msg)

    if _AUTH_RE.search(haystack):
        return Cause(category=CauseCategoryEnum.AUTH, message=msg)

    if _QUOTA_RE.search(haystack):
        return Cause(category=CauseCategoryEnum.QUOTA, message=msg)

    if _NETWORK_RE.search(haystack):
        return Cause(category=CauseCategoryEnum.NETWORK, message=msg)

    if _API_SERVER_RE.search(haystack):
        return Cause(category=CauseCategoryEnum.API_SERVER, message=msg)

    return Cause(category=CauseCategoryEnum.UNKNOWN, message=msg)


# ---------------------------------------------------------------------------
# Public API: run_lifecycle context manager
# ---------------------------------------------------------------------------


class ConcurrentRunError(RuntimeError):
    """Raised when another live run already owns the project's PID file."""


class RunHandle:
    """Handle yielded by ``run_lifecycle`` — lets the CLI attach cost data.

    Mutable because the cost is only known after the pipeline returns.
    Stays ``None`` for runs that didn't make LLM calls (transcribe-only
    with local Whisper) — that's fine; the terminus event records None.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.cost: RunCost | None = None
        self.summary: PipelineSummary | None = None

    def set_cost(self, cost: RunCost | None) -> None:
        """Attach the cost totals; stamped onto the terminus event."""
        self.cost = cost

    def set_summary(self, summary: PipelineSummary | None) -> None:
        """Attach the per-stage outcome rollup; stamped onto the terminus event."""
        self.summary = summary


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
            message="Analysis stopped unexpectedly.",
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
) -> Iterator[RunHandle]:
    """Wrap a CLI command body with run-level event-log discipline.

    Yields a ``RunHandle``. Use ``handle.set_cost(...)`` after the
    pipeline returns to stamp token + USD totals onto the terminus event.

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

    log.info("run_started run_id=%s kind=%s", run_id, kind.value)

    handle = RunHandle(run_id)

    def _terminus_kwargs() -> dict[str, object]:
        """Render handle-attached cost + summary as terminus-event kwargs."""
        out: dict[str, object] = {}
        if handle.cost is not None:
            out["input_tokens"] = handle.cost.input_tokens
            out["output_tokens"] = handle.cost.output_tokens
            out["cost_usd_estimate"] = handle.cost.cost_usd_estimate
            out["price_table_version"] = handle.cost.price_table_version
        if handle.summary is not None:
            out["summary"] = handle.summary
        return out

    telemetry_tokens = telemetry.set_run_context(run_id, output_dir / ".bristlenose")

    try:
        try:
            yield handle
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
                ended_at=ended, cause=cancel_cause, **_terminus_kwargs(),
            ))
            log.info("run_cancelled run_id=%s signal=%s", run_id, cancel_cause.signal_name)
            telemetry.trim_run_terminus()
            _remove_pid_file(output_dir)
            raise
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
            ended = _now_iso()
            if code == 0:
                append_event(events_file, RunCompletedEvent(
                    ts=ended, run_id=run_id, kind=kind, started_at=started_at,
                    ended_at=ended, **_terminus_kwargs(),
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
                    **_terminus_kwargs(),
                ))
                log.info("run_failed run_id=%s exit_code=%s", run_id, code)
            telemetry.trim_run_terminus()
            _remove_pid_file(output_dir)
            raise
        except PipelineAbandonedError as exc:
            # Abandon path: stage produced no usable data. The exception
            # carries its own cause + accumulated summary; prefer those over
            # the handle's (the handle may not have been populated yet).
            ended = _now_iso()
            kw = _terminus_kwargs()
            kw["summary"] = exc.summary
            append_event(events_file, RunFailedEvent(
                ts=ended, run_id=run_id, kind=kind, started_at=started_at,
                ended_at=ended, cause=exc.cause, **kw,
            ))
            log.error(
                "run_abandoned run_id=%s category=%s",
                run_id, exc.cause.category.value,
            )
            telemetry.trim_run_terminus()
            _remove_pid_file(output_dir)
            raise
        except BaseException as exc:
            ended = _now_iso()
            cause = categorise_exception(exc)
            append_event(events_file, RunFailedEvent(
                ts=ended, run_id=run_id, kind=kind, started_at=started_at,
                ended_at=ended, cause=cause, **_terminus_kwargs(),
            ))
            log.info("run_failed run_id=%s category=%s", run_id, cause.category.value)
            telemetry.trim_run_terminus()
            _remove_pid_file(output_dir)
            raise
        else:
            ended = _now_iso()
            append_event(events_file, RunCompletedEvent(
                ts=ended, run_id=run_id, kind=kind, started_at=started_at,
                ended_at=ended, **_terminus_kwargs(),
            ))
            log.info("run_completed run_id=%s", run_id)
            telemetry.trim_run_terminus()
            _remove_pid_file(output_dir)
    finally:
        telemetry.reset_run_context(telemetry_tokens)
