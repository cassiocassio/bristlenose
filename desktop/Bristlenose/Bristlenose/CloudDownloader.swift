import CryptoKit
import Foundation

// The one download path all three adapters use.
//
// Engine choice, per §7: `URLSession` download tasks, not `CopyMachinery`.
// `CopyMachinery`'s ring, hover-cancel and subtitle slot are reusable; its
// *engine* is not — it is single-in-flight, its transport is a local
// `FileManager.copyItem`, and its `rollback(written:)` deletes every
// already-written file on cancel. That last property would destroy the recovery
// path §6 is built on, where the unit of recovery is the file and an
// interrupted batch loses at most one file's progress.
//
// `OllamaDownloadModel` is the in-tree precedent for a large network transfer
// with streaming progress and cooperative cancel, and this follows its shape.

/// Per-platform transfer policy — the three genuine differences between how
/// Teams, Meet and Zoom hand over bytes.
///
/// Everything *else* about downloading is identical, which is the whole reason
/// this file exists once rather than three times.
struct CloudTransferPolicy: Equatable {

    /// How the request proves who it is.
    enum Authorization: Equatable {
        /// Send `Authorization: Bearer …`. Google and Zoom's initial request.
        case bearer
        /// Send nothing — the URL carries its own credential.
        ///
        /// Graph's `@microsoft.graph.downloadUrl` arrives pre-authenticated
        /// with a `tempauth=` token **in the query string**, which is exactly
        /// why §9 forbids logging these URLs: the URL *is* the credential.
        case preAuthorizedURL
    }

    let authorization: Authorization

    /// Whether to keep sending the header after a cross-host redirect.
    ///
    /// **False for Zoom, and that is load-bearing.** `download_url` redirects
    /// from `zoom.us` to a pre-signed CDN URL on `ssrweb.zoom.us` that carries
    /// its own credentials; a signed URL arriving with *both* a signature and
    /// an `Authorization` header has been reported to 403. `URLSession`
    /// re-attaches headers across redirects by default, so this must be said
    /// explicitly. Python's `requests` strips it automatically, which is why so
    /// much shipped Zoom code works by accident.
    let keepAuthorizationAcrossRedirect: Bool

    static let teams = CloudTransferPolicy(
        authorization: .preAuthorizedURL,
        keepAuthorizationAcrossRedirect: false
    )
    static let meet = CloudTransferPolicy(
        authorization: .bearer,
        keepAuthorizationAcrossRedirect: true
    )
    static let zoom = CloudTransferPolicy(
        authorization: .bearer,
        keepAuthorizationAcrossRedirect: false
    )

    static func `for`(_ platform: CloudPlatform) -> CloudTransferPolicy {
        switch platform {
        case .teams: return .teams
        case .meet:  return .meet
        case .zoom:  return .zoom
        }
    }
}

/// One file's transfer request.
struct CloudDownloadRequest {
    let url: URL
    /// Nil when the policy is `.preAuthorizedURL`.
    let accessToken: String?
    let policy: CloudTransferPolicy
    let expected: ExpectedFile
    /// Where it lands, already named by `CloudDownloadNaming`.
    let destination: URL
}

enum CloudDownloadError: LocalizedError {
    case rejected(DownloadVerdict)
    case insufficientSpace(needed: Int64, available: Int64)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .rejected(let verdict):
            return verdict.rowMessage
        case .insufficientSpace(let needed, let available):
            let f = ByteCountFormatter.string(fromByteCount:countStyle:)
            return "Not enough disk space — \(f(needed, .file)) needed, \(f(available, .file)) free."
        case .cancelled:
            return "Stopped."
        }
    }

    /// The row's version: a case, not a sentence. `errorDescription` above is
    /// the log's version and stays English on purpose.
    ///
    /// The byte figures do not survive the trip — `CloudFetchFailure` is a plain
    /// enum so its key derives from `rawValue`, and "Not enough disk space." is
    /// the actionable half anyway. The numbers remain in `errorDescription`,
    /// which is what the log records.
    var fetchFailure: CloudFetchFailure {
        switch self {
        case .rejected(let verdict):  return verdict.fetchFailure ?? .downloadFailed
        case .insufficientSpace:      return .notEnoughSpace
        // Every caller tests `.cancelled` before asking, because a stop is not
        // a failure and must not draw a red row.
        case .cancelled:              return .downloadFailed
        }
    }
}

