import Foundation

// MARK: - Project model

/// A project entry in the sidebar — a pointer to a directory on disk.
/// All project data lives in the directory; only metadata lives here.
struct Project: Identifiable, Hashable, Codable {
    var id: UUID
    var name: String
    var path: String
    var createdAt: Date
    var lastOpened: Date?

    enum CodingKeys: String, CodingKey {
        case id, name, path
        case createdAt = "created_at"
        case lastOpened = "last_opened"
    }
}

// MARK: - Notification names

extension Notification.Name {
    /// Posted by File > New Project (Cmd+N) and the sidebar [+] button.
    static let createNewProject = Notification.Name("bristlenoseCreateNewProject")

    /// Posted by Project > Rename to trigger inline rename in the sidebar.
    static let renameSelectedProject = Notification.Name("bristlenoseRenameSelectedProject")

    /// Posted by Project > Delete to remove the selected project.
    static let deleteSelectedProject = Notification.Name("bristlenoseDeleteSelectedProject")
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
    /// Returns the new project so the caller can select it.
    @discardableResult
    func addProject(name: String, path: String) -> Project {
        let finalName = uniqueName(name, excluding: nil)
        let project = Project(
            id: UUID(),
            name: finalName,
            path: path,
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
        } catch {
            print("[ProjectIndex] Failed to load projects.json: \(error)")
        }
    }

    private func save() {
        let wrapper = ProjectsFile(version: "1.0", folders: [], projects: projects)
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
/// Phase 1: folders array is always empty. Included for forward compatibility.
private struct ProjectsFile: Codable {
    let version: String
    let folders: [FolderStub]
    let projects: [Project]
}

/// Placeholder for future folder support (Phase 3).
private struct FolderStub: Codable {
    let id: UUID
    let name: String
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
