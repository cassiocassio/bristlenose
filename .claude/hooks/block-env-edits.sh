#!/bin/bash
# PreToolUse hook: blocks Edit/Write/MultiEdit to .env files (secrets, gitignored).
# Enforces CLAUDE.md's standing "Never touch .env" rule deterministically, in EVERY
# directory — main repo and all worktrees alike (a gitignored hookify rule can't,
# because gitignored files don't follow into new worktrees).
# Allows template files: .env.example / .env.sample / .env.template.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Match .env, .env.local, .env.production, etc. (a dotfile whose name is exactly
# `.env` or starts with `.env.`), at the path's final component.
BASENAME=$(basename "$FILE_PATH")
if [[ "$BASENAME" == ".env" || "$BASENAME" == ".env."* ]]; then
  # Exempt tracked templates — these are safe to edit and intentionally committed.
  case "$BASENAME" in
    *.example|*.sample|*.template) exit 0 ;;
  esac

  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Blocked: editing a .env file. CLAUDE.md has a standing rule — never touch .env (it holds API keys/secrets and is gitignored). Edit .env.example (the tracked template) instead, or write the secret by hand outside Claude."}}'
  exit 0
fi

exit 0
