#!/usr/bin/env bash
# Cheap invariant tests for the .dmg publish path — the decision logic only, no
# network, no remote host, no fresh 40-minute cut.
# Run: desktop/scripts/test-upload-dmg.sh
#
# Covers the two things that actually decide whether a bad artefact reaches
# strangers, both of which were absent on 4 Aug 2026:
#
#   1. swap_decision — may the uploaded bytes replace the live download? The
#      empty-vs-empty case is the point: `ssh host 'shasum …'` in a command
#      substitution discards ssh's exit status, so a failure yields "", and a
#      bare `[ "$a" = "$b" ]` compares two empty strings EQUAL and swaps.
#   2. check-dmg-shippable — is the artefact notarised at all? Proven against
#      the real notarised Bristlenose-0.21.0.dmg already on disk, and against
#      real violations, per the bar check-appearance-seam.sh set: every
#      assertion is shown to FAIL on its own violation, because a gate that
#      can't fail is worse than no gate.
#
# Deliberately NOT covered (see docs/design-dmg-build.md): the notarisation
# round-trip, the transfer itself, and the Gatekeeper verdict on a stranger's
# Mac. Those are environmental — mocking Apple's notary API would cost more to
# maintain than it catches, and the real cut is their acceptance test.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT/desktop/build"
SCRATCH="$BUILD_DIR/.test-upload-dmg"

pass=0; fail=0
ok()  { echo "  ok   — $1"; pass=$((pass+1)); }
bad() { echo "  FAIL — $1"; fail=$((fail+1)); }

cleanup() { rm -rf "$SCRATCH"; }
trap cleanup EXIT

echo "== test-upload-dmg =="

# ---------------------------------------------------------------------------
# swap_decision
# ---------------------------------------------------------------------------
UPLOAD_DMG_SOURCE_ONLY=1 . "$SCRIPT_DIR/upload-dmg.sh"

A="$(printf 'a%.0s' {1..64})"
B="$(printf 'b%.0s' {1..64})"

[ "$(swap_decision "$A" "$A")" = "swap" ] \
    && ok "matching 64-hex hashes → swap" \
    || bad "matching hashes did not authorise the swap"

# THE case. Both sides failed to measure; a naive equality test says "equal".
case "$(swap_decision "" "")" in
    abort*) ok "empty == empty → abort (does not read as a match)" ;;
    *)      bad "empty vs empty authorised a swap — the exact 4 Aug failure shape" ;;
esac

case "$(swap_decision "$A" "")" in
    abort*remote*) ok "remote hash unreadable → abort naming the remote side" ;;
    *)             bad "unreadable remote hash did not abort" ;;
esac

case "$(swap_decision "" "$A")" in
    abort*local*) ok "local hash unreadable → abort naming the local side" ;;
    *)            bad "unreadable local hash did not abort" ;;
esac

case "$(swap_decision "$A" "$B")" in
    abort*differ*) ok "hashes differ → abort (corrupted transfer)" ;;
    *)             bad "mismatched hashes did not abort" ;;
esac

# A truncated hash is not a hash. Guards against a `cut` that silently returns
# a prefix, or a remote shasum whose output format shifts.
case "$(swap_decision "$A" "${A:0:40}")" in
    abort*) ok "short remote hash → abort" ;;
    *)      bad "a 40-char remote value was accepted as a sha256" ;;
esac

# ---------------------------------------------------------------------------
# retention_plan — nothing else ever cleans dmg/ (deploy.sh protects it)
# ---------------------------------------------------------------------------
plan="$(retention_plan 3 v5 v4 v3 v2 v1 | tr '\n' ' ')"
[ "$plan" = "v2 v1 " ] \
    && ok "keep 3 of 5 → reaps the 2 oldest" \
    || bad "retention kept the wrong set (got '$plan')"

[ -z "$(retention_plan 3 v2 v1)" ] \
    && ok "fewer artefacts than the keep count → reaps nothing" \
    || bad "retention reaped below the keep count"

[ "$(retention_plan 0 v1 | tr -d '\n')" = "v1" ] \
    && ok "keep 0 → reaps everything" \
    || bad "keep 0 did not reap"

# ---------------------------------------------------------------------------
# upload-dmg refuses to run unconfigured (the remote is never hardcoded)
# ---------------------------------------------------------------------------
# Neutralise BOTH sources — the env var AND the local conf file. Without the
# second, this assertion passes on a machine that has no conf and silently
# stops testing anything on a machine that does.
set +e
out="$(cd "$ROOT" && env -u BRISTLENOSE_DMG_REMOTE BRISTLENOSE_SHIP_CONF=/dev/null \
        bash "$SCRIPT_DIR/upload-dmg.sh" --dry-run 2>&1)"
