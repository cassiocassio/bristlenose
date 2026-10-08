#!/bin/bash
# guest-matrix.sh — the Swift suite on every supported macOS, overnight, in tart guests.
#
# The owner's ask (8 Oct 2026): on nights the Mac is otherwise idle, run the
# Swift suite in a local guest per supported macOS, and have one line waiting in
# the morning — "still cool on all the old macOS versions", or which test broke
# on which version. On nights a big agent goal is running, stay out of its way.
# Design and history: docs/design-test-environments.md §3.7.
#
#   guest-matrix.sh check     print the gates' verdict now; exit 0 = would run
#   guest-matrix.sh run       the nightly job (launchd ticks it every 30 min)
#   guest-matrix.sh run --now run outside the night window (still gated)
#   guest-matrix.sh report    print last night's line; exit 0 green, 1 red,
#                             3 skipped, 4 no report (the trigger never ran)
#   guest-matrix.sh behind    change commits at HEAD no full run has tested
#   guest-matrix.sh install   load the LaunchAgent (uninstall removes it)
#
# WHEN IT RUNS — every gate must pass, and a failing gate is a REASON in the
# morning line, never silence:
#   - inside the night window (23:00–06:00 by default);
#   - desktop/ changed since the commit the last full run tested;
#   - on AC power (a sleeping Mac runs nothing; `pmset repeat wake` is the
#     owner's to set — see §3.7);
#   - no release running or pending (scripts/lib-release-state.sh, shared with
#     the pre-commit freeze);
#   - idle: no Claude Code transcript written in the last 15 min, no
#     xcodebuild/pytest/vitest/playwright running, 5-min load under the limit;
#   - Iona attached, its config present, and no guest already running.
# A retryable reason (busy, battery, Iona) is re-asked on the next tick, so a
# goal that finishes at 01:00 still gets a run by 01:30. "No desktop change" is
# decisive and ends the night. The last tick of the night posts the skip as a
# notification, so a quiet morning is never ambiguous.
#
# WHAT IT TESTS: the COMMITTED HEAD, shipped into each guest as a git bundle —
# never the working tree, which a concurrent session may be half-way through.
# Guests run one after another (two macOS guests is the licence and the
# Virtualization.framework ceiling, and one keeps the host usable).
#
# Machine specifics stay on the drive, not in this public tree: the VM names and
# TART_HOME come from $GM_IONA/guest-matrix.conf (§3.7 has the shape).
#
# Written for /bin/bash 3.2, deliberately: that is what launchd and a clean guest
# give you, and test-swift.sh once exited 0 without building under it.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${GM_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
GM_IONA="${GM_IONA:-/Volumes/Iona/tart}"
STATE="${GM_STATE:-$HOME/Library/Logs/bristlenose-guest-matrix}"
TART="${GM_TART:-$HOME/bin/tart}"
CLAUDE_DIR="${GM_CLAUDE_DIR:-$HOME/.claude/projects}"
# One tick's minutes, and the quiet a goal must show before we count it as over.
GM_QUIET_MIN="${GM_QUIET_MIN:-15}"
GM_MAX_LOAD="${GM_MAX_LOAD:-4}"
GM_WINDOW_START="${GM_WINDOW_START:-23}"
GM_WINDOW_END="${GM_WINDOW_END:-6}"
# Per guest: boot, clone, a full unsigned compile and the suite. Measured 8 Oct
# 2026: about 5 min each (15.7.3 and 26.6.2, 1811 tests). 30 is six times that,
# room for a slow night without letting a hang eat it.
GM_GUEST_TIMEOUT_MIN="${GM_GUEST_TIMEOUT_MIN:-30}"
GM_GUEST_TIMEOUT_S="${GM_GUEST_TIMEOUT_S:-$((GM_GUEST_TIMEOUT_MIN * 60))}"
GM_BOOT_TIMEOUT_S="${GM_BOOT_TIMEOUT_S:-300}"
GM_POLL_S="${GM_POLL_S:-10}"
# How long `tart stop` gets before the VM process is killed outright. A stop that
# never returns would otherwise hold the lock and keep the Mac awake for good.
GM_STOP_TIMEOUT_S="${GM_STOP_TIMEOUT_S:-90}"
# What counts as a change worth a night. The Swift suite reads the locale JSON
# (I18nTests), so a locale edit can turn it red with nothing under desktop/.
CHANGE_PATHS="desktop/ bristlenose/locales/"

