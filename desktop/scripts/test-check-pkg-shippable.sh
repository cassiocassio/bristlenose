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
# then mutate ONE thing per case and assert the gate rejects it FOR THAT ROW.
#
# Every fixture is rejected whatever the case — it has an unsigned installer, no
# provisioning profile, no speech helper — so the exit code proves nothing, and
# the row LABEL proves nothing either, because the ✓ line prints it too. Until
# 22 Oct 2026 cases 1-6 matched the label and could not fail: turning the export
# compliance row's die into an ok left this harness at 9 passed. So a negative
# case matches its row's ✗ line, and an intact fixture must print that row's ✓
# line — the second half catches a row that always fails, which the first half
# would read as a pass.
#
# A synthetic pkg is ~50 KB and builds in under a second, so this runs in the
# inner loop; the real 644 MB artefact is exercised by the positive path in
# build-all.sh.
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
# Synthetic fixtures must never reach Apple: the gate runs altool --validate-app
# with the machine's App Store Connect key unless the identity is ad-hoc.
export SIGN_IDENTITY=-
# And the uploader's skip too: the gate sources .ship-local.conf after reading
# the environment, so a conf that ever set SIGN_IDENTITY would undo the line above.
export BN_SKIP_ASC_VALIDATE=1

# The fixture carries the working tree's version, read as the gate reads it, so
# the intact fixture passes the version row and case 3 is a real mismatch.
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TREE_VER=$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$ROOT/bristlenose/__init__.py" 2>/dev/null | head -1)
TREE_BUILD=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([0-9]*\);.*/\1/p' \
    "$ROOT/desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj" 2>/dev/null | head -1)
[ -n "$TREE_VER" ] && [ -n "$TREE_BUILD" ] \
    || { echo "cannot read the working tree's version/build under $ROOT" >&2; exit 2; }

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
    cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>app.bristlenose</string>
  <key>CFBundleExecutable</key><string>Bristlenose</string>
  <key>CFBundleShortVersionString</key><string>$TREE_VER</string>
  <key>CFBundleVersion</key><string>$TREE_BUILD</string>
  <key>ITSAppUsesNonExemptEncryption</key><false/>
  <key>MicrosoftOAuthClientID</key><string>00000000-0000-0000-0000-000000000000</string>
  <key>MicrosoftOAuthRedirectURI</key><string>msauth.app.bristlenose://auth</string>
  <key>GoogleOAuthClientID</key><string>0-test.apps.googleusercontent.com</string>
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

