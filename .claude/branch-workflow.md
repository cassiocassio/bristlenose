# Branch workflow and branch switching

Moved verbatim from the root `CLAUDE.md` on 5 Nov 2026 to cut what every session loads on every turn. The root keeps a short rule and a pointer here.

### Branch workflow (solo — trunk by default)

**This is a solo project; the default is trunk.** Work directly on `main`, in the main repo, in the env that's already built. Commit at every green checkpoint. **Do not spin a branch/worktree per feature** — the cost is the worktree's env build (`.[dev,serve]` venv + frontend build + ffmpeg/model symlinks + smoke test), paid on creation *and* teardown, routinely out of proportion to the work. GitHub's branch-per-feature + PR flow is built for teams across timezones; for one person it's pure ceremony. (5 → 50 → 500 devs need it; a team of one does not.)

**A branch is free; a worktree costs an env.** `git branch foo` is a 40-byte pointer — instant, no env. `git worktree add` is a second working copy that must be built and proven. Your safety net is git *history*, not worktree *isolation*:
- **Commit often** — every green checkpoint is a rollback point.
- **Checkpoint before risky surgery:** `git branch -f checkpoint` (free pointer); roll back with `git reset --hard checkpoint`.
- **Undo something already committed:** `git revert <sha>` — safe, never loses history. This is the "plausible rollback".
- **Rescue one file from a bad session:** `git restore -s <good-sha> -- <path>`.
- **Panic button:** `git reflog` → `git reset --hard HEAD@{n}`. Nothing is lost for 90 days.
- **Safe remote backup, no CI/release:** `git push origin main:wip`.

`main` is not "released" until *you* push + tag (evening rule), so a half-done change on local `main` is fine — just don't push it. Trunk is also *safer* for this repo: the two worst recorded incidents (edits landing on the wrong working copy; stale `__pycache__` after an in-place switch) were both *caused by* the multi-worktree pattern. Fewer working copies = fewer feet to shoot.

**Don't default to offering a new branch.** When a handoff/plan is written, the default next step is to do the work on `main`, NOT to hand back a `/new-branch` invocation. Only propose a worktree when the exception below genuinely applies, and say *why*. (Defaulting-to-branch is exactly how the retired "short-lived branches / one-branch-plus-nudges" rules accreted — don't regrow them. See memory `feedback_solo_trunk_default.md`.)

**The worktree is the rare exception — only when two envs must be live at once:** a long pipeline run going while you code something else, or a genuine second parallel Claude session that would clobber the working tree. Then — and only then — use **`/new-branch`** (never hand-roll a worktree; DIY ones produce broken envs: missing extras, unbuilt frontend, missing symlinks). Checkpoint *pointers* (`git branch -f`) are not worktrees and need no skill.

**Session-start check** (cheap, still worth it):

```bash
pwd
git branch --show-current
test -f .claude/setup-incomplete && cat .claude/setup-incomplete
.venv/bin/python -c 'import sys; print("venv", ".".join(map(str, sys.version_info[:2])))'; grep '^python ' .tool-versions
```

**The venv's minor must match `.tool-versions`.** If it doesn't, the env has drifted off the pin — rebuild before doing real work (`rm -rf .venv && python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev,serve]'`), don't work around it. Drift is silent: the suite still passes on a neighbouring minor, so nothing fails until a release build disagrees with the dev box. Found 4 Aug 2026 — a crash-recovery `uv venv` had quietly rebuilt `.venv` on 3.11 **and** dropped `presidio-analyzer`/`presidio-anonymizer` (core deps, stage 7 PII removal) from the install, with a green suite throughout because those tests mock or skip. **Don't reach for `uv` or `mise` to fix it** — that migration is Phases 1–4 of `docs/design-dev-environment.md` and is explicitly gated post-TestFlight; the house mechanism is `python3.12 -m venv` + `pip install -e`. A stray untracked `uv.lock` is the tell.

