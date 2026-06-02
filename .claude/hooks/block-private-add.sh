#!/bin/bash
# PreToolUse (Bash) hook: blocks `git add` of paths under docs/private/.
# docs/private/ is gitignored and holds launch strategy, succession, pricing,
# and other founder-only material. The original leak happened via
# `git add -f docs/private/...` (commit 5ae9eb2: "accidentally added with -f").
# This intercepts that class deterministically in Claude sessions; the
# pre-commit `check-tracked-vs-gitignore.sh` guard is the repo-wide backstop.
# Editing files under docs/private/ is fine — only STAGING them is blocked.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only inspect git add commands.
if echo "$COMMAND" | grep -qE '(^|\s|&&|;|\|)git\s+add\b'; then
  # Block if the command references docs/private (with or without -f).
  if echo "$COMMAND" | grep -qE 'docs/private(/|\b)'; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked: git add of docs/private/. That directory is gitignored on purpose (launch strategy, pricing, succession, Apple credentials) and must never be tracked on the public repo. Do not use git add -f to override. If a file genuinely belongs in the public tree, move it out of docs/private/ first."}}'
    exit 0
  fi
fi

exit 0
