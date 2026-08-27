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
. "$(dirname "$0")/test-lib.sh"

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

# Every irreversible step must state its cost.
missing=$(printf '%s\n' "$TBL" | awk -F'|' '($3=="soft"||$3=="hard") && $6==""{print $1}' | tr '\n' ' ')
if [ -z "$missing" ]; then ok "every irreversible step names its consequence"
else bad "irreversible steps with no consequence: $missing"; fi

# And no reversible step may claim one — crying wolf on the cheap steps is how
# the real warnings stop being read.
noisy=$(printf '%s\n' "$TBL" | awk -F'|' '$3=="plain" && $6!=""{print $1}' | tr '\n' ' ')
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
last_irrev=$(printf '%s\n' "$TBL" | awk -F'|' '$3=="soft"||$3=="hard"{i=$1; c=$6} END{print i"|"c}')
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
# Use a version nothing real will ever be, and record whether the directory
# pre-existed. This assertion used to run against 0.28.0 and the live .release/
# tree, so a GENUINE release in flight — which legitimately leaves resume state —
# failed it. Red for the right reason in the wrong scenario is still a gate you
# learn to ignore. Observed 27 Aug 2026 mid-release.
_decl="8.8.8"
_had_dir=0; [ -d "$ROOT/.release/$_decl" ] && _had_dir=1
echo "not-the-version" | bash "$ROOT/scripts/release.sh" run "$_decl" --bump minor >/dev/null 2>&1
eq "wrong confirmation aborts" 2 "$?"
if [ "$_had_dir" = 1 ]; then
    ok "a declined run leaves nothing (skipped — $_decl pre-existed)"
elif [ -d "$ROOT/.release/$_decl" ]; then
    bad "a declined run left a directory behind"
    rm -rf "$ROOT/.release/$_decl"
else
    ok "a declined run leaves nothing"
fi

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
V=0.28.0; probe_done testflight; _r=$?
eq "TestFlight reports NO PROBE (2), not absent (1)" 2 "$_r"
# The distinction is load-bearing: 1 would silently re-run the upload on resume
# and spend a second build number; 2 stops and asks.
V=9.9.9; probe_done tag; eq "a missing tag is absent (1), not unprobeable" 1 "$?"

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


# (consequence naming is asserted once, above, against the same table)
_p=$(bash "$ROOT/scripts/release.sh" plan 0.28.0 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
case "$_p" in *"git tag v0.28.0"*) ok "plan renders the tag step" ;;
              *) bad "plan lost the tag step" ;; esac
_tagline=$(printf '%s' "$_p" | grep -n 'git tag' | cut -d: -f1)
_tfline=$(printf '%s' "$_p" | grep -n 'upload-testflight' | cut -d: -f1)
[ -n "$_tagline" ] && [ -n "$_tfline" ] && [ "$_tagline" -gt "$_tfline" ] \
    && ok "plan and run agree: the tag comes after the uploads" \
    || bad "plan shows the tag BEFORE the uploads — plan and run disagree"



head_ "the run table's shape"
# A row with a stray | puts the surplus into $steptier, and run then treats it as
# a tier restriction and CONTINUEs — the step vanishes from execution with no
# event, no log, no exit code, while plan still renders it. A pipe inside a cmd
# is the natural thing to write when adding a step.
_badrows=$(printf '%s\n' "$RT" | awk -F'|' 'NF!=7{print NR": "$1}' | tr '\n' ' ')
[ -z "$_badrows" ] && ok "every run row has exactly 7 fields" \
                   || bad "rows with the wrong column count: $_badrows"

# verify cannot be a step of the run that pushes the tag: release.yml runs the
# full matrix before publish, so every channel is legitimately absent for ~40min.
case "$RT" in *"verify-channels.sh"*) bad "verify is back in the run table — it can never pass there" ;;
              *) ok "verify is not a synchronous step of run" ;; esac

head_ "the redirect discipline, pinned"
# release.sh:406 claims "$? is the command's own status, not tail's" and that
# claim is the whole reason 0.27.0 #1 cannot recur here. Nothing asserted it.
# A single `| tee` added for debugging would silently reinstate the bug.
_evalline=$(grep -n 'eval "\$cmd"' "$ROOT/scripts/release.sh" | head -1)
case "$_evalline" in
    *'> "$LOG" 2>&1'*) ok "run redirects the step, never pipes it" ;;
    *)                 bad "run's eval is not a plain redirect: $_evalline" ;;
esac
case "$_evalline" in
    *'|'*) bad "a pipe appeared on the eval line — \$? would be the pipe's" ;;
    *)     ok "no pipe on the eval line" ;;
esac


