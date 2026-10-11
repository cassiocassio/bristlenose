import Foundation
import Testing
@testable import Bristlenose

/// A released folder watcher must actually be freed.
///
/// `NSFileCoordinator` retains its registered presenters, and the watcher
/// unregistered itself only in `deinit` — which therefore never ran. Every
/// watcher ever released (a project removed, gone missing, or switched out of
/// `.ready`) stayed alive with its security-scoped lease open and its scans
/// still running. Measured before the fix: dropping the last reference left
/// the watcher alive. `releaseLeaseAndWatcher` now calls `stop()`.
@Suite("ProjectFolderWatcher lifetime")
struct ProjectFolderWatcherLifetimeTests {

    private func makeWatcher() throws -> (ProjectFolderWatcher, URL) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-watcher-life-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let lease = try ProjectBookmarkLease(bookmarkData: dir.bookmarkData(options: .withSecurityScope))
        let watcher = ProjectFolderWatcher(
            projectID: UUID(), lease: lease, initialKnownBasenames: [], onChange: { _ in }
        )
        return (watcher, dir)
    }

    @Test func stoppedAndReleasedWatcherIsFreed() async throws {
        weak var weakWatcher: ProjectFolderWatcher?
        var dir: URL?
        do {
            let (watcher, d) = try makeWatcher()
            weakWatcher = watcher
            dir = d
            watcher.stop()
        }
        defer { if let dir { try? FileManager.default.removeItem(at: dir) } }
        // The initial scan and the stop's queue hop each hold the watcher
        // briefly; give them a moment.
        try await Task.sleep(for: .milliseconds(500))
        // If this fails: something still retains a stopped watcher, so its
        // lease (the security scope) and its scans outlive the project.
        #expect(weakWatcher == nil)
    }
}
