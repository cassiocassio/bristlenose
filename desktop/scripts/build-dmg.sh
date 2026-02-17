#!/usr/bin/env bash
# Build the Bristlenose.app and package it as a .dmg for distribution.
#
# Prerequisites:
#   - Xcode 14+ with command-line tools
#   - The Xcode project exists at desktop/Bristlenose.xcodeproj
#   - Sidecar binaries built (run build-sidecar.sh and fetch-ffmpeg.sh first)
#   - Optional: brew install create-dmg (for pretty .dmg with drag-to-Applications)
#
# Output: desktop/build/Bristlenose.dmg

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$SCRIPT_DIR/.."
BUILD_DIR="$DESKTOP_DIR/build"

mkdir -p "$BUILD_DIR"

echo "==> Building Bristlenose.app..."

# Archive the app
xcodebuild -project "$DESKTOP_DIR/Bristlenose.xcodeproj" \
           -scheme Bristlenose \
           -configuration Release \
           -archivePath "$BUILD_DIR/Bristlenose.xcarchive" \
           archive \
           CODE_SIGN_IDENTITY="-" \
           CODE_SIGNING_ALLOWED=YES

# Export the .app from the archive
# For ad-hoc distribution, we just grab the .app directly from the archive
APP_PATH="$BUILD_DIR/Bristlenose.xcarchive/Products/Applications/Bristlenose.app"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: Bristlenose.app not found in archive"
    exit 1
fi

echo "==> Built: $APP_PATH"

# Create .dmg
DMG_PATH="$BUILD_DIR/Bristlenose.dmg"

if command -v create-dmg >/dev/null 2>&1; then
    echo "==> Creating .dmg with create-dmg..."
    # Remove old dmg if it exists (create-dmg won't overwrite)
    rm -f "$DMG_PATH"

    create-dmg \
        --volname "Bristlenose" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "Bristlenose.app" 150 190 \
        --app-drop-link 450 190 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$APP_PATH"
else
    echo "==> Creating .dmg with hdiutil (install create-dmg for a prettier result)..."
    DMG_STAGING="$BUILD_DIR/dmg-staging"
    rm -rf "$DMG_STAGING"
    mkdir -p "$DMG_STAGING"

    cp -R "$APP_PATH" "$DMG_STAGING/"
    ln -s /Applications "$DMG_STAGING/Applications"

    rm -f "$DMG_PATH"
    hdiutil create -volname "Bristlenose" \
                   -srcfolder "$DMG_STAGING" \
                   -ov -format UDZO \
                   "$DMG_PATH"

    rm -rf "$DMG_STAGING"
fi

echo "==> Done: $DMG_PATH"
ls -lh "$DMG_PATH"
