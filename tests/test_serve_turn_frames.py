"""The tapestry's hover thumbnail in serve: frames_key on /tapestry, GET .../turn-frames, and
the strip job taking the frames (server/tapestry_turns.py, utils/turn_frames.py)."""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server import scene_strips as sj
from bristlenose.server import tapestry_turns as tt
from bristlenose.server.app import create_app
from bristlenose.server.models import Session as SessionModel
from bristlenose.server.models import SourceFile
from bristlenose.utils import turn_frames as tf
from tests.conftest import LOOPBACK_BASE_URL, AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "input"
    shutil.copytree(_FIXTURE_DIR, p)
    return p


def _out(project: Path) -> Path:
    return project / "bristlenose-output"


def _app(project: Path):
    return create_app(project_dir=project, dev=True, db_url="sqlite://")


def _write_strip(project: Path, changes: list[float]) -> None:
    d = _out(project) / ".bristlenose" / "intermediate" / "scene-strips"
    d.mkdir(parents=True, exist_ok=True)
    d.joinpath("s1.json").write_text(json.dumps(
        {"version": 2, "key": "k", "fps": 4, "n": 2, "t0": 0.0, "png": "AA==", "edges": [], "changes": changes}))


def _turns(app) -> list[tuple[float, float]]:
    db = app.state.db_factory()
    try:
        return tt.all_participant_turns(db)["s1"]
    finally:
        db.close()


def _give_s1_a_video(app, project: Path) -> Path:
    """The smoke fixture has no recording; point s1 at a file that exists."""
    video = project / "s1.mp4"
    video.write_bytes(b"x")
    db = app.state.db_factory()
    try:
        sess = db.query(SessionModel).filter_by(session_id="s1").one()
        db.add(SourceFile(session_id=sess.id, file_type="video", path=str(video), size_bytes=1))
        db.commit()
    finally:
        db.close()
    return video


def _write_frames(app, project: Path, turns: list[tuple[float, float]], changes: list[float]) -> Path:
    video = project / "s1.mp4"
    video.write_bytes(b"x")
    frames = tf.select_frames(turns, changes)
    path = tf.extract_turn_frames("s1", video, frames, tt.frames_dir(_out(project)),
                                  grabber=lambda v, t: b"\xff\xd8" + str(t).encode())
    assert path is not None
    return path


class _FakeJob:
    def __init__(self) -> None:
        self.running = False
        self.starts = 0

    def start(self) -> bool:
        self.starts += 1
        self.running = True
        return True


def _session(client: TestClient) -> dict:
    return client.get("/api/projects/1/tapestry").json()["sessions"][0]


def test_the_smoke_fixture_has_participant_turns(project: Path) -> None:
    assert _turns(_app(project))  # every test below would be vacuous without them


def test_no_strip_means_no_frames_and_no_pass(project: Path) -> None:
    app = _app(project)
    app.state.scene_strips = job = _FakeJob()
    client = AuthTestClient(app)
    assert _session(client)["frames_key"] is None
    assert job.starts == 0
    assert client.get("/api/projects/1/sessions/s1/turn-frames").status_code == 404


def test_a_strip_without_frames_asks_the_job_for_a_pass(project: Path) -> None:
    _write_strip(project, [])
    app = _app(project)
    _give_s1_a_video(app, project)
    app.state.scene_strips = job = _FakeJob()
    client = AuthTestClient(app)
    data = client.get("/api/projects/1/tapestry").json()
    assert data["sessions"][0]["frames_key"] is None
    assert job.starts == 1 and data["strips_pending"] is True  # the grid polls until they land


def test_current_frames_are_keyed_and_served(project: Path) -> None:
    changes = [7.5]
    _write_strip(project, changes)
    app = _app(project)
    path = _write_frames(app, project, _turns(app), changes)
    app.state.scene_strips = job = _FakeJob()
    client = AuthTestClient(app)
    data = client.get("/api/projects/1/tapestry").json()
    key = json.loads(path.read_text())["key"]
    assert data["sessions"][0]["frames_key"] == key
    assert job.starts == 0 and data["strips_pending"] is False
    body = client.get("/api/projects/1/sessions/s1/turn-frames").json()
    assert body["key"] == key
    want = tf.select_frames(_turns(app), changes)
    assert [(f["t"], f["a"], f["b"], f["change"]) for f in body["frames"]] == [
        (f["t"], f["a"], f["b"], f["change"]) for f in want]
    assert all(f["src"].startswith("data:image/jpeg;base64,") for f in body["frames"])


