#!/usr/bin/env bash
# test-release-e2e.sh — drive the REAL cmd_run loop end to end, against fake steps.
#
# WHY THIS EXISTS
#
# Every other suite stops at validation, confirmation, or a stranded step. The
# loop itself — event appends, elapsed times, the skip branch, the probe branch,
# the failure tail, resume — had never executed with any command, real or fake.
# A reviewer called that the largest coverage gap, and it is: that loop is what
# performs irreversible acts.
#
# The seam is RELEASE_STEPS_FILE (scripts/release.sh). It replaces the step table
# with harmless commands, so the loop runs for real while nothing is published.
# probe_done is overridden per scenario by a stub `git`/`curl` on PATH, because
# overriding the function would test a different function than the one that ships.
#
# These are deliberately adversarial. The happy path is one of sixteen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$(dirname "$0")/test-lib.sh"

REL="$ROOT/scripts/release.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

# steps <<'EOF' … EOF  — write a fake step table
steps() { cat > "$WORK/steps.tbl"; }

# stub <name> <body>  — a fake binary earlier on PATH than the real one
stub() {
    mkdir -p "$WORK/bin"
    printf '#!/bin/sh\n%s\n' "$2" > "$WORK/bin/$1"
    chmod +x "$WORK/bin/$1"
}

# drive <version> [args…]  — run the real driver in an isolated .release root
drive() {
    local v="$1"; shift
    ( cd "$WORK/repo" \
      && PATH="$WORK/bin:$PATH" RELEASE_STEPS_FILE="$WORK/steps.tbl" \
         bash "$WORK/repo/scripts/release.sh" run "$v" --bump patch --yes "$@" ) >"$WORK/out" 2>&1
    echo $?
}

events() { cat "$WORK/repo/.release/$1/events.jsonl" 2>/dev/null; }
status_of() { events "$1" | grep "\"step\":\"$2\"" | tail -1 | sed 's/.*"status":"\([^"]*\)".*/\1/'; }
ran() { events "$1" | grep -qc "\"step\":\"$2\",\"status\":\"running\"" 2>/dev/null; }

fresh() {
    rm -rf "$WORK/repo" "$WORK/bin"
    mkdir -p "$WORK/repo/scripts" "$WORK/bin"
    # release.sh does `ROOT=$(dirname $0)/..; cd $ROOT` — it always operates on
    # ITS OWN repo, which is right in production and means a harness cannot
    # isolate it by cd-ing. So give the sandbox its own copy: ROOT then resolves
    # to $WORK/repo and .release/ lands there, not in the real tree.
    cp "$REL" "$WORK/repo/scripts/release.sh"
    # release.sh sources project.conf; the sandbox needs it too, or every run
    # dies before the loop and 28 assertions fail for one missing file.
    cp "$ROOT/scripts/project.conf" "$WORK/repo/scripts/project.conf"
    ( cd "$WORK/repo" && git init -q . && git commit -q --allow-empty -m init ) 2>/dev/null
}

# ---------------------------------------------------------------------------

head_ "1 · happy path — every step succeeds"
fresh
steps <<'EOF'
one|first|plain|1m|||true
two|second|plain|1m|||true
three|third|soft|1m||spends something|true
EOF
rc=$(drive 1.0.0)
eq "exits 75 (acts done, verification pending)" 75 "$rc"
eq "step one ok"   ok "$(status_of 1.0.0 one)"
eq "step three ok" ok "$(status_of 1.0.0 three)"
grep -q '"step":"run","status":"completed"' "$WORK/repo/.release/1.0.0/events.jsonl" \
    && ok "run records a terminus" || bad "no terminus event"

head_ "2 · a step fails mid-table — later steps must not run"
fresh
steps <<'EOF'
one|first|plain|1m|||true
two|second|plain|1m|||sh -c 'echo boom >&2; exit 7'
three|third|soft|1m||spends something|true
EOF
rc=$(drive 1.0.0)
eq "exits 1"              1  "$rc"
eq "the failing step is fail" fail "$(status_of 1.0.0 two)"
eq "the step after it never started" "" "$(status_of 1.0.0 three)"
grep -q 'exit 7' "$WORK/out" && ok "the real exit code is reported" || bad "exit code lost"
grep -q 'boom' "$WORK/out" && ok "the log tail is shown" || bad "no tail"

