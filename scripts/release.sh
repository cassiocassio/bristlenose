#!/usr/bin/env bash
# release.sh — the conductor's page, executable. READ-ONLY.
#
# WHAT THIS IS
#
# The release train. `plan` shows what would happen, `run` does it, `verify`
# probes every channel, `status` folds the log, `abandon` prints the recipe and
# its website consequence, `retry` un-strands a step.
#
# THE TAG IS THE RELEASE (23 Aug 2026). The pypi required-reviewer hold was
# removed, so `release.yml` runs to completion on a tag push. `run` therefore
# puts the tag LAST, after the soft uploads, and gets its strict verdict from a
# `workflow_dispatch` of ci.yml on main — which is what keeps every verdict
# ahead of every irreversible act now that the tag publishes.
#
# The gate is the job graph, not a click: publish needs build needs ci, invoked
# with strict-macos: true. check-release-ready.sh's `publish gate` row asserts
# that chain and fails if it breaks.
#
# Usage (defaults, 28 Aug 2026: the version and the bump kind are one fact
# spelled two ways — either alone suffices, both cross-check, and every
# inference is narrated):
#   release.sh plan [<X.Y.Z>] [--bump minor|patch|major] [--tier 1|2]
#                                     bare = next minor after the last tag
#   release.sh run [<X.Y.Z>] [--bump minor|patch|major] [--yes] [--board]
#                                     version alone infers the bump; --bump
#                                     alone infers the version; bare = next
#                                     minor, and the confirm prompt is then
#                                     mandatory (--yes cannot skip typing a
#                                     version that was never given); a resume
#                                     needs neither (the run dir remembers)
#   release.sh verify [<X.Y.Z>] [--abandoned <X.Y.Z>]
#                                     bare = the tree's version
#   release.sh status
#   release.sh abandon [<X.Y.Z>]      bare = the sole run under .release/
#   release.sh retry [<X.Y.Z>] <step> likewise
#   release.sh recover [<X.Y.Z>]      after a failed or missing release run
#
# Exit codes:
#   0   ready / verified / complete
#   1   not ready, a step failed, or a channel is not on this version
#   2   usage error, or another run holds the lock
#   3   a step is stranded — started, outcome unrecorded, never auto-advanced
#   75  EX_TEMPFAIL — every act is done, verification is pending. Not an error.
#       `run` is a launcher, not a foreground poll: release.yml runs the full
#       matrix before publish, so PyPI, the GitHub Release, Homebrew and Snap
#       are legitimately absent for ~40 minutes after the tag lands. Kept
#       distinct from 0 so `release.sh run … && deploy-website` cannot fire on
#       a release that has not published yet.
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
    # Escape, never mutilate. The old `tr -d '"'` stripped quotes but left
    # backslashes bare, so a detail carrying `C:\Users` was ALREADY invalid
    # JSON — unnoticed only because details were short ASCII. Order matters
    # twice. (1) Truncate BEFORE escaping: the other order can slice a \" at
    # char 160 and leave a trailing backslash. (2) iconv is not decoration:
    # BSD `cut -c` counts BYTES even under a UTF-8 locale (measured 27 Aug
    # 2026), so the cut can split a multibyte character; `iconv -c` drops the
    # incomplete tail. Its stderr warning is the expected case, and its exit
    # code is discarded by the substitution. Control bytes (ANSI colour, CR)
    # are stripped, not escaped — invalid in JSON strings, never information.
    printf '{"ts":"%s","run":"%s","step":"%s","status":"%s","detail":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$V" "$1" "$2" \
        "$(printf '%s' "${3-}" | tr '\n' ' ' | tr -d '\000-\037' | cut -c1-160 \
             | iconv -c -f UTF-8 -t UTF-8 2>/dev/null \
             | sed 's/\\/\\\\/g; s/"/\\"/g')" >> "$EVENTS"
}

# fold_status <step> — ok | fail | running | pending
#   A `running` with no terminus is the STRANDED case: the driver died, the
#   machine slept, someone hit Ctrl-C. It is never auto-advanced past.
fold_status() {
    [ -f "$EVENTS" ] || { echo pending; return; }
    # TOTAL, deliberately. A write truncated mid-ev_append yields a fragment like
    # "o", which used to fall through the ok/running cases in cmd_run and EXECUTE
    # the step — re-publishing 644 MB, or spending a build number. A corrupt line
    # is the same unknown outcome the stranded branch exists for, and must take
    # the same path. (Comment lives out here: an apostrophe inside the awk
    # program would close the shell single-quote.)
    awk -F'"' -v s="$1" '$0 ~ "\"step\":\""s"\"" {
        for (i=1;i<=NF;i++) if ($i=="status") { st=$(i+2) }
    } END {
        out = (st == "" ? "pending" : st)
        if (out !~ /^(ok|fail|running|pending|skipped)$/) out = "corrupt"
        print out
    }' "$EVENTS"
}

# next_version <X.Y.Z> <patch|minor|major> — the successor, or fail.
#   Strictly three numeric parts: a 4-part build-only version has no single
#   successor, and inferring one would guess.
next_version() {
    printf '%s' "$1" | awk -F. -v k="$2" '
        NF==3 && $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/ {
            if      (k=="patch") { print $1"."$2"."$3+1; ok=1 }
            else if (k=="minor") { print $1"."$2+1".0";  ok=1 }
            else if (k=="major") { print $1+1".0.0";     ok=1 }
        } END { exit !ok }'
}

# bump_kind <base> <target> — patch|minor|major|same|irregular.
#   The version and the bump kind are one fact spelled two ways; this is the
#   translation, so the CLI can accept either spelling and cross-check both.
bump_kind() {
    local _k
    [ "$1" = "$2" ] && { echo same; return; }
    for _k in patch minor major; do
        [ "$(next_version "$1" "$_k" 2>/dev/null)" = "$2" ] && { echo "$_k"; return; }
    done
    echo irregular
}