. "$REPO/scripts/lib-release-state.sh"

die() { echo "guest-matrix: $*" >&2; exit 2; }

hour() { local h="${GM_HOUR:-$(date +%H)}"; echo $((10#$h)); }
# The night is named for its evening: 02:00 on the 9th belongs to the 8th.
night() { echo "${GM_NIGHT:-$(date -v-12H +%F)}"; }
# What this run's report and logs are filed under. A `run --now` outside the
# window is a TRIAL, filed under its own name: filed under the night, it would
# overwrite the morning's line, or (filed under today) be read at 23:00 as a
# finished night and cancel the scheduled run (found by review, 8 Oct 2026).
RUN_NAME=""
run_name() {
    [ -n "$RUN_NAME" ] || RUN_NAME="$(night)"
    echo "$RUN_NAME"
}
in_window() {
    local h; h="$(hour)"
    [ "$h" -ge "$GM_WINDOW_START" ] || [ "$h" -lt "$GM_WINDOW_END" ]
}
# The last tick before the window closes (launchd ticks on :00 and :30).
last_tick() {
    local h m; h="$(hour)"; m="${GM_MINUTE:-$(date +%M)}"; m=$((10#$m))
    [ "$h" -eq $((GM_WINDOW_END - 1)) ] && [ "$m" -ge 30 ]
}

# --- the gates ---------------------------------------------------------------
# Each prints a reason when it says no, and nothing when it says yes.

gate_changed() {
    local last head n
    head="$(git -C "$REPO" rev-parse --verify HEAD 2>/dev/null)" || { echo "cannot read HEAD"; return; }
    last="$(cat "$STATE/last-tested-sha" 2>/dev/null)"
    [ -n "$last" ] || return 0                        # never run: everything is new
    git -C "$REPO" merge-base --is-ancestor "$last" "$head" 2>/dev/null || return 0
    n="$(git -C "$REPO" rev-list --count "$last..$head" -- $CHANGE_PATHS)"
    [ "$n" -gt 0 ] && return 0
    # Carry the last verdict, so a red from an earlier night stays in view
    # instead of vanishing behind "nothing changed".
    local lastv; lastv="$(cat "$STATE/last-verdict" 2>/dev/null)"
    echo "no desktop change since ${last:0:8}${lastv:+ (last: $lastv)}"
}

# behind — how many change commits HEAD carries that no full run has tested.
# "never" when nothing has been tested. Read by the release preflight.
cmd_behind() {
    local last; last="$(cat "$STATE/last-tested-sha" 2>/dev/null)"
    [ -n "$last" ] || { echo never; return; }
    git -C "$REPO" merge-base --is-ancestor "$last" HEAD 2>/dev/null || { echo never; return; }
    git -C "$REPO" rev-list --count "$last..HEAD" -- $CHANGE_PATHS
}

gate_power() {
    local src
    src="$(pmset -g batt 2>/dev/null | head -1)"
    case "$src" in
        *"AC Power"*) ;;
        *"Battery Power"*) echo "on battery" ;;
        *) echo "cannot read the power source" ;;
    esac
}

gate_release() { release_engaged "$REPO"; }

gate_idle() {
    local recent procs load
    # A deliberate daytime trial from a working session would trip every one of
    # these; GM_IGNORE_IDLE=1 skips them and the morning line says it did.
    [ -n "${GM_IGNORE_IDLE:-}" ] && return 0
    recent="$(find "$CLAUDE_DIR" -name '*.jsonl' -mmin "-$GM_QUIET_MIN" 2>/dev/null | head -1)"
    [ -n "$recent" ] && { echo "a Claude Code session wrote in the last $GM_QUIET_MIN min"; return; }
    # Whole command lines, because pytest runs as `python3.12` and vitest as
    # `node`, so the executable name alone sees neither. Each name is spelled
    # with a bracket (`py[t]est`) so the pattern does not match the grep that
    # carries it — the classic self-match. A word boundary is a path separator,
    # space or `@` before, a path separator or space after — so
    # `node_modules/@playwright/test` and `node_modules/vitest/vitest.mjs` count,
    # and an editor with `pytest.ini` open does not.
    procs="$(ps -axo command= 2>/dev/null \
        | grep -oE '(^|[/ @])(xcode[b]uild|py[t]est|vi[t]est|play[w]right|swift-fronten[d]|pyinstalle[r])([ /]|$)' \
        | tr -d '/ @' | sort -u | tr '\n' ' ')"
    procs="${procs% }"
    [ -n "$procs" ] && { echo "busy: $procs running"; return; }
    # vm.loadavg is "{ 1m 5m 15m }"; the 5-minute figure ignores a single spike.
    load="$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $3}')"
    [ -n "$load" ] || { echo "cannot read the load average"; return; }
    awk -v l="$load" -v m="$GM_MAX_LOAD" 'BEGIN { exit !(l > m) }' \
        && echo "busy: 5-min load $load (limit $GM_MAX_LOAD)"
}

gate_iona() {
    [ -d "$GM_IONA" ] || { echo "Iona not attached"; return; }
    [ -f "$GM_IONA/guest-matrix.conf" ] || { echo "Iona attached, but $GM_IONA/guest-matrix.conf is missing"; return; }
    # shellcheck disable=SC1090,SC1091
    . "$GM_IONA/guest-matrix.conf"
    [ -n "${GUESTS:-}" ] || { echo "guest-matrix.conf names no GUESTS"; return; }
    export TART_HOME="${TART_HOME:-}"
    [ -x "$TART" ] || { echo "tart not found at $TART"; return; }
    local running
    running="$("$TART" list 2>/dev/null | awk '$NF=="running" {print $2}' | tr '\n' ' ')"
    [ -n "$running" ] && echo "a guest is already running: ${running% }"
}

# Ask every gate, not just the first: "on battery · Iona not attached" tells the
# owner both things to change, where the first alone costs another night.
GATE_REASONS=""
GATE_DECISIVE=0
run_gates() {
    local r
    GATE_REASONS=""; GATE_DECISIVE=0
    r="$(gate_changed)"
    if [ -n "$r" ]; then GATE_REASONS="$r"; GATE_DECISIVE=1; return; fi
    for g in gate_power gate_release gate_idle; do
        r="$($g)"; [ -n "$r" ] && GATE_REASONS="${GATE_REASONS:+$GATE_REASONS · }$r"
    done
    # In this shell, not a subshell: it sources the drive's config.
    r="$(gate_iona)"; [ -n "$r" ] && GATE_REASONS="${GATE_REASONS:+$GATE_REASONS · }$r"
    [ -d "$GM_IONA" ] && [ -f "$GM_IONA/guest-matrix.conf" ] && . "$GM_IONA/guest-matrix.conf" && export TART_HOME="${TART_HOME:-}"
    return 0
}

# --- one guest ---------------------------------------------------------------

# The script the guest runs. GM-* lines are the protocol; everything else is
# test-swift.sh's own output, whose verdict lines are parsed by summarise_guest.
write_guest_script() {
    cat > "$1" <<'EOF'
#!/bin/bash
set -u
share="/Volumes/My Shared Files/gm"
src="$HOME/guest-matrix/src"; dd="$HOME/guest-matrix/dd"
rm -rf "$src" "$dd"; mkdir -p "$HOME/guest-matrix"
echo "GM-OS: $(sw_vers -productVersion)"
echo "GM-SIP: $(csrutil status 2>&1 | head -1)"
echo "GM-XCODE: $(xcodebuild -version 2>/dev/null | head -1)"
git -c advice.detachedHead=false clone -q "$share/tree-$1.bundle" "$src" 2>&1 || { echo "GM-ERROR: could not clone the tree bundle"; exit 4; }
git -C "$src" -c advice.detachedHead=false checkout -q "$1" 2>&1 || { echo "GM-ERROR: commit $1 is not in the bundle"; exit 4; }
[ -n "${2:-}" ] && { /bin/bash -c "$2" 2>&1 || echo "GM-WARN: guest prep exited $?"; }
cd "$src" || exit 4
# CI's two stub steps (mac-build.yml): the sidecar is a hard build input, and
# GeneratedBuildInfo.swift is gitignored, so a fresh clone has neither.
mkdir -p desktop/Bristlenose/Resources/bristlenose-sidecar
: > desktop/Bristlenose/Resources/bristlenose-sidecar/bristlenose-sidecar
chmod +x desktop/Bristlenose/Resources/bristlenose-sidecar/bristlenose-sidecar
desktop/scripts/generate-build-info.sh >/dev/null 2>&1 || echo "GM-WARN: generate-build-info.sh failed"
sudo -n xcodebuild -license accept >/dev/null 2>&1 || true
# -d keeps the guest's display awake: Core Animation stops with it asleep and the
# animation-driven sidebar scenarios then fail deterministically (desktop/CLAUDE.md).
CI=1 BN_DERIVED_DATA="$dd" /usr/bin/caffeinate -dimsu /bin/bash desktop/scripts/test-swift.sh 2>&1
rc=$?
echo "GM-RC: $rc"
exit "$rc"
EOF
    chmod +x "$1"
}

# summarise_guest <vm> <log> — PURE: one verdict cell from a guest's log.
#   "✓ 15.7.3 1569 passed" | "✗ 15.7.3 2 failed: A.a(), B.b()" | "✗ 15.7.3 build failed" | …
# Only test-swift.sh's own verdict lines count. Its exit code and its counts are
# reconciled THERE (a red at 0.000s, a reporter change); this only reads them.
summarise_guest() {
    # A guest-side warning (a failed screen-size prep leaves the guest at
    # 1024x768, which fails the window tests every time) rides on the cell.
    local warn; warn="$(sed -n 's/^GM-WARN: //p' "$2" | head -1)"
    printf '%s%s\n' "$(summarise_verdict "$1" "$2")" "${warn:+ (warn: $warn)}"
}
summarise_verdict() {
    local vm="$1" log="$2" os rc green red names
    os="$(sed -n 's/^GM-OS: //p' "$log" | head -1)"; os="${os:-$vm}"
    rc="$(sed -n 's/^GM-RC: //p' "$log" | tail -1)"
    if grep -q '^GM-BOOT-FAILED' "$log"; then echo "✗ $vm did not boot"; return; fi
    if grep -q '^GM-TIMEOUT' "$log"; then local t="$((GM_GUEST_TIMEOUT_S / 60)) min"; [ "$GM_GUEST_TIMEOUT_S" -lt 120 ] && t="${GM_GUEST_TIMEOUT_S}s"; echo "✗ $os timed out after $t"; return; fi
    if grep -q '^GM-ERROR' "$log"; then echo "✗ $os $(sed -n 's/^GM-ERROR: //p' "$log" | head -1)"; return; fi
    green="$(sed -n 's/^Swift suite green — \([0-9]*\) passed.*/\1/p' "$log" | tail -1)"
    if [ "$rc" = 0 ] && [ -n "$green" ]; then echo "✓ $os $green passed"; return; fi
    red="$(sed -n 's/^SWIFT SUITE RED — \([0-9]*\) failed.*/\1/p' "$log" | tail -1)"
    if [ -n "$red" ]; then
        names="$(sed -n "s/^Test case '\(.*\)' failed on.*/\1/p" "$log" | sort -u | head -5 | tr '\n' ',' | sed 's/,$//; s/,/, /g')"
        echo "✗ $os $red failed: $names"; return
    fi
    if [ "$rc" = 3 ]; then echo "✗ $os build failed"; return; fi
    if [ -z "$rc" ]; then echo "✗ $os no verdict (the guest never reported)"; return; fi
    echo "✗ $os no verdict (exit $rc)"
}

# with_timeout <secs> <cmd…> — macOS has no `timeout`. Exit status is the
# command's, or the kill's when the clock wins.
with_timeout() {
    local s="$1" p w rc; shift
    "$@" & p=$!
    ( sleep "$s"; kill "$p" 2>/dev/null ) >/dev/null 2>&1 & w=$!
    wait "$p"; rc=$?
    kill "$w" 2>/dev/null; wait "$w" 2>/dev/null
    return "$rc"
}

# The guest this run has up, so the exit trap can take it down: a runner killed
# by launchd or a signal must not leave a VM running, or every later night skips
# with "a guest is already running" until someone notices.
CUR_VM=""; CUR_PID=""; CUR_EXEC=""
stop_guest() {
    [ -n "$CUR_EXEC" ] && kill "$CUR_EXEC" 2>/dev/null
    if [ -n "$CUR_VM" ]; then
        with_timeout 60 "$TART" stop "$CUR_VM" >/dev/null 2>&1
        local i=0
        while [ -n "$CUR_PID" ] && kill -0 "$CUR_PID" 2>/dev/null && [ "$i" -lt "$GM_STOP_TIMEOUT_S" ]; do
            sleep 1; i=$((i + 1))
        done
        [ -n "$CUR_PID" ] && kill -9 "$CUR_PID" 2>/dev/null
    fi
    CUR_VM=""; CUR_PID=""; CUR_EXEC=""
}

run_guest() {
    local vm="$1" sha="$2" share="$3" log="$4" i deadline
    : > "$log"
    "$TART" run --no-graphics --no-audio --dir="gm:$share:ro" "$vm" >>"$log.tart" 2>&1 &
    CUR_PID=$!; CUR_VM="$vm"
    i=0
    until with_timeout 20 "$TART" exec "$vm" /usr/bin/true >/dev/null 2>&1; do
        i=$((i + 5))
        if [ "$i" -ge "$GM_BOOT_TIMEOUT_S" ] || ! kill -0 "$CUR_PID" 2>/dev/null; then
            echo "GM-BOOT-FAILED" >> "$log"
            stop_guest
            return
        fi
        sleep 5
    done
    "$TART" exec "$vm" /bin/bash "/Volumes/My Shared Files/gm/run-in-guest.sh" "$sha" "${GUEST_PREP:-}" >> "$log" 2>&1 &
    CUR_EXEC=$!
    deadline=$(( $(date +%s) + GM_GUEST_TIMEOUT_S ))
    while kill -0 "$CUR_EXEC" 2>/dev/null; do
        if [ "$(date +%s)" -ge "$deadline" ]; then
            kill "$CUR_EXEC" 2>/dev/null; echo "GM-TIMEOUT" >> "$log"; break
        fi
        sleep "$GM_POLL_S"
    done
    wait "$CUR_EXEC" 2>/dev/null
    CUR_EXEC=""
    stop_guest
}

# --- the report --------------------------------------------------------------

write_report() { # write_report <line>
    mkdir -p "$STATE/reports"
    printf '%s\n' "$1" > "$STATE/reports/$(run_name).txt"
    printf '%s\n' "$1" > "$STATE/latest.txt"
}

# After the gates pass, a failure must still leave a line: exiting quietly here
# reads in the morning as "the trigger never ran", which is a different fault.
run_error() {
    write_report "$(run_name) · error: $*"
    notify "error: $*"
    exit 2
}

notify() {
    [ -n "${GM_NO_NOTIFY:-}" ] && return 0
    # `display notification` never waits on a click, so it cannot wedge a launchd
    # job the way a dialog does.
    osascript -e "display notification \"$(printf '%s' "$1" | sed 's/"/\\"/g')\" with title \"Bristlenose · macOS guests\"" >/dev/null 2>&1 || true
}

cmd_report() {
    local f n; n="$(night)"
    # The morning asks about the night that just ended.
    [ "$(hour)" -ge "$GM_WINDOW_END" ] && [ "$(hour)" -lt "$GM_WINDOW_START" ] && n="${GM_NIGHT:-$(date -v-1d +%F)}"
    f="$STATE/reports/$n.txt"
    if [ ! -f "$f" ]; then
        echo "no report for the night of $n — the trigger never ran (Mac asleep all night, or the launchd job is not loaded)"
        return 4
    fi
    cat "$f"
    case "$(cat "$f")" in
        *"error:"*) return 1 ;;
        *"skipped:"*"(last: "*"✗"*) return 1 ;;
        *"skipped:"*) return 3 ;;
        *"✗"*) return 1 ;;
        *) return 0 ;;
    esac
}

