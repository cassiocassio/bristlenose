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
# Matches the fleet's stand-in too: after the crossing a returning shared serve
# would be spelled `.environmentObject(serveFleet.frontedOrIdle)`, which the
# original pattern missed — so this assertion passed vacuously the moment it
# was written.
if grep -nE "\.environmentObject\((serveManager|.*frontedOrIdle|.*\.fronted)\)" "$APP" >&2; then
  die "a single ServeManager is injected app-wide — that is the shared serve returning"
fi

# 3. App-level facts are read off the fleet, never off a window's serve. Both
#    were misclassified as per-serve during the 3b plan and caught by review:
#    mcpMounted is per-BUILD, and the handshake is ONE global file whose
#    per-instance delete edges would let one project erase another's exposure.
for fact in mcpMounted handshakeProjectPaths; do
  if grep -nE "serveManager\??\.$fact" "$CV" >&2; then
    die "$fact is an app-level fact and must be read from serveFleet, not a window's serve"
  fi
done

# 4. The peer-era cross-window selection sync must stay deleted. It forced every
#    window onto one study, which is the constraint 3b removes.
# Scoped to the SOURCE dirs, not the whole Bristlenose tree. That tree carries
# desktop/Bristlenose/build/ and Resources/ — 2.4 GB and 7,596 files of build
# output, ffmpeg and models — so the unscoped walk cost 22.8s of this gate's 23s
# runtime while asserting nothing about source. It was also wrong in principle:
# a stray match inside a build artefact would have failed the gate on clean
# source. Measured 23s -> 0.1s, 23 Aug 2026.
_SRC="$(dirname "$0")/../Bristlenose/Bristlenose"
_TESTS="$(dirname "$0")/../Bristlenose/BristlenoseTests"
if grep -rn --include='*.swift' "SelectionSync" "$_SRC" "$_TESTS" >&2; then
  die "SelectionSync is back — windows are being forced onto one study again"
fi

# 5. The app-level facts must be WRITTEN, not just declared and read. Both
#    shipped with no writer at all: `mcpMounted` was permanently false, which
#    hides Turn On Agent Access entirely, and `handshakeProjectPath` permanently
#    nil, so the antenna could never go solid for a study an agent could reach.
#    A property that is read but never assigned reads exactly like a truthful
#    "no", which is why a green suite never noticed.
#
#    THESE TWO STRINGS ARE LOAD-BEARING AND MUST MOVE WITH ANY RENAME. They are
#    exact source lines, so a rename does not adapt them — it makes them
#    unmatchable, and the gate then fails permanently on correct code. That
#    happened: `037b371e` (20 Aug 2026) made the handshake scope plural,
#    `handshakeProjectPath` -> `handshakeProjectPaths`, and this assertion kept
#    the singular. It went unnoticed for two days only because nothing ran a
#    full build in between; the first release build after it failed pre-flight
#    naming a defect that was not there. Failing loud beats the export-CSS
#    class, which fails silent — but it is the same rename hazard.
FLEET="$(dirname "$0")/../Bristlenose/Bristlenose/ServeFleet.swift"
grep -q "if mounted != mcpMounted { mcpMounted = mounted }" "$FLEET" \
  || die "ServeFleet.mcpMounted has no writer — Turn On Agent Access would be hidden everywhere"
grep -q "if paths != handshakeProjectPaths { handshakeProjectPaths = paths }" "$FLEET" \
  || die "ServeFleet.handshakeProjectPaths has no writer — the antenna could never go solid"

echo "window surfaces: per-window serve, app-level facts written and on the fleet — clean"
