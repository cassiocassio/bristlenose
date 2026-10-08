#!/usr/bin/env bash
# Rehearse both release archives, unsigned, off release night.
#
#     desktop/scripts/check-release-archive.sh [appstore|developer-id|both]
#
# Mac Build (mac-build.yml) compiles and tests the DEBUG configuration. Both
# release lanes archive RELEASE: build-all.sh for the App Store, build-dmg.sh for
# the .dmg with DEVELOPER_ID_BETA on top. So a Release-only compile break — code
# that references a `#if DEBUG` symbol unguarded, a `#elseif DEVELOPER_ID_BETA`
# branch that no longer compiles, an optimiser-only diagnostic, an Xcode image
# whose SDK moved under us — is first seen on release night, by the step that is
# then ten minutes into a thirty-minute build. This compiles exactly those two
# configurations, nightly on a GitHub runner (mac-release-archive.yml) and on
# demand here.
#
# What it CANNOT see, measured 8 Oct 2026: signing. An ad-hoc archive of the app
# fails "requires a provisioning profile" — the keychain-access-group and app-group
# entitlements need one — so a runner with no team cannot rehearse the .dmg's
# signing, its entitlements, the native MCP helper (skipped unsigned by the copy
# phase), notarisation or Gatekeeper. Those stay release-night facts. The
# Developer-ID contract that CAN be checked without signing is pinned on every
# push by tests/test_entitlements_split.py (the override path, the untruncated
# invocation, the app-group split, the gates' agreement).
#
# Signing is switched off with CODE_SIGNING_ALLOWED=NO. The sidecar ensure and
# freshness gate are bypassed exactly as test-swift.sh does it, both vars passed
# TWICE (environment AND build setting — the phase's own shell does not see plain
# env, desktop/CLAUDE.md), so a stub sidecar is enough.
#
# Exit codes: 0 every requested archive built · 1 an archive failed · 2 usage.
set -euo pipefail

WHICH="${1:-both}"
case "$WHICH" in appstore|developer-id|both) ;; *) echo "usage: $(basename "$0") [appstore|developer-id|both]" >&2; exit 2 ;; esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../Bristlenose"
OUT="${BN_ARCHIVE_DIR:-$SCRIPT_DIR/../build/release-archive-check}"
mkdir -p "$OUT"
command -v xcodebuild >/dev/null 2>&1 || { echo "xcodebuild not on PATH" >&2; exit 2; }

BYPASS_A=BRISTLENOSE_SKIP_SIDECAR_ENSURE=1
BYPASS_B=BRISTLENOSE_ALLOW_STALE_SIDECAR=1
# A private DerivedData by default: the shared one is locked while Xcode builds,
# and a same-tree build there fails signing on stale residue (desktop/CLAUDE.md).
DD="${BN_DERIVED_DATA:-$OUT/DerivedData}"

archive() {
    local name="$1"; shift
    local log="$OUT/$name.log" rc=0
    echo "==> archiving Release · $name (unsigned)"
    rm -rf "$OUT/$name.xcarchive"
    env "$BYPASS_A" "$BYPASS_B" xcodebuild \
        -project "$PROJECT_DIR/Bristlenose.xcodeproj" \
        -scheme Bristlenose \
        -configuration Release \
        -destination "generic/platform=macOS" \
        -derivedDataPath "$DD" \
        -archivePath "$OUT/$name.xcarchive" \
        CODE_SIGNING_ALLOWED=NO \
        "$BYPASS_A" "$BYPASS_B" \
        "$@" \
        archive > "$log" 2>&1 || rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "ARCHIVE FAILED · $name (xcodebuild exit $rc) — log: $log" >&2
        grep -E "error:" "$log" | sort -u | head -20 >&2 || true
        return 1
    fi
    # The status is xcodebuild's own, read from a redirect, never a pipe. Belt and
    # braces against a reporter that exits 0 without archiving: the product must exist.
    [ -d "$OUT/$name.xcarchive/Products/Applications/Bristlenose.app" ] || {
        echo "ARCHIVE FAILED · $name — xcodebuild exited 0 but no Bristlenose.app in the archive" >&2; return 1; }
    echo "    ✓ $name archived"
}

fail=0
if [ "$WHICH" = appstore ] || [ "$WHICH" = both ]; then
    archive appstore || fail=1
fi
if [ "$WHICH" = developer-id ] || [ "$WHICH" = both ]; then
    # The flags build-dmg.sh's archive passes that change what COMPILES. The
    # entitlements override and the helper channel only matter to signing, which
    # this cannot do (see the header).
    archive developer-id "SWIFT_ACTIVE_COMPILATION_CONDITIONS=\$(inherited) DEVELOPER_ID_BETA" || fail=1
fi
exit "$fail"
