"""LazyMCP's holder logic, attacked with a fake server (no SDK, no app).

The reasons to hold the session manager in one long-lived task, and to refuse work once the app
is closing, are in bristlenose/server/mcp_mount.py. These tests make the awkward orderings
happen on purpose: a call cancelled mid-build, a call arriving after shutdown began, shutdown
during a build, closing twice, a build that fails and is retried.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

import pytest

from bristlenose.server.mcp_mount import LazyMCP


class _Manager:
    def __init__(self, start_delay: float = 0.0) -> None:
        self.entered = 0
        self.exited = 0
        self.start_delay = start_delay

    @asynccontextmanager
    async def run(self):  # type: ignore[no-untyped-def]
        if self.start_delay:
            await asyncio.sleep(self.start_delay)
        self.entered += 1
        try:
            yield
        finally:
            self.exited += 1


class _Server:
    def __init__(self, start_delay: float = 0.0) -> None:
        self.session_manager = _Manager(start_delay)


def _http_app_factory(server: _Server):  # type: ignore[no-untyped-def]
    async def app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return app


def _lazy(
    delay: float = 0.0,
    servers: list[_Server] | None = None,
    fail_first: bool = False,
    start_delay: float = 0.0,
) -> LazyMCP:
    made: list[_Server] = servers if servers is not None else []
    state = {"n": 0}

    def build() -> tuple[Any, Any]:
        state["n"] += 1
        if fail_first and state["n"] == 1:
            raise RuntimeError("broken install")
        if delay:
            time.sleep(delay)
        server = _Server(start_delay)
        made.append(server)
        return server, _http_app_factory(server)

    return LazyMCP(build)


def _manager_tasks() -> list[asyncio.Task[Any]]:
    return [t for t in asyncio.all_tasks() if t.get_name() == "bristlenose-mcp-session-manager"]


async def _call(lazy: LazyMCP) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send(m: dict[str, Any]) -> None:
        sent.append(m)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    await lazy({"type": "http", "method": "POST", "path": "/"}, receive, send)
    return sent


def test_a_call_cancelled_mid_build_leaves_nothing_running_and_the_next_call_works() -> None:
    async def go() -> None:
        servers: list[_Server] = []
        lazy = _lazy(delay=0.3, servers=servers)
        first = asyncio.create_task(_call(lazy))
        await asyncio.sleep(0.05)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert _manager_tasks() == []  # nothing was started for the cancelled call
        sent = await _call(lazy)  # the next call builds (the cancelled build's result is lost)
        assert sent[0]["status"] == 200
        await lazy.aclose()
        assert _manager_tasks() == []
        assert all(s.session_manager.entered == s.session_manager.exited for s in servers)

    asyncio.run(asyncio.wait_for(go(), timeout=20))


def test_a_call_after_shutdown_began_is_refused_and_leaks_no_manager() -> None:
    async def go() -> None:
        lazy = _lazy()
        await _call(lazy)
        await lazy.aclose()
        with pytest.raises(RuntimeError):
            await _call(lazy)
        assert _manager_tasks() == []

    asyncio.run(asyncio.wait_for(go(), timeout=20))


def test_shutdown_during_a_build_does_not_start_a_manager_afterwards() -> None:
    async def go() -> None:
        servers: list[_Server] = []
        lazy = _lazy(delay=0.3, servers=servers)
        call = asyncio.create_task(_call(lazy))
        await asyncio.sleep(0.05)
        await lazy.aclose()  # the build is still running in its thread
        with pytest.raises(RuntimeError):
            await call
        assert _manager_tasks() == []
        assert all(s.session_manager.entered == 0 for s in servers)

    asyncio.run(asyncio.wait_for(go(), timeout=20))


def test_closing_twice_and_closing_when_never_started_are_both_safe() -> None:
    async def go() -> None:
        lazy = _lazy()
        await lazy.aclose()
        await lazy.aclose()
        lazy2 = _lazy()
        await _call(lazy2)
        await lazy2.aclose()
        await lazy2.aclose()

    asyncio.run(asyncio.wait_for(go(), timeout=20))


def test_a_failed_build_is_not_remembered() -> None:
    async def go() -> None:
        lazy = _lazy(fail_first=True)
        with pytest.raises(RuntimeError):
            await _call(lazy)
        assert (await _call(lazy))[0]["status"] == 200
        await lazy.aclose()

    asyncio.run(asyncio.wait_for(go(), timeout=20))


def test_forty_simultaneous_first_calls_start_one_manager() -> None:
    async def go() -> None:
        servers: list[_Server] = []
        lazy = _lazy(delay=0.1, servers=servers)
        results = await asyncio.gather(*(_call(lazy) for _ in range(40)))
        assert all(r[0]["status"] == 200 for r in results)
        assert len(servers) == 1 and servers[0].session_manager.entered == 1
        await lazy.aclose()
        assert servers[0].session_manager.exited == 1

    asyncio.run(asyncio.wait_for(go(), timeout=20))


def test_a_lock_made_before_any_loop_exists_works_on_two_different_loops() -> None:
    # create_app builds the holder with no running loop; tests (and TestClient) then use fresh loops.
    lazy = _lazy()

    async def once() -> None:
        assert (await _call(lazy))[0]["status"] == 200
        await lazy.aclose()

    asyncio.run(once())
    lazy2 = _lazy()  # a closed holder is final; a second app gets its own

    async def again() -> None:
        assert (await _call(lazy2))[0]["status"] == 200
        await lazy2.aclose()

    asyncio.run(again())


def test_a_call_cancelled_while_the_manager_starts_leaves_no_manager_running() -> None:
    async def go() -> None:
        servers: list[_Server] = []
        lazy = _lazy(servers=servers, start_delay=0.4)
        call = asyncio.create_task(_call(lazy))
        await asyncio.sleep(0.15)  # built; the manager is still starting
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        await asyncio.sleep(0.05)
        assert _manager_tasks() == []  # without the cleanup this task parks in stop.wait() for ever
        assert (await _call(lazy))[0]["status"] == 200
        await lazy.aclose()
        assert _manager_tasks() == []

    asyncio.run(asyncio.wait_for(go(), timeout=20))
