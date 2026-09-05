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

# The sink (docs/design-release-board.md §1.1): every row, plus a start and a
# done line so a verify interrupted after five rows can never be rolled up as
# complete by a reader. No-op unless release.sh exported BN_EVENT_SINK.
_VC_SINK="$(cd "$(dirname "$0")/.." && pwd)/desktop/scripts/sink.sh"
if [ -f "$_VC_SINK" ]; then . "$_VC_SINK"; else sink_line() { :; }; fi

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
    # Trailing rule is NOT simply [^0-9.]. "Bristlenose-0.28.0.dmg" puts a dot
    # straight after the version, so that form rejected every correct .dmg — a
    # green release reporting a red channel, which is worse than the substring
    # bug it was fixing. What must be excluded is a digit, or a dot FOLLOWED by a
    # digit (0.28.1 inside 0.28.10). A dot followed by anything else is fine.
    # Herestring, NOT a pipe. Under `set -o pipefail`, `grep -q` exits at the
    # first match, the producer takes SIGPIPE and exits 141, and 141 becomes the
    # pipeline's status — so a match near the TOP of a large body reads as no
    # match. A changelog's newest entry is always at the top, which made the
    # Website row red on every correct release and made verdict_absent report a
    # present abandoned version as gone. check-release-ready.sh:419 already uses
    # the herestring form.
    grep -qE -- "(^|[^0-9.])${esc}(\$|[^0-9.]|[.][^0-9])" <<<"$body"
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
    for v in "$@"; do
        case "$v" in
            ok|skipped) : ;;   # skipped = no probe exists here, and we said so
            *)          echo 1; return ;;
        esac
    done
    echo 0
}

# verdict_testflight_probe <probe-exit> — pure mapper for the --probe contract
# (0 delivered · 1 absent · 3 could-not-look). Absent is BAD: a released
# version with no TestFlight build is a real gap. Could-not-look stays the
# informational skip — most machines legitimately lack the ASC key, and an
# UNVERIFIED row must not read as a FAILED one. Any unexpected exit maps to
# the skip for the same reason 1 and 3 must never conflate in probe_done.
verdict_testflight_probe() {
    case "${1:-}" in
        0) echo ok ;;
        1) echo bad ;;
        *) echo skipped ;;
    esac
}

[ "${VERIFY_CHANNELS_LIB:-0}" = "1" ] && return 0 2>/dev/null

# ---------------------------------------------------------------------------
# Everything below is I/O and presentation.
# ---------------------------------------------------------------------------

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"

# Project identity and the channel list. Everything about WHICH project this is
# lives there; everything about HOW a release is verified lives here.
# shellcheck source=scripts/project.conf
. "$ROOT/scripts/project.conf"

VERSION=""; ABANDONED=""
while [ $# -gt 0 ]; do
    case "$1" in
        --abandoned) ABANDONED="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit 0 ;;
        [0-9]*) VERSION="$1"; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
# No version = the tree's version. "What is the state of the latest release?"
# is the question this script answers, and the tree names the latest — after a
# release they agree, and mid-release the tree carries the version in flight,
# which is exactly the one worth probing. Narrated in the header below.
VERSION_SOURCE=""
if [ -z "$VERSION" ]; then
    VERSION="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' bristlenose/__init__.py 2>/dev/null)"
    [ -n "$VERSION" ] || { echo "usage: verify-channels.sh <X.Y.Z> [--abandoned <X.Y.Z>] — and no tree version to default to" >&2; exit 2; }
    VERSION_SOURCE=" · the tree's version"
