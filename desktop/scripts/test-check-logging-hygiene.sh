#!/usr/bin/env bash
# Negative fixtures for check-logging-hygiene.sh.
#
# A lint that can't fail converts "unchecked" into "checked and fine". This drives the gate red on
# each pattern it claims to catch, against a scratch repo root (the gate takes one as an argument),
# and shows each exemption (privacy marker, allowlist, *Tests.swift) is the only reason a line passes.
#
# A negative case matches the gate's own `violation[<rule>]` line, not just a non-zero exit: a gate
# that rejects every fixture would pass an exit-code check, so the intact fixture must exit 0 too.
#
# BN_REPORT=0 turns off the report renderer, which would otherwise swallow the gate's own lines.
#
# Usage: test-check-logging-hygiene.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-logging-hygiene.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-hygiene-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# A scratch repo root holding one Swift file (and optionally an allowlist). Echoes its path.
fixture() {  # <name> <swift-line> [file-name] [allowlist-entry]
    local root="$TMP/$1" file="${3:-Sample.swift}"
    mkdir -p "$root/desktop/Bristlenose/Bristlenose" "$root/desktop/scripts"
    printf '%s\n' "$2" > "$root/desktop/Bristlenose/Bristlenose/$file"
    if [ -n "${4:-}" ]; then
        printf '%s\n' "$4" > "$root/desktop/scripts/logging-hygiene-allowlist.md"
    fi
    echo "$root"
}

# expect <label> <want-exit> <want-substring-or-empty> <root>
expect() {
    local label="$1" want="$2" needle="$3" root="$4" out rc
    out=$(BN_REPORT=0 "$GATE" "$root" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -8; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! grep -qF -- "$needle" <<<"$out"; then
        echo "  ✗ $label: exit $rc but no \"$needle\" line"; echo "$out" | sed 's/^/      /' | head -8; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

echo "check-logging-hygiene negative fixtures"

expect "a log line with no credential is clean" 0 "" \
    "$(fixture clean 'logger.info("started \(projectName)")')"

expect "a credential interpolated with no privacy marker is a violation" 1 'violation[cred-call]' \
    "$(fixture cred 'logger.info("injected \(apiKey)")')"

expect "the same credential with privacy: .private passes" 0 "" \
    "$(fixture marker 'logger.info("injected \(apiKey, privacy: .private)")')"

expect "the same credential with privacy: .sensitive passes" 0 "" \
    "$(fixture sensitive 'logger.info("injected \(apiKey, privacy: .sensitive)")')"

expect "a token, a secret and a password are caught as well as a key" 1 'violation[cred-call]' \
    "$(fixture token 'logger.error("bad \(authToken)")')"

expect "print(env) is a violation" 1 'violation[env-dump]' \
    "$(fixture envdump 'print("launching", env)')"

expect "an allowlisted line passes" 0 "" \
    "$(fixture allow 'logger.info("provider \(providerKey)")' Sample.swift \
        '<!-- ci-allowlist: HYG-1 --> providerKey')"

expect "an unrelated allowlist entry does not excuse the line" 1 'violation[cred-call]' \
    "$(fixture allow-other 'logger.info("injected \(apiKey)")' Sample.swift \
        '<!-- ci-allowlist: HYG-1 --> somethingElseEntirely')"

expect "a *Tests.swift file is not scanned" 0 "" \
    "$(fixture tests 'logger.info("injected \(apiKey)")' SampleTests.swift)"

K84=$(printf 'aB3xY9kQ%.0s' 1 2 3 4 5 6 7 8 9 10 11 | cut -c1-84)
H32=$(printf 'deadbeef%.0s' 1 2 3 4)
GUID='3d1fae88-0000-4000-8000-000000000000'
SHA1='da39a3ee5e6b4b0d3255bfef95601890afd80709'
SHA256=$(printf 'ab12cd34%.0s' 1 2 3 4 5 6 7 8)

expect "an 84-character key literal is a violation" 1 'violation[key-literal]' \
    "$(fixture lit84 "let k = \"$K84\"")"

expect "a 32-hex literal after a key word is a violation" 1 'violation[key-literal]' \
    "$(fixture lit32 "let h = [\"api-key\": \"x\"]; let s = \"api-key: $H32\"")"

expect "a Bearer 32-hex literal is a violation" 1 'violation[key-literal]' \
    "$(fixture litbearer "let h = \"Authorization: Bearer $H32\"")"

expect "an old-shape literal (Google) is a violation" 1 'violation[key-literal]' \
    "$(fixture litgoogle "let k = \"AIza$(printf 'D%.0s' $(seq 35))\"")"

expect "a GUID request id is clean" 0 "" \
    "$(fixture guid "let h = \"apim-request-id: $GUID\"")"

expect "a bare 32-hex (dashless GUID or MD5) is clean" 0 "" \
    "$(fixture bare32 "let h = \"$H32\"")"

expect "a git SHA-1 and a SHA-256 after a key word are clean" 0 "" \
    "$(fixture sha "let a = \"key: $SHA1\"; let b = \"key=$SHA256\"")"

expect "an 84-character run of one letter is clean" 0 "" \
    "$(fixture letters84 "let k = \"$(printf 'a%.0s' $(seq 84))\"")"

expect "a key-shaped literal in a *Tests.swift file is not scanned" 0 "" \
    "$(fixture litTests "let k = \"$K84\"" SampleTests.swift)"

expect "an allowlisted key-shaped literal passes" 0 "" \
    "$(fixture litallow "let k = \"$K84\"" Sample.swift '<!-- ci-allowlist: HYG-1 --> aB3xY9kQ')"

mkdir -p "$TMP/noroot"
expect "a root with no Swift sources is a usage error, not a pass" 2 "" "$TMP/noroot"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
