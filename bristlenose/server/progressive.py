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
import dataclasses
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from bristlenose.run_condition import Condition

logger = logging.getLogger(__name__)

#: An import that raised is tried this many times before the session waits for
#: the whole report: one "database is locked" while the researcher edits must
#: not hide a session for the rest of an hour-long run.
_ATTEMPTS = 3


def _parse_ts(value: str) -> datetime:
    # Events write ``Z`` (``events._now_iso``), the manifest ``+00:00``; Python
    # 3.10's ``fromisoformat`` refuses the former.
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _predates(created_at: str, run_started_at: str | None) -> bool:
    """True when a manifest was created before the run started.

    A timestamp that will not parse reads as the previous run's: the manifest's
    sessions then wait for the whole import rather than risk being another run's
    unredacted ones.
    """
    if not run_started_at:
        return False
    try:
        return _parse_ts(created_at) < _parse_ts(run_started_at)
    except (TypeError, ValueError):
        return True


def _gave_up(failures: dict[str, int], sid: str) -> bool:
    """Count one more failed import of ``sid``; True once it has had its attempts."""
    failures[sid] = failures.get(sid, 0) + 1
    if failures[sid] < _ATTEMPTS:
        logger.info("progressive | %s did not import (attempt %d); trying again",
                    sid, failures[sid])
        return False
    return True


