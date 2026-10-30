# Codex instructions for Bristlenose

Read `CLAUDE.md` for repository conventions and the relevant directory's
`CLAUDE.md` before working there. The workflows in `.claude/skills/` apply to
Codex too: read their `SKILL.md` files and follow them using the available tools.
They contain BN-specific setup and close-out knowledge; do not replace them
with a generic branch/worktree routine.

## Shared checkout is the default

Ordinary work belongs in the established checkout at
`/Users/cassio/Code/bristlenose`, normally on `main`, using its working environment.
This is a solo-owner project with parallel agent sessions. Working concurrently
on mostly different files is intentional. A dirty tree or another active session
is not by itself a reason to create a branch or worktree.

- Inspect the current directory, branch, status, and relevant diffs first.
- Coordinate ownership of files or individual hunks when work overlaps. Preserve
  other sessions' changes and stage only the work you own.
- Never switch the shared checkout's branch, stash/reset its changes, or move
  other sessions' work merely to make your task easier. If it is currently on a
  non-main branch, establish the existing task context before any Git mutation;
  do not automatically switch it back to main.
- Coordinate builds and app launches as well as source edits. Concurrent Xcode
  builds and multiple app instances can interfere even when source files differ.
- Use frequent, scoped green checkpoints when committing is authorized. Do not
  sweep unrelated changes into a checkpoint or push without authorization.

## Read the matching lifecycle skill before acting

| Situation | Canonical workflow |
| --- | --- |
| Start ordinary work in the shared checkout | `.claude/skills/new-feature/SKILL.md` |
| Finish that work on trunk | `.claude/skills/close-feature/SKILL.md` |
| Create or prepare an isolated branch/worktree | `.claude/skills/new-branch/SKILL.md` |
| Archive an integrated worktree branch | `.claude/skills/close-branch/SKILL.md` |
| Wrap a session, including verification and durable handoff | `.claude/skills/end-session/SKILL.md` |

The index is `.claude/skills/WORKFLOW.md`. Read the selected skill completely,
including its prerequisites, verification gates, and recovery steps. Claude
slash-command syntax need not be available in Codex: execute the documented
workflow with Codex tools, respecting user authorization and tool constraints.
Reading a skill does not itself authorize a merge, push, deletion, or branch
switch. Resolve routes from current Git/worktree state, not stale task metadata.

## Isolation is an exception with a complete lifecycle

Use an isolated environment when the user requests it, two environments must
remain live independently, overlapping work would otherwise clobber the shared
checkout, a multi-day task requires a separately shippable main, or an experiment
needs isolation. Explain the concrete reason. Parallel agents working on separate
files do not automatically meet that threshold.

Before creating a worktree, read both `new-branch` and `close-branch`. Follow the
setup skill rather than handing the user a bare checkout: pinned Python and
verified extras, frontend dependencies/build, shared trial-data links, desktop
resource links, bundle-aware sidecar copy with `ditto`, build-info generation
before first Xcode open, smoke checks, setup sentinel, and branch tracking.
Consult the skill's current details instead of duplicating its commands here.

At completion, verify/document the branch and integrate into the intended base
under the authorized workflow. Then follow `close-branch`: its actual steps
require merge verification before archival, check uncommitted work and the
`end-session` sign-off, preserve the local directory with an archive marker,
and update `docs/BRANCHES.md`. Do not assume its shorthand description performs
the merge. Resolve actual worktree paths from Git and the branch registry;
Codex-managed paths need not match the skill's example directory names.

For Swift changes, use `desktop/scripts/test-swift.sh` for the authoritative
local suite verdict. A compiler warning mentioning "exit code 0" is not a build
or test verdict. Follow each lifecycle skill's remaining checks for the scope.
