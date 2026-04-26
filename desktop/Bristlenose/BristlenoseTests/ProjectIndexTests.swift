import Testing
import Foundation
@testable import Bristlenose

/// ProjectIndex is @MainActor — all tests must be @MainActor too.
/// All tests use a temp directory to avoid touching the real projects.json.
@MainActor
@Suite("ProjectIndex persistence and logic")
struct ProjectIndexTests {

    /// Create a ProjectIndex backed by a temp file.
    @MainActor
    private static func makeTempIndex() -> (ProjectIndex, URL) {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let fileURL = tempDir.appendingPathComponent("projects.json")
        let index = ProjectIndex(fileURL: fileURL)
        return (index, tempDir)
    }

    /// Clean up a temp directory.
    private static func cleanup(_ tempDir: URL) {
        try? FileManager.default.removeItem(at: tempDir)
    }

    // MARK: - Add / remove

    @MainActor @Test func addProject_createsProject() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let project = index.addProject(name: "Test Project", path: "/tmp/test")
        #expect(project.name == "Test Project")
        #expect(project.path == "/tmp/test")
        #expect(index.projects.count == 1)
    }

    @MainActor @Test func removeProject_removesIt() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let project = index.addProject(name: "Doomed", path: "/tmp/doomed")
        index.removeProject(id: project.id)
        #expect(index.projects.isEmpty)
    }

    // MARK: - Name uniqueness

    @MainActor @Test func addProject_duplicateName_appendsSuffix() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        index.addProject(name: "My Project", path: "/tmp/a")
        let second = index.addProject(name: "My Project", path: "/tmp/b")
        #expect(second.name == "My Project 2")
    }

    @MainActor @Test func addProject_tripleDuplicate_incrementsSuffix() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        index.addProject(name: "P", path: "/tmp/a")
        index.addProject(name: "P", path: "/tmp/b")
        let third = index.addProject(name: "P", path: "/tmp/c")
        #expect(third.name == "P 3")
    }

    @MainActor @Test func renameProject_deduplicates() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        index.addProject(name: "Alpha", path: "/tmp/a")
        let beta = index.addProject(name: "Beta", path: "/tmp/b")
        index.renameProject(id: beta.id, newName: "Alpha")
        #expect(index.projects.first(where: { $0.id == beta.id })?.name == "Alpha 2")
    }

    // MARK: - Find by path

    @MainActor @Test func findByPath_existingPath_returnsProject() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        index.addProject(name: "Found", path: "/tmp/findme")
        #expect(index.findByPath("/tmp/findme") != nil)
    }

    @MainActor @Test func findByPath_missingPath_returnsNil() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        #expect(index.findByPath("/tmp/nonexistent") == nil)
    }

    // MARK: - Folder CRUD

    @MainActor @Test func addFolder_createsFolder() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "Research")
        #expect(folder.name == "Research")
        #expect(index.folders.count == 1)
    }

    @MainActor @Test func addFolder_duplicateName_appendsSuffix() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        index.addFolder(name: "Research")
        let second = index.addFolder(name: "Research")
        #expect(second.name == "Research 2")
    }

    @MainActor @Test func removeFolder_movesProjectsToRoot() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "F")
        let project = index.addProject(name: "P", path: "/tmp/p")
        index.moveProject(projectId: project.id, toFolder: folder.id)

        index.removeFolder(id: folder.id)
        #expect(index.folders.isEmpty)
        #expect(index.projects.first?.folderId == nil)
    }

    // MARK: - Move project to folder

    @MainActor @Test func moveProject_intoFolder() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "F")
        let project = index.addProject(name: "P", path: "/tmp/p")
        index.moveProject(projectId: project.id, toFolder: folder.id)

        #expect(index.projects.first?.folderId == folder.id)
        #expect(index.projectsInFolder(folder.id).count == 1)
    }

    @MainActor @Test func moveProject_toRoot() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "F")
        let project = index.addProject(name: "P", path: "/tmp/p")
        index.moveProject(projectId: project.id, toFolder: folder.id)
        index.moveProject(projectId: project.id, toFolder: nil)

        #expect(index.projects.first?.folderId == nil)
    }

    // MARK: - Sidebar items

    @MainActor @Test func sidebarItems_sortedNewestFirst() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let first = index.addProject(name: "First", path: "/tmp/1")
        // Small delay to ensure different timestamps
        let second = index.addProject(name: "Second", path: "/tmp/2")

        let items = index.sidebarItems
        #expect(items.count == 2)
        // Newest (second) should be first in the list
        #expect(items.first?.id == second.id)
    }

    @MainActor @Test func sidebarItems_excludeFolderedProjects() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "F")
        let project = index.addProject(name: "P", path: "/tmp/p")
        index.moveProject(projectId: project.id, toFolder: folder.id)

        // Sidebar items should contain the folder but not the foldered project
        let projectItems = index.sidebarItems.compactMap { item -> UUID? in
            if case .project(let p) = item { return p.id }
            return nil
        }
        #expect(!projectItems.contains(project.id))
    }

    // MARK: - Location detection

    @Test func detectLocation_localPath() {
        let location = ProjectIndex.detectLocation(for: "/Users/test/Documents/research")
        #expect(location.type == .local)
        #expect(location.displayHint == "On this Mac")
    }

    @Test func detectLocation_volumePath() {
        let location = ProjectIndex.detectLocation(for: "/Volumes/Samsung T7/research/project")
        #expect(location.type == .volume || location.type == .network)
        #expect(location.volumeName == "Samsung T7")
        #expect(location.volumeRelativePath == "research/project")
    }

    @Test func detectLocation_iCloudPath() {
        let location = ProjectIndex.detectLocation(
            for: "/Users/test/Library/Mobile Documents/com~apple~CloudDocs/research"
        )
        #expect(location.type == .cloud)
        #expect(location.displayHint == "iCloud Drive")
    }

    @Test func detectLocation_dropboxPath() {
        let location = ProjectIndex.detectLocation(
            for: "/Users/test/Library/CloudStorage/Dropbox/research"
        )
        #expect(location.type == .cloud)
        #expect(location.displayHint == "Dropbox")
    }

    @Test func detectLocation_oneDrivePath() {
        let location = ProjectIndex.detectLocation(
            for: "/Users/test/Library/CloudStorage/OneDrive-Corp/research"
        )
        #expect(location.type == .cloud)
        #expect(location.displayHint == "OneDrive")
    }

    // MARK: - JSON round-trip

    @MainActor @Test func jsonRoundTrip_persistsAndReloads() {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let fileURL = tempDir.appendingPathComponent("projects.json")
        defer { try? FileManager.default.removeItem(at: tempDir) }

        // Write
        let index1 = ProjectIndex(fileURL: fileURL)
        let folder = index1.addFolder(name: "Research")
        let project = index1.addProject(name: "IKEA Study", path: "/tmp/ikea")
        index1.moveProject(projectId: project.id, toFolder: folder.id)

        // Read back
        let index2 = ProjectIndex(fileURL: fileURL)
        #expect(index2.projects.count == 1)
        #expect(index2.projects.first?.name == "IKEA Study")
        #expect(index2.projects.first?.folderId == folder.id)
        #expect(index2.folders.count == 1)
        #expect(index2.folders.first?.name == "Research")
    }

    // MARK: - Folder collapse state

    @MainActor @Test func setFolderCollapsed_persists() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "F")
        #expect(folder.collapsed == false)

        index.setFolderCollapsed(id: folder.id, collapsed: true)
        #expect(index.folders.first?.collapsed == true)
    }
}
