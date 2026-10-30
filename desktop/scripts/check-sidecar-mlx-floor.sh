#!/usr/bin/env bash
# Fail if the sidecar's MLX was built for a macOS newer than the app's floor.
#
# Usage:
#   desktop/scripts/check-sidecar-mlx-floor.sh <sidecar-dir>
#   (the directory holding bristlenose-sidecar and _internal/)
#
# WHY THIS EXISTS
# ---------------
# MLX is published once per macOS target. pip takes the newest tag the BUILD HOST
# accepts, so a macOS 27 build machine shipped the macosx_26_0 wheels (minos 26.2) in
# an app whose floor is 15.0. On a clean macOS 15.7.7 guest the first
# `import mlx_whisper` aborted in mlx::core::metal::Device::Device() (SIGTRAP, a native
# abort no `except` catches), so the Whisper status probe, every Retry and `run`
# died with it: a red pill that never cleared (30 Oct 2026). The same bundle with only
# the MLX files swapped for the macosx_15_0 wheels answered and exited 0.
#
# WHAT IT CHECKS, AND WHAT IT DELIBERATELY DOES NOT
# -------------------------------------------------
#   1. the WHEEL Tag of mlx and mlx-metal, from the dist-info the bundle ships, is
#      macosx_<=floor. This is the receipt: it names what pip chose.
#   2. minos of mlx/core*.so and mlx/lib/libmlx.dylib is <= the floor. This is the
#      fact, read from the binary the app will load.
# It does NOT ask every Mach-O in the bundle for minos <= floor. 65 of 315 exceed 15.0
# today (Python 26.0, libssl, libsqlite3, liblzma 27.0 ...) and run fine on macOS 15:
# a minos above the floor is only fatal where the code calls an API the older OS lacks,
# which Metal initialisation does and a CPython built on a newer host does not.
#
# The floor is read from check-deployment-floors.sh (EXPECT_APP), the one place that
# pins the app's deployment target.
#
# Exit 0 = pass, 1 = MLX is newer than the floor, 2 = usage / unreadable bundle.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SIDECAR="${1:-}"
[ -d "$SIDECAR/_internal" ] || { echo "usage: check-sidecar-mlx-floor.sh <sidecar-dir>" >&2; exit 2; }

FLOOR="$(sed -n 's/^EXPECT_APP="\([0-9.]*\)".*/\1/p' "$HERE/check-deployment-floors.sh" | head -1)"
[ -n "$FLOOR" ] || { echo "error: could not read EXPECT_APP from check-deployment-floors.sh" >&2; exit 2; }

# newer A B — true when version A is greater than version B.
# Both sides are normalised to N.N first: `sort -V` ranks 15.0 above 15, so a floor written
# "15" would fail every bundle.
norm() { case "$1" in *.*) printf '%s' "$1" ;; *) printf '%s.0' "$1" ;; esac; }
newer() {
    local a b; a="$(norm "$1")"; b="$(norm "$2")"
    [ "$a" != "$b" ] && [ "$(printf '%s\n%s\n' "$a" "$b" | sort -V | tail -1)" = "$a" ]
}

fail=0
bad() { echo "  FAIL $1" >&2; fail=1; }

shopt -s nullglob
for pkg in mlx mlx_metal; do
    wheels=("$SIDECAR"/_internal/"$pkg"-*.dist-info/WHEEL)
    if [ "${#wheels[@]}" -eq 0 ]; then
        bad "$pkg: no dist-info/WHEEL in the bundle (cannot say which wheel shipped)"
        continue
    fi
    # Every dist-info, not the first: a stale mlx-0.30.0.dist-info beside the real one would
    # otherwise decide the verdict (found in review, 30 Oct 2026).
    for wheel in "${wheels[@]}"; do
        tags="$(sed -n 's/^Tag: //p' "$wheel")"
        [ -n "$tags" ] || { bad "$pkg: $(basename "$(dirname "$wheel")") has no Tag lines"; continue; }
        while IFS= read -r tag; do
            plat="${tag##*-}"
            case "$plat" in
                macosx_*_arm64|macosx_*_universal2)
                    ver="$(echo "$plat" | sed -E 's/^macosx_([0-9]+)_([0-9]+)_.*/\1.\2/')"
                    if newer "$ver" "$FLOOR"; then
                        bad "$pkg wheel is $plat, built for macOS $ver; the app's floor is $FLOOR"
                    fi ;;
                *) bad "$pkg: unrecognised platform tag '$plat'" ;;
            esac
        done <<< "$tags"
    done
done

macho_minos() {
    otool -l "$1" 2>/dev/null | awk '
        /LC_BUILD_VERSION/ {b=1}
        b && $1=="minos" {print $2; exit}
        /LC_VERSION_MIN_MACOSX/ {m=1}
        m && $1=="version" {print $2; exit}'
}

checked=0
for f in "$SIDECAR"/_internal/mlx/core*.so "$SIDECAR"/_internal/mlx/lib/libmlx.dylib; do
    # `|| minos=""`: an unreadable file must reach `bad` and say so, not kill the script
    # silently inside the substitution (set -e + pipefail).
    minos="$(macho_minos "$f")" || minos=""
    if [ -z "$minos" ]; then bad "$(basename "$f"): no minimum macOS in the Mach-O header"; continue; fi
    checked=$((checked + 1))
    if newer "$minos" "$FLOOR"; then
        bad "$(basename "$f") has minos $minos; the app's floor is $FLOOR"
    fi
done
[ "$checked" -ge 2 ] || bad "found $checked of the 2 MLX binaries to read (core*.so, libmlx.dylib)"

if [ "$fail" -ne 0 ]; then
    echo "check-sidecar-mlx-floor: MLX is newer than macOS $FLOOR. Rebuild the sidecar venv:" >&2
    echo "  desktop/scripts/build-sidecar.sh --force   (build-sidecar.sh pins the $FLOOR wheels)" >&2
    exit 1
fi
echo "check-sidecar-mlx-floor: mlx + mlx-metal at macOS <= $FLOOR ($checked binaries read)"
