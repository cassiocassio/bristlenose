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

# A manufactured repo configures its own identity. Git guesses one from the
# hostname when none is set, and on a GitHub runner that guess yields
# `fatal: empty ident name (for <runner@runnervm...>)` — every commit below
# fails, and the failures cascade absurdly: `git rev-parse HEAD` on an unborn
# branch prints the literal "HEAD", which then equals itself, so
# verdict_tag_provenance reported `dirty` rather than anything true. 31 of 33
# assertions in the first Linux run traced to this. macOS guesses a valid name
# from the passwd record, which is why nulling the git config locally did not
# reproduce it — the suites must not depend on ambient identity at all.

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

head_ "board_link — the board is optional: one file, one line, never a failure"
_bl_root="$(mktemp -d)"; mkdir -p "$_bl_root/.release/1.2.3"
( cd "$_bl_root" && board_link 1.2.3 ); eq "no handshake → exit 0" 0 "$?"
eq "no handshake → prints nothing" "" "$(cd "$_bl_root" && board_link 1.2.3)"
printf '{"url":"http://127.0.0.1:4321/","pid":999999}' > "$_bl_root/.release/1.2.3/board-server.json"
eq "dead pid → prints nothing" "" "$(cd "$_bl_root" && board_link 1.2.3)"
# a live pid alone is not enough (pids recycle): the url's port must be the file's, and open
python3 -c 'import socket,sys,time; s=socket.socket(); s.bind(("127.0.0.1",0)); s.listen(64); open(sys.argv[1],"w").write(str(s.getsockname()[1])); time.sleep(20)' "$_bl_root/port" &
_bl_lpid=$!
for _i in 1 2 3 4 5 6 7 8 9 10; do [ -s "$_bl_root/port" ] && break; sleep 0.2; done
_bl_port="$(cat "$_bl_root/port" 2>/dev/null)"
if [ -n "$_bl_port" ]; then
    printf '{"url":"http://127.0.0.1:%s/?k=abc","pid":%s,"port":%s}' "$_bl_port" "$$" "$_bl_port" > "$_bl_root/.release/1.2.3/board-server.json"
    case "$(cd "$_bl_root" && board_link 1.2.3)" in *"http://127.0.0.1:$_bl_port/?k=abc"*) ok "live pid + open port → prints the url" ;; *) bad "live pid + open port → url not printed" ;; esac
    printf '{"url":"http://127.0.0.1:%s/","pid":%s,"port":1}' "$_bl_port" "$$" > "$_bl_root/.release/1.2.3/board-server.json"
    eq "url port ≠ file port → prints nothing" "" "$(cd "$_bl_root" && board_link 1.2.3)"
else
    ok "could not open a listener to test against (lsof/python3 absent) — skipped, not passed"
fi
kill "$_bl_lpid" 2>/dev/null
printf '{"url":"http://127.0.0.1:1/","pid":%s,"port":1}' "$$" > "$_bl_root/.release/1.2.3/board-server.json"
eq "live pid, closed port → prints nothing" "" "$(cd "$_bl_root" && board_link 1.2.3)"
printf '{"url":"http://evil.example/","pid":%s,"port":4321}' "$$" > "$_bl_root/.release/1.2.3/board-server.json"
eq "non-loopback url → prints nothing" "" "$(cd "$_bl_root" && board_link 1.2.3)"
printf 'not json' > "$_bl_root/.release/1.2.3/board-server.json"
( cd "$_bl_root" && board_link 1.2.3 ); eq "unreadable handshake → exit 0" 0 "$?"
rm -rf "$_bl_root"
# board_ensure — run --board: start a detached server if none serves; never fail the run
head_ "board_ensure — spawn, wait briefly, print, forget; never a failure"
_be_root="$(mktemp -d)"; mkdir -p "$_be_root/.release/1.2.3"
( cd "$_be_root" && RELEASE_BOARD_PY="/nonexistent/release-board.py" board_ensure 1.2.3 >"$_be_root/out" 2>&1 ); eq "generator missing → exit 0" 0 "$?"
case "$(cat "$_be_root/out")" in *"not started"*) ok "generator missing → says so, one line" ;; *) bad "generator missing → no note: $(cat "$_be_root/out")" ;; esac
cat > "$_be_root/fake-board.py" <<'PYF'
import json, os, socket, sys, time
v = sys.argv[1]; s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(64); port = s.getsockname()[1]
open(f".release/{v}/board-server.json", "w").write(json.dumps({"url": f"http://127.0.0.1:{port}/?k=t", "port": port, "pid": os.getpid(), "token": "t"}))
time.sleep(8)
PYF
( cd "$_be_root" && RELEASE_BOARD_PY="$_be_root/fake-board.py" board_ensure 1.2.3 >"$_be_root/out" 2>&1 ); eq "spawn path → exit 0" 0 "$?"
case "$(cat "$_be_root/out")" in *"board"*"http://127.0.0.1:"*"/?k=t"*) ok "spawned server's url printed within the wait" ;; *) bad "spawned url not printed: $(cat "$_be_root/out")" ;; esac
[ -f "$_be_root/.release/1.2.3/board-server.log" ] && ok "server log lands in the run dir" || bad "no board-server.log"
( cd "$_be_root" && RELEASE_BOARD_PY="$_be_root/fake-board.py" board_ensure 1.2.3 >"$_be_root/out2" 2>&1 )
eq "already serving → prints the same link, spawns nothing" "$(cat "$_be_root/out")" "$(cat "$_be_root/out2")"
pkill -f "fake-board.py 1.2.3" 2>/dev/null; rm -rf "$_be_root"
# the rehearsal: the real writers (ev_append, sink.sh, report.sh) driven through a whole
# synthetic release against the live server, with --check asserting the final model —
# guard 3 of the drift review (docs/design-release-board.md §6): the fold in two
# languages, proven equal on a run that never happened
head_ "rehearse-board.sh --check — the board reads back what the real writers wrote"
if _rb_out="$(timeout 120 bash "$ROOT/scripts/rehearse-board.sh" --check --pace 0.05 --no-stall 2>&1)"; then
    ok "rehearsal check passed: $(printf '%s\n' "$_rb_out" | grep 'check passed' | sed 's/^ *//')"
