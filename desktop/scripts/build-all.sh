#!/usr/bin/env bash
# End-to-end alpha build for Bristlenose.app (Track C C2).
#
# Ported from desktop/v0.1-archive/scripts/build-all.sh — shape only,
# the architecture is now: one signed, notarised .app archive ready for
# C3 / Track B to export as a .pkg and upload to TestFlight.
#
# Chain (bailing on any non-zero exit):
#   1. Pre-flight — identities, profiles, notarytool credentials.
#   2. Parallel:   fetch-ffmpeg.sh  &&  build-sidecar.sh
#   3. sign-ffmpeg.sh (bundled static FFmpeg + ffprobe)
#   4. sign-sidecar.sh (PyInstaller bundle; parallel inner loop)
#   5. xcodebuild archive  [added in commit 3, once pbxproj flips manual]
#   6. xcodebuild -exportArchive  [ditto]
#   7. check-release-binary.sh on the exported .app  [commit 4]
#   8. Provisioning profile sanity check  [commit 4]
#   9. Notarisation + stapling  [commit 4]
#  10. Final verification battery  [commit 4]
#
# Usage:
#   desktop/scripts/build-all.sh
#
# Environment (passed through to child scripts):
#   SIGN_IDENTITY  codesign identity; default "-" = ad-hoc.
#                  Alpha: "Apple Distribution: Martin Storey (Z56GZVA2QB)"
#   SIGN_JOBS      parallelism for sign-sidecar.sh; default hw.ncpu.
#   ALLOW_RESIGN   pass-through for sign-sidecar.sh re-sign override.
#   NOTARY_PROFILE notarytool --keychain-profile; default "bristlenose-notary"
#                  (used by commit 4 onwards).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"

SIGN_IDENTITY="${SIGN_IDENTITY:--}"
NOTARY_PROFILE="${NOTARY_PROFILE:-bristlenose-notary}"
TEAM_ID="Z56GZVA2QB"
PROFILE_NAME="Bristlenose Mac App Store"
PROFILE_PATH="$HOME/Library/MobileDevice/Provisioning Profiles/Bristlenose_Mac_App_Store.provisionprofile"

echo "=============================================="
echo " Bristlenose.app — end-to-end build"
echo "=============================================="
echo "identity: $SIGN_IDENTITY"
echo "notary:   $NOTARY_PROFILE"
echo "team:     $TEAM_ID"
echo

# ------------------------------------------------------------
# 1. Pre-flight
# ------------------------------------------------------------
# Cryptic errors otherwise. Ad-hoc identity skips the Apple-signed
# checks because those only matter for a shipping archive.

echo "==> 1. Pre-flight..."

# 1a. Source-level logging hygiene — catches credential-shaped interpolations
# in Swift logger calls without a privacy marker. Complements the runtime
# redactor in ServeManager.handleLine (Python-side leakage defence). Cheap;
# runs in <1s; fails fast before expensive archive work.
echo "==> 1a. check-logging-hygiene.sh..."
"$SCRIPT_DIR/check-logging-hygiene.sh" "$ROOT"

if [ "$SIGN_IDENTITY" != "-" ]; then
    # Capture output before grepping (SIGPIPE + pipefail trap —
    # see sign-sidecar.sh Timestamp= assertion for the full story).
    _identities=$(security find-identity -v -p codesigning)
    if ! grep -qF "$SIGN_IDENTITY" <<< "$_identities"; then
        echo "error: signing identity not found in keychain:" >&2
        echo "  $SIGN_IDENTITY" >&2
        echo "Install the Apple Distribution cert (see" >&2
        echo "docs/design-desktop-python-runtime.md §Signing strategy)." >&2
        exit 1
    fi

    if [ ! -f "$PROFILE_PATH" ]; then
        echo "error: provisioning profile not found at:" >&2
        echo "  $PROFILE_PATH" >&2
        echo "Install the '$PROFILE_NAME' profile from the Apple" >&2
        echo "Developer portal." >&2
        exit 1
    fi

    # Notarytool keychain profile check is gated on commit 4 work.
    # Announce the expectation for now; sign-only runs don't need it.
    if ! xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" \
        >/dev/null 2>&1; then
        echo "note: notarytool keychain profile '$NOTARY_PROFILE' not set up." >&2
        echo "      required for notarisation step (commit 4)." >&2
        echo "      set up: xcrun notarytool store-credentials \"$NOTARY_PROFILE\" ..." >&2
    fi
fi

