# CODEX.md

Codex starts at [`AGENTS.md`](AGENTS.md), which points at [`CLAUDE.md`](CLAUDE.md)
for the conventions both harnesses share. There is no separate Codex rulebook:
a rule that lives only here is a rule Claude never sees.

Branching is trunk by default: work on `main` in the shared checkout, and use a
worktree only when two environments must be live at once (`AGENTS.md` §
"Isolation is an exception with a complete lifecycle"). Do not add a
per-feature worktree rule here.

Working style both harnesses follow:

- Small, reviewable commits with clear intent; stage only the paths you own.
- Working code plus tests over speculative refactors. Behaviour changes update
  tests in the same commit.
- Python changes: `ruff check .` and the relevant tests. Frontend changes: lint,
  typecheck and Vitest.
- Say risks and trade-offs plainly. Recommend one default when there is a choice.
- Ask before anything destructive or broad.

Handoff rules (ownership, records, pickup) are in `CLAUDE.md` § Session-end
housekeeping.
