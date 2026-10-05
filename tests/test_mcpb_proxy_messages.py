"""The .mcpb proxy's permission sentence, driven through the real proxy.

On macOS 27 an agent app's first read of our container is denied with no
dialog, and the grant is a switch in System Settings ▸ Files & Folders
(measured 29 Sep 2026, ``docs/design-mcp-files-and-folders.md`` §1). The
sentence the model relays has to say so, name the host the PACKAGE declares
(never a detected client), and end with the grounding line every failure
carries. These run the unmodified proxy under Node, with the handshake made
unreadable (EACCES is the same branch as TCC's EPERM).

``HOME`` points at a temp dir so the proxy's real container paths resolve to
nothing, whatever this machine has installed. ``BRISTLENOSE_DEV_DARWIN_MAJOR``
picks the macOS branch on any OS, so the tests run on Linux CI too; both dev
overrides are stripped from the packed extension (``build-mcpb.sh``).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PROXY_JS = Path(__file__).parent.parent / "desktop" / "mcpb" / "server" / "index.js"
_GROUNDING = "Do not answer from memory or from general knowledge."

pytestmark = [
    pytest.mark.skipif(shutil.which("node") is None, reason="node not installed"),
    pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                       reason="root reads a 000 file, so the denial can't be staged"),
    pytest.mark.skipif(sys.platform == "win32",
                       reason="chmod 0 denies nothing on Windows, and these are macOS TCC messages"),
]


def _permission_text(tmp_path: Path, *, darwin_major: str, host: str | None) -> str:
    handshake = tmp_path / "mcp-handshake.json"
    handshake.write_text('{"schema": 2, "projects": []}', encoding="utf-8")
    handshake.chmod(0)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "BRISTLENOSE_DEV_MCP_HANDSHAKE": str(handshake),
        "BRISTLENOSE_DEV_DARWIN_MAJOR": darwin_major,
    }
    if host is not None:
        env["BRISTLENOSE_MCP_HOST"] = host
    frames = [
        {"jsonrpc": "2.0", "id": 0, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "list_projects", "arguments": {}}},
    ]
    try:
        proc = subprocess.run(
            ["node", str(_PROXY_JS)],
            input="".join(json.dumps(f) + "\n" for f in frames),
            capture_output=True, text=True, env=env, timeout=20,
        )
    finally:
        handshake.chmod(0o600)
    for line in proc.stdout.splitlines():
        msg = json.loads(line)
        if msg.get("id") == 1:
            return msg["result"]["content"][0]["text"]
    raise AssertionError(f"no reply to the tool call; stderr: {proc.stderr[-800:]}")


def test_macos27_names_the_declared_host_and_the_switch(tmp_path: Path) -> None:
    text = _permission_text(tmp_path, darwin_major="27", host="Claude")
    assert "macOS has blocked Claude from reading Bristlenose" in text
    assert "there is no prompt" in text
    assert "System Settings ▸ Privacy & Security ▸ Files & Folders" in text
    assert "expand Claude in the list, and turn on Bristlenose" in text
    assert "Nothing in Bristlenose needs changing" in text
    assert "click Allow" not in text
    assert text.endswith(_GROUNDING)


def test_macos27_without_a_declared_host_names_no_product(tmp_path: Path) -> None:
    text = _permission_text(tmp_path, darwin_major="27", host=None)
    assert "macOS has blocked your AI app from reading Bristlenose" in text
    assert "expand your AI app in the list" in text
    assert "Claude" not in text and "ChatGPT" not in text
    assert text.endswith(_GROUNDING)


def test_macos26_keeps_the_dialog_sentence_with_the_declared_host(tmp_path: Path) -> None:
    text = _permission_text(tmp_path, darwin_major="25", host="ChatGPT")
    assert "macOS is asking whether ChatGPT may access data from other apps" in text
    assert "click Allow" in text
    assert "Files & Folders" not in text
    assert text.endswith(_GROUNDING)
