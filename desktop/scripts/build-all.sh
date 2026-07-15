#!/usr/bin/env bash
# End-to-end alpha build for Bristlenose.app (Track C C2).
#
# Ported from desktop/v0.1-archive/scripts/build-all.sh — shape only,
# the architecture is now: one signed, notarised .app archive ready for
# C3 / Track B to export as a .pkg and upload to TestFlight.
#
# Chain (bailing on any non-zero exit):
#   1. Pre-flight — identities, profiles, notarytool credentials.
#   2. Parallel:   fetch-ffmpeg.sh  &&  build-sidecar.sh
#   3. sign-ffmpeg.sh (bundled static FFmpeg + ffprobe)
#   4. sign-sidecar.sh (PyInstaller bundle; parallel inner loop)
#   5. xcodebuild archive  [added in commit 3, once pbxproj flips manual]
#   6. xcodebuild -exportArchive  [ditto]
#   7. check-release-binary.sh on the exported .app  [commit 4]
#   8. Provisioning profile sanity check  [commit 4]
#   9. Notarisation + stapling  [commit 4]
#  10. Final verification battery  [commit 4]
#
# Usage:
#   desktop/scripts/build-all.sh
#
# Environment (passed through to child scripts):
#   SIGN_IDENTITY  codesign identity; default "-" = ad-hoc.
#                  Alpha: "Apple Distribution: Martin Storey (Z56GZVA2QB)"
#   SIGN_JOBS      parallelism for sign-sidecar.sh; default hw.ncpu.
#   ALLOW_RESIGN   pass-through for sign-sidecar.sh re-sign override.
#   NOTARY_PROFILE notarytool --keychain-profile; default "bristlenose-notary"
#                  (used by commit 4 onwards).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"

SIGN_IDENTITY="${SIGN_IDENTITY:--}"
NOTARY_PROFILE="${NOTARY_PROFILE:-bristlenose-notary}"
TEAM_ID="Z56GZVA2QB"
PROFILE_NAME="Bristlenose Mac App Store"
PROFILE_PATH="$HOME/Library/MobileDevice/Provisioning Profiles/Bristlenose_Mac_App_Store.provisionprofile"

# ------------------------------------------------------------
# Pretty report (see REPORT-STYLE.md)
# ------------------------------------------------------------
# bn_autowrap re-execs this script with stdout piped through build_report.py
# (exiting with OUR status), then the inner run emits @bn events. BN_REPORT=0 —
# or a missing python / build_report.py — falls back to plain output. Noisy tool
# output still goes to per-step logs.
source "$SCRIPT_DIR/report.sh"
bn_autowrap "$0" "$@"
# Any nonzero exit (set -e or explicit) closes the report with a fail footer.
trap '_bn_ec=$?; [ "$_bn_ec" -ne 0 ] && bn_trap_fail' EXIT

bn_meta \
    title="Bristlenose.app — release build" \
    target="macOS · arm64 · App Store Connect" \
    identity="$SIGN_IDENTITY" \
    bundle="app.bristlenose  ·  team $TEAM_ID" \
    logs="$DESKTOP_DIR/build/  ·  tail -f xcodebuild-archive.log"

# ------------------------------------------------------------
# 1. Pre-flight
# ------------------------------------------------------------
# Cryptic errors otherwise. Ad-hoc identity skips the Apple-signed
# checks because those only matter for a shipping archive.

bn_step_start 1 Pre-flight "Pre-flight" \
    narrative="Fails fast before any expensive work — identities, profiles, hygiene."
_bn_t1=$SECONDS

# 1a. Source-level logging hygiene — catches credential-shaped interpolations
# in Swift logger calls without a privacy marker. Complements the runtime
# redactor in ServeManager.handleLine (Python-side leakage defence). Cheap;
# runs in <1s; fails fast before expensive archive work.
"$SCRIPT_DIR/check-logging-hygiene.sh" "$ROOT" >/dev/null
bn_check 1 ok "logging hygiene" "no credential-shaped log calls"

# 1b. Bundle manifest coverage — asserts every runtime-data dir under
# bristlenose/ is covered by a datas entry in the spec. Prevents the
# C3-smoke-test BUG-3/4/5 class (data file in source, missing from bundle).
# ~60ms; fail-closed on parse errors.
"$SCRIPT_DIR/check-bundle-manifest.sh" "$ROOT" >/dev/null
bn_check 1 ok "bundle manifest" "every runtime dir covered by spec"

