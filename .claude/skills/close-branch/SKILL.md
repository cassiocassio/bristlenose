---
name: close-branch
description: Archive a merged feature branch — stale marker, detach worktree, update BRANCHES.md (preserves local directory)
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

Close and archive the feature branch `$0` after it has been merged to main.

If no branch name was provided (`$0` is empty), run `git worktree list` and show the active worktrees, then ask the user which branch to close.

**Important:** This skill does NOT delete the local worktree directory. The directory stays on disk with a stale marker file so the user can revisit old experiments or delete it manually later.

Follow these steps **in order**:

## Step 1: Verify location (CRITICAL SAFETY CHECK)

Check that:
- `pwd` is `/Users/cassio/Code/bristlenose`
- `git branch --show-current` returns `main`
- The current directory is NOT inside `/Users/cassio/Code/bristlenose_branch $0`

If ANY of these checks fail, **stop immediately** with:
> "You must run /close-branch from the main bristlenose repo on the main branch. If you are inside the worktree you're trying to close, run `cd /Users/cassio/Code/bristlenose` first — removing a worktree from inside it will break your shell."

## Step 2: Check merge status

Run `git branch --merged main` and check if `$0` appears.

If the branch is **NOT merged**, stop with:
> "Branch `$0` has NOT been merged to main. This skill is for closing merged branches only. Merge the branch first, or delete it manually with `git branch -D $0` if you want to discard the work."

Show the unmerged commits with `git log main..$0 --oneline` for reference.

If merged, continue.

## Step 3: Run tests on main

```bash
cd /Users/cassio/Code/bristlenose
.venv/bin/python -m pytest tests/
```

If tests fail, warn the user but continue — the merge already landed, so test failures may be pre-existing. Note which tests failed.

## Step 4: Create stale marker file

First, gather information for the marker:
- Read the branch's entry in `docs/BRANCHES.md` for the description
- Run `git log main..$0 --oneline` (if branch still exists) or `git log --oneline -20` to find the relevant commits

Then create a file inside the worktree directory:

**Filename:** `_Stale - Merged by Claude DD-Mon-YY.txt` (where DD-Mon-YY is today, e.g. `10-Feb-26`)

**Contents:**
```
Branch: $0
Merged to main: <today's date, D Mon YYYY format>
Closed by: Claude (/close-branch skill)

What this branch did:
<summary from BRANCHES.md entry>

Commits on this branch:
<output of git log>

---
This directory is a detached git worktree. It is no longer tracked by git
but has been kept on disk as a local archive. You can safely delete this
entire directory when you no longer need it.

To undo the merge on main:
  git revert -m 1 <merge-commit-hash>
This creates a new commit that reverses the merge, keeping full history.
```

If the worktree directory no longer exists, skip this step and note it.

## Step 5: Detach worktree from git

```bash
git worktree remove --force "/Users/cassio/Code/bristlenose_branch $0"
```

The `--force` flag is needed because the directory will have untracked files (the stale marker, .venv, __pycache__, etc.). This unregisters the worktree from git but the `--force` remove may delete the directory — so we need to handle this carefully:

Actually, `git worktree remove` deletes the directory. Since we want to KEEP the directory, use this approach instead:

1. First, copy the stale marker info we need
2. Unlink the worktree: `git worktree remove --force "/Users/cassio/Code/bristlenose_branch $0"` will remove the directory
3. Recreate JUST the directory and the stale marker file

**Alternative approach (simpler):** Since `git worktree remove` deletes the working tree, and we want to preserve the directory:

```bash
# Prune the worktree link without deleting the directory
# by removing the .git file that links it to the main repo
rm "/Users/cassio/Code/bristlenose_branch $0/.git"
git worktree prune
```

This detaches the worktree from git (so `git worktree list` no longer shows it) while leaving all files on disk intact. The directory becomes a regular (non-git) folder with the source code frozen at the merge point.

If the worktree is already detached or the directory is gone, just run `git worktree prune`.

## Step 6: Ask about branch deletion

Present these as separate choices — the user can say no to either or both:

**Local branch:**
> Delete local branch `$0`? This is safe — the branch is merged to main, so no commits are lost. The branch ref just gets cleaned up. (yes/no)

If yes: `git branch -d $0`

**Remote branch:**
> Delete remote branch `origin/$0`? Collaborators who cloned this branch will lose access to it on GitHub. The code is already in main. (yes/no)

If yes: `git push origin --delete $0`

If the user says no to either, that's fine — the branches stay around harmlessly.

## Step 7: Update docs/BRANCHES.md

Read the file. Then:

1. Remove the branch's full section from **Active Branches**
2. Remove the branch's row from the **Worktree Convention** table (if present)
3. Remove the branch's row from the **Backup Strategy** table (if present)
4. Add an entry under **Completed Branches (for reference)** following the existing format:

```markdown
### `$0` — merged <today's date, D Mon YYYY>

<Brief summary pulled from the "What it does" text of the active entry>
```

5. Update the **Updated:** date at the top of the file

## Step 8: Commit

```bash
cd /Users/cassio/Code/bristlenose
git add docs/BRANCHES.md
git commit -m "close $0 branch, update BRANCHES.md"
```

## Step 9: Report

Print a summary of everything that was done:

- Stale marker: created (or skipped if directory was gone)
- Worktree: detached from git, directory preserved on disk at `...`
- Local branch: deleted / kept
- Remote branch: deleted / kept
- BRANCHES.md: updated and committed
- Tests: passed / N failures noted

Then remind the user:
> The worktree directory is still on disk at `/Users/cassio/Code/bristlenose_branch $0/`. Delete it whenever you like — it's just a regular folder now, not connected to git.
>
> If you need to undo the merge: `git revert -m 1 <merge-commit-hash>`