else
    bad "rehearsal check failed: $(printf '%s\n' "$_rb_out" | tail -6 | tr '\n' ' ')"
fi
# the driver's knowledge of the board is board_link + board_ensure, and nothing else
eq "release.sh names the generator exactly once (board_ensure's default)" 1 "$(grep -c 'release-board\.py' "$ROOT/scripts/release.sh")"
eq "…and only board_ensure invokes it" 1 "$(grep -c '"\$_gen" "\$_v" --serve' "$ROOT/scripts/release.sh")"
eq "build scripts never name the generator, server or handshake" 0 "$(grep -l 'release-board\.py\|board-server' "$ROOT"/desktop/scripts/*.sh 2>/dev/null | wc -l | tr -d ' ')"

head_ "verdict_act — release / rebuild / nothing"
eq "wheel moved"           release "$(verdict_act ' 5 files' '')"
eq "wheel + desktop"       release "$(verdict_act ' 5 files' ' 2 files')"
eq "desktop only"          rebuild "$(verdict_act '' ' 8 files')"
eq "nothing moved"         nothing "$(verdict_act '' '')"

head_ "verdict_signing_identity — fingerprints split what names cannot"
# The renewal-twin case is THE case: Apple cert renewal leaves two VALID
# identities with the identical common name, so exactly-one-by-name refuses
# during every renewal window and only a fingerprint pin can split the pair.
# (No expired-cert case on purpose: find-identity -v filters expiry before
# this function ever sees the list — an expired twin is untestable input.)
_ONE='  1) AAAA000000000000000000000000000000000000 "Apple Distribution: M (Z)"
  2) FFFF000000000000000000000000000000000000 "Developer ID Application: M (Z)"'
_TWINS='  1) AAAA000000000000000000000000000000000000 "Apple Distribution: M (Z)"
  2) BBBB000000000000000000000000000000000000 "Apple Distribution: M (Z)"'
_INST='  1) EEEE000000000000000000000000000000000000 "3rd Party Mac Developer Installer: M (Z)"'
eq "one match"        "ok AAAA000000000000000000000000000000000000 Apple Distribution: M (Z)" \
    "$(printf '%s\n' "$_ONE" | verdict_signing_identity "Apple Distribution")"
eq "absent type"      absent \
    "$(printf '%s\n' "$_ONE" | verdict_signing_identity "Mac Installer Distribution")"
eq "renewal twins"    "ambiguous 2" \
    "$(printf '%s\n' "$_TWINS" | verdict_signing_identity "Apple Distribution")"
eq "hash pin splits twins" "ok BBBB000000000000000000000000000000000000 Apple Distribution: M (Z)" \
    "$(printf '%s\n' "$_TWINS" | verdict_signing_identity "Apple Distribution" BBBB000000000000000000000000000000000000)"
