#!/usr/bin/env bash
# Developer-ID `.dmg` build for Bristlenose.app (lifecycle stage 2.5).
#
# Produces a notarised, stapled, Developer-ID-signed `.dmg` for direct download
# from bristlenose.app — the friends-of-friends BYOK preview channel, distinct
# from the App Store `.pkg` path (build-all.sh).
#
# This is the EXPIRING ALPHA build: no Sparkle, no auto-update, no appcast. It's
# a deliberately-disposable low-friction sampler (a Substack/LinkedIn link for
# people who bounce off TestFlight), NOT a real distribution channel. Every build
# stops working 30 days after it's cut (AlphaBuild.swift, scoped to the
# DEVELOPER_ID_BETA channel this script sets). Refresh the public download by
# re-cutting. The funnel past expiry is the App Store or Homebrew. Auto-update is
# deliberately absent — see docs/private/sparkle-plan.md (superseded for this
# channel; kept for history / if the strategy ever changes).
#
# Chain (bails on any non-zero exit):
#   1. Pre-flight  — Developer ID cert, create-dmg, notarytool creds.
#   1b. Swift tests — test-swift.sh (SKIP_SWIFT_TESTS=1 to bypass).
#   2. Sidecar     — ensure-sidecar.sh --force, signed under the Developer ID cert.
#   3. Archive     — xcodebuild archive, Developer-ID signing overrides.
#   4. Export      — xcodebuild -exportArchive → standalone .app.
#   5. Verify app  — codesign --deep --strict (catches the sandbox/keychain-group spike).
#   6. (retired 14 Aug 2026) app-level notarisation — the .dmg submission in
#      step 8 covers the nested app; see the step-6 comment for the trade.
#   7. create-dmg  — branded backdrop + drag-to-Applications.
#   8. Sign .dmg + notarise + staple — the ONE notary round trip.
#   9. Manifest    — sha256s of .app / .dmg / sidecar + the commit SHA and tree
#                    state captured back at step 3 (NOT re-read here — the chain
#                    can span a resumed notarisation and outlive HEAD).
#  10. Final gates — spctl accept, stapler validate.
#
# Usage:
#   desktop/scripts/build-dmg.sh
#
# Environment:
#   SIGN_IDENTITY_DEVELOPER_ID
#                  Developer ID Application codesign identity. REQUIRED — no
#                  ad-hoc fallback (notarisation needs a real Developer ID cert).
#                  Default: "Developer ID Application: Martin Storey (Z56GZVA2QB)".
#   NOTARY_PROFILE notarytool --keychain-profile; default "bristlenose-notary".
#   SIGN_JOBS      parallelism for sign-sidecar.sh; default hw.ncpu.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# The sink (docs/design-release-board.md §1.1): the .dmg's build time is the
# 30-day clock's origin; the 30 lives in AlphaBuild.swift, not here.
if [ -f "$SCRIPT_DIR/sink.sh" ]; then . "$SCRIPT_DIR/sink.sh"; else sink_line() { :; }; fi
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"