head_ "3 · resume — done steps skip, the failure re-runs"
steps <<'EOF'
one|first|plain|1m|||true
two|second|plain|1m|||true
three|third|soft|1m||spends something|true
EOF
rc=$(drive 1.0.0)
eq "resume exits 75" 75 "$rc"
grep -q 'skipped (done)' "$WORK/out" && ok "completed steps are skipped" || bad "did not skip"
eq "the previously-failed step is now ok" ok "$(status_of 1.0.0 two)"

head_ "4 · stranded step — never auto-advanced"
fresh
steps <<'EOF'
one|first|plain|1m|||true
two|second|soft|1m||spends something|true
EOF
mkdir -p "$WORK/repo/.release/1.0.0/logs"
printf '{"ts":"x","run":"1.0.0","step":"one","status":"ok","detail":"1s"}\n' \
     > "$WORK/repo/.release/1.0.0/events.jsonl"
printf '{"ts":"x","run":"1.0.0","step":"two","status":"running","detail":"attempt 1"}\n' \
    >> "$WORK/repo/.release/1.0.0/events.jsonl"
rc=$(drive 1.0.0)
eq "exits 3" 3 "$rc"
grep -q 'interrupted and its outcome is unrecorded' "$WORK/out" \
    && ok "names the stranded step" || bad "did not name it"

head_ "5 · a CORRUPT event line takes the stranded path, it does not execute"
fresh
steps <<'EOF'
one|first|plain|1m|||sh -c 'echo SHOULD-NOT-RUN > ran.txt'
EOF
mkdir -p "$WORK/repo/.release/1.0.0/logs"
printf '{"ts":"x","run":"1.0.0","step":"one","status":"o\n' \
     > "$WORK/repo/.release/1.0.0/events.jsonl"
rc=$(drive 1.0.0)
eq "exits 3 on a truncated write" 3 "$rc"
[ -f "$WORK/repo/ran.txt" ] && bad "THE STEP EXECUTED on a corrupt log" \
                            || ok "a corrupt line does not execute the step"

head_ "6 · the lock — a second driver refuses"
fresh
steps <<'EOF'
one|first|plain|1m|||true
EOF
mkdir -p "$WORK/repo/.release/1.0.0/.lock"; echo 99999 > "$WORK/repo/.release/1.0.0/.lock/pid"
rc=$(drive 1.0.0)
eq "exits 2 when the lock is held" 2 "$rc"
grep -q 'another run holds' "$WORK/out" && ok "says who holds it" || bad "unhelpful lock message"
rm -rf "$WORK/repo/.release/1.0.0/.lock"

head_ "7 · irreversible, recorded ok, NO probe — must stop, not re-run"
fresh
steps <<'EOF'
tf|upload to TestFlight|soft|1m||spends a build number|sh -c 'echo RERAN >> ran.txt'
EOF
mkdir -p "$WORK/repo/.release/1.0.0/logs"
printf '{"ts":"x","run":"1.0.0","step":"tf","status":"ok","detail":"6m"}\n' \
     > "$WORK/repo/.release/1.0.0/events.jsonl"
rc=$(drive 1.0.0)
eq "exits 3 rather than guessing" 3 "$rc"
[ -f "$WORK/repo/ran.txt" ] && bad "RE-SPENT an irreversible step with no probe" \
                            || ok "refuses to re-run an unprobeable irreversible step"
grep -q 'cannot be probed from here' "$WORK/out" && ok "explains why" || bad "no explanation"

head_ "8 · --skip moves past it, and records that it did"
rc=$(drive 1.0.0 --skip tf)
eq "--skip lets the run proceed" 75 "$rc"
eq "the skip is recorded, not silent" skipped "$(status_of 1.0.0 tf)"

