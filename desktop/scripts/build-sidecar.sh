#!/usr/bin/env bash
# Build the bristlenose desktop sidecar via PyInstaller (Track C).
#
# Produces a --onedir bundle at
#   desktop/Bristlenose/Resources/bristlenose-sidecar/
#
# Signing is a separate step: desktop/scripts/sign-sidecar.sh. Splitting
# build from sign (C2) lets CI re-sign cached PyInstaller output without
# paying the ~60 s rebuild cost on every signing-identity change.
#
# Xcode's "Copy Sidecar Resources" build phase picks the bundle up from
# the Resources directory at archive time.
#
# Prerequisites:
#   - Python 3.12 venv with bristlenose[dev,serve] installed (.venv at repo root)
#   - pip install pyinstaller

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
SPEC="$DESKTOP_DIR/bristlenose-sidecar.spec"
DIST="$DESKTOP_DIR/Bristlenose/Resources"
WORK="$DESKTOP_DIR/build/pyinstaller"
BUNDLE="$DIST/bristlenose-sidecar"

if [ ! -x "$PYTHON" ]; then
    echo "error: venv python not found at $PYTHON" >&2
    echo "run: cd $ROOT && python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev,serve]' pyinstaller" >&2
    exit 1
fi

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "error: PyInstaller not installed. run: $PYTHON -m pip install pyinstaller" >&2
    exit 1
fi

mkdir -p "$DIST"

# Fresh-slate the bundle. Repeated C1 runs appended stale Mach-Os into
# the old tree, which then failed verification without a clear cause.
rm -rf "$BUNDLE"

echo "==> Building sidecar with PyInstaller..."
"$PYTHON" -m PyInstaller \
    --distpath "$DIST" \
    --workpath "$WORK" \
    --clean --noconfirm \
    "$SPEC"

echo "==> Bundle size:"
du -sh "$BUNDLE"

# Privacy manifest. Apple requires a PrivacyInfo.xcprivacy at the bundle
# root covering required-reason API usage by the embedded Python interpreter
# and vendored packages. Source kept at desktop/bristlenose-sidecar.PrivacyInfo.xcprivacy
# so it travels with the spec. C4 (28 Apr 2026).
PRIVACY_SRC="$DESKTOP_DIR/bristlenose-sidecar.PrivacyInfo.xcprivacy"
PRIVACY_DST="$BUNDLE/PrivacyInfo.xcprivacy"
if [ ! -f "$PRIVACY_SRC" ]; then
    echo "error: privacy manifest source missing at $PRIVACY_SRC" >&2
    exit 1
fi
cp "$PRIVACY_SRC" "$PRIVACY_DST"
echo "==> Privacy manifest: $PRIVACY_DST"

echo "==> Done. Bundle: $BUNDLE"
echo "    Next: desktop/scripts/sign-sidecar.sh"
