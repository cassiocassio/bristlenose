# session-handoff-sentinels

## Purpose

Close the visibility gap between `/new-feature`, `/end-session`, and `/close-branch`: today only the bookends leave durable markers, so a session that lands in a worktree (or returns to one days later) can't tell whether `/end-session` ever ran, against what SHA, or whether HEAD has drifted since.

The concrete failure mode this prevents was hit on 14 May 2026: a parent session added `bf8a4ec` (merge of main) on top of an `/end-session`-validated tip (`3bc1796`) on `ci-version-pinning`. Nothing in the repo flagged that the validated state had moved; the user was the only memory. Same class of bug as the historical `setup-incomplete` sentinel that `/new-feature` already has — solved one end, not the other.

## Context (cold-read)

- Conversation transcript: 14 May 2026 session that closed `tf-phase-1-ux-wins` and `no-red-ci-merges`, then walked `ci-version-pinning`. The zoom-out happened at the end of that session — search the transcript for "zoom out and look at our lifecycles".
- Skills involved:
  - `.claude/skills/new-feature/SKILL.md` (420 lines, owns `.claude/setup-incomplete`)
  - `.claude/skills/end-session/SKILL.md` (165 lines, **no marker today** — the gap)
  - `.claude/skills/close-branch/SKILL.md` (209 lines, owns `_Stale - Merged by Claude DD-Mon-YY.txt`)
- Sentinel convention prior art: `.claude/setup-incomplete` is negative (presence = bad), `_Stale - Merged...txt` is positive (presence = archived). The new sentinel is positive.
- Handoff README: `docs/private/handoffs/README.md`.

## Spec

Two-file core. Resist scope creep — the accretive ideas in the zoom-out (BRANCHES.md Status updates, branch-manifest.json, no-op detection) stay parked unless evidence demands them.

### 1. `/end-session` writes `.claude/last-end-session.json` on success

After Phase 3 completes (commit + close out, post step 13), write a JSON sentinel to `<worktree>/.claude/last-end-session.json`. Gitignored. Schema:

```json
{
  "completed_at": "2026-05-14T09:52:18Z",
  "head_sha": "3bc1796abc...",
  "branch": "ci-version-pinning",
  "phases": {
    "verify": "ok" | "skipped-docs-only" | "skipped-no-changes",
    "document": "ok" | "skipped",
    "commit": "ok" | "skipped-no-changes"
  },
  "tests": "passed" | "skipped" | "failed",
  "lint": "clean" | "skipped" | "errors",
  "handoff_drift": "none" | "appended" | "no-handoff",
  "pushed": false | "origin/main" | "origin/main:wip" | "origin/<branch>"
}
```

- ISO-8601 UTC timestamp (`date -u +"%Y-%m-%dT%H:%M:%SZ"` in shell, or Python `datetime.now(UTC).isoformat()`).
- `head_sha` is full 40-char SHA from `git rev-parse HEAD`.
- `branch` from `git branch --show-current`.
- Write only on successful Phase 3 completion. If `/end-session` aborts mid-phase, leave the prior file in place (stale-but-truthful is better than absent).
- Use `ensure_ascii=True` if writing via Python — defensive, even though all fields are ASCII today.
- The file goes in `.claude/` to keep workspace-state colocated; `.gitignore` already excludes `.claude/` (verify before relying on it — `git check-ignore .claude/last-end-session.json` should print the path).

### 2. `/close-branch` reads the sentinel and warns on drift

Insert a new step between current Step 3 (uncommitted-work check) and Step 4 (capture commit history):

**Step 3.5: Check `/end-session` sign-off**