head_ "8a · a resume must not silently re-run what --skip protected (F38)"
# The bug: fold_status returns `skipped`, the resume branch handled only ok and
# running|corrupt, so `skipped` fell through and EXECUTED — re-spending the
# build number on the one step whose declared cost is that it cannot be unspent.
fresh
steps <<'EOF'
a|first|plain|1m|||true
tf|upload tf|soft|1m||SOFT: spends a build number|sh -c 'echo SPENT >> spent.txt'
b|second|plain|1m|||true
EOF
rc=$(drive 1.0.0 --skip tf)
eq "the skipping run completes" 75 "$rc"
rc=$(drive 1.0.0)
eq "the bare resume refuses rather than spending it" 3 "$rc"
[ -f "$WORK/repo/spent.txt" ] && bad "RE-SPENT a step that --skip had protected" \
                              || ok "the irreversible step was not re-run"
grep -q 'keep skipping it' "$WORK/out" && ok "offers both readings explicitly" || bad "no guidance"
rc=$(drive 1.0.0 --skip tf)
eq "re-skipping proceeds" 75 "$rc"
[ -f "$WORK/repo/spent.txt" ] && bad "spent it under --skip" || ok "still not spent"

head_ "8b · a skipped REVERSIBLE step just runs on resume"
fresh
steps <<'EOF'
r|reversible|plain|1m|||sh -c 'echo RAN >> ran.txt'
EOF
rc=$(drive 1.0.0 --skip r)
eq "skipped first time" 75 "$rc"
[ -f "$WORK/repo/ran.txt" ] && bad "ran despite --skip" || ok "not run when skipped"
rc=$(drive 1.0.0)
eq "resume proceeds" 75 "$rc"
[ -f "$WORK/repo/ran.txt" ] && ok "a reversible skip is not sticky" || bad "did not run on resume"

head_ "8c · the resume line a failure prints carries the skips it was given"
fresh
steps <<'EOF'
tf|upload tf|soft|1m||SOFT|true
boom|fails|plain|1m|||false
EOF
rc=$(drive 1.0.0 --skip tf)
eq "fails at boom" 1 "$rc"
grep -q -- '--bump patch --skip tf' "$WORK/out" \
    && ok "the printed resume keeps --skip tf" \
    || bad "printed a resume that would re-spend tf: $(grep -o 'release.sh run.*' "$WORK/out" | head -1)"

head_ "8d · --skip on a step that does not exist is refused"
fresh
steps <<'EOF'
a|first|plain|1m|||true
EOF
rc=$(drive 1.0.0 --skip flibbertigibbet)
eq "refuses an unknown step id" 2 "$rc"
grep -q "no such step" "$WORK/out" && ok "names the valid ids" || bad "silent"

head_ "9 · a probe that says DONE skips; one that says ABSENT re-runs"
fresh
steps <<'EOF'
tag|tag + push|hard|1m||THIS PUBLISHES|sh -c 'echo RERAN >> ran.txt'
EOF
mkdir -p "$WORK/repo/.release/1.0.0/logs"
printf '{"ts":"x","run":"1.0.0","step":"tag","status":"ok","detail":"2s"}\n' \
     > "$WORK/repo/.release/1.0.0/events.jsonl"
stub git 'case "$*" in *ls-remote*) echo "abc123	refs/tags/v1.0.0" ;; *) exit 0 ;; esac'
rc=$(drive 1.0.0)
[ -f "$WORK/repo/ran.txt" ] && bad "re-ran a step the world says is done" \
                            || ok "probe says done -> skipped"
stub git 'case "$*" in *ls-remote*) exit 0 ;; *) exit 0 ;; esac'   # empty output = absent
rc=$(drive 1.0.0)
[ -f "$WORK/repo/ran.txt" ] && ok "probe says absent -> re-ran" \
                            || bad "did not re-run when the world says absent"

head_ "9a · an UNREACHABLE probe must not read as absent (F41)"
# `git ls-remote | grep -q .` gave 1 for both "no such tag" and "no network".
# The caller answers 1 by re-running — so a blip re-pushed a tag, or re-published
# 644 MB. Tri-state is the rule this whole chain is built on; this was the one
# place where breaking it costs something irreversible.
fresh
steps <<'EOF'
tag|tag + push|hard|1m||THIS PUBLISHES|sh -c 'echo RERAN >> ran.txt'
EOF
mkdir -p "$WORK/repo/.release/1.0.0/logs"
printf '{"ts":"x","run":"1.0.0","step":"tag","status":"ok","detail":"2s"}\n' \
     > "$WORK/repo/.release/1.0.0/events.jsonl"
