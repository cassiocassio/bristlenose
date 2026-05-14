import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "bookmark-lease")

/// Errors thrown when acquiring a security-scoped bookmark lease.
enum BookmarkLeaseError: Error, CustomStringConvertible {
    /// Bookmark resolved but `startAccessingSecurityScopedResource()` returned false.
    /// Typically means the user revoked folder access via System Settings, or the
    /// app no longer has the `files.user-selected.read-write` entitlement.
    case scopeRefused

    /// Bookmark data could not be resolved at all (volume unmounted, bookmark
    /// corrupt, or the underlying file deleted with no replacement found).
    case resolveFailed(underlying: Error)

    var description: String {
        switch self {
        case .scopeRefused:
            return "scopeRefused"
        case .resolveFailed(let err):
            return "resolveFailed(\(err))"
        }
    }
}

/// Holds an open security-scoped bookmark for the lifetime of the lease.
///
/// **Lifetime invariant:** while a `ProjectBookmarkLease` exists, the security
/// scope on `url` is open. The scope is released when the lease deinitialises.
///
/// **Why this can't be a per-read helper:** `NSFilePresenter` callbacks
/// (folder watcher in #14) fire arbitrary times after registration. If scope
/// was opened/closed per read, the callbacks find scope closed and fail
/// silently. The lease holds scope open for the entire watcher's lifetime.
///
/// **Usage:**
/// - `ProjectIndex` (or its caller) holds one lease per `ready` project.
/// - Borrowers (file watcher, copy worker, sidecar spawn) receive `lease.url`
///   and do NOT call `start/stopAccessingSecurityScopedResource` themselves.
/// - The lease is released (set to nil) when the project transitions to
///   `cantFind` or `inCloud(downloading:)`.
///
/// **Stale bookmark handling:** if the resolved bookmark is stale, the lease
/// still succeeds (the URL is valid for this session), but the caller may
/// invoke `refreshedBookmarkData()` to persist a fresh bookmark for the next
/// launch. This is intentionally pull-based rather than fire-and-forget —
/// callers know where the persistence layer is; the lease doesn't.
final class ProjectBookmarkLease {

    /// Resolved file URL with security scope open.
    let url: URL

    /// True if the bookmark resolved but was marked stale. Callers should
    /// rewrite `projects.json` with a fresh bookmark via `refreshedBookmarkData()`.
    let isStale: Bool

    /// True once `stopAccessingSecurityScopedResource()` has been called.
    /// Used by tests; production code should rely on `deinit`.
    private(set) var isReleased: Bool = false

    /// Acquire a lease from persisted bookmark data.
    /// - Throws: `BookmarkLeaseError.resolveFailed` if the bookmark can't be
    ///           resolved (volume unmounted, corrupt, target deleted).
    ///           `BookmarkLeaseError.scopeRefused` if scope grant failed.
    init(bookmarkData: Data) throws {
        var stale = false
        let resolved: URL
        do {
            resolved = try URL(
                resolvingBookmarkData: bookmarkData,
                options: [.withSecurityScope],
                relativeTo: nil,
                bookmarkDataIsStale: &stale
            )
        } catch {
            throw BookmarkLeaseError.resolveFailed(underlying: error)
        }
        guard resolved.startAccessingSecurityScopedResource() else {
            throw BookmarkLeaseError.scopeRefused
        }
        self.url = resolved
        self.isStale = stale
        if stale {
            log.info("bookmark resolved stale; caller should refresh persisted data")
        }
    }

    /// Generate a fresh bookmark data blob from the currently-open URL.
    /// Returns nil if regeneration fails (rare — scope is open, file exists).
    /// Callers typically write the result back into `projects.json` so the
    /// next launch starts with a non-stale bookmark.
    func refreshedBookmarkData() -> Data? {
        try? url.bookmarkData(options: .withSecurityScope)
    }

    /// Manually release the scope. Idempotent. Normally not needed — `deinit`
    /// releases automatically. Exposed for tests and any code path that wants
    /// to release scope eagerly before the lease falls out of scope.
    func release() {
        guard !isReleased else { return }
        url.stopAccessingSecurityScopedResource()
        isReleased = true
    }

    deinit {
        if !isReleased {
            url.stopAccessingSecurityScopedResource()
        }
    }
}
