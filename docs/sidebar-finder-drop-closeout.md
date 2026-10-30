# Sidebar Finder drop close-out — 30 October 2026

Status: integrated into local main; sidebar work complete and archived at the
owner's request. This is a scoped close-out, not a release-wide green sign-off.
No push or release.

## Integration and behavior

Sidebar implementation: `56b46608a`, included in main by `5a7830935`.
Canonical filesystem-location test correction: `c92bba10a`.
Python routing-contract correction: `5120928de`.

BN projects open their existing analysis. Known projects select their existing
entry; unknown projects can establish an empty New Project placeholder. Wrapper
folders register contained projects and ignore loose sibling media. Populated
projects refuse other BN projects. Irrelevant or indeterminate folders cannot
establish a project or start analysis. Selected sidebar-folder panes target that
folder. Structural and concurrent-copy refusals do not produce toasts.

Hover never lists directories. Discovery runs off-main with bounds of eight
levels and 1,024 entries; source acceptance respects the pipeline scan depth.
Dataless items are refused before listing; no cloud download/wait UI was added.
Existing identity, copy rollback, disk-space and real filesystem error handling
remain. Known or moved projects are not rescanned merely to erase foreign-run
status. The 29 October supersession note in design-sidebar-drop-behaviour.md is
the current behavior contract; older V1 tables remain historical.

## Evidence and limits

- Owner reported the launched QA build working. No new macOS-15/26 visual matrix
  is claimed.
- Recovery's authoritative final combined Swift gate: 2,846 passed, zero failed,
  exit 0, on the source/test tree through c92bba10a.
  Receipt: /private/tmp/bn-recovery-main-final-native-canonical-runner.log.
- Recovery selected Python gate: 343 passed, two expected failures.
  Receipt: /private/tmp/bn-recovery-main-final-python.log.
- Whole-repository Ruff passed on that pinned tree.
  Receipt: /private/tmp/bn-recovery-main-whole-ruff.log.
- Sidebar Python routing, extension, localization and scan contracts: 44 passed
  after 5120928de; scoped Ruff and whitespace checks passed.
- The additional full free Python run reported 19 failed, 8,953 passed, 46
  skipped, 133 deselected, six expected failures and three errors in 753.36s.
  Receipt: /private/tmp/bn-sidebar-close-full-pytest-unrestricted.log.
  Two failures were the sidebar source-contract parsers corrected in 5120928de;
  the remaining 17 failures and three errors were handed to recovery for triage.
  They include startup/ownership fixtures, missing built SPA assets, Signals
  accessibility/schema/style contracts and generated timeline CSS. No exclusions
  or production safety relaxations were used to manufacture green.
- That broad run began at feb46d9b2 and main moved to eecfab8de during it
  (error-screen integration). It is not an exact-tree release receipt.
  The first sandboxed attempt aborted importing MLX; its log is retained at
  /private/tmp/bn-sidebar-close-full-pytest.log.

End-session's normal green-before-documenting gate was not met by the broad
Python suite. The owner subsequently explicitly requested documentation,
committing, closure and archival. This record preserves that exception;
no positive all-green last-end-session sentinel is manufactured.

## Archive and follow-up ownership

The sidebar worktree is
/Users/cassio/.codex/worktrees/integration-sidebar-drag/bristlenose.
Its directory, ignored runtime/build files and local branch reference are kept.
Only its Git registration is retired after verifying it is clean and merged.
The clean main checkout is used for archive administration under the owner's
cleanup authorization; the historical dirty shared Signals checkout is untouched.

Recovery owns the remaining broad-suite repairs and the final main/shared-checkout
consolidation. Existing unrelated QA backlog entries remain open. No additional
100days sprint item is marked complete by this close-out.

Codex workflow guidance is in root AGENTS.md: shared checkout by default, and BN's
new-branch/close-branch setup and archival workflows for actual isolation.