# ls-remote fails the way an offline remote fails: non-zero, no output.
stub git 'case "$*" in *ls-remote*) exit 128 ;; *) exit 0 ;; esac'
rc=$(drive 1.0.0)
eq "an unreachable probe stops the run" 3 "$rc"
[ -f "$WORK/repo/ran.txt" ] && bad "RE-RAN an irreversible step on a network failure" \
                            || ok "did not re-run on an unreachable probe"
grep -q 'could not reach the network' "$WORK/out" \
    && ok "and says so, rather than 'the world disagrees'" || bad "wrong diagnosis"

head_ "10 · a command containing quotes, semicolons and a pipe"
fresh
steps <<'EOF'
q|quoting|plain|1m|||sh -c 'printf "a;b|c\"d\n" > out.txt'
EOF
rc=$(drive 1.0.0)
eq "survives shell metacharacters" 75 "$rc"
grep -q 'a;b|c"d' "$WORK/repo/out.txt" && ok "the command ran verbatim" || bad "mangled"

head_ "11 · carriage-return output (the rsync shape) is legible in the tail"
fresh
steps <<'EOF'
cr|progress|plain|1m|||sh -c 'printf "1%%\r50%%\r99%%\rboom\n" >&2; exit 4'
EOF
rc=$(drive 1.0.0)
eq "fails" 1 "$rc"
grep -q '^      boom$' "$WORK/out" && ok "CRs became newlines; the last line is visible" \
                                  || bad "tail unreadable — tr not applied"

head_ "12 · a step id that is a PREFIX of another must not collide"
fresh
steps <<'EOF'
snap|snap edge|plain|1m|||true
snap-stable|snap stable|plain|1m|||true
EOF
rc=$(drive 1.0.0)
eq "both run" 75 "$rc"
eq "snap ok"        ok "$(status_of 1.0.0 snap)"
eq "snap-stable ok" ok "$(status_of 1.0.0 snap-stable)"

head_ "13 · huge step output does not break the tail or the log"
fresh
steps <<'EOF'
big|noisy|plain|1m|||sh -c 'i=0; while [ $i -lt 5000 ]; do echo "line $i"; i=$((i+1)); done; exit 3'
EOF
rc=$(drive 1.0.0)
eq "fails cleanly on 5000 lines" 1 "$rc"
n=$(grep -c '^      line ' "$WORK/out" || true)
[ "$n" -le 12 ] && ok "the tail is bounded ($n lines)" || bad "tail unbounded: $n lines"

head_ "14 · an empty events file is not a completed run"
fresh
steps <<'EOF'
one|first|plain|1m|||true
EOF
mkdir -p "$WORK/repo/.release/1.0.0/logs"; : > "$WORK/repo/.release/1.0.0/events.jsonl"
rc=$(drive 1.0.0)
eq "an empty log means everything is pending" 75 "$rc"
eq "the step actually ran" ok "$(status_of 1.0.0 one)"

head_ "15 · a step that writes NOTHING still gets a terminus"
fresh
steps <<'EOF'
silent|says nothing|plain|1m|||true
EOF
rc=$(drive 1.0.0)
eq "silent success is still recorded" ok "$(status_of 1.0.0 silent)"

head_ "16 · SIGTERM mid-run releases the lock and stops"
fresh
steps <<'EOF'
slow|long step|plain|1m|||sleep 30
EOF
# exec, so $! is the DRIVER and not the subshell wrapping it. Without exec,
# kill -TERM reaps the subshell and leaves release.sh running as an orphan —
# which is a harness artefact, but also a true statement about process trees
# worth encoding rather than tripping over twice.
( cd "$WORK/repo" && PATH="$WORK/bin:$PATH" RELEASE_STEPS_FILE="$WORK/steps.tbl" \
    exec bash "$WORK/repo/scripts/release.sh" run 1.0.0 --bump patch --yes >/dev/null 2>&1 ) &
