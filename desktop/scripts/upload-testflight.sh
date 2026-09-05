#!/usr/bin/env bash
# Send a signed .pkg to App Store Connect / TestFlight.
#
# Replaces dragging the .pkg into Transporter.app. That step was the one part of
# the release that was irreversible, outward-facing, unrecorded, and manual — and
# it recurs, because TestFlight builds expire 90 days after upload.
#
# THE GATE IS A PRECONDITION, NOT A SIBLING STEP.
# check-pkg-shippable.sh runs here, inside the uploader, and there is no flag to
# skip it. The .dmg channel learned this the hard way: a complete, correctly-sized
# 0.24.0 image sat for 14 hours looking finished while spctl called it
# `rejected — Unnotarized Developer ID`, because the check that would have caught
# it was a step someone could forget on the one night it mattered.
#
# WRITTEN FROM A MEASURED TRANSCRIPT, NOT THE MAN PAGE.
# Build 0.25.1 (2450) went up on 7 Aug 2026; every claim below was observed:
#   - 675 MB in 8.11 min (1.4 MB/s); processing then took ~2.5 min, not the 10-60
#     that was budgeted. --wait polls every 30s.
#   - Terminal block carries PROCESSINGSTATE, IS-ON-APP-STORE-CONNECT and
#     EXPIRATION-DATE. The last is the 90-day clock this whole thing services —
#     print Apple's date, don't compute one.
#   - EXPIRATION-DATE (hyphenated, outer block) is the real date. EXPIRATIONDATE
#     (no hyphen, nested under APP-STORE-ATTRIBUTES) is the literal placeholder
#     string "expirationDate". Parse the hyphenated one; they differ.
#   - --show-progress emits \r-overwritten bars that turned an 11-line log into
#     131 KB. TTY-gated below.
#
# A ZERO EXIT FROM altool IS NOT PROOF THE BUILD LANDED.
# There is a documented failure where altool exits 0, prints no error, and the
# build never appears in ASC — while ASC has registered the delivery, so the
# retry is then refused as a duplicate. So the verdict here is the terminal
# state, confirmed by a second, independent --build-status call. That call is
# cheap, needs no artefact, and works with an API key (unlike --list-providers,
# which is Apple-ID-only).
#
# Deliberately NOT here:
#   --dry-run       Apple's --validate-app IS the dry run: server-side, on the
#                   real artefact — run `check-pkg-shippable.sh <pkg>` standalone
#                   and it is the last check. (On THIS path the gate skips it,
#                   announced, via BN_SKIP_ASC_VALIDATE: the upload itself
#                   revalidates the same bytes server-side minutes later, so
#                   pre-validating shipped 675 MB to Apple twice per release.)
#   --validate-only `check-pkg-shippable.sh <pkg>` already is that verb.
#   --force/--skip  There is no way to bypass the gate. That is the design.
#
# Usage:
#   upload-testflight.sh [<path-to-pkg>]     # defaults to the standard export path
#
# Config — desktop/scripts/.ship-local.conf (gitignored), or the environment:
#   BRISTLENOSE_ASC_KEY_ID       API key id; altool finds ~/.private_keys/AuthKey_<id>.p8
#   BRISTLENOSE_ASC_ISSUER_ID    issuer uuid (per-team, not per-key)
#   BRISTLENOSE_ASC_APPLE_ID     numeric app id — passed so altool never has to
#                                INFER the app record from the bundle id (see below)
# None are secrets. The secret is the .p8, which altool reads by name and which
# never appears here or in any log.
#
# Exit codes:
#   0  Delivered and confirmed present in App Store Connect.
#   1  Refused, failed, or landed in a state we can't confirm — read the output.
#   2  Usage / not configured.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GATE="$SCRIPT_DIR/check-pkg-shippable.sh"
DEFAULT_PKG="$ROOT/desktop/build/export/Bristlenose.pkg"
LOG_DIR="$ROOT/desktop/build"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
say()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %-22s %s\n' "$1" "${2:-}"; }
die()  { printf '\n  \033[31m✗\033[0m %s\n\n' "$*" >&2; exit 1; }

