#!/usr/bin/env bash
# Post-archive gate: assert no dev escape-hatch env var literals survive
# in the shipped Release Mach-O.
#
# `ServeManager.init` reads BRISTLENOSE_DEV_EXTERNAL_PORT and
# BRISTLENOSE_DEV_SIDECAR_PATH only inside `#if DEBUG`. Swift's #if is a
# true preprocessor, so a Release compile should exclude the string
# literals entirely. This script verifies that — so a future refactor
# that moves a read outside the guard fails the build, not silently
# ships a Release binary that honours dev overrides.
#
# Usage:
#   desktop/scripts/check-release-binary.sh <archive-or-app-path>
#
# Accepts either:
#   - An .xcarchive path (looks for Products/Applications/*.app)
#   - A Bristlenose.app path directly
#   - The Mach-O binary inside Contents/MacOS/<name> directly
#
# Exit codes:
#   0  Clean — no dev env-var literals in the binary.
#   1  Leak — at least one literal found; prints the offending strings.
#   2  Usage error / binary not found.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $(basename "$0") <archive-or-app-path>" >&2
    exit 2
fi

TARGET="$1"
APP=""

# Resolve the .app bundle we should scan.
if [ -d "$TARGET" ] && [ -d "$TARGET/Products/Applications" ]; then
    # xcarchive
    APP=$(find "$TARGET/Products/Applications" -maxdepth 1 -name "*.app" | head -1)
    if [ -z "$APP" ]; then
        echo "error: no .app inside $TARGET/Products/Applications" >&2
        exit 2
    fi
elif [ -d "$TARGET" ] && [[ "$TARGET" == *.app ]]; then
    APP="$TARGET"
elif [ -f "$TARGET" ]; then
    # Single binary — scan that one file.
    APP=""
    SINGLE="$TARGET"
else
    echo "error: could not locate a Mach-O executable at $TARGET" >&2
    exit 2
fi

# Skip the Python sidecar and its dylibs/sos — those are expected to
# contain many strings, and no Swift `#if DEBUG` invariant applies to
# them. This script protects the Swift shell only.
SKIP_PREFIX=""
if [ -n "$APP" ]; then
    SKIP_PREFIX="$APP/Contents/Resources/bristlenose-sidecar"
fi

# Collect every Swift-shell Mach-O inside the bundle. For a .app this
# includes the main executable plus any bundled dylibs/frameworks; for
# a Release build the list is usually just one file. For Debug the main
# exec is a stub and code lives in *.debug.dylib.
#
# Predicate: executable-bit set OR dylib suffix. Parenthesised to
# avoid find's -a/-o precedence ambiguity.
TARGETS=()
if [ -n "$APP" ]; then
    SEARCH_PATHS=()
    [ -d "$APP/Contents/MacOS" ] && SEARCH_PATHS+=("$APP/Contents/MacOS")
    [ -d "$APP/Contents/Frameworks" ] && SEARCH_PATHS+=("$APP/Contents/Frameworks")
    if [ ${#SEARCH_PATHS[@]} -eq 0 ]; then
        echo "error: $APP contains neither Contents/MacOS nor Contents/Frameworks" >&2
        exit 2
    fi
    while IFS= read -r -d '' f; do
        [ -n "$SKIP_PREFIX" ] && [[ "$f" == "$SKIP_PREFIX"* ]] && continue
        # Confirm it's actually a Mach-O — filters out executable scripts,
        # +x plists, and other non-binary files that survived the find.
        file -b "$f" | grep -q "Mach-O" || continue
        TARGETS+=("$f")
    done < <(
        find "${SEARCH_PATHS[@]}" \
            -type f \( -perm -u+x -o -name "*.dylib" -o -name "*.so" \) \
            -print0
    )
else
    TARGETS=("$SINGLE")
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    echo "error: no Mach-O files found to scan" >&2
    exit 2
fi

echo "==> Scanning ${#TARGETS[@]} Mach-O file(s) for dev env-var literals..."

LEAK_COUNT=0
for f in "${TARGETS[@]}"; do
    # -F = fixed string, `|| true` stops `set -e` killing us on zero
    # matches — we want to keep going.
    # -a scans beyond the default __TEXT section (e.g. __DATA literals).
    # The prefix entry "BRISTLENOSE_DEV_" catches future string-concat
    # refactors like "BRISTLENOSE_DEV_" + "SIDECAR_PATH" that would
    # evade exact-literal matches. No legitimate Swift code in the
    # shipped Mach-O should reference that prefix.
    hits=$(strings -a "$f" | grep -F \
        -e "BRISTLENOSE_DEV_" || true)
    if [ -n "$hits" ]; then
        LEAK_COUNT=$((LEAK_COUNT + 1))
        echo "  LEAK: $f" >&2
        echo "$hits" | sed 's/^/    /' >&2
    fi
done

if [ "$LEAK_COUNT" -gt 0 ]; then
    echo >&2
    echo "FAIL: $LEAK_COUNT binary/binaries leak dev env-var literals." >&2
    echo "A Release Mach-O must not reference BRISTLENOSE_DEV_EXTERNAL_PORT" >&2
    echo "or BRISTLENOSE_DEV_SIDECAR_PATH. These are Debug-only dev" >&2
    echo "overrides — a leak here means the shipped app could honour them." >&2
    echo "Check ServeManager.init for a read moved outside #if DEBUG." >&2
    echo >&2
    echo "Note: this script is for Release archives. Debug builds ship the" >&2
    echo "#if DEBUG branch by design; run this against a Release build only." >&2
    exit 1
fi

echo "OK: no dev env-var literals found in any scanned Mach-O."
