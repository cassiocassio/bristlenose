#!/usr/bin/env bash
# verify-channels.sh — is version X.Y.Z actually live on every channel?
#
# Phase 6 of the /bn-release skill, made executable. The skill's table told the
# reader which command answers each channel; this runs them and prints one table.
#
# THE RULE THIS SCRIPT EXISTS TO ENFORCE
#
#   A successful probe wins. An unsuccessful probe wins over nothing.
#
# A failed probe must never read as a negative one. `curl` writes 000 on a
# connection failure, and a naive [ "$code" = 200 ] reads that as "not
# published" — which, under a driver that treats the probe as authoritative,
# manufactures a false conclusion from a network fault. Every probe here is
# tri-state: ok / bad / unreachable. The pattern is lifted from
# check-release-ready.sh:204-215, not re-derived.
#
# Corollary from release-log 0.27.0 #8: "I can't probe this" is itself a claim
# that must be checked. There is no row here that says "look at the workflow
# conclusion instead" — every channel has an HTTP endpoint behind whatever CLI
# normally reads it.
#
# Usage:
#   verify-channels.sh 0.28.0            # all seven channels
#   verify-channels.sh 0.28.0 --abandoned 0.27.9
#                                        # also assert this version is GONE from
#                                        # any surface rendered from CHANGELOG.md
#
# Exit codes:
#   0  every channel is on this version
#   1  at least one channel is not (including unreachable — unverified is not ok)
#   2  usage error
#
# Sourcing:
#   VERIFY_CHANNELS_LIB=1 source verify-channels.sh
#   …exposes the pure verdict_* functions without running any probe. This is how
#   tests/test-verify-channels.sh drives every worst case with synthetic input.

set -uo pipefail

# ---------------------------------------------------------------------------
# Pure decision functions. No I/O. These are the whole risk surface, and they
# are the only thing the test suite needs to exercise.
# ---------------------------------------------------------------------------

# verdict_http <code> — the shape shared by PyPI, the .dmg permalink, the site.
#   200/30x → ok · 404 → bad · anything else (incl. 000) → unreachable
verdict_http() {
    case "${1:-}" in
        200|201|204)  echo ok ;;
        301|302|307|308) echo ok ;;
        404|410)      echo bad ;;
        ""|000)       echo unreachable ;;
        *)            echo unreachable ;;
    esac
}

# _token_present <haystack> <needle> — substring match on VERSION BOUNDARIES.
#
#   A plain substring test is wrong here and fails in the flattering direction:
#   "0.28.1" is a substring of "0.28.10", so a page naming only 0.28.10 reports
#   0.28.1 as PRESENT — a channel reads verified when it is not. Likewise "0.2"
#   matches "0.28.0", and "0.28.0" matches "10.28.0". Found by the synthetic
#   suite, not by reasoning; three of its cases failed on the first run.
#
#   Same family as CLAUDE.md's export-CSS note — `.badge-accept` matching
#   `.badge-accept-flash` — and the fix is the same: match whole tokens. Here the
#   token characters are [0-9.], so the needle must not be flanked by one.
_token_present() {
    local body="${1-}" needle="${2-}" esc
    esc=$(printf '%s' "$needle" | sed 's/[][\.^$*+?(){}|\/]/\\&/g')
    printf '%s' "$body" | grep -qE "(^|[^0-9.])${esc}([^0-9.]|\$)"
}

# verdict_contains <haystack> <needle> — did a fetched body name the version?
#   Empty haystack is UNREACHABLE, never "absent". This is the distinction the
#   whole script turns on: nothing fetched is not the same as nothing found.
verdict_contains() {
    local body="${1-}" needle="${2-}"
    [ -z "$body" ]   && { echo unreachable; return; }
    [ -z "$needle" ] && { echo unreachable; return; }
    if _token_present "$body" "$needle"; then echo ok; else echo bad; fi
}

