#!/usr/bin/env bash
# compare-render.sh — Render project-ikea and compare against baseline.
#
# Usage:
#   scripts/compare-render.sh              # Render, diff against baseline, open browser if different
#   scripts/compare-render.sh --baseline   # Capture current output as the golden baseline
#   scripts/compare-render.sh --diff-only  # Just diff (no re-render)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$REPO_DIR/.venv/bin"
PROJECT_OUTPUT="$REPO_DIR/trial-runs/project-ikea/bristlenose-output"
BASELINE="$REPO_DIR/_comparison/baseline"
CURRENT="$REPO_DIR/_comparison/current"

REPORT="bristlenose-project-ikea-report.html"
FILES=(
    "$REPORT"
    "codebook.html"
    "sessions/transcript_s1.html"
    "sessions/transcript_s2.html"
    "sessions/transcript_s3.html"
    "sessions/transcript_s4.html"
    "assets/bristlenose-theme.css"
)

copy_output() {
    local dest="$1"
    rm -rf "$dest"
    mkdir -p "$dest/sessions" "$dest/assets"
    for f in "${FILES[@]}"; do
        if [[ -f "$PROJECT_OUTPUT/$f" ]]; then
            cp "$PROJECT_OUTPUT/$f" "$dest/$f"
        fi
    done
}

# --baseline mode: capture current output as golden baseline
if [[ "${1:-}" == "--baseline" ]]; then
    echo "==> Rendering with current code..."
    "$VENV/bristlenose" render "$PROJECT_OUTPUT"
    copy_output "$BASELINE"
    echo "==> Baseline captured in $BASELINE"
    exit 0
fi

# Default mode: render, diff, open browser if different
if [[ "${1:-}" != "--diff-only" ]]; then
    echo "==> Rendering with current code..."
    "$VENV/bristlenose" render "$PROJECT_OUTPUT"
fi

if [[ ! -d "$BASELINE" ]]; then
    echo "ERROR: No baseline found. Run: scripts/compare-render.sh --baseline"
    exit 1
fi

copy_output "$CURRENT"

echo ""
echo "==> Comparing against baseline..."
echo ""

DIFF_FOUND=0
for f in "${FILES[@]}"; do
    if [[ -f "$BASELINE/$f" && -f "$CURRENT/$f" ]]; then
        if ! diff -q "$BASELINE/$f" "$CURRENT/$f" > /dev/null 2>&1; then
            echo "  CHANGED: $f"
            diff --unified=3 "$BASELINE/$f" "$CURRENT/$f" | head -40
            echo "  ..."
            echo ""
            DIFF_FOUND=1
        else
            echo "  identical: $f"
        fi
    elif [[ ! -f "$BASELINE/$f" ]]; then
        echo "  NEW (no baseline): $f"
        DIFF_FOUND=1
    elif [[ ! -f "$CURRENT/$f" ]]; then
        echo "  MISSING (was in baseline): $f"
        DIFF_FOUND=1
    fi
done

echo ""
if [[ "$DIFF_FOUND" -eq 0 ]]; then
    echo "==> All files identical to baseline."
else
    echo "==> Differences found. Opening both in browser..."
    open "$BASELINE/$REPORT"
    sleep 0.5
    open "$CURRENT/$REPORT"
fi
