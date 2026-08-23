#!/usr/bin/env bash
# test-lib.sh — the shared harness for scripts/test-*.sh.
#
# WHY THIS EXISTS
#
# Five suites in scripts/ had carried a byte-identical copy of ok/bad/head_/eq,
# and desktop/scripts/ has two more copies in a third dialect. Seven is well past
# the Rule of Three, and the cost had already been paid once: the SIGTERM-safe
# restore added to test-doc-surfaces.sh after it corrupted the man page was never
# propagated to its structural twin, because there was no shared place to put it.
# Scaffolding that is copied is scaffolding whose fixes do not travel.
#
# Deliberately NOT extended to desktop/scripts/test-*.sh in the same commit.
# Those use pass/fail counters and an `ok "— message"` dash convention; converting
# them is a rename with no behavioural gain, and this file exists to stop the
# eighth copy, not to unify history.
#
# Usage:
#     . "$(dirname "$0")/test-lib.sh"
#     head_ "a section"
#     eq "label" "$expected" "$actual"
#     ok "something true" ; bad "something false"
#     finish            # prints the summary, exits 0/1
#
# guard_tracked <path> — restore a tracked file on ANY exit path, including a
# signal. Use it in any suite that mutates the working tree to prove a gate
# fires. A test that damages the tree when interrupted is worse than no test,
# because the damage then reads as a finding.

PASS=0
FAIL=0

ok()    { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad()   { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; FAIL=$((FAIL+1)); }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }
eq()    { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 — expected '$2', got '$3'"; fi; }

# meta_check — prove eq() can actually fail. A suite whose assertions cannot
# fail is decoration, and the check for that must not itself inflate the count:
# the deliberate failure runs in a subshell, so its FAIL++ is lost, and an
# earlier version decremented anyway — which meant a suite with exactly one REAL
# failure reported zero and exited green.
meta_check() {
    head_ "meta"
    local before=$FAIL out
    out=$(eq "deliberate" ok bad 2>&1)
    case "$out" in
        *"expected 'ok', got 'bad'"*) ok "eq() reports a real mismatch" ;;
        *) bad "eq() cannot fail — this suite is decoration" ;;
    esac
    [ "$FAIL" -eq "$before" ] || bad "harness leaked the deliberate failure into the count"
}

# guard_tracked <repo-relative path>...
guard_tracked() {
    _GUARDED="$*"
    # shellcheck disable=SC2064  # expand _GUARDED now, deliberately
    trap "git checkout -- $_GUARDED 2>/dev/null || true" EXIT INT TERM
}

finish() {
    printf '\n\033[1m%d passed, %d failed\033[0m\n\n' "$PASS" "$FAIL"
    [ "$FAIL" -eq 0 ]
}