if [ "$SIGN_IDENTITY" != "-" ]; then
    # Capture output before grepping (SIGPIPE + pipefail trap —
    # see sign-sidecar.sh Timestamp= assertion for the full story).
    _identities=$(security find-identity -v -p codesigning)
    if ! grep -qF "$SIGN_IDENTITY" <<< "$_identities"; then
        echo "error: signing identity not found in keychain:" >&2
        echo "  $SIGN_IDENTITY" >&2
        echo "Install the Apple Distribution cert (see" >&2
        echo "docs/design-desktop-python-runtime.md §Signing strategy)." >&2
        exit 1
    fi
    bn_check 1 ok "signing identity" "found in keychain"

    if [ ! -f "$PROFILE_PATH" ]; then
        echo "error: provisioning profile not found at:" >&2
        echo "  $PROFILE_PATH" >&2
        echo "Install the '$PROFILE_NAME' profile from the Apple" >&2
        echo "Developer portal." >&2
        exit 1
    fi
    bn_check 1 ok "provisioning profile" "$PROFILE_NAME"

    # Notarytool keychain profile check is gated on commit 4 work.
    # Announce the expectation for now; sign-only runs don't need it.
    if ! xcrun notarytool history --keychain-profile "$NOTARY_PROFILE" \
        >/dev/null 2>&1; then
        echo "note: notarytool keychain profile '$NOTARY_PROFILE' not set up." >&2
        echo "      required for notarisation step (commit 4)." >&2
        echo "      set up: xcrun notarytool store-credentials \"$NOTARY_PROFILE\" ..." >&2
    fi
fi

bn_step_ok 1 elapsed=$((SECONDS-_bn_t1))

# ------------------------------------------------------------
# 2. Ensure the sidecar is fresh + signed (fetch ffmpeg + build + sign)
# ------------------------------------------------------------
# Collapsed onto the single orchestrator (replaces the old steps 2-4):
# ensure-sidecar.sh does fetch-ffmpeg + build-sidecar (--force = full clean
# rebuild for release) + sign BOTH ffmpeg/ffprobe AND the sidecar bundle under
# one identity, then deep-verifies. `_BRISTLENOSE_RELEASE=1` authorises the real
# identity (the IDE inner loop is refused one). Self-test (2a) + inventory (2b)
# run AFTER, against the freshly built+signed tree.
#
# (Trade-off, finding 19: this serialises the old fetch||build concurrency —
# ~10-30s of network fetch that used to hide under PyInstaller. Negligible on a
# ~25-minute release; kept simple. ensure can background the fetch later if it
# ever matters.)

bn_step_start 2 Build "Sidecar — fetch · build · sign" \
    log="$DESKTOP_DIR/build/ensure-sidecar.log" \
    narrative="Freezes the Python engine (PyInstaller), bundles FFmpeg, and signs every Mach-O under your identity."
_bn_t2=$SECONDS
export SIGN_IDENTITY
_BRISTLENOSE_RELEASE=1 "$SCRIPT_DIR/ensure-sidecar.sh" --force
bn_step_ok 2 elapsed=$((SECONDS-_bn_t2)) detail="built + signed under $SIGN_IDENTITY"

# ------------------------------------------------------------
# 2a. Bundle integrity self-test
# ------------------------------------------------------------
# Spawns the just-built sidecar binary with `doctor --self-test`. Asserts
# every runtime-data file (React SPA, codebook YAMLs, LLM prompts, locales,
# theme, Alembic migrations) is present in the bundle and non-trivial.
#
# Catches the BUG-3/4/5 class — data file in source, missing from bundle.
# Spec→bundle complement to step 1b's source→spec check (which catches
# "forgot to add to spec"). This step catches "in spec but PyInstaller
# silently dropped it." See docs/walkthroughs/c3-smoke-test results.md
# for the post-mortem.
#
# Runs the binary directly (single in-process exec, ~2-3s). No HTTP,
# no port handling, no subprocess orchestration.

bn_step_start 2a Build "Bundle self-test" \
    narrative="Spawns the just-built sidecar with doctor --self-test — asserts every runtime-data file is present in the bundle."
