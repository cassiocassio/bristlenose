#!/usr/bin/env bash
# test-release-sh.sh — the read-only driver's decisions, and the step table's
# structural invariants.
#
# The table is the interesting part. It encodes irreversibility order, and a
# table that says a step is IRREVERSIBLE without saying WHAT it costs is a table
# that lies at the exact moment someone is reading it to decide. These assertions
# pin that, so adding a step cannot quietly break it.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0
ok()  { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
bad() { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; FAIL=$((FAIL+1)); }
head_(){ printf '\n\033[1m%s\033[0m\n' "$1"; }
eq() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 — expected '$2', got '$3'"; fi; }

RELEASE_LIB=1 . "$ROOT/scripts/release.sh"

head_ "verdict_version — a typo must not select a different release silently"
eq "normal"                ok        "$(verdict_version 0.28.0)"
eq "four-part"             ok        "$(verdict_version 0.28.0.1)"
eq "letter O for zero"     malformed "$(verdict_version 0.28.O)"
eq "v prefix"              malformed "$(verdict_version v0.28.0)"
eq "path traversal"        malformed "$(verdict_version ../../tmp)"
eq "word"                  malformed "$(verdict_version latest)"
eq "empty"                 empty     "$(verdict_version '')"
eq "spaces"                malformed "$(verdict_version '0.28.0 ')"
eq "shell metachars"       malformed "$(verdict_version '0.28.0;rm -rf /')"
eq "two-part rejected"     malformed "$(verdict_version 0.28)"

head_ "verdict_act — release / rebuild / nothing"
eq "wheel moved"           release "$(verdict_act ' 5 files' '')"
eq "wheel + desktop"       release "$(verdict_act ' 5 files' ' 2 files')"
eq "desktop only"          rebuild "$(verdict_act '' ' 8 files')"
eq "nothing moved"         nothing "$(verdict_act '' '')"

head_ "rollup_exit — held is not ready, and not an error"
eq "ready"                 0  "$(rollup_exit 0 0)"
eq "not ready"             1  "$(rollup_exit 1 0)"
eq "held beats ready"      75 "$(rollup_exit 0 1)"
eq "held beats not-ready"  75 "$(rollup_exit 1 1)"

head_ "the step table — structural invariants"
TBL=$(sed -n "/^cat <<'RUNTBL'$/,/^RUNTBL$/p" "$ROOT/scripts/release.sh" | sed '1d;$d')
n_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$3=="soft"||$3=="hard"' | grep -c . || true)
eq "three irreversible steps" 3 "$n_irrev"

# Every irreversible step must state its cost.
missing=$(printf '%s\n' "$TBL" | awk -F'|' '($3=="soft"||$3=="hard") && $5==""{print $1}' | tr '\n' ' ')
if [ -z "$missing" ]; then ok "every irreversible step names its consequence"
else bad "irreversible steps with no consequence: $missing"; fi

# And no reversible step may claim one — crying wolf on the cheap steps is how
# the real warnings stop being read.
noisy=$(printf '%s\n' "$TBL" | awk -F'|' '$3=="plain" && $5!=""{print $1}' | tr '\n' ' ')
if [ -z "$noisy" ]; then ok "no reversible step claims a consequence"
else bad "reversible steps claiming consequences: $noisy"; fi

# The gate must sit before the first irreversible act — that IS the 0.25.2 fix.
gate_id=$(printf '%s\n' "$TBL" | awk -F'|' '$1=="ci-green"{print NR}')
first_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$3=="soft"||$3=="hard"{print NR; exit}')
if [ -n "$gate_id" ] && [ -n "$first_irrev" ] && [ "$gate_id" -lt "$first_irrev" ]; then
    ok "the CI gate precedes every irreversible act (step $gate_id < $first_irrev)"
else bad "gate at '$gate_id' does not precede first irreversible '$first_irrev'"; fi

# The hard line is last of the three: a burned PyPI version is the one thing
# nothing can undo, so it must not be crossed before the recoverable ones.
last_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$3=="soft"||$3=="hard"{i=$1; c=$5} END{print i"|"c}')
case "$last_irrev" in
    *HARD*) ok "the HARD line is the last irreversible step" ;;
    *)      bad "last irreversible step is not the HARD one: $last_irrev" ;;
esac

