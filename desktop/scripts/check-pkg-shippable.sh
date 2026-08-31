#!/usr/bin/env bash
# Publish gate: is this .pkg genuinely safe to send to App Store Connect?
#
# Sibling of check-dmg-shippable.sh, same doctrine, different channel. It is called
# as a PRECONDITION INSIDE upload-testflight.sh — not as a sibling step an operator
# can forget on the one night it matters.
#
# WHY IT INTERROGATES THE PKG PAYLOAD, NOT THE ARCHIVE
#
# build-all.sh's gates c-f read $EXPORTED_APP, which under method=app-store is the
# .app from the *xcarchive* — export yields only a .pkg, so :335-348 falls back and
# prints a `note:` saying so. So nothing has ever checked the bundle that actually
# ships. That is the .dmg channel's load-bearing lesson (create-dmg takes a COPY;
# stapling the original leaves the copy ticketless) applied to this channel, where
# it turns out to be a live gap rather than a hypothetical one.
#
# Verified 7 Aug 2026 that this is worth doing: `pkgutil --expand-full` round-trips
# the signature intact — the extracted payload reports "valid on disk" and
# "satisfies its Designated Requirement" under codesign --verify --deep --strict,
# and its entitlements are readable. If that ever stops being true, this script
# fails loudly rather than quietly falling back to the archive copy.
#
# WHAT IT CHECKS, AND WHY EACH ONE IS HERE
#
# Four of these exist because this project actually took the rejection:
#   - nested-executable app-sandbox     -> ASC rejection #2, 14 Jul 2026
#   - framework --identifier            -> ASC rejection #3, 14 Jul 2026
#   - host app-sandbox (ITMS-90296)     -> auto-reject
#   - Hardened Runtime (ITMS-90287)     -> auto-reject
# Local `codesign --verify` passes without any of them. That is the whole point:
# a battery written to prevent upload rejections that omits the rejections you
# received is decoration.
#
# EVERY ASSERTION IS `|| die`, NEVER `&& ok`.
# POSIX shells exempt the left operand of && from errexit, so `cmd && ok "passed"`
# is a gate that cannot fail — it prints nothing and falls through to the success
# banner. Two of build-dmg.sh stage 10's four gates were written that way and were
# decorative through two releases (fixed 4 Aug 2026, fc1d6ca7); the near-miss was a
# complete, correctly-sized .dmg that sat for 14 hours looking finished while spctl
# called it `rejected — Unnotarized Developer ID`.
#
# Usage:
#   check-pkg-shippable.sh <path-to-Bristlenose.pkg>
#
# Environment:
#   BRISTLENOSE_ASC_KEY_ID / _ISSUER_ID   if set (or in .ship-local.conf), the
#                                         final check runs Apple's own validator.
#   SIGN_IDENTITY                         "-" (ad-hoc) skips the Apple round trip.
#
# Exit codes:
#   0  Shippable.
#   1  NOT shippable — at least one assertion failed; the reason is printed.
#   2  Usage error / file not found.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $(basename "$0") <path-to-pkg>" >&2
    exit 2
fi

