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
# 7-10. Post-export gates, notarisation, final verification.
# Added in commit 4.
# ------------------------------------------------------------

echo
echo "=============================================="
echo " Archive + export complete."
echo "=============================================="
echo "Exported: $EXPORTED_APP"
echo "Next: notarisation + verification (commit 4)."
