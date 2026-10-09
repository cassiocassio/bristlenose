---
name: tighten-the-ratchet-on-easy-squish-bugs
description: >
  Drive a counted, mechanically fixable class of defect (type errors, lint
  warnings, missing timeouts, unregistered files) down to zero or near it, then
  lock the gain in so it cannot come back. Measures where the gate measures,
  partitions the findings by CAUSE into disjoint slices, fans them out to
  parallel fixers under honest-fix rules, verifies the combined result
  independently, and ratchets or hardens the gate — building the counter first
  if nothing counts the defect yet. Use when a number in CI is large, boring,
  and mostly mechanical; not for work that needs an opinion per item.
user-invocable: true
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent, SendMessage, ListAgents
---

# Tighten the ratchet on easy-squish bugs

Distilled from mypy 146 → 0 in one morning (9 Oct 2026: five fixer sessions,
three real bugs, then the gate made blocking and the tool pinned —
`724b969c`..`94a0e076`, branch `mypy-hard-gate`). Tested the same day on two
items that had no gate at all: CI job timeouts (`372711c2`) and an ESLint
warning ceiling (`9dd5230a`).

## The philosophy

The principles are the *why*; the steps below are the *how* and do not repeat
them.

1. **Measure where the gate measures.** The number that matters is the one CI
   computes, on CI's tool version, platform and **every path that runs the
   thing**. A local count is a forecast.
2. **Group by cause.** One construct often produces a large share of findings
   (one helper was 44 of 146). Find the biggest fan-out first.
3. **Slices partition the total.** Every finding has exactly one owner.
4. **The count must fall because the code got better.** No suppression without
   a specific code, a reason and a ledger entry; nothing widened to make a
   finding vanish; stale suppressions deleted, never re-targeted.
5. **Every finding is a possible bug until read.** A real bug gets a test that
   fails first, then the fix, flagged.
6. **Proportion.** Fan-out sized to the work. Fixers run only the tests they
   touched; the coordinator runs the full suite once.
7. **The coordinator verifies; it does not tally.** Reports are claims about
   the tree; re-measure.
8. **A lock that passes on arrival proves nothing.** Every ceiling, test or
   gate this work adds is shown failing on the old tree (or a mutant) before
   it is trusted.
9. **Reversible acts are ours, irreversible ones the user's.** Commit locally,
   prepare gate promotions on a branch; pushes, ceiling adoption and repo
   settings belong to the user.

## When to use it, and when not

Use it when every item's fix is determined by the code or by a measurement:
an annotation the callers dictate, a timeout sized from real run durations, a
directive the linter itself calls unused.

Not when:
- the fix needs an **opinion** per item (a design status, wording, a product
  call) — mechanical fixers will invent one;
- there is no number and no cheap way to build a counter — without a count
  there is nothing to ratchet;
- the fix changes what users see — that is a feature, not a squish.

If the whole job is a handful of findings with one cause, skip the fan-out:
fix it yourself, then still do Steps 5–6 (verify, lock).

## Procedure

### Step 0 — Is anything counting this?

If no gate counts the defect, the deliverable includes the counter: a test, a
linter option (`--max-warnings`), a `ratchet.json` entry, a structural check.
Write it first and run it on the current tree; it must fail, naming the
findings. That failure is your baseline.

### Step 1 — Measure like CI

- Find the gate's exact command (from a CI log, not from config), its tool
  version, its platform.
- List every **caller and path** that runs the gated thing (a reusable
  workflow called from a release workflow, a second entry point) and measure
  each. A number sized on one path can break another.
- Measure against CI's **installed set**, not just its platform flag: a
  dependency with a platform marker (mlx is darwin-only) is typed on the Mac
  and absent on the Linux runner, so a check can pass here and fail there.