_bn_t2a=$SECONDS
SIDECAR_BIN="$DESKTOP_DIR/Bristlenose/Resources/bristlenose-sidecar/bristlenose-sidecar"
if [ ! -x "$SIDECAR_BIN" ]; then
    echo "error: sidecar binary not found or not executable: $SIDECAR_BIN" >&2
    exit 1
fi
# A MAS build signs the sidecar with com.apple.security.app-sandbox + inherit, which
# makes it ABORT when exec'd standalone (no parent .app to inherit the sandbox from —
# dies in _libsecinit_appsandbox). So the bare `doctor --self-test` below only works on
# non-sandbox (Debug / ad-hoc) builds. For a sandbox-signed sidecar, skip it: the
# spec→bundle datas are already gated by check-bundle-manifest.sh (step 1b, no exec)
# and by App Store Connect's own validation, and the runtime path is exercised via the
# launched .app. (14 Jul 2026 — added with the nested-sandbox signing fix.)
if codesign -d --entitlements - "$SIDECAR_BIN" 2>/dev/null | grep -q "app-sandbox"; then
    bn_step_skip 2a detail="app-sandbox-signed sidecar can't run standalone (MAS build); datas covered by 1b + ASC"
else
    "$SIDECAR_BIN" doctor --self-test >/dev/null
    bn_step_ok 2a elapsed=$((SECONDS-_bn_t2a)) detail="doctor --self-test: all runtime data present"
fi

# ------------------------------------------------------------
# 2b. THIRD-PARTY-BINARIES.md staleness check (C5)
# ------------------------------------------------------------
# Asserts the supply-chain inventory is up to date with the venv that
# produced the bundle. Runs the regen script in --check mode; exits 1
# if the file would change. Avoids the "shipped a release with stale
# licence/version inventory" failure mode.
#
# Skipped when pip-licenses isn't installed (release extra not pulled
# in) — keeps non-release builds friction-free.

PYTHON_BIN="$ROOT/.venv/bin/python"
if [ -x "$PYTHON_BIN" ] && "$PYTHON_BIN" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('piplicenses') else 1)" 2>/dev/null; then
    bn_step_start 2b Build "Supply-chain inventory"
    _bn_t2b=$SECONDS
    "$PYTHON_BIN" "$ROOT/scripts/generate-third-party-binaries.py" --check >/dev/null
    bn_step_ok 2b elapsed=$((SECONDS-_bn_t2b)) detail="THIRD-PARTY-BINARIES.md fresh"
else
    bn_step_skip 2b phase=Build name="Supply-chain inventory" detail="pip-licenses not installed (release extra)"
fi

# ------------------------------------------------------------
# 3-4. Signing — now performed inside ensure-sidecar (step 2)
# ------------------------------------------------------------
# Both sign-ffmpeg.sh and sign-sidecar.sh are invoked by ensure-sidecar.sh under
# a single identity, with a post-sign `codesign --verify --deep --strict`. No
# separate sign steps here.

# Ad-hoc runs stop here — xcodebuild with the manual-signing Release
# config requires a real Apple Distribution identity.
if [ "$SIGN_IDENTITY" = "-" ]; then
    bn_meta done_title="✓ Ad-hoc signing stage complete"
    bn_art "note" "skipped archive + export — Release config requires a real Apple Distribution identity"
    bn_art "next" "set SIGN_IDENTITY to the Apple Distribution cert to exercise the full pipeline"
    bn_done ok
    exit 0
fi

# ------------------------------------------------------------
# 5. xcodebuild archive
# ------------------------------------------------------------
# The Release config (pbxproj) is manual-signing against the Apple
# Distribution cert + "Bristlenose Mac App Store" profile. The Copy
# Sidecar Resources build phase picks up the signed tree from
# desktop/Bristlenose/Resources/bristlenose-sidecar/.

ARCHIVE_PATH="$DESKTOP_DIR/build/Bristlenose.xcarchive"
EXPORT_DIR="$DESKTOP_DIR/build/export"
PROJECT_DIR="$DESKTOP_DIR/Bristlenose"
EXPORT_OPTIONS="$PROJECT_DIR/ExportOptions.plist"
ARCHIVE_LOG="$DESKTOP_DIR/build/xcodebuild-archive.log"
EXPORT_LOG="$DESKTOP_DIR/build/xcodebuild-export.log"

rm -rf "$ARCHIVE_PATH" "$EXPORT_DIR"

