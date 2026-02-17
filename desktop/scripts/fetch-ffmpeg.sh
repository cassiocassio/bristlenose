#!/usr/bin/env bash
# Download a static FFmpeg binary for macOS arm64 and place it in the
# app's Resources directory for bundling.
#
# Output: desktop/Bristlenose/Resources/ffmpeg

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$DESKTOP_DIR/Bristlenose/Resources"

mkdir -p "$RESOURCES_DIR"

FFMPEG_PATH="$RESOURCES_DIR/ffmpeg"

if [ -x "$FFMPEG_PATH" ]; then
    echo "==> FFmpeg already present: $FFMPEG_PATH"
    "$FFMPEG_PATH" -version | head -1
    exit 0
fi

echo "==> Downloading static FFmpeg for macOS arm64..."

# Option 1: Martin Riedl's builds (macOS arm64 static)
# Uncomment and set the URL when a specific version is chosen:
# FFMPEG_URL="https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"
# curl -L -o /tmp/ffmpeg.zip "$FFMPEG_URL"
# unzip -o /tmp/ffmpeg.zip -d "$RESOURCES_DIR"
# rm /tmp/ffmpeg.zip

# Option 2: Copy from Homebrew (not truly static, but works on same-version macOS)
if command -v ffmpeg >/dev/null 2>&1; then
    BREW_FFMPEG="$(which ffmpeg)"
    echo "==> Copying ffmpeg from: $BREW_FFMPEG"
    cp "$BREW_FFMPEG" "$FFMPEG_PATH"
    chmod +x "$FFMPEG_PATH"
    echo "==> FFmpeg copied: $FFMPEG_PATH"
    "$FFMPEG_PATH" -version | head -1
    exit 0
fi

echo "Error: No FFmpeg found. Install via 'brew install ffmpeg' or set FFMPEG_URL above."
exit 1
