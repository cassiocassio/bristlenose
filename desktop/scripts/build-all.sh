#!/usr/bin/env bash
# Build everything needed for a distributable .dmg from scratch.
#
# Runs the four build steps in order:
#   1. PyInstaller sidecar
#   2. Static FFmpeg + ffprobe binaries
#   3. Whisper model (small.en)
#   4. Xcode archive + .dmg packaging
#
# Output: desktop/build/Bristlenose.dmg

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Step 1/4: Building sidecar..."
"$SCRIPT_DIR/build-sidecar.sh"

echo ""
echo "==> Step 2/4: Fetching FFmpeg..."
"$SCRIPT_DIR/fetch-ffmpeg.sh"

echo ""
echo "==> Step 3/4: Fetching Whisper model..."
"$SCRIPT_DIR/fetch-whisper-model.sh"

echo ""
echo "==> Step 4/4: Building .dmg..."
"$SCRIPT_DIR/build-dmg.sh"