# infer_rundir — the sole run under .release/, or fail (1 none, 2 ambiguous).
infer_rundir() {
    set -- .release/*/
    [ -d "${1:-}" ] || return 1
    [ $# -eq 1 ] || return 2
    basename "$1"
}

# verdict_complete — names every Tier-1 step the ledger cannot account for.
#   stdin: the step table (run_steps output) · needs $EVENTS set.
#   Prints missing step ids one per line; prints nothing when complete.
#
#   Exists because the loop ENDING is not the table FINISHING. On 28 Aug 2026 a
#   step command consumed the loop's heredoc stdin, so the remaining rows were
#   never read: the steps never ran, wrote no events, and the driver fell off
#   the end and declared the run complete. A step that is never read is never
#   recorded — no ledger read can see it. Only re-deriving the table and
#   demanding a terminal status per step can. Same class as the pipeline's
#   attempted==succeeded+failed tautology (CLAUDE.md): a rollup that is green
#   because the missing thing was never counted. "Done" is a claim about a
#   checklist, never about an input stream ending.
verdict_complete() {
    local id label kind est steptier cons cmd
    while IFS='|' read -r id label kind est steptier cons cmd; do
        [ -z "$id" ] && continue
        [ -n "$steptier" ] && continue
        case "$(fold_status "$id")" in
            ok|skipped) : ;;
            *) printf '%s\n' "$id" ;;
        esac
    done
}

# verdict_tag_provenance — may the tag land on THIS HEAD? Needs $CI_SHA_FILE.
#   ok      HEAD is the commit the strict verdict names, and the tree is clean
#   moved   HEAD is not the recorded ci-sha
#   dirty   uncommitted changes
#   no-sha  nothing recorded — strict CI was never dispatched from this run
#
#   The gap this closes was live on 28 Aug 2026: fixes landed mid-run after
#   ci-green failed, and only a hand re-dispatch + hand-updated ci-sha kept
#   the verdict and the tag on the same commit. The verdict is ABOUT a sha;
#   the tag is the publishing act; nothing mechanical demanded they agree —
#   and this repo's history includes concurrent sessions moving HEAD.
verdict_tag_provenance() {
    local want have
    want="$(cat "$CI_SHA_FILE" 2>/dev/null)"
    [ -n "$want" ] || { echo no-sha; return; }
    have="$(git rev-parse HEAD 2>/dev/null)"
    [ "$have" = "$want" ] || { echo moved; return; }
    git diff-index --quiet HEAD -- 2>/dev/null || { echo dirty; return; }
    echo ok
}

# write_context <rundir> — what this run was CONFIGURED with, to context.json.
#
#   events.jsonl records that a step ran; it has never recorded what the step
#   was configured with. On 27 Aug 2026 an inherited SIGN_IDENTITY selected
#   the App Store certificate for the .dmg: 19 minutes and a notarisation
#   round-trip later the image was unshippable, and the ledger could not say
#   why, because nothing had written the environment down.
#
#   The env capture is an ALLOWLIST and must stay one — this file is what a
#   person pastes into a bug report. Every name below is an identifier (a
#   certificate name, a keychain profile name, a team id), never a secret.
#   Non-fatal, never silent: a release must not fail because its telemetry
#   did, but a missing context.json must say so rather than just not exist.
write_context() {
    command -v python3 >/dev/null 2>&1 || {
        printf '  %b·%b context.json skipped — no python3\n' "${Y-}" "${N-}"; return 0; }
    python3 - "$1/context.json" <<'PYEOF' || \
        printf '  %b·%b context.json failed to write\n' "${Y-}" "${N-}"
import json, os, platform, shutil, subprocess, sys

def sh(*a):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""

WATCHED = ("SIGN_IDENTITY", "SIGN_IDENTITY_APPSTORE", "SIGN_IDENTITY_DEVELOPER_ID",
           "TEAM_ID", "NOTARY_PROFILE", "NOTARY_ZIP")

free = shutil.disk_usage(".").free // (1024 ** 3)
ctx = {
    "host": platform.node(),
    "os": "%s %s" % (platform.system(), platform.mac_ver()[0] or platform.release()),
    "arch": platform.machine(),
    "xcode": " ".join(sh("xcodebuild", "-version").split()),
    "python": platform.python_version(),
    "disk_free_gb": free,
    "git": {"sha": sh("git", "rev-parse", "--short", "HEAD"),
            "branch": sh("git", "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(sh("git", "status", "--porcelain"))},
    "env": {k: os.environ.get(k, "<unset>") for k in WATCHED},
}
with open(sys.argv[1], "w") as fh:
    json.dump(ctx, fh, indent=2, sort_keys=True)
    fh.write("\n")
print("  context %s %s \u00b7 %s \u00b7 %d GB free" % (
    ctx["git"]["sha"], "dirty" if ctx["git"]["dirty"] else "clean", ctx["arch"], free))
PYEOF
}

# probe_done <step> — is this irreversible step ALREADY done in the world?
#   0 = done · 1 = probed, absent · 2 = no probe exists here · 3 = probe FAILED.
#   3 is not 1. "I could not look" and "I looked and it is not there" lead to
#   opposite actions on a step that cannot be un-performed.
#   A recorded `ok` is a statement about the past; skipping an irreversible step
#   on it is an assertion about the present. 0.26.0's log would have said
#   "tag pushed ok" for a tag that was then deleted. Probe, then skip.
probe_done() {
    local _out _rc
    case "$1" in
        testflight)
            # upload-testflight.sh --probe asks App Store Connect, via the API
            # key, whether a build of $V exists: 0 delivered · 1 absent · 3
            # could not look. Wired 28 Aug 2026, after a resume stopped to ask
            # a human a question the machine had credentials to answer. A
            # missing script or unexpected exit maps to 3, never 1 — "could
            # not look" and "looked and it is not there" lead to opposite
            # actions on a step that spends a build number forever.
            [ -x desktop/scripts/upload-testflight.sh ] || return 3
            # BN_PROBE_WINDOW_S: keep re-reading before answering "absent".
            # ASC's build index is eventually consistent and this probe gates a
            # step that cannot be un-performed, so a single negative read
            # inside the propagation window is not evidence. Only the caller
            # that already has a recorded success sets this (see the `prev=ok`
            # arm below); a cold probe stays instant.
            BN_PROBE_WINDOW_S="${BN_PROBE_WINDOW_S:-0}" \
                desktop/scripts/upload-testflight.sh --probe "$V" >/dev/null 2>&1
            case $? in 0) return 0 ;; 1) return 1 ;; *) return 3 ;; esac
            ;;
        tag)
            # Capture, THEN test. `git ls-remote | grep -q .` cannot tell an
            # absent tag (exit 0, no output) from an unreachable remote (exit
            # non-zero, no output) — both came out as 1, "probed and absent", and
            # the caller answers that by RE-PERFORMING an irreversible step. A
            # network blip was enough. Tri-state is the rule everywhere else in
            # this chain; this is the one place where breaking it re-publishes.
            _out=$(git ls-remote --tags origin "v$V" 2>/dev/null); _rc=$?
            [ "$_rc" -ne 0 ] && return 3
            printf '%s' "$_out" | grep -q .
            ;;
        dmg)
            # -F on the versioned filename, not a regex on the bare version.
            # `location:.*$V` treats the dots as wildcards, so 0.28.0 would match
            # 0X28Y0 — too loose to be a probe that decides whether to re-publish.
            _out=$(curl -sI --max-time 20 "$DMG_PERMALINK" 2>/dev/null); _rc=$?
            if [ "$_rc" -ne 0 ] || [ -z "$_out" ]; then return 3; fi
            printf '%s' "$_out" | tr -d '\r' | grep -qiF "$(printf "$DMG_VERSIONED" "$V")"
            ;;
        *)
            # 2 = NO PROBE EXISTS from here. Distinct from 1, which means a probe
            # ran and the thing is absent. Collapsing them meant a resume after a
            # SUCCESSFUL TestFlight upload re-ran it and spent a second build
            # number forever — on the one step whose declared cost is that it
            # cannot be unspent. TestFlight needs an ASC key; there is no probe.
            return 2
            ;;
    esac
}

# verdict_signing_identity <type> [<pin>] — resolve ONE signing identity from
# `security find-identity` text on STDIN. Pure text→verdict; the suite drives
# it with synthetic keychains.
#   stdout: ok <sha1> <common name> · absent · ambiguous <n> · pin-not-found ·
#           pin-wrong-type        (non-ok also returns 1)
#
# WHY FINGERPRINTS, NOT NAMES (31 Aug 2026): Apple certificate renewal leaves
# two VALID identities carrying the IDENTICAL common name for days. A name can
# never split that pair; the SHA-1 can, so a pin is a fingerprint (a full CN is
# accepted for standalone convenience but cannot disambiguate twins), and the
# resolved identity is returned hash-first — codesign accepts the hash and
# signs deterministically. find-identity -v filters EXPIRED identities before
# we ever see the list, so expiry is not a case here; the renewal twin is.
verdict_signing_identity() {
    local _type="$1" _pin="${2:-}" _all _rows _sel _n
    _all=$(cat)
    _rows=$(printf '%s\n' "$_all" | grep -E '^[[:space:]]*[0-9]+\)' \
                | grep -F "\"$_type:" || true)
    if [ -n "$_pin" ]; then
        if printf '%s' "$_pin" | grep -qiE '^[0-9a-f]{40}$'; then
            _sel=$(printf '%s\n' "$_rows" | grep -iF " $_pin " || true)
            if [ -z "$_sel" ]; then
                printf '%s\n' "$_all" | grep -qiF " $_pin " \
                    && { echo pin-wrong-type; return 1; }
                echo pin-not-found; return 1
            fi
        else
            _sel=$(printf '%s\n' "$_rows" | grep -F "\"$_pin\"" || true)
            if [ -z "$_sel" ]; then
                printf '%s\n' "$_all" | grep -qF "\"$_pin\"" \
                    && { echo pin-wrong-type; return 1; }
                echo pin-not-found; return 1
            fi
        fi
        _rows=$_sel
    fi
    _n=$(printf '%s\n' "$_rows" | grep -c .)
    case "$_n" in
        0) echo absent; return 1 ;;
        1) : ;;
        *) echo "ambiguous $_n"; return 1 ;;
    esac
    printf 'ok %s %s\n' \
        "$(printf '%s\n' "$_rows" | awk '{print $2}')" \
        "$(printf '%s\n' "$_rows" | sed 's/^[^\"]*\"//; s/\".*$//')"
}

# resolve_identity <type> [<pin>] — live wrapper with the per-type POLICY the
# keychain demands. Measured 31 Aug 2026: the installer certificate is
# INVISIBLE under `-p codesigning` and appears only under the basic policy —
# one flag for all types refuses a certificate that is present.
resolve_identity() {
    local _type="$1"
    case "$_type" in
        "3rd Party Mac Developer Installer")
            security find-identity -v 2>/dev/null ;;
        *)  security find-identity -v -p codesigning 2>/dev/null ;;
    esac | verdict_signing_identity "$_type" "${2:-}"
}

# verdict_recover <published> <run_state> <tag_sha> <head_sha>
#   The rerun-vs-retag decision, which release-log v0.15.13 got wrong at cost.
#
#   `gh run rerun --failed` replays the TAGGED COMMIT, not main's latest. So if
#   a later commit already fixed the failing step, the rerun fails identically —
#   which is what happened on v0.15.13 (an e2e Playwright CDN stall; the rerun
#   of the stale commit failed the same way, and moving the tag to the fix
#   published cleanly).
#
#   It is three cases, not two, and the third is the one people forget: a run
#   that NEVER FIRED. `git push origin main --tags` bundles the branch and tag
#   events and the tag-driven workflow gets debounced into never running
#   (v0.15.0). That needs redelivery of the same sha, not a rerun of nothing.
#
#   Prints: published | wait | redeliver | rerun | retag | investigate
verdict_recover() {
    local published="${1-}" run_state="${2-}" tag_sha="${3-}" head_sha="${4-}"
    # Published wins over everything: there is nothing to recover, only to
    # supersede. Reached first so no branch below can suggest tag surgery on an
    # immutable version.
    [ "$published" = yes ] && { echo published; return; }
    case "$run_state" in
        none)                echo redeliver ;;
        queued|in_progress)  echo wait ;;
        success)             echo investigate ;;   # green but not on PyPI
        failure|cancelled|timed_out|startup_failure)
            # THE decision. Same sha means no fix exists yet, so the failure can
            # only be transient — rerun. A moved HEAD means main carries
            # something the tagged commit does not, and a rerun would replay the
            # commit without it.
            if [ -n "$tag_sha" ] && [ "$tag_sha" = "$head_sha" ]; then echo rerun
            else echo retag; fi ;;
        *)                   echo investigate ;;
    esac
}

# board_link <version> — print the live board's url if one is serving this run.
# The board is optional and the driver must not need it (design-release-board
# §1): this reads one file the server wrote, checks its pid is alive, prints
# one line, and is silent on every other outcome. Never starts, waits, or fails.
board_link() {
    local _f=".release/$1/board-server.json" _url _pid _port
    [ -f "$_f" ] || return 0
    _url="$(jq -r '.url // empty' "$_f" 2>/dev/null)" || return 0
    _pid="$(jq -r '.pid // empty' "$_f" 2>/dev/null)" || return 0
    _port="$(jq -r '.port // empty' "$_f" 2>/dev/null)" || return 0
    case "$_pid" in ''|*[!0-9]*) return 0 ;; esac
    case "$_port" in ''|*[!0-9]*) return 0 ;; esac
    kill -0 "$_pid" 2>/dev/null || return 0
    # a recycled pid is not the board: the port in the url must be the file's, and open
    case "$_url" in "http://127.0.0.1:$_port/"*) ;; *) return 0 ;; esac
    ( exec 3<>"/dev/tcp/127.0.0.1/$_port" ) 2>/dev/null || return 0
    case "$_url" in *[![:print:]]*|*' '*) return 0 ;; esac
    printf '  %sboard%s  %s\n' "${B:-}" "${N:-}" "$_url"
    return 0
}

# board_ensure <version> — `run --board`: print the board's link, starting a
# detached server first if none is serving this run. The server owns its own
# life (idle exit, run-dir-gone exit); the driver spawns it, waits at most a
# few seconds for its handshake, prints, and forgets it. It never fails the run:
# a missing generator or python is one line of note, and the release proceeds.
board_ensure() {
    local _v="$1" _py _gen="${RELEASE_BOARD_PY:-$ROOT/scripts/release-board.py}" _i _out
    _out="$(board_link "$_v")"; if [ -n "$_out" ]; then printf '%s\n' "$_out"; return 0; fi
    _py="$ROOT/.venv/bin/python"; [ -x "$_py" ] || _py="$(command -v python3 || true)"
    if [ -z "$_py" ] || [ ! -f "$_gen" ]; then
        printf '  %sboard%s  not started — %s\n' "${D:-}" "${N:-}" "$([ -f "$_gen" ] && echo 'no python' || echo "no $_gen")"
        return 0
    fi
    mkdir -p ".release/$_v" 2>/dev/null || return 0
    ( nohup "$_py" "$_gen" "$_v" --serve --with-logs >".release/$_v/board-server.log" 2>&1 </dev/null & ) 2>/dev/null
    for _i in 1 2 3 4 5 6; do
        sleep 0.5
        _out="$(board_link "$_v")"; if [ -n "$_out" ]; then printf '%s\n' "$_out"; return 0; fi
    done
    printf '  %sboard%s  not up after 3s — see .release/%s/board-server.log\n' "${D:-}" "${N:-}" "$_v"
    return 0
}

[ "${RELEASE_LIB:-0}" = "1" ] && return 0 2>/dev/null

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
# The sink (docs/design-release-board.md §1.2). The driver writes its own
# boundary lines — asserted, unlike the children's — so an empty sink under a
# completed step reads "ran; sink received nothing", never "did not run".
if [ -f "$ROOT/desktop/scripts/sink.sh" ]; then
    # shellcheck source=desktop/scripts/sink.sh
    . "$ROOT/desktop/scripts/sink.sh"
else
    sink_line() { :; }; sink_line_or_die() { :; }
fi
# resolve_run — the run a bare `verify`/`status` means: the sole run under
# .release/, or the newest by events.jsonl mtime when several exist (narrated
# to stderr). Prints the version or nothing. Used to export the sink so the
# post-release verbs write channel and CI rows into the run they describe.
resolve_run() {
    local d newest="" n=0
    for d in .release/*/; do
        [ -f "$d/events.jsonl" ] || continue
        n=$((n+1))
        if [ -z "$newest" ] || [ "$d/events.jsonl" -nt "$newest/events.jsonl" ]; then newest="${d%/}"; fi
    done
    [ -n "$newest" ] || return 0
    [ "$n" -gt 1 ] && printf '  %s(%d runs under .release/ — using the newest, %s)%s\n' "$D" "$n" "$(basename "$newest")" "$N" >&2
    basename "$newest"
}
export_sink_for() { # export_sink_for <version> — says so when the run dir is absent
    if [ -z "${1:-}" ] || [ ! -d ".release/$1" ]; then
        printf '  %s(no run dir for %s under .release/ — rows will not be recorded)%s\n' "$D" "${1:-?}" "$N" >&2
        return 0
    fi
    export BN_RUN_ID="$1" BN_EVENT_SINK="$ROOT/.release/$1/bn-events.log"
}

