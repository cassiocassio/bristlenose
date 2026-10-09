#!/usr/bin/env bash
# test-channel-scenarios.sh — feed the release machine's follower channels and
# holds a corpus of unlikely-but-possible worlds, and check each answer.
#
# The corpus is scripts/channel-scenarios.txt; its header is the format. This
# file only builds each world and reads the machine's verdict on it.
#
# HOW A WORLD IS BUILT
#
# A sandbox git repo holding copies of release.sh, verify-channels.sh and
# project.conf, a second sandbox repo standing in for the website, and fakes for
# `gh` and `curl` on PATH. curl answers every lockstep channel as live, so the
# only things that vary are the ones a scenario names. gh answers from files the
# runner writes, and counts its calls so a scenario can change the world
# between two reads (flip_after). Then the REAL `release.sh verify` runs, under a
# watchdog, in its own process group so a hung fake can be killed with its parent.
#
# WHY "known=" IS A RATCHET, NOT AN EXCUSE
#
# A scenario states the correct answer even when the code gets it wrong today.
# Tagged known=<issue> it reports KNOWN and the suite stays green. When a fix
# makes it pass, the suite goes RED ("FIXED, remove known=") until the tag is
# deleted, so the record of what is broken cannot drift from the code.
#
# This is a test, not a gate: nothing here runs during a release, so adding a
# scenario never narrows the path a release must take.
#
# Usage: scripts/test-channel-scenarios.sh [scenario-id-substring]

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CORPUS="$ROOT/scripts/channel-scenarios.txt"
FILTER="${1:-}"

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
[ -t 1 ] || { G=""; Y=""; R=""; D=""; N=""; }

WORK=$(mktemp -d "${TMPDIR:-/tmp}/bn-scenarios.XXXXXX")
trap 'rm -rf "$WORK"' EXIT INT TERM

# ── the fakes ───────────────────────────────────────────────────────────────
mkdir -p "$WORK/bin"
cat > "$WORK/bin/curl" <<'CURL'
#!/bin/sh
# Every lockstep channel answers "live at $BN_V". Nothing here varies by scenario.
for a in "$@"; do case "$a" in
  *changelog*) echo "$BN_V released"; exit 0 ;;
  *snapcraft*) echo '{"channel-map":[{"channel":{"name":"edge"},"version":"'"$BN_V"'"}]}'; exit 0 ;;
  *copr*) echo '{"items":[{"state":"succeeded","source_package":{"version":"'"$BN_V"'-1"}}]}'; exit 0 ;;
  *.dmg.sha256) printf '%s  Bristlenose-%s.dmg\n' "$(printf '%064d' 0 | tr 0 a)" "$BN_V"; exit 0 ;;
  *dmg*) printf 'HTTP/2 302\nlocation: https://x/Bristlenose-%s.dmg\n' "$BN_V"; exit 0 ;;
  *Formula/*) echo "url \"https://x/bristlenose-$BN_V.tar.gz\""; exit 0 ;;
  *pypi*) case " $* " in *" -w "*) printf '200' ;; esac; exit 0 ;;
esac; done
exit 0
CURL
cat > "$WORK/bin/gh" <<'GH'
#!/bin/sh
# Answers from $BN_WORLD. Each call reads the world as it stands, then counts
# itself; after flip_after calls the *_after files take over.
W="$BN_WORLD"
# Only winget's reads (api, pr) move the world's clock. The github row's
# `gh release view` runs first, and counting it flipped the world before
# winget ever looked, so the race scenario passed without racing.
n=$(cat "$W/calls" 2>/dev/null || echo 0)
case "$1" in api|pr) n=$((n+1)); echo "$n" > "$W/calls"; echo "$1" >> "$W/order" ;; esac
sfx=""; f=$(cat "$W/flip_after" 2>/dev/null || echo 0)
[ "$f" -gt 0 ] && [ "$n" -gt "$f" ] && sfx="_after"
case "$1" in
  release) echo "v$BN_V"; exit 0 ;;
  api)
    s=$(cat "$W/served$sfx" 2>/dev/null || cat "$W/served")
    case "$s" in
      404)   echo '{"message":"Not Found","status":"404"}'; echo 'gh: Not Found (HTTP 404)' >&2; exit 1 ;;
      403)   echo 'gh: API rate limit exceeded for user (HTTP 403)' >&2; exit 1 ;;
      FAIL)  echo 'error connecting to api.github.com' >&2; exit 1 ;;
      HANG)  sleep 600; exit 1 ;;
      SLOW:*) d=${s#SLOW:}; sleep "${d%%:*}"; printf '%s\n' ${d#*:}; exit 0 ;;
      *)     printf '%s\n' $s; exit 0 ;;
    esac ;;
  pr)
    p=$(cat "$W/prs$sfx.json" 2>/dev/null || cat "$W/prs.json")
    case "$p" in
      FAIL) echo 'gh: GraphQL: something went wrong' >&2; exit 1 ;;
      HANG) sleep 600; exit 1 ;;
      *)    printf '%s' "$p"; exit 0 ;;
    esac ;;
esac
echo "v$BN_V"
GH
chmod +x "$WORK/bin/curl" "$WORK/bin/gh"

# ── corpus parsing ──────────────────────────────────────────────────────────
# Blocks of key=value separated by blank lines. No associative arrays: macOS's
# /bin/bash is 3.2, and the other release suites run there too.
BLOCK=""
scenarios=()
_block=""
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in \#*) continue ;; esac
    if [ -z "${line// /}" ]; then
        [ -n "$_block" ] && scenarios+=("$_block"); _block=""
    else
        _block+="$line"$'\n'
    fi
done < "$CORPUS"
[ -n "$_block" ] && scenarios+=("$_block")

load() { BLOCK="$1"; }
get() { # get <key> [default] — first value for <key> in the current block
    local l
    while IFS= read -r l; do
        case "$l" in "$1="*) printf '%s' "${l#*=}"; return ;; esac
    done <<<"$BLOCK"
    printf '%s' "${2-}"
}
keys() { printf '%s\n' "$BLOCK" | sed -n 's/^\([^=]*\)=.*/\1/p'; }

