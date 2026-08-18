import Foundation

// The live Zoom adapter.
//
// Three things here are shaped by findings rather than by taste, and each
// prevents a failure that is silent:
//
//  1. **One preflight call answers the whole eligibility question.**
//     `GET /users/me/settings` returns cloud recording, audio transcript and
//     auto-delete in a single response, so the window can say "your plan
//     doesn't do this" once, up front, instead of failing per row.
//  2. **Enumerate every page before downloading anything.** `next_page_token`
//     expires in 15 minutes; an importer that downloads between pages
//     invalidates its own cursor mid-study and silently returns a prefix.
//  3. **Follow the download redirect by hand, stripping the Authorization
//     header.** `download_url` redirects to a pre-signed CDN URL that carries
//     its own credentials; `URLSession` re-attaches headers across redirects by
//     default, and the signed URL has been reported to reject requests that
//     arrive with both.

// MARK: - Wire shapes

private struct ZoomUserSettings: Decodable {
    struct Recording: Decodable {
        let cloud_recording: Bool?
        let recording_audio_transcript: Bool?
        let auto_delete_cmr: Bool?
        let auto_delete_cmr_days: Int?
    }
    let recording: Recording?
}

private struct ZoomRecordingsPage: Decodable {
    struct Meeting: Decodable {
        struct File: Decodable {
            let id: String?
            let file_type: String?
            let recording_type: String?
            let file_size: Int64?
            let download_url: String?
            let recording_start: String?
            let deleted_time: String?
        }
        /// Per-instance. **The dedup key** — `id` is the reusable meeting
        /// number and a recurring interview series shares one across every
        /// session, so keying on it collapses a study into a single row.
        let uuid: String?
        let id: Int64?
        let topic: String?
        let start_time: String?
        let duration: Int?
        let total_size: Int64?
        let auto_delete: Bool?
        let auto_delete_date: String?
        let recording_files: [File]?
    }
    let meetings: [Meeting]?
    let next_page_token: String?
    let total_records: Int?
}

// MARK: - Preflight

/// The answer to "can this researcher use this feature at all", from one call.
///
/// Zoom's real gate is narrower than the plan ladder suggests, and every clause
/// here excludes people the others do not:
///
/// - **Basic is local-only.** Nothing exists in the cloud to fetch, so there is
///   no API surface at all — not an empty list, an absent capability.
/// - **Cloud recording can be off**, at account or group level, and a non-admin
///   token cannot tell "off" from "off and locked by your admin". So the copy
///   says what is true — it is off — and never guesses at whose decision it was.
/// - **The transcript is English-only**, on every plan. For a product shipping
///   in 21 languages that excludes more real researchers than any tier
///   boundary, and it is invisible until a VTT fails to arrive.
struct ZoomPreflight: Equatable {
    let cloudRecordingEnabled: Bool
    let audioTranscriptEnabled: Bool
    let autoDeleteEnabled: Bool
    let autoDeleteDays: Int?

    /// Nil when everything needed is present. Otherwise the single sentence the
    /// window shows instead of a list.
    var blockingReason: String? {
        guard cloudRecordingEnabled else {
            return "Cloud recording is turned off for this Zoom account, so there's nothing for Bristlenose to fetch. "
                + "Recordings saved to your own Mac can still be dragged in from Finder."
        }
        return nil
    }

    /// A caveat rather than a block: the meetings are fetchable, the transcript
    /// will not be there. Stated once rather than discovered per row.
    var transcriptCaveat: String? {
        audioTranscriptEnabled
            ? nil
            : "“Create audio transcript” is off in your Zoom recording settings, so no transcripts will come with these recordings."
    }
}

// MARK: - The adapter

final class ZoomSource: CloudImportSource {
    private let config: ZoomOAuthConfig
    private let sessionOwner: CloudSessionOwner
    private var session: URLSession { sessionOwner.session }
    private var tokens: ZoomTokens?
    private var identity: String?
    private(set) var preflight: ZoomPreflight?

