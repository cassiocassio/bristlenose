"""When a quote starts counting, AutoCode codes it (ruling 4, 30 Oct 2026).

A quote that was hidden, or whose participant was recoded as a moderator or
observer, when a codebook ran was not sent: it did not count. Unhide it, or undo
the recode, and it counts, so it is owed (``autocode.owed_quotes``). This module
is the trigger: it schedules the existing catch-up
(``autocode.reapply_to_new_quotes``) for every codebook with something owed, at
the stored cutoff, with no review, and the tags appear.

**Debounced.** A curating researcher unhides in bursts, and one call re-sends the
whole codebook (4-10k tokens) however few quotes ride in it, so each trigger
restarts a trailing timer (``DEBOUNCE_S``), capped at ``CAP_S`` from the first
trigger, and ONE pass per codebook then codes everything owed, 25 to a batch.
What is owed is derived from the register at fire time, so the queue is not
persisted (quitting during the wait loses nothing; the quotes are still owed) and
a quote re-hidden during the wait is skipped. Nothing here runs at serve start:
owed quotes alone spend nothing.

**Quiet failure.** A pass that cannot run leaves its quotes owed and says nothing
new: no dialog, no retry. The job's existing "Tagging failed" chip shows the
first time. While the last attempt failed for a key or credit reason
(``invalid_key``, ``out_of_credit``) further triggers do not call the provider
again until the key or provider state has changed, then one pass codes the whole
backlog. "State" is the provider, the model and whether a key is set, never the
key: no key value is read, kept or logged here. It is held in this process, so a
serve restart (which the Mac does when a key is saved) is a change too. A
provider with no key is not tried at all (as ``app.py`` skips the run's re-apply)
and writes nothing to the job.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

#: A trailing timer restarted by each trigger, and the longest a burst may keep
#: pushing the pass back. Module constants so a test can shrink them.
DEBOUNCE_S = 10.0
CAP_S = 60.0

#: The failure kinds that a retry cannot mend: fix the key or add credit first.
#: Rate limits, outages and a stopped pass are not here: they pass.
KEY_OR_CREDIT_KINDS = frozenset({"invalid_key", "out_of_credit"})


class _Wait:
    """One project's pending pass: when its first trigger arrived, and its timer."""

    def __init__(self, first: float) -> None:
        self.first = first
        self.handle: asyncio.TimerHandle | None = None


_WAITS: dict[int, _Wait] = {}
#: ``(project, framework)`` -> the state in which its last attempt failed for a
#: key or credit reason. Memory only: on the row it would outlive the restart
#: that fixes it.
_BLOCKED: dict[tuple[int, str], tuple[str, str, bool]] = {}
#: Strong references: the loop holds a bare task weakly (server/CLAUDE.md).
_FIRING: set[asyncio.Task[Any]] = set()


def _settings(app: Any) -> BristlenoseSettings:
    from bristlenose.config import load_settings

    return getattr(app.state, "settings", None) or load_settings()


def cloud_ready(settings: Any) -> bool:
    """A cloud provider with a key. Without one nothing is tried (no spend, no
    row written), as ``app.py`` skips the run's re-apply."""
    from bristlenose.server.elaboration import _has_api_key

    return settings.llm_provider != "local" and _has_api_key(settings)


def signature(settings: Any) -> tuple[str, str, bool]:
    """What a key or credit failure is held against: the provider, the model and
    whether a key is set. Never the key."""
    from bristlenose.server.elaboration import _has_api_key

    return (
        str(settings.llm_provider), str(settings.llm_model), bool(_has_api_key(settings)),
    )


def blocked(project_id: int, framework_id: str, settings: Any) -> bool:
    """Whether the last attempt failed for a key or credit reason and nothing has
    changed since."""
    held = _BLOCKED.get((project_id, framework_id))
    return held is not None and held == signature(settings)


def eligible_frameworks(db: SASession, project_id: int, settings: Any) -> list[str]:
    """The codebooks a pass would code something for now: applied at least once,
    still installed and switched on, owing a quote that counts, not held back by
    a key or credit failure, and a cloud provider that has a key."""
    from bristlenose.server.autocode import _maintained_framework_ids, owed_quotes
    from bristlenose.server.models import AutoCodeJob

    if not cloud_ready(settings):
        return []
    maintained = _maintained_framework_ids(db, project_id)
    jobs = (
        db.query(AutoCodeJob)
        .filter(AutoCodeJob.project_id == project_id, AutoCodeJob.completed_at.isnot(None))
        .order_by(AutoCodeJob.id)
        .all()
    )
    return [
        job.framework_id
        for job in jobs
        if job.framework_id in maintained
        and not blocked(project_id, job.framework_id, settings)
        and owed_quotes(db, job)
    ]


