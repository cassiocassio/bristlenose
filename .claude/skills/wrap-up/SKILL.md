---
name: wrap-up
description: End-of-chunk ritual — update docs for humans (TODO, CHANGELOG, design docs) and robots (CLAUDE.md gotchas, auto-memory), then commit
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Agent, TodoWrite
---

Wrap up the current chunk of work. "Document for humans and for robots, then commit."

This skill has three phases: **verify**, **document**, **commit**. Run all three unless the user says to skip one.

## Phase 1: Verify (green before documenting)

1. **Run tests** — `.venv/bin/python -m pytest tests/`
2. **Run linter** — `.venv/bin/ruff check .` (whole repo, not just `bristlenose/`)
3. If frontend files changed: `cd frontend && npm run build` (tsc catches type errors Vitest doesn't)

If anything fails, **stop and fix before documenting**. Don't document a broken state.

## Phase 2: Document

Two audiences, done in parallel where possible.

### For humans (what changed, what's left, how to work with it)

4. **`TODO.md`** — mark completed items done, add new items discovered during the session. Update the "Last updated" date. If the near-horizon roadmap changed, reorder it.

5. **Design docs** — if the session produced or updated a design doc (`docs/design-*.md`), check that it reflects the final state, not an intermediate plan. Remove stale TODOs inside design docs that were resolved.

6. **`CHANGELOG.md`** — if a version was bumped, add an entry. Format: `**X.Y.Z** — _D Mon YYYY_`. If no version bump, skip.

7. **`README.md`** — if a version was bumped, update the changelog section. If a user-visible feature shipped, add it to the feature list if appropriate. Don't touch README for internal-only changes.

8. **`CONTRIBUTING.md`** — only if design system, release process, or dev setup changed.

### For robots (corrections, patterns, and conventions for future sessions)

9. **CLAUDE.md gotchas** — review the session for anything Claude got wrong, had to retry, or learned the hard way. Add corrections to the appropriate CLAUDE.md file:
   - Root `CLAUDE.md` — project-wide conventions, infrastructure gotchas
   - `frontend/CLAUDE.md` — React/TS/Vite patterns, test gotchas
   - `bristlenose/theme/CLAUDE.md` — CSS, design system
   - `bristlenose/stages/CLAUDE.md` — pipeline, transcript format
   - `bristlenose/llm/CLAUDE.md` — providers, credentials
   - `bristlenose/server/CLAUDE.md` — FastAPI, data API
   - `desktop/CLAUDE.md` — macOS app, bridge, SwiftUI

   **The test:** "If I removed this line, would a future Claude session make the same mistake?" If yes, add it. If not, skip it. Don't add things Claude can infer from reading the code.

10. **Auto-memory** — save anything that should persist across conversations but doesn't belong in CLAUDE.md:
    - User preferences or feedback given during the session
    - Project context (deadlines, stakeholder decisions, external constraints)
    - References to external systems discovered
    - Patterns confirmed as correct (not just corrections — record successes too)

    Write to `/Users/cassio/.claude/projects/-Users-cassio-Code-bristlenose/memory/` following the memory file format (frontmatter with name, description, type). Update `MEMORY.md` index if a new file was created.

    **Skip if nothing new was learned.** Don't write memory for the sake of writing memory.

### What NOT to update

- Don't update CLAUDE.md with things that are already obvious from the code
- Don't add session-specific debugging notes (the fix is in the code; the commit message has the context)
- Don't copy code into docs (it goes stale — use file:line pointers instead)
- Don't update test counts or file counts in memory unless they changed significantly (50+)

## Phase 3: Commit

11. **Check for uncommitted changes** — `git status` + `git diff --stat`

12. **Stage and commit** — commit all changes from this chunk with a descriptive message. If multiple logical changes were made, ask the user whether to bundle into one commit or split.

    Commit message style: short, descriptive, lowercase. Examples:
    - `add security findings to TODO, document bridge handler wiring`
    - `fix tag suggest offering tags the quote already has`
    - `inspector panel with drag-resize and signal card selection`

13. **Don't push** unless the user explicitly asks. Remind them of the evening release rule (after 9pm London on weekdays; weekends any time). If they want to see work remotely before release: `git push origin main:wip`.

## What to skip

- **No maintenance schedule check** — only do this at actual session end, not every chunk
- **No branch cleanup** — only at session end
- **No CI verification** — only after push
- **No human QA suggestions** — those belong at the end of the implementation step, not wrap-up

## Output

After completing, print a brief summary:

```
Wrapped up:
- Tests: passed (N tests)
- Lint: clean
- Updated: TODO.md, desktop/CLAUDE.md (list what was touched)
- Memory: saved feedback on X (or "nothing new")
- Committed: "commit message here" (N files, +X -Y lines)
- Not pushed (evening release rule)
```
