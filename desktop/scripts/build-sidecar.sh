#!/usr/bin/env bash
# Build the bristlenose CLI as a PyInstaller one-file binary for bundling
# inside the macOS .app.
#
# Prerequisites:
#   - Python 3.10+ with bristlenose installed (editable or regular)
#   - pip install pyinstaller
#
# Output: desktop/Bristlenose/Resources/bristlenose-cli

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

# Build the one-file binary
"$PYTHON" -m PyInstaller \
    --onefile \
    --name bristlenose-cli \
    --distpath "$RESOURCES_DIR" \
    --workpath "$DESKTOP_DIR/build/pyinstaller" \
    --specpath "$DESKTOP_DIR/build" \
    --clean \
    --noconfirm \
    "$PROJECT_ROOT/bristlenose/__main__.py"

echo "==> Sidecar built: $RESOURCES_DIR/bristlenose-cli"
ls -lh "$RESOURCES_DIR/bristlenose-cli"
