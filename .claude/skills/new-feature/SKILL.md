---
name: new-feature
description: Start a piece of work on main (trunk — the DEFAULT path). Loads the plan / 100days item, checks recent history, agrees a plan, and records the task. No branch, no worktree, no env setup. For work that needs an isolated live environment, use /new-branch instead.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Edit, Glob, Grep
---

Start work on `main` for the task described in `$ARGUMENTS`.

This is the **default** way to start work: trunk. You stay on `main`, in the env that's already built, and commit liberally as you go. Reach for `/new-branch` only when two envs must be live at once, the work is multi-day *and* main must stay shippable meanwhile, or it's a throwaway spike.

**Instrumentation:** every step calls the shared logger so the run is observable. Set `BRISTLENOSE_WORKFLOW_DEBUG=1` for verbose step-by-step echo to stderr. The log lands at `.claude/workflow-log.jsonl`. Call shape: `bash .claude/skills/_shared/wflog.sh new-feature <step> "<detail>"`.

**Failure policy:** Step 1 (location) is critical — stop on failure. The rest are about loading context and recording state; warn and continue.

## Step 1: Confirm trunk + log start

```bash
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"; hash -r 2>/dev/null || true
bash .claude/skills/_shared/wflog.sh new-feature start
git branch --show-current
git status --short
```

If the current branch is **not** `main`, you're likely already inside a worktree. This is the **forgiving** case — don't fail hard:

> "You're on `<branch>`, not `main`. If you meant to start isolated work, you're already in the right place — just work here and `/close-branch` when done. To start *trunk* work, `cd /Users/cassio/Code/bristlenose` first, then re-run `/new-feature`."

Then stop. On `main`, continue.

## Step 2: Load the plan context

- If `$ARGUMENTS` names or matches a `docs/private/100days.md` item, read that entry, note its sprint tag, and find any linked board card.
- If a handoff exists at `docs/private/handoffs/<slug>.md`, read it as the **starting brief** — don't synthesise from scratch.
- **Handoffs aren't specs.** Run `git log -3 -p` on the files the task/handoff names and grep commit bodies for decision-shapes ("not Y", "deferred to", "rejected", "chose X over Y", "post-TF", "status-only"). If a recent commit contradicts the plan, raise it as a question BEFORE planning. Recent commits win unless the user overrides.

```bash
bash .claude/skills/_shared/wflog.sh new-feature context "<what was loaded>"
```

## Step 3: Plan — or skip it for a one-liner

If you could describe the diff in **one sentence** (typo, log line, rename, one-line copy fix), **skip planning** — just do the work. Otherwise draft a short bullet plan and get the user's nod. For anything structural or convention-touching, offer `/usual-suspects` on the plan first.

```bash
bash .claude/skills/_shared/wflog.sh new-feature plan "<skipped|drafted: N bullets>"
```

## Step 4: Record the task

Write `.claude/current-task.json` (per-working-dir, gitignored). Get the timestamp from bash (`date -u +%Y-%m-%dT%H:%M:%SZ`):

```json
{
  "route": "main",
  "task": "<one line>",
  "source": "<100days line / board card / freeform>",
  "plan": ["<bullet>", "..."],
  "started": "<UTC now>",
  "changelog_needed": false
}
```

Set `changelog_needed` true only if the work is user-facing (ships in the wheel / changes the app). Then:

```bash
bash .claude/skills/_shared/wflog.sh new-feature state-written main
```

## Step 5: Hand back

Tell the user: *"On `main`, task recorded. Build away — I'll commit at every green checkpoint. Run `/close-feature` when done."*

```bash
bash .claude/skills/_shared/wflog.sh new-feature ready
```

## During implementation (your behaviour — not a step the user runs)

**Commit liberally — at every green checkpoint — with real messages.** Each commit is a labelled rollback point: `git log --oneline` is the menu, `git reset --hard <sha>` returns to a named state. That is the whole safety net; no hooks, no wip refs. Reflog is the last-ditch backstop, not the plan.
