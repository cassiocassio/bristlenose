import Foundation

// One session shape for every cloud-import request, and one redirect policy for
// the calls that were not covered by any.
//
// Before this file existed, each adapter defaulted to `URLSession.shared` and
// `CloudDownloader` built a fresh `URLSession(configuration: .default)` per
// file. Both carry `URLCache.shared` and `HTTPCookieStorage.shared`, so meeting
// subjects, attendee addresses and redirect `Location` headers were written to
// the app container's on-disk cache — outside the project folder, surviving a
// delete of `bristlenose-output/`, and not cleared on sign-out. And a session
// that is never invalidated leaks for the process's life, once per downloaded
// file.

enum CloudNetworking {

    /// A session that keeps nothing.
    ///
    /// `.ephemeral` already holds cache and cookies in memory rather than on
    /// disk; the three explicit nils are belt-and-braces, and they are the lines
    /// that state the intent — participant data must not outlive the process,
    /// because none of it is ours to keep.
    ///
    /// - Parameter delegate: retained by the session until it is invalidated,
    ///   which is why every caller must invalidate. See `CloudSessionOwner`.
    static func makeSession(delegate: URLSessionDelegate? = nil) -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
    }
}

/// Strips `Authorization` the moment a redirect changes host.
///
/// This governs the **metadata** calls — listing, identity, preflight,
/// pagination — which previously had no task delegate at all, so URLSession's
/// default applied. That default is to *re-attach* the header, which matters
/// most on the one call that follows a URL taken from a response body:
/// Graph's `@odata.nextLink`. A tenant-shaped answer that redirected elsewhere
/// would have carried the bearer with it.
///
/// Deliberately stricter than `CloudTransferPolicy`: on a metadata call a
/// cross-host redirect has no legitimate use, so there is no per-platform
/// dial here. The download path keeps its own policy, because a pre-signed CDN
/// hand-off is exactly what those redirects are *for*.
final class CloudMetadataRedirectPolicy: NSObject, URLSessionTaskDelegate {

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        let fromHost = task.originalRequest?.url?.host?.lowercased()
        let toHost = request.url?.host?.lowercased()
        guard fromHost != toHost else {
            completionHandler(request)
            return
        }
        var stripped = request
        stripped.setValue(nil, forHTTPHeaderField: "Authorization")
        completionHandler(stripped)
    }
}

/// Holds a session and invalidates it exactly once.
///
/// `URLSession` retains its delegate until invalidated, and an un-invalidated
/// session leaks until the process exits — so "who invalidates this?" needs an
/// answer that is not "whoever remembers". Each adapter owns one of these for
/// its lifetime; `CloudDownloader` owns one per transfer only when it built the
/// session itself.
final class CloudSessionOwner {

    let session: URLSession
    private let ownsSession: Bool
    private var invalidated = false
    /// Held because the session's own reference is weak-ish in practice: the
    /// delegate must outlive the requests that use it.
    private let policy: CloudMetadataRedirectPolicy?

    /// Builds and owns an ephemeral, redirect-policed session.
    init() {
        let policy = CloudMetadataRedirectPolicy()
        self.policy = policy
        self.session = CloudNetworking.makeSession(delegate: policy)
        self.ownsSession = true
    }

    /// Adopts a session someone else owns — the seam the transport tests use to
    /// inject a `URLProtocol` stub. Adopted sessions are never invalidated here,
    /// because this object did not create them.
    init(adopting session: URLSession) {
        self.session = session
        self.ownsSession = false
        self.policy = nil
    }

    /// Lets in-flight work finish, then tears the session down. Idempotent.
    func finish() {
        guard ownsSession, !invalidated else { return }
        invalidated = true
        session.finishTasksAndInvalidate()
    }

    deinit { finish() }
}
