"""`bristlenose serve` prints its Report and MCP lines only once the port is bound (N148).

On a second study while another report was still being served it printed the link and the
MCP connect block, opened the browser, and then died with "address already in use": a link
to the other study's server, announced as this one's. Owner ruling 1 Nov 2026: print after
the bind succeeds, no new words.
"""

from __future__ import annotations

import shutil
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from bristlenose import cli

_FIXTURE = Path(__file__).parent / "fixtures" / "smoke-test" / "input"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    shutil.copytree(_FIXTURE, proj)
    return proj


@pytest.fixture(autouse=True)
def _quiet_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_run_preflight", lambda *_a: None)


def test_a_busy_port_prints_no_report_line_and_opens_no_browser(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url, *a, **k: opened.append(url) or True)
    with socket.socket() as other:  # "another study's report server"
        other.bind(("127.0.0.1", 0))
        other.listen(1)
        busy = other.getsockname()[1]
        started = time.monotonic()
        result = CliRunner().invoke(cli.app, ["serve", str(project), "--port", str(busy)])
        elapsed = time.monotonic() - started
    assert result.exit_code != 0, result.output
    assert elapsed < 8, "a refused bind ends the run at once, it does not wait out the 10 s bound"
    assert "Report:" not in result.output, "no link to a server that never came up"
    assert opened == [], "and no browser opened on the other study's server"


def test_the_lines_come_after_the_bind_not_before(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_print = cli.console.print

    def record(*args: Any, **kwargs: Any) -> None:
        text = " ".join(str(a) for a in args)
        if "Report:" in text:
            events.append("report-line")
        real_print(*args, **kwargs)

    class FakeServer:
        def __init__(self, config: Any) -> None:
            self.config = config
            self.started = False
            self.servers: list[Any] = []

        async def serve(self) -> None:
            import asyncio

            await asyncio.sleep(0.2)
            assert "report-line" not in events, "the Report line was printed before the bind"
            sock = SimpleNamespace(getsockname=lambda: ("127.0.0.1", self.config.port))
            self.servers = [SimpleNamespace(sockets=[sock])]
            self.started = True
            events.append("bound")
            await asyncio.sleep(0.3)

    monkeypatch.setattr(cli.console, "print", record)
    monkeypatch.setattr("uvicorn.Server", FakeServer)
    monkeypatch.setattr(cli, "_create_admitted_app", lambda *a, **k: object())
    monkeypatch.setattr(cli, "_print_mcp_connect", lambda port: events.append("mcp-block"))
    result = CliRunner().invoke(cli.app, ["serve", str(project), "--port", "8187", "--no-open"])
    assert result.exit_code == 0, result.output
    assert events == ["bound", "report-line", "mcp-block"]


def test_the_report_line_keeps_the_text_the_host_parses(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeServer:
        def __init__(self, config: Any) -> None:
            self.config = config
            self.started = True
            sock = SimpleNamespace(getsockname=lambda: ("127.0.0.1", config.port))
            self.servers = [SimpleNamespace(sockets=[sock])]

        async def serve(self) -> None:
            return None

    monkeypatch.setattr("uvicorn.Server", FakeServer)
    monkeypatch.setattr(cli, "_create_admitted_app", lambda *a, **k: object())
    monkeypatch.setattr(cli, "_print_mcp_connect", lambda port: None)
    result = CliRunner().invoke(cli.app, ["serve", str(project), "--port", "8186", "--no-open"])
    assert "Report: http://127.0.0.1:8186/report/" in result.output


def test_a_server_that_ends_before_it_starts_does_not_wait_out_the_bound(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # uvicorn ends a refused bind or a failed lifespan with SystemExit, which stops the wait
    # by itself; a serve() that returns without ever starting (should_exit set before
    # startup) must end the wait too, not run the 10 s bound down and then print nothing.
    class FakeServer:
        def __init__(self, config: Any) -> None:
            self.config = config
            self.started = False
            self.servers: list[Any] = []

        async def serve(self) -> None:
            return None

    monkeypatch.setattr("uvicorn.Server", FakeServer)
    monkeypatch.setattr(cli, "_create_admitted_app", lambda *a, **k: object())
    monkeypatch.setattr(cli, "_print_mcp_connect", lambda port: None)
    started = time.monotonic()
    result = CliRunner().invoke(cli.app, ["serve", str(project), "--port", "8185", "--no-open"])
    elapsed = time.monotonic() - started
    assert elapsed < 5, "the wait ran its 10 s bound down after the server had already ended"
    assert "Report:" not in result.output