# The sidecar was already built + signed with the real identity in step 2
# (ensure-sidecar --force). Skip the redundant in-archive "Ensure Sidecar Fresh"
# phase: xcodebuild inherits the exported real SIGN_IDENTITY but NOT the one-shot
# _BRISTLENOSE_RELEASE=1, so the phase's ensure-sidecar.sh would hit its own guard
# ("refusing to sign with a real identity outside build-all.sh") and the archive
# fails. Copy Sidecar Resources' check-sidecar-freshness.sh gate remains the
# independent backstop that the embedded bundle is current.
export BRISTLENOSE_SKIP_SIDECAR_ENSURE=1

bn_step_start 5 Build "Xcode archive" \
    log="$ARCHIVE_LOG" \
    narrative="Compiles + signs the native app shell. Opaque subprocess — tail the log for the live stream."
_bn_t5=$SECONDS
if ! xcodebuild \
    -project "$PROJECT_DIR/Bristlenose.xcodeproj" \
    -scheme Bristlenose \
    -configuration Release \
    -destination "generic/platform=macOS" \
    -archivePath "$ARCHIVE_PATH" \
    archive \
    > "$ARCHIVE_LOG" 2>&1; then
    bn_step_fail 5 detail="xcodebuild archive failed"
    bn_done fail
    echo "error: xcodebuild archive failed. tail:" >&2
    tail -50 "$ARCHIVE_LOG" >&2
    exit 1
fi
bn_step_ok 5 elapsed=$((SECONDS-_bn_t5)) detail="Release · manual-signed · Bristlenose.xcarchive"

# ------------------------------------------------------------
# 6. xcodebuild -exportArchive
# ------------------------------------------------------------

bn_step_start 6 Package "Export → .pkg" \
    narrative="Wraps the signed app in an App Store installer (method reads ExportOptions.plist)."
_bn_t6=$SECONDS
if ! xcodebuild \
    -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_DIR" \
    -exportOptionsPlist "$EXPORT_OPTIONS" \
    > "$EXPORT_LOG" 2>&1; then
    bn_step_fail 6 detail="xcodebuild -exportArchive failed"
    bn_done fail
    echo "error: xcodebuild -exportArchive failed. tail:" >&2
    tail -50 "$EXPORT_LOG" >&2
    exit 1
fi

# method=app-store-connect produces a .pkg (App Store upload format),
# not a standalone .app. Steps 7–9 (release-binary check, profile sanity,
# notarisation + staple) need a .app, so when the export dir holds only
# a .pkg we fall back to the .app inside the .xcarchive — it's the same
# signed bundle, just unwrapped. Methods that emit .app directly
# (developer-id, mac-application) keep using $EXPORT_DIR as before.
EXPORTED_APP=$(find "$EXPORT_DIR" -maxdepth 2 -name "*.app" -type d | head -1)
EXPORTED_PKG=$(find "$EXPORT_DIR" -maxdepth 2 -name "*.pkg" -type f | head -1)
if [ -z "$EXPORTED_APP" ]; then
    ARCHIVE_APP=$(find "$ARCHIVE_PATH/Products/Applications" -maxdepth 1 -name "*.app" -type d | head -1)
    if [ -n "$ARCHIVE_APP" ] && [ -n "$EXPORTED_PKG" ]; then
        EXPORTED_APP="$ARCHIVE_APP"
        echo "note: app-store export produced .pkg only — using .app from xcarchive for downstream gates" >&2
    else
        bn_step_fail 6 detail="no .app found under export dir or xcarchive"
        bn_done fail
        echo "error: no .app found under $EXPORT_DIR or in $ARCHIVE_PATH/Products/Applications" >&2
        exit 1
    fi
fi
_bn_pkg_detail="$(basename "$EXPORTED_APP")"
[ -n "$EXPORTED_PKG" ] && _bn_pkg_detail="$(basename "$EXPORTED_PKG") · $(du -h "$EXPORTED_PKG" 2>/dev/null | cut -f1)"
bn_step_ok 6 elapsed=$((SECONDS-_bn_t6)) detail="$_bn_pkg_detail"

# ------------------------------------------------------------
# 7. check-release-binary.sh post-export
# ------------------------------------------------------------
# Scans every Mach-O in the exported .app for:
#   - BRISTLENOSE_DEV_* string literals (dev escape-hatch leak)
#   - get-task-allow entitlement (Debug-only; App-Store-rejected)
# Skips Contents/Resources/bristlenose-sidecar/* (Python strings
# expected; no Swift #if DEBUG invariant applies).

