---
name: end-session
description: End-of-session ritual — verify, document for humans and robots, commit, close out
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Agent, TodoWrite
---

End the current session. "Verify, document for humans and for robots, commit, close out."

This skill has three phases: **verify**, **document**, **commit + close out**. Run all three unless the user says to skip one.

## Phase 1: Verify (green before documenting)

**Skip condition:** if the only changes since the last commit are documentation files (`.md`, `.txt`, locale `.json`, `CLAUDE.md`, `TODO.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `MEMORY.md`, `SKILL.md`), skip Phase 1 entirely — there's nothing to break. Check with `git diff --name-only` and `git diff --cached --name-only` and `git ls-files --others --exclude-standard`.

If code files were changed:

1. **Run tests** — `.venv/bin/python -m pytest tests/`
2. **Run linter** — `.venv/bin/ruff check .` (whole repo, not just `bristlenose/`)
3. If frontend files changed: `cd frontend && npm run build` (tsc catches type errors Vitest doesn't)

If anything fails, **stop and fix before documenting**. Don't document a broken state.

## Phase 2: Document

Two audiences, done in parallel where possible.

### For humans (what changed, what's left, how to work with it)

4. **`TODO.md`** — mark completed items done, add new items discovered during the session. Update the "Last updated" date. If the near-horizon roadmap changed, reorder it.

5. **`100days.md` sprint progress** — read `docs/private/100days.md`. Find the current sprint (check the sprint schedule table against today's date). Compare items tagged with that sprint — and any untagged items — against what was accomplished this session (check `git log --oneline` since session start, TODO.md completions, and the work just done). Strike through completed items with `~~`. If an item is partially done, leave it unstruck but add a brief parenthetical note (e.g. `— phase 1 done, phase 2 remains`). Don't touch items the session didn't work on.

6. **Design docs** — if the session produced or updated a design doc (`docs/design-*.md`), check that it reflects the final state, not an intermediate plan. Remove stale TODOs inside design docs that were resolved.

7. **`CHANGELOG.md`** — if a version was bumped, add an entry. Format: `**X.Y.Z** — _D Mon YYYY_`. If no version bump, skip.

8. **`README.md`** — if a version was bumped, update the changelog section. If a user-visible feature shipped, add it to the feature list if appropriate. Don't touch README for internal-only changes.

9. **`CONTRIBUTING.md`** — only if design system, release process, or dev setup changed.

### For robots (corrections, patterns, and conventions for future sessions)

10. **CLAUDE.md gotchas** — review the session for anything Claude got wrong, had to retry, or learned the hard way. Add corrections to the appropriate CLAUDE.md file:
   - Root `CLAUDE.md` — project-wide conventions, infrastructure gotchas
   - `frontend/CLAUDE.md` — React/TS/Vite patterns, test gotchas
   - `bristlenose/theme/CLAUDE.md` — CSS, design system
   - `bristlenose/stages/CLAUDE.md` — pipeline, transcript format
   - `bristlenose/llm/CLAUDE.md` — providers, credentials
   - `bristlenose/server/CLAUDE.md` — FastAPI, data API
   - `desktop/CLAUDE.md` — macOS app, bridge, SwiftUI

   **The test:** "If I removed this line, would a future Claude session make the same mistake?" If yes, add it. If not, skip it. Don't add things Claude can infer from reading the code.

11. **Auto-memory** — save anything that should persist across conversations but doesn't belong in CLAUDE.md:
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

## Phase 3: Commit + close out

12. **Check for uncommitted changes** — `git status` + `git diff --stat`

13. **Stage and commit** — commit all changes from this chunk with a descriptive message. If multiple logical changes were made, ask the user whether to bundle into one commit or split.

    Commit message style: short, descriptive, lowercase. Examples:
    - `add security findings to TODO, document bridge handler wiring`
    - `fix tag suggest offering tags the quote already has`
    - `inspector panel with drag-resize and signal card selection`

14. **Maintenance schedule check** — read the "Dependency maintenance" section of `TODO.md`. If today's date is past any unchecked quarterly/annual item, remind the user it's due.

15. **QA backlog reminder** — check `docs/private/qa-backlog.md` for unacked items. Remind the user if any exist.

16. **Branch cleanup** — check for merged feature branches that can be deleted. Ask before deleting.

17. **Push decision** — don't push by default. Remind about the evening release rule (after 9pm London on weekdays; weekends any time). If they want to see work remotely before release: `git push origin main:wip`. Push only if the user says to.

18. **CI verification** — only if pushed. Check the latest push passes CI.

## Output

After completing, print a brief summary:

```
End of session:
- Tests: passed (N tests) / skipped (docs only)
- Lint: clean / skipped (docs only)
- Updated: TODO.md, CLAUDE.md (list what was touched)
- 100days: struck through 2 items in S1 (or "no sprint items completed")
- Memory: saved feedback on X (or "nothing new")
- Committed: "commit message here" (N files, +X -Y lines)
- Maintenance: nothing due (or "May 2026 dep review is due")
- QA backlog: 0 unacked (or "3 items need review")
- Not pushed (evening release rule — push with `git push origin main`)
```