# Shared non-secret constants — same conf, same env-wins shape as build-all.sh
# (the generic SIGN_IDENTITY is pinned across the source so the conf can never
# feed it; see the 27 Aug 2026 note below).
_env_di="${SIGN_IDENTITY_DEVELOPER_ID:-}"; _env_np="${NOTARY_PROFILE:-}"
_env_tm="${TEAM_ID:-}"; _env_generic="${SIGN_IDENTITY:-}"
_SHIP_CONF="${BRISTLENOSE_SHIP_CONF:-$SCRIPT_DIR/.ship-local.conf}"
# shellcheck disable=SC1090
[ -f "$_SHIP_CONF" ] && . "$_SHIP_CONF"
[ -n "$_env_di" ] && SIGN_IDENTITY_DEVELOPER_ID="$_env_di"
[ -n "$_env_np" ] && NOTARY_PROFILE="$_env_np"
[ -n "$_env_tm" ] && TEAM_ID="$_env_tm"
SIGN_IDENTITY="$_env_generic"
TEAM_ID="${TEAM_ID:-Z56GZVA2QB}"
# Deliberately does NOT fall back to an ambient $SIGN_IDENTITY. That variable is
# also read by build-all.sh, which signs an App Store archive with a completely
# different certificate — and exporting it for that script silently overrode the
# default below, producing a .dmg signed Apple Distribution. Gatekeeper rejects
# that, and only after a 30-minute build and a notarisation round-trip (27 Aug
# 2026). The default is right for this script; an ambient value from elsewhere
# is not evidence that anyone meant it to apply here.
# No guessed default any more (retired 31 Aug 2026): the old fallback
# interpolated a personal name from TEAM_ID — a guess that was never checked
# against the keychain until minute 30, and the last personal-name hardcode in
# a tracked script. Unset now fails LOUD, mirroring build-all.sh: the release
# driver exports the resolved fingerprint, and a standalone run gets it from
# .ship-local.conf or says so explicitly.
if [ -z "${SIGN_IDENTITY_DEVELOPER_ID:-}" ]; then
    printf '\033[31merror:\033[0m SIGN_IDENTITY_DEVELOPER_ID is not set.\n' >&2
    printf '  A notarised .dmg wants the Developer ID Application identity:\n' >&2
    printf '    set SIGN_IDENTITY_DEVELOPER_ID in %s\n' "$_SHIP_CONF" >&2
    printf '    (name or SHA-1 fingerprint, from: security find-identity -v -p codesigning)\n' >&2
    exit 1
fi
SIGN_IDENTITY="$SIGN_IDENTITY_DEVELOPER_ID"

# Fingerprint → common name for the type gate (the driver hands over hashes;
# renewal twins share a name). Signing keeps the form that arrived.
SIGN_CN="$SIGN_IDENTITY"
if printf '%s' "$SIGN_IDENTITY" | grep -qiE '^[0-9a-f]{40}$'; then
    SIGN_CN=$(security find-identity -v -p codesigning 2>/dev/null \
        | grep -iF " $SIGN_IDENTITY " | head -1 | sed 's/^[^"]*"//; s/".*$//')
    [ -n "$SIGN_CN" ] || {
        printf '\033[31merror:\033[0m signing fingerprint %s is not in the keychain.\n' "$SIGN_IDENTITY" >&2
        exit 1
    }
fi

# Refuse the other script's certificate rather than discovering it at the
# Gatekeeper assertion 30 minutes from now. Uses printf/exit rather than die(),
# which is not defined until line ~96 — an earlier draft called it here and got
# "die: command not found", turning a clear refusal into a confusing one.
case "$SIGN_CN" in
    *"Developer ID Application"*) : ;;
    *"Apple Distribution"*)
        printf '\033[31merror:\033[0m that is an Apple Distribution certificate, which belongs to build-all.sh.\n' >&2
        printf '  got:  %s\n' "$SIGN_IDENTITY" >&2
        printf '  want: a Developer ID Application identity — Gatekeeper rejects a .dmg\n' >&2
        printf '        signed Apple Distribution, which is what happened on 27 Aug 2026.\n' >&2
        printf '  If SIGN_IDENTITY is exported in your shell for the App Store build,\n' >&2
        printf '  unset it: this script defaults correctly on its own.\n' >&2
        exit 1 ;;
    *)
        printf '\033[31merror:\033[0m unrecognised signing identity for a notarised .dmg.\n' >&2
        printf '  got:  %s\n' "$SIGN_IDENTITY" >&2
        printf '  want: "Developer ID Application: ..."\n' >&2
        exit 1 ;;
esac
NOTARY_PROFILE="${NOTARY_PROFILE:-bristlenose-notary}"

PROJECT_DIR="$DESKTOP_DIR/Bristlenose"
BUILD_DIR="$DESKTOP_DIR/build"
ARCHIVE_PATH="$BUILD_DIR/Bristlenose-DeveloperID.xcarchive"
EXPORT_DIR="$BUILD_DIR/export-developer-id"
EXPORT_OPTIONS="$PROJECT_DIR/ExportOptions-DeveloperID.plist"
ARCHIVE_LOG="$BUILD_DIR/xcodebuild-archive-dmg.log"
EXPORT_LOG="$BUILD_DIR/xcodebuild-export-dmg.log"

