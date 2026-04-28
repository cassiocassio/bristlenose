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
    for pat in "${ALLOW_REGEXES[@]}"; do
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

echo "logging-hygiene: clean (scan root: $SCAN_ROOT)"
