import Foundation
import Testing

@testable import Bristlenose

// Transport-layer tests — the layer three separate reviews called the highest-
// value unbuilt one, and the only layer that can prove the behaviours which
// actually bite.
//
// Everything below is reachable **only** through a stubbed transport. The
// existing suites test the *policy* — does `CloudTransferPolicy.zoom` say to
// strip the header, does `verifyPayload` reject a short read — but a policy
// that is never consulted by the code under test is a decoration. These drive
// the real `CloudDownloader` and the real adapters over a fake network and
// assert what was actually sent and what actually landed on disk.
//
// The seam already existed and was unused: `CloudDownloader.init(session:)` and
// all three adapters take an injectable `URLSession`.

// MARK: - The stub

/// A `URLProtocol` that answers from a queue and records what it was asked.
///
/// Recording the *requests* is the point, not just serving responses: the whole
/// of `CloudTransferPolicy` is a claim about which headers survive a redirect,
/// and that claim is unfalsifiable without seeing the second request.
final class StubURLProtocol: URLProtocol {

    struct Stub {
        var status: Int = 200
        var headers: [String: String] = ["Content-Type": "video/mp4"]
        var body: Data = Data()

        /// A 302 to `location`. `URLSession` will consult the task delegate's
        /// `willPerformHTTPRedirection` before issuing the second request,
        /// which is exactly the hook under test.
        static func redirect(to location: String) -> Stub {
            Stub(status: 302, headers: ["Location": location], body: Data())
        }

        /// An ISO base-media file: four bytes of box length, then `ftyp`.
        static func mp4(bytes: Int) -> Stub {
            var data = Data([0x00, 0x00, 0x00, 0x20]) + Data("ftypisom".utf8)
            if bytes > data.count { data.append(Data(repeating: 0x41, count: bytes - data.count)) }
            return Stub(headers: ["Content-Type": "video/mp4"], body: data)
        }

        /// The failure that produced 880 corrupt files in one real run: an
        /// error page wearing a 200.
        static func htmlErrorPage() -> Stub {
            Stub(status: 200,
                 headers: ["Content-Type": "text/html; charset=utf-8"],
                 body: Data("<!DOCTYPE html><html>Sign in</html>".utf8))
        }

        static func json(_ raw: String, status: Int = 200) -> Stub {
            Stub(status: status,
                 headers: ["Content-Type": "application/json"],
                 body: Data(raw.utf8))
        }
    }

    // URLProtocol callbacks arrive on arbitrary queues, so the shared state is
    // locked rather than merely `nonisolated(unsafe)`.
    private static let lock = NSLock()
    nonisolated(unsafe) private static var queued: [Stub] = []
    nonisolated(unsafe) private static var seen: [URLRequest] = []

    static func reset() {
        lock.lock(); defer { lock.unlock() }
        queued = []; seen = []
    }

    static func enqueue(_ stubs: Stub...) {
        lock.lock(); defer { lock.unlock() }
        queued.append(contentsOf: stubs)
    }

    static var requests: [URLRequest] {
        lock.lock(); defer { lock.unlock() }
        return seen
    }

    /// A session wired to this protocol. `.ephemeral` so nothing is cached
    /// between tests.
    static func session() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        return URLSession(configuration: config)
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lock.lock()
        Self.seen.append(request)
        // An empty queue answers 200-with-nothing rather than hanging, so a
        // test that under-stubs fails on an assertion instead of a timeout.
        let stub = Self.queued.isEmpty ? Stub(body: Data()) : Self.queued.removeFirst()
        Self.lock.unlock()

        guard let url = request.url,
              let response = HTTPURLResponse(url: url, statusCode: stub.status,
                                             httpVersion: "HTTP/1.1",
                                             headerFields: stub.headers)
        else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }

        if (300...399).contains(stub.status), let location = stub.headers["Location"],
           let next = URL(string: location) {
            client?.urlProtocol(self, wasRedirectedTo: URLRequest(url: next),
                                redirectResponse: response)
            client?.urlProtocolDidFinishLoading(self)
            return
        }

        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        if !stub.body.isEmpty { client?.urlProtocol(self, didLoad: stub.body) }
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