- Reproduce locally with the same command and version (a scratch venv if
  yours differs; `--platform linux` or the tool's equivalent). Explain every
  local/CI difference before going on.

### Step 2 — Categorise

Count by rule/code, then by file, then look for the one construct behind many
findings. **Exception: when fixers will run an autofixer that rewrites whole
files** (`ruff --fix`, `eslint --fix`), slice by directory instead, so no two
fixers ever hold the same file — two causes sharing a file is a lost update. Output a table — slice, count, files, fix shape, chance of real
bugs — and show it to the user unless they already said go.

### Step 3 — Brief

Self-contained; the fixer never sees this conversation. Template:

```
Repo: <abs path>, work on `main` (trunk). Goal: <metric>. CI measured <N>
on <date> (<tool> <version>, <platform>, run <url>); gate: <command> in
<workflow>; ceiling: <ceiling or "none yet — build it">. You are one of <K>
fixers. YOUR SLICE: <definition, counts, files; what is NOT yours>.
RESERVED: <lines/regions another prepared branch or session is editing —
do not touch>. <Known cause and fix shape, if known.>

Rules:
- Measure with <exact command>, own cache dir in your scratchpad.
- Exit codes come from an UNPIPED run; quote the tool's summary line.
- Fix honestly: no suppression without a specific code + reason (list each);
  nothing widened; stale suppressions deleted, not re-targeted.
- A real bug: failing test first, then fix, flagged.
- Any lock you add (test, ceiling, option) is shown failing first, then
  passing — give both commands and exit codes.
- Scripted edits assert their match count.
- No full test suite: only tests for what you touched, plus the linter and
  the repo's structural checks (`check-gate-policy.py`,
  `gen-test-inventory.py --check`). If a generator must regenerate, keep only
  the lines your change caused.
- Concurrency: re-read before editing; `git commit -F- -- <paths>` (a new
  file needs `git add` in the same command); your hunks only; never --amend,
  stash or `git add -A`; commit locally, don't push; don't edit ratchet.json.
- Report: before/after, commits, suppressions added/removed (file:line,
  reason), real bugs + tests, lock proof, thin or missing evidence, anything
  left or uncommitted.
```

### Step 4 — Fan out

While fixers are editing `main`, **don't commit there yourself**: pre-commit
stashes every unstaged change in the checkout while its hooks run, so for
those seconds the fixers' edits vanish. Work on a branch worktree, or warn
them. Background subagents (`Agent`, all in one message) for small slices; separate
sessions (`spawn_task`) for large ones — tell the user each chip opens a
worktree by default while the brief says `main`, and let them choose. Do not
work a slice yourself while it is out.

### Step 5 — Verify

- Collect every report (`SendMessage` + `notify_when_idle` for sessions).
- Read each commit's diff; `git status` for stray edits.
- Re-measure the combined tree on CI's toolchain; run the full suite once;
  run the linter.
- Read the line behind every added suppression and every "real bug".
- Fix stragglers (between slices, tool-version-only) yourself.
- Flag decisions resting on thin evidence (few observations, no runs) rather
  than silently re-guessing them.
- Close/archive fixers once each has reported and committed.

### Step 6 — Lock it in

Use the gate's own mechanism, already proven red in Step 0 or by the fixer.
For an existing CI-owned ratchet, the user pushes first, then the ceiling moves
from a CI measurement (here: `gh workflow run ratchet-tighten.yml`, then
`--adopt`). When a soft gate reaches zero, prepare its promotion on a branch in
a scratch worktree (mypy's set: drop `soft`/`continue-on-error` and its
`soft-gates.json` entry, pin the tool exactly with a pinning-register row,
update the doc that called it soft), run `check-gate-policy.py` and
`gen-test-inventory.py --check` there, and say it lands after CI confirms.

### Step 7 — Report

One table: slice, before → after, commits, real bugs. Then the suppressions
ledger, what you verified yourself, decisions on thin evidence, and the
user's next acts in order.

## Lessons paid for (append)

- A blanket `sed` that restored one value in `inventory.json` also overwrote
  two nulls meant to be null. Assert match counts; rebuild from the base file
  and change only the intended line.
- A generator run in a scratch worktree reported the pytest count as unknown
  (no installed package there). Diff regenerated files; keep only your lines.
- A fixer that builds a commit with `commit-tree` (to dodge others' hunks)
  skips pre-commit hooks; the coordinator's full suite is its only check.
- A fixer judged a lock "passing" from `| tail`'s exit code. Unpiped runs only.
- Reusable CI jobs ran 4× longer when called from the release workflow than in
  plain CI (29 vs 7.5 min). Size against the slowest caller.
- Triage before fan-out paid: of six audit items, three failed "when not to
  use" (a design status per mockup; `doctor || true`, which hid that `doctor`
  always exits 0 — a CLI behaviour decision; making `npm audit` blocking — a
  policy call). Measuring an item is often how you find it is not a squish.
- A swallowed step (`pip install … >/dev/null 2>&1 || true`) turned out to be
  unneeded entirely; the honest fix was deletion, proven by running the test
  without what it claimed to need.
