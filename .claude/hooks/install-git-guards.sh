#!/bin/bash
# SessionStart hook: make sure THIS clone carries both git-side guards.
# Idempotent; silent unless it changes something; never blocks a session.
#
# Both guards are per-clone, so a cloud session's fresh clone has neither
# until something installs them -- and cloud sessions push (`claude/*`).
#
#   pre-push   scripts/git-hooks/pre-push -- native hook, every ref. Refuses
#              a push whose tree carries a path the current .gitignore ignores.
#              Needs only the script in the tree, so it always installs.
#   pre-commit pre-commit's own hook (gitleaks + tracked-vs-gitignore). Needs
#              the `pre-commit` binary, which a fresh clone lacks until deps are
#              installed -- so this may skip, and will land on the next session.
#
# NEVER `pre-commit install --hook-type commit-msg` (the leak-scan commit-msg
# hook is hand-installed on the Mac and would be overwritten) or
# `--hook-type pre-push` (pre-commit's stage checks one ref; see CLAUDE.md).

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
common=$(git -C "$root" rev-parse --git-common-dir 2>/dev/null) || exit 0
case "$common" in /*) ;; *) common="$root/$common" ;; esac
[ -d "$common/hooks" ] || mkdir -p "$common/hooks" 2>/dev/null || exit 0

if [ -f "$root/scripts/git-hooks/pre-push" ]; then
  want=../../scripts/git-hooks/pre-push
  if [ "$(readlink "$common/hooks/pre-push" 2>/dev/null)" != "$want" ]; then
    ln -sf "$want" "$common/hooks/pre-push" && echo "install-git-guards: installed pre-push guard"
  fi
fi

if [ ! -f "$common/hooks/pre-commit" ]; then
  pc="$root/.venv/bin/pre-commit"
  [ -x "$pc" ] || pc=$(command -v pre-commit 2>/dev/null) || exit 0
  (cd "$root" && "$pc" install >/dev/null 2>&1) && echo "install-git-guards: installed pre-commit hook"
fi
exit 0
