#!/usr/bin/env bash
# Build and sign bristlenose-speech, the Apple speech helper
# (docs/design-apple-first-transcription.md §3 A).
#
# Built like desktop/mcp-helper/ (embedded Info.plist, the app's floor, its own
# build directory, a stamp), but SIGNED LIKE FFMPEG (desktop/scripts/sign-ffmpeg.sh):
# the bundled sidecar launches it, so it carries app-sandbox + inherit and
# nothing else — no network (the model fetch is a system daemon's), no app
# group (an inherit child runs in the app's own container). The opposite of
# mcp-helper, whose launcher is a foreign app.
#
# One identifier for every signer kind, app.bristlenose.speech: an inherit
# child has no container of its own, so the signer-kind trap that splits the
# MCP helper's identifiers (design-mcp-native-proxy.md §6.7) does not arise.
# Ad-hoc ("-") is allowed, unlike mcp-helper: an inherit child of an ad-hoc
# app runs, as ffmpeg does in local builds.
#
# Usage:
#   SIGN_IDENTITY="-" HELPER_VERSION="0.40.0+5150" desktop/speech-helper/build-helper.sh <out-dir>
#
# Environment:
#   SIGN_IDENTITY   required: "-" (ad-hoc), "Apple Development: …",
#                   "Apple Distribution: …" or "Developer ID Application: …".
#   HELPER_VERSION  required: "<release>+<build>", into the embedded Info.plist.
#   HELPERS_OUT     optional: also place a copy there (the app's Contents/Helpers).
#   MIN_MACOS       default: the app's MACOSX_DEPLOYMENT_TARGET from the pbxproj.
#
# Writes <out-dir>/bristlenose-speech (plus a stamp). Exit 0 = built, signed,
# and passed check-speech-helper.sh; anything else = do not ship.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="${1:?usage: build-helper.sh <out-dir>}"
: "${SIGN_IDENTITY:?SIGN_IDENTITY must be the identity the host app is signed with (- for ad-hoc)}"
: "${HELPER_VERSION:?HELPER_VERSION must be <release>+<build>}"
HELPER_ID="app.bristlenose.speech"

case "$SIGN_IDENTITY" in
    -) TIMESTAMP_FLAG="--timestamp=none" ;;
    "Apple Development:"*) TIMESTAMP_FLAG="--timestamp=none" ;;
    "Apple Distribution:"*|"Developer ID Application:"*) TIMESTAMP_FLAG="--timestamp" ;;
    *) echo "error: unrecognised identity kind: $SIGN_IDENTITY" >&2; exit 1 ;;
esac
case "$HELPER_VERSION" in
    *+*) ;;
    *) echo "error: HELPER_VERSION must be <release>+<build> (got '$HELPER_VERSION')" >&2; exit 1 ;;
esac

# The floor, read from the project rather than restated: a helper built for the
# build machine's OS crashes at launch on 15 (libswift_DarwinFoundation1).
if [ -z "${MIN_MACOS:-}" ]; then
    MIN_MACOS="$(grep -m1 -o 'MACOSX_DEPLOYMENT_TARGET = [0-9.]*;' \
        "$ROOT/desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj" | grep -o '[0-9.]*[0-9]')"
fi
[ -n "$MIN_MACOS" ] || { echo "error: could not read MACOSX_DEPLOYMENT_TARGET" >&2; exit 1; }

# Skip the compile and sign when nothing that shapes the binary has moved: the
# source, this script (it writes the Info.plist and entitlements), the
# identity, the version and the floor. The gate below still runs.
STAMP="$(cat "$HERE/main.swift" "$HERE/build-helper.sh" | shasum | cut -c1-16) $SIGN_IDENTITY $HELPER_VERSION $MIN_MACOS"
if [ -x "$OUT/bristlenose-speech" ] && [ "$(cat "$OUT/.stamp" 2>/dev/null)" = "$STAMP" ]; then
    echo "bristlenose-speech up to date ($HELPER_ID)"
else
WORK="$(mktemp -d "${TMPDIR:-/tmp}/bristlenose-speech.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

# A sandboxed bare tool traps at launch without an embedded Info.plist, and its
# CFBundleIdentifier must equal the signing identifier.
cat > "$WORK/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>$HELPER_ID</string>
  <key>CFBundleName</key><string>bristlenose-speech</string>
  <key>CFBundleShortVersionString</key><string>${HELPER_VERSION%%+*}</string>
  <key>CFBundleVersion</key><string>${HELPER_VERSION##*+}</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_MACOS</string>
</dict></plist>
EOF

# ffmpeg's set (desktop/bristlenose-ffmpeg.entitlements), and only it.
cat > "$WORK/helper.entitlements" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>com.apple.security.app-sandbox</key><true/>
  <key>com.apple.security.inherit</key><true/>
</dict></plist>
EOF

# Compiled and signed alone in its own directory: signed beside a loose
# Info.plist, codesign seals that directory as the binary's resources, and the
# signature is then "invalid resource directory" the moment the file is copied.
mkdir -p "$WORK/bin"
xcrun swiftc -O -target "arm64-apple-macos$MIN_MACOS" \
    "$HERE/main.swift" \
    -o "$WORK/bin/bristlenose-speech" \
    -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$WORK/Info.plist"

codesign --force --sign "$SIGN_IDENTITY" --options runtime "$TIMESTAMP_FLAG" \
    --identifier "$HELPER_ID" --entitlements "$WORK/helper.entitlements" "$WORK/bin/bristlenose-speech"

cp "$WORK/bin/bristlenose-speech" "$OUT/bristlenose-speech"
echo "$STAMP" > "$OUT/.stamp"
fi  # end of the compile-and-sign block skipped when the stamp matches

COPIES=("$OUT/bristlenose-speech")
if [ -n "${HELPERS_OUT:-}" ]; then
    mkdir -p "$HELPERS_OUT"
    cp -p "$OUT/bristlenose-speech" "$HELPERS_OUT/bristlenose-speech"
    COPIES+=("$HELPERS_OUT/bristlenose-speech")
fi

MIN_MACOS="$MIN_MACOS" "$ROOT/desktop/scripts/check-speech-helper.sh" "${COPIES[@]}"
echo "built $OUT/bristlenose-speech ($HELPER_ID, $HELPER_VERSION, macOS $MIN_MACOS+)"
