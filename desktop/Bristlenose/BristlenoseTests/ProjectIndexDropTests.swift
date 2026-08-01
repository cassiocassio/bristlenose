import Testing
import Foundation
@testable import Bristlenose

/// `ProjectIndex.apply(_:)` — the model half of the sidebar's unified drag-and-drop.
/// Sibling to `DropRoutingTests`, which covers the pure routing that produces the plan;
/// this suite covers what the plan does to `folderId` + `position`.
///
/// Root ordering is **interleaved** by design: a folder is just another row in the root
/// sequence, sharing one `position` space with root projects.
@MainActor
@Suite("ProjectIndex drag-and-drop")
struct ProjectIndexDropTests {

    private static func makeTempIndex() -> (ProjectIndex, URL) {
        let tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: tempDir.appendingPathComponent("projects.json"))
        return (index, tempDir)
    }

    private static func cleanup(_ tempDir: URL) {
        try? FileManager.default.removeItem(at: tempDir)
    }

    /// `addProject` inserts at the top, so add in reverse to get the names in order.
    private static func seedRootProjects(_ index: ProjectIndex, _ names: [String]) {
        for name in names.reversed() {
            index.addProject(name: name, path: "/tmp/\(name)")
        }
    }

    private static func rootNames(_ index: ProjectIndex) -> [String] {
        index.sidebarItems.map { item in
            switch item {
            case .project(let p): p.name
            case .folder(let f): f.name
            }
        }
    }

    private static func id(_ index: ProjectIndex, _ name: String) -> UUID {
        index.projects.first { $0.name == name }!.id
    }

    // MARK: - New projects land at the top

    /// The eye-line invariant: a new project arrives at the top and pushes the rest
    /// down. Manual order composes with it — nothing re-sorts behind the user.
    @Test func newProject_landsAtTop() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B"])
        index.addProject(name: "C", path: "/tmp/C")
        #expect(Self.rootNames(index) == ["C", "A", "B"])
    }

    // MARK: - Reorder within root

    @Test func reorderAtRoot_movesDownward() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B", "C", "D"])
        index.apply(DropPlan(items: [.project(Self.id(index, "A"))], toFolder: nil, atIndex: 2))
        #expect(Self.rootNames(index) == ["B", "A", "C", "D"])
    }

    @Test func reorderAtRoot_movesUpward() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B", "C", "D"])
        index.apply(DropPlan(items: [.project(Self.id(index, "D"))], toFolder: nil, atIndex: 1))
        #expect(Self.rootNames(index) == ["A", "D", "B", "C"])
    }

    @Test func reorderAtRoot_renumbersContiguously() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B", "C"])
        index.apply(DropPlan(items: [.project(Self.id(index, "C"))], toFolder: nil, atIndex: 0))
        #expect(index.sidebarItems.map(\.position) == [0, 1, 2])
    }

    // MARK: - Folders reorder, and interleave with projects

    @Test func folderReordersAmongRootProjects() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B"])
        let folder = index.addFolder(name: "Client")
        #expect(Self.rootNames(index) == ["Client", "A", "B"])

        index.apply(DropPlan(items: [.folder(folder.id)], toFolder: nil, atIndex: 2))
        #expect(Self.rootNames(index) == ["A", "Client", "B"])
    }

    @Test func mixedFolderAndProject_dragTogether() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B", "C"])
        let folder = index.addFolder(name: "Client")
        // ["Client", "A", "B", "C"] → move Client + C to the end.
        index.apply(DropPlan(items: [.folder(folder.id), .project(Self.id(index, "C"))],
                             toFolder: nil, atIndex: DropRouting.append))
        #expect(Self.rootNames(index) == ["A", "B", "Client", "C"])
    }

    // MARK: - Cross-scope moves

    @Test func intoFolder_setsMembershipAndPosition() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B"])
        let folder = index.addFolder(name: "Client")
        let a = Self.id(index, "A")

        index.apply(DropPlan(items: [.project(a)], toFolder: folder.id,
                             atIndex: DropRouting.append))
        #expect(index.projects.first { $0.id == a }?.folderId == folder.id)
        #expect(index.projectsInFolder(folder.id).map(\.name) == ["A"])
        #expect(Self.rootNames(index) == ["Client", "B"])
    }

    /// The bug `moveProject` had: it set `folderId` and left `position` alone, so a
    /// project leaving a folder carried its in-folder index into the root scope and
    /// collided with an unrelated row. `sidebarItems`' sort has no tiebreak, so tied
    /// rows could swap places between renders.
    @Test func outOfFolder_toRoot_leavesNoCollidingPositions() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B", "C"])
        let folder = index.addFolder(name: "Client")
        let inner = index.addProject(name: "Inner", path: "/tmp/Inner", intoFolder: folder.id)

        index.apply(DropPlan(items: [.project(inner.id)], toFolder: nil, atIndex: 1))

        #expect(index.projects.first { $0.id == inner.id }?.folderId == nil)
        #expect(Self.rootNames(index) == ["Client", "Inner", "A", "B", "C"])
        let positions = index.sidebarItems.map(\.position)
        #expect(positions == Array(0..<positions.count))
        #expect(Set(positions).count == positions.count)   // no duplicates → no tie
    }

    @Test func betweenFolders_renumbersBothScopes() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folderA = index.addFolder(name: "A")
        let folderB = index.addFolder(name: "B")
        index.addProject(name: "A2", path: "/tmp/A2", intoFolder: folderA.id)
        let a1 = index.addProject(name: "A1", path: "/tmp/A1", intoFolder: folderA.id)
        index.addProject(name: "B1", path: "/tmp/B1", intoFolder: folderB.id)

        #expect(index.projectsInFolder(folderA.id).map(\.name) == ["A1", "A2"])

        index.apply(DropPlan(items: [.project(a1.id)], toFolder: folderB.id,
                             atIndex: DropRouting.append))

        #expect(index.projectsInFolder(folderA.id).map(\.name) == ["A2"])
        #expect(index.projectsInFolder(folderB.id).map(\.name) == ["B1", "A1"])
        #expect(index.projectsInFolder(folderA.id).map(\.position) == [0])
        #expect(index.projectsInFolder(folderB.id).map(\.position) == [0, 1])
    }

    @Test func reorderWithinFolder() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        let folder = index.addFolder(name: "Client")
        index.addProject(name: "Third", path: "/tmp/3", intoFolder: folder.id)
        index.addProject(name: "Second", path: "/tmp/2", intoFolder: folder.id)
        let first = index.addProject(name: "First", path: "/tmp/1", intoFolder: folder.id)
        #expect(index.projectsInFolder(folder.id).map(\.name) == ["First", "Second", "Third"])

        index.apply(DropPlan(items: [.project(first.id)], toFolder: folder.id,
                             atIndex: DropRouting.append))
        #expect(index.projectsInFolder(folder.id).map(\.name) == ["Second", "Third", "First"])
    }

    // MARK: - Persistence

    @Test func order_survivesReload() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }
        let fileURL = tempDir.appendingPathComponent("projects.json")

        Self.seedRootProjects(index, ["A", "B", "C"])
        index.apply(DropPlan(items: [.project(Self.id(index, "C"))], toFolder: nil, atIndex: 0))
        #expect(Self.rootNames(index) == ["C", "A", "B"])

        let reloaded = ProjectIndex(fileURL: fileURL)
        #expect(Self.rootNames(reloaded) == ["C", "A", "B"])
    }

    // MARK: - The Move To menu shares the same path

    /// `moveProject` is the Move-To context menu. It names a destination but no slot,
    /// so it appends — and, routed through `apply`, renumbers like a drag does rather
    /// than carrying a stale index into the new scope.
    @Test func moveProject_appendsAndRenumbers() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B", "C"])
        let folder = index.addFolder(name: "Client")
        let inner = index.addProject(name: "Inner", path: "/tmp/Inner", intoFolder: folder.id)
        index.addProject(name: "Also", path: "/tmp/Also", intoFolder: folder.id)

        index.moveProject(projectId: inner.id, toFolder: nil)

        #expect(index.projects.first { $0.id == inner.id }?.folderId == nil)
        #expect(Self.rootNames(index).last == "Inner")
        let positions = index.sidebarItems.map(\.position)
        #expect(positions == Array(0..<positions.count))
        #expect(index.projectsInFolder(folder.id).map(\.position) == [0])
    }

    @Test func emptyPlan_isANoOp() {
        let (index, tempDir) = Self.makeTempIndex()
        defer { Self.cleanup(tempDir) }

        Self.seedRootProjects(index, ["A", "B"])
        index.apply(DropPlan(items: [], toFolder: nil, atIndex: 0))
        #expect(Self.rootNames(index) == ["A", "B"])
    }
}
