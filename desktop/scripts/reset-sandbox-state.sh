#!/usr/bin/env bash
# Reset Bristlenose's macOS sandbox state for a clean re-test.
#
# Why this exists: when iterating on App Sandbox / entitlements (Track A),
# stale state in ~/Library/Containers/app.bristlenose/Data and UserDefaults
# can wedge libsecinit on subsequent launches even when the underlying
# entitlements are correct. Symptom is EXC_BREAKPOINT in
# _libsecinit_appsandbox.cold.* during process startup.
#
# What this does:
#   1. Kill any running host (Bristlenose) and sidecar processes
#   2. Free any TCP ports in the per-project range (8150–9149)
#   3. Wipe ~/Library/Containers/app.bristlenose/Data/* (NOT the directory
#      itself — SIP-protects the metadata plist)
#   4. Drop the app's UserDefaults
#
# Idempotent. Safe to run when nothing's running. Doesn't touch DerivedData
# (Cmd+Shift+K in Xcode handles that — different concern).
#
# Usage:
#   desktop/scripts/reset-sandbox-state.sh           # quiet
#   desktop/scripts/reset-sandbox-state.sh --verbose # show each step

set -euo pipefail

BUNDLE_ID="app.bristlenose"
CONTAINER="$HOME/Library/Containers/$BUNDLE_ID"
PORT_RANGE_START=8150
PORT_RANGE_END=9149

VERBOSE=0
[ "${1:-}" = "--verbose" ] || [ "${1:-}" = "-v" ] && VERBOSE=1

log() {
    if [ "$VERBOSE" = "1" ]; then
        echo "==> $*"
    fi
}

# 1. Kill running processes. Two-pass: SIGTERM then SIGKILL after a brief grace.
log "Stopping running Bristlenose / sidecar processes..."
pkill -TERM -x Bristlenose 2>/dev/null || true
pkill -TERM -f bristlenose-sidecar 2>/dev/null || true
sleep 1
pkill -9 -x Bristlenose 2>/dev/null || true
pkill -9 -f bristlenose-sidecar 2>/dev/null || true

# 2. Free any zombie ports in the per-project range.
log "Freeing zombie listeners on $PORT_RANGE_START-$PORT_RANGE_END..."
PIDS="$(lsof -ti ":$PORT_RANGE_START-$PORT_RANGE_END" 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null || true
fi

# 3. Wipe sandbox container contents. The directory + metadata plist are
# SIP-protected; we can only clear what's inside Data/.
if [ -d "$CONTAINER/Data" ]; then
    log "Wiping $CONTAINER/Data/*..."
    # Glob includes hidden dotfiles via .??* (skips . and ..).
    rm -rf "$CONTAINER/Data/"* "$CONTAINER/Data/".??* 2>/dev/null || true
else
    log "No Data dir at $CONTAINER — nothing to wipe."
fi

# 4. Drop UserDefaults. cfprefsd caches these; trigger a re-read by killing it
# (lightweight, system respawns it instantly).
log "Clearing UserDefaults for $BUNDLE_ID..."
defaults delete "$BUNDLE_ID" 2>/dev/null || true
killall cfprefsd 2>/dev/null || true

echo "✓ Sandbox state reset for $BUNDLE_ID. Ready for a fresh Cmd+R."