case "${1:-}" in
    -h|--help) sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit 0 ;;
    --dry-run|--validate-only|--force)
        cat >&2 <<EOF
$1 does not exist, deliberately.

  Want a dry run?     desktop/scripts/check-pkg-shippable.sh <pkg>
                      Its last check IS Apple's validator, server-side, on the
                      real artefact — a better dry run than a local one.
  Want to skip a gate? No. That is the design.
EOF
        exit 2 ;;
esac

# ---------------------------------------------------------------------------
# --probe <version>: does App Store Connect hold a build of <version>? Exists
# for release.sh's probe_done, which must answer "is this irreversible step
# already done in the world?" without a human. altool cannot answer it — its
# --build-status needs the delivery id, which is ephemeral to the upload — so
# this asks the ASC API for builds filtered by marketing version. Read-only.
#
# Exit contract (release.sh probe_done's tri-state, NOT this script's usual):
#   0  a build of <version> exists on ASC
#   1  probed successfully; no such build
#   3  could not look (missing config/key/tooling, auth or network failure).
#      NEVER conflate with 1: "I could not look" and "I looked and it is not
#      there" lead to opposite actions on a step that cannot be un-performed.
# No expired filter, deliberately: the question is "was a build of V ever
# delivered", and an expired build still proves the upload happened.
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--probe" ]; then
    PROBE_V="${2:-}"
    [ -n "$PROBE_V" ] || { echo "usage: upload-testflight.sh --probe <X.Y.Z>" >&2; exit 3; }
    CONF="$SCRIPT_DIR/.ship-local.conf"
    # shellcheck source=/dev/null
    [ -f "$CONF" ] && . "$CONF"
    for _v in BRISTLENOSE_ASC_KEY_ID BRISTLENOSE_ASC_ISSUER_ID BRISTLENOSE_ASC_APPLE_ID; do
        [ -n "${!_v:-}" ] || { echo "probe: $_v not configured — cannot look" >&2; exit 3; }
    done
    _KEYFILE="$HOME/.private_keys/AuthKey_${BRISTLENOSE_ASC_KEY_ID}.p8"
    [ -f "$_KEYFILE" ] || { echo "probe: no key at $_KEYFILE — cannot look" >&2; exit 3; }
    _PY="$ROOT/.venv/bin/python"; [ -x "$_PY" ] || _PY="python3"
    KEYFILE="$_KEYFILE" KEY_ID="$BRISTLENOSE_ASC_KEY_ID" ISSUER="$BRISTLENOSE_ASC_ISSUER_ID" \
    APPLE_ID="$BRISTLENOSE_ASC_APPLE_ID" PROBE_V="$PROBE_V" exec "$_PY" - <<'PYEOF'
import base64, json, os, sys, time, urllib.request, urllib.parse

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=")

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils
except Exception:
    print("probe: python lacks cryptography — cannot look", file=sys.stderr); sys.exit(3)

try:
    key = serialization.load_pem_private_key(
        open(os.environ["KEYFILE"], "rb").read(), password=None)
    now = int(time.time())
    header = b64u(json.dumps({"alg": "ES256", "kid": os.environ["KEY_ID"],
                              "typ": "JWT"}).encode())
    payload = b64u(json.dumps({"iss": os.environ["ISSUER"], "iat": now,
                               "exp": now + 600,
                               "aud": "appstoreconnect-v1"}).encode())
    signing_input = header + b"." + payload
    der = key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s_ = utils.decode_dss_signature(der)          # JWT wants raw r||s, not DER
    sig = b64u(r.to_bytes(32, "big") + s_.to_bytes(32, "big"))
    jwt = (signing_input + b"." + sig).decode()
except Exception as e:
    print("probe: could not build the token (%s) — cannot look" % e, file=sys.stderr)
    sys.exit(3)