// MARK: - Scratch directory

/// A real directory, because the download path's whole contract is about what
/// exists on disk at each moment.
private struct Scratch {
    let url: URL
    init() {
        url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-transport-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }
    func destroy() { try? FileManager.default.removeItem(at: url) }
    func contents() -> [String] {
        (try? FileManager.default.contentsOfDirectory(atPath: url.path)) ?? []
    }
}

// MARK: - Header policy across redirects

/// One parent suite so the three below are serialized **relative to each other**.
///
/// `.serialized` on a suite orders the tests *inside* it; Swift Testing still
/// runs separate suites in parallel. `StubURLProtocol`'s queue and request log
/// are process-global, so three parallel suites interleave their stubs and each
/// one reads someone else's responses.
///
/// This was not theoretical: all three suites passed in isolation and six tests
/// failed in the full run. Isolation is exactly the condition under which this
/// class of bug is invisible — the same shape as a test that passes because a
/// guard short-circuited before the code under test.
@Suite("Cloud transport", .serialized)
struct CloudTransportTests {

@Suite("Header policy across redirects", .serialized)
struct RedirectHeaderTests {

    private func download(
        policy: CloudTransferPolicy,
        token: String? = "SECRET",
        stubs: [StubURLProtocol.Stub]
    ) async throws -> (bytes: Int64, requests: [URLRequest]) {
        StubURLProtocol.reset()
        for stub in stubs { StubURLProtocol.enqueue(stub) }
        let scratch = Scratch()
        defer { scratch.destroy() }

        let downloader = CloudDownloader(session: StubURLProtocol.session())
        let request = CloudDownloadRequest(
            url: URL(string: "https://api.example.test/rec/download/x")!,
            accessToken: token,
            policy: policy,
            expected: ExpectedFile(expectedFormat: .mp4),
            destination: scratch.url.appendingPathComponent("out.mp4")
        )
        let bytes = try await downloader.download(request) { _, _ in }
        return (bytes, StubURLProtocol.requests)
    }

    @Test("Zoom drops Authorization when the CDN redirect crosses hosts")
    func zoomStripsAcrossRedirect() async throws {
        // The finding this exists for: `download_url` redirects to a
        // pre-signed URL on a different host that carries its own credentials,
        // and arriving with both has been reported to 403. URLSession
        // re-attaches headers by default, so the stripping must be ours.
        let (_, requests) = try await download(
            policy: .zoom,
            stubs: [.redirect(to: "https://ssrweb.example.test/signed?sig=abc"),
                    .mp4(bytes: 64)]
        )
        #expect(requests.count == 2)
        #expect(requests[0].value(forHTTPHeaderField: "Authorization") == "Bearer SECRET")
        #expect(requests[1].value(forHTTPHeaderField: "Authorization") == nil)
    }

    @Test("Teams sends no Authorization at all — the URL is the credential")
    func teamsSendsNoHeader() async throws {
        // Graph's downloadUrl carries `tempauth=` in the query string. A bearer
        // alongside it is redundant at best, and §9 forbids the URL reaching a
        // log precisely because it IS the credential.
        let (_, requests) = try await download(
            policy: .teams, token: nil, stubs: [.mp4(bytes: 64)]
        )
        #expect(requests.count == 1)
        #expect(requests[0].value(forHTTPHeaderField: "Authorization") == nil)
    }

