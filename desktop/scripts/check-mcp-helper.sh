#!/usr/bin/env bash
# The one gate over the native MCP helper (design-mcp-native-proxy.md §6.9, D3).
#
# Usage:
#   desktop/scripts/check-mcp-helper.sh [--host <App.app>] <helper> [<helper> ...]
#
# Every copy of the helper a build ships (Helpers/, and the ChatGPT
# marketplace's bin/) is checked, and the copies must carry the same code
# (CDHash; after export their timestamps differ, so bytes can't be compared). With
# --host, the helper's team group must be one the host app also carries,
# otherwise the app writes a handshake the helper can never read.
#
# Why each check exists:
#   sandboxed, no inherit   — App Store rule for nested executables; inherit
#                             would crash it, because the launcher is ChatGPT or
#                             Claude, not our app.
#   team group              — the only way it can read the handshake (§6.2).
#   Info.plist id == signer — a sandboxed bare tool traps without one; a
#                             mismatch is the 14 Jul "Invalid Code Signature
#                             Identifier" rejection.
#   id matches signer kind  — a helper container remembers its signer kind; two
#                             kinds under one id hang (§6.6, §6.7). Developer ID
#                             → .mcp.devid, Apple Development → .mcp.dev, Apple's
#                             store and TestFlight signers → .mcp.
#   minos == app floor      — built for the build machine's OS it crashes on 15.
#   no responsibility_*     — private SPI; App Review rejects it (§6.1).
#   no --seed               — the spike's write-the-group test mode.
#
# Exit 0 = every copy passes. Anything else = do not ship.
set -euo pipefail

TEAM_ID="${TEAM_ID:-Z56GZVA2QB}"
GROUP_ID="$TEAM_ID.app.bristlenose"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOST=""
if [ "${1:-}" = "--host" ]; then HOST="${2:?--host needs an app path}"; shift 2; fi
[ "$#" -ge 1 ] || { echo "usage: check-mcp-helper.sh [--host <App.app>] <helper>..." >&2; exit 2; }

MIN_MACOS="${MIN_MACOS:-$(grep -m1 -o 'MACOSX_DEPLOYMENT_TARGET = [0-9.]*;' \
    "$ROOT/desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj" | grep -o '[0-9.]*[0-9]')}"

fail=0
die_one() { echo "  FAIL $1" >&2; fail=1; }
WORK="$(mktemp -d "${TMPDIR:-/tmp}/check-mcp-helper.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

entitlement() {  # <binary> <key> → JSON value, or "null"
    codesign -d --entitlements - --xml "$1" 2>/dev/null > "$WORK/ent.plist" || true
    python3 - "$WORK/ent.plist" "$2" <<'PY'
import json, plistlib, sys
try:
    d = plistlib.load(open(sys.argv[1], "rb"))
except Exception:
    d = {}
print(json.dumps(d.get(sys.argv[2])))
PY
}

host_groups=""
if [ -n "$HOST" ]; then
    host_groups="$(entitlement "$HOST" com.apple.security.application-groups)"
fi

