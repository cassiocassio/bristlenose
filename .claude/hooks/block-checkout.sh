#!/bin/bash
# PreToolUse hook: blocks git checkout/switch of feature branches in the main repo.
# Only fires for Bash tool calls. Allows: checkout main, checkout -- <file>, checkout -b.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Only guard the main repo directory — worktrees can checkout freely
if [[ "$CWD" != "/Users/cassio/Code/bristlenose" ]]; then
  exit 0
fi

# Check for git checkout or git switch commands
if echo "$COMMAND" | grep -qE '(^|\s*&&\s*|;\s*)git\s+(checkout|switch)\s'; then

  # Allow: git checkout main, git checkout -
  if echo "$COMMAND" | grep -qE 'git\s+(checkout|switch)\s+(main|-)\s*($|&&|;|\|)'; then
    exit 0
  fi

  # Allow: git checkout -- <file> (file-level checkout)
  if echo "$COMMAND" | grep -qE 'git\s+checkout\s+--\s'; then
    exit 0
  fi

  # Allow: git checkout -b / git switch -c (creating a branch)
  if echo "$COMMAND" | grep -qE 'git\s+(checkout\s+-[bB]|switch\s+-[cC])\s'; then
    exit 0
  fi

  # Block everything else — this is a feature branch checkout in the main repo
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked: do not check out feature branches in the main bristlenose/ directory. Use git worktrees instead. Run /new-feature <name> to create a new worktree, or cd to an existing one at /Users/cassio/Code/bristlenose_branch <name>/"}}'
  exit 0
fi

exit 0
