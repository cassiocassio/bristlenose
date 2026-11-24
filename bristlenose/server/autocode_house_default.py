"""The house default: a study that shows screens is coded with the UXR codebook, once.

New researchers did not find AutoCode, so for a study that looks like a product study the first
codebook is applied for them. "Looks like" is one signal: the Screens lens has found a screen
keyed on what was on screen, an address or a title (``has_page_screens`` in ``/screens/status``).
A study without one spends nothing, including a study whose screens are named only by its
sections (16 Nov 2026: section screens widened ``has_screens``, and did not widen spending).

When it fires, and only then:

- A run **completed in this serve** arms it (``arm``, from ``_on_run_completed``). Opening an
  existing study never spends, so a study from before this feature is not charged on first open.
  A re-run of such a study does count: if its researcher had removed uxr before the marker
  existed, the next completed run offers it once more, and the marker holds from then on.
- The screen-text job reading its last recording to the end (``ScreenTextJob``'s ``on_idle``)
  asks ``maybe_apply``. Screens are only known then, which is after the run.
- Every other condition is a silent skip: no cloud provider or key, nothing that counts, uxr
  already installed or applied by the researcher, a run in progress (stays armed), or no
  screens. A skip other than "run in progress" disarms until the next completed run.

Progress is the project row's line "AutoCode · N of M" (the Mac polls ``/autocode/jobs``), not a
toast: no page started this job.

What it does: installs the framework (the same helper the Import button uses; AutoCode resolves
answers against the installed rows), and starts the ordinary AutoCode job, which ends, as every
first apply does, with the hybrid cut committed with its outcome (``autocode.cut_first_apply``;
docs/design-autocode-landing-plan.md D5, D46): the most confident 30% of the run's proposals,
never below 0.70, at the line stored for them (rounded up to the 0.05 grid); those below 0.30
excluded; the band between pending for the review. The lines are stored on the job, so later
sessions are coded at the same lines, and a catch-up excludes below 0.30 too. Once the job has
completed this writes its done marker. Until Phase 3 (23 Nov 2026) this accepted everything at 0.70
and stored a lower line of 0, so nothing was ever excluded: half of a typical UXR run, the flood
the plan removes. A run stopped partway settles its cut at once but is not done: no marker, so it
is retried, and the retry finishes at the stored lines (D27, D35).

Known overlap, as with the Apply button: the job can run while the same run's re-apply of other
codebooks and its Signals snapshot are still going.

One shot, to completion: ``<output>/.bristlenose/house-codebooks.json`` records ``started`` when
the job is launched and ``completed`` when it has finished and the cut is applied. It is a file
beside the database, not a row, so Remove (which deletes the job) cannot bring it back. A job
that did not finish (a restart or a closed window killed it: 14 Nov 2026, 28 s in, nothing coded)
is retried on the next completed run that shows screens; the register keeps quotes already coded
from being paid for twice. A researcher who had uxr before the marker existed is still left alone.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bristlenose.server.refusal import RefusalError

logger = logging.getLogger(__name__)

FRAMEWORK_ID = "uxr"
PROJECT_ID = 1  # a serve holds one project, and the SPA reads row 1 (server/CLAUDE.md)
MARKER_NAME = "house-codebooks.json"

_TASKS: set[asyncio.Task[Any]] = set()  # a bare task can be GC'd mid-flight


def marker_path(app: Any) -> Path:
    from bristlenose.output_paths import project_output_dir

    return project_output_dir(app.state.project_dir) / ".bristlenose" / MARKER_NAME


def _read_marker(app: Any) -> dict[str, Any]:
    """The framework's record: ``{"started": iso, "completed": iso | absent}``. A marker from
    before the two were told apart (a bare timestamp) reads as started, not completed."""
    try:
        data = json.loads(marker_path(app).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entry = data.get(FRAMEWORK_ID) if isinstance(data, dict) else None
    if isinstance(entry, dict):
        return entry
    return {"started": entry} if entry else {}


def already_done(app: Any) -> bool:
    """The default has gone through to the end: the job completed, with its end-of-run cut."""
    return bool(_read_marker(app).get("completed"))


def _write_marker(app: Any, *, completed: bool) -> None:
    from datetime import datetime, timezone

    path = marker_path(app)
    now = datetime.now(timezone.utc).isoformat()
    entry = _read_marker(app)
    entry.setdefault("started", now)
    if completed:
        entry["completed"] = now
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({FRAMEWORK_ID: entry}), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        logger.warning("Could not record the house default", exc_info=True)


def arm(app: Any) -> None:
    """A run completed and its import is in: the next time screen reading ends, look."""
    app.state.house_default_due = True


def schedule(app: Any) -> None:
    """Called from the screen-text thread. Hop to the event loop; never raises into the job."""
    loop = getattr(app.state, "event_loop", None)
    if loop is None or loop.is_closed() or not getattr(app.state, "house_default_due", False):
        return

    def _go() -> None:
        task = asyncio.ensure_future(maybe_apply(app))
        _TASKS.add(task)
        task.add_done_callback(_TASKS.discard)

    loop.call_soon_threadsafe(_go)


def _has_screens(app: Any) -> bool:
    """The Screens lens's own answer, read as the route reads it: one copy of the rule."""
    from bristlenose.server.routes.screens import get_screens_status

    db = app.state.db_factory()
    request: Any = SimpleNamespace(app=app)  # the route reads only ``request.app``
    status = get_screens_status(PROJECT_ID, request, db)  # closes ``db``
    # Page screens only (an address or a title was read): a study whose screens are named by its
    # sections spends nothing unasked, as before section screens existed (16 Nov 2026).
    return bool(status.get("has_page_screens"))


