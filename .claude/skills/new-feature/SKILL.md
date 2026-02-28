---
name: new-feature
description: Create a new feature branch with git worktree, venv, remote tracking, and BRANCHES.md entry
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

Create a new feature branch called `$0` for the bristlenose project.

If no branch name was provided (`$0` is empty), ask the user for one before proceeding.

Follow these steps **in order**, stopping on any failure:

## Step 1: Validate branch name

The branch name must be lowercase letters, numbers, and hyphens only. No spaces, no leading hyphens, no underscores. If invalid, tell the user and stop.

## Step 2: Verify location

Check that:
- `pwd` is `/Users/cassio/Code/bristlenose`
- `git branch --show-current` returns `main`

If either fails, stop with: "Run /new-feature from the main bristlenose repo on the main branch."

## Step 3: Check for uncommitted changes

Run `git status --porcelain`. If there are changes, warn the user and ask whether to proceed. Do NOT stash — the changes stay on main.

## Step 4: Create branch and worktree

```bash
git branch $0 main
git worktree add "/Users/cassio/Code/bristlenose_branch $0" $0
```

If `git branch` fails (branch already exists), tell the user and stop.
If `git worktree add` fails (directory exists), tell the user and stop.

## Step 5: Pause for Finder

Tell the user:

> The worktree directory has been created at:
> `/Users/cassio/Code/bristlenose_branch $0/`
>
> You can label it in Finder now (right-click > Tags > pick a colour) before I continue with setup.

Ask the user to confirm before continuing.

## Step 6: Set up venv

```bash
cd "/Users/cassio/Code/bristlenose_branch $0"
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

This takes 30-60 seconds. If it fails, warn but don't stop — the worktree is still usable and venv can be retried manually.

## Step 7: Symlink trial-runs

```bash
ln -s /Users/cassio/Code/bristlenose/trial-runs "/Users/cassio/Code/bristlenose_branch $0/trial-runs"
```

This symlinks the main repo's `trial-runs/` directory (gitignored, contains large video files and rendered reports) so that `./scripts/dev.sh` works in the worktree. Don't copy — the directory contains video files. If the symlink fails (target doesn't exist), warn but continue — the user may not have trial data.

## Step 8: Symlink skills

```bash
mkdir -p "/Users/cassio/Code/bristlenose_branch $0/.claude"
ln -s /Users/cassio/Code/bristlenose/.claude/skills "/Users/cassio/Code/bristlenose_branch $0/.claude/skills"
```

This ensures Claude sessions running from the worktree can access `/close-branch` and other skills defined in the main repo. Without this, skills won't load and Claude will improvise manual cleanup — which is how we bricked a shell session in Feb 2026.

If the symlink fails, warn but continue.

## Step 9: Stay local (do NOT push)

**Do NOT push to origin.** The branch stays local until the user explicitly asks to push. This avoids cluttering the remote with branches that may be short-lived or experimental.

Tell the user: "Branch is local only. Push with `git push -u origin $0` when you're ready."

## Step 10: Update docs/BRANCHES.md

Read `docs/BRANCHES.md` to understand the current format. Then:

1. Add a row to the **Worktree Convention** table:
   ```
   | `bristlenose_branch $0/` | `$0` | <ask user for purpose> |
   ```

2. Add a row to the **Backup Strategy** table:
   ```
   | `$0` | `bristlenose_branch $0/` | local only |
   ```

3. Add a new section under **Active Branches** following the exact format of existing entries:

   ```markdown
   ### `$0`

   **Status:** Just started
   **Started:** <today's date, format: D Mon YYYY, no leading zero on day>
   **Worktree:** `/Users/cassio/Code/bristlenose_branch $0/`
   **Remote:** local only (push when ready)

   **What it does:** <ask user for a brief description>

   **Files this branch will touch:**
   - <ask user, or write "TBD — will be filled in as work progresses">

   **Potential conflicts with other branches:**
   - <check existing active branches in BRANCHES.md and note likely overlaps, especially render_html.py, main.js, cli.py>
   ```

Ask the user for the description and files before writing.

## Step 11: Commit BRANCHES.md on main

```bash
cd /Users/cassio/Code/bristlenose
git add docs/BRANCHES.md
git commit -m "add $0 branch to BRANCHES.md"
```

## Step 12: Report

Print a summary:

- Branch: `$0`
- Worktree: `/Users/cassio/Code/bristlenose_branch $0/`
- Remote: local only (push with `git push -u origin $0` when ready)
- Venv: ready (or note if it failed)
- BRANCHES.md: updated and committed

Then: "To start working, open a new Claude session in the worktree directory, or tell me to switch."
