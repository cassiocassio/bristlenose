"""The native MCP helper (``desktop/mcp-helper/``), checked without building it.

Three contracts, each one a way the helper could ship quietly wrong:

1. **Nothing the App Store rejects, nothing from the spike.** The helper replaced
   a spike that relaunched itself through private SPI
   (``responsibility_spawnattrs_setdisclaim``) and carried a ``--seed`` test mode
   that writes the app group. Neither may reach the product source
   (docs/design-mcp-native-proxy.md §6.1, §6.9 D3).
2. **It says what the Node proxy says.** Hosts relay these sentences to the
   researcher; the two proxies speak for the same app and must not disagree.
   The permission sentence differs on purpose: a sandboxed helper cannot be
   rescued by Files & Folders, so it points at reinstalling instead.
3. **It is built for the app's floor and keeps the tool annotations.** A helper
   compiled for the build machine's OS crashes on macOS 15 (§6.7), and a tool
   list without ``readOnlyHint`` brings back ChatGPT's per-tool approval cards.

The gate over a *built* helper is ``desktop/scripts/check-mcp-helper.sh``; the
last test drives it against a binary it must refuse.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).parent.parent
_HELPER = _REPO / "desktop" / "mcp-helper" / "main.swift"
_BUILD = _REPO / "desktop" / "mcp-helper" / "build-helper.sh"
_GATE = _REPO / "desktop" / "scripts" / "check-mcp-helper.sh"
_NODE = _REPO / "desktop" / "mcpb" / "server" / "index.js"

# Node key → Swift constant. `permission` is absent deliberately (see docstring).
_SHARED_MESSAGES = {
    "closed": "MSG_CLOSED",
    "starting": "MSG_STARTING",
    "noAgentSupport": "MSG_NO_AGENT",
    "authFailed": "MSG_AUTH",
    "outdated": "MSG_OUTDATED",
}


def _join_literals(expr: str, *, swift: bool) -> str:
    """Concatenate the string literals in a `"a" + "b" + GROUNDING` expression."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', expr)
    text = "".join(parts)
    if swift:
        text = re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: chr(int(m.group(1), 16)), text)
    else:
        text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return text


def _node_message(key: str) -> str:
    src = _NODE.read_text(encoding="utf-8")
    m = re.search(rf"\n\s*{key}:\s*(.*?\+ GROUNDING),", src, re.S)
    assert m, f"Node proxy has no MSG.{key}"
    return _join_literals(m.group(1), swift=False)


def _swift_message(name: str) -> str:
    src = _HELPER.read_text(encoding="utf-8")
    m = re.search(rf"^let {name} = (.*?\+ GROUNDING)$", src, re.M)
    assert m, f"helper has no {name}"
    return _join_literals(m.group(1), swift=True)


def test_helper_source_has_no_private_spi_and_no_spike_mode() -> None:
    src = _HELPER.read_text(encoding="utf-8")
    for forbidden in ("responsibility_", "--seed", "_silgen_name", "setdisclaim", "GROUP_VARIANT"):
        assert forbidden not in src, f"{forbidden!r} must not be in the shipped helper"


@pytest.mark.parametrize(("node_key", "swift_name"), sorted(_SHARED_MESSAGES.items()))
def test_helper_speaks_the_node_proxys_sentences(node_key: str, swift_name: str) -> None:
    assert _swift_message(swift_name) == _node_message(node_key)


def test_helper_grounding_matches_node() -> None:
    node = re.search(r'const GROUNDING =\s*"([^"]*)"', _NODE.read_text(encoding="utf-8"))
    swift = re.search(r'^let GROUNDING = "([^"]*)"', _HELPER.read_text(encoding="utf-8"), re.M)
    assert node and swift
    assert swift.group(1) == node.group(1)


def test_helper_permission_sentence_points_at_reinstall_not_files_and_folders() -> None:
    # Sandboxed: the sandbox refuses the read before TCC is asked, so the Files &
    # Folders switch cannot help, and sending the researcher there is a dead end.
    text = _swift_message("MSG_PERMISSION")
    assert "Files & Folders" not in text
    assert "install the extension again" in text


def test_build_script_targets_the_apps_deployment_floor() -> None:
    script = _BUILD.read_text(encoding="utf-8")
    assert "MACOSX_DEPLOYMENT_TARGET" in script, "the floor must be read from the project"
    assert '-target "arm64-apple-macos$MIN_MACOS"' in script


def test_build_script_refuses_tools_without_read_only_hint() -> None:
    script = _BUILD.read_text(encoding="utf-8")
    assert 'get("readOnlyHint") is not True' in script


def test_build_script_maps_each_signer_kind_to_its_own_identifier() -> None:
    script = _BUILD.read_text(encoding="utf-8")
    for line in ('"Developer ID Application:"*) CHANNEL=devid',
                 '"Apple Distribution:"*) CHANNEL=appstore',
                 '"Apple Development:"*) CHANNEL=dev',
                 'appstore) HELPER_ID="app.bristlenose.mcp"',
                 'devid) HELPER_ID="app.bristlenose.mcp.devid"',
                 'dev) HELPER_ID="app.bristlenose.mcp.dev"'):
        assert line in script, line
    assert "app.bristlenose.mcp-proxy" not in script, "the spike's id is spent (§6.6)"


@pytest.mark.skipif(sys.platform != "darwin", reason="codesign/otool are macOS tools")
def test_gate_refuses_an_unsandboxed_unsigned_binary(tmp_path: Path) -> None:
    if shutil.which("clang") is None:
        pytest.skip("no clang")
    src = tmp_path / "x.c"
    src.write_text("int main(void){return 0;}\n")
    binary = tmp_path / "bristlenose-mcp"
    subprocess.run(["clang", "-o", str(binary), str(src)], check=True)
    subprocess.run(["codesign", "-f", "-s", "-", str(binary)], check=True, capture_output=True)
    r = subprocess.run(["bash", str(_GATE), str(binary)], capture_output=True, text=True)
    assert r.returncode == 1
    for reason in ("not sandboxed", "application-groups", "TeamIdentifier"):
        assert reason in r.stderr, f"gate did not report {reason!r}:\n{r.stderr}"
