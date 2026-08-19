#!/usr/bin/env bash
# Peer windows: the chrome must read ONE source for which study a window is about.
#
# The 18 Aug failure this exists to stop: a window titled "IKEA with uxfriends",
# highlighting "foo" in its sidebar, and showing foo's counts in its subtitle —
# three surfaces, three answers, on a green test suite. Every surface was tested
# in isolation; nothing tested that they agree.
#
# Under the peer model `windowProject` IS `selectedProject` (selection is synced
# to the serve), so the invariant is not "which name is used" but "the serve is
# never read directly by a chrome surface". A surface that reaches past the
# selection to `serveManager.currentProjectPath` reintroduces the second source.
#
# An assertion uses `|| die`, never `&& ok` — see the root CLAUDE.md gotcha about
# `set -e` not firing on a failing left operand of `&&`.
set -euo pipefail

CV="$(dirname "$0")/../Bristlenose/Bristlenose/ContentView.swift"
die() { echo "FAIL: $*" >&2; exit 1; }

# The sync is the ONLY place chrome-side code may read the served path. The
# mount guard is content, not chrome, and is allowed.
# Allowed, and each for a stated reason:
#   - comments
#   - the sync itself (the one sanctioned reader)
#   - the mount guard (content, not chrome — it decides what to *render*, and
#     refusing to render another study's report is the point)
#   - servingProjectPath (the agent-access antenna: exposure, not identity —
#     "this project's serve is up" is genuinely a fact about the serve)
hits=$(grep -n "currentProjectPath" "$CV" \
  | grep -vE "^[0-9]+: *//" \
  | grep -vE "flatMap \{ path in" \
  | grep -vE "currentProjectPath != project.path" \
  | grep -vE "servingProjectPath|\? serveManager.currentProjectPath : nil" || true)
if [ -n "$hits" ]; then
  echo "$hits" >&2
  die "a chrome surface reads the serve directly — that is the second source the peer model deletes"
fi

# windowProject must stay a single expression. If it grows a branch, some surface
# is being special-cased again, which is how 18 Aug happened.
body=$(grep -A2 "private var windowProject" "$CV" | grep -c "selectedProject" || true)
[ "$body" -ge 1 ] || die "windowProject no longer resolves to selectedProject"

echo "window surfaces: one source, clean"