    @Test("A same-host redirect still reaches the destination")
    func sameHostRedirect() async throws {
        let (bytes, requests) = try await download(
            policy: .zoom,
            stubs: [.redirect(to: "https://api.example.test/rec/download/y"),
                    .mp4(bytes: 128)]
        )
        #expect(requests.count == 2)
        #expect(bytes == 128)
    }
}

// MARK: - An undeliverable destination

/// The bug a real first download found, on 16 Aug 2026.
///
/// The import window offered "New Project" — an unlocated placeholder whose
/// `path` is the empty string — and `CloudImportWindow.start()` fell back to
/// `URL(fileURLWithPath: project.path)` when no security-scoped lease existed.
/// An empty path resolves to the process's **current working directory**, so
/// the transfer aimed at somewhere the researcher never chose. The window then
/// reported "✓ Imported" and "1 imported", and no file existed anywhere.
///
/// This suite pins the transport half: `download` must not report success for a
/// destination it cannot write. The window half — not offering an undeliverable
/// destination at all — is pinned separately.
@Suite("An undeliverable destination", .serialized)
struct UndeliverableDestinationTests {

    private func attempt(destination: URL) async -> Result<Int64, Error> {
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.mp4(bytes: 4096))
        let downloader = CloudDownloader(session: StubURLProtocol.session())
        let request = CloudDownloadRequest(
            url: URL(string: "https://api.example.test/file")!,
            accessToken: "T",
            policy: .meet,
            expected: ExpectedFile(expectedFormat: .mp4),
            destination: destination
        )
        do { return .success(try await downloader.download(request) { _, _ in }) }
        catch { return .failure(error) }
    }

    @Test("A directory that does not exist is a failure, not an import")
    func nonexistentDirectoryFails() async {
        let dest = URL(fileURLWithPath: "/nonexistent-\(UUID().uuidString)/out.mp4")
        guard case .failure = await attempt(destination: dest) else {
            Issue.record("reported success for a destination it cannot write")
            return
        }
    }

    @Test("An unwritable directory is a failure, not an import")
    func unwritableDirectoryFails() async {
        // /System is real and readable, so this fails at the write rather than
        // at a missing parent — a different code path from the case above.
        let dest = URL(fileURLWithPath: "/System/out-\(UUID().uuidString).mp4")
        guard case .failure = await attempt(destination: dest) else {
            Issue.record("reported success writing into /System")
            return
        }
    }
}

// MARK: - What lands on disk

@Suite("What lands on disk", .serialized)
struct DownloadDiskTests {

    private func attempt(
        stub: StubURLProtocol.Stub,
        expected: ExpectedFile
    ) async -> (result: Result<Int64, Error>, leftovers: [String]) {
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(stub)
        let scratch = Scratch()
        defer { scratch.destroy() }

        let downloader = CloudDownloader(session: StubURLProtocol.session())
        let request = CloudDownloadRequest(
            url: URL(string: "https://api.example.test/file")!,
            accessToken: "T",
            policy: .meet,
            expected: expected,
            destination: scratch.url.appendingPathComponent("interview.mp4")
        )
        do {
            let bytes = try await downloader.download(request) { _, _ in }
            return (.success(bytes), scratch.contents())
        } catch {
            return (.failure(error), scratch.contents())
        }
    }

    @Test("An HTML page with a 200 never becomes a .mp4")
    func htmlNeverLands() async {
        // 880 files in one real run. The status line says success, the body is
        // an apology, and a naive downloader writes it under a video name.
        let (result, leftovers) = await attempt(
            stub: .htmlErrorPage(),
            expected: ExpectedFile(expectedFormat: .mp4))

        guard case .failure = result else {
            Issue.record("an HTML error page was accepted as media")
            return
        }
        // The stronger assertion: nothing at all is left behind — no .mp4, and
        // no orphan .part either.
        #expect(leftovers.isEmpty)
    }

    @Test("A truncated body leaves nothing half-written")
    func truncationLeavesNothing() async {
        // The quiet failure: ffprobe accepts a truncated MP4, Whisper
        // transcribes forty minutes of sixty, and the report reads as a
        // confident analysis of a session it half read.
        let (result, leftovers) = await attempt(
            stub: .mp4(bytes: 400),
            expected: ExpectedFile(sizeBytes: 800, expectedFormat: .mp4))

        guard case .failure(let error) = result,
              case CloudDownloadError.rejected(let verdict) = error else {
            Issue.record("a short read was accepted")
            return
        }
        #expect(verdict == .shortRead(expected: 800, received: 400))
        #expect(leftovers.isEmpty)
    }