q = urllib.parse.urlencode({
    "filter[app]": os.environ["APPLE_ID"],
    "filter[preReleaseVersion.version]": os.environ["PROBE_V"],
    "limit": "1",
})
req = urllib.request.Request(
    "https://api.appstoreconnect.apple.com/v1/builds?" + q,
    headers={"Authorization": "Bearer " + jwt})


def _look():
    """One read. Returns the build list, or raises."""
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("data", [])


# ONE READ IS NOT EVIDENCE OF ABSENCE. ASC's build index is eventually
# consistent: a delivery confirmed VALID at upload time does not appear here
# for several minutes, and this probe gates a step that CANNOT be un-performed.
# On 31 Aug 2026 a single negative read inside that window told release.sh the
# 0.29.0 TestFlight upload had not happened, seconds after the upload had
# written "state VALID · confirmed present in App Store Connect" with a
# delivery id. It offered to re-run — spending a build number forever — and
# only Apple's own ENTITY_ERROR.ATTRIBUTE.INVALID.DUPLICATE refused the second
# upload. The build number survived because the downstream system declined,
# not because this gate was right.
#
# So: when the answer would be "absent", keep looking for BN_PROBE_WINDOW_S
# before saying so. Default 0 — a bare probe stays instant, which is what
# `verify` wants — and release.sh raises it for exactly the case where lag is
# the likely explanation (its own log already records the step as done).
window = int(os.environ.get("BN_PROBE_WINDOW_S", "0") or 0)
deadline = time.monotonic() + window
attempt = 0
while True:
    attempt += 1
    try:
        data = _look()
    except Exception as e:
        print("probe: ASC unreachable or refused (%s) — cannot look" % e, file=sys.stderr)
        sys.exit(3)
    if data:
        print("probe: ASC holds build %s of %s%s" % (
            data[0].get("attributes", {}).get("version", "?"), os.environ["PROBE_V"],
            "" if attempt == 1 else " (after %d reads)" % attempt))
        sys.exit(0)
    if time.monotonic() >= deadline:
        break
    print("probe: not yet — re-reading in 20s (%ds of %ds window used)" % (
        int(window - max(0, deadline - time.monotonic())), window), file=sys.stderr)
    time.sleep(20)
print("probe: no build of %s on ASC%s" % (
    os.environ["PROBE_V"],
    "" if window == 0 else " after %ds of re-reads" % window))
sys.exit(1)
PYEOF
fi

PKG="${1:-$DEFAULT_PKG}"
[ -f "$PKG" ] || {
    echo "not a file: $PKG" >&2
    echo "build one first: desktop/scripts/build-all.sh" >&2
    exit 2
}

# ---------------------------------------------------------------------------
# Config. upload-dmg.sh's contract: exit 2 and say what's missing.
# ---------------------------------------------------------------------------
CONF="$SCRIPT_DIR/.ship-local.conf"
# shellcheck source=/dev/null
[ -f "$CONF" ] && . "$CONF"

KEY_ID="${BRISTLENOSE_ASC_KEY_ID:-}"
ISSUER="${BRISTLENOSE_ASC_ISSUER_ID:-}"
APPLE_ID="${BRISTLENOSE_ASC_APPLE_ID:-}"

missing=()
[ -n "$KEY_ID" ]  || missing+=("BRISTLENOSE_ASC_KEY_ID")
[ -n "$ISSUER" ]  || missing+=("BRISTLENOSE_ASC_ISSUER_ID")
[ -n "$APPLE_ID" ] || missing+=("BRISTLENOSE_ASC_APPLE_ID")
if [ "${#missing[@]}" -gt 0 ]; then
    cat >&2 <<EOF
Not configured — missing: ${missing[*]}

Put them in $CONF (gitignored) or the environment. None are secrets:
  BRISTLENOSE_ASC_KEY_ID="<key id>"        # from ASC > Users and Access > Integrations
  BRISTLENOSE_ASC_ISSUER_ID="<issuer uuid>"
  BRISTLENOSE_ASC_APPLE_ID="<numeric app id>"   # xcrun altool --list-apps ...

