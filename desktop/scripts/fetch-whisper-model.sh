#!/usr/bin/env bash
# Download the faster-whisper small.en model for bundling inside the .app.
#
# Downloads the CTranslate2-converted model from HuggingFace (Systran).
# The model is ~461 MB and contains: model.bin, config.json,
# tokenizer.json, vocabulary.txt.
#
# Output: desktop/Bristlenose/Resources/models/small.en/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DESKTOP_DIR="$SCRIPT_DIR/.."
RESOURCES_DIR="$DESKTOP_DIR/Bristlenose/Resources"
MODEL_DIR="$RESOURCES_DIR/models/small.en"

if [ -d "$MODEL_DIR" ] && [ -f "$MODEL_DIR/model.bin" ]; then
    echo "==> Whisper model already present: $MODEL_DIR"
    du -sh "$MODEL_DIR"
    exit 0
fi

mkdir -p "$MODEL_DIR"

PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Error: Python venv not found at $PYTHON"
    exit 1
fi

echo "==> Downloading faster-whisper small.en model (~461 MB)..."

"$PYTHON" -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Systran/faster-whisper-small.en',
    local_dir='$MODEL_DIR',
)
print('Done.')
"

echo "==> Model downloaded:"
ls -lh "$MODEL_DIR/"
du -sh "$MODEL_DIR"
