import Foundation

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
    var id: UUID
    var name: String
    var path: String
    var inputFiles: [String]?
    var location: Location?
    var bookmarkData: Data?
    var icon: String?
    var folderId: UUID?
    var position: Int
    var createdAt: Date
    var lastOpened: Date?

    enum CodingKeys: String, CodingKey {
        case id, name, path, icon, position
        case inputFiles = "input_files"
        case location
        case bookmarkData = "bookmark_data"
        case folderId = "folder_id"
        case createdAt = "created_at"
        case lastOpened = "last_opened"
    }

    // Custom coding for bookmarkData (Base64 string in JSON instead of byte array).

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        path = try container.decode(String.self, forKey: .path)
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
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(path, forKey: .path)
        try container.encodeIfPresent(inputFiles, forKey: .inputFiles)
        try container.encodeIfPresent(icon, forKey: .icon)
        try container.encodeIfPresent(location, forKey: .location)
        try container.encodeIfPresent(bookmarkData?.base64EncodedString(), forKey: .bookmarkData)
        try container.encodeIfPresent(folderId, forKey: .folderId)
        try container.encode(position, forKey: .position)
        try container.encode(createdAt, forKey: .createdAt)
        try container.encodeIfPresent(lastOpened, forKey: .lastOpened)
    }

    init(id: UUID, name: String, path: String, inputFiles: [String]? = nil,
         icon: String? = nil, location: Location? = nil, bookmarkData: Data? = nil,
         folderId: UUID? = nil, position: Int = 0, createdAt: Date = Date(), lastOpened: Date? = nil) {
        self.id = id
        self.name = name
        self.path = path
        self.inputFiles = inputFiles
        self.icon = icon
        self.location = location
        self.bookmarkData = bookmarkData
        self.folderId = folderId
        self.position = position
        self.createdAt = createdAt
        self.lastOpened = lastOpened
    }

    /// Whether the project directory is currently accessible on disk.
    /// Always true for projects with no path (new, unsaved projects).
    var isAvailable: Bool {
        guard !path.isEmpty else { return true }
        return FileManager.default.fileExists(atPath: path)
    }

    /// Why the project is unavailable, if it is.
    enum UnavailabilityReason {
        /// The volume (external drive, network share) isn't mounted.
        case volumeNotMounted(displayHint: String)
        /// The path doesn't exist on a mounted volume — moved or deleted.
        case movedOrDeleted
    }

    /// Returns nil when the project is available.
    var unavailabilityReason: UnavailabilityReason? {
        guard !path.isEmpty, !isAvailable else { return nil }
        if let location, location.type == .volume || location.type == .network,
           let volumeName = location.volumeName {
            let volumePath = "/Volumes/\(volumeName)"
            if !FileManager.default.fileExists(atPath: volumePath) {
                return .volumeNotMounted(displayHint: location.displayHint)
            }
        }
        return .movedOrDeleted
    }
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
    /// Posted by File > New Project (Cmd+N) and the sidebar [+] button.
    static let createNewProject = Notification.Name("bristlenoseCreateNewProject")

    /// Posted by File > New Folder (⇧⌘N) and the sidebar folder.badge.plus button.
    static let createNewFolder = Notification.Name("bristlenoseCreateNewFolder")

    /// Posted by Project > Rename to trigger inline rename in the sidebar.
    static let renameSelectedProject = Notification.Name("bristlenoseRenameSelectedProject")

    /// Posted by Project > Rename Folder to trigger inline rename on the selected folder.
    static let renameSelectedFolder = Notification.Name("bristlenoseRenameSelectedFolder")

    /// Posted by Project > Delete to remove the selected project.
    static let deleteSelectedProject = Notification.Name("bristlenoseDeleteSelectedProject")

    /// Posted by Project > Delete Folder to remove the selected folder.
    static let deleteSelectedFolder = Notification.Name("bristlenoseDeleteSelectedFolder")

    /// Posted by Project > Move to to move the selected project into a folder.
    /// `userInfo["folderId"]` is the target `UUID` or `NSNull` for root.
    static let moveSelectedProject = Notification.Name("bristlenoseMoveSelectedProject")

    /// Posted by Project > Locate… to re-point a moved/deleted project.
    static let locateSelectedProject = Notification.Name("bristlenoseLocateSelectedProject")
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
    }

    // MARK: - CRUD

    /// Create a new project with the given name and path.
    /// The name is de-duplicated if it already exists (appends " 2", " 3", etc.).
    /// `inputFiles` optionally restricts which files the pipeline processes
    /// (nil = scan the whole directory).
    /// Returns the new project so the caller can select it.
    @discardableResult
    func addProject(name: String, path: String, inputFiles: [String]? = nil) -> Project {
        let finalName = uniqueName(name, excluding: nil)
        let location = path.isEmpty ? nil : Self.detectLocation(for: path)
        let bookmark = Self.createBookmark(for: path)
        // New items get position 0; push all existing root items down by 1.
        for i in projects.indices where projects[i].folderId == nil {
            projects[i].position += 1
        }
        for i in folders.indices {
            folders[i].position += 1
        }
        let project = Project(
            id: UUID(),
            name: finalName,
            path: path,
            inputFiles: inputFiles,
            location: location,
            bookmarkData: bookmark,
            position: 0,
            createdAt: Date(),
            lastOpened: nil
        )
        projects.insert(project, at: 0)
        save()
        return project
    }

    /// Remove a project by ID.
    func removeProject(id: UUID) {
        projects.removeAll { $0.id == id }
        save()
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

    /// Stamp the current date as last-opened.
    func updateLastOpened(id: UUID) {
        guard let index = projects.firstIndex(where: { $0.id == id }) else { return }
        projects[index].lastOpened = Date()
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

    /// Move a project into a folder (or to root if folderId is nil).
    func moveProject(projectId: UUID, toFolder folderId: UUID?) {
        guard let index = projects.firstIndex(where: { $0.id == projectId }) else { return }
        projects[index].folderId = folderId
        save()
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
        let homeDir = FileManager.default.homeDirectoryForCurrentUser.path

        // Cloud detection — check before local, since cloud paths live under /Users/
        let cloudPrefixes: [(prefix: String, label: String)] = [
            ("/Library/CloudStorage/OneDrive", "OneDrive"),
            ("/Library/CloudStorage/Dropbox", "Dropbox"),
            ("/Library/Mobile Documents", "iCloud Drive"),
        ]
        for cloud in cloudPrefixes {
            if path.contains(cloud.prefix) {
                return Location(type: .cloud, displayHint: cloud.label)
            }
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
                    projects[i].location = Self.detectLocation(for: resolvedPath)
                    projects[i].bookmarkData = Self.createBookmark(for: resolvedPath)
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
                    projects[i].location = Self.detectLocation(for: resolvedPath)
                    projects[i].bookmarkData = Self.createBookmark(for: resolvedPath)
                    changed = true
                }
            }
        }
        if changed { save() }
        objectWillChange.send()
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
        projects[index].location = Self.detectLocation(for: newPath)
        projects[index].bookmarkData = Self.createBookmark(for: newPath)
        save()
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
