#!/bin/bash
# Pin the deployment floors so one cannot be bumped without the other noticing.
#
# WHY THIS IS A SCRIPT AND NOT A COMMENT IN project.pbxproj
# ---------------------------------------------------------
# docs/design-platform-policy.md §"Pillar 3 — macOS" carried an open action to
# "add a comment block in pbxproj explaining which scheme uses which target".
# That cannot work: Xcode regenerates project.pbxproj from its in-memory model
# on save and writes only its own /* ... */ object markers. The file today
# contains zero hand-written comments, and one added by hand would be dropped
# silently the next time anyone adds a file or edits a setting. A comment that
# disappears is worse than no comment.
#
# WHAT THE FLOORS ACTUALLY ARE (measured 3 Sep 2026 via xcodebuild, not parsed)
# ----------------------------------------------------------------------------
# Do NOT read these out of project.pbxproj. It holds several XCBuildConfiguration
# blocks and which one a scheme resolves to is decided by the build system, not
# by reading order — three successive hand-parses on 3 Sep gave three different
# answers, two of which reached a committed doc.
#
#   Bristlenose       (all 4 app schemes, Debug + Release)  15.0
#   BristlenoseTests  (Debug + Release)                     26.1
#
# KNOWN GAP, deliberately pinned rather than "fixed" here
# ------------------------------------------------------
# The test target's floor is ABOVE the app's, so the Swift suite cannot run on
# the minimum OS the product ships to. The 26.1 arrived incidentally in
# cce34d2a ("wire up BristlenoseTests target") — Xcode defaults a new test
# target to the current SDK — and no test uses a macOS 26 API. Lowering it to
# match the app is a real change with real risk, so this gate pins today's
# reality and fails on drift; it does not assert the gap is acceptable.
#
# Bumping a floor on purpose? Change the constant here in the same commit.

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/Bristlenose/Bristlenose.xcodeproj"

EXPECT_APP="15.0"
EXPECT_TESTS="26.1"

die() { printf 'check-deployment-floors: FAIL — %s\n' "$*" >&2; exit 1; }

read_floor() {  # $1 = target, $2 = configuration
  xcodebuild -showBuildSettings -project "$PROJ" -target "$1" -configuration "$2" 2>/dev/null \
    | awk '/^[[:space:]]+MACOSX_DEPLOYMENT_TARGET /{print $3; exit}'
}

fail=0
for cfg in Debug Release; do
  app=$(read_floor Bristlenose "$cfg")
  tst=$(read_floor BristlenoseTests "$cfg")

  [ -n "$app" ] || die "could not read app floor for $cfg — is Xcode installed and the project readable?"
  [ -n "$tst" ] || die "could not read test floor for $cfg"

  if [ "$app" != "$EXPECT_APP" ]; then
    printf '  app  %-8s expected %s, got %s\n' "$cfg" "$EXPECT_APP" "$app" >&2; fail=1
  fi
  if [ "$tst" != "$EXPECT_TESTS" ]; then
    printf '  test %-8s expected %s, got %s\n' "$cfg" "$EXPECT_TESTS" "$tst" >&2; fail=1
  fi
done

[ "$fail" -eq 0 ] || die "deployment floor drifted. If deliberate, update EXPECT_* here and docs/design-platform-policy.md §Pillar 3 in the same commit."

printf 'check-deployment-floors: app=%s tests=%s (both configs)\n' "$EXPECT_APP" "$EXPECT_TESTS"
