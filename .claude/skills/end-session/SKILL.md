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

### Durable-artefact audit

Catches **things this branch did that aren't yet visible in the project's durable artefacts.** Two scans share one engine; a single consolidated prompt presents both kinds of finding so the user judges them as one set instead of context-switching between two pop-ups.

The two failure modes the audit catches — both have repeatedly cost plan-cycles when missed:

- **Scan A: decision burial** — branch made a deliberate scope reduction or affordance choice, but the decision lives only in a commit body. Future plan-pickups don't `git log -p` so they propose the rejected approach again. Worked example: F49 (`e4037d5`, 15 May 2026) chose `icloud` outline over `icloud.and.arrow.down` and deferred explicit download to post-TF. 3 days later, `multi-project-cloud-evicted`'s handoff proposed exactly the rejected affordance because nothing in `docs/` knew F49 had decided otherwise.
- **Scan B: incidental closure** — branch shipped something that was captured as an open bullet in a planning doc as a side-effect of larger work. Bullet stays open indefinitely until a sitrep catches it. 18 May 2026 audit during a high-merge window found ~33% silent-closure rate (4 of 12 captured bullets had already shipped under unrelated commits).

**Skip the whole audit** if the branch touched only docs / config / lockfiles (signal-to-noise too low). Audit is otherwise non-blocking — empty result on both scans = silent skip.

#### Shared engine