echo "    OK"

# ------------------------------------------------------------
# 2. Parallel: fetch ffmpeg + build sidecar (no dependency)
# ------------------------------------------------------------
# PyInstaller build is ~100 s CPU; FFmpeg fetch is ~10-30 s network.
# Running them concurrently trims the longer of (T_pyi, T_ff) off the
# wall clock.

echo
echo "==> 2. Parallel: fetch-ffmpeg + build-sidecar..."
rm -f "$DESKTOP_DIR/build/fetch-ffmpeg.log" "$DESKTOP_DIR/build/build-sidecar.log"
mkdir -p "$DESKTOP_DIR/build"

"$SCRIPT_DIR/fetch-ffmpeg.sh" > "$DESKTOP_DIR/build/fetch-ffmpeg.log" 2>&1 &
FETCH_PID=$!
"$SCRIPT_DIR/build-sidecar.sh" > "$DESKTOP_DIR/build/build-sidecar.log" 2>&1 &
BUILD_PID=$!

FETCH_FAILED=0
BUILD_FAILED=0
if ! wait "$FETCH_PID"; then FETCH_FAILED=1; fi
if ! wait "$BUILD_PID"; then BUILD_FAILED=1; fi

if [ "$FETCH_FAILED" = "1" ]; then
    echo "error: fetch-ffmpeg failed. tail of log:" >&2
    tail -30 "$DESKTOP_DIR/build/fetch-ffmpeg.log" >&2
fi
if [ "$BUILD_FAILED" = "1" ]; then
    echo "error: build-sidecar failed. tail of log:" >&2
    tail -30 "$DESKTOP_DIR/build/build-sidecar.log" >&2
fi
if [ "$FETCH_FAILED" = "1" ] || [ "$BUILD_FAILED" = "1" ]; then
    exit 1
fi

echo "    OK (fetch-ffmpeg + build-sidecar)"

# ------------------------------------------------------------
# 3. Sign bundled FFmpeg + ffprobe
# ------------------------------------------------------------
# Child scripts inherit SIGN_IDENTITY (+ optional SIGN_JOBS,
# ALLOW_RESIGN) from the parent environment.

export SIGN_IDENTITY

echo
echo "==> 3. Signing FFmpeg + ffprobe..."
"$SCRIPT_DIR/sign-ffmpeg.sh"

# ------------------------------------------------------------
# 4. Sign PyInstaller sidecar bundle (parallel inner loop)
# ------------------------------------------------------------

echo
echo "==> 4. Signing sidecar bundle..."
"$SCRIPT_DIR/sign-sidecar.sh"

# Ad-hoc runs stop here — xcodebuild with the manual-signing Release
# config requires a real Apple Distribution identity.
if [ "$SIGN_IDENTITY" = "-" ]; then
    echo
    echo "=============================================="
    echo " Ad-hoc signing stage complete."
    echo "=============================================="
    echo "Skipping archive + export (Release config requires a real"
    echo "Apple Distribution identity). Set SIGN_IDENTITY to exercise"
    echo "the full pipeline."
    exit 0
fi

# ------------------------------------------------------------
# 5. xcodebuild archive
# ------------------------------------------------------------
# The Release config (pbxproj) is manual-signing against the Apple
# Distribution cert + "Bristlenose Mac App Store" profile. The Copy
# Sidecar Resources build phase picks up the signed tree from
# desktop/Bristlenose/Resources/bristlenose-sidecar/.

ARCHIVE_PATH="$DESKTOP_DIR/build/Bristlenose.xcarchive"
EXPORT_DIR="$DESKTOP_DIR/build/export"
PROJECT_DIR="$DESKTOP_DIR/Bristlenose"
EXPORT_OPTIONS="$PROJECT_DIR/ExportOptions.plist"
ARCHIVE_LOG="$DESKTOP_DIR/build/xcodebuild-archive.log"
EXPORT_LOG="$DESKTOP_DIR/build/xcodebuild-export.log"

rm -rf "$ARCHIVE_PATH" "$EXPORT_DIR"

echo
echo "==> 5. xcodebuild archive..."
if ! xcodebuild \
    -project "$PROJECT_DIR/Bristlenose.xcodeproj" \
    -scheme Bristlenose \
    -configuration Release \
    -destination "generic/platform=macOS" \
    -archivePath "$ARCHIVE_PATH" \
    archive \
    > "$ARCHIVE_LOG" 2>&1; then
    echo "error: xcodebuild archive failed. tail:" >&2
    tail -50 "$ARCHIVE_LOG" >&2
    exit 1