# verdict_absent <haystack> <needle> — the inverse, for abandoned versions.
#   0.27.0's real website failure was the live changelog naming 0.26.0 — a
#   version that never published — while the download served 0.27.0. A
#   presence-of-target probe passes the moment the target appears and would not
#   have caught it.
verdict_absent() {
    local body="${1-}" needle="${2-}"
    [ -z "$body" ]   && { echo unreachable; return; }
    [ -z "$needle" ] && { echo ok; return; }
    if _token_present "$body" "$needle"; then echo bad; else echo ok; fi
}

# verdict_json_field <json> <expected> — a value pulled from an API response.
#   Distinguishes "the API said something else" from "the API said nothing".
verdict_json_field() {
    local got="${1-}" want="${2-}"
    [ -z "$got" ] && { echo unreachable; return; }
    case "$got" in
        null|"null") echo unreachable ;;
        "$want")     echo ok ;;
        *)           echo bad ;;
    esac
}

# verdict_gate <query_output> — the publish hold.
#   An EMPTY result must never read as "no pending deployment": `gh api` with
#   expired auth, a rate limit or no network returns empty and exits non-zero,
#   and folding that to "gate cleared" is a network fault reading as a human
#   approval. Callers pass QUERY_FAILED explicitly on non-zero exit.
verdict_gate() {
    case "${1-}" in
        QUERY_FAILED|"") echo unreachable ;;
        NONE)            echo cleared ;;
        *)               echo held ;;
    esac
}

# Roll a set of per-channel verdicts into one exit code.
#   unreachable counts as NOT ok — unverified is not verified.
rollup() {
    local v
    for v in "$@"; do [ "$v" = ok ] || { echo 1; return; }; done
    echo 0
}

[ "${VERIFY_CHANNELS_LIB:-0}" = "1" ] && return 0 2>/dev/null

# ---------------------------------------------------------------------------
# Everything below is I/O and presentation.
# ---------------------------------------------------------------------------

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"

VERSION=""; ABANDONED=""
while [ $# -gt 0 ]; do
    case "$1" in
        --abandoned) ABANDONED="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit 0 ;;
        [0-9]*) VERSION="$1"; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$VERSION" ] || { echo "usage: verify-channels.sh <X.Y.Z> [--abandoned <X.Y.Z>]" >&2; exit 2; }
case "$VERSION" in
    [0-9]*.[0-9]*.[0-9]*) : ;;
    *) echo "refusing: unexpected version shape '$VERSION'" >&2; exit 2 ;;
esac

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
[ -t 1 ] || { G=""; Y=""; R=""; D=""; N=""; }

VERDICTS=()
row() { # row <name> <verdict> <evidence>
    local glyph
    case "$2" in
        ok)          glyph="${G}✓${N}" ;;
        bad)         glyph="${R}✗${N}" ;;
        unreachable) glyph="${Y}⚠${N}" ;;
        *)           glyph="${Y}⚠${N}" ;;
    esac
    printf '  %b %-18s %s%s%s\n' "$glyph" "$1" "$D" "$3" "$N"
    VERDICTS+=("$2")
}

fetch() { curl -s --max-time 20 "$1" 2>/dev/null || true; }
code_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1" 2>/dev/null || echo 000; }

printf '\n\033[1mChannels · %s\033[0m\n\n' "$VERSION"

# 1 · PyPI — the version-specific endpoint, which is authoritative. The index
# endpoint is CDN-cached and reads stale (release.md's own warning).
c=$(code_of "https://pypi.org/pypi/bristlenose/$VERSION/json")
row "PyPI" "$(verdict_http "$c")" "HTTP $c"

# 2 · GitHub Release
if command -v gh >/dev/null 2>&1; then
    gh_out=$(gh release view "v$VERSION" --json tagName --jq .tagName 2>/dev/null || true)
    row "GitHub Release" "$(verdict_json_field "$gh_out" "v$VERSION")" "${gh_out:-query failed}"
else
    row "GitHub Release" "unreachable" "gh not installed"
fi

# 3 · Homebrew — the tap formula must name this sdist.
tap=$(fetch "https://raw.githubusercontent.com/cassiocassio/homebrew-bristlenose/main/Formula/bristlenose.rb")
row "Homebrew" "$(verdict_contains "$tap" "bristlenose-$VERSION.tar.gz")" \
    "$([ -n "$tap" ] && echo "formula fetched" || echo "formula unreachable")"

