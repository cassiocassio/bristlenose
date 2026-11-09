#!/bin/bash
# Negative fixtures for check-tracked-vs-gitignore.sh.
#
# The gate exists because a .gitignore rule written AFTER a file was committed gives false
# confidence: git keeps tracking the file, so it is public while looking ignored. A gate that
# could not fail would be the same false confidence one level up. Each case builds a scratch git
# repo and runs the gate inside it, so the real tree is never touched.
#
# Usage: scripts/test-check-tracked-vs-gitignore.sh
# Exit:  0 all cases behaved · 1 at least one gate failed to fail (or failed a clean fixture)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GATE="$SCRIPT_DIR/check-tracked-vs-gitignore.sh"
[ -x "$GATE" ] || { echo "gate not executable: $GATE" >&2; exit 2; }

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bn-gitignore-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

# A fresh repo with identity set and hooks off, so a developer's global config cannot change it.
repo() {  # <name>
    local d="$TMP/$1"
    mkdir -p "$d" && git -C "$d" init -q
    git -C "$d" config user.email test@example.invalid
    git -C "$d" config user.name test
    git -C "$d" config core.hooksPath /dev/null
    echo "$d"
}
commit() { git -C "$1" add -A >/dev/null 2>&1; git -C "$1" commit -q -m "$2" >/dev/null 2>&1; }

expect() {  # <label> <want-exit> <want-substring-or-empty> <repo>
    local label="$1" want="$2" needle="$3" d="$4" out rc
    out=$(cd "$d" && "$GATE" 2>&1); rc=$?
    if [ "$rc" -ne "$want" ]; then
        echo "  ✗ $label: exit $rc, wanted $want"; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    if [ -n "$needle" ] && ! printf '%s' "$out" | grep -qF -- "$needle"; then
        echo "  ✗ $label: exit $rc but no \"$needle\""; echo "$out" | sed 's/^/      /' | head -6; FAIL=$((FAIL+1)); return
    fi
    echo "  ✓ $label"; PASS=$((PASS+1))
}

echo "check-tracked-vs-gitignore negative fixtures"

d=$(repo clean); echo a > "$d/notes.txt"; commit "$d" first
expect "a repo whose tracked files are all unignored is clean" 0 "No tracked files match" "$d"

d=$(repo ignored-untracked); echo a > "$d/notes.txt"; echo "scratch.txt" > "$d/.gitignore"; echo b > "$d/scratch.txt"
commit "$d" first
expect "an ignored file that was never committed is clean" 0 "No tracked files match" "$d"

d=$(repo late-rule); mkdir -p "$d/private-notes"; echo secret > "$d/private-notes/plan.md"; commit "$d" first
echo "private-notes/" > "$d/.gitignore"; commit "$d" "ignore it too late"
expect "a file committed before its ignore rule is a violation" 1 "private-notes/plan.md" "$d"

d=$(repo forced); echo "*.key" > "$d/.gitignore"; echo k > "$d/id.key"
git -C "$d" add .gitignore >/dev/null 2>&1; git -C "$d" add -f id.key >/dev/null 2>&1; commit "$d" first
expect "a force-added ignored file is a violation" 1 "id.key" "$d"

d=$(repo two); echo a > "$d/a.log"; echo b > "$d/b.log"; commit "$d" first
echo "*.log" > "$d/.gitignore"; commit "$d" ignore
expect "every offender is named, not just the first" 1 "b.log" "$d"

d=$(repo fixed); echo a > "$d/old.log"; commit "$d" first
echo "*.log" > "$d/.gitignore"; git -C "$d" rm -q --cached old.log; commit "$d" untrack
expect "untracking the file (git rm --cached) clears the violation" 0 "No tracked files match" "$d"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