The private key itself lives at ~/.private_keys/AuthKey_<key id>.p8, mode 0600,
and altool finds it by name.
EOF
    exit 2
fi

KEYFILE="$HOME/.private_keys/AuthKey_${KEY_ID}.p8"
[ -f "$KEYFILE" ] || die "no private key at $KEYFILE — altool resolves it from BRISTLENOSE_ASC_KEY_ID"

# ---------------------------------------------------------------------------
# 1. The gate. Not optional, not skippable.
# ---------------------------------------------------------------------------
bold ""
bold "UPLOAD  ·  $(basename "$PKG")  →  TestFlight"
printf '\n'
say "1. Precondition — check-pkg-shippable.sh"
GATE_LOG="$LOG_DIR/upload-gate.log"
# BN_SKIP_ASC_VALIDATE turns the gate's LAST check (altool --validate-app) into
# an announced skip — on this path only. The upload below transfers the same
# bytes to the same endpoint minutes later and Apple revalidates server-side,
# so the pre-upload validate was a duplicate 675 MB / ~8 min transfer per
# release. Every LOCAL check still runs, unskippably; a standalone
# `check-pkg-shippable.sh <pkg>` keeps validate-app and remains the dry run.
if BN_SKIP_ASC_VALIDATE=1 "$GATE" "$PKG" > "$GATE_LOG" 2>&1; then
    ok "gate" "$(grep -c '✓' "$GATE_LOG" 2>/dev/null || echo '?') checks passed"
else
    printf '\n'
    sed 's/^/  /' "$GATE_LOG" >&2
    die "NOT SHIPPABLE — nothing was uploaded. Full log: $GATE_LOG"
fi