bn_step_start 7 Verify "Release-binary scan" \
    narrative="Scans every Mach-O for dev escape-hatch literals + the get-task-allow entitlement."
_bn_t7=$SECONDS
_bn_rb_log="$DESKTOP_DIR/build/check-release-binary.log"
if "$SCRIPT_DIR/check-release-binary.sh" "$EXPORTED_APP" > "$_bn_rb_log" 2>&1; then
    bn_step_ok 7 elapsed=$((SECONDS-_bn_t7)) detail="no BRISTLENOSE_DEV_* literals · no get-task-allow"
else
    bn_step_fail 7 log="$_bn_rb_log" detail="disallowed string or entitlement in a shipping binary"
    bn_done fail
    cat "$_bn_rb_log" >&2
    exit 1
fi

# ------------------------------------------------------------
# 8. Provisioning profile sanity check
# ------------------------------------------------------------
# Assert the embedded profile matches our bundle ID + team ID. Xcode
# sometimes embeds a stale or wrong profile when manual signing is
# misconfigured — easier to catch here than at App Store upload time.

bn_step_start 8 Verify "Provisioning profile" \
    narrative="Asserts the embedded profile matches our bundle ID + team ID."
_bn_t8=$SECONDS
EMBEDDED_PROFILE="$EXPORTED_APP/Contents/embedded.provisionprofile"
if [ ! -f "$EMBEDDED_PROFILE" ]; then
    echo "error: embedded.provisionprofile missing from exported app." >&2
    echo "check ExportOptions.plist and pbxproj signing settings." >&2
    exit 1
fi

# security cms -D decodes the PKCS#7 wrapper into an XML plist.
# PlistBuddy needs a real file (can't read stdin), so stage through
# desktop/build/.
PROFILE_DECODED="$DESKTOP_DIR/build/embedded-profile.plist"
security cms -D -i "$EMBEDDED_PROFILE" -o "$PROFILE_DECODED" 2>/dev/null

# The Mac App Store profile declares the entitlements using the
# com.apple.* reverse-DNS keys (NOT the iOS-style short keys).
PROFILE_APP_ID=$(/usr/libexec/PlistBuddy \
    -c "Print :Entitlements:com.apple.application-identifier" \
    "$PROFILE_DECODED")
PROFILE_TEAM_ID=$(/usr/libexec/PlistBuddy \
    -c "Print :Entitlements:com.apple.developer.team-identifier" \
    "$PROFILE_DECODED")

# application-identifier = "<TEAMID>.<bundle>".
EXPECTED_APP_ID="${TEAM_ID}.app.bristlenose"
if [ "$PROFILE_APP_ID" != "$EXPECTED_APP_ID" ]; then
    echo "error: embedded profile application-identifier mismatch." >&2
    echo "  expected: $EXPECTED_APP_ID" >&2
    echo "  found:    $PROFILE_APP_ID" >&2
    exit 1
fi
if [ "$PROFILE_TEAM_ID" != "$TEAM_ID" ]; then
    echo "error: embedded profile team ID mismatch." >&2
    echo "  expected: $TEAM_ID" >&2
    echo "  found:    $PROFILE_TEAM_ID" >&2
    exit 1
fi
bn_step_ok 8 elapsed=$((SECONDS-_bn_t8)) detail="$PROFILE_APP_ID / $PROFILE_TEAM_ID"

# ------------------------------------------------------------
# 9. Notarisation + stapling
# ------------------------------------------------------------
# `notarytool` only accepts Developer ID-signed binaries — it explicitly
# rejects Apple Distribution-signed builds with "not signed with a valid
# Developer ID certificate". App Store / TestFlight builds are validated
# server-side after upload to App Store Connect, NOT via notarytool. So
# when `method=app-store(-connect)` we skip steps 9 and 10[a] entirely;
# the .pkg in $EXPORT_DIR is the alpha deliverable, ready for Transporter
# / `xcrun altool --upload-app`.
#
# `ditto` is mandatory for zipping a .app for notarisation — plain
# `zip` mangles extended attributes and symlinks, producing a zip
# that notarytool rejects. Staple the .app (not the zip).