# Step ids must be unique — the fold keys on them, so a duplicate would make two
# different steps share one status and silently skip the second.
dupes=$(printf '%s
' "$TBL" | awk -F'|' '{print $1}' | sort | uniq -d | tr '
' ' ')
[ -z "$dupes" ] && ok "step ids are unique (the fold keys on them)" \
                || bad "duplicate step ids: $dupes"

head_ "tier filtering — a Tier 2 step must not inflate a Tier 1 estimate"
t1=$(bash "$ROOT/scripts/release.sh" plan 0.28.0 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
t2=$(bash "$ROOT/scripts/release.sh" plan 0.28.0 --tier 2 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
case "$t1" in *"--ref v0.28.0"*) bad "Tier 1 plan shows the Tier 2 stable push" ;;
              *) ok "Tier 1 omits the Tier 2 stable push" ;; esac
case "$t2" in *"--ref v0.28.0"*) ok "Tier 2 includes the stable push" ;;
              *) bad "Tier 2 omits the stable push" ;; esac
e1=$(printf '%s' "$t1" | grep -oE '~[0-9]+h[0-9]+' | head -1)
e2=$(printf '%s' "$t2" | grep -oE '~[0-9]+h[0-9]+' | head -1)
if [ -n "$e1" ] && [ -n "$e2" ] && [ "$e1" != "$e2" ]; then
    ok "Tier 1 estimate ($e1) differs from Tier 2 ($e2)"
else bad "tier estimates identical ($e1 / $e2) — the filter is not applied to the total"; fi
case "$e1" in *m*) bad "estimate double-labels minutes ($e1)" ;; *) ok "estimate formatted as XhYY" ;; esac

head_ "end to end"
bash "$ROOT/scripts/release.sh" run >/dev/null 2>&1
eq "run refuses with exit 2" 2 "$?"
bash "$ROOT/scripts/release.sh" plan 0.28.O >/dev/null 2>&1
eq "malformed version exit 2" 2 "$?"
bash "$ROOT/scripts/release.sh" bogus >/dev/null 2>&1
eq "unknown command exit 2" 2 "$?"
bash "$ROOT/scripts/release.sh" plan 0.28.0 >/dev/null 2>&1
eq "plan on a shippable tree exit 0" 0 "$?"
out=$(bash "$ROOT/scripts/release.sh" status 2>&1)
case "$out" in
    *$'\n0'*|"0"*) bad "status leaks a bare exit code into its output" ;;
    *)             ok "status output carries no stray value" ;;
esac

head_ "width — REPORT-STYLE.md budget"
overlong=$(bash "$ROOT/scripts/release.sh" plan 0.28.0 2>&1 \
    | sed 's/\x1b\[[0-9;]*m//g' | awk 'length($0)>92' | grep -c . || true)
eq "no line exceeds 92 cols" 0 "$overlong"


head_ "run — every safety path, none of which may touch the world"
_h0=$(git rev-parse HEAD); _t0=$(git tag -l | wc -l | tr -d ' ')

bash "$ROOT/scripts/release.sh" run 0.28.0 </dev/null >/dev/null 2>&1
eq "missing --bump refuses" 2 "$?"
bash "$ROOT/scripts/release.sh" run 0.28.O --bump minor </dev/null >/dev/null 2>&1
eq "malformed version refuses" 2 "$?"
bash "$ROOT/scripts/release.sh" run 0.28.0 --bump wat </dev/null >/dev/null 2>&1
eq "bad bump kind refuses" 2 "$?"
echo "not-the-version" | bash "$ROOT/scripts/release.sh" run 0.28.0 --bump minor >/dev/null 2>&1
eq "wrong confirmation aborts" 2 "$?"
[ -d "$ROOT/.release/0.28.0" ] && bad "a declined run left a directory behind" \
                               || ok "a declined run leaves nothing"

head_ "run — resume from a synthetic log, with the stranded step first"
_rd="$ROOT/.release/9.9.9"; mkdir -p "$_rd/logs"
cat > "$_rd/events.jsonl" <<'LOG'
{"ts":"2026-08-23T10:00:00Z","run":"9.9.9","step":"preflight","status":"ok","detail":"52s"}
{"ts":"2026-08-23T10:02:00Z","run":"9.9.9","step":"bump","status":"ok","detail":"4s"}
{"ts":"2026-08-23T10:03:00Z","run":"9.9.9","step":"push-main","status":"ok","detail":"11s"}
{"ts":"2026-08-23T10:04:00Z","run":"9.9.9","step":"strict-ci","status":"ok","detail":"2s"}
{"ts":"2026-08-23T10:05:00Z","run":"9.9.9","step":"build-all","status":"running","detail":"attempt 1"}
LOG
_out=$(echo "9.9.9" | bash "$ROOT/scripts/release.sh" run 9.9.9 --bump patch 2>&1)
_rc=$?
eq "a stranded step exits 3, never auto-advances" 3 "$_rc"
case "$_out" in *"skipped (done)"*) ok "steps already ok are skipped" ;;
                *) bad "completed steps were not skipped" ;; esac
