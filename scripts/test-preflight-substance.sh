#!/usr/bin/env bash
# test-preflight-substance.sh — drive the preflight's Substance decisions with
# synthetic input. No git repositories manufactured, no network, no venv.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$(dirname "$0")/test-lib.sh"

# Source the REAL function — no duplicate to drift. The lib guard returns before
# any check runs, so this costs nothing and cannot test a fiction.
CHECK_RELEASE_READY_LIB=1 . "$ROOT/scripts/check-release-ready.sh"
command -v verdict_shippable >/dev/null || {
    echo "verdict_shippable not exported by check-release-ready.sh" >&2; exit 1; }

head_ "verdict_shippable — the release / rebuild / nothing decision"
eq "no tag at all"                      no-tag  "$(verdict_shippable '' '' '')"
eq "no tag, even with diffs"            no-tag  "$(verdict_shippable '' ' 3 files' ' 2 files')"
eq "wheel changed → a real release"     release "$(verdict_shippable v0.27.0 ' 5 files changed' '')"
eq "wheel + desktop → still a release"  release "$(verdict_shippable v0.27.0 ' 5 files' ' 2 files')"
eq "desktop only → rebuild, not release" rebuild "$(verdict_shippable v0.27.0 '' ' 8 files changed')"
eq "nothing anywhere → do not bump"     nothing "$(verdict_shippable v0.27.0 '' '')"

head_ "worst cases — whitespace-only diff output must not read as change"
eq "empty-string wheel diff"            nothing "$(verdict_shippable v0.27.0 '' '')"
eq "wheel diff is a single space"       release "$(verdict_shippable v0.27.0 ' ' '')"

head_ "the 0.27.0 scenario, replayed"
# A fortnight of desktop work, wheel untouched: the row must say REBUILD, because
# calling it a release manufactures a version with nothing in it, and calling it
# nothing loses a Mac build that is genuinely owed.
eq "desktop-only fortnight"             rebuild "$(verdict_shippable v0.27.0 '' ' 41 files changed, 900 insertions')"

head_ "verdict_main_ci — main's own last CI verdict (incident 42)"
command -v verdict_main_ci >/dev/null || bad "verdict_main_ci not exported"
_jobs() { printf '%s\t%s\n' "$@"; }
eq "no run, no jobs"                    none  "$(printf '' | verdict_main_ci 'mypy ' 0)"
eq "all green"                          green "$(_jobs ruff success 'test (3.12, ubuntu-latest)' success | verdict_main_ci 'mypy ' 0)"
eq "only the soft job red is green"     green "$(_jobs ruff success mypy failure | verdict_main_ci 'mypy ' 0)"
eq "skipped and neutral are not red"    green "$(_jobs e2e skipped notes neutral | verdict_main_ci 'mypy ' 0)"
# The 0.35.0 scenario, replayed: four blocking reds, mypy too, HEAD unpushed.
_r=$(_jobs 'test (3.12, ubuntu-latest)' failure mypy failure ruff failure ratchet failure \
     'build (macos-26)' failure | verdict_main_ci 'mypy ' 0)
eq "0.35.0: unpushed HEAD fails, mypy not named" \
   "red-unverified:test (3.12, ubuntu-latest); ruff; ratchet; build (macos-26)" "$_r"
eq "pushed HEAD downgrades to superseded" "red-superseded:ruff" "$(_jobs ruff failure | verdict_main_ci 'mypy ' 1)"
eq "cancelled counts as red"            "red-unverified:e2e" "$(_jobs e2e cancelled | verdict_main_ci '' 0)"
eq "timed_out counts as red"            "red-unverified:e2e" "$(_jobs e2e timed_out | verdict_main_ci '' 0)"
eq "an empty soft set makes mypy red"   "red-unverified:mypy" "$(_jobs mypy failure | verdict_main_ci '' 0)"
eq "a soft name is matched whole"       "red-unverified:mypy-strict" "$(_jobs mypy-strict failure | verdict_main_ci 'mypy ' 0)"

head_ "meta — the assertions can fail"
_r=$(eq "deliberate" release nothing 2>&1)
case "$_r" in *"expected 'release', got 'nothing'"*) ok "eq() reports a real mismatch" ;;
             *) bad "eq() cannot fail — suite is decoration" ;; esac
[ "$FAIL" -eq 0 ] || bad "harness leaked the deliberate failure into the count"

finish
