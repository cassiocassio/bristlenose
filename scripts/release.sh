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


# ---------------------------------------------------------------------------
# Event log. The DRIVER is the sole producer — it never parses report.sh's @bn
# stream. That stream is presentation: it lives in the one process whose exit
# code bn_autowrap discards, behind a process-tree suppression flag, behind a
# parser that drops a line on an apostrophe. Recording what we ourselves
# observed is both simpler and the only thing that cannot be silently empty.
#
# Append-only. Run state is FOLDED on every read, never stored, so derived state
# cannot drift from the record — it is the record. State someone else owns
# (PyPI, ASC, the Snap store) is probed; only what we did is written down.
# ---------------------------------------------------------------------------

ev_append() { # ev_append <step> <status> [detail]
    printf '{"ts":"%s","run":"%s","step":"%s","status":"%s","detail":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$V" "$1" "$2" \
        "$(printf '%s' "${3-}" | tr -d '"' | tr '\n' ' ' | cut -c1-160)" >> "$EVENTS"
}

# fold_status <step> — ok | fail | running | pending
#   A `running` with no terminus is the STRANDED case: the driver died, the
#   machine slept, someone hit Ctrl-C. It is never auto-advanced past.
fold_status() {
    [ -f "$EVENTS" ] || { echo pending; return; }
    awk -F'"' -v s="$1" '$0 ~ "\"step\":\""s"\"" {
        for (i=1;i<=NF;i++) if ($i=="status") { st=$(i+2) }
    } END { print (st=="" ? "pending" : st) }' "$EVENTS"
}

# probe_done <step> — is this irreversible step ALREADY done in the world?
#   A recorded `ok` is a statement about the past; skipping an irreversible step
#   on it is an assertion about the present. 0.26.0's log would have said
#   "tag pushed ok" for a tag that was then deleted. Probe, then skip.
probe_done() {
    case "$1" in
        tag)
            git ls-remote --tags origin "v$V" 2>/dev/null | grep -q .
            ;;
        dmg)
            curl -sI --max-time 20 "https://bristlenose.app/dmg/Bristlenose.dmg" 2>/dev/null \
                | tr -d '\r' | grep -qi "location:.*$V"
            ;;
        *)
            return 1
            ;;
    esac
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

    kind=""
    total=0
    while IFS='|' read -r id label k est cons cmd steptier; do
        [ -z "$id" ] && continue
        [ -n "$steptier" ] && [ "$steptier" != "$TIER" ] && continue
        _band="$k"; case "$k" in soft|hard) _band=irreversible ;; esac
        if [ "$_band" != "$kind" ]; then
            kind="$_band"
            case "$k" in
                irreversible) printf '\n%bIRREVERSIBLE%b %b- past here nothing can be taken back%b\n' "$B" "$N" "$D" "$N" ;;
                gate)      printf '\n%bGATE%b %b- every verdict lands before any irreversible act%b\n' "$B" "$N" "$D" "$N" ;;
                *)         printf '\n%bREVERSIBLE%b\n' "$B" "$N" ;;
            esac
        fi
        [ -n "$cons" ] && printf '      %b%s%b\n' "$Y" "${cons//__V__/$V}" "$N"
        cmd="${cmd//__V__/$V}"
        case "$cmd" in
            __BUMP__)   cmd="./scripts/bump-version.py <minor|patch> && git commit" ;;
            __TAG__)    cmd="git tag v$V && git push origin v$V" ;;
            __CIWAIT__) cmd="wait for the strict CI run on main" ;;
        esac
        printf '  %b%-10s%b %-50s %b%s%b\n' "$D" "$id" "$N" "$cmd" "$D" "$est" "$N"
        case "$est" in *m) total=$(( total + ${est%m} )) ;; esac
    done <<EOF
$(run_steps)
EOF

    if [ "$total" -ge 60 ]; then
        printf '\n%s  ~%dh%02d pipeline · excludes human decision time%s\n' \
            "$D" $(( total / 60 )) $(( total % 60 )) "$N"
    else
        printf '\n%s  ~%dm pipeline · excludes human decision time%s\n' \
            "$D" "$total" "$N"
    fi
    printf '%s  measured from docs/release-log.md 0.27.0, not estimated%s\n\n' "$D" "$N"

    printf '  %brelease.sh run %s --bump minor|patch%b   %bexecutes this, resumably%b\n' "$B" "$V" "$N" "$D" "$N"
    printf '  %b/bn-release%b                             %bdrafts the prose first%b\n\n' "$B" "$N" "$D" "$N"
    printf '  %bThe tag is the release.%b Everything above it is abandonable; nothing\n' "$Y" "$N"
    printf '  below it can be taken back.\n\n'
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