    /// The media file chosen for each row, kept from list time.
    ///
    /// The row itself deliberately does not carry a download URL: those are
    /// credentials (§9 — Zoom's redirects to a pre-signed CDN URL, Graph's
    /// carries `tempauth=` in the query string), and putting one on a value
    /// type that flows into the view layer is how it reaches a log line or a
    /// screenshot. The adapter keeps them; the row hands out nothing.
    private var chosenFiles: [String: ZoomRecordingFile] = [:]

    /// - Parameter restoredTokens: a previously-obtained grant.
    ///
    ///   Forward-looking rather than a test hook: §2 requires the refresh token
    ///   to be restored from the Keychain at launch, so an adapter must be
    ///   constructible already-authenticated. Nothing persists yet, so today
    ///   the only caller that passes this is the transport test suite — which
    ///   is also the only way to drive the listing path over a stub.
    /// - Parameter session: injection seam for the transport tests. Omit it and
    ///   the adapter builds — and owns — an ephemeral, redirect-policed session
    ///   (`CloudNetworking`); an injected one is adopted and never invalidated
    ///   here, because this object did not create it.
    init(config: ZoomOAuthConfig,
         session: URLSession? = nil,
         restoredTokens: ZoomTokens? = nil) {
        self.config = config
        self.sessionOwner = session.map(CloudSessionOwner.init(adopting:)) ?? CloudSessionOwner()
        self.tokens = restoredTokens
    }

    var accountEmail: String? { identity }

    /// Zoom has no consumer/work split to detect — cloud recording is a plan
    /// feature, answered by `preflight` rather than by an address domain. The
    /// protocol still wants a tier, so this reports the honest shape.
    var accountTier: GoogleAccountTier {
        guard let preflight else { return .unknown }
        return preflight.cloudRecordingEnabled
            ? .workspace(domain: identity.flatMap(Self.domain) ?? "")
            : .personal
    }

    private static func domain(_ email: String) -> String? {
        guard let at = email.lastIndex(of: "@") else { return nil }
        return String(email[email.index(after: at)...]).lowercased()
    }

    // MARK: Sign-in

    @MainActor
    func signIn() async throws {
        let client = ZoomOAuthClient(config: config, session: session)
        tokens = try await client.signIn()
        identity = try? await fetchIdentity()
        preflight = try? await fetchPreflight()
    }

    private func fetchIdentity() async throws -> String? {
        struct Me: Decodable { let email: String? }
        let data = try await get("https://api.zoom.us/v2/users/me")
        return (try? JSONDecoder().decode(Me.self, from: data))?.email
    }

    /// One call, three answers. `GET /users/me/settings` returns the `recording`
    /// object by default — there is no `option=recording`, and passing
    /// `option=recording_authentication` returns a *different, narrower*
    /// payload that does not contain any of these fields.
    private func fetchPreflight() async throws -> ZoomPreflight {
        let data = try await get("https://api.zoom.us/v2/users/me/settings")
        let settings = try JSONDecoder().decode(ZoomUserSettings.self, from: data)
        let recording = settings.recording
        return ZoomPreflight(
            cloudRecordingEnabled: recording?.cloud_recording ?? false,
            audioTranscriptEnabled: recording?.recording_audio_transcript ?? false,
            autoDeleteEnabled: recording?.auto_delete_cmr ?? false,
            autoDeleteDays: recording?.auto_delete_cmr_days
        )
    }

    // MARK: Listing

