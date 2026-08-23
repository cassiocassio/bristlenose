#!/usr/bin/env bash
# release.sh — the conductor's page, executable. READ-ONLY.
#
# WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT
#
# docs/design-release-machine.md splits the release into Tier A (gates and
# probes, all shipped) and Tier B (an event log and a driver that executes).
# This is Tier B's READ-ONLY half only: plan, verify, status, abandon.
#
# There is no `run`, and that is a decision rather than an omission. Executing
# the release means crossing two irreversibility lines — a spent TestFlight
# build number and a burned PyPI version — and the design gates that work on
# evidence: build it when two release-log entries show a stranded step or an
# unusable timing estimate. Neither has happened. `run` therefore refuses and
# points at /bn-release, which still owns the order.
#
# What this DOES own is the step table. Until now it lived as prose in
# SKILL.md Phase 5, which meant a model retyped it every release — and the
# estimates in it were guesses nobody had measured. Both now live here, once,
# with the numbers from docs/release-log.md's 0.27.0 entry.
#
# Usage:
#   release.sh plan <X.Y.Z> [--tier 1|2] [--build-only]
#   release.sh verify <X.Y.Z> [--abandoned <X.Y.Z>]
#   release.sh status
#   release.sh abandon <X.Y.Z>
#
# Exit codes:
#   0   ready / verified / informational
#   1   not ready, or a channel is not on this version
#   2   usage error
#   75  EX_TEMPFAIL — a run is held awaiting the publish approval. Not an error:
#       a release waiting on a person is behaving correctly. Distinguishable
#       from 0 so `release.sh … && deploy-website` cannot fire on a release that
#       has published nothing.
#
# Sourcing:  RELEASE_LIB=1 source release.sh   → pure helpers, nothing runs.

set -uo pipefail

# ---------------------------------------------------------------------------
# Pure helpers. The whole decision surface; scripts/test-release-sh.sh drives
# these with synthetic input.
# ---------------------------------------------------------------------------

# verdict_version <string> — is this a version we will act on?
#   The realistic failure is not traversal, it is a typo selecting the wrong
#   thing silently: `0.28.O` (letter O) reads as a different release entirely.
verdict_version() {
    case "${1-}" in
        "")                     echo empty ;;
        *[!0-9.]*)              echo malformed ;;
        [0-9]*.[0-9]*.[0-9]*)   echo ok ;;
        *)                      echo malformed ;;
    esac
}

# verdict_act <wheel_diff> <desktop_diff> — release, rebuild, or nothing?
#   Mirrors check-release-ready.sh's verdict_shippable. Kept as its own function
#   because this one is asked BEFORE a version exists.
verdict_act() {
    [ -n "${1-}" ] && { echo release; return; }
    [ -n "${2-}" ] && { echo rebuild; return; }
    echo nothing
}

# rollup_exit <preflight_rc> <held:0|1>
#   held wins over ready: a held run is not a ready one.
rollup_exit() {
    [ "${2-0}" = "1" ] && { echo 75; return; }
    [ "${1-1}" = "0" ] && { echo 0; return; }
    echo 1
}

[ "${RELEASE_LIB:-0}" = "1" ] && return 0 2>/dev/null

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"

B=$'\033[1m'; D=$'\033[2m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
[ -t 1 ] || { B=""; D=""; G=""; Y=""; R=""; N=""; }

die() { printf '%b\n' "${R}error${N}: $*" >&2; exit 2; }

usage() { sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; }

# ---------------------------------------------------------------------------
# The step table. One home. Estimates are MEASURED (docs/release-log.md 0.27.0),
# not guessed — the plan table's originals were guesses and the log says so.
#
#   id | phase | est | consequence | command | tier
#
# tier is empty for every tier, or 2 for a step only a Tier 2 promotion runs.
# It exists because the Snap STABLE push is Tier 2 only, and counting its 10
# minutes into a Tier 1 estimate silently inflated the plan by ten minutes.
# Consequence is empty for reversible steps; anything else is printed in colour
# immediately before the step, because announcing it on a page where nothing
# happens and withholding it where the act occurs is backwards.
# ---------------------------------------------------------------------------
steps_tier1() {
cat <<'TBL'
1|PRE-FLIGHT|1m||./scripts/check-release-ready.sh <V>
2|PRE-FLIGHT|-||write CHANGELOG + README entries, then re-run the preflight
3|REVERSIBLE|1m||./scripts/bump-version.py minor|patch
4|REVERSIBLE|1m||git add CHANGELOG.md README.md CLAUDE.md; git commit; git tag v<V>
4a|REVERSIBLE|-||verify: git rev-parse HEAD == git rev-parse v<V>^{}
5|REVERSIBLE|1m||git push origin main; git push origin v<V>   (two commands, never --tags)
6|REVERSIBLE|11m||SIGN_IDENTITY="$SIGN_IDENTITY" desktop/scripts/build-all.sh
7|REVERSIBLE|30m||desktop/scripts/build-dmg.sh
8|GATE|38m||both CI runs green — the main push run AND the release run
9|IRREVERSIBLE|6m|SOFT: spends a build number forever, and it reaches cohort testers|desktop/scripts/upload-testflight.sh
10|IRREVERSIBLE|13m|the public .dmg permalink swaps the moment this lands|desktop/scripts/upload-dmg.sh
11|IRREVERSIBLE|2m|HARD: this version can never be re-used on PyPI|GitHub run page ▸ Review deployments ▸ Approve and deploy
12|AFTER|-||website: ./build.py && ./deploy.sh   (only AFTER PyPI returns 200)
13|AFTER|10m||gh workflow run snap.yml --ref main          (edge · Tier 1)
13a|AFTER|10m||gh workflow run snap.yml --ref v<V>        (stable)|2
14|AFTER|1m||./scripts/verify-channels.sh <V>
TBL
}