# Single source of version — same field bump-version.py drives.
VERSION="$("$ROOT/.venv/bin/python" -c 'import bristlenose; print(bristlenose.__version__)' 2>/dev/null \
    || python3 -c 'import sys; sys.path.insert(0, "'"$ROOT"'"); import bristlenose; print(bristlenose.__version__)')"
[ -n "$VERSION" ] || { echo "error: could not read bristlenose.__version__" >&2; exit 1; }

DMG_NAME="Bristlenose-$VERSION.dmg"
DMG_PATH="$BUILD_DIR/$DMG_NAME"
MANIFEST_PATH="$BUILD_DIR/Bristlenose-$VERSION.manifest.txt"
SBOM_PATH="$BUILD_DIR/Bristlenose-$VERSION.sidecar-sbom.json"

say()  { printf '\n\033[1m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# notarize_and_staple <path-to-.app-or-.dmg>
# .app must be zipped with ditto (plain zip mangles xattrs/symlinks). .dmg
# submits directly. Staple the ORIGINAL path (not the zip) on success.
notarize_and_staple() {
    local target="$1" ext="${1##*.}" submit_target="$1"
    if [ "$ext" = "app" ]; then
        submit_target="$BUILD_DIR/$(basename "$target").zip"
        rm -f "$submit_target"
        ditto -c -k --sequesterRsrc --keepParent "$target" "$submit_target"
    fi

    echo "    submitting $(basename "$submit_target") to Apple (1–15 min)…"
    local submit_log="$BUILD_DIR/notarytool-$(basename "$target").log"
    local submit_rc sid

    # Normal output format, deliberately NOT `--output-format plist`.
    # plist/json buffer to completion — notarytool's own help says "a single
    # update will be output at the end of the operation" — so a crash during
    # the upload leaves a ZERO-BYTE file and the submission ID exists nowhere
    # on this machine. That is precisely what happened on 4 Aug 2026: the
    # client took a Bus error partway through a 644 MB upload and
    # notarytool-Bristlenose-0.24.0.dmg.plist was 0 bytes. Apple later purged
    # the half-arrived submission, and `notarytool history` never carried it,
    # so there was nothing to reconcile against — the only recovery was to
    # resubmit.
    #
    # Normal format prints `id: <uuid>` BEFORE the upload begins, so tee-ing it
    # captures the ID while the upload is still in flight. A crash then leaves
    # a resumable ID rather than a mystery.
    set +e
    # --timeout: an unbounded --wait on Apple's queue is the release chain's
    # only in-step infinite hang (audited 31 Aug 2026); two hours is far past
    # any observed notarisation and still fails while the log is warm.
    xcrun notarytool submit "$submit_target" --timeout 2h \
        --keychain-profile "$NOTARY_PROFILE" --wait 2>&1 | tee "$submit_log"
    submit_rc=${PIPESTATUS[0]}
    set -e
    sid="$(sed -n 's/^ *id: *//p' "$submit_log" | head -1)"

    if [ "$submit_rc" -ne 0 ]; then
        echo "notarytool submit failed (exit $submit_rc)." >&2
        if [ -n "$sid" ]; then
            # The upload may have completed even though the client died.
            echo "  submission ID was issued: $sid" >&2
            echo "  check it before resubmitting — a live submission cannot be" >&2
            echo "  withdrawn, and a second one just queues behind the first:" >&2
            echo "    xcrun notarytool info $sid --keychain-profile $NOTARY_PROFILE" >&2
            echo "  'Submission does not exist' means Apple never took it — resubmit." >&2
        else
            echo "  no submission ID was issued — nothing reached Apple. Resubmit." >&2
            echo "  if it dies mid-upload again, retry with --no-s3-acceleration." >&2
        fi
        return 1
    fi

    [ -n "$sid" ] || { echo "no submission UUID in the submit log:" >&2; tail -20 "$submit_log" >&2; return 1; }

    # Don't trust `notarytool history` (can show a cached prior run) — fetch
    # this submission's log and assert Accepted.
    local log_json="$BUILD_DIR/notarytool-$(basename "$target").log.json"
    xcrun notarytool log "$sid" --keychain-profile "$NOTARY_PROFILE" "$log_json"
    local status
    status="$(/usr/bin/python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "$log_json")"
    if [ "$status" != "Accepted" ]; then
        echo "notarisation status '$status' (expected Accepted). log: $log_json" >&2
        /usr/bin/python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); [print(i) for i in d.get("issues",[])[:10]]' "$log_json" >&2
        return 1
    fi
    # Stapling DOWNLOADS the ticket from Apple, and it can 404 for a short
    # while after `Accepted` as the ticket propagates (Error 65, "could not
    # retrieve ticket"). Unretried, that kills a run which has already paid for
    # a 15-minute round trip. Assert with `stapler validate` rather than
    # trusting staple's own exit code.
    local staple_ok=0 attempt
    for attempt in 1 2 3 4 5 6; do
        if xcrun stapler staple "$target" >/dev/null 2>&1 \
           && xcrun stapler validate "$target" >/dev/null 2>&1; then
            staple_ok=1
            break
        fi
        [ "$attempt" -lt 6 ] && { echo "    ticket not ready (attempt $attempt/6) — retrying in 30s…"; sleep 30; }
    done
    [ "$staple_ok" -eq 1 ] || {
        echo "stapling failed after 6 attempts — the notarisation was Accepted ($sid)," >&2
        echo "so retry the staple alone rather than rebuilding:" >&2
        echo "    xcrun stapler staple '$target'" >&2
        return 1
    }
    ok "notarised + stapled: $(basename "$target") (UUID $sid)"
}

