import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "project-index")

// MARK: - Location model

/// Where a project lives on disk — auto-detected from the path on creation.
/// Persisted to `projects.json` for availability detection when volumes unmount.
struct Location: Codable, Hashable {
    enum LocationType: String, Codable {
        case local, volume, network, cloud
    }

    var type: LocationType
    var volumeName: String?
    var volumeRelativePath: String?
    var displayHint: String

    enum CodingKeys: String, CodingKey {
        case type
        case volumeName = "volume_name"
        case volumeRelativePath = "volume_relative_path"
        case displayHint = "display_hint"
    }
}

// MARK: - Project model

/// A project entry in the sidebar — a logical container referencing files on disk.
///
/// `path` is the project's home directory (pipeline output goes here).
/// `inputFiles` optionally restricts which files the pipeline processes:
/// - nil → scan the entire directory (folder-drop or legacy projects)
/// - populated → process only these files (file-drop projects)
///
/// This follows the Logic Pro / Final Cut precedent: the project is a logical
/// thing, the files are references. See `docs/design-project-sidebar.md`.
struct Project: Identifiable, Hashable, Codable {
    /// Per-project schema version. `0` means a pre-v1 record (missing on decode);
    /// migration on load upgrades to `1`. Bump in lockstep with breaking schema
    /// changes; always decode-with-default so older readers don't crash on
    /// newer files.
    static let currentSchemaVersion: Int = 1

    var id: UUID
    var name: String
    var path: String
    /// The path last observed to resolve successfully. Display fallback when
    /// the live path has drifted but the bookmark still resolves to a different
    /// URL — keeps the sidebar truthful while the bookmark re-anchors.
    var lastSeenPath: String
    /// Stable filesystem identity captured from `URLResourceKey.fileResourceIdentifierKey`,
    /// base64-encoded. Used by drag-onto-existing dedupe (#11) and lazy-captured
    /// on first availability resolution if not present.
    var resourceIdentifier: String?
    var schemaVersion: Int
    var inputFiles: [String]?
    var location: Location?
    var bookmarkData: Data?
    var icon: String?
    var folderId: UUID?
    var position: Int
    var createdAt: Date
    var lastOpened: Date?
    /// Timestamp of the last successful `bristlenose run` against this project.
    /// Sourced from the manifest's final-stage completion time; mirrored here
    /// so sidebar rows can show "Analysed 2 hours ago" without re-reading the
    /// manifest on every render. Reactive pipeline state lives in
    /// `PipelineRunner.state[project.id]`, not on this model.
    var lastPipelineRunAt: Date?
    /// Whether agents may read this project (Turn On Agent Access). Host-side
    /// — in `projects.json`, NOT the per-project DB: the DB is only readable
    /// while *that* project's serve runs, so a DB flag makes "on, but not
    /// open" unrenderable, and that is a badge state the design needs
    /// (`docs/design-mcp-extension.md` §3.6a). A permission, not a
    /// connection — turning it on with no agent installed succeeds.
    /// `ServeManager.syncHandshake()` reads it via `agentAccessResolver`.
    var agentAccess: Bool
    /// The lens this project was last left on (`Tab.rawValue`), restored when a
    /// window opens on it. Host-side, in `projects.json`, deliberately **not**
    /// inside the researcher's project folder: this is window management, not
    /// study data, and it has no business travelling with the study to a
    /// client's Drive. See `docs/design-workspace.md` §"What a window opens
    /// onto" for why a wrong restore costs a click and a wrong reset can cost a
    /// search.
    var lastLens: String?
    /// Where in that lens — a heading id on Quotes/Codebook, a session id on
    /// Sessions, nil elsewhere. Meaningless without `lastLens`, which is why
    /// `LensAnchor` interprets the pair rather than this alone.
    var lastAnchor: String?

    enum CodingKeys: String, CodingKey {
        case id, name, path, icon, position
        case schemaVersion = "schema_version"
        case lastSeenPath = "last_seen_path"
        case resourceIdentifier = "resource_identifier"
        case inputFiles = "input_files"
        case location
        case bookmarkData = "bookmark_data"
        case folderId = "folder_id"
        case createdAt = "created_at"
        case lastOpened = "last_opened"
        case lastPipelineRunAt = "last_pipeline_run_at"
        case agentAccess = "agent_access"
        case lastLens = "last_lens"
        case lastAnchor = "last_anchor"
    }