# ---------------------------------------------------------------------------
# 2. Say what is about to be sent, before sending it.
#
# Read from the artefact, having just proven it agrees with the working tree.
# A build number is spent the moment ASC sees it — worth one line of "this is
# what leaves the building".
# ---------------------------------------------------------------------------
WORK=$(mktemp -d "${TMPDIR:-/tmp}/bn-upload.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
pkgutil --expand-full "$PKG" "$WORK/x" >/dev/null 2>&1 || die "could not read the pkg"
APP=$(find "$WORK/x" -maxdepth 6 -name '*.app' -type d | head -1)
PLIST="$APP/Contents/Info.plist"
VER=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST" 2>/dev/null || echo '?')
BUILD=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$PLIST" 2>/dev/null || echo '?')
rm -rf "$WORK/x"

printf '\n'
say "2. Sending"
ok "build" "$VER ($BUILD)"
ok "size" "$(du -h "$PKG" | cut -f1)"
ok "app record" "$APPLE_ID"

# ---------------------------------------------------------------------------
# 3. Upload, and wait for a terminal state.
#
# --apple-id is passed so altool never INFERS the app record from the bundle id.
# The Xcode 26 rewrite does infer, and has been reported picking the wrong record
# (fastlane #29698) and failing outright with -19237 (#29820); in Apple Forums
# 812132 Transporter uploaded the same artefact correctly where altool misrouted
# it. One app record here means we're mostly insulated, but naming it is free.
#
# --show-progress only when stdout is a terminal: on a pipe it emits
# \r-overwritten bars that bloat a log 12,000× and hide the real lines.
# ---------------------------------------------------------------------------
printf '\n'
say "3. Transferring — 90 s to first byte is normal; the log below is live"
# Per-attempt, not a fixed name. The Delivery UUID is parsed out of this log and
# the skill calls it "the one probe you cannot reconstruct later" — but it WAS
# reconstructable, right up until the next upload overwrote the file. Every
# upload spends a build number forever, so every upload's log is evidence about
# a spent number and must not be clobbered by the next one.
#
# Ordinal, not a timestamp: `ls` sorts them in upload order, and nothing here is
# allowed to call date(1) for a filename (BSD/GNU divergence, CLAUDE.md).
_n=1
while [ -e "$LOG_DIR/upload-altool.$_n.log" ]; do _n=$((_n+1)); done
UPLOAD_LOG="$LOG_DIR/upload-altool.$_n.log"
ATTEMPT="$_n"
say "   $UPLOAD_LOG"
printf '\n'

ALTOOL_ARGS=(
    --upload-package "$PKG"
    --type macos
    --apple-id "$APPLE_ID"
    --apiKey "$KEY_ID"
    --apiIssuer "$ISSUER"
    --wait
)
[ -t 1 ] && ALTOOL_ARGS+=(--show-progress)

set +e
xcrun altool "${ALTOOL_ARGS[@]}" > "$UPLOAD_LOG" 2>&1
ALTOOL_RC=$?
set -e

# Strip the \r progress spam once, up front — every read below uses this.
CLEAN="$WORK/clean.log"
tr '\r' '\n' < "$UPLOAD_LOG" | grep -vE '^\s*\[[#-]*\]|Uploading to App Store Connect' > "$CLEAN" || true

# The delivery UUID is the only handle on a delivery that goes missing. Print it
# on EVERY path, including failure, before anything else can go wrong.
DELIVERY=$(sed -n 's/.*Delivery UUID: *\([0-9a-f-]*\).*/\1/p' "$CLEAN" | head -1)

# Write the UUID beside the log under its own name, so recovering it later is an
# `ls` rather than a re-parse of a file format Apple owns and can change.
[ -n "$DELIVERY" ] && printf '%s\n' "$DELIVERY" > "$LOG_DIR/delivery-uuid.$ATTEMPT.txt"
[ -n "$DELIVERY" ] && ok "delivery" "$DELIVERY"

if [ "$ALTOOL_RC" -ne 0 ]; then
    printf '\n  \033[31mUPLOAD FAILED\033[0m — Apple'"'"'s own words:\n\n' >&2
    grep -iE 'ERROR|error:' "$CLEAN" | sed 's/^/      /' | head -20 >&2
    cat >&2 <<EOF

  Full log: $UPLOAD_LOG
  ${DELIVERY:+Delivery UUID $DELIVERY — quote it to Apple, and use it to re-query:
    xcrun altool --build-status --delivery-id $DELIVERY --apiKey \$BRISTLENOSE_ASC_KEY_ID --apiIssuer \$BRISTLENOSE_ASC_ISSUER_ID
  }
  Still stuck? Transporter.app takes this same .pkg by drag, and has
  succeeded where altool misrouted (Apple Forums 812132). --use-old-altool
  is the other escape hatch.
EOF
    exit 1
fi

# ---------------------------------------------------------------------------
# 4. The verdict is the STATE, not the exit code.
#
# Allowlist, never denylist: an unrecognised state must fail. A new ASC state
# string appearing one day should stop the release, not sail through it.
# ---------------------------------------------------------------------------
printf '\n'
say "4. Confirming"
STATE=$(sed -n 's/.*PROCESSINGSTATE: *\([A-Z_]*\).*/\1/p' "$CLEAN" | tail -1)
case "$STATE" in
    VALID) ok "processing" "$STATE" ;;
    "")    die "no PROCESSINGSTATE in altool's output — cannot confirm. Log: $UPLOAD_LOG" ;;
    *)     die "unexpected processing state '$STATE' — check App Store Connect. Log: $UPLOAD_LOG" ;;
esac

# Independent second opinion. altool exiting 0 is not evidence the build exists;
# this asks ASC directly. Cheap, no artefact, works with an API key.
# An empty DELIVERY after a zero-exit upload is not a soft condition: the UUID
# sed is a text parse of Apple's output, and losing it silently disables the only
# independent check this script has. Say so before it becomes a shrug below.
[ -n "$DELIVERY" ] || die "upload reported success but no Delivery UUID was parsed — the independent ASC check cannot run. The build may or may not have landed; verify by hand in App Store Connect before re-uploading (this build number is spent either way). Log: $UPLOAD_LOG"

