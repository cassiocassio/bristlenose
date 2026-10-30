---
status: pending
last-trued: 2026-10-26
trued-against: read-only source audit of project menus, window commands, copy machinery and identity; no duplication implementation
---

# Duplicate a study — native menu fit and staged feasibility

Owner request, 26 Oct 2026: investigate the existing context menu and all its
variations, reuse its machinery, report a plan; this is substantial and need
not be built all at once. One read-only audit agent (`duplicate_menu_audit`)
traced the native menu/copy paths; Codex parent reviewed the relationship to
read-only v1 and the existing copy contract. No production changes or Swift
build are part of this investigation.

## Preserve the existing product contract

Canonical semantics remain [project identity §9](design-project-identity.md#9-a-copy-is-an-independent-duplicate):
an independent study carrying recordings, analysis, curation, transcripts,
caches and history; a new identity, with `copied_from` provenance; no automatic
merge later; no separate “clean copy” mode (Re-analyse the copy instead).
The decided design expects Finder duplication to work and treats an in-app
command as convenience. That is intended behaviour, not evidence that every
active/synced folder copy is consistent today. WAL alone does not establish
an atomic copy of a DB/WAL/assets bundle. The R114 recovery guard intentionally
leaves unknown attempts untouched; it does not make copying them safe.

Two sources must not be silently conflated:

| Operation | Meaning | Additional requirement |
|---|---|---|
| Ordinary duplicate | An independent copy of the current study at a coherent instant | Quiesce writers or capture a coherent whole-study source; own the media and remint the destination explicitly |
| Escape from read-only | An independent editable copy of the earlier report currently visible | Pin that report's DB, transcripts, registry, recording references and necessary assets together; copying the current live folder is not the same operation |

Do not call the second route an already-working consequence of the first.
A database-only snapshot is not automatically a whole-study duplicate.

## Native surface and targeting

`ProjectSidebarOutline.menuNeedsUpdate` builds an AppKit `NSMenu` from the
**clicked node**, not necessarily the selected or displayed study. Its project,
folder, lens and group-header branches are different. Context-menu items are
hidden when inapplicable; the Project menu-bar counterpart remains visible and
disabled. The new operation should have one capability decision shared by the
presenters and rechecked by the command handler before executing.

Proposed placement: a **single-study right-click item** in the project
housekeeping group, near Rename, with a Project menu-bar twin. No new titlebar
ellipsis, report action or popover button. “Duplicate Study…” is draft English;
the ellipsis is appropriate if a name/destination panel follows. Do not allocate
a shortcut without checking the existing command map. The native menu's final
ordering/label is a review decision, not fixed by the earlier HTML sketch.

Context targeting should remain clicked-study-only in the first implementation,
including when that row belongs to a larger selection. The removal action's
special selected-set behaviour is not a general menu convention. The menu-bar
twin should require one selected study and the correct front window; no implicit
batch duplicates. Capture the target ID for the operation, so later selection
changes cannot retarget an async copy. Use the scene-focused native
`WindowCommand` routing; duplication is not a webview bridge event.

The old v1 mock's titlebar ellipsis and immediate switch to an editable copy
are **superseded sketches**, not a native placement specification or evidence of
a working copy workflow. Popover duplication guidance is rejected by the owner, even after a safe copy
implementation: the escape is exceptional and deliberately initiated.

## Observed menu variations — source audit

These describe current code, not the proposed Duplicate eligibility.

| Surface/condition | Existing behaviour | Duplicate fit |
|---|---|---|
| AppKit project row, `ProjectSidebarOutline.swift:2298` | Lifecycle group first: Stop when stoppable; Cancel Copy only during this project's `.copying`; Diagnostics for failure/partial; Analyse/Re-analyse via their work predicates; Locate for missing/access problems | New single-study operation in housekeeping near Rename, not in run/recovery or Agent Access groups |
| Ordinary project housekeeping | Open in New Window has its own group; then Show in Finder when revealable, Rename, Choose Icon, Move to if folders exist | Preserve grouping; reuse existing operation presentation rather than adding an ellipsis |
| Move to submenu | No Folder plus folders; current location dimmed | Duplication is not this sidebar-only reorganisation |
| Agent Access | Separate group; On/Off verb swap, only if mounted and policy permits | New study starts without inheriting an access grant or token |
| Running/queued project | Remove hidden; run verbs vary independently from availability | Completed/quiesced-source phase refuses active work; recheck when starting, not only when drawing menu |
| Copying/cancelling | Cancel Copy offered only for `.copying`; cancelling has no second cancel | Whole-study operation must own its progress/cancel state, not masquerade as Add Files |
| Missing/unreadable/unavailable study | Locate and reveal policy use availability separate from pipeline state | No blind path-exists eligibility; no unsafe copy fallback |
| Project clicked while another study is displayed | Clicked node supplies target | Explicit ID passed through; do not change selection to route it |
| Clicked member of a multi-selection | Builder is still per clicked row; Remove deliberately expands to selected set | Proposed Duplicate stays clicked-study-only. This is a new policy to test, not a bulk-copy precedent |
| Unselected clicked project during multi-selection | Other single-row actions target that clicked node | Same explicit target; menu-bar sole-selection rule is a different input |
| Folder row, `:2414` | Open All in New Windows only for >1 study, Rename, Delete; Archive withdrawn | No study Duplicate item; no folder/bulk duplicate in first scope |
| Enabled lens row, `:2280` | Only Open in New Window | No Duplicate item |
| Disabled lens, group header, blank area | No applicable menu | No Duplicate item |
| Menu-bar Project, `MenuCommands.swift:1237` | Folder selection has folder menu; window commands dim with no valid front window; single-study actions dim on no/multi selection | Visible-but-disabled twin, one selected study, same operation capability policy |
| SwiftUI fallback sidebar | Separate project and folder context menus at `ContentView.swift:3678` / `:3407`; selected by `BristlenoseFlags.appKitSidebar` at `:3124` / `:3143` | Update both supported presenters, or explicitly retire/gate fallback; do not accidentally implement only the shipping AppKit path |

**Command seam:** add a native case such as `.duplicateProject` to
`WindowCommandFocus.swift:33`; menu-bar dispatch goes through the focused
`WindowCommandSink` (`:128`) and `ContentView.perform` (`:1787`). AppKit adds
an `onDuplicate(UUID)` callback alongside the row's existing explicit-ID
callbacks (`ProjectSidebarOutline.swift:86–112`). Both call the same
window-owned coordinator. The context-menu builder itself starts at `:2251`.
`desktop/scripts/check-menu-routing.sh` is the existing seam check. Current
removal's selected-set exception is at `ContentView.swift:2116–2130`.

**Location and grants:** `ContentView.createFolderProjectViaSavePanel` (`:2437`)
provides the native panel/host appearance/window-modal pattern;
`ProjectFolderDefaults.swift` owns configured, remembered and Documents defaults.
`ProjectBookmarkLease.swift:27–94` and `ProjectIndex.leaseURL` (`:1549`) provide
the source's live security scope. Do not reconstruct a source URL from display
text or create a competing destination-default mechanism.

**Publication trap:** `ProjectIndex.addProject` (`:515`) immediately syncs
watchers. The existing import path creates the row before copy and starts
analysis afterward (`ContentView.swift:2480–2520`). A duplicate must not expose
its half-copied DB or pay to analyse an already usable report. Stage the full
result before registration, or explicitly design a nonservable copying row;
this is an implementation choice to prove in the spike.

**Undo boundary:** the removal undo store restores sidebar rows and leaves disk
alone (`ProjectIndex.swift:590–650`, `ContentView.swift:2079`). It is not undo
for deleting a new study directory. Initial scope can have Cancel/rollback
while copying and ordinary Remove from Sidebar afterward; do not promise that
⌘Z reverses the on-disk duplicate without a separate ownership/deletion design.

## Staged recommendation — each stage can stop

| Stage | Deliverable | Stop line |
|---|---|---|
| Read-only v1 independently | Real protection and ordinary report browsing; factual sidebar/popover wording | No Duplicate command, dead menu stub or unsupported “duplicate in Finder” escape instructions required to ship it |
| Copy contract and feasibility spike | Pure eligibility/target policy, source/destination manifest, consistency/media/identity/cancel plan; proving fixtures | No menu item until a complete copy can be produced without touching the source |
| Ordinary completed-study duplication | One clicked/sole-selected, available, quiesced study; independent media and curation; explicit destination identity; existing native progress/error/cancel conventions | Refuse unsupported active/unavailable/partial cases. Do not auto-run analysis. No bulk, merge, clean-copy variant or read-only escape claim |
| Read-only escape | Build the destination from the pinned report actually being browsed; preserve drafts and media ownership, explain that copies diverge | Only then add contextual guidance about continuing on a duplicate. Still no takeover or later reconciliation promise |

These stages are proposals, not implementation authorisation. The copy spike may
show that even the ordinary completed-study stage needs more source-quiescence
work than is worth doing now. Keep the read-only safety work independent.

## Reuse boundary

`CopyMachinery` is an import engine: it filters supported media/transcript
extensions and copies them into an existing study. Passing a whole study to
that API would omit analysis/curation and does not create an independent study.
Across the existing copy flow, useful mechanisms include disk-space checks, security-scope lifetimes,
per-file staging, progress, cancellation, rollback, dataless-file refusal and
normalised errors. Reuse or extract narrow mechanisms where appropriate; do
not turn study duplication into an import job or inherit import auto-analysis.

Existing `ProjectIndex.captureStudyID`/`StudyMarker.remint` and importer copy
recognition help with identity, but a deliberate duplicate should create its
new identity in destination staging rather than rely on arrival heuristics
that may instead treat a missing original as a move. Preserve original grants;
do not copy per-study agent credentials/access as though the new study had
already been authorised. Never remint or tidy the protected source.

Do not add a cloud waiting state or download-management surface. Existing
[cloud-file policy](design-cloud-files.md) and copy-error machinery apply.
A full-media copy may be large, on another volume, or contain dataless files.
An APFS fast path is an optimisation, not a cross-volume/iCloud guarantee.

## Proof before exposing a command

- Menu shape for project states and clicked-vs-selected targets, including
  selected/unselected right-click during multi-selection, and menu-bar
  no/sole/multi selection and no/key/utility-window focus.
- Eligibility rechecked when the operation actually starts; no source writes
  or stale-state copy if analysis/copy jobs begin after menu construction.
- All curation and stable recording/session identity retained, fresh study
  identity/provenance, original unchanged, separate agent grant; no new paid work.
- Destination cannot equal, overlap or recursively contain the source; no
  overwrite. Symlinks, aliases, external media and large/cross-volume sources
  have explicit ownership and resolution rules.
- Cancel/failure removes only newly created destination items, never source or
  pre-existing destination files; no usable sidebar row published too early.
- Reopen the result through the real importer/server, read every lens and
  confirm the original remains valid independently. Include WAL and assets,
  not just “the folder exists”.
- For read-only escape, verify the copy matches the displayed generation and
  that deleting/moving the original does not break promised independent media.
  Draft preservation remains mandatory; do not silently omit drafts.

## Evidence and review disposition

Read-only audit agent: `duplicate_menu_audit`, 26 Oct 2026, completed; no edits,
no tests. Parent reviewed the source/contract split and wrote this plan. No
production code or menu item changed, no Swift build/test claim. Existing test
families to extend: `CopyMachineryTests`, `CopyMachineryStagingTests`,
`CopyMachineryDatalessTests`, `CopyErrorSurfacingTests`,
`PipelineRunnerCopyTests`, `StudyMarkerTests`, focused-window/command routing
and context-menu shape/selection contracts. Existing cancellation is between
files; do not promise instant cancellation during a large synchronous file copy.

Recommendation: stop this task at the plan. Read-only enforcement stays a
separate workstream. The completed-source copy spike and command can be a later
feature; the frozen-report escape is a further extension, not v1's prerequisite.
The earlier mock's working one-click-copy transition is superseded by this plan.

Owner correction, 26 Oct: the titlebar ellipsis was invented and rejected. It
and the speculative menu/one-click duplicate transition have now been removed
from the v1 mock, together with premature popover duplication guidance.

## Owner ruling — exceptional escape, not handover workflow

26 Oct: forking to bypass read-only is a “get out of jail” choice for exceptional
circumstances. Do not make the warning popover a convenient invitation to keep
editing elsewhere. Keep it out of that popover entirely. A supported operation
would be deliberately found in the project context menu / Project menu, and
its own flow must explain that the studies diverge and cannot be merged by
Bristlenose. Do not promise that merging will eventually be available. This
supersedes earlier suggestions of contextual duplication guidance. The exact
choice/panel remains to be designed; this is not authority to build it now.


## Current implementation entry point — 27 Oct

See [owner read-only design](design-study-read-only.md) and
[implementation plan](design-study-read-only-plan.md) for the current sequential
v1 scope and POC-backed build sequence. This document retains its scenario or
deferred-operation role; it is not an alternative implementation specification.
