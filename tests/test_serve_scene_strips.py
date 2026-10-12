"""Scene strips in serve: the background job, when it starts, and what the tapestry says meanwhile."""

from __future__ import annotations

import asyncio
import os
import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.events import (
    Cause,
    CauseCategoryEnum,
    KindEnum,
    Process,
    RunCompletedEvent,
    RunFailedEvent,
    RunStartedEvent,
    append_event,
    events_path,
    new_run_id,
)
from bristlenose.run_lifecycle import _ps_start_time, _write_pid_file
from bristlenose.server import scene_strips as sj
from bristlenose.server.app import _make_run_completed_handler, create_app
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import SourceFile
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_TS = "2026-10-12T12:00:00+00:00"


@pytest.fixture(autouse=True)
def strips_enabled(monkeypatch):
    """conftest switches the job off for every other test; this module is about it."""
    monkeypatch.delenv("BRISTLENOSE_SCENE_STRIPS", raising=False)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, p)
    return p


def _app(project: Path):
    return create_app(project_dir=project, dev=True, db_url="sqlite://")


def _give_s1_a_video(app, project: Path) -> Path:
    """The smoke fixture has no recording; point s1 at a file that exists."""
    video = project / "s1.mp4"
    video.write_bytes(b"not really a video")
    db = app.state.db_factory()
    try:
        sess = db.query(SessionModel).filter_by(session_id="s1").one()
        db.add(SourceFile(session_id=sess.id, file_type="video", path=str(video), size_bytes=1))
        db.commit()
    finally:
        db.close()
    return video


class _Extractor:
    """Stands in for utils.scene_strip.extract_scene_strips: records its call, can block."""

    def __init__(self, hold: bool = False) -> None:
        self.calls: list[tuple[dict[str, Path], Path]] = []
        self.started = threading.Event()
        self.release = threading.Event()
        if not hold:
            self.release.set()
        self.done = threading.Event()

    def __call__(self, videos: dict[str, Path], out_dir: Path) -> dict[str, Path]:
        self.calls.append((videos, out_dir))
        self.started.set()
        self.release.wait(5)
        out_dir.mkdir(parents=True, exist_ok=True)
        for sid in videos:
            (out_dir / f"{sid}.json").write_text(
                '{"version": 1, "key": "k", "fps": 4, "n": 2, "png": "AA==", "edges": [1.0]}')
        self.done.set()
        return {sid: out_dir / f"{sid}.json" for sid in videos}


def _job(app, project: Path, extractor: _Extractor, in_progress: bool = False) -> sj.SceneStripJob:
    return sj.SceneStripJob(app.state.db_factory, lambda: project / "bristlenose-output",
                            lambda: in_progress, extractor)


class TestJob:
    def test_runs_the_extractor_over_video_sessions_into_the_strips_dir(self, project):
        app = _app(project)
        video = _give_s1_a_video(app, project)
        ex = _Extractor()
        job = _job(app, project, ex)
        assert job.start() is True
        assert ex.done.wait(5)
        assert ex.calls == [({"s1": video}, project / "bristlenose-output" / ".bristlenose" / "intermediate" / "scene-strips")]

    def test_no_video_means_no_extractor_call(self, project):
        app = _app(project)
        ex = _Extractor()
        job = _job(app, project, ex)
        assert job.start() is True
        for _ in range(50):
            if not job.running:
                break
            threading.Event().wait(0.02)
        assert not job.running and ex.calls == []

    def test_is_a_no_op_while_running_and_reports_running(self, project):
        app = _app(project)
        _give_s1_a_video(app, project)
        ex = _Extractor(hold=True)
        job = _job(app, project, ex)
        assert job.start() is True
        assert ex.started.wait(5) and job.running
        assert job.start() is False  # already running
        ex.release.set()
        assert ex.done.wait(5)
        for _ in range(50):
            if not job.running:
                break
            threading.Event().wait(0.02)
        assert not job.running
        assert job.start() is True  # and can run again

    def test_a_start_while_running_runs_another_pass(self, project):
        """A run that completes mid-pass added sessions the running pass never saw."""
        app = _app(project)
        _give_s1_a_video(app, project)
        ex = _Extractor(hold=True)
        job = _job(app, project, ex)
        assert job.start() is True
        assert ex.started.wait(5)
        assert job.start() is False
        ex.release.set()
        for _ in range(100):
            if not job.running:
                break
            threading.Event().wait(0.02)
        assert not job.running
        assert len(ex.calls) == 2

    def test_stops_between_sessions_when_a_run_starts(self, project):
        app = _app(project)
        v1 = _give_s1_a_video(app, project)
        v2 = project / "s2.mp4"
        v2.write_bytes(b"x")
        db = app.state.db_factory()
        try:
            s2 = db.query(SessionModel).filter_by(session_id="s1").one()
            db.add(SourceFile(session_id=s2.id, file_type="video", path=str(v2), size_bytes=1))
            db.commit()
        finally:
            db.close()
        # A run begins after the first session is handed to the extractor.
        state = {"running": False}
        ex = _Extractor()
        original = ex.__call__

        def extract(videos, out_dir):
            state["running"] = True
            return original(videos, out_dir)

        job = sj.SceneStripJob(app.state.db_factory, lambda: project / "bristlenose-output",
                               lambda: state["running"], extract)
        assert job.start() is True
        for _ in range(100):
            if not job.running:
                break
            threading.Event().wait(0.02)
        assert len(ex.calls) == 1 and list(ex.calls[0][0]) == ["s1"]
        assert v1.exists()

    def test_a_thread_that_cannot_start_releases_the_job(self, project, monkeypatch):
        app = _app(project)
        _give_s1_a_video(app, project)

        class NoThread:
            def __init__(self, *a, **k): ...
            def start(self):
                raise RuntimeError("can't start new thread")

        monkeypatch.setattr(sj.threading, "Thread", NoThread)
        ex = _Extractor()
        job = _job(app, project, ex)
        assert job.start() is False
        assert not job.running
        monkeypatch.undo()
        monkeypatch.delenv("BRISTLENOSE_SCENE_STRIPS", raising=False)
        assert job.start() is True  # the lock was released

    def test_disabled_by_env(self, project, monkeypatch):
        monkeypatch.setenv("BRISTLENOSE_SCENE_STRIPS", "0")
        app = _app(project)
        _give_s1_a_video(app, project)
        ex = _Extractor()
        assert _job(app, project, ex).start() is False
        assert ex.calls == []

    def test_defers_while_a_run_is_in_progress(self, project):
        app = _app(project)
        _give_s1_a_video(app, project)
        ex = _Extractor()
        assert _job(app, project, ex, in_progress=True).start() is False
        assert ex.calls == []

    def test_an_extractor_failure_releases_the_job(self, project):
        app = _app(project)
        _give_s1_a_video(app, project)

        def boom(videos, out_dir):
            raise RuntimeError("ffmpeg missing")

        job = sj.SceneStripJob(app.state.db_factory, lambda: project / "bristlenose-output", lambda: False, boom)
        assert job.start() is True
        for _ in range(50):
            if not job.running:
                break
            threading.Event().wait(0.02)
        assert not job.running
        assert job.start() is True


