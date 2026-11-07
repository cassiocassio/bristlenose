"""The .mcpb proxy never sends the bearer to a port it has not verified (trust map row 54).

Before the proxy sends a tool call it asks the port's unauthenticated ``/api/health`` for an
``mcp.instance_id`` and compares it with the one in the handshake file; any mismatch, or an
answer without one, or a handshake entry without one, must leave the bearer unsent, because
a squatter on the port would receive it. The unmodified proxy is run under Node against a fake
local server that records every request it gets. A matching answer is the positive control:
the same run does send the bearer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

_PROXY_JS = Path(__file__).parent.parent / "desktop" / "mcpb" / "server" / "index.js"
_TOKEN = "sentinel-" + uuid.uuid4().hex

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


class _Squatter:
    """A local server that answers /api/health as told and records what reaches /mcp."""

    def __init__(self, health: dict) -> None:
        self.health = health
        self.mcp_requests: list[dict[str, str]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a: object) -> None:  # quiet
                pass

            def _send(self, code: int, body: dict) -> None:
                raw = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                if self.path.startswith("/api/health"):
                    self._send(200, outer.health)
                else:
                    self._send(404, {})

            def do_POST(self) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(n)
                if self.path.startswith("/mcp"):
                    outer.mcp_requests.append(dict(self.headers.items()))
                self._send(500, {"error": "squatter"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> _Squatter:
        self.thread.start()
        return self

    def __exit__(self, *a: object) -> None:
        self.server.shutdown()
        self.server.server_close()


def _run_proxy(tmp_path: Path, port: int, entry_instance: str | None) -> None:
    entry = {"key": "k1", "name": "Study", "port": port, "token": _TOKEN}
    if entry_instance is not None:
        entry["instance_id"] = entry_instance
    handshake = tmp_path / "mcp-handshake.json"
    handshake.write_text(json.dumps({"schema": 2, "projects": [entry]}), encoding="utf-8")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "BRISTLENOSE_DEV_MCP_HANDSHAKE": str(handshake),
    }
    frames = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "get_project_overview", "arguments": {}}},
    ]
    # The proxy answers asynchronously and exits when stdin closes, so keep stdin open until
    # the reply to the tool call has arrived.
    proc = subprocess.Popen(
        ["node", str(_PROXY_JS)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        proc.stdin.write("".join(json.dumps(f) + "\n" for f in frames))
        proc.stdin.flush()
        timer = threading.Timer(20, proc.kill)
        timer.start()
        try:
            for line in proc.stdout:
                if json.loads(line).get("id") == 1:
                    return
        finally:
            timer.cancel()
        raise AssertionError("the proxy never answered the tool call")
    finally:
        proc.kill()
        proc.wait()


def _health(instance: str | None) -> dict:
    mcp: dict = {"mounted": True}
    if instance is not None:
        mcp["instance_id"] = instance
    return {"version": "0.0-test", "mcp": mcp}


def _bearers(squatter: _Squatter) -> list[str]:
    return [h.get("Authorization", "") for h in squatter.mcp_requests]


def test_positive_control_a_matching_instance_is_sent_the_bearer(tmp_path: Path) -> None:
    with _Squatter(_health("INSTANCE-A")) as s:
        _run_proxy(tmp_path, s.port, "INSTANCE-A")
        assert f"Bearer {_TOKEN}" in _bearers(s), "the control must reach /mcp with the bearer"


@pytest.mark.parametrize(
    ("served", "expected", "why"),
    [
        ("INSTANCE-B", "INSTANCE-A", "a different instance answers on the port"),
        (None, "INSTANCE-A", "the answer carries no instance id (a squatter mimicking health)"),
        ("INSTANCE-A", None, "the handshake entry has no instance id (malformed)"),
        ("INSTANCE-A", "", "the handshake entry's instance id is empty"),
    ],
)
def test_no_bearer_reaches_an_unverified_port(
    tmp_path: Path, served: str | None, expected: str | None, why: str,
) -> None:
    with _Squatter(_health(served)) as s:
        _run_proxy(tmp_path, s.port, expected)
        assert _TOKEN not in " ".join(_bearers(s)), why
        assert s.mcp_requests == [], f"nothing should reach /mcp at all: {why}"
