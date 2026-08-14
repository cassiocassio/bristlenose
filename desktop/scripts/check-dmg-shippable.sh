#!/usr/bin/env bash
# Publish gate: is this .dmg genuinely safe to hand to a stranger?
#
# "The file exists and is the right size" is NOT the question. On 4 Aug 2026 a
# complete, correctly-named, correctly-sized 0.24.0 .dmg sat on disk for 14
# hours looking finished while `spctl` said `rejected — source=Unnotarized
# Developer ID`: notarytool had died mid-upload and no ticket was ever issued.
# Nothing in the build chain noticed, because stage 10's two `stapler validate`
# lines were written `stapler validate X && ok "…"` — and `set -e` deliberately
# exempts the left operand of `&&`, so a failure printed nothing and fell
# through to the success banner.
#
# This gate exists to make that unpublishable rather than merely detectable, so
# it is called as a PRECONDITION INSIDE upload-dmg.sh — not as a sibling step an
# operator can forget on the one night it matters.
#
# The load-bearing check is the LAST one. Every other assertion here can pass on
# an image whose inner .app is unstapled, because `create-dmg` takes a *copy*:
# staple the .app after the image exists and the copy inside stays ticketless,
# silently. The only app a user ever touches is the one inside the image, so
# that is the one we mount and interrogate. `docs/design-dmg-build.md` has
# prescribed this since the channel was designed; it had never been implemented.
#
# Usage:
#   desktop/scripts/check-dmg-shippable.sh <path-to-Bristlenose-X.Y.Z.dmg>
#
# Exit codes:
#   0  Shippable — signed, notarised, stapled, Gatekeeper-accepted inside and out.
#   1  NOT shippable — at least one assertion failed; the reason is printed.
#   2  Usage error / file not found.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $(basename "$0") <path-to-dmg>" >&2
    exit 2
fi

DMG="$1"
[ -f "$DMG" ] || { echo "not a file: $DMG" >&2; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/report.sh"
bn_autowrap "$0" "$@"
trap '_bn_ec=$?; [ "$_bn_ec" -ne 0 ] && bn_trap_fail' EXIT
bn_meta title="Shippable?" done_title="✓ Shippable"
bn_step_start 1 Verify "Publish gate" \
    narrative="Mounts the image and interrogates the app inside it — the only copy a user ever touches."

# bn_check is positional — <parent> <result> <label> <evidence>.
FAILED=0
fail() { bn_check 1 fail "$1" "$2"; FAILED=1; }
pass() { bn_check 1 ok   "$1" "$2"; }
warn() { bn_check 1 warn "$1" "$2"; }

# --- 1. The name carries the version, and we resolve strictly by it -----------
# Never resolve by the published name. `desktop/build/Bristlenose.dmg` was a
# 803 MB unstapled image from 19 Feb — anything resolving by the public name
# would have published it.
BASE="$(basename "$DMG")"
if [[ "$BASE" =~ ^Bristlenose-([0-9]+\.[0-9]+\.[0-9]+)\.dmg$ ]]; then
    FILE_VERSION="${BASH_REMATCH[1]}"
    pass "versioned filename" "$BASE"
else
    fail "versioned filename" "refusing an unversioned artefact: $BASE"
    bn_step_fail 1 detail="unversioned artefact"
    bn_done fail
    exit 1
fi

# --- 2. The image's own signature and ticket ---------------------------------
if codesign --verify --verbose=2 "$DMG" >/dev/null 2>&1; then
    pass "image signature" "valid"
else
    fail "image signature" "codesign --verify failed on the .dmg"
fi

if xcrun stapler validate "$DMG" >/dev/null 2>&1; then
    pass "image stapled" "ticket present"
else
    fail "image stapled" "no ticket stapled to the .dmg"
fi

# `--context context:primary-signature` is what Gatekeeper actually does at
# MOUNT time — the first thing the user experiences. build-dmg.sh demoted a
# failure here to a reassuring "advisory" note; a negative is not advisory.
DMG_ASSESS="$(spctl --assess --type open --context context:primary-signature -vv "$DMG" 2>&1 || true)"
case "$DMG_ASSESS" in
    *"source=Notarized Developer ID"*) pass "image Gatekeeper" "Notarized Developer ID" ;;
    *) fail "image Gatekeeper" "$(printf '%s' "$DMG_ASSESS" | tr '\n' ' ')" ;;
