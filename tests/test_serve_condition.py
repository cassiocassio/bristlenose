"""The serve follows the project's condition while it runs — end to end.

Each test reproduces a verified defect with the real app, the real lifespan
and the live event watcher (docs/design-project-condition.md §4 and appendix):

* F4  — a run that fails while the serve is up was invisible until restart;
* N19 — ``--clean`` replaces the events log and the line-counting watcher
  never saw the new run's completion, so Re-analyse never reached the report;
* N46 — a serve started before the first run watched the interview folder;
* F6  — a failed re-import was still published as the new data version.
"""

from __future__ import annotations

import functools
import time
from pathlib import Path
from unittest.mock import patch

import pytest

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
)
from bristlenose.server import event_watcher
from bristlenose.server.app import create_app
from bristlenose.server.importer import import_project as real_import
from tests.conftest import AuthTestClient

_VITE_INDEX_HTML = (
    '<!doctype html><html><head></head><body>'
    '<div id="bn-app-root"></div></body></html>'
)
_PROC = Process(pid=1, start_time="1.0", hostname="h", user="u",
                bristlenose_version="0", python_version="3.12", os="darwin-arm64")


def _started(out: Path, rid: str) -> None:
    append_event(events_path(out), RunStartedEvent(
        ts="t", run_id=rid, kind=KindEnum.RUN, started_at="t", process=_PROC))


def _completed(out: Path, rid: str) -> None:
    append_event(events_path(out), RunCompletedEvent(
        ts="t", run_id=rid, kind=KindEnum.RUN, started_at="t", ended_at="t"))


def _failed(out: Path, rid: str) -> None:
    append_event(events_path(out), RunFailedEvent(
        ts="t", run_id=rid, kind=KindEnum.RUN, started_at="t", ended_at="t",
        cause=Cause(category=CauseCategoryEnum.OUT_OF_CREDIT, message="no credit")))


@pytest.fixture()
def fast_watcher(monkeypatch: pytest.MonkeyPatch):
    fast = functools.partial(event_watcher.run_event_watcher, poll_interval=0.05)
    monkeypatch.setattr(event_watcher, "run_event_watcher", fast)


def _app(project_dir: Path, tmp_path: Path):
    static = tmp_path / "static"
    static.mkdir(exist_ok=True)
    (static / "index.html").write_text(_VITE_INDEX_HTML)
    (static / "assets").mkdir(exist_ok=True)
    # A file database, not "sqlite://": the in-memory one is a StaticPool — one
    # connection for every thread — so the watcher's re-import (a worker thread)
    # and the test's polling requests shared a transaction, and a request's
    # rollback could wipe the import mid-flight (StaleDataError on `projects`,
    # 5 of 5 ubuntu cells on 28 Sep 2026, ~1 in 25 locally). Production opens a
    # connection per thread; so does this.
    with patch("bristlenose.server.app._STATIC_DIR", static):
        return create_app(project_dir=project_dir, dev=False,
                          db_url=f"sqlite:///{tmp_path / 'serve.db'}")


