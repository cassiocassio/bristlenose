---
name: close-feature
description: Finish a piece of trunk work on main — runs tests + lint, surfaces human-QA checks, trues docs, adds a changelog line, marks the 100days item done, and commits. No merge (you're already on main). If you're on a branch, it offers to close the branch properly instead.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Edit, Glob, Grep, AskUserQuestion
---

Finish the current piece of work on `main`.

**Instrumentation:** call `bash .claude/skills/_shared/wflog.sh close-feature <step> "<detail>"` at each step. `BRISTLENOSE_WORKFLOW_DEBUG=1` for verbose echo. Log: `.claude/workflow-log.jsonl`.

**Failure policy:** Step 1 (forgiving check) and Step 2 (tests + lint gate) are critical — stop on failure. The rest warn and continue.

## Step 1: Forgiving context check

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"; hash -r 2>/dev/null || true
bash .claude/skills/_shared/wflog.sh close-feature start
git branch --show-current
```

- If the current branch is **not** `main` — you're on a branch / in a worktree. This work wants `/close-branch` (it merges + tears the worktree down); `/close-feature` would skip both. Say:
  > "You're on branch `<x>`. Close it properly with `/close-branch <x>`? `/close-feature` would skip the merge and teardown."

  Tell the user to run `/close-branch <x>`. Log `bash .claude/skills/_shared/wflog.sh close-feature redirect-to-close-branch "<x>"` and stop unless the user explicitly insists on a bare commit-on-branch.
- On `main` — continue.

## Step 2: Tests + lint gate (critical)

**Skip condition (docs-only):** if every file this task touched is documentation (`.md`, `.txt`, locale `.json`, `CLAUDE.md`, `TODO.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `MEMORY.md`, `SKILL.md`), there's nothing pytest or ruff can catch — skip the gate. Check this task's files with `git diff --name-only`, `git diff --cached --name-only`, and `git ls-files --others --exclude-standard`. If all are docs, log `bash .claude/skills/_shared/wflog.sh close-feature gate skipped-docs-only` and go to Step 3. (Mirrors end-session's Phase 1 docs-only skip — same rationale: a `.md`/`.txt`/locale change can't break the Python suite.)

Otherwise, run the gate — nothing else in this block, so the exit status is the checks', not a logger's:

```bash
.venv/bin/python -m pytest tests/
.venv/bin/ruff check .
```

Both must pass (whole-repo ruff = CI parity). **If either is red: STOP, fix, and do not commit a red gate.** Only once both are green, record it in a separate block (the always-exit-0 logger must never be the last command in the gate, or it masks a failing exit code):

```bash
bash .claude/skills/_shared/wflog.sh close-feature gate pass
```

## Step 3: QA nudges (human-only checks)

Surface only the checks a human must do that tests can't — visual regression, browser interaction, UX feel. Give copy-paste commands, e.g.:

```
.venv/bin/bristlenose serve --dev trial-runs/project-ikea   # then open http://localhost:8150/report/
```

**Never** use the Claude Code preview tools for Bristlenose QA — they are documented to fail (wrong port, no Vite HMR, white-on-white). For a small diff, a proportionate review (`silent-failure-hunter` + `code-review`) is enough; offer the full `/usual-suspects` only for structural or convention-touching change. Log `bash .claude/skills/_shared/wflog.sh close-feature qa "<surfaced>"`.

## Step 4: True the docs (if design docs touched)

If the work touched a surface that has a `docs/design-*.md`, offer `/true-the-docs --topic <surface>`. Log the offer.

## Step 5: Note changelog-worthy work (if user-facing)

The CHANGELOG entry is written by `/new-release`, which owns the version number + date — you can't write a correct `**X.Y.Z** — _D Mon YYYY_` line now (no version yet, and `CHANGELOG.md` has no "unreleased" section). If this work is user-facing, ensure `.claude/current-task.json` has `changelog_needed: true` and a one-line `summary` so `/new-release` can fold it into the next release entry. Log `bash .claude/skills/_shared/wflog.sh close-feature changelog-flagged "<yes|n/a>"`.

## Step 6: Mark the plan done

- Strike the `docs/private/100days.md` item if this completes one: `~~<item>~~ ✅ shipped <D Mon YYYY> (<sha>)`.
- Offer to run `/sync-board` to move the board card to Done.
- Log `bash .claude/skills/_shared/wflog.sh close-feature plan-marked "<item|none>"`.

## Step 7: Commit + clear state

**Look before you `git add -A`.** It sweeps the *whole* working tree — if unrelated WIP is present (another task's work), it would bundle it into this commit. Show the tree first:

```bash
git status --short
```

If everything shown belongs to this task → `git add -A`. If unrelated work is present → stage only this task's files (`git add <paths>`). Then commit and clear state:

```bash
git commit -m "<concise, lowercase message>"
rm -f .claude/current-task.json
bash .claude/skills/_shared/wflog.sh close-feature committed
```

No merge — the work is already on `main`. It isn't public until `/new-release`.

## Step 8: Offer to wrap the session

If the user is stepping away, suggest `/end-session` (parks state, session-level housekeeping). Otherwise you're done. Log `bash .claude/skills/_shared/wflog.sh close-feature done`.
