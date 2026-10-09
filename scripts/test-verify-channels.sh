#!/usr/bin/env bash
# test-verify-channels.sh — drive verify-channels.sh's decision layer with
# synthetic input, including every failure shape a real release can produce.
#
# WHY THIS SHAPE
#
# The network round trip is not the risk; the DECISION is. So verify-channels.sh
# splits `probe` (I/O) from `verdict_*` (pure), and this suite sources the script
# with VERIFY_CHANNELS_LIB=1 and drives only the pure half. No network, no
# mocking, runs in milliseconds. Same split desktop/scripts/test-upload-dmg.sh
# already uses for swap_decision / retention_plan.
#
# Every assertion is proven to fail on its own violation — a test that cannot
# fail is decoration (docs/design-test-philosophy.md).

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

. "$(dirname "$0")/test-lib.sh"


VERIFY_CHANNELS_LIB=1 . "$ROOT/scripts/verify-channels.sh"

head_ "verdict_http — the tri-state that stops a network fault reading as 'not published'"
eq "200 published"              ok          "$(verdict_http 200)"
eq "201 published"              ok          "$(verdict_http 201)"
eq "204 published"              ok          "$(verdict_http 204)"
eq "301 redirect is a hit"      ok          "$(verdict_http 301)"
eq "302 redirect is a hit"      ok          "$(verdict_http 302)"
eq "308 redirect is a hit"      ok          "$(verdict_http 308)"
eq "404 genuinely absent"       bad         "$(verdict_http 404)"
eq "410 genuinely gone"         bad         "$(verdict_http 410)"
eq "000 conn failure ≠ absent"  unreachable "$(verdict_http 000)"
eq "empty ≠ absent"             unreachable "$(verdict_http '')"
eq "500 ≠ absent"               unreachable "$(verdict_http 500)"
eq "403 rate-limited ≠ absent"  unreachable "$(verdict_http 403)"
eq "429 throttled ≠ absent"     unreachable "$(verdict_http 429)"
eq "502 gateway ≠ absent"       unreachable "$(verdict_http 502)"
eq "garbage ≠ absent"           unreachable "$(verdict_http 'curl: (6)')"

head_ "verdict_contains — nothing fetched is not the same as nothing found"
eq "version present"            ok          "$(verdict_contains 'v0.28.0 shipped' '0.28.0')"
eq "version absent"             bad         "$(verdict_contains 'v0.27.0 shipped' '0.28.0')"
eq "EMPTY body is unreachable"  unreachable "$(verdict_contains '' '0.28.0')"
eq "empty needle is unreachable" unreachable "$(verdict_contains 'anything' '')"
eq "multiline body"             ok          "$(verdict_contains 'a
0.28.0
b' '0.28.0')"

head_ "verdict_testflight_probe — unverified must not read as failed"
eq "0 delivered = ok"            ok      "$(verdict_testflight_probe 0)"
eq "1 absent = bad (real gap)"   bad     "$(verdict_testflight_probe 1)"
eq "3 could-not-look = skipped"  skipped "$(verdict_testflight_probe 3)"
eq "unexpected exit = skipped"   skipped "$(verdict_testflight_probe 7)"
eq "empty = skipped"             skipped "$(verdict_testflight_probe '')"

head_ "verdict_contains — the substring trap (a longer version must not satisfy a shorter one)"
eq "0.28.1 vs page naming only 0.28.10"  bad "$(verdict_contains 'released 0.28.10 today' '0.28.1')"
eq "0.2 must not match 0.28.0"           bad "$(verdict_contains 'released 0.28.0' '0.2')"
eq "0.28.0 vs 10.28.0"                   bad "$(verdict_contains 'released 10.28.0' '0.28.0')"
eq "exact still matches"                 ok  "$(verdict_contains 'released 0.28.1 today' '0.28.1')"
eq "matches at end of body"              ok  "$(verdict_contains 'released 0.28.1' '0.28.1')"
eq "matches in a tarball name"           ok  "$(verdict_contains 'bristlenose-0.28.1.tar.gz' 'bristlenose-0.28.1.tar.gz')"
eq "version followed by .dmg"            ok  "$(verdict_contains 'Location: /dmg/Bristlenose-0.28.0.dmg' '0.28.0')"
eq "version followed by .tar.gz"         ok  "$(verdict_contains 'bristlenose-0.28.0.tar.gz' '0.28.0')"
eq "a dot then a DIGIT still rejects"    bad "$(verdict_contains 'released 0.28.0.1 today' '0.28.0.1x')"

