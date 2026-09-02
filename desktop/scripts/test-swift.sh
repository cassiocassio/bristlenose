#!/usr/bin/env bash
# Run the Swift unit suite (BristlenoseTests) and report an honest verdict.
#
# This exists because NOTHING ELSE COVERS THE SWIFT TARGET. `/end-session`
# Phase 1 runs pytest and ruff; CI does not build the Swift target at all (see
# desktop/CLAUDE.md). So a Swift regression can sit red on `main` indefinitely
# while every close-out truthfully records `tests: passed`.
#
# It already did: `TabLeftPanelTests/everyCaseIsDecided()` asserted
# `Tab.allCases.count == 6` after baa1aa0e folded `codebookV2` into `codebook`
# and left the enum at five. Red for 10 commits; the sentinel written at
# 8fee4ead said tests passed (31 Aug 2026).
#
# Two traps are the reason this is a script rather than a paragraph telling you
# to run xcodebuild — a warning you have to remember is a warning you skip:
#
#   1. THE EXIT CODE OF A PIPED OR BACKGROUNDED RUN IS NOT XCODEBUILD'S. In a
#      shell without `pipefail` it is the LAST stage's status, so
#      `xcodebuild test … | tail` reports 0 on a red suite because `tail`
#      succeeded. The 31 Aug session was handed "exit code 0" by its own task
#      notification on a run that exited 65.
#   2. `grep "Test case.*failed"` MATCHES TEST NAMES. With xcodebuild's default
#      reporter a Swift Testing failure carries no `✘` and no "recorded an
#      issue" — but `failedDeclines()`, `failedRowsAreNotAnnounced()` and
#      `failedWithDiagnosticMapsToHeaderCase()` all contain the word and all go
#      on to say `passed`. A clean suite then reports six failures.
#
# The only anchor that means what it says is the verdict token `' failed on`
# — quote, space, word, trailing ` on`. This script counts those AND checks
# xcodebuild's own status, and fails if either says failure or if the two
# disagree (a disagreement means the reporter changed; do not paper over it).
#
# The sidecar ensure + freshness gate are bypassed deliberately: a unit-test
# run needs the Swift module to compile, not a current bundle, and without the
# bypass any session that touched frontend/ pays a multi-minute PyInstaller
# rebuild to run tests that never load the bundle. The two env vars are passed
# TWICE on build-for-testing — as environment AND as xcodebuild settings —
# because the Ensure phase's own shell does not see plain env (desktop/CLAUDE.md).
#
# Usage:
#   desktop/scripts/test-swift.sh [--quiet]
#
# Exit codes:
#   0  Suite green.
#   1  One or more tests failed (names printed).
#   2  Usage / environment error.
#   3  Build failed (compile break — no tests ran).

set -euo pipefail

QUIET=0
case "${1:-}" in
  --quiet) QUIET=1 ;;
  "") ;;
  *) echo "usage: $(basename "$0") [--quiet]" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../Bristlenose"
[ -d "$PROJECT_DIR" ] || { echo "not found: $PROJECT_DIR" >&2; exit 2; }
command -v xcodebuild >/dev/null 2>&1 || { echo "xcodebuild not on PATH" >&2; exit 2; }

# Concurrent runs on the same scheme wedge in teardown — the tests pass and
# xcodebuild never returns (desktop/CLAUDE.md). Warn; don't refuse, since the
# match may be an unrelated build.
if pgrep -x xcodebuild >/dev/null 2>&1; then
  echo "warning: another xcodebuild is running — concurrent runs on this scheme can hang in teardown" >&2
fi

# BN_LOG_DIR lets a caller (CI) put the logs somewhere it can upload from.
# Unset, we use a temp dir and bin it on success.
if [ -n "${BN_LOG_DIR:-}" ]; then
  LOG_DIR="$BN_LOG_DIR"; mkdir -p "$LOG_DIR"
  trap 'rc=$?; [ "$rc" -eq 0 ] || echo "logs kept: $LOG_DIR" >&2' EXIT
else
  LOG_DIR="$(mktemp -d)"
  # Keep the logs when something went wrong — the failure branches print the
  # actionable lines, but a crash-before-report needs the whole file.
  trap 'rc=$?; if [ "$rc" -eq 0 ]; then rm -rf "$LOG_DIR"; else echo "logs kept: $LOG_DIR" >&2; fi' EXIT
fi
BUILD_LOG="$LOG_DIR/build.log"
TEST_LOG="$LOG_DIR/test.log"

DEST='platform=macOS,arch=arm64'
BYPASS_A=BRISTLENOSE_SKIP_SIDECAR_ENSURE=1
BYPASS_B=BRISTLENOSE_ALLOW_STALE_SIDECAR=1

# A GitHub runner has no signing identity. Scoped to CI deliberately rather than
# applied always: locally the app is dev-signed, and the data-protection
# Keychain reads that some future test may want are entitlement-gated.
SIGNING=()
[ -n "${CI:-}" ] && SIGNING=(CODE_SIGNING_ALLOWED=NO)

[ "$QUIET" -eq 1 ] || echo "==> building test bundle"
build_rc=0
env "$BYPASS_A" "$BYPASS_B" xcodebuild build-for-testing \
    -scheme Bristlenose -configuration Debug -destination "$DEST" \
    -project "$PROJECT_DIR/Bristlenose.xcodeproj" \
    "${SIGNING[@]}" \
    "$BYPASS_A" "$BYPASS_B" > "$BUILD_LOG" 2>&1 || build_rc=$?
if [ "$build_rc" -ne 0 ]; then
  echo "BUILD FAILED (xcodebuild exit $build_rc)" >&2
  grep -E "error:" "$BUILD_LOG" | sort -u | head -20 >&2 || true
  exit 3
fi

[ "$QUIET" -eq 1 ] || echo "==> running BristlenoseTests"
test_rc=0
env "$BYPASS_A" xcodebuild test-without-building \
    -scheme Bristlenose -destination "$DEST" \
    -project "$PROJECT_DIR/Bristlenose.xcodeproj" \
    -only-testing:BristlenoseTests "${SIGNING[@]}" > "$TEST_LOG" 2>&1 || test_rc=$?

# `grep` exits 1 when it matches nothing, so under `set -e` + `pipefail` a suite
# with ZERO failures kills the script — exit 1, no output, indistinguishable from
# a red suite. This script's whole job is not to do that, and it did it anyway on
# its first green run (2 Sep 2026). `wc -l` prints 0 on empty input, so the
# counts are correct once errexit is out of the way.
set +e
passed=$(grep -oE "' passed on" "$TEST_LOG" | wc -l | tr -d ' ')
failed=$(grep -oE "' failed on" "$TEST_LOG" | wc -l | tr -d ' ')
set -e

if [ "$failed" -gt 0 ]; then
  echo "SWIFT SUITE RED — $failed failed, $passed passed" >&2
  grep -E "' failed on" "$TEST_LOG" >&2 || true
  exit 1
fi

if [ "$test_rc" -ne 0 ]; then
  # No failing verdict token, yet xcodebuild is unhappy: a crash before the
  # suite reported, or the reporter changed shape. Either way the count above
  # is not evidence of green.
  echo "xcodebuild exited $test_rc with no failing test — suite did not report cleanly" >&2
  tail -30 "$TEST_LOG" >&2
  exit 1
fi

if [ "$passed" -eq 0 ]; then
  echo "no test verdicts in output — nothing ran, or the reporter changed" >&2
  tail -30 "$TEST_LOG" >&2
  exit 1
fi

[ "$QUIET" -eq 1 ] || echo "Swift suite green — $passed passed, 0 failed"
