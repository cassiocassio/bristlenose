#!/usr/bin/env bash
# Track C C0 spike: build + ad-hoc-sign the trimmed sidecar.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
DIST="$HERE/dist"
BUNDLE="$DIST/bristlenose-sidecar"

if [ ! -x "$PYTHON" ]; then
    echo "error: venv python not found at $PYTHON" >&2
    exit 1
fi

echo "==> Building sidecar with PyInstaller..."
"$PYTHON" -m PyInstaller \
    --distpath "$DIST" \
    --workpath "$HERE/build" \
    --clean --noconfirm \
    "$HERE/bristlenose-sidecar.spec"

echo "==> Bundle size:"
du -sh "$BUNDLE"

echo "==> Counting signable Mach-O files..."
COUNT=$(find "$BUNDLE" -type f \( -name "*.dylib" -o -name "*.so" -o -perm +111 \) 2>/dev/null | wc -l | tr -d ' ')
echo "    $COUNT"

echo "==> Ad-hoc signing every Mach-O with Hardened Runtime..."
# Sign innermost first, outer binary last. `codesign --deep --force` works
# on a staged bundle for the C0 spike; C2 will parallelise with xargs -P8.
find "$BUNDLE" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 |
    while IFS= read -r -d '' f; do
        codesign --force --options=runtime --timestamp=none \
            --entitlements "$HERE/bristlenose-sidecar.entitlements" \
            --sign - "$f" 2>&1 | tail -1 || true
    done

codesign --force --options=runtime --timestamp=none \
    --entitlements "$HERE/bristlenose-sidecar.entitlements" \
    --sign - "$BUNDLE/bristlenose-sidecar"

echo "==> Verifying signature..."
codesign -dv --entitlements :- "$BUNDLE/bristlenose-sidecar" 2>&1 | head -30

echo "==> Done. Binary: $BUNDLE/bristlenose-sidecar"