# ------------------------------------------------------------
# 1. Pre-flight
# ------------------------------------------------------------
say "Pre-flight"

if ! security find-identity -v -p codesigning | grep -qF "$SIGN_IDENTITY"; then
    die "Developer ID cert not in keychain: $SIGN_IDENTITY
     Generate one at https://developer.apple.com/account/resources/certificates
     (Certificates → + → Developer ID Application), download, double-click to install."
fi
ok "signing identity: $SIGN_IDENTITY"

command -v create-dmg >/dev/null 2>&1 || die "create-dmg not found — brew install create-dmg"
ok "create-dmg: $(command -v create-dmg)"

xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" >/dev/null 2>&1 \
    || die "notarytool keychain profile '$NOTARY_PROFILE' not set up.
     xcrun notarytool store-credentials \"$NOTARY_PROFILE\" --key <AuthKey.p8> --key-id <ID> --issuer <ISSUER>"
ok "notarytool profile: $NOTARY_PROFILE"

ok "target: $DMG_NAME  ·  team $TEAM_ID"

# ------------------------------------------------------------
# 1b. Swift unit suite — the .dmg channel's gate
# ------------------------------------------------------------
# The .dmg was the one shipping channel with no Swift gate. mac-build.yml covers
# a push and build-all.sh step 1c covers the App Store archive; a notarised
# direct download could still carry a red suite, and on 31 Aug 2026 v0.29.0
# shipped on all nine channels with TabLeftPanelTests failing.
#
# Before the sidecar for the same reason build-all.sh runs it there: step 2 is
# ensure-sidecar.sh --force, ~10 minutes every time, and a compile break should
# not buy that first. No ad-hoc branch is needed here — this script refuses
# ad-hoc signing outright, so every run of it is a real one.
say "Swift unit suite (BristlenoseTests)"
if [ "${SKIP_SWIFT_TESTS:-0}" = "1" ]; then
    ok "SKIPPED — SKIP_SWIFT_TESTS=1, gate deliberately bypassed"
else
    "$SCRIPT_DIR/test-swift.sh" --quiet || die "Swift suite did not pass.
     reproduce: desktop/scripts/test-swift.sh"
    ok "BristlenoseTests green"
