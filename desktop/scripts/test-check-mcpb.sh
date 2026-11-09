#!/usr/bin/env bash
# Negative fixtures for check-mcpb.sh.
#
# The gate stands between a build and a notarised extension: it refuses an unexpected member, a
# Mach-O, a dev override or a stale version. A gate that cannot fail would let the day an unsigned
# binary enters the bundle read "ok", so each of its checks is driven red against a synthetic
# .mcpb (a zip built here), and an intact one must pass.
#
# Usage: test-check-mcpb.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-mcpb.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-mcpb-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# Builds one .mcpb per case into $TMP and writes a table of "<file>\t<want rc>\t<needle>\t<version>\t<label>".
python3 - "$TMP" <<'PY'
import json, sys, zipfile, copy
tmp = sys.argv[1]
GOOD_M = {
    "manifest_version": "0.3", "tools_generated": True, "name": "bristlenose", "version": "1.2.3",
    "compatibility": {"claude_desktop": ">=1.13576.0", "platforms": ["darwin"], "runtimes": {"node": ">=18"}},
    "server": {"type": "node", "entry_point": "server/index.js"},
}
GOOD_JS = b"console.log('proxy');\n"
rows = []

def make(name, members, rc, needle, label, version="-"):
    with zipfile.ZipFile(f"{tmp}/{name}.mcpb", "w") as z:
        for k, v in members.items():
            z.writestr(k, v)
    rows.append(f"{name}.mcpb\t{rc}\t{needle}\t{version}\t{label}")

def with_manifest(**changes):
    m = copy.deepcopy(GOOD_M)
    for path, value in changes.items():
        keys = path.split("__")
        node = m
        for k in keys[:-1]:
            node = node[k]
        if value is DELETE:
            node.pop(keys[-1], None)
        else:
            node[keys[-1]] = value
    return {"manifest.json": json.dumps(m), "server/index.js": GOOD_JS}

DELETE = object()
make("good", with_manifest(), 0, "check-mcpb: ok", "an intact pack passes")
make("good_ver", with_manifest(), 0, "check-mcpb: ok", "a matching expected version passes", version="1.2.3")
make("stale_ver", with_manifest(), 1, "!= expected", "a pack older than the app is refused", version="9.9.9")
make("extra", {**with_manifest(), "README.md": "hi"}, 1, "unexpected members", "an extra member rides along")
make("missing", {"manifest.json": json.dumps(GOOD_M)}, 1, "missing members", "a missing member is refused")
make("env", {**with_manifest(), ".env": "K=v"}, 1, ".env member must never ship", "a .env member is refused")
make("node", {**with_manifest(), "server/addon.node": "x"}, 1, "native-module filename", "a .node file is refused")
make("macho", {"manifest.json": json.dumps(GOOD_M), "server/index.js": b"\xcf\xfa\xed\xfe" + b"\0" * 8}, 1, "Mach-O magic", "Mach-O magic is refused")
make("placeholder_js", {"manifest.json": json.dumps(GOOD_M), "server/index.js": b'const VERSION = "0.0.0-dev";'}, 1, "unstamped placeholder", "an unstamped proxy VERSION is refused")
make("devoverride", {"manifest.json": json.dumps(GOOD_M), "server/index.js": b"process.env.BRISTLENOSE_DEV_MCP_HANDSHAKE"}, 1, "BRISTLENOSE_DEV_*", "a dev handshake override is refused")
make("badjson", {"manifest.json": "{not json", "server/index.js": GOOD_JS}, 1, "does not parse", "an unparseable manifest is refused")
make("mv04", with_manifest(manifest_version="0.4"), 1, "manifest_version must be", "manifest_version 0.4 is refused")
make("notools", with_manifest(tools_generated=False), 1, "tools_generated must be true", "tools_generated false is refused")
make("digitname", with_manifest(name="bristlenose2"), 1, "no version string in manifest name", "a digit in the name is refused")
make("nofloor", with_manifest(compatibility__claude_desktop=""), 1, "claude_desktop floor missing", "no Claude Desktop floor is refused")
make("platform", with_manifest(compatibility__platforms=["darwin", "win32"]), 1, "platforms must be", "an extra platform is refused")
make("nonode", with_manifest(compatibility__runtimes={}), 1, "runtimes.node floor missing", "no node floor is refused")
make("zerover", with_manifest(version="0.0.0"), 1, "unstamped placeholder", "a 0.0.0 manifest version is refused")
make("servertype", with_manifest(server__type="python"), 1, "server.type must be 'node'", "a non-node server is refused")
make("entry", with_manifest(server__entry_point="server/other.js"), 1, "not in archive", "an entry point that is not packed is refused")
open(f"{tmp}/cases.tsv", "w").write("\n".join(rows) + "\n")
PY

echo "check-mcpb negative fixtures"
while IFS=$'\t' read -r file want needle version label; do
    [ "$version" = "-" ] && version=""   # "-" stands for "no expected version" (tab IFS collapses empties)
    out=$("$GATE" "$TMP/$file" $version 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -4; FAIL=$((FAIL+1)); continue
    fi
    if ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -4; FAIL=$((FAIL+1)); continue
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
done < "$TMP/cases.tsv"

out=$("$GATE" "$TMP/does-not-exist.mcpb" 2>&1); rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$out" | grep -qF "no such .mcpb"; then
    echo "  ✓ a path that does not exist is refused"; PASS=$((PASS+1))
else
    echo "  ✗ a path that does not exist is refused: exit $rc"; FAIL=$((FAIL+1))
fi

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
