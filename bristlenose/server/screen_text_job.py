"""Screen text in serve: a background job that reads each recording's shared screen.

Shaped like the scene-strip job (``server/scene_strips.py``): a daemon thread after the report is
readable, at startup and after each run; one session at a time; deferred while a run is in
progress and stopped between sessions (and between frames) when one starts; a ``start`` while a
pass runs asks for another pass. An index is cached by the recording's identity and the engine, so
a pass over indexed sessions costs a stat per session.

Off unless asked for: ``BRISTLENOSE_SCREEN_TEXT=1`` (the Mac app sets it when the Diagnostics
preference is on) or ``serve --dev``. Where no engine can run (anything but macOS with
``pyobjc-framework-Vision``), the job does nothing and says why to the screens route.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from bristlenose.screen_text.engine import ScreenTextEngine, VisionEngine
from bristlenose.screen_text.index import build_index, index_dir
from bristlenose.server.scene_strips import video_sessions
from bristlenose.utils.fs import CloudFetchTimeoutError, ensure_materialised

logger = logging.getLogger(__name__)


class ScreenTextJob:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        output_dir: Callable[[], Path],
        run_in_progress: Callable[[], bool] = lambda: False,
        enabled: Callable[[], bool] = lambda: False,
        engine: ScreenTextEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._output_dir = output_dir
        self._run_in_progress = run_in_progress
        self._enabled = enabled
        self.engine: ScreenTextEngine = engine or VisionEngine()
        self._lock = threading.Lock()
        self._flag = threading.Lock()
        self.running = False
        self._rerun = False
        #: The session being read, for the lens's "reading s3…" line.
        self.current: str | None = None
        #: Why a session has no index, by session id, so the lens can say so instead of "reading".
        #: Cleared for a session when it next indexes; lives as long as the server.
        self.failed: dict[str, str] = {}

    def unavailable(self) -> str | None:
        """None when the engine can run on this machine, else why not."""
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

    def _pass(self) -> None:
        db = self._session_factory()
        try:
            videos = video_sessions(db)
        finally:
            db.close()
        out = index_dir(self._output_dir())
        for session_id, video in videos.items():
            if self._run_in_progress():
                self._rerun = False  # the run's completion starts a fresh pass
                return
            self.current = session_id
            try:
                ensure_materialised(video)
                if build_index(video, self.engine, out / f"{session_id}.json", should_stop=self._run_in_progress):
                    self.failed.pop(session_id, None)
            except CloudFetchTimeoutError:
                self.failed[session_id] = "the recording is still downloading from the cloud"
                logger.warning("No screen text for %s: cloud download timed out", session_id)
            except subprocess.CalledProcessError as exc:
                err = (exc.stderr or "")[-300:] if isinstance(exc.stderr, str) else ""
                self.failed[session_id] = f"ffprobe could not read the recording (exit {exc.returncode})"
                logger.warning("No screen text for %s: exit %s %s", session_id, exc.returncode, err)
            except Exception as exc:  # noqa: BLE001 — one recording must not stop the rest
                self.failed[session_id] = f"{type(exc).__name__}: {exc}"[:300]
                logger.warning("No screen text for %s", session_id, exc_info=True)