PKG="$1"
[ -f "$PKG" ] || { echo "not a file: $PKG" >&2; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEAM_ID="${TEAM_ID:-Z56GZVA2QB}"  # env (release driver) > literal fallback
BUNDLE_ID="app.bristlenose"
INSTALLER_CERT="3rd Party Mac Developer Installer"

FAILURES=0
say()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %-34s %s\n' "$1" "${2:-}"; }
skip() { printf '  \033[2m—\033[0m %-34s %s\n' "$1" "${2:-}"; }
die()  { printf '  \033[31m✗\033[0m %-34s %s\n' "$1" "${2:-}" >&2; FAILURES=$((FAILURES+1)); }

printf '\nSHIPPABLE?  %s\n\n' "$(basename "$PKG")"

# ---------------------------------------------------------------------------
# 1. The installer wrapper
# ---------------------------------------------------------------------------
SIGOUT=$(pkgutil --check-signature "$PKG" 2>&1) || true

grep -q "Status: signed by" <<<"$SIGOUT" \
    || die "installer signature" "pkgutil reports unsigned"

# Assert the SPECIFIC cert, not merely "trusted". A Developer ID Installer pkg
# satisfies the loose test, and there is a live Developer ID channel writing
# artefacts into the same desktop/build/ tree.
if grep -q "$INSTALLER_CERT" <<<"$SIGOUT"; then
    ok "installer certificate" "$INSTALLER_CERT"
else
    die "installer certificate" "expected '$INSTALLER_CERT'; got: $(grep -m1 '1\.' <<<"$SIGOUT" | sed 's/^ *//')"
fi

# ---------------------------------------------------------------------------
# 2. Expand the payload — the bundle the recipient actually receives
# ---------------------------------------------------------------------------
WORK=$(mktemp -d "${TMPDIR:-/tmp}/bn-pkg-gate.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

pkgutil --expand-full "$PKG" "$WORK/x" >/dev/null 2>&1 \
    || { die "expand payload" "pkgutil --expand-full failed"; echo; exit 1; }

# Exactly one .app, or we are not looking at what we think we are.
mapfile -t APPS < <(find "$WORK/x" -maxdepth 6 -name '*.app' -type d)
if [ "${#APPS[@]}" -ne 1 ]; then
    die "payload shape" "expected exactly one .app, found ${#APPS[@]}"
    echo; exit 1
fi
APP="${APPS[0]}"
ok "payload" "1 app · $(basename "$APP")"

OUTER="$APP/Contents/MacOS/Bristlenose"
[ -x "$OUTER" ] || { die "host binary" "missing at Contents/MacOS/Bristlenose"; echo; exit 1; }

# ---------------------------------------------------------------------------
# 3. Identity — the pkg must be the tree you think you built
#
# "Expected" is read from the working tree, NOT from the artefact. Comparing the
# artefact to itself is a tautology, and the .pkg filename carries no version, so
# resolving "the newest pkg" cannot tell you which build it is.
# ---------------------------------------------------------------------------
PLIST="$APP/Contents/Info.plist"
GOT_ID=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$PLIST" 2>/dev/null || echo "")
GOT_VER=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST" 2>/dev/null || echo "")
GOT_BUILD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$PLIST" 2>/dev/null || echo "")

if [ "$GOT_ID" = "$BUNDLE_ID" ]; then
    ok "bundle identifier" "$GOT_ID"
else
    die "bundle identifier" "expected $BUNDLE_ID, got '${GOT_ID:-<none>}'"
fi

PBXPROJ="$ROOT/desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj"
WANT_VER=$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$ROOT/bristlenose/__init__.py" 2>/dev/null | head -1)
WANT_BUILD=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([0-9]*\);.*/\1/p' "$PBXPROJ" 2>/dev/null | head -1)

# Both guards used to read `[ -n "$WANT" ] && [ mismatch ]`, so an EMPTY
# extraction — an Xcode release reformatting the pbxproj, a changed __version__
# style, a moved script resolving ROOT wrong — made both false, fell through to
# the else, and printed a confident "agrees with tree" for a comparison that
# never ran. This is the only defence against the stale-artefact class this
# script's own header warns about (a live Developer ID build writes into the
# same desktop/build/ tree, and the .pkg filename carries no version), in a file
# whose stated doctrine is that every assertion must be able to fail.
[ -n "$WANT_VER" ]   || die "version" "cannot read __version__ from bristlenose/__init__.py — comparison impossible"
[ -n "$WANT_BUILD" ] || die "build number" "cannot read CURRENT_PROJECT_VERSION from $PBXPROJ — comparison impossible"

# The pbxproj carries CURRENT_PROJECT_VERSION once per build configuration and
# `head -1` silently compares against whichever appears first. They are identical
# today and bump-version.py moves them together, so a divergence means something
# edited one by hand — worth saying rather than picking one arbitrarily.
PBX_BUILDS=$(sed -n 's/.*CURRENT_PROJECT_VERSION = \([0-9]*\);.*/\1/p' "$PBXPROJ" 2>/dev/null | sort -u | tr '\n' ' ')
case "$(printf '%s' "$PBX_BUILDS" | wc -w | tr -d ' ')" in
    0|1) : ;;
    *)   die "build number" "pbxproj configurations disagree: $PBX_BUILDS" ;;
esac

