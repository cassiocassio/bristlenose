"""The Screens lens's server contract: reason codes, response models, a poll that ends, and the
progress route the Mac app's sidebar row reads (``GET …/screens/status``).

Synthetic indexes and a fake engine, so nothing here needs ffmpeg or Vision.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import get_args

import pytest

from bristlenose.screen_text import INDEX_VERSION, EngineUnavailable, ReadFailure, Unavailable
from bristlenose.screen_text.engine import FakeEngine, VisionEngine
from bristlenose.screen_text.index import cache_key, index_dir
from bristlenose.screen_text.screens import SessionInput, derive_screens
from bristlenose.server.app import create_app
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import SourceFile
from bristlenose.server.routes.screens import (
    Screen,
    ScreenPin,
    ScreensResponse,
    ScreensStatusResponse,
    ScreenTab,
    screens_available,
)
from bristlenose.server.screen_text_job import ScreenTextJob
from bristlenose.utils.fs import CloudFetchTimeoutError
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    import shutil

    p = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, p)
    return p


def _out(project: Path) -> Path:
    return project / "bristlenose-output"


def _app(project: Path, monkeypatch: pytest.MonkeyPatch, on: bool = True):
    if on:
        monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    else:
        monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    # The app's own job reads with Vision; a fake engine makes "can run here" true on any machine.
    app.state.screen_text.engine = FakeEngine(lambda t: [])
    return app


def _give_s1_a_video(app, project: Path, duration: float = 600.0) -> Path:
    video = project / "s1.mp4"
    video.write_bytes(b"x")
    db = app.state.db_factory()
    try:
        sess = db.query(SessionModel).filter_by(session_id="s1").one()
        sess.duration_seconds = duration
        db.add(SourceFile(session_id=sess.id, file_type="video", path=str(video), size_bytes=1))
        db.commit()
    finally:
        db.close()
    return video


def _write_index(project: Path, video: Path, engine, sid: str = "s1", episodes: list | None = None) -> Path:
    d = index_dir(_out(project))
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{sid}.json"
    path.write_text(json.dumps(
        {"version": INDEX_VERSION, "engine": "fake", "engine_version": "1", "every": 4.0, "size": [320, 180],
         "samples": 3, "raw_lines": len(episodes or []), "moments": [], "episodes": episodes or [],
         "key": cache_key(video, engine)}), encoding="utf-8")
    return path


def _line(text: str, y: float) -> dict:
    return {"text": text, "box": [0.1, y, 0.5, 0.03], "sticky": False, "runs": [[0, 60]]}


#: A talking head: plenty of text (a slide, captions), no address bar and no tab title to key on.
_TALKING_HEAD = [_line(f"we talked about the onboarding flow {i}", 0.3 + i * 0.05) for i in range(12)]
#: A browser on one page: an address to key on, and the page's own lines.
_ONE_PAGE = [_line("example.com/gb/en/checkout", 0.03)] + _TALKING_HEAD


class _Captured(logging.Handler):
    """``create_app`` reconfigures logging and drops caplog's handler; listen on the module's own."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        text = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            text += f" {record.exc_info[1]}"
        self.messages.append(text)


# ── Reason codes ──────────────────────────────────────────────────────────


def test_the_vision_engine_says_why_as_a_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert VisionEngine().available() == "not_macos"
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "Vision", None)  # an import that fails
    assert VisionEngine().available() == "vision_missing"
    assert set(get_args(EngineUnavailable)) <= set(get_args(Unavailable))


@pytest.mark.parametrize(("raised", "code", "logged"), [
    # The type, never an OSError's text: it carries a path, and the log goes into support bundles.
    (OSError("permission denied: /secret/path"), "unreadable", "OSError"),
    (CloudFetchTimeoutError("icloud took too long"), "cloud_downloading", "cloud download timed out"),
    (subprocess.CalledProcessError(1, ["ffprobe"], stderr="moov atom not found"), "ffprobe_failed",
     "moov atom not found"),
    (RuntimeError("decoder said no"), "read_failed", "decoder said no"),
])
def test_a_failed_recording_is_a_code_and_its_detail_goes_to_the_log(
        project: Path, monkeypatch: pytest.MonkeyPatch, raised: Exception, code: str, logged: str) -> None:
    app = _app(project, monkeypatch)
    _give_s1_a_video(app, project)

    def boom(*a, **k):
        raise raised
    target = "cache_key" if isinstance(raised, OSError) else "build_index"
    monkeypatch.setattr(f"bristlenose.server.screen_text_job.{target}", boom)
    job = ScreenTextJob(app.state.db_factory, lambda: _out(project), enabled=lambda: True,
                        engine=FakeEngine(lambda t: []))
    log = logging.getLogger("bristlenose.server.screen_text_job")
    cap = _Captured()
    log.addHandler(cap)
    try:
        job._pass()
    finally:
        log.removeHandler(cap)
    assert job.failed == {"s1": code}
    assert code in get_args(ReadFailure)
    assert any(logged in m for m in cap.messages), cap.messages
    assert not any("/secret/path" in m for m in cap.messages)