def _wait(pred, seconds: float = 6.0) -> None:
    deadline = time.monotonic() + seconds
    while not pred():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


class TestWiring:
    def test_a_failed_run_re_arms_a_deferred_job(self, project, monkeypatch):
        """A run's start defers the job. Only run_completed used to start it again, so a run that
        failed left every strip missing until the next restart; any change to the log re-arms it."""
        results: list[bool] = []
        orig = sj.SceneStripJob.start
        monkeypatch.setattr(sj.SceneStripJob, "start", lambda self: results.append(orig(self)) or results[-1])
        app = _app(project)
        events_file = events_path(project / "bristlenose-output")
        proc = Process(pid=os.getpid(), start_time=_TS, hostname="h", user="u", bristlenose_version="0",
                       python_version="3", os="darwin")
        with TestClient(app):
            # The lifespan starts it, and the watcher's first read of the log asks again; both are
            # allowed (nothing is running yet), neither is deferred.
            _wait(lambda: len(results) >= 2)
            assert all(results)
            seen = len(results)
            rid = new_run_id()
            # In progress means a started run whose PID file names a live process (the reducer reads
            # a started run with no PID file as stranded); this process stands in for the run.
            _write_pid_file(project / "bristlenose-output", rid, _ps_start_time(os.getpid()) or "")
            append_event(events_file, RunStartedEvent(ts=_TS, run_id=rid, kind=KindEnum.RUN, started_at=_TS, process=proc))
            _wait(lambda: len(results) > seen)
            assert results[-1] is False  # deferred: a run is in progress
            seen = len(results)
            append_event(events_file, RunFailedEvent(ts=_TS, run_id=rid, kind=KindEnum.RUN, started_at=_TS, ended_at=_TS,
                                                     cause=Cause(category=CauseCategoryEnum.USER_SIGNAL)))
            _wait(lambda: len(results) > seen)
            assert results[-1] is True  # re-armed by the failure, not by a completion

    def test_the_lifespan_starts_the_job(self, project, monkeypatch):
        started: list[bool] = []
        monkeypatch.setattr(sj.SceneStripJob, "start", lambda self: started.append(True) or True)
        app = _app(project)
        with TestClient(app):
            pass
        assert started and all(started)  # once from the lifespan, and the watcher's first read may ask again
        assert isinstance(app.state.scene_strips, sj.SceneStripJob)

    def test_run_completed_starts_the_job_after_publishing(self, project, monkeypatch):
        app = _app(project)
        seen: list[dict] = []

        def start(self):
            seen.append(dict(app.state.last_run.get(1, {})))
            return True

        monkeypatch.setattr(sj.SceneStripJob, "start", start)
        handler = _make_run_completed_handler(app, app.state.db_factory, project)
        rid = new_run_id()
        asyncio.run(handler(RunCompletedEvent(ts=_TS, run_id=rid, kind=KindEnum.RUN, started_at=_TS, ended_at=_TS)))
        assert seen and seen[0].get("run_id") == rid  # published first, then the job

    def test_tapestry_says_pending_while_the_job_runs(self, project):
        app = _app(project)
        _give_s1_a_video(app, project)
        ex = _Extractor(hold=True)
        app.state.scene_strips = _job(app, project, ex)
        client = AuthTestClient(app)
        assert client.get("/api/projects/1/tapestry").json()["strips_pending"] is False
        app.state.scene_strips.start()
        assert ex.started.wait(5)
        assert client.get("/api/projects/1/tapestry").json()["strips_pending"] is True
        ex.release.set()
        assert ex.done.wait(5)
        for _ in range(50):
            if not app.state.scene_strips.running:
                break
            threading.Event().wait(0.02)
        data = client.get("/api/projects/1/tapestry").json()
        assert data["strips_pending"] is False
        assert data["sessions"][0]["strip"] == {"fps": 4, "n": 2, "t0": 0.0, "png": "data:image/png;base64,AA==", "edges": [1.0]}
