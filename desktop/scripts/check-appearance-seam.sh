#!/usr/bin/env bash
# Source-level lint: keep light/dark appearance on its single seam.
#
# The app applies the Settings ▸ Appearance preference once, app-wide, via
# `NSApp.appearance` (AppAppearance.beginApplying, called from AppDelegate).
# Every window, panel, alert, menu and popover inherits it.
#
# This gate exists because the bug it prevents already happened: the
# preference mapping was written out THREE times and applied per-window, so
# every non-window surface — and seven auxiliary Window scenes that had never
# opted in — silently followed the *system* theme instead. It is invisible
# whenever the app preference agrees with System Settings, which is how it
# survived from the Settings pane's introduction to 2 Aug 2026.
#
# Four assertions:
#   1. `NSAppearance(named:` appears only in AppAppearance.swift — nobody
#      re-derives the "light"/"dark"/"auto" mapping a fourth time.
#   2. `forKey: "appearance"` appears only in AppAppearance.swift — the raw
#      default is read through one accessor. (`@AppStorage("appearance")` is
#      fine and deliberately not matched; it's the SwiftUI binding, not a
#      second mapping.)
#   3. Every NSSavePanel/NSOpenPanel creation is followed by
#      `adoptHostAppearance` within a short window. Panels are powerbox-hosted
#      under App Sandbox — the one surface where inheritance crosses a process
#      boundary, so it is stated rather than trusted.
#   4. AppDelegate still calls `AppAppearance.beginApplying()`. Delete that and
#      every assertion above still passes while nothing is themed.
#
# Scans `.swift` under desktop/Bristlenose/Bristlenose/, excluding
# `*Tests.swift`. Scope-limited by intent — don't scan v0.1-archive or Python.
#
# Usage:
#   desktop/scripts/check-appearance-seam.sh [<repo-root>]
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
if [ ! -d "$SRC" ]; then
    echo "check-appearance-seam: source dir not found: $SRC" >&2
    exit 2
fi

command -v python3 >/dev/null 2>&1 || {
    echo "check-appearance-seam: python3 not found on PATH" >&2
    exit 2
}

python3 - "$SRC" <<'PY'
import os, re, sys

src = sys.argv[1]
owner = "AppAppearance.swift"          # the one file allowed to map the pref
panel_window = 25                      # lines a panel has to adopt appearance
violations = []

files = []
for root, _, names in os.walk(src):
    for n in sorted(names):
        if n.endswith(".swift") and not n.endswith("Tests.swift"):
            files.append(os.path.join(root, n))

panel_re = re.compile(r"\b(NSSavePanel|NSOpenPanel)\s*\(\s*\)")

for path in files:
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    for i, line in enumerate(lines, start=1):
        code = line.split("//", 1)[0]      # ignore prose in comments

        # 1 + 2: the mapping and the raw default belong to one file.
        if name != owner:
            if "NSAppearance(named:" in code:
                violations.append(
                    (path, i, "re-derives the appearance mapping — use AppAppearance.current")
                )
            if 'forKey: "appearance"' in code:
                violations.append(
                    (path, i, 'reads the raw default — use AppAppearance.preference')
                )

        # 3: panels state their appearance explicitly (powerbox crosses a
        #    process boundary, so inheritance is not trusted there).
        if panel_re.search(code):
            window = "".join(lines[i - 1 : i - 1 + panel_window])
            if "adoptHostAppearance" not in window:
                violations.append(
                    (path, i, f"panel created without adoptHostAppearance() within {panel_window} lines")
                )

# 4: the seam is actually installed.
app_delegate = os.path.join(src, "BristlenoseApp.swift")
if not os.path.exists(app_delegate):
    violations.append((app_delegate, 0, "BristlenoseApp.swift missing — cannot verify the seam is installed"))
else:
    with open(app_delegate, encoding="utf-8") as fh:
        body = fh.read()
    if "AppAppearance.beginApplying()" not in body:
        violations.append(
            (app_delegate, 0, "AppDelegate no longer calls AppAppearance.beginApplying() — nothing applies the preference")
        )

if violations:
    print("check-appearance-seam: FAIL")
    print()
    for path, line, why in violations:
        rel = os.path.relpath(path, os.path.dirname(os.path.dirname(os.path.dirname(src))))
        where = f"{rel}:{line}" if line else rel
        print(f"  {where}: {why}")
    print()
    print("Appearance is applied once, app-wide, via NSApp.appearance.")
    print("See desktop/CLAUDE.md §Appearance before adding a per-surface override.")
    sys.exit(1)

print(f"check-appearance-seam: OK ({len(files)} files scanned)")
PY
