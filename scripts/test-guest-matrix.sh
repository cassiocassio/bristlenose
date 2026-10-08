#!/usr/bin/env bash
# test-guest-matrix.sh — the overnight macOS-guest runner says what happened.
#
#     bash scripts/test-guest-matrix.sh
#
# desktop/scripts/guest-matrix.sh's whole product is one morning line, so the
# failures that matter are lines that lie: a green for a guest that never
# reported, a run on battery, a run under a live release, a night marked tested
# when a guest timed out, a silent night that reads as a quiet one. Each is a
# case here, driven end to end against the real script with fake `tart`,
# `pmset`, `sysctl` and `ps` on PATH, inside a throwaway git repo. No VM, no
# Xcode, no Iona.
#
# GM_SCRIPT points at the script under test, so a mutant can be run through the
# same cases to prove the suite goes red (§3.7 records the mutants tried).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$(dirname "$0")/test-lib.sh"
GM="${GM_SCRIPT:-$ROOT/desktop/scripts/guest-matrix.sh}"

W="$(mktemp -d)"
BGPIDS=""
trap 'for p in $BGPIDS; do kill "$p" 2>/dev/null; done; rm -rf "$W"' EXIT
REPO="$W/repo"; BIN="$W/bin"; IONA="$W/iona"; ST="$W/state"; CL="$W/claude"
mkdir -p "$REPO/desktop/Bristlenose" "$REPO/bristlenose" "$REPO/scripts" "$BIN" "$CL"
cp "$ROOT/scripts/lib-release-state.sh" "$REPO/scripts/"
printf '__version__ = "1.0.0"\n' > "$REPO/bristlenose/__init__.py"
printf 'one\n' > "$REPO/desktop/Bristlenose/App.swift"
printf 'readme\n' > "$REPO/README.md"
gitc() { git -C "$REPO" -c user.email=t@t -c user.name=t "$@"; }
git -C "$REPO" init -q && git -C "$REPO" add -A && gitc commit -qm init && gitc tag v1.0.0 \
    || { bad "could not build the fixture repo"; finish; exit 1; }

# --- fakes -------------------------------------------------------------------
cat > "$BIN/pmset" <<'EOF'
#!/bin/bash
echo "Now drawing from '${FAKE_POWER:-AC Power}'"
EOF
cat > "$BIN/sysctl" <<'EOF'
#!/bin/bash
echo "{ 1.00 ${FAKE_LOAD:-1.00} 1.00 }"
EOF
# `ps -axo command=` is the busy probe; `ps -p` is the release lock's, which must stay real.
cat > "$BIN/ps" <<'EOF'
#!/bin/bash
case "$*" in *"-axo command="*) printf '%s\n' "${FAKE_PS:-/sbin/launchd}"; exit 0 ;; esac
exec /bin/ps "$@"
EOF
cat > "$BIN/osascript" <<'EOF'
#!/bin/bash
echo "$*" >> "$FAKE_DIR/notified"
EOF
# tart: `run` blocks until `stop`; `exec … true` is the agent probe; `exec …
# run-in-guest.sh` replays $FAKE_DIR/guest-<vm>.out and its exit code.
cat > "$BIN/tart" <<'EOF'
#!/bin/bash
vm="${2:-}"
case "$1" in
  list) printf 'Source Name Disk Size SizeOnDisk State\n'; [ -n "${FAKE_RUNNING:-}" ] && printf 'local %s 50 20 20 running\n' "$FAKE_RUNNING"; exit 0 ;;
  run)  for a in "$@"; do vm="$a"; done; rm -f "$FAKE_DIR/stopped-$vm"
        [ -f "$FAKE_DIR/noboot-$vm" ] && exit 1
        echo "$vm" >> "$FAKE_DIR/booted"
        while [ ! -f "$FAKE_DIR/stopped-$vm" ]; do sleep 0.1; done; exit 0 ;;
  stop) touch "$FAKE_DIR/stopped-$vm"; exit 0 ;;
  exec) [ "$3" = /usr/bin/true ] && { [ -f "$FAKE_DIR/noboot-$vm" ] && exit 1; exit 0; }
        [ -f "$FAKE_DIR/hang-$vm" ] && sleep 30
        cat "$FAKE_DIR/guest-$vm.out" 2>/dev/null; exit "$(cat "$FAKE_DIR/guest-$vm.rc" 2>/dev/null || echo 0)" ;;
