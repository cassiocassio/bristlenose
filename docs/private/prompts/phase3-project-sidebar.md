# Phase 3 — Project Sidebar: Folders

## What to build

Add one-level-deep folders for organising projects in the sidebar. This is Phase 3 from `docs/design-project-sidebar.md`.

## Design doc

Read `docs/design-project-sidebar.md` — the full design with wireframes, menus, interaction patterns, and phasing. **This task is Phase 3 only.**

Also read `docs/design-multi-project.md` for the folder data model and `project_multi_project_folders.md` in memory for prior design decisions.

## Phase 1–2 recap (already shipped)

- `ProjectIndex.swift` — model with `inputFiles` support, CRUD, `findByPath()`, `addFiles()`
- `ProjectRow.swift` — sidebar row with `doc.text` icon, inline rename (menu/context menu driven)
- Context menus on project rows: Show in Finder, Rename, Delete
- Drag-and-drop from Finder: single file, multiple files, single folder, multiple folders, mixed
- `inputFiles` model: nil = scan whole directory, populated = specific files/folders only
- ⌘⌫ keyboard shortcut for Delete in Project menu
- Selection by UUID, `@AppStorage` persistence across launches

### Known limitations from Phase 2

- No slow-double-click rename (SwiftUI gesture breaks List selection on macOS 26 — parked in 100days.md)
- No multi-select (Shift/Cmd click) — needs `Set<UUID>` selection model (parked in 100days.md)
- No drop-on-existing-project-row (per-row `.onDrop` also breaks List selection)
- No drag-to-reorder (needs multi-select first)

## Phase 3 scope (from the design doc)

- **`FolderRow.swift`** — collapsible folder header with disclosure triangle
- **Create folder** — File > New Folder (⇧⌘N), sidebar button (folder.badge.plus, currently disabled)
- **"Move to" submenu** — in context menu and Project menu, lists all folders
- **Folder context menu** — Rename Folder, Archive Folder (disabled), Delete Folder
- **Project menu adapts** — shows project items when project selected, folder items when folder selected
- **Folder persistence** — `FolderStub` in `projects.json` already has `id` and `name` fields; add projects to folders via `folder_id` on Project

### NOT in Phase 3

- Drag-to-reorder (needs multi-select — parked)
- Spring-loaded folders during drag (SwiftUI List doesn't support natively)
- Archive section (Phase 5)
- Recently Deleted bin (Phase 5)

## Key files to modify

- `desktop/Bristlenose/Bristlenose/ProjectIndex.swift` — folder CRUD, `folder_id` on Project, promote `FolderStub` to public `Folder` struct
- `desktop/Bristlenose/Bristlenose/FolderRow.swift` — NEW, collapsible folder header
- `desktop/Bristlenose/Bristlenose/ContentView.swift` — sidebar structure with `DisclosureGroup` or `Section` per folder, enable folder.badge.plus button, wire "Move to"
- `desktop/Bristlenose/Bristlenose/ProjectRow.swift` — may need updates for folder context
- `desktop/Bristlenose/Bristlenose/MenuCommands.swift` — adaptive Project menu (project vs folder), "Move to" submenu, New Folder wiring

## Conventions

- Read `desktop/CLAUDE.md` for desktop app conventions, security rules, and existing patterns
- Security rule 3: never interpolate user strings into JavaScript — use `callAsyncJavaScript(arguments:)`
- Folder names are display-only, same as project names — never construct filesystem paths from them
- One level deep only — no nested folders

## Verification

```bash
cd desktop/Bristlenose && xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"
```

Then manual QA:
1. File > New Folder (⇧⌘N) — creates folder in sidebar with inline rename
2. Sidebar folder.badge.plus button — creates folder
3. Folder appears with disclosure triangle, collapsible
4. Right-click project > Move to > folder name — moves project into folder
5. Project menu > Move to > folder name — same
6. Right-click folder — Rename Folder, Delete Folder
7. Delete Folder — projects inside move to top level, folder removed
8. Folder collapsed state persists across app relaunch
9. Project menu shows folder-specific items when folder is selected