head_ "verdict_recover — rerun vs retag vs redeliver, the v0.15.13 decision"
# published always wins: nothing to recover, only to supersede. Reached first so
# no branch can suggest tag surgery on an immutable version.
eq "published beats a failed run"   published  "$(verdict_recover yes failure aaa bbb)"
eq "published beats no run at all"  published  "$(verdict_recover yes none aaa aaa)"

# v0.15.0: `git push --tags` bundled the events and the workflow never fired.
eq "no run fired -> redeliver"      redeliver  "$(verdict_recover no none aaa aaa)"

# v0.15.13: the run failed, main already carried the fix, and a --failed rerun
# replayed the STALE tagged commit and failed identically.
eq "failed + main moved -> retag"   retag      "$(verdict_recover no failure aaa bbb)"
eq "failed + tag IS head -> rerun"  rerun      "$(verdict_recover no failure aaa aaa)"
eq "cancelled + moved -> retag"     retag      "$(verdict_recover no cancelled aaa bbb)"
eq "timed_out + same -> rerun"      rerun      "$(verdict_recover no timed_out aaa aaa)"
eq "startup_failure + same"         rerun      "$(verdict_recover no startup_failure aaa aaa)"

eq "still running -> wait"          wait       "$(verdict_recover no in_progress aaa aaa)"
eq "queued -> wait"                 wait       "$(verdict_recover no queued aaa aaa)"
# Green but absent from PyPI is neither a rerun nor a retag — it is the
# v0.15.5-0.15.9 shape, where five runs looked fine and delivered nothing.
eq "green but unpublished"          investigate "$(verdict_recover no success aaa aaa)"
eq "an unknown state is not a fix"  investigate "$(verdict_recover no weird aaa aaa)"
# An empty tag sha must not be treated as equal to an empty head sha.
eq "no local tag -> retag, not rerun" retag    "$(verdict_recover no failure '' '')"

head_ "recover — end to end against the real 0.27.0"
_out=$(bash "$ROOT/scripts/release.sh" recover 0.27.0 2>&1)
case "$_out" in
    *"is published"*) ok "recognises a published version" ;;
    *) bad "did not detect 0.27.0 on PyPI" ;;
esac
case "$_out" in
    *"git tag -f"*|*"rerun --failed"*|*"push --delete"*)
        bad "offered tag surgery on a PUBLISHED version" ;;
    *)  ok "offers no tag surgery once published" ;;
esac
bash "$ROOT/scripts/release.sh" recover 0.28.O >/dev/null 2>&1
eq "malformed version refuses" 2 "$?"


head_ "project.conf — the identity seam"
. "$ROOT/scripts/project.conf"
eq "CHANNELS is set"            0 "$([ -n "$CHANNELS" ] && echo 0 || echo 1)"
for _c in $CHANNELS; do
    grep -q "^probe_${_c}()" "$ROOT/scripts/verify-channels.sh" \
        && ok "channel '$_c' has a probe" \
        || bad "channel '$_c' is listed with NO probe — it would be silently unchecked"
done
# Every unprobeable channel must also be a real channel, or the note is a lie.
for _u in $CHANNELS_UNPROBEABLE; do
    case " $CHANNELS " in *" $_u "*) ok "unprobeable '$_u' is a real channel" ;;
                          *) bad "CHANNELS_UNPROBEABLE names '$_u', which is not in CHANNELS" ;; esac
done
# Derived URLs must actually carry the identity, or a rename half-lands.
case "$DMG_PERMALINK"  in *"$SITE"*)            ok "DMG_PERMALINK derives from SITE" ;;  *) bad "DMG_PERMALINK does not use SITE" ;; esac
case "$TAP_FORMULA_RAW" in *"$TAP_REPO"*)       ok "TAP_FORMULA_RAW derives from TAP_REPO" ;; *) bad "TAP_FORMULA_RAW does not use TAP_REPO" ;; esac
case "$SNAP_INFO"      in *"$PROJECT_NAME"*)    ok "SNAP_INFO derives from PROJECT_NAME" ;; *) bad "SNAP_INFO does not use PROJECT_NAME" ;; esac
[ -f "$ROOT/$VERSION_FILE" ] && ok "VERSION_FILE exists" || bad "VERSION_FILE points at nothing: $VERSION_FILE"
_v=$(sed -n "$VERSION_REGEX" "$ROOT/$VERSION_FILE")
case "$_v" in [0-9]*.[0-9]*.[0-9]*) ok "VERSION_REGEX extracts a version ($_v)" ;;
              *) bad "VERSION_REGEX extracted '$_v'" ;; esac

