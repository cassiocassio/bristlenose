#!/usr/bin/env bash
# report.sh must not change a script's exit status.
#
# Every gate that sources report.sh installs `trap '_ec=$?; [ $_ec -ne 0 ] && bn_trap_fail' EXIT`.
# bn_trap_fail's last line was `[ "$_BN_DONE" = "0" ] && bn_done fail`; when the script had already
# called bn_done, that test is false, the function returned 1, and under `set -e` that final status
# replaced the script's own `exit 2`. So every gate that reports a failure and then exits with a
# specific code (usage = 2, say) exited 1 instead, found while proving check-sidecar-appstore-strings
# (9 Nov 2026), whose header promises 0, 1 and 2.
#
# Usage: test-report-exit-status.sh
# Exit:  0 the exit status survives the report trap · 1 it does not
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-report-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# A script shaped like the gates: report.sh, the same EXIT trap, a step, then <body>.
mk() {  # <name> <body>
    cat > "$TMP/$1.sh" <<SH
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$SCRIPT_DIR"
source "\$SCRIPT_DIR/report.sh"
bn_autowrap "\$0" "\$@"
trap '_bn_ec=\$?; [ "\$_bn_ec" -ne 0 ] && bn_trap_fail' EXIT
bn_meta title="exit status probe"
bn_step_start 1 Verify "probe" narrative="probe"
$2
SH
    chmod +x "$TMP/$1.sh"
}

check() {  # <label> <want-exit> <script>
    local label="$1" want="$2" script="$3" rc
    BN_REPORT=0 "$script" >/dev/null 2>&1; rc=$?
    if [ "$rc" -eq "$want" ]; then echo "  ✓ $label"; PASS=$((PASS+1))
    else echo "  ✗ $label: exit $rc, wanted $want"; FAIL=$((FAIL+1)); fi
}

echo "report.sh exit status"
mk ok2     'bn_step_ok 1 detail="fine"; bn_done ok; exit 0'
mk fail1   'bn_step_fail 1 detail="no"; bn_done fail; exit 1'
mk fail2   'bn_step_fail 1 detail="usage"; bn_done fail; exit 2'
mk fail3   'bn_step_fail 1 detail="env"; bn_done fail; exit 3'
mk abort2  'exit 2'
mk setE    'false'

check "a clean run exits 0" 0 "$TMP/ok2.sh"
check "bn_done fail then exit 1 exits 1" 1 "$TMP/fail1.sh"
check "bn_done fail then exit 2 exits 2 (not 1)" 2 "$TMP/fail2.sh"
check "bn_done fail then exit 3 exits 3" 3 "$TMP/fail3.sh"
check "an exit 2 before bn_done still exits 2" 2 "$TMP/abort2.sh"
check "a command killed by set -e exits 1" 1 "$TMP/setE.sh"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