DP=$!
sleep 2
kill -TERM $DP 2>/dev/null; wait $DP 2>/dev/null
[ -d "$WORK/repo/.release/1.0.0/.lock" ] && bad "the lock survived SIGTERM" \
                                         || ok "the lock is released on SIGTERM"
eq "the interrupted step is left running, not ok" running "$(status_of 1.0.0 slow)"
# Scoped to THIS run's sandbox, not the machine: `pgrep -f "sleep 30"` matches
# any such process anywhere, including leftovers from an earlier failing run of
# this suite — a test that fails because of its own history.
sleep 1
if pgrep -f "$WORK/steps.tbl" >/dev/null 2>&1; then
    bad "a child of this run survived the driver"
else
    ok "no orphaned child from this run"
fi

head_ "17 · the strict-CI gate filters on the POST-BUMP sha (F39)"
# The regression: CI_SHA was captured before the loop, so the dispatch ran
# against post-bump main while the watcher filtered on the pre-bump sha —
# a fresh run failed closed ~45 minutes in, every time.
fresh
steps <<'EOF'
bump|bump + commit|plain|1m|||git commit -q --allow-empty -m bumped
strict-ci|dispatch strict CI|plain|1m|||__DISPATCH__
ci-green|GATE strict CI green|gate|1m|||__CIWAIT__
EOF
# The stub records what the selector actually filtered on. CI_CMD exports SHA
# for jq's env.SHA, so the stub can read the same value jq would.
stub gh 'case "$1 $2" in
  "run list") printf "%s" "$SHA" > "$PWD/filtered-on" ; echo 12345 ;;
  "run watch") exit 0 ;;
  *) exit 0 ;;
esac'
rc=$(drive 1.0.0)
eq "the run completes" 75 "$rc"
_post=$( cd "$WORK/repo" && git rev-parse HEAD )
eq "the recorded sha is post-bump HEAD" "$_post" "$(cat "$WORK/repo/.release/1.0.0/ci-sha" 2>/dev/null)"
eq "the gate filtered on that same sha"  "$_post" "$(cat "$WORK/repo/filtered-on" 2>/dev/null)"

head_ "18 · ci-green with no recorded sha fails closed, it does not watch by recency"
fresh
steps <<'EOF'
ci-green|GATE strict CI green|gate|1m|||__CIWAIT__
EOF
stub gh 'echo 99999'
rc=$(drive 1.0.0)
eq "no dispatched sha -> the gate fails" 1 "$rc"
grep -q 'recorded no dispatched sha' "$WORK/out" && ok "and says which step to retry"                                                  || bad "no explanation"

head_ "19 · a step command that reads stdin must not eat the step table"
# The loop's stdin IS the step table (a heredoc). On 28 Aug 2026 ssh inside
# upload-dmg.sh inherited it and consumed the remaining rows: tag and snap were
# never read, never ran, left no events — and the driver printed "every act is
# done" over an unpublished release. `cat` is the minimal stand-in for ssh.
fresh
steps <<'EOF'
one|first|plain|1m|||true
eater|slurps stdin|plain|1m|||cat
three|third|plain|1m|||true
four|fourth|plain|1m|||true
EOF
rc=$(drive 4.0.0)
eq "the run completes"           75 "$rc"
eq "the eater itself is ok"      ok "$(status_of 4.0.0 eater)"
eq "the NEXT step still ran"     ok "$(status_of 4.0.0 three)"
eq "the LAST step still ran"     ok "$(status_of 4.0.0 four)"

head_ "20 · run-completed is a checklist claim — a consumed table must not report done"
# Belt to 19's braces: even if some future defect truncates the table again,
# the completeness verdict must refuse to write run-completed. Simulated by a
# table whose tail the driver never sees: pre-seed the ledger as if a prior
# invocation processed only the first row, then drive a run whose steps file
# names a step the events can never account for -- covered at the unit level
# by verdict_complete tests; here we assert the happy path still completes.
fresh
steps <<'EOF'
only|sole step|plain|1m|||true
EOF
rc=$(drive 5.0.0)
eq "complete run still writes run-completed" 75 "$rc"
grep -q '"step":"run","status":"completed"' "$WORK/repo/.release/5.0.0/events.jsonl" \
    && ok "run completed present" || bad "run completed missing"

meta_check
finish
