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
# Per guest: boot, unpack, a full unsigned compile and the suite. A first compile
# in a guest has taken ~25 min; 90 leaves room without letting a hang eat the night.
GM_GUEST_TIMEOUT_MIN="${GM_GUEST_TIMEOUT_MIN:-90}"
GM_BOOT_TIMEOUT_S="${GM_BOOT_TIMEOUT_S:-300}"

. "$REPO/scripts/lib-release-state.sh"

die() { echo "guest-matrix: $*" >&2; exit 2; }

hour() { local h="${GM_HOUR:-$(date +%H)}"; echo $((10#$h)); }
# The night is named for its evening: 02:00 on the 9th belongs to the 8th.
night() { echo "${GM_NIGHT:-$(date -v-12H +%F)}"; }
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
    n="$(git -C "$REPO" rev-list --count "$last..$head" -- desktop/)"
    [ "$n" -gt 0 ] && return 0
    echo "no desktop change since ${last:0:8}"
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
git clone -q "$share/tree.bundle" "$src" 2>&1 || { echo "GM-ERROR: could not clone the tree bundle"; exit 4; }
git -C "$src" checkout -q "$1" 2>&1 || { echo "GM-ERROR: commit $1 is not in the bundle"; exit 4; }
[ -n "${2:-}" ] && { /bin/bash -c "$2" 2>&1 || echo "GM-WARN: guest prep exited $?"; }
cd "$src" || exit 4
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
    local vm="$1" log="$2" os rc green red names
    os="$(sed -n 's/^GM-OS: //p' "$log" | head -1)"; os="${os:-$vm}"
    rc="$(sed -n 's/^GM-RC: //p' "$log" | tail -1)"
    if grep -q '^GM-BOOT-FAILED' "$log"; then echo "✗ $vm did not boot"; return; fi
    if grep -q '^GM-TIMEOUT' "$log"; then echo "✗ $os timed out after ${GM_GUEST_TIMEOUT_MIN} min"; return; fi
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

run_guest() {
    local vm="$1" sha="$2" share="$3" log="$4" pid i deadline rc
    : > "$log"
    "$TART" run --no-graphics --no-audio --dir="gm:$share:ro" "$vm" >>"$log.tart" 2>&1 &
    pid=$!
    i=0
    until "$TART" exec "$vm" /usr/bin/true >/dev/null 2>&1; do
        i=$((i + 5))
        if [ "$i" -ge "$GM_BOOT_TIMEOUT_S" ] || ! kill -0 "$pid" 2>/dev/null; then
            echo "GM-BOOT-FAILED" >> "$log"
            "$TART" stop "$vm" >/dev/null 2>&1; wait "$pid" 2>/dev/null
            return
        fi
        sleep 5
    done
    "$TART" exec "$vm" /bin/bash "/Volumes/My Shared Files/gm/run-in-guest.sh" "$sha" "${GUEST_PREP:-}" >> "$log" 2>&1 &
    rc=$!
    deadline=$(( $(date +%s) + GM_GUEST_TIMEOUT_MIN * 60 ))
    while kill -0 "$rc" 2>/dev/null; do
        if [ "$(date +%s)" -ge "$deadline" ]; then
            kill "$rc" 2>/dev/null; echo "GM-TIMEOUT" >> "$log"; break
        fi
        sleep 10
    done
    wait "$rc" 2>/dev/null
    "$TART" stop "$vm" >/dev/null 2>&1
    wait "$pid" 2>/dev/null
}

# --- the report --------------------------------------------------------------

write_report() { # write_report <line>
    mkdir -p "$STATE/reports"
    printf '%s\n' "$1" > "$STATE/reports/$(night).txt"
    printf '%s\n' "$1" > "$STATE/latest.txt"
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
    local f
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
    mkdir "$STATE/.lock" 2>/dev/null || { echo "another guest-matrix run is in progress" >&2; return 0; }
    trap 'rm -rf "$STATE/.lock"' EXIT

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

    head="$(git -C "$REPO" rev-parse --verify HEAD)" || die "cannot read HEAD"
    last="$(cat "$STATE/last-tested-sha" 2>/dev/null)"
    if [ -n "$last" ]; then
        n="$(git -C "$REPO" rev-list --count "$last..$head" -- desktop/)"
        shortlog="$n desktop commit$([ "$n" = 1 ] || echo s) since ${last:0:8}"
    else
        shortlog="first run"
    fi
    share="$GM_IONA/share/guest-matrix"
    mkdir -p "$share" || die "cannot write to $share"
    git -C "$REPO" bundle create "$share/tree.bundle.tmp" HEAD >/dev/null 2>&1 \
        && mv "$share/tree.bundle.tmp" "$share/tree.bundle" || die "could not bundle HEAD"
    write_guest_script "$share/run-in-guest.sh"

    mkdir -p "$STATE/logs/$(night)"
    cells=""
    for vm in $GUESTS; do
        log="$STATE/logs/$(night)/$vm.log"
        run_guest "$vm" "$head" "$share" "$log"
        cell="$(summarise_guest "$vm" "$log")"
        cells="${cells:+$cells · }$cell"
        # A guest that never reported is not a tested version: the next night
        # must retry rather than read this commit as covered.
        case "$cell" in *"did not boot"*|*"timed out"*|*"no verdict"*|*"could not"*|*"not in the bundle"*) all_ran=0 ;; esac
    done
    verdict="$(night) · tested ${head:0:8} ($shortlog) · $cells"
    write_report "$verdict"
    [ "$all_ran" = 1 ] && printf '%s\n' "$head" > "$STATE/last-tested-sha"
    notify "$cells"
    return 0
}

# install / uninstall — the LaunchAgent that ticks `run` on :00 and :30. A
# calendar interval, not StartInterval: launchd fires one missed calendar event
# on wake, so a Mac woken at 23:29 by `pmset repeat wake` runs the :30 tick.
LABEL="com.cassio.bristlenose-guest-matrix"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
cmd_install() {
    mkdir -p "$STATE" "$(dirname "$PLIST")"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string>$REPO/desktop/scripts/guest-matrix.sh</string><string>run</string></array>
    <key>StartCalendarInterval</key>
    <array><dict><key>Minute</key><integer>0</integer></dict><dict><key>Minute</key><integer>30</integer></dict></array>
    <key>EnvironmentVariables</key>
    <dict><key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:$HOME/bin:/opt/homebrew/bin</string></dict>
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
}
cmd_uninstall() {
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    rm -f "$PLIST"
    echo "removed $LABEL"
}

case "${1:-}" in
    check)  cmd_check ;;
    install)   cmd_install ;;
    uninstall) cmd_uninstall ;;
    run)    cmd_run "${2:-}" ;;
    report) cmd_report ;;
    summarise) summarise_guest "$2" "$3" ;;   # the test's seam; pure
    *) echo "usage: $(basename "$0") check | run [--now] | report | install | uninstall" >&2; exit 2 ;;
esac