# Separate ifs, not if/elif: a version mismatch used to mask a simultaneous
# build-number mismatch. die() accumulates rather than exits, so both report.
VERSION_OK=1
if [ -n "$WANT_VER" ] && [ "$GOT_VER" != "$WANT_VER" ]; then
    die "marketing version" "pkg is $GOT_VER, working tree is $WANT_VER — stale artefact?"
    VERSION_OK=0
fi
if [ -n "$WANT_BUILD" ] && [ "$GOT_BUILD" != "$WANT_BUILD" ]; then
    die "build number" "pkg is $GOT_BUILD, working tree is $WANT_BUILD — stale artefact?"
    VERSION_OK=0
fi
if [ -n "$WANT_VER" ] && [ -n "$WANT_BUILD" ] && [ "$VERSION_OK" -eq 1 ]; then
    ok "version" "$GOT_VER ($GOT_BUILD) · agrees with tree"
fi

# ---------------------------------------------------------------------------
# 4. Signature validity
# ---------------------------------------------------------------------------
if codesign --verify --deep --strict "$APP" >"$WORK/codesign.log" 2>&1; then
    ok "code signature" "--deep --strict valid"
else
    die "code signature" "$(tail -1 "$WORK/codesign.log")"
fi

REQ=$(codesign -d --requirements - "$OUTER" 2>&1 || true)
if grep -q "$TEAM_ID" <<<"$REQ"; then
    ok "designated requirement" "references Team $TEAM_ID"
else
    die "designated requirement" "does not reference $TEAM_ID"
fi

# ---------------------------------------------------------------------------
# 5. Entitlements on the HOST binary
# ---------------------------------------------------------------------------
ENTS=$(codesign -d --entitlements :- "$OUTER" 2>/dev/null || echo "")

if grep -A1 'get-task-allow' <<<"$ENTS" | grep -q '<true/>'; then
    die "get-task-allow" "present and TRUE — Debug entitlement, App Store rejects"
else
    ok "get-task-allow" "absent"
fi

if grep -q 'com.apple.security.app-sandbox' <<<"$ENTS"; then
    ok "host app-sandbox" "present (ITMS-90296)"
else
    die "host app-sandbox" "MISSING — ITMS-90296 auto-reject"
fi

CSFLAGS=$(codesign -dvvv "$OUTER" 2>&1 || true)
if grep -qE 'flags=.*runtime' <<<"$CSFLAGS"; then
    ok "hardened runtime" "flags include runtime"
else
    die "hardened runtime" "MISSING — ITMS-90287 auto-reject"
fi

# ---------------------------------------------------------------------------
# 6. NESTED EXECUTABLES — ASC rejection #2, 14 Jul 2026
#
# Every nested Mach-O of type EXECUTABLE must carry app-sandbox. `codesign
# --verify` passes without it; only App Store Connect objects, after a 644 MB
# upload. Today that set is exactly four: the host, ffmpeg, ffprobe, and the
# sidecar — the same three-plus-host the 14 Jul rejection named.
#
# EXECUTABLES ONLY, and the distinction is load-bearing. `find -perm -111`
# matches 227 Mach-Os here, but 207 are *bundles* (Python .so extension modules)
# and 16 are *dylibs*. Libraries and bundles carry no entitlements at all — they
# inherit from the loading process — so demanding app-sandbox on them is
# meaningless. The first draft of this check did exactly that and reported
# "223 of 227 missing it" against a correctly-signed pkg: a false alarm loud
# enough to look like a blocker. A gate that cries wolf gets switched off, so
# the filter is `Mach-O .* executable`, not bare `Mach-O`.
# ---------------------------------------------------------------------------
MISSING_SANDBOX=(); TOTAL_MACHO=0
while IFS= read -r -d '' b; do
    file -b "$b" 2>/dev/null | grep -qE 'Mach-O.*executable' || continue
    TOTAL_MACHO=$((TOTAL_MACHO+1))
    codesign -d --entitlements :- "$b" 2>/dev/null | grep -q 'app-sandbox' \
        || MISSING_SANDBOX+=("${b#"$APP"/}")
done < <(find "$APP" -type f -perm -111 -print0)

if [ "${#MISSING_SANDBOX[@]}" -eq 0 ]; then
    ok "nested app-sandbox" "$TOTAL_MACHO Mach-Os, all sandboxed"
