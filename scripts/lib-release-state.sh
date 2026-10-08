#!/usr/bin/env bash
# lib-release-state.sh — is a release running, or pending? One copy of the answer.
#
# Sourced, not run. Two callers ask the same question for different reasons:
#   - check-release-freeze.sh (pre-commit) refuses a commit while a run is live;
#   - desktop/scripts/guest-matrix.sh skips the night's macOS-guest run while a
#     release is running or pending, so the guests never compete with it for
#     the CPU, the disk or the owner's attention in the morning.
# The live-lock test was inline in the first; it moved here (8 Oct 2026) so the
# second did not become a copy whose fixes do not travel.
#
# Every function takes the MAIN checkout's root (the directory holding .release/)
# and prints a reason, or nothing. Printing nothing means "no", never "unknown":
# a probe that cannot read something it expects to read says so in its output.

# release_live_lock <root> — "<version> (pid <n>)" if a `release.sh run` driver
# holds its lock and is alive. A dead pid, or a pid that now belongs to another
# program (a driver killed with -9 cannot remove its lock, and macOS reuses
# pids), is not a live run.
release_live_lock() {
    local root="$1" pidfile pid v
    for pidfile in "$root"/.release/*/.lock/pid; do
        [ -f "$pidfile" ] || continue
        pid="$(tr -cd '0-9' < "$pidfile")"
        [ -n "$pid" ] || continue
        kill -0 "$pid" 2>/dev/null || continue
        ps -p "$pid" -o command= 2>/dev/null | grep -qF 'release.sh run' || continue
        v="${pidfile#"$root"/.release/}"; v="${v%%/*}"
        printf '%s (pid %s)\n' "$v" "$pid"
        return 0
    done
    return 0
}

# release_stopped_run <root> — the newest ledger (by mtime) whose last `run`
# event is not `completed`: a run that started and stopped on a failed step, and
# is waiting for `release.sh retry`. That is when a fix is supposed to land, so
# the freeze deliberately does not cover it — but it is still a release pending.
release_stopped_run() {
    local root="$1" ledger last v
    ledger="$(ls -t "$root"/.release/*/events.jsonl 2>/dev/null | head -1)"
    [ -n "$ledger" ] || return 0
    last="$(grep '"step":"run"' "$ledger" | tail -1)"
    [ -n "$last" ] || return 0
    case "$last" in *'"status":"completed"'*) return 0 ;; esac
    v="${ledger#"$root"/.release/}"; v="${v%%/*}"
    printf 'release %s started and has not completed\n' "$v"
}

# release_unshipped_bump <root> — __version__ moved past the newest tag: a bump
# is committed and the tag has not gone out yet.
release_unshipped_bump() {
    local root="$1" ver tag
    ver="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$root/bristlenose/__init__.py" 2>/dev/null)"
    tag="$(git -C "$root" describe --tags --abbrev=0 2>/dev/null)"
    if [ -z "$ver" ] || [ -z "$tag" ]; then
        printf 'could not read the version or the last tag\n'
        return 0
    fi
    [ "v$ver" = "$tag" ] && return 0
    printf 'version %s is bumped but not tagged (last tag %s)\n' "$ver" "$tag"
}

# release_engaged <root> — the first of the three that answers, or nothing.
release_engaged() {
    local root="$1" r
    r="$(release_live_lock "$root")"
    [ -n "$r" ] && { printf 'release %s is running\n' "$r"; return 0; }
    r="$(release_stopped_run "$root")"
    [ -n "$r" ] && { printf '%s\n' "$r"; return 0; }
    release_unshipped_bump "$root"
}
