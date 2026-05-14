import Testing
import Foundation
@testable import Bristlenose

/// Tests for ProjectBookmarkLease — Mini-spec 3 RAII security-scope holder.
///
/// The lifetime invariant is the contract: while a lease exists, the security
/// scope on `url` is open; when it deinitialises, the scope is released.
/// This invariant is silent — scope mismanagement produces no console error,
/// just folder-watcher (NSFilePresenter) callbacks failing to fire.
///
/// NOTE: BristlenoseTests target is not wired into Xcode yet (qa-backlog).
/// These tests are aspirational reference code that compiles standalone.
@Suite("ProjectBookmarkLease")
struct ProjectBookmarkLeaseTests {

    /// Build a security-scoped bookmark for a freshly-created temporary
    /// directory and return the bookmark data + URL for cleanup.
    private func makeTempBookmark() throws -> (data: Data, dir: URL) {
        let tempRoot = FileManager.default.temporaryDirectory
        let dir = tempRoot.appendingPathComponent("bn-lease-test-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let data = try dir.bookmarkData(options: .withSecurityScope)
        return (data, dir)
    }

    @Test func lease_resolves_url_and_keeps_scope_open() throws {
        let (data, dir) = try makeTempBookmark()
        defer { try? FileManager.default.removeItem(at: dir) }

        let lease = try ProjectBookmarkLease(bookmarkData: data)
        // URL is resolved.
        #expect(lease.url.standardizedFileURL == dir.standardizedFileURL)
        // Not yet released — invariant intact.
        #expect(lease.isReleased == false)
        // Holding the lease, the URL is readable.
        let contents = try FileManager.default.contentsOfDirectory(atPath: lease.url.path)
        #expect(contents.isEmpty)
    }

    @Test func release_is_idempotent() throws {
        let (data, dir) = try makeTempBookmark()
        defer { try? FileManager.default.removeItem(at: dir) }

        let lease = try ProjectBookmarkLease(bookmarkData: data)
        #expect(lease.isReleased == false)
        lease.release()
        #expect(lease.isReleased == true)
        // Second release is a no-op — doesn't crash, flag stays true.
        lease.release()
        #expect(lease.isReleased == true)
    }

    @Test func deinit_releases_scope_when_release_was_not_called() throws {
        let (data, dir) = try makeTempBookmark()
        defer { try? FileManager.default.removeItem(at: dir) }

        // Scope this in a do-block so the lease deinits on exit.
        do {
            let lease = try ProjectBookmarkLease(bookmarkData: data)
            #expect(lease.isReleased == false)
            // Don't call release(); let deinit handle it.
        }
        // No assertion on post-deinit state (the object is gone). If deinit
        // had failed to release scope, subsequent leases / processes would
        // accumulate stale scope tickets — invisible until exhaustion. We
        // can at minimum re-acquire a fresh lease against the same data
        // without OS-level rejection.
        let fresh = try ProjectBookmarkLease(bookmarkData: data)
        #expect(fresh.isReleased == false)
    }

    @Test func refreshedBookmarkData_returns_non_nil_for_live_url() throws {
        let (data, dir) = try makeTempBookmark()
        defer { try? FileManager.default.removeItem(at: dir) }

        let lease = try ProjectBookmarkLease(bookmarkData: data)
        let refreshed = lease.refreshedBookmarkData()
        #expect(refreshed != nil)
        #expect(refreshed?.isEmpty == false)
    }

    @Test func resolveFailed_thrown_for_corrupt_data() {
        let garbage = Data([0xDE, 0xAD, 0xBE, 0xEF, 0x00, 0x01, 0x02, 0x03])
        do {
            _ = try ProjectBookmarkLease(bookmarkData: garbage)
            Issue.record("Expected resolveFailed error, got success")
        } catch BookmarkLeaseError.resolveFailed {
            // Expected.
        } catch {
            Issue.record("Expected resolveFailed, got \(error)")
        }
    }
}
