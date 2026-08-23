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

head_ "meta — the assertions can fail"
_r=$(eq "deliberate" release nothing 2>&1)
case "$_r" in *"expected 'release', got 'nothing'"*) ok "eq() reports a real mismatch" ;;
             *) bad "eq() cannot fail — suite is decoration" ;; esac
[ "$FAIL" -eq 0 ] || bad "harness leaked the deliberate failure into the count"

finish
