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


def _flat_types(spec: dict) -> set[str]:
    """Every JSON-Schema type a property spec admits, flattening anyOf."""
    types: set[str] = set()
    for variant in spec.get("anyOf", [spec]):
        t = variant.get("type")
        if isinstance(t, str):
            types.add(t)
        elif isinstance(t, list):
            types.update(t)
    return types


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


#: Tools the PROXY implements and the server deliberately does not.
#: `list_projects` is answered from the handshake with no upstream call and no
#: bearer transmitted — the proxy is the only party that knows the whole set,
#: since each serve knows only itself. Not drift; the gate must still catch
#: everything else.
_PROXY_ONLY_TOOLS = {"list_projects"}

#: Arguments the PROXY consumes and strips before forwarding. `project` names
#: which serve to route to; a single-project server would reject it as unknown.
_PROXY_ONLY_ARGS = {"project"}


class TestProxyToolParity:
    def test_tool_names_match(self) -> None:
        proxy = {t["name"] for t in _proxy_tools()}
        server = {t["name"] for t in _server_tools()}
        assert proxy - _PROXY_ONLY_TOOLS == server, (
            "a tool exists on one side only — if that is deliberate, add it to "
            "_PROXY_ONLY_TOOLS with the reason"
        )

    def test_params_and_required_match_per_tool(self) -> None:
        proxy = {t["name"]: t for t in _proxy_tools()}
        server = {t["name"]: t for t in _server_tools()}
        for name, server_tool in server.items():
            proxy_schema = proxy[name]["inputSchema"]
            server_schema = server_tool["inputSchema"]
            proxy_props = set(proxy_schema.get("properties", {})) - _PROXY_ONLY_ARGS
            assert proxy_props == set(
                server_schema.get("properties", {})
            ), f"{name}: property names drifted"
            assert set(proxy_schema.get("required", [])) == set(
                server_schema.get("required", [])
            ), f"{name}: required params drifted"
            # Types too — a limit that went integer→string would otherwise
            # pass on names alone. The server wraps optional params in
            # anyOf/[type, "null"]; accept the proxy naming the non-null arm.
            for prop, proxy_spec in proxy_schema.get("properties", {}).items():
                if prop in _PROXY_ONLY_ARGS:
                    continue
                server_spec = server_schema["properties"][prop]
                server_types = _flat_types(server_spec)
                proxy_type = proxy_spec.get("type")
                assert proxy_type in server_types, (
                    f"{name}.{prop}: proxy type {proxy_type!r} not among "
                    f"server types {sorted(server_types)}"
                )

    def test_proxy_descriptions_are_present(self) -> None:
        # The static list is what the model sees when Bristlenose is closed —
        # a blank description degrades tool choice silently.
        for tool in _proxy_tools():
            assert tool.get("description"), f"{tool['name']}: empty description"

    def test_proxy_only_additions_are_optional(self) -> None:
        # The compatibility rule that makes a stale extension degrade rather
        # than break: an installed .mcpb never auto-updates, so a REQUIRED
        # param the old proxy doesn't know about would make every call fail.
        # Additive-and-optional is the whole contract.
        for tool in _proxy_tools():
            required = set(tool["inputSchema"].get("required", []))
            assert not (required & _PROXY_ONLY_ARGS), (
                f"{tool['name']}: proxy-only args must never be required"
            )
