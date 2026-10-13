"""The Screens lens in serve: GET …/screens, GET …/screens/still, and the screen-text job."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from bristlenose.screen_text.engine import FakeEngine
from bristlenose.screen_text.index import index_dir
from bristlenose.server.app import create_app
from bristlenose.server.models import Quote, SourceFile
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.screen_text_job import ScreenTextJob
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, p)
    return p


def _out(project: Path) -> Path:
    return project / "bristlenose-output"


def _give_s1_a_video(app, project: Path, real: bool = False) -> Path:
    video = project / "s1.mp4"
    if real:
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc=size=320x180:rate=5:duration=9", "-pix_fmt", "yuv420p", str(video)], check=True)
    else:
        video.write_bytes(b"x")
    db = app.state.db_factory()
    try:
        sess = db.query(SessionModel).filter_by(session_id="s1").one()
        db.add(SourceFile(session_id=sess.id, file_type="video", path=str(video), size_bytes=1))
        db.commit()
    finally:
        db.close()
    return video


def _first_quote(app) -> Quote:
    db = app.state.db_factory()
    try:
        return db.query(Quote).filter_by(session_id="s1").order_by(Quote.start_timecode).first()
    finally:
        db.close()


def _write_index(project: Path, lines: list[dict], t0: float, t1: float) -> None:
    eps = [{"text": "example.com/gb/en/checkout", "box": [0.2, 0.03, 0.4, 0.02], "sticky": False, "runs": [[t0, t1]]}]
    eps += [{"text": ln["text"], "box": ln["box"], "sticky": False, "runs": [[t0, t1]]} for ln in lines]
    eps += [{"text": f"filler line {i}", "box": [0.05, 0.3 + i * 0.05, 0.7, 0.02], "sticky": False,
             "runs": [[t0, t1]]} for i in range(10)]
    d = index_dir(_out(project))
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath("s1.json").write_text(json.dumps(
        {"version": 1, "engine": "fake", "engine_version": "1", "every": 4.0, "size": [320, 180],
         "samples": 3, "moments": [t0], "episodes": eps, "key": "k"}))


def test_screens_are_off_unless_asked_for(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["enabled"] is False and body["screens"] == []
    r = AuthTestClient(app).get("/api/projects/1/screens/still", params={"session_id": "s1", "t": 1})
    assert r.status_code == 404


def test_a_quote_said_on_a_screen_is_pinned_to_the_line_it_shares(project: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project)
    q = _first_quote(app)
    words = [w for w in (q.verbatim_excerpt or q.text).split() if len(w) >= 5][:3]
    assert len(words) >= 2, "the smoke fixture's first quote needs two long words"
    _write_index(project, [{"text": " ".join(words), "box": [0.4, 0.5, 0.3, 0.04]}],
                 q.start_timecode - 4, q.end_timecode + 4)
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["enabled"] is True and body["indexed"] == 1
    [screen] = body["screens"]
    assert screen["name"] == "/checkout"
    [tab] = screen["tabs"]
    assert tab["session_id"] == "s1" and tab["code"] == q.participant_id
    assert [p["dom_id"] for p in tab["pins"]] == [f"q-{q.participant_id}-{int(q.start_timecode)}"]


def test_the_still_route_refuses_a_bad_crop(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    client = AuthTestClient(app)
    for crop in ("0,0,2,1", "a,b,c,d", "0.5,0.5,0.52,0.52"):
        r = client.get("/api/projects/1/screens/still", params={"session_id": "s1", "t": 1, "crop": crop})
        assert r.status_code == 422, crop
    r = client.get("/api/projects/1/screens/still", params={"session_id": "nope", "t": 1})
    assert r.status_code == 404


@pytest.mark.skipif(not _HAS_FFMPEG, reason="needs ffmpeg")
def test_a_still_is_a_cropped_jpeg_and_is_cached(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project, real=True)
    client = AuthTestClient(app)
    params = {"session_id": "s1", "t": 2, "w": 200, "crop": "0,0.1,0.9,1"}
    src = client.get("/api/projects/1/screens/still", params=params).json()["src"]
    assert src.startswith("data:image/jpeg;base64,/9j/")
    assert list((index_dir(_out(project)) / "stills").glob("*.jpg"))
    assert client.get("/api/projects/1/screens/still", params=params).json()["src"] == src


@pytest.mark.skipif(not _HAS_FFMPEG, reason="needs ffmpeg")
def test_the_job_indexes_each_recording_with_the_engine(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project, real=True)
    seen: list[float] = []
    engine = FakeEngine(lambda t: seen.append(t) or [{"text": "Checkout", "conf": 0.9, "box": [0.1, 0.4, 0.2, 0.03]}])
    job = ScreenTextJob(app.state.db_factory, lambda: _out(project), enabled=lambda: True, engine=engine)
    assert job.start()
    deadline = time.time() + 30
    while job.running and time.time() < deadline:
        time.sleep(0.05)
    rec = json.loads((index_dir(_out(project)) / "s1.json").read_text())
    assert rec["engine"] == "fake" and rec["samples"] == len(seen) >= 2


def test_the_job_does_nothing_when_off_or_while_a_run_is_in_progress(project: Path) -> None:
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    engine = FakeEngine(lambda t: [])
    assert not ScreenTextJob(app.state.db_factory, lambda: _out(project), enabled=lambda: False,
                             engine=engine).start()
    assert not ScreenTextJob(app.state.db_factory, lambda: _out(project), run_in_progress=lambda: True,
                             enabled=lambda: True, engine=engine).start()


def test_a_start_while_a_pass_runs_asks_for_another_pass(project: Path) -> None:
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    release = threading.Event()
    passes: list[int] = []

    class Slow(ScreenTextJob):
        def _pass(self) -> None:
            passes.append(1)
            release.wait(5)

    job = Slow(app.state.db_factory, lambda: _out(project), enabled=lambda: True, engine=FakeEngine(lambda t: []))
    assert job.start()
    assert not job.start()  # a pass is running: asks for another instead
    release.set()
    deadline = time.time() + 5
    while job.running and time.time() < deadline:
        time.sleep(0.02)
    assert len(passes) == 2