    @Test("A hash mismatch is refused even when the size is right")
    func hashMismatchRefused() async {
        // Microsoft is the only platform that publishes a hash before the
        // download, so this is the one place verification is exact rather than
        // heuristic — and size alone would have passed this file.
        let (result, leftovers) = await attempt(
            stub: .mp4(bytes: 64),
            expected: ExpectedFile(
                sizeBytes: 64,
                hash: FileHash(algorithm: .sha256, value: "not-the-real-digest"),
                expectedFormat: .mp4))

        guard case .failure(let error) = result,
              case CloudDownloadError.rejected(let verdict) = error else {
            Issue.record("a hash mismatch was accepted")
            return
        }
        #expect(verdict == .hashMismatch(algorithm: .sha256))
        #expect(leftovers.isEmpty)
    }

    @Test("A good download lands under its real name, with no .part beside it")
    func happyPathPublishes() async {
        let (result, leftovers) = await attempt(
            stub: .mp4(bytes: 256),
            expected: ExpectedFile(sizeBytes: 256, expectedFormat: .mp4))

        guard case .success(let bytes) = result else {
            Issue.record("a valid download was refused: \(result)")
            return
        }
        #expect(bytes == 256)
        // Exactly one file, under the final name — the .part is gone, which is
        // what makes "derive already-imported state from stat" safe.
        #expect(leftovers == ["interview.mp4"])
    }
}

// MARK: - Listing behaviour

@Suite("Listing", .serialized)
struct ListingTransportTests {

    private var window: DateInterval {
        let end = Date()
        return DateInterval(start: Calendar.current.date(byAdding: .day, value: -90, to: end)!,
                            end: end)
    }

    private func zoomTokens() -> ZoomTokens {
        ZoomTokens(accessToken: "T", refreshToken: "R",
                   expiresAt: Date().addingTimeInterval(3600), scopes: ZoomScopes.requested)
    }