# Project identity. Everything about WHICH project this is lives in project.conf;
# everything about HOW a release is ordered and executed lives here. A second
# project should be a copy of that file, not a fork of this one.
# shellcheck source=scripts/project.conf
. "$ROOT/scripts/project.conf"

B=$'\033[1m'; D=$'\033[2m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
[ -t 1 ] || { B=""; D=""; G=""; Y=""; R=""; N=""; }

die() { printf '%b\n' "${R}error${N}: $*" >&2; exit 2; }

usage() { sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; }

# ---------------------------------------------------------------------------
# The step table. One home. Estimates are MEASURED (docs/release-log.md 0.27.0),
# not guessed — the plan table's originals were guesses and the log says so.
#
#   id | label | kind | est | tier | consequence | COMMAND (last)
#
# command is LAST so `read` gives it the line's remainder: a pipe inside a
# command would otherwise spill into the next field and silently drop the step.
#
# tier is empty for every tier, or 2 for a step only a Tier 2 promotion runs.
# It exists because the Snap STABLE push is Tier 2 only, and counting its 10
# minutes into a Tier 1 estimate silently inflated the plan by ten minutes.
# Consequence is empty for reversible steps; anything else is printed in colour
# immediately before the step, because announcing it on a page where nothing
# happens and withholding it where the act occurs is backwards.
# ---------------------------------------------------------------------------
run_steps() {
# RELEASE_STEPS_FILE is a testability seam, not a feature. scripts/test-release-e2e.sh
# points it at a table of harmless commands so the REAL cmd_run loop — its event
# appends, elapsed times, skip logic, probe branch, failure tail and resume — can
# be driven end to end without performing a release. Same shape as BN_BIN in
# check-doc-surfaces.sh. Unset in every real invocation.
if [ -n "${RELEASE_STEPS_FILE:-}" ]; then cat "$RELEASE_STEPS_FILE"; return; fi
cat <<'RUNTBL'
preflight|preflight|gate|1m|||./scripts/check-release-ready.sh __V__
bump|bump + commit|plain|1m|||__BUMP__
push-main|push main|plain|1m|||git push origin main
strict-ci|dispatch strict CI on main|plain|1m|||__DISPATCH__
build-all|build the app|plain|11m|||desktop/scripts/build-all.sh
build-dmg|build the dmg|plain|30m|||desktop/scripts/build-dmg.sh
ci-green|GATE strict CI green|gate|38m|||__CIWAIT__
testflight|upload to TestFlight|soft|6m||SOFT: spends a build number forever, and it reaches cohort testers|desktop/scripts/upload-testflight.sh
dmg|publish the dmg|soft|13m||the public permalink swaps the moment this lands|desktop/scripts/upload-dmg.sh
tag|tag + push|hard|2m||HARD: this PUBLISHES. __V__ can never be re-used on PyPI|__TAG__
snap|snap edge|plain|10m|||gh workflow run __WF_SNAP__ --ref main
snap-stable|snap stable|plain|10m|2||gh workflow run __WF_SNAP__ --ref v__V__
RUNTBL
}

cmd_plan() {
    V=""
    case "${1-}" in ""|-*) : ;; *) V="$1"; shift ;; esac
    TIER=1; PLAN_BUMP=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --tier) [ $# -ge 2 ] || die "--tier needs a tier"; TIER="$2"; shift 2 ;;
            --bump) [ $# -ge 2 ] || die "--bump needs a value"; PLAN_BUMP="$2"; shift 2 ;;
            *) die "unknown argument: $1" ;;
        esac
    done
    if [ -z "$V" ]; then
        # plan is read-only, so a narrated guess is safe. The house bias is
        # minor ("does this add a capability?" is usually yes); --bump picks
        # otherwise, and the printed assumption is the correction affordance.
        _tagbase="$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')"
        [ -n "$_tagbase" ] || die "usage: release.sh plan <X.Y.Z> — no tag to infer from"
        case "${PLAN_BUMP:-minor}" in minor|patch|major) : ;; *) die "--bump minor|patch|major (got '$PLAN_BUMP')" ;; esac
        V="$(next_version "$_tagbase" "${PLAN_BUMP:-minor}")" \
            || die "cannot compute the next ${PLAN_BUMP:-minor} from v$_tagbase — pass a version"
        printf '  %bplanning %s%b %b— next %s after v%s; pass a version or --bump to change%b\n' \
            "$B" "$V" "$N" "$D" "${PLAN_BUMP:-minor}" "$_tagbase" "$N"
    fi
    case "$(verdict_version "$V")" in
        empty)     die "usage: release.sh plan <X.Y.Z>" ;;
        malformed) die "refusing: unexpected version shape '$V'" ;;
    esac
    case "$TIER" in 1|2) : ;; *) die "--tier must be 1 or 2 (got '$TIER')" ;; esac

    LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    WHEEL=$([ -n "$LAST_TAG" ] && git diff "$LAST_TAG"..HEAD --stat -- bristlenose/ frontend/ 2>/dev/null | tail -1 || echo "")
    DESK=$([ -n "$LAST_TAG" ] && git diff "$LAST_TAG"..HEAD --stat -- desktop/ 2>/dev/null | tail -1 || echo "")
    ACT=$(verdict_act "$WHEEL" "$DESK")

    printf '\n%sRelease %s · Tier %s%s' "$B" "$V" "$TIER" "$N"
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
    while IFS='|' read -r id label k est steptier cons cmd; do
        [ -z "$id" ] && continue
        [ -n "$steptier" ] && [ "$steptier" != "$TIER" ] && continue
        _band="$k"; case "$k" in soft|hard) _band=irreversible ;; esac
        if [ "$_band" != "$kind" ]; then
            kind="$_band"
            # On $_band, not $k. Switching on the raw kind meant soft/hard fell to
            # the *) arm and every irreversible step was announced REVERSIBLE —
            # on the one line whose entire job is warning you.
            case "$_band" in
                irreversible) printf '\n%bIRREVERSIBLE%b %b- past here nothing can be taken back%b\n' "$B" "$N" "$D" "$N" ;;
                gate)      printf '\n%bGATE%b %b- every verdict lands before any irreversible act%b\n' "$B" "$N" "$D" "$N" ;;
                *)         printf '\n%bREVERSIBLE%b\n' "$B" "$N" ;;
            esac
        fi
        [ -n "$cons" ] && printf '      %b%s%b\n' "$Y" "${cons//__V__/$V}" "$N"
        cmd="${cmd//__V__/$V}"; cmd="${cmd//__WF_CI__/$WF_CI}"; cmd="${cmd//__WF_STRICT__/$WF_STRICT_INPUT}"; cmd="${cmd//__WF_SNAP__/$WF_SNAP}"
        case "$cmd" in
            __BUMP__)   cmd="./scripts/bump-version.py <minor|patch> && git commit" ;;
            __TAG__)    cmd="git tag v$V && git push origin v$V" ;;
            __DISPATCH__) cmd="gh workflow run $WF_CI --ref main -f $WF_STRICT_INPUT=true" ;;
            __CIWAIT__) cmd="wait for the strict CI run it dispatched" ;;
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

cmd_verify() {
    # The version is the first non-flag argument, else the resolved run; the
    # sink is exported for it so verify-channels.sh's rows land in the run dir.
    local _v=""
    case "${1-}" in ""|-*) _v="$(resolve_run)" ;; *) _v="$1" ;; esac
    export_sink_for "$_v"
    board_link "$_v" || true
    exec "$ROOT/scripts/verify-channels.sh" "$@"
}

