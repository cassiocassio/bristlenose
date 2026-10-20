#!/bin/bash
# guest-walk.sh <night-dir> — one night's walk: clone the base, walk, compare, tear down.
#
# Called by guest-matrix.sh after the Swift suite (docs/design-guest-walk.md). The
# base, WALK_BASE, is a Cirrus macOS vanilla image plus only the tart guest agent
# and three grants a person gave once (prep-base.sh). Each night is a throwaway
# clone named gw-<night>, a prefix that cannot match the base, and this script
# refuses to delete WALK_BASE by name: the grants cannot be scripted back.
#
# Writes, inside <night-dir>: the walk's captures, walk.log and verdict.txt (from
# walk.sh), then index.html + img/ and summary.txt (from report.py, against the
# last completed walk). Moves <walks>/latest to tonight, and <walks>/baseline to
# tonight only when the walk COMPLETED. Prints nothing the caller relies on: the
# caller reads verdict.txt and summary.txt.
#
# Env: WALK_BASE (required), TART_HOME, GW_TART (the tart binary), PROVIDER
# (default ollama), GW_SHARE (the read-only share the guest mounts).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NIGHT_DIR="${1:?night dir}"
mkdir -p "$(dirname "$NIGHT_DIR")" 2>/dev/null
WALKS="$(cd "$(dirname "$NIGHT_DIR")" 2>/dev/null && pwd)" || { echo "guest-walk: no parent for $NIGHT_DIR" >&2; exit 2; }
RUN="$(basename "$NIGHT_DIR")"
[ -n "$RUN" ] || { echo "guest-walk: empty night name" >&2; exit 2; }
BASE="${WALK_BASE:?WALK_BASE is not set}"
export TART_HOME="${TART_HOME:-/Volumes/Iona/tart}"
TART="${GW_TART:-$HOME/Applications/tart.app/Contents/MacOS/tart}"
export TART_BIN="$TART"
SHARE="${GW_SHARE:-$TART_HOME/share/bn-walk}"
CACHE="${GW_CACHE:-$HOME/Library/Caches/bristlenose-guest-walk}"
export GUEST="gw-$RUN"
export PROVIDER="${PROVIDER:-ollama}"
[ "$GUEST" != "$BASE" ] || { echo "guest-walk: clone name equals the base" >&2; exit 2; }

VM_PID=""; WALK_PID=""
# bounded <secs> <cmd…> — macOS has no `timeout`; a tart call that never returns
# must not stall the night (the caller gives this script 150 s to clean up).
bounded() {
    local s="$1" p w rc; shift
    "$@" & p=$!
    ( sleep "$s"; kill "$p" 2>/dev/null ) >/dev/null 2>&1 & w=$!
    wait "$p"; rc=$?
    kill "$w" 2>/dev/null; wait "$w" 2>/dev/null
    return "$rc"
}
# delete_clone <name> — only ever a gw-* clone, never the base. The caller has
# stopped it already.
delete_clone() {
    case "$1" in gw-?*) ;; *) echo "guest-walk: refusing to delete '$1'" >&2; return 1 ;; esac
    [ "$1" = "$BASE" ] && { echo "guest-walk: refusing to delete the base" >&2; return 1; }
    "$TART" delete "$1" >/dev/null 2>&1
}
cleanup() {
    # The walk's own children first (its tart exec and ssh calls, the tunnel), so
    # nothing writes into the night after the caller has reported on it.
    if [ -n "$WALK_PID" ]; then pkill -TERM -P "$WALK_PID" 2>/dev/null; kill "$WALK_PID" 2>/dev/null; fi
    GUEST="$GUEST" "$HERE/tunnel.sh" down >/dev/null 2>&1
    # One stop, then wait for the VM process, then insist: 60 + 60 at worst,
    # inside the caller's 150 s.
    bounded 60 "$TART" stop "$GUEST" >/dev/null 2>&1
    if [ -n "$VM_PID" ]; then
        local i=0
        while kill -0 "$VM_PID" 2>/dev/null && [ "$i" -lt 60 ]; do sleep 1; i=$((i + 1)); done
        kill -9 "$VM_PID" 2>/dev/null
    fi
    delete_clone "$GUEST"
}
trap cleanup EXIT
# A TERM from the caller (timeout, or a release starting) must run the cleanup:
# bash runs the EXIT trap on a signal only when that signal has a trap.
trap 'echo "STOPPED by the caller" > "$NIGHT_DIR/verdict.txt" 2>/dev/null; exit 143' TERM INT