head_ "verdict_absent — 0.27.0's real website failure"
eq "abandoned version present"  bad         "$(verdict_absent 'changelog names 0.26.0' '0.26.0')"
eq "abandoned version gone"     ok          "$(verdict_absent 'changelog names 0.27.0' '0.26.0')"
eq "empty body unreachable"     unreachable "$(verdict_absent '' '0.26.0')"
eq "no abandoned version given" ok          "$(verdict_absent 'anything' '')"
eq "0.26.0 gone but 0.26.01 present is still GONE" ok "$(verdict_absent 'names 0.26.01' '0.26.0')"

head_ "verdict_json_field — an API that answers nothing is not an API that answers no"
eq "field matches"              ok          "$(verdict_json_field 'v0.28.0' 'v0.28.0')"
eq "field differs"              bad         "$(verdict_json_field 'v0.27.0' 'v0.28.0')"
eq "EMPTY is unreachable"       unreachable "$(verdict_json_field '' 'v0.28.0')"
eq "literal null unreachable"   unreachable "$(verdict_json_field 'null' 'v0.28.0')"

head_ "verdict_edge — the edge channel moves on every push; a post-release build is not a broken one"
eq "release-day exact"          ok          "$(verdict_edge '0.29.1' '0.29.1')"
eq "post-release edge build"    ok          "$(verdict_edge '0.29.1+git.30483d1' '0.29.1')"
eq "a different version"        bad         "$(verdict_edge '0.29.0+git.abc1234' '0.29.1')"
eq "a longer version is not a prefix match" bad "$(verdict_edge '0.29.10' '0.29.1')"
eq "EMPTY is unreachable"       unreachable "$(verdict_edge '' '0.29.1')"

head_ "verdict_gate — expired auth must not read as a human approval"
eq "query failed"               unreachable "$(verdict_gate QUERY_FAILED)"
eq "EMPTY ≠ gate cleared"       unreachable "$(verdict_gate '')"
eq "explicit NONE is cleared"   cleared     "$(verdict_gate NONE)"
eq "a pending deployment"       held        "$(verdict_gate 'pypi')"

head_ "rollup — unverified is not verified"
eq "all ok"                     0 "$(rollup ok ok ok)"
eq "one bad"                    1 "$(rollup ok bad ok)"
eq "one unreachable"            1 "$(rollup ok unreachable ok)"
eq "all unreachable"            1 "$(rollup unreachable unreachable)"
eq "single ok"                  0 "$(rollup ok)"
eq "skipped does not fail"      0 "$(rollup ok skipped ok)"
eq "skipped + bad still fails"  1 "$(rollup ok skipped bad)"
eq "all skipped passes"         0 "$(rollup skipped skipped)"

head_ "version_ge — numeric per field, and malformed is never 'newer'"
version_ge 0.36.0 0.36.0; eq "equal is ≥"                 0 "$?"
version_ge 0.36.1 0.36.0; eq "patch above"                0 "$?"
version_ge 0.36.0 0.36.1; eq "patch below"                1 "$?"
version_ge 0.36.10 0.36.9; eq "0.36.10 > 0.36.9 (not lexical)" 0 "$?"
version_ge 1.0.0 0.99.99; eq "major wins"                 0 "$?"
version_ge 0.36.08 0.36.7; eq "a leading zero is not octal" 0 "$?"
version_ge NONE 0.36.0;    eq "malformed left is neither (2)"  2 "$?"
version_ge 0.36.0 '';      eq "empty right is neither (2)"     2 "$?"
version_ge '0.36.0;x' 0.1.0; eq "injection shape is neither (2)" 2 "$?"