cmd_status() {
    CUR=$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' bristlenose/__init__.py 2>/dev/null)
    LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "none")
    printf '\n%sBristlenose%s  tree %s · last tag %s\n\n' "$B" "$N" "${CUR:-?}" "$LAST_TAG"

    held=0
    # Status is the one verb that asks GitHub, so it is where CI facts enter the
    # sink: the strict run on the sha strict-ci dispatched (the same selector
    # CI_CMD uses — --event workflow_dispatch, headSha == ci-sha; a sha-only
    # match picks the non-strict push run, release-log 0.25.2), and the release
    # run. Results are tri-state: a run, `no run for sha`, or `unreachable`.
    _sv="$(resolve_run)"; export_sink_for "$_sv"
    if command -v gh >/dev/null 2>&1; then
        if [ -n "${_sv:-}" ] && [ -f ".release/$_sv/ci-sha" ]; then
            _sha="$(cat ".release/$_sv/ci-sha" 2>/dev/null)"
            if printf '%s' "$_sha" | grep -qE '^[0-9a-f]{40}$'; then
                _ci="$(SHA="$_sha" gh run list --workflow=$WF_CI --event workflow_dispatch --branch main --limit 10 \
                        --json databaseId,headSha,status,conclusion \
                        --jq '[.[]|select(.headSha==env.SHA)]|.[0] | "\(.databaseId) \(.status) \(.conclusion // "-")"' 2>/dev/null)"
                if [ -z "$_ci" ]; then
                    sink_line ci workflow="$WF_CI" sha="$_sha" result=unreachable
                elif [ "${_ci%% *}" = null ]; then
                    # jq interpolates a null .[0] as "null null -" — the first
                    # word is the test, not the whole string (review, 5 Sep 2026)
                    sink_line ci workflow="$WF_CI" sha="$_sha" result="no run for sha"
                else
                    set -- $_ci
                    _cires="${3-}"; [ "${2-}" = completed ] || _cires="${2-}"
                    sink_line ci workflow="$WF_CI" sha="$_sha" run_id="${1-}" result="$_cires"
                    if [ -n "${1-}" ] && [ "${1-}" != null ]; then
                        gh run view "$1" --json jobs --jq '.jobs[] | "\(.name)\t\(.status)\t\(.conclusion // "-")"' 2>/dev/null \
                          | while IFS=$'\t' read -r _jn _js _jc; do
                                [ -n "$_jn" ] || continue
                                _jr="$_jc"; [ "$_js" = completed ] || _jr="$_js"
                                sink_line ci workflow="$WF_CI" sha="$_sha" run_id="$1" job="$_jn" result="$_jr"
                            done
                    fi
                fi
            fi
        fi
        run=$(gh run list --workflow=$WF_RELEASE --limit 1 --json databaseId,status,conclusion \
                --jq '.[0] | "\(.databaseId) \(.status) \(.conclusion // "-")"' 2>/dev/null || echo "")
        # The sink's release row is keyed to THIS run's tag branch, never the
        # newest run of the workflow: a 0.30.0 dir must not receive 0.29.1's
        # success (review, 5 Sep 2026). The status line above stays as it was.
        if [ -n "${_sv:-}" ] && [ -n "$BN_EVENT_SINK" ]; then
            _rel="$(BR="v$_sv" gh run list --workflow=$WF_RELEASE --branch "v$_sv" --limit 1 \
                    --json databaseId,status,conclusion,headBranch \
                    --jq '.[0] | "\(.databaseId) \(.status) \(.conclusion // "-") \(.headBranch)"' 2>/dev/null)"
            if [ -z "$_rel" ]; then sink_line ci workflow="$WF_RELEASE" branch="v$_sv" result=unreachable
            elif [ "${_rel%% *}" = null ]; then sink_line ci workflow="$WF_RELEASE" branch="v$_sv" result="no run for sha"
            else set -- $_rel; _rr="${3-}"; [ "${2-}" = completed ] || _rr="${2-}"; sink_line ci workflow="$WF_RELEASE" branch="${4-}" run_id="${1-}" result="$_rr"; fi
        fi
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
    _hb=".release/${CUR:-}/heartbeat"
    if [ -n "${CUR:-}" ] && [ -f "$_hb" ]; then
        IFS=$'\t' read -r _hep _hid _hel _hmsg < "$_hb" 2>/dev/null || true
        if [ -n "${_hep:-}" ]; then
            _age=$(( $(date +%s) - _hep ))
            if [ "$_age" -lt $(( ${BN_HEARTBEAT_SECS:-300} * 3 )) ]; then
                printf '  %b◦%b live step      %b%s · %sm in · %s%b\n' \
                    "$D" "$N" "$D" "${_hid:-?}" "$(( ${_hel:-0} / 60 ))" "${_hmsg:-}" "$N"
            else
                printf '  %b⚠%b live step      %b%s wrote no heartbeat for %sm — driver stranded?%b\n' \
                    "$Y" "$N" "$Y" "${_hid:-?}" "$(( _age / 60 ))" "$N"
            fi
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
    if [ -z "$V" ]; then
        V="$(infer_rundir)" || die "usage: release.sh abandon <X.Y.Z> — no sole run to infer"
        printf '  %b%s%b %b— the only run under .release/%b\n' "$B" "$V" "$N" "$D" "$N"
    fi
    case "$(verdict_version "$V")" in
        ok) : ;;
        *)  die "usage: release.sh abandon <X.Y.Z>" ;;
    esac
    printf '\n%bAbandoning %s%b\n\n' "$B" "$V" "$N"

    # PROBE, do not assert. This used to say "an un-approved run expires in 30
    # days having published nothing" — written when a hold existed, false since
    # it was removed this morning. It is the command a frightened person reaches
    # for at 11pm, and it was telling them a published version never published.
    _code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
              "$(printf "$PYPI_JSON" "$V")" 2>/dev/null || echo 000)
    _tagged=no
    git ls-remote --tags origin "v$V" 2>/dev/null | grep -q . && _tagged=yes

    case "$_code" in
        200)
            printf '  %b✗ %s IS ON PYPI AND CANNOT BE ABANDONED.%b\n\n' "$R" "$V" "$N"
            printf '  A PyPI version is immutable. Deleting the tag changes nothing there,\n'
            printf '  and Homebrew was dispatched from it.\n\n'
            printf '  %bSupersede it:%b cut the next version with the fix.\n' "$B" "$N"
            printf '  Do not re-cut %s — the preflight will refuse, correctly.\n\n' "$V"
            return 1
            ;;
        404) : ;;
        *)
            printf '  %b⚠ could not reach PyPI (HTTP %s) — state unconfirmed%b\n\n' "$Y" "$_code" "$N"
            ;;
    esac

    if [ "$_tagged" = yes ]; then
        printf '  %b⚠ v%s is on origin, so release.yml is running.%b\n' "$Y" "$V" "$N"
        printf '  Deleting the tag cancels the publish only if you win that race:\n\n'
    else
        printf '  %b✓ not tagged, not published — nothing has left this machine.%b\n\n' "$G" "$N"
    fi
    printf '    git push --delete origin v%s && git tag -d v%s\n\n' "$V" "$V"

    printf '  %b⚠ The website is part of this decision, not a later step.%b\n' "$Y" "$N"
    printf '  The changelog page renders from CHANGELOG.md at BUILD time, so removing\n'
    printf '  the %s entry makes every already-deployed copy of the site wrong.\n\n' "$V"
    printf '    cd ../bristlenose-website && ./build.py && ./deploy.sh\n\n'
}

cmd_recover() {
    V="${1-}"
    if [ -z "$V" ]; then
        V="$(infer_rundir)" || die "usage: release.sh recover <X.Y.Z> — no sole run to infer"
        printf '  %b%s%b %b— the only run under .release/%b\n' "$B" "$V" "$N" "$D" "$N"
    fi
    [ "$(verdict_version "$V")" = ok ] || die "usage: release.sh recover <X.Y.Z>"

    printf '\n%bRecovering %s%b\n\n' "$B" "$V" "$N"

    _pub=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
             "$(printf "$PYPI_JSON" "$V")" 2>/dev/null || echo 000)
    _published=no; [ "$_pub" = 200 ] && _published=yes

    _tag_sha=$(git rev-parse "v$V^{}" 2>/dev/null || echo "")
    _head_sha=$(git rev-parse HEAD 2>/dev/null || echo "")

    # The id comes back WITH the state, from the same v$V-filtered query. The
    # remedies below used to paste `gh run … $(gh run list --limit 1 …)`, which
    # selects by RECENCY — so recovering an older version while any newer release
    # run existed reran or viewed the wrong run. cmd_run's own comment condemns
    # exactly this selector; the commands a frightened person pastes at 11pm were
    # still using it.
    _run_id=""
    if command -v gh >/dev/null 2>&1; then
        _q=$(gh run list --workflow=$WF_RELEASE --limit 20 \
                   --json databaseId,headBranch,status,conclusion \
                   --jq "[.[]|select(.headBranch==\"v$V\")]|.[0]|
                         if . == null then \"|none\"
                         else \"\(.databaseId)|\(if .status != \"completed\" then .status else .conclusion end)\"
                         end" 2>/dev/null || echo "|QUERY_FAILED")
        _run_id="${_q%%|*}"; _state="${_q#*|}"
    else
        _state=QUERY_FAILED
    fi
    [ -z "$_state" ] || [ "$_state" = null ] && _state=none
    # An id-less remedy would be `gh run watch ""` — which fails closed, but
    # silently and with a useless message. Say which run, or say there isn't one.
    _run_ref="${_run_id:-<no run id — check \`gh run list --workflow=$WF_RELEASE\`>}"

    printf '  %bPyPI%b        %s\n' "$D" "$N" \
        "$([ "$_published" = yes ] && echo "$V is published" || echo "$V not published (HTTP $_pub)")"
    printf '  %btag%b         %s\n' "$D" "$N" "${_tag_sha:-not found locally}"
    printf '  %bHEAD%b        %s%s\n' "$D" "$N" "${_head_sha:-?}" \
        "$([ -n "$_tag_sha" ] && [ "$_tag_sha" != "$_head_sha" ] && echo "  (main has moved past the tag)" || echo "")"
    printf '  %brelease run%b %s\n\n' "$D" "$N" "$_state"

    if [ "$_state" = QUERY_FAILED ]; then
        printf '  %b⚠ could not query the release runs — diagnosis unavailable.%b\n\n' "$Y" "$N"
        return 1
    fi

    case "$(verdict_recover "$_published" "$_state" "$_tag_sha" "$_head_sha")" in
        published)
            printf '  %b✓ Nothing to recover — %s is on PyPI.%b\n' "$G" "$V" "$N"
            printf '  A PyPI version is immutable. If it is wrong, supersede it.\n\n' ;;
        wait)
            printf '  %bℹ The run is still going. Watch it:%b\n\n' "$Y" "$N"
            printf '    gh run watch %s --exit-status\n\n' "$_run_ref" ;;
        redeliver)
            printf '  %bNo run fired for v%s — this is the DEBOUNCE case.%b\n' "$B" "$V" "$N"
            printf '  A bundled `git push --tags` sends the branch and tag events together\n'
            printf '  and the tag-driven workflow can be debounced into never firing.\n'
            printf '  Redelivering the SAME sha is a semantic no-op that re-triggers it:\n\n'
            printf '    git push --delete origin v%s && git push origin v%s\n\n' "$V" "$V" ;;
        rerun)
            printf '  %bThe run failed and the tag IS HEAD — rerun is correct.%b\n' "$B" "$N"
            printf '  Nothing on main is missing from the tagged commit, so the failure can\n'
            printf '  only be transient (a CDN stall, a flake, a runner).\n\n'
            printf '    gh run rerun --failed %s\n\n' "$_run_ref" ;;
        retag)
            printf '  %b⚠ The run failed and MAIN HAS MOVED — do NOT rerun.%b\n\n' "$Y" "$N"
            printf '  `gh run rerun --failed` replays the TAGGED COMMIT, not main. If a later\n'
            printf '  commit fixed the failing step, the rerun fails identically — which is\n'
            printf '  what happened on v0.15.13. Move the tag to the fix instead:\n\n'
            printf '    git tag -f v%s %s\n' "$V" "$(git rev-parse --short HEAD 2>/dev/null)"
            printf '    git push --delete origin v%s && git push origin v%s\n\n' "$V" "$V"
            printf '  %bCheck first%b that HEAD actually contains the fix:\n' "$B" "$N"
            printf '    git log %s..HEAD --oneline\n\n' "${_tag_sha:0:9}" ;;
        investigate)
            printf '  %b⚠ The run reports %s but %s is not on PyPI.%b\n' "$Y" "$_state" "$V" "$N"
            printf '  Neither a rerun nor a retag is indicated. Read the run first:\n\n'
            printf '    gh run view %s\n\n' "$_run_ref" ;;
    esac
}