/// Performs a verified download.
///
/// Deliberately not an `ObservableObject` and not `@MainActor`: this is the
/// transport, and the batch above it owns concurrency, ordering and UI state.
/// Keeping it inert makes it usable from a task group without the store's
/// isolation leaking into the network layer.
final class CloudDownloader: NSObject {

    private let session: URLSession
    private let fileManager: FileManager

    /// Set per-request so the redirect delegate knows the policy. A stored
    /// property rather than a parameter because `URLSessionTaskDelegate` gives
    /// no route to pass context into the redirect callback.
    ///
    /// **Defaults to the strict policy, not `.meet`.** It is overwritten before
    /// any request goes out, so the value is unreachable — but this decides
    /// whether a bearer token crosses a host boundary, and the fail-safe default
    /// for that is "strip". A future path that redirects before assignment
    /// should leak nothing.
    private var currentPolicy = CloudTransferPolicy(
        authorization: .bearer,
        keepAuthorizationAcrossRedirect: false
    )

    /// True when this object built the session and must therefore tear it down.
    /// An un-invalidated `URLSession` leaks for the life of the process, and
    /// this type is constructed **once per downloaded file** — so a 20-file
    /// batch leaked 20 sessions before this existed.
    private let ownsSession: Bool

    /// Set for the duration of one transfer so the delegate's progress
    /// callbacks can reach the caller. Same reasoning as `currentPolicy`:
    /// `URLSessionDownloadDelegate` offers no route to pass context in.
    private var progressHandler: (@Sendable (Int64, Int64?) -> Void)?

    /// The session task behind the current transfer, captured in
    /// `didCreateTask` so its byte counters can be sampled. Written on the
    /// delegate queue and read from the sampling task, hence the lock.
    private let taskLock = NSLock()
    private var _currentTask: URLSessionTask?
    private var currentTask: URLSessionTask? {
        get { taskLock.withLock { _currentTask } }
        set { taskLock.withLock { _currentTask = newValue } }
    }

    /// How often a transfer's byte count is read while it runs.
    static let progressSampleInterval: Duration = .milliseconds(250)

    init(session: URLSession? = nil, fileManager: FileManager = .default) {
        self.fileManager = fileManager
        // A configuration of our own so the redirect delegate is guaranteed to
        // be consulted; `URLSession.shared` cannot take one — and `.shared`
        // would also write meeting metadata and redirect `Location` headers to
        // the app container's on-disk cache, which is not ours to keep.
        self.ownsSession = (session == nil)
        self.session = session ?? CloudNetworking.makeSession()
        super.init()
    }

    deinit {
        // Lets the transfer finish, then releases the session. Only when we
        // built it: an injected one belongs to the caller.
        if ownsSession { session.finishTasksAndInvalidate() }
    }