EXPORT_METHOD=$(/usr/libexec/PlistBuddy -c "Print :method" "$EXPORT_OPTIONS" 2>/dev/null || echo "")
case "$EXPORT_METHOD" in
    app-store|app-store-connect)
        bn_step_skip 9 phase=Verify name="Notarisation" detail="method=$EXPORT_METHOD (App Store Connect validates server-side)"
        SKIP_NOTARISE=1
        ;;
    *)
        SKIP_NOTARISE=0
        ;;
esac

if [ "$SKIP_NOTARISE" = "0" ]; then
bn_step_start 9 Verify "Notarisation" \
    narrative="Developer-ID path — submit to Apple, wait, then staple. (Skipped for App Store methods.)"
_bn_t9=$SECONDS
NOTARY_ZIP="$DESKTOP_DIR/build/$(basename "$EXPORTED_APP").zip"
rm -f "$NOTARY_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$EXPORTED_APP" "$NOTARY_ZIP"
echo "    zip: $NOTARY_ZIP"

echo "    submitting to Apple notarisation service (this can take"
echo "    1–15 minutes; --wait blocks until Apple's response)..."
SUBMIT_LOG="$DESKTOP_DIR/build/notarytool-submit.log"
if ! xcrun notarytool submit "$NOTARY_ZIP" \
        --keychain-profile "$NOTARY_PROFILE" \
        --wait \
        --output-format plist \
        > "$SUBMIT_LOG" 2>&1; then
    echo "error: notarytool submit failed. tail:" >&2
    tail -50 "$SUBMIT_LOG" >&2
    exit 1
fi

# Extract the submission UUID from the plist-formatted output.
# `notarytool submit --output-format plist` writes a top-level dict
# with :id set to the UUID.
SUBMISSION_ID=$(
    /usr/libexec/PlistBuddy -c "Print :id" "$SUBMIT_LOG" 2>/dev/null || true
)
if [ -z "$SUBMISSION_ID" ]; then
    echo "error: could not extract submission UUID from notarytool output." >&2
    cat "$SUBMIT_LOG" >&2
    exit 1
fi

echo "    submission UUID: $SUBMISSION_ID"

# Don't trust `notarytool history` — it can show a cached prior run.
# Explicitly fetch this submission's log and assert Accepted.
LOG_JSON="$DESKTOP_DIR/build/notarytool-log.json"
xcrun notarytool log "$SUBMISSION_ID" \
    --keychain-profile "$NOTARY_PROFILE" \
    "$LOG_JSON"