esac
EOF
chmod +x "$BIN"/*

reset_env() {
    rm -rf "$ST" "$IONA" "$W/fake"; mkdir -p "$IONA" "$W/fake"
    printf 'GUESTS="seq tahoe"\nTART_HOME=%s\n' "$IONA/home" > "$IONA/guest-matrix.conf"
    for vm in seq tahoe; do
        printf 'GM-OS: %s\n==> running BristlenoseTests\nSwift suite green — 1569 passed, 0 failed\nGM-RC: 0\n' \
            "$([ $vm = seq ] && echo 15.7.3 || echo 26.6.2)" > "$W/fake/guest-$vm.out"
    done
}
# gm <subcommand> [VAR=value…] — the real script, faked world, a fixed night.
gm() {
    local sub="$1"; shift
    env PATH="$BIN:$PATH" GM_REPO="$REPO" GM_IONA="$IONA" GM_STATE="$ST" GM_TART="$BIN/tart" \
        GM_CLAUDE_DIR="$CL" FAKE_DIR="$W/fake" GM_HOUR=02 GM_MINUTE=00 GM_NIGHT=2026-10-08 \
        GM_BOOT_TIMEOUT_S=5 GM_GUEST_TIMEOUT_MIN=1 GM_NO_CAFFEINATE=1 "$@" /bin/bash "$GM" $sub
}
report() { cat "$ST/reports/2026-10-08.txt" 2>/dev/null; }
has() { case "$2" in *"$1"*) echo yes ;; *) echo no ;; esac; }

meta_check

# --- the verdict cell (pure) -------------------------------------------------
head_ "one guest's verdict, read from test-swift.sh's own lines"
L="$W/g.log"
cell() { printf '%b' "$1" > "$L"; env PATH="$BIN:$PATH" GM_REPO="$REPO" /bin/bash "$GM" summarise seq "$L"; }
eq "green"            "✓ 15.7.3 1569 passed" "$(cell 'GM-OS: 15.7.3\nSwift suite green — 1569 passed, 0 failed\nGM-RC: 0\n')"
eq "red names the failing tests, not the passing ones whose names say 'failed'" \
   "✗ 15.7.3 2 failed: A.b(), Side.fit()" \
   "$(cell "GM-OS: 15.7.3\nTest case 'A.failedDeclines()' passed on 'Mac' (0.1 seconds)\nSWIFT SUITE RED — 2 failed, 1567 passed\nTest case 'Side.fit()' failed on 'Mac' (0.1 seconds)\nTest case 'A.b()' failed on 'Mac' (0.1 seconds)\nGM-RC: 1\n")"
eq "a compile break"  "✗ 15.7.3 build failed" "$(cell 'GM-OS: 15.7.3\nBUILD FAILED (xcodebuild exit 65)\nGM-RC: 3\n')"
eq "exit 0 with no green line is not green" "✗ 15.7.3 no verdict (exit 0)" "$(cell 'GM-OS: 15.7.3\nGM-RC: 0\n')"
eq "a green line with a non-zero exit is not green" "✗ 15.7.3 no verdict (exit 1)" \
   "$(cell 'GM-OS: 15.7.3\nSwift suite green — 9 passed, 0 failed\nGM-RC: 1\n')"
eq "a guest that never reported"   "✗ 15.7.3 no verdict (the guest never reported)" "$(cell 'GM-OS: 15.7.3\n')"
eq "a guest that did not boot"     "✗ seq did not boot" "$(cell 'GM-BOOT-FAILED\n')"
eq "a guest that timed out"        "✗ 15.7.3 timed out after 90 min" "$(cell 'GM-OS: 15.7.3\nGM-TIMEOUT\n')"

# --- the gates ---------------------------------------------------------------
head_ "gates: each reason is named, and all of them at once"
reset_env
eq "a clear night says go"            yes "$(has 'go: HEAD' "$(gm check)")"
eq "on battery"                       yes "$(has 'on battery' "$(gm check FAKE_POWER='Battery Power')")"
eq "an unreadable power source is not AC" yes "$(has 'cannot read the power source' "$(gm check FAKE_POWER='UPS Power')")"
touch "$CL/session.jsonl"
eq "a Claude Code session writing now" yes "$(has 'Claude Code session' "$(gm check)")"
touch -t 202001010000 "$CL/session.jsonl"
eq "…an old transcript is not a session" yes "$(has 'go:' "$(gm check)")"
eq "pytest running (as python, so by command line)" yes \
   "$(has 'busy: pytest' "$(gm check FAKE_PS='/opt/homebrew/bin/python3.12 -m pytest tests/')")"
eq "vitest running under node"        yes "$(has 'vitest' "$(gm check FAKE_PS='node /x/node_modules/vitest/vitest.mjs run')")"
eq "an editor with pytest.ini open is not a test run" yes "$(has 'go:' "$(gm check FAKE_PS='/usr/bin/vim pytest.ini')")"
eq "a sustained load"                 yes "$(has '5-min load 9.50' "$(gm check FAKE_LOAD=9.50)")"
eq "a guest already running"          yes "$(has 'already running: seq' "$(gm check FAKE_RUNNING=seq)")"
out="$(gm check FAKE_POWER='Battery Power' FAKE_LOAD=9.50)"
eq "two reasons, both reported"       yes "$(has 'on battery · busy: 5-min load' "$out")"
rm -f "$IONA/guest-matrix.conf"
eq "Iona attached, config missing"    yes "$(has 'guest-matrix.conf is missing' "$(gm check)")"
rm -rf "$IONA"
eq "Iona not attached"                yes "$(has 'Iona not attached' "$(gm check)")"
gm check >/dev/null; eq "a skip exits 3" 3 "$?"

head_ "gates: a release running or pending"
reset_env
mkdir -p "$REPO/.release/1.0.0/.lock"
printf 'sleep 30\n' > "$W/release.sh"
( cd "$W" && exec bash release.sh run ) & BGPIDS="$BGPIDS $!"; sleep 0.3
echo "$!" > "$REPO/.release/1.0.0/.lock/pid"
eq "a live release.sh run"            yes "$(has 'release 1.0.0 (pid' "$(gm check)")"
kill "$!" 2>/dev/null; wait "$!" 2>/dev/null
eq "…its driver gone, the lock is stale" yes "$(has 'go:' "$(gm check)")"
rm -rf "$REPO/.release/1.0.0/.lock"
printf '{"step":"run","status":"started"}\n{"step":"build","status":"failed"}\n' > "$REPO/.release/1.0.0/events.jsonl"
eq "a run stopped mid-way"            yes "$(has 'release 1.0.0 started and has not completed' "$(gm check)")"
printf '{"step":"run","status":"completed"}\n' >> "$REPO/.release/1.0.0/events.jsonl"
eq "…completed, it is not pending"    yes "$(has 'go:' "$(gm check)")"
rm -rf "$REPO/.release"
printf '__version__ = "1.1.0"\n' > "$REPO/bristlenose/__init__.py"
eq "a bump with no tag yet"           yes "$(has '1.1.0 is bumped but not tagged' "$(gm check)")"
printf '__version__ = "1.0.0"\n' > "$REPO/bristlenose/__init__.py"

# --- a whole night -----------------------------------------------------------
head_ "a night that runs"
reset_env
gm run GM_NO_NOTIFY=1 >/dev/null 2>&1
HEAD8="$(git -C "$REPO" rev-parse --short=8 HEAD)"
eq "both guests, one line" \
   "2026-10-08 · tested $HEAD8 (first run) · ✓ 15.7.3 1569 passed · ✓ 26.6.2 1569 passed" "$(report)"
eq "the tested commit is recorded"    "$(git -C "$REPO" rev-parse HEAD)" "$(cat "$ST/last-tested-sha" 2>/dev/null)"
eq "guests ran one after another, both stopped" "seq tahoe" "$(tr '\n' ' ' < "$W/fake/booted" | sed 's/ $//')"
eq "the guest got the committed tree as a bundle" yes "$([ -f "$IONA/share/guest-matrix/tree.bundle" ] && echo yes || echo no)"
eq "report exits 0 on green"          0 "$(gm report >/dev/null; echo $?)"
rm -f "$W/fake/booted"
gm run GM_NO_NOTIFY=1 >/dev/null 2>&1
eq "a later tick the same night does not run again" no "$([ -f "$W/fake/booted" ] && echo yes || echo no)"

head_ "the next night, nothing changed (or only outside desktop/)"
printf 'more\n' >> "$REPO/README.md"; gitc commit -qam "docs only"
gm run GM_NO_NOTIFY=1 GM_NIGHT=2026-10-09 >/dev/null 2>&1
eq "no desktop change ends the night" yes "$(has 'skipped: no desktop change since' "$(cat "$ST/reports/2026-10-09.txt" 2>/dev/null)")"
eq "…without booting anything"        no "$([ -f "$W/fake/booted" ] && echo yes || echo no)"
printf 'two\n' >> "$REPO/desktop/Bristlenose/App.swift"; gitc commit -qam "swift"
gm run GM_NO_NOTIFY=1 GM_NIGHT=2026-10-10 >/dev/null 2>&1
eq "a desktop commit runs, and says how far it came" yes \
   "$(has '(1 desktop commit since' "$(cat "$ST/reports/2026-10-10.txt" 2>/dev/null)")"

head_ "a night where a guest does not report"
reset_env
printf 'GM-OS: 26.6.2\n' > "$W/fake/guest-tahoe.out"; echo 1 > "$W/fake/guest-tahoe.rc"
gm run GM_NO_NOTIFY=1 >/dev/null 2>&1
eq "the line says so"                 yes "$(has '✗ 26.6.2 no verdict (the guest never reported)' "$(report)")"
eq "…and the commit is NOT marked tested" no "$([ -f "$ST/last-tested-sha" ] && echo yes || echo no)"
eq "report exits 1"                   1 "$(gm report >/dev/null; echo $?)"
reset_env; touch "$W/fake/noboot-seq"
gm run GM_NO_NOTIFY=1 >/dev/null 2>&1
eq "a guest that cannot boot"         yes "$(has '✗ seq did not boot' "$(report)")"
eq "…the other guest still runs"      yes "$(has '✓ 26.6.2 1569 passed' "$(report)")"
eq "…and the commit is NOT marked tested" no "$([ -f "$ST/last-tested-sha" ] && echo yes || echo no)"

head_ "a night that skips"
reset_env
gm run GM_NO_NOTIFY=1 FAKE_POWER='Battery Power' >/dev/null 2>&1
eq "the skip is written, with its reason" "2026-10-08 · skipped: on battery" "$(report)"
eq "report exits 3 on a skip"         3 "$(gm report >/dev/null; echo $?)"
gm run GM_MINUTE=00 FAKE_POWER='Battery Power' >/dev/null 2>&1
eq "a mid-night skip is not notified" no "$([ -f "$W/fake/notified" ] && echo yes || echo no)"
gm run GM_HOUR=05 GM_MINUTE=30 FAKE_POWER='Battery Power' >/dev/null 2>&1
eq "the night's last tick posts it"   yes "$(has 'on battery' "$(cat "$W/fake/notified" 2>/dev/null)")"
gm run GM_NO_NOTIFY=1 >/dev/null 2>&1
eq "a retryable skip is retried, and the run replaces it" yes "$(has '✓ 15.7.3' "$(report)")"

head_ "outside the window, and the morning with no report"
reset_env
gm run GM_HOUR=14 GM_NO_NOTIFY=1 >/dev/null 2>&1
eq "a daytime tick does nothing"      "" "$(report)"
eq "no report reads as 'never ran', not as quiet" yes \
   "$(has 'the trigger never ran' "$(gm report GM_HOUR=09)")"
eq "…and exits 4"                     4 "$(gm report GM_HOUR=09 >/dev/null; echo $?)"

finish
