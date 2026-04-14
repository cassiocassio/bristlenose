# Phase 3 — Project Sidebar: Folders

## Context

The desktop app sidebar lists projects in a flat list (Phase 1–2). Researchers working with multiple clients need to group projects by client or engagement. Phase 3 adds one-level-deep folders — the third phase from `docs/design-project-sidebar.md`.

## Scope

**In:** Folder CRUD, collapsible folders, "Move to" submenu, adaptive Project menu, folder persistence
**Out:** Drag-to-reorder, spring-loaded folders, Archive section, Recently Deleted (all future phases)

## Files to modify

| File | Change |
|------|--------|
| `desktop/.../ProjectIndex.swift` | Folder model, folderId on Project, CRUD methods, SidebarItem enum |
| `desktop/.../FolderRow.swift` | **NEW** — collapsible folder row with inline rename |
| `desktop/.../ContentView.swift` | Selection model, sidebar restructuring, folder toolbar button, notifications |
| `desktop/.../MenuCommands.swift` | File > New Folder, Project menu adaptation, Move To submenu |
| `desktop/.../BridgeHandler.swift` | Add `selectedFolderName` property |
| `bristlenose/locales/*/desktop.json` | New folder-related locale keys (6 files) |

## Step 1 — Data model (`ProjectIndex.swift`)

Promote `FolderStub` → public `Folder`:

```swift
struct Folder: Identifiable, Hashable, Codable {
    var id: UUID
    var name: String
    var collapsed: Bool
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id, name, collapsed
        case createdAt = "created_at"
    }
}
```

Backward compat: `collapsed` and `createdAt` may be absent in old files — use `init(from:)` with `decodeIfPresent` defaulting to `false` / `Date()`.

Add `folderId: UUID?` to `Project` (`folder_id` in JSON). Missing key decodes as `nil`.

Add `@Published var folders: [Folder] = []`. Update `load()`/`save()` to read/write folders.

Add a `SidebarItem` enum for ordering:

```swift
enum SidebarItem: Identifiable {
    case folder(Folder)
    case project(Project)
    var id: UUID { ... }
    var createdAt: Date { ... }
}
```

Add computed `sidebarItems` — root-level projects + folders sorted by `createdAt` descending.

Add `projectsInFolder(_:)` — projects with matching `folderId`, sorted by `createdAt` descending.

Folder CRUD methods:
- `addFolder(name:) -> Folder` — unique name, insert, save
- `removeFolder(id:)` — move contained projects to root, remove folder, save
- `renameFolder(id:newName:)` — unique name, save
- `setFolderCollapsed(id:collapsed:)` — flip, save
- `moveProject(projectId:toFolder:)` — set `folderId`, save

Add `uniqueFolderName(_:excluding:)` mirroring existing `uniqueName`.

## Step 2 — FolderRow (`FolderRow.swift`, new file)

Same pattern as `ProjectRow.swift`: Label with `folder.fill` icon, inline rename via `isRenaming` binding, `onRename`/`onDelete` callbacks, commit on Return, cancel on Escape.

## Step 3 — Selection model & sidebar (`ContentView.swift`)

Replace `@State private var selectedID: UUID?` with:

```swift
enum SidebarSelection: Hashable {
    case project(UUID)
    case folder(UUID)
}
@State private var selection: SidebarSelection?
```

Derive `selectedProject` and `selectedFolder` as computed properties from `selection`.

