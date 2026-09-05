#!/usr/bin/env bash
# rehearse-board.sh — a whole release, at fake speed, on the live board.
#
#   scripts/rehearse-board.sh [--pace SECS] [--version X.Y.Z] [--no-stall] [--keep] [--check] [--port N]
#
# Builds a throwaway root with its own .release/, a previous run to diff against,
# the real step table (run_steps) and the real desktop build scripts (copied, so
# the board can read that they report steps), starts `release-board.py --serve`
# on it, then walks the table the way release.sh does: the REAL ev_append writes
# the ledger, the REAL sink.sh writes the driver's windows, the REAL report.sh
# helpers write the build lane's steps, checks, gates and art (plain mode,
# stdout to the step's log). Nothing here touches the repo's .release/.
#
# What you should see, in order: every pane dim; the preflight fill (one warn,
# one duplicate label, one result the board has no rule for); the line advance
# with the running station pulsing; a build lane fill step by step; build-dmg
# fail, its log in the Log pane, then a retry; the heartbeat STALL — the station
# goes amber, the pill counts — and resume; CI rows; a verify with one channel
# missing and one unreachable; two clocks; the tag; run completed; and a
# confounded log that is computable and non-zero, diffing against the previous
# synthetic run. --check asserts that final model and exits non-zero otherwise.
#
# Two knobs the real chain shares: BN_HEARTBEAT_SECS (5 here, 300 for real —
# the board reads the same variable) and the sink env vars. The board is the
# thing under rehearsal; the scripts it reads from are the real ones.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PACE=2; VERSION="9.9.9"; STALL=1; KEEP=0; CHECK=0; PORT=0
while [ $# -gt 0 ]; do
    case "$1" in
        --pace) PACE="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --no-stall) STALL=0; shift ;;
        --keep) KEEP=1; shift ;;
        --check) CHECK=1; shift ;;
        --port) PORT="$2"; shift 2 ;;
        -h|--help) sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//;$d'; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"
export BN_HEARTBEAT_SECS="${BN_HEARTBEAT_SECS:-5}"

# ── the throwaway root ──────────────────────────────────────────────────────
R="$(mktemp -d "${TMPDIR:-/tmp}/bn-rehearsal-XXXXXX")"
mkdir -p "$R/scripts" "$R/docs/testing" "$R/desktop/scripts" "$R/.release"
cp "$ROOT/scripts/project.conf" "$R/scripts/"; cp "$ROOT/docs/testing/ratchet.json" "$R/docs/testing/"
cp "$ROOT/desktop/scripts/build-all.sh" "$ROOT/desktop/scripts/build-dmg.sh" "$R/desktop/scripts/" 2>/dev/null || true
PREV="9.9.8"
mkdir -p "$R/.release/$PREV"
RELEASE_LIB=1 . "$ROOT/scripts/release.sh"
. "$ROOT/desktop/scripts/sink.sh"
V="$VERSION"
# the previous run: one step the table no longer has, a verify that named one channel fewer
{ echo "# steps.tbl v1"; V="$PREV" run_steps; echo "old-step|a step that was retired|plain|1m|||true"; } > "$R/.release/$PREV/steps.tbl"
printf '{"ts":"2026-09-01T10:00:00Z","run":"%s","step":"run","status":"started","detail":""}\n{"ts":"2026-09-01T10:30:00Z","run":"%s","step":"run","status":"completed","detail":""}\n' "$PREV" "$PREV" > "$R/.release/$PREV/events.jsonl"
printf '@bn verify ts=2026-09-01T10:20:00Z run=%s status=start version=%s\n@bn row ts=2026-09-01T10:20:01Z run=%s src=verify label=pypi result=ok evidence=x\n@bn verify ts=2026-09-01T10:20:02Z run=%s status=done version=%s rollup=0 channels=1 ok=1\n' "$PREV" "$PREV" "$PREV" "$PREV" "$PREV" > "$R/.release/$PREV/bn-events.log"
sleep 0.2
RUNDIR="$R/.release/$V"; mkdir -p "$RUNDIR/logs" "$RUNDIR/.lock"
EVENTS="$RUNDIR/events.jsonl"; : > "$EVENTS"
{ echo "# steps.tbl v1"; run_steps; } > "$RUNDIR/steps.tbl"
printf 'af7e136f4af2a68df2a199ab9a0d44d220ed45c2\n' > "$RUNDIR/ci-sha"
printf '{"os":"macOS 26.6","arch":"arm64","xcode":"Xcode 26.6 Build version 17F113","python":"3.12.13","disk_free_gb":211,"git":{"sha":"af7e136f","branch":"main","dirty":false}}\n' > "$RUNDIR/context.json"
export BN_RUN_ID="$V" BN_EVENT_SINK="$RUNDIR/bn-events.log"