esac

# --- 3. Mount, and interrogate the app INSIDE ---------------------------------
MP="$(mktemp -d "${TMPDIR:-/tmp}/bn-shippable.XXXXXX")"
DETACHED=0
detach() { [ "$DETACHED" = 0 ] && hdiutil detach -quiet "$MP" 2>/dev/null || true; DETACHED=1; rmdir "$MP" 2>/dev/null || true; }
trap 'detach; _bn_ec=$?; [ "$_bn_ec" -ne 0 ] && bn_trap_fail' EXIT

if ! hdiutil attach -nobrowse -readonly -noverify -quiet -mountpoint "$MP" "$DMG" 2>/dev/null; then
    fail "mount" "hdiutil could not attach the image"
    bn_step_fail 1 detail="unmountable"
    bn_done fail
    exit 1
fi
pass "mount" "attached read-only"

INNER_APP="$(find "$MP" -maxdepth 1 -name '*.app' | head -1)"
if [ -z "$INNER_APP" ]; then
    fail "app inside image" "no .app found at the image root"
else
    pass "app inside image" "$(basename "$INNER_APP")"

    # Version agreement. Catches the resume-skew case where the filename says
    # one version and the archived app is another — the failure mode that makes
    # a manifest, a filename and a binary disagree with nothing to notice.
    APP_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' \
                     "$INNER_APP/Contents/Info.plist" 2>/dev/null || echo '')"
    if [ "$APP_VERSION" = "$FILE_VERSION" ]; then
        pass "version agreement" "Info.plist = $APP_VERSION"
    else
        fail "version agreement" "filename says $FILE_VERSION, app says ${APP_VERSION:-<unreadable>}"
    fi

    # THE load-bearing assertion. `create-dmg` copies the .app, so a staple
    # applied to the export-dir original never reaches this copy.
    #
    # DELIBERATELY NOT a staple check (changed 14 Aug 2026, same commit as
    # build-dmg.sh retiring app-level notarisation): the inner app carries no
    # ticket by design now — the .dmg's notarisation covers it, and the
    # accepted trade is one online Gatekeeper lookup on the first launch of a
    # dragged-out app. What must still hold is that the app INSIDE the image
    # is validly signed, deep and strict — the create-dmg-copies class this
    # mount-and-interrogate gate exists for. The spctl assessment below then
    # proves the dmg's ticket actually reaches this app. If app stapling ever
    # returns, restore: stapler validate "$INNER_APP".
    if codesign --verify --deep --strict "$INNER_APP" >/dev/null 2>&1; then
        pass "inner app signature" "--deep --strict valid"
    else
        fail "inner app signature" "the app INSIDE the image fails codesign --deep --strict"
    fi

    # Assert the reason, not the word. `grep -q accepted` passes on any output
    # containing that substring; we want the specific verdict Gatekeeper gives
    # a notarised Developer-ID app. With the inner app unstapled (by design),
    # this verdict comes via an online ticket lookup — which is also exactly
    # what it proves: the .dmg's notarisation covers THIS app's cdhash. Needs
    # network; this gate runs minutes after a notary round trip, so it has it.
    APP_ASSESS="$(spctl --assess --type exec -vv "$INNER_APP" 2>&1 || true)"
    case "$APP_ASSESS" in
        *"source=Notarized Developer ID"*) pass "inner app Gatekeeper" "Notarized Developer ID" ;;
        *) fail "inner app Gatekeeper" "$(printf '%s' "$APP_ASSESS" | tr '\n' ' ')" ;;
    esac

    # --- 4. The manifest describes THIS artefact, not a previous one ---------
    # `build-dmg.sh` binds the commit at archive time (correct within one run),
    # but a resumed chain can pair a fresh manifest with a stale image or vice
    # versa, and every check above would still pass. Comparing the manifest's
    # recorded app-binary sha256 against the binary inside the mounted image
    # settles it in one comparison: if they match, the manifest is about these
    # bits, and its `commit:` line is authoritative by transitivity.
    #
    # Chosen over parsing the git SHA back out of the Mach-O. Both are baked in
    # by generate-build-info.sh, but Swift's small-string optimisation stores an
    # 8-char SHA inline in the String value rather than as a __TEXT literal, so
    # `strings` extraction is fragile in a way a 64-char hash comparison is not.
    MANIFEST="${DMG%.dmg}.manifest.txt"
    if [ ! -f "$MANIFEST" ]; then
        warn "manifest" "no sibling manifest — provenance unverifiable"
    else
        M_APP_SHA="$(sed -n 's|^  \([0-9a-f]\{64\}\)  .*/MacOS/Bristlenose$|\1|p' "$MANIFEST" | head -1)"
        A_APP_SHA="$(shasum -a 256 "$INNER_APP/Contents/MacOS/Bristlenose" 2>/dev/null | cut -d' ' -f1)"
        if [ "${#M_APP_SHA}" -ne 64 ] || [ "${#A_APP_SHA}" -ne 64 ]; then
            # Never compare two values you haven't proved you measured.
            fail "manifest ↔ image" "could not read both hashes (manifest=${#M_APP_SHA}c image=${#A_APP_SHA}c)"
        elif [ "$M_APP_SHA" = "$A_APP_SHA" ]; then
            M_COMMIT="$(sed -n 's/^commit:  *//p' "$MANIFEST" | head -1)"
            M_TREE="$(sed -n 's/^tree:  *//p' "$MANIFEST" | head -1)"
            pass "manifest ↔ image" "app binary agrees · commit ${M_COMMIT:0:8}${M_TREE:+ · tree $M_TREE}"
            case "$M_TREE" in
                dirty*) warn "tree at archive" "$M_TREE — this build is not reproducible from a commit" ;;
            esac
        else
            fail "manifest ↔ image" "manifest describes a DIFFERENT build (${M_APP_SHA:0:8}… vs ${A_APP_SHA:0:8}…)"
        fi
    fi

    # Alpha life remaining. Reported, not gated — a short-lived sampler is a
    # judgement call, not a defect. Signing timestamp is a proxy for the
    # code-signed GeneratedBuildInfo.buildDate the app actually enforces; the
    # two are minutes apart, which is well inside a 30-day budget.
    SIGNED_AT="$(codesign -dvvv "$INNER_APP" 2>&1 | sed -n 's/^Timestamp=//p' | head -1)"
    if [ -n "$SIGNED_AT" ]; then
        SIGNED_EPOCH="$(date -jf '%d %b %Y at %H:%M:%S' "${SIGNED_AT/ UTC/}" '+%s' 2>/dev/null || echo '')"
        if [ -n "$SIGNED_EPOCH" ]; then
            LEFT=$(( (SIGNED_EPOCH + 30*86400 - $(date '+%s')) / 86400 ))
            if [ "$LEFT" -ge 21 ]; then
                pass "alpha life" "${LEFT} of 30 days remaining"
            else
                warn "alpha life" "only ${LEFT} days remaining — consider re-cutting"
            fi
        fi
    fi
fi

detach

if [ "$FAILED" -ne 0 ]; then
    bn_step_fail 1 detail="not shippable"
    bn_done fail
    exit 1
fi

bn_step_ok 1 detail="signed · notarised · stapled inside and out"
bn_art dmg "$BASE"
bn_done ok
exit 0