fi

# ------------------------------------------------------------
# 2. Sidecar — build + sign under the Developer ID cert
# ------------------------------------------------------------
# Every inner Mach-O must be Developer-ID-signed + notarisable (Apple
# Distribution won't notarise). ensure-sidecar.sh --force rebuilds and re-signs
# the whole PyInstaller tree under SIGN_IDENTITY. _BRISTLENOSE_RELEASE=1
# authorises signing with a real identity (the IDE inner loop is refused one).
say "Sidecar — fetch · build · sign (Developer ID)"
export SIGN_IDENTITY
_BRISTLENOSE_RELEASE=1 "$SCRIPT_DIR/ensure-sidecar.sh" --force
ok "sidecar built + signed under $SIGN_IDENTITY"

# ------------------------------------------------------------
# 3. Archive — development signing (Developer ID is applied at EXPORT)
# ------------------------------------------------------------
# Do NOT force Developer ID at archive time. This app is sandboxed AND carries
# the Keychain Sharing (keychain-access-groups) entitlement, which Xcode treats
# as profile-gated: a manual Developer-ID archive with an empty profile fails
# "requires a provisioning profile" — and it's the *capability* it gates on, not
# the $(AppIdentifierPrefix) variable (hardcoding the Team-ID prefix doesn't help;
# automatic signing only does *development*, never Developer ID). Both were
# verified dead ends (16 Jul 2026).
#
# The working path is Apple's standard archive→export split:
#   • archive with automatic DEVELOPMENT signing — uses the auto-managed
#     "Mac Team Provisioning Profile" (which carries the keychain entitlement);
#   • re-sign as Developer ID at the EXPORT step with -allowProvisioningUpdates,
#     which has Xcode MINT the Developer ID provisioning profile itself — no
#     portal trip. The DEVELOPER_ID_BETA flag baked here persists through export
#     (export re-signs, doesn't recompile). Sidecar is fresh+signed from step 2;
#     skip the in-archive ensure phase.
say "Xcode archive (development signing; Developer ID applied at export)"

# Provenance is captured HERE, not at manifest-writing time. Stage 9 runs at the
# end of a chain with two notarisation round-trips in it; re-reading HEAD there
# is only correct if nothing moved in between. On 4 Aug 2026 something did — a
# notarytool SIGBUS mid-upload, resumed ~14h later against a main that had
# advanced two commits, and the manifest credited the wrong commit for the
# binary. A manifest whose sole purpose is provenance is worse than useless when
# it lies, so bind the fact to the moment the bits are cut.
BUILD_COMMIT="$(git -C "$ROOT" rev-parse HEAD)"
# The .dmg is the one channel with no update mechanism behind it, so record
# whether the tree was clean too — a recipient has nothing else to go on.
# GeneratedBuildInfo.swift is rewritten by every Xcode compile; it's gitignored
# today (so `status --porcelain` already omits it), filtered anyway so an
# un-ignored copy can't report every build as dirty. See CLAUDE.md's
# "Status-bar `-dirty` ≠ source dirty".
BUILD_DIRT="$(git -C "$ROOT" status --porcelain \
    | grep -v 'desktop/Bristlenose/Bristlenose/GeneratedBuildInfo\.swift' || true)"
if [ -n "$BUILD_DIRT" ]; then
    # Split modified-vs-untracked rather than reporting a bare "dirty". Untracked
    # scratch under experiments/ or docs/ can't reach the .app, but an untracked
    # .swift under the synced root group compiles straight in — so neither count
    # can be dropped, and a lone "dirty" that's always on would just get ignored.
    _dirt_mod="$(printf '%s\n' "$BUILD_DIRT" | grep -cv '^??' || true)"
    _dirt_unt="$(printf '%s\n' "$BUILD_DIRT" | grep -c  '^??' || true)"
    BUILD_TREE="dirty — $_dirt_mod modified, $_dirt_unt untracked"
else
    BUILD_TREE="clean"
