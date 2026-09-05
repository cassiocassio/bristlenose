#!/usr/bin/env bash
# report.sh — event helpers for the shared build-script report (see REPORT-STYLE.md).
#
# Source this, call bn_autowrap once, then use the bn_* helpers instead of bare
# `echo "==> N"`. Each helper prints one `@bn …` sentinel line; build_report.py
# (piped on the other end) renders it. Noisy tool output still goes to per-step
# log files under desktop/build/ — the helpers only emit events.
#
# Usage (every adopting script):
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   source "$SCRIPT_DIR/report.sh"
#   bn_autowrap "$0" "$@"          # re-execs self through the renderer if standalone
#   trap '_ec=$?; [ "$_ec" -ne 0 ] && bn_trap_fail' EXIT
#   bn_meta title="…" identity="…"
#   bn_step_start 5 Build "Xcode archive" log="$ARCHIVE_LOG"
#   xcodebuild … > "$ARCHIVE_LOG" 2>&1
#   bn_step_ok 5 elapsed=$((SECONDS-t)) detail="…"
#
# Escape hatch: BN_REPORT=0 (or missing python / build_report.py) → plain output.
#
# ── bash 3.2 SAFE ──────────────────────────────────────────────────────────
# ensure-sidecar.sh and the Xcode "Ensure Sidecar Fresh" build phase run under
# /bin/bash 3.2. So this file uses NO associative arrays (`local -A`), NO
# `${var,,}`, NO `mapfile` — only string ops, `case` globs, `printf %q`, and
# PIPESTATUS, all of which 3.2 supports.
#
# ── Nesting ────────────────────────────────────────────────────────────────
# When script A (already rendering) calls script B, B must NOT start a second
# renderer. bn_autowrap exports _BN_ACTIVE=1 for children; a child seeing it does
# not wrap, and its bn_* calls emit nothing (the parent narrates the step + logs
# B's real output). Only the render OWNER (the process bn_autowrap re-exec'd)
# carries the non-exported _bn_owner=1 and therefore emits.

# _bn_field <key> <pair>… — echo the value of key= from a list of k=v pairs.
# 3.2-safe replacement for an associative-array lookup.
_bn_field() {
    local key="$1"; shift
    local pair
    for pair in "$@"; do
        case "$pair" in
            "$key="*) printf '%s' "${pair#*=}"; return 0 ;;
        esac
    done
}

# The sink (docs/design-release-board.md §1.1): when BN_EVENT_SINK is set, the
# owner's events are also appended to that file with ts= and run=. Same
# directory as this file; a partial checkout without it must not break a build
# phase, so the source is guarded and sink_line degrades to a no-op.
_BN_SINK_SH="${BASH_SOURCE[0]%/*}/sink.sh"
if [ -f "$_BN_SINK_SH" ]; then
    # shellcheck source=desktop/scripts/sink.sh
    . "$_BN_SINK_SH"
else
    sink_line() { :; }
fi

# Emit one sentinel line. Suppressed for nested children (parent renders).
_bn_emit() {
    # Nested under a rendering parent, and not the owner → stay silent.
    if [ -n "${_BN_ACTIVE:-}" ] && [ -z "${_bn_owner:-}" ]; then
        return 0
    fi
    local kind="$1"; shift
    # Record before rendering, in every mode: the sink follows rendering
    # ownership (the guard above), so a nested child that is silent on stdout
    # is silent in the file too — the parent narrates it. BN_REPORT=0 still
    # records, because plain output is a view and the sink is the record.
    sink_line "$kind" "$@"
    if [ "${BN_REPORT:-1}" = "0" ]; then
        _bn_plain "$kind" "$@"
        return
    fi
    local out="@bn $kind"
    local pair k v
    for pair in "$@"; do
        k="${pair%%=*}"
        v="${pair#*=}"
        out="$out $k=$(printf '%q' "$v")"
    done
    printf '%s\n' "$out"
}

# Plain fallback (BN_REPORT=0): approximate the old `==> N. name` shape. 3.2-safe.
_bn_plain() {
    local kind="$1"; shift
    case "$kind" in
        step)
            local id name status detail
            id="$(_bn_field id "$@")"; name="$(_bn_field name "$@")"
            status="$(_bn_field status "$@")"; detail="$(_bn_field detail "$@")"
            # A compact step carries its name (no preceding start) → print a header.
            local hdr=""
            [ -n "$name" ] && hdr="==> $id. $name — "
            case "$status" in
                start) echo "==> $id. $name..." ;;
                ok)    echo "${hdr:-    }OK${detail:+ — $detail}" ;;
                skip)  echo "${hdr:-    }SKIPPED${detail:+ ($detail)}" ;;
                fail)  echo "${hdr:-    }FAILED${detail:+ — $detail}" >&2 ;;
            esac ;;
        check) echo "      - $(_bn_field label "$@"): $(_bn_field evidence "$@")" ;;
        gate)  echo "    [$(_bn_field id "$@")] $(_bn_field desc "$@"): $(_bn_field evidence "$@")" ;;
        done)  [ "$(_bn_field status "$@")" = fail ] && echo "BUILD FAILED" >&2 || echo "DONE" ;;
    esac
}

