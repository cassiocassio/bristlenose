"""Scene strips in serve: a background job that runs after the report is readable.

The tapestry's scene strip (``utils/scene_strip.py``) decodes every recording at 4 fps, so it is
not on the run's path: serve computes it on a thread once the project is imported, at startup and
again after each run completes, and the tapestry route serves whatever exists. While the job runs
the route says ``strips_pending``, and the Sessions grid refetches until it stops. A machine
already busy with a run is left alone: the job defers while the project's latest run is in
progress, stops between sessions when one starts, and the run's completion starts it again. A
``start`` while a pass is running asks for another pass, so sessions a run added while the job
was busy are not missed.

Kill switch: ``BRISTLENOSE_SCENE_STRIPS=0`` before launching serve.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from bristlenose.models import VIDEO_EXTENSIONS
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import SourceFile
from bristlenose.utils.scene_strip import extract_scene_strips

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return os.environ.get("BRISTLENOSE_SCENE_STRIPS", "1") != "0"


def strips_dir(output_dir: Path) -> Path:
    return output_dir / ".bristlenose" / "intermediate" / "scene-strips"


def video_sessions(db: Session) -> dict[str, Path]:
    """Every session with a video recording on disk: session id → path (the first imported,
    which is the pipeline's first). By the pipeline's own extension set, not the importer's
    ``file_type``, whose spelling of "video" is narrower."""
    out: dict[str, Path] = {}
    rows = (db.query(SessionModel, SourceFile)
            .join(SourceFile, SourceFile.session_id == SessionModel.id)
            .order_by(SessionModel.session_number, SourceFile.id).all())
    for sess, sf in rows:
        path = Path(sf.path)
        if sess.session_id not in out and path.suffix.lower() in VIDEO_EXTENSIONS and path.exists():
            out[sess.session_id] = path
    return out


class SceneStripJob:
    """One strip job per server; ``start`` is a no-op while a job is running."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        output_dir: Callable[[], Path],
        run_in_progress: Callable[[], bool] = lambda: False,
        extractor: Callable[[dict[str, Path], Path], dict[str, Path]] = extract_scene_strips,
    ) -> None:
        self._session_factory = session_factory
        self._output_dir = output_dir
        self._run_in_progress = run_in_progress
        self._extractor = extractor
        self._lock = threading.Lock()
        #: Guards ``running`` and ``_rerun`` across the start/finish race: a ``start`` that finds
        #: the pass finishing must either get the lock or be seen by the finishing pass.
        self._flag = threading.Lock()
        self.running = False
        #: Set by a ``start`` that found a pass running: the pass goes round again when it ends.
        self._rerun = False

    def start(self) -> bool:
        """Start the job on a daemon thread. False when disabled, deferred or already running
        (in which case the running pass will go round again)."""
        if not enabled() or self._run_in_progress():
            return False
        with self._flag:
            if not self._lock.acquire(blocking=False):
                self._rerun = True
                return False
            self.running = True
        try:
            threading.Thread(target=self._run, daemon=True, name="scene-strips").start()
        except RuntimeError:  # can't start new thread: the process limit, not our bug
            with self._flag:
                self._finish()
            logger.warning("Scene strips skipped: no thread", exc_info=True)
            return False
        return True

    def _finish(self) -> None:
        self.running = False
        self._lock.release()

    def _run(self) -> None:
        try:
            while True:
                self._rerun = False
                self._pass()
                with self._flag:
                    if not self._rerun:
                        self._finish()
                        return
        except Exception:  # noqa: BLE001 — cosmetic; must never take the server with it
            logger.warning("Scene strips skipped", exc_info=True)
            with self._flag:
                self._finish()

    def _pass(self) -> None:
        """One session at a time, so a run that starts meanwhile gets the machine back."""
        db = self._session_factory()
        try:
            videos = video_sessions(db)
        finally:
            db.close()
        out = strips_dir(self._output_dir())
        for session_id, video in videos.items():
            if self._run_in_progress():
                self._rerun = False  # the run's completion starts a fresh pass
                return
            self._extractor({session_id: video}, out)