fi
# NEGATED CLASS FIRST. `[0-9]*.[0-9]*.[0-9]*` reads as "a digit, ANYTHING, a
# dot, a digit, ANYTHING, a dot, a digit, anything" — it accepts
# 0';id;'.0.0 and 1x.2y.3"; system("x"). Measured. The strict form is
# already in scripts/release.sh as verdict_version, with a test asserting
# 0.28.0;rm -rf / is malformed.
case "$VERSION" in
    ""|*[!0-9.]*) echo "refusing: unexpected version shape '$VERSION'" >&2; exit 2 ;;
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
        skipped)     glyph="${D}—${N}" ;;
        bad)         glyph="${R}✗${N}" ;;
        unreachable) glyph="${Y}⚠${N}" ;;
        *)           glyph="${Y}⚠${N}" ;;
    esac
    printf '  %b %-18s %s%s%s\n' "$glyph" "$1" "$D" "$3" "$N"
    VERDICTS+=("$2")
    sink_line row src=verify label="$1" result="$2" evidence="$3"
}

# -f: fail on an HTTP error rather than returning the error PAGE as content.
# Without it a 404 HTML body reads as a real response — the .dmg digest row
# reported `bad: not a sha256 line` for a file that simply does not exist yet,
# which is the "unreachable is not absent" rule this file opens with, broken by
# its own fetch helper.
# -L is load-bearing: the .dmg permalink 302s to the versioned file, and
# without it fetch returned the redirect's 223-byte HTML page as the BODY —
# on 28 Aug 2026 the sha256 probe measured that page and reported "digest
# is not 64 characters" against a good, byte-identical artefact. Every
# fetch call site is a content read; all of them want the final body.
fetch() { curl -sfL --max-time 20 "$1" 2>/dev/null || true; }
code_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1" 2>/dev/null || echo 000; }

# ---------------------------------------------------------------------------
# One probe_<channel> per channel, each echoing "<verdict>|<evidence>".
#
# The main loop iterates $CHANNELS from project.conf rather than hardcoding
# rows, so removing a channel removes its probe, its verdict and its line in the
# rollup — and a channel listed with NO probe is a hard error rather than a
# silently unchecked channel, which is the defect this whole file exists for.
# ---------------------------------------------------------------------------

probe_pypi() {
    local url code
    url=$(printf "$PYPI_JSON" "$VERSION")
    code=$(code_of "$url")
    printf '%s|HTTP %s' "$(verdict_http "$code")" "$code"
}

probe_github() {
    command -v gh >/dev/null 2>&1 || { printf 'unreachable|gh not installed'; return; }
    local out
    out=$(gh release view "v$VERSION" --json tagName --jq .tagName 2>/dev/null || true)
    printf '%s|%s' "$(verdict_json_field "$out" "v$VERSION")" "${out:-query failed}"
}

probe_homebrew() {
    local tap want
    tap=$(fetch "$TAP_FORMULA_RAW")
    want=$(printf "$SDIST_NAME" "$VERSION")
    printf '%s|%s' "$(verdict_contains "$tap" "$want")" \
        "$([ -n "$tap" ] && echo "formula fetched" || echo "formula unreachable")"
}

probe_testflight() {
    local _rc
    if [ -x "$ROOT/desktop/scripts/upload-testflight.sh" ]; then
        "$ROOT/desktop/scripts/upload-testflight.sh" --probe "$VERSION" >/dev/null 2>&1
        _rc=$?
    else
        _rc=3
    fi
    case "$(verdict_testflight_probe "$_rc")" in
        ok)  printf 'ok|ASC holds a build of %s' "$VERSION" ;;
        bad) printf 'bad|no build of %s on App Store Connect' "$VERSION" ;;
        *)   printf 'skipped|could not look (ASC key, config, or network) — upload-testflight.sh --probe %s' "$VERSION" ;;
    esac
}

probe_dmg() {
    local head want
    head=$(curl -sI --max-time 20 "$DMG_PERMALINK" 2>/dev/null || true)
    [ -z "$head" ] && { printf 'unreachable|permalink unreachable'; return; }
    want=$(printf "$DMG_VERSIONED" "$VERSION")
    printf '%s|%s' "$(verdict_contains "$head" "$want")" \
        "$(printf '%s' "$head" | tr -d '\r' | grep -i '^location:' | head -1 | cut -c1-52)"
}