head_ "every project.conf constant has a consumer (F44)"
# The file's own header claimed check-release-ready.sh sourced it. It did not,
# and carried the PyPI URL, both GitHub repos and the advisory workflow list as
# literals — while WF_SNAP, WF_ADVISORY and ADVISORY_STREAK_MAX sat in the conf
# with no reader anywhere. A config nobody reads is worse than a literal: the
# literal at least does not lie about where the value lives.
#
# Comment lines are stripped before searching, so a constant merely NAMED in
# prose does not count as consumed — which is the shape the old header had.
_consumers="$ROOT/scripts/release.sh $ROOT/scripts/verify-channels.sh $ROOT/scripts/check-release-ready.sh $ROOT/scripts/project.conf"
# Collapsed to a STRING and searched with a herestring, never a live pipe. Under
# `set -o pipefail`, `grep -q` exits at its first match, the upstream grep takes
# SIGPIPE and exits 141, and 141 becomes the pipeline's status — so a match near
# the TOP of the stream reads as no match. The first draft of this block did
# exactly that and reported 15 consumed constants as unconsumed, the ones whose
# only hit was early in release.sh. Same trap verify-channels.sh's
# _token_present carries a paragraph about; reproduced here, in the test written
# to enforce these conventions.
_haystack=$(grep -hvE '^[[:space:]]*#' $_consumers 2>/dev/null)
_names=$(grep -oE '^[A-Z][A-Z0-9_]*=' "$ROOT/scripts/project.conf" | tr -d '=')
_count=$(printf '%s\n' "$_names" | grep -c .)
[ "${#_haystack}" -gt 10000 ] && ok "read $((${#_haystack}/1024))KB of consumer source" \
                             || bad "the consumer corpus is ${#_haystack} bytes — nothing would match"
# A broken extraction finds nothing and every assertion below silently passes.
[ "$_count" -ge 15 ] && ok "found $_count constants to check" \
                     || bad "extracted only $_count constants — the regex is wrong, not the conf"
for _v in $_names; do
    # \$VAR or \${VAR}, not followed by another name character: CHANNELS must not
    # be satisfied by CHANNELS_UNPROBEABLE.
    if grep -qE '\$\{?'"$_v"'\}?([^A-Za-z0-9_]|$)' <<<"$_haystack"; then
        ok "$_v is read by something"
    else
        bad "$_v has no consumer — wire it or delete it"
    fi
done
# And prove that check can fail, on a name that is deliberately absent.
if grep -qE '\$\{?BN_NO_SUCH_CONSTANT\}?([^A-Za-z0-9_]|$)' <<<"$_haystack"; then
    bad "the consumer search matches a constant that does not exist"
else
    ok "the search reports a genuinely unconsumed name"
fi

head_ "recover names the run it DIAGNOSED, not the newest one (F42)"
# The diagnosis filters headBranch=="v$V"; the three pasted remedies used to be
# `gh run … $(gh run list --limit 1 …)` — recency. Recovering an older version
# while any newer release run existed reran the wrong one. They also printed a
# literal, unexpanded $WF_RELEASE, so the paste ran `gh run list --workflow=`.
_W=$(mktemp -d); trap 'rm -rf "$_W"' EXIT INT TERM
mkdir -p "$_W/repo/scripts" "$_W/bin"
cp "$ROOT/scripts/release.sh" "$ROOT/scripts/project.conf" "$_W/repo/scripts/"
( cd "$_W/repo" && git init -q . && git commit -q --allow-empty -m init && git tag v1.0.0 ) 2>/dev/null
# 111 is v1.0.0's run; 999 is a newer, unrelated one — what recency would pick.
cat > "$_W/bin/gh" <<'GHSTUB'
#!/bin/sh
case "$*" in
  *databaseId,headBranch*) echo "111|$BN_FAKE_STATE" ;;
  *) echo 999 ;;
esac
GHSTUB
printf '#!/bin/sh
case " $* " in *" -w "*) printf 404 ;; esac
' > "$_W/bin/curl"
chmod +x "$_W/bin/gh" "$_W/bin/curl"

for _case in "failure:rerun --failed" "in_progress:watch" "success:view"; do
    _st="${_case%%:*}"; _want="${_case#*:}"
    _out=$( cd "$_W/repo" && PATH="$_W/bin:$PATH" BN_FAKE_STATE="$_st" \
            bash scripts/release.sh recover 1.0.0 2>&1 )
    _line=$(printf '%s' "$_out" | sed 's/\x1b\[[0-9;]*m//g' | grep -E '^ *gh run' | head -1)
    case "$_line" in
        *"gh run $_want 111"*) ok "$_st -> names run 111" ;;
        *999*)                 bad "$_st -> pasted the NEWEST run (999): $_line" ;;
        *)                     bad "$_st -> unexpected remedy: ${_line:-<none printed>}" ;;
    esac
    case "$_line" in
        *'$('*|*'$WF'*) bad "$_st -> remedy still carries an unresolved shell expansion: $_line" ;;
        *)              ok "$_st -> the remedy is paste-ready" ;;
    esac
done