STATUS_LOG="$WORK/status.log"
CONFIRMED=0
if xcrun altool --build-status --delivery-id "$DELIVERY" \
        --apiKey "$KEY_ID" --apiIssuer "$ISSUER" > "$STATUS_LOG" 2>&1; then
    ON_ASC=$(sed -n 's/.*IS-ON-APP-STORE-CONNECT: *\([a-z]*\).*/\1/p' "$STATUS_LOG" | head -1)
    BSTATUS=$(sed -n 's/.*BUILD-STATUS: *\([A-Z_]*\).*/\1/p' "$STATUS_LOG" | head -1)
    [ "$ON_ASC" = "true" ] \
        || die "ASC does not report the build as present (IS-ON-APP-STORE-CONNECT=$ON_ASC). This is the exit-0-but-vanished case — do NOT re-upload at this build number, it is spent. Delivery $DELIVERY"
    ok "app store connect" "present · BUILD-STATUS $BSTATUS"
    CONFIRMED=1
    # EXPIRATION-DATE, hyphenated, from the OUTER block. The nested
    # EXPIRATIONDATE under APP-STORE-ATTRIBUTES is the literal placeholder
    # string "expirationDate" — same word, different key, not a date.
    EXPIRES=$(sed -n 's/.*EXPIRATION-DATE: *\(.*\)/\1/p' "$STATUS_LOG" | head -1)
else
    EXPIRES=$(sed -n 's/.*EXPIRATION-DATE: *\(.*\)/\1/p' "$CLEAN" | head -1)
fi

# The independent check is this script's entire reason to exist — its header says
# a zero exit from altool is not evidence the build landed. Yet the fallback used
# to print a soft warning and then fall through to a banner reading "confirmed
# present in App Store Connect", exit 0. So the ONE failure mode it was built to
# catch was the one it reported as success.
#
# Non-zero here does NOT mean the upload failed. It means the upload is
# unconfirmed, which is a different and more awkward state: the build number is
# spent either way, so the recovery is to look in App Store Connect, never to
# re-upload at the same number.
if [ "$CONFIRMED" -ne 1 ]; then
    printf '\n'
    bold "  ⚠ Delivered, but UNCONFIRMED"
    printf '\n'
    printf '     build  %s (%s)\n' "$VER" "$BUILD"
    printf '  delivery  %s\n' "$DELIVERY"
    printf '     state  %s per altool · ASC NOT independently confirmed\n' "$STATE"
    cat >&2 <<EOF

  altool reported the upload succeeded, but the independent --build-status check
  could not be run or did not answer. That is the documented exit-0-but-vanished
  case, so altool's own word is exactly what must not be trusted here.

  Build $BUILD is spent regardless. Do NOT re-upload at this number.
  Check App Store Connect ▸ TestFlight ▸ Builds, or re-run the check by hand:

    xcrun altool --build-status --delivery-id $DELIVERY \\
      --apiKey "\$BRISTLENOSE_ASC_KEY_ID" --apiIssuer "\$BRISTLENOSE_ASC_ISSUER_ID"

  Status log: $STATUS_LOG
EOF
    exit 1
fi

# ---------------------------------------------------------------------------
printf '\n'
bold "  ✓ On TestFlight"
printf '\n'
printf '     build  %s (%s)\n' "$VER" "$BUILD"
printf '  delivery  %s\n' "${DELIVERY:-unknown}"
printf '     state  %s · confirmed present in App Store Connect\n' "$STATE"
[ -n "${EXPIRES:-}" ] && printf '   expires  %s\n' "$EXPIRES"
cat <<EOF

     Next  It appears in TestFlight within a few minutes. Internal testers get
           it automatically if the group has automatic distribution enabled —
           that is an ASC checkbox this script cannot see.
     Undo  A build cannot be recalled, and build $BUILD is now spent forever.
           Expire it in App Store Connect ▸ TestFlight ▸ Builds.
           A replacement needs a HIGHER build number:
             ./scripts/bump-version.py --build-only

EOF
