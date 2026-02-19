#!/usr/bin/env bash
# Build the bristlenose CLI as a PyInstaller --onedir bundle for embedding
# inside the macOS .app.
#
# Prerequisites:
#   - Python 3.10+ with bristlenose installed (editable or regular)
#   - pip install pyinstaller
#
# Output: desktop/Bristlenose/Resources/bristlenose-sidecar/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DESKTOP_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$DESKTOP_DIR/Bristlenose/Resources"

echo "==> Building bristlenose sidecar with PyInstaller..."

mkdir -p "$RESOURCES_DIR"

# Use the project's venv Python
PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Error: Python venv not found at $PYTHON"
    echo "Run: cd $PROJECT_ROOT && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

# Check PyInstaller is installed
if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "Error: PyInstaller not installed. Run: $PYTHON -m pip install pyinstaller"
    exit 1
fi

# Build using the spec file (--onedir mode with hidden imports and data files)
"$PYTHON" -m PyInstaller \
    --distpath "$RESOURCES_DIR" \
    --workpath "$DESKTOP_DIR/build/pyinstaller" \
    --clean \
    --noconfirm \
    "$DESKTOP_DIR/bristlenose-sidecar.spec"

echo "==> Sidecar built: $RESOURCES_DIR/bristlenose-sidecar/"
ls -lh "$RESOURCES_DIR/bristlenose-sidecar/bristlenose-sidecar"
du -sh "$RESOURCES_DIR/bristlenose-sidecar/"
