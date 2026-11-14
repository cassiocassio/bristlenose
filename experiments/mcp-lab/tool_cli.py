"""A command line over the synthetic MCP lab study, for a LIVE agent to use.

It goes through the real FastMCP server (real tool list, real argument
validation), so an agent that reads only `--describe` and picks its own calls
meets the tools the way Claude does. Every call is logged to live/<agent>.jsonl.

    LAB_AGENT=a1 .venv/bin/python experiments/mcp-lab/tool_cli.py --describe
    LAB_AGENT=a1 .venv/bin/python experiments/mcp-lab/tool_cli.py --call search_quotes '{"sentiment": "frustration"}'
    ... --study swap    (the study where session 1's roles were swapped)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import anyio

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

from run_lab import FIXTURE, apply_swap, build_study, create_app  # noqa: E402

from bristlenose.server.mcp_server import build_instructions, create_mcp_server  # noqa: E402


def make_server(study: str):
    app = create_app(project_dir=FIXTURE, dev=True, db_url="sqlite://")
    db = app.state.db_factory()
    build_study(db)
    if study == "swap":
        apply_swap(db)
    db.close()
    return create_mcp_server(app.state.db_factory, lambda: None)


async def describe(server) -> str:
    out = ["SERVER INSTRUCTIONS", build_instructions(), "", "TOOLS"]
    for tool in await server.list_tools():
        schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", {})
        props = schema.get("properties", {})
        out.append(f"\n- {tool.name}: {tool.description}")
        out.append("  inputs: " + json.dumps(props))
    return "\n".join(out)


async def call(server, name: str, args: dict):
    result = await server.call_tool(name, args)
    if isinstance(result, tuple):  # (content blocks, structured)
        result = result[1] if result[1] is not None else result[0]
    if isinstance(result, dict):
        return result
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if structured:
        return structured
    blocks = getattr(result, "content", result)
    return json.loads(blocks[0].text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="main", choices=["main", "swap"])
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--call", nargs=2, metavar=("TOOL", "JSON_ARGS"))
    ns = ap.parse_args()
    server = make_server(ns.study)
    if ns.describe:
        print(anyio.run(describe, server))
        return
    if not ns.call:
        ap.error("give --describe or --call TOOL JSON_ARGS")
    name, raw = ns.call
    args = json.loads(raw or "{}")
    log = HERE / "live" / f"{os.environ.get('LAB_AGENT', 'anon')}.jsonl"
    log.parent.mkdir(exist_ok=True)
    try:
        result = anyio.run(call, server, name, args)
        entry = {"t": time.time(), "study": ns.study, "tool": name, "args": args, "result": result}
        print(json.dumps(result, indent=1, default=str))
    except Exception as exc:  # the agent sees what Claude would: an error message
        entry = {"t": time.time(), "study": ns.study, "tool": name, "args": args,
                 "error": f"{type(exc).__name__}: {exc}"}
        print("TOOL ERROR:", entry["error"])
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


if __name__ == "__main__":
    main()