cmd_check() {
    run_gates
    if [ -n "$GATE_REASONS" ]; then echo "skip: $GATE_REASONS"; return 3; fi
    echo "go: HEAD $(git -C "$REPO" rev-parse --short=8 HEAD) on ${GUESTS:-?}"
}

cmd_run() {
    local now="${1:-}" head last n shortlog cells cell sha share vm verdict all_ran=1
    local f lockpid
    if [ "$now" = "--now" ] && ! in_window; then RUN_NAME="trial-$(date +%F-%H%M)"; fi
    if [ "$now" != "--now" ]; then
        in_window || return 0
        # A finished night — it ran, or there was nothing to test — is not
        # repeated by later ticks. A retryable skip is asked again.
        f="$STATE/reports/$(night).txt"
        if [ -f "$f" ] && { ! grep -q 'skipped:' "$f" || grep -q 'no desktop change' "$f"; }; then
            return 0
        fi
    fi
    mkdir -p "$STATE" || die "cannot create $STATE"
    # The lock carries its holder's pid. A lock whose holder is gone — a runner
    # killed with -9, a panic, a power cut — is taken over; left alone it would
    # block every later night and leave no line at all.
    if ! mkdir "$STATE/.lock" 2>/dev/null; then
        lockpid="$(tr -cd '0-9' < "$STATE/.lock/pid" 2>/dev/null)"
        if [ -n "$lockpid" ] && kill -0 "$lockpid" 2>/dev/null \
            && ps -p "$lockpid" -o command= 2>/dev/null | grep -qF guest-matrix; then
            write_report "$(run_name) · skipped: a run is still in progress (pid $lockpid)"
            return 0
        fi
        rm -rf "$STATE/.lock"
        mkdir "$STATE/.lock" 2>/dev/null || run_error "cannot take the lock in $STATE"
    fi
    echo $$ > "$STATE/.lock/pid"
    trap 'stop_guest; rm -rf "$STATE/.lock"' EXIT
    # A run stopped by a signal says so; with no line, the morning would blame
    # the trigger. The EXIT trap then stops the guest and drops the lock.
    trap 'write_report "$(run_name) · error: interrupted by a signal"; exit 143' TERM
    trap 'write_report "$(run_name) · error: interrupted by a signal"; exit 130' INT

    run_gates
    if [ -n "$GATE_REASONS" ]; then
        write_report "$(night) · skipped: $GATE_REASONS"
        # "Nothing changed" needs no notification; a retryable skip is posted
        # once, by the night's last tick, so the morning shows why nothing ran.
        if [ "$GATE_DECISIVE" = 0 ] && last_tick; then notify "skipped: $GATE_REASONS"; fi
        return 0
    fi

    # A scheduled wake lets the Mac idle back to sleep within minutes; hold it
    # awake (not the display) for exactly as long as this process lives.
    [ -n "${GM_NO_CAFFEINATE:-}" ] || caffeinate -i -s -w $$ >/dev/null 2>&1 &

    head="$(git -C "$REPO" rev-parse --verify HEAD)" || run_error "cannot read HEAD"
    last="$(cat "$STATE/last-tested-sha" 2>/dev/null)"
    if [ -n "$last" ]; then
        n="$(git -C "$REPO" rev-list --count "$last..$head" -- $CHANGE_PATHS)"
        shortlog="$n desktop commit$([ "$n" = 1 ] || echo s) since ${last:0:8}"
    else
        shortlog="first run"
    fi
    share="$GM_IONA/share/guest-matrix"
    mkdir -p "$share" 2>/dev/null || run_error "cannot write to $share"
    # Named for the commit, never rewritten in place: the guest's VirtioFS share
    # has served the old bytes of a file rewritten at the same size (Iona README,
    # 25 Sep 2026). A new name cannot be stale.
    rm -f "$share"/tree-*.bundle
    git -C "$REPO" bundle create "$share/tree-$head.bundle.tmp" HEAD >/dev/null 2>&1 \
        && mv "$share/tree-$head.bundle.tmp" "$share/tree-$head.bundle" || run_error "could not bundle HEAD into $share"
    write_guest_script "$share/run-in-guest.sh" || run_error "could not write the guest script into $share"

    mkdir -p "$STATE/logs/$(run_name)"
    cells=""
    for vm in $GUESTS; do
        log="$STATE/logs/$(run_name)/$vm.log"
        run_guest "$vm" "$head" "$share" "$log"
        cell="$(summarise_guest "$vm" "$log")"
        cells="${cells:+$cells · }$cell"
        # A guest that never reported is not a tested version: the next night
        # must retry rather than read this commit as covered.
        case "$cell" in *"did not boot"*|*"timed out"*|*"no verdict"*|*"could not"*|*"not in the bundle"*) all_ran=0 ;; esac
    done
    verdict="$(run_name) · tested ${head:0:8} ($shortlog)${GM_IGNORE_IDLE:+, idle gate overridden} · $cells"
    write_report "$verdict"
    if [ "$all_ran" = 1 ]; then
        printf '%s\n' "$head" > "$STATE/last-tested-sha"
        printf '%s\n' "$cells" > "$STATE/last-verdict"
    fi
    notify "$cells"
    return 0
}