def test_frames_taken_for_other_turns_are_stale(project: Path) -> None:
    # A paragraph split or moved since the frames were taken: the turns no longer match.
    _write_strip(project, [])
    app = _app(project)
    _give_s1_a_video(app, project)
    _write_frames(app, project, [(t0, t1 + 1.0) for t0, t1 in _turns(app)], [])
    app.state.scene_strips = job = _FakeJob()
    client = AuthTestClient(app)
    assert _session(client)["frames_key"] is None
    assert job.starts == 1


def test_a_strip_whose_recording_has_gone_asks_for_nothing(project: Path) -> None:
    # The pass could never take its frames, so asking would restart it on every poll.
    _write_strip(project, [])
    app = _app(project)
    app.state.scene_strips = job = _FakeJob()
    client = AuthTestClient(app)
    data = client.get("/api/projects/1/tapestry").json()
    assert job.starts == 0 and data["strips_pending"] is False


def test_a_busy_job_is_not_started_again(project: Path) -> None:
    _write_strip(project, [])
    app = _app(project)
    _give_s1_a_video(app, project)
    app.state.scene_strips = job = _FakeJob()
    job.running = True
    client = AuthTestClient(app)
    assert client.get("/api/projects/1/tapestry").json()["strips_pending"] is True
    assert job.starts == 0


def test_a_failure_written_down_is_not_asked_for_again_on_every_poll(project: Path) -> None:
    # Every grab failed (ffmpeg missing, a download timed out): the record says so, for the
    # current turns, and the route neither offers frames nor starts a pass.
    _write_strip(project, [])
    app = _app(project)
    video = _give_s1_a_video(app, project)
    tf.extract_turn_frames("s1", video, tf.select_frames(_turns(app), []), tt.frames_dir(_out(project)),
                           grabber=lambda v, t: None)
    app.state.scene_strips = job = _FakeJob()
    client = AuthTestClient(app)
    data = client.get("/api/projects/1/tapestry").json()
    assert data["sessions"][0]["frames_key"] is None
    assert job.starts == 0 and data["strips_pending"] is False


def test_frames_need_the_bearer(project: Path) -> None:
    # Participants' screens: never one unauthenticated GET away for a local process.
    _write_strip(project, [])
    app = _app(project)
    _write_frames(app, project, _turns(app), [])
    bare = TestClient(app, base_url=LOOPBACK_BASE_URL)
    assert bare.get("/api/projects/1/sessions/s1/turn-frames").status_code == 401


def test_unknown_project_or_session_is_404(project: Path) -> None:
    client = AuthTestClient(_app(project))
    assert client.get("/api/projects/9/sessions/s1/turn-frames").status_code == 404
    assert client.get("/api/projects/1/sessions/s9/turn-frames").status_code == 404


def test_the_strip_job_takes_frames_after_each_strip(project: Path, monkeypatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCENE_STRIPS", raising=False)
    app = _app(project)
    video = _give_s1_a_video(app, project)

    def extractor(videos: dict[str, Path], out_dir: Path) -> dict[str, Path]:
        _write_strip(project, [7.5])
        return {sid: out_dir / f"{sid}.json" for sid in videos}

    calls: list[tuple[str, Path, list[tf.Frame], Path]] = []
    done = threading.Event()

    def framer(sid: str, v: Path, frames: list[tf.Frame], out_dir: Path) -> Path | None:
        calls.append((sid, v, frames, out_dir))
        done.set()
        return None

    job = sj.SceneStripJob(app.state.db_factory, lambda: _out(project), lambda: False, extractor, framer)
    assert job.start() is True
    assert done.wait(5)
    assert calls == [("s1", video, tf.select_frames(_turns(app), [7.5]), tt.frames_dir(_out(project)))]