# ── the server ──────────────────────────────────────────────────────────────
"$PY" "$ROOT/scripts/release-board.py" "$V" --serve --with-logs --root "$R" --port "$PORT" --poll 0.3 > "$R/board-server.log" 2>&1 &
SERVER=$!
cleanup() {
    kill -INT "$SERVER" 2>/dev/null; wait "$SERVER" 2>/dev/null
    rm -rf "$RUNDIR/.lock"
    if [ "$KEEP" = 1 ]; then echo "  kept: $R"; else rm -rf "$R"; fi
}
trap cleanup EXIT
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do [ -f "$RUNDIR/board-server.json" ] && break; sleep 0.25; done
[ -f "$RUNDIR/board-server.json" ] || { echo "the board server did not start — $R/board-server.log:"; cat "$R/board-server.log"; exit 1; }
URL="$(jq -r .url "$RUNDIR/board-server.json")"; TOKEN="$(jq -r .token "$RUNDIR/board-server.json")"; BPORT="$(jq -r .port "$RUNDIR/board-server.json")"
echo
echo "  rehearsal $V  ·  root $R"
echo "  board  $URL"
echo "  open it now; the run starts in 3 s and takes about $(awk -v p="$PACE" -v s="$STALL" -v h="$BN_HEARTBEAT_SECS" 'BEGIN{printf "%d", p*14 + s*3*h + 4}')s"
echo
sleep 3

# ── the driver, imitated with the real writers ──────────────────────────────
NOW() { date -u +%Y-%m-%dT%H:%M:%SZ; }
heartbeat() { printf '%s\t%s\t%s\t%s\n' "$(date +%s)" "$1" "${2:-0}" "${3:-}" > "$RUNDIR/heartbeat"; }
echo $$ > "$RUNDIR/.lock/pid"
_attempt=1
ev_append run started "bump=minor"
sink_line_or_die run status=start attempt="$_attempt" proto=1 || { echo "sink refused"; exit 1; }
say() { printf '  %-12s %s\n' "$1" "$2"; }

step_start() { # <id> <attempt>
    ev_append "$1" running "attempt $2"; sink_line step id="$1" attempt="$2" status=start; heartbeat "$1" 0 "starting $1"
    STEP_T0=$(date +%s); : > "$RUNDIR/logs/$1.$2.log"
}
step_end() { # <id> <attempt> <rc> [detail]
    local el=$(( $(date +%s) - STEP_T0 )); sink_line step id="$1" attempt="$2" status=end rc="$3" elapsed="$el"
    if [ "$3" = 0 ]; then ev_append "$1" ok "${el}s"; say "$1" "ok · ${el}s"; else ev_append "$1" fail "exit $3"; say "$1" "FAIL · exit $3"; fi
}

# preflight: the real gate's row shape, with the three things the drift guard exists for
step_start preflight 1
sleep "$PACE"
for r in "branch|ok|main" "working tree|ok|clean" "untracked|warn|1 file(s) — decide, don't ignore" "venv python|ok|3.12 matches .tool-versions" \
         "dependency drift|ok|0 new" "dependency drift (age)|ok|3 days" "PyPI|ok|$V not yet published" "publish gate|ok|ci → build → publish" \
         "CI status|ok|success" "ruff|ok|clean" "man page .TH|ok|$V" "providers live|meh|a result the board has no rule for"; do
    IFS='|' read -r lbl res ev <<< "$r"; sink_line row src=preflight label="$lbl" result="$res" evidence="$ev"
    echo "  ✓ $lbl — $ev" >> "$RUNDIR/logs/preflight.1.log"
