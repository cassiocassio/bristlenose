---
status: partial
last-trued: 2026-04-23
trued-against: HEAD@port-v01-ingestion on 2026-04-23
---

> **Truing status:** Partial — Phases 1–3 (project list, drag-and-drop, folders) shipped and broadly accurate; drop-matrix outcomes, project-state table, "Pipeline does not auto-run on drop" claim, activity-status-bar placement, and Phase 2 "not shipped" list have drifted and carry inline `Superseded 2026-04-23` banners. Pipeline-state × run-trigger matrix added at end. See changelog below.

## Changelog

- _2026-04-23_ — trued up during port-v01-ingestion QA: inline-banner'd the Project-states table (shipped `PipelineState` enum has .scanning/.queued/.failed/.unreachable/attached-orphan that the table omits); inline-banner'd drop-matrix row 2 (shipped behaviour is blocker toast for `.ready` until incremental re-analyse lands); inline-banner'd "Pipeline does not auto-run on drop" (shipped behaviour DOES auto-run on folder drop); inline-banner'd Activity-status-bar section (shipped placement is toolbar pill `PipelineActivityItem`, not sidebar-bottom); inline-banner'd Phase 2 "not shipped" list (multi-select delete, drag-to-folder, duplicate-drop alert, drop-on-row via SidebarDropDelegate, extension allow-list, addedInterviews toast are in fact shipped); added "Pipeline state × run-trigger matrix" at end. Anchors: `ContentView.swift:508-605`, `PipelineRunner.swift:37-53`, `MenuCommands.swift:397-400`, `PipelineActivityItem.swift:207-210`. Commits: 3d9f43c, 5e254cd, 6d08f3f.
- _Previous_ — shipped Phases 1–3 (project list from disk, drag-and-drop + context menus, folders).

# Multi-Project Sidebar — macOS Desktop App

## Context

The desktop app (`desktop/Bristlenose/`) currently has a hardcoded `ProjectStub` array in `ContentView.swift` and a `Project` menu in `MenuCommands.swift` with 5 unimplemented items. The design doc (`docs/design-multi-project.md`) covers the data model, project index, folder grouping, and security review — but doesn't specify the sidebar UX, menu hierarchy, or interaction details. This plan fills that gap.

Existing design doc: `docs/design-multi-project.md`

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

> **Superseded 2026-04-23.** Shipped `PipelineState` enum (`PipelineRunner.swift:37-53`) has additional states not in this table: `.scanning` (initial), `.queued` (FIFO wait), `.running` (includes attached orphans), `.failed(category)`, `.unreachable` (e.g. offline volume). User-cancelled runs land in `.idle`; never-run and post-cancel are conflated under `.idle` today — a split (`.stopped` / `.cancelled`) is in the alpha backlog. Shipped UI surfaces activity in the toolbar pill `PipelineActivityItem`, not in the sidebar row — the spinner/badges described below are not on the row. See `Pipeline state × run-trigger matrix` at end of doc for the current trigger map.

| State | Row appearance | Trailing icon |
|-------|---------------|---------------|
| Available | Normal text | — |
| Selected/Open | System highlight | — |
| Analysing | Normal text | ◐ spinner |
| Unavailable | Grey text + secondary line with `display_hint` | — |
| Unavailable — moved/deleted | Grey text + "Locate…" | `questionmark.folder` (actionable) |
| Read-only | Normal text | `lock` |
| Archived | In Archive section | — |

Unavailable projects use one grey treatment regardless of cause (external drive, network, cloud). The `display_hint` text explains why ("Samsung T7", "Acme VPN", "Syncing…"). Only moved/deleted gets a distinct icon because it's actionable (click to relocate). "Needs analysis" and "Stale version" are surfaced in Get Info, not the sidebar row.

All trailing icons and status text must have `.accessibilityLabel()` / `.accessibilityValue()` so VoiceOver reads e.g. "Onboarding Pilot, unavailable, external drive Samsung T7".

### "New Project" placement

Explore options — possibilities include:
- Toolbar `+` button (most standard macOS pattern — Mail, Notes, Reminders)
- `+` at bottom of sidebar list
- Subtle drag target / proxy row in the sidebar
- File > New Project (Cmd+N) always available as keyboard path