eq "hash pin is case-insensitive" "ok BBBB000000000000000000000000000000000000 Apple Distribution: M (Z)" \
    "$(printf '%s\n' "$_TWINS" | verdict_signing_identity "Apple Distribution" bbbb000000000000000000000000000000000000)"
eq "stale pin"        pin-not-found \
    "$(printf '%s\n' "$_TWINS" | verdict_signing_identity "Apple Distribution" CCCC000000000000000000000000000000000000)"
eq "pin of the wrong type" pin-wrong-type \
    "$(printf '%s\n' "$_ONE" | verdict_signing_identity "Apple Distribution" FFFF000000000000000000000000000000000000)"
eq "name pin, unique" "ok AAAA000000000000000000000000000000000000 Apple Distribution: M (Z)" \
    "$(printf '%s\n' "$_ONE" | verdict_signing_identity "Apple Distribution" "Apple Distribution: M (Z)")"
eq "name pin cannot split twins" "ambiguous 2" \
    "$(printf '%s\n' "$_TWINS" | verdict_signing_identity "Apple Distribution" "Apple Distribution: M (Z)")"
eq "installer parses under basic-policy text" \
    "ok EEEE000000000000000000000000000000000000 3rd Party Mac Developer Installer: M (Z)" \
    "$(printf '%s\n' "$_INST" | verdict_signing_identity "3rd Party Mac Developer Installer")"
eq "empty keychain"   absent "$(printf '' | verdict_signing_identity "Apple Distribution")"

head_ "rollup_exit — held is not ready, and not an error"
eq "ready"                 0  "$(rollup_exit 0 0)"
eq "not ready"             1  "$(rollup_exit 1 0)"
eq "held beats ready"      75 "$(rollup_exit 0 1)"
eq "held beats not-ready"  75 "$(rollup_exit 1 1)"

head_ "verdict_complete — the loop ending is not the table finishing"
_CT=$(mktemp -d); EVENTS="$_CT/events.jsonl"
_TBL='one|a|plain|1m|||true
two|b|plain|1m|||true
tiertwo|c|plain|1m|2||true
three|d|soft|1m||spends|true'
printf '%s\n' \
  '{"ts":"t","run":"v","step":"one","status":"running","detail":""}' \
  '{"ts":"t","run":"v","step":"one","status":"ok","detail":""}' \
  '{"ts":"t","run":"v","step":"three","status":"skipped","detail":""}' > "$EVENTS"
eq "names the never-reached step"      "two" "$(printf '%s\n' "$_TBL" | verdict_complete)"
printf '%s\n' '{"ts":"t","run":"v","step":"two","status":"ok","detail":""}' >> "$EVENTS"
eq "silent when every step accounts"   ""    "$(printf '%s\n' "$_TBL" | verdict_complete)"
printf '%s\n' '{"ts":"t","run":"v","step":"three","status":"running","detail":""}' >> "$EVENTS"
eq "a stranded running counts missing" "three" "$(printf '%s\n' "$_TBL" | verdict_complete)"
eq "tier-2 rows are never demanded"    ""    "$(printf 'tiertwo|c|plain|1m|2||true\n' | verdict_complete)"
rm -rf "$_CT"; unset EVENTS

head_ "next_version / bump_kind — one fact, two spellings, translated both ways"
eq "patch"                 0.28.1 "$(next_version 0.28.0 patch)"
eq "minor"                 0.29.0 "$(next_version 0.28.0 minor)"
eq "major"                 1.0.0  "$(next_version 0.28.0 major)"
eq "minor resets patch"    0.29.0 "$(next_version 0.28.7 minor)"
next_version 0.28.0.1 patch >/dev/null 2>&1; eq "4-part has no successor" 1 "$?"
next_version 0.28.O  patch >/dev/null 2>&1;  eq "letter O fails"          1 "$?"
eq "recognises patch"      patch     "$(bump_kind 0.28.0 0.28.1)"
eq "recognises minor"      minor     "$(bump_kind 0.28.0 0.29.0)"
eq "recognises major"      major     "$(bump_kind 0.28.0 1.0.0)"
eq "same version"          same      "$(bump_kind 0.28.0 0.28.0)"
eq "a leap is irregular"   irregular "$(bump_kind 0.28.0 0.30.0)"
eq "backwards is irregular" irregular "$(bump_kind 0.28.0 0.27.9)"

head_ "verdict_tag_provenance — the verdict and the tag must name the same commit"
_TP=$(mktemp -d)
( cd "$_TP" && git init -q . \
  && git config user.email "suite@bristlenose.test" && git config user.name "Release Suite" \
  && echo a > f && git add -A && git commit -qm one ) 2>/dev/null
