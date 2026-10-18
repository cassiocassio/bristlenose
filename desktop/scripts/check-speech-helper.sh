#!/usr/bin/env bash
# The one gate over the Apple speech helper, bristlenose-speech
# (docs/design-apple-first-transcription.md §3 A). Not a copy of
# check-mcp-helper.sh, which asserts the opposite entitlement set.
#
# Usage:
#   desktop/scripts/check-speech-helper.sh <binary> [<binary> ...]
#
# Why each check exists:
#   arm64 only             — the app is arm64-only; a fat or x86_64 helper is
#                            a build-script slip, not a choice.
#   minos == app floor     — built for the build machine's OS it crashes at
#                            launch on 15.
#   Info.plist id          — a sandboxed bare tool traps at launch (exit 133)
#                            without an embedded Info.plist, and the id must be
#                            the signing identifier (the 14 Jul 2026 "Invalid
#                            Code Signature Identifier" rejection).
#   signature verifies     — notarisation and App Store Connect reject the app
#                            over one bad nested signature.
#   sandbox + inherit, and NOTHING else
#                          — App Store rule for nested executables; inherit
#                            because the sidecar launches it. Any extra key is
#                            a widening: no network.client (audio never leaves
#                            the Mac — the model fetch is a system daemon's), no
#                            app group, no Hardened Runtime exception. ffmpeg's
#                            set, desktop/bristlenose-ffmpeg.entitlements.
#   Hardened Runtime       — notarisation requires it on every nested Mach-O.
#
# Exit 0 = every binary passes. Anything else = do not ship.
set -euo pipefail

HELPER_ID="app.bristlenose.speech"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ "$#" -ge 1 ] || { echo "usage: check-speech-helper.sh <binary>..." >&2; exit 2; }

MIN_MACOS="${MIN_MACOS:-$(grep -m1 -o 'MACOSX_DEPLOYMENT_TARGET = [0-9.]*;' \
    "$ROOT/desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj" | grep -o '[0-9.]*[0-9]')}"
[ -n "$MIN_MACOS" ] || { echo "error: could not read MACOSX_DEPLOYMENT_TARGET" >&2; exit 2; }

fail=0
die_one() { echo "  FAIL $1" >&2; fail=1; }
WORK="$(mktemp -d "${TMPDIR:-/tmp}/check-speech-helper.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

for h in "$@"; do
    echo "== $h"
    [ -f "$h" ] || { die_one "missing"; continue; }
    before="$fail"

    # Mach-O, arm64 only. lipo fails outright on a non-Mach-O file.
    archs="$(lipo -archs "$h" 2>/dev/null)" || archs="(not a Mach-O)"
    [ "$archs" = "arm64" ] || die_one "architectures are '$archs', want arm64 only"

    # Deployment floor, from LC_BUILD_VERSION. Captured to a file first: a
    # pipe into awk that exits early SIGPIPEs otool under pipefail.
    otool -l "$h" > "$WORK/load.txt" 2>/dev/null || true
    minos="$(awk '/LC_BUILD_VERSION/{f=1} f&&/minos/{print $2; exit}' "$WORK/load.txt")"
    [ "$minos" = "$MIN_MACOS" ] || die_one "minos '$minos', want the app floor $MIN_MACOS"

    # Signature.
    codesign --verify --strict "$h" 2>"$WORK/verify.txt" \
        || die_one "codesign --verify --strict: $(tr '\n' ' ' < "$WORK/verify.txt")"
    codesign -dvvv "$h" > "$WORK/info.txt" 2>&1 || true
    ident="$(sed -n 's/^Identifier=//p' "$WORK/info.txt")"
    [ "$ident" = "$HELPER_ID" ] || die_one "signing identifier '$ident', want $HELPER_ID"

    # Hardened Runtime: the CodeDirectory flags carry "runtime".
    cdflags="$(sed -n 's/^CodeDirectory .*flags=\(0x[0-9a-f]*([^)]*)\).*/\1/p' "$WORK/info.txt")"
    case "$cdflags" in
        *runtime*) ;;
        *) die_one "no Hardened Runtime (CodeDirectory flags '$cdflags')" ;;
    esac

    # Embedded Info.plist.
    otool -P "$h" > "$WORK/plist.txt" 2>/dev/null || true
    plist_id="$(python3 - "$WORK/plist.txt" <<'PY'
import plistlib, re, sys
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"<\?xml.*</plist>", raw, re.S)
print(plistlib.loads(m.group(0).encode()).get("CFBundleIdentifier", "") if m else "")
PY
)"
    [ "$plist_id" = "$HELPER_ID" ] || die_one "embedded Info.plist CFBundleIdentifier '$plist_id', want $HELPER_ID"

    # Entitlements: exactly app-sandbox and inherit, both true.
    codesign -d --entitlements - --xml "$h" > "$WORK/ent.plist" 2>/dev/null || : > "$WORK/ent.plist"
    ent_verdict="$(python3 - "$WORK/ent.plist" <<'PY'
import plistlib, sys
want = {"com.apple.security.app-sandbox", "com.apple.security.inherit"}
try:
    d = plistlib.load(open(sys.argv[1], "rb"))
except Exception:
    d = {}
problems = []
for k in sorted(want):
    if d.get(k) is not True:
        problems.append(f"{k} is {d.get(k)!r}, want true")
for k in sorted(set(d) - want):
    problems.append(f"unexpected {k}")
print("; ".join(problems) if problems else "ok")
PY
)"
    [ "$ent_verdict" = "ok" ] || die_one "entitlements: $ent_verdict"

    if [ "$fail" = "$before" ]; then
        echo "  ok  $ident · arm64 · macOS $minos+ · sandbox+inherit · runtime"
    fi
done

if [ "$fail" != 0 ]; then echo "check-speech-helper: FAILED" >&2; exit 1; fi
echo "check-speech-helper: $# ok"
