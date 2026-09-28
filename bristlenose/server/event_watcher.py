"""Tail ``pipeline-events.jsonl`` and dispatch on ``run_completed``.

The serve process imports project data from disk once at startup
(:func:`bristlenose.server.app._import_on_startup`). Anything written by
the pipeline *while serve is running* — i.e. the desktop's PipelineRunner
finishing its job — needs to land in SQLite too. The events log is the
single source of truth for run-level outcomes (see
``docs/design-pipeline-resilience.md``), so we tail it and dispatch a
re-import whenever a new ``run_completed`` arrives.

This module is a thin "noticer". It does not know what an import is —
the caller passes a callback. That keeps the tests trivial (no DB
needed) and keeps re-import dispatch on a single line of glue in
``app.py``.

Ordering note: the pipeline writes intermediate JSON during stages 10–11
and emits ``run_completed`` from ``run_lifecycle.py`` after stage 12
(render). Files are on disk before the event, so a re-import triggered
by ``run_completed`` is safe to read ``intermediate/*.json``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from bristlenose.events import AnyEvent, EventTypeEnum, RunCompletedEvent, read_events

logger = logging.getLogger(__name__)

def _file_identity(path: Path) -> tuple[int, int, int, int] | None:
    """(device, inode, size, mtime_ns) — or None when the file is absent."""
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


async def run_event_watcher(
    events_file: Path | Callable[[], Path],
    on_run_completed: Callable[[RunCompletedEvent], Awaitable[None]],
    *,
    on_change: Callable[[], Awaitable[None]] | None = None,
    poll_interval: float = 1.0,
) -> None:
    """Poll the events log; re-import on each new completion, and say when it changed.

    Two callbacks, deliberately separate:

    * ``on_run_completed`` — re-import. Only a first-seen ``run_completed``
      triggers it; a failed or cancelled run has nothing new to import (pinned
      by ``test_ignores_run_failed``).
    * ``on_change`` — called once at start and on **every** change to the file
      (identity, size or mtime), so the server's *condition* follows the log:
      failures and cancels, progress lines (a heartbeat that lets liveness be
      re-checked), and ``output_backup.restore`` rewriting the file without
      adding a new run. Until 28 Sep 2026 there was no such callback, and a run
      that failed while the serve was up was invisible until restart.

    **Identity, not line count.** Re-import is keyed on ``run_id``: the watcher
    used to dispatch ``events[seen:]``, which misses everything when ``--clean``
    moves the output folder aside and the new run writes a fresh, *shorter* log
    — Re-analyse never reached the report. Runs already on disk at start are
    treated as imported (startup import covered them).

    ``events_file`` may be a callable, re-evaluated on every poll, so a serve
    started before the project's first run follows the output folder into
    existence rather than watching the interview folder forever.

    Runs until cancelled. Callback and read errors are logged, never fatal: a
    watcher that dies takes the condition with it, silently.
    """
    resolve = events_file if callable(events_file) else (lambda: events_file)
    path = resolve()
    imported = _completed_run_ids(_safe_read(path))
    identity = _file_identity(path)
    logger.info("event_watcher started | file=%s baseline=%d", path, len(imported))
    await _call(on_change, "change")

    while True:
        await asyncio.sleep(poll_interval)
        path = resolve()
        current = _file_identity(path)
        if current == identity:
            continue
        identity = current
        await _call(on_change, "change")
        if current is None:
            continue
        for ev in _safe_read(path):
            if ev.event != EventTypeEnum.RUN_COMPLETED or ev.run_id in imported:
                continue
            imported.add(ev.run_id)
            assert isinstance(ev, RunCompletedEvent)
            logger.info("event_watcher saw run_completed | run_id=%s", ev.run_id)
            try:
                await on_run_completed(ev)
            except Exception:
                logger.exception("event_watcher re-import callback failed")


def _safe_read(path: Path) -> list[AnyEvent]:
    try:
        return read_events(path) if path.exists() else []
    except OSError:
        # Moved aside between exists() and read (``--clean``); next poll retries.
        return []


def _completed_run_ids(events: list[AnyEvent]) -> set[str]:
    return {ev.run_id for ev in events if ev.event == EventTypeEnum.RUN_COMPLETED}


async def _call(cb: Callable[[], Awaitable[None]] | None, name: str) -> None:
    if cb is None:
        return
    try:
        await cb()
    except Exception:
        logger.exception("event_watcher %s callback failed", name)
