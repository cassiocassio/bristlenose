#!/usr/bin/env bash
# Source-level lint: catch logger calls that interpolate credential-shaped
# identifiers without an explicit privacy marker, and print() calls that
# dump env.
#
# Defence against Swift-side leakage regressions (future dev writing
# `Logger.info("injected \(apiKey)")` without `privacy: .private`).
# Complements the runtime redactor in ServeManager.handleLine which
# catches Python-side leakage — both are belt-and-braces.
#
# Scans `.swift` files under desktop/Bristlenose/Bristlenose/, excluding
# any `*Tests.swift`. Intentionally scope-limited — don't scan archived
# code (v0.1-archive) or Python.
#
# Exclusions live in desktop/scripts/logging-hygiene-allowlist.md; add
# entries with a <!-- ci-allowlist: HYG-<N> --> marker plus justification
# when a legitimate call trips the regex.
#
# Usage:
#   desktop/scripts/check-logging-hygiene.sh [<repo-root>]
#
# Exit codes:
#   0  Clean — no unjustified violations.
#   1  Violations found; prints offending lines.
#   2  Usage / environment error.

set -euo pipefail

REPO_ROOT="${1:-}"
if [ -z "$REPO_ROOT" ]; then
    # default: the directory two levels up from this script
    SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
    REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
fi
: "${SCRIPT_DIR:=$(cd "$(dirname "$0")" && pwd)}"
source "$SCRIPT_DIR/report.sh"
bn_autowrap "$0" "$@"
trap '_bn_ec=$?; [ "$_bn_ec" -ne 0 ] && bn_trap_fail' EXIT
bn_meta title="Logging hygiene" done_title="✓ Logging hygiene clean"
bn_step_start 1 Pre-flight "Logging hygiene" \
    narrative="Scans Swift Logger calls for credential-shaped interpolation without a privacy marker."

SCAN_ROOT="$REPO_ROOT/desktop/Bristlenose/Bristlenose"
ALLOWLIST="$REPO_ROOT/desktop/scripts/logging-hygiene-allowlist.md"

if [ ! -d "$SCAN_ROOT" ]; then
    echo "error: scan root not found: $SCAN_ROOT" >&2
    exit 2
fi

# --- Build the allowlisted-regex set from the markdown allowlist. ----------
# Each entry takes the form:
#   <!-- ci-allowlist: HYG-<N> --> <regex-pattern>
# One per line. Blank lines + anything without the marker are ignored.
# The regex pattern must match the full offending line reported by grep.
ALLOW_REGEXES=()
if [ -f "$ALLOWLIST" ]; then
    while IFS= read -r line; do
        # Extract the pattern after the closing "-->"
        pattern=$(echo "$line" | sed -E 's/^.*<!-- ci-allowlist: HYG-[0-9]+ --> *//')
        [ -n "$pattern" ] && ALLOW_REGEXES+=("$pattern")
    done < <(grep -E 'ci-allowlist: HYG-[0-9]+' "$ALLOWLIST" 2>/dev/null || true)
fi

is_allowlisted() {
    local line="$1"
    # `+` guard: an empty ALLOW_REGEXES is "unbound" to `set -u` under macOS's
    # stock /bin/bash 3.2, and the abort exits 0 — a real leak reported clean.
    for pat in ${ALLOW_REGEXES[@]+"${ALLOW_REGEXES[@]}"}; do
        if echo "$line" | grep -qE "$pat"; then
            return 0
        fi
    done
    return 1
}

# --- Pattern 1: interpolated credential identifiers in logging calls. ------
# Matches lines where a logging call (Logger instance method like .info/.debug,
# or a global log function) contains \(...(key|secret|...)...) on the same
# line AND the line does NOT carry a privacy: marker.
#
# Covers both Logger.info-style instance calls (via .info/.debug/etc. method
# pattern) and bare log-function calls (os_log, NSLog, print, etc.).
CRED_CALL_RE='(\.(info|debug|error|warning|fault|notice|trace|log|critical)|os_log|NSLog|print|debugPrint|dump)[[:space:]]*\(.*\\\(.*([kK]ey|[sS]ecret|[tT]oken|[cC]redential|[pP]assword).*\)'
PRIVACY_MARKER_RE='privacy:[[:space:]]*\.(private|sensitive)'

# --- Pattern 2: print() calls dumping env dict. ----------------------------
ENV_DUMP_RE='print[[:space:]]*\(.*env\b'