cmd_run() {
    V=""
    case "${1-}" in ""|-*) : ;; *) V="$1"; shift ;; esac
    BUMP=""; ASSUME_YES=0; SKIP=""; V_FULLY_INFERRED=0; WANT_BOARD=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --bump) [ $# -ge 2 ] || die "--bump needs a value"; BUMP="$2"; shift 2 ;;
            --yes|-y) ASSUME_YES=1; shift ;;
            --board) WANT_BOARD=1; shift ;;
            --skip) [ $# -ge 2 ] || die "--skip needs a step"; SKIP="${SKIP:-} $2"; shift 2 ;;
            *) die "unknown argument: $1" ;;
        esac
    done

    # ── Less-needy defaults (28 Aug 2026). The version and the bump kind are
    # one fact spelled two ways, so demanding both was ceremony: either alone
    # now suffices, both together cross-check, and a resume reads its bump
    # from its own first ledger line. Every inference is NARRATED — a silent
    # default is a trap; a narrated one is a colleague — and the confirmation
    # prompt still makes the human type the version, inferred or not. The
    # inference base is the LAST TAG (the released truth), never the tree,
    # which is mid-bump exactly when it matters.
    _tagbase="$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')"
    if [ -n "$V" ] && [ -f ".release/$V/events.jsonl" ]; then
        _led="$(sed -n 's/.*"step":"run","status":"started","detail":"bump=\([a-z]*\)".*/\1/p' \
                    ".release/$V/events.jsonl" | head -1)"
        if [ -n "$_led" ]; then
            [ -n "$BUMP" ] && [ "$BUMP" != "$_led" ] \
                && die "this run was started with --bump $_led; refusing --bump $BUMP on a resume"
            [ -z "$BUMP" ] && printf '  %bresuming %s%b %b(bump=%s, from its own ledger)%b\n' \
                "$B" "$V" "$N" "$D" "$_led" "$N"
            BUMP="$_led"
        fi
    fi
    if [ -z "$V" ] && [ -n "$BUMP" ]; then
        case "$BUMP" in minor|patch|major) : ;; *) die "--bump minor|patch|major (got '$BUMP')" ;; esac
        [ -n "$_tagbase" ] || die "no tag to infer the version from — pass it explicitly"
        V="$(next_version "$_tagbase" "$BUMP")" \
            || die "cannot compute the next $BUMP from v$_tagbase — pass the version explicitly"
        printf '  %brelease %s%b %b— next %s after v%s%b\n' "$B" "$V" "$N" "$D" "$BUMP" "$_tagbase" "$N"
    elif [ -n "$V" ] && [ -z "$BUMP" ]; then
        [ -n "$_tagbase" ] || die "no tag to infer the bump kind from — pass --bump minor|patch|major"
        BUMP="$(bump_kind "$_tagbase" "$V")"
        case "$BUMP" in
            minor|patch|major)
                printf '  %brelease %s%b %b— a %s after v%s%b\n' "$B" "$V" "$N" "$D" "$BUMP" "$_tagbase" "$N" ;;
            same) die "$V is already tagged and has no run dir to resume — release.sh recover $V" ;;
            *)    die "v$_tagbase → $V is no single step of patch/minor/major — pass --bump explicitly" ;;
        esac
    elif [ -n "$V" ] && [ -n "$BUMP" ]; then
        case "$BUMP" in minor|patch|major) : ;; *) die "--bump minor|patch|major (got '$BUMP')" ;; esac
        if [ -n "$_tagbase" ]; then
            _k="$(bump_kind "$_tagbase" "$V")"
            case "$_k" in
                "$BUMP"|same) : ;;  # same = a resume of a tagged version; live resumes were handled above
                irregular) printf '  %b⚠ %s is not one step after v%s — proceeding, both were explicit%b\n' \
                               "$Y" "$V" "$_tagbase" "$N" ;;
                *) die "v$_tagbase → $V is a $_k, not a $BUMP — one of the two is a typo" ;;
            esac
        fi
    else
        # Bare `run` infers the next MINOR — the house bias ("does this add a
        # capability?" is usually yes, and the 0.15.x line is what a patch
        # habit looks like). The safety is not the flag, it is the
        # confirmation prompt: the inferred version must pass through the
        # human's fingers before anything runs. --yes does not skip typing a
        # version that was never given.
        [ -n "$_tagbase" ] || die "usage: release.sh run [<X.Y.Z>] [--bump minor|patch|major] — no tag to infer from"
        BUMP=minor
        V_FULLY_INFERRED=1
        V="$(next_version "$_tagbase" "$BUMP")" \
            || die "cannot compute the next minor from v$_tagbase — pass the version explicitly"
        printf '  %brelease %s%b %b— next minor after v%s; --bump patch or a version to change%b\n' \
            "$B" "$V" "$N" "$D" "$_tagbase" "$N"
    fi
    [ "$(verdict_version "$V")" = ok ] || die "refusing: unexpected version shape '$V'"

    # Validate the skips against the table. `--skip flibbertigibbet` used to be
    # accepted in silence — the same class cmd_retry already refuses, and here it
    # is worse: you believe you have skipped the step that spends a build number,
    # and you have skipped nothing.
    SKIP_FLAGS=""
    for _s in $SKIP; do
        run_steps | awk -F'|' -v s="$_s" '$1==s{f=1} END{exit !f}' \
            || die "no such step '$_s' (try: $(run_steps | awk -F'|' 'NF>1{printf "%s ", $1}'))"
        SKIP_FLAGS="$SKIP_FLAGS --skip $_s"
    done

    RUNDIR=".release/$V"; EVENTS="$RUNDIR/events.jsonl"; LOGDIR="$RUNDIR/logs"

    # One driver at a time. mkdir is atomic on every POSIX filesystem and its
    # failure is unambiguous — flock does not exist on macOS.
    mkdir -p "$RUNDIR"
    # Private: context.json carries the host name and signing identity, logs/
    # carry raw tool output. One mode on the directory beats one per file.
    chmod 700 "$RUNDIR" 2>/dev/null || true
    LOCK="$RUNDIR/.lock"
    if ! mkdir "$LOCK" 2>/dev/null; then
        printf 'error: another run holds %s (pid %s)\n' \
            "$LOCK" "$(cat "$LOCK/pid" 2>/dev/null || echo '?')" >&2
        exit 2
    fi
    echo $$ > "$LOCK/pid"
    # EXIT cleans up; INT/TERM must also STOP. Trapping INT without exiting released
    # the lock and let the loop continue — a running driver with no lock, and a
    # second `run` in another window would have started.
    trap 'rm -rf "$LOCK"; rmdir "$RUNDIR" 2>/dev/null || true' EXIT
    STEP_PID=""
    # Kill the running step, then leave. Without this the child outlives the
    # driver: a half-finished upload with nothing watching it.
    # Kill the step AND its descendants. $STEP_PID is the subshell wrapping the
    # command; `build-dmg.sh` spawns xcodebuild under that, and killing only the
    # wrapper orphans a 30-minute build with nothing watching it. pkill -P walks
    # one generation, which covers the shape every step here has.
    _stop_step() {
        _stop_heartbeat
        [ -n "${STEP_PID:-}" ] || return 0
        pkill -TERM -P "$STEP_PID" 2>/dev/null || true
        kill -TERM "$STEP_PID" 2>/dev/null || true
    }
    # Liveness, deliberately NOT in events.jsonl: fold_status folds any status
    # outside its fixed set to `corrupt`, which takes the stranded path — a
    # heartbeat status in the ledger would make every long step unresumable.
    # The ledger is history; liveness is present tense, so it is one
    # overwritten line whose STALENESS is the signal. A clean stop removes the
    # file; a SIGKILLed driver cannot, so a surviving file that stopped
    # updating IS the stranded case, which the events file alone cannot
    # distinguish from a slow step. The ticker exits by itself within one
    # interval of the driver dying (the kill -0 guard), and reads nothing
    # from stdin — the step table lives there.
    #   format: epoch<TAB>step<TAB>elapsed-seconds<TAB>last non-blank log line
    HB_PID=""
    _start_heartbeat() { # _start_heartbeat <step> <logfile>
        local _id="$1" _log="$2" _t0 _drv=$$
        _t0=$(date +%s)
        ( while :; do
              sleep "${BN_HEARTBEAT_SECS:-300}"
              kill -0 "$_drv" 2>/dev/null || exit 0
              printf '%s\t%s\t%s\t%s\n' "$(date +%s)" "$_id" \
                  "$(( $(date +%s) - _t0 ))" \
                  "$(tr '\r' '\n' < "$_log" 2>/dev/null | grep -vE '^[[:space:]]*$' \
                       | tail -1 | tr -d '\000-\037' | cut -c1-100)" \
                  > "$RUNDIR/heartbeat"
          done ) < /dev/null 2>/dev/null &
        HB_PID=$!
    }
    _stop_heartbeat() {
        [ -n "${HB_PID:-}" ] || return 0
        kill "$HB_PID" 2>/dev/null || true
        HB_PID=""
        rm -f "$RUNDIR/heartbeat"
    }
    trap '_stop_step; exit 130' INT TERM

    printf '\n%bRelease %s%b  bump=%s\n' "$B" "$V" "$N" "$BUMP"
    printf '%b  the tag push publishes. Everything before it is abandonable.%b\n\n' "$D" "$N"

    # A synthetic step table means there is no release to gather credentials
    # for. RELEASE_STEPS_FILE is the seam this file already documents as
    # "a testability seam, not a feature … Unset in every real invocation", so
    # reusing it costs no new bypass — and a NEW flag would be the wrong answer
    # twice over: settable in production, and therefore able to reinstate the
    # exact 31 Aug 2026 bug the block below exists to prevent.
    #
    # Without this the e2e suite could not run at all. It died at exit 2 before
    # the step loop it exists to exercise, and had done since 2 Sep: 82
    # assertions all reporting `expected '75', got '2'`, one cause. It cannot be
    # fixed by stubbing either, because `stat -f '%Lp'` is BSD and this suite
    # runs on ubuntu — the harness would have to impersonate a Mac.
    #
    # What the block does below is still covered, just not from here:
    # verdict_signing_identity is a pure text→verdict function and
    # test-release-sh.sh drives it directly, which is where its logic lives.
    if [ -n "${RELEASE_STEPS_FILE:-}" ]; then
        printf '  %bsynthetic step table — credential gathering skipped%b\n\n' "$D" "$N"
    else
    # ── Credentials: gathered HERE, before the one confirmation — never
    # discovered by a step. 31 Aug 2026: SIGN_IDENTITY_APPSTORE was unset and
    # build-all found out four steps in, after an outward-facing push. The
    # design intent of `run` is ONE authorisation, then bed: everything the
    # steps will need is resolved, probed and DISPLAYED while a human is
    # provably present, and nothing below the confirmation may prompt, hang,
    # or discover a missing credential. Failures here are die → exit 2, with
    # nothing performed and nothing written outside the lock.
    #
    # An ambient generic SIGN_IDENTITY is the 27 Aug 2026 vector (it selected
    # the App Store certificate for the .dmg, caught only after a notarisation
    # round-trip). Under the driver it is refused outright, not warned.
    [ -z "${SIGN_IDENTITY:-}" ] \
        || die "SIGN_IDENTITY is exported — the generic name is the 27 Aug 2026 mis-sign vector. unset it; the driver resolves per-purpose identities itself"

    # Non-secret publishing constants share ONE home with the scripts that
    # already source it (env wins; BRISTLENOSE_SHIP_CONF is the test seam,
    # upload-dmg.sh's convention). Values are cert names/fingerprints, a team
    # id, a keychain profile NAME — identifiers, never secrets.
    _env_as="${SIGN_IDENTITY_APPSTORE:-}"; _env_di="${SIGN_IDENTITY_DEVELOPER_ID:-}"
    _env_np="${NOTARY_PROFILE:-}";         _env_tm="${TEAM_ID:-}"
    SHIP_CONF="${BRISTLENOSE_SHIP_CONF:-$ROOT/desktop/scripts/.ship-local.conf}"
    # shellcheck disable=SC1090
    [ -f "$SHIP_CONF" ] && . "$SHIP_CONF"
    [ -n "$_env_as" ] && SIGN_IDENTITY_APPSTORE="$_env_as"
    [ -n "$_env_di" ] && SIGN_IDENTITY_DEVELOPER_ID="$_env_di"
    [ -n "$_env_np" ] && NOTARY_PROFILE="$_env_np"
    [ -n "$_env_tm" ] && TEAM_ID="$_env_tm"
    NOTARY_PROFILE="${NOTARY_PROFILE:-bristlenose-notary}"

    _out=$(resolve_identity "Apple Distribution" "${SIGN_IDENTITY_APPSTORE:-}")
    case "$_out" in ok\ *) : ;; *) die "Apple Distribution identity: $_out — pin the fingerprint as SIGN_IDENTITY_APPSTORE in $SHIP_CONF (from: security find-identity -v -p codesigning)" ;; esac
    ID_AS_HASH=$(printf '%s' "$_out" | awk '{print $2}')
    ID_AS_CN=$(printf '%s' "$_out" | cut -d' ' -f3-)
    _out=$(resolve_identity "Developer ID Application" "${SIGN_IDENTITY_DEVELOPER_ID:-}")
    case "$_out" in ok\ *) : ;; *) die "Developer ID identity: $_out — pin the fingerprint as SIGN_IDENTITY_DEVELOPER_ID in $SHIP_CONF" ;; esac
    ID_DI_HASH=$(printf '%s' "$_out" | awk '{print $2}')
    ID_DI_CN=$(printf '%s' "$_out" | cut -d' ' -f3-)
    _out=$(resolve_identity "3rd Party Mac Developer Installer" "${SIGN_IDENTITY_INSTALLER:-}")
    case "$_out" in ok\ *) : ;; *) die "installer certificate: $_out — the .pkg cannot be signed (basic policy: security find-identity -v)" ;; esac
    ID_IN_CN=$(printf '%s' "$_out" | cut -d' ' -f3-)

    # The probe battery. Tri-state in spirit: a timeout is reported as
    # BLOCKED-ON-A-DIALOG, a distinct state from failed — because on an
    # unattended resume a keychain/TCC dialog HANGS a probe rather than
    # failing it, and < /dev/null cannot save you from a GUI dialog.
    # Dialog-capable probes are ANNOUNCED first (house rule: never auto-fire
    # a trust dialog): the confirmation is the one right time to fire them.
    _TIMEOUT=$(command -v timeout || command -v gtimeout || true)
    _probe() { # _probe <seconds> <label> <cmd...>
        local _t="$1" _lab="$2" _rc; shift 2
        ${_TIMEOUT:+"$_TIMEOUT" "$_t"} "$@" >/dev/null 2>&1 < /dev/null
        _rc=$?
        if [ "$_rc" -eq 0 ]; then
            printf '    %b✓%b %s\n' "$G" "$N" "$_lab"
        elif [ "$_rc" -eq 124 ]; then
            die "$_lab: blocked waiting on a dialog (${_t}s) — run once interactively, answer it (Allow, never Always Allow), then re-run"
        else
            die "$_lab failed (exit $_rc) — nothing has been done; fix and re-run"
        fi
    }
    printf '  %bprobing every credential the steps will use%b — dialogs, if any, fire NOW:\n' "$B" "$N"
    printf '    %b·%b a keychain dialog may appear per signing key — answer Allow, never Always Allow\n' "$D" "$N"
    cp /bin/ls "$LOCK/probe.bin"
    _probe 45 "sign as Apple Distribution" codesign -f -s "$ID_AS_HASH" "$LOCK/probe.bin"
    cp /bin/ls "$LOCK/probe.bin"
    _probe 45 "sign as Developer ID"       codesign -f -s "$ID_DI_HASH" "$LOCK/probe.bin"
    rm -f "$LOCK/probe.bin"
    _probe 60 "notary profile '$NOTARY_PROFILE'" xcrun notarytool history --keychain-profile "$NOTARY_PROFILE"
    [ -n "${BRISTLENOSE_ASC_KEY_ID:-}" ] \
        || die "BRISTLENOSE_ASC_KEY_ID is not set ($SHIP_CONF) — the TestFlight upload would fail at minute 50"
    _keyfile="$HOME/.private_keys/AuthKey_${BRISTLENOSE_ASC_KEY_ID}.p8"
    [ -f "$_keyfile" ] || die "ASC API key absent: $_keyfile (Apple's documented layout; altool reads keys from the filesystem only)"
    [ "$(stat -f '%Lp' "$_keyfile" 2>/dev/null)" = "600" ] \
        || die "ASC API key $_keyfile is not mode 600"
    printf '    %b✓%b ASC API key AuthKey_%s.p8 (mode 600)\n' "$G" "$N" "$BRISTLENOSE_ASC_KEY_ID"
    _probe 30 "git credentials (push --dry-run)" env GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/usr/bin/false git push --dry-run origin main
    _probe 30 "gh auth" gh auth status
    [ -n "${BRISTLENOSE_DMG_REMOTE:-}" ] \
        || die "BRISTLENOSE_DMG_REMOTE is not set ($SHIP_CONF) — the dmg publish step needs it"
    _probe 30 "dmg remote ssh (BatchMode)" ssh -o BatchMode=yes -o ConnectTimeout=15 "${BRISTLENOSE_DMG_REMOTE%%:*}" true
    printf '    %b·%b Finder automation (create-dmg drives it) — a permission dialog may appear once\n' "$D" "$N"
    _probe 20 "Finder automation (TCC)" osascript -e 'tell application "Finder" to count windows'
    [ -x "$ROOT/desktop/Bristlenose/Resources/ffmpeg" ] && [ -x "$ROOT/desktop/Bristlenose/Resources/ffprobe" ] \
        || die "bundled ffmpeg/ffprobe missing — run desktop/scripts/fetch-ffmpeg.sh first; a release run must never reach for the network here"
    printf '    %b✓%b bundled ffmpeg + ffprobe present\n' "$G" "$N"
    _slp=$(pmset -g 2>/dev/null | awk '$1=="sleep"{print $2; exit}')
    [ -n "$_slp" ] && [ "$_slp" != "0" ] \
        && printf '    %b⚠ system sleep is %s min — the run holds caffeinate -i (idle), but a CLOSED LID still sleeps%b\n' "$Y" "$_slp" "$N"

    printf '\n  will sign and publish as:\n'
    printf '    %-22s %s  %b%.8s…%b\n' "Apple Distribution" "$ID_AS_CN" "$D" "$ID_AS_HASH" "$N"
    printf '    %-22s %s  %b%.8s…%b\n' "Developer ID" "$ID_DI_CN" "$D" "$ID_DI_HASH" "$N"
    printf '    %-22s %s\n' "installer (.pkg)" "$ID_IN_CN"
    printf '    %-22s %s · ASC key %s\n\n' "notary profile" "$NOTARY_PROFILE" "$BRISTLENOSE_ASC_KEY_ID"

    fi

    # A fully inferred version must pass through the human's fingers: --yes
    # cannot skip typing a version that was never given. (Headless, that read
    # hits EOF, matches nothing, and dies — fail closed.) With a version or
    # --bump on the command line the human already named the release, so
    # --yes keeps its meaning there.
    if [ "$ASSUME_YES" != "1" ] || [ "$V_FULLY_INFERRED" = 1 ]; then
        printf '  Type the version to confirm: '
        read -r typed
        [ "$typed" = "$V" ] || die "confirmation did not match, nothing done"
        echo
    fi
    # One confirmation covered the version AND the credential set. Arm the run:
    # identities exported BY FINGERPRINT (deterministic under renewal twins —
    # the build scripts map hash → CN for their type gates and sign by hash),
    # and every interactive fallback converted to a loud failure. Nothing
    # below may prompt; if something tries anyway, it now fails instead.
    [ -n "${ID_AS_HASH:-}" ] && export SIGN_IDENTITY_APPSTORE="$ID_AS_HASH"
    [ -n "${ID_DI_HASH:-}" ] && export SIGN_IDENTITY_DEVELOPER_ID="$ID_DI_HASH"
    export NOTARY_PROFILE
    [ -n "${TEAM_ID:-}" ] && export TEAM_ID
    export GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/usr/bin/false
    export SSH_ASKPASS_REQUIRE=never SSH_ASKPASS=/usr/bin/false
    export GH_PROMPT_DISABLED=1 GH_NO_UPDATE_NOTIFIER=1

    # After the confirmation, not before: a declined run should leave nothing.
    mkdir -p "$LOGDIR"

    # Pathspec commit, never `git add -A`: the index is shared between concurrent
    # sessions, and a sweep once carried six unrelated files into someone else's
    # commit (CLAUDE.md, 21 Aug). bump-version.py already stages what it touches.
    # Idempotent, because `run` is RESUMABLE and this step is not naturally so.
    # bump-version.py moves the version relative to wherever it currently is, so
    # re-running it after a partial failure bumps AGAIN — 0.28.0 becomes 0.29.0
    # while CHANGELOG still says 0.28.0. That happened on 27 Aug 2026: the
    # version had already been bumped by hand, `run 0.28.0 --bump minor` bumped
    # on top of it, and committed the result under the message "bump to 0.28.0".
    # Skip the bump when the file already reads $V, and only commit if something
    # actually changed.
    #
    # `git diff --quiet HEAD --`, NOT `git diff --quiet --`. bump-version.py
    # STAGES what it touches (its own docstring says so), and plain `git diff`
    # compares the working tree to the INDEX — so against a staged bump it finds
    # no difference, takes the && arm, prints "version files already committed"
    # and commits nothing. The assertion on the next line then reads the
    # WORKING-TREE file, sees $V, and passes. Step green, bump uncommitted.
    #
    # Measured 31 Aug 2026 on 0.29.1: __init__.py read 0.29.1 while HEAD read
    # 0.29.0, and `git push origin main` shipped the un-bumped commit. Only a
    # later step failing for an unrelated reason stopped the tag landing on a
    # commit whose version was already immutable on PyPI. Same family as the
    # `cmd && ok "passed"` gate in CLAUDE.md: the success arm asserted a
    # conclusion the command never established.
    BUMP_CMD="{ [ \"\$(sed -n '$VERSION_REGEX' '$VERSION_FILE')\" = \"$V\" ] || ./scripts/bump-version.py $BUMP; }"
    BUMP_CMD="$BUMP_CMD && { git diff --quiet HEAD -- bristlenose/__init__.py bristlenose/data/bristlenose.1 desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj CHANGELOG.md README.md && echo 'version files already committed' || git commit -m \"bump to $V\" -- bristlenose/__init__.py bristlenose/data/bristlenose.1 desktop/Bristlenose/Bristlenose.xcodeproj/project.pbxproj CHANGELOG.md README.md; }"
    # $V and --bump are two sources for one number. `run 0.29.0 --bump minor`
    # from 0.27.0 writes 0.28.0, commits "bump to 0.29.0", tags v0.29.0 — and
    # the mismatch surfaces at release.yml's PyPI poll, i.e. AFTER twine has
    # consumed 0.28.0 immutably. Reconcile immediately after the bump.
    # SINGLE quotes around the regex in the EMITTED command. Interpolating
    # $VERSION_REGEX into a double-quoted string lets its own quotes close the
    # outer one, so sed received `s/^__version__` as its whole script and died
    # with "unterminated substitute pattern" — on every run, correct or not.
    # The reconciliation this line exists to perform has therefore never once
    # been performed.
    BUMP_CMD="$BUMP_CMD && [ \"\$(sed -n '$VERSION_REGEX' '$VERSION_FILE')\" = \"$V\" ]"
    # Assigned BEFORE the command strings below: TAG_CMD interpolates it at
    # build time, DISPATCH_CMD and CI_CMD at run time. It only needs RUNDIR.
    CI_SHA_FILE="$RUNDIR/ci-sha"
    # The verdict names a sha; the tag is the act. They must agree at the
    # MOMENT of tagging — resumes and concurrent sessions both move HEAD.
    TAG_CMD="_v=\$(verdict_tag_provenance); [ \"\$_v\" = ok ] || { echo \"refusing (\$_v): the tag must land on the exact commit strict CI validated — see $CI_SHA_FILE. If the new HEAD should ship: release.sh retry $V strict-ci\"; exit 1; }; git tag v$V && git push origin v$V"
    # --event workflow_dispatch is LOAD-BEARING.
    #
    # push-main (the step before) creates a ci.yml run on main from a `push`
    # event, where inputs is empty and macOS is therefore INFORMATIONAL.
    # strict-ci dispatches a second, strict run seconds later. `--limit 1`
    # selects by RECENCY, and push webhooks are not ordered against dispatch
    # API calls — so this gate could watch the non-strict run, go green with
    # every macOS cell red, and release the uploads. That is the 0.25.2 window
    # this step exists to close, reopened by the selector.
    #
    # Pinned to a sha too: 41 minutes of build sit between dispatch and watch,
    # and this repo is trunk-on-main with concurrent sessions. A push in that
    # window would otherwise become "the newest run" — a verdict about a
    # DIFFERENT commit. Empty id fails closed (measured: `gh run watch ""` → 1).
    #
    # WHICH sha is the whole fix. This was `CI_SHA=$(git rev-parse HEAD)`
    # evaluated HERE, before the loop — i.e. BEFORE the bump step commits. The
    # dispatch then ran against post-bump main while the selector filtered on
    # the pre-bump sha, so a fresh `run` matched nothing and failed closed ~45
    # minutes in, EVERY TIME. A resume recomputed it post-bump and passed,
    # which is worse than a consistent failure: it reads as a flaky gate.
    #
    # So the dispatch step WRITES the sha it dispatched, and the watch step
    # READS it. That also survives what a lazy $(git rev-parse HEAD) at watch
    # time would not — a resume in a new shell, and a concurrent session
    # committing during the 41 minutes.
    DISPATCH_CMD="git rev-parse HEAD > '$CI_SHA_FILE' && gh workflow run $WF_CI --ref main -f $WF_STRICT_INPUT=true"
    # env.SHA rather than interpolating into the jq program: one less quoting
    # level, and the sha never passes through a string the shell re-parses.
    CI_CMD="SHA=\$(cat '$CI_SHA_FILE' 2>/dev/null); [ -n \"\$SHA\" ] || { echo 'strict-ci recorded no dispatched sha — release.sh retry $V strict-ci'; exit 1; }; export SHA; _id=\$(gh run list --workflow=$WF_CI --event workflow_dispatch --branch main --limit 10 --json databaseId,headSha --jq '[.[]|select(.headSha==env.SHA)]|.[0].databaseId'); [ -n \"\$_id\" ] && [ \"\$_id\" != null ] && gh run watch \"\$_id\" --exit-status"

    # Count prior invocations BEFORE this one is appended (it was counted after,
    # and every run recorded one attempt too many — review, 5 Sep 2026).
    _attempt=$(grep -c '"step":"run","status":"started"' "$EVENTS" 2>/dev/null || true)
    _attempt=$(( ${_attempt:-0} + 1 ))
    ev_append run started "bump=$BUMP"
    # The board's inputs (after the prompt: a declined run must leave an EMPTY
    # dir for the EXIT trap's rmdir — test-release-sh pins it), written by the driver (docs/design-release-board.md
    # §1.2). Absolute sink path: a child's cwd is not ours. The step table is
    # snapshotted per run so the board reads THIS run's topology, and no seam
    # (RELEASE_STEPS_FILE) can feed it a synthetic one after the fact.
    export BN_RUN_ID="$V" BN_EVENT_SINK="$ROOT/$RUNDIR/bn-events.log"
    { echo "# steps.tbl v1"; run_steps; } > "$RUNDIR/steps.tbl" || die "could not snapshot the step table"
    sink_line_or_die run status=start attempt="$_attempt" proto=1 \
        || die "cannot write the event sink at $BN_EVENT_SINK"
    if [ "$WANT_BOARD" = 1 ]; then board_ensure "$V" || true; else board_link "$V" || true; fi
    write_context "$RUNDIR"
    # Idle sleep parks xcodebuild/notarytool/altool with no error — the
    # overnight run's quietest failure mode, and no env var converts machine
    # sleep into a loud failure. -i holds IDLE sleep only (a closed lid still
    # sleeps — warned at the probes); -w $$ ties the assertion to this driver,
    # so it dies with us and a killed run holds nothing open.
    command -v caffeinate >/dev/null 2>&1 && { caffeinate -i -w $$ & }
    while IFS='|' read -r id label kind est steptier cons cmd; do
        [ -z "$id" ] && continue
        # run is Tier 1; a Tier 2 promotion is a different act, not a longer run.
        [ -n "$steptier" ] && continue
        cmd="${cmd//__V__/$V}"; cmd="${cmd//__WF_CI__/$WF_CI}"; cmd="${cmd//__WF_STRICT__/$WF_STRICT_INPUT}"; cmd="${cmd//__WF_SNAP__/$WF_SNAP}"
        [ "$cmd" = "__BUMP__" ] && cmd="$BUMP_CMD"
        [ "$cmd" = "__TAG__" ] && cmd="$TAG_CMD"
        [ "$cmd" = "__DISPATCH__" ] && cmd="$DISPATCH_CMD"
        [ "$cmd" = "__CIWAIT__" ] && cmd="$CI_CMD"

        case " $SKIP " in *" $id "*)
            printf '  %b—%b %-26s %bskipped by --skip%b\n' "$D" "$N" "$label" "$D" "$N"
            ev_append "$id" skipped "--skip"; continue ;;
        esac
        prev="$(fold_status "$id")"
        if [ "$prev" = "ok" ]; then
            case "$kind" in
                soft|hard)
                    # A recorded success plus an absent probe is most often
                    # propagation lag, so give the probe a window HERE and only
                    # here — a cold probe (no recorded success) has nothing to
                    # wait for and stays instant.
                    BN_PROBE_WINDOW_S=180 probe_done "$id"; _pd=$?
                    case "$_pd" in
                        0) printf '  %b—%b %-26s %balready done in the world%b\n' "$D" "$N" "$label" "$D" "$N"
                           continue ;;
                        1) # THE LOG AND THE PROBE DISAGREE — STOP, DO NOT RE-RUN.
                           #
                           # This used to print "re-running" and do it. On
                           # 31 Aug 2026 that offered to re-upload a TestFlight
                           # build seconds after the upload had recorded
                           # "state VALID · confirmed present in App Store
                           # Connect" with a delivery id — a positive ASC read —
                           # because a later ASC read inside the propagation
                           # window came back empty. Apple refused the duplicate
                           # (ENTITY_ERROR.ATTRIBUTE.INVALID.DUPLICATE); the
                           # build number survived because the downstream system
                           # declined, not because this was right.
                           #
                           # Two readings of the same eventually-consistent
                           # system disagreed, and the newer one won. Recency is
                           # the wrong tie-break — provenance is. A confirmed
                           # delivery cannot be un-happened by a later empty
                           # read, and an empty read has a known benign cause.
                           #
                           # And the costs are asymmetric: believing the false
                           # negative spends a build number forever; believing
                           # the stale positive costs a re-check. On a soft or
                           # hard step the tie breaks toward the reversible
                           # option, which is to stop and let a human look.
                           #
                           # The probe above already re-read for the window
                           # before saying this, so reaching here means it
                           # stayed absent throughout — which is worth a human
                           # either way.
                           printf '\n  %b✗%b %s is recorded done, but the probe still cannot find it.\n' "$R" "$N" "$label"
                           printf '    Two readings disagree and one of them is a recorded success.\n'
                           printf '    Check the step log before re-running — a re-run here is not free:\n'
                           printf '      %s\n' "$RUNDIR/logs/$id.1.log"
                           printf '    If it really did not happen:  release.sh retry %s %s\n' "$V" "$id"
                           printf '    If it did and the world is slow:  release.sh run %s   (re-probes)\n\n' "$V"
                           exit 3 ;;
                        *) # 2 = no probe exists · 3 = the probe could not run.
                           # Both are "I do not know", and the only safe answer
                           # on an irreversible step is to stop and ask.
                           if [ "$_pd" = 3 ]; then
                               printf '\n  %b✗%b %s is recorded done and the probe could not reach the network.\n' "$R" "$N" "$label"
                               printf '    An unreachable probe is not an absent artefact. Retry when online, or:\n'
                           else
                               printf '\n  %b✗%b %s is recorded done and cannot be probed from here.\n' "$R" "$N" "$label"
                               printf '    Re-running would spend it again. Confirm by hand, then either\n'
                           fi
                           printf '    %brelease.sh run %s --bump %s%s --skip %s%b to move past it,\n' "$B" "$V" "$BUMP" "$SKIP_FLAGS" "$id" "$N"
                           printf '    or %brelease.sh retry %s %s%b to genuinely redo it.\n\n' "$B" "$V" "$id" "$N"
                           exit 3 ;;
                    esac
                    ;;
                *)
                    printf '  %b—%b %-26s %bskipped (done)%b\n' "$D" "$N" "$label" "$D" "$N"
                    continue
                    ;;
            esac
        elif [ "$prev" = "skipped" ]; then
            # fold_status returns `skipped`, and this branch did not exist — so a
            # skipped step fell through and EXECUTED on the next invocation. The
            # resume line printed after a later failure omitted the --skip flags,
            # so the documented flow (skip testflight, dmg fails, fix, re-run as
            # printed) re-spent the build number the skip existed to protect.
            #
            # Reversible steps just run: that is what a resume is for. An
            # irreversible one stops and makes the human say which they meant,
            # because both readings are defensible and only one is recoverable.
            case "$kind" in
                soft|hard)
                    printf '\n  %b✗%b %s was skipped by --skip on an earlier run.\n' "$R" "$N" "$label"
                    printf '    It is irreversible, so this will not decide for you:\n'
                    printf '      %brelease.sh run %s --bump %s%s%b   keep skipping it\n' "$B" "$V" "$BUMP" "$SKIP_FLAGS --skip $id" "$N"
                    printf '      %brelease.sh retry %s %s%b   run it after all\n\n' "$B" "$V" "$id" "$N"
                    exit 3 ;;
                *) : ;;   # reversible — fall through and run it
            esac
        elif [ "$prev" = "running" ] || [ "$prev" = "corrupt" ]; then
            printf '\n  %b✗%b %s was interrupted and its outcome is unrecorded.\n' "$R" "$N" "$label"
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
        sink_line_or_die step id="$id" attempt="$n" status=start \
            || die "cannot write the event sink at $BN_EVENT_SINK"
        t0=$SECONDS
        # REDIRECT, never pipe. $? is then the command's own status, not tail's.
        # release-log 0.27.0 #1: five runs reported exit 0 and three had failed.
        # Backgrounded + wait, NOT a foreground call: bash defers traps until the
        # current foreground command returns, so Ctrl-C during a 30-minute build
        # was queued for 30 minutes — the driver looked hung and the lock
        # outlived the signal. `wait` is interruptible; the handler kills $STEP_PID.
        #
        # < /dev/null is LOAD-BEARING: the loop's stdin IS the step table (the
        # heredoc feeding this while-read). A step command that reads stdin
        # therefore eats the remaining rows — ssh inside upload-dmg.sh did
        # exactly that on 28 Aug 2026, and tag + snap were silently never run
        # while the driver printed "every act is done". No step may read stdin;
        # the only interactive read (the confirmation) happens before the loop.
        eval "$cmd" > "$LOG" 2>&1 < /dev/null &
        STEP_PID=$!
        _start_heartbeat "$id" "$LOG"
        wait "$STEP_PID"
        rc=$?
        _stop_heartbeat
        STEP_PID=""
        el=$(( SECONDS - t0 ))

        sink_line_or_die step id="$id" attempt="$n" status=end rc="$rc" elapsed="$el" \
            || die "cannot write the event sink at $BN_EVENT_SINK"
        if [ "$rc" -eq 0 ]; then
            ev_append "$id" ok "${el}s"
            printf '  %b✓%b %-26s %b%ss%b\n\n' "$G" "$N" "$label" "$D" "$el" "$N"
        else
            ev_append "$id" fail "exit $rc"
            printf '  %b✗%b %-26s %bexit %s%b\n' "$R" "$N" "$label" "$R" "$rc" "$N"
            # tr: rsync --progress writes carriage returns, so a raw tail shows
            # the START of one enormous line and a healthy transfer reads frozen.
            tr '\r' '\n' < "$LOG" | grep -vE '^[[:space:]]*$' | tail -12 | sed 's/^/      /'
            printf '\n  %blog%b %s\n' "$D" "$N" "$LOG"
            # SKIP_FLAGS, or the printed resume silently drops the skips and the
            # next invocation re-performs what they were protecting.
            printf '  %bfix, then%b release.sh run %s --bump %s%s   %b(resumes here)%b\n\n' \
                "$B" "$N" "$V" "$BUMP" "$SKIP_FLAGS" "$D" "$N"
            exit 1
        fi
    done <<EOF
