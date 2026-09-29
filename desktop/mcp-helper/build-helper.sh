#!/usr/bin/env bash
# Build and sign bristlenose-mcp, the native MCP helper (design-mcp-native-proxy.md §6.9, D1–D3).
#
# One helper per signing class, never mixed: the helper's sandbox container
# remembers the *kind* of signer that first ran it (team + id + validation
# category, measured §6.7), so a Developer ID build and an App Store build of
# the same identifier cannot share a Mac. The channel therefore comes from the
# identity, not from a flag someone can forget:
#
#   "Developer ID Application: …"  → app.bristlenose.mcp.devid   (.dmg)
#   "Apple Distribution: …"        → app.bristlenose.mcp          (App Store / TestFlight)
#   "Apple Development: …"         → app.bristlenose.mcp.dev      (Debug, local)
#   "-" (ad-hoc)                   → refused: an ad-hoc helper cannot read the group
#
# The .dev name is not optional. A Debug build that claimed app.bristlenose.mcp
# would create that container under the `development` category on the
# maintainer's Mac, and the TestFlight build's helper would then hang there
# (§6.7, P0.2b).
#
# A lane whose ARCHIVE identity differs from its final one says so with
# HELPER_CHANNEL: the .dmg archives with Apple Development and is re-signed
# Developer ID at export, so build-dmg.sh passes HELPER_CHANNEL=devid.
#
# Usage:
#   SIGN_IDENTITY="Developer ID Application: … (TEAM)" \
#   HELPER_VERSION="0.32.0+3950" desktop/mcp-helper/build-helper.sh <out-dir>
#
# Environment:
#   SIGN_IDENTITY    required; the identity the host app is signed with (D2).
#   HELPER_VERSION   required; "<release>+<build>", sent as X-Bristlenose-Proxy-Version.
#   HELPER_CHANNEL   optional: appstore | devid | dev, overriding the identity's kind.
#   MARKETPLACE_OUT  optional: also assemble the ChatGPT plugin marketplace there
#                    (.agents/plugins/marketplace.json + plugins/bristlenose/…).
#   TEAM_ID          default Z56GZVA2QB; the group is "$TEAM_ID.app.bristlenose".
#   MIN_MACOS        default: the app's MACOSX_DEPLOYMENT_TARGET from the pbxproj.
#
# Writes <out-dir>/bristlenose-mcp (plus a stamp). Exit 0 = built, signed, and
# passed check-mcp-helper.sh; anything else = do not ship.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="${1:?usage: build-helper.sh <out-dir>}"
: "${SIGN_IDENTITY:?SIGN_IDENTITY must be the identity the host app is signed with}"
: "${HELPER_VERSION:?HELPER_VERSION must be <release>+<build>}"
TEAM_ID="${TEAM_ID:-Z56GZVA2QB}"
GROUP_ID="$TEAM_ID.app.bristlenose"

case "$SIGN_IDENTITY" in
    "Developer ID Application:"*) CHANNEL=devid ;;
    "Apple Distribution:"*) CHANNEL=appstore ;;
    "Apple Development:"*) CHANNEL=dev ;;
    -|"") echo "error: refusing an ad-hoc helper — it cannot read the team group (§6.2)" >&2; exit 1 ;;
    *) echo "error: unrecognised identity kind: $SIGN_IDENTITY" >&2; exit 1 ;;
esac
CHANNEL="${HELPER_CHANNEL:-$CHANNEL}"
case "$CHANNEL" in
    appstore) HELPER_ID="app.bristlenose.mcp" ;;
    devid) HELPER_ID="app.bristlenose.mcp.devid" ;;
    dev) HELPER_ID="app.bristlenose.mcp.dev" ;;
    *) echo "error: HELPER_CHANNEL must be appstore, devid or dev (got '$CHANNEL')" >&2; exit 1 ;;
esac

