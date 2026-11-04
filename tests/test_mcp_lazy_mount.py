"""The MCP endpoint is built on its first request, not at startup.

`import mcp` is 275 to 280 ms (measured 4 Nov 2026) and every serve start paid it whether or
not Agent Access was on. The route, the explainer page and `health.mcp.mounted` are unchanged;
the import, the server and its session manager come with the first agent call.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from bristlenose.server import mcp_server
from bristlenose.server.app import create_app
from tests.conftest import AuthTestClient

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"
_TOKEN = "lazy-mcp-token"
_HEADERS = {
    "Authorization": f"Bearer {_TOKEN}",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
_INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "pytest", "version": "0"}},
}


def _fresh_app() -> Any:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    app.state.auth_token = _TOKEN
    return app


def _python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)


def test_building_the_app_does_not_import_the_mcp_package() -> None:
    r = _python(
        "import sys\n"
        "from bristlenose.server.app import create_app\n"
        "from pathlib import Path\n"
        f"app = create_app(project_dir=Path({str(_FIXTURE_DIR)!r}), dev=True, db_url='sqlite://')\n"
        "print('mcp' in sys.modules, app.state.mcp_mounted)\n"
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout.split()[-2:] == ["False", "True"]  # not imported, yet reported as mounted


def test_a_browser_click_on_the_endpoint_does_not_load_the_mcp_package() -> None:
    r = _python(
        "import sys\n"
        "from fastapi.testclient import TestClient\n"
        "from bristlenose.server.app import create_app\n"
        "from pathlib import Path\n"
        f"app = create_app(project_dir=Path({str(_FIXTURE_DIR)!r}), dev=True, db_url='sqlite://')\n"
        "with TestClient(app, base_url='http://127.0.0.1:8150') as c:\n"
        "    page = c.get('/mcp/', headers={'Accept': 'text/html'})\n"
        "print(page.status_code, 'MCP endpoint' in page.text, 'mcp' in sys.modules)\n"
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout.split()[-3:] == ["200", "True", "False"]


def test_twenty_simultaneous_first_calls_build_it_once(monkeypatch: pytest.MonkeyPatch) -> None:
    builds: list[int] = []
    lock = threading.Lock()
    real = mcp_server.create_mcp_server

    def counting(*a: Any, **kw: Any) -> Any:
        with lock:
            builds.append(1)
        return real(*a, **kw)

    monkeypatch.setattr(mcp_server, "create_mcp_server", counting)
    app = _fresh_app()

    async def go() -> list[int]:
        # run the app's own lifespan, then fire the calls together
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1:8150"
            ) as c:
                resps = await asyncio.gather(*(
                    c.post("/mcp/", headers=_HEADERS, json={**_INIT, "id": i}) for i in range(20)
                ))
                return [r.status_code for r in resps]

    assert asyncio.run(go()) == [200] * 20
    assert builds == [1]


def test_leaving_the_app_stops_the_session_manager_and_does_not_hang() -> None:
    app = _fresh_app()
    handle = {}

    async def go() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1:8150"
            ) as c:
                assert (await c.post("/mcp/", headers=_HEADERS, json=_INIT)).status_code == 200
            # find the holder through the mount
            for route in app.routes:
                if getattr(route, "path", "") == "/mcp":
                    inner = route.app
                    while hasattr(inner, "inner"):
                        inner = inner.inner
                    handle["lazy"] = inner
            assert handle["lazy"]._task is not None and not handle["lazy"]._task.done()
            handle["task"] = handle["lazy"]._task
        # lifespan exited: aclose ran

    asyncio.run(asyncio.wait_for(go(), timeout=20))
    assert handle["task"].done() and handle["lazy"]._task is None


def test_a_failed_build_is_a_500_and_the_next_call_tries_again(monkeypatch: pytest.MonkeyPatch) -> None:
    real = mcp_server.create_mcp_server
    state = {"calls": 0}

    def flaky(*a: Any, **kw: Any) -> Any:
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("a present-but-broken install")
        return real(*a, **kw)

    monkeypatch.setattr(mcp_server, "create_mcp_server", flaky)
    app = _fresh_app()
    with TestClient(app, base_url="http://127.0.0.1:8150", raise_server_exceptions=False) as client:
        assert client.post("/mcp/", headers=_HEADERS, json=_INIT).status_code == 500
        assert client.post("/mcp/", headers=_HEADERS, json=_INIT).status_code == 200
    assert state["calls"] == 2


def test_the_health_probe_does_not_load_the_mcp_package() -> None:
    # /api/health is the app's readiness probe: it must not pay the import it was moved off.
    r = _python(
        "import sys\n"
        "from fastapi.testclient import TestClient\n"
        "from bristlenose.server.app import create_app\n"
        "from pathlib import Path\n"
        f"app = create_app(project_dir=Path({str(_FIXTURE_DIR)!r}), dev=True, db_url='sqlite://')\n"
        "with TestClient(app, base_url='http://127.0.0.1:8150') as c:\n"
        "    body = c.get('/api/health').json()\n"
        "print(body['mcp']['mounted'], 'mcp' in sys.modules)\n"
    )
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout.split()[-2:] == ["True", "False"]


def test_health_reports_mounted_before_any_call() -> None:
    app = _fresh_app()
    with TestClient(app, base_url="http://127.0.0.1:8150") as client:
        body = client.get("/api/health").json()
        assert body["mcp"]["mounted"] is True


def test_an_absent_package_is_not_mounted(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **kw: None if name == "mcp" else real(name, *a, **kw))
    app = _fresh_app()
    assert app.state.mcp_mounted is False
    with TestClient(app, base_url="http://127.0.0.1:8150") as client:
        assert client.post("/mcp/", headers=_HEADERS, json=_INIT).status_code in (401, 404)
    assert AuthTestClient  # imported for parity with the other serve tests
