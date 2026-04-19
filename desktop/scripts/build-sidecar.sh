#!/usr/bin/env bash
# Build + sign the bristlenose desktop sidecar (Track C).
#
# Produces a --onedir PyInstaller bundle at
#   desktop/Bristlenose/Resources/bristlenose-sidecar/
# signed with Hardened Runtime + entitlements in
#   desktop/bristlenose-sidecar.entitlements
#
# Xcode's "Copy Sidecar Resources" build phase picks it up from there.
#
# Signing identity is taken from $SIGN_IDENTITY (default: "-" = ad-hoc).
# Set to "Apple Distribution: <Name> (<TeamID>)" for TestFlight builds.
#
# Prerequisites:
#   - Python 3.12 venv with bristlenose[dev,serve] installed (.venv at repo root)
#   - pip install pyinstaller
#
# C2 will parallelise the inner-binary signing loop with `xargs -P`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
SPEC="$DESKTOP_DIR/bristlenose-sidecar.spec"
ENTITLEMENTS="$DESKTOP_DIR/bristlenose-sidecar.entitlements"
DIST="$DESKTOP_DIR/Bristlenose/Resources"
WORK="$DESKTOP_DIR/build/pyinstaller"
BUNDLE="$DIST/bristlenose-sidecar"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"

# Ad-hoc identity uses --timestamp=none (no Apple timestamp service);
# real Apple Distribution identities must use --timestamp for notarisation.
# Override explicitly to --timestamp=none for TestFlight off-line dry-runs.
if [ -n "${TIMESTAMP_FLAG:-}" ]; then
    : # honour caller-provided value
elif [ "$SIGN_IDENTITY" = "-" ]; then
    TIMESTAMP_FLAG="--timestamp=none"
else
    TIMESTAMP_FLAG="--timestamp"
fi

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

echo "==> Building sidecar with PyInstaller..."
"$PYTHON" -m PyInstaller \
    --distpath "$DIST" \
    --workpath "$WORK" \
    --clean --noconfirm \
    "$SPEC"

echo "==> Bundle size:"
du -sh "$BUNDLE"

echo "==> Signing every Mach-O with Hardened Runtime (identity: $SIGN_IDENTITY, $TIMESTAMP_FLAG)..."
# Inner binaries first, outer last (codesign requires this order).
# No `|| true` — if any inner sign fails, stop and surface the error;
# `set -e` takes us out on the first failure.
while IFS= read -r -d '' f; do
    codesign --force --options=runtime $TIMESTAMP_FLAG \
        --entitlements "$ENTITLEMENTS" \
        --sign "$SIGN_IDENTITY" "$f"
done < <(find "$BUNDLE" -type f \( -name "*.dylib" -o -name "*.so" \) -print0)

codesign --force --options=runtime $TIMESTAMP_FLAG \
    --entitlements "$ENTITLEMENTS" \
    --sign "$SIGN_IDENTITY" "$BUNDLE/bristlenose-sidecar"

echo "==> Verifying outer signature..."
codesign -dv --entitlements :- "$BUNDLE/bristlenose-sidecar" 2>&1 | head -30

echo "==> Strict-verifying every inner Mach-O..."
# Defence in depth against partial-sign bundles that pass ad-hoc `-dv` but
# fail Gatekeeper / notarisation on another machine.
while IFS= read -r -d '' f; do
    codesign -v --strict "$f"
done < <(find "$BUNDLE" -type f \( -name "*.dylib" -o -name "*.so" \) -print0)

echo "==> Deep-verifying outer bundle (Gatekeeper-equivalent)..."
# --deep is deprecated for signing but still supported (and recommended)
# for verification — catches mismatches between inner and outer seals.
codesign --verify --deep --strict --verbose=2 "$BUNDLE/bristlenose-sidecar"

echo "==> Done. Binary: $BUNDLE/bristlenose-sidecar"
