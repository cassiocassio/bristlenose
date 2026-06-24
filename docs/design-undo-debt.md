# Away with Undo Debt

_A running register of desktop actions that mutate state and **should** be undoable —
and which of them already are. The goal, in one line: **nothing confirms, everything
⌘Z's.** Append to the register as undo gaps surface; the systematic pass is tracked in
the private planning backlog._

Surfaced 23 Jun 2026 during folder-delete QA (the AppKit context menu): folder Delete
is immediate + irreversible, while project Remove is toast-undoable — a half-undo-story
that made the gap obvious.

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

**"Undo debt"** = the set of mutating actions not yet wired into that single ⌘Z story.

## The mechanism (one decision, then it's mechanical)

Target: one `NSUndoManager` on the window / responder chain; every `ProjectIndex`
mutation registers its inverse, so ⌘Z (and the Edit menu) restore it. The existing
project-remove **toast retires into it**.

**Open scope call (the user's):** bite off the `NSUndoManager` infrastructure pre-TF
(unifies undo, but it's real work) vs. match the toast for the few cases now and do the
migration as one post-TF pass. A *half* undo-story (toast here, nothing there, ⌘Z
nowhere) is worse than either pure option — so the choice is "do it right now" or "stay
fully toast-consistent until the migration," not a mix.

## Register

Sidebar / `ProjectIndex` mutations (desktop chrome). Append as new ones surface.

| Action | Mutates | Undoable today | ⌘Z should restore | Notes |
|---|---|---|---|---|
| **Delete folder** | folder removed; contained projects orphaned to root (`folderId = nil`) | ❌ none (immediate) | the folder + each project's prior `folderId` | the trigger for this doc; non-destructive but silently scatters an organised folder |
| **Remove project from sidebar** | project removed from sidebar (on-disk folder untouched) | ⚠️ 8 s toast | the project row | migrate the toast → ⌘Z |
| **Move project** (to folder / to root) | project `folderId` | ❌ none | prior `folderId` | |
| **Rename** project / folder | `name` | ❌ field-local only (while the NSTextField edits) | prior name | the *committed* rename should ⌘Z, not just the edit-in-progress |
| **Choose Icon** (set / clear) | project `icon` | ❌ none | prior icon | |
| **Reorder** project / folder (drag) | `position` | ❌ none | prior order | |
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
