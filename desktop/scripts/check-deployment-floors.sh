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
#   BristlenoseTests  (Debug + Release)                     15.0
#   BAExtension       (Debug + Release; only once the target exists)  26.0
#
# THE EXTENSION'S FLOOR IS 26.0, ABOVE THE APP'S, ON PURPOSE
# ----------------------------------------------------------
# Background Assets' managed packs and `AssetPackManager` are macOS 26.0 API and the system
# refuses to load an extension above its own version. A template target defaults to the SDK
# (27.2 here), which would not load on macOS 26.x, so this pins it. The app's own floor stays
# 15.0: on macOS 15 the extension is simply never launched (the app never asks for it). The
# check is skipped while no BAExtension target exists, so it cannot fail before there is
# anything to check.
#
# THE TWO FLOORS ARE EQUAL, AND THAT IS WHAT THIS GATE NOW PROTECTS
# ----------------------------------------------------------------
# The test target sat at 26.1 from cce34d2a ("wire up BristlenoseTests target"),
# because Xcode defaults a new test target to the current SDK. That put it ABOVE
# the app's floor, so the Swift suite could not run on the minimum OS the product
# ships to. Lowered to 15.0 on 25 Sep 2026 after it was proven on real guests:
# the suite builds and runs on macOS 15.7.3 (Xcode 26.3) and 26.6.2 (Xcode 27.0),
# and its first run on 15 found a sidebar defect no 26/27 machine could show.
# A test target above the app's floor is the regression this gate now catches.
#
# Bumping a floor on purpose? Change the constant here in the same commit.

set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/Bristlenose/Bristlenose.xcodeproj"

EXPECT_APP="15.0"
EXPECT_TESTS="15.0"
EXPECT_EXT="26.0"

die() { printf 'check-deployment-floors: FAIL — %s\n' "$*" >&2; exit 1; }

read_floor() {  # $1 = target, $2 = configuration
  xcodebuild -showBuildSettings -project "$PROJ" -target "$1" -configuration "$2" 2>/dev/null \
    | awk '/^[[:space:]]+MACOSX_DEPLOYMENT_TARGET /{print $3; exit}'
}

# Whether the extension target is in the project. BN_FLOORS_EXT=present|absent is for the
# self-test; otherwise it is read from the project file (existence only: values are asked of
# xcodebuild, as above).
ext_target_exists() {
  case "${BN_FLOORS_EXT:-}" in present) return 0 ;; absent) return 1 ;; esac
  grep -q 'name = BAExtension;' "$PROJ/project.pbxproj"
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
  if ext_target_exists; then
    ext=$(read_floor BAExtension "$cfg")
    [ -n "$ext" ] || die "could not read extension floor for $cfg"
    if [ "$ext" != "$EXPECT_EXT" ]; then
      printf '  ext  %-8s expected %s, got %s\n' "$cfg" "$EXPECT_EXT" "$ext" >&2; fail=1
    fi
  fi
done

[ "$fail" -eq 0 ] || die "deployment floor drifted. If deliberate, update EXPECT_* here and docs/design-platform-policy.md §Pillar 3 in the same commit."

if ext_target_exists; then
  printf 'check-deployment-floors: app=%s tests=%s ext=%s (both configs)\n' "$EXPECT_APP" "$EXPECT_TESTS" "$EXPECT_EXT"
else
  printf 'check-deployment-floors: app=%s tests=%s (both configs; no extension target yet)\n' "$EXPECT_APP" "$EXPECT_TESTS"
fi
