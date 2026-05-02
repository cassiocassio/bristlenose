---
name: new-feature
description: Create a new feature branch with git worktree, venv, remote tracking, and BRANCHES.md entry
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

Create a new feature branch called `$0` for the bristlenose project.

If no branch name was provided (`$0` is empty), ask the user for one before proceeding.

**Failure policy:** Steps 1–4 are critical — stop on failure. Steps 5–8 are setup — warn on failure but continue (the worktree is usable without them).

**Idempotency:** If the branch or worktree already exists from a partial previous run, detect that and skip to the first incomplete step rather than failing.

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

First, check current state to handle partial previous runs:

```bash
# Check if branch already exists
git show-ref --verify --quiet refs/heads/$0 && echo "BRANCH_EXISTS" || echo "NO_BRANCH"
# Check if worktree directory already exists
test -d "/Users/cassio/Code/bristlenose_branch $0" && echo "DIR_EXISTS" || echo "NO_DIR"
```

Then proceed based on what exists:
- **Neither exists:** Create both: `git branch $0 main && git worktree add "/Users/cassio/Code/bristlenose_branch $0" $0`
- **Branch exists, no directory:** Just add the worktree: `git worktree add "/Users/cassio/Code/bristlenose_branch $0" $0`
- **Both exist and worktree is registered** (`git worktree list` shows it): Skip — tell the user "Branch and worktree already exist, resuming setup."
- **Directory exists but isn't a worktree:** Stop — something unexpected is there, ask the user what to do.

If the git commands fail for any other reason, tell the user and stop.

**After the worktree directory exists, drop a setup-incomplete sentinel:**

```bash
mkdir -p "/Users/cassio/Code/bristlenose_branch $0/.claude"
date -u +"setup started at %Y-%m-%dT%H:%M:%SZ" \
  > "/Users/cassio/Code/bristlenose_branch $0/.claude/setup-incomplete"
```

The file's presence tells future Claude sessions (and the user) that the worktree environment isn't fully prepped yet. It gets removed in Step 8 only after the smoke test confirms the environment works. If setup aborts halfway, the flag survives and the next attempt knows.

## Step 4b: Seed handoff plan from prior diagnostic session (non-critical)

Diagnostic / sandpit / planning sessions write per-branch handoff prompts into `~/Code/bristlenose/docs/private/handoffs/` (the gitignored docs area in the main repo). If one exists for this branch, copy it into the new worktree's `.claude/plans/<branch>.md` so the next session lands with its purpose already in scope — no synthesis required.

```bash
HANDOFF="/Users/cassio/Code/bristlenose/docs/private/handoffs/$0.md"
PLAN_DIR="/Users/cassio/Code/bristlenose_branch $0/.claude/plans"
if [ -f "$HANDOFF" ]; then
  mkdir -p "$PLAN_DIR"
  cp "$HANDOFF" "$PLAN_DIR/$0.md"
  echo "✓ Seeded plan from handoff: $PLAN_DIR/$0.md"
else
  echo "ℹ No prior handoff at $HANDOFF — new session will need a brief from the user."
fi
```

If absent, that's fine — the branch may have been hand-typed by the user with no prior session. The new session will ask the user for a brief.

## Step 5: Tag folder purple in Finder (non-critical)

Set the worktree folder to purple (= active branch) in Finder:

```bash
osascript -e 'tell application "Finder" to set label index of (POSIX file "/Users/cassio/Code/bristlenose_branch $0" as alias) to 5'
```

If this fails (e.g. Finder not running, headless environment), warn but continue.

## Step 6: Set up venv (non-critical)

Skip **only** if `.venv/bin/python` exists **and** the extras verification passes:

```bash
cd "/Users/cassio/Code/bristlenose_branch $0"
# Check if venv exists AND has the required extras
if .venv/bin/python -c "import sqlalchemy; import fastapi; import pytest" 2>/dev/null; then
  echo "Venv already set up with all extras — skipping"
else
  # Derive Python version from CI (single source of truth) instead of baking it in.
  # release.yml is the canonical "primary" version — install-test.yml, i18n-check.yml,
  # and the lint/coverage jobs in ci.yml all match it. Fallback to 3.12 if grep fails.
  # NEVER use bare `python3` — default may be 3.14 (brew) with broken ensurepip on macOS
  # (see CLAUDE.md gotcha).
  PYVER=$(grep -oE 'python-version: "[0-9]+\.[0-9]+"' /Users/cassio/Code/bristlenose/.github/workflows/release.yml | head -1 | grep -oE '[0-9]+\.[0-9]+')
  PYVER=${PYVER:-3.12}
  if ! command -v "python${PYVER}" >/dev/null; then
    echo "✗ python${PYVER} not installed — install with: brew install python@${PYVER}"
    exit 1
  fi
  "python${PYVER}" -m venv .venv
  .venv/bin/pip install -e '.[dev,serve]'
fi
```

After install (or after skipping), **always verify**:

