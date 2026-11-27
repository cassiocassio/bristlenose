#!/usr/bin/env bash
# Put the Mac app's ffmpeg + ffprobe in desktop/Bristlenose/Resources/, where the
# Xcode "Copy Resources" build phase picks them up.
#
# They are an LGPL build we make from pinned sources (build-ffmpeg-lgpl.sh), not
# a download: no reputable source publishes a static LGPL macOS arm64 build with
# libass, and the app ships under Apple's EULA, which a GPL binary can't go out
# under. Until 25 Nov 2026 this script downloaded martin-riedl.de's GPL build
# (x264, x265), pinned by SHA256.
#
# Usage:
#   desktop/scripts/fetch-ffmpeg.sh          install (build once, then from cache)
#   desktop/scripts/fetch-ffmpeg.sh --check  exit 0 if Resources/ already holds
#                                            this recipe's build, 1 if not
#
# --check reads the binaries' embedded strings instead of running them: once
# sign-ffmpeg.sh has signed them with the sandbox entitlements they exit 133
# with no output outside the app.
#
# Output (gitignored):
#   desktop/Bristlenose/Resources/ffmpeg
#   desktop/Bristlenose/Resources/ffprobe
# They are unsigned until sign-ffmpeg.sh runs; ensure-sidecar.sh signs after a
# fetch.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Overridable only so tests/test_ffmpeg_lgpl_recipe.py can feed --check fake binaries.
RESOURCES_DIR="${FETCH_FFMPEG_RESOURCES_DIR:-$DESKTOP_DIR/Bristlenose/Resources}"
VERSION="$("$SCRIPT_DIR/build-ffmpeg-lgpl.sh" --version)"
BUILT_DIR="$DESKTOP_DIR/build/ffmpeg-cache/$VERSION"

# True if $1 is this recipe's build: it carries the version string and passes
# check-ffmpeg-licence.sh (LGPL-2.1+, no GPL, nonfree, version3, x264 or x265
# flag), the same gate build-all.sh runs on the exported app.
_is_ours() {
    local bin="$1" text
    [ -f "$bin" ] || return 1
    # Herestrings, not pipes: `strings | grep -q` closes the pipe at the first
    # match, and under pipefail the SIGPIPE makes a found match read as failure.
    text="$(strings -a "$bin")"
    grep -qx -- "$VERSION" <<<"$text" || return 1
    "$SCRIPT_DIR/check-ffmpeg-licence.sh" "$bin" >/dev/null 2>&1
}

_installed() {
    [ -x "$RESOURCES_DIR/ffmpeg" ] && [ -x "$RESOURCES_DIR/ffprobe" ] \
        && _is_ours "$RESOURCES_DIR/ffmpeg" && _is_ours "$RESOURCES_DIR/ffprobe"
}

if [ "${1:-}" = "--check" ]; then
    _installed
    exit
fi

if _installed; then
    echo "==> FFmpeg $VERSION already present in Resources/."
    exit 0
fi

if ! { _is_ours "$BUILT_DIR/ffmpeg" && _is_ours "$BUILT_DIR/ffprobe"; }; then
    echo "==> No cached build of FFmpeg $VERSION; building (about 4 minutes)..."
    # A private temp dir, so a second fetch can't delete this one's output.
    mkdir -p "$(dirname "$BUILT_DIR")"
    tmp="$(mktemp -d "$BUILT_DIR.tmp.XXXXXX")"
    "$SCRIPT_DIR/build-ffmpeg-lgpl.sh" "$tmp" || { rm -rf "$tmp"; exit 1; }
    rm -rf "$BUILT_DIR"
    mv "$tmp" "$BUILT_DIR"
fi

mkdir -p "$RESOURCES_DIR"
for name in ffmpeg ffprobe; do
    cp "$BUILT_DIR/$name" "$RESOURCES_DIR/$name.tmp"
    chmod +x "$RESOURCES_DIR/$name.tmp"
    mv -f "$RESOURCES_DIR/$name.tmp" "$RESOURCES_DIR/$name"
done
_installed || { echo "error: installed binaries are not FFmpeg $VERSION" >&2; exit 1; }
echo "==> FFmpeg $VERSION installed in Resources/ (unsigned until sign-ffmpeg.sh)."
(cd "$RESOURCES_DIR" && shasum -a 256 ffmpeg ffprobe)
