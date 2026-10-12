import Foundation
import Testing
@testable import Bristlenose

/// A watcher must follow its folder when Finder renames it.
///
/// `presentedItemURL` was fixed at lease creation and the presenter had no
/// `presentedItemDidMove(to:)`, so after a rename the app's bookmark followed
/// the folder while every scan went on asking the old path — and nothing
/// upstream heard that the project had moved, so the serve stayed on the old
/// path too (measured 12 Oct 2026: a re-analyse after a rename ran at the new
/// path and was never imported).
@Suite("ProjectFolderWatcher follows a rename")
struct ProjectFolderWatcherMoveTests {

    private func makeFolder() throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-watcher-move-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// Rename through `NSFileCoordinator`, which is how Finder does it and the
    /// only way an in-process presenter is told.
    private func coordinatedRename(_ from: URL, to: URL) throws {
        let coordinator = NSFileCoordinator(filePresenter: nil)
        var coordinationError: NSError?
        var moveError: Error?
        coordinator.coordinate(
            writingItemAt: from, options: .forMoving,
            writingItemAt: to, options: .forReplacing,
            error: &coordinationError
        ) { src, dst in
            do {
                try FileManager.default.moveItem(at: src, to: dst)
                coordinator.item(at: src, didMoveTo: dst)
            } catch {
                moveError = error
            }
        }
        if let coordinationError { throw coordinationError }
        if let moveError { throw moveError }
    }

    /// A watcher that has published its first scan is registered with the
    /// coordinator and listening. Moving the folder before that races the
    /// registration: under a full-suite load the move was coordinated with no
    /// presenter to tell (one timeout in 1849, 12 Oct 2026). Wait for the state
    /// the test acts on, not a proxy that merely precedes it.
    final class Ready: @unchecked Sendable { var published = false }

    private func waitUntil(_ deadline: Duration = .seconds(5),
                           _ condition: @escaping () -> Bool) async -> Bool {
        let clock = ContinuousClock()
        let end = clock.now + deadline
        while clock.now < end {
            if condition() { return true }
            try? await Task.sleep(for: .milliseconds(50))
        }
        return condition()
    }

    @Test func presentedItemURLFollowsTheRename() async throws {
        let old = try makeFolder()
        let new = old.deletingLastPathComponent()
            .appendingPathComponent(old.lastPathComponent + "-renamed")
        defer {
            try? FileManager.default.removeItem(at: old)
            try? FileManager.default.removeItem(at: new)
        }
        let lease = try ProjectBookmarkLease(bookmarkData: old.bookmarkData(options: .withSecurityScope))
        let ready = Ready()
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [], onChange: { _ in ready.published = true }
        )
        defer { watcher.stop() }
        #expect(await waitUntil { ready.published }, "the watcher never published its first scan")

        try coordinatedRename(old, to: new)

        let followed = await waitUntil {
            watcher.presentedItemURL?.standardizedFileURL.path == new.standardizedFileURL.path
        }
        #expect(followed, "watcher still presents \(watcher.presentedItemURL?.path ?? "nil") after the folder moved to \(new.path)")
    }

    /// The owner is told, on the main actor, so `ProjectIndex` can relocate the
    /// project and the serve can follow.
    @Test func theOwnerIsToldWhereTheFolderWent() async throws {
        let old = try makeFolder()
        let new = old.deletingLastPathComponent()
            .appendingPathComponent(old.lastPathComponent + "-renamed")
        defer {
            try? FileManager.default.removeItem(at: old)
            try? FileManager.default.removeItem(at: new)
        }
        final class Box: @unchecked Sendable { var moved: URL? }
        let box = Box()
        let lease = try ProjectBookmarkLease(bookmarkData: old.bookmarkData(options: .withSecurityScope))
        let ready = Ready()
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [],
            onMove: { url in
                dispatchPrecondition(condition: .onQueue(.main))
                box.moved = url
            },
            onChange: { _ in ready.published = true }
        )
        defer { watcher.stop() }
        #expect(await waitUntil { ready.published }, "the watcher never published its first scan")

        try coordinatedRename(old, to: new)

        let told = await waitUntil { box.moved?.standardizedFileURL.path == new.standardizedFileURL.path }
        #expect(told, "onMove was never called with the new path (got \(box.moved?.path ?? "nil"))")
    }
}
