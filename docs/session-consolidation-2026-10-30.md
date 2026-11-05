# Session consolidation — 30 October 2026

This is the pickup map for Claude and Codex after the reliability and repository
closeout work. It records where each known session ended, what reached local
`main`, what remains parked, and what must not be mistaken for unfinished merge
work. `docs/private/100days.md` remains the authority for future priorities.

## Final repository state

- Canonical checkout: `/Users/cassio/Code/bristlenose`
- Branch and tip: clean local `main` at `d20eb11bb`
- Remote state: 127 commits ahead of `origin/main`; no push, tag or release
- Registered worktrees: canonical `main`, plus Claude's scratch worktree on
  `reliability/ruling-4-sent-register`
- Deliberately parked branch: `codex/study-access-poc` at `e1f73c713`
- Retired: the integration worktree, `codex/signals-lens`, and eight other
  Codex branches already fully merged into `main`

The full consolidation tests were green before the final documentation-only
commit:

- Python: 9,013 passed, 8 skipped, 133 deselected, 6 expected failures
- Native Swift: 2,851 passed, 0 failed
- Whole-repo Ruff, locale-key checks, mockup-register check and diff whitespace
  check passed

## Reliability work led by this Codex session

### Ruling #193 — truthful MCP name-sharing message

The CLI now describes the current policy accurately: connected agents may see
participant names; quote text remains verbatim and may contain other names; the
printed credential also opens the report API. The owner deferred a new visible
CLI/per-study anonymity control. The existing app-wide environment setting and
per-study server setting remain the available controls. Long-term CLI parity is
in `100days`.

### Ruling #92 — first-load budget and held browser fixes

Sessions navigation/grid code now follows the later lens-loading pattern: it is
loaded when needed and preloaded after the main report becomes usable. Sidebar
visibility and width state are preserved. The four held fixes landed with the
budget still at 222 kB: refreshed participant/session names, correct playback
availability, and refusal of disabled codebook tags. The broader lens-consistency
audit produced future checks in `100days`; no speculative lens framework was
introduced.

### Ruling #179 / R114 — synced studies on more than one Mac

The selected minimum delivery is on `main`:

1. Automatic crash recovery is machine- and run-owned. Foreign, legacy,
   malformed or unverifiable unfinished work is preserved rather than restored
   over or deleted.
2. Fresh server/importer/job/analysis startup is refused before ordinary writers
   open when unfinished ownership is foreign or cannot be verified.
3. The approved native experience uses existing project-row status, diagnostic
   popover and unavailable-pane patterns. It says “Started on another Mac” or
   “Activity not confirmed”, includes the friendly Mac name/time when available,
   and offers a non-writing Retry check.

The optional immutable reader, duplication escape, automatic handover, editing
re-entry, merge and real cloud-project architecture are deferred. The current
product cannot view or edit that protected study on the second Mac. The larger
prototype is evidence for future work, not partially shipping code.

Primary records:

- `docs/design-study-recovery-guard.md`
- `docs/design-multi-mac-study.md`
- `docs/design-study-read-only.md`
- `docs/design-study-read-only-plan.md`
- `docs/design-study-read-only-writers.md`
- registered `docs/mockups/multi-mac-*.html`

## Other work integrated during the closeout

- Signals, snapshots, evidence assertions and their ordered migrations are on
  `main`; the old `codex/signals-lens` branch had no unique commits left.
- Sidebar Finder drag/drop, sidebar status retention, error gallery, appearance
  work and their integration repairs are on `main`.
- Zoom list windows now add days in UTC, so DST transitions cannot make a chunk
  exceed Zoom's 30-inclusive-date limit (`0b7eb11d5`).
- Startup-probe tests now wait for actual probe completion and prove the
  generation guard. The successful-process fixture uses `/usr/bin/true`; result
  mapping remains separately tested (`0b7eb11d5`).
- The multi-Mac design/mockup bundle is preserved in the tracked tree with
  explicit implemented/proposed/parked lifecycle labels (`c84c26606`).
- Consolidation handoffs were committed in `32cc65d0b` and `d20eb11bb`.

## Reports from the other sessions

### Claude organising session `a9fcb7`

Reported no owned edits or commits. Its work was read-only inspection and focused
Signals/machine-identity/elaboration tests (62 passed). At the owner's request it
removed three untracked root strays: `the`, `with` and `uv.lock`. Those were not
feature files and were not part of the preservation manifest.

### Claude Reliability session `e070a8`

Reported no uncommitted work: its reliability work was already on `main`, and
its scratch worktree and `r105` branch had been removed.

### Claude Release-readiness session `20b168`

Reported branch cleanup only; it did not leave checkout edits.

### Claude Teams/Meet/Zoom/Miro/Figma session `a5424c`

Reported no local changes. Its remaining items require owner/product or live
service work and must be taken from the relevant design records/`100days`, not
treated as an unmerged branch.