fi
echo "    OK — $ARCHIVE_PATH"

# ------------------------------------------------------------
# 6. xcodebuild -exportArchive
# ------------------------------------------------------------

echo
echo "==> 6. xcodebuild -exportArchive..."
if ! xcodebuild \
    -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_DIR" \
    -exportOptionsPlist "$EXPORT_OPTIONS" \
    > "$EXPORT_LOG" 2>&1; then
    echo "error: xcodebuild -exportArchive failed. tail:" >&2
    tail -50 "$EXPORT_LOG" >&2
    exit 1
fi

EXPORTED_APP=$(find "$EXPORT_DIR" -maxdepth 2 -name "*.app" -type d | head -1)
if [ -z "$EXPORTED_APP" ]; then
    echo "error: no .app found under $EXPORT_DIR" >&2
    exit 1
fi
echo "    OK — $EXPORTED_APP"

# ------------------------------------------------------------
# 7. check-release-binary.sh post-export
# ------------------------------------------------------------
# Scans every Mach-O in the exported .app for:
#   - BRISTLENOSE_DEV_* string literals (dev escape-hatch leak)
#   - get-task-allow entitlement (Debug-only; App-Store-rejected)
# Skips Contents/Resources/bristlenose-sidecar/* (Python strings
# expected; no Swift #if DEBUG invariant applies).

echo
echo "==> 7. check-release-binary.sh (strings + entitlements)..."
"$SCRIPT_DIR/check-release-binary.sh" "$EXPORTED_APP"

# ------------------------------------------------------------
# 8. Provisioning profile sanity check
# ------------------------------------------------------------
# Assert the embedded profile matches our bundle ID + team ID. Xcode
# sometimes embeds a stale or wrong profile when manual signing is
# misconfigured — easier to catch here than at App Store upload time.

echo
echo "==> 8. Embedded provisioning profile sanity check..."
EMBEDDED_PROFILE="$EXPORTED_APP/Contents/embedded.provisionprofile"
if [ ! -f "$EMBEDDED_PROFILE" ]; then
    echo "error: embedded.provisionprofile missing from exported app." >&2
    echo "check ExportOptions.plist and pbxproj signing settings." >&2
    exit 1
fi

# security cms -D decodes the PKCS#7 wrapper into an XML plist.
# PlistBuddy needs a real file (can't read stdin), so stage through
# desktop/build/.
PROFILE_DECODED="$DESKTOP_DIR/build/embedded-profile.plist"
security cms -D -i "$EMBEDDED_PROFILE" -o "$PROFILE_DECODED" 2>/dev/null

# The Mac App Store profile declares the entitlements using the
# com.apple.* reverse-DNS keys (NOT the iOS-style short keys).
PROFILE_APP_ID=$(/usr/libexec/PlistBuddy \
    -c "Print :Entitlements:com.apple.application-identifier" \
    "$PROFILE_DECODED")
PROFILE_TEAM_ID=$(/usr/libexec/PlistBuddy \
    -c "Print :Entitlements:com.apple.developer.team-identifier" \
    "$PROFILE_DECODED")

# application-identifier = "<TEAMID>.<bundle>".
EXPECTED_APP_ID="${TEAM_ID}.app.bristlenose"
if [ "$PROFILE_APP_ID" != "$EXPECTED_APP_ID" ]; then
    echo "error: embedded profile application-identifier mismatch." >&2
    echo "  expected: $EXPECTED_APP_ID" >&2
    echo "  found:    $PROFILE_APP_ID" >&2
    exit 1
fi
if [ "$PROFILE_TEAM_ID" != "$TEAM_ID" ]; then
    echo "error: embedded profile team ID mismatch." >&2
    echo "  expected: $TEAM_ID" >&2
    echo "  found:    $PROFILE_TEAM_ID" >&2
    exit 1
fi
echo "    OK — $PROFILE_APP_ID / $PROFILE_TEAM_ID"

# ------------------------------------------------------------
# 9. Notarisation + stapling
# ------------------------------------------------------------
# `ditto` is mandatory for zipping a .app for notarisation — plain
# `zip` mangles extended attributes and symlinks, producing a zip
# that notarytool rejects. Staple the .app (not the zip).

echo
echo "==> 9. Notarisation..."
NOTARY_ZIP="$DESKTOP_DIR/build/$(basename "$EXPORTED_APP").zip"
rm -f "$NOTARY_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$EXPORTED_APP" "$NOTARY_ZIP"
echo "    zip: $NOTARY_ZIP"

