# Project identity icons (desktop)

Every project gets a distinctive identity icon in the sidebar. New projects are
**auto-assigned a random icon**, revealed once with a **split-flap** animation, so
users learn to recognise a project by its mark — not just its name.

## Why (the cognitive basis)

Recognition is far cheaper than recall: spotting "the orange diamond one" beats
re-reading a list of names (Nielsen's recognition-over-recall; the picture
superiority effect — images out-remember words). The icons earn their keep only
if they're *distinctive*, so assignment is **random rather than chosen**:
left to choose, people cluster (everyone picks the star), collapsing
distinctiveness (von Restorff). Random assignment spreads projects across the
visual space, and — crucially — the benefit is highest when user effort is
lowest, so it's a guaranteed default, not an opt-in nobody touches. The one-shot
flip is an *episodic anchor* (you watched it land) and makes the auto-assignment
legible ("the app chose one, on purpose"), not a silent accident.

## Assignment — `RandomProjectIcon.swift`

Pure, deterministic, unit-tested (`RandomProjectIconTests`):

- **Pool**: the existing manual picker set (`IconPickerPopover.palette`, 100
  curated SF Symbols), **minus `circle`** — `circle` is the reserved "no icon /
  un-iconed default" mark, so a randomised project is always visually distinct
  from an opted-out one. 99 drawable symbols.
- **Seeded** off the project name via a stable **FNV-1a** hash (NOT Swift's
  `Hashable`, which is per-process randomised) → a **SplitMix64**-seeded
  Fisher–Yates shuffle of the pool. Same name → same icon across machines /
  re-imports in the common case.
- **Collision-avoided**: walk the seeded order, take the first icon not already
  in the sidebar. No two projects share an icon until all 99 are used; the 100th
  is the first forced repeat (reshuffle for the next lap).
- Seeded-determinism and collision-avoidance are in tension (one is name-pure,
  the other set-dependent); the probe reconciles them — determinism holds unless
  two names collide on their first pick.

Wired at creation in `ProjectIndex.addProject` (reads the Appearance toggle; nil
= keep the default ring). Stored in the existing `Project.icon: String?`
(`projects.json`) — **no schema change**. A transient `pendingIconReveal: UUID?`
flags the just-created project for its one-shot reveal; the row consumes it.

## The reveal — split-flap

A decelerating flip through palette symbols, settling on the assigned one (the
train-departure-board idiom — reads as "deciding", calmer than a casino reel).
Two surfaces, kept in sync:

- **SwiftUI** `TumblingProjectIcon.swift` — used by `ProjectRow` (the default
  sidebar). Animates a value (`rotation3DEffect` / opacity) per step.
- **AppKit** `SidebarIconFlip.swift` — used by `ProjectSidebarOutline` (the
  source-list sidebar behind `BristlenoseFlags.appKitSidebar`). Core Animation
  `transform.rotation.x` on a **controller-owned overlay** added to the
  `outlineView`. The overlay (not a cell-level animation) is load-bearing: the
  sidebar `reloadData`s every progress tick during a run, which would destroy a
  cell animation — the overlay survives it. The real cell icon is hidden
  (`alphaValue = 0`, kept hidden across `reloadData` by `viewFor`) while the
  overlay plays.

**Cadence dials** (top of each animation loop): the per-step `interval` ramps
`0.10 → 0.30s` quadratically over ~12 steps (raise the floor for a slower start,
the ceiling for a longer tail). Final step gets a spring/longer ease as the
settle.

**Threading**: the flip is a `Task { @MainActor }` whose `await Task.sleep`
*yields* the main thread between steps; the actual rotation runs on the Core
Animation render server (separate process). The analysis run (`bristlenose run`)
is a separate OS process entirely. They interleave on the main thread without
blocking each other — the overlay-survives-reloadData design is what keeps the
flip and the run's per-tick refresh from clashing.

## Settings & accessibility

- **Appearance ▸ "Assign a random icon to new projects"** (`AppearanceSettingsView`,
  `@AppStorage(RandomProjectIcon.defaultsKey)`, default **on**). Off → new
  projects keep the plain ring and the user assigns via the picker.
- **Reduce Motion** (system) → the project still gets its random icon, just
  placed instantly with no flip. Independent of the off switch.

## Known follow-ups

- **i18n**: the Appearance toggle strings are English literals with a
  `TODO(i18n)` — they need `settings.appearance.randomIcons{Legend,Help}` across
  all 7 `common.json` before shipping.
- **AppKit overlay frame**: the overlay must read the icon's frame *after*
  layout — `maybeStartIconReveal` forces `outlineView.layoutSubtreeIfNeeded()`
  first, else the overlay is 0×0 (invisible: blank, then the icon pops in).
  Pivot/alignment of the AppKit flip are pixel-tunable in `SidebarIconFlip` /
  the overlay placement.

## Files

`RandomProjectIcon.swift` · `TumblingProjectIcon.swift` · `SidebarIconFlip.swift`
· `IconPickerPopover.swift` (the palette + default) · reveal wiring in
`ProjectIndex.swift` / `ProjectRow.swift` / `ProjectSidebarOutline.swift` ·
`AppearanceSettingsView.swift` · tests in `RandomProjectIconTests.swift`.