    func list(window: DateInterval) async -> MeetingListing {
        guard tokens != nil else {
            return empty(window, outcome: .failed(after: 0, outcome: .needsReauthentication(reason: "no token")))
        }
        if let preflight, preflight.blockingReason != nil {
            // Eligible-but-empty and ineligible are different answers, and this
            // is the second. Returning an empty list would render as "no
            // recordings in the last 30 days", which is a factual statement
            // about the wrong question.
            return MeetingListing(
                rows: [],
                arithmetic: JoinArithmetic(eventsInWindow: 0, fetchable: 0,
                                           organisedByOthers: 0, outcome: .exhausted),
                window: window
            )
        }

        // Zoom caps a query at one month, and *silently* — a 90-day request
        // does not error, it just answers for less. So the window is split
        // before it is sent, and the chunks are exhausted in full.
        let chunks = ZoomListWindow.chunks(covering: window)
        var meetings: [ZoomRecordingsPage.Meeting] = []
        var outcome: ListOutcome = .exhausted
        var pagesFetched = 0
        let pageCap = 20

        outer: for chunk in chunks {
            var pageToken: String?
            repeat {
                do {
                    let page = try await fetchPage(chunk, pageToken: pageToken)
                    meetings.append(contentsOf: page.meetings ?? [])
                    pageToken = page.next_page_token?.isEmpty == false ? page.next_page_token : nil
                    pagesFetched += 1
                    if pageToken != nil && pagesFetched >= pageCap {
                        outcome = .pageCapHit(pagesFetched: pagesFetched)
                        break outer
                    }
                } catch let error as ZoomAPIError {
                    outcome = .failed(after: pagesFetched, outcome: mapOutcome(error.outcome))
                    break outer
                } catch {
                    outcome = .failed(after: pagesFetched,
                                      outcome: .unexpected(status: 0, reason: error.localizedDescription))
                    break outer
                }
            } while pageToken != nil
        }

        let rows = meetings.compactMap(makeRow)
        return MeetingListing(
            rows: rows,
            arithmetic: JoinArithmetic(
                eventsInWindow: meetings.count,
                fetchable: rows.filter(\.isSelectable).count,
                // Zoom has no not-yours case to count: cloud recordings belong
                // to the host and there is no API surface for recordings you
                // merely attended. Organiser-first is forced here rather than
                // chosen, which makes Zoom a cleaner fit for §4 than either
                // other platform.
                organisedByOthers: 0,
                outcome: outcome
            ),
            window: window
        )
    }

    private func fetchPage(
        _ chunk: ZoomListWindow,
        pageToken: String?
    ) async throws -> ZoomRecordingsPage {
        var components = URLComponents(string: "https://api.zoom.us/v2/users/me/recordings")!
        var items = [
            // Both mandatory. Omitted, Zoom answers for TODAY ONLY — an
            // unparameterised call against a busy account returns
            // total_records: 0, which reads as "you have no recordings" and is
            // the single most reported confusion in Zoom's developer forum.
            URLQueryItem(name: "from", value: chunk.fromString),
            URLQueryItem(name: "to", value: chunk.toString),
            URLQueryItem(name: "page_size", value: "300"),
        ]
        if let pageToken { items.append(URLQueryItem(name: "next_page_token", value: pageToken)) }
        components.queryItems = items

        let data = try await get(components.url!.absoluteString)
        return try JSONDecoder().decode(ZoomRecordingsPage.self, from: data)
    }

    private func makeRow(_ meeting: ZoomRecordingsPage.Meeting) -> CloudImportRow? {
        guard let uuid = meeting.uuid,
              let start = meeting.start_time.flatMap(Self.parseDate)
        else { return nil }

        let files = (meeting.recording_files ?? []).map { file in
            ZoomRecordingFile(
                id: file.id,
                fileType: ZoomFileType(file.file_type ?? ""),
                layout: ZoomRecordingLayout(file.recording_type ?? ""),
                sizeBytes: file.file_size,
                downloadURL: file.download_url.flatMap(URL.init(string:)),
                recordingStart: file.recording_start.flatMap(Self.parseDate)
            )
        }
        let choice = ZoomFileSelection.choose(from: files)
        guard let media = choice.media else { return nil }
        chosenFiles[uuid] = media

        let expiry = ZoomExpiry(
            autoDelete: meeting.auto_delete,
            autoDeleteDate: meeting.auto_delete_date.flatMap(Self.parseDay),
            deletedTime: nil
        )

        return CloudImportRow(
            id: uuid,
            title: meeting.topic ?? "Untitled meeting",
            startsAt: start,
            duration: meeting.duration.map { TimeInterval($0 * 60) },
            // The chosen file's size, not `total_size` — that figure covers
            // every artefact including the MP4s we deliberately skip, so using
            // it would over-state the download by a factor of three and make
            // the free-space precheck refuse a batch that fits.
            sizeBytes: media.sizeBytes,
            expiresAt: expiry.date,
            attendees: [],
            localState: .notImported,
            video: media.isDownloadable ? .available : .unsupported,
            // Zoom's list call carries no participant roster at all — that
            // needs a separate report endpoint behind an admin scope this
            // design refuses. Absent, and said so, rather than an empty line
            // pretending to be a roster.
            roster: .unsupported,
            transcript: choice.transcript != nil ? .available : .unsupported,
            organiser: nil
        )
    }