$(run_steps)
EOF

    # A consumed table must not report done — see verdict_complete.
    _missing="$(run_steps | verdict_complete)"
    if [ -n "$_missing" ]; then
        printf '\n  %b✗ the step loop ended with steps never reached:%b %s\n' \
            "$R" "$N" "$(printf '%s' "$_missing" | tr '\n' ' ')"
        printf '    No event exists for them — the table was consumed, not completed.\n'
        printf '    This is a driver defect, not a step failure; the acts above DID happen.\n'
        printf '    Resume: %brelease.sh run %s --bump %s%s%b\n\n' "$B" "$V" "$BUMP" "$SKIP_FLAGS" "$N"
        exit 1
    fi

    ev_append run completed ""
    # 75 = EX_TEMPFAIL: the acts are done, verification is pending. NOT 0.
    #
    # `verify` used to be the last step here and it could never pass: release.yml
    # runs the full CI matrix before publish, so PyPI, the GitHub Release,
    # Homebrew and Snap are all legitimately absent for ~40 minutes after the tag
    # lands — and the step was budgeted 1m. A run that always ends red teaches
    # you to ignore its verdict, which is the one thing it must not do.
    #
    # So run is a launcher, not a foreground poll. It reports what it DID; what
    # LANDED is a separate act, tomorrow morning or in half an hour.
    printf '  %b✓ every act is done.%b PyPI publishes when the tag run goes green.\n\n' "$G" "$N"
    printf '    %bgh run watch --exit-status $(gh run list --workflow=$WF_RELEASE --limit 1 --json databaseId --jq ".[0].databaseId")%b\n' "$D" "$N"
    printf '    %b./scripts/release.sh verify %s%b   %bthen, and it is not instant%b\n\n' "$B" "$V" "$N" "$D" "$N"
    return 75
}

