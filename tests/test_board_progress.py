"""Board build progress: the counted plan, the phases, the earned estimate, and Stop.

The tracker is pure (a fake clock); the quotes board runs its real job route against the smoke
fixture with Miro faked; the screens board runs its worker with Miro and ffmpeg faked. What these
pin is the contract both clients read: every call the board makes was counted before the first,
nothing is claimed while the board is opening, Miro's own waits are said as waiting and kept out of
the rate, and an estimate appears only once this build has earned one.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from bristlenose import miro_client as mc
from bristlenose.board_progress import (
    ETA_FLOOR_SECONDS,
    MIN_MEASURED_CALLS,
    BoardCancelledError,
    BoardProgress,
    load_history,
)
from bristlenose.server.app import create_app
from bristlenose.server.routes import miro as miro_routes
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


# ── The tracker on its own ──────────────────────────────────────────────────────────────────


def test_nothing_is_claimed_while_the_board_is_opening() -> None:
    clock = _Clock()
    p = BoardProgress("quotes", clock=clock)
    assert p.snapshot()["phase"] == "starting"  # not "preparing": the quotes board has no screenshots
    p.plan({"board": 1, "frame": 2, "bulk": 7})
    p.enter("opening")
    for kind in ("board", "frame", "frame"):  # slow as Miro's start-up makes them
        clock.now += 30
        p.call_done(kind)
    assert p.fraction() is None and p.eta_seconds() is None
    p.enter("quotes", 40)
    assert p.fraction() == pytest.approx(0.3) and p.opening_seconds == pytest.approx(90)
    assert "frame" not in p._rates  # start-up time never becomes a rate


def test_no_estimate_until_enough_calls_are_measured_and_none_under_the_floor() -> None:
    clock = _Clock()
    p = BoardProgress("quotes", clock=clock)
    p.plan({"bulk": 100})
    p.enter("quotes", 100)
    for _ in range(MIN_MEASURED_CALLS - 1):
        clock.now += 2
        p.call_done("bulk", 1)
    assert p.eta_seconds() is None  # three calls are not a rate
    clock.now += 2
    p.call_done("bulk", 1)
    assert p.eta_seconds() == pytest.approx((100 - MIN_MEASURED_CALLS) * 2)
    while p.done < 100:
        clock.now += 2
        p.call_done("bulk", 1)
        if (100 - p.done) * 2 < ETA_FLOOR_SECONDS:
            assert p.eta_seconds() is None  # "a few seconds" is not worth saying
    assert p.count_done == 100 and p.fraction() == 1.0


def test_a_wait_for_miro_is_said_and_kept_out_of_the_rate() -> None:
    clock = _Clock()
    p = BoardProgress("quotes", clock=clock)
    p.plan({"bulk": 10})
    p.enter("quotes", 10)
    for i in range(MIN_MEASURED_CALLS):
        clock.now += 1
        if i == 1:  # a rate limit: eight seconds of backoff inside this call
            with p.waiting_for(8, "rate_limit"):
                assert p.snapshot()["waiting"] is True
                clock.now += 8
        p.call_done("bulk", 1)
    assert p.waiting is False and p.waited == pytest.approx(8)
    assert p._rates["bulk"].mean == pytest.approx(1.0)  # the wait did not make every call look slower


def test_the_log_line_carries_counts_and_timings(caplog: pytest.LogCaptureFixture) -> None:
    clock = _Clock()
    p = BoardProgress("screens", clock=clock)
    p.plan({"board": 1, "image": 1})
    p.enter("opening")
    clock.now += 31
    p.call_done("board")
    p.enter("screens", 1)
    clock.now += 1
    p.call_done("image", 1)
    with caplog.at_level(logging.INFO, logger="bristlenose.board_progress"):
        p.log_summary("completed")
    line = caplog.records[-1].getMessage()
    assert line.startswith("miro_board_built kind=screens outcome=completed calls=2/2")
    assert "opening=31.0s" in line and "rates=[image=1.00s/1]" in line


def _the_measured_board(clock: _Clock, p: BoardProgress) -> None:
    """The 242-quote board measured 18 Oct 2026: 13 sticky batches, then 212 groups, every call
    about 0.4 s. Built to its fifth batch."""
    p.plan({"board": 1, "frame": 2, "bulk": 13, "group": 212, "text": 1})
    p.enter("opening")
    for kind in ("board", "frame", "frame"):
        clock.now += 0.4
        p.call_done(kind)
    p.enter("quotes", 242)
    for _ in range(5):
        clock.now += 0.4
        p.call_done("bulk", 20)


def test_a_kind_of_call_not_yet_timed_holds_the_estimate_back() -> None:
    # One rate for every call said "<1 min left" five seconds into this 94-second build: the
    # 212 groups to come had never been timed. With a rate per kind there is no estimate yet...
    clock = _Clock()
    p = BoardProgress("quotes", clock=clock)
    _the_measured_board(clock, p)
    assert p.eta_seconds() is None
    # ...until the groups have been timed themselves, and then it is the true remainder.
    p.enter("groups", 212)
    for _ in range(8):
        clock.now += 0.4
        p.call_done("bulk" if p._made.get("bulk", 0) < 13 else "group", 1)
    for _ in range(MIN_MEASURED_CALLS):
        clock.now += 0.4
        p.call_done("group", 1)
    left = 212 - MIN_MEASURED_CALLS + 1  # the groups, and the title on the build's average
    assert p.eta_seconds() == pytest.approx(left * 0.4)


def test_rates_kept_from_earlier_builds_earn_the_estimate_at_once(tmp_path: Path) -> None:
    first_clock = _Clock()
    first = BoardProgress("quotes", clock=first_clock, history_dir=tmp_path)
    _the_measured_board(first_clock, first)
    first.enter("groups", 212)
    for _ in range(10):
        first_clock.now += 0.4
        first.call_done("group", 1)
    first.remember()
    assert (tmp_path / "board-timing.json").exists()
    assert not (tmp_path / "timing.json").exists()  # never the pipeline's file

    clock = _Clock()
    second = BoardProgress("quotes", clock=clock, history_dir=tmp_path)
    _the_measured_board(clock, second)
    # Five batches in, the groups' kept rate answers for them: 8 batches + 212 groups + 1 title.
    assert second.eta_seconds() == pytest.approx((8 + 212 + 1) * 0.4)


def test_no_folder_means_nothing_is_read_or_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = BoardProgress("quotes")
    p.plan({"bulk": 5})
    p.enter("quotes", 5)
    for _ in range(5):
        p.call_done("bulk", 1)
    p.remember()
    assert list(tmp_path.rglob("board-timing.json")) == []


# ── The wait hook in the Miro client ────────────────────────────────────────────────────────


def test_every_backoff_sleep_is_reported_to_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def __init__(self, status: int) -> None:
            self.status_code, self.content, self.text = status, b"{}", ""

        def json(self) -> dict[str, Any]:
            return {"id": "b1"}

    answers = iter([_Resp(429), _Resp(429), _Resp(200)])
    monkeypatch.setattr(mc.httpx, "request", lambda *a, **k: next(answers))
    monkeypatch.setattr(mc.time, "sleep", lambda _s: None)
    p = BoardProgress("quotes")
    seen: list[str] = []

    class _Spy:
        def __call__(self, seconds: float, reason: str) -> Any:
            seen.append(f"{reason}:{seconds}")
            return p.waiting_for(seconds, reason)

    with mc.observe_waits(_Spy()):
        mc.create_board("tok", "Board")
    assert seen == ["rate_limit:1.0", "rate_limit:2.0"] and p.waiting is False
    mc._pause(0, "rate_limit")  # outside a build nothing is told, and nothing breaks


# ── The quotes board as a job, through its routes ───────────────────────────────────────────


class _FakeMiro:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.before_bulk: Any = None

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def note(name: str, out: Any) -> Any:
            self.calls.append(name)
            return out

        def bulk(_t: str, _b: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            if self.before_bulk:
                self.before_bulk()
            return note("bulk", [{"id": f"i{len(self.calls)}{n}"} for n in range(len(items))])

        monkeypatch.setattr(mc, "create_board", lambda *a, **k: note(
            "board", {"id": "b1", "viewLink": "https://miro.com/app/board/b1/"}))
        monkeypatch.setattr(mc, "create_frame", lambda *a, **k: note("frame", {"id": "f"}))
        monkeypatch.setattr(mc, "bulk_create_items", bulk)
        monkeypatch.setattr(mc, "create_group", lambda *a, **k: note("group", {"id": "g"}))
        monkeypatch.setattr(mc, "create_text", lambda *a, **k: note("text", {"id": "t"}))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AuthTestClient:
    from bristlenose.server.routes import miro as miro_routes

    miro_routes._board_jobs.clear()  # (conftest keeps a build's rates out of the real config)
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    return AuthTestClient(app)


def _wait_for(client: AuthTestClient, done: Any, deadline: float = 10.0) -> dict[str, Any]:
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        s = client.get("/api/projects/1/miro/board/status").json()
        if done(s):
            return s
        time.sleep(0.02)
    raise AssertionError(f"board job never reached the state: {s}")


def test_the_quotes_board_job_counts_every_call_it_makes(
        client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMiro()
    fake.install(monkeypatch)
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value="tok"):
        assert client.get("/api/projects/1/miro/board/status").json()["status"] == "idle"
        r = client.post("/api/projects/1/miro/board", json={"split_long_quotes": False})
        assert r.status_code == 200 and r.json()["status"] == "started"
        s = _wait_for(client, lambda s: s["status"] != "running")
    assert s["status"] == "completed", s
    assert s["board_url"] == "https://miro.com/app/board/b1/" and s["stickies"] == 4
    build = s["build"]
    # The plan made before the first call is exactly what was made.
    assert build["done"] == build["total"] == len(fake.calls)
    assert build["fraction"] == 1.0 and build["waiting"] is False
    assert build["phase"] == "groups"  # nothing split, so a group phase with nothing to count
    assert fake.calls[0] == "board" and fake.calls[-1] == "text"


def test_a_stopped_board_keeps_what_it_has_and_says_cancelled(
        client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMiro()
    fake.install(monkeypatch)
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value="tok"):
        # The researcher presses Stop while the first sticky batch is in hand.
        fake.before_bulk = lambda: client.post("/api/projects/1/miro/board/cancel")
        client.post("/api/projects/1/miro/board", json={})
        s = _wait_for(client, lambda s: s["status"] != "running")
        assert s["status"] == "cancelled" and s["reason"] is None
        assert s["board_url"] == "https://miro.com/app/board/b1/"  # where to find what was made
        assert fake.calls.count("bulk") == 1 and "text" not in fake.calls
        assert client.post("/api/projects/1/miro/board/cancel").status_code == 404


def test_a_failure_part_way_names_the_board_in_both_reason_and_vars(
        client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMiro()
    fake.install(monkeypatch)

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise mc.MiroError("boom", status=400)

    monkeypatch.setattr(mc, "bulk_create_items", refuse)
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value="tok"):
        client.post("/api/projects/1/miro/board", json={})
        s = _wait_for(client, lambda s: s["status"] != "running")
    assert s["status"] == "failed" and s["reason"] == "board_incomplete"
    assert s["vars"] == {"url": "https://miro.com/app/board/b1/"}


def test_a_second_board_waits_for_the_first(
        client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    fake = _FakeMiro()
    fake.install(monkeypatch)
    release = threading.Event()
    fake.before_bulk = lambda: release.wait(5)
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value="tok"):
        client.post("/api/projects/1/miro/board", json={})
        _wait_for(client, lambda s: (s["build"] or {}).get("phase") == "quotes")
        assert client.post("/api/projects/1/miro/board", json={}).status_code == 409
        release.set()
        assert _wait_for(client, lambda s: s["status"] != "running")["status"] == "completed"


def test_not_connected_is_refused_before_any_job_starts(client: AuthTestClient) -> None:
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value=None):
        assert client.post("/api/projects/1/miro/board", json={}).status_code == 400
        assert client.get("/api/projects/1/miro/board/status").json()["status"] == "idle"


# ── The screens board's worker ──────────────────────────────────────────────────────────────


def test_the_screens_board_counts_every_call_and_each_screen(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bristlenose.server.routes import screens_export as se
    from tests.test_serve_screens_export import _JPEG, _Q, _job, _screens
    from tests.test_serve_screens_export import _FakeMiro as _ScreensMiro

    fake = _ScreensMiro()
    fake.install(monkeypatch)
    calls = {"n": 0}
    for name in ("create_board", "create_frame", "upload_image", "bulk_create_items", "create_group"):
        original = getattr(mc, name)

        def counted(*a: Any, _original: Any = original, **k: Any) -> Any:
            calls["n"] += 1
            return _original(*a, **k)

        monkeypatch.setattr(mc, name, counted)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)
    job = _job()
    se._run_miro_sync(job, "tok", "Board", tmp_path, _screens(3), {"s1": tmp_path / "v.mp4"},
                      {f"q-p1-{i}": _Q(f"q-p1-{i}") for i in range(1, 4)}, "none")
    snap = job["tracker"].snapshot()
    assert job["status"] == "completed"
    assert snap["phase"] == "screens" and snap["count_done"] == snap["count_total"] == 3
    assert snap["done"] == snap["total"] == calls["n"]


def test_a_stop_mid_screen_is_acted_on_at_the_next_call(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import asyncio

    from bristlenose.server.routes import screens_export as se
    from tests.test_serve_screens_export import _JPEG, _Q, _job, _screens
    from tests.test_serve_screens_export import _FakeMiro as _ScreensMiro

    fake = _ScreensMiro()
    fake.install(monkeypatch)
    job = _job()

    def stop_on_upload(*_a: Any, **_k: Any) -> dict[str, str]:
        job["status"] = "cancelled"
        return {"id": "i"}

    monkeypatch.setattr(mc, "upload_image", stop_on_upload)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)
    asyncio.run(se._run_miro(1, job, "tok", "Board", tmp_path, _screens(2), {"s1": tmp_path / "v.mp4"},
                             {"q-p1-1": _Q("q-p1-1"), "q-p1-2": _Q("q-p1-2")}, "none"))
    assert job["status"] == "cancelled" and fake.stickies == 0  # stopped before the stickies


def test_board_cancelled_is_not_a_miro_error() -> None:
    # A Stop must never be wrapped as "board incomplete" by the push's MiroError handler.
    assert not issubclass(BoardCancelledError, mc.MiroError)


# ── From the 18 Oct 2026 review ─────────────────────────────────────────────────────────────


def test_a_stop_that_lands_during_the_last_call_reports_the_finished_board(
        client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # The title is the last call and is not followed by a Stop check: a Stop arriving while it
    # is in hand was too late. The board is whole, so it is reported completed, with its link.
    fake = _FakeMiro()
    fake.install(monkeypatch)

    def title_then_stop(*_a: Any, **_k: Any) -> dict[str, str]:
        client.post("/api/projects/1/miro/board/cancel")
        return {"id": "t"}

    monkeypatch.setattr(mc, "create_text", title_then_stop)
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value="tok"):
        client.post("/api/projects/1/miro/board", json={"split_long_quotes": False})
        # Not `status != "running"`: the Stop reads "cancelled" until the call in hand returns,
        # and a slow runner polled inside that gap (strict CI, 19 Oct 2026). Wait for the job.
        s = _wait_for(client, lambda s: miro_routes._board_jobs[1]["task"].done())
    assert s["status"] == "completed" and s["board_url"] == "https://miro.com/app/board/b1/"


def test_miro_refusing_the_token_is_named_not_shown_as_a_connection_problem(
        client: AuthTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a: Any, **_k: Any) -> Any:
        raise mc.MiroError("POST /boards -> 401 unauthorized", status=401)

    monkeypatch.setattr(mc, "create_board", refuse)
    with client, patch("bristlenose.server.routes.miro._miro_token", return_value="tok"):
        client.post("/api/projects/1/miro/board", json={})
        s = _wait_for(client, lambda s: s["status"] != "running")
    assert s["status"] == "failed" and s["reason"] == "token_rejected"


@pytest.mark.parametrize("content", ['{"profiles": []}', '{"profiles": {"miro": []}}',
                                     '{"profiles": {"miro": {"group": {"mean": "x"}}}}', "not json"])
def test_a_malformed_rates_file_costs_the_estimate_not_the_export(tmp_path: Path, content: str) -> None:
    (tmp_path / "board-timing.json").write_text(content)
    p = BoardProgress("quotes", history_dir=tmp_path)  # raised inside every board's start
    p.plan({"group": 5})
    p.enter("groups", 5)
    for _ in range(5):
        p.call_done("group", 1)
    p.remember()
    assert load_history(tmp_path)["group"].n == 5  # rewritten whole


def test_groups_miro_never_makes_leave_the_plan(caplog: pytest.LogCaptureFixture) -> None:
    clock = _Clock()
    p = BoardProgress("quotes", clock=clock)
    p.plan({"bulk": 1, "group": 3})
    p.enter("quotes", 4)
    p.call_done("bulk", 4)
    p.enter("groups", 3)
    p.unplan("group", 3)  # Miro made fewer stickies than sent: group_sets made none
    assert p.total == 1 and p.fraction() == 1.0 and p.count_total == 0
    with caplog.at_level(logging.INFO, logger="bristlenose.board_progress"):
        p.log_summary("completed")
    assert caplog.records[-1].levelno == logging.INFO  # whole by its own (corrected) plan


def test_a_board_finished_short_of_its_plan_is_logged_as_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    p = BoardProgress("quotes")
    p.plan({"bulk": 2})
    p.enter("quotes", 2)
    p.call_done("bulk", 1)
    with caplog.at_level(logging.INFO, logger="bristlenose.board_progress"):
        p.log_summary("completed")
    assert caplog.records[-1].levelno == logging.WARNING


def test_a_refused_screengrab_is_counted_but_never_becomes_a_rate(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bristlenose.server.routes import screens_export as se
    from tests.test_serve_screens_export import _JPEG, _job
    from tests.test_serve_screens_export import _FakeMiro as _ScreensMiro

    fake = _ScreensMiro()
    fake.install(monkeypatch)
    monkeypatch.setattr(se, "render_still", lambda *a, **k: _JPEG)

    def refuse_the_back_one(_t: Any, _b: Any, _j: Any, name: str, **_k: Any) -> dict[str, str]:
        if name.endswith("p1.jpg"):
            raise mc.MiroError("timeout", status=500)
        return {"id": "i"}

    monkeypatch.setattr(mc, "upload_image", refuse_the_back_one)
    screen = {"screen_key": "/s1", "title": "S1", "groups": [],
              "versions": [{"session_id": "s1", "code": f"p{n}", "t": 1.0, "crop": [0, 0, 1, 1],
                            "title": "S1", "filename": f"screen-01-p{n}.jpg"} for n in (2, 1)]}
    job = _job()
    se._run_miro_sync(job, "tok", "Board", tmp_path, [screen], {"s1": tmp_path / "v.mp4"}, {}, "none")
    tracker = job["tracker"]
    assert job["status"] == "completed" and tracker.done == tracker.total
    assert tracker._rates["image"].n == 1  # the front one only