probe_snap() {
    local body edge
    body=$(curl -s --max-time 20 -H 'Snap-Device-Series: 16' "$SNAP_INFO" 2>/dev/null || true)
    [ -z "$body" ] && { printf 'unreachable|store API unreachable'; return; }
    edge=$(printf '%s' "$body" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for m in d.get('channel-map',[]):
    if m.get('channel',{}).get('name')=='edge':
        print(m.get('version','')); break
" 2>/dev/null || true)
    printf '%s|channel-map: %s' "$(verdict_json_field "$edge" "$VERSION")" "${edge:-unparseable}"
}

probe_copr() {
    # Copr's own API, the one copr-cli uses. Unauthenticated for public
    # projects, so this needs no token — which matters, because a probe that
    # needs a credential is a probe that quietly stops running.
    #
    # 404 means the project does not exist yet, which is the honest state
    # before the first build and is NOT the same as "built the wrong version".
    # Reported as unreachable rather than bad, so a not-yet-created channel
    # cannot read as a broken one.
    local body ver
    body=$(fetch "$COPR_BUILDS")
    [ -z "$body" ] && { printf 'unreachable|no such project yet, or API unreachable'; return; }
    # Copr reports version-release ("0.27.0-1"); compare the version half.
    # Newest build first — a later failed build must not be masked by an
    # earlier success, so this reads the most recent SUCCEEDED build and the
    # newest build overall, and disagrees loudly when they differ.
    ver=$(printf '%s' "$body" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
items=d.get('items') or []
best=None
for b in items:
    if b.get('state')=='succeeded':
        v=(b.get('source_package') or {}).get('version') or ''
        if v: best=v.split('-')[0]; break
print(best or '')
" 2>/dev/null || true)
    printf '%s|latest succeeded build: %s' "$(verdict_json_field "$ver" "$VERSION")" "${ver:-none}"
}

probe_website() {
    # The STRONGEST probe available: that page renders from CHANGELOG.md at build
    # time, so a hit proves the deploy ran AFTER the entry existed.
    #
    # Reads $SITE_BODY, fetched by the PARENT below. It used to fetch it here,
    # which looked right and could not work: the loop calls every probe in a
    # command substitution, so the assignment died with the subshell and the
    # --abandoned row that rides this body always read "changelog not fetched"
    # — one line under a website row saying "changelog fetched". Fails closed,
    # so it never false-passed; it simply never worked.
    printf '%s|%s' "$(verdict_contains "$SITE_BODY" "$VERSION")" \
        "$([ -n "$SITE_BODY" ] && echo "changelog fetched" || echo "unreachable")"
}

# Fetched once, in the parent, before the loop — the only scope both the website
# probe and the --abandoned row below can see. Fetched when EITHER needs it, so
# --abandoned works against a project whose CHANNELS omit the website.
SITE_BODY=""
_need_site=0
case " $CHANNELS " in *" website "*) _need_site=1 ;; esac
[ -n "$ABANDONED" ] && _need_site=1
[ "$_need_site" = 1 ] && SITE_BODY=$(fetch "$CHANGELOG_URL")

printf '\n\033[1mChannels · %s\033[0m\033[2m%s\033[0m\n\n' "$VERSION" "$VERSION_SOURCE"

sink_line verify status=start version="$VERSION"
for _ch in $CHANNELS; do
    # CHANNELS_UNPROBEABLE is the allow-list for "no probe exists here", and it
    # is consulted in BOTH directions. It used to be consulted in neither: the
    # constant sat in project.conf with no reader while probe_testflight
    # hardcoded the same fact, so the declaration and the behaviour could
    # disagree indefinitely and nothing would say so.
    _declared=0
    case " $CHANNELS_UNPROBEABLE " in *" $_ch "*) _declared=1 ;; esac

    if ! command -v "probe_$_ch" >/dev/null 2>&1 && ! declare -F "probe_$_ch" >/dev/null 2>&1; then
        if [ "$_declared" = 1 ]; then
            row "$_ch" "skipped" "declared unprobeable in project.conf"
        else
            printf '  %b✗%b %-18s %sno probe_%s function — channel listed but unchecked%s\n' \
                "$R" "$N" "$_ch" "$D" "$_ch" "$N"
            VERDICTS+=("bad")
        fi
        continue
    fi

    _res="$(probe_"$_ch")"
    _verdict="${_res%%|*}"
    # The other direction, and the one that actually hides a channel: a probe
    # that answers `skipped` while nothing declares it unprobeable is a channel
    # excusing itself. `skipped` is the one verdict rollup() accepts as a pass,
    # so this is the shape that reads verified while checking nothing.
    if [ "$_verdict" = skipped ] && [ "$_declared" = 0 ]; then
        row "$_ch" "bad" "reported skipped but is not in CHANNELS_UNPROBEABLE"
        continue
    fi
    row "$_ch" "$_verdict" "${_res#*|}"