cmd_plan() {
    V="${1-}"; shift || true
    TIER=1; BUILD_ONLY=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --tier) TIER="${2:-1}"; shift 2 ;;
            --build-only) BUILD_ONLY=1; shift ;;
            *) die "unknown argument: $1" ;;
        esac
    done
    case "$(verdict_version "$V")" in
        empty)     die "usage: release.sh plan <X.Y.Z>" ;;
        malformed) die "refusing: unexpected version shape '$V'" ;;
    esac

    LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    WHEEL=$([ -n "$LAST_TAG" ] && git diff "$LAST_TAG"..HEAD --stat -- bristlenose/ frontend/ 2>/dev/null | tail -1 || echo "")
    DESK=$([ -n "$LAST_TAG" ] && git diff "$LAST_TAG"..HEAD --stat -- desktop/ 2>/dev/null | tail -1 || echo "")
    ACT=$(verdict_act "$WHEEL" "$DESK")

    printf '\n%sRelease %s · Tier %s%s' "$B" "$V" "$TIER" "$N"
    [ "$BUILD_ONLY" = "1" ] && printf ' · %s--build-only%s' "$Y" "$N"
    printf '\n%s  from %s · %s commits%s\n\n' "$D" "${LAST_TAG:-<no tag>}" \
        "$([ -n "$LAST_TAG" ] && git rev-list --count "$LAST_TAG"..HEAD 2>/dev/null || echo '?')" "$N"

    case "$ACT" in
        nothing) printf '  %s✗ NOTHING SHIPPABLE since %s%s\n' "$R" "$LAST_TAG" "$N"
                 printf '  %sRe-use the tag; do not bump. This is a normal outcome.%s\n\n' "$D" "$N"
                 return 1 ;;
        rebuild) printf '  %s⚠ wheel byte-identical to %s — a Mac rebuild, not a release%s\n' "$Y" "$LAST_TAG" "$N"
                 printf '  %sConsider ./scripts/bump-version.py --build-only%s\n\n' "$D" "$N" ;;
        release) printf '  %s✓ shippable:%s%s\n\n' "$G" "$N" "$(printf '%s' "$WHEEL" | sed 's/^ */ /')" ;;
    esac

    phase=""
    total=0
    while IFS='|' read -r id ph est cons cmd steptier; do
        [ -z "$id" ] && continue
        # A Tier 2-only step is neither shown nor counted on a Tier 1 plan.
        [ -n "$steptier" ] && [ "$steptier" != "$TIER" ] && continue
        if [ "$ph" != "$phase" ]; then
            phase="$ph"
            case "$ph" in
                IRREVERSIBLE) printf '\n%s%s%s %s— past here nothing can be taken back%s\n' "$B" "$ph" "$N" "$D" "$N" ;;
                GATE)         printf '\n%s%s%s %s— every verdict lands before any irreversible act%s\n' "$B" "$ph" "$N" "$D" "$N" ;;
                *)            printf '\n%s%s%s\n' "$B" "$ph" "$N" ;;
            esac
        fi
        [ -n "$cons" ] && printf '      %s%s%s\n' "$Y" "$cons" "$N"
        printf '  %s%2s%s  %-58s %s%s%s\n' "$D" "$id" "$N" \
            "$(printf '%s' "$cmd" | sed "s|<V>|$V|g")" "$D" "$est" "$N"
        case "$est" in
            *m) total=$(( total + ${est%m} )) ;;
        esac
    done <<EOF
