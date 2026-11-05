"""``server/busy.py`` and ``GET /api/background-work``: what a serve says it must not lose.

The Mac holds the reap of a window-less study's server while this says busy (``ServeReaping``). Busy
means paid or unrecoverable: AutoCode and Signals elaboration, never Screens reading or the scene
strips (they spend nothing and pick up at the next start).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from bristlenose.server import autocode_catch_up, busy
from bristlenose.server.app import create_app
from tests.conftest import LOOPBACK_BASE_URL, AuthTestClient


@pytest.fixture(autouse=True)
def _nothing_busy():
    busy._active.clear()
    autocode_catch_up._WAITS.clear()
    autocode_catch_up._FIRING.clear()
    yield
    busy._active.clear()
    autocode_catch_up._WAITS.clear()
    autocode_catch_up._FIRING.clear()


@pytest.fixture
def app():
    return create_app(dev=True, db_url="sqlite://")


def test_idle_is_not_busy() -> None:
    assert busy.active_kinds() == []


def test_working_marks_busy_for_the_block_and_clears_on_error() -> None:
    with busy.working("autocode"):
        assert busy.active_kinds() == ["autocode"]
    assert busy.active_kinds() == []
    with pytest.raises(RuntimeError):
        with busy.working("signals"):
            raise RuntimeError("boom")
    assert busy.active_kinds() == []  # a crash must not leave the server busy for ever


def test_overlapping_work_of_one_kind_stays_busy_until_the_last_ends() -> None:
    a, b = busy.working("autocode"), busy.working("autocode")
    a.__enter__()
    b.__enter__()
    a.__exit__(None, None, None)
    assert busy.active_kinds() == ["autocode"]
    b.__exit__(None, None, None)
    assert busy.active_kinds() == []


def test_kinds_are_listed_once_each_and_sorted() -> None:
    with busy.working("signals"), busy.working("autocode"), busy.working("autocode"):
        assert busy.active_kinds() == ["autocode", "signals"]


def test_tracked_covers_an_async_function_while_it_runs() -> None:
    seen: list[list[str]] = []

    @busy.tracked("autocode")
    async def job() -> str:
        await asyncio.sleep(0)
        seen.append(busy.active_kinds())
        return "done"

    assert asyncio.run(job()) == "done"
    assert seen == [["autocode"]]
    assert busy.active_kinds() == []


def test_tracked_covers_a_sync_function_and_clears_after_it_raises() -> None:
    @busy.tracked("signals")
    def job() -> None:
        assert busy.active_kinds() == ["signals"]
        raise ValueError("x")

    with pytest.raises(ValueError):
        job()
    assert busy.active_kinds() == []


def test_a_waiting_or_firing_catch_up_counts_as_autocode() -> None:
    autocode_catch_up._WAITS[1] = object()  # type: ignore[assignment]
    assert busy.active_kinds() == ["autocode"]
    autocode_catch_up._WAITS.clear()
    assert busy.active_kinds() == []

    async def check() -> None:
        task = asyncio.ensure_future(asyncio.sleep(0.05))
        autocode_catch_up._FIRING.add(task)
        assert busy.active_kinds() == ["autocode"]
        await task
        autocode_catch_up._FIRING.discard(task)

    asyncio.run(check())
    assert busy.active_kinds() == []


def test_the_paid_entry_points_are_the_ones_marked() -> None:
    # Pin the callers, not only the helper: removing a decorator would silently make a paid pass
    # reapable again with every helper test still green.
    from bristlenose.server.autocode import reapply_to_new_quotes, run_autocode_job
    from bristlenose.server.elaboration import generate_elaborations

    assert getattr(run_autocode_job, "_busy_kind", None) == "autocode"
    assert getattr(reapply_to_new_quotes, "_busy_kind", None) == "autocode"
    assert getattr(generate_elaborations, "_busy_kind", None) == "signals"


def test_the_route_reports_idle_and_busy(app) -> None:
    client = AuthTestClient(app)
    assert client.get("/api/background-work").json() == {"busy": False, "kinds": []}
    with busy.working("signals"):
        assert client.get("/api/background-work").json() == {"busy": True, "kinds": ["signals"]}
    assert client.get("/api/background-work").json()["busy"] is False


def test_the_route_is_behind_the_bearer_unlike_health(app) -> None:
    bare = TestClient(app, base_url=LOOPBACK_BASE_URL)
    assert bare.get("/api/health").status_code == 200  # auth-exempt, by design
    assert bare.get("/api/background-work").status_code in (401, 403)  # not a timeline for any local process