# Signing the bundle re-signs its main executable, so the bundle is signed with
# the host's options too. A bare `codesign --sign - "$app"` here stripped the
# host's runtime flag and entitlements, until 22 Oct 2026: every fixture then
# failed the host sandbox, hardened runtime and nested sandbox rows, and cases 5
# and 6 passed on the host whatever their own mutation did.
sign_app() {   # sign_app <app> <entitlements-or-empty>
    local app="$1" ents="${2:-}" b
    for b in "$app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar" "$app"; do
        if [ -n "$ents" ]; then
            codesign --force --options=runtime --entitlements "$ents" --sign - "$b" 2>/dev/null
        else
            codesign --force --options=runtime --sign - "$b" 2>/dev/null
        fi
    done
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

# expect_reject <label> <pattern> <pkg> — <pattern> must match only the row's ✗
# line ("✗.*<row label>", or its detail text), never the bare label.
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

# reject_case <label> <pattern> <dir> — package <dir>'s app and expect_reject it.
# A pkgbuild failure is a failed case, not a skipped one: `make_pkg && expect`
# would run no assertion and count nothing.
reject_case() {
    if make_pkg "$3/Bristlenose.app" "$3/t.pkg"; then
        expect_reject "$1" "$2" "$3/t.pkg"
    else
        fail "$1 — pkgbuild failed, case not run"
    fi
}

# expect_row_passes <label> <pattern> — <pattern> matches the row's ✓ line in
# the intact fixture's output. Asserts the ✓, not the absence of the ✗: a gate
# that never ran prints neither, and an absence check would pass it.
expect_row_passes() {
    if grep -qi "$2" <<<"$INTACT_OUT"; then
        pass "$1"
    else
        fail "$1 — row did not pass the intact fixture"
        sed 's/^/        /' <<<"$INTACT_OUT" | grep -i '✗' >&2
    fi
}

printf '\nNEGATIVE FIXTURES — check-pkg-shippable.sh\n\n'

command -v cc >/dev/null 2>&1 || { skip "no compiler — cannot synthesise Mach-Os"; printf '\n  %d passed · %d failed · %d skipped\n\n' "$PASS" "$FAIL" "$SKIP"; exit 0; }

# --- 1. privacy manifest deleted -------------------------------------------
D=$WORK/c1; mkdir -p "$D"; A=$(build_app "$D"); sign_app "$A" "$ENTS"
rm -f "$A/Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy"
reject_case "privacy manifest absent" "✗.*privacy manifests" "$D"

# --- 2. export-compliance key removed ---------------------------------------
# The silent-failure case: without this, builds process fine and then sit in
# ASC as "Missing Compliance" forever, reaching no testers, with nothing red.
D=$WORK/c2; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c 'Delete :ITSAppUsesNonExemptEncryption' "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
reject_case "export compliance absent" "✗.*export compliance" "$D"

# --- 3. version disagrees with the working tree ------------------------------
# Two rows, two cases: the gate reports them separately, so one matching pattern
# for both would let either row go dead behind the other.
D=$WORK/c3; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 9.9.9' "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
reject_case "stale artefact (marketing version mismatch)" "✗.*marketing version" "$D"

D=$WORK/c3b; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $((TREE_BUILD + 1))" "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
reject_case "stale artefact (build number mismatch)" "✗.*build number.*pkg is" "$D"

# --- 4. wrong bundle identifier ---------------------------------------------
D=$WORK/c4; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.evil.other' "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
reject_case "wrong bundle identifier" "✗.*bundle identifier" "$D"

# --- 5. nested executable missing app-sandbox — ASC rejection #2 -------------
# The regression this gate exists for. Sign the sidecar WITHOUT entitlements,
# the host WITH: codesign --verify still passes, only ASC would object.
D=$WORK/c5; mkdir -p "$D"; A=$(build_app "$D")
codesign --force --options=runtime --sign - "$A/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar" 2>/dev/null
codesign --force --options=runtime --entitlements "$ENTS" --sign - "$A" 2>/dev/null
reject_case "nested executable unsandboxed" "✗.*nested app-sandbox" "$D"

# --- 6. hardened runtime absent — ITMS-90287 ---------------------------------
D=$WORK/c6; mkdir -p "$D"; A=$(build_app "$D")
codesign --force --entitlements "$ENTS" --sign - "$A/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar" 2>/dev/null
codesign --force --entitlements "$ENTS" --sign - "$A" 2>/dev/null
reject_case "hardened runtime absent" "✗.*hardened runtime" "$D"

# --- 7. cloud sign-in ID missing ---------------------------------------------
# The quiet one: an app without the baked IDs offers Teams and Meet and cannot
# start either sign-in, and on a Mac whose defaults hold the IDs it looks fine.
D=$WORK/c7; mkdir -p "$D"; A=$(build_app "$D")
/usr/libexec/PlistBuddy -c 'Delete :GoogleOAuthClientID' "$A/Contents/Info.plist" >/dev/null 2>&1
sign_app "$A" "$ENTS"
# Glyph AND detail: the detail alone also matches a die turned into an ok that
# keeps its text, which is how this case survived its own mutation.
reject_case "cloud sign-in ID absent" "✗.*missing or placeholder: GoogleOAuthClientID" "$D"

# --- 8. host may print — printing is post-v1 ---------------------------------
# File ▸ Print is not in the menus for v1 (owner, 23 Oct 2026), so an artefact
# carrying com.apple.security.print is a capability with no affordance. The
# entitlement comes from a build setting, so an Xcode capability toggle brings it
# back with no diff in any .entitlements file; this row is what notices.
ENTS_PRINT="$WORK/ents-print.plist"
cat > "$ENTS_PRINT" <<'E'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.app-sandbox</key><true/><key>com.apple.security.print</key><true/></dict></plist>
E
D=$WORK/c8; mkdir -p "$D"; A=$(build_app "$D"); sign_app "$A" "$ENTS_PRINT"
reject_case "host may print (post-v1)" "✗.*host print.*PRESENT" "$D"

# --- positive controls: the intact fixture passes every row above ------------
# Without these, a row that always fails passes its negative case. The output is
# captured once and read with a herestring, not a pipe: under pipefail `grep -q`
# SIGPIPEs the gate, the pipeline reads false, and a pass is reported unchecked.
D=$WORK/c0; mkdir -p "$D"; A=$(build_app "$D"); sign_app "$A" "$ENTS"
if make_pkg "$A" "$D/t.pkg"; then
    INTACT_OUT=$("$GATE" "$D/t.pkg" 2>&1)
else
    INTACT_OUT=""; fail "intact fixture — pkgbuild failed, positive controls cannot pass"
fi
expect_row_passes "privacy manifests present → row passes" "✓.*privacy manifests"
expect_row_passes "export compliance present → row passes" "✓.*export compliance"
expect_row_passes "version + build agree with tree → row passes" "✓.*version.*agrees with tree"
expect_row_passes "bundle identifier right → row passes" "✓.*bundle identifier"
expect_row_passes "nested executables sandboxed → row passes" "✓.*nested app-sandbox"
expect_row_passes "hardened runtime on → row passes" "✓.*hardened runtime"
expect_row_passes "cloud sign-in IDs present → row passes" "✓.*Teams + Meet client IDs baked"
expect_row_passes "no print entitlement → row passes" "✓.*host print.*absent"

# --- 9. usage: not a pkg ------------------------------------------------------
if "$GATE" "$WORK/nope.pkg" >/dev/null 2>&1; then
    fail "missing file — gate accepted a nonexistent path"
else
    [ $? -eq 2 ] && pass "missing file → exit 2 (usage)" || pass "missing file rejected"
fi

printf '\n  %d passed · %d failed · %d skipped\n\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