# install / uninstall — the LaunchAgent that ticks `run` on :00 and :30. A
# calendar interval, not StartInterval: launchd fires one missed calendar event
# on wake, so a Mac woken at 23:29 by `pmset repeat wake` runs the :30 tick.
#
# launchd runs a small applet, not /bin/bash, for two reasons. System Settings ▸
# General ▸ Login Items names a background item after the program it launches,
# so bare bash would be listed as "bash"; the applet is listed by its own name.
# And macOS asks permission prompts (an external drive, for one) of that same
# program, so the applet gets an entry of its own instead of bash getting one
# that covers every script on the machine. Same shape as the code-backup agent.
LABEL="com.cassio.bristlenose-guest-matrix"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
APP_NAME="Bristlenose Guest Matrix"
APP="$HOME/Library/Application Support/$APP_NAME/$APP_NAME.app"
build_applet() {
    local src; src="$(mktemp -d)/applet.applescript"
    # `|| true` and the redirect are load-bearing: an applet whose shell command
    # exits non-zero puts up an error dialog, and a dialog at 02:00 waits for a
    # click that never comes. The mkdir is too: with the log's directory gone the
    # redirect fails, `|| true` swallows it, and every night does nothing
    # (measured 8 Oct 2026 — exit 0 in half a second, no run, no log).
    cat > "$src" <<EOF
do shell script "mkdir -p " & quoted form of "$STATE" & "; /bin/bash " & quoted form of "$REPO/desktop/scripts/guest-matrix.sh" & " run >> " & quoted form of "$STATE/launchd.log" & " 2>&1 || true"
EOF
    rm -rf "$APP"; mkdir -p "$(dirname "$APP")"
    osacompile -o "$APP" "$src" || die "osacompile failed"
    # No Dock icon while it runs.
    plutil -replace LSUIElement -bool true "$APP/Contents/Info.plist" || die "could not set LSUIElement"
    plutil -replace CFBundleIdentifier -string "$LABEL" "$APP/Contents/Info.plist"
    codesign --force --sign - "$APP" >/dev/null 2>&1 || die "could not sign $APP"
}
cmd_install() {
    mkdir -p "$STATE" "$(dirname "$PLIST")"
    build_applet
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>$APP/Contents/MacOS/applet</string></array>
    <key>StartCalendarInterval</key>
    <array><dict><key>Minute</key><integer>0</integer></dict><dict><key>Minute</key><integer>30</integer></dict></array>
    <key>Umask</key><integer>63</integer>
    <key>StandardOutPath</key><string>$STATE/launchd.log</string>
    <key>StandardErrorPath</key><string>$STATE/launchd.log</string>
</dict>
</plist>
EOF
    plutil -lint "$PLIST" >/dev/null || die "the generated plist does not lint: $PLIST"
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    launchctl bootstrap "gui/$(id -u)" "$PLIST" || die "launchctl bootstrap refused $PLIST"
    launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || die "loaded, but launchctl cannot see $LABEL"
    echo "installed $LABEL — ticks on :00 and :30, runs 23:00–06:00"
    echo "listed in System Settings ▸ General ▸ Login Items as \"$APP_NAME\""
}
cmd_uninstall() {
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    rm -f "$PLIST"; rm -rf "$(dirname "$APP")"
    echo "removed $LABEL"
}

case "${1:-}" in
    check)  cmd_check ;;
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    run)    cmd_run "${2:-}" ;;
    report) cmd_report ;;
    behind) cmd_behind ;;
    summarise) summarise_guest "$2" "$3" ;;   # the test's seam; pure
    *) echo "usage: $(basename "$0") check | run [--now] | report | install | uninstall" >&2; exit 2 ;;
esac