head_ "verdict_follower — pending needs evidence, and a failed query is never a negative"
eq "serves want"                         ok          "$(verdict_follower 0.36.0 NONE 0.36.0 '' 72)"
eq "serves newer than want (≥)"          ok          "$(verdict_follower 0.37.0 NONE 0.36.0 '' 72)"
eq "open PR for want, inside budget"     pending     "$(verdict_follower NONE 0.36.0 0.36.0 9 72)"
eq "open PR at exactly the budget"       pending     "$(verdict_follower NONE 0.36.0 0.36.0 72 72)"
eq "open PR past the budget"             overdue     "$(verdict_follower 0.35.0 0.36.0 0.36.0 80 72)"
eq "unreadable age leaves it pending"    pending     "$(verdict_follower NONE 0.36.0 0.36.0 '' 72)"
eq "want skipped, newer in flight"       superseded  "$(verdict_follower NONE 0.37.0 0.36.0 3 72)"
eq "0.36.10 in flight supersedes 0.36.9" superseded  "$(verdict_follower NONE 0.36.10 0.36.9 3 72)"
eq "nothing in flight"                   bad         "$(verdict_follower NONE NONE 0.36.0 '' 72)"
eq "only an OLDER version in flight"     bad         "$(verdict_follower NONE 0.35.0 0.36.0 3 72)"
eq "serves older, nothing in flight"     bad         "$(verdict_follower 0.35.0 NONE 0.36.0 '' 72)"
eq "served query failed"                 unreachable "$(verdict_follower QUERY_FAILED 0.36.0 0.36.0 3 72)"
eq "served empty"                        unreachable "$(verdict_follower '' 0.36.0 0.36.0 3 72)"
eq "in-flight query failed"              unreachable "$(verdict_follower NONE QUERY_FAILED 0.36.0 '' 72)"
eq "in-flight empty"                     unreachable "$(verdict_follower NONE '' 0.36.0 '' 72)"
eq "a failed PR query cannot hide ok"    ok          "$(verdict_follower 0.36.0 QUERY_FAILED 0.36.0 '' 72)"
eq "no want"                             unreachable "$(verdict_follower 0.36.0 NONE '' '' 72)"

head_ "meta — the assertions can actually fail"
# The deliberate failure runs inside $( ), i.e. a SUBSHELL — so its FAIL++ is
# lost and there is nothing to discount. An earlier draft decremented anyway,
# which meant a suite with exactly one REAL failure reported zero and exited
# green. A harness that can hide a failure is worse than no harness.
_r=$(eq "deliberate failure" ok bad 2>&1); case "$_r" in
    *"expected 'ok', got 'bad'"*) ok "eq() reports a real mismatch" ;;
    *) bad "eq() cannot fail — the suite is decoration" ;;
esac
[ "$FAIL" -eq 0 ] || bad "harness leaked the deliberate failure into the count"

head_ "argument validation — the fold reads the wrong transcript on a typo"
for v in "0.28.O" "../../tmp" "" "latest" "v0.28.0"; do
    out=$(bash "$ROOT/scripts/verify-channels.sh" "$v" 2>&1); rc=$?
    if [ "$rc" = "2" ]; then ok "refused '$v' (exit 2)"
    else bad "accepted '$v' (exit $rc) — should be a usage error"; fi
done
out=$(bash "$ROOT/scripts/verify-channels.sh" --bogus 2>&1); rc=$?
[ "$rc" = "2" ] && ok "refused unknown flag" || bad "accepted unknown flag (exit $rc)"

# ---------------------------------------------------------------------------
head_ "the DRIVER, not just its verdicts — the half the LIB seam cannot see"
# --abandoned was structurally broken for as long as the channel loop has
# existed: probe_website assigned SITE_BODY inside a command substitution, so
# the row that rides that body always said "changelog not fetched". Every
# assertion above passed throughout — the bug lived below the seam, which is
# the argument for this section existing at all.
# ---------------------------------------------------------------------------
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT INT TERM
mkdir -p "$WORK/repo/scripts" "$WORK/bin"
cp "$ROOT/scripts/verify-channels.sh" "$ROOT/scripts/project.conf" "$WORK/repo/scripts/"