async def maybe_apply(app: Any) -> bool:
    """Apply the house default if every condition holds. True when a job was started."""
    if not getattr(app.state, "house_default_due", False):
        return False
    job = getattr(app.state, "screen_text", None)
    if job is not None and job.run_in_progress():
        return False  # the run's completion arms and starts another pass; stay armed
    app.state.house_default_due = False  # decided from here: one look per completed run
    try:
        return await _apply(app)
    except Exception:  # noqa: BLE001 — a default must never break the study
        logger.exception("House default (%s) failed", FRAMEWORK_ID)
        return False


def _switched_off(db: Any) -> bool:
    """Whether the researcher has switched the house default's codebook off."""
    from bristlenose.server.models import ProjectFrameworkState

    row = (
        db.query(ProjectFrameworkState)
        .filter_by(project_id=PROJECT_ID, framework_id=FRAMEWORK_ID)
        .first()
    )
    return row is not None and not row.enabled


async def _apply(app: Any) -> bool:
    from bristlenose.server.codebook import get_template
    from bristlenose.server.codebook_install import link_framework_once
    from bristlenose.server.models import AutoCodeJob, Project
    from bristlenose.server.routes import autocode as routes
    from bristlenose.server.speaker_slots import analysis_quotes

    if already_done(app):
        return False
    template = get_template(FRAMEWORK_ID)
    if template is None or not template.enabled:
        return False
    db = app.state.db_factory()
    try:
        if db.get(Project, PROJECT_ID) is None:
            return False
    finally:
        db.close()
    if not await asyncio.to_thread(_has_screens, app):
        logger.info("House default: no screens, nothing spent")
        return False
    try:
        routes.require_provider_ready(routes.current_settings())
    except RefusalError as exc:
        logger.info("House default skipped: %s", exc.reason)
        return False

    db = app.state.db_factory()
    try:
        if not analysis_quotes(db, PROJECT_ID):
            return False
        started_before = bool(_read_marker(app).get("started"))
        existing = (
            db.query(AutoCodeJob)
            .filter_by(project_id=PROJECT_ID, framework_id=FRAMEWORK_ID)
            .first()
        )
        if not started_before:
            if existing is not None:
                return False  # the researcher has it, or had it: theirs to decide
        elif existing is not None and (
            existing.status not in ("failed", "cancelled") or existing.completed_at is not None
        ):
            return False  # in flight, or applied: nothing to retry
        elif existing is not None and _switched_off(db):
            # Switching the codebook off mid-run stops the run (owner, 24 Nov 2026), and
            # off means off: the retry a Stop earns (D35) would code it again unasked.
            return False
        # An earlier attempt of ours that did not finish is retried (a restart or a closed window
        # killed it): the job row is re-run and the register keeps quotes already coded from
        # being paid for twice.
        if not link_framework_once(db, PROJECT_ID, template) and not started_before:
            return False  # already installed (checked under the install lock): theirs
    finally:
        db.close()

    def _mark_done() -> None:
        # Runs once the job has completed, which since Phase 3 means its cut has landed with
        # it, in one transaction the job's save retries (``autocode.cut_first_apply``): the
        # marker is written after the cut, never instead of it. A stop is not a completion,
        # so a stopped run is settled but never marked done (D35) and is retried.
        _write_marker(app, completed=True)

    _write_marker(app, completed=False)  # tried: a retry is allowed, an unasked first one is not
    await routes.start_autocode(app, PROJECT_ID, FRAMEWORK_ID, after_apply=_mark_done)
    logger.info("House default: %s applied to a study with screens", FRAMEWORK_ID)
    return True