# 4 · TestFlight — needs ASC credentials; absence is unreachable, not absent.
row "TestFlight" "unreachable" "needs ASC key — probe with upload-testflight.sh --build-status"

# 5 · .dmg permalink — a 302 to the versioned name.
dmg=$(curl -sI --max-time 20 "https://bristlenose.app/dmg/Bristlenose.dmg" 2>/dev/null || true)
if [ -z "$dmg" ]; then
    row ".dmg" "unreachable" "permalink unreachable"
else
    row ".dmg" "$(verdict_contains "$dmg" "$VERSION")" \
        "$(printf '%s' "$dmg" | tr -d '\r' | grep -i '^location:' | head -1 | cut -c1-58)"
fi

# 5b · The .dmg's published checksum. Gatekeeper is the real control here — an
# attacker with the web host cannot serve a .dmg that launches without a valid
# Developer ID signature and staple — but that control is invisible and says
# nothing a user can check BEFORE running the thing.
sha=$(fetch "https://bristlenose.app/dmg/Bristlenose.dmg.sha256")
if [ -z "$sha" ]; then
    row ".dmg sha256" "unreachable" "no published digest"
else
    _d=$(printf '%s' "$sha" | awk '{print $1}')
    _f=$(printf '%s' "$sha" | awk '{print $2}')
    case "$_d" in
        [0-9a-f]*) [ ${#_d} -eq 64 ] \
            && row ".dmg sha256" "$(verdict_contains "$_f" "$VERSION")" "${_d:0:16}… $_f" \
            || row ".dmg sha256" "bad" "digest is not 64 hex chars" ;;
        *) row ".dmg sha256" "bad" "not a sha256 line" ;;
    esac
fi

# 6 · Snap — the store API, public and unauthenticated. The workflow conclusion
# says the UPLOAD succeeded; channel-map says what a user actually gets. They
# diverge, and Tier 2 can only use the second (release-log 0.27.0 #8).
snap=$(curl -s --max-time 20 -H 'Snap-Device-Series: 16' \
    "https://api.snapcraft.io/v2/snaps/info/bristlenose" 2>/dev/null || true)
if [ -z "$snap" ]; then
    row "Snap (edge)" "unreachable" "store API unreachable"
else
    edge=$(printf '%s' "$snap" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(0)
for m in d.get('channel-map',[]):
    if m.get('channel',{}).get('name')=='edge':
        print(m.get('version','')); break
" 2>/dev/null || true)
    row "Snap (edge)" "$(verdict_json_field "$edge" "$VERSION")" "channel-map: ${edge:-unparseable}"
fi

# 7 · Website — the STRONGEST probe available: that page renders from
# CHANGELOG.md at build time, so a hit proves the deploy ran AFTER the entry
# existed. Manual deploy and unverifiable are different properties.
site=$(fetch "https://bristlenose.app/docs/changelog.html")
row "Website" "$(verdict_contains "$site" "$VERSION")" \
    "$([ -n "$site" ] && echo "changelog fetched" || echo "unreachable")"

if [ -n "$ABANDONED" ]; then
    row "  ↳ $ABANDONED gone" "$(verdict_absent "$site" "$ABANDONED")" \
        "a version abandoned pre-publication leaves a footprint on any surface already rendered"
fi

echo
printf '  %sexpiry   .dmg 30d from the BUILD · TestFlight 90d from the UPLOAD%s\n' "$D" "$N"
echo

RC=$(rollup "${VERDICTS[@]}")
total=${#VERDICTS[@]}
oks=0; for v in "${VERDICTS[@]}"; do [ "$v" = ok ] && oks=$((oks+1)); done
if [ "$RC" = "0" ]; then
    printf '  %b %s of %s channels on %s\n\n' "${G}✓${N}" "$oks" "$total" "$VERSION"
else
    printf '  %b %s of %s channels on %s · %s outstanding\n\n' \
        "${R}✗${N}" "$oks" "$total" "$VERSION" "$((total-oks))"
fi
exit "$RC"
