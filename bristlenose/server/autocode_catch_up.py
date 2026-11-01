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
key: no key value is kept or logged here. It is held in this process, so a serve
restart (which the Mac does when a key is saved) is a change too, and only while
the job still says it failed that way, so any later pass that works lifts it.
Topping up credit or replacing a key from another terminal changes none of these,
so the hold also lapses with the clock (``HOLD_S``, 15 minutes): the next trigger
after that makes one attempt, and a failure for the same reason holds for another
period. Nothing runs on a timer; with no trigger, nothing is spent. A provider with no
key is not tried at all (as ``app.py`` skips the run's re-apply) and writes nothing to
the job.

**Saving a key starts it (owner, 1 Nov 2026).** A write that made quotes count while no
key was set leaves a marker file (``AWAITING_KEY``) in the study's ``.bristlenose``
folder. The Mac restarts the serve when a key is saved, and ``resume_after_key`` (the
lifespan's startup) arms one pass when it finds the marker and a key: the owed quotes
are coded without another gesture. The marker is only ever written by a write that
found something owed and no key, so an ordinary launch never spends; the fire-time
check is still the authority on what is owed, so a stale marker costs nothing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SASession

    from bristlenose.config import BristlenoseSettings
    from bristlenose.server.models import AutoCodeJob

logger = logging.getLogger(__name__)

#: A trailing timer restarted by each trigger, and the longest a burst may keep
#: pushing the pass back. Module constants so a test can shrink them.
DEBOUNCE_S = 10.0
CAP_S = 60.0

#: The failure kinds that a retry cannot mend: fix the key or add credit first.
#: Rate limits, outages and a stopped pass are not here: they pass.
KEY_OR_CREDIT_KINDS = frozenset({"invalid_key", "out_of_credit"})

#: How long that hold lasts. A key mended where this process cannot see it (``bristlenose
#: configure`` in another terminal while a CLI ``serve`` runs) changes nothing the
#: signature holds, so the hold also lapses with the clock: the first trigger after
#: it makes ONE attempt, and a failure for the same reason holds for another period.
#: No timer runs and nothing is spent without a trigger.
HOLD_S = 15 * 60.0

#: A write made quotes count while no key was set; the next serve start with a key codes them.
AWAITING_KEY = "autocode-awaiting-key"

#: The clock the hold is measured on; a test replaces it. The wall clock, not
#: ``time.monotonic``: on a Mac the monotonic clock stops while the lid is closed, so a
#: hold set at 17:55 would have run for five of its fifteen minutes by the next morning.
#: A wall-clock jump costs one early attempt or a longer hold, never a key or a spend.
_clock = time.time


class _Wait:
    """One project's pending pass: when its first trigger arrived, and its timer."""

    def __init__(self, first: float) -> None:
        self.first = first
        self.handle: asyncio.TimerHandle | None = None


_WAITS: dict[int, _Wait] = {}
#: ``(project, framework)`` -> the state in which its last attempt failed for a
#: key or credit reason, and when (``_clock``). Memory only: on the row it would
#: outlive the restart that fixes it.
_BLOCKED: dict[tuple[int, str], tuple[tuple[str, str, bool], float]] = {}
#: Strong references: the loop holds a bare task weakly (server/CLAUDE.md).
_FIRING: set[asyncio.Task[Any]] = set()
#: One attempt at a time per ``(project, framework)``, from the check to the hold
#: being set again. Without it a second trigger could slip between a finished pass
#: and its continuation and make a second provider call for one lapse.
_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}


#: ``load_settings()`` reads the credential store, which on the Mac is a subprocess per key,
#: and a route asks on every unhide: the answer is kept this long. A serve built with settings
#: (tests, an embedding) is not asked at all.
_SETTINGS_TTL_S = 30.0
_settings_memo: tuple[int, float, Any] | None = None  # (id of the app, when, settings)


def _settings(app: Any) -> BristlenoseSettings:
    global _settings_memo
    injected = getattr(app.state, "settings", None)
    if injected is not None:
        return injected  # type: ignore[no-any-return]
    now = time.monotonic()
    memo = _settings_memo
    if memo is not None and memo[0] == id(app) and now - memo[1] < _SETTINGS_TTL_S:
        return memo[2]  # type: ignore[no-any-return]
    from bristlenose.config import load_settings

    loaded = load_settings()
    _settings_memo = (id(app), now, loaded)
    return loaded


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


def blocked(project_id: int, framework_id: str, settings: Any, job: AutoCodeJob) -> bool:
    """Whether the last attempt failed for a key or credit reason and nothing has
    changed since: the state is the one it failed in, the job still says so, and
    ``HOLD_S`` has not passed. A pass that has worked since (any path) cleared the
    job's failure and lifts it. Two attempts for one codebook never overlap
    (``_catch_up`` serialises them), so a second trigger during the attempt a lapsed
    hold allows waits for it and then finds the hold set again."""
    key = (project_id, framework_id)
    held = _BLOCKED.get(key)
    if held is None:
        return False
    if job.status != "failed" or job.failure_kind not in KEY_OR_CREDIT_KINDS:
        del _BLOCKED[key]
        return False
    state, since = held
    return state == signature(settings) and _clock() - since < HOLD_S


def _eligible_jobs(
    db: SASession, project_id: int, app: Any, *, need_key: bool = True,
) -> list[AutoCodeJob]:
    """The codebooks a pass would code something for now: applied at least once,
    still installed and switched on, owing a quote that counts, not held back by
    a key or credit failure, and a cloud provider that has a key.

    The cheap questions first, since a route asks on every unhide: which codebooks
    were applied and are on (a project with none stops here), then the settings, then
    one read of the quotes that count, shared by every codebook."""
    from bristlenose.server.autocode import _maintained_framework_ids, owed_quotes
    from bristlenose.server.models import AutoCodeJob
    from bristlenose.server.speaker_slots import analysis_quotes

    maintained = _maintained_framework_ids(db, project_id)
    jobs = [
        job
        for job in db.query(AutoCodeJob)
        .filter(AutoCodeJob.project_id == project_id, AutoCodeJob.completed_at.isnot(None))
        .order_by(AutoCodeJob.id)
        if job.framework_id in maintained
    ]
    if not jobs:
        return []
    settings = _settings(app)
    if need_key and not cloud_ready(settings):
        return []
    counted = analysis_quotes(db, project_id)
    return [
        job
        for job in jobs
        if not blocked(project_id, job.framework_id, settings, job)
        and owed_quotes(db, job, counted)
    ]


def note_quotes_counting(app: Any, project_id: int) -> list[dict[str, str]]:
    """A write has made quotes count that did not (an unhide, a recode back in).

    Called by a route after its commit, from a worker thread. Arms the debounced
    pass when some codebook has something to code, and answers which, as
    ``[{"framework_id", "title", "started_at"}]``: ``started_at`` is the job's start
    now, so the page can tell the pass this write causes from an earlier one, which
    ``/autocode/jobs`` could not show it when it ended in a second. Never raises: the
    write is done, and an owed quote waits.
    """
    try:
        from bristlenose.server.codebook import get_template

        db = app.state.db_factory()
        try:
            jobs = _eligible_jobs(db, project_id, app)
            armed = [
                {
                    "framework_id": job.framework_id,
                    "title": template.title if (template := get_template(job.framework_id))
                    else job.framework_id,
                    "started_at": job.started_at.isoformat() if job.started_at else "",
                }
                for job in jobs
            ]
            # Cheap question first: a project with no codebook applied reads no settings.
            if not jobs and _eligible_jobs(db, project_id, app, need_key=False) and not (
                cloud_ready(_settings(app))
            ):
                _note_waiting_for_key(app)
        finally:
            db.close()
        if armed:
            _arm_on_the_loop(app, project_id)
        return armed
    except Exception:
        logger.exception("Could not schedule the AutoCode catch-up for project %d", project_id)
        return []


def _marker(app: Any) -> Path | None:
    project_dir = getattr(app.state, "project_dir", None)
    if project_dir is None:
        return None
    from bristlenose.output_paths import project_output_dir

    return project_output_dir(project_dir) / ".bristlenose" / AWAITING_KEY


def _note_waiting_for_key(app: Any) -> None:
    """Something is owed and there is no key: leave word for the next start that has one."""
    marker = _marker(app)
    if marker is None:
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n", encoding="utf-8")
    except OSError:
        logger.warning("Could not note that the AutoCode catch-up is waiting for a key",
                       exc_info=True)


def resume_after_key(app: Any, project_id: int = 1) -> bool:
    """At serve start: if a write found quotes owed and no key, and there is a key now,
    arm one pass (the Mac restarts the serve when a key is saved). On the event loop.
    Answers whether it armed one; never raises."""
    try:
        marker = _marker(app)
        if marker is None or not marker.exists():
            return False
        if not cloud_ready(_settings(app)):
            return False  # still no key: the word stays for the start that has one
        marker.unlink(missing_ok=True)
        _arm(app, project_id)
        return True
    except Exception:
        logger.exception("Could not resume the AutoCode catch-up after a key was saved")
        return False


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
        db = app.state.db_factory()
        try:
            frameworks = [job.framework_id for job in _eligible_jobs(db, project_id, app)]
        finally:
            db.close()
    except Exception:
        logger.exception("AutoCode catch-up after a quote counted again could not start")
        return
    for framework_id in frameworks:
        try:
            await _catch_up(app, project_id, framework_id)
        except Exception:
            # One codebook's failure does not stop the next.
            logger.exception("AutoCode catch-up %s after a quote counted again failed", framework_id)


async def _catch_up(app: Any, project_id: int, framework_id: str) -> None:
    lock = _LOCKS.setdefault((project_id, framework_id), asyncio.Lock())
    async with lock:
        await _catch_up_locked(app, project_id, framework_id)


async def _catch_up_locked(app: Any, project_id: int, framework_id: str) -> None:
    from bristlenose.server.autocode import live_reapply
    from bristlenose.server.models import AutoCodeJob
    from bristlenose.server.routes.data import _start_catch_ups, launch_catch_up

    # A pass already coding this codebook read what was owed when it began, so it
    # may not have this quote: wait for it, then ask what is left.
    while (running := live_reapply(project_id, framework_id)) is not None:
        await asyncio.wait({running})
    db = app.state.db_factory()
    try:
        # Its turn may be minutes after the list was made (the codebooks go one at a
        # time): it may have been switched off since, or held, or owe nothing now.
        if framework_id not in [j.framework_id for j in _eligible_jobs(db, project_id, app)]:
            return
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
        _BLOCKED[key] = (signature(_settings(app)), _clock())
        logger.info(
            "AutoCode catch-up %s failed (%s); no more attempts until the provider "
            "or key changes, or %d minutes pass", framework_id, kind, int(HOLD_S // 60),
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
    _LOCKS.clear()
    global _settings_memo
    _settings_memo = None
