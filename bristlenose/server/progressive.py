"""Import a first analysis's sessions while the run is still going.

docs/design-progressive-lenses.md, Phase 1, steps 9–10. The pipeline records a
session merged once its transcript is readable (``readable_chain.py``) and
writes a counts-only ``run_progress`` line. The events watcher calls
:meth:`ProgressiveImport.follow` on every change to the log; this reads the
manifest, imports the sessions that became readable, and moves
``data_version`` so the SPA refetches.

Only for a first analysis: an in-progress run of kind ``run`` with no report on
record. A project with a report shows that report while it re-runs, exactly as
before, and ``app.state.progress`` stays None (every lens available).

One session per transaction. A session that will not import is said once, at
WARNING, and left to the whole-project import at ``run_completed`` — it must
not hold back the sessions after it, and it must not retry with a traceback on
every heartbeat of the events log.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from bristlenose.run_condition import Condition

logger = logging.getLogger(__name__)


def is_progressive(condition: Condition) -> bool:
    """A first analysis in progress: the only run whose sessions arrive one by one."""
    from bristlenose.events import KindEnum
    from bristlenose.run_condition import RunStateEnum

    latest = condition.latest
    return (
        latest is not None
        and latest.state == RunStateEnum.IN_PROGRESS
        and latest.kind == KindEnum.RUN
        and condition.report is None
    )


class ProgressiveImport:
    """The server half of a progressive run: follow the manifest, import, publish."""

    def __init__(
        self, app: Any, session_factory: Callable[[], Session], project_dir: Path,
    ) -> None:
        self._app = app
        self._session_factory = session_factory
        self._project_dir = project_dir
        self._run_id: str | None = None
        self._imported: set[str] = set()
        #: Sessions that would not import this run: said once, not retried.
        self._refused: set[str] = set()
        self._manifest_error: str | None = None

    async def follow(self, condition: Condition) -> None:
        from bristlenose.run_condition import RunStateEnum
        from bristlenose.server.lens_readiness import Progress

        state = self._app.state
        if not is_progressive(condition):
            latest = condition.latest
            if (
                latest is not None and latest.run_id == self._run_id
                and latest.state == RunStateEnum.COMPLETED
            ):
                # The run this follower imported for has just completed. The
                # whole-project import is about to run; until it lands the
                # lenses keep saying what is true now, and the completion
                # handler clears the overlay when it has published.
                return
            state.progress = None
            return
        assert condition.latest is not None
        if condition.latest.run_id != self._run_id:
            self._run_id = condition.latest.run_id
            self._imported, self._refused = set(), set()
            state.sessions_imported = False
        readable = self._readable()
        if readable is None:
            return  # unreadable manifest: keep saying what we said
        new = set(readable) - self._imported - self._refused
        if new:
            added, present = await asyncio.to_thread(self._import, new)
            self._imported |= present
            if added:
                state.data_version = getattr(state, "data_version", 0) + 1
        if self._imported:
            # From what the database holds, not from what this call added: a
            # serve restarted mid-run finds session 1 imported at startup.
            state.sessions_imported = True
        state.progress = Progress(readable=frozenset(self._imported))

    def _readable(self) -> frozenset[str] | None:
        from bristlenose.manifest import load_manifest
        from bristlenose.output_paths import project_output_dir
        from bristlenose.server.lens_readiness import readable_in_manifest

        try:
            manifest = load_manifest(project_output_dir(self._project_dir))
        except Exception as exc:  # noqa: BLE001 — a half-written or moved file
            said = f"{type(exc).__name__}: {exc}"
            if said != self._manifest_error:
                self._manifest_error = said
                logger.warning("progressive | cannot read the manifest (%s); "
                               "sessions are imported when it reads again", said)
            return None
        self._manifest_error = None
        return readable_in_manifest(manifest)

    def _import(self, sids: set[str]) -> tuple[set[str], set[str]]:
        """``(added, now in the database)`` for the requested sessions."""
        added: set[str] = set()
        present: set[str] = set()
        for sid in sorted(sids):
            outcome = self._import_one(sid)
            if outcome is None:
                self._refused.add(sid)
                continue
            if outcome:
                added.add(sid)
            present.add(sid)
        return added, present

    def _import_one(self, sid: str) -> bool | None:
        """True: added. False: already there. None: it would not import."""
        from bristlenose.server.importer import import_readable_sessions
        from bristlenose.server.models import Session as SessionModel

        db = self._session_factory()
        try:
            project, added = import_readable_sessions(db, self._project_dir, {sid})
            if project.id != 1:
                # The SPA reads row 1: a session imported elsewhere is invisible,
                # and calling it done would leave it "waiting" for good.
                logger.error(
                    "progressive import of %s landed in project row %s, not 1 — the "
                    "project forked; the report reads row 1", sid, project.id,
                )
                return None
            if sid in added:
                return True
            there = db.query(SessionModel.session_id).filter_by(
                project_id=project.id, session_id=sid,
            ).first()
            if there is None:
                logger.warning(
                    "progressive | %s is recorded readable but its transcript is not on "
                    "disk; it arrives with the whole report", sid,
                )
                return None
            return False
        except Exception:
            logger.warning(
                "progressive | %s did not import during the run; it arrives with the "
                "whole report", sid, exc_info=True,
            )
            db.rollback()
            return None
        finally:
            db.close()