case "$_out" in *"interrupted and its outcome is unrecorded"*) ok "the stranded step is named" ;;
                *) bad "stranded step not reported" ;; esac
[ -z "$(ls -A "$_rd/logs" 2>/dev/null)" ] && ok "no step executed" || bad "a step ran during a stranded resume"
[ "$(git rev-parse HEAD)" = "$_h0" ] && ok "HEAD unchanged" || bad "HEAD MOVED during a test"
[ "$(git tag -l | wc -l | tr -d ' ')" = "$_t0" ] && ok "no tag created" || bad "A TAG WAS CREATED during a test"

head_ "fold — the last status wins, and absence is pending"
V=9.9.9; EVENTS="$_rd/events.jsonl"
eq "terminus overrides an earlier running" ok      "$(fold_status preflight)"
eq "running with no terminus is stranded"  running "$(fold_status build-all)"
eq "never seen is pending"                 pending "$(fold_status tag)"
bash "$ROOT/scripts/release.sh" retry 9.9.9 build-all >/dev/null 2>&1
eq "retry resets to pending"               pending "$(fold_status build-all)"
rm -rf "$_rd"

head_ "probe_done — the world beats the log for irreversible steps"
V=0.27.0; probe_done tag && ok "finds a tag that is on origin" || bad "missed a real tag"
V=9.9.9;  probe_done tag && bad "claimed a nonexistent tag exists" || ok "does not invent a tag"
V=0.28.0; probe_done testflight && bad "assumed TestFlight state" \
                                || ok "never assumes TestFlight is done (needs ASC)"

head_ "the run table — the tag is last, and it is the hard line"
RT=$(sed -n "/^cat <<'RUNTBL'$/,/^RUNTBL$/p" "$ROOT/scripts/release.sh" | sed '1d;$d')
_hard=$(printf '%s\n' "$RT" | awk -F'|' '$3=="hard"{print $1}')
eq "exactly one hard step" "tag" "$_hard"
_lastirrev=$(printf '%s\n' "$RT" | awk -F'|' '$3=="hard"||$3=="soft"{print NR}' | tail -1)
_gate=$(printf '%s\n' "$RT" | awk -F'|' '$1=="ci-green"{print NR}')
[ -n "$_gate" ] && [ "$_gate" -lt "$_lastirrev" ] \
    && ok "the strict-CI gate precedes every irreversible step" \
    || bad "gate at $_gate does not precede irreversible at $_lastirrev"
_tagpos=$(printf '%s\n' "$RT" | awk -F'|' '$1=="tag"{print NR}')
_tfpos=$(printf '%s\n' "$RT" | awk -F'|' '$1=="testflight"{print NR}')
[ "$_tagpos" -gt "$_tfpos" ] \
    && ok "the tag (which publishes) comes after the soft uploads" \
    || bad "the tag publishes before the uploads are verified"


_nocons=$(printf '%s\n' "$RT" | awk -F'|' '($3=="hard"||$3=="soft") && $5==""{print $1}' | tr '\n' ' ')
[ -z "$_nocons" ] && ok "every irreversible run-step names its consequence" \
                  || bad "irreversible steps with no consequence: $_nocons"
_plain=$(printf '%s\n' "$RT" | awk -F'|' '$3=="plain" && $5!=""{print $1}' | tr '\n' ' ')
[ -z "$_plain" ] && ok "no reversible run-step claims a consequence" \
                 || bad "reversible steps claiming consequences: $_plain"
_p=$(bash "$ROOT/scripts/release.sh" plan 0.28.0 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
case "$_p" in *"git tag v0.28.0"*) ok "plan renders the tag step" ;;
              *) bad "plan lost the tag step" ;; esac
_tagline=$(printf '%s' "$_p" | grep -n 'git tag' | cut -d: -f1)
_tfline=$(printf '%s' "$_p" | grep -n 'upload-testflight' | cut -d: -f1)
[ -n "$_tagline" ] && [ -n "$_tfline" ] && [ "$_tagline" -gt "$_tfline" ] \
    && ok "plan and run agree: the tag comes after the uploads" \
    || bad "plan shows the tag BEFORE the uploads — plan and run disagree"

head_ "meta"
_before=$FAIL
_r=$(eq "deliberate" ok malformed 2>&1)
case "$_r" in *"expected 'ok', got 'malformed'"*) ok "eq() reports a real mismatch" ;;
             *) bad "eq() cannot fail" ;; esac
[ "$FAIL" -eq "$_before" ] || bad "harness leaked the deliberate failure"

printf '\n\033[1m%d passed, %d failed\033[0m\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
