#!/usr/bin/env bash
# test-verify-channels.sh — drive verify-channels.sh's decision layer with
# synthetic input, including every failure shape a real release can produce.
#
# WHY THIS SHAPE
#
# The network round trip is not the risk; the DECISION is. So verify-channels.sh
# splits `probe` (I/O) from `verdict_*` (pure), and this suite sources the script
# with VERIFY_CHANNELS_LIB=1 and drives only the pure half. No network, no
# mocking, runs in milliseconds. Same split desktop/scripts/test-upload-dmg.sh
# already uses for swap_decision / retention_plan.
#
# Every assertion is proven to fail on its own violation — a test that cannot
# fail is decoration (docs/design-test-philosophy.md).

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PASS=0; FAIL=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; FAIL=$((FAIL+1)); }
head_(){ printf '\n\033[1m%s\033[0m\n' "$1"; }

# eq <label> <expected> <actual>
eq() {
    if [ "$2" = "$3" ]; then ok "$1"
    else bad "$1 — expected '$2', got '$3'"; fi
}

VERIFY_CHANNELS_LIB=1 . "$ROOT/scripts/verify-channels.sh"

head_ "verdict_http — the tri-state that stops a network fault reading as 'not published'"
eq "200 published"              ok          "$(verdict_http 200)"
eq "201 published"              ok          "$(verdict_http 201)"
eq "204 published"              ok          "$(verdict_http 204)"
eq "301 redirect is a hit"      ok          "$(verdict_http 301)"
eq "302 redirect is a hit"      ok          "$(verdict_http 302)"
eq "308 redirect is a hit"      ok          "$(verdict_http 308)"
eq "404 genuinely absent"       bad         "$(verdict_http 404)"
eq "410 genuinely gone"         bad         "$(verdict_http 410)"
eq "000 conn failure ≠ absent"  unreachable "$(verdict_http 000)"
eq "empty ≠ absent"             unreachable "$(verdict_http '')"
eq "500 ≠ absent"               unreachable "$(verdict_http 500)"
eq "403 rate-limited ≠ absent"  unreachable "$(verdict_http 403)"
eq "429 throttled ≠ absent"     unreachable "$(verdict_http 429)"
eq "502 gateway ≠ absent"       unreachable "$(verdict_http 502)"
eq "garbage ≠ absent"           unreachable "$(verdict_http 'curl: (6)')"

head_ "verdict_contains — nothing fetched is not the same as nothing found"
eq "version present"            ok          "$(verdict_contains 'v0.28.0 shipped' '0.28.0')"
eq "version absent"             bad         "$(verdict_contains 'v0.27.0 shipped' '0.28.0')"
eq "EMPTY body is unreachable"  unreachable "$(verdict_contains '' '0.28.0')"
eq "empty needle is unreachable" unreachable "$(verdict_contains 'anything' '')"
eq "multiline body"             ok          "$(verdict_contains 'a
0.28.0
b' '0.28.0')"

head_ "verdict_contains — the substring trap (a longer version must not satisfy a shorter one)"
eq "0.28.1 vs page naming only 0.28.10"  bad "$(verdict_contains 'released 0.28.10 today' '0.28.1')"
eq "0.2 must not match 0.28.0"           bad "$(verdict_contains 'released 0.28.0' '0.2')"
eq "0.28.0 vs 10.28.0"                   bad "$(verdict_contains 'released 10.28.0' '0.28.0')"
eq "exact still matches"                 ok  "$(verdict_contains 'released 0.28.1 today' '0.28.1')"
eq "matches at end of body"              ok  "$(verdict_contains 'released 0.28.1' '0.28.1')"
eq "matches in a tarball name"           ok  "$(verdict_contains 'bristlenose-0.28.1.tar.gz' 'bristlenose-0.28.1.tar.gz')"

head_ "verdict_absent — 0.27.0's real website failure"
eq "abandoned version present"  bad         "$(verdict_absent 'changelog names 0.26.0' '0.26.0')"
eq "abandoned version gone"     ok          "$(verdict_absent 'changelog names 0.27.0' '0.26.0')"
eq "empty body unreachable"     unreachable "$(verdict_absent '' '0.26.0')"
eq "no abandoned version given" ok          "$(verdict_absent 'anything' '')"
eq "0.26.0 gone but 0.26.01 present is still GONE" ok "$(verdict_absent 'names 0.26.01' '0.26.0')"

head_ "verdict_json_field — an API that answers nothing is not an API that answers no"
eq "field matches"              ok          "$(verdict_json_field 'v0.28.0' 'v0.28.0')"
eq "field differs"              bad         "$(verdict_json_field 'v0.27.0' 'v0.28.0')"
eq "EMPTY is unreachable"       unreachable "$(verdict_json_field '' 'v0.28.0')"
eq "literal null unreachable"   unreachable "$(verdict_json_field 'null' 'v0.28.0')"

head_ "verdict_gate — expired auth must not read as a human approval"
eq "query failed"               unreachable "$(verdict_gate QUERY_FAILED)"
eq "EMPTY ≠ gate cleared"       unreachable "$(verdict_gate '')"
eq "explicit NONE is cleared"   cleared     "$(verdict_gate NONE)"
eq "a pending deployment"       held        "$(verdict_gate 'pypi')"

head_ "rollup — unverified is not verified"
eq "all ok"                     0 "$(rollup ok ok ok)"
eq "one bad"                    1 "$(rollup ok bad ok)"
eq "one unreachable"            1 "$(rollup ok unreachable ok)"
eq "all unreachable"            1 "$(rollup unreachable unreachable)"
eq "single ok"                  0 "$(rollup ok)"

head_ "meta — the assertions can actually fail"
# The deliberate failure runs inside $( ), i.e. a SUBSHELL — so its FAIL++ is
# lost and there is nothing to discount. An earlier draft decremented anyway,
# which meant a suite with exactly one REAL failure reported zero and exited
# green. A harness that can hide a failure is worse than no harness.
_r=$(eq "deliberate failure" ok bad 2>&1); case "$_r" in
    *"expected 'ok', got 'bad'"*) ok "eq() reports a real mismatch" ;;
    *) bad "eq() cannot fail — the suite is decoration" ;;
esac
[ "$FAIL" -eq 0 ] || bad "harness leaked the deliberate failure into the count"

head_ "argument validation — the fold reads the wrong transcript on a typo"
for v in "0.28.O" "../../tmp" "" "latest" "v0.28.0"; do
    out=$(bash "$ROOT/scripts/verify-channels.sh" "$v" 2>&1); rc=$?
    if [ "$rc" = "2" ]; then ok "refused '$v' (exit 2)"
    else bad "accepted '$v' (exit $rc) — should be a usage error"; fi
done
out=$(bash "$ROOT/scripts/verify-channels.sh" --bogus 2>&1); rc=$?
[ "$rc" = "2" ] && ok "refused unknown flag" || bad "accepted unknown flag (exit $rc)"

printf '\n\033[1m%d passed, %d failed\033[0m\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
