# CODEX.md

Working agreement for Codex ↔ Cassio collaboration on this repo.

## Purpose

This file captures how we like to work together so each new session starts with the same expectations.
Treat this as a living document: short, practical, and updated as we learn.

## Branching and Worktrees

- Use feature branches in dedicated worktrees (`/Users/cassio/Code/bristlenose_branch <name>`).
- Keep `/Users/cassio/Code/bristlenose` on `main`.
- Keep branch setup/teardown aligned with `.claude/skills/new-feature` and `.claude/skills/close-branch`.
- Update `docs/BRANCHES.md` when starting/closing branches.

## Delivery Style

- Prefer small, reviewable commits with clear intent.
- Prioritize working code plus tests over large speculative refactors.
- Call out risks and tradeoffs directly; avoid vague reassurance.
- Keep momentum: implement, verify, summarize, suggest next step.

## Quality Bar

- For Python changes: run lint + relevant tests.
- For frontend changes: run lint, typecheck, and Vitest.
- CI should gate both backend and frontend regressions.
- If behavior changes, add or update tests in the same branch.

## Communication Preferences

- Be concise and explicit.
- Surface blockers quickly.
- Ask before destructive or broad-impact actions.
- When choices exist, recommend one default and explain why.

## Evolving This File

- Add concrete conventions, not philosophy.
- Keep entries short and actionable.
- If a rule stops helping, revise or delete it.