else
    die "nested app-sandbox" "${#MISSING_SANDBOX[@]} of $TOTAL_MACHO missing it"
    printf '        %s\n' "${MISSING_SANDBOX[@]:0:8}" >&2
fi

# ---------------------------------------------------------------------------
# 7. Framework identifiers — ASC rejection #3, 14 Jul 2026
#
# sign-sidecar.sh passes --identifier from each framework's CFBundleIdentifier.
# Nothing verified the result, so a change to its find predicate silently reverts
# to an auto-derived `Python-<hash>` and every other gate still passes.
# ---------------------------------------------------------------------------
BAD_IDENT=()
while IFS= read -r -d '' b; do
    file -b "$b" 2>/dev/null | grep -q 'Mach-O' || continue
    ident=$(codesign -dvv "$b" 2>&1 | sed -n 's/^Identifier=//p')
    [[ "$ident" =~ -[0-9a-f]{20,}$ ]] && BAD_IDENT+=("${b#"$APP"/} -> $ident")
done < <(find "$APP" -path '*.framework/Versions/*' -type f -perm -111 ! -name '*.*' -print0 2>/dev/null)

if [ "${#BAD_IDENT[@]}" -eq 0 ]; then
    ok "framework identifiers" "none auto-derived"
else
    die "framework identifiers" "${#BAD_IDENT[@]} auto-derived (Name-<hash>)"
    printf '        %s\n' "${BAD_IDENT[@]:0:5}" >&2
fi

# ---------------------------------------------------------------------------
# 8. Privacy manifests — parsed by ASC at upload since 1 May 2024
# ---------------------------------------------------------------------------
MISSING_MANIFEST=()
for m in "$APP/Contents/Resources/PrivacyInfo.xcprivacy" \
         "$APP/Contents/Resources/bristlenose-sidecar/PrivacyInfo.xcprivacy"; do
    if [ ! -f "$m" ]; then
        MISSING_MANIFEST+=("${m#"$APP"/} (absent)")
    elif ! plutil -lint "$m" >/dev/null 2>&1; then
        MISSING_MANIFEST+=("${m#"$APP"/} (malformed)")
    fi
done
if [ "${#MISSING_MANIFEST[@]}" -eq 0 ]; then
    ok "privacy manifests" "host + sidecar present, lint-clean"
else
    die "privacy manifests" "${MISSING_MANIFEST[*]}"
fi

# ---------------------------------------------------------------------------
# 9. Export compliance
#
# Silent-failure class: delete this key and EVERY other gate here still passes,
# while builds stop reaching testers — they sit in ASC as "Missing Compliance"
# forever, with no error anywhere in the build chain.
# ---------------------------------------------------------------------------
ENC=$(/usr/libexec/PlistBuddy -c 'Print :ITSAppUsesNonExemptEncryption' "$PLIST" 2>/dev/null || echo "MISSING")
if [ "$ENC" != "MISSING" ]; then
    ok "export compliance" "ITSAppUsesNonExemptEncryption = $ENC"
else
    die "export compliance" "ITSAppUsesNonExemptEncryption absent — builds stall in Missing Compliance"
fi

# ---------------------------------------------------------------------------
# 10. App Store §2.5.2 — re-run against the SIDECAR INSIDE THE PKG
#
# build-all.sh step 2c scans the source tree's sidecar. Fine inside one linear
# run; wrong under this script's premise, which is that the artefact handed to
# the uploader gets re-checked whatever produced it.
# ---------------------------------------------------------------------------
SIDECAR="$APP/Contents/Resources/bristlenose-sidecar"
SCANNER="$SCRIPT_DIR/check-sidecar-appstore-strings.sh"
if [ ! -d "$SIDECAR" ]; then
    die "§2.5.2 string scan" "no sidecar at Contents/Resources/bristlenose-sidecar"
elif [ ! -x "$SCANNER" ]; then
    skip "§2.5.2 string scan" "scanner not executable at $SCANNER"
elif "$SCANNER" "$SIDECAR" >"$WORK/pyz.log" 2>&1; then
    ok "§2.5.2 string scan" "no itms-services in bundled PYZ"
else
    die "§2.5.2 string scan" "$(tail -2 "$WORK/pyz.log" | tr '\n' ' ')"
fi

