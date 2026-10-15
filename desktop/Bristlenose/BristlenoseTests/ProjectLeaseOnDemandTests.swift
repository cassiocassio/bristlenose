import Foundation
import Testing
@testable import Bristlenose

/// The folder-watcher cap favours the projects in use, and a project past it
/// still gets its folder access the moment something asks.
///
/// Before 15 Oct 2026 the first fifty projects in list order took the watchers
/// and the fifty-first got none, so `leaseURL` returned nil and its callers
/// fell back to a bare path with no sandbox extension (register row 34).
@MainActor
@Suite("Project leases on demand")
struct ProjectLeaseOnDemandTests {

    /// The cap is set before any project is added: `addProject` syncs the
    /// watchers, and a cap lowered afterwards evicts nothing.
    private func makeIndex(folders: Int, cap: Int) throws -> (ProjectIndex, [Project], URL) {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-lease-demand-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
        index.watcherCap = cap
        var made: [Project] = []
        for n in 0..<folders {
            let dir = root.appendingPathComponent("study-\(n)")
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            made.append(index.addProject(name: "study-\(n)", path: dir.path))
        }
        return (index, made, root)
    }

    @Test func theCapFavoursTheMostRecentlyOpened() throws {
        let (index, made, root) = try makeIndex(folders: 2, cap: 1)
        defer { try? FileManager.default.removeItem(at: root) }
        let old = made[0], recent = made[1]
        #expect(old.bookmarkData != nil && recent.bookmarkData != nil,
                "the test needs real bookmarks to take leases")
        index.updateLastOpened(id: recent.id)
        index.syncWatchers()
        #expect(index.hasWatcher(projectID: recent.id) == true)
        #expect(index.hasWatcher(projectID: old.id) == false)
    }

    @Test func aProjectPastTheCapGetsALeaseWhenAsked() throws {
        let (index, made, root) = try makeIndex(folders: 2, cap: 1)
        defer { try? FileManager.default.removeItem(at: root) }
        let old = made[0], recent = made[1]
        index.updateLastOpened(id: recent.id)
        index.syncWatchers()
        #expect(index.hasWatcher(projectID: old.id) == false)

        let url = index.leaseURL(projectID: old.id)
        #expect(url != nil, "a project past the cap got no lease when asked")
        #expect(index.hasWatcher(projectID: old.id) == true)
        #expect(index.hasWatcher(projectID: recent.id) == false,
                "the cap was exceeded instead of the other watcher giving way")

        // A later sync must not thrash it back.
        index.syncWatchers()
        #expect(index.hasWatcher(projectID: old.id) == true)
    }

    /// At launch nothing has been opened yet this session, so the order the
    /// index syncs in is the only thing deciding who gets the watchers.
    @Test func atLaunchTheCapFavoursTheMostRecentlyOpened() async throws {
        let (index, _, root) = try makeIndex(folders: 2, cap: 2)
        defer { try? FileManager.default.removeItem(at: root) }
        let file = root.appendingPathComponent("projects.json")
        // The project LOWER in the list is opened last, so list order and
        // recency disagree. A second apart: projects.json stores whole
        // seconds, and a tie falls back to list order.
        let first = index.projects[0].id
        let second = index.projects[1].id
        index.updateLastOpened(id: first)
        try await Task.sleep(for: .milliseconds(1100))
        index.updateLastOpened(id: second)

        let relaunched = ProjectIndex(fileURL: file, watcherCap: 1)
        #expect(relaunched.hasWatcher(projectID: second) == true,
                "the cap went to the project higher in the list, not the one opened last")
        #expect(relaunched.hasWatcher(projectID: first) == false)
    }

    @Test func orderIsByLastOpenedThenCreation() {
        let now = Date()
        let a = Project(id: UUID(), name: "a", path: "/a", createdAt: now.addingTimeInterval(-300))
        let b = Project(id: UUID(), name: "b", path: "/b", createdAt: now.addingTimeInterval(-100))
        let c = Project(id: UUID(), name: "c", path: "/c", createdAt: now.addingTimeInterval(-500),
                        lastOpened: now)
        #expect(ProjectIndex.watcherOrder([a, b, c]).map(\.name) == ["c", "b", "a"])
    }
}