# ---------------------------------------------------------------------------
# run — execute the release.
#
# ORDER, AND WHY IT CHANGED (23 Aug 2026)
#
# The pypi environment's required-reviewer hold was removed. That hold was what
# made "push the tag early" safe: the tag started release.yml and its publish job
# then waited for a human. Without it a tag push publishes as soon as release.yml
# is satisfied — so THE TAG PUSH IS NOW THE RELEASE, and it moves to the end.
#
# Removing the hold is not removing the gate. publish `needs: build` needs `ci`,
# and release.yml invokes ci.yml with strict-macos: true. PyPI cannot receive a
# version whose full matrix, e2e and strict macOS suite did not pass on the
# tagged commit. The click was replaced by assertions that actually inspect the
# artefact, which a human clicking approve at 11pm does not.
#
# The 0.25.2 lesson is preserved, and step `strict-ci` is what preserves it.
# Moving the tag last would otherwise ship the Mac artefacts BEFORE any strict
# verdict — exactly the window 0.25.2 died in. ci.yml exposes strict-macos on
# workflow_dispatch, so the strict verdict is obtainable on main WITHOUT a tag.
# Every verdict still lands before every irreversible act; only the act that
# publishes moved.
#
#   id | label | kind | command
# kind: gate = must pass, no side effect · soft/hard = irreversible · plain
# ---------------------------------------------------------------------------
run_steps() {
cat <<'RUNTBL'
preflight|preflight|gate|1m||./scripts/check-release-ready.sh __V__|
bump|bump + commit|plain|1m||__BUMP__|
push-main|push main|plain|1m||git push origin main|
strict-ci|dispatch strict CI on main|plain|1m||gh workflow run ci.yml --ref main -f strict-macos=true|
build-all|build the app|plain|11m||desktop/scripts/build-all.sh|
build-dmg|build the dmg|plain|30m||desktop/scripts/build-dmg.sh|
ci-green|GATE strict CI green|gate|38m||__CIWAIT__|
testflight|upload to TestFlight|soft|6m|SOFT: spends a build number forever, and it reaches cohort testers|desktop/scripts/upload-testflight.sh|
dmg|publish the dmg|soft|13m|the public permalink swaps the moment this lands|desktop/scripts/upload-dmg.sh|
tag|tag + push|hard|2m|HARD: this PUBLISHES. __V__ can never be re-used on PyPI|__TAG__|
snap|snap edge|plain|10m||gh workflow run snap.yml --ref main|
snap-stable|snap stable|plain|10m||gh workflow run snap.yml --ref v__V__|2
verify|verify every channel|gate|1m||./scripts/verify-channels.sh __V__|
RUNTBL
}


