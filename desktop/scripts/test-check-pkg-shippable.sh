#!/usr/bin/env bash
# Negative fixtures for check-pkg-shippable.sh.
#
# Every assertion is shown to FAIL on its own violation, because a gate that
# can't fail is worse than no gate — it converts "unchecked" into "checked and
# fine", which is the more expensive state to be in.
#
# This is not paranoia. The gate's FIRST run against a real .pkg reported
# "223 of 227 Mach-Os missing app-sandbox" — a false alarm, because the check
# matched every Mach-O rather than only executables (207 of those are Python .so
# bundles, which carry no entitlements by design). It looked exactly like a
# blocker. A gate is only worth what its failure mode is worth, so each one gets
# driven red here before it is trusted green.
#
# Method: build a tiny synthetic .app, sign it ad-hoc, wrap it with pkgbuild,
# then mutate ONE thing per case and assert the gate rejects it. A synthetic pkg
# is ~50 KB and builds in under a second, so this runs in the inner loop; the
# real 644 MB artefact is exercised by the positive path in build-all.sh.
#
# Deliberately NOT covered here (needs a real signed artefact, so it is proven
# by the green run against the actual .pkg rather than synthesised):
#   - the §2.5.2 PYZ scan (needs a real PyInstaller bundle)
#   - Apple's --validate-app (needs a credential and a network round trip)
#   - designated-requirement / Team ID (ad-hoc signing has no team)
#
# Usage: test-check-pkg-shippable.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-pkg-shippable.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }

PASS=0; FAIL=0; SKIP=0
WORK=$(mktemp -d "${TMPDIR:-/tmp}/bn-gate-test.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

pass() { printf '  \033[32m✓\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; FAIL=$((FAIL+1)); }
skip() { printf '  \033[2m—\033[0m %s\n' "$*"; SKIP=$((SKIP+1)); }

# build_app <dir> — a minimal, structurally-valid .app the gate can chew on.
build_app() {
    local app="$1/Bristlenose.app"
    mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources/bristlenose-sidecar"
    # A real Mach-O executable, so `file` classifies it as one.
    printf 'int main(void){return 0;}' > "$WORK/m.c"
    cc -o "$app/Contents/MacOS/Bristlenose" "$WORK/m.c" 2>/dev/null
    cp "$app/Contents/MacOS/Bristlenose" "$app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar"
    cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>app.bristlenose</string>
  <key>CFBundleExecutable</key><string>Bristlenose</string>
  <key>CFBundleShortVersionString</key><string>9.9.9</string>
  <key>CFBundleVersion</key><string>99999</string>
  <key>ITSAppUsesNonExemptEncryption</key><false/>
</dict></plist>
PLIST
    for m in Contents/Resources Contents/Resources/bristlenose-sidecar; do
        cat > "$app/$m/PrivacyInfo.xcprivacy" <<'P'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>NSPrivacyTracking</key><false/></dict></plist>
P
    done
    echo "$app"
}

sign_app() {   # sign_app <app> <entitlements-or-empty>
    local app="$1" ents="${2:-}"
    for b in "$app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar" \
             "$app/Contents/MacOS/Bristlenose"; do
        if [ -n "$ents" ]; then
            codesign --force --options=runtime --entitlements "$ents" --sign - "$b" 2>/dev/null
        else
            codesign --force --options=runtime --sign - "$b" 2>/dev/null
        fi
    done
    codesign --force --sign - "$app" 2>/dev/null
}

make_pkg() {   # make_pkg <app> <out.pkg>
    pkgbuild --component "$1" --install-location /Applications "$2" >/dev/null 2>&1
}

ENTS="$WORK/ents.plist"
cat > "$ENTS" <<'E'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.app-sandbox</key><true/></dict></plist>
E

# expect_reject <label> <pattern> <pkg>
expect_reject() {
    local label="$1" pattern="$2" pkg="$3" out
    out=$("$GATE" "$pkg" 2>&1)
    if [ $? -eq 0 ]; then
        fail "$label — gate PASSED a broken pkg (it cannot fail on this)"
    elif grep -qi "$pattern" <<<"$out"; then
        pass "$label"
    else
        fail "$label — rejected, but not for the expected reason"
        sed 's/^/        /' <<<"$out" | grep -i '✗' >&2
    fi
}

printf '\nNEGATIVE FIXTURES — check-pkg-shippable.sh\n\n'

command -v cc >/dev/null 2>&1 || { skip "no compiler — cannot synthesise Mach-Os"; printf '\n  %d passed · %d failed · %d skipped\n\n' "$PASS" "$FAIL" "$SKIP"; exit 0; }

# --- 1. privacy manifest deleted -------------------------------------------
D=$WORK/c1; mkdir -p "$D"; A=$(build_app "$D"); sign_app "$A" "$ENTS"
rm -f "$A/Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy"
make_pkg "$A" "$D/t.pkg" && expect_reject "privacy manifest absent" "privacy manifest" "$D/t.pkg"

# --- 2. export-compliance key removed ---------------------------------------
# The silent-failure case: without this, builds process fine and then sit in
# ASC as "Missing Compliance" forever, reaching no testers, with nothing red.
D=$WORK/c2; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c 'Delete :ITSAppUsesNonExemptEncryption' "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
make_pkg "$A" "$D/t.pkg" && expect_reject "export compliance absent" "export compliance" "$D/t.pkg"

# --- 3. version disagrees with the working tree ------------------------------
D=$WORK/c3; mkdir -p "$D"; A=$(build_app "$D"); sign_app "$A" "$ENTS"
make_pkg "$A" "$D/t.pkg" && expect_reject "stale artefact (version mismatch)" "version\|build number" "$D/t.pkg"

# --- 4. wrong bundle identifier ---------------------------------------------
D=$WORK/c4; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.evil.other' "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
make_pkg "$A" "$D/t.pkg" && expect_reject "wrong bundle identifier" "bundle identifier" "$D/t.pkg"

# --- 5. nested executable missing app-sandbox — ASC rejection #2 -------------
# The regression this gate exists for. Sign the sidecar WITHOUT entitlements,
# the host WITH: codesign --verify still passes, only ASC would object.
D=$WORK/c5; mkdir -p "$D"; A=$(build_app "$D")
codesign --force --options=runtime --sign - "$A/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar" 2>/dev/null
codesign --force --options=runtime --entitlements "$ENTS" --sign - "$A/Contents/MacOS/Bristlenose" 2>/dev/null
codesign --force --sign - "$A" 2>/dev/null
make_pkg "$A" "$D/t.pkg" && expect_reject "nested executable unsandboxed" "nested app-sandbox" "$D/t.pkg"

# --- 6. hardened runtime absent — ITMS-90287 ---------------------------------
D=$WORK/c6; mkdir -p "$D"; A=$(build_app "$D")
codesign --force --entitlements "$ENTS" --sign - "$A/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar" 2>/dev/null
codesign --force --entitlements "$ENTS" --sign - "$A/Contents/MacOS/Bristlenose" 2>/dev/null
codesign --force --sign - "$A" 2>/dev/null
make_pkg "$A" "$D/t.pkg" && expect_reject "hardened runtime absent" "hardened runtime" "$D/t.pkg"

# --- 7. usage: not a pkg ------------------------------------------------------
if "$GATE" "$WORK/nope.pkg" >/dev/null 2>&1; then
    fail "missing file — gate accepted a nonexistent path"
else
    [ $? -eq 2 ] && pass "missing file → exit 2 (usage)" || pass "missing file rejected"
fi

printf '\n  %d passed · %d failed · %d skipped\n\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