done
sink_line frobnicate ts_note="an event kind the board has no rule for" widget=7
step_end preflight 1 0

for s in bump push-main strict-ci; do step_start "$s" 1; sleep "$PACE"; echo "did $s" >> "$RUNDIR/logs/$s.1.log"; step_end "$s" 1 0; done

# build-all: the real report.sh helpers, plain mode, stdout to the step log — exactly what the driver captures
step_start build-all 1
(
    export BN_REPORT=0; _bn_owner=1; export _BN_ACTIVE=1
    . "$ROOT/desktop/scripts/report.sh"
    bn_meta title="Build the app" bundle="Bristlenose.app"
    n=0
    for st in "Pre-flight|1|Pre-flight checks" "Sidecar|2|Build the Python sidecar" "Sidecar|3|Sign 224 Mach-Os" "Archive|4|xcodebuild archive" "Export|5|Export and notarise"; do
        IFS='|' read -r phase id name <<< "$st"; n=$((n+1))
        bn_step_start "$id" "$phase" "$name"; heartbeat build-all "$n" "$name"
        sleep "$PACE"
        [ "$id" = 1 ] && { bn_check 1 ok "logging hygiene" "clean"; bn_check 1 ok "appearance seam" "1 site"; bn_check 1 warn "bundle manifest" "1 unreferenced data dir"; }
        [ "$id" = 3 ] && bn_bar 3 224 224
        bn_step_ok "$id" elapsed="$PACE" detail="fine"
    done
    bn_gate staple ok "Notarisation staple" "stapled"
    bn_gate spctl ok "Gatekeeper assessment" "accepted"
    bn_art app "build/export/Bristlenose.app"
    bn_art signed "Developer ID Application: Rehearsal Person (ABCDE12345)"
    bn_meta done_title="✓ Bristlenose.app notarised and stapled"
    bn_done ok
) >> "$RUNDIR/logs/build-all.1.log" 2>&1
step_end build-all 1 0

# build-dmg: fails once (its log fills the Log pane), then a retry succeeds and writes the dmg clock
step_start build-dmg 1; sleep "$PACE"
printf 'hdiutil: create failed - Resource busy\nerror: could not attach the staging image\n' >> "$RUNDIR/logs/build-dmg.1.log"
step_end build-dmg 1 1
sleep "$PACE"
step_start build-dmg 2; sleep "$PACE"
echo "created Bristlenose-$V.dmg" >> "$RUNDIR/logs/build-dmg.2.log"
sink_line clock name=dmg version="$V" built="$(NOW)" commit=af7e136f
step_end build-dmg 2 0

# ci-green: a long wait — the heartbeat stalls here if asked, and the status rows land
step_start ci-green 1
if [ "$STALL" = 1 ]; then
    say "ci-green" "running · the heartbeat now STALLS for $(( 3 * BN_HEARTBEAT_SECS + 2 ))s — watch the station go amber"
    sleep $(( 3 * BN_HEARTBEAT_SECS + 2 ))
    say "ci-green" "heartbeat resumes"
fi
heartbeat ci-green "$PACE" "gh run watch 33421589462"
SHA="$(cat "$RUNDIR/ci-sha")"
sink_line ci workflow=ci.yml sha="$SHA" run_id=33421589462 result=success
for os in macos ubuntu; do for py in 3.10 3.11 3.12 3.13 3.14; do
    res=success; [ "$os$py" = "ubuntu3.14" ] && res=in_progress
    sink_line ci workflow=ci.yml sha="$SHA" run_id=33421589462 job="test ($py, $os-latest)" result="$res"
done; done
for j in ruff lint e2e release-suites; do sink_line ci workflow=ci.yml sha="$SHA" run_id=33421589462 job="$j" result=success; done
sleep "$PACE"; step_end ci-green 1 0

# testflight + dmg + tag: the irreversible three, with the testflight clock
step_start testflight 1; sleep "$PACE"
sink_line clock name=testflight build=3099 expires="$(date -u -v+90d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '+90 days' +%Y-%m-%dT%H:%M:%SZ)" confirmed=1
step_end testflight 1 0
step_start dmg 1; sleep "$PACE"; step_end dmg 1 0
step_start tag 1; sleep "$PACE"; step_end tag 1 0