cmd_retry() {
    # Both spellings work: `retry <X.Y.Z> <step>` and, when only one run
    # exists under .release/, just `retry <step>` — narrated, never guessed
    # between candidates.
    if [ "$(verdict_version "${1-}")" = ok ]; then
        V="$1"; STEP="${2-}"
    else
        STEP="${1-}"
        V="$(infer_rundir)" || die "which release? $(ls -d .release/*/ 2>/dev/null | tr '\n' ' ' || echo 'no runs')— release.sh retry <X.Y.Z> <step>"
        printf '  %b%s%b %b— the only run under .release/%b\n' "$B" "$V" "$N" "$D" "$N"
    fi
    [ "$(verdict_version "$V")" = ok ] || die "usage: release.sh retry [<X.Y.Z>] <step>"
    [ -n "$STEP" ] || die "usage: release.sh retry [<X.Y.Z>] <step>"
    # `retry <V> flibbertigibbet` used to print "reset to pending" and exit 0.
    run_steps | awk -F'|' -v s="$STEP" '$1==s{f=1} END{exit !f}' \
        || die "no such step '$STEP' (try: $(run_steps | awk -F'|' 'NF>1{printf "%s ", $1}'))"
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
    recover) shift; cmd_recover "$@" ;;
    -h|--help|help) usage ;;
    *)       die "unknown command: $1 (try: plan run verify status abandon retry recover)" ;;
esac
