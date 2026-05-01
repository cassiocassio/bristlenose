#!/usr/bin/env bash
# Reset Bristlenose's macOS sandbox state for a clean re-test.
#
# Platform: macOS only, forever. App Sandbox, ~/Library/Containers, defaults,
# cfprefsd, libsecinit are all Apple concepts with no Linux equivalent. The
# desktop app this supports is macOS-only too. The uname guard below refuses
# fast on anything else rather than producing surprising behaviour.
#
# Why this exists: when iterating on App Sandbox / entitlements (Track A),
# stale state in ~/Library/Containers/app.bristlenose/Data and UserDefaults
# can wedge libsecinit on subsequent launches even when the underlying
# entitlements are correct. Symptom is EXC_BREAKPOINT in
# _libsecinit_appsandbox.cold.* during process startup.
#
# Background — what that EXC_BREAKPOINT actually means:
# At process spawn, libSystem_initializer() calls _libsecinit_initializer(),
# which IPCs with secinitd (a per-user agent) to mint the sandbox container.
# If secinitd cannot identify the app the process belongs to (stale Container
# state, code-sign mismatch, bundle-ID rename, container metadata corruption),
# libsystem_secinit.dylib calls abort(3) and the debugger sees it as
# EXC_BREAKPOINT in _libsecinit_appsandbox.cold.*. This script targets the
# stale-state path (steps 3–4); for the others, codesign / bundle-ID changes
# need a separate diagnostic. See:
# https://developer.apple.com/documentation/security/discovering-and-diagnosing-app-sandbox-violations
#
# Do NOT extend this script to touch ~/Library/ContainerManager/ — that
# directory is managed by Apple's containermanagerd; mutating it can produce
# undefined behaviour or data loss across all sandboxed apps on the machine.
#
# Why we built our own (vs upstream): no first-party equivalent exists
# (xcrun simctl erase is iOS-only; tccutil reset is permissions only;
# `defaults delete` is partial). Community tools (AppCleaner / Pearcleaner /
# nektony) target end-user uninstall, not iterative dev reset. So every
# sandboxed-Mac dev rolls their own; ours is parameterised by BUNDLE_ID and
# the per-project port range. Worth sharing as a gist/Homebrew formula
# post-alpha — see the project_app_store_police_share_reminder memory for
# the indie-community sharing window.
#
# What this does (in order):
#   1. Send SIGTERM to host (Bristlenose) and bundled sidecar processes,
#      one-second grace, then SIGKILL the survivors.
#   2. Free any TCP listeners in the per-project range 8150-9149, but
#      only those owned by Bristlenose-named processes (won't nuke an
#      unrelated dev server in that range).
#   3. Wipe ~/Library/Containers/app.bristlenose/Data/* (NOT the directory
#      itself — SIP protects the metadata plist).
#   4. Drop the app's UserDefaults via `defaults delete` and bounce
#      cfprefsd so the wipe is observed immediately.
#
# Output is verbose by default — each step reports what it found and
# what it did, so when sandbox iteration misbehaves you have clues
# (e.g. "killed PID 49215 (Bristlenose)" vs "no Bristlenose processes").
# Pass --quiet for one-line summary only.
#
# Idempotent and safe to run when nothing is running. Doesn't touch
# DerivedData (Cmd+Shift+K in Xcode handles that — different concern).
#
# Usage:
#   desktop/scripts/reset-sandbox-state.sh             # verbose (default)
#   desktop/scripts/reset-sandbox-state.sh --quiet     # summary line only
#   desktop/scripts/reset-sandbox-state.sh --dry-run   # show what would happen, change nothing

set -euo pipefail

BUNDLE_ID="app.bristlenose"
CONTAINER="$HOME/Library/Containers/$BUNDLE_ID"
PORT_RANGE_START=8150
PORT_RANGE_END=9149

