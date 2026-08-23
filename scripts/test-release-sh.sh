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
TBL=$(sed -n "/^cat <<'TBL'$/,/^TBL$/p" "$ROOT/scripts/release.sh" | sed '1d;$d')
n_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$2=="IRREVERSIBLE"' | grep -c . || true)
eq "three irreversible steps" 3 "$n_irrev"

# Every irreversible step must state its cost.
missing=$(printf '%s\n' "$TBL" | awk -F'|' '$2=="IRREVERSIBLE" && $4==""{print $1}' | tr '\n' ' ')
if [ -z "$missing" ]; then ok "every irreversible step names its consequence"
else bad "irreversible steps with no consequence: $missing"; fi

# And no reversible step may claim one — crying wolf on the cheap steps is how
# the real warnings stop being read.
noisy=$(printf '%s\n' "$TBL" | awk -F'|' '$2=="REVERSIBLE" && $4!=""{print $1}' | tr '\n' ' ')
if [ -z "$noisy" ]; then ok "no reversible step claims a consequence"
else bad "reversible steps claiming consequences: $noisy"; fi

# The gate must sit before the first irreversible act — that IS the 0.25.2 fix.
gate_id=$(printf '%s\n' "$TBL" | awk -F'|' '$2=="GATE"{print $1; exit}')
first_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$2=="IRREVERSIBLE"{print $1; exit}')
if [ -n "$gate_id" ] && [ -n "$first_irrev" ] && [ "$gate_id" -lt "$first_irrev" ]; then
    ok "the CI gate precedes every irreversible act (step $gate_id < $first_irrev)"
else bad "gate at '$gate_id' does not precede first irreversible '$first_irrev'"; fi

# The hard line is last of the three: a burned PyPI version is the one thing
# nothing can undo, so it must not be crossed before the recoverable ones.
last_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$2=="IRREVERSIBLE"{i=$1; c=$4} END{print i"|"c}')
case "$last_irrev" in
    *HARD*) ok "the HARD line is the last irreversible step" ;;
    *)      bad "last irreversible step is not the HARD one: $last_irrev" ;;
esac

# The INTEGER sequence must be contiguous from 1 — a gap means an edit dropped a
# step. Letter-suffixed sub-steps (4a, 13a) are the house convention, not a
# defect: REPORT-STYLE.md rule 3 names them and build-all.sh already runs
# 1 2 2a 2b 2c 2d 5 6 7 8 9. An earlier version of this assertion rejected them
# and flagged a correct table, which is the gate-that-cries-wolf shape.
majors=$(printf '%s\n' "$TBL" | awk -F'|' '{print $1}' | sed 's/[a-z]*$//' | awk '!seen[$0]++')
expected=$(seq 1 "$(printf '%s\n' "$majors" | grep -c .)")
if [ "$(printf '%s' "$majors")" = "$(printf '%s' "$expected")" ]; then
    ok "step ids contiguous ($(printf '%s\n' "$majors" | grep -c .) majors, sub-steps allowed)"
else
    bad "step id majors are not contiguous: $(printf '%s' "$majors" | tr '\n' ' ')"
fi

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

head_ "meta"
_before=$FAIL
_r=$(eq "deliberate" ok malformed 2>&1)
case "$_r" in *"expected 'ok', got 'malformed'"*) ok "eq() reports a real mismatch" ;;
             *) bad "eq() cannot fail" ;; esac
[ "$FAIL" -eq "$_before" ] || bad "harness leaked the deliberate failure"

printf '\n\033[1m%d passed, %d failed\033[0m\n\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