done

# The abandoned-version check rides the website body the loop already fetched.
if [ -n "$ABANDONED" ]; then
    if [ -z "$SITE_BODY" ]; then
        row "  ↳ $ABANDONED gone" "unreachable" "changelog not fetched"
    else
        row "  ↳ $ABANDONED gone" "$(verdict_absent "$SITE_BODY" "$ABANDONED")" \
            "a version abandoned pre-publication leaves a footprint on any rendered surface"
    fi
fi

# The .dmg digest, when that channel is in play.
case " $CHANNELS " in *" dmg "*)
    sha=$(fetch "$DMG_SHA_URL")
    if [ -z "$sha" ]; then
        row ".dmg sha256" "unreachable" "no published digest"
    else
        _d=$(printf '%s' "$sha" | awk '{print $1}')
        _f=$(printf '%s' "$sha" | awk '{print $2}')
        if [ "${#_d}" -ne 64 ]; then
            row ".dmg sha256" "bad" "digest is not 64 characters"
        else
            case "$_d" in
                *[!0-9a-f]*) row ".dmg sha256" "bad" "digest is not hex" ;;
                *) row ".dmg sha256" "$(verdict_contains "$_f" "$VERSION")" \
                       "filename names $VERSION · ${_d:0:12}…" ;;
            esac
        fi
    fi ;;
esac

printf '  %sexpiry   .dmg 30d from the BUILD · TestFlight 90d from the UPLOAD%s\n' "$D" "$N"
echo

# Floor at the CALL SITE, not inside rollup — rollup is a pure function driven
# by synthetic input, and a floor there makes it untestable at small scale.
# A rollup over nothing is not a pass: that is the class this work exists for.
if [ "${#VERDICTS[@]}" -lt 6 ]; then
    printf '\n  %b✗%b only %s channel(s) probed — refusing to report a verdict\n\n' \
        "$R" "$N" "${#VERDICTS[@]}"
    exit 2
fi
RC=$(rollup "${VERDICTS[@]}")
total=${#VERDICTS[@]}
oks=0; skips=0
for v in "${VERDICTS[@]}"; do
    [ "$v" = ok ] && oks=$((oks+1))
    [ "$v" = skipped ] && skips=$((skips+1))
done
total=$(( total - skips ))
if [ "$RC" = "0" ]; then
    printf '  %b %s of %s channels on %s\n\n' "${G}✓${N}" "$oks" "$total" "$VERSION"
else
    printf '  %b %s of %s channels on %s · %s outstanding\n\n' \
        "${R}✗${N}" "$oks" "$total" "$VERSION" "$((total-oks))"
fi
sink_line verify status=done version="$VERSION" rollup="$RC" channels="$total" ok="$oks"
exit "$RC"