If you're in a worktree (rare) and `.claude/setup-incomplete` exists, its env isn't prepped — don't start real work until `/new-branch` finishes or setup is done manually (frontend build, venv, smoke test). A `PreToolUse` hook in `.claude/settings.json` blocks `git checkout`/`git switch` to feature branches from the main repo — harmless under trunk (you stay on `main`) and it still guards against accidental in-place checkouts.

**Session-handoff sentinels:** `.claude/setup-incomplete` (negative — `/new-branch` setup didn't finish) and `.claude/last-end-session.json` (positive — `/end-session` signed off; carries `head_sha` for drift detection). Both gitignored.

**Branch handoff plan:** if `HANDOFF.md` exists at a worktree root (gitignored symlink to `.claude/plans/<branch>.md`), it's the **starting brief** — read it first, don't synthesise from sandpit logs. Canonical home is `docs/private/handoffs/<branch>.md` (gitignored, backed up by `backup.sh`). **Handoffs are NOT specs** — before drafting a plan, run `git log -3 -p <files-the-handoff-names>` and grep commit bodies for decision-shapes ("not Y", "deferred to", "rejected", "chose X over Y", "post-TF", "status-only"). If a recent commit chose against an affordance the handoff proposes, raise it as a question BEFORE planning. Recent commits win unless the user overrides. (Memory `feedback_handoff_not_a_spec.md`.)

**Skills for the worktree exception (not the default path):**
- **`/new-branch <name>`** — creates branch + worktree + venv + symlinks + `docs/BRANCHES.md` entry. Use only for genuine parallel-env work; never hand-roll a worktree (DIY ones ship broken envs). If `disable-model-invocation` blocks auto-invocation, read `.claude/skills/new-branch/SKILL.md` and follow every step manually.
- **`/new-feature <name>`** / **`/close-feature`** — the trunk default: start / finish work on `main`, no worktree. See `.claude/skills/WORKFLOW.md`.
- **`/close-branch <name>`** — archives a merged worktree branch; reads `.claude/last-end-session.json` and prompts before archiving an un-end-sessioned or drifted branch.
- **Reverting a merge:** `git revert -m 1 <merge-commit-hash>`.

See `docs/BRANCHES.md` for any active worktrees and the parked set.

## Branch switching

When the user says "let's switch to branch X" or similar, **automatically run this checklist before switching**:

### Pre-switch checks (on current branch)

1. **Check for uncommitted changes** — `git status`
   - If changes exist, commit them with a descriptive message (ask user for message if unclear)
   - Never leave uncommitted work when switching branches
2. **Run tests** — `.venv/bin/python -m pytest tests/`
   - If tests fail, warn the user before proceeding
3. **Run linter** — `.venv/bin/ruff check .`
   - If lint errors, fix them or warn before proceeding

### Switch

4. **Execute the switch** — `git checkout <branch-name>`
   - If branch doesn't exist locally but exists on remote: `git checkout -b <branch-name> origin/<branch-name>`
   - If branch doesn't exist anywhere, ask user if they want to create it

### Post-switch cleanup

5. **Clear Python cache** — `find . -name __pycache__ -exec rm -rf {} +`
   - Editable installs cache imports; stale `.pyc` files cause mysterious bugs
6. **Reinstall package** — `.venv/bin/pip install -e .`
   - Shebang paths and import paths may reference old locations
7. **Report status** — `git status` + `git log --oneline -3`
   - Show user what branch they're on and recent commits

### Why this matters

Python editable installs (`pip install -e .`) write absolute paths into `.pth` files. Switching branches can leave stale bytecode that serves old code, causing:
- `ImportError` for modules that don't exist on the new branch
- Functions behaving like the old branch's version
- Mysterious test failures

The PreferencesFile incident (keyboard-navigation branch, Feb 2026) was caused by exactly this — stale imports from a feature that was stashed on another branch.
