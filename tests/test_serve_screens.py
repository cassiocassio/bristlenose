"""The Screens lens in serve: GET …/screens, GET …/screens/still, and the screen-text job."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from bristlenose.screen_text import INDEX_VERSION
from bristlenose.screen_text.engine import FakeEngine
from bristlenose.screen_text.index import cache_key, index_dir
from bristlenose.server.app import create_app
from bristlenose.server.models import Quote, SourceFile
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.scene_strips import video_sessions
from bristlenose.server.screen_text_job import ScreenTextJob
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
# One marker, as test_format_ingest_coverage.py does: CI's Linux cells install ffmpeg.
_needs_ffmpeg = pytest.mark.skipif(not _HAS_FFMPEG, reason="needs ffmpeg")


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


def _write_index(app, project: Path, lines: list[dict], t0: float, t1: float, raw_lines: int = 20) -> None:
    eps = [{"text": "example.com/gb/en/checkout", "box": [0.2, 0.03, 0.4, 0.02], "sticky": False, "runs": [[t0, t1]]}]
    eps += [{"text": ln["text"], "box": ln["box"], "sticky": False, "runs": [[t0, t1]]} for ln in lines]
    eps += [{"text": f"filler line {i}", "box": [0.05, 0.3 + i * 0.05, 0.7, 0.02], "sticky": False,
             "runs": [[t0, t1]]} for i in range(10)]
    d = index_dir(_out(project))
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath("s1.json").write_text(json.dumps(
        {"version": INDEX_VERSION, "engine": "fake", "engine_version": "1", "every": 4.0, "size": [320, 180],
         "samples": 3, "raw_lines": raw_lines, "moments": [t0], "episodes": eps,
         "key": cache_key(project / "s1.mp4", app.state.screen_text.engine)}))


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
    _write_index(app, project, [{"text": " ".join(words), "box": [0.4, 0.5, 0.3, 0.04]}],
                 q.start_timecode - 4, q.end_timecode + 4)
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["enabled"] is True and body["indexed"] == 1
    [screen] = body["screens"]
    assert screen["name"] == "/checkout"
    [tab] = screen["tabs"]
    assert tab["session_id"] == "s1" and tab["code"] == q.participant_id
    assert [p["dom_id"] for p in tab["pins"]] == [f"q-{q.participant_id}-{int(q.start_timecode)}"]


def test_a_second_quote_in_the_second_is_its_own_pin(project: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """Two quotes with one start, both said on the screen, are two pins (R86)."""
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project)
    db = app.state.db_factory()
    try:
        first = db.query(Quote).filter_by(project_id=1).order_by(Quote.start_timecode).first()
        second = Quote(project_id=1, session_id=first.session_id, participant_id="p1",
                       start_timecode=first.start_timecode, ordinal=1, end_timecode=first.end_timecode,
                       text=first.text, verbatim_excerpt=first.verbatim_excerpt,
                       quote_type=first.quote_type, topic_label=first.topic_label)
        db.add(second)
        db.commit()
    finally:
        db.close()
    q = _first_quote(app)
    words = [w for w in (q.verbatim_excerpt or q.text).split() if len(w) >= 5][:3]
    _write_index(app, project, [{"text": " ".join(words), "box": [0.4, 0.5, 0.3, 0.04]}],
                 q.start_timecode - 4, q.end_timecode + 4)
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    [screen] = body["screens"]
    [tab] = screen["tabs"]
    assert sorted(p["dom_id"] for p in tab["pins"]) == ["q-p1-10", "q-p1-10-1"]


def test_the_still_route_refuses_a_bad_crop(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    client = AuthTestClient(app)
    for crop in ("0,0,2,1", "a,b,c,d", "0.5,0.5,0.52,0.52"):
        r = client.get("/api/projects/1/screens/still", params={"session_id": "s1", "t": 1, "crop": crop})
        assert r.status_code == 422, crop
    r = client.get("/api/projects/1/screens/still", params={"session_id": "nope", "t": 1})
    assert r.status_code == 404


@_needs_ffmpeg
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


@_needs_ffmpeg
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
    # ffmpeg's fps filter gives 0 and 4 for 9 s: exactly two.
    assert rec["engine"] == "fake" and rec["samples"] == len(seen) == 2
    assert job.failed == {}


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


def test_a_changed_recording_is_pending_and_a_textless_one_is_blank(project: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    video = _give_s1_a_video(app, project)
    _write_index(app, project, [], 0, 8, raw_lines=0)
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["indexed"] == 1 and body["blank"] == ["s1"]
    video.write_bytes(b"a different recording")  # the index no longer describes it
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["indexed"] == 0 and body["blank"] == []


@_needs_ffmpeg
def test_one_unreadable_recording_does_not_stop_the_others(project: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project, real=True)
    # A second session whose "video" has no picture, read first.
    audio = project / "s0.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=duration=3",
                    "-c:a", "aac", str(audio)], check=True)
    real = video_sessions

    def two(db):
        return {"s0": audio, **real(db)}
    monkeypatch.setattr("bristlenose.server.screen_text_job.video_sessions", two)
    monkeypatch.setattr("bristlenose.server.routes.screens.video_sessions", two)
    engine = FakeEngine(lambda t: [{"text": "Checkout", "conf": 0.9, "box": [0.1, 0.4, 0.2, 0.03]}])
    job = ScreenTextJob(app.state.db_factory, lambda: _out(project), enabled=lambda: True, engine=engine)
    app.state.screen_text = job
    assert job.start()
    deadline = time.time() + 30
    while job.running and time.time() < deadline:
        time.sleep(0.05)
    assert (index_dir(_out(project)) / "s1.json").exists()
    assert job.failed["s0"] == "read_failed"  # a case, not ValueError's sentence
    body = AuthTestClient(app).get("/api/projects/1/screens").json()
    assert body["pending"] is False and "s0" in body["failed"] and body["indexed"] == 1


@_needs_ffmpeg
def test_stills_are_named_for_their_session(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project, real=True)
    AuthTestClient(app).get("/api/projects/1/screens/still", params={"session_id": "s1", "t": 2, "w": 120})
    [still] = (index_dir(_out(project)) / "stills").glob("*.jpg")
    assert still.name.startswith("s1_")  # so the per-session prune removes a withdrawn participant's


def test_a_recording_that_failed_is_not_read_again_until_it_changes(project: Path,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    video = _give_s1_a_video(app, project)
    calls: list[str] = []

    def fail(v, *a, **k):
        calls.append(v.name)
        raise RuntimeError("decoder said no")
    monkeypatch.setattr("bristlenose.server.screen_text_job.build_index", fail)
    job = ScreenTextJob(app.state.db_factory, lambda: _out(project), enabled=lambda: True,
                        engine=FakeEngine(lambda t: []))
    job._pass()
    job._pass()
    assert calls == ["s1.mp4"] and job.failed["s1"] == "read_failed"
    video.write_bytes(b"replaced")
    job._pass()
    assert calls == ["s1.mp4", "s1.mp4"]


def test_the_job_waits_for_the_scene_strips(project: Path) -> None:
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    strips_busy = threading.Event()
    strips_busy.set()
    passes: list[float] = []

    class Counting(ScreenTextJob):
        def _pass(self) -> None:
            super()._pass()
            passes.append(time.time())

    job = Counting(app.state.db_factory, lambda: _out(project), enabled=lambda: True,
                   engine=FakeEngine(lambda t: []), busy=strips_busy.is_set)
    assert job.start()
    time.sleep(1.5)
    assert passes == []  # still waiting
    strips_busy.clear()
    deadline = time.time() + 5
    while job.running and time.time() < deadline:
        time.sleep(0.05)
    assert len(passes) == 1