# verify: one channel missing (website), one unreachable (copr), the rest ok
sink_line verify status=start version="$V"
n=0
for ch in pypi github homebrew testflight dmg snap copr; do
    n=$((n+1)); res=ok; ev="HTTP 200"; [ "$ch" = copr ] && { res=unreachable; ev="timed out"; }; [ "$ch" = testflight ] && { res=skipped; ev="no probe from this machine"; }
    sink_line row src=verify label="$ch" result="$res" evidence="$ev"; sleep 0.2
done
sink_line verify status=done version="$V" rollup=1 channels=7 ok=5
ev_append run completed ""
rm -rf "$RUNDIR/.lock"
say "run" "completed"
echo

# ── the check: the final model must show what the rehearsal wrote ───────────
if [ "$CHECK" = 1 ]; then
    sleep 1
    curl -s "http://127.0.0.1:$BPORT/board.json?k=$TOKEN" > "$R/final.json" || { echo "check: board.json unreachable"; exit 1; }
    "$PY" - "$R/final.json" <<'PYEOF'
import json, sys
m = json.load(open(sys.argv[1]))
st = {s["id"]: s["state"] for s in m["line"]["stations"]}
bad = []
def want(cond, what):
    if not cond: bad.append(what)
want(m["phase"] == "completed", f"phase {m['phase']}")
want(st.get("build-dmg") == "ok" and next(s for s in m["line"]["stations"] if s["id"] == "build-dmg")["attempt"] == 2, "build-dmg ok on attempt 2")
want(m["preflight"]["state"] == "data" and len(m["preflight"]["rows"]) >= 12, f"preflight rows {len(m['preflight']['rows'])}")
lanes = {l["id"]: l for l in m["build"]["lanes"]}
want(lanes["build-all"]["state"] == "data" and len(lanes["build-all"]["steps"]) == 5, "build-all lane 5 steps")
want(len(lanes["build-all"]["checks"]) == 3 and len(lanes["build-all"]["gates"]) == 2, "3 checks, 2 gates")
want(not any("ABCDE12345" in json.dumps(a) for a in lanes["build-all"]["arts"]), "team id scrubbed from art")
want(lanes["build-dmg"]["state"] == "ran-no-sink" and lanes["build-dmg"]["source_emits"] is False, "build-dmg lane: ran, source does not report")
want(m["ci"]["state"] == "data" and len(m["ci"]["matrix"]) == 10, f"ci matrix {len(m['ci'].get('matrix', []))}")
cards = {c["name"]: c["state"] for c in m["channels"]["cards"]}
want(cards.get("copr") == "unreachable" and cards.get("website") == "no-data" and m["channels"]["complete"], f"channels {cards}")
want({k["name"] for k in m["clocks"]} == {"dmg", "testflight"}, f"clocks {[k['name'] for k in m['clocks']]}")
c = m["confounded"]
want(c["computable"] and c["count"] >= 4, f"confounded computable={c['computable']} count={c['count']}")
want(any("frobnicate" in u["what"] for u in c["unknown"]), "unknown kind listed")
want(any("meh" in n["what"] for n in c["new_shape"]), "unknown result listed")
want(any("website" in x["what"] for x in c["missing"]), "missing channel listed")
want(any("old-step" in x["what"] for x in c["changed"]), "retired step listed as changed")
want(lanes["build-dmg"].get("log", {}).get("attempts") == 2, "build-dmg lane names its second log")   # ended ok on the retry: the log is the lane's, not the failed-step list's
if bad:
    print("  check FAILED:"); [print("   -", b) for b in bad]; sys.exit(1)
print(f"  check passed: completed · {len(m['preflight']['rows'])} preflight rows · build-all {len(lanes['build-all']['steps'])} steps · ci {len(m['ci']['matrix'])} cells · channels {len(cards)} · clocks {len(m['clocks'])} · confounded {c['count']}")
PYEOF
    exit $?
fi
echo "  the board stays up so you can look; press Enter (or ^C) to stop it"
read -r _ </dev/tty 2>/dev/null || sleep 600