rc=$?
set -e
if [ "$rc" -eq 2 ] && echo "$out" | grep -q 'BRISTLENOSE_DMG_REMOTE'; then
    ok "unconfigured remote → exit 2, names the env var"
else
    bad "unconfigured remote did not exit 2 with guidance (rc=$rc)"
fi

# ---------------------------------------------------------------------------
# check-dmg-shippable — against real artefacts
# ---------------------------------------------------------------------------
GATE="$SCRIPT_DIR/check-dmg-shippable.sh"
FIXTURE="$BUILD_DIR/Bristlenose-0.21.0.dmg"
STALE="$BUILD_DIR/Bristlenose.dmg"

gate() { BN_REPORT=0 "$GATE" "$1" >/dev/null 2>&1; }

if [ -f "$FIXTURE" ]; then
    gate "$FIXTURE" \
        && ok "real notarised artefact (0.21.0) → shippable" \
        || bad "the gate rejected a known-good notarised artefact"
else
    echo "  skip — no 0.21.0 fixture on disk to prove the happy path"
fi

mkdir -p "$SCRATCH"

# Unversioned name — refused before anything else is even examined, because
# resolving by the published name is how a stale artefact gets published.
if [ -f "$STALE" ]; then
    gate "$STALE" && bad "an unversioned artefact was accepted" \
                  || ok "unversioned filename → refused"

    # Same bytes under a versioned name: now the notarisation assertions run,
    # and this image (19 Feb, unstapled, version 0.1) fails them.
    if ln "$STALE" "$SCRATCH/Bristlenose-9.9.9.dmg" 2>/dev/null; then
        gate "$SCRATCH/Bristlenose-9.9.9.dmg" \
            && bad "an unstapled, unnotarised image was accepted" \
            || ok "versioned but unstapled/unnotarised → refused"
    fi
else
    echo "  skip — no unversioned artefact on disk to prove the refusal"
fi

# A perfectly good image whose manifest describes DIFFERENT bytes. This is the
# resume-skew class: every signature and ticket assertion passes, and only the
# manifest cross-check notices the pairing is wrong.
if [ -f "$FIXTURE" ] && [ -f "${FIXTURE%.dmg}.manifest.txt" ]; then
    ln -f "$FIXTURE" "$SCRATCH/Bristlenose-0.21.0.dmg" 2>/dev/null || cp "$FIXTURE" "$SCRATCH/"
    sed 's|^  [0-9a-f]\{64\}\(  .*/MacOS/Bristlenose\)$|  deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef\1|' \
        "${FIXTURE%.dmg}.manifest.txt" > "$SCRATCH/Bristlenose-0.21.0.manifest.txt"
    gate "$SCRATCH/Bristlenose-0.21.0.dmg" \
        && bad "a manifest describing different bytes was accepted" \
        || ok "manifest ↔ image mismatch → refused"
fi

# ── checksum sidecar ─────────────────────────────────────────────────────────
# The published digest is the only integrity claim a user can check BEFORE
# running the app; Gatekeeper's is invisible until launch. The format must be
# exactly what `shasum -a 256 -c` consumes, or the instruction we imply is wrong.
SHA64="$(printf 'x' | shasum -a 256 | cut -d' ' -f1)"
out="$(checksum_sidecar "$SHA64" "Bristlenose-0.28.0.dmg")"
[ "$out" = "$SHA64  Bristlenose-0.28.0.dmg" ] \
    && ok "sidecar is shasum -c format (two spaces)" \
    || bad "sidecar format wrong: $(printf '%q' "$out")"

# Round-trip through the real tool — the only proof that matters. Note $( )
# strips trailing newlines, so the newline can only be checked via a file.
_td="$(mktemp -d)"
printf 'x' > "$_td/Bristlenose-0.28.0.dmg"
checksum_sidecar "$SHA64" "Bristlenose-0.28.0.dmg" > "$_td/s.sha256"
[ "$(wc -l < "$_td/s.sha256" | tr -d ' ')" = "1" ] \
    && ok "sidecar is one newline-terminated line" \
    || bad "sidecar not newline-terminated — shasum -c needs it"
( cd "$_td" && shasum -a 256 -c s.sha256 >/dev/null 2>&1 ) \
    && ok "shasum -a 256 -c accepts what we publish" \
    || bad "shasum -c REJECTS our sidecar — the verify instruction would not work"
rm -rf "$_td"

echo
echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ]