VERBOSE=1
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --quiet|-q) VERBOSE=0 ;;
        --dry-run|-n) DRY_RUN=1 ;;
        --verbose|-v) VERBOSE=1 ;;  # accepted for back-compat, no-op (default)
        --help|-h)
            sed -n '2,30p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            echo "usage: $0 [--quiet|-q] [--dry-run|-n] [--help|-h]" >&2
            exit 2
            ;;
    esac
    shift
done

DRY_PREFIX=""
[ "$DRY_RUN" = "1" ] && DRY_PREFIX="(dry-run) "

say() {
    [ "$VERBOSE" = "1" ] && echo "${DRY_PREFIX}$*"
    return 0
}

run() {
    if [ "$DRY_RUN" = "1" ]; then
        say "would run: $*"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Sanity check: is the script running on macOS? Container/sandbox/cfprefsd
# all assume macOS. Refuse fast on Linux/CI.
if [ "$(uname)" != "Darwin" ]; then
    echo "error: reset-sandbox-state.sh is macOS-only (uname=$(uname))" >&2
    exit 1
fi

if [ -z "$BUNDLE_ID" ]; then
    # Defensive — guards against an accidental empty-var rewrite breaking the
    # rm -rf below into something dangerous. Belt-and-braces; should never fire.
    echo "error: BUNDLE_ID empty — refusing to continue" >&2
    exit 1
fi

say "==> reset-sandbox-state.sh starting (bundle=$BUNDLE_ID)"

# ---------------------------------------------------------------------------
# Step 1: kill host + sidecar processes.
#
# - Host: pkill -x matches the exact short name "Bristlenose".
# - Sidecar: pkill -f against the full path "Resources/bristlenose-sidecar/"
#   so we hit only sidecar processes spawned out of a real .app bundle, not
#   a terminal whose argv contains the literal string "bristlenose-sidecar"
#   (e.g. someone running build-sidecar.sh).
say "==> step 1: stopping running processes"

count_matches() {
    # pgrep exits 1 when nothing matches, which under `set -euo pipefail`
    # trips even when piped to wc. Capture first, then count, so a "no
    # matches" path returns 0 cleanly without nuking the script.
    local pids
    pids="$(pgrep "$@" 2>/dev/null || true)"
    if [ -z "$pids" ]; then
        echo 0
    else
        printf '%s\n' "$pids" | wc -l | tr -d ' '
    fi
}

HOST_BEFORE=$(count_matches -x Bristlenose)
SIDECAR_BEFORE=$(count_matches -f "Resources/bristlenose-sidecar/")
say "    found: host=$HOST_BEFORE sidecar=$SIDECAR_BEFORE"

if [ "$HOST_BEFORE" -gt 0 ] || [ "$SIDECAR_BEFORE" -gt 0 ]; then
    say "    SIGTERM..."
    run pkill -TERM -x Bristlenose 2>/dev/null || true
    run pkill -TERM -f "Resources/bristlenose-sidecar/" 2>/dev/null || true
    [ "$DRY_RUN" = "0" ] && sleep 1

    HOST_MID=$(count_matches -x Bristlenose)
    SIDECAR_MID=$(count_matches -f "Resources/bristlenose-sidecar/")
    if [ "$HOST_MID" -gt 0 ] || [ "$SIDECAR_MID" -gt 0 ]; then
        say "    survivors after grace: host=$HOST_MID sidecar=$SIDECAR_MID — SIGKILL"
        run pkill -9 -x Bristlenose 2>/dev/null || true
        run pkill -9 -f "Resources/bristlenose-sidecar/" 2>/dev/null || true
    else
        say "    all stopped after SIGTERM"
    fi
else
    say "    nothing running"
fi

# ---------------------------------------------------------------------------
# Step 2: free zombie ports in the project range.
#
# Filter by command name (Bristlenose / bristlenose-sidecar) so we only kill
# our own listeners. An unrelated dev server in 8150-9149 (e.g. someone's
# Python http.server) is left alone.
say "==> step 2: freeing zombie listeners on $PORT_RANGE_START-$PORT_RANGE_END"

# lsof's -c is prefix-match; explicit exec names cover both cases. -t = PIDs only.
ZOMBIE_PIDS="$(lsof -ti ":$PORT_RANGE_START-$PORT_RANGE_END" -c Bristlenose -c bristlenose-sidecar 2>/dev/null || true)"
if [ -n "$ZOMBIE_PIDS" ]; then
    say "    found PIDs: $(echo "$ZOMBIE_PIDS" | tr '\n' ' ')"
    if [ "$DRY_RUN" = "0" ]; then
        echo "$ZOMBIE_PIDS" | xargs kill -9 2>/dev/null || true
        say "    SIGKILL sent"
    else
        say "    would SIGKILL"
    fi
else
    say "    no Bristlenose-owned listeners in range"
fi

# ---------------------------------------------------------------------------
# Step 3: wipe sandbox container contents.
#
# We can only clear inside Data/ — the parent directory and the metadata plist
# are SIP-protected (rm returns "Operation not permitted" even as the user).
say "==> step 3: wiping container Data/"

if [ -d "$CONTAINER/Data" ]; then
    DATA_BYTES_BEFORE=$(du -sk "$CONTAINER/Data" 2>/dev/null | awk '{print $1}')
    DATA_FILE_COUNT=$(find "$CONTAINER/Data" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')
    say "    $CONTAINER/Data — ${DATA_FILE_COUNT} entries, ${DATA_BYTES_BEFORE} KB"

    if [ "$DATA_FILE_COUNT" -gt 0 ]; then
        if [ "$DRY_RUN" = "0" ]; then
            # Two globs: visible and hidden (.??* covers .x... — single-char
            # dotfiles are vanishingly rare in macOS sandbox containers, so
            # not worth the .[!.]* gymnastics).
            rm -rf "$CONTAINER/Data/"* "$CONTAINER/Data/".??* 2>/dev/null || true
            DATA_FILE_AFTER=$(find "$CONTAINER/Data" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')
            say "    after wipe: ${DATA_FILE_AFTER} entries remaining"
            if [ "$DATA_FILE_AFTER" -gt 0 ]; then
                say "    note: ${DATA_FILE_AFTER} entries survived (likely SIP-protected files)"
            fi
        else
            say "    would rm -rf $CONTAINER/Data/* $CONTAINER/Data/.??*"
        fi
    else
        say "    Data/ is empty — nothing to wipe"
    fi
else
    say "    no Data/ at $CONTAINER (app may never have launched yet)"
fi

# ---------------------------------------------------------------------------
# Step 4: clear UserDefaults.
#
# `defaults delete <bundle-id>` blows away the whole pref domain. cfprefsd
# caches in memory, so we bounce it; macOS launchd respawns it instantly.
say "==> step 4: clearing UserDefaults"

# Same pipefail dance as count_matches: defaults read exits non-zero on a
# missing domain; capture-then-count avoids the pipeline tripping set -e.
DEFAULTS_RAW="$(defaults read "$BUNDLE_ID" 2>/dev/null || true)"
if [ -z "$DEFAULTS_RAW" ]; then
    DEFAULTS_BEFORE=0
else
    DEFAULTS_BEFORE=$(printf '%s\n' "$DEFAULTS_RAW" | wc -l | tr -d ' ')
fi
say "    pref domain $BUNDLE_ID has $DEFAULTS_BEFORE lines of state"

if [ "$DEFAULTS_BEFORE" -gt 0 ]; then
    run defaults delete "$BUNDLE_ID" 2>/dev/null || say "    (defaults delete returned non-zero — domain may have been empty)"
    run killall cfprefsd 2>/dev/null || true
    say "    defaults dropped, cfprefsd bounced"
else
    say "    nothing to clear"
fi

# ---------------------------------------------------------------------------
if [ "$DRY_RUN" = "1" ]; then
    echo "✓ Dry-run complete for $BUNDLE_ID. No state changed."
else
    echo "✓ Sandbox state reset for $BUNDLE_ID. Ready for a fresh Cmd+R."
fi
