#!/usr/bin/env bash
# Download pinned static FFmpeg + ffprobe binaries for macOS arm64
# and place them under desktop/Bristlenose/Resources/ so the Xcode
# "Copy Resources" build phase picks them up for bundling.
#
# Ported from desktop/v0.1-archive/scripts/fetch-ffmpeg.sh with SHA256
# pinning added (Track C C2). v0.1 followed the "latest" redirect,
# which contradicted desktop/CLAUDE.md's "pinned SHA256" claim and
# meant any rebuild silently accepted whatever binary upstream had
# shipped that day.
#
# Output:
#   desktop/Bristlenose/Resources/ffmpeg
#   desktop/Bristlenose/Resources/ffprobe
#
# Upstream: Martin Riedl's static macOS arm64 builds —
#           https://ffmpeg.martin-riedl.de
# To bump: fetch the current "latest" URL, compute `shasum -a 256` on
# each zip, paste the resolved location path + hash below, then bump
# the FFMPEG_VERSION comment.

set -euo pipefail

# FFmpeg 8.1 — pinned 2026-04-19.
FFMPEG_VERSION="8.1"
FFMPEG_URL="https://ffmpeg.martin-riedl.de/download/macos/arm64/1774549676_8.1/ffmpeg.zip"
FFPROBE_URL="https://ffmpeg.martin-riedl.de/download/macos/arm64/1774549676_8.1/ffprobe.zip"
FFMPEG_SHA256="cc3a7e0cce36c5eca6c17eeb93830984c657637a8e710dc98f19c8051201fa3a"
FFPROBE_SHA256="fd2e6b7fad9c9aa2bec17c0d7211b5afcc00b4b5c9b63c120985e80c3c198af6"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCES_DIR="$DESKTOP_DIR/Bristlenose/Resources"
CACHE_DIR="$DESKTOP_DIR/build/ffmpeg-cache"

mkdir -p "$RESOURCES_DIR" "$CACHE_DIR"

FFMPEG_PATH="$RESOURCES_DIR/ffmpeg"
FFPROBE_PATH="$RESOURCES_DIR/ffprobe"

# Download + verify + extract one binary. Cache zips under build/ so
# repeated runs don't re-hit upstream.
_fetch_one() {
    local name="$1"
    local url="$2"
    local expected_sha="$3"
    local out_path="$4"
    local zip_path="$CACHE_DIR/${name}-${FFMPEG_VERSION}.zip"

    if [ ! -f "$zip_path" ]; then
        echo "==> Downloading $name ($FFMPEG_VERSION)..."
        curl -fL --retry 3 -o "$zip_path.tmp" "$url"
        mv "$zip_path.tmp" "$zip_path"
    else
        echo "==> Cached: $zip_path"
    fi

    echo "==> Verifying SHA256 of $name..."
    local actual_sha
    actual_sha="$(shasum -a 256 "$zip_path" | awk '{print $1}')"
    if [ "$actual_sha" != "$expected_sha" ]; then
        echo "error: SHA256 mismatch for $name" >&2
        echo "  expected: $expected_sha" >&2
        echo "  actual:   $actual_sha" >&2
        echo "  Upstream artefact changed. Bump FFMPEG_VERSION + hashes" >&2
        echo "  in this script, or investigate before continuing." >&2
        # Purge the bad cache entry so the next run re-downloads.
        rm -f "$zip_path"
        exit 1
    fi

    echo "==> Extracting $name..."
    unzip -o "$zip_path" -d "$RESOURCES_DIR" >/dev/null
    chmod +x "$out_path"
}

if [ -x "$FFMPEG_PATH" ] && [ -x "$FFPROBE_PATH" ]; then
    # Already present — verify version matches what we expect. If
    # someone hand-copied a different binary into Resources/ it'll
    # fail signing downstream; bail early with a clearer message.
    installed_version="$("$FFMPEG_PATH" -version 2>/dev/null | head -1 | awk '{print $3}' | cut -d- -f1)"
    if [ "$installed_version" = "$FFMPEG_VERSION" ]; then
        echo "==> FFmpeg $FFMPEG_VERSION already present in Resources/."
        exit 0
    fi
    echo "==> Installed FFmpeg is $installed_version, expected $FFMPEG_VERSION — re-fetching."
fi

_fetch_one ffmpeg "$FFMPEG_URL" "$FFMPEG_SHA256" "$FFMPEG_PATH"
_fetch_one ffprobe "$FFPROBE_URL" "$FFPROBE_SHA256" "$FFPROBE_PATH"

echo "==> FFmpeg installed:"
"$FFMPEG_PATH" -version | head -1
"$FFPROBE_PATH" -version | head -1

echo "==> Dynamic dependencies (ffmpeg — should be system libs only):"
otool -L "$FFMPEG_PATH" 2>/dev/null | tail -n +2 | head -10 || true