$(steps_tier1)
EOF

    if [ "$total" -ge 60 ]; then
        printf '\n%s  ~%dh%02d pipeline · excludes human decision time and the approval wait%s\n' \
            "$D" $(( total / 60 )) $(( total % 60 )) "$N"
    else
        printf '\n%s  ~%dm pipeline · excludes human decision time and the approval wait%s\n' \
            "$D" "$total" "$N"
    fi
    printf '%s  measured from docs/release-log.md 0.27.0, not estimated%s\n\n' "$D" "$N"

    printf '  %sThis is a plan, not a driver.%s Run the steps yourself, or use %s/bn-release%s,\n' "$B" "$N" "$B" "$N"
    printf '  which owns the order and drafts the prose.\n\n'
    return 0
}

cmd_verify() { exec "$ROOT/scripts/verify-channels.sh" "$@"; }

cmd_status() {
    CUR=$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' bristlenose/__init__.py 2>/dev/null)
    LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "none")
    printf '\n%sBristlenose%s  tree %s · last tag %s\n\n' "$B" "$N" "${CUR:-?}" "$LAST_TAG"

    held=0
    if command -v gh >/dev/null 2>&1; then
        run=$(gh run list --workflow=release.yml --limit 1 --json databaseId,status,conclusion \
                --jq '.[0] | "\(.databaseId) \(.status) \(.conclusion // "-")"' 2>/dev/null || echo "")
        if [ -z "$run" ]; then
            printf '  %s⚠%s release runs   %scould not query — unverified%s\n' "$Y" "$N" "$D" "$N"
        else
            set -- $run
            case "${2-}" in
                waiting) printf '  %s◦%s release run    %s%s waiting on the pypi approval%s\n' "$Y" "$N" "$D" "$1" "$N"; held=1 ;;
                completed) printf '  %s✓%s release run    %s%s %s%s\n' "$G" "$N" "$D" "$1" "${3-}" "$N" ;;
                *) printf '  %s◦%s release run    %s%s %s%s\n' "$D" "$N" "$D" "$1" "${2-}" "$N" ;;
            esac
        fi
    fi
    printf '\n  %sChannel truth needs a probe:  ./scripts/release.sh verify %s%s\n\n' "$D" "${CUR:-<X.Y.Z>}" "$N"
    # Called once. An earlier draft called it twice — the first invocation's
    # stdout leaked a bare "0" into the report, which is precisely the kind of
    # stray output that makes a status page untrustworthy.
    return "$(rollup_exit 0 "$held")"
}

cmd_abandon() {
    V="${1-}"
    case "$(verdict_version "$V")" in
        ok) : ;;
        *)  die "usage: release.sh abandon <X.Y.Z>" ;;
    esac
    printf '\n%sAbandoning %s%s\n\n' "$B" "$V" "$N"
    printf '  %sDelete the tag:%s\n' "$B" "$N"
    printf '    git push --delete origin v%s && git tag -d v%s\n\n' "$V" "$V"
    printf '  %sDo not approve the publish job.%s An un-approved run expires in 30 days\n' "$B" "$N"
    printf '  having published nothing. The only residue is a tag that briefly existed.\n\n'
    printf '  %s⚠ The website is part of this decision, not a later step.%s\n' "$Y" "$N"
    printf '  bristlenose.app/docs/changelog.html renders from CHANGELOG.md at BUILD time,\n'
    printf '  so renaming or removing the %s entry makes every already-deployed copy of\n' "$V"
    printf '  the site wrong the moment the rename lands — actively wrong, not merely stale.\n'
    printf '  That is exactly what happened when 0.26.0 was abandoned: the live changelog\n'
    printf '  named a version nobody could install while the download served 0.27.0.\n\n'
    printf '    cd ../bristlenose-website && ./build.py && ./deploy.sh\n\n'
    printf '  %sThen confirm:%s ./scripts/verify-channels.sh <the version you DID ship> --abandoned %s\n\n' "$B" "$N" "$V"
}

cmd_run() {
    printf '\n  %sThere is no `run`, deliberately.%s\n\n' "$B" "$N"
    printf '  Executing a release crosses two irreversibility lines: a TestFlight build\n'
    printf '  number that is spent forever and reaches cohort testers, and a PyPI version\n'
    printf '  that can never be re-used. docs/design-release-machine.md §7 designs the\n'
    printf '  driver and §12 gates building it on evidence — two release-log entries\n'
    printf '  showing a stranded step or an unusable timing estimate. Neither has\n'
    printf '  happened, so the order still lives with a human and a skill.\n\n'
    printf '    ./scripts/release.sh plan %s      %swhat would happen%s\n' "${1:-<X.Y.Z>}" "$D" "$N"
    printf '    /bn-release                        %sthe order, and the prose%s\n\n' "$D" "$N"
    return 2
}

case "${1-}" in
    plan)    shift; cmd_plan "$@" ;;
    verify)  shift; cmd_verify "$@" ;;
    status|"") cmd_status ;;
    abandon) shift; cmd_abandon "$@" ;;
    run)     shift; cmd_run "$@" ;;
    -h|--help|help) usage ;;
    *)       die "unknown command: $1 (try: plan verify status abandon)" ;;
esac
