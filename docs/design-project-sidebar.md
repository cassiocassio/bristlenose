---
status: partial
last-trued: 2026-06-21
trued-against: HEAD@main on 2026-06-21
---

> **Trued 2026-06-15 (`per-project-activity` @ `518e6d3`):** the per-project run glance **moved onto the
> sidebar row** (spinner + hover-× Stop, `ProjectRowActivityIndicator.swift`; clickable failure glyph →
> diagnostic popover). The toolbar pill (`PipelineActivityItem.swift`) was **deleted** (commit
> `8ffa470`). Two 2026-04-23 "Superseded" banners below claimed the spinner/badges were *not* on the
> row and lived in the toolbar pill — that is **now reversed**: the row-spinner vision they dismissed is
> what shipped. The banners are re-flipped inline. See `docs/design-sidebar-activity-indicators.md`.

> **Trued 2026-06-18 (`main` @ `bcb4187`, post `progress-text-surfacing` merge):** the running row's
> **subtitle** now shows the live progress ladder (stage · N of M · ETA, e.g. "Transcribing · 2 of 3 ·
> <1 min left"), not just a trailing spinner; drag-create **adopts the folder / first-item name with no
> inline rename** ("+ New Project" still prompts); and the title-line **session count refreshes on run
> completion** (was stale until relaunch). New "Row anatomy (two-line)" section below is the doc home for
> all three. Progress-ladder + ring details: `docs/design-sidebar-activity-indicators.md`.

> **Trued 2026-06-21 (`main`, post `project-status-line` + `warm-sidecar-pool`):** the 18 Jun truing
> above predated two same-week landings (its `bcb4187` SHA is an ancestor of the rewrite). (1) The row's
> subtitle precedence chain was lifted out of the view into a pure, unit-tested `ProjectSubtitle.resolve`
> (`ProjectSubtitle.swift` + `ProjectSubtitleTests.swift`), and **copy progress moved onto the row** —
> `"Copying · N%"` + determinate ring + hover-cancel + a "Cancel copy" context-menu item (the standalone
> `CopyProgressPill` was deleted). See "Row anatomy" below + `design-desktop-project-status.md` §4 (the
> placement axis). (2) Switching *back* to the previous project now re-points to a parked warm sidecar
> instead of teardown+restart — "Click behaviour" updated; see `design-desktop-switch-performance.md`.

> **Truing status:** Trued. Phases 1–3 shipped; remaining drift carries inline banners. Project-menu and context-menu ASCII art trued (phantom Add Interviews / Analyse / Get Info removed). Drop matrix duplicate row clarified. Phase 2 "not shipped" list updated with strikethrough on items that did ship. Pipeline-state × run-trigger matrix at end of doc.

## Changelog

- _2026-06-22_ — added a **"Substrate + ownership"** banner after §Context delineating this doc (sidebar behaviour/content) from the two newer docs that now own slices of the surface: `design-desktop-nav-toolbar-rearrangement.md` (the relocated lens rail) and `design-desktop-sidebar-appkit.md` (the SwiftUI `List` → AppKit `NSOutlineView` migration, alpha default at cutover). Cross-ref'd §"Row anatomy" to the appkit §2.4 cell port. **No behaviour claims changed** — the SwiftUI content here is accurate for the flag-OFF default build; the banner closes the cross-doc drift risk (those mechanics are deleted at cutover). Anchors: `ProjectSidebarOutline.swift`, `OutlineNode.swift`, `LensRail.swift`, `BristlenoseFlags.swift`.
- _2026-06-21_ — re-trued against `main` after the `project-status-line` + `warm-sidecar-pool` merges, which landed the day *after* the 18 Jun truing (its front-matter SHA `bcb4187` is an ancestor of the rewrite — false-fresh). Added copy-on-row to §"Row anatomy" (`"Copying · N%"` ring + hover-cancel + context-menu; standalone `CopyProgressPill` deleted); flipped §"Click behaviour" — switch-back now re-points to a parked warm sidecar (Phase A2). Anchors: `ProjectSubtitle.swift`, `ProjectRow.swift`, `ParkedSidecar.swift`, `ServeManager.swift`; commits `0842081`, `4313bff`, `beaac38`.
- _2026-06-18_ — Trued against `main` @ `bcb4187` after the `progress-text-surfacing` merge. Running-row subtitle now shows the live progress ladder via `RunProgressSubtitle` (states table L81 updated); drag-create adopts the folder/first-item name with no inline rename (drop matrix + Phase 2 list updated, commit `09f8625`); added a "Row anatomy (two-line)" section documenting the title-line session count + its refresh-on-completion (commit `1e1d608`) and the subtitle progress ladder, cross-referencing `desktop/CLAUDE.md` + `bristlenose/server/CLAUDE.md` for the WAL-checkpoint mechanics rather than duplicating them.
- _2026-05-01_ — §"Empty state" status banner flipped from `partial` to `shipped` after `WelcomeView` landed on `first-run` (commit `816ab65`). Drop-target affordance and New Project CTA now ship via the welcome detail-pane (not via the sidebar `ContentUnavailableView` shape originally designed in this doc); see `WelcomeView.swift` and `design-desktop-app.md` §"Loading and transition states" empty-state row. The four downstream "ContentUnavailableView empty state" mentions in this doc were not rewritten — the original sidebar-level vision is preserved as planning history; the actual empty surface lives in the detail pane. TipKit first-project hint remains parked.
- _2026-04-24 (evening)_ — Sidebar row subtitle now switches "Analysing…" → "Stopping…" the moment the user clicks Stop on the toolbar pill, in lockstep with the pill itself. `ProjectRow` takes `liveData: PipelineLiveData` and reads `progress[id].isStopping` (commit `da5cc45`). See `design-subprocess-lifecycle.md` §Cancellation for the full chain.
- _2026-04-24_ — Tier 1 truing follow-up (post `design-doc-review` audit): Project menu ASCII art corrected to match `MenuCommands.swift:317-415` shipped reality (phantom `Add Interviews… ⇧⌘I`, `Analyse… ⇧⌘A`, `Get Info ⌘I` removed; Locate, Move to submenu, ⌘⌫ shortcut added); right-click context menu ASCII corrected and `Choose Icon…` added (`ContentView.swift:967-969`); drop-matrix "Drop on empty area" column nuanced to call out `duplicateDropAlert` flow (`ContentView.swift:301-323`); Phase 2 "not shipped" list updated with strikethrough markers for items that the override banner already noted as shipped (multi-select, drop-on-row, duplicate alert, addedInterviews toast, extension allow-list).
- _2026-04-23_ — trued up during port-v01-ingestion QA: inline-banner'd the Project-states table (shipped `PipelineState` enum has .scanning/.queued/.failed/.unreachable/attached-orphan that the table omits); inline-banner'd drop-matrix row 2 (shipped behaviour is blocker toast for `.ready` until incremental re-analyse lands); inline-banner'd "Pipeline does not auto-run on drop" (shipped behaviour DOES auto-run on folder drop); inline-banner'd Activity-status-bar section (shipped placement is toolbar pill `PipelineActivityItem`, not sidebar-bottom); inline-banner'd Phase 2 "not shipped" list (multi-select delete, drag-to-folder, duplicate-drop alert, drop-on-row via SidebarDropDelegate, extension allow-list, addedInterviews toast are in fact shipped); added "Pipeline state × run-trigger matrix" at end. Anchors: `ContentView.swift:508-605`, `PipelineRunner.swift:37-53`, `MenuCommands.swift:397-400`, `PipelineActivityItem.swift:207-210`. Commits: 3d9f43c, 5e254cd, 6d08f3f.
- _Previous_ — shipped Phases 1–3 (project list from disk, drag-and-drop + context menus, folders).

# Multi-Project Sidebar — macOS Desktop App

## Context

The desktop app (`desktop/Bristlenose/`) currently has a hardcoded `ProjectStub` array in `ContentView.swift` and a `Project` menu in `MenuCommands.swift` with 5 unimplemented items. The design doc (`docs/design-multi-project.md`) covers the data model, project index, folder grouping, and security review — but doesn't specify the sidebar UX, menu hierarchy, or interaction details. This plan fills that gap.

Existing design doc: `docs/design-multi-project.md`

> **Substrate + ownership (trued 22 Jun 2026 — read first).** This doc is canonical for the project sidebar's **behaviour and content**: states, row anatomy, project-index storage, on-disk drag semantics, menus, Get Info, the pipeline-state matrix. Two newer docs now own slices of the same surface — keep one-canonical-per-concern:
> - **`design-desktop-nav-toolbar-rearrangement.md`** owns the **lens rail** — the five Project/Sessions/Quotes/Codebook/Analysis *mode* rows relocated to the **top** of the sidebar (above the project list; **not** shown in the §"Sidebar structure" diagram below, which predates them).
> - **`design-desktop-sidebar-appkit.md`** owns the **rendering substrate** — the project list is migrating from SwiftUI `List` to a native AppKit `NSOutlineView` source list (flag-gated `BristlenoseAppKitSidebar`, **the alpha default at cutover**).
>
> So the SwiftUI mechanics named throughout (`List(selection:)`, `SidebarDropDelegate`, `DisclosureGroup`, `ProjectRow`/`FolderRow`) describe the **flag-OFF default build** and are **deleted at cutover** — their *behaviour* is ported verbatim to the outline, but the *how* moves to the appkit doc. Read here for **what the sidebar does**; read the appkit doc for **how the native list renders it**.

## Sidebar structure

Mental model: **Mail sidebar** — curated list of items you've placed, not a live directory listing. Items stay where you put them.

```
┌─────────────────────────────┐
│                             │
│  ■ New Interviews      ◐    │  ← newest at top, spinner = analysing
│  ■ Q1 Usability Study     ● │  ← ● = selected/open
│                             │
│  ▼ Acme Corp                │  ← collapsible folder
│    ■ Mobile Banking Pilot    │
│    ▪ Onboarding Pilot        │  ← grey = unavailable
│      External drive — T7     │     secondary line with hint
│                             │
│  ▼ Beta Inc                  │
│    ■ Checkout Redesign       │
│                             │
│  ─────────────────────────  │  ← separator
│  ▶ Archive (3)              │  ← sorted last, collapsed by default
│                             │
└─────────────────────────────┘
```

### Sort and arrangement

- **Default sort**: newest first (creation date), pushing older items down
- **After that**: user drag-and-drop reorder, persisted via `position` integer in project index
- **System never re-sorts** — once placed, items stay where the user put them
- Folders and root-level projects share one flat position list
- Projects inside a folder also sort newest-first, then user reorder
- Archive section: sorted last (after a separator line), not pinned outside scroll region

### Project states (simplified)

> **Partially superseded 2026-04-23, re-flipped 2026-06-15.** Shipped `PipelineState` enum
> (`PipelineRunner.swift`) has additional states not in this table: `.scanning` (initial), `.queued`
> (FIFO wait), `.running` (includes attached orphans), `.failed(category)`, `.completedPartial`,
> `.stopped`, `.unreachable` (e.g. offline volume). **Update (15 Jun 2026):** the row-level spinner +
> trailing-icon vision in the table below is now **shipped** — the per-project glance lives on the
> sidebar row (`ProjectRowActivityIndicator.swift`), not the toolbar pill (which was deleted, commit
> `8ffa470`). The 2026-04-23 claim that "spinner/badges are not on the row" no longer holds. See
> `Pipeline state × run-trigger matrix` at end of doc for the trigger map (its "Pill popover Retry"
> column is itself now stale — Stop moved to the row hover-× / context menu / Project-menu ⌘.).

| State | Row appearance | Trailing icon |
|-------|---------------|---------------|
| Available | Normal text | — |
| Selected/Open | System highlight | — |
| Analysing | Subtitle shows progress ladder (stage · N of M · ETA) | ◐ progress ring |
| Unavailable | Grey text + secondary line with `display_hint` | — |
| Unavailable — moved/deleted | Grey text + "Locate…" | `questionmark.folder` (actionable) |
| Read-only | Normal text | `lock` |
| Archived | In Archive section | — |

Unavailable projects use one grey treatment regardless of cause (external drive, network, cloud). The `display_hint` text explains why ("Samsung T7", "Acme VPN", "Syncing…"). Only moved/deleted gets a distinct icon because it's actionable (click to relocate). "Needs analysis" and "Stale version" are surfaced in Get Info, not the sidebar row.

All trailing icons and status text must have `.accessibilityLabel()` / `.accessibilityValue()` so VoiceOver reads e.g. "Onboarding Pilot, unavailable, external drive Samsung T7".

### Row anatomy (two-line)

The canonical spec is the `ProjectRow.swift` doc-comment; this is its design home. **(The AppKit `NSTableCellView` port of this same anatomy is `design-desktop-sidebar-appkit.md` §2.4 — that doc owns the substrate rendering; the content + precedence rules stay canonical here. At cutover the SwiftUI `ProjectRow` retires; what the port preserves is the *behaviour* described below.)**

- **Title line** — identity icon · project name · *(right)* **session count** (the interview count — Finder's right-column treatment; empty when the analysis DB isn't readable).
- **Subtitle line** — status text · *(right)* storage/activity qualifier (iCloud arrow, or the activity indicator while a run is in flight). During a run the subtitle shows the **live progress ladder** — stage · N of M · ETA (e.g. "Transcribing · 2 of 3 · <1 min left"), degrading to "Analysing · <1 min left" then "Analysing…" — composed by the pure `RunProgressSubtitle` helper (stage vocabulary = `timing.py ALL_STAGES`, six coarse ids, **not** `manifest.STAGE_ORDER`). Ring / spinner / Stop-× / failure-glyph details: `docs/design-sidebar-activity-indicators.md`.
- **Copy progress on the row** — when files are being copied into a project (drag-drop import), the trailing slot shows a determinate ring (byte fraction) with the subtitle `"Copying · N%"` / `"Cancelling…"`, hover-to-cancel on the ring, and a "Cancel copy" context-menu item. Copy is a per-project op so it lives on the row, **not** a toolbar pill — the standalone `CopyProgressPill` was deleted (19 Jun 2026; the placement axis, `design-desktop-project-status.md` §4). Byte-% not "N of M" (no file-item source exists). Source: `CopyMachinery.inFlight` matched by `projectID`; `ProjectSubtitle.swift` (`.copying` / `.copyCancelling`); `ProjectRow.swift`.

**The session count refreshes on run completion** (it used to go stale until relaunch). It's read from the project's analysis DB (`SELECT COUNT(*) FROM sessions`) via a sandbox-mandated `immutable=1` open that can't see WAL-resident rows — and the count is written by the *serve importer*, not the pipeline run, so a finished run wouldn't refresh it on its own. Two-part fix: the importer PASSIVE-checkpoints the WAL after import, and the desktop rescans the watcher on the analysing→terminal transition (`ContentView.scheduleCountRescan`). The cross-process WAL trap + mechanics live in `bristlenose/server/CLAUDE.md` and `desktop/CLAUDE.md` (immutable-read gotcha) — not duplicated here.

### "New Project" placement

Explore options — possibilities include:
- Toolbar `+` button (most standard macOS pattern — Mail, Notes, Reminders)
- `+` at bottom of sidebar list
- Subtle drag target / proxy row in the sidebar
- File > New Project (Cmd+N) always available as keyboard path

No full-width button row at the top of the sidebar (that's an iOS pattern).

### Empty state

> **Status (shipped 2026-05-01):** The drop-target + CTA empty-surface vision in this section moved out of the sidebar and into the detail pane via `WelcomeView` (`WelcomeView.swift`, commit `816ab65` on `first-run`). `WelcomeView.firstRun` ships the affordance with a different SF Symbol pair (`plus.square.dashed` for the New Project card, `tray.and.arrow.down(.fill)` for the drop card) inside dashed-border accent-tinted cards, plus a 3-step rail and an AI privacy link. `WelcomeView.noSelection` keeps closer to the original sidebar-icon-plus-CTA spirit. The sidebar itself still shows only `Text(i18n.t("desktop.chrome.emptyStateHint"))` at `ContentView.swift:833` ("Drag a folder here or press ⌘N") — the full empty UX lives one column over. The four "ContentUnavailableView" mentions later in this doc are preserved as planning history; the shipped surface is `WelcomeView`. TipKit first-project hint remains parked.

`ContentUnavailableView` with clear CTA: "Drag a folder of interviews here, or press Cmd+N to create a project" with a `doc.badge.plus` SF Symbol. The placeholder doubles as a drag target.

First-project hint: one-time TipKit tip ("Bristlenose remembers your projects here") for the v0.1→v0.2 conceptual transition. Disappears after second project is added.

### Empty folders

Show "(empty)" or "(2 archived)" so an empty disclosed folder doesn't look broken.

## Project index storage

### Location

`~/Library/Application Support/Bristlenose/projects.json`

- Use `FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)` — never `NSHomeDirectory()`
- Not synced by iCloud by default
- Create empty `{ "version": "1.0", "folders": [], "projects": [] }` on first launch if missing
- No iCloud sync — bookmarks are machine-specific, Bristlenose is local-first

### File references (hybrid path + bookmark)

```json
{
  "version": "1.0",
  "folders": [],
  "projects": [
    {
      "id": "uuid-1",
      "name": "Q1 Usability Study",
      "path": "/Volumes/Samsung T7/Research/q1-usability",
      "bookmark_data": "YdB6AAAA...",
      "location": {
        "type": "volume",
        "volume_name": "Samsung T7",
        "volume_relative_path": "Research/q1-usability",
        "display_hint": "External drive — Samsung T7"
      },
      "position": 0,
      "folder_id": null,
      "created_at": "2026-01-10T09:00:00Z",
      "last_opened": "2026-03-15T14:30:00Z",
      "archived": false
    }
  ]
}
```

**Resolution strategy** (on launch / volume mount):
1. Try resolving bookmark first (fastest if volume is mounted)
2. If bookmark fails (stale), try resolving `volume_relative_path` by scanning mounted volumes
3. If both fail, mark project as unavailable (grey, show `display_hint`)

Phase 1 ships with plain paths only. Bookmark data added in Phase 2.

### Ownership

`ProjectIndex` is `@StateObject` at the App level alongside `ServeManager` and `BridgeHandler`, passed via `.environmentObject()`. `MenuCommands` observes it for the "Move to" submenu.

### What drag-and-drop does on disk

**Updated Mar 2026** — follows Logic Pro / Final Cut / GarageBand precedent: the project is a logical container with file references, not a directory alias. No filesystem changes on drop (no creating folders, no moving files).

When files/folders are dragged from Finder:
- **Drag a single folder** → `path` = folder, `inputFiles` = nil (scan entire directory)
- **Drag multiple folders** → one project, `path` = first folder, `inputFiles` = all folder paths
- **Drag file(s)** → one project, `path` = first file's parent dir, `inputFiles` = exactly the dropped files (never siblings)
- **Drag mix of files + folders** → one project, `path` = first item's dir, `inputFiles` = all paths
- No dedup — dropping the same folder twice creates two projects (user may tag/analyse differently). Duplicate warning is a future enhancement (see 100days.md)
- The `name` field is display-only. It must never be used to construct filesystem paths. The `path` field is set at creation and only changed by relocate
- `inputFiles` (optional `[String]?` in `projects.json` as `input_files`): when nil, the pipeline scans the entire `path` directory. When populated, only those files/directories are processed. This is how single-file projects and multi-source projects coexist with the legacy folder-scan model

## Rename interaction

Based on survey of 14 macOS apps:

- **Slow double-click** on name in sidebar → inline text field (universal across all Mac apps)
- **Right-click > Rename** (common, include in context menu)
- **Menu bar > Project > Rename** (no keyboard shortcut — rename is infrequent)
- **New project from drop/create** → item appears with name selected inline for editing (Finder pattern, used by 9 of 14 apps)
- **Commit**: Return. **Cancel**: Escape
- **No dialog, no sheet** — inline only, always

Enter key does NOT trigger rename (only Finder/Xcode do this — most apps use Enter to open/activate).

## Menus

### File menu (updated)

```
File
┌──────────────────────────────┐
│ New Project…           ⌘N    │
│ New Folder…            ⇧⌘N   │
│ Open in New Window…    ⇧⌘O   │
├──────────────────────────────┤
│ Export Report…         ⇧⌘E   │
│ Export Anonymised…            │
├──────────────────────────────┤
│ Page Setup…                   │
│ Print…                 ⌘P    │
└──────────────────────────────┘
```

### Project menu (adapts based on selection — project or folder)

> **Trued 2026-04-24.** Original ASCII art listed `Add Interviews… ⇧⌘I`, `Analyse… ⇧⌘A`, and `Get Info ⌘I` — none exist in `MenuCommands.swift`. The shipped Project menu (`MenuCommands.swift:317-415`) wires Show in Finder, Locate (when unavailable), Rename, Move to (submenu, conditional on folders existing), Re-analyse (`.disabled(true)`), Archive (`.disabled(true)`), and Delete. Get Info is Phase 5 (see §"Get Info" below). Add Interviews / Analyse remain valid future work but should be tracked in §"Implementation phases", not asserted as shipped menu items.

When a project is selected (shipped):
```
Project
┌──────────────────────────────┐
│ Show in Finder         ⇧⌘R   │
│ Locate                        │   (enabled only when project unreachable)
│ Rename                        │
│ Move to                ▶     │   (when folders exist)
├──────────────────────────────┤
│ Re-analyse…                   │   (disabled — Phase 2+)
│ Archive                       │   (disabled — Phase 5)
├──────────────────────────────┤
│ Delete                 ⌘⌫    │
└──────────────────────────────┘
```

When a folder is selected (shipped, `MenuCommands.swift:336-352`):
```
Project
┌──────────────────────────────┐
│ Rename Folder                 │
│ Archive Folder                │   (disabled — Phase 5)
├──────────────────────────────┤
│ Delete Folder          ⌘⌫    │
└──────────────────────────────┘
```

All items disabled when nothing is selected.

### Right-click context menu on a project (NO keyboard shortcut glyphs — HIG rule)

> **Trued 2026-04-24.** Same drift as above — `Add Interviews…` and `Analyse…` are not in the shipped context menu (`ContentView.swift:944-995`). Add `Choose Icon…` (opens IconPickerPopover via `ContentView.swift:967-969`).

```
┌──────────────────────────────┐
│ Show in Finder                │
│ Rename                        │
│ Move to                ▶     │
│ Choose Icon…                  │
├──────────────────────────────┤
│ Re-analyse…                   │   (disabled)
│ Archive                       │   (disabled)
├──────────────────────────────┤
│ Delete                        │
└──────────────────────────────┘
```

**Alpha gap:** no `Analyse` / `Resume` / `Retry` actions in either menu — see matrix at end of doc.

### Right-click on a folder

```
┌──────────────────────────────┐
│ Rename Folder                 │
│ Archive Folder                │
├──────────────────────────────┤
│ Delete Folder…                │
└──────────────────────────────┘
```

### Delete semantics

- **Delete project**: removes from `projects.json` index AND deletes `bristlenose-output/` directory. Never deletes original recordings — that's Finder's job. Confirmation dialog shows what will be removed with absolute paths
- **Delete folder**: moves all projects inside to root level, then removes the folder from the index. Confirmation: "Delete folder 'Acme Corp'? The 3 projects inside will be moved to the top level. No files will be deleted."
- Undo for delete-from-index: designed later (part of undo backlog)

## Drag and drop

### Interaction model

> **Superseded 2026-04-23.** Drop-on-row matrix ships differently from the table below. Shipped policy (see `ContentView.swift:548-605`, `handleDropOnProject`) is state-dependent:
>
> | Target state | Shipped behaviour |
> |---|---|
> | `.idle` / `.scanning` | `addFiles` + auto-run, toast "Added N interviews to …" (no Undo button) |
> | `.ready` | Blocker toast "Adding extra interviews to an analysed project isn't supported yet" — incremental re-analyse not yet implemented |
> | `.failed` | Toast redirects user to pill-popover Retry |
> | `.running` / `.queued` | Toast "Finish or stop the current run before adding more" |
> | `.unreachable` | Blocked with explanation toast |
>
> Empty-sidebar-area drop (row 1 below) matches the shipped path. The row 2 vision (Add interviews + Undo on any state) is the aspirational target once incremental re-analyse lands.

| Drag source | Drop target | Result |
|-------------|-------------|--------|
| Files/folder from Finder | Empty sidebar area | Create new project, name adopted from folder/first item (no inline rename; "+ New Project" still prompts) |
| Files/folder from Finder | Existing project row | Add interviews, toast: "Added 3 interviews to Mobile Banking Pilot" with Undo button |

### Native affordances

- Return `.copy` from drop handler — system draws green + badge automatically
- System blue rounded-rect row highlight on valid drop target
- Prohibition badge during drag for invalid file types (validate in `validateDrop`)
- Spring-loaded folders: collapsed folders auto-expand after 500ms hover during drag, re-collapse on drag-away (implementation note: SwiftUI List doesn't support natively — needs timer in drop delegate)
- Drop animation: drag image zooms into target (free with AppKit)
- UTType registration: `.mpeg4Movie`, `.quickTimeMovie`, `.mpeg4Audio`, `.wav`, `.mp3`, `.plainText`, plus custom UTTypes for `.srt`/`.vtt`. Reject `.html`, `.py`, `.json` etc
- `ContentUnavailableView` as drag target for empty sidebar
- **Menu bar equivalents for everything**: File > New Project…, context menu > Add Interviews…

### What drag does NOT do

> **Superseded 2026-04-23.** First bullet below is reversed: shipped behaviour (`ContentView.swift:508-510`) DOES auto-run the pipeline on folder drop (ported from v0.1 where drop-equals-analyse was the whole UX). No separate "Analyse" menu action exists today — `Project > Re-analyse…` menu item is `.disabled(true)` per `MenuCommands.swift:397-400`. The "Analyse as a separate action" design intent is still on the table, but gated on landing the `Analyse` / `Resume` / `Retry` context-menu verbs alongside incremental re-analyse.

- Pipeline does not auto-run on drop — "Analyse" is a separate action
- No confirmation modal for new project creation — just do it (Finder pattern)
- Undo mechanism (Cmd+Z) designed later

## Click behaviour

- **Single click**: select project, load in detail pane (starts serve)
- **Double click**: open in new window (Notes pattern — future, multi-window)
- **Slow double-click on name**: inline rename

Note: switching to a *new* project starts a serve process (the target row shows a loading indicator during startup). Switching **back** to the immediately-previous project is now fast — it re-points to a parked, still-running sidecar instead of teardown+restart (warm-sidecar pool, Phase A2, shipped 19 Jun 2026 — `ServeManager.swift`, `ParkedSidecar.swift`). The "cache recently-served projects" idea below is what shipped, for a single warm slot; broader caching (warm *WebView*, N-pool) is future work. See `design-desktop-switch-performance.md`.

## Get Info

Non-modal panel (like Finder's Cmd+I window). Shows:

- Project name, path on disk, location type
- Created date, last analysed date, Bristlenose version used
- Number of sessions / quotes / tags
- Disk space (input + output)
- LLM provider used for analysis
- "Needs re-analysis" / "stale version" status (moved here from sidebar row)

Built later — not Phase 1.

## Activity status bar

> **Superseded 2026-04-23, updated 2026-06-15.** The 2026-04-23 note said all activity was centralised
> in a trailing-toolbar pill (`PipelineActivityItem`) and per-row spinners were *not* shipped. **Both
> halves are now stale:** the pill was **deleted** (commit `8ffa470`), and the **per-row spinner IS
> shipped** (`ProjectRowActivityIndicator.swift`, right-slot — running spinner, hover-× Stop, clickable
> failure glyph). The Mail-pattern sidebar-bottom status strip described in this section is still *not*
> the shipped placement (the row is) — retained as planning history for a future cross-project surface.

Bottom-left of sidebar, like Mail's "Updated just now" area.
- Use `safeAreaInset(edge: .bottom)` to place below the list without fighting scroll
- Shows current activity: "Transcribing session 3/8", "Extracting quotes…"
- Individual project rows show spinner when that project is busy
- **Hidden when idle** — no "All good!" message
- Completion signal: brief checkmark on the project row for 2-3 seconds when analysis finishes
- VoiceOver: post `AccessibilityNotification.Announcement` on pipeline start/complete

## Accessibility backlog (future)

- Keyboard alternative for sidebar drag-to-reorder ("Move Up"/"Move Down" in context menu or Edit mode)
- VoiceOver announcements for drop results ("Added 3 interviews to Mobile Banking Pilot")
- Spring-loaded folder state announcements for assistive drag
- `accessibilityDropPoint` labels on drop targets
- Proactive status bar updates via `.accessibilityAddTraits(.updatesFrequently)`

## Security notes

- `projects.json` is an unencrypted client roster. Document risk in SECURITY.md. Encryption is a pre-v1.0 task, not needed for beta
- Project and folder names are user-controlled strings — never interpolate into JavaScript (use `callAsyncJavaScript(arguments:)`), never use to construct filesystem paths
- Presentation/focus mode (collapse all other folders during screen-share) is a fast-follow

## Implementation phases

### Phase 1 — Project list from disk (MVP)

Replace `ProjectStub` array with `ProjectIndex` loading from `projects.json`.
- `ProjectIndex.swift` — model, load/save, `@Published` for SwiftUI observation
- `ProjectRow.swift` — sidebar row view with selection highlight
- "New Project" via `NSOpenPanel` (folder picker) — creates index entry, starts serve
- Plain file paths (no bookmarks yet)
- Project menu wired: Show in Finder, Rename (inline), Delete (index + output)
- No folders, no archive, no drag-from-Finder

**Files**: `ProjectIndex.swift` (new), `ProjectRow.swift` (new), `ContentView.swift` (replace stubs), `MenuCommands.swift` (wire Project menu), `BridgeHandler.swift` (new actions)

### Phase 2 — Drag-and-drop + context menus (shipped 26 Mar 2026)

**Shipped:**
- Drag-and-drop from Finder onto sidebar — files and folders, single and multiple
  - Single folder → project scans whole directory (`inputFiles: nil`)
  - Multiple folders → one project, `inputFiles` lists all folder paths
  - Single/multiple files → one project, `inputFiles` = exactly the dropped files (never siblings)
  - Mixed files + folders → one project, all paths in `inputFiles`
  - No dedup — same folder dropped twice creates two projects (user may analyse differently)
  - Project named after first item (folder name or filename stem) — drag-create adopts it with no inline rename ("+ New Project" still prompts; commit `09f8625`)
- `Project.inputFiles` (`input_files` in JSON) — optional `[String]?`. nil = scan whole directory (backward compatible). Populated = process only listed files/directories. Follows Logic Pro / Final Cut precedent: project is a logical container, files are references
- Right-click context menu on project rows: Show in Finder, Rename, Delete (destructive role)
- Context menu actions scoped to right-clicked row (not necessarily the selected row)
- ⌘⌫ keyboard shortcut for Delete in Project menu
- `ProjectIndex.addFiles(to:files:)` — append files to existing project with dedup
- `ProjectIndex.findByPath()` — lookup by filesystem path
- Async URL loading from drop providers via `withTaskGroup` + `withCheckedContinuation`

**Not shipped (parked in 100days.md):**
- Slow-double-click rename — `simultaneousGesture(TapGesture())` and `onTapGesture` on List rows break selection on macOS 26. Rename works via right-click and Project menu. Needs NSEvent monitor or AppKit subclass
- ~~Multi-select (Shift/Cmd click)~~ — **shipped** (`List(selection: Set<SidebarSelection>)`); known multi-select Delete bug is the alpha-blocker
- ~~Drop-on-existing-project-row~~ — **shipped** via `SidebarDropDelegate` frame hit-test
- Drag-to-reorder — needs multi-select first. Phase 3 in design doc
- ~~Duplicate folder drop warning~~ — **shipped** as `duplicateDropAlert` (`ContentView.swift:301-323`)
- ~~Toast for "added interviews to project"~~ — **shipped** (`desktop.chrome.addedInterviews`, `ContentView.swift:586-592`)
- Empty state `ContentUnavailableView` as drag target
- ~~UTType validation for media files~~ — **shipped** as extension allow-list (`acceptedExtensions`, `ContentView.swift:410-419`); not UTType-based but equivalent outcome

> **Superseded 2026-04-23 — items that actually did ship:**
> - **Multi-select** shipped via `List(selection: Set<SidebarSelection>)` (`ContentView.swift` sidebar). Context-menu Delete uses the Finder pattern (`removeFromSidebarContextMenu`, `ContentView.swift:797`) — right-clicking a row in the selection acts on the whole selection; right-clicking outside acts only on that row. ⌘⌫ bulk-deletes. The earlier "context-menu Delete deletes only focused row" bug is resolved; verified by smoke 21 May 2026.
> - **Drop-on-existing-project-row** shipped via `SidebarDropDelegate` with frame hit-testing (workaround for `.onDrop` + List selection breakage). Outcome is state-dependent (see drop matrix above).
> - **Duplicate folder drop warning** shipped as `duplicateDropAlert` with Open Existing / Create Anyway / Cancel (`ContentView.swift:301-323`).
> - **"Added interviews to project" toast** shipped via `desktop.chrome.addedInterviews` format string (`ContentView.swift:586-592`) for `.idle` / `.scanning` targets.
> - **Drag-to-folder (internal)** shipped via `.draggable` + `SidebarDropDelegate` hit-test on folder rows.
> - **File-type validation** shipped as extension allow-list (`acceptedExtensions` Set in `ContentView.swift:410-419`) — not UTType-based as originally specced, but equivalent outcome for accepted formats.
> - **Subset-project state** (drag of single file(s)) shipped via `UnsupportedSubsetView` — displays "Bristlenose analyses folders" detail view for projects created from individual files.
>
> Still accurately parked: slow-double-click rename, drag-to-reorder, spring-loaded folders, empty-state ContentUnavailableView.

**Files**: `ProjectIndex.swift` (model, CRUD, inputFiles), `ProjectRow.swift` (context menu callbacks, rename), `ContentView.swift` (drop handling, context menu, async URL loading), `MenuCommands.swift` (⌘⌫ shortcut)

### Phase 3 — Folders

**Shipped:**
- `FolderRow.swift` — collapsible folder header with disclosure triangle (`DisclosureGroup`)
- `Folder` struct replaces `FolderStub` — `id`, `name`, `collapsed`, `createdAt` (backward-compatible decoder)
- `folderId: UUID?` on `Project` — nil = root level
- `SidebarSelection` enum — `List(selection:)` handles both `.project(UUID)` and `.folder(UUID)`
- Create folder: File > New Folder (⇧⌘N), sidebar `folder.badge.plus` button, inline rename on creation
- "Move to" submenu in context menu and Project menu — lists all folders + "No Folder" for root
- Folder context menu: Rename Folder, Archive Folder (disabled — Phase 5), Delete Folder
- Delete folder: projects inside move to root level, folder removed
- Project menu adapts based on selection (project items vs folder items)
- Folder collapsed state persisted in `projects.json`
- Locale keys in all 6 languages (en, es, fr, de, ko, ja)

**Not shipped (parked):**
- Drag-to-reorder projects and folders — needs multi-select first (parked in 100days.md)
- Spring-loaded folders during drag — SwiftUI List doesn't support natively

**Files**: `FolderRow.swift` (new), `ProjectIndex.swift` (Folder model, folder CRUD, SidebarItem/SidebarSelection enums, folderId on Project), `ContentView.swift` (sidebar restructuring, DisclosureGroup, folder notifications), `MenuCommands.swift` (adaptive Project menu, Move To submenu, New Folder in File menu), `BridgeHandler.swift` (selectedFolderName), 6 locale files

### Phase 4 — Availability + volume tracking ✅ shipped 26 Apr 2026 (port-v01-ingestion)

- `location` field auto-populated on project creation (local/volume/network/cloud detection) — `Location` struct in `ProjectIndex.swift:14-22`
- Grey treatment for unavailable projects with `display_hint` secondary line — `Project.availability` enum in `ProjectIndex.swift:132-145`
- Bookmark data stored alongside paths (hybrid resolution) — `bookmarkData: Data?` accepted in init; resolution-on-access still to verify under sandbox (Track A territory)
- `NSWorkspace.didMountNotification` / `didUnmountNotification` to update availability — `VolumeWatcher.swift:21-44`
- Volume-relative path fallback for remounted drives — shipped
- "Locate…" action for moved/deleted projects (re-select via NSOpenPanel) — verify
- `VolumeWatcher.swift` — separate observer, not on ContentView ✅

**Files**: `ProjectIndex.swift` (availability, bookmarks), `VolumeWatcher.swift`, `ProjectRow.swift` (grey state, secondary line)

**Outstanding under Phase 4:** confirm security-scoped bookmark resolution under the macOS sandbox once Track A (`sandbox-debug` worktree) lands its inventory; also confirm the "Locate…" action is wired.

### Phase 5 — Archive + status bar + Get Info

- Archive section (sorted last after separator, collapsed by default)
- Archive/unarchive actions in menus and context menus
- Restore-to-folder prompt using `previous_folder_id`
- Activity status bar (`safeAreaInset(edge: .bottom)`)
- Pipeline progress forwarded from serve process to status bar
- Get Info non-modal panel (Cmd+I)
- Completion checkmark animation on project row

**Files**: `StatusBar.swift` (new), `GetInfoPanel.swift` (new), `ProjectRow.swift` (archive state, completion animation), `ContentView.swift` (status bar placement)

### Future

- Undo for all sidebar mutations (add, delete, move, rename)
- Accessibility: keyboard reorder, drop announcements
- Presentation/focus mode (hide other client folders during screen-share)
- Concurrent serve sessions (multiple projects open simultaneously)
- Project index encryption (pre-v1.0)
- `bristlenose projects` CLI command reading same index
- Cross-project search scoped to folders

## Key files to modify

- `desktop/Bristlenose/Bristlenose/ContentView.swift` — replace `ProjectStub` array, add sidebar content
- `desktop/Bristlenose/Bristlenose/MenuCommands.swift` — update Project menu, add New Folder to File menu
- `desktop/Bristlenose/Bristlenose/BridgeHandler.swift` — new actions for project operations
- New: `ProjectIndex.swift` — model for `projects.json` (load/save/reorder/CRUD)
- New: `ProjectRow.swift` — sidebar row view with state icons, context menu, drop target, inline rename
- New: `FolderRow.swift` — collapsible folder header with context menu
- New: `VolumeWatcher.swift` — NSWorkspace mount/unmount observer
- New: `StatusBar.swift` — bottom-left activity indicator
- New: `GetInfoPanel.swift` — non-modal project metadata panel
- `docs/design-multi-project.md` — add this sidebar UX spec as a new section

Note: Xcode uses `PBXFileSystemSynchronizedRootGroup` — new Swift files in `desktop/Bristlenose/Bristlenose/` are auto-discovered. No manual pbxproj edits needed.

## Verification

- Build desktop app: `cd desktop/Bristlenose && xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"`
- Manual QA per phase: each phase has its own testable surface
- VoiceOver: verify sidebar navigation, status announcements (Phase 4+)

## Pipeline state × run-trigger matrix (as of 2026-04-23)

Added during 23 Apr 2026 QA pass — shipped reality for "how can a user start/resume/retry/re-analyse a project?" Not previously documented in any design doc.

| State | Pill popover Retry | Menu `Project > Re-analyse…` | Drop on row (state-dependent) | Drop on empty area |
|---|---|---|---|---|
| `.idle` (never run or post-cancel) | n/a | disabled (`Phase 2+`) | auto-run via `addFiles` + spawn | new project; single-folder duplicate → `duplicateDropAlert` (Open Existing / Create Anyway / Cancel) |
| `.scanning` (initial manifest read) | n/a | disabled | auto-run | as above |
| `.queued` | n/a | disabled | rejected with toast | as above |
| `.running` (includes attached orphan) | shows Stop, not Retry | disabled | rejected with toast | as above |
| `.failed` | ✅ Retry | disabled | redirects user to toolbar Retry (toast text: "Use Retry on the toolbar to try this run again") | as above |
| `.ready` | n/a | disabled | blocker toast (no incremental re-analyse) | as above |
| `.unreachable` (moved / offline volume) | n/a | disabled | blocked with explanation toast | as above |

**Empty-area drop note:** "Drop on empty area" creates a new project on first drop. For single-folder drops matching an existing project path, `duplicateDropAlert` (`ContentView.swift:301-323`) intercepts before creation — the user picks Open Existing / Create Anyway / Cancel. Multi-item drops bypass the dedup check.

**Gaps this table surfaces:**

- `.idle`, `.stopped` (would-be post-cancel), and `.ready` have **no first-class run trigger** — users must drop the folder again on the empty area, which creates a duplicate project, OR rely on pill Retry for `.failed` only.
- `Project > Re-analyse…` menu item exists (`MenuCommands.swift:397-400`) but is `.disabled(true)` with Phase 2+ comment.
- Context menu on project rows has no `Analyse` / `Resume` / `Retry` items.
- Three user-facing verbs have been scoped for alpha (see also `docs/design-subprocess-lifecycle.md` and plan-note):
  - **Resume** — pipeline was interrupted, manifest has partial state, safe to continue (no human data exists yet).
  - **Retry** — pipeline errored, same mechanism as Resume, different entry.
  - **Re-analyse…** — destructive do-over, nukes human edits/tags/stars/hidden quotes, confirmation modal. Copy: "Discards all your edits, tags, stars, and hidden quotes. Runs a fresh analysis."

**Alpha scope:** splitting `.idle` into `.idle` (never-run) and `.stopped` (post-cancel); context-menu verbs above; incremental re-analyse (to unblock drop-on-`.ready`). Logged in plan-note `docs/private/truing-ingestion-lifecycle-2026-04-23.md` and in active QA plan.
