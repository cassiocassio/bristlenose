---
name: new-feature
description: Create a new branch (feature, diagnostic, spike, chore, or parked) with git worktree, venv, remote tracking, and BRANCHES.md entry. Despite the skill name, not every branch is a feature — Kind is captured in Step 3.5.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

Create a new branch called `$0` for the bristlenose project.

If no branch name was provided (`$0` is empty), ask the user for one before proceeding.

**`$0` may also include optional flags after the branch name** — see Step 0. Bare `/new-feature foo` (no flags) is the default path: the human is just starting a branch and will be asked the usual questions interactively. Flags exist for the case where a parent Claude session is proposing the branch and has already made the decisions.

**Branch Kind is mandatory.** Not every branch is a feature. The Kind controls merge intent and end-of-life behaviour — see `docs/BRANCHES.md` "Branch Kinds" section. Step 3.5 captures it before the worktree is created so it can be recorded in BRANCHES.md correctly.

**Failure policy:** Steps 1–4 are critical — stop on failure. Steps 5–8 are setup — warn on failure but continue (the worktree is usable without them).

**Idempotency:** If the branch or worktree already exists from a partial previous run, detect that and skip to the first incomplete step rather than failing.

**Shell environment:** Every Bash invocation in this skill must start with:

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"
hash -r 2>/dev/null || true
```

The Claude Code Bash tool inherits PATH from the harness, which has occasionally been observed without `/usr/bin` and `/bin` — bare `mkdir` / `ln` / `rm` / `date` then fail with `command not found` mid-step. Prepending the standard system paths is cheap and makes every block robust regardless of harness state. `/opt/homebrew/bin` is included so `python3.12`, `npm`, etc. resolve. Apply this to every bash block in this skill — including the inline ones below.

`hash -r` is required because zsh caches "command → path" lookups at shell start. If the harness shell came up with a degraded PATH and zsh cached `mkdir` as not-found, a later `export PATH` doesn't invalidate that cache — bare `mkdir`/`ln` would still hit the cached miss. Clearing the hash table after the PATH fix ensures fresh lookups. (Observed 2026-05-08: silent `mkdir`/`ln` "command not found" inside Step 9 despite a corrected PATH.)

## Step 0: Parse optional flags

`$0` may contain a branch name optionally followed by any subset of these flags:

| Flag | Purpose | Skips |
|---|---|---|
| `--kind=<feature\|spike\|diagnostic\|chore\|parked>` | Pre-declares Branch Kind | Step 3.5 question |
| `--base=<branch-name>` | Fork from a branch other than `main`. Used when the new branch sits on top of in-flight work that hasn't merged yet (typical case: stacked feature branches where conflicting with the parent would be guaranteed). Defaults to `main`. | Nothing — feeds Step 4 |
| `--plan=<path>` | Path (absolute or `~/`-style) to a Markdown file with the self-contained prompt for the new session | Nothing — feeds Step 4b |
| `--purpose="<one line>"` | "What it does" line for BRANCHES.md | Step 11 question |
| `--files="<comma,separated,paths>"` | Files this branch will touch | Step 11 question |
| `--print-launch-url` | Print a `claude://code/new?folder=…` URL the user can click to open a new desktop-app session | Step 14 |

**All flags are optional.** Bare `/new-feature my-branch` works exactly as before — interactive prompts for Kind, purpose, files. Flags exist so a parent Claude session that already knows these answers can pass them in and avoid re-asking.

Parse the args as: first token is the branch name, remaining tokens are flags. If a flag's value contains spaces it must be quoted (`--purpose="trim bundle: stage 1 + stage 2"`).