# The floor, read from the project rather than restated: a helper built for the
# build machine's OS crashes at launch on 15 (libswift_DarwinFoundation1, §6.7).
if [ -z "${MIN_MACOS:-}" ]; then
    MIN_MACOS="$(grep -m1 -o 'MACOSX_DEPLOYMENT_TARGET = [0-9.]*;' \
        "$ROOT/desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj" | grep -o '[0-9.]*[0-9]')"
fi
[ -n "$MIN_MACOS" ] || { echo "error: could not read MACOSX_DEPLOYMENT_TARGET" >&2; exit 1; }

# Skip the compile and sign when nothing that shapes the binary has moved: the
# source, the tool list, the identity, the channel, the version and the floor.
# The gate below still runs over whatever is there.
STAMP="$(cat "$HERE/main.swift" "$ROOT/desktop/mcpb/server/index.js" | shasum | cut -c1-16) $SIGN_IDENTITY $HELPER_ID $HELPER_VERSION $MIN_MACOS"
if [ -x "$OUT/bristlenose-mcp" ] && [ "$(cat "$OUT/.stamp" 2>/dev/null)" = "$STAMP" ]; then
    echo "bristlenose-mcp up to date ($HELPER_ID)"
else
WORK="$(mktemp -d "${TMPDIR:-/tmp}/bristlenose-mcp.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

# Tool list: the Node proxy's BN-TOOLS-JSON block, annotations and all. The
# block is the single source until the Node extension retires (§6.9 P2), and
# tests/test_mcpb_proxy.py holds it equal to the server's tools/list.
python3 - "$ROOT/desktop/mcpb/server/index.js" "$WORK/ToolsEmbedded.swift" <<'PY'
import json, re, sys
src = open(sys.argv[1]).read()
m = re.search(r"BN-TOOLS-JSON-BEGIN \*/\s*const TOOLS = (\[.*?\]);\s*/\* BN-TOOLS-JSON-END", src, re.S)
if not m:
    sys.exit("error: BN-TOOLS-JSON block not found in index.js")
tools = json.loads(m.group(1))
for t in tools:
    if t.get("annotations", {}).get("readOnlyHint") is not True:
        sys.exit(f"error: tool {t.get('name')} lacks readOnlyHint")
text = json.dumps(tools, ensure_ascii=True)
if '"""#' in text:
    sys.exit("error: tool JSON would close the raw string literal")
open(sys.argv[2], "w").write('let TOOLS_JSON = #"""\n' + text + '\n"""#\n')
PY

cat > "$WORK/BuildConfig.swift" <<EOF
let GROUP_ID = "$GROUP_ID"
let VERSION = "$HELPER_VERSION"
EOF

