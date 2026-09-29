#!/usr/bin/env bash
# Build the native MCP proxy spike (both variants) and the TCC probes.
# Spike only: see README.md and docs/design-mcp-native-proxy.md.
#
#   SIGN_IDENTITY="Developer ID Application: <you> (<TEAM>)" ./build.sh
#
# The identity's team must be the one that signs Bristlenose (the container and
# group owner), or the same-team access the design rests on will not happen.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"
OUT="${OUT:-build}"
mkdir -p "$OUT"
: "${SIGN_IDENTITY:?set SIGN_IDENTITY to a Developer ID identity on the Bristlenose team}"

# Tool list, compiled in: the Node proxy's BN-TOOLS-JSON block, each tool marked
# read-only so hosts that honour MCP annotations stop asking per tool.
python3 - "$ROOT/desktop/mcpb/server/index.js" "$OUT/tools.json" "$OUT/tools_embedded.swift" <<'EOF'
import json, re, sys
src = open(sys.argv[1]).read()
m = re.search(r"BN-TOOLS-JSON-BEGIN \*/\s*const TOOLS = (\[.*?\]);\s*/\* BN-TOOLS-JSON-END", src, re.S)
if not m:
    sys.exit("BN-TOOLS-JSON block not found in index.js")
tools = json.loads(m.group(1))
for t in tools:
    t["annotations"] = {"readOnlyHint": True}
text = json.dumps(tools, ensure_ascii=True)
json.dump(tools, open(sys.argv[2], "w"), indent=1)
assert '"""' not in text and "\\(" not in text
open(sys.argv[3], "w").write('let TOOLS_JSON = #"""\n' + text + '\n"""#\n')
print(f"tools: {len(tools)}")
EOF

# 1. Disclaim variant (private SPI; Developer ID only).
xcrun swiftc -O main.swift "$OUT/tools_embedded.swift" -o "$OUT/bristlenose-mcp"
codesign -f -s "$SIGN_IDENTITY" -o runtime -i app.bristlenose.mcp-proxy "$OUT/bristlenose-mcp"

# 2. Group variant (App Store shape): sandboxed, no inherit, network client,
#    the Team-ID-prefixed group, and an embedded Info.plist. Without the
#    Info.plist a sandboxed bare tool traps at launch with exit 133.
cat > "$OUT/group-Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>app.bristlenose.mcp-proxy</string>
  <key>CFBundleName</key><string>bristlenose-mcp</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>0.0.6</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
</dict></plist>
EOF
cat > "$OUT/group.entitlements" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>com.apple.security.app-sandbox</key><true/>
  <key>com.apple.security.network.client</key><true/>
  <key>com.apple.security.application-groups</key>
  <array><string>Z56GZVA2QB.app.bristlenose</string></array>
</dict></plist>
EOF
xcrun swiftc -O -D GROUP_VARIANT main.swift "$OUT/tools_embedded.swift" -o "$OUT/bristlenose-mcp-group" \
    -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$OUT/group-Info.plist"
codesign -f -s "$SIGN_IDENTITY" -o runtime --entitlements "$OUT/group.entitlements" \
    -i app.bristlenose.mcp-proxy "$OUT/bristlenose-mcp-group"
if nm -u "$OUT/bristlenose-mcp-group" | grep -q responsibility_; then
    echo "error: group variant references responsibility_* (private SPI)" >&2; exit 1
fi

# 3. Probes.
clang -O2 -o "$OUT/reader" probes/reader.c
cp "$OUT/reader" "$OUT/reader-adhoc"
codesign -f -s - -i org.bristlenose.probe "$OUT/reader-adhoc"
codesign -f -s "$SIGN_IDENTITY" -o runtime -i app.bristlenose.probe "$OUT/reader"
clang -O2 -o "$OUT/teamcat" probes/teamcat.c
codesign -f -s "$SIGN_IDENTITY" -o runtime -i app.bristlenose.teamcat "$OUT/teamcat"
clang -O2 -o "$OUT/disclaim" probes/disclaim.c
codesign -f -s - "$OUT/disclaim"

for b in bristlenose-mcp bristlenose-mcp-group; do
    printf '%s: ' "$b"; codesign -dv "$OUT/$b" 2>&1 | grep -E 'TeamIdentifier' | tr '\n' ' '
    if codesign -d --entitlements - "$OUT/$b" 2>/dev/null | grep -q app-sandbox; then echo sandboxed; else echo unsandboxed; fi
done
echo "built into $OUT/"
