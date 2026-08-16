#!/usr/bin/env bash
# Source-level lint: menu-bar commands route to a window, they don't broadcast.
#
# This gate exists because the drift it prevents is already measured. Stage 1
# (28 Jul 2026) converted View ▸ Hide/Show Projects to `focusedSceneValue` and
# left a note saying sixteen commands still went out over
# `NotificationCenter.default`. By 15 Aug that count had grown to **nineteen** —
# new commands kept being written as broadcasts because it is the path of least
# resistance and nothing fails when you take it.
#
# A broadcast is received by every open window, so with two windows open ⌘N
# created two projects and Rename opened an editor in both. The commands are now
# `WindowCommand` cases delivered through the key window's `WindowCommandSink`
# (`WindowCommandFocus.swift`); this asserts the door stays shut.
#
# Two assertions:
#   1. `MenuCommands.swift` posts nothing. It is the menu bar; every one of its
#      commands acts on a window, an app-level model, or a dedicated scene, and
#      none of those is a broadcast.
#   2. The notification names it used to post are gone from the whole target, so
#      a converted command cannot be quietly re-wired to a surviving name.
#
# Deliberately NOT asserted: `NotificationCenter` use elsewhere. Plenty of it is
# correct — `NSWindow.didBecomeKeyNotification`, palette changes, app
# termination. The rule is about the menu bar, not the mechanism.
#
# Usage:
#   desktop/scripts/check-menu-routing.sh [<repo-root>]
#
# Exit codes:
#   0  Clean.
#   1  Violations found; prints offending lines.
#   2  Usage / environment error.

set -euo pipefail

REPO_ROOT="${1:-}"
if [ -z "$REPO_ROOT" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

SRC="$REPO_ROOT/desktop/Bristlenose/Bristlenose"
MENU="$SRC/MenuCommands.swift"

if [ ! -f "$MENU" ]; then
    echo "check-menu-routing: MenuCommands.swift not found: $MENU" >&2
    exit 2
fi

fail=0

# 1 — the menu bar posts nothing, except the two that open a dedicated scene.
#
# `openCloudImport` / `openCloudImportFixture` are received by a `Window` scene
# rather than by a project window, so there is one receiver by construction and
# the broadcast fault doesn't apply. Named individually, not waved through by a
# pattern, so a third exemption has to be argued for here.
command -v python3 >/dev/null 2>&1 || {
    echo "check-menu-routing: python3 not found on PATH" >&2
    exit 2
}

python3 - "$MENU" <<'PY' || fail=1
import re, sys

path = sys.argv[1]
allowed = {"openCloudImport", "openCloudImportFixture"}
lines = open(path, encoding="utf-8").read().splitlines()
bad = []

for i, line in enumerate(lines):
    if "NotificationCenter.default.post" not in line:
        continue
    # `name:` may be on this line or wrap onto the next couple.
    window = " ".join(lines[i:i + 3])
    match = re.search(r"name:\s*\.(\w+)", window)
    name = match.group(1) if match else "<unparsed>"
    if name not in allowed:
        bad.append((i + 1, name, line.strip()))

for lineno, name, text in bad:
    print(f"{path}:{lineno}: posts .{name} — {text}")

if bad:
    print()
    print("check-menu-routing: MenuCommands.swift posts a notification.",
          file=sys.stderr)
    print("  Every open window receives it. Add a WindowCommand case and send it",
          file=sys.stderr)
    print("  through @FocusedValue(\\.windowCommands) instead — see",
          file=sys.stderr)
    print("  WindowCommandFocus.swift and docs/design-workspace.md "
          "§\"P1's taxonomy\".", file=sys.stderr)
    sys.exit(1)
PY

# 2 — the retired names stay retired. Bare stems (no leading dot) so both the
#     declaration and any use is caught.
RETIRED="createNewProject createNewFolder addFilesToSelectedProject showWelcome
         revealTranscripts renameSelectedProject renameSelectedFolder
         deleteSelectedFolder moveSelectedProject locateSelectedProject
         stopSelectedProject removeSelectedProjectsFromSidebar
         showAIConsentSheet showMiroSheet showSessionsSwitcher applyDebugFixture"

for name in $RETIRED; do
    # Only a Notification.Name declaration counts — the same word is fine as a
    # method or enum case (`ContentView.removeSelectedProjectsFromSidebar()`,
    # `PipelineRunner.applyDebugFixture(named:)`).
    if grep -rn --include='*.swift' "static let ${name} *= *Notification\.Name" "$SRC"; then
        echo >&2
        echo "check-menu-routing: retired notification '${name}' is back." >&2
        echo "  It was a menu-bar broadcast; it belongs in WindowCommand now." >&2
        fail=1
    fi
done

if [ "$fail" -ne 0 ]; then
    exit 1
fi

echo "check-menu-routing: clean — the menu bar routes, it does not broadcast."