render_prs() { # render_prs <spec> <title-template> → JSON or FAIL/HANG
    case "$1" in FAIL|HANG) printf '%s' "$1"; return ;; esac
    SPEC="$1" TITLE="$2" python3 - <<'PY'
import json, os
from datetime import datetime, timedelta, timezone
spec, title = os.environ["SPEC"], os.environ["TITLE"]
out = []
if spec not in ("", "none"):
    for i, item in enumerate(spec.split(",")):
        v, _, age = item.partition("@")
        t = datetime.now(timezone.utc) - timedelta(hours=float(age or 0))
        out.append({"number": 449000 + i, "title": title.replace("{v}", v),
                    "createdAt": t.strftime("%Y-%m-%dT%H:%M:%SZ")})
print(json.dumps(out))
PY
}

new_repo() { # new_repo <dir> — a repo with one commit on main
    mkdir -p "$1" && git -C "$1" init -q -b main \
      && git -C "$1" -c user.email=s@t -c user.name=s commit -q --allow-empty -m base
}

# run_watched <seconds> <cmd…> — run in its own process group; kill the group
# if it overruns. Prints the output; returns the exit code, or 124 on timeout.
run_watched() {
    local secs="$1"; shift
    local out="$WORK/out.$$" t=0
    perl -e 'setpgrp(0,0); exec @ARGV' "$@" > "$out" 2>&1 &
    local pid=$!
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$t" -ge $((secs * 5)) ]; then
            kill -TERM -- "-$pid" 2>/dev/null; sleep 0.2; kill -KILL -- "-$pid" 2>/dev/null
            wait "$pid" 2>/dev/null; cat "$out"; return 124
        fi
        sleep 0.2; t=$((t+1))
    done
    wait "$pid"; local rc=$?
    cat "$out"; return "$rc"
}