`@AppStorage("selectedProjectID")` persists only project UUIDs — folder selections are not persisted (folders don't open a report).

Add `@State private var renamingFolderID: UUID?`.

### Sidebar body

Replace flat `ForEach(projectIndex.projects)` with:

```swift
ForEach(projectIndex.sidebarItems) { item in
    switch item {
    case .folder(let folder):
        DisclosureGroup(isExpanded: /* !folder.collapsed binding */) {
            ForEach(projectIndex.projectsInFolder(folder.id)) { project in
                ProjectRow(...)
                    .tag(SidebarSelection.project(project.id))
                    .contextMenu { /* project menu + Move To */ }
            }
        } label: {
            FolderRow(...)
                .tag(SidebarSelection.folder(folder.id))
                .contextMenu { /* Rename Folder, Archive (disabled), Delete Folder */ }
        }
    case .project(let project):
        ProjectRow(...)
            .tag(SidebarSelection.project(project.id))
            .contextMenu { /* existing + Move To submenu */ }
    }
}
```

If `DisclosureGroup` inside `List(selection:)` doesn't propagate `.tag()` on the label (SwiftUI limitation), fall back to manual expand/collapse: a `Button` row that toggles `collapsed`, with a conditional `ForEach` underneath.

### Context menus

**Project context menu** (both root and in-folder) adds "Move to" submenu:

```swift
Menu(i18n.t("desktop.menu.project.moveTo")) {
    Button(i18n.t("desktop.menu.project.noFolder")) { moveProject(..., toFolder: nil) }
        .disabled(project.folderId == nil)
    Divider()
    ForEach(projectIndex.folders) { folder in
        Button(folder.name) { moveProject(..., toFolder: folder.id) }
            .disabled(project.folderId == folder.id)
    }
}
```

**Folder context menu:** Rename Folder, Archive Folder (disabled), Delete Folder.

### Toolbar

Enable `folder.badge.plus` button — wire to `createNewFolder()`.

### onChange handler

Update `onChange(of: selection)`: only start serve for `.project(id)` case. For `.folder(id)`, stop serve and clear `bridgeHandler.selectedProjectPath`. Set `bridgeHandler.selectedFolderName` for menu dimming.

### Notification receivers

Add receivers for `.createNewFolder`, `.renameSelectedFolder`, `.deleteSelectedFolder`, `.moveSelectedProject`.

## Step 4 — BridgeHandler

Add `@Published var selectedFolderName: String = ""`. Set by `ContentView` on selection change. Reset in `reset()`.

## Step 5 — Menu changes (`MenuCommands.swift`)

### File menu

Add after "New Project":
```swift
Button(i18n.t("desktop.menu.file.newFolder")) { post(.createNewFolder) }
    .keyboardShortcut("n", modifiers: [.command, .shift])
```

### Project menu

Make adaptive: rename/delete labels change based on `hasFolder` vs `hasProject`. Show "Move to" submenu (disabled when folder selected). Archive Folder disabled (Phase 5).

```
When project selected:    Show in Finder, Rename, Move To▶, Re-Analyse⊘, Archive⊘, ─, Delete
When folder selected:     Rename Folder, Archive Folder⊘, ─, Delete Folder
When nothing selected:    all dimmed
```

## Step 6 — Locale keys

Add to `desktop.json` in all 6 locales (en, es, fr, de, ko, ja):

```json
"menu": {
  "file": {
    "newFolder": "New Folder…"
  },
  "project": {
    "moveTo": "Move to",
    "noFolder": "No Folder"
  },
  "folder": {
    "rename": "Rename Folder",
    "archive": "Archive Folder",
    "delete": "Delete Folder…"
  }
}
```

`chrome.newFolder` already exists.

## Implementation order

1. `ProjectIndex.swift` — data model (self-contained, no UI breakage)
2. `FolderRow.swift` — new file
3. `BridgeHandler.swift` — add `selectedFolderName`
4. Notification names in `ProjectIndex.swift`
5. `ContentView.swift` — selection model, sidebar body, notifications, toolbar
6. `MenuCommands.swift` — File menu, Project menu adaptation
7. Locale files — all 6 languages
8. Build verification + manual QA

## Verification

```bash
cd desktop/Bristlenose && xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"
```

Manual QA:
1. File > New Folder (⇧⌘N) — creates folder with inline rename
2. Sidebar `folder.badge.plus` button — same
3. Folder shows disclosure triangle, collapses/expands
4. Right-click project > Move to > folder name — moves project into folder
5. Project menu > Move to > folder name — same
6. Move to > No Folder — moves project back to root
7. Right-click folder — Rename Folder, Delete Folder work; Archive Folder disabled
8. Delete folder — projects inside move to top level, folder removed
9. Folder collapsed state persists across app relaunch
10. Project menu shows folder items when folder selected, project items when project selected
11. Old `projects.json` (no folders) loads without crash
12. ⌘⌫ still deletes selected project (and folder when folder selected)

## Gotchas

- `DisclosureGroup` label `.tag()` propagation: test early. If broken, use manual collapse
- `Project.folderId` absent in old JSON: `UUID?` decodes as `nil` when key missing — safe
- `Folder.collapsed`/`createdAt` absent in old JSON: need `decodeIfPresent` with defaults
- Folder names have their own uniqueness namespace (separate from project names)
- Never construct filesystem paths from folder names (display-only)
- `Menu` (submenu) inside `CommandMenu` should render as native submenu on macOS — verify
