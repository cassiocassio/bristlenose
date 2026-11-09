#!/usr/bin/env bash
# Negative fixtures for check-menu-routing.sh.
#
# The gate exists because the drift it prevents was measured (sixteen broadcast commands became
# nineteen in two weeks, with nothing failing). A gate that cannot fail would let that happen again
# while reading "clean", so each of its two assertions is driven red here against a scratch repo
# root, and each exemption is shown to be the only reason a line passes.
#
# Usage: test-check-menu-routing.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-menu-routing.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-menu-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# A scratch root with MenuCommands.swift holding $2 and, optionally, Other.swift holding $3.
fixture() {  # <name> <menu-source> [other-source]
    local src="$TMP/$1/desktop/Bristlenose/Bristlenose"
    mkdir -p "$src"
    printf '%s\n' "$2" > "$src/MenuCommands.swift"
    [ -n "${3:-}" ] && printf '%s\n' "$3" > "$src/Other.swift"
    echo "$TMP/$1"
}

expect() {  # <label> <want-exit> <want-substring-or-empty> <root>
    local label="$1" want="$2" needle="$3" root="$4" out rc
    out=$("$GATE" "$root" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

echo "check-menu-routing negative fixtures"

expect "a menu file that posts nothing is clean" 0 "clean" \
    "$(fixture clean 'Button("New") { windowCommands?.send(.newProject) }')"

expect "a menu command that broadcasts is a violation" 1 "posts .createNewProject" \
    "$(fixture bcast 'Button("New") { NotificationCenter.default.post(name: .createNewProject, object: nil) }')"

expect "a name wrapped onto the next line is still caught" 1 "posts .renameThing" \
    "$(fixture wrapped 'NotificationCenter.default.post(
        name: .renameThing,
        object: nil)')"

expect "a post whose name cannot be read is a violation, not a pass" 1 "<unparsed>" \
    "$(fixture unparsed 'NotificationCenter.default.post(someNotification)')"

expect "the Cloud Import scene opener is the allowed exemption" 0 "clean" \
    "$(fixture allowed 'NotificationCenter.default.post(name: .openCloudImport, object: nil)')"

expect "the fixture opener is the second allowed exemption" 0 "clean" \
    "$(fixture allowed2 'NotificationCenter.default.post(name: .openCloudImportFixture, object: nil)')"

expect "a retired notification name declared again is a violation" 1 "retired notification 'showWelcome' is back" \
    "$(fixture retired 'Button("Hi") { }' 'extension Notification.Name { static let showWelcome = Notification.Name("x") }')"

expect "a retired word used as a method, not a Notification.Name, is fine" 0 "clean" \
    "$(fixture method 'Button("Hi") { }' 'func showWelcome() {}')"

expect "NotificationCenter used outside the menu bar is not the rule" 0 "clean" \
    "$(fixture elsewhere 'Button("Hi") { }' 'NotificationCenter.default.post(name: NSWindow.didBecomeKeyNotification, object: nil)')"

mkdir -p "$TMP/nomenu/desktop/Bristlenose/Bristlenose"
expect "no MenuCommands.swift is a usage error, not a pass" 2 "not found" "$TMP/nomenu"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
