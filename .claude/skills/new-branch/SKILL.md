---
name: new-branch
description: Start work in an ISOLATED git worktree (the exception path — use only when two envs must be live at once, the work is multi-day and main must stay shippable meanwhile, or it's a throwaway spike). Creates the branch + worktree + venv + frontend build + smoke test + BRANCHES.md entry. For ordinary work, use /new-feature (trunk) instead. Any Kind — captured in Step 3.5. The `--from-cloud` flag instead ADOPTS an existing `origin/claude/*` cloud branch (built on phone/cloud, never compiled): fetch → build the Mac env → run the tests the cloud couldn't → preview the merge against main.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

Create a new branch called `$0` for the bristlenose project.

If no branch name was provided (`$0` is empty), ask the user for one before proceeding.

**`$0` may also include optional flags after the branch name** — see Step 0. Bare `/new-branch foo` (no flags) is the default path: the human is just starting a branch and will be asked the usual questions interactively. Flags exist for the case where a parent Claude session is proposing the branch and has already made the decisions.

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

**`export PATH` + `hash -r` is necessary but NOT sufficient — call system binaries by absolute path.** Observed again 2026-06-28 in a from-cloud run: `mkdir` reported "command not found" *mid-script*, in a block that had already run `hash -r` at the top **and** had successfully run `mkdir` + 30 `ln -s` calls seconds earlier in the same shell. A shell-start hash-miss cannot explain a failure that appears *after* the same binary resolved fine — so the hash-cache story is at best incomplete and the `hash -r` incantation demonstrably did not prevent it. The root trigger is not fully understood, so don't rely on resolution working: invoke the handful of critical system binaries by absolute path, which can't be shadowed by PATH state or a stale hash table whatever the cause — `/bin/mkdir`, `/bin/ln`, `/bin/rmdir`, `/bin/rm`, `/usr/bin/ditto`, `/bin/date`. The PATH export + `hash -r` still belongs at the top of every block (for `git`, `python3.12`, `npm`, `osascript`, `gh` etc. that you won't path-qualify); absolute paths are the belt-and-braces for the few commands whose silent failure corrupts setup. The bash blocks below already use absolute paths for these — keep it that way.

**Instrumentation:** this skill logs via `bash /Users/cassio/Code/bristlenose/.claude/skills/_shared/wflog.sh new-branch <step> "<detail>"` — appends a JSON line to `.claude/workflow-log.jsonl`; `BRISTLENOSE_WORKFLOW_DEBUG=1` echoes each step to stderr. At minimum it logs `done` and writes the task route at Step 13; add `start` (Step 2) / `worktree-created` (Step 4) calls if you want fuller traces. Log calls are non-fatal — a logging failure must never stop the skill.

## Step 0: Parse optional flags

`$0` may contain a branch name optionally followed by any subset of these flags:

| Flag | Purpose | Skips |
|---|---|---|
| `--kind=<feature\|bugfix\|refactor\|docs\|ci\|chore\|spike\|diagnostic\|parked>` | Pre-declares Branch Kind | Step 3.5 question |
| `--base=<branch-name>` | Fork from a branch other than `main`. Used when the new branch sits on top of in-flight work that hasn't merged yet (typical case: stacked feature branches where conflicting with the parent would be guaranteed). Defaults to `main`. | Nothing — feeds Step 4 |
| `--plan=<path>` | Path (absolute or `~/`-style) to a Markdown file with the self-contained prompt for the new session | Nothing — feeds Step 4b |
| `--purpose="<one line>"` | "What it does" line for BRANCHES.md | Step 11 question |
| `--files="<comma,separated,paths>"` | Files this branch will touch | Step 11 question |
| `--print-launch-url` | Print a `claude://code/new?folder=…` URL the user can click to open a new desktop-app session | Step 14 |
| `--from-cloud[=<ref-or-fragment>]` | **Adopt an existing `origin/claude/*` branch** instead of forking a new one from main. Inverts Step 4 (fetch + checkout, not fork) and adds Steps 8.6 (run tests) + 9.5 (merge preview). See Step 0.6. | Changes Step 4; the name token becomes optional |
| `--no-tests` | In `--from-cloud` mode, skip the full pytest run (Step 8.6). Default is to RUN it — catching unrun-in-cloud defects is the whole point. | Step 8.6 |

**All flags are optional.** Bare `/new-branch my-branch` works exactly as before — interactive prompts for Kind, purpose, files. Flags exist so a parent Claude session that already knows these answers can pass them in and avoid re-asking.

Parse the args as: first token is the branch name, remaining tokens are flags. If a flag's value contains spaces it must be quoted (`--purpose="trim bundle: stage 1 + stage 2"`).

Validation:
- `--kind` value must be one of the nine entries in `docs/BRANCHES.md` § "Branch Kinds" (currently: feature, bugfix, refactor, docs, ci, chore, spike, diagnostic, parked); reject anything else with a clear message (don't silently fall back).
- `--base` value must be an existing local branch ref (`git show-ref --verify --quiet refs/heads/<value>`). If it doesn't exist, stop with: "Base branch `<value>` doesn't exist locally. Check `git branch --list` or fetch from origin first." If `--base` is absent, the effective base is `main`.
- `--plan` path must exist and be a `.md` file; if not, stop with the bad path quoted back.
- `--purpose` and `--files` are free text; no validation.

If a `--plan` path is provided, copy it now (before any branch creation) to `~/Code/bristlenose/docs/private/handoffs/<name>.md`. If a handoff file already exists at that target, **stop and ask the user** before overwriting — handoffs from prior sessions are precious. The existing Step 4b will pick the file up automatically once the worktree exists.

## Step 0.6: From-cloud mode (adopt an existing cloud branch)

**Only when `--from-cloud` is present.** This is a fundamentally different shape from the default. The default *creates* a new branch off main; from-cloud *adopts* an existing `origin/claude/*` branch that was built in a phone/cloud session and **never compiled or tested** (no venv, no Miro creds, no Xcode — see `feedback_spawn_task_prefers_local.md`). The job is to reconstruct the Mac build environment around someone else's already-written commits, run the tests the cloud could not, and report honestly how far it is from mergeable.

**Resolve which cloud branch.** `git fetch origin` first, then resolve `--from-cloud`'s value (or the bare name token) against `origin/claude/*`:

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"; hash -r 2>/dev/null || true
cd /Users/cassio/Code/bristlenose && git fetch origin --quiet
FRAG="<value of --from-cloud, or the bare name token, possibly empty>"
MATCHES=$(git branch -r --list "origin/claude/*${FRAG}*" | sed 's#origin/##;s/^[* ]*//')
```

- **Exactly one match** → that's `$CLOUD` (the full ref, e.g. `claude/figjam-miro-market-share-px52tg`).
- **Zero or many** → list all `origin/claude/*` with their last-commit subject + date and ask the user via `AskUserQuestion`. Never guess.

Derive the **clean name** = `$CLOUD` minus the `claude/` prefix and the trailing `-XXXXXX` cloud suffix. The suffix is the last `-`-delimited segment and is always present on cloud refs, but only strip it when it *looks* like a random token (contains a digit or uppercase) so a manually-named ref like `claude/my-feature` keeps its last word:

```bash
CLEAN=$(printf '%s' "$CLOUD" | sed -E 's#^claude/##' | sed -E 's/-([a-z]*[A-Z0-9][A-Za-z0-9]*)$//')
# verified across all 10 live origin/claude/* refs 24 Jun 2026: e.g.
#   claude/figjam-miro-market-share-px52tg -> figjam-miro-market-share
#   claude/opus-4-8-transcript-eval-7QpEY  -> opus-4-8-transcript-eval  (mid-name 4-8 preserved)
```

The clean name drives the worktree dir and the BRANCHES.md entry; **`$0` is set to `$CLOUD`** for the rest of the skill (so Step 11's branch references and the local branch name stay the cloud ref — see naming note below).

**Naming policy (deliberate).** Keep the **local branch = the full cloud ref** so a bare `git push` updates the existing PR with zero upstream gymnastics, and provenance is preserved (per `feedback_cloud_branches_trust_git.md`: prefer normal git flow, don't copy files around). The **worktree dir uses the clean name** (`bristlenose_branch <clean-name>`) for human friendliness. Consequence: the dir basename ≠ the branch name, so `/close-branch <clean-name>` can't auto-derive this worktree's path from the name — Step 11 records the exact dir + branch in BRANCHES.md so close-out can read them. (Known seam — see the WORKFLOW.md note.)

**Skip Step 3.5's Kind question** unless `--kind` is given: adopted cloud branches are almost always `feature` or `spike`. Default to `feature` if the branch has an open PR targeting main, else ask.

The remaining steps run with these from-cloud deltas: **Step 4** fetches + checks out the cloud ref instead of forking; **Step 4a** (new) inspects the diff; **Step 8.6** (new) runs the full suite; **Step 9.5** (new) previews the merge against main; **Steps 6–9** (env setup) and **Step 14** (handoff) are unchanged.

## Step 1: Validate branch name

After Step 0 has parsed flags out of `$0`, the remaining first token is the branch name. It must be lowercase letters, numbers, and hyphens only. No spaces, no leading hyphens, no underscores. If invalid, tell the user and stop.

Throughout the rest of this skill, `$0` refers to **just the branch name** (flags already extracted in Step 0).

**In `--from-cloud` mode this step is skipped** — there is no user-supplied branch name to validate. `$0` was set to the resolved cloud ref (`$CLOUD`) in Step 0.6, and the worktree dir uses the derived clean name. The clean name is already constrained to the validity rules above because cloud refs are themselves lowercase-hyphen.

## Step 2: Verify location

Check that:
- `pwd` is `/Users/cassio/Code/bristlenose`
- `git branch --show-current` returns `main`

If either fails, stop with: "Run /new-branch from the main bristlenose repo on the main branch."

## Step 3: Check for uncommitted changes

Run `git status --porcelain`. If there are changes, warn the user and ask whether to proceed. Do NOT stash — the changes stay on main.

## Step 3.5: Determine Branch Kind (mandatory)

**If `--kind=<value>` was passed in Step 0, use that value and skip the question.** Otherwise, ask the user which **Kind** best describes the branch. Use `AskUserQuestion` with these choices (full descriptions in `docs/BRANCHES.md` § "Branch Kinds"):

- **feature** — new capability or surface
- **bugfix** — corrective change to existing behaviour
- **refactor** — same behaviour, cleaner internals
- **docs** — documentation-only
- **ci** — build / release / test-infra
- **chore** — small ephemeral work (dep bumps, doc reconciliation, release tooling)
- **spike** — exploratory throwaway
- **diagnostic** — produces reports/repros for *other* branches to fix
- **parked** — opened now but on hold; may resume later

Record the answer; it gets written into BRANCHES.md in Step 11. Kind is descriptive metadata, not control flow — pick the one that best matches the work shape, don't agonise.

## Step 4: Create branch and worktree

**From-cloud mode — fetch + checkout, do NOT fork.** When `--from-cloud` is set, the branch already exists on the remote with real commits; the worktree must check it out, not create a fresh branch off main. The placeholder dir may already exist (the user often `mkdir`s it in advance) — `git worktree add` refuses an existing path, so `rmdir` it first **only if empty**:

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"; hash -r 2>/dev/null || true
cd /Users/cassio/Code/bristlenose
CLOUD="$0"                                   # full cloud ref, set in Step 0.6
CLEAN="<clean name from Step 0.6>"
DIR="/Users/cassio/Code/bristlenose_branch $CLEAN"
# git worktree add refuses an existing path; remove the empty placeholder if present
[ -d "$DIR" ] && /bin/rmdir "$DIR" 2>/dev/null
git worktree add --track -b "$CLOUD" "$DIR" "origin/$CLOUD"
```

`--track -b "$CLOUD"` creates a local branch with the cloud ref's name tracking `origin/$CLOUD`, so a later bare `git push` updates the existing PR. If `rmdir` fails (dir non-empty), stop and ask — something unexpected is there. **Then skip the rest of Step 4** (the fork logic below is default-mode only) and continue at Step 4a. Drop the setup-incomplete sentinel as in default mode.

---

*Default mode (no `--from-cloud`):* The effective base from Step 0 is the value of `--base`, or `main` if absent. Call this `$BASE` below.

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
/bin/mkdir -p "/Users/cassio/Code/bristlenose_branch $0/.claude"
/bin/date -u +"setup started at %Y-%m-%dT%H:%M:%SZ" \
  > "/Users/cassio/Code/bristlenose_branch $0/.claude/setup-incomplete"
```

The file's presence tells future Claude sessions (and the user) that the worktree environment isn't fully prepped yet. It gets removed in Step 8 only after the smoke test confirms the environment works. If setup aborts halfway, the flag survives and the next attempt knows.

## Step 4a: Inspect the cloud diff (from-cloud only, non-critical)

Before building, look at what you're adopting — per `feedback_cloud_branches_trust_git.md` (inspect first; prefer normal git flow) and `feedback_cloud_local_divergence_warning.md` (catch twin-build divergence early):

```bash
cd /Users/cassio/Code/bristlenose
git log --oneline main..$CLOUD                 # what the branch adds
echo "ahead $(git rev-list --count main..$CLOUD) / behind $(git rev-list --count $CLOUD..main)"
git diff --stat main...$CLOUD                   # the surface area
# Divergence check: matching commit subjects = the same work built twice (cloud + local)
comm -12 <(git log --format='%s' main | sort -u) <(git log --format='%s' main..$CLOUD | sort -u)
```

Report to the user, and adapt:
- **Divergence detected** (matching subjects, different SHAs) → warn: the work was built twice. Do NOT `git reset --hard` or `git merge`; reach for `git pull --rebase` (patch-id dedupe) at merge time. (See the memory.)
- **Messy diff** (staging dirs, rogue installs to `~/`, mixed concerns) → flag it; cherry-pick may beat a full merge. **Clean diff is the default and the happy path** — treat it like any other branch.
- Note whether the diff touches `desktop/` — but **do NOT skip Step 9's desktop setup just because it doesn't.** "No desktop *code* changed" ≠ "won't build the desktop app": the `.app` bundles the SPA-inside-sidecar, so *any* frontend/server feature is desktop-buildable (e.g. to test a WebView/popout surface), and a missing `desktop/Bristlenose/Resources/` fails Xcode's Copy phase with a cryptic error — even on a zero-Swift diff. Always run Step 9's ffmpeg/ffprobe/models symlinks (free pointers, no disk cost). The sidecar `ditto` (~428 MB) is the *only* deferrable part: skipping it is fine for a pure-Python/server branch you'll only `serve`, but if you skip it, **warn loudly** — "the desktop `.app` build will fail until the sidecar is present: `ditto` main's, or run `desktop/scripts/build-sidecar.sh` to bundle this branch's code." (`serve` is the *primary* QA target for such a branch; the `.app` build is still reachable, so never present it as impossible.)

## Step 4b: Seed handoff plan from prior diagnostic session (non-critical)

Diagnostic / sandpit / planning sessions write per-branch handoff prompts into `~/Code/bristlenose/docs/private/handoffs/` (the gitignored docs area in the main repo). If one exists for this branch, copy it into the new worktree's `.claude/plans/<branch>.md` so the next session lands with its purpose already in scope — no synthesis required.

```bash
HANDOFF="/Users/cassio/Code/bristlenose/docs/private/handoffs/$0.md"
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
PLAN_DIR="$WORKTREE/.claude/plans"
if [ -f "$HANDOFF" ]; then
  /bin/mkdir -p "$PLAN_DIR"
  /bin/cp "$HANDOFF" "$PLAN_DIR/$0.md"
  # Visible alias at worktree root — .claude/ is hidden, so users miss the
  # plan unless we surface it. Symlink shows up in Finder, IDE file trees,
  # and `ls`. HANDOFF.md is gitignored.
  /bin/ln -sf ".claude/plans/$0.md" "$WORKTREE/HANDOFF.md"
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

**From-cloud:** do NOT remove the sentinel here — defer it to Step 8.6, so it clears only after the test suite is also green.

## Step 8.6: Run the test suite (from-cloud only; the whole point)

**Only when `--from-cloud` is set and `--no-tests` is absent.** This is the single highest-value step in from-cloud mode: the cloud session had no venv, so the suite never ran there. Running it on the Mac is the only thing that catches "handler changed, test not updated" defects that sail past syntax-check and typecheck.

Run the suite **exactly as CI does** — deselect the real-LLM `slow` tests (no API key needed), so "green here" means "green in CI":

```bash
cd "/Users/cassio/Code/bristlenose_branch $CLEAN"
.venv/bin/python -m pytest --tb=short -q -m "not slow" -p no:cacheprovider
```

(~3 min for the full suite. Also run `cd frontend && npx tsc -b` to confirm the frontend typechecks on this machine.)

**Report failures; do NOT auto-fix them.** A flag that rewrites tests until they pass is an anti-pattern — it manufactures green. Surface each failure to the user with the raw traceback (per `feedback_dont_trust_failure_label_get_stderr.md`) and your read on whether it's (a) a genuine branch defect, (b) a stale test that the branch's intended behaviour outgrew, or (c) an environment-version difference (the Mac venv is often newer than the cloud assumed — e.g. a newer FastAPI uses lazy router inclusion, so introspecting `app.routes` for paths gives false negatives; probe routes with a TestClient request instead). Fix only with the user's nod, reproduce-first (`feedback_bug_reproduces_first.md`), and re-run to confirm.

**Only after the suite is green (and the Step 8 smoke checks passed), remove the sentinel:**

```bash
rm -f "/Users/cassio/Code/bristlenose_branch $CLEAN/.claude/setup-incomplete"
```

If `--no-tests` was passed, leave the sentinel in place and say so — the env is built but unverified.

## Step 9: Symlink trial-runs (non-critical)

`trial-runs/` is **partially tracked** — `trial-runs/fossda-opensource/perf-baselines/…` is in git, so every fresh worktree already has a *real* `trial-runs/` dir holding just `fossda-opensource/`. A blanket `ln -s main/trial-runs trial-runs` therefore can't work: the dir already exists, so it would either be refused or nest as `trial-runs/trial-runs`. **So symlink per-entry** — link each of main's `trial-runs/` children into the worktree's real dir, skipping anything already present (the tracked `fossda-opensource`, or links from a previous run). This makes every gitignored project in main reachable from the worktree via the normal relative path (`trial-runs/<project>`), **with no copies** — the whole point is to reuse one set of (large, video-bearing) trial data across worktrees.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
MAIN_TRIAL="/Users/cassio/Code/bristlenose/trial-runs"
TRIAL="$WORKTREE/trial-runs"
/bin/mkdir -p "$TRIAL"
made=0; skipped=0
if [ -d "$MAIN_TRIAL" ]; then
  for src in "$MAIN_TRIAL"/*; do
    [ -e "$src" ] || continue                       # empty-glob guard
    dst="$TRIAL/${src##*/}"                         # builtin, not $(basename) — basename hits the PATH/hash gremlin mid-loop (observed 3 Jul 2026: silent "command not found" → empty name → falsely "skipped 34", worktree left without trial-runs)
    if [ -e "$dst" ] || [ -L "$dst" ]; then
      skipped=$((skipped+1))                        # tracked fossda-opensource, or already linked
    else
      /bin/ln -s "$src" "$dst" && made=$((made+1)) || echo "✗ failed to link $(basename "$src")"
    fi
  done
  echo "✓ trial-runs: symlinked $made project(s) from main, skipped $skipped (tracked/existing)"
else
  echo "ℹ no trial-runs/ in main — nothing to symlink"
fi
```

Per-entry, not a blanket symlink: the tracked `fossda-opensource` real dir is left untouched, every other (gitignored) project becomes reachable via `trial-runs/<project>`, and `./scripts/dev.sh` works. The links match the `trial-runs/*` gitignore, so they never show up as worktree changes. (`*` skips dotfiles, so `.DS_Store` is excluded; loose recordings get linked too, harmlessly — a symlink is a few bytes.)

> ⚠️ **Shared-db caveat — only bites branches that add an Alembic migration.** Each project's serve DB lives *inside* the project at `bristlenose-output/.bristlenose/bristlenose.db`, so a symlinked project shares **one** db across every worktree. For ordinary branches that's exactly what you want. But a branch that adds a migration (a new `bristlenose/server/alembic/versions/NNN_*.py`) will — the first time it runs `bristlenose serve` against a shared project — upgrade that db to *its* head. After that, any worktree/main *without* the migration fails to reopen the project: `CommandError: Can't locate revision 'NNN'` (verified — `bristlenose/server/db.py` runs `alembic upgrade head` on every serve startup). Recovery is one **lossless** command — it resets only the version marker; data and the extra tables are untouched:
> ```bash
> # reset to the revision main's code is on (currently 001 — check main's alembic/versions/)
> sqlite3 "<project>/bristlenose-output/.bristlenose/bristlenose.db" \
>   "UPDATE alembic_version SET version_num='001';"      # or: alembic stamp <main-head>
> ```
> If you're QA-ing a migration-bearing branch and would rather not migrate a shared db at all, serve a project you won't also serve from main, or `ditto` that one project into the worktree as a real dir. Once the branch merges, main carries the migration too and the divergence disappears.

Then symlink the gitignored desktop binaries from main, so Xcode's Copy Resources phase finds them when the user opens the worktree's `Bristlenose.xcodeproj` and Cmd+R's. Without these, the .app builds without ffmpeg/ffprobe and the pipeline can't probe video files. Each link is gated on existence, so worktrees on machines that have never run `desktop/scripts/fetch-ffmpeg.sh` in main don't error.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
for path in ffmpeg ffprobe models; do
  src="/Users/cassio/Code/bristlenose/desktop/Bristlenose/Resources/$path"
  dst="$WORKTREE/desktop/Bristlenose/Resources/$path"
  if [ -e "$src" ] && [ ! -e "$dst" ]; then
    /bin/mkdir -p "$WORKTREE/desktop/Bristlenose/Resources" \
      && /bin/ln -s "$src" "$dst" \
      && echo "✓ symlinked $path from main" \
      || echo "✗ failed to symlink $path"
  elif [ -e "$dst" ]; then
    echo "✓ $path already present in worktree"
  else
    echo "ℹ $path not in main — run desktop/scripts/fetch-ffmpeg.sh in main first if you'll build the desktop .app"
  fi
done
```

Chain `/bin/mkdir`/`/bin/ln`/`echo` with `&&` (not separate lines): a bare `echo` after a failed `mkdir`/`ln` would still fire, falsely reporting "✓ symlinked" while `Resources/` doesn't exist. (Observed 2026-05-08 alongside the `hash -r` issue — three "✓ symlinked" lines printed despite `mkdir`/`ln` failing with "command not found".) The absolute-path forms (`/bin/mkdir`, `/bin/ln`) are why this block now resolves regardless of PATH/hash state — it was exactly this block that failed again on 2026-06-28 with bare names *after* `hash -r`; see the PATH note at the top of the skill.

Then copy main's PyInstaller sidecar bundle into the worktree using `ditto`. Without it, Cmd+R on the default Bristlenose scheme fails with "Bundled sidecar missing at …" — and the bundled scheme is the only TestFlight-honest path; the v0.2-launcher fallbacks (External Server / Dev Sidecar) are deprecated scaffolding. The sidecar is ~428 MB per worktree, disk-cheap. If you're iterating on `bristlenose/server/` or signing, run `desktop/scripts/build-sidecar.sh` in this worktree afterwards to replace the copy with a locally-built bundle.

**Why `ditto`, not `cp -R*` or symlink:** A symlink at the top-level breaks Xcode's `Copy Sidecar Resources` build phase, which uses `rsync -a` and preserves symlinks as dangling-outside-bundle pointers the sandbox can't follow. `cp -RL` materialises real bytes but *also dereferences internal symlinks*, which breaks the PyInstaller bundle's rpath-relative library structure — mlx then can't find its Metal library and the sidecar crashes at startup with "Failed to load the default metallib". `cp -R` (default `-P`) preserves internal symlinks but follows the source-argument symlink correctly. `ditto` is the macOS-native bundle-aware copy: preserves resource forks, extended attributes, codesignatures, and internal symlinks; auto-dereferences the source-argument. Use `ditto`.

```bash
WORKTREE="/Users/cassio/Code/bristlenose_branch $0"
src="/Users/cassio/Code/bristlenose/desktop/Bristlenose/Resources/bristlenose-sidecar"
dst="$WORKTREE/desktop/Bristlenose/Resources/bristlenose-sidecar"
if [ -d "$src" ] && [ ! -e "$dst" ]; then
  /bin/mkdir -p "$WORKTREE/desktop/Bristlenose/Resources" \
    && /usr/bin/ditto "$src" "$dst" \
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
    echo "✗ desktop binaries not resolvable — Cmd+R from this worktree's Xcode project will produce an .app without them. Either: re-run /new-branch setup, or run desktop/scripts/fetch-ffmpeg.sh from main."
  fi
else
  echo "ℹ no desktop/Bristlenose/Resources/ in this worktree — desktop .app build will be missing ffmpeg/ffprobe. Run desktop/scripts/fetch-ffmpeg.sh in main first if you'll build the desktop app."
fi
```

## Step 9.5: Merge-readiness preview (from-cloud only, non-critical)

**Only when `--from-cloud` is set.** "Ready to merge" is the goal, but a cloud branch that sat while main moved is usually behind and conflicting. Characterise the gap **read-only** — never auto-resolve conflicts or rebase here (that's design-laden human work; doing it silently is how you corrupt a PR):

```bash
cd /Users/cassio/Code/bristlenose
# Read-only in-memory merge — lists conflicting files without touching any working tree
git merge-tree --write-tree --name-only main $CLOUD > /tmp/nb-merge.out 2>&1
echo "merge vs main: $([ $? -eq 0 ] && echo CLEAN || echo CONFLICTS)"
tail -n +2 /tmp/nb-merge.out          # conflicting paths (line 1 is the tree OID)
gh pr list --head $CLOUD --state all --json number,state,mergeable,url 2>/dev/null
```

Also scan for the branch's own self-declared blockers — cloud sessions often leave a build-status / "before merge" section in a design doc (grep the changed `docs/*.md` for `before merge`, `size gate`, `i18n`, `TODO`, `assumption`). Report a **merge-readiness verdict**, not a green light:

- builds + tests: ✅/❌ (from Steps 8 / 8.6)
- conflicts with main: list the files (1 doc + 1 code file is tractable; many code files is a real reconciliation)
- pre-merge blockers the branch flagged (e.g. i18n / size-gate, security posture decisions)

Make clear what's left: typically a rebase/merge onto local main + the flagged blockers. The flag gets it **built, tested, and characterised** — it does not make it mergeable on its own.

## Step 10: Stay local (do NOT push)

**Do NOT push to origin.** The branch stays local until the user explicitly asks to push. This avoids cluttering the remote with branches that may be short-lived or experimental.

Tell the user: "Branch is local only. Push with `git push -u origin $0` when you're ready." **From-cloud:** the branch already has a remote + PR; a bare `git push` from the worktree updates that PR (the local branch tracks the cloud ref). Don't push without the user asking — updating a PR is outward-facing.

## Step 11: Update docs/BRANCHES.md

Read `docs/BRANCHES.md` to understand the current format. Check if `$0` already has an entry (partial previous run) — if so, skip this step.

**From-cloud — record the seam explicitly.** Because the worktree dir uses the clean name but the local branch keeps the cloud ref, the name→dir derivation `/close-branch` relies on won't work. So the entry MUST carry both, plus the PR and the Step 9.5 verdict, so close-out can read them rather than guess:
- Worktree Convention row: dir = `bristlenose_branch <clean-name>/`, Branch = the full cloud ref.
- Backup Strategy row: remote = `origin/<cloud-ref>` (PR #N).
- Active Branches section: add a `**Local branch:**` line (the cloud ref) distinct from `**Worktree:**`, a `**Remote:**` line naming the PR, a one-line pointer to the worktree's `.claude/from-cloud-import-notes.md`, and a `**Blockers before merge:**` list from Step 9.5. Mark the heading `(imported from cloud)`.

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

   **Kind:** <one of: feature | bugfix | refactor | docs | ci | chore | spike | diagnostic | parked> — <one-line summary of what the branch is for>
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

**From-cloud — report the verdict, not just "done".** The user needs to know how far from mergeable it is:
- Imported: `<cloud ref>` (PR #N) → worktree `bristlenose_branch <clean-name>/`
- Build: ✅ venv + frontend + CLI · Tests: ✅ N passed (CI-equivalent) / ❌ list failures + your fix-or-surface call
- Defects found by running what the cloud couldn't: <one line each, or "none">
- Merge readiness: conflicts with main (`<files>`) + flagged blockers (`<i18n/size-gate/…>`) → **not mergeable yet; remaining work = rebase onto local main + blockers**
- Notes file: `.claude/from-cloud-import-notes.md` in the worktree

Then record the task route in the worktree (so `/close-branch` knows this was the branch path) and log completion:

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"; hash -r 2>/dev/null || true
WT="/Users/cassio/Code/bristlenose_branch $0"
/bin/mkdir -p "$WT/.claude"
printf '{"route":"branch","branch":"%s","started":"%s"}\n' "$0" "$(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)" > "$WT/.claude/current-task.json"
bash /Users/cassio/Code/bristlenose/.claude/skills/_shared/wflog.sh new-branch done "$0"
```

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
