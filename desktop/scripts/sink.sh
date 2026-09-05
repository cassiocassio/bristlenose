#!/usr/bin/env bash
# sink.sh — the event sink: tee the @bn report protocol into a file.
#
# sink_line <kind> k=v …
#   Appends one line — `@bn <kind> ts=<UTC> run=<id> k=v …` — to $BN_EVENT_SINK.
#   The line IS the report protocol (REPORT-STYLE.md) with two fields added, so
#   bn_events.py's one parser reads both the live stream and the file.
#
# Contract (docs/design-release-board.md §1.1):
#   - No-op unless BN_EVENT_SINK is set AND absolute. A relative sink resolves
#     against whichever cwd a child happens to have, and the write then lands
#     somewhere else or fails — silently either way. Refusing is the honest no.
#   - Never fails the caller. A dashboard must not be the reason a release step
#     fails; a write failure is swallowed. The DRIVER (release.sh) asserts its
#     own boundary writes separately — see sink_line_or_die.
#   - Values are NORMALISED BEFORE `printf %q`. %q emits ANSI-C quoting ($'…')
#     for control bytes, which shlex does not decode: a value with a newline and
#     an apostrophe made parse_event raise and the whole line was dropped
#     (measured 5 Sep 2026). CR/LF/TAB become spaces, the rest of \000-\037 is
#     removed, and the value is cut to 200 bytes — which also keeps every line
#     under PIPE_BUF so concurrent appenders cannot interleave, and stops a
#     value from forging a second "@bn" line.
#   - ts is written HERE, in UTC, so a child cannot write local time into the
#     merge with events.jsonl.
#   - run is $BN_RUN_ID, or standalone-<epoch> when a sink is set by hand.
#   - The file is created under umask 077: it aggregates build identity.
#
# bash 3.2 safe: no associative arrays, no ${var,,}, no mapfile.

sink_line() {
    [ -n "${BN_EVENT_SINK:-}" ] || return 0
    case "$BN_EVENT_SINK" in /*) ;; *) return 0 ;; esac
    local kind="$1"; shift
    local out="@bn $kind ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) run=${BN_RUN_ID:-standalone-$(date +%s)}"
    local pair k v
    for pair in "$@"; do
        k="${pair%%=*}"
        v="${pair#*=}"
        v="$(printf '%s' "$v" | tr '\r\n\t' '   ' | tr -d '\000-\037' | cut -c1-200)"
        out="$out $k=$(printf '%q' "$v")"
    done
    ( umask 077; printf '%s\n' "$out" >> "$BN_EVENT_SINK" ) 2>/dev/null || true
}

# sink_line_or_die — the driver's variant: same line, but a write that fails is
# an error the caller must handle (release.sh dies, as it does for events.jsonl).
# Returns 1 on failure instead of swallowing it.
sink_line_or_die() {
    [ -n "${BN_EVENT_SINK:-}" ] || return 0
    case "$BN_EVENT_SINK" in /*) ;; *) return 1 ;; esac
    local kind="$1"; shift
    local out="@bn $kind ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) run=${BN_RUN_ID:-standalone-$(date +%s)}"
    local pair k v
    for pair in "$@"; do
        k="${pair%%=*}"
        v="${pair#*=}"
        v="$(printf '%s' "$v" | tr '\r\n\t' '   ' | tr -d '\000-\037' | cut -c1-200)"
        out="$out $k=$(printf '%q' "$v")"
    done
    ( umask 077; printf '%s\n' "$out" >> "$BN_EVENT_SINK" )
}