    // MARK: Fetching

    func fetch(
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        guard let file = chosenFiles[row.id], let url = file.downloadURL else {
            return .failed(reason: "That recording has no downloadable file.", isRetryable: false)
        }
        guard let token = tokens?.accessToken else {
            return .failed(reason: "Signed out.", isRetryable: true)
        }

        let name = CloudDownloadNaming.filename(
            title: row.title,
            startsAt: row.startsAt,
            fileExtension: file.fileType == .m4a ? "m4a" : "mp4"
        )
        let request = CloudDownloadRequest(
            url: url,
            accessToken: token,
            policy: .zoom,
            expected: ExpectedFile(
                // The listing's own figure — an independent second source, so
                // it catches a redirect that served something else entirely
                // rather than merely a truncated stream.
                sizeBytes: file.sizeBytes,
                // Zoom publishes no content hash, so verification here is
                // size + magic bytes rather than exact.
                hash: nil,
                expectedFormat: .mp4
            ),
            destination: destination.appendingPathComponent(name)
        )

        do {
            let bytes = try await CloudDownloader().download(request) { written, total in
                progress(FetchProgress(
                    rowID: row.id,
                    fraction: total.map { Double(written) / Double($0) },
                    bytesWritten: written,
                    bytesExpected: total
                ))
            }
            return .imported(bytes: bytes, at: request.destination)
        } catch let error as CloudDownloadError {
            if case .cancelled = error { return .cancelled }
            return .failed(
                reason: error.errorDescription ?? "The download failed.",
                isRetryable: {
                    if case .rejected(let verdict) = error { return verdict.isRetryable }
                    return false
                }()
            )
        } catch is CancellationError {
            return .cancelled
        } catch let error as URLError where error.code == .cancelled {
            // `URLSession.download` reports Task cancellation as
            // `URLError(.cancelled)`, NOT as `CloudDownloadError.cancelled` —
            // so without this arm a deliberate Stop fell through to the generic
            // catch below and was recorded as a *failure*. The terminus then
            // counted the user's own decision as a fault and offered "Retry" for
            // rows they had chosen to abandon.
            return .cancelled
        } catch {
            return .failed(reason: "The download failed.", isRetryable: true)
        }
    }

    // MARK: HTTP

    private func get(_ urlString: String) async throws -> Data {
        guard let url = URL(string: urlString), let token = tokens?.accessToken else {
            throw ZoomAPIError(outcome: .needsReauthentication)
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        let outcome = ZoomResponseClassifier.classify(status: status, body: data)
        guard outcome == .ok else { throw ZoomAPIError(outcome: outcome) }
        return data
    }

    private func empty(_ window: DateInterval, outcome: ListOutcome) -> MeetingListing {
        MeetingListing(
            rows: [],
            arithmetic: JoinArithmetic(eventsInWindow: 0, fetchable: 0,
                                       organisedByOthers: 0, outcome: outcome),
            window: window
        )
    }

    /// Bridges Zoom's outcome vocabulary into the shared one the store renders.
    private func mapOutcome(_ outcome: ZoomAPIOutcome) -> GoogleAPIOutcome {
        switch outcome {
        case .ok:                   return .ok
        case .needsReauthentication: return .needsReauthentication(reason: "zoom")
        case .planDoesNotInclude:   return .notAvailableOnThisPlan(detail: nil)
        case .scopeNotGranted:      return .scopeNotGranted(scope: nil)
        case .notFound:             return .notFound
        case .rateLimited(let a):   return .rateLimited(retryAfter: a)
        case .transient(let s):     return .transient(status: s)
        case .unexpected(let s, let c): return .unexpected(status: s, reason: c.map(String.init))
        }
    }

    static func parseDate(_ string: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: string) { return d }
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: string)
    }

    /// `auto_delete_date` is a bare `yyyy-MM-dd`, not an RFC3339 instant.
    static func parseDay(_ string: String) -> Date? {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.locale = Locale(identifier: "en_US_POSIX")
        return f.date(from: string)
    }
}