    /// Downloads, verifies, and only then puts the file under its real name.
    ///
    /// The sequence is the point:
    ///  1. free-space precheck — before a byte moves
    ///  2. response head — before the destination exists
    ///  3. stream to `.part`
    ///  4. size, magic bytes, hash — while still `.part`
    ///  5. atomic replace
    ///
    /// A failure at any step leaves either nothing or a `.part` file, never a
    /// plausible-looking recording. That is what makes "derive already-imported
    /// state, never store it" safe: what you can see on disk is true.
    func download(
        _ request: CloudDownloadRequest,
        progress: @escaping @Sendable (Int64, Int64?) -> Void
    ) async throws -> Int64 {

        // 1 — room to land.
        if let needed = request.expected.sizeBytes {
            let available = CopyMachinery.availableBytes(at: request.destination.deletingLastPathComponent())
            guard CloudDownloadVerification.hasRoom(forBytes: needed, available: available) else {
                throw CloudDownloadError.insufficientSpace(needed: needed, available: available ?? 0)
            }
        }

        currentPolicy = request.policy
        var urlRequest = URLRequest(url: request.url)
        if request.policy.authorization == .bearer, let token = request.accessToken {
            urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let partURL = request.destination.appendingPathExtension("part")
        // A leftover .part from an interrupted run is not resumable state we
        // trust — Range support is undocumented on Zoom and unproven on the
        // others — so it is replaced rather than appended to. Appending to
        // bytes of unknown provenance is precisely how a corrupt file gets a
        // clean size.
        try? fileManager.removeItem(at: partURL)

        // 2/3 — transfer to the system's own temp location.
        //
        // A download *task*, not `URLSession.bytes`. The byte-sequence API
        // reads pleasantly and is the wrong tool here: iterating an 800 MB
        // recording one `UInt8` at a time spends the whole transfer in Swift
        // array bookkeeping rather than in the network. The task streams to
        // disk in the kernel's own buffers and reports progress through the
        // delegate.
        //
        // **Progress is sampled, not delivered.** The async
        // `download(for:delegate:)` never calls `didWriteData` — not on the
        // task delegate, not on a session delegate — and KVO on
        // `task.progress` fires once at the start and once at the end.
        // Measured 30 Sep 2026 on macOS 27 against a 100 MB file: zero
        // `didWriteData` calls and two KVO ticks, while `countOfBytesReceived`
        // rose steadily across thirty 250 ms samples. So every row sat on
        // "Queued" with nothing moving until the file landed, on all three
        // platforms. The delegate method stays below in case a future OS
        // honours it; the sampler is what the row actually runs on.
        self.progressHandler = progress
        self.currentTask = nil
        let fallbackTotal = request.expected.sizeBytes
        let sampler = Task { [weak self] in
            var last: Int64 = -1
            while true {
                // A thrown sleep is the stop signal. `try?` here would run the
                // body once more after cancellation — exactly the late sample
                // the lock below exists to rule out.
                do { try await Task.sleep(for: Self.progressSampleInterval) } catch { return }
                guard let self else { return }
                // Read and report under the lock the teardown clears the task
                // with. Once `defer` has nilled it, no sample is mid-flight, so
                // every progress hop is queued ahead of the caller's
                // continuation — the store clears the row's bar on settling,
                // and a sample landing after that would put it back on a row
                // already marked Imported, with a cancel button that does
                // nothing. `progress` only builds a value and enqueues a hop,
                // so calling it under the lock cannot re-enter here.
                self.taskLock.withLock {
                    guard let task = self._currentTask else { return }
                    let received = task.countOfBytesReceived
                    guard received != last else { return }
                    last = received
                    let expected = task.countOfBytesExpectedToReceive
                    // Zoom's CDN often omits Content-Length; the listing's
                    // size is the next best denominator, nil the last.
                    progress(received, expected > 0 ? expected : fallbackTotal)
                }
            }
        }
        defer {
            sampler.cancel()
            self.progressHandler = nil
            self.currentTask = nil
        }

        let (tempURL, response) = try await session.download(for: urlRequest, delegate: self)

        // Judge the response before anything reaches the project folder. The
        // bytes exist by now — they are in the system temp dir — but nothing
        // has appeared where the researcher can see it, which is the property
        // that matters.
        let http = response as? HTTPURLResponse
        let verdict = CloudDownloadVerification.inspectResponse(
            status: http?.statusCode ?? 0,
            contentType: http?.value(forHTTPHeaderField: "Content-Type")
        )
        guard verdict.isUsable else {
            try? fileManager.removeItem(at: tempURL)
            throw CloudDownloadError.rejected(verdict)
        }
        if Task.isCancelled {
            try? fileManager.removeItem(at: tempURL)
            throw CloudDownloadError.cancelled
        }

        // 4 — prove it, still outside the destination name.
        let written = (try? fileManager.attributesOfItem(atPath: tempURL.path)[.size] as? Int64) ?? 0
        let head = Self.readHead(of: tempURL, count: MediaFormat.probeLength)
        let computed = request.expected.hash?.algorithm == .sha256
            ? Self.sha256Hex(of: tempURL)
            : nil

        let payload = CloudDownloadVerification.verifyPayload(
            received: written,
            head: head,
            expected: request.expected,
            computedHash: computed
        )
        guard payload.isUsable else {
            try? fileManager.removeItem(at: tempURL)
            throw CloudDownloadError.rejected(payload)
        }

        // 5 — publish, in two moves for one reason.
        //
        // The system temp dir is frequently on a different volume from the
        // project folder, and a cross-volume move is a copy — not atomic. So
        // the copy lands under `.part`, where a crash leaves something
        // obviously unfinished, and only the final same-volume rename makes the
        // real name appear. That rename IS atomic, so the destination path
        // never names a partial file for even an instant.
        try? fileManager.removeItem(at: partURL)
        try fileManager.moveItem(at: tempURL, to: partURL)
        _ = try? fileManager.removeItem(at: request.destination)
        try fileManager.moveItem(at: partURL, to: request.destination)
        progress(written, written)
        return written
    }

    /// Publishes bytes we produced ourselves the way step 5 above publishes a
    /// download: written beside the destination as `.part`, then one
    /// same-volume rename, so the destination never names a partial file for
    /// even an instant. The transcript the import writes next to a recording is
    /// the second caller — one atomic writer, not two (design-cloud-import-
    /// transcripts.md §0a).
    ///
    /// On failure the `.part` is removed and the error rethrown; the
    /// destination is untouched.
    static func publish(_ data: Data, to destination: URL, fileManager: FileManager = .default) throws {
        let part = destination.appendingPathExtension("part")
        try? fileManager.removeItem(at: part)
        do {
            try data.write(to: part)
            _ = try? fileManager.removeItem(at: destination)
            try fileManager.moveItem(at: part, to: destination)
        } catch {
            try? fileManager.removeItem(at: part)
            throw error
        }
    }

    /// The first few bytes, for the magic-number check. Reads a handle rather
    /// than the file, so a 2 GB recording costs sixteen bytes to identify.
    static func readHead(of url: URL, count: Int) -> [UInt8] {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return [] }
        defer { try? handle.close() }
        guard let data = try? handle.read(upToCount: count) else { return [] }
        return [UInt8](data)
    }