# A sandboxed bare tool traps at launch (exit 133) without an embedded
# Info.plist, and its CFBundleIdentifier must equal the signing identifier.
cat > "$WORK/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>$HELPER_ID</string>
  <key>CFBundleName</key><string>bristlenose-mcp</string>
  <key>CFBundleShortVersionString</key><string>${HELPER_VERSION%%+*}</string>
  <key>CFBundleVersion</key><string>${HELPER_VERSION##*+}</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_MACOS</string>
</dict></plist>
EOF

# Sandboxed, NOT inherit (the host that launches it is not our app), network
# client for the loopback serve, and the team group. Nothing else.
cat > "$WORK/helper.entitlements" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>com.apple.security.app-sandbox</key><true/>
  <key>com.apple.security.network.client</key><true/>
  <key>com.apple.security.application-groups</key><array><string>$GROUP_ID</string></array>
</dict></plist>
EOF

# Compiled and signed alone in its own directory: signed beside a loose
# Info.plist, codesign seals that directory as the binary's resources, and the
# signature is then "invalid resource directory" the moment the file is copied.
mkdir -p "$WORK/bin"
xcrun swiftc -O -target "arm64-apple-macos$MIN_MACOS" \
    "$HERE/main.swift" "$WORK/BuildConfig.swift" "$WORK/ToolsEmbedded.swift" \
    -o "$WORK/bin/bristlenose-mcp" \
    -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$WORK/Info.plist"

TIMESTAMP=(--timestamp)
[ "${SIGN_IDENTITY#Apple Development:}" != "$SIGN_IDENTITY" ] && TIMESTAMP=(--timestamp=none)
codesign --force --sign "$SIGN_IDENTITY" --options runtime "${TIMESTAMP[@]}" \
    --identifier "$HELPER_ID" --entitlements "$WORK/helper.entitlements" "$WORK/bin/bristlenose-mcp"

cp "$WORK/bin/bristlenose-mcp" "$OUT/bristlenose-mcp"
echo "$STAMP" > "$OUT/.stamp"
fi  # end of the compile-and-sign block skipped when the stamp matches

COPIES=("$OUT/bristlenose-mcp")
if [ -n "${MARKETPLACE_OUT:-}" ]; then
    # The ChatGPT plugin, laid out as ChatGPT's own link expects it: the
    # marketplace file two levels under its root, the plugin beside it
    # (design §1.1). Rebuilt from scratch every time: it is small, and a
    # leftover file from an older layout must not survive.
    rm -rf "$MARKETPLACE_OUT"
    PLUGIN="$MARKETPLACE_OUT/plugins/bristlenose"
    mkdir -p "$MARKETPLACE_OUT/.agents/plugins" "$PLUGIN/.codex-plugin" "$PLUGIN/bin" "$PLUGIN/assets"
    cp -p "$OUT/bristlenose-mcp" "$PLUGIN/bin/bristlenose-mcp"
    # The app's own icon, so ChatGPT shows the fish rather than its generic mark.
    ICONS="$ROOT/desktop/Bristlenose/Bristlenose/Assets.xcassets/AppIcon.appiconset"
    cp "$ICONS/icon_256x256.png" "$PLUGIN/assets/logo.png"
    cp "$ICONS/icon_32x32@2x.png" "$PLUGIN/assets/icon.png"
    python3 - "$MARKETPLACE_OUT" "$HELPER_VERSION" <<'PY'
import json, sys
root, version = sys.argv[1], sys.argv[2]
def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
dump(f"{root}/.agents/plugins/marketplace.json", {
    "name": "bristlenose",
    "interface": {"displayName": "Bristlenose"},
    "plugins": [{
        "name": "bristlenose",
        "source": {"source": "local", "path": "./plugins/bristlenose"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Research",
    }],
})
# The version carries the build number: ChatGPT caches by version (D8).
dump(f"{root}/plugins/bristlenose/.codex-plugin/plugin.json", {
    "name": "bristlenose",
    "version": version,
    "description": "Ask your Bristlenose study — quotes, themes, signals, frameworks — from your agent. Read-only.",
    "author": {"name": "Bristlenose"},
    "mcpServers": "./.mcp.json",
    "interface": {"displayName": "Bristlenose", "shortDescription": "Ask your Bristlenose study",
                  "developerName": "Bristlenose", "category": "Research", "capabilities": ["Read"],
                  "composerIcon": "./assets/icon.png", "logo": "./assets/logo.png",
                  "websiteURL": "https://bristlenose.app",
                  "privacyPolicyURL": "https://bristlenose.app/privacy.html"},
})
# A relative command resolves against the installed plugin folder when cwd is
# "./"; `env` replaces PATH, which the helper does not need (design §1.1).
dump(f"{root}/plugins/bristlenose/.mcp.json", {
    "mcpServers": {"bristlenose": {
        "type": "stdio", "command": "./bin/bristlenose-mcp", "args": [], "cwd": "./",
        "env": {"BRISTLENOSE_MCP_HOST": "ChatGPT", "PATH": "/usr/bin:/bin"},
    }},
})
PY
    COPIES+=("$PLUGIN/bin/bristlenose-mcp")
fi

MCP_HELPER_EXPECT_ID="$HELPER_ID" "$ROOT/desktop/scripts/check-mcp-helper.sh" "${COPIES[@]}"
echo "built $OUT/bristlenose-mcp ($HELPER_ID, $HELPER_VERSION, macOS $MIN_MACOS+)"