### Claude Trust-factors session `c72feb`

Its transcript reported 13 trust fixes committed and no outstanding local edits.
Apple Mail MCP work mentioned beside it belongs to a different repository.

### Codex toolbar dark-mode session

It tried a per-window AppKit appearance synchronizer, then withdrew it after
finding Bristlenose's declared `NSApp.appearance` seam. No toolbar change was
committed. Its final withdrawn file bytes are preserved under
`/Users/cassio/.codex/preservation/bristlenose-final-consolidation-2026-10-30/late-withdrawn-toolbar-state`.
The session also corrected the reusable theming skill outside this repository.

That session parked three unique groups in named Git stashes:

- QA fixtures and Playwright specs
- research and design drafts
- generated transcript-copy and report output

Do not apply or drop these stashes automatically. Their bytes also exist in the
verified external preservation copy.

### Codex workflow-visualisation session

It reported no repository writes. Its exploratory HTML work remains outside the
repository under the Codex visualisations directory; it is not a branch waiting
to merge.

## Preservation and cleanup evidence

The former canonical dirty tree had 105 classified paths. Every path was matched
by content and mode to the private snapshot before cleanup. The three private
preservation trees were copied and compared byte-for-byte outside the repository:

`/Users/cassio/.codex/preservation/bristlenose-final-consolidation-2026-10-30`

After another session parked several groups, 58 visible paths remained. The
explicit cleanup restored 42 named tracked paths and removed 16 named,
non-ignored untracked files. It did not use `git clean` or a hard reset. Ignored
private records, including `docs/private/100days.md`, remain in the canonical
checkout.

Two stale app attachments named `study-access-poc` and
`study-recovery-guard` still appear in this chat. Their directories are already
unregistered and are not Git worktrees. The app archive tool could not verify
this chat's former primary checkout, so the directories were left intact rather
than deleted outside the safeguard. Their meaningful contents are preserved.

## Safe pickup rules

1. Start in `/Users/cassio/Code/bristlenose` on `main`; inspect status before
   editing.
2. Treat `docs/private/100days.md` as the future-work source of truth.
3. Do not continue `codex/study-access-poc` by default. Start only a bounded,
   owner-approved future slice and retain its default-off boundary.
4. Do not retire Claude's `reliability/ruling-4-sent-register` worktree until its
   owner confirms it is idle.
5. Do not apply/drop the three new parking stashes merely to make the stash list
   tidy.
6. Do not push, tag or release local `main` without explicit owner direction.


## Root CLAUDE.md account (moved verbatim 5 Nov 2026)

This was the "Codex consolidation complete" block in the root `CLAUDE.md` § Session-end housekeeping. The standing line "No push, tag, release or public changelog update is authorised" stays in the root.

**30 Oct Codex consolidation complete:** the canonical checkout
`/Users/cassio/Code/bristlenose` is clean on local `main`. It contains
`0b7eb11d5` (Zoom UTC/DST range fix
and deterministic startup-probe completion verification) and `c84c26606`
(parked multi-Mac designs/mockups and trued register). Full Python gate on the
resulting tree: **9,013 passed, 8 skipped, 133 deselected, 6 expected failures**;
full native gate: **2,851 passed, 0 failed**. Mockup register, whole-repo Ruff,
locale-key and staged-diff checks pass. `frontend/node_modules` is a generated
untracked symlink and must not be committed.

The canonical checkout's former 105 dirty/untracked
paths were classified and checksum/mode-verified against the private snapshot;
all three private preservation trees were also copied byte-for-byte outside the
repository to
`/Users/cassio/.codex/preservation/bristlenose-final-consolidation-2026-10-30`.
Claude's organising session reports no owned edits or commits; it deliberately
removed only the untracked root debris `the`, `with` and `uv.lock`. The explicit
cleanup restored 42 tracked paths and removed 16 preserved untracked files;
ignored private records remain. The redundant integration worktree, spent
Signals branch and eight other fully merged Codex branches were retired.

The larger reader/handover implementation remains intentionally **unmerged** at
`codex/study-access-poc` (`e1f73c7136`). Its design/mockup records are now staged
as parked supporting material; its full source and bundle are preserved in the
private recovery archive and the external preservation copy. It is the deferred
study reader prototype, not the About-page animation work. The Claude scratch
worktree on `reliability/ruling-4-sent-register` is clean and still potentially
Claude-owned; do not retire it without establishing that it is idle. Two stale
app attachments (`study-access-poc`, `study-recovery-guard`) are already
unregistered directories, not Git worktrees; app archival could not verify this
chat's old primary checkout, so their directories were left intact. No push,
tag, release or public changelog update is authorised.

The complete cross-session map and preservation/cleanup account is
[`docs/session-consolidation-2026-10-30.md`](docs/session-consolidation-2026-10-30.md).
Read it before resuming any branch or stash named there.
