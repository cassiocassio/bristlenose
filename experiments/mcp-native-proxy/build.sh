#!/usr/bin/env bash
# Build the native MCP proxy spike and the two TCC probes.
# Spike only: see README.md and docs/design-mcp-native-proxy.md.
#
#   SIGN_IDENTITY="Developer ID Application: <you> (<TEAM>)" ./build.sh
#
# The identity's team must be Bristlenose's (the container owner), or the
# same-team container read the whole design rests on will not happen.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
OUT="${OUT:-build}"
mkdir -p "$OUT"
: "${SIGN_IDENTITY:?set SIGN_IDENTITY to a Developer ID identity on the Bristlenose team}"

# tools.json: the same tool list the Node proxy serves (its BN-TOOLS-JSON block),
# each marked read-only so hosts that honour MCP annotations stop asking per tool.
python3 - "$ROOT/desktop/mcpb/server/index.js" "$OUT/tools.json" <<'EOF'
import json, re, sys
src = open(sys.argv[1]).read()
m = re.search(r"BN-TOOLS-JSON-BEGIN \*/\s*const TOOLS = (\[.*?\]);\s*/\* BN-TOOLS-JSON-END", src, re.S)
if not m:
    sys.exit("BN-TOOLS-JSON block not found in index.js")
tools = json.loads(m.group(1))
for t in tools:
    t["annotations"] = {"readOnlyHint": True}
json.dump(tools, open(sys.argv[2], "w"), indent=1)
print(f"tools.json: {len(tools)} tools")
EOF

xcrun swiftc -O main.swift -o "$OUT/bristlenose-mcp"
codesign -f -s "$SIGN_IDENTITY" -o runtime -i app.bristlenose.mcp-proxy "$OUT/bristlenose-mcp"

clang -O2 -o "$OUT/reader" probes/reader.c
cp "$OUT/reader" "$OUT/reader-adhoc"
codesign -f -s - -i org.bristlenose.probe "$OUT/reader-adhoc"
codesign -f -s "$SIGN_IDENTITY" -o runtime -i app.bristlenose.probe "$OUT/reader"
clang -O2 -o "$OUT/disclaim" probes/disclaim.c
codesign -f -s - "$OUT/disclaim"

codesign -dv "$OUT/bristlenose-mcp" 2>&1 | grep -E 'Identifier|TeamIdentifier'
echo "built into $OUT/"
