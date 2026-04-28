#!/usr/bin/env bash
# Sign the bundled FFmpeg + ffprobe binaries (Track C C2).
#
# These are third-party static builds that ship inside
# Bristlenose.app/Contents/Resources/ alongside the PyInstaller
# sidecar tree. Notarisation rejects the outer bundle unless every
# bundled Mach-O carries a Hardened Runtime signature from us.
#
# Kept separate from sign-sidecar.sh because the two have different
# inputs (FFmpeg is a single Mach-O; sidecar is a tree of 240+) and
# different entitlement stories (FFmpeg needs none; sidecar carries
# the DLV entitlement for now).
#
# Usage:
#   desktop/scripts/sign-ffmpeg.sh
#
# Environment:
#   SIGN_IDENTITY  codesign identity. Default "-" = ad-hoc.
#   TIMESTAMP_FLAG explicit --timestamp; default matches sign-sidecar.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCES="$DESKTOP_DIR/Bristlenose/Resources"

SIGN_IDENTITY="${SIGN_IDENTITY:--}"

if [ -n "${TIMESTAMP_FLAG:-}" ]; then
    TIMESTAMP=("$TIMESTAMP_FLAG")
elif [ "$SIGN_IDENTITY" = "-" ]; then
    TIMESTAMP=(--timestamp=none)
else
    TIMESTAMP=(--timestamp)
fi

for binary in ffmpeg ffprobe; do
    target="$RESOURCES/$binary"
    if [ ! -f "$target" ]; then
        echo "error: $binary missing at $target" >&2
        echo "run desktop/scripts/fetch-ffmpeg.sh first." >&2
        exit 1
    fi

    echo "==> Signing $binary (identity: $SIGN_IDENTITY)..."
    codesign --force --options=runtime "${TIMESTAMP[@]}" \
        --sign "$SIGN_IDENTITY" "$target"

    if [ "$SIGN_IDENTITY" != "-" ]; then
        # Capture first: `grep -q` causes SIGPIPE on codesign under
        # pipefail. See sign-sidecar.sh for the full story.
        _dvv_out=$(codesign -dvv "$target" 2>&1)
        if ! grep -q "Timestamp=" <<< "$_dvv_out"; then
            echo "error: no trusted timestamp on $target" >&2
            exit 1
        fi
    fi

    codesign -v --strict "$target"
done

echo "==> Done."