**Window** — what range of commits constitutes "this branch":
- On a feature branch: `git merge-base main HEAD`..HEAD
- On direct-on-main: HEAD~N where N = commits since last `/end-session` (from `.claude/last-end-session.json`'s `head_sha`). If no prior sentinel, fall back to HEAD~10 and note this in the prompt so the user can see the audit isn't anchored.

**Inputs**:
```bash
WINDOW_BASE=$(git merge-base main HEAD 2>/dev/null || echo HEAD~10)
git log "$WINDOW_BASE"..HEAD --format="%H%n%B%n---END---"     # commit bodies — Scan A
git log "$WINDOW_BASE"..HEAD --pretty=%s                       # commit subjects — Scan B keywords
git diff "$WINDOW_BASE"..HEAD --name-only                      # files touched — Scan B keywords
```

**Sentinel `audit_version`** — when running the audit, also note the `audit_version` you implemented for inside the sentinel JSON written at step 13a. `/close-branch`'s Step 3.5 will read this to detect "sentinel exists but predates audit feature" (treat as if the sentinel were missing — re-prompt for `/end-session`). Current audit_version: `1`.

**Consolidated prompt** — once both scans have candidates, present them in a single audit summary:

```
End-of-session audit
====================

Decisions to promote (Scan A — commit bodies → design docs):
 A1. e4037d5: "icloud (outline), not icloud.and.arrow.down …" → docs/design-decisions.md?
 A2. ...

Bullets to close (Scan B — branch diff → planning trackers):
 B1. [100days.md:267] sidebar drag-drop into folder — matched on `FolderRow.swift`
 B2. [TODO.md:42] ...

For each, answer:
 - <ID> yes              (apply the proposed edit)
 - <ID> defer            (skip this session, surface again next /end-session)
 - <ID> no               (record nothing — false match or genuinely still open)
 - <ID> CLAUDE.md        (Scan A only — write to CLAUDE.md gotchas instead of design docs)
 - <ID> <other path>     (write to a specific doc you name)
 - all yes / all no / all defer
```

`'defer'` is the third option (genuinely uncertain whether to promote / strike). Without it, "no" carries two semantics — *false match* and *don't decide yet* — and the audit can't distinguish the two on next run.

**Instrumentation** — log one line per audit to `.claude/audit-log.jsonl` (gitignored), so we can tune the noise budget against the catch rate:

```json
{"date": "2026-05-18", "branch": "<branch>", "head_sha": "<sha>",
 "scan_a": {"surfaced": 2, "yes": 1, "defer": 0, "no": 1},
 "scan_b": {"surfaced": 5, "yes": 3, "defer": 0, "no": 2}}
```

After ~10 audited sessions, review the log: if "no" rate is consistently >70%, the matchers are too loose; tighten the regex / keyword filter. If catch is genuinely cold (consistently 0 surfaced even when branch was substantive), they're too tight.

#### Scan A — decision burial

**Matcher** — grep commit bodies for decision-shaped sentences:

```bash
git log "$WINDOW_BASE"..HEAD --format="%H%n%B%n---END---" | \
  grep -B1 -iE "(^| )not [a-z.]+|deferred to|explicitly (chose|rejected)|chose .+ over|post-TF|v2 only|rather than|status-only|never wire|did NOT|out of scope"
```

**Doc targets** for promotion (proposed in this order; user can override):
- `docs/design-decisions.md` — the default for user-facing affordance choices.
- The most-relevant `docs/design-*.md` — when the decision is feature-specific (e.g. iCloud handling → `docs/design-multi-project.md`).
- Root `CLAUDE.md` or a sibling `CLAUDE.md` — when the decision is internal mechanics that future Claude might re-invent (use `proc_pidpath` not `subprocess`, `cp -RL` breaks bundle rpath, etc.). The grep already prefilters for affordance-shaped language, so this branch is rare but real.

**Already-recorded check** — before prompting, grep the proposed target for the feature/affordance keyword. If the decision is already there, silently drop the candidate. Avoids reflexive-dismissal noise.

**Promotion format** — append a one-line entry:

```markdown
- <area>: <decision in one line>. Reason: <quote from commit body>. (`<short-sha>`, D Mon YYYY)
```

**Edge cases:**
- Multiple decisions in one commit body → surface as separate candidates; user can answer them independently.
- Decision is partial / "we'll see" — user picks `defer`; surfaces again next session. If still partial after 3 deferrals, the matcher should probably loosen.
- Decision is internal-mechanics-shaped → prompt offers `CLAUDE.md` as a target alongside the design docs.

**What this won't catch (by design):**
- Decisions phrased as plain English without the matcher's keywords (*"We're going with foo for now."*) — recall floor. Bias toward writing commit bodies with the keywords when the decision is durable.
- Decisions made in code comments without a matching commit body line — the audit doesn't read diffs for prose. (`/end-session` step 10 — CLAUDE.md gotchas — is the right place for those.)
- Decisions made in conversation that never landed in commit text — out of band; needs a different mechanism (e.g. memory file or explicit prompt at session end).

#### Scan B — incidental closure

**Keyword extraction** from window inputs:
- File basenames stripped of extension (`ProjectRow`, `cli`, `s12_render`)
- Path fragments (`theme/`, `stages/s07`, `frontend/src/islands`, `desktop/Bristlenose/`)
- Non-stopword nouns from commit subjects
- Cap to ~30 most distinctive tokens
- Filter out generic noise: `package.json`, `README`, `CHANGELOG`, `BRANCHES`, `MEMORY`, `TODO`, `CLAUDE`, lockfiles

**Doc set**:
- `docs/private/100days.md`
- `TODO.md`
- `docs/private/plans/*.md`
- `CHANGELOG.md` (catches bullets announced as shipped that never got the planning-doc strike-through — same matcher, different target)

**Candidate** = any markdown bullet that is BOTH:
- unstruck (not enclosed in `~~ ... ~~`)
- not already marked shipped (no `✅` token + sha pattern)

**Ranking** — by keyword-hit count, weighting file-path matches higher than commit-noun matches (paths are higher-signal). Cap to top 10. Each surfaced candidate carries its match reason inline so the user judges confidence at a glance.

**Open question — match presentation:** show a numeric confidence score, or stay with the inline match-reason hint we ship today? Numeric score helps the top-10 cap but adds complexity. Worth letting the audit-log data answer empirically before deciding. (Plan author flagged this; leaving open.)

**Open question — filename-only thoroughness:** path matches with no bullet-text overlap are excluded by default (high recall, low precision, reflexive-dismissal risk). User can request `'more'` to surface ranks 11–20, but `'more'` overloads two axes (overflow + filename-only). Probably wants a separate `'thorough'` answer that adds the filename-only candidates to the prompt. Leaving open until usage shows whether reflexive-dismissal materialises.

**Apply strike-throughs.** For each confirmed closure:
- Wrap the matched bullet span with `~~ ... ~~`
- Append ` ✅ shipped <today as "D Mon YYYY"> (`<sha>`)`
- `<sha>` = merge commit on PR branches, HEAD on direct-on-main
- Date format matches existing in-document convention (`D Mon YYYY`, e.g. `18 May 2026`)

**Edge cases:**
- No matches → silent skip.
- User says `no` → record nothing; unstruck bullets stay open. Primary false-positive mode is *"file mentioned but bug still present"* — human is the right judge.
- >10 matches → cap at 10; `'more'` shows 11–20.
- Audit runs after `/end-session` aborts → no harm, idempotent (struck bullets are filtered next time).

**What this won't catch (by design):**
- "Capture was wrong at capture time" — bullet describes something never broken; needs a different periodic audit (sibling tool, not this).
- "Branch closed a bug whose surface keywords aren't in the diff" — purely symptom-described bullets (*"Analysed in 0 sec"*) may not match if the formatter site doesn't contain that string. Recall floor.
- "Could have closed while you were nearby" — adjacent-but-not-touched bullets. Different problem; out of band.

**Worked examples that motivated this scan** (18 May 2026 audit during a high-merge window — ~33% silent-closure rate, 4 of 12):
- Sidebar row-height jump on new project — fixed during `multi-project-folder-watcher` row reshape; commit said *"F53 subtitle text uses .secondary uniformly"*, never mentioned the bullet.
- Multi-select projects (Shift/Cmd-click) — fell out of the `Set<SidebarSelection>` evolution; code comment says *"Set enables Cmd+click / Shift+click multi-select natively"*; tracker never updated.
- Sidebar drag-drop into folder — landed in `multi-project-drag-onto`; commit message (*"copy machinery, progress pill, NewFilesSheet stub"*) didn't list it.
- (Fourth audit hit was a "capture-mode-2" finding — pre-existing capability mis-captured. Excluded by design; the right behaviour is to leave such bullets unstruck so they get re-examined in a periodic reverse-audit, not closed here.)

#### Tuning

Steady-state silent-closure rate may be lower outside high-merge windows. After ~10 audited sessions of audit-log data, review:
- Per-scan "no" rate (too high → matcher too loose)
- Per-scan "surfaced" rate when branch was substantive (too low → matcher too tight)
- Per-scan "defer" half-life (deferred items resolved within 3 sessions, or accumulating?)

Tighten / loosen the regex and keyword filter accordingly. Update `audit_version` in the sentinel JSON when the matcher changes materially so `/close-branch` can detect "sentinel from old audit_version" and re-prompt.

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

### Handoff drift (this branch's own handoff)

If this session implemented against a `HANDOFF.md` (symlink to `.claude/plans/<branch>.md`, canonical home `~/Code/bristlenose/docs/private/handoffs/<branch>.md`), capture any judgement calls that deviated from the original §Scope before closing.

**Why:** the original §Scope is what QA reads against. If the implementer changed a control from disabled-to-hidden, picked a different component than specced, deferred a sub-item to a follow-up branch, or chose inline over an extracted molecule — and only documented it in a code comment — QA verifies against the wrong spec. The fix is to log the drift in the handoff as it happens, so the next reader (QA, reviewer, future-Claude) sees the current spec alongside the original reasoning.

**Heuristic — fire the prompt automatically.** Grep this session's commits and changed files for deviation markers; if any match, run the prompt below. (If they don't match, still ask once — the implementer may have made an undocumented call.)