# Leftovers from a night that was killed outright: gw-* clones only.
"$TART" list 2>/dev/null | awk '$1=="local" && $2 ~ /^gw-/ {print $2}' | while read -r old; do
    bounded 60 "$TART" stop "$old" >/dev/null 2>&1
    delete_clone "$old"
done

# The walker, built on the host and named for its source, so a rebuilt walker is a
# new file the guest cannot be served stale (VirtioFS, Iona README).
mkdir -p "$CACHE" "$SHARE"
wsha="$(shasum -a 256 "$HERE/walker.swift" | cut -c1-8)"
WALKER_GUEST="$SHARE/walker-$wsha"
WALKER_HOST="$CACHE/walker-host-$wsha"
if [ ! -x "$WALKER_HOST" ]; then
    swiftc -O -target arm64-apple-macos15.0 "$HERE/walker.swift" -o "$WALKER_HOST.tmp" >/dev/null 2>&1 \
        && mv "$WALKER_HOST.tmp" "$WALKER_HOST" || { echo "guest-walk: walker did not build" >&2; exit 2; }
fi
[ -x "$WALKER_GUEST" ] || cp "$WALKER_HOST" "$WALKER_GUEST" || exit 2
# The screens fixture is regenerated when missing (75 KB, fixture/make.sh).
[ -f "$SHARE/screens-project/Session 1.mp4" ] || "$HERE/fixture/make.sh" "$SHARE/screens-project" >/dev/null 2>&1

"$TART" clone "$BASE" "$GUEST" || { echo "guest-walk: clone of $BASE failed" >&2; exit 2; }
# A tracked child, not nohup-detached: the cleanup needs a pid to wait on and kill.
# --no-clipboard: tart's clipboard sync runs both ways, so the walk neither reads
# nor writes the host's clipboard.
"$TART" run --no-clipboard --no-audio --dir="walk:$SHARE:ro" "$GUEST" >/dev/null 2>&1 </dev/null &
VM_PID=$!
up=0
for i in $(seq 1 60); do
    if bounded 20 "$HERE/g.sh" true >/dev/null 2>&1; then up=1; break; fi
    kill -0 "$VM_PID" 2>/dev/null || break
    sleep 3
done
[ "$up" = 1 ] || { mkdir -p "$NIGHT_DIR"; echo "HALTED step 0: the guest never answered" > "$NIGHT_DIR/verdict.txt"; exit 0; }
# Tonight's walker, over whatever the base was frozen with.
"$HERE/g.sh" sh -c "mkdir -p ~/walk/bin && cp '/Volumes/My Shared Files/walk/walker-$wsha' ~/walk/bin/walker" || exit 2
if [ "${FIXTURE:-smoke}" = screens ]; then
    "$HERE/g.sh" sh -c 'rm -rf ~/Documents/screens-project && cp -R "/Volumes/My Shared Files/walk/screens-project" ~/Documents/' || exit 2
fi

OUT="$WALKS" FIXTURE="${FIXTURE:-smoke}" "$HERE/walk.sh" "$RUN" >/dev/null 2>&1 &
WALK_PID=$!
wait "$WALK_PID"
WALK_PID=""

# Compare against the last completed walk. A halted walk is compared as far as it
# got (missing screens are a state the page shows) and never becomes the baseline.
verdict="$(cat "$NIGHT_DIR/verdict.txt" 2>/dev/null)"
base_dir=""
if [ -L "$WALKS/baseline" ]; then base_dir="$WALKS/$(readlink "$WALKS/baseline")"; fi
if [ -n "$verdict" ]; then
    if [ -n "$base_dir" ] && [ -d "$base_dir" ] && [ "$base_dir" != "$NIGHT_DIR" ]; then
        if WALKER="$WALKER_HOST" python3 "$HERE/report.py" "$base_dir" "$NIGHT_DIR" "$NIGHT_DIR" \
            > "$NIGHT_DIR/report.out" 2>&1; then
            line="$(sed -E 's/  ->  .*$//' "$NIGHT_DIR/report.out" | tail -1)"
            printf '%s vs %s\n' "$line" "$(basename "$base_dir")" > "$NIGHT_DIR/summary.txt"
        else
            echo "the comparison failed (report.out has why)" > "$NIGHT_DIR/summary.txt"
        fi
    else
        echo "first walk, no baseline yet" > "$NIGHT_DIR/summary.txt"
    fi
fi
ln -sfn "$RUN" "$WALKS/latest"
case "$verdict" in COMPLETED*) ln -sfn "$RUN" "$WALKS/baseline" ;; esac
exit 0
