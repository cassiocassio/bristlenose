"""Parity gate: the .mcpb proxy's static tool list vs the live MCP server.

The proxy (``desktop/mcpb/server/index.js``) must list tools even when
Bristlenose is closed, so it carries a STATIC copy of the four tool schemas.
Installed extensions never auto-update, so any drift between that copy and
``bristlenose/server/mcp_server.py`` ships permanently (review Finding 25 on
the extension design doc wanted a mechanical gate — this is it): a renamed
tool, a new required param, or a dropped filter would make the model call
tools that no longer exist, or never discover params that do.

The JSON blob lives between ``BN-TOOLS-JSON-BEGIN``/``END`` markers in the
JS precisely so this test can parse it without a JS runtime.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bristlenose.server.app import create_app

pytest.importorskip("mcp", reason="mcp extra not installed")

_REPO = Path(__file__).parent.parent
_PROXY_JS = _REPO / "desktop" / "mcpb" / "server" / "index.js"
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "smoke-test" / "input"

_PROTO_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _proxy_tools() -> list[dict]:
    source = _PROXY_JS.read_text(encoding="utf-8")
    match = re.search(
        r"/\* BN-TOOLS-JSON-BEGIN \*/\s*const TOOLS =\s*(\[.*?\]);\s*/\* BN-TOOLS-JSON-END \*/",
        source,
        re.DOTALL,
    )
    assert match, "BN-TOOLS-JSON markers missing from the proxy source"
    return json.loads(match.group(1))


def _server_tools() -> list[dict]:
    app = create_app(project_dir=_FIXTURE_DIR, dev=True, db_url="sqlite://")
    app.state.auth_token = "test-mcp-token"
    with TestClient(app, base_url="http://127.0.0.1:8150") as client:
        resp = client.post(
            "/mcp/",
            headers={"Authorization": "Bearer test-mcp-token", **_PROTO_HEADERS},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["result"]["tools"]


class TestProxyToolParity:
    def test_tool_names_match(self) -> None:
        proxy = {t["name"] for t in _proxy_tools()}
        server = {t["name"] for t in _server_tools()}
        assert proxy == server

    def test_params_and_required_match_per_tool(self) -> None:
        proxy = {t["name"]: t for t in _proxy_tools()}
        server = {t["name"]: t for t in _server_tools()}
        for name, server_tool in server.items():
            proxy_schema = proxy[name]["inputSchema"]
            server_schema = server_tool["inputSchema"]
            assert set(proxy_schema.get("properties", {})) == set(
                server_schema.get("properties", {})
            ), f"{name}: property names drifted"
            assert set(proxy_schema.get("required", [])) == set(
                server_schema.get("required", [])
            ), f"{name}: required params drifted"

    def test_proxy_descriptions_are_present(self) -> None:
        # The static list is what the model sees when Bristlenose is closed —
        # a blank description degrades tool choice silently.
        for tool in _proxy_tools():
            assert tool.get("description"), f"{tool['name']}: empty description"