```bash
SENTINEL="/Users/cassio/Code/bristlenose_branch $0/.claude/last-end-session.json"
HEAD_SHA=$(git -C "/Users/cassio/Code/bristlenose_branch $0" rev-parse HEAD 2>/dev/null)

if [ ! -f "$SENTINEL" ]; then
  # Never end-sessioned — ask
  # Prompt: "This branch has no /end-session sign-off record. The validate/document
  #          ritual (tests, lint, TODO/100days updates, CLAUDE.md gotchas, memory)
  #          may have been skipped. Run /end-session first? (Y/n)"
  # If yes: stop and tell user to cd into the worktree and run /end-session.
  # If no: continue (user override — closing without end-session is allowed
  # for cases where the branch was end-sessioned in a prior session whose
  # sentinel pre-dates this feature).
else
  LAST_SHA=$(python3 -c "import json; print(json.load(open('$SENTINEL'))['head_sha'])")
  if [ "$LAST_SHA" != "$HEAD_SHA" ]; then
    # Drift
    AHEAD=$(git -C "/Users/cassio/Code/bristlenose_branch $0" rev-list --count "$LAST_SHA..$HEAD_SHA" 2>/dev/null)
    # Prompt: "HEAD is N commits ahead of last /end-session (at $LAST_SHA).
    #          Run /end-session again first? (Y/n)"
    # If yes: stop. If no: continue.
  fi
fi
```

- Treat `python3 -c` failures as soft (sentinel exists but malformed — warn, continue).
- The two prompts above use the `AskUserQuestion` tool the skill already loads.

### 3. Root `CLAUDE.md` gotcha entry

Add a one-line entry under the existing **"`/new-feature` has `disable-model-invocation: true`"** gotcha (currently in the "Skill Gotchas" cluster), or just below the `setup-incomplete` mention:

