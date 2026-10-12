import Foundation
import Testing
@testable import Bristlenose

/// Every path change the index makes is announced, so the window showing the
/// project can move its serve. Before 12 Oct 2026 a relocation healed the
/// bookmark and nothing else: the serve kept polling the old path for a
/// `run_completed` that was being written at the new one.
@MainActor
@Suite("ProjectIndex path-change announcement")
struct ProjectIndexPathChangedTests {

    @Test func relocatingAProjectPostsItsNewPath() async throws {
        let (index, dir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(dir) }
        let project = index.addProject(name: "Moving", path: "/tmp/was-here")

        final class Box: @unchecked Sendable { var notes: [(UUID, String)] = []; var pathAtPost: String? }
        let box = Box()
        let token = NotificationCenter.default.addObserver(
            forName: .bristlenoseProjectPathChanged, object: nil, queue: .main
        ) { note in
            if let id = note.userInfo?["id"] as? UUID, let path = note.userInfo?["path"] as? String {
                box.notes.append((id, path))
                // Delivery is synchronous; the window's handler rescans the
                // project at the path the INDEX holds, so it must already be
                // the new one here (review finding 3 — it was posted first).
                box.pathAtPost = MainActor.assumeIsolated { index.projects.first?.path }
            }
        }
        defer { NotificationCenter.default.removeObserver(token) }

        index.relocateProject(id: project.id, newPath: "/tmp/now-here")

        #expect(box.notes.map(\.0) == [project.id])
        #expect(box.notes.map(\.1) == ["/tmp/now-here"])
        #expect(box.pathAtPost == "/tmp/now-here", "the index still held the old path when the change was announced")
        #expect(index.projects.first?.path == "/tmp/now-here")
    }

    /// Move to Trash is a coordinated move. It must not be followed: the
    /// project would be served from the bin and Empty Trash would destroy an
    /// Analyse written there (review finding 6).
    @Test func aMoveIntoTheTrashIsNotFollowed() {
        let (index, dir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(dir) }
        let project = index.addProject(name: "Binned", path: "/Users/r/Documents/Study")
        final class Box: @unchecked Sendable { var count = 0 }
        let box = Box()
        let token = NotificationCenter.default.addObserver(
            forName: .bristlenoseProjectPathChanged, object: nil, queue: .main
        ) { _ in box.count += 1 }
        defer { NotificationCenter.default.removeObserver(token) }

        index.projectFolderDidMove(id: project.id, to: URL(fileURLWithPath: "/Users/r/.Trash/Study"))

        #expect(index.projects.first?.path == "/Users/r/Documents/Study")
        #expect(box.count == 0)
    }

    @Test func trashDetectionCoversTheHomeTrashAndVolumeTrashes() {
        #expect(ProjectIndex.isInTrash(URL(fileURLWithPath: "/Users/r/.Trash/Study")))
        #expect(ProjectIndex.isInTrash(URL(fileURLWithPath: "/Volumes/T7/.Trashes/501/Study")))
        #expect(!ProjectIndex.isInTrash(URL(fileURLWithPath: "/Users/r/Documents/Study")))
        #expect(!ProjectIndex.isInTrash(URL(fileURLWithPath: "/Users/r/Documents/Trash research/Study")))
    }

    /// A watcher-reported move to the path the project already has is not a
    /// change — no announcement, no serve restart.
    @Test func aMoveToTheSamePathIsSilent() {
        let (index, dir) = ProjectIndexTests.makeTempIndex()
        defer { ProjectIndexTests.cleanup(dir) }
        let project = index.addProject(name: "Still", path: "/tmp/still-here")
        final class Box: @unchecked Sendable { var count = 0 }
        let box = Box()
        let token = NotificationCenter.default.addObserver(
            forName: .bristlenoseProjectPathChanged, object: nil, queue: .main
        ) { _ in box.count += 1 }
        defer { NotificationCenter.default.removeObserver(token) }

        index.projectFolderDidMove(id: project.id, to: URL(fileURLWithPath: "/tmp/still-here"))

        #expect(box.count == 0)
    }
}