STATUS=$(/usr/bin/python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' \
    "$LOG_JSON")

if [ "$STATUS" != "Accepted" ]; then
    echo "error: notarisation status '$STATUS' (expected Accepted)." >&2
    echo "log: $LOG_JSON" >&2
    /usr/bin/python3 -c \
        'import json,sys; d=json.load(open(sys.argv[1])); [print(i) for i in d.get("issues",[])[:10]]' \
        "$LOG_JSON" >&2
    exit 1
fi
echo "    status: Accepted" >&2

xcrun stapler staple "$EXPORTED_APP"
bn_step_ok 9 elapsed=$((SECONDS-_bn_t9)) detail="notarised + stapled"
fi  # end SKIP_NOTARISE guard

# ------------------------------------------------------------
# 10. Final verification battery
# ------------------------------------------------------------

if [ "$SKIP_NOTARISE" = "0" ]; then
xcrun stapler validate "$EXPORTED_APP"
bn_gate a ok "Notarisation staple" "stapler validate passed"
else
bn_gate a skip "Notarisation staple" "App Store validates server-side"
fi

# Local Gatekeeper assessment only makes sense for notarised Developer ID
# builds. Apple Distribution / App Store builds are validated server-side
# by App Store Connect after upload — spctl will always reject them locally
# because they lack the notarised-Developer-ID provenance Gatekeeper expects
# for standalone exec on this machine. For app-store flow we instead verify
# the .pkg installer signature with pkgutil.
if [ "$SKIP_NOTARISE" = "0" ]; then
    SPCTL_OUT=$(spctl -a -t exec -vv "$EXPORTED_APP" 2>&1)
    if ! grep -q "accepted" <<< "$SPCTL_OUT"; then
        echo "error: spctl did not accept the app." >&2
        echo "$SPCTL_OUT" >&2
        exit 1
    fi
    bn_gate b ok "Gatekeeper (spctl)" "accepted"
elif [ -n "$EXPORTED_PKG" ]; then
    PKGUTIL_OUT=$(pkgutil --check-signature "$EXPORTED_PKG" 2>&1)
    if ! grep -q "Status: signed by a developer certificate issued by Apple" <<< "$PKGUTIL_OUT" \
       && ! grep -q "Status: signed by a certificate trusted for current user" <<< "$PKGUTIL_OUT"; then
        echo "error: pkgutil did not accept the .pkg signature." >&2
        echo "$PKGUTIL_OUT" >&2
        exit 1
    fi
    bn_gate b ok "Installer signature" "signed, trusted for current user"
else
    bn_gate b skip "Installer signature" "no .pkg and notarisation skipped"
fi

codesign --verify --deep --strict --verbose=2 "$EXPORTED_APP" \
    2>"$DESKTOP_DIR/build/codesign-verify.log" \
    || { cat "$DESKTOP_DIR/build/codesign-verify.log" >&2; exit 1; }
bn_gate c ok "Code signature" "--deep --strict valid"

OUTER_BIN="$EXPORTED_APP/Contents/MacOS/Bristlenose"
OUTER_ENTS=$(codesign -d --entitlements :- "$OUTER_BIN" 2>/dev/null || true)
# Xcode may record the key with <false/>; only flag <true/>.
if grep -A1 "get-task-allow" <<< "$OUTER_ENTS" | grep -q "<true/>"; then
    echo "error: outer binary has get-task-allow=TRUE" >&2
    echo "$OUTER_ENTS" | sed 's/^/    /' >&2
    exit 1
fi
bn_gate d ok "get-task-allow" "absent (debug entitlement)"

CS_FLAGS=$(codesign -dvvv "$OUTER_BIN" 2>&1 || true)
if ! grep -qE "flags=.*runtime" <<< "$CS_FLAGS"; then
    echo "error: outer binary is NOT signed with Hardened Runtime (--options=runtime)" >&2
    echo "       set ENABLE_HARDENED_RUNTIME = YES in the Release config" >&2
    grep -E "^(Signature|CodeDirectory)" <<< "$CS_FLAGS" | sed 's/^/    /' >&2
    exit 1
fi
bn_gate d2 ok "Hardened Runtime" "flags include runtime"

REQ=$(codesign -d --requirements - "$OUTER_BIN" 2>&1 || true)
if ! grep -q "$TEAM_ID" <<< "$REQ"; then
    echo "error: designated requirement does not reference $TEAM_ID" >&2
    echo "$REQ" | sed 's/^/    /' >&2
    exit 1
fi
bn_gate e ok "Designated requirement" "references Team $TEAM_ID"

HOST_MANIFEST="$EXPORTED_APP/Contents/Resources/PrivacyInfo.xcprivacy"
SIDECAR_MANIFEST="$EXPORTED_APP/Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy"
for m in "$HOST_MANIFEST" "$SIDECAR_MANIFEST"; do
    if [ ! -f "$m" ]; then
        echo "error: privacy manifest missing at expected path: $m" >&2
        echo "       (check Copy Bundle Resources phase in the xcodeproj.)" >&2
        exit 1
    fi
    if ! plutil -lint "$m" >/dev/null 2>&1; then
        echo "error: privacy manifest fails plutil -lint: $m" >&2
        plutil -lint "$m" >&2 || true
        exit 1
    fi
done
bn_gate f ok "Privacy manifests" "host + sidecar present, lint-clean"

SIGN_MANIFEST="$DESKTOP_DIR/build/sign-manifest.json"
if [ "$SKIP_NOTARISE" = "0" ]; then
    bn_meta done_title="✓ Bristlenose.app notarised and stapled"
    bn_art "app" "$EXPORTED_APP"
    bn_art "archive" "$ARCHIVE_PATH"
    bn_art "sign manifest" "$SIGN_MANIFEST"
    bn_art "notary log" "$LOG_JSON"
else
    bn_meta done_title="✓ Ready for App Store Connect"
    _bn_size=$(du -h "$EXPORTED_PKG" 2>/dev/null | cut -f1)
    bn_art "artifact" "$EXPORTED_PKG"
    bn_art "size" "${_bn_size:-?} · ready for App Store Connect"
    bn_art "signed" "$SIGN_IDENTITY"
    bn_art "next" "drag into Transporter.app, or: xcrun altool --upload-app -f Bristlenose.pkg --type macos --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>"
fi
bn_done ok