fi
ok "archiving from $(git -C "$ROOT" rev-parse --short HEAD) · tree $BUILD_TREE"

rm -rf "$ARCHIVE_PATH" "$EXPORT_DIR"
export BRISTLENOSE_SKIP_SIDECAR_ENSURE=1
xcodebuild \
    -project "$PROJECT_DIR/Bristlenose.xcodeproj" \
    -scheme Bristlenose \
    -configuration Release \
    -destination "generic/platform=macOS" \
    -archivePath "$ARCHIVE_PATH" \
    CODE_SIGN_STYLE=Automatic \
    CODE_SIGN_IDENTITY="Apple Development" \
    PROVISIONING_PROFILE_SPECIFIER="" \
    DEVELOPMENT_TEAM="$TEAM_ID" \
    SWIFT_ACTIVE_COMPILATION_CONDITIONS="\$(inherited) DEVELOPER_ID_BETA" \
    -allowProvisioningUpdates \
    archive \
    > "$ARCHIVE_LOG" 2>&1 \
    || { echo "xcodebuild archive failed. tail:" >&2; tail -50 "$ARCHIVE_LOG" >&2; exit 1; }
ok "archived: $(basename "$ARCHIVE_PATH")"

# ------------------------------------------------------------
# 4. Export → standalone .app
# ------------------------------------------------------------
say "Export → Developer ID .app"
xcodebuild \
    -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_DIR" \
    -exportOptionsPlist "$EXPORT_OPTIONS" \
    -allowProvisioningUpdates \
    > "$EXPORT_LOG" 2>&1 \
    || { echo "xcodebuild -exportArchive failed. tail:" >&2; tail -50 "$EXPORT_LOG" >&2; exit 1; }

APP="$(find "$EXPORT_DIR" -maxdepth 2 -name "*.app" -type d | head -1)"
[ -n "$APP" ] || die "no .app found under $EXPORT_DIR"
ok "exported: $(basename "$APP")"

# ------------------------------------------------------------
# 5. Verify the exported .app BEFORE the expensive notarise round-trip
# ------------------------------------------------------------
# This is the gate for the Developer-ID + sandbox + keychain-access-group spike:
# if a profile-required entitlement is misconfigured under Developer ID, it
# surfaces here as a signature failure, not 15 minutes into notarisation.
say "Verify exported .app"
codesign --verify --deep --strict --verbose=2 "$APP" \
    || die "codesign --deep --strict failed on the exported .app (see spike note in ExportOptions-DeveloperID.plist)"
ok "codesign --deep --strict: valid"

# Release-binary scan: no BRISTLENOSE_DEV_* / BRISTLENOSE_DEBUG_* escape-hatch
# literals and no get-task-allow in the shipping binary. The Developer-ID `.dmg`
# is the ONE channel where the alpha expiry is live, so a leaked debug override
# (e.g. BRISTLENOSE_DEBUG_ALPHA_DAYS) would actually matter here — scan it.
"$SCRIPT_DIR/check-release-binary.sh" "$APP" \
    || die "release-binary scan failed — a dev/debug literal or get-task-allow in the shipping .app"
ok "release-binary scan: no dev/debug literals · no get-task-allow"

# ------------------------------------------------------------
# 6. (retired 14 Aug 2026) Notarise + staple the .app — deliberately absent
# ------------------------------------------------------------
# Apple requires notarising the OUTERMOST distributable only: the .dmg
# submission in step 8 scans the nested .app and its ticket covers the app's
# cdhashes, so Gatekeeper clears both the mount and the dragged-out app. What
# a separate app-level round trip bought was exactly one scenario — FIRST
# launch of the dragged-out app on a fully OFFLINE Mac (no stapled ticket on
# the app itself, so Gatekeeper needs one online lookup). For a 30-day
# expiring BYOK sampler whose user pulled 660 MB over the network seconds
# earlier, that guarantee is not worth doubling the slowest, most
# failure-prone stretch of this lane (~600 MB zip + upload + 1-15 min wait +
# staple-retry, before the dmg does it all again). One online launch clears
# quarantine; every later launch is offline-clean.
#
# check-dmg-shippable.sh changed in the SAME commit: its "inner app stapled"
# assertion became "inner app signature" (codesign --deep --strict) — the gate
# would otherwise fail every image this script now produces. The inner-app
# spctl assessment stays: it proves the dmg's notarisation actually covers the
# app (via ticket lookup). If offline-first-launch ever becomes a requirement
# (e.g. a channel for air-gapped users), restore: `notarize_and_staple "$APP"`
# here, BEFORE create-dmg copies the app into the image — and revert the gate.
# Audit: docs/design-release-system-audit.md §5.