echo "    submitting to Apple notarisation service (this can take"
echo "    1–15 minutes; --wait blocks until Apple's response)..."
SUBMIT_LOG="$DESKTOP_DIR/build/notarytool-submit.log"
if ! xcrun notarytool submit "$NOTARY_ZIP" \
        --keychain-profile "$NOTARY_PROFILE" \
        --wait \
        --output-format plist \
        > "$SUBMIT_LOG" 2>&1; then
    echo "error: notarytool submit failed. tail:" >&2
    tail -50 "$SUBMIT_LOG" >&2
    exit 1
fi

# Extract the submission UUID from the plist-formatted output.
# `notarytool submit --output-format plist` writes a top-level dict
# with :id set to the UUID.
SUBMISSION_ID=$(
    /usr/libexec/PlistBuddy -c "Print :id" "$SUBMIT_LOG" 2>/dev/null || true
)
if [ -z "$SUBMISSION_ID" ]; then
    echo "error: could not extract submission UUID from notarytool output." >&2
    cat "$SUBMIT_LOG" >&2
    exit 1
fi

echo "    submission UUID: $SUBMISSION_ID"

# Don't trust `notarytool history` — it can show a cached prior run.
# Explicitly fetch this submission's log and assert Accepted.
LOG_JSON="$DESKTOP_DIR/build/notarytool-log.json"
xcrun notarytool log "$SUBMISSION_ID" \
    --keychain-profile "$NOTARY_PROFILE" \
    "$LOG_JSON"

STATUS=$(/usr/bin/python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' \
    "$LOG_JSON")

if [ "$STATUS" != "Accepted" ]; then
    echo "error: notarisation status '$STATUS' (expected Accepted)." >&2
    echo "log: $LOG_JSON" >&2
    /usr/bin/python3 -c \
        'import json,sys; d=json.load(open(sys.argv[1])); [print(i) for i in d.get("issues",[])[:10]]' \
        "$LOG_JSON" >&2
    exit 1
fi
echo "    status: Accepted"

echo "==> Stapling..."
xcrun stapler staple "$EXPORTED_APP"

# ------------------------------------------------------------
# 10. Final verification battery
# ------------------------------------------------------------

echo
echo "==> 10. Final verification..."

echo "    [a] stapler validate"
xcrun stapler validate "$EXPORTED_APP"

echo "    [b] spctl (Gatekeeper assessment)"
SPCTL_OUT=$(spctl -a -t exec -vv "$EXPORTED_APP" 2>&1)
echo "$SPCTL_OUT" | sed 's/^/        /'
if ! grep -q "accepted" <<< "$SPCTL_OUT"; then
    echo "error: spctl did not accept the app." >&2
    exit 1
fi

echo "    [c] codesign --verify --deep --strict"
codesign --verify --deep --strict --verbose=2 "$EXPORTED_APP"

echo "    [d] outer binary entitlements (must not contain get-task-allow)"
OUTER_BIN="$EXPORTED_APP/Contents/MacOS/Bristlenose"
OUTER_ENTS=$(codesign -d --entitlements :- "$OUTER_BIN" 2>/dev/null || true)
# Xcode may record the key with <false/>; only flag <true/>.
if grep -A1 "get-task-allow" <<< "$OUTER_ENTS" | grep -q "<true/>"; then
    echo "error: outer binary has get-task-allow=TRUE" >&2
    echo "$OUTER_ENTS" | sed 's/^/    /' >&2
    exit 1
fi

echo "    [e] designated requirement (must include Team ID)"
REQ=$(codesign -d --requirements - "$OUTER_BIN" 2>&1 || true)
if ! grep -q "$TEAM_ID" <<< "$REQ"; then
    echo "error: designated requirement does not reference $TEAM_ID" >&2
    echo "$REQ" | sed 's/^/    /' >&2
    exit 1
fi

SIGN_MANIFEST="$DESKTOP_DIR/build/sign-manifest.json"
echo
echo "=============================================="
echo " DONE — Bristlenose.app notarised and stapled"
echo "=============================================="
echo "  app:           $EXPORTED_APP"
echo "  archive:       $ARCHIVE_PATH"
echo "  sign manifest: $SIGN_MANIFEST"
echo "  notary log:    $LOG_JSON"
echo
echo "Ready for C3 / Track B: .pkg export + TestFlight upload."