# ── one scenario ────────────────────────────────────────────────────────────
PASS=0; FAILN=0; KNOWN=0; FIXED=0
run_one() {
    local id v sb site world out rc start secs want got problems=() b
    id=$(get id); v=$(get version 0.36.0)
    sb="$WORK/$id/repo"; site="$WORK/$id/site"; world="$WORK/$id/world"
    new_repo "$sb" >/dev/null; new_repo "$site" >/dev/null; mkdir -p "$world" "$sb/scripts" "$sb/bristlenose"
    cp "$ROOT/scripts/release.sh" "$ROOT/scripts/verify-channels.sh" "$ROOT/scripts/project.conf" "$sb/scripts/"
    printf '__version__ = "%s"\n' "$v" > "$sb/bristlenose/__init__.py"
    case "$(get budget)" in "") ;; *)
        sed -i.bak "s/^WINGET_BUDGET_HOURS=.*/WINGET_BUDGET_HOURS=$(get budget)/" "$sb/scripts/project.conf" ;; esac

    # the world
    get served 404 > "$world/served"
    [ -n "$(get served_after)" ] && get served_after > "$world/served_after"
    local title; title=$(get title "Add version: Bristlenose.Bristlenose version {v}")
    render_prs "$(get prs none)" "$title" > "$world/prs.json"
    [ -n "$(get prs_after)" ] && render_prs "$(get prs_after)" "$title" > "$world/prs_after.json"
    get flip_after 0 > "$world/flip_after"
    get publish ok > "$world/publish"

    # the holds: branches off main; a landed one is a commit already merged
    for b in $(get holds); do
        git -C "$sb" branch "$b" 2>/dev/null || problems+=("could not create branch $b")
    done
    for b in $(get landed); do
        git -C "$sb" branch -D "$b" >/dev/null 2>&1
        git -C "$sb" -c user.email=s@t -c user.name=s commit -q --allow-empty -m "land $b"
        git -C "$sb" branch "$b"
    done
    for b in $(get site_holds); do git -C "$site" branch "$b"; done
    [ "$(get site)" = missing ] && site="$WORK/$id/no-such-site"

    secs=$(get expect.seconds 30)
    start=$(date +%s)
    if [ -n "$(get results)" ]; then
        # Skip the probes: hand print_holds a results file directly.
        local rf="$WORK/$id/results" item
        : > "$rf"
        for item in $(get results); do printf '%s\n' "$item" | tr ':' '\t' >> "$rf"; done
        out=$(cd "$sb" && WEBSITE_REPO="$site" run_watched "$secs" bash -c \
              'RELEASE_LIB=1 . scripts/release.sh; print_holds "$1"' _ "$rf"); rc=$?
        rc_expected_skip=1
    else
        out=$(cd "$sb" && PATH="$WORK/bin:$PATH" BN_V="$v" BN_WORLD="$world" BN_WEBSITE_REPO="$site" \
              run_watched "$secs" bash scripts/release.sh verify "$v"); rc=$?
        rc_expected_skip=0
    fi
    local took=$(( $(date +%s) - start ))
    out=$(printf '%s' "$out" | sed 's/\x1b\[[0-9;]*m//g')

    # the checks
    if [ "$rc" = 124 ]; then problems+=("HUNG: killed after ${secs}s")
    elif [ "$took" -gt "$secs" ]; then problems+=("took ${took}s, budget ${secs}s"); fi
    want=$(get expect.winget)
    if [ -n "$want" ]; then
        got=$(printf '%s\n' "$out" | sed -n 's/^  following: winget \([a-z]*\).*/\1/p' | head -1)
        [ "$got" = "$want" ] || problems+=("winget: want $want, got ${got:-<none>}")
    fi
    want=$(get expect.exit)
    if [ -n "$want" ] && [ "$rc_expected_skip" = 0 ] && [ "$rc" != 124 ]; then
        [ "$rc" = "$want" ] || problems+=("exit: want $want, got $rc")
    fi
    local k
    for k in $(keys); do
        case "$k" in expect.hold.*) ;; *) continue ;; esac
        b="${k#expect.hold.}"; want=$(get "$k")
        got=$(printf '%s\n' "$out" | awk -v b="$b" '$2==b {print $1; exit}')
        case "$got" in "?name") got=badname ;; "?") got=unknown ;; esac
        [ "$got" = "$want" ] || problems+=("hold $b: want $want, got ${got:-<not listed>}")
    done
    want=$(get expect.out)
    if [ -n "$want" ]; then
        case "$out" in *"$want"*) ;; *) problems+=("output lacks: $want") ;; esac
    fi

    local known; known=$(get known)
    if [ "${#problems[@]}" -eq 0 ]; then
        if [ -n "$known" ]; then
            FIXED=$((FIXED+1)); printf '  %bFIXED%b  %-28s %s — remove known=%s\n' "$R" "$N" "$id" "$(get about)" "$known"
        else
            PASS=$((PASS+1)); printf '  %bpass%b   %-28s %s%s%s\n' "$G" "$N" "$id" "$D" "$(get about)" "$N"
        fi
    elif [ -n "$known" ]; then
        KNOWN=$((KNOWN+1)); printf '  %bKNOWN%b  %-28s [%s] %s\n' "$Y" "$N" "$id" "$known" "${problems[*]}"
    else
        FAILN=$((FAILN+1)); printf '  %bFAIL%b   %-28s %s\n' "$R" "$N" "$id" "$(get about)"
        printf '           %s\n' "${problems[@]}"
        [ -n "${BN_SCENARIO_VERBOSE:-}" ] && printf '%s\n' "$out" | sed 's/^/           | /'
    fi
}

printf '\nchannel scenarios · %s\n\n' "$(basename "$CORPUS")"
for blk in "${scenarios[@]}"; do
    load "$blk"
    [ -n "$(get id)" ] || continue
    case "$(get id)" in *"$FILTER"*) ;; *) continue ;; esac
    run_one
done
printf '\n  %s passed · %s known · %s failed · %s fixed-but-still-tagged\n\n' "$PASS" "$KNOWN" "$FAILN" "$FIXED"
[ "$FAILN" -eq 0 ] && [ "$FIXED" -eq 0 ]