def test_a_serve_with_no_job_says_no_job(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    app.state.screen_text = None
    client = AuthTestClient(app)
    assert client.get("/api/projects/1/screens").json()["unavailable"] == "no_job"
    assert client.get("/api/projects/1/screens/status").json()["unavailable"] == "no_job"


# ── Response models ──────────────────────────────────────────────────────


def test_the_routes_declare_their_response_models(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    paths = app.openapi()["paths"]

    def ref(path: str) -> str:
        return paths[path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref("/api/projects/{project_id}/screens").endswith("/ScreensResponse")
    assert ref("/api/projects/{project_id}/screens/still").endswith("/StillResponse")
    assert ref("/api/projects/{project_id}/screens/status").endswith("/ScreensStatusResponse")


def test_the_models_carry_every_field_derive_screens_returns() -> None:
    """A field added to ``derive_screens`` and not to the model would be dropped from the response
    silently (response_model filters): the two must name the same fields."""
    def ln(text: str, x: float, y: float, w: float = 0.3, h: float = 0.04) -> dict:
        return {"text": text, "box": [x, y, w, h], "sticky": False, "runs": [[0, 60]]}
    eps = [ln("ikea.com/gb/en/shoppingcart", 0.2, 0.05, 0.4, 0.02), ln("Continue to checkout", 0.5, 0.6),
           ln("Shopping Bag", 0.1, 0.2)]
    eps += [{"text": f"filler {i}", "box": [0.1, 0.3 + i * 0.05, 0.6, 0.02], "sticky": False,
             "runs": [[0, 1000]]} for i in range(10)]
    quotes = [{"dom_id": "q-p1-10", "start": 10, "end": 18, "text": "so I click continue to checkout, I think"},
              {"dom_id": "q-p1-30", "start": 30, "end": 34, "text": "this is quite expensive really"}]
    [screen] = derive_screens([SessionInput("s1", "p1", {"every": 4.0, "episodes": eps, "moments": []},
                                            quotes)])
    [tab] = screen["tabs"]
    assert tab["pins"] and tab["loose"], "the fixture must exercise pins and loose quotes"
    assert set(screen) == set(Screen.model_fields)
    assert set(tab) == set(ScreenTab.model_fields)
    assert set(tab["pins"][0]) == set(ScreenPin.model_fields)
    Screen.model_validate(screen)


def test_the_screens_response_names_the_keys_the_route_builds(project: Path,
                                                              monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert set(body) == set(ScreensResponse.model_fields)


# ── A poll that ends ──────────────────────────────────────────────────────


def test_a_recording_the_idle_job_did_not_read_is_not_read(project: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """The lens polls while a recording has neither an index nor a reason. With the job idle,
    nothing will read it until the next pass, so the answer must be terminal."""
    app = _app(project, monkeypatch)
    _give_s1_a_video(app, project)
    client = AuthTestClient(app)
    body = client.get("/api/projects/1/screens").json()
    assert body["pending"] is False and body["indexed"] == 0 and body["failed"] == {"s1": "not_read"}
    app.state.screen_text.running = True  # while a pass runs, it is waiting, not "not read"
    body = client.get("/api/projects/1/screens").json()
    assert body["pending"] is True and body["failed"] == {}


def test_a_pass_cut_short_by_a_run_waits_for_the_run(project: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    _give_s1_a_video(app, project)
    in_run = threading.Event()  # false when the job starts, true by the time it reaches s1

    def started(*a, **k):
        raise AssertionError("a run started: s1 must not be read")
    monkeypatch.setattr("bristlenose.server.screen_text_job.build_index", started)
    job = ScreenTextJob(app.state.db_factory, lambda: _out(project), run_in_progress=in_run.is_set,
                        enabled=lambda: True, engine=FakeEngine(lambda t: []),
                        busy=lambda: (in_run.set(), False)[1])
    app.state.screen_text = job
    assert job.start()
    deadline = time.time() + 5
    while job.running and time.time() < deadline:
        time.sleep(0.02)
    assert not job.running and job.failed == {}
    # While the run is in progress the recording is waiting for it, not "not read": the run's
    # completion starts the next pass. Reporting not_read here stopped the lens's poll and showed
    # "Couldn't read" through every first analysis (review, 14 Oct 2026).
    client = AuthTestClient(app)
    body = client.get("/api/projects/1/screens").json()
    assert body["failed"] == {}
    status = client.get("/api/projects/1/screens/status").json()
    assert status["done"] == 0
    in_run.clear()  # the run ended and nothing started the job: now nothing will read it
    body = client.get("/api/projects/1/screens").json()
    assert body["failed"] == {"s1": "not_read"}


def test_where_the_engine_cannot_run_nothing_is_not_read(project: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    _give_s1_a_video(app, project)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    app.state.screen_text.engine = VisionEngine()
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["unavailable"] == "not_macos" and body["failed"] == {}


# ── The progress route ────────────────────────────────────────────────────


def test_status_when_off_is_200_and_says_off(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch, on=False)
    _give_s1_a_video(app, project)
    r = AuthTestClient(app).get("/api/projects/1/screens/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "unavailable": None, "running": False, "done": 0, "total": 0,
                        "seconds_done": 0.0, "seconds_total": 0.0, "rate": None, "has_screens": False,
                        "available": False}


def test_status_counts_from_the_database_and_never_decodes(project: Path,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    video = _give_s1_a_video(app, project, duration=600.0)

    def no(*a, **k):
        raise AssertionError("the status route must stay cheap")
    monkeypatch.setattr("bristlenose.server.routes.screens.ensure_materialised", no)
    monkeypatch.setattr("bristlenose.screen_text.index.probe_duration", no)
    client = AuthTestClient(app)
    job = app.state.screen_text

    job.running = True  # reading, s1 not done yet
    job.rate = 40.5
    assert client.get("/api/projects/1/screens/status").json() == {
        "enabled": True, "unavailable": None, "running": True, "done": 0, "total": 1,
        "seconds_done": 0.0, "seconds_total": 600.0, "rate": 40.5, "has_screens": False,
        "available": True}

    _write_index(project, video, job.engine)  # s1 read
    body = client.get("/api/projects/1/screens/status").json()
    assert (body["done"], body["seconds_done"]) == (1, 600.0)

    video.write_bytes(b"a different recording")  # the index no longer describes it: waiting again
    assert client.get("/api/projects/1/screens/status").json()["done"] == 0

    job.failed["s1"] = "read_failed"  # a reason is an answer: not waiting
    assert client.get("/api/projects/1/screens/status").json()["done"] == 1

    job.failed.clear()
    job.running = False  # idle: not_read, not waiting
    body = client.get("/api/projects/1/screens/status").json()
    assert (body["running"], body["done"]) == (False, 1)

    assert client.get("/api/projects/99/screens/status").status_code == 404


def test_a_pass_measures_its_own_rate_from_what_it_read(project: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(project, monkeypatch)
    video = _give_s1_a_video(app, project, duration=600.0)
    engine = FakeEngine(lambda t: [])
    reads: list[str] = []

    def read(v, eng, path, should_stop=lambda: False) -> bool:
        reads.append(v.name)
        _write_index(project, v, eng)
        return True
    monkeypatch.setattr("bristlenose.server.screen_text_job.build_index", read)
    ticks = iter([100.0, 115.0])  # 15 s of wall clock to read 600 s of recording
    job = ScreenTextJob(app.state.db_factory, lambda: _out(project), enabled=lambda: True, engine=engine,
                        clock=lambda: next(ticks))
    assert job.rate is None
    job._pass()
    assert reads == ["s1.mp4"] and job.rate == pytest.approx(40.0)
    job._pass()  # indexed already: a cache hit says nothing about the rate, and this pass read nothing
    assert reads == ["s1.mp4"] and job.rate is None
    assert video.exists()


def test_the_status_response_model_is_the_mac_contract() -> None:
    assert list(ScreensStatusResponse.model_fields) == [
        "enabled", "unavailable", "running", "done", "total", "seconds_done", "seconds_total", "rate",
        "has_screens", "available"]


@pytest.mark.parametrize(("status", "expected"), [
    ({"enabled": False, "unavailable": None, "running": False, "done": 0, "total": 3, "has_screens": True}, False),
    ({"enabled": True, "unavailable": "not_macos", "running": True, "done": 0, "total": 3, "has_screens": True}, False),
    ({"enabled": True, "unavailable": None, "running": False, "done": 3, "total": 3, "has_screens": True}, True),
    ({"enabled": True, "unavailable": None, "running": True, "done": 3, "total": 3, "has_screens": False}, True),
    ({"enabled": True, "unavailable": None, "running": False, "done": 1, "total": 3, "has_screens": False}, True),
    ({"enabled": True, "unavailable": None, "running": False, "done": 3, "total": 3, "has_screens": False}, False),
    ({"enabled": True, "unavailable": None, "running": True, "done": 0, "total": 0, "has_screens": False}, False),
])
def test_the_lens_shows_by_one_rule(status: dict, expected: bool) -> None:
    """Off or impossible: no lens. Screens found: a lens. Still reading: a lens. Read to the end
    with nothing found, or nothing to read: none."""
    assert screens_available(status) is expected


# ── Whether there is anything to show ────────────────────────────────────


@pytest.fixture
def derives(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the route module's derivations, each by how many sessions it was given."""
    from bristlenose.server.routes import screens as routes

    routes._HAS_SCREENS.clear()
    routes._CACHE.clear()
    calls: list[int] = []

    def counted(sessions):
        sessions = list(sessions)
        calls.append(len(sessions))
        return derive_screens(sessions)
    monkeypatch.setattr("bristlenose.server.routes.screens.derive_screens", counted)
    return calls


def test_nothing_indexed_has_no_screens_and_derives_nothing(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                            derives: list[int]) -> None:
    app = _app(project, monkeypatch)
    _give_s1_a_video(app, project)
    client = AuthTestClient(app)
    assert client.get("/api/projects/1/screens/status").json()["has_screens"] is False
    assert derives == []


def test_a_talking_head_has_no_screens_and_two_polls_derive_once(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                                 derives: list[int]) -> None:
    app = _app(project, monkeypatch)
    video = _give_s1_a_video(app, project)
    _write_index(project, video, app.state.screen_text.engine, episodes=_TALKING_HEAD)
    client = AuthTestClient(app)
    for _ in range(2):
        body = client.get("/api/projects/1/screens/status").json()
        assert (body["done"], body["has_screens"]) == (1, False)
    assert derives == [1]


def test_a_derived_screen_has_screens_and_a_new_index_derives_again(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                                    derives: list[int]) -> None:
    app = _app(project, monkeypatch)
    video = _give_s1_a_video(app, project)
    path = _write_index(project, video, app.state.screen_text.engine, episodes=_ONE_PAGE)
    client = AuthTestClient(app)
    assert client.get("/api/projects/1/screens/status").json()["has_screens"] is True
    assert client.get("/api/projects/1/screens/status").json()["has_screens"] is True
    assert derives == [1]
    # The job rewrote the index (a re-read): a new identity, one more derivation, then cached again.
    _write_index(project, video, app.state.screen_text.engine, episodes=_TALKING_HEAD)
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert client.get("/api/projects/1/screens/status").json()["has_screens"] is False
    assert client.get("/api/projects/1/screens/status").json()["has_screens"] is False
    assert derives == [1, 1]


def test_the_lens_derivation_answers_the_status_poll(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                     derives: list[int]) -> None:
    """``/screens`` and ``/screens/status`` share the indexes' identity: what the lens derived, the
    poll does not derive again."""
    app = _app(project, monkeypatch)
    video = _give_s1_a_video(app, project)
    _write_index(project, video, app.state.screen_text.engine, episodes=_ONE_PAGE)
    client = AuthTestClient(app)
    assert client.get("/api/projects/1/screens").json()["screens"]
    assert client.get("/api/projects/1/screens/status").json()["has_screens"] is True
    assert derives == [1]


def test_quotes_never_make_or_remove_a_screen() -> None:
    """Why ``has_screens`` is derived without the quotes, and cached without them in its key."""
    rec = {"every": 4.0, "episodes": _ONE_PAGE, "moments": []}
    quotes = [{"dom_id": "q-p1-10", "start": 10, "end": 14, "text": "the onboarding flow was fine"}]
    with_quotes = derive_screens([SessionInput("s1", "p1", rec, quotes)])
    without = derive_screens([SessionInput("s1", "s1", rec, [])])
    assert with_quotes and {s["key"] for s in with_quotes} == {s["key"] for s in without}
