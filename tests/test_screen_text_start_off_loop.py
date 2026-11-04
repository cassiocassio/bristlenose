"""ScreenTextJob.start() must not ask the engine whether it can run on the caller's thread.

The Vision engine's first availability check imports four pyobjc frameworks (Foundation, objc,
Quartz, Vision): about 260 ms, measured 4 Nov 2026, and the server's lifespan calls start() on
the event loop at every launch of the Mac app, where the Screens feature is on by default.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from bristlenose.server.screen_text_job import ScreenTextJob


class _Engine:
    name = "probe"
    version = "1"

    def __init__(self, unavailable: str | None = None) -> None:
        self.asked_on: list[int] = []
        self._unavailable = unavailable

    def available(self) -> str | None:
        self.asked_on.append(threading.get_ident())
        return self._unavailable

    def recognize(self, frame: object) -> list[object]:
        return []


def _job(engine: _Engine, tmp_path: Path) -> ScreenTextJob:
    return ScreenTextJob(
        lambda: None, lambda: tmp_path, enabled=lambda: True, engine=engine,  # type: ignore[arg-type]
    )


def _settle(job: ScreenTextJob) -> None:
    deadline = time.time() + 10
    while job.running and time.time() < deadline:
        time.sleep(0.02)


def test_start_returns_without_asking_the_engine_on_the_callers_thread(tmp_path: Path) -> None:
    engine = _Engine()
    job = _job(engine, tmp_path)
    caller = threading.get_ident()
    job.start()
    _settle(job)
    assert engine.asked_on, "the job's own thread should have asked"
    assert caller not in engine.asked_on


def test_an_engine_that_cannot_run_here_leaves_nothing_running(tmp_path: Path) -> None:
    engine = _Engine(unavailable="vision_missing")
    job = _job(engine, tmp_path)
    job.start()
    _settle(job)
    assert job.running is False
    # and the lock is free again: a second start is accepted, not stuck behind a dead pass
    assert job.start() is True
    _settle(job)
    assert job.running is False
