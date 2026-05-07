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

from bristlenose.events import EventTypeEnum, read_events

logger = logging.getLogger(__name__)


async def run_event_watcher(
    events_file: Path,
    on_run_completed: Callable[[], Awaitable[None]],
    *,
    poll_interval: float = 1.0,
) -> None:
    """Poll ``events_file`` and call ``on_run_completed`` on each new terminus.

    Establishes a baseline event count at start so events written before
    the watcher started (already covered by startup-time import) are not
    re-dispatched. Only ``run_completed`` triggers the callback;
    ``run_failed`` / ``run_cancelled`` are ignored — there's nothing new
    to import.

    Runs until cancelled. Exceptions in the callback are logged but do
    not stop the watcher — a transient import failure shouldn't blind
    us to the next run.
    """
    seen = len(read_events(events_file)) if events_file.exists() else 0
    logger.info(
        "event_watcher started | file=%s baseline=%d", events_file, seen,
    )

    while True:
        await asyncio.sleep(poll_interval)
        if not events_file.exists():
            continue

        events = read_events(events_file)
        if len(events) <= seen:
            continue

        new_events = events[seen:]
        seen = len(events)

        for ev in new_events:
            if ev.event == EventTypeEnum.RUN_COMPLETED:
                logger.info(
                    "event_watcher saw run_completed | run_id=%s",
                    getattr(ev, "run_id", "?"),
                )
                try:
                    await on_run_completed()
                except Exception:
                    logger.exception(
                        "event_watcher callback failed — "
                        "next run_completed will retry",
                    )
