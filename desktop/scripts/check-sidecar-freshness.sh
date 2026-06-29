#!/usr/bin/env bash
# Fail the Xcode build if the bundled PyInstaller sidecar is STALE relative to
# the source it serves — the Python under bristlenose/ OR the React frontend.
#
# WHY: the desktop app runs the *bundled* sidecar binary (and the SPA baked into
# it), not the worktree's live source. A Python OR frontend change that isn't
# followed by `build-sidecar.sh` silently ships old behaviour — the app serves
# stale code with no signal. This class of bug ate a multi-hour debugging session
# (Run Inspector 404/401, 28 Jun 2026: the endpoint+schema fixes were in the
# source but not in the bundle the app ran) and recurs at the frontend layer
# every time a new SPA feature renders blank because the bundled static/ predates
# it. This turns "silent stale" into a loud, one-line build error.
#
# HOW: build-sidecar.sh runs `npm run build` (so server/static/ matches the
# frontend source) then stamps the bundle with a fingerprint over all
# bristlenose/**/*.py + bristlenose/locales/** + frontend build inputs (see
# sidecar-source-hash.sh — the shared recipe). Here we recompute it and compare.
# Because the fingerprint only changes when that source actually changes,
# pure-Swift builds never trip this.
#
# BYPASS: BRISTLENOSE_ALLOW_STALE_SIDECAR=1 (downgrades to a warning) — for
# deliberately running a stale sidecar while iterating on Swift only.
#
# Invoked from the "Copy Sidecar Resources" build phase (before the rsync), so a
# stale bundle is never copied into the .app. bash 3.2-compatible.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE="$ROOT/desktop/Bristlenose/Resources/bristlenose-sidecar"
STAMP="$BUNDLE/.source-stamp"

# shellcheck source=sidecar-source-hash.sh
. "$SCRIPT_DIR/sidecar-source-hash.sh"

if [ "${BRISTLENOSE_ALLOW_STALE_SIDECAR:-0}" = "1" ]; then
    echo "warning: sidecar freshness check bypassed (BRISTLENOSE_ALLOW_STALE_SIDECAR=1)"
    exit 0
fi

if [ ! -d "$BUNDLE" ]; then
    # No bundle at all — the existing rsync guard already no-ops; not this gate's
    # job to require one (lets pure-Swift checkouts build without a 428 MB bundle).
    echo "warning: no bundled sidecar present — run desktop/scripts/build-sidecar.sh if you need the desktop server."
    exit 0
fi

current="$(sidecar_source_hash "$ROOT")"

if [ ! -f "$STAMP" ]; then
    echo "error: bundled sidecar has no .source-stamp — it predates the freshness gate (e.g. ditto'd from main). Rebuild it so it carries a stamp: desktop/scripts/build-sidecar.sh && desktop/scripts/sign-sidecar.sh. Bypass: BRISTLENOSE_ALLOW_STALE_SIDECAR=1."
    exit 1
fi

stamped="$(head -1 "$STAMP")"

if [ "$current" != "$stamped" ]; then
    echo "error: bundled sidecar is STALE — Python or frontend source under bristlenose/ / frontend/ changed since the last build-sidecar.sh (bundle ${stamped:0:12} vs source ${current:0:12}). The desktop app runs the bundled sidecar + baked SPA, so this build would serve OLD code. Rebuild: desktop/scripts/build-sidecar.sh && desktop/scripts/sign-sidecar.sh (build-sidecar.sh runs npm build for you). Bypass (Swift-only work): BRISTLENOSE_ALLOW_STALE_SIDECAR=1."
    exit 1
fi

echo "✓ bundled sidecar matches source — Python + frontend (${current:0:12})"
