#!/usr/bin/env bash
# Start both dev servers (Vite + FastAPI) in one terminal.
# Ctrl-C kills both. Re-run to restart cleanly.
#
# Usage:
#   ./scripts/dev.sh                    # default: trial-runs/project-ikea
#   ./scripts/dev.sh ~/other-project    # override project directory
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_DIR="${1:-$REPO_DIR/trial-runs/project-ikea}"
BACKEND_PORT=8150

# --- Kill anything on our ports ---
for port in $BACKEND_PORT 5173 5174 5175; do
  lsof -ti:"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
done
sleep 0.3

# --- Start Vite in background ---
cd "$REPO_DIR/frontend"
npm run dev &
VITE_PID=$!

# --- Cleanup on exit ---
cleanup() {
  kill "$VITE_PID" 2>/dev/null || true
  for port in $BACKEND_PORT 5173 5174 5175; do
    lsof -ti:"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

# --- Start FastAPI in foreground ---
cd "$REPO_DIR"
.venv/bin/bristlenose serve "$PROJECT_DIR" --dev --no-open -p "$BACKEND_PORT"
