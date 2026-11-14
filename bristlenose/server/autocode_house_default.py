"""The house default: a study that shows screens is coded with the UXR codebook, once.

New researchers did not find AutoCode, so for a study that looks like a product study the first
codebook is applied for them. "Looks like" is one signal: the Screens lens has found screens
(``has_screens`` in ``/screens/status``). A study without screens spends nothing.

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

What it does: installs the framework (the same helper the Import button uses; AutoCode resolves
answers against the installed rows), starts the ordinary AutoCode job, and when that job has
completed applies the default cutoff, because no researcher is there to open the review. The band
below the cutoff stays pending for the review and nothing is denied, now or later: the lower
line is stored as 0, so the post-run re-apply, which would otherwise deny below the dialog's
default, only accepts at the cutoff and leaves the rest pending. The cutoff is stored on the job,
so later sessions are coded at the same line.

Known overlap, as with the Apply button: the job can run while the same run's re-apply of other
codebooks and its Signals snapshot are still going.

One shot: ``<output>/.bristlenose/house-codebooks.json`` records that it was done, written once
the install has been tried. It is a file beside the database, not a row, so Remove (which deletes
the job) cannot bring it back. A start that fails after the install, or a first job that dies,
leaves the marker, the installed codebook and the manual Apply button; retrying a failure nobody
asked for would spend again.
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


def already_done(app: Any) -> bool:
    try:
        data = json.loads(marker_path(app).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and FRAMEWORK_ID in data


def _write_marker(app: Any) -> None:
    from datetime import datetime, timezone

    path = marker_path(app)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps({FRAMEWORK_ID: datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )
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
    return bool(status.get("has_screens"))


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
        if (
            db.query(AutoCodeJob.id)
            .filter_by(project_id=PROJECT_ID, framework_id=FRAMEWORK_ID)
            .first()
            is not None
        ):
            return False  # the researcher has it, or had it: theirs to decide
        if not link_framework_once(db, PROJECT_ID, template):
            return False  # already installed (checked under the install lock): theirs
    finally:
        db.close()

    from bristlenose.server.autocode import DEFAULT_ACCEPT_THRESHOLD
    from bristlenose.server.routes.autocode import accept_at_default_cutoff

    def _apply_cutoff() -> None:
        # Once more on failure: a threadpool writer can hold the database for a moment, and a
        # completed job with every proposal pending is the outcome this exists to avoid.
        for attempt in (1, 2):
            try:
                accept_at_default_cutoff(
                    app.state.db_factory, PROJECT_ID, FRAMEWORK_ID, DEFAULT_ACCEPT_THRESHOLD
                )
                return
            except Exception:  # noqa: BLE001
                if attempt == 2:
                    raise
                logger.warning("House default: applying the cutoff failed, retrying", exc_info=True)

    try:
        await routes.start_autocode(app, PROJECT_ID, FRAMEWORK_ID, after_apply=_apply_cutoff)
    finally:
        # Installed, so tried: recorded whether or not the start went through (see the docstring).
        _write_marker(app)
    logger.info("House default: %s applied to a study with screens", FRAMEWORK_ID)
    return True