def _wait(pred, timeout: float = 3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def _latest(client) -> dict | None:
    return client.get("/api/projects/1/condition").json()["condition"]["latest"]


def test_failure_while_serve_is_up_reaches_the_page(tmp_path: Path, fast_watcher) -> None:
    out = tmp_path / "bristlenose-output"
    _started(out, "A")
    _completed(out, "A")
    app = _app(tmp_path, tmp_path)
    with AuthTestClient(app) as client:
        assert 'id="bn-app-root"' in client.get("/report/").text
        _started(out, "B")
        _failed(out, "B")
        assert _wait(lambda: (_latest(client) or {}).get("state") == "failed")
        page = client.get("/report/").text
        assert "Last run failed." in page
        assert "no credit" in page
        # /last-run is the data version: still the report that is on disk.
        assert client.get("/api/projects/1/last-run").json()["run_id"] == "A"


def test_clean_rerun_replacing_the_log_is_seen(tmp_path: Path, fast_watcher) -> None:
    out = tmp_path / "bristlenose-output"
    for i in range(6):  # a long history for the old line-count baseline
        _started(out, f"old{i}")
        _completed(out, f"old{i}")
    reimported: list[str] = []
    armed = {"on": False}

    def _import(db, pd):
        if armed["on"]:
            reimported.append("yes")
        else:
            real_import(db, pd)  # startup import creates the project row

    # Patched before the app is built: the handler binds import_project then.
    with patch("bristlenose.server.importer.import_project", side_effect=_import):
        app = _app(tmp_path, tmp_path)
        with AuthTestClient(app) as client:
            armed["on"] = True
            # --clean moves the whole output folder aside; the new run writes a
            # fresh log shorter than the one the watcher baselined.
            (out.parent / "stash").mkdir()
            out.rename(out.parent / "stash" / "bristlenose-output")
            _started(out, "NEW")
            _completed(out, "NEW")
            assert _wait(lambda: (_latest(client) or {}).get("run_id") == "NEW")
            assert _wait(lambda: reimported == ["yes"])
            assert _wait(
                lambda: client.get("/api/projects/1/last-run").json()["run_id"] == "NEW")


def test_serve_started_before_first_run_follows_the_output(
    tmp_path: Path, fast_watcher,
) -> None:
    interviews = tmp_path / "interviews"
    interviews.mkdir()
    (interviews / "s1.vtt").write_text("WEBVTT\n")
    with patch("bristlenose.server.importer.import_project", side_effect=real_import):
        app = _app(interviews, tmp_path)
        with AuthTestClient(app) as client:
            assert "Nothing to see here" in client.get("/report/").text
            out = interviews / "bristlenose-output"
            _started(out, "A")
            _completed(out, "A")
            assert _wait(lambda: (_latest(client) or {}).get("state") == "completed")
            assert _wait(
                lambda: client.get("/api/projects/1/last-run").json() is not None)


def test_failed_import_is_not_published(tmp_path: Path, fast_watcher) -> None:
    out = tmp_path / "bristlenose-output"
    _started(out, "A")
    _completed(out, "A")
    armed = {"on": False}

    def _import(db, pd):
        if armed["on"]:
            raise RuntimeError("disk full")
        real_import(db, pd)

    with patch("bristlenose.server.importer.import_project", side_effect=_import):
        app = _app(tmp_path, tmp_path)
        with AuthTestClient(app) as client:
            armed["on"] = True
            _started(out, "B")
            _completed(out, "B")
            assert _wait(lambda: client.get("/api/projects/1/condition").json()
                         ["import_failed_run_id"] == "B")
            # The data version still names the report the database holds.
            assert client.get("/api/projects/1/last-run").json()["run_id"] == "A"


def test_status_page_carries_its_condition_and_refreshes(tmp_path: Path) -> None:
    out = tmp_path / "bristlenose-output"
    _started(out, "A")
    _failed(out, "A")
    app = _app(tmp_path, tmp_path)
    with AuthTestClient(app) as client:
        page = client.get("/report/").text
    assert 'data-condition="A:failed|-|1"' in page
    assert "setInterval(tick" in page


def _pid_file(out: Path, run_id: str, *, alive: bool) -> None:
    """Point run.pid at this (live) process, or at a start time no process has."""
    import json as _json
    import os

    from bristlenose.run_lifecycle import _ps_start_time, pid_file_path

    start = _ps_start_time(os.getpid()) if alive else "0.000001"
    # Our own PID's start time is readable on every platform we test on; if it
    # is not, that is a failure to see, not a test to skip.
    assert not (alive and start is None), "process start time unavailable"
    path = pid_file_path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({"pid": os.getpid(), "start_time": start, "run_id": run_id}))


def test_owner_dying_without_a_terminus_is_noticed(tmp_path: Path, fast_watcher) -> None:
    """SIGKILL / OOM / crash writes nothing to the log. The cached in-progress
    must not outlive the process (review finding: it did, until restart)."""
    out = tmp_path / "bristlenose-output"
    _started(out, "A")
    _pid_file(out, "A", alive=True)
    app = _app(tmp_path, tmp_path)
    with AuthTestClient(app) as client:
        assert _latest(client)["state"] == "in_progress"
        assert "Analysing" in client.get("/report/").text
        _pid_file(out, "A", alive=False)  # the process is gone; the log is unchanged
        assert _latest(client)["state"] == "stranded"
        assert "stopped unexpectedly" in client.get("/report/").text


def test_run_seen_before_its_pid_file_recovers(tmp_path: Path, fast_watcher) -> None:
    """run_started lands before run.pid is written; a poll in that gap must not
    pin the run as stranded for its whole life."""
    out = tmp_path / "bristlenose-output"
    _started(out, "A")
    app = _app(tmp_path, tmp_path)
    with AuthTestClient(app) as client:
        assert _latest(client)["state"] == "stranded"
        _pid_file(out, "A", alive=True)
        assert _latest(client)["state"] == "in_progress"


def test_restore_without_a_new_run_is_noticed(tmp_path: Path, fast_watcher) -> None:
    """A failed --clean run is restored onto the old tree: the file changes but
    no new run id appears. The report must come back (review finding)."""
    import shutil

    out = tmp_path / "bristlenose-output"
    _started(out, "A")
    _completed(out, "A")
    app = _app(tmp_path, tmp_path)
    with AuthTestClient(app) as client:
        stash = tmp_path / "stash"
        stash.mkdir()
        out.rename(stash / "bristlenose-output")
        _started(out, "B")
        _failed(out, "B")
        assert _wait(lambda: client.get("/api/projects/1/condition").json()
                     ["condition"]["report"] is None)
        # restore: old tree back, the failed run's history appended to it
        failed_log = events_path(out).read_text()
        shutil.rmtree(out)
        (stash / "bristlenose-output").rename(out)
        with events_path(out).open("a") as fh:
            fh.write(failed_log)
        assert _wait(lambda: (client.get("/api/projects/1/condition").json()
                              ["condition"]["report"] or {}).get("run_id") == "A")