cmd_run() {
    V="${1-}"; shift || true
    BUMP=""; ASSUME_YES=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --bump) BUMP="${2:-}"; shift 2 ;;
            --yes|-y) ASSUME_YES=1; shift ;;
            *) die "unknown argument: $1" ;;
        esac
    done
    [ "$(verdict_version "$V")" = ok ] || die "usage: release.sh run <X.Y.Z> --bump minor|patch"
    case "$BUMP" in minor|patch|major) : ;; *) die "--bump minor|patch|major is required" ;; esac

    RUNDIR=".release/$V"; EVENTS="$RUNDIR/events.jsonl"; LOGDIR="$RUNDIR/logs"

    # One driver at a time. mkdir is atomic on every POSIX filesystem and its
    # failure is unambiguous — flock does not exist on macOS.
    mkdir -p "$RUNDIR"
    LOCK="$RUNDIR/.lock"
    if ! mkdir "$LOCK" 2>/dev/null; then
        printf 'error: another run holds %s (pid %s)\n' \
            "$LOCK" "$(cat "$LOCK/pid" 2>/dev/null || echo '?')" >&2
        exit 2
    fi
    echo $$ > "$LOCK/pid"
    trap 'rm -rf "$LOCK"; rmdir "$RUNDIR" 2>/dev/null || true' EXIT INT TERM

    printf '\n%bRelease %s%b  bump=%s\n' "$B" "$V" "$N" "$BUMP"
    printf '%b  the tag push publishes. Everything before it is abandonable.%b\n\n' "$D" "$N"

    if [ "$ASSUME_YES" != "1" ]; then
        printf '  Type the version to confirm: '
        read -r typed
        [ "$typed" = "$V" ] || die "confirmation did not match, nothing done"
        echo
    fi
    # After the confirmation, not before: a declined run should leave nothing.
    mkdir -p "$LOGDIR"

    BUMP_CMD="./scripts/bump-version.py $BUMP && git add -A && git commit -m \"bump to $V\""
    TAG_CMD="git tag v$V && git push origin v$V"
    CI_CMD="gh run watch \$(gh run list --workflow=ci.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status"

    ev_append run started "bump=$BUMP"
    while IFS='|' read -r id label kind est cons cmd steptier; do
        [ -z "$id" ] && continue
        # run is Tier 1; a Tier 2 promotion is a different act, not a longer run.
        [ -n "$steptier" ] && continue
        cmd="${cmd//__V__/$V}"
        [ "$cmd" = "__BUMP__" ] && cmd="$BUMP_CMD"
        [ "$cmd" = "__TAG__" ] && cmd="$TAG_CMD"
        [ "$cmd" = "__CIWAIT__" ] && cmd="$CI_CMD"

        prev="$(fold_status "$id")"
        if [ "$prev" = "ok" ]; then
            case "$kind" in
                soft|hard)
                    if probe_done "$id"; then
                        printf '  %b-%b %-26s %balready done in the world%b\n' "$D" "$N" "$label" "$D" "$N"
                        continue
                    fi
                    printf '  %b!%b %-26s %blog says done, the world disagrees, re-running%b\n' \
                        "$Y" "$N" "$label" "$D" "$N"
                    ;;
                *)
                    printf '  %b-%b %-26s %bskipped (done)%b\n' "$D" "$N" "$label" "$D" "$N"
                    continue
                    ;;
            esac
        elif [ "$prev" = "running" ]; then
            printf '\n  %bx%b %s was interrupted and its outcome is unrecorded.\n' "$R" "$N" "$label"
            printf '    Check it by hand, then: %brelease.sh retry %s %s%b\n\n' "$B" "$V" "$id" "$N"
            exit 3
        fi

        if [ -n "$cons" ]; then
            case "$kind" in
                hard) printf '  %b* %s%b\n' "$R" "${cons//__V__/$V}" "$N" ;;
                *)    printf '  %b* %s%b\n' "$Y" "${cons//__V__/$V}" "$N" ;;
            esac
        fi
        printf '  %b$ %s%b\n' "$D" "$cmd" "$N"

        n=1; while [ -e "$LOGDIR/$id.$n.log" ]; do n=$((n+1)); done
        LOG="$LOGDIR/$id.$n.log"
        ev_append "$id" running "attempt $n"
        t0=$SECONDS
        # REDIRECT, never pipe. $? is then the command's own status, not tail's.
        # release-log 0.27.0 #1: five runs reported exit 0 and three had failed.
        eval "$cmd" > "$LOG" 2>&1
        rc=$?
        el=$(( SECONDS - t0 ))

        if [ "$rc" -eq 0 ]; then
            ev_append "$id" ok "${el}s"
            printf '  %bv%b %-26s %b%ss%b\n\n' "$G" "$N" "$label" "$D" "$el" "$N"
        else
            ev_append "$id" fail "exit $rc"
            printf '  %bx%b %-26s %bexit %s%b\n' "$R" "$N" "$label" "$R" "$rc" "$N"
            # tr: rsync --progress writes carriage returns, so a raw tail shows
            # the START of one enormous line and a healthy transfer reads frozen.
            tr '\r' '\n' < "$LOG" | grep -vE '^[[:space:]]*$' | tail -12 | sed 's/^/      /'
            printf '\n  %blog%b %s\n' "$D" "$N" "$LOG"
            printf '  %bfix, then%b release.sh run %s --bump %s   %b(resumes here)%b\n\n' \
                "$B" "$N" "$V" "$BUMP" "$D" "$N"
            exit 1
        fi
    done <<EOF
$(run_steps)
EOF

    ev_append run completed ""
    printf '  %bv %s released.%b  ./scripts/release.sh verify %s\n\n' "$G" "$V" "$N" "$V"
}

cmd_retry() {
    V="${1-}"; STEP="${2-}"
    [ "$(verdict_version "$V")" = ok ] || die "usage: release.sh retry <X.Y.Z> <step>"
    [ -n "$STEP" ] || die "usage: release.sh retry <X.Y.Z> <step>"
    EVENTS=".release/$V/events.jsonl"
    [ -f "$EVENTS" ] || die "no run log at $EVENTS"
    printf '{"ts":"%s","run":"%s","step":"%s","status":"pending","detail":"reset by retry"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$V" "$STEP" >> "$EVENTS"
    printf '\n  %b%s reset to pending.%b  release.sh run %s --bump <kind>\n\n' "$B" "$STEP" "$N" "$V"
}

case "${1-}" in
    plan)    shift; cmd_plan "$@" ;;
    verify)  shift; cmd_verify "$@" ;;
    status|"") cmd_status ;;
    abandon) shift; cmd_abandon "$@" ;;
    run)     shift; cmd_run "$@" ;;
    retry)   shift; cmd_retry "$@" ;;
    -h|--help|help) usage ;;
    *)       die "unknown command: $1 (try: plan run verify status abandon retry)" ;;
esac