struct ZoomAPIError: Error {
    let outcome: ZoomAPIOutcome
}

// MARK: - The redirect trap

/// Strips `Authorization` when a download redirects to Zoom's CDN.
///
/// `download_url` on `zoom.us` answers with a 302 to a **pre-signed** URL on
/// `ssrweb.zoom.us` that carries its own credentials in the query string.
/// `URLSession` re-attaches the original headers across the redirect by
/// default, and a signed URL arriving with both a signature and an
/// `Authorization` header has been reported to 403 — the same behaviour S3-style
/// backends have.
///
/// So this hands back a request with the header removed. The failure it
/// prevents is not loud: a 403 here yields an HTML error body that a naive
/// downloader writes into a `.mp4`, producing a 3 KB file that ffprobe rejects
/// hours later at stage 2, long after the researcher stopped watching.
final class ZoomRedirectStripper: NSObject, URLSessionTaskDelegate {
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        var stripped = request
        stripped.setValue(nil, forHTTPHeaderField: "Authorization")
        completionHandler(stripped)
    }
}

/// Guards against Zoom's download failure shapes, of which the dangerous one is
/// **an error delivered as HTTP 200**.
///
/// This is not a theoretical hardening. The best-documented case in the whole
/// Zoom ecosystem: a developer ran the leading open-source downloader over
/// ~2,000 recordings and **880 of them wrote a 59-byte JSON error body to disk
/// as a `.mp4`** — and every one was logged as a successful download. A
/// permission failure renders as an HTML login page or a JSON error with a 200
/// status line, so nothing throws, nothing 4xxs, and the batch reports success.
///
/// The two leading downloaders independently converged on the same fix, which
/// is the second check here: **compare bytes received against the size the
/// listing already told you.** One maintainer removed his completed-downloads
/// log entirely because it "often erroneously classif[ied] recordings as
/// successfully downloaded".
///
/// It is the same defect `docs/design-cloud-import.md` §6 calls "prove the bytes
/// arrived", arrived at independently by strangers — which is the strongest
/// evidence available that the rule is right.
enum ZoomDownloadGuard {

    enum Verdict: Equatable {
        case usable
        /// The response is an error wearing a success status.
        case notMedia(contentType: String)
        case badStatus(Int)
        /// Arrived, but not all of it. A truncated-but-valid MP4 is the quiet
        /// version of this failure: ffprobe accepts it, Whisper transcribes 40
        /// of 60 minutes, and the report presents a confident analysis of a
        /// session that was never fully read.
        case shortRead(expected: Int64, received: Int64)
    }

    /// Checked *before* the destination file is opened, so nothing half-written
    /// is ever visible.
    static func inspect(response: URLResponse?) -> Verdict {
        guard let http = response as? HTTPURLResponse else { return .badStatus(0) }
        guard (200...299).contains(http.statusCode) else { return .badStatus(http.statusCode) }
        let type = (http.value(forHTTPHeaderField: "Content-Type") ?? "").lowercased()
        if type.contains("text/html") || type.contains("application/json") {
            return .notMedia(contentType: type)
        }
        return .usable
    }

    /// Checked after the transfer, against the listing's own figure.
    ///
    /// `expected` comes from `recording_files[].file_size` — an independent
    /// second source, so it catches a redirect that served something else
    /// entirely, not just a truncated stream. Nil expected means the file type
    /// carries no size (`CC` and `TIMELINE` genuinely have none), and an absent
    /// figure must read as unknown rather than as zero.
    static func verify(received: Int64, expected: Int64?) -> Verdict {
        guard let expected, expected > 0 else { return .usable }
        return received == expected ? .usable
                                    : .shortRead(expected: expected, received: received)
    }

    static func isUsableMedia(response: URLResponse?) -> Bool {
        inspect(response: response) == .usable
    }
}
