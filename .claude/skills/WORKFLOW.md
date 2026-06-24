# Workflow skills — index & cheat-sheet

The canonical reference for the bookend workflow. Solo, trunk-by-default. The skills here point back to this file.

**The one idea:** you work on `main`. Commands *bookend* your work — one to start, one to finish. Branches are the exception, not the rule.

## The verbs

| You type | When | What it does |
|---|---|---|
| `/new-feature` | starting almost anything | loads the plan/card → you work **on main**. No branch, no setup. |
| `/close-feature` | done with that work | tests + lint + QA nudges + docs + changelog line + marks it done + commits |
| `/new-branch` | work needs its own live env *(rare)* | everything `new-feature` does **+** worktree · venv · frontend build · smoke test |
| `/new-branch --from-cloud` | pulling a phone/cloud `claude/*` branch down to the Mac | fetch + adopt the cloud branch into a worktree · build the Mac env · **run the tests the cloud couldn't** · preview the merge vs main · report a merge-readiness verdict |
| `/close-branch` | done with a branch | merge + stale-marker + detach worktree + update BRANCHES.md |
| `/new-release` | shipping to the world | bump · finalise changelog · tag · push · verify PyPI *(evening; `--dry-run` to rehearse)* |
| `/end-session` | stepping away | parks state safely — resume later or not (time, not task) |

## Which "new" do I type?

- **Default → `/new-feature`.** Work on main, commit as you go.
- **`/new-branch` only if:** you need a 2nd env live at once · multi-day *and* main must stay shippable meanwhile · throwaway spike.
- Unsure? It's `/new-feature`.

## Typed the wrong close? It catches you.

- `/close-feature` while on a branch → *"you're on a branch — close it properly?"*
- `/close-branch` while doing trunk work → *"your current task is on main — did you mean `/close-feature`?"*

You can't strand a branch or hit a confusing error by guessing.

## Reach tiers

- **feature** = your machine (local `main`) · **branch** = a private remote ref · **release** = the world sees it.
- `main` isn't public until *you* `/new-release`. A half-done `main` is invisible — don't fear it.

## Safety net — just commit, liberally

Commit at every green checkpoint with a real message. `git log --oneline` is your rollback **menu**; `git reset --hard <sha>` returns to a named state. That's the whole defence — no hooks, no wip refs.

| Want to… | Do |
|---|---|
| roll back to a checkpoint | `git reset --hard <sha>` (from `git log`) |
| undo a commit cleanly | `git revert <sha>` |
| back up off-machine, no CI | `git push origin main:wip` |
| last-ditch recovery | `git reflog` |

---

## How it's wired (for maintainers)

- **State file:** `.claude/current-task.json` (per-working-dir, gitignored) carries task *context* — task line, plan, `changelog_needed`, `summary` for `/new-release`. It is NOT the routing oracle: routing is read from **git reality** (`close-feature` checks the current branch; `close-branch` checks `git worktree list`). `new-feature` writes it; `close-feature` clears it.
- **Instrumentation:** every skill calls `.claude/skills/_shared/wflog.sh <skill> <step> "<detail>"`, appending one JSON line to `.claude/workflow-log.jsonl` (gitignored). **Debug mode:** `export BRISTLENOSE_WORKFLOW_DEBUG=1` echoes each step to stderr. Log path overridable via `BRISTLENOSE_WORKFLOW_LOG`. Tested by `tests/test_workflow_log.py`.
- **`new-branch` = old `new-feature`** (the worktree/env machinery, renamed). **`new-feature` is now the thin trunk skill.** All five bookends are `disable-model-invocation: true` — you type them; Claude never auto-fires them (keeps them out of the activation budget, and nothing ships by surprise).
- **No skill calls another skill.** Bookends call **scripts** directly, **prompt** for heavy siblings (`/true-the-docs`, `/usual-suspects`, `/sync-board`), and the wrap steps are **inlined** into `close-feature` (not a shared file — `close-branch` keeps its own richer flow with the `/end-session` sentinel checks).
- **Backups of the pre-bookend skills:** `.claude/skills-backup-2026-06-21/` (and git history).
- **`/new-branch --from-cloud` naming seam (known).** Adopted cloud branches keep the local branch = the full `claude/<name>-XXXXXX` ref (so a bare `git push` updates the existing PR) but put the worktree at `bristlenose_branch <clean-name>/`. So the dir basename ≠ the branch name, and `/close-branch <clean-name>` can't derive the worktree path from the name the way it does for normal branches. Mitigation today: `--from-cloud` records both the dir and the branch (and the PR) in the BRANCHES.md entry. Proper fix (deferred): teach `/close-branch` to read the worktree path from the BRANCHES.md Worktree Convention row instead of deriving `bristlenose_branch $0`. This also subsumes the pre-existing space-vs-underscore dir drift (recent dirs like `bristlenose_branch_desktop-export/` already break the space-based derivation).
