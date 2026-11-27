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
@Suite("ProjectFolderWatcher follows a rename", .timeLimit(.minutes(3)))
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

    /// A callback awaited as an event, with no clock. Both callbacks under test
    /// reach the owner through `DispatchQueue.main.async`, and on CI's runners
    /// the main queue went unserviced for 30 s and more under the parallel
    /// suite: a 5 s deadline failed every run there (12–13 Oct 2026), and the
    /// 30 s that replaced it failed with `onMove` never called in 5 of 13 runs
    /// (24–27 Nov 2026; desktop/gotchas.md, the timed-read entry). Waiting for
    /// the call itself, a slow main queue costs the test time and never its
    /// verdict; the suite's time limit is the guard against a callback that
    /// never comes. The first call wins: one rename, one callback.
    final class Event<Value: Sendable>: @unchecked Sendable {
        private let lock = NSLock()
        private var fired = false
        private var value: Value?
        private var waiter: CheckedContinuation<Value?, Never>?

        func fire(_ v: Value) { settle(v) }

        /// The first value fired, or nil once the test is cancelled.
        func wait() async -> Value? {
            await withTaskCancellationHandler {
                await withCheckedContinuation { (c: CheckedContinuation<Value?, Never>) in
                    let now: (Bool, Value?) = lock.withLock {
                        if fired { return (true, value) }
                        waiter = c
                        return (false, nil)
                    }
                    if now.0 { c.resume(returning: now.1) }
                }
            } onCancel: { settle(nil) }
        }

        private func settle(_ v: Value?) {
            let w: CheckedContinuation<Value?, Never>? = lock.withLock {
                guard !fired else { return nil }
                fired = true
                value = v
                defer { waiter = nil }
                return waiter
            }
            w?.resume(returning: v)
        }
    }

    /// For a state with no callback: the presenter's URL, read with no main hop.
    private func waitUntil(_ deadline: Duration = .seconds(30),
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
        // A watcher that has published its first scan is registered with the
        // coordinator and listening. Moving the folder before that races the
        // registration (one timeout in 1849, 12 Oct 2026).
        let ready = Event<Void>()
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [], onChange: { _ in ready.fire(()) }
        )
        defer { watcher.stop() }
        #expect(await ready.wait() != nil, "the watcher never published its first scan")

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
        let moved = Event<URL>()
        let lease = try ProjectBookmarkLease(bookmarkData: old.bookmarkData(options: .withSecurityScope))
        let ready = Event<Void>()
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [],
            onMove: { url in
                dispatchPrecondition(condition: .onQueue(.main))
                moved.fire(url)
            },
            onChange: { _ in ready.fire(()) }
        )
        defer { watcher.stop() }
        #expect(await ready.wait() != nil, "the watcher never published its first scan")

        try coordinatedRename(old, to: new)

        let told = await moved.wait()
        #expect(told?.standardizedFileURL.path == new.standardizedFileURL.path,
                "onMove was not called with the new path (got \(told?.path ?? "nil"))")
    }
}