# ---------------------------------------------------------------------------
# 11. Provisioning profile expiry
#
# The canonical evening-waster: an expired profile archives fine locally and only
# App Store Connect objects. Warn at T-30 so it never becomes a surprise.
# ---------------------------------------------------------------------------
EMBEDDED="$APP/Contents/embedded.provisionprofile"
if [ ! -f "$EMBEDDED" ]; then
    die "provisioning profile" "no embedded.provisionprofile in the payload"
else
    security cms -D -i "$EMBEDDED" > "$WORK/prof.plist" 2>/dev/null || true
    EXP=$(/usr/libexec/PlistBuddy -c 'Print :ExpirationDate' "$WORK/prof.plist" 2>/dev/null || echo "")
    if [ -z "$EXP" ]; then
        die "provisioning profile" "could not read ExpirationDate"
    else
        EXP_EPOCH=$(date -j -f "%a %b %d %T %Z %Y" "$EXP" "+%s" 2>/dev/null || echo 0)
        NOW=$(date +%s)
        DAYS=$(( (EXP_EPOCH - NOW) / 86400 ))
        if [ "$EXP_EPOCH" -eq 0 ]; then
            die "provisioning profile" "unparseable ExpirationDate: $EXP"
        elif [ "$DAYS" -lt 0 ]; then
            die "provisioning profile" "EXPIRED ${DAYS#-} days ago"
        elif [ "$DAYS" -lt 30 ]; then
            say "  ⚠ provisioning profile             expires in $DAYS days — renew before it bites"
            ok "provisioning profile" "valid, $DAYS days left"
        else
            ok "provisioning profile" "valid, $DAYS days left"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 12. Apple's own validator — LAST, because it is the only one that costs a round
# trip. Skipped for ad-hoc builds and when no ASC credential is configured, so
# build-all.sh's every-build path stays offline.
# ---------------------------------------------------------------------------
CONF="$SCRIPT_DIR/.ship-local.conf"
# shellcheck source=/dev/null
[ -f "$CONF" ] && . "$CONF"
KEY_ID="${BRISTLENOSE_ASC_KEY_ID:-}"
ISSUER="${BRISTLENOSE_ASC_ISSUER_ID:-}"

if [ "${SIGN_IDENTITY:-}" = "-" ]; then
    skip "App Store validation" "ad-hoc identity — nothing to validate"
elif [ -z "$KEY_ID" ] || [ -z "$ISSUER" ]; then
    skip "App Store validation" "no ASC credential configured (see .ship-local.conf)"
elif [ "${BN_SKIP_ASC_VALIDATE:-}" = "1" ]; then
    # Set ONLY by upload-testflight.sh, which runs this gate as its precondition
    # and then immediately transfers the pkg with --upload-package — whose
    # server side runs the same validation on the same bytes minutes later.
    # Running validate-app here too shipped the 675 MB artefact to Apple TWICE
    # back to back (~8 min, ~10% of the release's wall clock) to learn the same
    # answer, and a server-rejectable pkg discovered at upload costs the same
    # transfer it would have cost to discover pre-upload. Expected loss: ~zero.
    # (This also covers the duplicate-build-number refusal that validate-app
    # used to catch pre-transfer — the upload rejects it identically.)
    # A STANDALONE gate run never sets this: there, validate-app is the best
    # dry run available — server-side, on the real artefact — and stays.
    skip "App Store validation" "skipped by the uploader — --upload-package revalidates server-side (BN_SKIP_ASC_VALIDATE=1)"
elif xcrun altool --validate-app "$PKG" --type macos \
        --apiKey "$KEY_ID" --apiIssuer "$ISSUER" >"$WORK/validate.log" 2>&1; then
    ok "App Store validation" "altool --validate-app: no issues"
else
    die "App Store validation" "altool rejected it — Apple's own words below"
    sed 's/^/        /' "$WORK/validate.log" >&2
fi

# ---------------------------------------------------------------------------
echo
if [ "$FAILURES" -eq 0 ]; then
    printf '  \033[32mSHIPPABLE\033[0m  %s · %s (%s)\n\n' \
        "$(du -h "$PKG" | cut -f1)" "$GOT_VER" "$GOT_BUILD"
    exit 0
fi
printf '  \033[31mNOT SHIPPABLE\033[0m  %d check(s) failed — do not upload.\n\n' "$FAILURES"
exit 1
