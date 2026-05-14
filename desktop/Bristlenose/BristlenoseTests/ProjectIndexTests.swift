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

    // MARK: - Phase 0a schema lock

    /// New projects added via `addProject(...)` get the current schema version
    /// and `lastSeenPath` mirrors `path`.
    @MainActor @Test func addProject_setsCurrentSchemaVersion() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let p = index.addProject(name: "Schema", path: "/tmp/schema-v1")
        #expect(p.schemaVersion == Project.currentSchemaVersion)
        #expect(p.lastSeenPath == "/tmp/schema-v1")
    }

    /// Pre-v1 records (no `schema_version` / `last_seen_path` keys in JSON)
    /// load, migrate on first save, and round-trip with the new fields filled.
    @MainActor @Test func loadPreV1Record_upgradesToCurrentSchema() throws {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let fileURL = tempDir.appendingPathComponent("projects.json")

        // Hand-rolled pre-v1 fixture — no schema_version, no last_seen_path,
        // no resource_identifier. Matches what existing user installs have.
        let preV1 = """
        {
          "version": "1.0",
          "folders": [],
          "projects": [
            {
              "id": "00000000-0000-0000-0000-000000000001",
              "name": "Legacy",
              "path": "/tmp/legacy",
              "position": 0,
              "created_at": "2026-01-01T00:00:00Z"
            }
          ]
        }
        """
        try preV1.write(to: fileURL, atomically: true, encoding: .utf8)

        let index = ProjectIndex(fileURL: fileURL)
        #expect(index.projects.count == 1)
        let migrated = try #require(index.projects.first)
        #expect(migrated.schemaVersion == Project.currentSchemaVersion)
        #expect(migrated.lastSeenPath == "/tmp/legacy")
        #expect(migrated.resourceIdentifier == nil)

        // Round-trip: the on-disk file now has the new fields.
        let reloaded = ProjectIndex(fileURL: fileURL)
        let again = try #require(reloaded.projects.first)
        #expect(again.schemaVersion == Project.currentSchemaVersion)
        #expect(again.lastSeenPath == "/tmp/legacy")
    }

    /// A v1 record (schema_version explicitly present) loads unchanged.
    @MainActor @Test func loadV1Record_noMigrationTriggered() throws {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let fileURL = tempDir.appendingPathComponent("projects.json")

        let v1 = """
        {
          "version": "1.0",
          "folders": [],
          "projects": [
            {
              "id": "00000000-0000-0000-0000-000000000002",
              "name": "Already v1",
              "path": "/tmp/already-v1",
              "schema_version": 1,
              "last_seen_path": "/tmp/already-v1-elsewhere",
              "position": 0,
              "created_at": "2026-04-01T00:00:00Z"
            }
          ]
        }
        """
        try v1.write(to: fileURL, atomically: true, encoding: .utf8)

        let index = ProjectIndex(fileURL: fileURL)
        let p = try #require(index.projects.first)
        #expect(p.schemaVersion == 1)
        // lastSeenPath preserved verbatim — not stomped to match path.
        #expect(p.lastSeenPath == "/tmp/already-v1-elsewhere")
    }

    // MARK: - Phase 0b ProjectAvailability

    /// A project with a path that exists returns `.ready`.
    @MainActor @Test func availability_existingPath_isReady() throws {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }

        let (index, _) = Self.makeTempIndex()
        let p = index.addProject(name: "Live", path: tempDir.path)
        #expect(p.availability == .ready)
        #expect(p.isAvailable)
    }

    /// A project with a non-existent path on the local volume returns
    /// `.cantFind(.moved)` (or `.missingBookmark` if no bookmark survived).
    @MainActor @Test func availability_missingLocalPath_isCantFind() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let p = index.addProject(name: "Ghost", path: "/tmp/definitely-not-a-real-path-\(UUID().uuidString)")
        if case .cantFind = p.availability { } else {
            Issue.record("Expected .cantFind, got \(p.availability)")
        }
        #expect(!p.isAvailable)
    }

    /// Volume paths with the volume missing surface the volume name in
    /// `.unmountedVolume` so the row subtitle can say "Samsung T7 · missing".
    @MainActor @Test func availability_volumePathMissing_surfacesVolumeName() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        // Synthetic volume path — /Volumes/Phantom Drive almost certainly
        // doesn't exist on the test host.
        let p = index.addProject(name: "Drive", path: "/Volumes/Phantom Drive/research")
        switch p.availability {
        case .cantFind(.unmountedVolume(let name)):
            #expect(name == "Phantom Drive")
        default:
            Issue.record("Expected .cantFind(.unmountedVolume), got \(p.availability)")
        }
    }

    /// The enum's UI mapping is deterministic — each case has a fixed icon
    /// and primary action. Catches accidental drift in the type-level switch.
    @Test func availability_uiMapping_isStable() {
        #expect(ProjectAvailability.ready.sfSymbolName == nil)
        #expect(ProjectAvailability.ready.primaryAction == .none)
        #expect(ProjectAvailability.cantFind(reason: .moved).sfSymbolName == "questionmark.folder")
        #expect(ProjectAvailability.cantFind(reason: .moved).primaryAction == .locate)
        #expect(ProjectAvailability.inCloud(downloading: nil).primaryAction == .downloadFromCloud)
    }

    // MARK: - restoreProject (undoable removal)

    @MainActor @Test func restoreProject_reinsertsAtSameRootPosition() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        index.addProject(name: "Alpha", path: "/tmp/a")
        let beta = index.addProject(name: "Beta", path: "/tmp/b")
        index.addProject(name: "Gamma", path: "/tmp/g")
        // After three insertions, positions are 0=Gamma, 1=Beta, 2=Alpha
        // (each new project goes to position 0, others shift down).
        let snapshot = index.projects.first { $0.id == beta.id }!
        let originalPosition = snapshot.position
        index.removeProject(id: beta.id)
        #expect(index.projects.count == 2)

        index.restoreProject(snapshot, folderId: nil, position: originalPosition)
        #expect(index.projects.count == 3)
        #expect(index.projects.first { $0.id == beta.id }?.position == originalPosition)
    }

    @MainActor @Test func restoreProject_isIdempotent_whenAlreadyPresent() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let p = index.addProject(name: "Alpha", path: "/tmp/a")
        let snapshot = index.projects.first { $0.id == p.id }!
        index.restoreProject(snapshot, folderId: nil, position: snapshot.position)
        #expect(index.projects.count == 1)
    }

    @MainActor @Test func restoreProject_preservesFolderMembership() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "Studies")
        let p = index.addProject(name: "Alpha", path: "/tmp/a")
        index.moveProject(projectId: p.id, toFolder: folder.id)
        let snapshot = index.projects.first { $0.id == p.id }!
        #expect(snapshot.folderId == folder.id)

        index.removeProject(id: p.id)
        index.restoreProject(snapshot, folderId: folder.id, position: snapshot.position)
        let restored = index.projects.first { $0.id == p.id }
        #expect(restored?.folderId == folder.id)
    }

    // MARK: - UndoableRemovalStore round-trip

    @MainActor @Test func removalStore_undo_restoresProject() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let p = index.addProject(name: "Alpha", path: "/tmp/a")
        let store = UndoableRemovalStore(undoWindow: 60)
        store.setProjectIndex(index)

        store.removeFromSidebar(p)
        #expect(index.projects.isEmpty)
        #expect(store.hasPending)
        #expect(store.pendingName == "Alpha")
        #expect(store.pendingCount == 1)

        store.undoLastRemoval()
        #expect(index.projects.count == 1)
        #expect(!store.hasPending)
    }

    @MainActor @Test func removalStore_secondRemove_commitsFirst() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let a = index.addProject(name: "Alpha", path: "/tmp/a")
        let b = index.addProject(name: "Beta", path: "/tmp/b")
        let store = UndoableRemovalStore(undoWindow: 60)
        store.setProjectIndex(index)

        store.removeFromSidebar(a)
        store.removeFromSidebar(b)
        // Only the most recent removal is undoable.
        #expect(store.pendingName == "Beta")
        store.undoLastRemoval()
        // Alpha was committed by the second remove call — it stays gone.
        #expect(index.projects.contains { $0.id == b.id })
        #expect(!index.projects.contains { $0.id == a.id })
    }

    @MainActor @Test func removalStore_batchRemove_undoRestoresAll() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let a = index.addProject(name: "Alpha", path: "/tmp/a")
        let b = index.addProject(name: "Beta", path: "/tmp/b")
        let c = index.addProject(name: "Gamma", path: "/tmp/c")
        let store = UndoableRemovalStore(undoWindow: 60)
        store.setProjectIndex(index)

        store.removeFromSidebar([a, b, c])
        #expect(index.projects.isEmpty)
        #expect(store.pendingCount == 3)
        // pendingName is nil for batches > 1.
        #expect(store.pendingName == nil)

        store.undoLastRemoval()
        #expect(index.projects.count == 3)
    }

    @MainActor @Test func removalStore_undoRestoresPriorSelection() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let a = index.addProject(name: "Alpha", path: "/tmp/a")
        let b = index.addProject(name: "Beta", path: "/tmp/b")
        let store = UndoableRemovalStore(undoWindow: 60)
        store.setProjectIndex(index)

        var restored: Set<SidebarSelection> = []
        store.setOnUndo { selection in
            restored = selection
        }

        let priorSelection: Set<SidebarSelection> = [.project(a.id), .project(b.id)]
        store.removeFromSidebar([a, b], priorSelection: priorSelection)
        store.undoLastRemoval()
        #expect(restored == priorSelection)
    }

    /// Acceptance criterion 1: removed cantFind projects must restore to the
    /// exact prior state — including bookmarkData. Locks the round-trip so
    /// future refactors of `Pending` can't drop the bookmark field by mistake.
    @MainActor @Test func removalStore_cantFindProject_restoresBookmark() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let p = index.addProject(name: "Acme Q3", path: "/tmp/a")
        // Force-stamp bookmark bytes so the test doesn't depend on the
        // sandbox-scoped bookmark machinery succeeding under xcodebuild test.
        let bookmarkBytes = Data([0x01, 0x02, 0x03, 0x04, 0x05])
        if let idx = index.projects.firstIndex(where: { $0.id == p.id }) {
            index.projects[idx].bookmarkData = bookmarkBytes
            index.projects[idx].lastSeenPath = "/Volumes/Phantom/Acme Q3"
        }
        let snapshot = index.projects.first { $0.id == p.id }!
        #expect(snapshot.bookmarkData == bookmarkBytes)

        let store = UndoableRemovalStore(undoWindow: 60)
        store.setProjectIndex(index)
        store.removeFromSidebar(snapshot)
        store.undoLastRemoval()

        let restored = index.projects.first { $0.id == p.id }
        #expect(restored?.bookmarkData == bookmarkBytes)
        #expect(restored?.lastSeenPath == "/Volumes/Phantom/Acme Q3")
    }

    // MARK: - LocateFlow marker validation

    @MainActor @Test func locateFlow_rejectsEmptyMarkerDirectory() throws {
        // Folder with an empty `bristlenose-output/` shouldn't pass — the
        // stronger marker check (security finding #15) requires at least one
        // canonical artefact inside.
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("LocateFlowTest-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }
        try FileManager.default.createDirectory(
            at: tempDir.appendingPathComponent("bristlenose-output"),
            withIntermediateDirectories: true
        )

        #expect(LocateFlow.folderLooksAnalysed(url: tempDir) == false)
    }

    @MainActor @Test func locateFlow_acceptsFolderWithManifest() throws {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("LocateFlowTest-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputDir = tempDir.appendingPathComponent("bristlenose-output")
        try FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)
        try Data().write(to: outputDir.appendingPathComponent("manifest.json"))

        #expect(LocateFlow.folderLooksAnalysed(url: tempDir) == true)
    }

    @MainActor @Test func locateFlow_acceptsFolderWithBristlenoseDir() throws {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("LocateFlowTest-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputDir = tempDir.appendingPathComponent("bristlenose-output")
        try FileManager.default.createDirectory(
            at: outputDir.appendingPathComponent(".bristlenose"),
            withIntermediateDirectories: true
        )

        #expect(LocateFlow.folderLooksAnalysed(url: tempDir) == true)
    }

    @MainActor @Test func locateFlow_rejectsArbitraryFolder() throws {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("LocateFlowTest-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: tempDir) }
        #expect(LocateFlow.folderLooksAnalysed(url: tempDir) == false)
    }
}