```bash
.venv/bin/python -c "import sqlalchemy; import fastapi; import pytest; print('All extras OK')"
```

If verification fails, warn: "Venv is missing packages. Run: `.venv/bin/pip install -e '.[dev,serve]'`" — but don't stop (worktree is still usable).

This takes 30-60 seconds on first run. If it fails, warn but don't stop — the worktree is still usable and venv can be retried manually.

## Step 7: Build the React frontend (non-critical, slow)

The React bundle lives at `bristlenose/server/static/` and `frontend/node_modules/`. Both are gitignored, so a fresh worktree starts blank. Without this step, `bristlenose serve` (and the Mac app's WebView) silently serves an unstyled HTML skeleton — the cause of a long diagnostic detour during port-v01-ingestion QA (see plan followup section dated 20 Apr 2026).

Skip if both `frontend/node_modules/.bin/tsc` exists AND `bristlenose/server/static/index.html` is newer than `frontend/package.json`:

```bash
cd "/Users/cassio/Code/bristlenose_branch $0/frontend"
if [ -x node_modules/.bin/tsc ] && \
   [ -f ../bristlenose/server/static/index.html ] && \
   [ ../bristlenose/server/static/index.html -nt package.json ]; then
  echo "Frontend already built — skipping"
else
  npm install && npm run build
fi
```

This takes ~2 minutes on first run (npm install ~60s, build ~30s). If it fails, warn but don't stop — the worktree is still usable for Python-only work, and frontend can be set up manually with `cd frontend && npm install && npm run build`.

## Step 8: Smoke test the worktree (non-critical)

Validate the environment actually works before handing back to the user. If any check fails, warn (don't stop) and surface what's missing — saves a diagnostic detour on the next session.

```bash
cd "/Users/cassio/Code/bristlenose_branch $0"

# 1. Venv extras
.venv/bin/python -c "import sqlalchemy; import fastapi; import pytest" 2>&1 \
  && echo "✓ venv extras OK" \
  || echo "✗ venv missing packages — run: .venv/bin/pip install -e '.[dev,serve]'"

# 2. Bristlenose CLI
.venv/bin/bristlenose --version 2>&1 \
  && echo "✓ bristlenose CLI runnable" \
  || echo "✗ bristlenose CLI not runnable — venv install incomplete"

# 3. Frontend bundle
if [ -f bristlenose/server/static/index.html ] && [ -d bristlenose/server/static/assets ]; then
  echo "✓ frontend bundle present"
else
  echo "✗ frontend bundle missing — run: cd frontend && npm install && npm run build"
fi

# 4. Doctor (canonical 'does this thing work' check; doesn't fail on missing API key)
.venv/bin/bristlenose doctor 2>&1 | head -20
```

Print a one-line summary at the end: "Smoke test: N/4 checks passed". If any failed, list the specific remediation lines for the user.

**If all 4 checks passed, remove the setup-incomplete sentinel:**

```bash
rm -f "/Users/cassio/Code/bristlenose_branch $0/.claude/setup-incomplete"
```

If any check failed, leave the sentinel in place — the next Claude session entering this worktree will see it and know the environment isn't fully prepped.

## Step 9: Symlink trial-runs (non-critical)

Skip if the symlink already exists.

```bash
ln -s /Users/cassio/Code/bristlenose/trial-runs "/Users/cassio/Code/bristlenose_branch $0/trial-runs"
```

This symlinks the main repo's `trial-runs/` directory (gitignored, contains large video files and rendered reports) so that `./scripts/dev.sh` works in the worktree. Don't copy — the directory contains video files. If the symlink fails (target doesn't exist), warn but continue — the user may not have trial data.

## Step 10: Stay local (do NOT push)

**Do NOT push to origin.** The branch stays local until the user explicitly asks to push. This avoids cluttering the remote with branches that may be short-lived or experimental.

Tell the user: "Branch is local only. Push with `git push -u origin $0` when you're ready."

## Step 11: Update docs/BRANCHES.md

Read `docs/BRANCHES.md` to understand the current format. Check if `$0` already has an entry (partial previous run) — if so, skip this step.

Then:

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
   - <check existing active branches in BRANCHES.md and note likely overlaps, especially render/ package, main.js, cli.py>
   ```

Ask the user for the description and files before writing.

## Step 12: Commit BRANCHES.md on main

```bash
cd /Users/cassio/Code/bristlenose
git add docs/BRANCHES.md
git commit -m "add $0 branch to BRANCHES.md"
```

## Step 13: Report

Print a summary:

- Branch: `$0`
- Worktree: `/Users/cassio/Code/bristlenose_branch $0/`
- Remote: local only (push with `git push -u origin $0` when ready)
- Venv: ready (or note if it failed)
- BRANCHES.md: updated and committed
- Handoff plan: copied from prior diagnostic to `.claude/plans/$0.md` (or note "no prior handoff — next session will need a brief from you")

Then: "To start working, open a new Claude session in the worktree directory, or tell me to switch."
