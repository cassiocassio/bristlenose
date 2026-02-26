#!/usr/bin/env bash
# prep-logo-assets.sh — Convert a source video to animated logo formats.
#
# Usage: ./scripts/prep-logo-assets.sh <source-video-with-alpha>
#
# The source video should have an alpha channel (transparent background).
# Outputs two files into bristlenose/theme/images/:
#   bristlenose-alive.webm  — VP9 with alpha (Chrome, Firefox, Edge)
#   bristlenose-alive.mov   — HEVC with alpha (Safari on macOS)
#
# Both are scaled to 160px wide (2× retina for the 80px CSS display size).
# Run this as many times as you like with different source videos — it
# overwrites the previous output each time.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <source-video>"
    echo ""
    echo "The source video should have a transparent (alpha) background."
    echo "Outputs WebM VP9 alpha + MOV HEVC alpha to bristlenose/theme/images/."
    exit 1
fi

SRC="$1"
DIR="$(cd "$(dirname "$0")/../bristlenose/theme/images" && pwd)"

echo "==> Converting to WebM VP9 alpha..."
ffmpeg -i "$SRC" \
    -c:v libvpx-vp9 -pix_fmt yuva420p \
    -b:v 200k -crf 30 \
    -vf "scale=160:-1" \
    -an -y \
    "$DIR/bristlenose-alive.webm"

echo "==> Converting to MOV HEVC alpha..."
ffmpeg -i "$SRC" \
    -c:v hevc_videotoolbox -pix_fmt bgra \
    -allow_sw 1 -alpha_quality 0.75 \
    -tag:v hvc1 \
    -vf "scale=160:-1" \
    -an -y \
    "$DIR/bristlenose-alive.mov"

echo ""
echo "Done. Output files:"
ls -lh "$DIR/bristlenose-alive."*
