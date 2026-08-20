#!/usr/bin/env bash
# Independent windows: a window's serve must be ITS OWN, and app-level facts
# must not be read off one.
#
# The 18 Aug failure this exists to stop: a window titled "IKEA with uxfriends",
# highlighting "foo" in its sidebar, and showing foo's counts in its subtitle —
# three surfaces, three answers, on a green test suite. Every surface was tested
# in isolation; nothing tested that they agree.
#
# **Repointed 20 Aug 2026, not retired.** The peer model's invariant ("no chrome
# surface reads the serve directly") died with the shared serve: under Stage 3b
# every window reads a serve, and the question is *whose*. Deleting the gate at
# the moment the window model became MORE plural would have left the class it
# guards unwatched — the class that shipped twice in three days (`9f4183af`,
# `29f70e33`). Two invariants replace the old one.
#
# An assertion uses `|| die`, never `&& ok` — see the root CLAUDE.md gotcha about
# `set -e` not firing on a failing left operand of `&&`.
set -euo pipefail

CV="$(dirname "$0")/../Bristlenose/Bristlenose/ContentView.swift"
APP="$(dirname "$0")/../Bristlenose/Bristlenose/BristlenoseApp.swift"
die() { echo "FAIL: $*" >&2; exit 1; }

# 1. `serveManager` must stay OPTIONAL and fleet-derived. A window with no study
#    has no serve; making it non-optional is how a "null manager" or a
#    window-id-keyed idle instance creeps back in, and either is a second source
#    of state by another name.
grep -q "var serveManager: ServeManager? {" "$CV" \
  || die "ContentView.serveManager is no longer an optional fleet-derived property"
grep -q "selectedProject.map { serveFleet.manager(for: \$0.id) }" "$CV" \
  || die "ContentView.serveManager no longer resolves through the fleet"

# 2. No ServeManager may be injected app-wide. One shared manager in the
#    environment IS the shared serve, whatever the window model says.
if grep -nE "\.environmentObject\(serveManager\)" "$APP" >&2; then
  die "a ServeManager is injected app-wide — that is the shared serve returning"
fi

# 3. App-level facts are read off the fleet, never off a window's serve. Both
#    were misclassified as per-serve during the 3b plan and caught by review:
#    mcpMounted is per-BUILD, and the handshake is ONE global file whose
#    per-instance delete edges would let one project erase another's exposure.
for fact in mcpMounted handshakeProjectPath; do
  if grep -nE "serveManager\??\.$fact" "$CV" >&2; then
    die "$fact is an app-level fact and must be read from serveFleet, not a window's serve"
  fi
done

# 4. The peer-era cross-window selection sync must stay deleted. It forced every
#    window onto one study, which is the constraint 3b removes.
if grep -rn "SelectionSync" "$(dirname "$0")/../Bristlenose" >&2; then
  die "SelectionSync is back — windows are being forced onto one study again"
fi

echo "window surfaces: per-window serve, app-level facts on the fleet — clean"
