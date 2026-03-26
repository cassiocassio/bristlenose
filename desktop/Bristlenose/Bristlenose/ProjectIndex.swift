import Foundation

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
    var folderId: UUID?
    var createdAt: Date
    var lastOpened: Date?

    enum CodingKeys: String, CodingKey {
        case id, name, path
        case inputFiles = "input_files"
        case folderId = "folder_id"
        case createdAt = "created_at"
        case lastOpened = "last_opened"
    }
}

// MARK: - Folder model

/// A one-level-deep folder for grouping projects in the sidebar.
/// Folder names are display-only — never construct filesystem paths from them.
struct Folder: Identifiable, Hashable, Codable {
    var id: UUID
    var name: String
    var collapsed: Bool
    var createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id, name, collapsed
        case createdAt = "created_at"
    }

    /// Custom decoder for backward compatibility — old `projects.json` files
    /// have FolderStub shapes with only `id` and `name`.
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        collapsed = try container.decodeIfPresent(Bool.self, forKey: .collapsed) ?? false
        createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt) ?? Date()
    }

    init(id: UUID, name: String, collapsed: Bool = false, createdAt: Date = Date()) {
        self.id = id
        self.name = name
        self.collapsed = collapsed
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

    init() {
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first!.appendingPathComponent("Bristlenose")

        // Create the directory if it doesn't exist.
        try? FileManager.default.createDirectory(
            at: appSupport, withIntermediateDirectories: true
        )

        fileURL = appSupport.appendingPathComponent("projects.json")
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
        let project = Project(
            id: UUID(),
            name: finalName,
            path: path,
            inputFiles: inputFiles,
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
        let folder = Folder(id: UUID(), name: finalName, createdAt: Date())
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

    /// Root-level items (projects without a folder + folders), sorted newest first.
    var sidebarItems: [SidebarItem] {
        let rootProjects = projects.filter { $0.folderId == nil }.map { SidebarItem.project($0) }
        let allFolders = folders.map { SidebarItem.folder($0) }
        return (rootProjects + allFolders).sorted { $0.createdAt > $1.createdAt }
    }

    /// Projects belonging to a specific folder, sorted newest first.
    func projectsInFolder(_ folderId: UUID) -> [Project] {
        projects.filter { $0.folderId == folderId }.sorted { $0.createdAt > $1.createdAt }
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