def mark_ended(state: Any) -> None:
    """The progressive run ended without a whole report: keep its overlay, ended."""
    progress = getattr(state, "progress", None)
    if progress is None or progress.ended:
        return
    state.progress = dataclasses.replace(progress, ended=True)
    # The grid's processing row goes: the SPA refetches.
    state.data_version = getattr(state, "data_version", 0) + 1


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
        #: Sessions whose quotes are imported (Phase 2), and those with at least one.
        self._quotes_done: set[str] = set()
        self._quoted: set[str] = set()
        self._quotes_refused: set[str] = set()
        #: Imports that raised, per session: retried up to ``_ATTEMPTS``.
        self._failures: dict[str, int] = {}
        self._quote_failures: dict[str, int] = {}
        self._manifest_error: str | None = None
        #: The run's one import stamp (see ``import_readable_sessions``).
        self._run_stamp: datetime | None = None
        #: Whether the run redacts, from its manifest: which folder is this run's.
        self._redacted = False

    async def follow(self, condition: Condition) -> None:
        from bristlenose.run_condition import RunStateEnum
        from bristlenose.server.lens_readiness import Progress

        state = self._app.state
        if not is_progressive(condition):
            latest = condition.latest
            if latest is not None and latest.run_id == self._run_id:
                if latest.state == RunStateEnum.COMPLETED:
                    # The run this follower imported for has just completed. The
                    # whole-project import is about to run; until it lands the
                    # lenses keep saying what is true now, and the completion
                    # handler clears the overlay when it has published.
                    return
                if condition.report is None and state.progress is not None:
                    # Stopped or failed with no report: the database holds what
                    # the run delivered and nothing more. Lighting every lens
                    # would show empty sections and allow an export of a partial
                    # report, so the overlay stays, with nothing processing.
                    mark_ended(state)
                    return
            if state.progress is not None:
                # The overlay lifts without a whole import of ours: a failed
                # ``--clean`` run's stash put the previous report back. What the
                # SPA holds is the partial delivery; it refetches.
                state.data_version = getattr(state, "data_version", 0) + 1
            state.progress = None
            return
        assert condition.latest is not None
        if condition.latest.run_id != self._run_id:
            self._run_id = condition.latest.run_id
            self._imported, self._refused = set(), set()
            self._quotes_done, self._quoted, self._quotes_refused = set(), set(), set()
            self._failures, self._quote_failures = {}, {}
            # The run's start, not this follower's: a serve restarted mid-run
            # stamps its sessions as the first serve did.
            try:
                self._run_stamp = _parse_ts(condition.latest.started_at or "")
            except ValueError:
                self._run_stamp = datetime.now(timezone.utc)
            state.sessions_imported = False
        sets = self._manifest_sets(condition.latest.started_at)
        if sets is None:
            return  # unreadable manifest: keep saying what we said
        readable, quoted, self._redacted = sets
        moved = False
        new = set(readable) - self._imported - self._refused
        if new:
            added, present = await asyncio.to_thread(self._import, new)
            self._imported |= present
            moved = bool(added)
        # Quotes for sessions already in the database (Phase 2).
        new_q = (set(quoted) & self._imported) - self._quotes_done - self._quotes_refused
        if new_q:
            counts = await asyncio.to_thread(self._import_quotes, new_q)
            self._quotes_done |= set(counts)
            self._quoted |= {sid for sid, n in counts.items() if n}
            moved = moved or any(counts.values())
        if moved:
            state.data_version = getattr(state, "data_version", 0) + 1
        if self._imported:
            # From what the database holds, not from what this call added: a
            # serve restarted mid-run finds session 1 imported at startup.
            state.sessions_imported = True
        state.progress = Progress(
            readable=frozenset(self._imported), quoted=frozenset(self._quoted),
        )

    def _manifest_sets(
        self, run_started_at: str | None,
    ) -> tuple[frozenset[str], frozenset[str], bool] | None:
        """``(readable, quoted, redacting)`` from the manifest, or None when it will not read.

        A manifest created before this run started is the previous run's: the
        pipeline builds the new one in memory and first writes it after ingest, so a
        re-run of a first analysis that failed reads its predecessor's records until
        then. Those sessions and quotes are not this run's (they may be unredacted,
        or re-transcribed to new timecodes), so they read as nothing yet.
        """
        from bristlenose.manifest import load_manifest
        from bristlenose.output_paths import project_output_dir
        from bristlenose.server.lens_readiness import (
            quoted_in_manifest,
            readable_in_manifest,
            redacting_in_manifest,
        )

        try:
            manifest = load_manifest(project_output_dir(self._project_dir), strict=True)
        except Exception as exc:  # noqa: BLE001 — a half-written or moved file
            said = f"{type(exc).__name__}: {exc}"
            if said != self._manifest_error:
                self._manifest_error = said
                logger.warning("progressive | cannot read the manifest (%s); "
                               "sessions are imported when it reads again", said)
            return None
        self._manifest_error = None
        if manifest is None or _predates(manifest.created_at, run_started_at):
            return frozenset(), frozenset(), False
        return (
            readable_in_manifest(manifest), quoted_in_manifest(manifest),
            redacting_in_manifest(manifest),
        )

    def _import_quotes(self, sids: set[str]) -> dict[str, int]:
        """Per session imported, how many quotes it holds. A session that will
        not import is said once and left to the whole import."""
        from bristlenose.server.importer import import_session_quotes

        counts: dict[str, int] = {}
        for sid in sorted(sids):
            db = self._session_factory()
            try:
                project, got = import_session_quotes(db, self._project_dir, {sid})
                if project.id != 1:
                    logger.error(
                        "progressive quote import of %s landed in project row %s, not 1",
                        sid, project.id,
                    )
                    self._quotes_refused.add(sid)
                    continue
                counts[sid] = got.get(sid, 0)
            except Exception:
                db.rollback()
                if _gave_up(self._quote_failures, sid):
                    logger.warning(
                        "progressive | %s's quotes did not import during the run; they "
                        "arrive with the whole report", sid, exc_info=True,
                    )
                    self._quotes_refused.add(sid)
            finally:
                db.close()
        return counts

    def _import(self, sids: set[str]) -> tuple[set[str], set[str]]:
        """``(added, now in the database)`` for the requested sessions."""
        added: set[str] = set()
        present: set[str] = set()
        for sid in sorted(sids):
            outcome = self._import_one(sid)
            if outcome is None:
                # An import that raised is tried again; anything else is final.
                failures = self._failures.get(sid, 0)
                if failures == 0 or failures >= _ATTEMPTS:
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
            project, added = import_readable_sessions(
                db, self._project_dir, {sid}, run_stamp=self._run_stamp,
                redacted=self._redacted,
            )
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
            db.rollback()
            if _gave_up(self._failures, sid):
                logger.warning(
                    "progressive | %s did not import during the run; it arrives with the "
                    "whole report", sid, exc_info=True,
                )
            return None
        finally:
            db.close()
