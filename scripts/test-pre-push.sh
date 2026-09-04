#!/bin/bash
# test-pre-push.sh — proves scripts/git-hooks/pre-push refuses, rather than
# reporting clean because it is blind.
#
# Drives the hook directly with fabricated "<local ref> <local sha> <remote ref>
# <remote sha>" lines; no push happens. The leaky ref is built from plumbing
# (hash-object / mktree / commit-tree) around a path the current .gitignore
# ignores, so the suite depends on no particular branch surviving and never
# touches the index or the working tree. The dangling commit is garbage.
#
# The case that matters is "offender SECOND in a multi-ref push": pre-commit's
# pre-push stage returns on the first pushable ref and cannot fail it.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. scripts/test-lib.sh

hook=scripts/git-hooks/pre-push
zero=0000000000000000000000000000000000000000
ignored=.env   # must be ignored by the current rules, or the suite proves nothing

head_ "fixtures"
if git check-ignore --no-index -q "$ignored"; then ok "'$ignored' is ignored by the current rules"
else bad "'$ignored' is not ignored — the suite would prove nothing"; finish; fi
if git check-ignore --no-index -q README.md; then bad "README.md reads as ignored — rules are broken"; finish
else ok "README.md is not ignored (rules sane)"; fi

clean=$(git rev-parse main)
blob=$(printf 'leak\n' | git hash-object -w --stdin)
tree=$(printf '100644 blob %s\t%s\n' "$blob" "$ignored" | git mktree)
leaky=$(git commit-tree "$tree" -m "test-pre-push: fabricated leaky commit")
ok "fabricated a commit whose tree carries $ignored (${leaky:0:8}, dangling)"

# rc <line>... — the hook's exit code for those stdin lines; runs in $(...) so
# the set +e is local to the subshell and cannot leak into the suite.
rc() {
  set +e
  if [ $# -gt 0 ]; then printf '%s\n' "$@"; fi | "$hook" origin https://example.invalid >/dev/null 2>&1
  echo $?
}

head_ "the gate"
eq "clean branch alone passes"                          0 "$(rc "refs/heads/main $clean refs/heads/main $clean")"
eq "leaky branch alone is refused"                      1 "$(rc "refs/heads/leak $leaky refs/heads/leak $zero")"
eq "leaky ref SECOND in a multi-ref push is refused"    1 "$(rc "refs/heads/main $clean refs/heads/main $clean" "refs/heads/leak $leaky refs/heads/leak $zero")"
eq "leaky TAG is refused — tags are refs too"           1 "$(rc "refs/tags/leak $leaky refs/tags/leak $zero")"
eq "a deletion passes — nothing to inspect"             0 "$(rc "(delete) $zero refs/heads/leak $leaky")"
eq "empty push passes"                                  0 "$(rc)"
eq "a blank line is tolerated, not a broken gate"       0 "$(rc "")"
eq "an unreadable sha is a hard error (2), not a pass"  2 "$(rc "refs/heads/x deadbeefdeadbeefdeadbeefdeadbeefdeadbeef refs/heads/x $zero")"

head_ "the refusal names the file"
msg=$(printf '%s\n' "refs/heads/leak $leaky refs/heads/leak $zero" | "$hook" origin u 2>&1 >/dev/null || true)
case "$msg" in *"$ignored"*) ok "refusal names $ignored" ;; *) bad "refusal does not name the offending path" ;; esac

finish