def note_quotes_counting(app: Any, project_id: int) -> list[dict[str, str]]:
    """A write has made quotes count that did not (an unhide, a recode back in).

    Called by a route after its commit, from a worker thread. Arms the debounced
    pass when some codebook has something to code, and answers which, as
    ``[{"framework_id", "title"}]``, so the page can look for the pass. Never
    raises: the write is done, and an owed quote waits.
    """
    try:
        from bristlenose.server.codebook import get_template

        db = app.state.db_factory()
        try:
            frameworks = eligible_frameworks(db, project_id, _settings(app))
        finally:
            db.close()
        if not frameworks:
            return []
        _arm_on_the_loop(app, project_id)
        out = []
        for framework_id in frameworks:
            template = get_template(framework_id)
            out.append({
                "framework_id": framework_id,
                "title": template.title if template else framework_id,
            })
        return out
    except Exception:
        logger.exception("Could not schedule the AutoCode catch-up for project %d", project_id)
        return []


def _arm_on_the_loop(app: Any, project_id: int) -> None:
    """Reach the event loop from a route's worker thread (or from the loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        from anyio import from_thread

        from_thread.run_sync(_arm, app, project_id)
        return
    _arm(app, project_id)


def _arm(app: Any, project_id: int) -> None:
    """Start or restart the project's timer. On the loop."""
    loop = asyncio.get_running_loop()
    now = loop.time()
    wait = _WAITS.get(project_id)
    if wait is None:
        wait = _WAITS[project_id] = _Wait(now)
    elif wait.handle is not None:
        wait.handle.cancel()
    delay = min(DEBOUNCE_S, max(0.0, wait.first + CAP_S - now))
    wait.handle = loop.call_later(delay, _start_firing, app, project_id)


def _start_firing(app: Any, project_id: int) -> None:
    _WAITS.pop(project_id, None)
    task = asyncio.ensure_future(_fire(app, project_id))
    _FIRING.add(task)
    task.add_done_callback(_FIRING.discard)


async def _fire(app: Any, project_id: int) -> None:
    """One pass per codebook that has something to code. What counts is read now,
    not when the timer started: a quote hidden again in the wait is not owed."""
    try:
        settings = _settings(app)
        db = app.state.db_factory()
        try:
            frameworks = eligible_frameworks(db, project_id, settings)
        finally:
            db.close()
        for framework_id in frameworks:
            await _catch_up(app, project_id, framework_id, settings)
    except Exception:
        logger.exception("AutoCode catch-up after a quote counted again failed")


async def _catch_up(
    app: Any, project_id: int, framework_id: str, settings: Any,
) -> None:
    from bristlenose.server.autocode import live_reapply
    from bristlenose.server.models import AutoCodeJob
    from bristlenose.server.routes.data import _start_catch_ups, launch_catch_up

    # A pass already coding this codebook read what was owed when it began, so it
    # may not have this quote: wait for it, then ask what is left.
    while (running := live_reapply(project_id, framework_id)) is not None:
        await asyncio.wait({running})
    db = app.state.db_factory()
    try:
        started = _start_catch_ups(db, project_id, [framework_id])
    finally:
        db.close()
    if not started:
        return
    try:
        launch_catch_up(app, project_id, framework_id)
    except Exception:
        # The job was set "running" for a task that never started: say it is not,
        # or its chip would spin for ever.
        from bristlenose.server.autocode import _set_job_status

        db = app.state.db_factory()
        try:
            _set_job_status(db, project_id, framework_id, "completed", when="running")
        finally:
            db.close()
        raise
    task = live_reapply(project_id, framework_id)
    if task is not None:
        await asyncio.wait({task})

    db = app.state.db_factory()
    try:
        job = (
            db.query(AutoCodeJob)
            .filter_by(project_id=project_id, framework_id=framework_id)
            .first()
        )
        status = job.status if job is not None else ""
        kind = job.failure_kind if job is not None else ""
    finally:
        db.close()
    key = (project_id, framework_id)
    if status == "failed" and kind in KEY_OR_CREDIT_KINDS:
        _BLOCKED[key] = signature(settings)
        logger.info(
            "AutoCode catch-up %s failed (%s); no more attempts until the provider "
            "or key changes", framework_id, kind,
        )
    elif status == "completed":
        _BLOCKED.pop(key, None)


def forget_everything() -> None:
    """Reset for tests."""
    for wait in _WAITS.values():
        if wait.handle is not None:
            wait.handle.cancel()
    _WAITS.clear()
    _BLOCKED.clear()