head_ "the copr token gate — a credential that expires between releases"
# Copr API tokens last 180 days and this channel ships a few times a year, so
# the token is reliably dead when it is next needed. The gate lives in
# check-release-ready.sh because it matters AT release time; a calendar
# reminder fires while you are doing something else.
#
# Driven as a unit: the block is eval'd with stub ok/warn/bad, so these assert
# the DECISION rather than the whole preflight run. Same seam as
# test-verify-channels.sh's lib mode.
_copr_block=$(sed -n '/^# The Fedora Copr API token/,/^;; esac/p' "$ROOT/scripts/check-release-ready.sh")
[ -n "$_copr_block" ] && ok "the copr block is locatable in check-release-ready.sh" \
    || bad "could not extract the copr block — the assertions below prove nothing"

# $1 = HOME to run against, $2 = extra PATH entry (for a copr-cli stub), $3 = owner
_copr_verdict() {
    bash -c '
        set -uo pipefail
        ok()   { printf "ok|%s|%s\n"   "$1" "${2:-}"; }
        warn() { printf "warn|%s|%s\n" "$1" "${2:-}"; }
        bad()  { printf "bad|%s|%s\n"  "$1" "${2:-}"; }
        CHANNELS="copr"; COPR_OWNER="'"${3:-cassiocassio}"'"; HOME="'"$1"'"
        [ -n "'"${2:-}"'" ] && PATH="'"${2:-}"':$PATH"
        eval "$COPR_BLOCK"' 2>&1
}
export COPR_BLOCK="$_copr_block"
_row() { printf '%s\n' "$1" | grep "|$2|" | head -1 | cut -d'|' -f1; }

_W=$(mktemp -d); trap 'rm -rf "$_W"' EXIT INT TERM
mkdir -p "$_W/none" "$_W/good/.config" "$_W/old/.config" "$_W/soon/.config" \
         "$_W/noexp/.config" "$_W/stub"
printf '# expiration date: 2099-01-01\n'                       > "$_W/good/.config/copr"
printf '# expiration date: 2020-01-01\n'                       > "$_W/old/.config/copr"
printf "# expiration date: $(date -v+10d +%Y-%m-%d 2>/dev/null || date -d '+10 days' +%Y-%m-%d)\n" \
                                                                > "$_W/soon/.config/copr"
printf '[copr-cli]\nlogin = x\n'                               > "$_W/noexp/.config/copr"

eq "no config at all"      bad  "$(_row "$(_copr_verdict "$_W/none")"  "copr token")"
eq "healthy expiry"        ok   "$(_row "$(_copr_verdict "$_W/good")"  "copr token")"
eq "EXPIRED"               bad  "$(_row "$(_copr_verdict "$_W/old")"   "copr token")"
eq "expiring within 30d"   warn "$(_row "$(_copr_verdict "$_W/soon")"  "copr token")"
eq "no expiry recorded"    warn "$(_row "$(_copr_verdict "$_W/noexp")" "copr token")"

# The read-back. An expiry comment is a CLAIM about the token; a hand-edited
# file, a revoked token or the wrong username all read fine on expiry alone.
printf '#!/bin/sh\necho cassiocassio\n' > "$_W/stub/copr-cli"; chmod +x "$_W/stub/copr-cli"
eq "auth matches the owner" ok \
    "$(_row "$(_copr_verdict "$_W/good" "$_W/stub" cassiocassio)" "copr auth")"
eq "auth is a DIFFERENT owner" bad \
    "$(_row "$(_copr_verdict "$_W/good" "$_W/stub" someone-else)" "copr auth")"
printf '#!/bin/sh\nexit 1\n' > "$_W/stub/copr-cli"
eq "token does not authenticate" bad \
    "$(_row "$(_copr_verdict "$_W/good" "$_W/stub")" "copr auth")"
eq "no copr-cli — unverified, not passed" warn \
    "$(_row "$(_copr_verdict "$_W/good")" "copr auth")"

# And the reason it is safe to ship before the channel exists: gated on
# CHANNELS, so it renders nothing at all while copr is off.
_off=$(bash -c '
    set -uo pipefail
    ok(){ echo ok; }; warn(){ echo warn; }; bad(){ echo bad; }
    CHANNELS="pypi github"; COPR_OWNER="x"; HOME="'"$_W/none"'"
    eval "$COPR_BLOCK"' 2>&1)
[ -z "$_off" ] && ok "silent while copr is not in CHANNELS — no wolf cried" \
    || bad "the gate fired with copr disabled: $_off"

head_ "meta"
_before=$FAIL
_r=$(eq "deliberate" ok malformed 2>&1)
case "$_r" in *"expected 'ok', got 'malformed'"*) ok "eq() reports a real mismatch" ;;
             *) bad "eq() cannot fail" ;; esac
[ "$FAIL" -eq "$_before" ] || bad "harness leaked the deliberate failure"

finish