No full-width button row at the top of the sidebar (that's an iOS pattern).

### Empty state

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

When a project is selected:
```
Project
┌──────────────────────────────┐
│ Show in Finder         ⇧⌘R   │
│ Rename                        │
│ Move to                ▶     │
│ Get Info               ⌘I    │
├──────────────────────────────┤
│ Add Interviews…        ⇧⌘I   │
│ Analyse…               ⇧⌘A   │
├──────────────────────────────┤
│ Archive                       │
│ Delete…                       │
└──────────────────────────────┘
```

When a folder is selected:
```
Project
┌──────────────────────────────┐
│ Rename Folder                 │
│ Archive Folder                │
├──────────────────────────────┤
│ Delete Folder…                │
└──────────────────────────────┘
```

All items disabled when nothing is selected.

### Right-click context menu on a project (NO keyboard shortcut glyphs — HIG rule)

```
┌──────────────────────────────┐
│ Show in Finder                │
│ Rename                        │
│ Move to                ▶     │
│ Get Info                      │
├──────────────────────────────┤
│ Add Interviews…               │
│ Analyse…                      │
├──────────────────────────────┤
│ Archive                       │
│ Delete…                       │
└──────────────────────────────┘
```

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
| Files/folder from Finder | Empty sidebar area | Create new project, name from folder/parent, inline rename selected |
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

Note: switching projects stops and restarts the serve process (5-15 second delay). The target project row should show a loading indicator during startup. May need to cache recently-served projects for faster switching later.

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

> **Superseded 2026-04-23.** Shipped placement is a trailing-toolbar pill (`PipelineActivityItem` in `ContentView.swift:754-761`), not a sidebar-bottom status bar. The pill opens a popover with stage/elapsed/Stop/Retry. Per-row spinner icons and row-level completion checkmarks described below are not shipped — all activity is centralised in the toolbar pill. This section retained as planning history; when re-designing the cross-project activity surface, reconsider the Mail-pattern bottom strip vs the current pill.

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
  - Project named after first item (folder name or filename stem), inline rename activated
- `Project.inputFiles` (`input_files` in JSON) — optional `[String]?`. nil = scan whole directory (backward compatible). Populated = process only listed files/directories. Follows Logic Pro / Final Cut precedent: project is a logical container, files are references
- Right-click context menu on project rows: Show in Finder, Rename, Delete (destructive role)
- Context menu actions scoped to right-clicked row (not necessarily the selected row)
- ⌘⌫ keyboard shortcut for Delete in Project menu
- `ProjectIndex.addFiles(to:files:)` — append files to existing project with dedup
- `ProjectIndex.findByPath()` — lookup by filesystem path
- Async URL loading from drop providers via `withTaskGroup` + `withCheckedContinuation`

**Not shipped (parked in 100days.md):**
- Slow-double-click rename — `simultaneousGesture(TapGesture())` and `onTapGesture` on List rows break selection on macOS 26. Rename works via right-click and Project menu. Needs NSEvent monitor or AppKit subclass
- Multi-select (Shift/Cmd click) — needs `List(selection:)` with `Set<UUID>` instead of `UUID?`. Detail pane would show "N projects selected". Prerequisite for drag-to-folder
- Drop-on-existing-project-row — per-row `.onDrop` also breaks List selection. Data model (`addFiles`) is ready but UI is parked
- Drag-to-reorder — needs multi-select first. Phase 3 in design doc
- Duplicate folder drop warning — dismissable warning when folder matches existing project path
- Toast for "added interviews to project"
- Empty state `ContentUnavailableView` as drag target
- UTType validation for media files (currently accepts any file/folder)

> **Superseded 2026-04-23 — items that actually did ship:**
> - **Multi-select** shipped via `List(selection: Set<SidebarSelection>)` (`ContentView.swift` sidebar). Multi-select context-menu Delete has a known bug: deletes only the focused row, not the full selection (logged as alpha fix).
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

### Phase 4 — Availability + volume tracking

- `location` field auto-populated on project creation (local/volume/network/cloud detection)
- Grey treatment for unavailable projects with `display_hint` secondary line
- Bookmark data stored alongside paths (hybrid resolution)
- `NSWorkspace.didMountNotification` / `didUnmountNotification` to update availability
- Volume-relative path fallback for remounted drives
- "Locate…" action for moved/deleted projects (re-select via NSOpenPanel)
- `VolumeWatcher.swift` — separate observer, not on ContentView

**Files**: `ProjectIndex.swift` (availability, bookmarks), `VolumeWatcher.swift` (new), `ProjectRow.swift` (grey state, secondary line)

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
| `.idle` (never run or post-cancel) | n/a | disabled (`Phase 2+`) | auto-run via `addFiles` + spawn | ✅ creates new project (duplicate) |
| `.scanning` (initial manifest read) | n/a | disabled | auto-run | ✅ duplicate |
| `.queued` | n/a | disabled | rejected with toast | ✅ duplicate |
| `.running` (includes attached orphan) | shows Stop, not Retry | disabled | rejected with toast | ✅ duplicate |
| `.failed` | ✅ Retry | disabled | redirects user to pill Retry | ✅ duplicate |
| `.ready` | n/a | disabled | blocker toast (no incremental re-analyse) | ✅ duplicate |
| `.unreachable` (moved / offline volume) | n/a | disabled | blocked | ✅ duplicate |

**Gaps this table surfaces:**

- `.idle`, `.stopped` (would-be post-cancel), and `.ready` have **no first-class run trigger** — users must drop the folder again on the empty area, which creates a duplicate project, OR rely on pill Retry for `.failed` only.
- `Project > Re-analyse…` menu item exists (`MenuCommands.swift:397-400`) but is `.disabled(true)` with Phase 2+ comment.
- Context menu on project rows has no `Analyse` / `Resume` / `Retry` items.
- Three user-facing verbs have been scoped for alpha (see also `docs/design-subprocess-lifecycle.md` and plan-note):
  - **Resume** — pipeline was interrupted, manifest has partial state, safe to continue (no human data exists yet).
  - **Retry** — pipeline errored, same mechanism as Resume, different entry.
  - **Re-analyse…** — destructive do-over, nukes human edits/tags/stars/hidden quotes, confirmation modal. Copy: "Discards all your edits, tags, stars, and hidden quotes. Runs a fresh analysis."

**Alpha scope:** splitting `.idle` into `.idle` (never-run) and `.stopped` (post-cancel); context-menu verbs above; incremental re-analyse (to unblock drop-on-`.ready`). Logged in plan-note `docs/private/truing-ingestion-lifecycle-2026-04-23.md` and in active QA plan.
