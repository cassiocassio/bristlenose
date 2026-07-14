#!/usr/bin/env bash
# report.sh — event helpers for the shared build-script report (see REPORT-STYLE.md).
#
# Source this, then call the bn_* helpers instead of bare `echo "==> N"`. Each
# helper prints one `@bn …` sentinel line; build_report.py (piped on the other
# end) turns the stream into the rendered report. Noisy tool output still goes
# to per-step log files under desktop/build/ — the helpers only emit events.
#
# Usage:
#   source "$SCRIPT_DIR/report.sh"
#   bn_meta title="Bristlenose.app — release build" identity="$SIGN_IDENTITY" …
#   bn_step_start 5 Build "Xcode archive" log="$ARCHIVE_LOG" \
#       narrative="Compiles + signs the native app shell."
#   xcodebuild … > "$ARCHIVE_LOG" 2>&1
#   bn_step_ok 5 elapsed=$SECONDS_SINCE detail="Bristlenose.xcarchive"
#
# The whole run is wrapped by the caller so its stdout is piped:
#   { build_body; } | "$PYTHON" "$SCRIPT_DIR/build_report.py"
# When build_report.py is absent or stdout is not wanted pretty, set
# BN_REPORT=0 and the helpers fall back to plain `==>`-style echoes.

# Emit one sentinel line. Fields are passed verbatim as key=value; values with
# spaces must be quoted by the caller (bn_kv helps) — report.sh re-quotes with
# %q so build_report.py's shlex.split re-parses them intact.
_bn_emit() {
    local kind="$1"; shift
    if [ "${BN_REPORT:-1}" = "0" ]; then
        _bn_plain "$kind" "$@"
        return
    fi
    local out="@bn $kind"
    local pair k v
    for pair in "$@"; do
        k="${pair%%=*}"
        v="${pair#*=}"
        out+=" $k=$(printf '%q' "$v")"
    done
    printf '%s\n' "$out"
}

# Plain fallback (BN_REPORT=0): approximate the old `==> N. name` shape so a
# raw run without the renderer stays legible.
_bn_plain() {
    local kind="$1"; shift
    local -A f=()
    local pair
    for pair in "$@"; do f["${pair%%=*}"]="${pair#*=}"; done
    case "$kind" in
        step)
            # A compact step carries its name on the ok/skip/fail event (no
            # preceding start); print a header line for it. A step that had a
            # start already printed its header, so name is absent here.
            local hdr=""
            [ -n "${f[name]:-}" ] && hdr="==> ${f[id]}. ${f[name]} — "
            case "${f[status]}" in
                start) echo "==> ${f[id]}. ${f[name]}..." ;;
                ok)    echo "${hdr:-    }OK${f[detail]:+ — ${f[detail]}}" ;;
                skip)  echo "${hdr:-    }SKIPPED${f[detail]:+ (${f[detail]})}" ;;
                fail)  echo "${hdr:-    }FAILED${f[detail]:+ — ${f[detail]}}" >&2 ;;
            esac ;;
        check) echo "      - ${f[label]}: ${f[evidence]}" ;;
        gate)  echo "    [${f[id]}] ${f[desc]}: ${f[evidence]}" ;;
        done)  [ "${f[status]}" = fail ] && echo "BUILD FAILED" >&2 || echo "DONE" ;;
    esac
}

# ── public helpers ─────────────────────────────────────────────────────────
bn_meta() { _bn_emit meta "$@"; }

# bn_step_start <tag> <phase> <name> [detail=… narrative=… log=…]
bn_step_start() {
    local tag="$1" phase="$2" name="$3"; shift 3
    _bn_emit step "id=$tag" "phase=$phase" "name=$name" "status=start" "$@"
}

# bn_step_ok <tag> [elapsed=… detail=… name=… phase=…]   (name/phase optional if
# no matching start was emitted — for compact single-line steps)
bn_step_ok()   { local tag="$1"; shift; _bn_emit step "id=$tag" "status=ok"   "$@"; }
bn_step_skip() { local tag="$1"; shift; _bn_emit step "id=$tag" "status=skip" "$@"; }
bn_step_fail() { local tag="$1"; shift; _bn_emit step "id=$tag" "status=fail" "$@"; }

# bn_check <parent-tag> <result> <label> <evidence>
bn_check() { _bn_emit check "parent=$1" "result=$2" "label=$3" "evidence=$4"; }

# bn_bar <parent-tag> <done> <total>
bn_bar() { _bn_emit bar "parent=$1" "done=$2" "total=$3"; }

# bn_gate <id> <result> <desc> <evidence>
bn_gate() { _bn_emit gate "id=$1" "result=$2" "desc=$3" "evidence=$4"; }

# bn_art <key> <value>
bn_art() { _bn_emit art "key=$1" "value=$2"; }

# bn_done ok|fail
bn_done() { _bn_emit done "status=${1:-ok}"; }