    /// Streams the file through SHA-256 rather than loading it.
    ///
    /// Only reached when the platform supplied a `sha256Hash` up front, which
    /// today means Microsoft alone — the one vendor of the three that makes
    /// exact verification possible instead of heuristic.
    static func sha256Hex(of url: URL) -> String? {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        var hasher = SHA256()
        while let chunk = try? handle.read(upToCount: 1_048_576), !chunk.isEmpty {
            hasher.update(data: chunk)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
}

extension CloudDownloader: URLSessionDownloadDelegate {

    /// Required by the protocol. The `download(for:delegate:)` async form hands
    /// the finished file back through its return value, so this is deliberately
    /// empty rather than doing the move — doing it here as well would race the
    /// return and delete the file out from under it.
    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didFinishDownloadingTo location: URL
    ) {}

    func urlSession(
        _ session: URLSession,
        downloadTask: URLSessionDownloadTask,
        didWriteData bytesWritten: Int64,
        totalBytesWritten: Int64,
        totalBytesExpectedToWrite: Int64
    ) {
        // `NSURLSessionTransferSizeUnknown` (-1) is common on these hosts —
        // Zoom's CDN in particular often omits Content-Length — so an unknown
        // total is reported as nil rather than as -1, and the UI shows an
        // indeterminate bar instead of a progress ring stuck at "-100%".
        let total = totalBytesExpectedToWrite > 0 ? totalBytesExpectedToWrite : nil
        progressHandler?(totalBytesWritten, total)
    }
}

extension CloudDownloader: URLSessionTaskDelegate {
    /// The one per-task callback the async API does deliver — and the only
    /// route to the task whose byte counters the progress sampler reads.
    func urlSession(_ session: URLSession, didCreateTask task: URLSessionTask) {
        currentTask = task
    }

    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        guard !currentPolicy.keepAuthorizationAcrossRedirect else {
            completionHandler(request)
            return
        }
        var stripped = request
        stripped.setValue(nil, forHTTPHeaderField: "Authorization")
        completionHandler(stripped)
    }
}