# ------------------------------------------------------------
# 7. Build the .dmg
# ------------------------------------------------------------
# Branded backdrop + drag-to-Applications layout. A bare `hdiutil` image is the
# default-Finder-with-toolbar look = unpolished tell. Backdrop asset is optional
# for the first cut (create-dmg falls back to a plain window if absent).
say "Build .dmg"
rm -f "$DMG_PATH"
DMG_BACKDROP="$DESKTOP_DIR/dmg-assets/background.png"
DMG_ICON="$PROJECT_DIR/Bristlenose/Assets.xcassets/AppIcon.appiconset"  # informational
create_dmg_args=(
    --volname "Bristlenose $VERSION (Alpha)"
    --window-pos 200 120
    --window-size 640 400
    --icon-size 128
    --icon "$(basename "$APP")" 170 190
    --app-drop-link 470 190
    --no-internet-enable
)
[ -f "$DMG_BACKDROP" ] && create_dmg_args+=(--background "$DMG_BACKDROP")
create-dmg "${create_dmg_args[@]}" "$DMG_PATH" "$APP" \
    || die "create-dmg failed"
ok "built: $DMG_NAME ($(du -h "$DMG_PATH" | cut -f1))"

# ------------------------------------------------------------
# 8. Sign + notarise + staple the .dmg
# ------------------------------------------------------------
# No --options runtime on the outer .dmg signature (that flag is Mach-O-only).
say "Sign + notarise .dmg"
codesign --sign "$SIGN_IDENTITY" --timestamp "$DMG_PATH" \
    || die "codesign of .dmg failed"
notarize_and_staple "$DMG_PATH"

# ------------------------------------------------------------
# 9. Build manifest / provenance
# ------------------------------------------------------------
# The sidecar SBOM, first: it is hashed into the manifest below, so the
# provenance record covers it.
#
# WHY IT EXISTS. Three answers to "what is in the sidecar" disagree, and until
# now none of them was machine-readable. THIRD-PARTY-BINARIES.md carries 130
# rows and is a deliberate over-estimate (it lists what is installed, not what
# PyInstaller kept). The bundle itself carries ~21 dist-infos, because pure-
# Python packages are bytecompiled into the archive and leave no metadata unless
# the spec copy_metadata's them -- and one of those 21, presidio_analyzer, is
# metadata for code the spec excludes. An SCA scanner reads that third set and
# concludes we ship 21 packages. This is the artefact to hand it instead.
#
# Generated from .venv-sidecar, never .venv: the two resolve separately and have
# differed by whole minors (see CLAUDE.md, the two-venv gotcha). Verified 5 Sep
# 2026 against `pip list` on that venv -- 130 components, zero discrepancy once
# names are normalised.
say "Sidecar SBOM"
CYCLONEDX="$ROOT/.venv/bin/cyclonedx-py"
if [ -x "$CYCLONEDX" ] && [ -x "$ROOT/.venv-sidecar/bin/python" ]; then
    # --pyproject is what produces a root component at all (without it
    # metadata.component is absent entirely). It reads the version from
    # pyproject.toml, which by house rule NEVER carries one -- the single source
    # is bristlenose/__init__.py -- so the root lands with version null and has
    # to be stamped. Not a workaround for a bug; the two rules simply meet here.
    "$CYCLONEDX" environment --pyproject "$ROOT/pyproject.toml" \
        --output-reproducible -o "$SBOM_PATH" "$ROOT/.venv-sidecar/bin/python" \
        || die "cyclonedx-py failed"
    "$ROOT/.venv/bin/python" - "$SBOM_PATH" "$VERSION" <<'PY' || die "could not stamp the SBOM version"
