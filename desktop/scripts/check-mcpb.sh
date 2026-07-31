#!/usr/bin/env bash
# Gate the packed .mcpb extension (built by build-mcpb.sh).
#
# Four checks, all fail-closed:
#   1. Exactly the allowlisted members (manifest.json, server/index.js) —
#      nothing rides along.
#   2. manifest.json parses and carries the settled values (design §4):
#      manifest_version 0.3, tools_generated true, the Claude Desktop
#      version floor, node >=18, darwin, and NO version string in `name`.
#   3. No Mach-O anywhere in the archive (.node/.dylib/.so or magic-number)
#      — the day a dep grows one is the day an unsigned binary silently
#      enters a notarised bundle (design §4a).
#   4. No dev handshake override (`BRISTLENOSE_DEV_MCP_HANDSHAKE`) and no
#      .env* member — the override is attacker-settable via launchctl
#      setenv (design §3.1, risk: MITM inside the tool-result envelope).
#
# Usage: check-mcpb.sh <path-to-.mcpb>
# bash 3.2-safe (may run under Xcode's /bin/bash one day).

set -euo pipefail

MCPB="${1:?usage: check-mcpb.sh <path-to-.mcpb>}"

if [ ! -f "$MCPB" ]; then
    echo "error: no such .mcpb: $MCPB" >&2
    exit 1
fi

# Resolve a python3: repo venv first (always present on dev machines),
# system python3 otherwise.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
    echo "error: no python3 available for .mcpb inspection" >&2
    exit 1
fi

"$PY" - "$MCPB" <<'PYEOF'
import json
import sys
import zipfile

MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",  # 32-bit
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",  # 64-bit
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",  # universal
}
ALLOWED = {"manifest.json", "server/index.js"}

path = sys.argv[1]
failures: list[str] = []

with zipfile.ZipFile(path) as z:
    names = [n for n in z.namelist() if not n.endswith("/")]

    unexpected = sorted(set(names) - ALLOWED)
    missing = sorted(ALLOWED - set(names))
    if unexpected:
        failures.append(f"unexpected members: {unexpected}")
    if missing:
        failures.append(f"missing members: {missing}")

    for name in names:
        if name.startswith(".env") or "/.env" in name:
            failures.append(f".env member must never ship: {name}")
        if name.endswith((".node", ".dylib", ".so")):
            failures.append(f"native-module filename in archive: {name}")
        data = z.read(name)
        if data[:4] in MACHO_MAGICS:
            failures.append(f"Mach-O magic in member: {name}")
        if b"BRISTLENOSE_DEV_MCP_HANDSHAKE" in data:
            failures.append(
                f"dev handshake override shipped in {name} — "
                "build-mcpb.sh must strip mcpb-dev-only lines"
            )

    if "manifest.json" in names:
        try:
            m = json.loads(z.read("manifest.json"))
        except ValueError as exc:
            failures.append(f"manifest.json does not parse: {exc}")
        else:
            def expect(cond: bool, msg: str) -> None:
                if not cond:
                    failures.append(msg)

            expect(m.get("manifest_version") == "0.3",
                   f"manifest_version must be '0.3' (0.4 fails 'latest' "
                   f"validation), got {m.get('manifest_version')!r}")
            expect(m.get("tools_generated") is True,
                   "tools_generated must be true — it is what lets the "
                   "fallback work when Bristlenose is closed")
            name = m.get("name", "")
            expect(bool(name), "manifest name missing")
            expect(not any(ch.isdigit() for ch in name),
                   f"no version string in manifest name (enterprise "
                   f"allowlists key on it): {name!r}")
            compat = m.get("compatibility", {})
            expect(compat.get("claude_desktop", "").startswith(">="),
                   "compatibility.claude_desktop floor missing (below "
                   "1.13576.0 a yauzl deadlock hangs the unzip)")
            expect(compat.get("platforms") == ["darwin"],
                   f"platforms must be ['darwin'], got {compat.get('platforms')!r}")
            expect(compat.get("runtimes", {}).get("node", "").startswith(">="),
                   "runtimes.node floor missing")
            server = m.get("server", {})
            expect(server.get("type") == "node", "server.type must be 'node'")
            expect(server.get("entry_point") in names,
                   f"entry_point {server.get('entry_point')!r} not in archive")

if failures:
    for f in failures:
        print(f"check-mcpb: FAIL: {f}", file=sys.stderr)
    sys.exit(1)
print(f"check-mcpb: ok ({path})")
PYEOF