> **Session-handoff sentinels:** `.claude/setup-incomplete` (negative — `/new-feature` setup didn't finish) and `.claude/last-end-session.json` (positive — `/end-session` signed off; carries `head_sha` for drift detection). Both gitignored. `/close-branch` reads the latter and prompts before archiving a branch that was never end-sessioned or has drifted since.

## Call sites / files

- `.claude/skills/end-session/SKILL.md` — append a sub-step to Phase 3 after step 13 (commit) or 14 (maintenance). Probably between 13 and 14 — write the sentinel as soon as the commit succeeds, before the maintenance / QA / push prompts which may be skipped. Update the printed-summary template at the bottom to include the sentinel path.
- `.claude/skills/close-branch/SKILL.md` — insert Step 3.5 between current Step 3 and Step 4. Renumber subsequent steps OR keep the 3.5 label (the skill uses `Step N` headers, so a 3.5 is fine).
- `CLAUDE.md` (root) — one-line gotcha entry.
- `.gitignore` — verify `.claude/` is excluded. If only specific patterns are, add `.claude/last-end-session.json`.

## Acceptance

- `/end-session` on a clean worktree writes `.claude/last-end-session.json` with the right schema. Open it; SHA matches `git rev-parse HEAD`; timestamp is ISO-8601 UTC; phases reflect what actually ran.
- Re-running `/end-session` immediately after overwrites the timestamp (new sign-off, same SHA — that's fine).
- Adding a commit on top and running `/close-branch <name>` from main triggers the drift prompt with the correct ahead-by count.
- Running `/close-branch` on a branch with no sentinel triggers the "never end-sessioned" prompt.
- Answering "no" to either prompt allows closure to proceed (override path).
- Answering "yes" stops the skill with a clear "run /end-session in the worktree first" message.
- The `.claude/setup-incomplete` behaviour from `/new-feature` is unchanged — this branch only adds, doesn't refactor.

## Out of scope

These were discussed in the zoom-out and explicitly **deferred** (William of Ockham: wait for evidence):

- BRANCHES.md "Status" field auto-update by `/end-session`.
- `.claude/branch-manifest.json` written by `/new-feature` (Kind / purpose / handoff-source in structured form).
- `/end-session` no-op short-circuit when HEAD matches last `head_sha`.
- Sentinel-naming-convention doc beyond the one-line CLAUDE.md gotcha.
- Migration: existing closed branches without sentinels are fine — the drift check only fires on branches still on disk and still active. Historical worktrees with `_Stale - Merged...txt` already are not touched by `/close-branch` again.

## Open questions

1. **Where exactly inside `/end-session` Phase 3 does the sentinel write land?** Suggestion above: between current step 13 (commit) and step 14 (maintenance). The argument is "as soon as the commit succeeds, before optional steps". The alternative is "at the very end after step 18 (CI verification)" — but then a `/end-session` that the user halted at the push prompt wouldn't get a sentinel, and we want one any time the *documenting* succeeded.

2. **Should `pushed` track `main:wip` vs `<branch>` distinctly?** Schema above suggests so; possibly overkill if the only consumer is drift detection. Keep distinct for now; cheap and adds no logic.

3. **Should the sentinel record the commit message of the final commit?** No — `head_sha` is enough; `git log -1` covers the rest.

4. **`disable-model-invocation` on the new sentinel logic:** the skills themselves carry that flag already (both `/end-session` and `/close-branch` are user-invocable but not model-invocable). No change to the flag is needed.

## Decisions during implementation

- 2026-05-14: Step 3.5 reads the sentinel via `python3 -c "..." < "$SENTINEL"` (stdin) rather than `python3 -c "...open('$SENTINEL')..."` (path interpolation). Reason: branch names may contain shell-hostile characters; stdin form is immune to all quoting hazards regardless of path or branch name. Supersedes §Spec item 2 `LAST_SHA=$(python3 -c "import json; print(json.load(open('$SENTINEL'))['head_sha'])")`. (code-review Finding 1, William-flagged real.)

- 2026-05-14: Drift check splits into fast-forward vs diverged-non-ancestor branches via `git merge-base --is-ancestor` before counting. Reason: `git rev-list --count A..B` silently returns 0 when A is no longer reachable from B (rewritten history) — the exact silent-drift failure mode the sentinel exists to catch. Two distinct user prompts surface accordingly. Supersedes §Spec item 2's drift block which used a single `AHEAD=$(git rev-list --count …)` without the ancestor check. (code-review Finding 2, William-flagged real.)

- 2026-05-14: Step 13a trigger restated as path-independent — "once Phase 2 has completed successfully and any required commit has landed (or has been skipped because there was nothing to commit)" rather than literally "between step 13 and step 14". Reason: `/end-session` has a branch-handoff path that may skip step 13; tying the sentinel write to a step number rather than to the semantic precondition produced a gap. Supersedes §Spec item 1 "Write only on successful Phase 3 completion" and Open question 1's "between current step 13 (commit) and step 14 (maintenance)". (code-review Finding 3, William's parsimonious choice between two proposed fixes: restate trigger (chosen) vs move step.)

- 2026-05-14: Failure policy line at `close-branch/SKILL.md:15` extended from "Steps 1–3 are critical safety checks" to "Steps 1–3 (and 3.5)". Reason: the new step is a safety check (clusters with 1–3 semantically), so the stop-on-failure invariant must explicitly cover it. Mechanical doc-clarity fix flagged in code-review Finding 8.

- 2026-05-14: Open question 1 resolved in favour of early-write (after Phase 2 / commit) rather than late-write (after step 18). Reason: drift detection only reads `head_sha`; the other schema fields (`pushed`, `tests`, `lint`) are descriptive. An early-written sentinel reflects "documenting was committed" which is the load-bearing claim. Inline note added to 13a so a future reader doesn't expect post-push fields to be authoritative. (code-review Finding 5, William-flagged edge — note, don't expand.)

- 2026-05-14: Open question 2 (`main:wip` vs `<branch>` distinction in `pushed`) and Open question 3 (commit message in schema) both resolved as originally suggested in the plan — distinct values for `pushed`; no commit message field. No deviation.

- 2026-05-14: Findings parked (William: speculative) — append-only `.claude/end-session-log.jsonl` ledger (Finding 6); CLAUDE.md gotcha alternative placement under "Skill Gotchas" cluster (Finding 4); explicit confirmation that the no-op short-circuit park is deliberate (Finding 9). All zero-evidence; revisit only if usage surfaces a need.