    // Custom coding for bookmarkData (Base64 string in JSON instead of byte array).

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        path = try container.decode(String.self, forKey: .path)
        // Pre-v1 records have no schemaVersion; decode-with-default flags them
        // for migration on load. `lastSeenPath` defaults to `path` for the same
        // reason — the load-time migration block fills it in for real.
        schemaVersion = try container.decodeIfPresent(Int.self, forKey: .schemaVersion) ?? 0
        lastSeenPath = try container.decodeIfPresent(String.self, forKey: .lastSeenPath) ?? path
        resourceIdentifier = try container.decodeIfPresent(String.self, forKey: .resourceIdentifier)
        inputFiles = try container.decodeIfPresent([String].self, forKey: .inputFiles)
        icon = try container.decodeIfPresent(String.self, forKey: .icon)
        location = try container.decodeIfPresent(Location.self, forKey: .location)
        if let b64 = try container.decodeIfPresent(String.self, forKey: .bookmarkData) {
            bookmarkData = Data(base64Encoded: b64)
        } else {
            bookmarkData = nil
        }
        folderId = try container.decodeIfPresent(UUID.self, forKey: .folderId)
        position = try container.decodeIfPresent(Int.self, forKey: .position) ?? 0
        createdAt = try container.decode(Date.self, forKey: .createdAt)
        lastOpened = try container.decodeIfPresent(Date.self, forKey: .lastOpened)
        lastPipelineRunAt = try container.decodeIfPresent(Date.self, forKey: .lastPipelineRunAt)
        // Decode-with-default like `position`/`collapsed` — older projects.json
        // files have no agent_access key and must keep parsing. Default OFF:
        // exposure is an explicit act (Option B, design §3.3).
        agentAccess = try container.decodeIfPresent(Bool.self, forKey: .agentAccess) ?? false
        // Absent for every project that predates lens memory, and for one never
        // opened. Both mean the same thing and want the same answer: land on
        // the Project dashboard, which is exactly the never-opened case the
        // design says the dashboard is right for.
        lastLens = try container.decodeIfPresent(String.self, forKey: .lastLens)
        lastAnchor = try container.decodeIfPresent(String.self, forKey: .lastAnchor)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(path, forKey: .path)
        try container.encode(schemaVersion, forKey: .schemaVersion)
        try container.encode(lastSeenPath, forKey: .lastSeenPath)
        try container.encodeIfPresent(resourceIdentifier, forKey: .resourceIdentifier)
        try container.encodeIfPresent(inputFiles, forKey: .inputFiles)
        try container.encodeIfPresent(icon, forKey: .icon)
        try container.encodeIfPresent(location, forKey: .location)
        try container.encodeIfPresent(bookmarkData?.base64EncodedString(), forKey: .bookmarkData)
        try container.encodeIfPresent(folderId, forKey: .folderId)
        try container.encode(position, forKey: .position)
        try container.encode(createdAt, forKey: .createdAt)
        try container.encodeIfPresent(lastOpened, forKey: .lastOpened)
        try container.encodeIfPresent(lastPipelineRunAt, forKey: .lastPipelineRunAt)
        try container.encode(agentAccess, forKey: .agentAccess)
        try container.encodeIfPresent(lastLens, forKey: .lastLens)
        try container.encodeIfPresent(lastAnchor, forKey: .lastAnchor)
    }

    init(id: UUID, name: String, path: String, inputFiles: [String]? = nil,
         icon: String? = nil, location: Location? = nil, bookmarkData: Data? = nil,
         folderId: UUID? = nil, position: Int = 0, createdAt: Date = Date(),
         lastOpened: Date? = nil, lastPipelineRunAt: Date? = nil,
         lastSeenPath: String? = nil, resourceIdentifier: String? = nil,
         schemaVersion: Int = Project.currentSchemaVersion,
         agentAccess: Bool = false, lastLens: String? = nil,
         lastAnchor: String? = nil) {
        self.id = id
        self.name = name
        self.path = path
        self.lastSeenPath = lastSeenPath ?? path
        self.resourceIdentifier = resourceIdentifier
        self.schemaVersion = schemaVersion
        self.inputFiles = inputFiles
        self.icon = icon
        self.location = location
        self.bookmarkData = bookmarkData
        self.folderId = folderId
        self.position = position
        self.createdAt = createdAt
        self.lastOpened = lastOpened
        self.lastPipelineRunAt = lastPipelineRunAt
        self.agentAccess = agentAccess
        self.lastLens = lastLens
        self.lastAnchor = lastAnchor
    }

    /// Whether the project directory is currently accessible on disk.
    /// Thin convenience wrapper around `availability` (defined in
    /// `ProjectAvailability.swift`). Prefer `availability` for new code that
    /// needs to discriminate cases.
    var isAvailable: Bool { availability.isReady }
}

// MARK: - Folder model

/// A one-level-deep folder for grouping projects in the sidebar.
/// Folder names are display-only — never construct filesystem paths from them.
struct Folder: Identifiable, Hashable, Codable {
    var id: UUID
    var name: String
    var collapsed: Bool
    var position: Int
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id, name, collapsed, position
        case createdAt = "created_at"
    }

    /// Custom decoder for backward compatibility — old `projects.json` files
    /// have FolderStub shapes with only `id` and `name`.
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        collapsed = try container.decodeIfPresent(Bool.self, forKey: .collapsed) ?? false
        position = try container.decodeIfPresent(Int.self, forKey: .position) ?? 0
        createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt) ?? Date()
    }

    init(id: UUID, name: String, collapsed: Bool = false, position: Int = 0, createdAt: Date = Date()) {
        self.id = id
        self.name = name
        self.collapsed = collapsed
        self.position = position
        self.createdAt = createdAt
    }
}

// MARK: - Sidebar item (ordering)

/// Unified type for sorting folders and root-level projects together.
enum SidebarItem: Identifiable {
    case folder(Folder)
    case project(Project)

    var id: UUID {
        switch self {
        case .folder(let f): f.id
        case .project(let p): p.id
        }
    }

    var position: Int {
        switch self {
        case .folder(let f): f.position
        case .project(let p): p.position
        }
    }

    var createdAt: Date {
        switch self {
        case .folder(let f): f.createdAt
        case .project(let p): p.createdAt
        }
    }
}

// MARK: - Sidebar selection

/// What is selected in the sidebar — a project or a folder.
/// Used as the `List(selection:)` tag type.
enum SidebarSelection: Hashable {
    case project(UUID)
    case folder(UUID)
}

// MARK: - Notification names

extension Notification.Name {
    /// Posted by File ▸ Import ▸ <platform>… — opens the cloud-import window
    /// against that platform's live APIs, pre-selecting the current project as
    /// the destination. `object` carries the `CloudPlatform`.
    static let openCloudImport = Notification.Name("bristlenoseOpenCloudImport")

    /// Posted by Diagnostics ▸ Google Meet Import — opens the same window
    /// against fixtures. `object` carries the `CloudImportScenario`.
    ///
    /// A separate notification rather than a parameter on the one above, so
    /// that no code path can reach the fixture source by passing a wrong or
    /// defaulted argument: the only way in is a menu item that says so.
    static let openCloudImportFixture = Notification.Name("bristlenoseOpenCloudImportFixture")

    // NOTE: `toggleProjectsSidebar` was removed 28 Jul 2026, and the whole
    // menu-bar family followed on 16 Aug 2026 — New Project, New Folder, Add
    // Files, Welcome, Show Transcripts, Rename ×2, Delete Folder, Move To,
    // Locate, Stop, Remove from Sidebar, AI & Privacy, Send to Miro, Switch
    // Session. Each was a broadcast every open window answered, so ⌘N created a
    // project per window and Rename opened an editor in all of them. They are
    // now `WindowCommand` cases routed to the key window — see
    // `WindowCommandFocus.swift`, gated by `desktop/scripts/check-menu-routing.sh`.
    //
    // The two above survive because they open a dedicated `Window` scene rather
    // than reaching into a project window, so there is exactly one receiver by
    // construction.
}

// MARK: - Project index (persistence)

/// Manages the list of projects persisted to `projects.json` in Application Support.
///
/// Storage location: `~/Library/Application Support/Bristlenose/projects.json`
/// Schema follows `docs/design-multi-project.md` §1 — Phase 1 uses a subset
/// (no folders, no location, no archived/position fields).
@MainActor
final class ProjectIndex: ObservableObject {