import json, sys
path, version = sys.argv[1], sys.argv[2]
d = json.load(open(path))
d["metadata"]["component"]["version"] = version
json.dump(d, open(path, "w"), indent=2, sort_keys=True)
PY
    ok "sbom: $(basename "$SBOM_PATH") ($("$ROOT/.venv/bin/python" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["components"]))' "$SBOM_PATH") components)"
elif [ "$SIGN_IDENTITY" != "-" ]; then
    # Same reasoning as build-all.sh step 2b: on a real signing identity this is
    # a release build, and a supply-chain artefact that silently does not get
    # generated is worse than one that is missing loudly.
    die "cyclonedx-py not installed, and this is a signed build.
         .venv/bin/pip install -e '.[release]'
       For a deliberately unsigned local build, use SIGN_IDENTITY=-."
else
    ok "sbom: skipped (cyclonedx-py not installed, ad-hoc build)"
    SBOM_PATH=""
fi

say "Manifest"
SIDECAR_BIN="$PROJECT_DIR/Resources/bristlenose-sidecar/bristlenose-sidecar"
{
    echo "Bristlenose $VERSION — Developer ID .dmg build manifest"
    echo "commit:  $BUILD_COMMIT"
    echo "tree:    $BUILD_TREE"
    echo "signed:  $SIGN_IDENTITY"
    echo
    echo "sha256:"
    shasum -a 256 "$DMG_PATH" | sed 's/^/  /'
    shasum -a 256 "$APP/Contents/MacOS/Bristlenose" 2>/dev/null | sed 's/^/  /'
    [ -f "$SIDECAR_BIN" ] && shasum -a 256 "$SIDECAR_BIN" | sed 's/^/  /'
    [ -n "$SBOM_PATH" ] && [ -f "$SBOM_PATH" ] && shasum -a 256 "$SBOM_PATH" | sed 's/^/  /'
} > "$MANIFEST_PATH"
ok "manifest: $(basename "$MANIFEST_PATH")"
sink_line clock name=dmg version="$VERSION" built="$(date -u +%Y-%m-%dT%H:%M:%SZ)" commit="$BUILD_COMMIT"

# ------------------------------------------------------------
# 10. Final gates
# ------------------------------------------------------------
say "Final verification"

# Delegated to check-dmg-shippable.sh — one implementation of "is this safe to
# publish", shared with the upload path, so the build and the publish can never
# disagree about what shippable means.
#
# What used to be here was four lines, two of which could not fail:
#
#     stapler validate "$DMG_PATH" && ok "…"
#     stapler validate "$APP"      && ok "…"
#
# `set -e` deliberately exempts the left operand of `&&`, so an unstapled
# artefact printed nothing and fell straight through to the success banner
# below. A third line demoted a `spctl` REJECTION on the .dmg to a reassuring
# "advisory" note — but `--context context:primary-signature` is exactly what
# Gatekeeper does at mount time, which is the first thing a user experiences.
#
# And all four asserted against $EXPORT_DIR's .app rather than the copy inside
# the image. create-dmg takes a COPY, so a staple applied after the image was
# built never reaches it, and nothing downstream would have said so. The gate
# mounts and interrogates the app a user actually double-clicks.
"$SCRIPT_DIR/check-dmg-shippable.sh" "$DMG_PATH" \
    || die "the artefact is not shippable — see the failed assertions above"

cat <<EOF

──────────────────────────────────────────────────────────────
✓ $DMG_NAME  ·  notarised + stapled  ·  $(du -h "$DMG_PATH" | cut -f1)
  dmg:      $DMG_PATH
  manifest: $MANIFEST_PATH

  Next: copy to the website's dmg/ dir on the server and deploy.
  See desktop/scripts/build-dmg.sh header + docs/private/sparkle-plan.md.
──────────────────────────────────────────────────────────────
EOF
