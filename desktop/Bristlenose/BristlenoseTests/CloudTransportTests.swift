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
        /// When set, the request fails at the transport rather than answering.
        var failure: URLError?

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

        /// The connection never completed — no status line at all.
        ///
        /// A distinct outcome from any HTTP status, and since 18 Aug 2026 the
        /// adapters branch on precisely that difference: a 4xx from the token
        /// endpoint is the provider refusing, while this is a train tunnel. One
        /// destroys the stored grant, the other must not.
        static func transportFailure(_ error: URLError.Code = .notConnectedToInternet) -> Stub {
            Stub(failure: URLError(error))
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

        if let failure = stub.failure {
            client?.urlProtocol(self, didFailWithError: failure)
            return
        }

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

    @Test("The recordings listing addresses the special folder, never the English path")
    func recordingsUsesSpecialFolderAlias() async throws {
        // Graph documents `special/recordings` as existing precisely to avoid a
        // path lookup "which would require localization". The hardcoded
        // `/drive/root:/Recordings:` path was therefore a bug on every
        // non-English tenant — and one that surfaced as an empty list
        // misdiagnosed as the wrong account tier, which is a confident wrong
        // answer rather than a visible failure.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"value":[]}"#))
        StubURLProtocol.enqueue(.json(#"{"value":[]}"#))   // the roster read

        _ = await teamsSource().list(window: window)

        let urls = StubURLProtocol.requests.compactMap(\.url?.absoluteString)
        let listing = try #require(urls.first)
        #expect(listing.contains("/drive/special/recordings/children"))
        #expect(!listing.contains("root:"), "the localised path is back: \(listing)")
    }

    @Test("A folder that isn't there is an empty list, not a permissions problem")
    func absentFolderWithReadableDriveIsNotDenied() async throws {
        // The trap the alias introduces. Graph answers **403 or 404** when a
        // read-only app asks for a special folder that does not exist, and the
        // classifier maps 403 to `scopeNotGranted` — so a researcher who simply
        // has not recorded yet would be told to re-consent a permission they
        // already hold, which is an instruction that cannot work.
        //
        // Reading the drive is the discriminator: if it answers, we hold
        // `Files.Read` and the refusal is about the folder.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"error":{"code":"accessDenied","message":"denied"}}"#,
                                      status: 403))
        StubURLProtocol.enqueue(.json(#"{"driveType":"business"}"#))

        let source = teamsSource()
        let listing = await source.list(window: window)

        #expect(listing.rows.isEmpty)
        #expect(listing.arithmetic.outcome.isComplete,
                "an absent folder was reported as a failed listing")
        #expect(source.accountTier != .personal,
                "a business drive must not be mistaken for a personal account")
    }

    @Test("A personal account is named from the drive, not guessed from a status code")
    func personalTierComesFromTheDrive() async throws {
        // A personal account attaches the recording to the meeting chat and
        // never creates the folder, so the refusal is identical to the business
        // case above. The tier is what tells them apart, and it is a *field* —
        // the old code inferred it from a 404, which is exactly the guess that
        // told a business tenant it was a consumer account.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"error":{"code":"itemNotFound","message":"not found"}}"#,
                                      status: 404))
        StubURLProtocol.enqueue(.json(#"{"driveType":"personal"}"#))

        let source = teamsSource()
        let listing = await source.list(window: window)

        #expect(listing.rows.isEmpty)
        #expect(source.accountTier == .personal)
    }

    @Test("A denial we cannot rule out stays a denial")
    func unreadableDriveKeepsTheError() async throws {
        // The other half, and the one that would rot silently: if the drive is
        // unreadable too, we have no evidence the grant is intact, so swallowing
        // the refusal as "you have no recordings" would hide a real permission
        // failure behind the feature's own designed output — an empty list.
        StubURLProtocol.reset()
        for _ in 0..<4 {
            StubURLProtocol.enqueue(.json(#"{"error":{"code":"accessDenied","message":"denied"}}"#,
                                          status: 403))
        }

        let listing = await teamsSource().list(window: window)

        #expect(listing.rows.isEmpty)
        #expect(!listing.arithmetic.outcome.isComplete,
                "a permission failure was reported as a complete, empty listing")
    }

    @Test("A restored token that has aged out renews before it is used")
    func expiredRestoredTokenRenewsFirst() async throws {
        // The whole point of keeping a sign-in is that it outlives the window —
        // so on the restore path an hour-old token is the ORDINARY case, not the
        // edge one. Without this the common experience of a remembered sign-in
        // is a 401 and a sign-in prompt nobody needed, which is indistinguishable
        // from the persistence never having worked.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"access_token":"NEW","expires_in":3600}"#))
        StubURLProtocol.enqueue(.json(#"{"value":[]}"#))   // the listing
        StubURLProtocol.enqueue(.json(#"{"value":[]}"#))   // the roster

        let listing = await teamsSource(tokens: expiredToken()).list(window: window)

        let urls = StubURLProtocol.requests.compactMap(\.url?.absoluteString)
        let first = try #require(urls.first)
        #expect(first.contains("/oauth2/v2.0/token"),
                "the listing ran before the token was renewed: \(urls)")
        #expect(listing.arithmetic.outcome.isComplete)
    }

    @Test("A refused renewal gives up once — a revoked grant fails identically forever")
    func refusedRenewalDoesNotLoop() async throws {
        // A refresh token the tenant has revoked will fail the same way on every
        // attempt, so retrying converts one honest sign-in into an unbreakable
        // loop of failed listings. Four responses are queued; giving up consumes
        // exactly one.
        StubURLProtocol.reset()
        for _ in 0..<4 {
            StubURLProtocol.enqueue(.json(#"{"error":"invalid_grant"}"#, status: 400))
        }

        let listing = await teamsSource(tokens: expiredToken()).list(window: window)

        #expect(StubURLProtocol.requests.count == 1,
                "a revoked grant was retried: \(StubURLProtocol.requests.count) requests")
        #expect(!listing.arithmetic.outcome.isComplete)
        #expect(listing.rows.isEmpty)
    }

    private func expiredToken() -> MicrosoftTokenResponse {
        MicrosoftTokenResponse(accessToken: "OLD", refreshToken: "R",
                               expiresAt: Date().addingTimeInterval(-3600))
    }

    private func teamsSource(
        tokens: MicrosoftTokenResponse? = nil,
        onGrantChanged: (@Sendable (MicrosoftGrant?) -> Void)? = nil
    ) -> TeamsSource {
        TeamsSource(
            config: MicrosoftOAuthConfig(clientID: "cid", tenant: "common",
                                         redirectURI: "msauth.test://auth"),
            session: StubURLProtocol.session(),
            restoredTokens: tokens ?? MicrosoftTokenResponse(
                data: Data(#"{"access_token":"T","expires_in":3600}"#.utf8))!,
            onGrantChanged: onGrantChanged)
    }

    // MARK: - The tier reaches Settings ▸ Accounts

    // Both halves of one seam, and the producer half is the one that can die
    // silently: Settings ▸ Accounts makes no network calls, so if the adapter
    // stops writing the verdict the pane simply shows nothing — which is also
    // exactly what it correctly shows for an account nobody has listed yet.
    // A dead producer and a working one are indistinguishable from the pane.

    @Test("A personal account's tier is written onto the grant, not just held in memory")
    func personalTierIsPersisted() async throws {
        // Without this the pane can never say it. `source.accountTier` being
        // right — which `personalTierComesFromTheDrive` already pins — buys
        // nothing on its own, because that value dies with the window.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"error":{"code":"itemNotFound","message":"not found"}}"#,
                                      status: 404))
        StubURLProtocol.enqueue(.json(#"{"driveType":"personal"}"#))

        let published = Published()
        let source = teamsSource(onGrantChanged: { published.record($0) })
        _ = await source.list(window: window)

        #expect(published.last??.driveType == "personal",
                "the pane reads this field and makes no call of its own")
    }

    @Test("A work account's tier rides the listing it came free with")
    func businessTierIsPersisted() async throws {
        // The ordinary path: `parentReference.driveType` is already on every
        // item, so this costs no extra request. Pinned because a positively
        // *known* business account is what stops the pane inferring anything
        // from silence.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"value":[{"id":"1","name":"2026-08-12 14-00-00.mp4","size":100,"createdDateTime":"2026-08-12T14:00:00Z","parentReference":{"driveType":"business"}}]}"#))
        StubURLProtocol.enqueue(.json(#"{"value":[]}"#))   // the roster read

        let published = Published()
        let source = teamsSource(onGrantChanged: { published.record($0) })
        _ = await source.list(window: window)

        #expect(published.last??.driveType == "business")
    }

    @Test("An unchanged tier does not rewrite the Keychain item on every listing")
    func unchangedTierIsNotRepublished() async throws {
        // `publishTierIfChanged` guards on a real change. Without the guard
        // every listing would rewrite the stored grant for no new fact — and a
        // write is the operation that can fail, race a concurrent refusal, or
        // lose a rekey.
        StubURLProtocol.reset()
        for _ in 0..<2 {
            StubURLProtocol.enqueue(.json(#"{"value":[{"id":"1","name":"2026-08-12 14-00-00.mp4","size":100,"createdDateTime":"2026-08-12T14:00:00Z","parentReference":{"driveType":"business"}}]}"#))
            StubURLProtocol.enqueue(.json(#"{"value":[]}"#))
        }

        let published = Published()
        let source = teamsSource(onGrantChanged: { published.record($0) })
        _ = await source.list(window: window)
        let afterFirst = published.count
        _ = await source.list(window: window)

        #expect(published.count == afterFirst,
                "the second listing established nothing new")
    }

    /// Collects grant publishes off whatever thread the writer contract allows.
    private final class Published: @unchecked Sendable {
        private let lock = NSLock()
        private var grants: [MicrosoftGrant?] = []
        func record(_ grant: MicrosoftGrant?) {
            lock.lock(); defer { lock.unlock() }
            grants.append(grant)
        }
        var last: MicrosoftGrant?? {
            lock.lock(); defer { lock.unlock() }
            return grants.last
        }
        var count: Int {
            lock.lock(); defer { lock.unlock() }
            return grants.count
        }
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
        //
        // 40 → 41 on 18 Aug 2026, and the same way: `list` gained a `/me`
        // backfill for a sign-in whose address never arrived, so an adapter
        // restored without one makes exactly one extra request. Two bounded
        // paginators plus one bookkeeping call. It is skipped entirely when the
        // listing failed — see `unlicensedNeverLoops`, whose bound is unmoved.
        #expect(StubURLProtocol.requests.count <= 41,
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

        // **Filtered to the listing calls, not every request.** A restored
        // session backfills preflight and identity before it lists, so counting
        // the whole log measures those too — and this test is about the window
        // split. Naming the endpoint also stops it silently passing if the
        // listing stopped happening at all, which is how it first broke.
        let listings = StubURLProtocol.requests.filter {
            $0.url?.path.hasSuffix("/users/me/recordings") == true
        }
        #expect(listings.count == 3)
        // Each chunk carries its own explicit from/to — omitting them makes
        // Zoom answer for TODAY ONLY, which reads as an empty account.
        for request in listings {
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

// MARK: - Deriving rows from a real response shape

/// The layer the outline tests cannot reach.
///
/// `CloudImportOutlineTests` proves the tree groups two rows correctly *given*
/// two rows. Nothing proved the adapter builds two rows from a Google response
/// carrying two recordings — which is precisely where the bug lived: a `.first`
/// that dropped the second half of any stopped-and-restarted interview, in
/// silence, in a feature whose failure output and success output are both a
/// shorter list. A revert to `.first`-shaped logic must fail something.
///
/// Nested inside `CloudTransportTests` for the reason its header explains:
/// `.serialized` orders tests *within* a suite, and `StubURLProtocol`'s queue
/// is process-global, so a sibling top-level suite reads someone else's
/// responses. Written outside first, and it failed exactly that way — passing
/// alone, failing in the full run.
@Suite("Deriving rows", .serialized)
struct AdapterRowDerivationTests {

    private var window: DateInterval {
        let end = Date()
        return DateInterval(start: Calendar.current.date(byAdding: .day, value: -30, to: end)!,
                            end: end)
    }

    private func googleTokens() -> GoogleTokens {
        // `meetReadonly` must be granted or `buildRows` skips the lookup
        // entirely and every row reads "Needs access" — a green test proving
        // nothing.
        GoogleTokens(accessToken: "T", refreshToken: "R",
                     expiresAt: Date().addingTimeInterval(3600),
                     granted: GoogleScopes.requested)
    }

    /// The stub queue is FIFO across every URL, so the order below is the order
    /// `list` actually makes its calls: identity, the calendar page, the
    /// window's conference records, each record's recordings, then the room of
    /// each record that produced a file.
    ///
    /// That last call is what makes the join exact — `spaces.get` returns the
    /// meeting code the calendar event already carries — and omitting it from
    /// this fixture is a good way to watch a booked meeting arrive as an
    /// instant one.
    @Test("Two FILE_GENERATED recordings become two rows of one meeting")
    func twoRecordingsBecomeTwoRows() async throws {
        let start = Date().addingTimeInterval(-3 * 3600)
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]

        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"email":"martin@stmarystrust.example"}"#))
        StubURLProtocol.enqueue(.json("""
        {"items":[{"id":"evt-1","summary":"P05 Interview",
          "start":{"dateTime":"\(iso.string(from: start))"},
          "end":{"dateTime":"\(iso.string(from: start.addingTimeInterval(3600)))"},
          "organizer":{"email":"martin@stmarystrust.example","self":true},
          "conferenceData":{"conferenceId":"abc-defg-hij",
            "conferenceSolution":{"key":{"type":"hangoutsMeet"}}}}]}
        """))
        StubURLProtocol.enqueue(.json("""
        {"conferenceRecords":[{"name":"conferenceRecords/rec-1","space":"spaces/sp-1",
          "startTime":"\(iso.string(from: start))"}]}
        """))
        StubURLProtocol.enqueue(.json("""
        {"recordings":[
          {"name":"r1","state":"FILE_GENERATED","driveDestination":{"file":"file-A"},
           "startTime":"\(iso.string(from: start.addingTimeInterval(120)))",
           "endTime":"\(iso.string(from: start.addingTimeInterval(2040)))"},
          {"name":"r2","state":"FILE_GENERATED","driveDestination":{"file":"file-B"},
           "startTime":"\(iso.string(from: start.addingTimeInterval(2400)))",
           "endTime":"\(iso.string(from: start.addingTimeInterval(4700)))"},
          {"name":"r3","state":"STARTED","driveDestination":{"file":"file-C"}}]}
        """))
        StubURLProtocol.enqueue(.json(#"{"meetingCode":"abc-defg-hij"}"#))

        let source = GoogleMeetSource(
            config: GoogleOAuthConfig(clientID: "cid.apps.googleusercontent.com"),
            session: StubURLProtocol.session(),
            restoredTokens: googleTokens())
        let listing = await source.list(window: window)

        #expect(listing.rows.count == 2, "both halves, not just the first")
        // Same call, so they nest — and the ids differ, or the outline cannot
        // draw both and one tick would queue them both.
        #expect(Set(listing.rows.map(\.meetingID)) == ["evt-1"])
        #expect(Set(listing.rows.map(\.id)).count == 2)
        // The ordinal is what keeps their filenames apart on the path where
        // Google omits the recording's own start.
        #expect(Set(listing.rows.compactMap(\.siblingOrdinal)) == [1, 2])
        // `STARTED` has no bytes behind it yet; offering it would produce a
        // fetch that 404s minutes after the researcher ticks it.
        #expect(listing.rows.allSatisfy { $0.video == .available })
        // Both clocks, and they disagree — which is the whole reason the grid
        // has two columns.
        let first = listing.rows.min { $0.startsAt < $1.startsAt }
        #expect(first?.scheduledAt != nil)
        #expect(first?.recordedAt != nil)
        #expect(first?.scheduledAt != first?.recordedAt)
        #expect(first?.duration == 1_920, "the recording's length, never the booked hour")
    }

    /// The reason the listing was inverted, end to end.
    ///
    /// A call started from the Meet home screen has no calendar event, so the
    /// old event-first walk produced no row for it at all — not a dimmed one,
    /// not a footer count. Two of five real recordings were invisible this way
    /// on a live tenant (16 Aug 2026).
    ///
    /// The booked meeting in the same window is here to prove the other half:
    /// an unmatched recording must not be quietly glued onto the nearest
    /// booking, which is exactly what a time-overlap join would have done.
    @Test("A recording with no calendar event becomes its own row")
    func instantMeetingBecomesItsOwnRow() async throws {
        let booked = Date().addingTimeInterval(-5 * 3600)
        let called = Date().addingTimeInterval(-2 * 3600)
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]

        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"email":"martin@stmarystrust.example"}"#))
        StubURLProtocol.enqueue(.json("""
        {"items":[{"id":"evt-1","summary":"P05 Interview",
          "start":{"dateTime":"\(iso.string(from: booked))"},
          "end":{"dateTime":"\(iso.string(from: booked.addingTimeInterval(3600)))"},
          "organizer":{"email":"martin@stmarystrust.example","self":true},
          "conferenceData":{"conferenceId":"abc-defg-hij",
            "conferenceSolution":{"key":{"type":"hangoutsMeet"}}}}]}
        """))
        // One call in the window, and it is not that meeting's room.
        StubURLProtocol.enqueue(.json("""
        {"conferenceRecords":[{"name":"conferenceRecords/rec-9","space":"spaces/sp-9",
          "startTime":"\(iso.string(from: called))"}]}
        """))
        StubURLProtocol.enqueue(.json("""
        {"recordings":[{"name":"r1","state":"FILE_GENERATED",
          "driveDestination":{"file":"file-Z"},
          "startTime":"\(iso.string(from: called.addingTimeInterval(60)))",
          "endTime":"\(iso.string(from: called.addingTimeInterval(74)))"}]}
        """))
        StubURLProtocol.enqueue(.json(#"{"meetingCode":"osp-jwrt-wff"}"#))

        let source = GoogleMeetSource(
            config: GoogleOAuthConfig(clientID: "cid.apps.googleusercontent.com"),
            session: StubURLProtocol.session(),
            restoredTokens: googleTokens())
        let listing = await source.list(window: window)

        #expect(listing.rows.count == 2, "the booking and the unbooked call")

        let instant = try #require(listing.rows.first { $0.isUnscheduled })
        // The code is the only name this call has ever had, and it is what
        // keeps two of them in one day apart — in the list and on disk.
        #expect(instant.title == "osp-jwrt-wff")
        #expect(instant.scheduledAt == nil)
        #expect(instant.scheduledDuration == nil)
        #expect(instant.recordedAt != nil)
        #expect(instant.duration == 14)
        #expect(instant.video == .available, "there is a file and we can reach it")

        let meeting = try #require(listing.rows.first { !$0.isUnscheduled })
        #expect(meeting.title == "P05 Interview")
        // The whole point: a recording in a different room is never annexed to
        // a booking just because it happened nearby.
        #expect(meeting.video == .notRecorded)
        #expect(meeting.isUnscheduled == false)
    }

    /// The blanket-claim guard, one layer below the blanket.
    ///
    /// "We could not read your calls" and "nobody recorded anything" arrive at
    /// the row as the same empty set, and rendering the first as the second
    /// puts *None of these were recorded* over a month of interviews that are
    /// all sitting in Drive.
    @Test("A refused conference-record list never reads as 'not recorded'")
    func refusedHarvestDoesNotClaimNotRecorded() async throws {
        let booked = Date().addingTimeInterval(-5 * 3600)
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]

        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"email":"martin@stmarystrust.example"}"#))
        StubURLProtocol.enqueue(.json("""
        {"items":[{"id":"evt-1","summary":"P05 Interview",
          "start":{"dateTime":"\(iso.string(from: booked))"},
          "end":{"dateTime":"\(iso.string(from: booked.addingTimeInterval(3600)))"},
          "organizer":{"email":"martin@stmarystrust.example","self":true},
          "conferenceData":{"conferenceId":"abc-defg-hij",
            "conferenceSolution":{"key":{"type":"hangoutsMeet"}}}}]}
        """))
        StubURLProtocol.enqueue(.json(
            #"{"error":{"code":403,"status":"PERMISSION_DENIED","message":"denied"}}"#,
            status: 403))

        let source = GoogleMeetSource(
            config: GoogleOAuthConfig(clientID: "cid.apps.googleusercontent.com"),
            session: StubURLProtocol.session(),
            restoredTokens: googleTokens())
        let listing = await source.list(window: window)

        let row = try #require(listing.rows.first)
        #expect(row.video == .unsupported, "'Unavailable' is what we actually know")
        #expect(row.video != .notRecorded)
    }

    /// Teams has always had the meeting's own clock in hand — Graph serves
    /// `start` and `end` on the matched event — and simply never passed it on,
    /// so the Scheduled column stood empty for a reason that looked like a
    /// platform limit and was ours.
    @Test("Teams populates the meeting clock from the matched calendar event")
    func teamsCarriesTheScheduledClock() async throws {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        let booked = Date().addingTimeInterval(-2 * 3600)
        let landed = booked.addingTimeInterval(240)

        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json("""
        {"value":[{"id":"item-1","name":"P04 Interview-20260816_090000-Meeting Recording.mp4",
          "size":1048576,"createdDateTime":"\(iso.string(from: landed))",
          "parentReference":{"driveType":"business"},
          "file":{"mimeType":"video/mp4"},
          "video":{"duration":3131000},
          "@microsoft.graph.downloadUrl":"https://example.invalid/d"}]}
        """))
        StubURLProtocol.enqueue(.json("""
        {"value":[{"id":"cal-1","subject":"P04 Interview",
          "start":{"dateTime":"\(iso.string(from: booked))"},
          "end":{"dateTime":"\(iso.string(from: booked.addingTimeInterval(3600)))"},
          "organizer":{"emailAddress":{"address":"martin@example.invalid"}}}]}
        """))

        let source = TeamsSource(
            config: MicrosoftOAuthConfig(clientID: "cid", tenant: "common",
                                         redirectURI: "msauth.test://auth"),
            session: StubURLProtocol.session(),
            restoredTokens: MicrosoftTokenResponse(
                data: Data(#"{"access_token":"T","expires_in":3600}"#.utf8))!)
        let listing = await source.list(window: window)

        let row = try #require(listing.rows.first)
        #expect(row.scheduledAt != nil, "the booked start, from the matched event")
        #expect(row.scheduledDuration == 3600)
        #expect(row.recordedAt != nil, "and when the file landed, separately")
        #expect(row.duration == 3131, "the media facet's own length, in seconds")
        // Flat, always. `matchEvent` is a ±30-minute proximity guess, and
        // grouping on it would nest two unrelated interviews as one call's two
        // halves — hiding the titles that are the only thing telling them apart.
        #expect(row.meetingID == nil)
    }
}

// MARK: - Zoom's single-use refresh token

/// The rotation contract, which is Zoom's alone.
///
/// Google and Microsoft tolerate a refresh token being reused, so their renewal
/// paths can be wasteful without being wrong. Zoom's token is **single-use**:
/// the instant a refresh returns, the token the caller still holds is dead
/// server-side. Every test here pins a consequence of that, and each one guards
/// a failure whose symptom is "I have to sign in to Zoom again" days later,
/// with nothing in between to connect it to a cause.
@Suite("Zoom token rotation", .serialized)
@MainActor
struct ZoomRotationTests {

    private let window = DateInterval(start: Date().addingTimeInterval(-86_400), duration: 86_400)

    private let config = ZoomOAuthConfig(publicClientID: "cid",
                                         redirectURI: "https://bristlenose.test/auth/zoom")

    private func expired() -> ZoomTokens {
        ZoomTokens(accessToken: "OLD", refreshToken: "R1",
                   expiresAt: Date().addingTimeInterval(-3600),
                   scopes: ZoomScopes.requested)
    }

    private func source(
        onGrantChanged: (@Sendable (ZoomGrant?) -> Void)? = nil,
        onRotation: (@Sendable (ZoomGrant) async -> Bool)? = nil
    ) -> ZoomSource {
        ZoomSource(config: config,
                   session: StubURLProtocol.session(),
                   restoredTokens: expired(),
                   onGrantChanged: onGrantChanged,
                   onRotation: onRotation)
    }

    private var rotated: StubURLProtocol.Stub {
        .json(#"{"access_token":"A2","refresh_token":"R2","expires_in":3600}"#)
    }

    private func tokenRequests() -> Int {
        StubURLProtocol.requests.filter {
            $0.url?.host == "zoom.us" && $0.url?.path == "/oauth/token"
        }.count
    }

    @Test("Three concurrent fetches refresh the token exactly once")
    func refreshIsSingleFlight() async throws {
        // **The grant-destroying race, and it is the ordinary shape of a real
        // study rather than an edge case.** `CloudImportStore` runs three
        // fetches at once, and each renews before reading the token. Without a
        // single-flight guard all three send the same single-use token: Zoom
        // honours the first and answers `400 invalid_grant` to the other two,
        // which read as authoritative refusals and tombstone the grant the
        // first call had just successfully renewed. The remaining rows then
        // fail "Signed out." An hour into a twelve-session import is exactly
        // when this fires.
        //
        // Only ONE rotation is queued. If the guard fails, the second and third
        // requests fall through to the stub's empty-200 default — the
        // assertion is about what was *sent*, not what came back.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(rotated)

        let adapter = source()
        await withTaskGroup(of: Void.self) { group in
            for _ in 0..<3 {
                group.addTask { [adapter, window] in _ = await adapter.list(window: window) }
            }
        }

        #expect(tokenRequests() == 1,
                "the single-use token was sent \(tokenRequests()) times")
    }

    @Test("A rotated token is committed before the refresh reports success")
    func rotationPersistsBeforeReturning() async throws {
        // The ordering is the whole contract. `refresh` cannot report success
        // on a path where the replacement was never written, because the token
        // it replaced is already dead — so "saved" has to be established
        // before the caller is told anything.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(rotated)

        let order = Ordering()
        let client = ZoomOAuthClient(config: config,
                                     session: StubURLProtocol.session(),
                                     persist: { order.mark("persisted:\($0.refreshToken)") })
        let renewed = try await client.refresh(expired())
        order.mark("returned")

        // **Asserted as a sequence, not as two outcomes.** Checking only that
        // the token was persisted and that the call returned cannot tell this
        // implementation apart from `Task { try? await persist(refreshed) };
        // return refreshed` — which satisfies both and voids the contract, on a
        // schedule that would pass on a quiet machine and fail under load.
        #expect(order.marks == ["persisted:R2", "returned"])
        #expect(renewed.refreshToken == "R2")
    }

    @Test("A refused save hands back the live token instead of destroying it")
    func persistFailureCarriesTheLiveTokens() async throws {
        // Zoom rotated; we could not write the replacement down. The pair in
        // hand is valid and is the only one that is, so throwing it away would
        // break the running session **and** leave the stored token dead —
        // strictly worse than every alternative. It matters most on an
        // ad-hoc-signed build, where a Keychain refusing every write is the
        // documented ordinary state.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(rotated)

        let client = ZoomOAuthClient(config: config,
                                     session: StubURLProtocol.session(),
                                     persist: { _ in throw PersistRefused() })

        do {
            _ = try await client.refresh(expired())
            Issue.record("the refresh reported success over a save that failed")
        } catch ZoomOAuthError.rotationNotPersisted(let live) {
            // The error carries the working pair. Matched on the case rather
            // than compared whole, because `expiresAt` is computed from
            // `Date()` inside the client and equality would be a clock race.
            #expect(live.accessToken == "A2")
            #expect(live.refreshToken == "R2", "the caller can still carry on with this")
        }
    }

    @Test("A rotation that cannot be stored keeps the session and writes no tombstone")
    func rotationFailureIsNotARevocation() async throws {
        // **The adapter's half of the rotation contract**, which the two
        // neighbouring tests approach from either side without meeting: one
        // injects a throwing `persist` straight into the client, the other
        // exercises the writer and store on their own. This is the branch
        // between them — sink returns false → `GrantNotStored` →
        // `.rotationNotPersisted` → adopt the live pair, publish nothing.
        //
        // It is also the branch that runs on every ad-hoc-signed build, where a
        // Keychain refusing every write is the documented ordinary state. The
        // mutation it catches is tombstoning here, which would turn a full disk
        // into a revocation and leaves every other test in the repo green.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(rotated)
        StubURLProtocol.enqueue(.json(#"{"recording":{"cloud_recording":true}}"#))
        StubURLProtocol.enqueue(.json(#"{"email":"martin@example.org"}"#))
        StubURLProtocol.enqueue(.json(#"{"meetings":[],"total_records":0}"#))

        let published = Published()
        let adapter = source(onGrantChanged: { published.record($0) },
                             onRotation: { _ in false })
        _ = await adapter.list(window: window)

        #expect(published.count == 0,
                "a save we could not complete is not Zoom revoking the account")
        let paths = StubURLProtocol.requests.compactMap(\.url?.path)
        #expect(paths.contains { $0.hasSuffix("/users/me/recordings") },
                "the session continues on the rotated token it is still holding")
    }

    @Test("A restored session still runs the eligibility gate")
    func restoredSessionBackfillsPreflight() async throws {
        // **The hole persistence opened.** `preflight` is assigned in exactly
        // one place — `signIn()` — and a restored grant never calls it. Before
        // the backfill, an account with cloud recording switched off sailed
        // past the gate and rendered as "no recordings in the last 30 days":
        // a factual statement about the wrong question, on what persistence
        // makes the *ordinary* launch path rather than an edge case.
        //
        // Asserted on the requests rather than the rows, because an ineligible
        // account and an empty one produce the same empty list — what tells
        // them apart is that the ineligible one is never listed at all.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"recording":{"cloud_recording":false}}"#))

        let live = ZoomTokens(accessToken: "A", refreshToken: "R",
                              expiresAt: Date().addingTimeInterval(3600),
                              scopes: ZoomScopes.requested)
        let adapter = ZoomSource(config: config,
                                 session: StubURLProtocol.session(),
                                 restoredTokens: live,
                                 restoredIdentity: "martin@example.org")
        _ = await adapter.list(window: window)

        let paths = StubURLProtocol.requests.compactMap(\.url?.path)
        #expect(paths.contains { $0.hasSuffix("/users/me/settings") },
                "the gate has to ask before it can answer")
        #expect(!paths.contains { $0.hasSuffix("/users/me/recordings") },
                "an account that cannot cloud-record must not be listed as though it could")
    }

    @Test("Zoom saying no tombstones the account; a rate limit does not")
    func onlyAnAuthoritativeRefusalTombstones() async throws {
        // Matched by CASE, never by a status range. Teams tests
        // `(400...499).contains(status)`, which sweeps up a 429 — and Zoom's
        // token endpoint is rate-limited, so a burst of renewals is exactly how
        // you earn one. Destroying a working grant over a condition that clears
        // in seconds costs the researcher a consent screen.
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"reason":"Invalid Token!"}"#, status: 400))
        let refusal = Published()
        _ = await source(onGrantChanged: { refusal.record($0) })
            .list(window: window)
        await refusal.waitForRecord()
        #expect(tokenRequests() == 1, "the 400 branch must actually have attempted a refresh")
        #expect(refusal.last??.needsSignIn == true, "a 400 is Zoom saying no")

        StubURLProtocol.reset()
        StubURLProtocol.enqueue(.json(#"{"message":"Too many requests"}"#, status: 429))
        let limited = Published()
        let listing = await source(onGrantChanged: { limited.record($0) })
            .list(window: window)
        try? await Task.sleep(nanoseconds: 150_000_000)
        // **The positive control comes first, because the assertion below is an
        // absence.** Without it this passes whenever the refresh never happened
        // at all — a non-expired token, a short-circuiting guard, or another
        // suite draining the queued 429 from `StubURLProtocol`'s process-wide
        // state. Every one of those failures is silent and green.
        #expect(tokenRequests() == 1, "the 429 branch must actually have attempted a refresh")
        #expect(limited.count == 0, "a 429 must leave the grant exactly where it is")
        // And it must not be *reported* as a dead account either — keeping the
        // grant while telling the researcher to sign in again would undo the
        // whole point one layer up.
        if case .failed(_, let outcome) = listing.arithmetic.outcome,
           case .needsReauthentication = outcome {
            Issue.record("a rate limit was reported as needing re-authentication")
        }
    }

    // MARK: Spies

    /// Records labelled events in the order they happened, off whatever thread
    /// the persist contract allows. Ordering is the assertion, so the spy has
    /// to preserve it rather than just collect values.
    private final class Ordering: @unchecked Sendable {
        private let lock = NSLock()
        private var events: [String] = []
        func mark(_ event: String) {
            lock.lock(); defer { lock.unlock() }
            events.append(event)
        }
        var marks: [String] {
            lock.lock(); defer { lock.unlock() }
            return events
        }
    }

    /// Collects grant publishes. Zoom's publishes are spawned into their own
    /// task, so a test that asserts immediately races them — `waitForRecord`
    /// is the bounded wait, and its absence is what the 429 case asserts.
    private final class Published: @unchecked Sendable {
        private let lock = NSLock()
        private var grants: [ZoomGrant?] = []
        func record(_ grant: ZoomGrant?) {
            lock.lock(); defer { lock.unlock() }
            grants.append(grant)
        }
        var last: ZoomGrant?? {
            lock.lock(); defer { lock.unlock() }
            return grants.last
        }
        var count: Int {
            lock.lock(); defer { lock.unlock() }
            return grants.count
        }
        func waitForRecord() async {
            for _ in 0..<100 where count == 0 {
                try? await Task.sleep(nanoseconds: 10_000_000)
            }
        }
    }

    private struct PersistRefused: Error {}
}
}