    @Published var projects: [Project] = []
    @Published var folders: [Folder] = []
    /// Per-project data state — unanalysed files, missing files, and
    /// session count — published by `ProjectFolderWatcher`. Absent entry =
    /// no watcher running (project not ready, or watcher not yet started).
    /// `.empty` value = watcher running, nothing to show.
    ///
    /// **F14 policy:** for projects that have never been analysed
    /// (`lastPipelineRunAt == nil`), `newFiles` is zeroed before publishing —
    /// "unanalysed" only makes sense once an analysis baseline exists.
    /// `sessionCount` and `missingFiles` are unaffected.
    @Published var unanalysed: [UUID: UnanalysedState] = [:]

    /// Transient (not persisted) one-shot signal: the id of a just-created
    /// project that was auto-assigned a random icon and should play the reveal
    /// animation once. The sidebar row consumes it via `consumeIconReveal`.
    @Published var pendingIconReveal: UUID?

    /// Transient (not persisted) one-shot signal: the id of a project OR folder
    /// that should begin inline rename the next time the sidebar renders. Set by
    /// New Folder (rename-on-create), the menu-bar "Rename …" items, and the
    /// row context menu. The AppKit outline consumes it via `consumeRename` and
    /// opens the row's editable name field. Mirrors `pendingIconReveal`.
    @Published var pendingRename: UUID?

    /// Transient (not persisted) one-shot signal: what the next project window
    /// to appear should select. Written only by `NewItemFallback` — the
    /// app-level half of New Project / New Folder, which runs when no project
    /// window is frontmost and so has nowhere to put the selection yet.
    /// `ContentView` consumes it via `consumePendingSelection`. Sibling of
    /// `pendingRename`, and set alongside it: the pair is "select this, then
    /// open its name for editing".
    @Published var pendingSelection: SidebarSelection?

    /// Bookmark leases held while a project is `.ready`. Released on
    /// transition to `.cantFind` / `.inCloud` or when the project is removed.
    /// Co-terminous with the watcher in `watchers`.
    private var leases: [UUID: ProjectBookmarkLease] = [:]
    /// Folder watchers, one per `.ready` project. Caps at ~50 to stay
    /// well under filecoordinationd's practical ceiling.
    private var watchers: [UUID: ProjectFolderWatcher] = [:]
    static let maxConcurrentWatchers: Int = 50

    private let fileURL: URL

    /// Create a project index backed by `projects.json` in Application Support.
    /// Pass a custom `fileURL` for testing (temp directory) to avoid touching
    /// the user's real project list.
    init(fileURL: URL? = nil) {
        if let fileURL {
            self.fileURL = fileURL
        } else {
            let appSupport = FileManager.default.urls(
                for: .applicationSupportDirectory,
                in: .userDomainMask
            ).first!.appendingPathComponent("Bristlenose")

            // Create the directory if it doesn't exist.
            try? FileManager.default.createDirectory(
                at: appSupport, withIntermediateDirectories: true
            )

            self.fileURL = appSupport.appendingPathComponent("projects.json")
        }
        load()
        syncWatchers()
    }

    // MARK: - CRUD

    /// Create a new project with the given name and path.
    /// The name is de-duplicated if it already exists (appends " 2", " 3", etc.).
    /// `inputFiles` optionally restricts which files the pipeline processes
    /// (nil = scan the whole directory).
    /// Returns the new project so the caller can select it.
    @discardableResult
    func addProject(name: String, path: String, inputFiles: [String]? = nil,
                    intoFolder folderID: UUID? = nil) -> Project {
        let finalName = uniqueName(name, excluding: nil)
        let location = path.isEmpty ? nil : Self.detectLocation(for: path)
        let bookmark = Self.createBookmark(for: path)
        let resourceID = Self.captureResourceIdentifier(for: path)
        // New items land at position 0 within their scope (root or folder);
        // push existing same-scope items down by 1. Folder positions are a
        // root-scope concept, so bump them only when inserting at root —
        // intoFolder insertions don't shift them.
        if let folderID {
            for i in projects.indices where projects[i].folderId == folderID {
                projects[i].position += 1
            }
        } else {
            for i in projects.indices where projects[i].folderId == nil {
                projects[i].position += 1
            }
            for i in folders.indices {
                folders[i].position += 1
            }
        }
        // Auto-assign a distinctive identity icon (seeded off the name,
        // collision-avoided against icons already in use). Nil when the
        // Appearance toggle is off — the project then keeps the default ring.
        let assignedIcon = RandomProjectIcon.iconForNewProject(
            name: finalName,
            existing: Set(projects.compactMap(\.icon))
        )
        let project = Project(
            id: UUID(),
            name: finalName,
            path: path,
            inputFiles: inputFiles,
            icon: assignedIcon,
            location: location,
            bookmarkData: bookmark,
            folderId: folderID,
            position: 0,
            createdAt: Date(),
            lastOpened: nil,
            lastSeenPath: path,
            resourceIdentifier: resourceID,
            schemaVersion: Project.currentSchemaVersion
        )
        projects.insert(project, at: 0)
        save()
        syncWatchers()
        // Flag the just-assigned icon for its one-shot reveal. Only when an icon
        // was actually assigned — an opted-out project (nil) plays nothing.
        if assignedIcon != nil { pendingIconReveal = project.id }
        return project
    }

    /// Clear the one-shot icon-reveal trigger after the row has played it.
    func consumeIconReveal(_ id: UUID) {
        if pendingIconReveal == id { pendingIconReveal = nil }
    }

    /// Clear the one-shot rename trigger after the row has entered inline edit.
    func consumeRename(_ id: UUID) {
        if pendingRename == id { pendingRename = nil }
    }

    /// Take the staged selection, if there is one, clearing it. Returning the
    /// value rather than exposing "read then clear" at the call site keeps this
    /// one-shot even if a second window appears in the same run loop.
    func consumePendingSelection() -> SidebarSelection? {
        defer { pendingSelection = nil }
        return pendingSelection
    }

    /// Remove a project by ID.
    func removeProject(id: UUID) {
        releaseLeaseAndWatcher(for: id)
        projects.removeAll { $0.id == id }
        save()
    }