    @Test("An unlicensed 401 stops after ONE request — it must never loop")
    func unlicensedNeverLoops() async throws {
        // The failure the Teams classifier exists for. Two 401s look identical
        // to anything reading the status line, and treating the licence one as
        // refresh-and-retry re-authenticates forever against an account that
        // can never work — silently, with the researcher watching a spinner.
        //
        // Ten responses are queued; a looping adapter would consume them all.
        StubURLProtocol.reset()
        for _ in 0..<10 {
            StubURLProtocol.enqueue(.json(
                #"{"error":{"code":"Unauthorized","message":"Invoked API requires a valid license. No valid license found."}}"#,
                status: 401))
        }

        let source = TeamsSource(
            config: MicrosoftOAuthConfig(clientID: "cid", tenant: "common",
                                         redirectURI: "msauth.test://auth"),
            session: StubURLProtocol.session(),
            restoredTokens: MicrosoftTokenResponse(
                data: Data(#"{"access_token":"T","expires_in":3600}"#.utf8))!)
        let listing = await source.list(window: window)

        // The invariant is **no retry loop**, which is precisely "no URL is
        // requested twice" — not "exactly one request". Ten responses were
        // queued; a looping adapter would consume them all.
        let urls = StubURLProtocol.requests.compactMap(\.url?.absoluteString)
        #expect(urls.count == Set(urls).count, "a URL was retried: \(urls)")
        #expect(urls.count < 10)

        // Two calls, not one: after the /Recordings listing fails, `list` still
        // attempts the calendar read for the roster. Harmless — it fails the
        // same way and the list survives without a roster by design — but on an
        // unlicensed account it is a second doomed request, and worth knowing
        // before anyone reads a network trace and suspects a loop.
        #expect(urls.count <= 2)

        // And it surfaces as a licence problem, not as an empty account.
        #expect(!listing.arithmetic.outcome.isComplete)
    }

    @Test("An unfollowed continuation reports pageCapHit, never exhausted")
    func paginationCapIsHonest() async throws {
        // The designed output of this feature and its failure mode are both
        // "a shorter list". A paginator that stops early and reports success
        // is indistinguishable from a study that had fewer sessions — so the
        // terminal state has to be carried, not inferred.
        StubURLProtocol.reset()
        // Eighty, deliberately more than both caps together. A queue sized to
        // the expected count cannot tell "it stopped because the cap held" from
        // "it stopped because the stub ran dry", and the second proves nothing.
        for _ in 0..<80 {
            StubURLProtocol.enqueue(.json(
                #"{"value":[],"@odata.nextLink":"https://graph.microsoft.com/v1.0/next"}"#))
        }

        let source = TeamsSource(
            config: MicrosoftOAuthConfig(clientID: "cid", tenant: "common",
                                         redirectURI: "msauth.test://auth"),
            session: StubURLProtocol.session(),
            restoredTokens: MicrosoftTokenResponse(
                data: Data(#"{"access_token":"T","expires_in":3600}"#.utf8))!)
        let listing = await source.list(window: window)

        guard case .pageCapHit = listing.arithmetic.outcome else {
            Issue.record("an endless paginator reported \(listing.arithmetic.outcome)")
            return
        }
        #expect(!listing.arithmetic.isExact)
        // It stopped rather than spinning. **Two** bounded paginators, not one:
        // the recordings walk caps at 20, and then `list` still reads the
        // calendar for the roster, which caps at 20 of its own. 40 is the sum
        // of two honest bounds, not one loose one.
        //
        // This bound read `<= 21` until 16 Aug 2026, when the calendar read
        // gained pagination and the assertion started failing — correctly. The
        // second paginator was added and the desktop suite was not re-run, so
        // the regression sat for a day in a test whose entire subject is
        // *noticing that a walk did not finish*. Worth the irony being written
        // down rather than quietly corrected.
        #expect(StubURLProtocol.requests.count <= 40,
                "neither paginator may exceed its cap: \(StubURLProtocol.requests.count)")
    }

    @Test("Zoom splits a 90-day window into month-sized requests")
    func zoomChunksTheWindow() async throws {
        // Zoom caps a query at one month and does NOT error on a wider one —
        // it answers for less. A single 90-day call silently loses two thirds
        // of the study, and only the request count can prove the split.
        StubURLProtocol.reset()
        for _ in 0..<10 {
            StubURLProtocol.enqueue(.json(#"{"meetings":[],"total_records":0}"#))
        }

        let source = ZoomSource(
            config: ZoomOAuthConfig(publicClientID: "cid",
                                    redirectURI: "https://example.test/cb"),
            session: StubURLProtocol.session(),
            restoredTokens: zoomTokens())
        _ = await source.list(window: window)

        #expect(StubURLProtocol.requests.count == 3)
        // Each chunk carries its own explicit from/to — omitting them makes
        // Zoom answer for TODAY ONLY, which reads as an empty account.
        for request in StubURLProtocol.requests {
            let query = request.url?.query ?? ""
            #expect(query.contains("from="))
            #expect(query.contains("to="))
        }
    }

    @Test("A denial wearing HTTP 200 is not read as an empty account")
    func zoomDenialIsNotEmpty() async throws {
        // Zoom delivers "You do not have the right permissions" with a 200
        // status line. Read as success it means "you have no recordings", and
        // the researcher concludes the session was never recorded.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(
            .json(#"{"code":200,"message":"You do not have the right permissions."}"#))

        let source = ZoomSource(
            config: ZoomOAuthConfig(publicClientID: "cid",
                                    redirectURI: "https://example.test/cb"),
            session: StubURLProtocol.session(),
            restoredTokens: zoomTokens())
        let listing = await source.list(window: window)

        #expect(listing.rows.isEmpty)
        // The distinction that matters: not-exhausted, so the footer cannot
        // print a confident total over a refusal.
        #expect(!listing.arithmetic.outcome.isComplete)
    }
}
}
