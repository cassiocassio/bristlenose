"""Export the Screens lens's stills as a folder (routes/screens_export.py)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient
from tests.test_serve_screens import (  # noqa: F401
    _give_s1_a_video,
    _needs_ffmpeg,
    _out,
    _write_index,
    project,
)

_BASE = "/api/projects/1/export/screens"


def _finish(client: AuthTestClient) -> dict:
    deadline = time.time() + 30
    while time.time() < deadline:
        body = client.get(f"{_BASE}/status").json()
        if body["status"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError("the export never finished")


def _width(jpg: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width", "-of", "csv=p=0", str(jpg)], capture_output=True, text=True)
    return int(out.stdout.strip())


def test_a_same_second_pair_is_two_keys_on_the_board(tmp_path: Path) -> None:
    """The board names quotes by DOM id: a second quote in the second is its own key, and a
    hidden one is hidden under that key (R86)."""
    from bristlenose.server.models import Quote, QuoteState
    from bristlenose.server.routes import screens_export as se

    fixture = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
    app = create_app(project_dir=fixture, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    try:
        first = (db.query(Quote).filter_by(project_id=1).order_by(Quote.start_timecode).first())
        second = Quote(project_id=1, session_id=first.session_id, participant_id="p1",
                       start_timecode=first.start_timecode, ordinal=1, end_timecode=60.0,
                       text="the second half", quote_type=first.quote_type, topic_label="")
        db.add(second)
        db.commit()
        quotes = se._quotes_by_dom_id(db, 1)
        assert quotes["q-p1-10"].quote_id == first.id
        assert quotes["q-p1-10-1"].quote_id == second.id
        db.add(QuoteState(quote_id=second.id, is_hidden=True))
        db.commit()
        assert se._hidden_dom_ids(db, 1) == {"q-p1-10-1"}
        assert "q-p1-10-1" not in se._quotes_by_dom_id(db, 1)  # hidden rows leave the export
    finally:
        db.close()


@_needs_ffmpeg
def test_each_still_is_written_full_size_and_replaces_the_last_export(
        project: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    _give_s1_a_video(app, project, real=True)
    _write_index(app, project, [{"text": "Your basket", "box": [0.4, 0.5, 0.3, 0.04]}], 1, 8)
    folder = _out(project) / "screens"
    folder.mkdir(parents=True)
    (folder / "p1-07.jpg").write_bytes(b"from an earlier export")
    (folder / ".screens_manifest.json").write_text(json.dumps({"files": ["p1-07.jpg"]}), encoding="utf-8")
    (folder / "notes.txt").write_text("the researcher's own", encoding="utf-8")
    with AuthTestClient(app) as client:
        x0, _, x1, _ = client.get("/api/projects/1/screens").json()["screens"][0]["tabs"][0]["crop"]
        started = client.post(_BASE).json()
        assert {k: started[k] for k in ("status", "total")} == {"status": "started", "total": 1}
        body = _finish(client)
    assert body["status"] == "completed" and body["files"] == ["p1-01.jpg"]
    jpg = folder / "p1-01.jpg"
    assert jpg.read_bytes()[:3] == b"\xff\xd8\xff"
    # The page's crop at the recording's own size (320 px wide), not scaled as the lens asks.
    assert abs(_width(jpg) - (x1 - x0) * 320) <= 2
    assert not (folder / "p1-07.jpg").exists()  # named by the last manifest: removed
    assert (folder / "notes.txt").exists()  # not named: left alone
    assert json.loads((folder / ".screens_manifest.json").read_text(encoding="utf-8"))["files"] == ["p1-01.jpg"]


def test_nothing_is_exported_while_screens_are_off(project: Path,  # noqa: F811
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRISTLENOSE_SCREEN_TEXT", raising=False)
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert AuthTestClient(app).post(_BASE).status_code == 404


def test_a_study_with_no_screens_says_so(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    monkeypatch.setenv("BRISTLENOSE_SCREEN_TEXT", "1")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    assert AuthTestClient(app).post(_BASE).json() == {"status": "no_screens", "total": 0,
                                                       "job_id": None}


def test_a_name_is_written_in_the_folder_and_a_link_there_is_replaced_not_followed(tmp_path: Path) -> None:
    from bristlenose.server.routes.screens_export import _write_inside

    target = tmp_path / "elsewhere.txt"
    target.write_text("keep me", encoding="utf-8")
    folder = tmp_path / "screens"
    folder.mkdir()
    (folder / "p1-01.jpg").symlink_to(target)
    _write_inside(folder, "p1-01.jpg", b"jpeg")
    assert target.read_text(encoding="utf-8") == "keep me"
    assert not (folder / "p1-01.jpg").is_symlink() and (folder / "p1-01.jpg").read_bytes() == b"jpeg"
    for bad in ("../x.jpg", "/tmp/x.jpg", ".hidden.jpg"):
        with pytest.raises(OSError):
            _write_inside(folder, bad, b"jpeg")


# ── The Miro job's own failure paths, with Miro and ffmpeg faked ────────────────────────────

_JPEG = (b"\xff\xd8\xff\xc0\x00\x11\x08" + (180).to_bytes(2, "big") + (320).to_bytes(2, "big")
         + b"\x03" + b"\x00" * 9 + b"\xff\xd9")


class _FakeMiro:
    def __init__(self) -> None:
        self.frames: list[str] = []
        self.images = 0
        self.stickies = 0

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bristlenose import miro_client as mc

        monkeypatch.setattr(mc, "create_board", lambda *a, **k: {"id": "b1", "viewLink": "https://miro.com/app/board/b1/"})
        monkeypatch.setattr(mc, "create_frame", lambda _t, _b, title, *a, **k: self.frames.append(title) or {"id": f"f{len(self.frames)}"})
        monkeypatch.setattr(mc, "upload_image", lambda *a, **k: setattr(self, "images", self.images + 1) or {"id": "i"})
        monkeypatch.setattr(mc, "bulk_create_items", lambda _t, _b, items: setattr(self, "stickies", self.stickies + len(items)) or items)


def _screens(n: int) -> list[dict]:
    return [{"screen_key": f"/s{i}", "title": f"S{i}", "groups": [("p1", [f"q-p1-{i}"])],
             "versions": [{"session_id": "s1", "code": "p1", "t": float(i), "crop": [0, 0, 1, 1],
                           "filename": f"screen-{i:02d}-p1.jpg"}]} for i in range(1, n + 1)]


class _Q:
    def __init__(self, dom: str) -> None:
        self.text, self.participant_code, self.timecode, self.sentiment = "said", "p1", f"0:{dom[-1]:0>2}", ""


def _job() -> dict:
    return {"status": "running", "progress": 0, "total": 0, "completed_count": 0, "skipped_count": 0,
            "current": "", "board_url": None, "reason": None}


def test_a_screen_whose_still_fails_is_counted_not_lost(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    def still(_o: object, _s: object, _v: object, t: float, *_: object) -> bytes:
        if t == 2.0:  # the second screen's still cannot be made
            raise se.StillError("x")
        return _JPEG

    monkeypatch.setattr(se, "render_still", still)
    screens = _screens(3)
    job = _job()
    se._run_miro_sync(job, "tok", "Board", tmp_path, screens, {"s1": tmp_path / "v.mp4"},
                      {f"q-p1-{i}": _Q(f"q-p1-{i}") for i in range(1, 4)}, "none")
    assert job["status"] == "completed" and job["skipped_count"] == 1
    assert job["completed_count"] == 2 and fake.frames == ["S1", "S3"]


def test_no_still_at_all_is_a_failure_not_an_empty_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import asyncio

    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: (_ for _ in ()).throw(se.StillError("x")))
    job = _job()
    asyncio.run(se._run_miro(1, job, "tok", "Board", tmp_path, _screens(2), {"s1": tmp_path / "v.mp4"}, {}, "none"))
    assert job["status"] == "failed" and job["reason"] == "no_stills" and fake.frames == []


def test_a_cancel_stays_a_cancel_when_the_call_in_hand_then_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import asyncio

    from bristlenose import miro_client as mc
    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    job = _job()

    def fail_after_cancel(*_a: object, **_k: object) -> dict:
        job["status"] = "cancelled"
        raise mc.MiroError("boom", status=500)

    monkeypatch.setattr(mc, "create_frame", fail_after_cancel)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)
    asyncio.run(se._run_miro(1, job, "tok", "Board", tmp_path, _screens(2), {"s1": tmp_path / "v.mp4"},
                             {"q-p1-1": _Q("q-p1-1"), "q-p1-2": _Q("q-p1-2")}, "none"))
    assert job["status"] == "cancelled" and job["reason"] is None


def test_a_screen_with_one_good_screengrab_is_built_and_the_front_goes_on_top(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bristlenose import miro_client as mc
    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    uploads: list[str] = []
    monkeypatch.setattr(mc, "upload_image", lambda _t, _b, _j, name, **_: uploads.append(name) or {"id": "i"})
    screen = {"screen_key": "/s1", "title": "S1", "groups": [("p1", ["q-p1-1"])],
              "versions": [{"session_id": f"s{n}", "code": f"p{n}", "t": float(n), "crop": [0, 0, 1, 1],
                            "title": "S1", "filename": f"screen-01-p{n}.jpg"} for n in (2, 1, 3)]}

    def still(_o: object, _s: object, _v: object, t: float, *_: object) -> bytes:
        if t == 3.0:  # p3's screengrab cannot be made
            raise se.StillError("x")
        return _JPEG

    monkeypatch.setattr(se, "render_still", still)
    job = _job()
    se._run_miro_sync(job, "tok", "Board", tmp_path, [screen],
                      {f"s{n}": tmp_path / "v.mp4" for n in (1, 2, 3)}, {"q-p1-1": _Q("q-p1-1")}, "none")
    assert job["status"] == "completed" and job["skipped_count"] == 0
    assert uploads == ["screen-01-p1.jpg", "screen-01-p2.jpg"]  # back first; the front, p2, last


def test_a_back_screengrab_miro_refuses_is_left_out_but_a_refused_front_fails(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bristlenose import miro_client as mc
    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)
    screen = {"screen_key": "/s1", "title": "S1", "groups": [],
              "versions": [{"session_id": "s1", "code": f"p{n}", "t": 1.0, "crop": [0, 0, 1, 1],
                            "title": "S1", "filename": f"screen-01-p{n}.jpg"} for n in (1, 2)]}
    for refused, ok in (("screen-01-p2.jpg", True), ("screen-01-p1.jpg", False)):
        def upload(_t: object, _b: object, _j: object, name: str, refused: str = refused, **_: object) -> dict:
            if name == refused:
                raise mc.MiroError("boom", status=500)
            return {"id": "i"}

        monkeypatch.setattr(mc, "upload_image", upload)
        job = _job()
        if ok:
            se._run_miro_sync(job, "tok", "Board", tmp_path, [screen], {"s1": tmp_path / "v.mp4"}, {}, "none")
            assert job["status"] == "completed"
        else:
            with pytest.raises(mc.MiroError):
                se._run_miro_sync(job, "tok", "Board", tmp_path, [screen], {"s1": tmp_path / "v.mp4"}, {}, "none")


def test_a_long_quote_on_the_screens_board_breaks_where_its_speaker_paused(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The screens board splits through the same splitter as the quotes board, pauses and all."""
    from bristlenose import miro_client as mc
    from bristlenose.board_layout import quote_pauses
    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    made: list[str] = []
    monkeypatch.setattr(mc, "bulk_create_items", lambda _t, _b, items: made.extend(
        str(i.get("data", {}).get("content", "")) for i in items) or items)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)
    monkeypatch.setattr("bristlenose.board_layout.SPLIT_AT", 200)
    said = ("we tried every one of the tools they had on offer that year and none of them stayed "
            "open long enough to finish a single thing we started on a monday morning before the "
            "coffee ran out and the meeting room filled up with the people from the other floor")
    at, words, t = said.split().index("finish"), [], 10.0
    for i, w in enumerate(said.split()):
        words.append({"t": w, "s": t, "e": t + 0.3})
        t += 0.3 + (1.2 if i == at else 0.0)
    quote = _Q("q-p1-1")
    quote.text = said
    se._run_miro_sync(_job(), "tok", "Board", tmp_path, _screens(1), {"s1": tmp_path / "v.mp4"},
                      {"q-p1-1": quote}, "none", True, "rectangle",
                      {"q-p1-1": quote_pauses(said, words)})
    assert any("to finish…" in c for c in made), made