```bash
# Commit messages since branch diverged from main
git log main..HEAD --format=%B | grep -iE "judgement call|decided to|instead of|deviation|chose .* over|hide.*instead|disabled.*instead"
# Code comments touched this branch
git diff main...HEAD -- '*.ts' '*.tsx' '*.py' '*.swift' | grep -iE "^\+.*(judgement call|decided to|instead of|reason:|rather than|visual noise)"
```

**Prompt to the user (or to self if running autonomously):**

> Did you make any judgement calls during implementation that weren't in the original handoff? Common examples:
> - changing a control from disabled-to-hidden (or vice versa)
> - picking a different component over the one specced
> - deferring a sub-item to a follow-up branch
> - choosing inline over an extracted molecule (or vice versa)
> - swapping an icon, copy string, or interaction pattern
>
> If yes, append to §Decisions in `HANDOFF.md` before closing.

**Pattern — append-only `## Decisions during implementation` block.** Preserve the original §Scope verbatim (useful for "why did we change our mind?"); the §Decisions block carries the current spec. QA reads both together.

```markdown
## Decisions during implementation

- YYYY-MM-DD: <decision in one line>. Reason: <why>. Supersedes §<section> "<original wording verbatim>".
```

Example (from `pipeline-completion-trust-ux`, 10 May 2026):

```markdown
- 2026-05-10: RefreshButton renders nothing when `lastRun === null` rather than rendering disabled. Reason: a disabled control with no path to enabled is just visual noise; empty-state copy carries the page. Supersedes §Scope item 1 "Pre-pipeline state: button is disabled (no run to refresh against). Read `lastRun === null` from the store."
```

Edit the **canonical** path (`~/Code/bristlenose/docs/private/handoffs/<branch>.md` in the main repo) so the change survives worktree removal. The `HANDOFF.md` symlink in this worktree points at the `.claude/plans/` copy — if the canonical path no longer exists, write to whichever path resolves.

If this session did not work off a HANDOFF, skip this step.

### Branch handoffs (only if this session identified follow-up branches)

