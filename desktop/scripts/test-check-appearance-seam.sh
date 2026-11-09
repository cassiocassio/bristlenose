#!/usr/bin/env bash
# Negative fixtures for check-appearance-seam.sh.
#
# The bug the gate prevents already happened and was invisible for weeks (the preference was
# mapped three times and applied per window, so every non-window surface followed the system
# theme). A gate that cannot fail would let it back in while reading OK, so each of its four
# assertions is driven red here against a scratch repo root, and the exemptions (the owner file,
# comments, a SwiftUI binding, *Tests.swift) are shown to be the only reasons a line passes.
#
# Usage: test-check-appearance-seam.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-appearance-seam.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-appearance-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# A scratch root that satisfies all four assertions: the owner file maps the preference, and the
# app file installs the seam. Extra files are added by the caller. Echoes the root.
base() {  # <name>
    local src="$TMP/$1/desktop/Bristlenose/Bristlenose"
    mkdir -p "$src"
    printf '%s\n' 'let a = NSAppearance(named: .aqua)' 'let p = d.string(forKey: "appearance")' > "$src/AppAppearance.swift"
    printf '%s\n' 'func applicationDidFinishLaunching() { AppAppearance.beginApplying() }' > "$src/BristlenoseApp.swift"
    echo "$TMP/$1"
}
put() {  # <root> <file> <content>
    printf '%s\n' "$3" > "$1/desktop/Bristlenose/Bristlenose/$2"
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

echo "check-appearance-seam negative fixtures"

r=$(base clean)
expect "a root that satisfies all four assertions is OK" 0 "OK" "$r"

r=$(base remap); put "$r" Other.swift 'let a = NSAppearance(named: .darkAqua)'
expect "re-deriving the mapping outside the owner file is a violation" 1 "re-derives the appearance mapping" "$r"

r=$(base rawdefault); put "$r" Other.swift 'let p = d.string(forKey: "appearance")'
expect "reading the raw default outside the owner file is a violation" 1 "reads the raw default" "$r"

r=$(base binding); put "$r" Other.swift '@AppStorage("appearance") var appearance = "auto"'
expect "a SwiftUI @AppStorage binding is not a second mapping" 0 "OK" "$r"

r=$(base comment); put "$r" Other.swift '// historically NSAppearance(named: .aqua) was written here'
expect "a mention in a comment is ignored" 0 "OK" "$r"

r=$(base tests); put "$r" OtherTests.swift 'let a = NSAppearance(named: .aqua)'
expect "a *Tests.swift file is not scanned" 0 "OK" "$r"

r=$(base panel); put "$r" Other.swift 'let panel = NSOpenPanel()'
expect "a panel with no adoptHostAppearance is a violation" 1 "panel created without adoptHostAppearance" "$r"

r=$(base panelok); put "$r" Other.swift 'let panel = NSSavePanel()
panel.adoptHostAppearance(host)'
expect "a panel that adopts the host appearance passes" 0 "OK" "$r"

r=$(base panelfar)
{ echo 'let panel = NSSavePanel()'; for _ in $(seq 1 30); do echo '// filler'; done; echo 'panel.adoptHostAppearance(host)'; } \
    > "$r/desktop/Bristlenose/Bristlenose/Other.swift"
expect "adoption beyond the 25-line window does not count" 1 "panel created without adoptHostAppearance" "$r"

r=$(base noseam); put "$r" BristlenoseApp.swift 'func applicationDidFinishLaunching() { }'
expect "an app that no longer calls beginApplying is a violation" 1 "no longer calls AppAppearance.beginApplying()" "$r"

r=$(base noapp); rm "$r/desktop/Bristlenose/Bristlenose/BristlenoseApp.swift"
expect "a missing BristlenoseApp.swift is a violation, not a pass" 1 "BristlenoseApp.swift missing" "$r"

mkdir -p "$TMP/nosrc"
expect "a root with no source directory is a usage error" 2 "source dir not found" "$TMP/nosrc"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
