#!/usr/bin/env bash
# Negative fixtures for check-release-binary.sh.
#
# The gate is the only thing between a Swift refactor that moves a `#if DEBUG` read and a shipped
# Release binary that honours dev overrides (or carries get-task-allow, which App Store Connect
# rejects). A gate that cannot fail would let both through reading "clean", so each literal it
# hunts is planted in a scratch file and must turn it red, a clean file must pass, and on macOS the
# bundle walk (the sidecar skip, the Mach-O filter) and get-task-allow are exercised on a real
# Mach-O. Cases that need a Mach-O or codesign are skipped, loudly, elsewhere.
#
# BN_REPORT=0 turns off the report renderer, which would otherwise swallow the gate's own lines.
#
# Usage: test-check-release-binary.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-release-binary.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }
command -v strings >/dev/null 2>&1 || { echo "strings not found" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-relbin-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0; SKIP=0

expect() {  # <label> <want-exit> <want-substring-or-empty> <path...>
    local label="$1" want="$2" needle="$3"; shift 3
    local out rc
    out=$(BN_REPORT=0 "$GATE" "$@" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}
skip() { echo "  - skipped: $1 ($2)"; SKIP=$((SKIP+1)); }

blob() {  # <name> <text> — a file whose printable strings include <text>
    printf 'padding padding padding\n%s\npadding padding padding\n' "$2" > "$TMP/$1"
    echo "$TMP/$1"
}

echo "check-release-binary negative fixtures"

expect "a binary with none of the literals is clean" 0 "clean" "$(blob clean 'ordinary release strings')"
expect "BRISTLENOSE_DEV_EXTERNAL_PORT is a leak" 1 "LEAK" "$(blob dev1 'BRISTLENOSE_DEV_EXTERNAL_PORT')"
expect "BRISTLENOSE_DEV_SIDECAR_PATH is a leak" 1 "LEAK" "$(blob dev2 'BRISTLENOSE_DEV_SIDECAR_PATH')"
expect "the bare BRISTLENOSE_DEV_ prefix is a leak (string-concat refactors)" 1 "LEAK" "$(blob dev3 'BRISTLENOSE_DEV_')"
expect "BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE is a leak" 1 "LEAK" "$(blob dbg 'BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE')"
expect "the design-review sample literal is a leak" 1 "LEAK" "$(blob sample 'Design-review sample')"
expect "the Review Gallery literal is a leak" 1 "LEAK" "$(blob gallery 'Review Gallery')"
expect "a path that does not exist is a usage error" 2 "" "$TMP/does-not-exist"
expect "no argument is a usage error" 2 ""

# --- the bundle walk and get-task-allow need a real Mach-O ---------------------------------------
MACHO=/bin/echo
# A real Mach-O whose __TEXT carries <literal> (a literal appended after the last segment would sit
# outside anything `strings` parses, so it would not look like a real leak).
mkbin() {  # <out> <literal>
    printf '#include <stdio.h>\nint main(void){puts("%s");return 0;}\n' "$2" > "$TMP/mk.c"
    cc -o "$1" "$TMP/mk.c" >/dev/null 2>&1 && chmod +x "$1"
}
if [ "$(uname)" = Darwin ] && file -b "$MACHO" | grep -q "Mach-O" && command -v codesign >/dev/null 2>&1 \
   && command -v cc >/dev/null 2>&1 && mkbin "$TMP/probe" "probe"; then
    app="$TMP/Clean.app"; mkdir -p "$app/Contents/MacOS"
    mkbin "$app/Contents/MacOS/Clean" "ordinary release strings"
    expect "a clean .app bundle passes" 0 "clean" "$app"

    leak="$TMP/Leak.app"; mkdir -p "$leak/Contents/MacOS"
    mkbin "$leak/Contents/MacOS/Leak" "BRISTLENOSE_DEV_SIDECAR_PATH"
    expect "a leaking executable inside a .app bundle is found" 1 "LEAK" "$leak"

    skipd="$TMP/Skip.app"; mkdir -p "$skipd/Contents/MacOS" "$skipd/Contents/Resources/bristlenose-sidecar"
    mkbin "$skipd/Contents/MacOS/Skip" "ordinary release strings"
    mkbin "$skipd/Contents/Resources/bristlenose-sidecar/py" "BRISTLENOSE_DEV_SIDECAR_PATH"
    expect "the Python sidecar is deliberately not scanned" 0 "clean" "$skipd"

    helper="$TMP/Helper.app"; mkdir -p "$helper/Contents/MacOS" "$helper/Contents/Helpers"
    mkbin "$helper/Contents/MacOS/Helper" "ordinary release strings"
    mkbin "$helper/Contents/Helpers/speech" "Review Gallery"
    expect "a leak in a bundled helper is found too" 1 "LEAK" "$helper"

    empty="$TMP/Empty.app"; mkdir -p "$empty"
    expect "an .app with nothing to scan is a usage error, not a pass" 2 "" "$empty"

    # get-task-allow: sign an ad-hoc copy with the entitlement true, then false.
    printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
        '<plist version="1.0"><dict><key>com.apple.security.get-task-allow</key><true/></dict></plist>' > "$TMP/gta-true.plist"
    sed 's#<true/>#<false/>#' "$TMP/gta-true.plist" > "$TMP/gta-false.plist"
    cp "$MACHO" "$TMP/gta-true"; cp "$MACHO" "$TMP/gta-false"
    if codesign -f -s - --entitlements "$TMP/gta-true.plist" "$TMP/gta-true" >/dev/null 2>&1 \
       && codesign -f -s - --entitlements "$TMP/gta-false.plist" "$TMP/gta-false" >/dev/null 2>&1; then
        expect "get-task-allow=true is refused" 1 "get-task-allow=TRUE" "$TMP/gta-true"
        expect "get-task-allow=false is not a leak" 0 "clean" "$TMP/gta-false"
    else
        skip "get-task-allow cases" "could not ad-hoc sign a fixture here"
    fi
else
    skip "bundle walk, sidecar skip, helper scan, get-task-allow" "needs macOS with a Mach-O, codesign and cc"
fi

echo
echo "$PASS passed, $FAIL failed, $SKIP skipped"
[ "$FAIL" -eq 0 ]