CI_SHA_FILE="$_TP/ci-sha"
eq "no recorded sha"        no-sha "$(cd "$_TP" && CI_SHA_FILE="$_TP/ci-sha" verdict_tag_provenance)"
( cd "$_TP" && git rev-parse HEAD > ci-sha )
eq "HEAD matches, clean"    ok     "$(cd "$_TP" && CI_SHA_FILE="$_TP/ci-sha" verdict_tag_provenance)"
( cd "$_TP" && echo b >> f )
eq "HEAD matches, dirty"    dirty  "$(cd "$_TP" && CI_SHA_FILE="$_TP/ci-sha" verdict_tag_provenance)"
( cd "$_TP" && git add -A && git commit -qm two )
eq "HEAD moved past verdict" moved "$(cd "$_TP" && CI_SHA_FILE="$_TP/ci-sha" verdict_tag_provenance)"
rm -rf "$_TP"; unset CI_SHA_FILE

head_ "ev_append — every detail must survive as valid JSON"
_EA=$(mktemp -d); EVENTS="$_EA/events.jsonl"; V=9.9.9
ev_append q ok 'id="Dev ID" path=C:\Users and a
newline'
ev_append b ok "$(printf 'x%.0s' $(seq 1 159))✓boundary-multibyte"
ev_append u ok '✓ archivé → café'
_bad=$(python3 -c '
import json,sys
bad=0
for l in open(sys.argv[1],encoding="utf-8"):
    try: json.loads(l)
    except Exception: bad+=1
print(bad)' "$EVENTS")
eq "0 unparseable lines (quotes, backslash, newline, split multibyte)" 0 "$_bad"
grep -q 'Dev ID' "$EVENTS" && ok "quotes escaped, not stripped" \
                           || bad "quote content was mutilated away"
rm -rf "$_EA"; unset EVENTS

head_ "write_context — an allowlist, and it must stay one"
_WC=$(mktemp -d)
write_context "$_WC" >/dev/null
_ck=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
want={"SIGN_IDENTITY","SIGN_IDENTITY_APPSTORE","SIGN_IDENTITY_DEVELOPER_ID",
      "TEAM_ID","NOTARY_PROFILE","NOTARY_ZIP"}
got=set(d["env"])
print("ok" if got==want else "drift:%s" % sorted(got.symmetric_difference(want)))
' "$_WC/context.json" 2>&1)
eq "context.json parses and env is EXACTLY the allowlist" ok "$_ck"
rm -rf "$_WC"

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

# plan's OUTPUT is asserted below, so plan must actually render its table — but
# on the real repo, right after a release, HEAD is at (or docs-only past) the
# tag, and plan legitimately short-circuits with NOTHING SHIPPABLE: exit 1, no
# table, and five assertions here go red. That happened the morning v0.28.0
# shipped — a suite that is red after every successful release is a gate that
# cries wolf. So plan runs in a sandbox whose git state is ALWAYS shippable
# (same isolation pattern as test-release-e2e.sh's fresh()); the real repo is
# still used below for everything with no shippability dependence.
_PLANREPO=$(mktemp -d)
trap 'rm -rf "$_PLANREPO"' EXIT
mkdir -p "$_PLANREPO/scripts" "$_PLANREPO/bristlenose"
cp "$ROOT/scripts/release.sh" "$_PLANREPO/scripts/"
cp "$ROOT/scripts/project.conf" "$_PLANREPO/scripts/"
( cd "$_PLANREPO" && git init -q . \
  && git config user.email "suite@bristlenose.test" && git config user.name "Release Suite" \
  && echo a > bristlenose/x && git add -A && git commit -qm base \
  && git tag v0.0.1 \
  && echo b > bristlenose/y && git add -A && git commit -qm ship ) 2>/dev/null
plan_sandboxed() { bash "$_PLANREPO/scripts/release.sh" plan "$@"; }

head_ "tier filtering — a Tier 2 step must not inflate a Tier 1 estimate"
t1=$(plan_sandboxed 0.28.0 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
t2=$(plan_sandboxed 0.28.0 --tier 2 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
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
# Bare run now INFERS the next minor and prompts — the confirmation is
# mandatory for a fully inferred version, so with stdin closed it must die
# at the prompt having done nothing. Run in the sandbox (version-stable:
# v0.0.1 → 0.1.0), and NEVER without </dev/null: with stdin open this read
# blocks forever, which is how this very test hung the suite on 28 Aug 2026.
( cd "$_PLANREPO" && bash scripts/release.sh run </dev/null >/dev/null 2>&1 )
eq "bare run dies at the mandatory prompt" 2 "$?"
[ -d "$_PLANREPO/.release/0.1.0" ] && bad "a declined bare run left a run dir" \
                                   || ok "declined bare run left nothing"
bash "$ROOT/scripts/release.sh" plan 0.28.O >/dev/null 2>&1
eq "malformed version exit 2" 2 "$?"
bash "$ROOT/scripts/release.sh" bogus >/dev/null 2>&1
eq "unknown command exit 2" 2 "$?"
plan_sandboxed 0.28.0 >/dev/null 2>&1
eq "plan on a shippable tree exit 0" 0 "$?"
out=$(bash "$ROOT/scripts/release.sh" status 2>&1)
case "$out" in
    *$'\n0'*|"0"*) bad "status leaks a bare exit code into its output" ;;
    *)             ok "status output carries no stray value" ;;
esac

head_ "width — REPORT-STYLE.md budget"
overlong=$(plan_sandboxed 0.28.0 2>&1 \
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
# Both `run` cases below drive the real driver with a SYNTHETIC step table.
# Without it they reach the credential block, which resolves Apple identities and
# probes codesign/notarytool/gh/ssh — so on this Mac they passed using the
# maintainer's real certificates (and fired real keychain probes on every run),
# and on CI's ubuntu they died at exit 2 with no certificates at all.
#
# That made "wrong confirmation aborts" pass on Linux for the WRONG REASON: it
# expects 2 from the confirmation mismatch and got 2 from the missing
# credentials. And it made the stranded-step case below fail outright, expecting
# 3 and getting the same 2. Neither is testing credentials; both are testing the
# resume machinery above them.
_SYNTH_TBL="$ROOT/.release/.synthetic-steps.tbl"
mkdir -p "$ROOT/.release"
cat > "$_SYNTH_TBL" <<'SYNTH'
preflight|preflight|plain|1m|||true
bump|bump + commit|plain|1m|||true
push-main|push main|plain|1m|||true
strict-ci|dispatch strict CI|plain|1m|||true
build-all|build the app|plain|1m|||true
SYNTH

echo "not-the-version" | RELEASE_STEPS_FILE="$_SYNTH_TBL" bash "$ROOT/scripts/release.sh" run "$_decl" --bump minor >/dev/null 2>&1
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
# Step ids match the synthetic events written above, so "skipped (done)" and the
# stranded report are about the same steps the log names.
_out=$(echo "9.9.9" | RELEASE_STEPS_FILE="$_SYNTH_TBL" bash "$ROOT/scripts/release.sh" run 9.9.9 --bump patch 2>&1)
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
# TestFlight's arm shells to desktop/scripts/upload-testflight.sh --probe,
# resolved RELATIVE to cwd — so these run from a temp cwd with a stub at that
# path, never the real script (which would call live ASC from a unit test).
# The 0/1/3 mapping is load-bearing: 1 re-runs the upload on resume and
# spends a build number; 3 stops and asks. An unexpected stub exit is 3.
_PDT=$(mktemp -d); mkdir -p "$_PDT/desktop/scripts"
_pdt_stub() { printf '#!/bin/sh\nexit %s\n' "$1" > "$_PDT/desktop/scripts/upload-testflight.sh"
              chmod +x "$_PDT/desktop/scripts/upload-testflight.sh"; }
_pdt_run()  { ( cd "$_PDT" && V=0.28.0 probe_done testflight ); echo $?; }
rm -f "$_PDT/desktop/scripts/upload-testflight.sh"
eq "no script on disk = could not look (3)"   3 "$(_pdt_run)"
_pdt_stub 0; eq "ASC holds the build = done (0)"          0 "$(_pdt_run)"
_pdt_stub 1; eq "ASC lacks the build = absent (1)"        1 "$(_pdt_run)"
_pdt_stub 3; eq "probe could not look = unprobeable (3)"  3 "$(_pdt_run)"
_pdt_stub 7; eq "an unexpected exit is 3, never absent"   3 "$(_pdt_run)"
rm -rf "$_PDT"
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
_p=$(plan_sandboxed 0.28.0 2>&1 | sed 's/\x1b\[[0-9;]*m//g')
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
( cd "$_W/repo" && git init -q . \
  && git config user.email "suite@bristlenose.test" && git config user.name "Release Suite" \
  && git commit -q --allow-empty -m init && git tag v1.0.0 ) 2>/dev/null
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