# bn_autowrap <self> [args…] — if this is a standalone run with the renderer
# available, re-exec self with stdout piped through build_report.py and exit with
# OUR status (PIPESTATUS[0]). No-op when: BN_REPORT=0, a parent is already
# rendering (_BN_ACTIVE), or python / build_report.py are unavailable.
bn_autowrap() {
    # A parent is already rendering → don't wrap; children stay silent (_bn_emit).
    # This guard is first for a reason: the re-exec'd inner run exports BOTH
    # _BN_ACTIVE and _BN_INNER to its children, so a child must be turned away
    # here before the _BN_INNER branch below can mistake it for the inner run.
    [ -n "${_BN_ACTIVE:-}" ] && return 0
    # Ownership is claimed ONCE, here, on every path a standalone run can take —
    # plain mode, no renderer, or the re-exec'd inner run. Rendering and the
    # sink share this one token; before 5 Sep 2026 the plain-mode and
    # no-renderer returns never set it, so under BN_REPORT=0 a parent and its
    # children all passed _bn_emit's guard and the sink would have recorded
    # every line twice. Nested children now go silent in plain mode exactly as
    # they do under the renderer (pinned by scripts/test-sink.sh).
    if [ "${BN_REPORT:-1}" = "0" ]; then
        _bn_owner=1; export _BN_ACTIVE=1
        return 0
    fi
    # This is the re-exec'd inner run: become the owner, silence descendants.
    if [ -n "${_BN_INNER:-}" ]; then
        _bn_owner=1
        export _BN_ACTIVE=1
        return 0
    fi
    # Standalone outer run: resolve python + renderer, then wrap.
    local self="$1"; shift
    local py="${BN_PYTHON:-}"
    [ -n "$py" ] && [ -x "$py" ] || py="$SCRIPT_DIR/../../.venv/bin/python"
    [ -x "$py" ] || py="$(command -v python3 2>/dev/null || true)"
    local renderer="$SCRIPT_DIR/build_report.py"
    if [ -z "$py" ] || [ ! -f "$renderer" ]; then
        _bn_owner=1; export _BN_ACTIVE=1
        return 0   # no renderer available → fall through to plain body, as owner
    fi
    set +e
    _BN_INNER=1 "$self" "$@" | "$py" "$renderer"
    local status=${PIPESTATUS[0]}
    set -e
    exit "$status"
}

# ── public helpers ─────────────────────────────────────────────────────────
bn_meta() { _bn_emit meta "$@"; }

# bn_step_start <tag> <phase> <name> [detail=… narrative=… log=…]
# _BN_CUR_TAG tracks the open step so bn_trap_fail can mark it failed if the
# script dies mid-step. _BN_DONE guards the trap from a second footer.
bn_step_start() {
    local tag="$1" phase="$2" name="$3"; shift 3
    _bn_emit step "id=$tag" "phase=$phase" "name=$name" "status=start" "$@"
    _BN_CUR_TAG="$tag"
}

# bn_step_ok/skip/fail <tag> [elapsed=… detail=… name=… phase=…]
bn_step_ok()   { local tag="$1"; shift; _bn_emit step "id=$tag" "status=ok"   "$@"; _BN_CUR_TAG=""; }
bn_step_skip() { local tag="$1"; shift; _bn_emit step "id=$tag" "status=skip" "$@"; _BN_CUR_TAG=""; }
bn_step_fail() { local tag="$1"; shift; _bn_emit step "id=$tag" "status=fail" "$@"; _BN_CUR_TAG=""; }

# bn_trap_fail — call from an EXIT trap on nonzero exit. Marks the open step
# failed (if any) and emits a fail footer (unless bn_done already ran).
bn_trap_fail() {
    [ -n "${_BN_CUR_TAG:-}" ] && bn_step_fail "$_BN_CUR_TAG" detail="step aborted — see error above"
    [ "${_BN_DONE:-0}" = "0" ] && bn_done fail
}

# bn_check <parent-tag> <result> <label> <evidence>
bn_check() { _bn_emit check "parent=$1" "result=$2" "label=$3" "evidence=$4"; }

# bn_bar <parent-tag> <done> <total>
bn_bar() { _bn_emit bar "parent=$1" "done=$2" "total=$3"; }

# bn_gate <id> <result> <desc> <evidence>
bn_gate() { _bn_emit gate "id=$1" "result=$2" "desc=$3" "evidence=$4"; }

# bn_art <key> <value>
bn_art() { _bn_emit art "key=$1" "value=$2"; }

# bn_done ok|fail
bn_done() { _bn_emit done "status=${1:-ok}"; _BN_DONE=1; }