Validation:
- `--kind` value must be one of the five enum entries; reject anything else with a clear message (don't silently fall back).
- `--base` value must be an existing local branch ref (`git show-ref --verify --quiet refs/heads/<value>`). If it doesn't exist, stop with: "Base branch `<value>` doesn't exist locally. Check `git branch --list` or fetch from origin first." If `--base` is absent, the effective base is `main`.
- `--plan` path must exist and be a `.md` file; if not, stop with the bad path quoted back.
- `--purpose` and `--files` are free text; no validation.

If a `--plan` path is provided, copy it now (before any branch creation) to `~/Code/bristlenose/docs/private/handoffs/<name>.md`. If a handoff file already exists at that target, **stop and ask the user** before overwriting — handoffs from prior sessions are precious. The existing Step 4b will pick the file up automatically once the worktree exists.

## Step 1: Validate branch name

After Step 0 has parsed flags out of `$0`, the remaining first token is the branch name. It must be lowercase letters, numbers, and hyphens only. No spaces, no leading hyphens, no underscores. If invalid, tell the user and stop.

Throughout the rest of this skill, `$0` refers to **just the branch name** (flags already extracted in Step 0).

## Step 2: Verify location

Check that:
- `pwd` is `/Users/cassio/Code/bristlenose`
- `git branch --show-current` returns `main`

If either fails, stop with: "Run /new-feature from the main bristlenose repo on the main branch."

## Step 3: Check for uncommitted changes

Run `git status --porcelain`. If there are changes, warn the user and ask whether to proceed. Do NOT stash — the changes stay on main.

## Step 3.5: Determine Branch Kind (mandatory)

**If `--kind=<value>` was passed in Step 0, use that value and skip the question.** Otherwise, ask the user which **Kind** this branch is — this controls how it ends, not just what it does. Use `AskUserQuestion` with these choices:

- **feature** — code intended for main; ends in merge or PR-and-squash
- **diagnostic** — produces inventory/reports/reproductions; fixes happen in *other* branches; the branch itself is **discarded** (not merged) when narrow children land. Example: `sandbox-debug`
- **spike** — exploratory throwaway; usually discarded; cherry-pick selectively if a commit is worth keeping
- **chore** — small ephemeral work (release tooling, doc reconciliation, dep bumps); merge or discard, low ceremony
- **parked** — opened now but on hold; may resume later. Pushed to origin as backup

Record the answer; it gets written into BRANCHES.md in Step 11. **Don't default to feature.** If the user can't articulate why this is a feature, it's probably a diagnostic or spike.

## Step 4: Create branch and worktree

The effective base from Step 0 is the value of `--base`, or `main` if absent. Call this `$BASE` below.

First, check current state to handle partial previous runs:

```bash
# Check if branch already exists
git show-ref --verify --quiet refs/heads/$0 && echo "BRANCH_EXISTS" || echo "NO_BRANCH"
# Check if worktree directory already exists
test -d "/Users/cassio/Code/bristlenose_branch $0" && echo "DIR_EXISTS" || echo "NO_DIR"
```

Then proceed based on what exists:
- **Neither exists:** Create both: `git branch $0 $BASE && git worktree add "/Users/cassio/Code/bristlenose_branch $0" $0`
- **Branch exists, no directory:** Just add the worktree: `git worktree add "/Users/cassio/Code/bristlenose_branch $0" $0`. (Don't re-fork from `$BASE` — the existing branch ref wins; if the user wanted a different base they should delete the branch first.)
- **Both exist and worktree is registered** (`git worktree list` shows it): Skip — tell the user "Branch and worktree already exist, resuming setup."
- **Directory exists but isn't a worktree:** Stop — something unexpected is there, ask the user what to do.

**If `$BASE` is not `main`**, tell the user explicitly so they know what the branch is forked from — this matters for `/close-branch` later (merge-back target) and for understanding which other in-flight work this branch depends on:

```
Branch $0 forked from $BASE (not main). It inherits all commits on $BASE.
When you /close-branch later, it'll be expected to merge back to $BASE,
not directly to main (unless $BASE itself is discarded first).
```

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
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
PLAN_DIR="$WORKTREE/.claude/plans"
if [ -f "$HANDOFF" ]; then
  mkdir -p "$PLAN_DIR"
  cp "$HANDOFF" "$PLAN_DIR/$0.md"
  # Visible alias at worktree root — .claude/ is hidden, so users miss the
  # plan unless we surface it. Symlink shows up in Finder, IDE file trees,
  # and `ls`. HANDOFF.md is gitignored.
  ln -sf ".claude/plans/$0.md" "$WORKTREE/HANDOFF.md"
  echo "✓ Seeded plan: $PLAN_DIR/$0.md (visible at $WORKTREE/HANDOFF.md)"
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
if ! node --version >/dev/null 2>&1; then
  echo "✗ node is broken — frontend build skipped"
  echo "  Likely cause: homebrew library drift (run 'node --version' to see the dyld error)"
  echo "  Try: brew reinstall node"
  echo "  Worktree is still usable for Python-only work; sentinel stays in place via Step 8."
elif [ -x node_modules/.bin/tsc ] && \
     [ -f ../bristlenose/server/static/index.html ] && \
     [ ../bristlenose/server/static/index.html -nt package.json ]; then
  echo "Frontend already built — skipping"
else
  npm install && npm run build
fi
```

This takes ~2 minutes on first run (npm install ~60s, build ~30s). If it fails, warn but don't stop — the worktree is still usable for Python-only work, and frontend can be set up manually with `cd frontend && npm install && npm run build`.

**Node-health pre-check rationale:** if `node` itself is broken (e.g. homebrew bumped a shared library and the locally-installed `node` is hardcoded against the older `.dylib`), `npm install` fails with a cryptic dyld error and the eventual smoke-test message recommends rerunning the exact thing that just failed. The pre-check surfaces "your node is broken, here's what to try" instead. Don't auto-`brew reinstall` — invasive, slow, and not the skill's job.

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

(Desktop-binaries probe lives in Step 9, after the symlinks are created — running it here would always say "skipped" on a fresh worktree, since `Resources/` contents are gitignored and Step 9 is what creates them.)

Print a one-line summary at the end: "Smoke test: N/4 checks passed". If any failed, list the specific remediation lines for the user.

**If all checks passed, remove the setup-incomplete sentinel:**

```bash
rm -f "/Users/cassio/Code/bristlenose_branch $0/.claude/setup-incomplete"
```

If any check failed, leave the sentinel in place — the next Claude session entering this worktree will see it and know the environment isn't fully prepped.

## Step 9: Symlink trial-runs (non-critical)

Skip if the symlink already exists, **or if the worktree already has a real `trial-runs/` directory** (the path is partially tracked — `trial-runs/fossda-opensource/perf-baselines/...` is in git, so every worktree starts with a real `trial-runs/` dir, and naively running `ln -s …` produces a broken nested layout: `trial-runs/trial-runs -> /…/main/trial-runs`).

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
TRIAL="$WORKTREE/trial-runs"
if [ -L "$TRIAL" ]; then
  echo "✓ trial-runs symlink already present"
elif [ -d "$TRIAL" ]; then
  echo "ℹ trial-runs/ already exists in worktree (tracked content) — skipping symlink. Worktree keeps its own copy of any tracked baselines; gitignored data in main isn't reachable from here."
else
  ln -s /Users/cassio/Code/bristlenose/trial-runs "$TRIAL" \
    && echo "✓ symlinked trial-runs/ to main" \
    || echo "ℹ trial-runs/ symlink failed — main may not have trial data"
fi
```

This symlinks the main repo's `trial-runs/` directory (mostly gitignored — contains large video files and rendered reports) so that `./scripts/dev.sh` works in the worktree. Don't copy — the directory contains video files. The "directory already exists" branch is the common case for fresh worktrees due to the partially tracked subtree; we accept the slight loss (gitignored trial data in main isn't reachable from a fresh worktree) rather than the silent broken-nested layout that the naive `ln` produced.

Then symlink the gitignored desktop binaries from main, so Xcode's Copy Resources phase finds them when the user opens the worktree's `Bristlenose.xcodeproj` and Cmd+R's. Without these, the .app builds without ffmpeg/ffprobe and the pipeline can't probe video files. Each link is gated on existence, so worktrees on machines that have never run `desktop/scripts/fetch-ffmpeg.sh` in main don't error.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
for path in ffmpeg ffprobe models; do
  src="/Users/cassio/Code/bristlenose/desktop/Bristlenose/Resources/$path"
  dst="$WORKTREE/desktop/Bristlenose/Resources/$path"
  if [ -e "$src" ] && [ ! -e "$dst" ]; then
    mkdir -p "$WORKTREE/desktop/Bristlenose/Resources" \
      && ln -s "$src" "$dst" \
      && echo "✓ symlinked $path from main" \
      || echo "✗ failed to symlink $path"
  elif [ -e "$dst" ]; then
    echo "✓ $path already present in worktree"
  else
    echo "ℹ $path not in main — run desktop/scripts/fetch-ffmpeg.sh in main first if you'll build the desktop .app"
  fi
done
```

Chain `mkdir`/`ln`/`echo` with `&&` (not separate lines): a bare `echo` after a failed `mkdir`/`ln` would still fire, falsely reporting "✓ symlinked" while `Resources/` doesn't exist. (Observed 2026-05-08 alongside the `hash -r` issue — three "✓ symlinked" lines printed despite `mkdir`/`ln` failing with "command not found".)

Then copy main's PyInstaller sidecar bundle into the worktree using `ditto`. Without it, Cmd+R on the default Bristlenose scheme fails with "Bundled sidecar missing at …" — and the bundled scheme is the only TestFlight-honest path; the v0.2-launcher fallbacks (External Server / Dev Sidecar) are deprecated scaffolding. The sidecar is ~428 MB per worktree, disk-cheap. If you're iterating on `bristlenose/server/` or signing, run `desktop/scripts/build-sidecar.sh` in this worktree afterwards to replace the copy with a locally-built bundle.

**Why `ditto`, not `cp -R*` or symlink:** A symlink at the top-level breaks Xcode's `Copy Sidecar Resources` build phase, which uses `rsync -a` and preserves symlinks as dangling-outside-bundle pointers the sandbox can't follow. `cp -RL` materialises real bytes but *also dereferences internal symlinks*, which breaks the PyInstaller bundle's rpath-relative library structure — mlx then can't find its Metal library and the sidecar crashes at startup with "Failed to load the default metallib". `cp -R` (default `-P`) preserves internal symlinks but follows the source-argument symlink correctly. `ditto` is the macOS-native bundle-aware copy: preserves resource forks, extended attributes, codesignatures, and internal symlinks; auto-dereferences the source-argument. Use `ditto`.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
src="/Users/cassio/Code/bristlenose/desktop/Bristlenose/Resources/bristlenose-sidecar"
dst="$WORKTREE/desktop/Bristlenose/Resources/bristlenose-sidecar"
if [ -d "$src" ] && [ ! -e "$dst" ]; then
  mkdir -p "$WORKTREE/desktop/Bristlenose/Resources" \
    && ditto "$src" "$dst" \
    && echo "✓ copied sidecar bundle from main (~428 MB)" \
    || echo "✗ failed to copy sidecar bundle"
elif [ -e "$dst" ]; then
  echo "✓ sidecar bundle already present in worktree"
else
  echo "ℹ sidecar bundle not in main — run desktop/scripts/build-sidecar.sh in main first if you'll build the desktop .app"
fi
```

Then probe the resolution path the app actually uses, so a broken symlink or wrong layout is caught now rather than at Cmd+R time:

```bash
cd "$WORKTREE"
if [ -d desktop/Bristlenose/Resources ]; then
  if .venv/bin/python -c "
from bristlenose.utils.bundled_binary import bundled_binary_path
import sys
missing = [n for n in ('ffmpeg', 'ffprobe') if bundled_binary_path(n) is None]
if missing:
    print('missing:', ' '.join(missing)); sys.exit(1)
" 2>/dev/null; then
    echo "✓ desktop binaries resolvable"
  else
    echo "✗ desktop binaries not resolvable — Cmd+R from this worktree's Xcode project will produce an .app without them. Either: re-run /new-feature setup, or run desktop/scripts/fetch-ffmpeg.sh from main."
  fi
else
  echo "ℹ no desktop/Bristlenose/Resources/ in this worktree — desktop .app build will be missing ffmpeg/ffprobe. Run desktop/scripts/fetch-ffmpeg.sh in main first if you'll build the desktop app."
fi
```

## Step 10: Stay local (do NOT push)

**Do NOT push to origin.** The branch stays local until the user explicitly asks to push. This avoids cluttering the remote with branches that may be short-lived or experimental.

Tell the user: "Branch is local only. Push with `git push -u origin $0` when you're ready."

## Step 11: Update docs/BRANCHES.md

Read `docs/BRANCHES.md` to understand the current format. Check if `$0` already has an entry (partial previous run) — if so, skip this step.

Then:

1. Add a row to the **Worktree Convention** table (Kind column is mandatory):
   ```
   | `bristlenose_branch $0/` | `$0` | <kind from Step 3.5> | <ask user for purpose> |
   ```

2. Add a row to the **Backup Strategy** table:
   ```
   | `$0` | `bristlenose_branch $0/` | local only |
   ```

3. Add a new section under **Active Branches** following the exact format of existing entries. Note the **Kind** field comes first — it sets reading expectations:

   ```markdown
   ### `$0`

   **Kind:** <feature | diagnostic | spike | chore | parked> — <one-line on merge intent: "code lands on main", "discard when children land", "throwaway exploration", etc.>
   **Status:** Just started
   **Started:** <today's date, format: D Mon YYYY, no leading zero on day>
   **Forked from:** <$BASE — omit this line entirely if $BASE is `main`; include if non-main so /close-branch knows the merge-back target>
   **Worktree:** `/Users/cassio/Code/bristlenose_branch $0/`
   **Remote:** local only (push when ready)

   **What it does:** <`--purpose` value if provided in Step 0, else ask user for a brief description>

   **Files this branch will touch:**
   - <`--files` value split on commas into bullet list if provided in Step 0, else ask user, else write "TBD — will be filled in as work progresses">

   **Potential conflicts with other branches:**
   - <check existing active branches in BRANCHES.md and note likely overlaps, especially render/ package, main.js, cli.py>
   ```

If `--purpose` and `--files` were both provided in Step 0, do not ask the user — write directly. If either is missing, ask only for the missing one.

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

## Step 14: Hand off to the worktree (do NOT auto-launch)

The Bash tool in *this* (parent) session pins CWD to the project root, so a parent session can't "switch into" the worktree — every command resets back. The user has to start a fresh session whose CWD *is* the worktree.

**Don't auto-launch.** Claude Desktop registers a `claude://code/new?folder=…` URL scheme that opens a new session at a given folder. It triggers a trust dialog by design — the human approves each folder. A skill that fires this URL on every invocation trains the user to click Confirm reflexively, defeating the safeguard. Same applies to spawning a terminal `claude` CLI: that's a *different* surface (separate settings, history, MCP servers) and quietly forks the session graph.

Default behaviour: just print the worktree path and let the user open it however they want — desktop-app "Open Folder" UI, drag-onto-Dock, whatever fits their flow.

Optional: if the user passed `--print-launch-url`, also print a clickable `claude://code/new` URL alongside the path. They can click it (still hits the trust dialog) but at least the URL isn't being fired reflexively by the skill itself.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
echo ""
echo "  Worktree ready: $WORKTREE"
echo ""
# Only if --print-launch-url was passed:
if [ "$PRINT_LAUNCH_URL" = "1" ]; then
  ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$WORKTREE")
  echo "  Click to open in Claude Desktop:"
  echo "  claude://code/new?folder=$ENCODED"
  echo ""
fi
echo "  This session stays here on main."
```

Don't `open` the URL programmatically. Don't open a Terminal window. Don't spawn a CLI claude. The user opens the new session themselves.