def test_the_screens_board_splits_by_the_language_the_quote_was_spoken_in(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bristlenose import miro_client as mc
    from bristlenose.server.routes import screens_export as se

    fake = _FakeMiro()
    fake.install(monkeypatch)
    made: list[str] = []
    monkeypatch.setattr(mc, "bulk_create_items", lambda _t, _b, items: made.extend(
        str(i.get("data", {}).get("content", "")) for i in items) or items)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)
    monkeypatch.setattr("bristlenose.board_layout.SPLIT_AT", 200)
    quote = _Q("q-p1-1")
    quote.text, quote.session = "dlouho " * 19 + "v praze" + " dlouho" * 19, "s1"
    se._run_miro_sync(_job(), "tok", "Board", tmp_path, _screens(1), {"s1": tmp_path / "v.mp4"},
                      {"q-p1-1": quote}, "none", True, "rectangle", None, {"s1": "cs"})
    assert made and not any(" v…" in c for c in made), made


def test_a_reveal_whose_exec_is_refused_says_so_rather_than_failing(
        project: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """R72: a refused exec (the App Sandbox) was a 500; it is ``revealed: false``."""
    from bristlenose.server.routes import screens_export

    folder = _out(project) / "screens"
    folder.mkdir(parents=True)
    (folder / "p1-01.jpg").write_bytes(b"x")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    monkeypatch.setitem(screens_export._jobs, 1, {
        "status": "completed", "output_dir": str(folder), "files": ["p1-01.jpg"],
    })

    def refused(*a: object, **k: object) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(screens_export.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(screens_export.subprocess, "run", refused)
    resp = AuthTestClient(app).post(f"{_BASE}/reveal")
    assert resp.status_code == 200
    assert resp.json()["revealed"] is False


def test_a_reveal_whose_open_hangs_is_given_up_on(
        project: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """No timeout held the request, and the server's event loop, as long as the
    command ran. A real `sleep` stands in for the hung `open`."""
    import time

    from bristlenose.server.routes import screens_export

    folder = _out(project) / "screens"
    folder.mkdir(parents=True)
    (folder / "p1-01.jpg").write_bytes(b"x")
    app = create_app(project_dir=project, dev=False, db_url="sqlite://")
    monkeypatch.setitem(screens_export._jobs, 1, {
        "status": "completed", "output_dir": str(folder), "files": ["p1-01.jpg"],
    })
    real_run = subprocess.run

    def hangs(command: list[str], **kwargs: object):  # noqa: ANN202
        return real_run(["sleep", "30"], **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(screens_export.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(screens_export, "_REVEAL_TIMEOUT_S", 0.2)
    monkeypatch.setattr(screens_export.subprocess, "run", hangs)
    warned: list[str] = []
    # Not caplog: create_app's setup_logging removes its handler.
    monkeypatch.setattr(screens_export.logger, "warning", lambda msg, *a, **k: warned.append(msg))
    t0 = time.monotonic()
    resp = AuthTestClient(app).post(f"{_BASE}/reveal")
    assert time.monotonic() - t0 < 10
    assert resp.status_code == 200
    assert resp.json()["revealed"] is False
    assert any("still running after" in m for m in warned)