first=""
for h in "$@"; do
    echo "== $h"
    [ -f "$h" ] || { die_one "missing"; continue; }
    codesign --verify --strict "$h" 2>"$WORK/verify.txt" || die_one "codesign --verify: $(tr '\n' ' ' < "$WORK/verify.txt")"
    codesign -dvv "$h" > "$WORK/info.txt" 2>&1 || true
    codesign -dvvv "$h" > "$WORK/cd.txt" 2>&1 || true
    ident="$(sed -n 's/^Identifier=//p' "$WORK/info.txt")"
    team="$(sed -n 's/^TeamIdentifier=//p' "$WORK/info.txt")"
    authority="$(sed -n 's/^Authority=//p' "$WORK/info.txt" | head -1)"

    [ "$(entitlement "$h" com.apple.security.app-sandbox)" = "true" ] || die_one "not sandboxed"
    [ "$(entitlement "$h" com.apple.security.inherit)" = "null" ] || die_one "carries com.apple.security.inherit"
    [ "$(entitlement "$h" com.apple.security.network.client)" = "true" ] || die_one "no network.client"
    groups="$(entitlement "$h" com.apple.security.application-groups)"
    [ "$groups" = "[\"$GROUP_ID\"]" ] || die_one "application-groups is $groups, want [\"$GROUP_ID\"]"
    if [ -n "$HOST" ]; then
        case "$host_groups" in *"\"$GROUP_ID\""*) ;; *) die_one "host $HOST lacks $GROUP_ID (has $host_groups)" ;; esac
    fi

    [ "$team" = "$TEAM_ID" ] || die_one "TeamIdentifier is '$team', want $TEAM_ID"
    case "$authority" in
        "Developer ID Application:"*) want="app.bristlenose.mcp.devid" ;;
        "Apple Distribution:"*|"TestFlight Beta Distribution"|"Apple Mac OS Application Signing") want="app.bristlenose.mcp" ;;
        "Apple Development:"*) want="app.bristlenose.mcp.dev" ;;
        *) want="(unsignable: $authority)" ;;
    esac
    # Mid-build, a lane whose archive identity is not its final one names the
    # identifier it will ship with (the .dmg archives Apple Development and is
    # re-signed Developer ID at export). After export, run without it.
    want="${MCP_HELPER_EXPECT_ID:-$want}"
    [ "$ident" = "$want" ] || die_one "identifier '$ident' for signer '$authority', want $want"

    otool -P "$h" > "$WORK/plist.txt" 2>/dev/null || true
    plist_id="$(python3 - "$WORK/plist.txt" <<'PY'
import plistlib, re, sys
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"<\?xml.*</plist>", raw, re.S)
print(plistlib.loads(m.group(0).encode()).get("CFBundleIdentifier", "") if m else "")
PY
)"
    [ "$plist_id" = "$ident" ] || die_one "embedded Info.plist CFBundleIdentifier '$plist_id' != signing identifier '$ident'"

    otool -l "$h" > "$WORK/load.txt"
    minos="$(awk '/LC_BUILD_VERSION/{f=1} f&&/minos/{print $2; exit}' "$WORK/load.txt")"
    [ "$minos" = "$MIN_MACOS" ] || die_one "minos $minos, want the app floor $MIN_MACOS"

    # Output to a file first, then grep: `nm | grep -q` under pipefail reports a
    # SIGPIPE'd nm as "no match" (root CLAUDE.md, printf|grep -q).
    nm -u "$h" > "$WORK/nm.txt" 2>/dev/null || true
    strings -a "$h" > "$WORK/strings.txt" 2>/dev/null || true
    if grep -q 'responsibility_' "$WORK/nm.txt" "$WORK/strings.txt"; then die_one "references responsibility_* (private SPI)"; fi
    if grep -q -- '--seed' "$WORK/strings.txt"; then die_one "contains the spike's --seed mode"; fi

    # The same CODE, not the same bytes: an export re-signs each copy with its
    # own secure timestamp, so two identical helpers differ byte for byte. The
    # CDHash covers the code and the signing identifier and nothing else.
    cdhash="$(sed -n 's/^CDHash=//p' "$WORK/cd.txt" 2>/dev/null)"
    if [ -z "$first" ]; then first="$h"; first_cdhash="$cdhash"
    elif [ "$cdhash" != "$first_cdhash" ]; then die_one "code differs from $first (CDHash $cdhash vs $first_cdhash)"; fi
    [ "$fail" = 0 ] && echo "  ok  $ident · $authority · macOS $minos+"
done

if [ "$fail" != 0 ]; then echo "check-mcp-helper: FAILED" >&2; exit 1; fi
echo "check-mcp-helper: $# cop$( [ "$#" = 1 ] && echo y || echo ies ) ok"
