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
  *.dmg.sha256) exit 22 ;;
  *dmg*) printf 'HTTP/2 302
location: https://x/App-9.9.9.dmg
'; exit 0 ;;
  *pypi*) case " $* " in *" -w "*) printf '200' ;; esac; exit 0 ;;
esac; done
exit 0
CURL
cat > "$WORK/bin/gh" <<'GH'
#!/bin/sh
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

# The direction that matters for the exit code: a present abandoned version
# must make the whole verify fail, not merely print a red row.
printf '9.9.9 released\n9.8.0 before it\n' > "$WORK/changelog"
verify 9.9.9 --abandoned 9.8.0 >/dev/null 2>&1; rc=$?
[ "$rc" = "1" ] && ok "a present abandoned version fails the rollup" \
                || bad "rollup passed with the abandoned version still live (exit $rc)"

finish
