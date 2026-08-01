---
status: partial
last-trued: 2026-07-28
trued-against: HEAD@main on 2026-07-28
---

# Away with Undo Debt

_A running register of desktop actions that mutate state and **should** be undoable —
and which of them already are. The goal, in one line: **nothing confirms, everything
⌘Z's.** Append to the register as undo gaps surface; the systematic pass is tracked in
the private planning backlog._

Surfaced 23 Jun 2026 during folder-delete QA (the AppKit context menu): folder Delete
is immediate + irreversible, while project Remove is toast-undoable — a half-undo-story
that made the gap obvious.

> **Scope note (28 Jul 2026).** This doc's register covers the *sidebar* actions
> (`ProjectIndex` / `projects.json`) and deliberately excludes the report's own
> domain. [`design-undo-catalog.md`](design-undo-catalog.md) is the companion that
> catalogues the excluded half — all five ownership domains, ~50 mutations, ten
> candidate history stacks, and the Swift↔Python boundary problems. It also flags
> **two unreconciled contradictions in this doc** that want settling before anyone
> builds: (1) §Mechanism names `NSUndoManager`, but the shipped `UndoableRemovalStore`
> explicitly rejected it; (2) §Corollaries bans undo toasts, but the one shipped undo
> affordance *is* a toast (and three other design docs propose more).

## Principle

Destructive and mutating actions should be **immediate + undoable**, not gated behind a
confirmation dialog. A dialog taxes *every* invocation to catch the rare misfire; undo
lets the action stay instant and just *reverses* the misfire. This is the native macOS
pattern, and it's on the project's no-confirm grain (memory
`feedback_dont_invent_confirm_steps` — "the user already chose; the action just happens").

Two corollaries:

- **No confirm dialogs** for reversible actions. Keep a dialog only where an action is
  genuinely irreversible *and* high-stakes — and prefer making it reversible first.
- **No undo toasts.** Toasts are banned (`feedback_toasts_are_morally_bankrupt`). The
  undo affordance is the standard responder-chain `NSUndoManager` → **⌘Z**, plus the
  Edit menu's "Undo &lt;action&gt;". Discoverable, no arbitrary time window, consistent
  app-wide, zero attention-theft.

  > **Contradicted by shipped behaviour (flagged 2026-07-28).** The one undo
  > affordance that exists **is** a toast — `RemoveToast.swift` +
  > `UndoableRemovalStore(undoWindow: 8)`. Three other design docs also propose
  > toast-based undo (`design-project-sidebar.md`, `design-sidebar-tag-assign.md`,
  > `design-quote-triage.md`). The posture is four-way inconsistent: banned here,
  > proposed in three docs, shipped in code. **This ban needs a carve-out or a
  > reversal before anyone builds** — as written it forbids what the app already
  > does. Resolve in one sweep, not per-doc.

**"Undo debt"** = the set of mutating actions not yet wired into that single ⌘Z story.

## The mechanism (one decision, then it's mechanical)

Target: one `NSUndoManager` on the window / responder chain; every `ProjectIndex`
mutation registers its inverse, so ⌘Z (and the Edit menu) restore it. The existing
project-remove **toast retires into it**.

> **Superseded by the implementation as of 2026-07-28 — plan preserved above.**
> `NSUndoManager` was **explicitly rejected** when removal-undo shipped. The sole
> repo-wide mention of it is the rejection itself, `UndoableRemovalStore.swift:23`:
> *"Wired via the Edit menu's `keyboardShortcut("z")` … **Not** via `NSUndoManager`
> — the SwiftUI menu interception is sufficient for the sidebar scope and avoids
> braiding removal-undo with whatever responder chain happens to hold focus."*
> That invariant lived only in a code comment; promoted here so a contributor
> reading the design doc doesn't reach for `NSUndoManager` and regress it. Any
> revival of the plan above must answer the focus-braiding objection first.

**Open scope call (the user's):** ~~bite off the `NSUndoManager` infrastructure pre-TF
vs. match the toast for the few cases now~~ — _restated 2026-07-28: that fork no longer
describes reality. The toast path **shipped**, and ⌘Z routing shipped **without**
`NSUndoManager`. The live question is now: retire the toast into a unified ⌘Z, or accept
toast-plus-⌘Z as the permanent shape? The full surface that decision must cover is
catalogued in [`design-undo-catalog.md`](design-undo-catalog.md)._ Original framing: A *half* undo-story (toast here, nothing there, ⌘Z
nowhere) is worse than either pure option — so the choice is "do it right now" or "stay
fully toast-consistent until the migration," not a mix.

## Register

Sidebar / `ProjectIndex` mutations (desktop chrome). Append as new ones surface.

| Action | Mutates | Undoable today | ⌘Z should restore | Notes |
|---|---|---|---|---|
| **Delete folder** | folder removed; contained projects orphaned to root (`folderId = nil`) | ❌ none (immediate) | the folder + each project's prior `folderId` | the trigger for this doc; non-destructive but silently scatters an organised folder |
| **Remove project from sidebar** | project removed from sidebar (on-disk folder untouched) | ✅ 8 s toast **and ⌘Z** | the project row | _Corrected 28 Jul 2026: ⌘Z already works here (`UndoRedoMenuContent` → `removalStore.undoLastRemoval()`); only the **toast retirement** is outstanding. The row read as "no ⌘Z yet"._ |
| **Move project** (to folder / to root) | project `folderId` — and, once reorder lands, `position` | ❌ none | prior `folderId` **and** prior `position` | a move that lands at a chosen index changes both fields; today `moveProject` sets only `folderId` and leaves `position` at its old in-folder value, so the inverse is currently under-specified in the same way the forward action is |
| **Rename** project / folder | `name` | ❌ field-local only (while the NSTextField edits) | prior name | the *committed* rename should ⌘Z, not just the edit-in-progress |
| **Choose Icon** (set / clear) | project `icon` | ❌ none | prior icon | |
| **Reorder** project / folder (drag) | `position` across the affected scope (root, or one folder's contents) | ❌ none — **and not yet reachable**: folders return `nil` from `pasteboardWriterForItem` (`ProjectSidebarOutline.swift:981`) and the resolved `toIndex` is computed then discarded (`DropRouting.swift:14`) | the prior `position` of **every** item in that scope — a reorder renumbers the whole sequence, so the inverse is a snapshot of the order, not one field | **A pre-condition on the reorder work, not existing debt.** Zero-debt today only because the gesture is inert; it becomes live debt the moment drag-reorder ships. Two invariants for whoever builds it: a multi-select drag is **one** undo step, not N; and the snapshot must cover the source scope as well as the target when a drag crosses a folder boundary. |
| **New Folder** | folder added | ❌ none | remove the folder | low-stakes (empty), included for completeness |

### Out of register (separate domains / genuinely tricky)

- **Project create** (drag-import / + New Project) and **add files to project** (drop)
  touch disk and may start analysis — "undo" would mean deleting copied files or
  cancelling a run. Treat separately: the practical undo is "Remove from Sidebar," not
  a true inverse.
- **React report edits** (hide / edit quote, edit heading, tag ops) live in the SPA —
  the report's **own** undo domain, not this `NSUndoManager`. Don't conflate the two.

## Sweep

A one-pass audit — grep every `ProjectIndex` / state mutation, classify undo-able-ness,
wire the inverses, retire the toast — is tracked in the private planning backlog (the
undo sweep + audit item). This register is the **input list** for that pass; keep
appending here as actions surface so the sweep starts from a real inventory, not a blank
grep.
