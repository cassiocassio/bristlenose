#!/usr/bin/env bash
# Negative fixtures for check-deployment-floors.sh.
#
# The gate exists because the test target once sat at 26.1 above the app's 15.0 floor for weeks
# (Xcode defaults a new test target to the current SDK), so the Swift suite could not run on the
# minimum OS the product ships to, and nothing noticed. A gate that cannot fail would let that
# happen again reading "app=15.0 tests=15.0", so each branch is driven here.
#
# The gate reads floors only through `xcodebuild -showBuildSettings`, so a stub xcodebuild first on
# PATH prints controlled values: no Xcode, no project state, and the same on any machine.
#
# Usage: test-check-deployment-floors.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-deployment-floors.sh"
[ -x "$GATE" ] || [ -f "$GATE" ] || { echo "gate not found: $GATE" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-floors-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

mkdir -p "$TMP/bin"
# Answers `xcodebuild -showBuildSettings ... -target <T> -configuration <C>` from FLOOR_<T>_<C>.
# An unset variable prints nothing at all (as a missing Xcode or an unreadable project would).
cat > "$TMP/bin/xcodebuild" <<'STUB'
#!/bin/sh
target=""; config=""
while [ $# -gt 0 ]; do
    case "$1" in -target) target="$2"; shift ;; -configuration) config="$2"; shift ;; esac
    shift
done
eval "value=\${FLOOR_${target}_${config}-__unset__}"
[ "$value" = "__unset__" ] && exit 0
printf 'Build settings for action build and target %s:\n' "$target"
printf '    ARCHS = arm64\n'
printf '    MACOSX_DEPLOYMENT_TARGET = %s\n' "$value"
STUB
chmod +x "$TMP/bin/xcodebuild"

# run <want-exit> <needle> [VAR=value ...] — defaults to every floor at 15.0.
check() {  # <label> <want-exit> <needle> [VAR=value ...]
    local label="$1" want="$2" needle="$3"; shift 3
    local out rc
    out=$(env FLOOR_Bristlenose_Debug=15.0 FLOOR_Bristlenose_Release=15.0 \
              FLOOR_BristlenoseTests_Debug=15.0 FLOOR_BristlenoseTests_Release=15.0 \
              "$@" PATH="$TMP/bin:$PATH" bash "$GATE" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -5; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -5; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

echo "check-deployment-floors negative fixtures"

check "every floor at 15.0 passes" 0 "app=15.0 tests=15.0"
check "a test floor above the app's (the 26.1 regression) is refused" 1 "test Release  expected 15.0, got 26.1" FLOOR_BristlenoseTests_Release=26.1
check "a Debug test floor drift is refused too" 1 "test Debug" FLOOR_BristlenoseTests_Debug=26.1
check "an app floor bumped on its own is refused" 1 "app  Debug" FLOOR_Bristlenose_Debug=16.0
check "an app floor lowered on its own is refused" 1 "app  Release" FLOOR_Bristlenose_Release=14.0
check "both floors drifting reports both" 1 "test Release" FLOOR_Bristlenose_Release=16.0 FLOOR_BristlenoseTests_Release=26.1
check "a drift names how to change it on purpose" 1 "update EXPECT_*" FLOOR_Bristlenose_Debug=16.0
check "an unreadable app floor is a failure, not a pass" 1 "could not read app floor" FLOOR_Bristlenose_Debug= 
check "an unreadable test floor is a failure, not a pass" 1 "could not read test floor" FLOOR_BristlenoseTests_Release=

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