# One stub for every network dependency. The changelog body is the only thing
# these tests actually vary; the rest just have to be well-formed enough that
# the run reaches the rollup.
cat > "$WORK/bin/curl" <<'CURL'
#!/bin/sh
for a in "$@"; do case "$a" in
  *changelog*) cat "$BN_FAKE_CHANGELOG"; exit 0 ;;
  *snapcraft*) echo '{"channel-map":[{"channel":{"name":"edge"},"version":"9.9.9"}]}'; exit 0 ;;
  *copr*) echo '{"items":[{"state":"'"${BN_FAKE_COPR_STATE:-succeeded}"'","source_package":{"version":"'"${BN_FAKE_COPR_VER:-9.9.9-1}"'"}}]}'; exit 0 ;;
  *.dmg.sha256) [ -n "${BN_FAKE_DMG_SHA:-}" ] && { echo "$BN_FAKE_DMG_SHA"; exit 0; }; exit 22 ;;
  *dmg*) printf 'HTTP/2 302
location: https://x/Bristlenose-9.9.9.dmg
'; exit 0 ;;
  *Formula/*) echo 'url "https://files.pythonhosted.org/x/bristlenose-9.9.9.tar.gz"'; exit 0 ;;
  *pypi*) case " $* " in *" -w "*) printf '200' ;; esac; exit 0 ;;
esac; done
exit 0
CURL
cat > "$WORK/bin/gh" <<'GH'
#!/bin/sh
# winget-pkgs reads, driven by env. BN_FAKE_WINGET_SERVED: version folders
# (space-separated), 404, or FAIL. BN_FAKE_WINGET_PRS: the PR-list JSON, or FAIL.
case "$1" in
  api) case "${BN_FAKE_WINGET_SERVED:-404}" in
         404)  echo 'gh: Not Found (HTTP 404)' >&2; exit 1 ;;
         FAIL) echo 'gh: error connecting to api.github.com' >&2; exit 1 ;;
         *)    printf '%s\n' $BN_FAKE_WINGET_SERVED; exit 0 ;;
       esac ;;
  pr)  case "${BN_FAKE_WINGET_PRS:-[]}" in
         FAIL) exit 1 ;;
         *)    printf '%s' "${BN_FAKE_WINGET_PRS:-[]}"; exit 0 ;;
       esac ;;
esac
echo v9.9.9
GH
chmod +x "$WORK/bin/curl" "$WORK/bin/gh"

verify() { ( cd "$WORK/repo" && PATH="$WORK/bin:$PATH" BN_FAKE_CHANGELOG="$WORK/changelog" \
             bash scripts/verify-channels.sh "$@" ) 2>&1; }

printf '9.9.9 released\n9.8.0 before it\n' > "$WORK/changelog"

# THE ROW, not the whole output. A `case "$out" in *"✗"*"gone"*)` glob matches a
# ✗ printed by any earlier row, so three of these four assertions passed against
# the broken script on their first draft — the substring trap this file's own
# _token_present tests are about, committed in the test that was checking for it.
gone_row() { printf '%s' "$1" | sed 's/\x1b\[[0-9;]*m//g' | grep 'gone' | head -1; }

out=$(verify 9.9.9 --abandoned 9.8.0)
case "$(gone_row "$out")" in
    *"changelog not fetched"*) bad "--abandoned still cannot see the fetched body" ;;
    *) ok "--abandoned reads the body the website probe fetched" ;;
esac
case "$(gone_row "$out")" in
    *✗*) ok "an abandoned version still on the page is caught" ;;
    *)   bad "did not catch a present abandoned version: $(gone_row "$out")" ;;
esac

printf '9.9.9 released\n' > "$WORK/changelog"
out=$(verify 9.9.9 --abandoned 9.8.0)
case "$(gone_row "$out")" in
    *✓*) ok "and clears once the entry is gone" ;;
    *)   bad "did not clear: $(gone_row "$out")" ;;
esac

# The Copr row. `copr` is deliberately not in CHANNELS yet (the project does not
# exist, and an unreachable row would fail every release verification until it
# does — see project.conf). So these turn it ON in the sandbox: that exercises
# probe_copr AND proves the switch works, which is the thing someone will flip
# on the day the channel goes live.
copr_row() { printf '%s' "$1" | sed 's/\x1b\[[0-9;]*m//g' | grep -i 'copr' | head -1; }
_cfg="$WORK/repo/scripts/project.conf"
_cfg_orig=$(cat "$_cfg")
_with_copr() { printf '%s\n' "${_cfg_orig/CHANNELS=\"pypi/CHANNELS=\"copr pypi}" > "$_cfg"; }

printf '9.9.9 released\n' > "$WORK/changelog"
_with_copr
grep -q 'CHANNELS="copr ' "$_cfg" && ok "the fixture actually enabled the copr channel" \
    || bad "fixture did not enable copr — the rows below prove nothing"

# Copr reports version-release ("9.9.9-1") where every other channel reports a
# bare version, so the probe has to split it. Comparing the raw field would
# read `bad` on a correct release, forever.
out=$(verify 9.9.9)
case "$(copr_row "$out")" in
    *✓*) ok "copr: version-release is compared on its version half" ;;
    *)   bad "copr row not ok for a matching build: $(copr_row "$out")" ;;
esac

out=$(BN_FAKE_COPR_VER=9.8.0-1 verify 9.9.9)
case "$(copr_row "$out")" in
    *✗*) ok "copr: a build of the WRONG version is caught" ;;
    *)   bad "copr passed on a stale build: $(copr_row "$out")" ;;
esac

# A failed build must not read as a shipped one. The probe reads the newest
# SUCCEEDED build; with none, there is nothing to report.
out=$(BN_FAKE_COPR_STATE=failed verify 9.9.9)
case "$(copr_row "$out")" in
    *✓*) bad "copr reported ok with no succeeded build: $(copr_row "$out")" ;;
    *)   ok "copr: a failed build does not read as shipped" ;;
esac

printf '%s\n' "$_cfg_orig" > "$_cfg"   # back to shipped CHANNELS for what follows

# CHANNELS_UNPROBEABLE, both directions (F44). It had no reader at all: the
# constant declared testflight unprobeable and probe_testflight independently
# hardcoded the same fact, so the two could disagree forever in silence.
printf '9.9.9 released\n' > "$WORK/changelog"
_conf="$WORK/repo/scripts/project.conf"
_orig=$(cat "$_conf")
_tf_row() { printf '%s' "$1" | sed 's/\x1b\[[0-9;]*m//g' | grep 'testflight' | head -1; }

# Declared: probe_testflight answers `skipped`, and that is accepted.
case "$(_tf_row "$(verify 9.9.9)")" in
    *—*) ok "a declared-unprobeable channel reports skipped" ;;
    *)   bad "declared unprobeable but did not report skipped: $(_tf_row "$(verify 9.9.9)")" ;;
esac

# Undeclared: the SAME probe, the same `skipped`, now with nothing declaring it.
# That is a channel excusing itself, and `skipped` is the one verdict the rollup
# accepts as a pass — so this is the shape that reads verified while checking
# nothing, which is the defect this whole file exists for.
printf '%s\n' "${_orig//CHANNELS_UNPROBEABLE=\"testflight\"/CHANNELS_UNPROBEABLE=\"\"}" > "$_conf"
grep -q 'CHANNELS_UNPROBEABLE=""' "$_conf" && ok "the fixture actually undeclared it" \
                                           || bad "fixture edit did not take — the test below proves nothing"
case "$(_tf_row "$(verify 9.9.9)")" in
    *"not in CHANNELS_UNPROBEABLE"*) ok "an undeclared skip is caught" ;;
    *) bad "a probe excused itself unchallenged: $(_tf_row "$(verify 9.9.9)")" ;;
esac
verify 9.9.9 >/dev/null 2>&1; rc=$?
[ "$rc" = "1" ] && ok "and it fails the rollup" || bad "undeclared skip passed the rollup (exit $rc)"
printf '%s' "$_orig" > "$_conf"

# ---------------------------------------------------------------------------
head_ "followers — reported with evidence, and NEVER in the exit code"
# The reason CHANNELS_FOLLOW exists: winget on a moderator's clock would hold
# the exit code for days. So the first assertion is that the exit code is the
# same whatever the follower says, ok or bad or unreachable.
# ---------------------------------------------------------------------------
printf '9.9.9 released\n' > "$WORK/changelog"
win_row() { printf '%s' "$1" | sed 's/\x1b\[[0-9;]*m//g' | grep -E ' winget  ' | head -1; }
_now=$(python3 -c 'from datetime import datetime,timezone;print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')
# A valid digest, so every LOCKSTEP row is green and the baseline exit is 0.
# Against a baseline of 1, a follower leaking into the rollup would change
# nothing, and the exit-code assertion below could not fail.
export BN_FAKE_DMG_SHA="$(printf 'a%.0s' $(seq 64))  App-9.9.9.dmg"
_pr() { printf '[{"number":%s,"title":"Add version: Bristlenose.Bristlenose version %s","createdAt":"%s"}]' "$1" "$2" "$3"; }

out=$(BN_FAKE_WINGET_SERVED=9.9.9 verify 9.9.9); rc_ok=$?
case "$(win_row "$out")" in *"merged into"*"9.9.9"*) ok "a merged version reads ok" ;; *) bad "merged version: $(win_row "$out")" ;; esac

out=$(BN_FAKE_WINGET_PRS="$(_pr 42 9.9.9 "$_now")" verify 9.9.9); rc_pend=$?
case "$(win_row "$out")" in *"PR #42 for 9.9.9 open 0h of a 72h budget"*"nothing yet"*) ok "an open PR for the version reads pending, with its number" ;;
                            *) bad "pending: $(win_row "$out")" ;; esac
case "$out" in *"following: winget pending"*) ok "and the summary line says so" ;; *) bad "no follower summary line" ;; esac

out=$(BN_FAKE_WINGET_PRS="$(_pr 42 9.9.9 2020-01-01T00:00:00Z)" verify 9.9.9); rc_over=$?
case "$(win_row "$out")" in *"past the 72h budget"*) ok "an old open PR reads overdue" ;; *) bad "overdue: $(win_row "$out")" ;; esac

out=$(BN_FAKE_WINGET_PRS="$(_pr 43 9.9.10 "$_now")" verify 9.9.9); rc_sup=$?
case "$(win_row "$out")" in *"9.9.9 never landed; PR #43 for 9.9.10"*) ok "a newer version in flight reads superseded (numeric, not lexical)" ;;
                            *) bad "superseded: $(win_row "$out")" ;; esac

out=$(verify 9.9.9); rc_bad=$?
case "$(win_row "$out")" in *"no open PR for 9.9.9"*) ok "nothing merged and nothing submitted reads bad" ;; *) bad "bad: $(win_row "$out")" ;; esac

out=$(BN_FAKE_WINGET_SERVED=FAIL BN_FAKE_WINGET_PRS="$(_pr 42 9.9.9 "$_now")" verify 9.9.9); rc_unr=$?
case "$(win_row "$out")" in *"query failed"*) ok "a failed folder read is unreachable, even with a PR open" ;; *) bad "served FAIL: $(win_row "$out")" ;; esac
out=$(BN_FAKE_WINGET_PRS=FAIL verify 9.9.9)
case "$(win_row "$out")" in *"query failed"*) ok "a failed PR query is unreachable, not bad" ;; *) bad "PR FAIL: $(win_row "$out")" ;; esac

# A PR for a different package whose id merely CONTAINS ours must not count.
out=$(BN_FAKE_WINGET_PRS='[{"number":7,"title":"Add version: Bristlenose.BristlenoseX version 9.9.9","createdAt":"2026-01-01T00:00:00Z"}]' verify 9.9.9)
case "$(win_row "$out")" in *"no open PR"*) ok "a look-alike id is not our submission" ;; *) bad "look-alike counted: $(win_row "$out")" ;; esac

if [ "$rc_ok" = "$rc_pend" ] && [ "$rc_ok" = "$rc_over" ] && [ "$rc_ok" = "$rc_sup" ] \
   && [ "$rc_ok" = "$rc_bad" ] && [ "$rc_ok" = "$rc_unr" ]; then
    ok "the exit code is the same for every follower verdict ($rc_ok)"
else
    bad "a follower moved the exit code: ok=$rc_ok pending=$rc_pend overdue=$rc_over superseded=$rc_sup bad=$rc_bad unreachable=$rc_unr"
fi
if [ "$rc_ok" = 0 ]; then ok "and that exit code is 0: every lockstep channel green, so a leak would show"
else bad "baseline exit is $rc_ok, not 0 — the equality above cannot catch a leak"; fi

# BN_VERIFY_RESULTS: what release.sh reads to decide which after-<channel>
# holds land. One version line, a verdict per channel (followers included), a
# served line where the probe knows one, and nothing at all without the var.
_rf="$WORK/results"; rm -f "$_rf"
( cd "$WORK/repo" && PATH="$WORK/bin:$PATH" BN_FAKE_CHANGELOG="$WORK/changelog" BN_FAKE_WINGET_SERVED="9.9.8 9.9.9" \
  BN_VERIFY_RESULTS="$_rf" bash scripts/verify-channels.sh 9.9.9 ) >/dev/null 2>&1
eq "results: the version"          "9.9.9"  "$(awk -F'\t' '$1=="version"{print $2}' "$_rf")"
eq "results: pypi's verdict"       "ok"     "$(awk -F'\t' '$1=="verdict"&&$2=="pypi"{print $3}' "$_rf")"
eq "results: the follower's too"   "ok"     "$(awk -F'\t' '$1=="verdict"&&$2=="winget"{print $3}' "$_rf")"
eq "results: winget serves 9.9.9"  "9.9.9"  "$(awk -F'\t' '$1=="served"&&$2=="winget"{print $3}' "$_rf")"
eq "results: no row for the digest" ""      "$(awk -F'\t' '$2==".dmg sha256"' "$_rf")"
eq "results: one line per channel" "9"      "$(awk -F'\t' '$1=="verdict"' "$_rf" | wc -l | tr -d ' ')"
rm -f "$_rf"
verify 9.9.9 >/dev/null 2>&1
[ ! -e "$_rf" ] && ok "no BN_VERIFY_RESULTS, no file" || bad "a results file appeared unasked"

# A channel in BOTH lists is a contradiction, and it must fail rather than
# silently pick one. Prove the edit took first.
_conf="$WORK/repo/scripts/project.conf"; _orig=$(cat "$_conf")
printf '%s\n' "${_orig//CHANNELS_FOLLOW=\"winget\"/CHANNELS_FOLLOW=\"winget copr\"}" > "$_conf"
grep -q 'CHANNELS_FOLLOW="winget copr"' "$_conf" && ok "the fixture listed copr in both" \
                                                || bad "fixture edit did not take — the test below proves nothing"
out=$(BN_FAKE_WINGET_SERVED=9.9.9 verify 9.9.9)
case "$out" in *"listed in both CHANNELS and CHANNELS_FOLLOW"*) ok "a channel in both lists is refused" ;; *) bad "both-lists contradiction passed silently" ;; esac
printf '%s' "$_orig" > "$_conf"
unset BN_FAKE_DMG_SHA

# The direction that matters for the exit code: a present abandoned version
# must make the whole verify fail, not merely print a red row.
printf '9.9.9 released\n9.8.0 before it\n' > "$WORK/changelog"
verify 9.9.9 --abandoned 9.8.0 >/dev/null 2>&1; rc=$?
[ "$rc" = "1" ] && ok "a present abandoned version fails the rollup" \
                || bad "rollup passed with the abandoned version still live (exit $rc)"

finish