If this session was a diagnostic / sandpit / planning walk that identified one or more follow-up branches the next session should pick up — **write a handoff prompt for each** before closing out. Do not assume the next session will reverse-engineer it from your logs.

Path: `~/Code/bristlenose/docs/private/handoffs/<branch>.md` (gitignored, lives in main repo, picked up automatically by `/new-feature <branch>`).

Required shape: see `docs/private/handoffs/README.md` in that directory. Sections — Purpose / Context (cold-read) / Spec / Call sites / Acceptance / Out of scope / Open questions. Self-contained — readable cold by a fresh session.

**`/new-feature` invocation line — `--kind` is a closed enum.** When you draft the recommended `/new-feature <branch> --plan=… --kind=… --purpose=… --files=…` line at the bottom of the handoff, `--kind` MUST be one of: `feature | diagnostic | spike | chore | parked`. These are the five values defined in `docs/BRANCHES.md` §"Branch Kinds (merge intent)" — the single source of truth — and they encode *merge intent / end-of-life*, not area. Do not invent area-shaped kinds (`desktop`, `i18n`, `ci`, `fix`, `infrastructure`, `research`, `tooling`); those belong in `--purpose` or in the "Files this branch will touch" list. If the new branch's code is intended for main, the kind is `feature`. `/new-feature` will reject anything outside the enum and stop before creating the branch.

**The test:** "If a future Claude session opened the new branch and read only this file, would they know exactly what to do?" If no, expand the handoff before closing the session. The cost of writing it now is a few minutes; the cost of skipping it is the next session re-doing the diagnostic walk to figure out its own purpose.

If this session did **not** identify follow-up branches, skip this step.

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

13a. **Write end-of-session sentinel** — once Phase 2 (document) has completed successfully and any required commit has landed (or has been skipped because there was nothing to commit), write `.claude/last-end-session.json` in the worktree root. This trigger is independent of step ordering — it fires whether the session went through the standard commit path (step 13), the branch-handoff path, or the no-changes-to-commit short-circuit. Write only once per `/end-session` invocation; subsequent steps (maintenance, QA backlog, push) don't re-trigger it. The sentinel reflects "documenting was committed", not "push succeeded" — `pushed` records the decision made at step 17, but the sentinel's primary consumer (`/close-branch` drift detection) only reads `head_sha`. This is the positive sentinel `/close-branch` reads to confirm sign-off and detect drift. Gitignored.

   Schema (ASCII-only — use `ensure_ascii=True` if writing via Python):

   ```json
   {
     "completed_at": "2026-05-14T09:52:18Z",
     "head_sha": "<full 40-char SHA from git rev-parse HEAD>",
     "branch": "<git branch --show-current>",
     "phases": {
       "verify": "ok" | "skipped-docs-only" | "skipped-no-changes",
       "document": "ok" | "skipped",
       "commit": "ok" | "skipped-no-changes"
     },
     "tests": "passed" | "skipped" | "failed",
     "lint": "clean" | "skipped" | "errors",
     "handoff_drift": "none" | "appended" | "no-handoff",
     "audit_version": 1,
     "pushed": false | "origin/main" | "origin/main:wip" | "origin/<branch>"
   }
   ```

   `audit_version` records which version of the Durable-artefact audit (Scan A + B) ran during this end-session. Bump when the matcher or doc set changes materially. `/close-branch`'s Step 3.5 reads it to distinguish "sentinel current with current audit" from "sentinel from before audit feature / from old audit_version" — both treated as stale and re-prompted. Current `audit_version`: `1`.

   Timestamp via `date -u +"%Y-%m-%dT%H:%M:%SZ"`. Write only on successful completion of Phase 3 commit (or successful no-op skip). If `/end-session` aborts mid-phase, leave any prior sentinel in place — stale-but-truthful beats absent. Re-running `/end-session` overwrites with the new timestamp; that's fine.

14. **Maintenance schedule check** — read the "Dependency maintenance" section of `TODO.md`. If today's date is past any unchecked quarterly/annual item, remind the user it's due.

15. **QA backlog reminder** — check `docs/qa-backlog.md` for unacked items. Remind the user if any exist.

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
- Handoff drift: appended 1 decision to HANDOFF.md (or "none" / "no handoff")
- Committed: "commit message here" (N files, +X -Y lines)
- Sentinel: wrote .claude/last-end-session.json (HEAD <short-sha>)
- Maintenance: nothing due (or "May 2026 dep review is due")
- QA backlog: 0 unacked (or "3 items need review")
- Not pushed (evening release rule — push with `git push origin main`)
```
