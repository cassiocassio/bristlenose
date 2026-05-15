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

**Failure policy:** Steps 1–3 (and 3.5) are critical safety checks — stop on failure (or stop if the user says so in Step 3 or 3.5). Steps 4–9 are cleanup — warn on failure but continue through the rest.

**Idempotency:** If this skill was partially run before (e.g. stale marker exists but BRANCHES.md wasn't updated), detect what's already done and skip to the first incomplete step.

## Step 1: Verify location (CRITICAL SAFETY CHECK)

Check that:
- `pwd` is `/Users/cassio/Code/bristlenose`
- `git branch --show-current` returns `main`
- The current directory is NOT inside `/Users/cassio/Code/bristlenose_branch $0`

If ANY of these checks fail, **stop immediately** with:
> "You must run /close-branch from the main bristlenose repo on the main branch. If you are inside the worktree you're trying to close, run `cd /Users/cassio/Code/bristlenose` first — removing a worktree from inside it will break your shell."

## Step 2: Check merge status

Run `git branch --merged main` and check if `$0` appears.

If the branch is **NOT merged**, show the unmerged commits with `git log main..$0 --oneline`, then stop with:

> Branch `$0` has NOT been merged to main. Merge it first: `git merge $0` (from main), then re-run `/close-branch $0`.
>
> <sub>If you actually want to abandon or force-delete instead, ask.</sub>

If the branch ref no longer exists (already deleted in a partial previous run), check if the worktree directory still exists — if so, continue from Step 4 (archival).

If merged, continue.

## Step 3: Check for uncommitted work in the worktree

If the worktree directory exists, check for uncommitted changes:

```bash
git -C "/Users/cassio/Code/bristlenose_branch $0" status --porcelain
```

Ignore `trial-runs` (symlink) and `_Stale*` files (from partial previous run). If there are real uncommitted changes:

1. Show the user the list of changed files
2. **Stop.** Tell the user to deal with the uncommitted work first (commit it, move it to main, or discard it), then re-run `/close-branch`.

Do NOT proceed past this step. Detaching the worktree makes it a non-git directory — uncommitted changes become invisible diffs with no easy recovery.

## Step 3.5: Check `/end-session` sign-off

Look for `.claude/last-end-session.json` inside the worktree — the positive sentinel `/end-session` writes on successful close-out. Compare its `head_sha` to current HEAD of the branch.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
SENTINEL="$WORKTREE/.claude/last-end-session.json"
HEAD_SHA=$(git -C "$WORKTREE" rev-parse HEAD 2>/dev/null)
```

**If the sentinel is missing** — the branch was never `/end-session`'d (or was end-sessioned before this feature existed). Prompt the user via `AskUserQuestion`:

> This branch has no `/end-session` sign-off record. The verify/document ritual (tests, lint, TODO/100days, CLAUDE.md gotchas, memory) may have been skipped. Run `/end-session` first? (Y/n)

- "Yes" → stop. Tell user: `cd "/Users/cassio/Code/bristlenose_branch $0"` and run `/end-session`, then re-run `/close-branch $0`.
- "No" → continue (override path for branches end-sessioned before this feature, or where the user explicitly accepts the gap).

**If the sentinel exists** — read `head_sha` via stdin (avoids shell-quoting hazards in the path or branch name):

```bash
LAST_SHA=$(python3 -c "import json,sys; print(json.load(sys.stdin)['head_sha'])" < "$SENTINEL" 2>/dev/null)
```

If `python3` fails or the file is malformed, warn ("sentinel exists but unreadable — continuing") and proceed.

If `LAST_SHA` matches current `HEAD_SHA`, continue silently.

If they differ, check whether the drift is a simple fast-forward or a history rewrite:

```bash
if git -C "$WORKTREE" merge-base --is-ancestor "$LAST_SHA" "$HEAD_SHA" 2>/dev/null; then
  AHEAD=$(git -C "$WORKTREE" rev-list --count "$LAST_SHA..$HEAD_SHA" 2>/dev/null)
  # Fast-forward drift: $AHEAD new commits on top of sign-off
else
  AHEAD="diverged"
  # History was rewritten (rebase / amend / force-push): LAST_SHA is no longer
  # reachable from HEAD. The ahead-count is meaningless — surface the divergence.
fi
```

Prompt via `AskUserQuestion`:

- Fast-forward: > HEAD is $AHEAD commit(s) ahead of last `/end-session` (signed off at `$LAST_SHA`). The new commits haven't been through the verify/document ritual. Run `/end-session` again first? (Y/n)
- Diverged: > Branch history has diverged from the last `/end-session` sign-off (`$LAST_SHA` is no longer an ancestor of HEAD — likely a rebase or amend). The previous sign-off no longer applies. Run `/end-session` again first? (Y/n)

- "Yes" → stop with the same instruction as above.
- "No" → continue (override).

## Step 4: Capture commit history (BEFORE any deletion)

This must happen while the branch ref still exists. Capture:

```bash
git log $(git merge-base main $0)..$0 --oneline
```

This uses `merge-base` instead of `main..$0` because `main..$0` is empty for merged branches.

Save this output — you'll need it for the stale marker file in Step 4.

## Step 5: Run tests on main (optional)

Ask the user:
> "Run tests on main to confirm the merge is clean? [Y/n]"

If yes:
```bash
cd /Users/cassio/Code/bristlenose
.venv/bin/python -m pytest tests/
```

If tests fail, warn the user but continue — the merge already landed, so test failures may be pre-existing. Note which tests failed.

If the user says no, skip.

## Step 6: Create stale marker file

Check if a stale marker already exists in the worktree directory (partial previous run). If so, skip.

Read the branch's entry in `docs/BRANCHES.md` for the description.

Create a file inside the worktree directory:

**Filename:** `_Stale - Merged by Claude DD-Mon-YY.txt` (where DD-Mon-YY is today, e.g. `10-Feb-26`)

**Contents:**
```
Branch: $0
Merged to main: <today's date, D Mon YYYY format>
Closed by: Claude (/close-branch skill)

What this branch did:
<summary from BRANCHES.md entry>

Commits on this branch:
<output captured in Step 3>

---
This directory is a detached git worktree. It is no longer tracked by git
but has been kept on disk as a local archive. You can safely delete this
entire directory when you no longer need it.

To undo the merge on main:
  git revert -m 1 <merge-commit-hash>
This creates a new commit that reverses the merge, keeping full history.
```

If the worktree directory no longer exists, skip this step and note it.

After creating the stale marker, tag the folder orange (= stale branch) in Finder:

```bash
osascript -e 'tell application "Finder" to set label index of (POSIX file "/Users/cassio/Code/bristlenose_branch $0" as alias) to 1'
```

If this fails (directory gone, headless environment), warn but continue.

## Step 7: Detach worktree from git

Check if the worktree is still registered (`git worktree list`). If not, just run `git worktree prune` and skip ahead.

**Do NOT use `git worktree remove`** — it deletes the directory, which we want to keep. Instead, unlink the worktree by removing its `.git` file:

```bash
# Verify the .git file exists and is a file (not a directory) before removing
test -f "/Users/cassio/Code/bristlenose_branch $0/.git" && rm "/Users/cassio/Code/bristlenose_branch $0/.git"
git worktree prune
```

This detaches the worktree from git (so `git worktree list` no longer shows it) while leaving all files on disk intact. The directory becomes a regular (non-git) folder with the source code frozen at the merge point.

## Step 8: Ask about branch deletion

Present these as separate choices — the user can say no to either or both.

**Local branch:**

First check if it still exists: `git show-ref --verify --quiet refs/heads/$0`

If it exists:
> Delete local branch `$0`? This is safe — the branch is merged to main, so no commits are lost. The branch ref just gets cleaned up. (yes/no)

If yes: `git branch -d $0`

**Remote branch:**

First check if it exists: `git ls-remote --heads origin $0`

If it exists on the remote:
> Delete remote branch `origin/$0`? Collaborators who cloned this branch will lose access to it on GitHub. The code is already in main. (yes/no)

If yes: `git push origin --delete $0`

If the remote branch doesn't exist, say so and skip the question.

If the user says no to either, that's fine — the branches stay around harmlessly.

## Step 9: Update docs/BRANCHES.md

Read the file. Check if `$0` has already been moved to Completed Branches (partial previous run). If so, skip.

Then:

1. Remove the branch's full section from **Active Branches**
2. Remove the branch's row from the **Worktree Convention** table (if present)
3. Remove the branch's row from the **Backup Strategy** table (if present)
4. Add an entry under **Completed Branches (for reference)** following the existing format:

```markdown
### `$0` — merged <today's date, D Mon YYYY>

<Brief summary pulled from the "What it does" text of the active entry>
```

5. Update the **Updated:** date at the top of the file

## Step 10: Commit

```bash
cd /Users/cassio/Code/bristlenose
git add docs/BRANCHES.md
git commit -m "close $0 branch, update BRANCHES.md"
```

## Step 11: Report

Print a summary of everything that was done:

- Stale marker: created (or skipped if directory was gone)
- Worktree: detached from git, directory preserved on disk at `...`
- Local branch: deleted / kept
- Remote branch: deleted / kept / didn't exist
- BRANCHES.md: updated and committed
- Tests: passed / skipped / N failures noted

Then remind the user:
> The worktree directory is still on disk at `/Users/cassio/Code/bristlenose_branch $0/`. Delete it whenever you like — it's just a regular folder now, not connected to git.
>
> If you need to undo the merge: `git revert -m 1 <merge-commit-hash>`
