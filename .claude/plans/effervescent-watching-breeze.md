# Phase 1 — Multi-Project Sidebar (MVP)

## Context

The desktop app currently uses a hardcoded `ProjectStub` array with 3 placeholder projects. This task replaces it with a real `ProjectIndex` model backed by `projects.json` on disk, giving users persistent project management with create, rename, and delete.

Scope is strictly Phase 1 from `docs/design-project-sidebar.md`: basic CRUD, no folders, no drag-from-Finder, no context menus, no archive, no bookmarks.

## Step 1 — Create `ProjectIndex.swift` (model)

**New file:** `desktop/Bristlenose/Bristlenose/ProjectIndex.swift`

`Project` struct (Codable, Identifiable, Hashable):
- `id: UUID`
- `name: String`
- `path: String`
- `createdAt: Date`
- `lastOpened: Date?`

`ProjectIndex` class (ObservableObject):
- `@Published var projects: [Project] = []`
- Storage: `~/Library/Application Support/Bristlenose/projects.json` via `FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)`
- `init()` — load from disk, create empty `{ "version": "1.0", "folders": [], "projects": [] }` if missing
- `addProject(name:path:) -> Project` — append, save, return new project
- `removeProject(id:)` — remove by ID, save
- `renameProject(id:newName:)` — update name, save
- `updateLastOpened(id:)` — stamp current date, save
- Private `load()` / `save()` methods with JSON encoding/decoding
- `CodingKeys` to map `createdAt`/`lastOpened` to snake_case JSON (`created_at`/`last_opened`) matching the schema in `docs/design-multi-project.md`

## Step 2 — Create `ProjectRow.swift` (sidebar row)

**New file:** `desktop/Bristlenose/Bristlenose/ProjectRow.swift`

A SwiftUI View showing a single project in the sidebar:
- Default state: `Text(project.name)` with system selection highlight
- Inline rename state: `TextField` with the project name, pre-selected
  - Commit on Return (`.onSubmit`) — calls `projectIndex.renameProject()`
  - Cancel on Escape (`.onExitCommand`) — reverts to original name
  - `@FocusState` to auto-focus the text field when rename activates
- Rename triggered by:
  - Slow double-click (timer-based: first click selects, second click within 0.3–1.0s window activates rename)
  - External trigger via `isRenaming` binding (for menu-driven rename)
- No folder icon — plain text, system selection

## Step 3 — Update `BristlenoseApp.swift`

- Add `@StateObject private var projectIndex = ProjectIndex()`
- Pass to ContentView: `.environmentObject(projectIndex)`
- Pass to MenuCommands: `MenuCommands(bridgeHandler: bridgeHandler, serveManager: serveManager, i18n: i18n, projectIndex: projectIndex)`

## Step 4 — Update `ContentView.swift`

**Remove:** `ProjectStub` struct, hardcoded `projects` array

**Add:** `@EnvironmentObject var projectIndex: ProjectIndex`

**Sidebar rewrite:**
- Section header "Projects" with `[+]` button (SF Symbol `plus.circle` in a `Button`, positioned in the section header)
- `List` bound to `projectIndex.projects` with selection
- Each row is a `ProjectRow`
- `[+]` button creates a new project via `projectIndex.addProject(name: "New Project", path: "")` and immediately puts it in inline rename mode
- Track which project is being renamed via `@State private var renamingProjectID: UUID?`

**Selection model:**
- `@State private var selectedProject: Project?` (was `ProjectStub?`)
- `@AppStorage("selectedProjectPath")` — restore on relaunch by matching path in `projectIndex.projects`
- `.onChange(of: selectedProject)` — existing logic stays (starts serve), plus call `projectIndex.updateLastOpened(id:)`

**Detail pane — empty new project state:**
- When `selectedProject?.path.isEmpty == true`: show `ContentUnavailableView("Drag interviews here to get started", systemImage: "square.and.arrow.down")`

**Notification listener for menu-driven rename:**
- `.onReceive(NotificationCenter.default.publisher(for: .renameSelectedProject))` sets `renamingProjectID = selectedProject?.id`

## Step 5 — Update `MenuCommands.swift`

**Add `projectIndex` parameter** to `MenuCommands` and `ProjectMenuContent`.

**File menu — New Project (Cmd+N):**
- Currently dispatches to bridge (`bridgeHandler.menuAction("newProject")`). Replace with native: post `Notification.Name.createNewProject` → ContentView handles it (creates project + enters rename mode)

**Project menu rewire:**
- **Show in Finder (Shift+Cmd+R):** Native `NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: path)`. Disabled when no project selected or path is empty
- **Rename:** Post `Notification.Name.renameSelectedProject`. Disabled when no project selected
- **Delete:** Call `projectIndex.removeProject(id:)` + clear selection if it was the deleted project. Disabled when no project selected
- **Re-Analyse, Archive:** Keep disabled (future phases) — leave existing bridge dispatch but add `.disabled(true)` explicitly

Pass `selectedProjectPath` from ContentView to menus via `bridgeHandler` (it already has state access) or via a new `@ObservedObject` on ProjectIndex. Since `ProjectMenuContent` needs to know the selected project's path for Show in Finder, the cleanest approach is passing `projectIndex` as `@ObservedObject` and adding a `selectedProjectID: UUID?` published property on `BridgeHandler` (or use a dedicated `Binding` forwarded from ContentView — but Commands can't receive Bindings).

**Simplest approach:** Add `@Published var selectedProjectPath: String = ""` to `BridgeHandler` (it already has other published state). ContentView's `.onChange(of: selectedProject)` updates it. ProjectMenuContent reads it for Show in Finder and disable guards.

## Step 6 — Notification names

Add to an extension (can go in `ProjectIndex.swift`):
```swift
extension Notification.Name {
    static let createNewProject = Notification.Name("bristlenoseCreateNewProject")
    static let renameSelectedProject = Notification.Name("bristlenoseRenameSelectedProject")
}
```

## Files changed

| File | Action |
|------|--------|
| `desktop/.../ProjectIndex.swift` | **New** — model + persistence |
| `desktop/.../ProjectRow.swift` | **New** — sidebar row with inline rename |
| `desktop/.../BristlenoseApp.swift` | Add ProjectIndex @StateObject + pass down |
| `desktop/.../ContentView.swift` | Remove ProjectStub, new sidebar, wire ProjectIndex |
| `desktop/.../MenuCommands.swift` | Wire native Project menu actions |
| `desktop/.../BridgeHandler.swift` | Add `selectedProjectPath` published property |

## Verification

```bash
cd desktop/Bristlenose && xcodebuild build -scheme Bristlenose -configuration Debug -destination "platform=macOS"
```

Then manual QA:
1. Launch app — sidebar shows "Projects" header with [+] button, empty list
2. Click [+] — new row appears in inline edit mode with "New Project" selected
3. Type a name, press Return — project created, persists in `~/Library/Application Support/Bristlenose/projects.json`
4. Slow double-click the name — inline rename activates
5. Press Escape during rename — reverts to original name
6. Project > Show in Finder — disabled (no path yet for a new empty project)
7. Project > Delete — removes from sidebar and from JSON
8. Quit and relaunch — projects persist, last-selected project re-selected
9. All Project menu items disabled when nothing selected
10. Cmd+N creates a new project (same as [+] button)
