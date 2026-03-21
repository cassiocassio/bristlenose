#!/usr/bin/env bash
# Download static FFmpeg and ffprobe binaries for macOS arm64 and place
# them in the app's Resources directory for bundling.
#
# Output: desktop/Bristlenose/Resources/ffmpeg
#         desktop/Bristlenose/Resources/ffprobe

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$DESKTOP_DIR/Bristlenose/Resources"

mkdir -p "$RESOURCES_DIR"

FFMPEG_PATH="$RESOURCES_DIR/ffmpeg"
FFPROBE_PATH="$RESOURCES_DIR/ffprobe"

if [ -x "$FFMPEG_PATH" ] && [ -x "$FFPROBE_PATH" ]; then
    echo "==> FFmpeg already present:"
    "$FFMPEG_PATH" -version | head -1
    "$FFPROBE_PATH" -version | head -1
    exit 0
fi

echo "==> Downloading static FFmpeg for macOS arm64..."

# Martin Riedl's static builds for macOS arm64
FFMPEG_URL="https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"
FFPROBE_URL="https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffprobe.zip"

if ! [ -x "$FFMPEG_PATH" ]; then
    echo "==> Downloading ffmpeg..."
    curl -L -o /tmp/ffmpeg-desktop.zip "$FFMPEG_URL"
    unzip -o /tmp/ffmpeg-desktop.zip -d "$RESOURCES_DIR"
    rm /tmp/ffmpeg-desktop.zip
    chmod +x "$FFMPEG_PATH"
fi

if ! [ -x "$FFPROBE_PATH" ]; then
    echo "==> Downloading ffprobe..."
    curl -L -o /tmp/ffprobe-desktop.zip "$FFPROBE_URL"
    unzip -o /tmp/ffprobe-desktop.zip -d "$RESOURCES_DIR"
    rm /tmp/ffprobe-desktop.zip
    chmod +x "$FFPROBE_PATH"
fi

echo "==> FFmpeg installed:"
"$FFMPEG_PATH" -version | head -1
"$FFPROBE_PATH" -version | head -1

# Verify dynamic dependencies (should show only system libs)
echo "==> Dynamic dependencies (ffmpeg):"
otool -L "$FFMPEG_PATH" 2>/dev/null | tail -n +2 || true
