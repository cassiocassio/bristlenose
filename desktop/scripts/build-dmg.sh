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
#   2. Sidecar     — ensure-sidecar.sh --force, signed under the Developer ID cert.
#   3. Archive     — xcodebuild archive, Developer-ID signing overrides.
#   4. Export      — xcodebuild -exportArchive → standalone .app.
#   5. Verify app  — codesign --deep --strict (catches the sandbox/keychain-group spike).
#   6. Notarise .app + staple.
#   7. create-dmg  — branded backdrop + drag-to-Applications.
#   8. Sign .dmg + notarise + staple.
#   9. Manifest    — sha256s of .app / .dmg / sidecar + commit SHA.
#  10. Final gates — spctl accept, stapler validate.
#
# Usage:
#   desktop/scripts/build-dmg.sh
#
# Environment:
#   SIGN_IDENTITY  Developer ID Application codesign identity. REQUIRED — no
#                  ad-hoc fallback (notarisation needs a real Developer ID cert).
#                  Default: "Developer ID Application: Martin Storey (Z56GZVA2QB)".
#   NOTARY_PROFILE notarytool --keychain-profile; default "bristlenose-notary".
#   SIGN_JOBS      parallelism for sign-sidecar.sh; default hw.ncpu.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"

TEAM_ID="Z56GZVA2QB"
SIGN_IDENTITY="${SIGN_IDENTITY:-Developer ID Application: Martin Storey ($TEAM_ID)}"
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
    local submit_log="$BUILD_DIR/notarytool-$(basename "$target").plist"
    xcrun notarytool submit "$submit_target" \
        --keychain-profile "$NOTARY_PROFILE" --wait --output-format plist \
        > "$submit_log" 2>&1 \
        || { echo "notarytool submit failed:" >&2; tail -50 "$submit_log" >&2; return 1; }

    local sid
    sid="$(/usr/libexec/PlistBuddy -c "Print :id" "$submit_log" 2>/dev/null || true)"
    [ -n "$sid" ] || { echo "no submission UUID:" >&2; cat "$submit_log" >&2; return 1; }

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
    xcrun stapler staple "$target"
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
# 6. Notarise + staple the .app
# ------------------------------------------------------------
# Staple the inner .app so a user who drags it out of the .dmg and discards the
# .dmg still gets clean Gatekeeper (the ticket is embedded in the .app).
say "Notarise .app"
notarize_and_staple "$APP"

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
say "Manifest"
SIDECAR_BIN="$PROJECT_DIR/Resources/bristlenose-sidecar/bristlenose-sidecar"
{
    echo "Bristlenose $VERSION — Developer ID .dmg build manifest"
    echo "commit:  $(git -C "$ROOT" rev-parse HEAD)"
    echo "signed:  $SIGN_IDENTITY"
    echo
    echo "sha256:"
    shasum -a 256 "$DMG_PATH" | sed 's/^/  /'
    shasum -a 256 "$APP/Contents/MacOS/Bristlenose" 2>/dev/null | sed 's/^/  /'
    [ -f "$SIDECAR_BIN" ] && shasum -a 256 "$SIDECAR_BIN" | sed 's/^/  /'
} > "$MANIFEST_PATH"
ok "manifest: $(basename "$MANIFEST_PATH")"

# ------------------------------------------------------------
# 10. Final gates
# ------------------------------------------------------------
say "Final verification"
stapler validate "$DMG_PATH"                 && ok "stapler validate (.dmg): passed"
stapler validate "$APP"                      && ok "stapler validate (.app): passed"
spctl -a -t open --context context:primary-signature -vv "$DMG_PATH" 2>&1 | grep -q "accepted" \
    && ok "spctl (.dmg): accepted" \
    || echo "    note: spctl on the .dmg is advisory; the .app is the Gatekeeper subject"
spctl -a -t exec -vv "$APP" 2>&1 | grep -q "accepted" \
    && ok "spctl (.app): accepted" \
    || die "spctl did not accept the .app — stapling or notarisation incomplete"

cat <<EOF

──────────────────────────────────────────────────────────────
✓ $DMG_NAME  ·  notarised + stapled  ·  $(du -h "$DMG_PATH" | cut -f1)
  dmg:      $DMG_PATH
  manifest: $MANIFEST_PATH

  Next: copy to the website's dmg/ dir on the server and deploy.
  See desktop/scripts/build-dmg.sh header + docs/private/sparkle-plan.md.
──────────────────────────────────────────────────────────────
EOF
