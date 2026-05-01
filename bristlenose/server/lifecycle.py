"""Sidecar lifecycle: structured exit logging + parent-death detection.

Two independent pieces, both safe to call in any context (CLI or desktop-hosted):

- ``install_exit_logger()`` — registers signal/excepthook/atexit handlers that
  capture *why* the sidecar exited (sigterm, sigint, parent_death,
  uncaught_exception, normal_shutdown) and emit one structured INFO line on
  exit. Always cheap; safe to call once at startup. Lets a tester or
  developer answer "why did it die?" with a single grep.

- ``install_parent_death_watcher()`` — spawns a daemon thread that polls
  ``os.getppid()`` every 2s; if the parent has gone away (process reparented
  to launchd, PID 1 on macOS), records the reason and SIGTERMs self for
  uvicorn's normal shutdown. Sandbox-friendly (own-state observation only;
  no proc enumeration). Only enable when the sidecar is owned by a parent
  whose lifetime should bound the sidecar's — i.e. the desktop host. CLI
  users may legitimately ``nohup`` or otherwise outlive their starting
  shell, so the watcher must NOT be installed there.

See ``desktop/CLAUDE.md`` "Zombie process cleanup" and
``bristlenose/server/CLAUDE.md`` for the design rationale (the host's
sandboxed view cannot enumerate processes; the orphan must self-clean).
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
import sys
import threading
import time
from types import FrameType, TracebackType

logger = logging.getLogger(__name__)

# Sentinel used by ``_set_reason`` to distinguish "still running normally"
# from any exit cause we have observed. First writer wins so we don't
# overwrite an early signal cause with a later atexit fallback.
_INITIAL_REASON = "normal_shutdown"

_state: dict[str, object] = {
    "exit_reason": _INITIAL_REASON,
    "exc_type": None,
    "started_at": time.monotonic(),
    "original_ppid": os.getppid(),
    "installed": False,
    "watcher_started": False,
}


def _set_reason(reason: str, *, exc_type: str | None = None) -> None:
    """First writer wins — so a SIGTERM cause isn't overwritten by atexit.

    Called from the main thread (signal handlers, atexit, excepthook) and
    from the watcher thread (`os.kill` then return). The check-then-set is
    technically racy, but CPython dict assignment is GIL-protected and the
    failure mode is "exit_reason ends up as one valid cause when both
    fired" — harmless. Acceptable for a log line.
    """
    if _state["exit_reason"] == _INITIAL_REASON:
        _state["exit_reason"] = reason
        if exc_type is not None:
            _state["exc_type"] = exc_type


def _log_exit() -> None:
    uptime = time.monotonic() - float(_state["started_at"])  # type: ignore[arg-type]
    current_ppid = os.getppid()
    parts = [
        f"reason={_state['exit_reason']}",
        f"uptime_sec={uptime:.1f}",
        f"original_ppid={_state['original_ppid']}",
        f"current_ppid={current_ppid}",
    ]
    if _state["exc_type"]:
        parts.append(f"exc={_state['exc_type']}")
    logger.info("sidecar_exit %s", " ".join(parts))


def install_exit_logger() -> None:
    """Install signal + excepthook + atexit handlers for structured exit logging.

    Idempotent — safe to call more than once; subsequent calls are no-ops.
    Chains to whatever signal handlers / excepthook existed before, so it
    plays nicely with uvicorn's own SIGTERM/SIGINT handlers.
    """
    if _state["installed"]:
        return
    _state["installed"] = True

    atexit.register(_log_exit)

    prev_sigterm = signal.getsignal(signal.SIGTERM)
    prev_sigint = signal.getsignal(signal.SIGINT)
    prev_excepthook = sys.excepthook

    def _on_sigterm(signum: int, frame: FrameType | None) -> None:
        _set_reason("sigterm")
        if callable(prev_sigterm) and prev_sigterm not in (signal.SIG_DFL, signal.SIG_IGN):
            prev_sigterm(signum, frame)

    def _on_sigint(signum: int, frame: FrameType | None) -> None:
        _set_reason("sigint")
        if callable(prev_sigint) and prev_sigint not in (signal.SIG_DFL, signal.SIG_IGN):
            prev_sigint(signum, frame)

    def _on_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        _set_reason("uncaught_exception", exc_type=exc_type.__name__)
        prev_excepthook(exc_type, exc_value, exc_tb)

    signal.signal(signal.SIGTERM, _on_sigterm)
    signal.signal(signal.SIGINT, _on_sigint)
    sys.excepthook = _on_exception


def install_parent_death_watcher(*, poll_interval_sec: float = 2.0) -> None:
    """Start a background thread that exits the sidecar when its parent dies.

    Polls ``os.getppid()`` every ``poll_interval_sec`` seconds. If the
    current parent PID differs from the one captured at startup (i.e. the
    process has been reparented — on macOS, to launchd / PID 1), records
    the reason and sends ``SIGTERM`` to self so uvicorn shuts down cleanly.

    The thread is a daemon and runs in its own kernel thread, so it is
    not blocked by a busy asyncio event loop or long-running LLM call.

    Idempotent — safe to call more than once; subsequent calls are no-ops.

    Caller responsibility: only install this when the sidecar is hosted
    by a parent whose lifetime should bound the sidecar (e.g. the macOS
    desktop app). Do not install for CLI users — they may legitimately
    ``nohup`` or background the server.
    """
    if _state["watcher_started"]:
        return
    _state["watcher_started"] = True

    original_ppid = int(_state["original_ppid"])  # type: ignore[arg-type]

    def _watch() -> None:
        while True:
            time.sleep(poll_interval_sec)
            current_ppid = os.getppid()
            if current_ppid != original_ppid:
                logger.info(
                    "parent_death detected: original_ppid=%s current_ppid=%s",
                    original_ppid,
                    current_ppid,
                )
                _set_reason("parent_death")
                # SIGTERM ourselves so uvicorn's existing handler runs the
                # graceful-shutdown path. Belt-and-braces: also flip
                # should_exit on any uvicorn server we can reach via the
                # global registry (None at the time of writing — kept as
                # a one-line extension point for future versions).
                os.kill(os.getpid(), signal.SIGTERM)
                return

    threading.Thread(
        target=_watch,
        daemon=True,
        name="parent-death-watcher",
    ).start()