# --- Pattern 3: a key-shaped literal in source. ----------------------------
# The same shapes the runtime redactor masks (BristlenoseShared.redactKeys),
# found in Swift source rather than in a log line. Tests are excluded, so a
# fake key lives there. Azure shapes (design-azure-connection.md section 12):
#   - 84 characters of [A-Za-z0-9_-] as a whole token (a dashed GUID is 36, a
#     SHA-1 40, a SHA-256 64, so none can match). ERE has no lookaround, so a
#     letter-and-digit requirement lives in the filter below, not here.
#   - exactly 32 hex only right after a key-ish word and a ":" or "=" (a bare
#     32-hex is also a dashless GUID or an MD5).
KEY_LIT_RE_PREFIX='(sk-ant-(api|sid)[0-9]{2}-[A-Za-z0-9_-]{90,}|sk-(proj|None)-[A-Za-z0-9_-]{48,}|AIza[A-Za-z0-9_-]{35})'
KEY_LIT_RE_84='(^|[^A-Za-z0-9_./-])[A-Za-z0-9_-]{84}($|[^A-Za-z0-9_/-])'
_KW='([kK][eE][yY]|[sS][eE][cC][rR][eE][tT]|[tT][oO][kK][eE][nN]|[pP][aA][sS][sS][wW][oO][rR][dD]|[aA][uU][tT][hH][oO][rR][iI][zZ][aA][tT][iI][oO][nN])'
_BR='[bB][eE][aA][rR][eE][rR][[:space:]]+'
_Q='["'"'"']?'
KEY_LIT_RE_HEX32="${_KW}${_Q}[[:space:]]*[:=][[:space:]]*${_Q}(${_BR})?[0-9a-fA-F]{32}(\$|[^0-9A-Za-z])|${_BR}${_Q}[0-9a-fA-F]{32}(\$|[^0-9A-Za-z])"

violations=0
report_violation() {
    violations=$((violations + 1))
    echo "$1"
}

scan_file() {
    local file="$1"
    # Skip test files.
    case "$file" in *Tests.swift) return 0 ;; esac

    # Pattern 1: credential-shaped interpolations without privacy marker.
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        if echo "$hit" | grep -qE "$PRIVACY_MARKER_RE"; then
            continue  # has marker, fine
        fi
        if is_allowlisted "$hit"; then
            continue
        fi
        report_violation "violation[cred-call]: $hit"
    done < <(grep -nE "$CRED_CALL_RE" "$file" 2>/dev/null || true)

    # Pattern 2: print(env ...) dumps.
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        if is_allowlisted "$hit"; then
            continue
        fi
        report_violation "violation[env-dump]: $hit"
    done < <(grep -nE "$ENV_DUMP_RE" "$file" 2>/dev/null || true)

    # Pattern 3: key-shaped literals.
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        if is_allowlisted "$hit"; then
            continue
        fi
        report_violation "violation[key-literal]: $hit"
    done < <({ grep -nE "$KEY_LIT_RE_PREFIX|$KEY_LIT_RE_HEX32" "$file" 2>/dev/null || true
               # 84-char whole token that holds at least one letter and one digit.
               grep -noE "$KEY_LIT_RE_84" "$file" 2>/dev/null | while IFS=: read -r n tok; do
                   core=$(printf '%s' "$tok" | grep -oE '[A-Za-z0-9_-]{84}')
                   if printf '%s' "$core" | grep -q '[0-9]' && printf '%s' "$core" | grep -q '[A-Za-z]'; then
                       printf '%s:%s\n' "$n" "$(sed -n "${n}p" "$file")"
                   fi
               done; })
}

while IFS= read -r swift_file; do
    scan_file "$swift_file"
done < <(find "$SCAN_ROOT" -type f -name "*.swift" -not -name "*Tests.swift")

if [ "$violations" -gt 0 ]; then
    echo "" >&2
    echo "logging-hygiene: $violations violation(s) found." >&2
    echo "Either (a) add privacy: .private / .sensitive on the call," >&2
    echo "       (b) refactor to not interpolate the credential, or" >&2
    echo "       (c) add an allowlist entry in desktop/scripts/logging-hygiene-allowlist.md" >&2
    echo "           with justification, using the HYG-<N> marker format." >&2
    exit 1
fi

bn_step_ok 1 detail="clean (scan root: $(basename "$SCAN_ROOT"))"
bn_done ok