    /// Re-insert a previously-removed project, preserving its prior folder
    /// membership and position. Other items in the same scope shift to make
    /// room. Used by `UndoableRemovalStore` for Undo of "Remove from Sidebar".
    /// No-op if a project with the same ID already exists (idempotent against
    /// double-undo / race with manifest scans).
    func restoreProject(_ project: Project, folderId: UUID?, position: Int) {
        guard !projects.contains(where: { $0.id == project.id }) else { return }
        var restored = project
        restored.folderId = folderId
        restored.position = position
        // Shift items in the same scope at or after `position` down by 1.
        if folderId == nil {
            for i in projects.indices where projects[i].folderId == nil
                && projects[i].position >= position {
                projects[i].position += 1
            }
            for i in folders.indices where folders[i].position >= position {
                folders[i].position += 1
            }
        } else {
            for i in projects.indices where projects[i].folderId == folderId
                && projects[i].position >= position {
                projects[i].position += 1
            }
        }
        projects.append(restored)
        save()
        syncWatchers()
    }

    /// Rename a project by ID.
    /// The name is de-duplicated if it clashes with another project.
    func renameProject(id: UUID, newName: String) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        projects[index].name = uniqueName(newName, excluding: id)
        save()
    }

    /// Set the SF Symbol icon for a project.
    /// Pass nil to reset to the default icon.
    func setIcon(id: UUID, icon: String?) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        projects[index].icon = icon
        save()
    }

    /// Turn Agent Access on or off for a project (the §3.6a verb-swap menu
    /// item's model half). A permission, not a connection — succeeds with no
    /// agent installed. Posts `.bristlenoseAgentAccessChanged` so
    /// `ServeManager` can write or delete the MCP handshake for the fronted
    /// project without this store knowing about serve lifecycles.
    func setAgentAccess(id: UUID, enabled: Bool) {
        guard let index = projects.firstIndex(where: { $0.id == id }),
              projects[index].agentAccess != enabled else { return }
        projects[index].agentAccess = enabled
        save()
        NotificationCenter.default.post(name: .bristlenoseAgentAccessChanged, object: nil)
    }

    /// Whether the project at `path` has agent access on. Path-standardised
    /// (same rule as `MCPTokenStore.accountKey` / `AgentActivity.samePath`)
    /// because `ServeManager.currentProjectPath` holds the spawn-time spelling
    /// while bookmark healing can respell `project.path`.
    func agentAccess(forPath path: String) -> Bool {
        projects.first { AgentActivity.samePath($0.path, path) }?.agentAccess ?? false
    }

    /// Stamp the current date as last-opened.
    /// Remember the lens a project was left on, for the next window that opens
    /// it. Writes only on a real change — the lens is reported on every route
    /// change, and `projects.json` is not worth rewriting to store what it
    /// already says.
    func setLastLens(id: UUID, lens: String) {
        guard let index = projects.firstIndex(where: { $0.id == id }),
              projects[index].lastLens != lens else { return }
        projects[index].lastLens = lens
        save()
    }

    /// Remember where in the lens. Same write-only-on-change rule as
    /// `setLastLens`: the anchor is reported on every scroll-settle, and
    /// `projects.json` is not worth rewriting to store what it already says.
    func setLastAnchor(id: UUID, anchor: String?) {
        guard let index = projects.firstIndex(where: { $0.id == id }),
              projects[index].lastAnchor != anchor else { return }
        projects[index].lastAnchor = anchor
        save()
    }

    func updateLastOpened(id: UUID) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        projects[index].lastOpened = Date()
        save()
    }

    /// Stamp the moment a pipeline run finished, whatever its outcome.
    ///
    /// **This field is deliberately write-only today — do not delete it as
    /// unused.** Its sole job is to open the F14 drift gate in
    /// `handleWatcherUpdate`, which suppresses the `+N unanalysed` delta until a
    /// project has an analysis baseline. It is *not* rendered anywhere: the
    /// sidebar's bare-date subtitle was retired on 29 Jul 2026 (Schema E — a
    /// clean row shows no status line at all; see
    /// `docs/design-desktop-project-status.md` §"Schema E").
    ///
    /// Before this existed the field had **no write site in any build**, so both
    /// the date *and* the drift delta were structurally unreachable — the delta
    /// silently, because the gate below could never open.
    ///
    /// Two future homes are noted and neither is built: an Appearance pref
    /// restoring the always-on status line, and a metadata block on the project
    /// dashboard lens.
    func recordPipelineRun(id: UUID, at date: Date = Date()) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        projects[index].lastPipelineRunAt = date
        save()
    }

    /// Append files to an existing project's input list.
    /// De-duplicates against files already in the project.
    func addFiles(to id: UUID, files: [String]) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        var existing = projects[index].inputFiles ?? []
        let newFiles = files.filter { !existing.contains($0) }
        guard !newFiles.isEmpty else { return }
        existing.append(contentsOf: newFiles)
        projects[index].inputFiles = existing
        save()
    }

    // MARK: - Lookup

    /// Find an existing project by its filesystem path.
    /// Used to prevent duplicates when the same folder is dropped again.
    func findByPath(_ path: String) -> Project? {
        projects.first { $0.path == path }
    }

    // MARK: - Folder CRUD

    /// Create a new folder. Name is de-duplicated against other folder names.
    @discardableResult
    func addFolder(name: String) -> Folder {
        let finalName = uniqueFolderName(name, excluding: nil)
        // New folders get position 0; push existing root items down.
        for i in projects.indices where projects[i].folderId == nil {
            projects[i].position += 1
        }
        for i in folders.indices {
            folders[i].position += 1
        }
        let folder = Folder(id: UUID(), name: finalName, position: 0, createdAt: Date())
        folders.insert(folder, at: 0)
        save()
        return folder
    }

    /// Remove a folder. Projects inside move to root level (folderId = nil).
    func removeFolder(id: UUID) {
        for i in projects.indices where projects[i].folderId == id {
            projects[i].folderId = nil
        }
        folders.removeAll { $0.id == id }
        save()
    }

    /// Rename a folder. De-duplicated against other folder names.
    func renameFolder(id: UUID, newName: String) {
        guard let index = folders.firstIndex(where: { $0.id == id }) else { return }
        folders[index].name = uniqueFolderName(newName, excluding: id)
        save()
    }

    /// Set folder collapsed state (persisted to projects.json).
    func setFolderCollapsed(id: UUID, collapsed: Bool) {
        guard let index = folders.firstIndex(where: { $0.id == id }) else { return }
        folders[index].collapsed = collapsed
        save()
    }

    /// Move a project into a folder (or to root if folderId is nil) — the **Move To**
    /// context menu, which names a destination but no slot, so the project appends to
    /// the end of it.
    ///
    /// Routed through `apply(_:)` so the menu path renumbers `position` exactly like a
    /// drag does. It used to set `folderId` alone, which left the project carrying its
    /// old scope's index into its new one — an arbitrary collision, and the reason rows
    /// could swap places between renders.
    func moveProject(projectId: UUID, toFolder folderId: UUID?) {
        guard projects.contains(where: { $0.id == projectId }) else { return }
        apply(DropPlan(items: [.project(projectId)], toFolder: folderId,
                       atIndex: DropRouting.append))
    }

    // MARK: - Sidebar ordering

    /// Root-level items (projects without a folder + folders), sorted by position.
    var sidebarItems: [SidebarItem] {
        let rootProjects = projects.filter { $0.folderId == nil }.map { SidebarItem.project($0) }
        let allFolders = folders.map { SidebarItem.folder($0) }
        return (rootProjects + allFolders).sorted { $0.position < $1.position }
    }

    /// Projects belonging to a specific folder, sorted by position.
    func projectsInFolder(_ folderId: UUID) -> [Project] {
        projects.filter { $0.folderId == folderId }.sorted { $0.position < $1.position }
    }

    /// Apply a sidebar drag-and-drop — the single entry point for the AppKit outline's
    /// unified insertion model (`DropRouting`). Moves `plan.items` into
    /// `plan.toFolder` (`nil` = root) at `plan.atIndex`.
    ///
    /// **Root ordering is interleaved**: a folder is just another row in the root
    /// sequence, so folders and root projects share one `position` space (what
    /// `sidebarItems` already sorts). Folders themselves are root-only — one level.
    ///
    /// Every affected scope is renumbered contiguously from 0, both the destination and
    /// any scope the items left. That's load-bearing, not tidiness: `moveProject` set
    /// `folderId` and left `position` untouched, so a project dragged out of a folder
    /// carried its in-folder index into the root scope, where it collided with an
    /// unrelated row — and `sidebarItems`' sort has no tiebreak, so tied rows could
    /// swap places between renders.
    func apply(_ plan: DropPlan) {
        guard !plan.items.isEmpty else { return }
        let movedIDs = plan.items.map(\.id)
        let movedSet = Set(movedIDs)

        // Snapshot scopes BEFORE re-parenting — `plan.atIndex` is expressed in the
        // destination's pre-move coordinates (the insertion line the user saw).
        let destinationBefore: [UUID] = plan.toFolder
            .map { projectsInFolder($0).map(\.id) } ?? sidebarItems.map(\.id)
        let rootBefore: [UUID] = sidebarItems.map(\.id)

        // Scopes losing an item, which therefore need renumbering too. Only projects
        // can change scope (a folder always lives at root).
        var sourceFolders = Set<UUID>()
        var sourceIncludesRoot = false
        for item in plan.items {
            switch item {
            case .folder:
                sourceIncludesRoot = true
            case .project(let id):
                guard let project = projects.first(where: { $0.id == id }) else { continue }
                if let parent = project.folderId {
                    sourceFolders.insert(parent)
                } else {
                    sourceIncludesRoot = true
                }
            }
        }
        var sourcesBefore: [UUID: [UUID]] = [:]
        for folder in sourceFolders { sourcesBefore[folder] = projectsInFolder(folder).map(\.id) }

        let destinationAfter = DropRouting.reordered(
            scope: destinationBefore, inserting: movedIDs, at: plan.atIndex)

        // Re-parent the moved projects (folders are root-only, so nothing to do).
        for item in plan.items {
            guard case .project(let id) = item,
                  let idx = projects.firstIndex(where: { $0.id == id }) else { continue }
            projects[idx].folderId = plan.toFolder
        }

        renumber(destinationAfter)
        for (folder, before) in sourcesBefore where folder != plan.toFolder {
            renumber(before.filter { !movedSet.contains($0) })
        }
        // Root only needs a separate pass when it's a source but not the destination —
        // otherwise `destinationAfter` already covered it.
        if sourceIncludesRoot, plan.toFolder != nil {
            renumber(rootBefore.filter { !movedSet.contains($0) })
        }
        save()
    }

    /// Assign `position = 0..<n` across one scope's ordered ids. Projects and folders
    /// share the root scope's numbering (the interleaved order), so this looks in both.
    private func renumber(_ order: [UUID]) {
        for (position, id) in order.enumerated() {
            if let idx = projects.firstIndex(where: { $0.id == id }) {
                projects[idx].position = position
            } else if let idx = folders.firstIndex(where: { $0.id == id }) {
                folders[idx].position = position
            }
        }
    }

    /// Reorder root-level sidebar items. Called from `.onMove` in the sidebar List.
    func moveSidebarItems(from source: IndexSet, to destination: Int) {
        var items = sidebarItems
        items.move(fromOffsets: source, toOffset: destination)
        // Reassign positions based on new order.
        for (newPosition, item) in items.enumerated() {
            switch item {
            case .project(let p):
                if let idx = projects.firstIndex(where: { $0.id == p.id }) {
                    projects[idx].position = newPosition
                }
            case .folder(let f):
                if let idx = folders.firstIndex(where: { $0.id == f.id }) {
                    folders[idx].position = newPosition
                }
            }
        }
        save()
    }

    /// Reorder projects within a folder. Called from `.onMove` on folder contents.
    func moveProjectsInFolder(_ folderId: UUID, from source: IndexSet, to destination: Int) {
        var items = projectsInFolder(folderId)
        items.move(fromOffsets: source, toOffset: destination)
        for (newPosition, project) in items.enumerated() {
            if let idx = projects.firstIndex(where: { $0.id == project.id }) {
                projects[idx].position = newPosition
            }
        }
        save()
    }

    // MARK: - Name uniqueness

    /// Return a unique project name by appending " 2", " 3", etc. if needed.
    /// `excluding` is the ID of the project being renamed (so it doesn't clash
    /// with its own current name).
    private func uniqueName(_ name: String, excluding: UUID?) -> String {
        let existing = Set(
            projects
                .filter { $0.id != excluding }
                .map { $0.name }
        )
        if !existing.contains(name) { return name }

        var counter = 2
        while existing.contains("\(name) \(counter)") {
            counter += 1
        }
        return "\(name) \(counter)"
    }

    /// Return a unique folder name (separate namespace from project names).
    private func uniqueFolderName(_ name: String, excluding: UUID?) -> String {
        let existing = Set(
            folders
                .filter { $0.id != excluding }
                .map { $0.name }
        )
        if !existing.contains(name) { return name }

        var counter = 2
        while existing.contains("\(name) \(counter)") {
            counter += 1
        }
        return "\(name) \(counter)"
    }

    // MARK: - Location detection

    /// Detect the storage location type from a filesystem path.
    static func detectLocation(for path: String) -> Location {
        let homeDir = UserHome.path

        // Cloud detection — check before local, since cloud paths live under /Users/
        if let label = cloudProviderLabel(for: path) {
            return Location(type: .cloud, displayHint: label)
        }

        // Volume — under /Volumes/
        if path.hasPrefix("/Volumes/") {
            let afterVolumes = path.dropFirst("/Volumes/".count)
            let components = afterVolumes.split(separator: "/", maxSplits: 1)
            let volumeName = String(components.first ?? "")
            let relativePath = components.count > 1 ? String(components[1]) : ""

            let isNetwork = isNetworkFilesystem(path: path)
            if isNetwork {
                return Location(
                    type: .network, volumeName: volumeName,
                    volumeRelativePath: relativePath,
                    displayHint: "Network drive — \(volumeName)"
                )
            }

            return Location(
                type: .volume, volumeName: volumeName,
                volumeRelativePath: relativePath,
                displayHint: "External drive — \(volumeName)"
            )
        }

        // Local — under /Users/ or home dir
        if path.hasPrefix(homeDir) || path.hasPrefix("/Users/") {
            return Location(type: .local, displayHint: "On this Mac")
        }

        return Location(type: .local, displayHint: "On this Mac")
    }

    /// The sync provider's name for a path, or nil if it is not synced.
    ///
    /// **Structural, not an allowlist.** This used to be three hardcoded
    /// prefixes (`/Library/CloudStorage/OneDrive`, `…/Dropbox`,
    /// `/Library/Mobile Documents`), which missed Google Drive and Box — and,
    /// worse, missed **`~/Documents` under Desktop & Documents sync**, so
    /// Bristlenose's own default project location was reported as "On this Mac"
    /// on any Mac with iCloud Drive turned on. The most likely sync root of all
    /// was the one the allowlist could not see.
    ///
    /// `isUbiquitousItemKey` is the OS's own File Provider flag, so it answers
    /// for every provider without naming any of them, and it reads no vendor's
    /// state — we know the protocol, never the client. The path shape is then
    /// consulted *only* to label what the flag already established.
    ///
    /// Naming the provider is the point: when a run stalls for three minutes
    /// materialising a dataless file, the researcher needs to already know this
    /// folder is Dropbox's, or the stall reads as Bristlenose being slow. It is
    /// attribution, never a warning — a project inside the client's tree is the
    /// intended configuration (`docs/design-project-storage.md` §3).
    static func cloudProviderLabel(for path: String) -> String? {
        guard !path.isEmpty else { return nil }

        // Shape first, and the order is load-bearing: it is free, it names the
        // vendor, and — critically — it still works for a path that no longer
        // exists. Projects on an unmounted or deleted cloud folder are exactly
        // the case the sidebar most needs labelled, and a filesystem probe
        // cannot answer for a path that isn't there. (Getting this order wrong
        // made a deleted Dropbox project read "On this Mac"; caught by
        // `ProjectIndexTests.detectLocation_dropboxPath` and friends, which pass
        // synthetic paths for precisely this reason.)
        //
        // `~/Library/CloudStorage/<Provider>-<account>` — the account suffix is
        // the user's, not ours to display. Unknown providers keep their own name
        // rather than being flattened to a generic "Cloud": structural, so Box
        // and Google Drive work without being enumerated.
        if let range = path.range(of: "/Library/CloudStorage/") {
            let container = String(path[range.upperBound...].split(separator: "/").first ?? "")
            let vendor = String(container.split(separator: "-").first ?? "")
            if !vendor.isEmpty { return providerNames[vendor] ?? vendor }
        }
        if path.contains("/Library/Mobile Documents") { return "iCloud Drive" }

        // Then the File Provider flag — the only way to catch a *home* folder
        // that Desktop & Documents sync has taken over. `~/Documents` has no
        // distinguishing shape at all, which is why the old three-prefix
        // allowlist reported Bristlenose's own default project location as "On
        // this Mac" on any Mac with iCloud Drive turned on.
        return isUbiquitous(path: path) ? "iCloud Drive" : nil
    }

    /// Product names, per the house rule that user-facing text uses the product
    /// the researcher recognises. Keys are the on-disk container names.
    private static let providerNames: [String: String] = [
        "GoogleDrive": "Google Drive",
        "ProtonDrive": "Proton Drive",
        "pCloudDrive": "pCloud",
    ]

    /// Whether the path is inside a File Provider (synced) domain.
    ///
    /// Walks up to the nearest folder that actually exists: `detectLocation` is
    /// called for unavailable projects too, and `resourceValues` on a missing
    /// path tells you nothing. A deleted project inside Dropbox is still a
    /// Dropbox project.
    private static func isUbiquitous(path: String) -> Bool {
        var url = URL(fileURLWithPath: path)
        let fileManager = FileManager.default
        while url.path != "/" && !url.path.isEmpty {
            if fileManager.fileExists(atPath: url.path) {
                let values = try? url.resourceValues(forKeys: [.isUbiquitousItemKey])
                return values?.isUbiquitousItem ?? false
            }
            let parent = url.deletingLastPathComponent()
            guard parent.path != url.path else { return false }
            url = parent
        }
        return false
    }

    /// Check if a path is on a network filesystem (SMB, AFP, NFS, WebDAV).
    private static func isNetworkFilesystem(path: String) -> Bool {
        var stat = statfs()
        guard statfs(path, &stat) == 0 else { return false }
        let fstype = withUnsafePointer(to: stat.f_fstypename) { ptr in
            ptr.withMemoryRebound(to: CChar.self, capacity: Int(MFSTYPENAMELEN)) {
                String(cString: $0)
            }
        }
        return ["smbfs", "afpfs", "nfs", "webdav"].contains(fstype)
    }

    // MARK: - Bookmark data

    /// Create a security-scoped bookmark for a path.
    /// Returns nil for empty paths or if bookmark creation fails.
    private static func createBookmark(for path: String) -> Data? {
        guard !path.isEmpty else { return nil }
        let url = URL(fileURLWithPath: path)
        return try? url.bookmarkData(options: .withSecurityScope)
    }

    /// Capture the stable filesystem identity for a path, base64-encoded.
    /// Returns nil if the path doesn't exist or the identifier isn't available
    /// (e.g. on filesystems that don't support `fileResourceIdentifierKey`).
    /// Used by #11 drag-onto-existing dedupe and as a defence-in-depth check
    /// against bookmark/path drift.
    static func captureResourceIdentifier(for path: String) -> String? {
        guard !path.isEmpty,
              FileManager.default.fileExists(atPath: path) else { return nil }
        let url = URL(fileURLWithPath: path)
        guard let values = try? url.resourceValues(forKeys: [.fileResourceIdentifierKey]),
              let identifier = values.fileResourceIdentifier else { return nil }
        // `fileResourceIdentifier` is documented as `(NSCopying & NSSecureCoding & NSObjectProtocol)` —
        // typically NSData on local volumes. Serialise via NSKeyedArchiver so any
        // conforming value type round-trips losslessly.
        guard let data = try? NSKeyedArchiver.archivedData(
            withRootObject: identifier as Any, requiringSecureCoding: true
        ) else { return nil }
        return data.base64EncodedString()
    }

    /// Try to resolve a path from bookmark data.
    /// Returns the resolved path if the target exists, nil otherwise.
    private static func resolveBookmark(_ data: Data) -> String? {
        var isStale = false
        guard let url = try? URL(
            resolvingBookmarkData: data,
            options: .withSecurityScope,
            relativeTo: nil,
            bookmarkDataIsStale: &isStale
        ) else { return nil }

        _ = url.startAccessingSecurityScopedResource()
        let resolvedPath = url.path
        return FileManager.default.fileExists(atPath: resolvedPath) ? resolvedPath : nil
    }

    // MARK: - Availability

    /// Re-check availability for all projects. Called on launch and volume mount/unmount.
    /// Tries bookmark resolution first, then volume-relative path fallback.
    func refreshAvailability() {
        var changed = false
        for i in projects.indices {
            let project = projects[i]
            guard !project.path.isEmpty else { continue }

            // Try bookmark resolution first
            if let bookmark = project.bookmarkData,
               let resolvedPath = Self.resolveBookmark(bookmark) {
                if resolvedPath != project.path {
                    projects[i].path = resolvedPath
                    projects[i].lastSeenPath = resolvedPath
                    projects[i].location = Self.detectLocation(for: resolvedPath)
                    projects[i].bookmarkData = Self.createBookmark(for: resolvedPath)
                    changed = true
                }
                // Lazy-capture resourceIdentifier on first successful resolution.
                if projects[i].resourceIdentifier == nil,
                   let id = Self.captureResourceIdentifier(for: resolvedPath) {
                    projects[i].resourceIdentifier = id
                    changed = true
                }
                continue
            }

            // Volume-relative path fallback for external/network drives
            if let location = project.location,
               (location.type == .volume || location.type == .network),
               let relativePath = location.volumeRelativePath, !relativePath.isEmpty {
                if let resolvedPath = Self.resolveVolumeRelativePath(relativePath) {
                    projects[i].path = resolvedPath
                    projects[i].lastSeenPath = resolvedPath
                    projects[i].location = Self.detectLocation(for: resolvedPath)
                    projects[i].bookmarkData = Self.createBookmark(for: resolvedPath)
                    if projects[i].resourceIdentifier == nil,
                       let id = Self.captureResourceIdentifier(for: resolvedPath) {
                        projects[i].resourceIdentifier = id
                    }
                    changed = true
                }
            }
        }
        if changed { save() }
        syncWatchers()
        objectWillChange.send()
    }

    // MARK: - Watcher lifecycle

    /// Bring `leases` and `watchers` into sync with current `availability`
    /// across all projects. Acquires lease + starts watcher on each `.ready`
    /// project that doesn't have one; releases lease + removes watcher on
    /// each non-`.ready` project that does. Idempotent. Safe to call from
    /// `refreshAvailability()`, project switch, or any state change.
    func syncWatchers() {
        let liveIDs = Set(projects.map(\.id))
        for stale in leases.keys where !liveIDs.contains(stale) {
            releaseLeaseAndWatcher(for: stale)
        }
        for project in projects {
            switch project.availability {
            case .ready:
                if watchers[project.id] != nil { continue }
                if watchers.count >= Self.maxConcurrentWatchers {
                    log.notice("watcher cap reached; skipping new presenter")
                    continue
                }
                guard let bookmark = project.bookmarkData else { continue }
                do {
                    let lease = try ProjectBookmarkLease(bookmarkData: bookmark)
                    leases[project.id] = lease
                    let id = project.id
                    let watcher = ProjectFolderWatcher(
                        projectID: id,
                        lease: lease,
                        initialKnownBasenames: []
                    ) { [weak self] state in
                        Task { @MainActor [weak self] in
                            self?.handleWatcherUpdate(projectID: id, state: state)
                        }
                    }
                    watchers[project.id] = watcher
                } catch {
                    log.notice("could not acquire lease for project")
                }
            case .cantFind, .inCloud:
                releaseLeaseAndWatcher(for: project.id)
            }
        }
    }

    /// Borrow the lease URL for a project. Returned URL has security scope
    /// open for the lifetime of the lease (i.e. while the project is
    /// `.ready`). Callers must not call `start/stopAccessingSecurityScopedResource`.
    /// Nil if the project is not currently `.ready` or has no bookmark.
    func leaseURL(projectID: UUID) -> URL? {
        leases[projectID]?.url
    }

    /// Extend a project's known-basenames after a drag-onto copy completes,
    /// so the count pill stays hidden for the just-copied files.
    func seedKnownBasenames(projectID: UUID, basenames: Set<String>) {
        watchers[projectID]?.seedKnown(basenames: basenames)
    }

    /// Force a fresh watcher scan — re-reads the analysis DB (session count +
    /// file deltas) for a project whose DB changed without a source-file event,
    /// e.g. a run just finished. The DB lives under `bristlenose-output/`, which
    /// the watcher's NSFilePresenter scope excludes, so completion can't be
    /// picked up passively. No-op if the project has no live watcher.
    func rescan(projectID: UUID) {
        watchers[projectID]?.refresh()
    }

    private func releaseLeaseAndWatcher(for id: UUID) {
        if let watcher = watchers.removeValue(forKey: id) {
            // NSFilePresenter is removed in deinit; explicit nil-out drops
            // our strong reference so deinit fires now.
            _ = watcher
        }
        leases.removeValue(forKey: id)
        unanalysed.removeValue(forKey: id)
    }

    private func handleWatcherUpdate(projectID: UUID, state: UnanalysedState) {
        // The `watchers[id] != nil` guard is load-bearing: between the scan
        // running and this hop to main, the project may have been removed
        // or transitioned out of `.ready` (lease + watcher released, scan
        // result still in-flight). Without this guard we'd republish state
        // for a project the user has dismissed.
        guard watchers[projectID] != nil else { return }
        // F14 policy: suppress newFiles for projects that have never been
        // analysed. The +N delta means "new since the last analysis run" —
        // before there's been a run, every file in the folder is "to be
        // analysed" by default and surfacing it as an exception would be
        // surprising. Session count + missingFiles are unaffected (neither
        // can be non-empty pre-analysis anyway).
        let project = projects.first { $0.id == projectID }
        let gated: UnanalysedState
        if project?.lastPipelineRunAt == nil {
            gated = UnanalysedState(
                newFiles: [],
                missingFiles: state.missingFiles,
                sessionCount: state.sessionCount,
                totalDurationSeconds: state.totalDurationSeconds
            )
        } else {
            gated = state
        }
        unanalysed[projectID] = gated
    }

    /// Scan all mounted volumes for a relative path.
    /// Handles "Samsung T7" → "Samsung T7 1" renames.
    private static func resolveVolumeRelativePath(_ relativePath: String) -> String? {
        guard let contents = try? FileManager.default.contentsOfDirectory(atPath: "/Volumes") else {
            return nil
        }
        for volumeName in contents {
            let candidatePath = "/Volumes/\(volumeName)/\(relativePath)"
            if FileManager.default.fileExists(atPath: candidatePath) {
                return candidatePath
            }
        }
        return nil
    }

    /// Relocate a project to a new path (after user selects via NSOpenPanel).
    func relocateProject(id: UUID, newPath: String) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        projects[index].path = newPath
        projects[index].lastSeenPath = newPath
        projects[index].location = Self.detectLocation(for: newPath)
        projects[index].bookmarkData = Self.createBookmark(for: newPath)
        projects[index].resourceIdentifier = Self.captureResourceIdentifier(for: newPath)
        save()
        // Drop any old lease/watcher and re-establish against the new path.
        releaseLeaseAndWatcher(for: id)
        syncWatchers()
    }

    // MARK: - Persistence

    private func load() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            // First launch — create empty index.
            save()
            return
        }

        do {
            let data = try Data(contentsOf: fileURL)
            let wrapper = try JSONDecoder.iso8601Fractional.decode(ProjectsFile.self, from: data)
            projects = wrapper.projects
            folders = wrapper.folders

            // Backfill location and bookmark for projects migrated from Phase 1–3.
            var needsSave = false
            for i in projects.indices {
                if !projects[i].path.isEmpty && projects[i].location == nil {
                    projects[i].location = Self.detectLocation(for: projects[i].path)
                    projects[i].bookmarkData = Self.createBookmark(for: projects[i].path)
                    needsSave = true
                }

                // Phase 0 schema lock: upgrade pre-v1 records.
                if projects[i].schemaVersion < Project.currentSchemaVersion {
                    if projects[i].lastSeenPath.isEmpty {
                        projects[i].lastSeenPath = projects[i].path
                    }
                    // resourceIdentifier stays nil — lazy-captured on next
                    // successful availability resolution.
                    projects[i].schemaVersion = Project.currentSchemaVersion
                    needsSave = true
                }
            }

            // Backfill positions for projects migrated from pre-position era.
            // All positions default to 0 — assign based on createdAt (newest first).
            let allZeroProjects = projects.allSatisfy { $0.position == 0 } && projects.count > 1
            let allZeroFolders = folders.allSatisfy { $0.position == 0 } && folders.count > 1
            if allZeroProjects || allZeroFolders {
                // Build combined root items sorted newest-first (preserving old behaviour).
                let rootProjects = projects.enumerated()
                    .filter { $0.element.folderId == nil }
                let rootFolders = folders.enumerated()

                var rootItems: [(kind: String, arrayIndex: Int, createdAt: Date)] = []
                for (idx, p) in rootProjects {
                    rootItems.append(("project", idx, p.createdAt))
                }
                for (idx, f) in rootFolders {
                    rootItems.append(("folder", idx, f.createdAt))
                }
                rootItems.sort { $0.createdAt > $1.createdAt }

                for (pos, item) in rootItems.enumerated() {
                    if item.kind == "project" {
                        projects[item.arrayIndex].position = pos
                    } else {
                        folders[item.arrayIndex].position = pos
                    }
                }

                // Also backfill positions within each folder.
                for folder in folders {
                    let inFolder = projects.enumerated()
                        .filter { $0.element.folderId == folder.id }
                        .sorted { $0.element.createdAt > $1.element.createdAt }
                    for (pos, (idx, _)) in inFolder.enumerated() {
                        projects[idx].position = pos
                    }
                }

                needsSave = true
            }

            if needsSave { save() }
        } catch {
            print("[ProjectIndex] Failed to load projects.json: \(error)")
        }
    }

    private func save() {
        let wrapper = ProjectsFile(version: "1.0", folders: folders, projects: projects)
        do {
            let data = try JSONEncoder.iso8601Fractional.encode(wrapper)
            try data.write(to: fileURL, options: .atomic)
        } catch {
            print("[ProjectIndex] Failed to save projects.json: \(error)")
        }
    }
}

// MARK: - File envelope

/// Top-level structure of `projects.json`.
private struct ProjectsFile: Codable {
    let version: String
    let folders: [Folder]
    let projects: [Project]
}

// MARK: - ISO 8601 date coding

private extension JSONDecoder {
    /// Decoder that handles ISO 8601 dates with optional fractional seconds.
    static let iso8601Fractional: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: string) { return date }

            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: string) { return date }

            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "Invalid date: \(string)"
            )
        }
        return decoder
    }()
}

private extension JSONEncoder {
    /// Encoder that writes ISO 8601 dates.
    static let iso8601Fractional: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return encoder
    }()
}

extension Notification.Name {
    /// A project's Agent Access flag flipped. `ServeManager` listens and
    /// re-syncs the MCP handshake file for the fronted project — turning
    /// access off deletes it (revocation is a file write, design §3.1).
    static let bristlenoseAgentAccessChanged = Notification.Name("bristlenoseAgentAccessChanged")
}
