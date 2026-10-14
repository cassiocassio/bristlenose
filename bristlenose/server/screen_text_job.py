"""Screen text in serve: a background job that reads each recording's shared screen.

Shaped like the scene-strip job (``server/scene_strips.py``), and waits for it to finish, since both
decode every recording: a daemon thread after the report is readable, at startup and after each run; one session at a time; deferred while a run is in
progress and stopped between sessions (and between frames) when one starts; a ``start`` while a
pass runs asks for another pass. An index is cached by the recording's identity and the engine, so
a pass over indexed sessions costs a stat per session, and a recording that failed is not read again
until it changes.

Why a recording has no index is a reason code (``bristlenose.screen_text.ReadFailure``), never a
sentence; the exception and ffmpeg's stderr go to the log. The job records real failures only; a
recording it has not read while idle is reported ``not_read`` by the routes, so a poller always
reaches an answer. Each pass also measures its own reading rate (recording seconds per wall-clock
second, from the sessions it actually read) for the Mac app's progress row.

Off unless asked for: ``BRISTLENOSE_SCREEN_TEXT=1`` (the Mac app sets it when the Diagnostics
preference is on) or ``serve --dev``. The switch is read from the environment the serve was spawned
with, so turning Diagnostics off reaches a running serve only by restarting it. Where no engine can
run (anything but macOS with ``pyobjc-framework-Vision``), the job does nothing and the screens
routes say why.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from bristlenose.screen_text import ReadFailure, Unavailable
from bristlenose.screen_text.engine import ScreenTextEngine, VisionEngine
from bristlenose.screen_text.index import build_index, cache_key, index_dir, stored_key
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.scene_strips import video_sessions
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)


def session_durations(db: Session, project_id: int | None = None) -> dict[str, float]:
    """Each session's length in seconds, from the database (no ffprobe, no file read). 0 when
    unknown."""
    q = db.query(SessionModel.session_id, SessionModel.duration_seconds)
    if project_id is not None:
        q = q.filter(SessionModel.project_id == project_id)
    return {sid: float(d or 0.0) for sid, d in q.all()}


class ScreenTextJob:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        output_dir: Callable[[], Path],
        run_in_progress: Callable[[], bool] = lambda: False,
        enabled: Callable[[], bool] = lambda: False,
        engine: ScreenTextEngine | None = None,
        busy: Callable[[], bool] = lambda: False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session_factory = session_factory
        self._output_dir = output_dir
        self._run_in_progress = run_in_progress
        self._enabled = enabled
        #: Another media job to let finish first (the scene strips): both decode every recording.
        self._busy = busy
        self._clock = clock
        self.engine: ScreenTextEngine = engine or VisionEngine()
        self._lock = threading.Lock()
        self._flag = threading.Lock()
        self.running = False
        self._rerun = False
        #: The session being read, for the lens's "reading s3…" line.
        self.current: str | None = None
        #: Why a session has no index, by session id: a reason code, so the lens can say so instead
        #: of "reading". Cleared for a session when it next indexes; lives as long as the server.
        self.failed: dict[str, ReadFailure] = {}
        #: The recording identity each failure was for: an unchanged recording is not read again.
        self._failed_keys: dict[str, str] = {}
        #: Recording seconds read per wall-clock second, over the sessions this pass read (not
        #: cache hits, not failures, not recordings of unknown length). None until this pass has
        #: read one; kept after the pass ends, until the next one starts.
        self.rate: float | None = None
        self._read_seconds = 0.0
        self._read_wall = 0.0

    def unavailable(self) -> Unavailable | None:
        """None when the engine can run on this machine, else the reason code."""
        return self.engine.available()

    def start(self) -> bool:
        if not self._enabled() or self._run_in_progress() or self.unavailable():
            return False
        with self._flag:
            if not self._lock.acquire(blocking=False):
                self._rerun = True
                return False
            self.running = True
        try:
            threading.Thread(target=self._run, daemon=True, name="screen-text").start()
        except RuntimeError:
            with self._flag:
                self._finish()
            logger.warning("Screen text skipped: no thread", exc_info=True)
            return False
        return True

    def _finish(self) -> None:
        self.running = False
        self.current = None
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
        except Exception:  # noqa: BLE001 — diagnostic; must never take the server with it
            logger.warning("Screen text skipped", exc_info=True)
            with self._flag:
                self._finish()

    def run_in_progress(self) -> bool:
        """Whether a pipeline run is in progress (the job defers to it). Not free: a route asks
        once per request and passes the answer to ``why_unread``."""
        return self._run_in_progress()

    def why_unread(self, session_id: str, in_run: bool | None = None) -> ReadFailure | None:
        """For a recording with no current index: why, or None while it is waiting to be read.

        A recorded failure wins. While a pass runs, or while a pipeline run is in progress (the
        job defers to it and the run's completion starts the next pass), it is waiting: None.
        Otherwise, with the job idle and able to run, nothing is going to read it until something
        starts the job again — the pass never got that far, or the recording changed since — so
        it is ``not_read``, never "still reading": a poller that waits for every recording to be
        indexed or failed must reach an answer. ``in_run`` lets a caller asking about many
        sessions read the run state once."""
        why = self.failed.get(session_id)
        if why is not None:
            return why
        if self.running:
            return None
        if self.run_in_progress() if in_run is None else in_run:
            return None
        if self.unavailable() is None:
            return "not_read"
        return None

    def _pass(self) -> None:
        self.rate = None
        self._read_seconds = self._read_wall = 0.0
        while self._busy() and not self._run_in_progress():
            time.sleep(1)
        db = self._session_factory()
        try:
            videos = video_sessions(db)
            durations = session_durations(db)
        finally:
            db.close()
        out = index_dir(self._output_dir())
        for session_id, video in videos.items():
            if self._run_in_progress():
                self._rerun = False  # the run's completion starts a fresh pass
                return
            self.current = session_id
            path = out / f"{session_id}.json"
            try:
                key = cache_key(video, self.engine)
            except OSError as exc:
                self.failed[session_id] = "unreadable"
                logger.warning("No screen text for %s: the recording can't be read (%s)",
                               session_id, type(exc).__name__)
                continue
            if stored_key(path) == key:
                self.failed.pop(session_id, None)  # indexed already: a stat, not a read
                self._failed_keys.pop(session_id, None)
                continue
            if self._failed_keys.get(session_id) == key:
                continue  # it failed as it is; reading it again would fail again
            started = self._clock()
            try:
                ensure_materialised(video)
                if build_index(video, self.engine, path, should_stop=self._run_in_progress):
                    self.failed.pop(session_id, None)
                    self._failed_keys.pop(session_id, None)
                    self._measured(durations.get(session_id, 0.0), self._clock() - started)
            except CloudFetchTimeoutError:
                self.failed[session_id] = "cloud_downloading"
                logger.warning("No screen text for %s: cloud download timed out", session_id)
            except subprocess.CalledProcessError as exc:
                err = (exc.stderr or "")[-300:] if isinstance(exc.stderr, str) else ""
                self.failed[session_id] = "ffprobe_failed"
                self._failed_keys[session_id] = key
                logger.warning("No screen text for %s: exit %s %s", session_id, exc.returncode, err)
            except Exception:  # noqa: BLE001 — one recording must not stop the rest
                self.failed[session_id] = "read_failed"
                self._failed_keys[session_id] = key
                logger.warning("No screen text for %s", session_id, exc_info=True)

    def _measured(self, seconds: float, wall: float) -> None:
        if seconds <= 0 or wall <= 0:
            return  # a recording of unknown length says nothing about the rate
        self._read_seconds += seconds
        self._read_wall += wall
        self.rate = self._read_seconds / self._read_wall
