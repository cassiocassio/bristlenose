#!/usr/bin/env bash
# Negative fixtures for check-window-surfaces.sh.
#
# The gate stops a class that shipped twice in three days (a window showing another window's
# serve), and its fifth assertion matches exact source lines, so a rename can make it fail
# permanently on correct code. Both directions are worth proving: each assertion goes red on its
# own violation, and a tree that satisfies them all passes.
#
# The gate finds its inputs relative to its own path (`$(dirname "$0")/../Bristlenose/...`), so each
# case copies the real gate into a scratch tree beside fixture sources.
#
# Usage: test-check-window-surfaces.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE_SRC="$SCRIPT_DIR/check-window-surfaces.sh"
[ -f "$GATE_SRC" ] || { echo "gate not found: $GATE_SRC" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-windows-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# A tree that satisfies every assertion. Echoes the path of the copied gate.
tree() {  # <name>
    local t="$TMP/$1"
    mkdir -p "$t/scripts" "$t/Bristlenose/Bristlenose" "$t/Bristlenose/BristlenoseTests"
    cp "$GATE_SRC" "$t/scripts/check-window-surfaces.sh"; chmod +x "$t/scripts/check-window-surfaces.sh"
    printf '%s\n' \
        'var serveManager: ServeManager? {' \
        '    selectedProject.map { serveFleet.manager(for: $0.id) }' \
        '}' > "$t/Bristlenose/Bristlenose/ContentView.swift"
    printf '%s\n' 'struct BristlenoseApp { var body: some Scene { WindowGroup { } } }' \
        > "$t/Bristlenose/Bristlenose/BristlenoseApp.swift"
    printf '%s\n' \
        'func f() {' \
        '    if mounted != mcpMounted { mcpMounted = mounted }' \
        '    if paths != handshakeProjectPaths { handshakeProjectPaths = paths }' \
        '}' > "$t/Bristlenose/Bristlenose/ServeFleet.swift"
    echo "$t"
}
put() { printf '%s\n' "$3" > "$1/Bristlenose/$2"; }   # <tree> <relative file> <content>

expect() {  # <label> <want-exit> <want-substring-or-empty> <tree>
    local label="$1" want="$2" needle="$3" t="$4" out rc
    out=$("$t/scripts/check-window-surfaces.sh" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

echo "check-window-surfaces negative fixtures"

expect "a tree that satisfies every assertion is clean" 0 "clean" "$(tree clean)"

t=$(tree nonopt); put "$t" Bristlenose/ContentView.swift 'var serveManager: ServeManager { shared }'
expect "a non-optional serveManager is a violation" 1 "no longer an optional fleet-derived property" "$t"

t=$(tree nofleet); put "$t" Bristlenose/ContentView.swift 'var serveManager: ServeManager? {
    return idleManager
}'
expect "a serveManager that stops resolving through the fleet is a violation" 1 "no longer resolves through the fleet" "$t"

t=$(tree appwide); put "$t" Bristlenose/BristlenoseApp.swift 'WindowGroup { ContentView().environmentObject(serveManager) }'
expect "a ServeManager injected app-wide is a violation" 1 "injected app-wide" "$t"

t=$(tree appwide2); put "$t" Bristlenose/BristlenoseApp.swift 'WindowGroup { ContentView().environmentObject(serveFleet.frontedOrIdle) }'
expect "the fleet's stand-in injected app-wide is a violation too" 1 "injected app-wide" "$t"

t=$(tree factread); put "$t" Bristlenose/ContentView.swift 'var serveManager: ServeManager? {
    selectedProject.map { serveFleet.manager(for: $0.id) }
}
let m = serveManager?.mcpMounted'
expect "mcpMounted read off a window's serve is a violation" 1 "app-level fact" "$t"

t=$(tree factread2); put "$t" Bristlenose/ContentView.swift 'var serveManager: ServeManager? {
    selectedProject.map { serveFleet.manager(for: $0.id) }
}
let m = serveManager.handshakeProjectPaths'
expect "handshakeProjectPaths read off a window's serve is a violation" 1 "app-level fact" "$t"

t=$(tree sync); put "$t" Bristlenose/Sync.swift 'final class SelectionSync { }'
expect "SelectionSync returning to the source is a violation" 1 "SelectionSync is back" "$t"

t=$(tree synctest); put "$t" BristlenoseTests/SyncTests.swift 'final class SelectionSync { }'
expect "SelectionSync returning to the tests is a violation too" 1 "SelectionSync is back" "$t"

t=$(tree nomount); put "$t" Bristlenose/ServeFleet.swift '    if paths != handshakeProjectPaths { handshakeProjectPaths = paths }'
expect "mcpMounted with no writer is a violation" 1 "mcpMounted has no writer" "$t"

t=$(tree nopaths); put "$t" Bristlenose/ServeFleet.swift '    if mounted != mcpMounted { mcpMounted = mounted }'
expect "handshakeProjectPaths with no writer is a violation" 1 "handshakeProjectPaths has no writer" "$t"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
