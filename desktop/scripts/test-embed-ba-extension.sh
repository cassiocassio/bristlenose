#!/usr/bin/env bash
# Fixtures for embed-ba-extension.sh (the Run Script phase that puts the Background Assets extension
# into the store build). Each case builds a fake build tree and runs the script with Xcode's variables.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SCRIPT_DIR/embed-ba-extension.sh"
[ -x "$SCRIPT" ] || { echo "not executable: $SCRIPT" >&2; exit 2; }
[ -x /usr/libexec/PlistBuddy ] || { echo "embed-ba-extension: skipped, needs PlistBuddy (macOS)"; exit 0; }
T=$(mktemp -d "${TMPDIR:-/tmp}/bn-embed-test.XXXXXX"); trap 'rm -rf "$T"' EXIT
PASS=0; FAIL=0
ok() { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

tree() {   # tree <name> -> prints the dir; has an app Info.plist, and optionally a product
    local d="$T/$1"; mkdir -p "$d/products/Bristlenose.app/Contents" "$d/products"
    printf '<?xml version="1.0"?><plist version="1.0"><dict><key>CFBundleIdentifier</key><string>app.bristlenose</string></dict></plist>' > "$d/products/Bristlenose.app/Contents/Info.plist"
    echo "$d"
}
product() { mkdir -p "$1/products/BAExtension.appex/Contents"; echo x > "$1/products/BAExtension.appex/Contents/Info.plist"; }
run() {  # run <dir> [VAR=val ...]; sets OUT and RC
    local d="$1"; shift
    OUT=$(env BUILT_PRODUCTS_DIR="$d/products" BUILD_DIR="$d" TARGET_BUILD_DIR="$d/products" \
          CONTENTS_FOLDER_PATH="Bristlenose.app/Contents" INFOPLIST_PATH="Bristlenose.app/Contents/Info.plist" \
          DEVELOPMENT_TEAM=Z56GZVA2QB "$@" bash "$SCRIPT" 2>&1); RC=$?
}
has_key() { /usr/libexec/PlistBuddy -c "Print :$2" "$1/products/Bristlenose.app/Contents/Info.plist" >/dev/null 2>&1; }

echo "embed-ba-extension fixtures"
d=$(tree on); product "$d"; run "$d" BN_EMBED_BA=YES
[ $RC -eq 0 ] && [ -d "$d/products/Bristlenose.app/Contents/PlugIns/BAExtension.appex/Contents" ] && ok "flag on: the extension is embedded" || { bad "flag on: embedded (rc=$RC)"; echo "$OUT" | sed 's/^/      /'; }
has_key "$d" BAAppGroupID && has_key "$d" BAHasManagedAssetPacks && has_key "$d" BAUsesAppleHosting && ok "flag on: the three host keys are added" || bad "flag on: keys"
[ "$(/usr/libexec/PlistBuddy -c 'Print :BAAppGroupID' "$d/products/Bristlenose.app/Contents/Info.plist" 2>/dev/null)" = "Z56GZVA2QB.app.bristlenose" ] && ok "flag on: the group is the team-prefixed one" || bad "flag on: group value"

# flag off, with leftovers from an earlier store build
run "$d" BN_EMBED_BA=NO
[ $RC -eq 0 ] && [ ! -e "$d/products/Bristlenose.app/Contents/PlugIns/BAExtension.appex" ] && ok "flag off: a stale extension is removed" || bad "flag off: stale extension kept"
! has_key "$d" BAAppGroupID && ! has_key "$d" BAHasManagedAssetPacks && ! has_key "$d" BAUsesAppleHosting && ok "flag off: stale host keys are removed" || bad "flag off: stale keys kept"
d=$(tree unset); product "$d"; mkdir -p "$d/products/Bristlenose.app/Contents/PlugIns"; run "$d"
[ $RC -eq 0 ] && [ ! -e "$d/products/Bristlenose.app/Contents/PlugIns/BAExtension.appex" ] && grep -q "nothing embedded" <<<"$OUT" && ok "flag unset: nothing embedded, succeeds, says so honestly (no 'removed' claim when nothing was)" || bad "flag unset (rc=$RC): $OUT"
! grep -q "removed:" <<<"$OUT" && ok "flag unset: no stale artefacts, so no removal is claimed" || bad "flag unset claims a removal"
# no Xcode variables at all (a wrong environment): must neither fail nor delete anything unrelated
sentinel="$T/sentinel"; mkdir -p "$sentinel/PlugIns/BAExtension.appex"
OUT=$(env -i PATH="$PATH" BN_EMBED_BA=NO bash "$SCRIPT" 2>&1); RC=$?
[ $RC -eq 0 ] && [ -d "$sentinel/PlugIns/BAExtension.appex" ] && ok "no Xcode variables: succeeds and touches nothing" || bad "no-variables case (rc=$RC)"

d=$(tree nosrc); run "$d" BN_EMBED_BA=YES
[ $RC -ne 0 ] && grep -q "BAExtension.appex not found" <<<"$OUT" && ok "flag on, no product: refuses (a store build must not quietly lack it)" || bad "flag on, no product: did not refuse"

d=$(tree dmg); product "$d"; run "$d" BN_EMBED_BA=YES SWIFT_ACTIVE_COMPILATION_CONDITIONS="DEBUG DEVELOPER_ID_BETA"
[ $RC -ne 0 ] && grep -q "DEVELOPER_ID_BETA" <<<"$OUT" && [ ! -e "$d/products/Bristlenose.app/Contents/PlugIns" ] && ok "flag on in a .dmg build: refuses, embeds nothing" || bad ".dmg build not refused"

d=$(tree noteam); product "$d"; before=$(cat "$d/products/Bristlenose.app/Contents/Info.plist")
run "$d" BN_EMBED_BA=YES DEVELOPMENT_TEAM=
[ $RC -ne 0 ] && [ ! -e "$d/products/Bristlenose.app/Contents/PlugIns" ] && [ "$before" = "$(cat "$d/products/Bristlenose.app/Contents/Info.plist")" ] && ok "flag on, no team: refuses and leaves the bundle untouched (no appex copied, plist unchanged)" || bad "no team: refused too late or changed something"

echo; echo "$PASS passed, $FAIL failed"; [ "$FAIL" -eq 0 ]
