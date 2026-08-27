import Foundation
import OSLog

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
    /// Never carries a token, a download URL or an account address — §9 of
    /// `docs/design-cloud-import.md`, and `httpx`-style full-URL logging is
    /// exactly the leak it forbids.
    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import.zoom")

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

    /// - Parameter restoredTokens: a previously-obtained grant, from the
    ///   Keychain via `CloudGrantStore.loadZoom`.
    /// - Parameter session: injection seam for the transport tests. Omit it and
    ///   the adapter builds — and owns — an ephemeral, redirect-policed session
    ///   (`CloudNetworking`); an injected one is adopted and never invalidated
    ///   here, because this object did not create it.
    /// - Parameter restoredIdentity: the signed-in address, restored with the
    ///   tokens. Without it `CloudImportStore` opens on `.signedOut` — it reads
    ///   that from `accountEmail` — so a good restored token would sit behind a
    ///   sign-in button and the restore would look like it had failed.
    /// - Parameter onGrantChanged: called whenever the grant materially moves —
    ///   signed in or revoked. **Nil means forget it.** Synchronous and
    ///   `Void`-returning, exactly like Teams' and Google's.
    /// - Parameter onRotation: called with a rotated pair, and answers whether
    ///   it was actually stored.
    ///
    ///   **Two seams rather than one, and the reason is ordering.** The single
    ///   `async -> Bool` sink this replaced was tidier and wrong:
    ///   `CloudGrantWriter` orders publishes by *enqueue*, and Teams and Google
    ///   get that for free because they call the sink synchronously, so enqueue
    ///   order is call order. Awaiting an async sink from a non-async publish
    ///   means wrapping it in an unstructured `Task`, and two unstructured
    ///   tasks have no defined order — each inherits its creator's priority, so
    ///   a `.utility` fetch's refusal can overtake a `.userInitiated` sign-in
    ///   and write a tombstone over a working grant. That is verbatim the
    ///   defect `CloudGrantWriter` was built to fix, reintroduced one layer up,
    ///   and on Zoom it costs a consent round-trip rather than one sign-in.
    ///
    ///   `onRotation` earns its separate existence: it is the only publish
    ///   whose *result* anybody reads, because a rotated single-use token that
    ///   failed to persist cannot be reported as success.
    init(config: ZoomOAuthConfig,
         session: URLSession? = nil,
         restoredTokens: ZoomTokens? = nil,
         restoredIdentity: String? = nil,
         onGrantChanged: (@Sendable (ZoomGrant?) -> Void)? = nil,
         onRotation: (@Sendable (ZoomGrant) async -> Bool)? = nil) {
        self.config = config
        self.sessionOwner = session.map(CloudSessionOwner.init(adopting:)) ?? CloudSessionOwner()
        self.tokens = restoredTokens
        self.identity = restoredIdentity
        self.onGrantChanged = onGrantChanged
        self.onRotation = onRotation
    }

    private let onGrantChanged: (@Sendable (ZoomGrant?) -> Void)?
    private let onRotation: (@Sendable (ZoomGrant) async -> Bool)?

    /// Publish the current grant, or its absence.
    ///
    /// **Handed to the sink synchronously — the hop lives in the writer**, as
    /// it does on Teams and Google. `CloudGrantWriter` enqueues on a serial
    /// queue, so publishes land in the order they were *made* only if the
    /// enqueue happens on this thread; putting a `Task` boundary in between
    /// hands the ordering back to the scheduler and reintroduces the tombstone-
    /// over-a-working-grant race the writer exists to close. The contract that
    /// replaces the hop: the sink must not block.
    ///
    /// The snapshot is taken here, on the caller's actor, so what gets written
    /// is what was true at the call rather than whatever the adapter has
    /// drifted to by the time the write lands.
    private func publishGrant() {
        let snapshot = tokens.map { ZoomGrant(tokens: $0, identity: identity) }
        onGrantChanged?(snapshot)
    }

    /// Record that Zoom ended the session, **keeping the account**.
    ///
    /// Same tombstone as Teams and for the same reason: a revoked grant that is
    /// deleted vanishes from Settings ▸ Accounts, which is indistinguishable
    /// from having disconnected it yourself, and the researcher's only evidence
    /// is that importing quietly stopped working. `revoked` carries no usable
    /// credential, so the retry loop this guards against cannot form.
    private func publishRefusal() {
        // Synchronous, for the ordering reason on `publishGrant` — and this is
        // the publish that reason was written about. A refusal that overtakes a
        // successful re-sign-in writes a tombstone over a live grant.
        onGrantChanged?(ZoomGrant.revoked(identity: identity))
    }

    /// The persist closure handed to `ZoomOAuthClient`, honouring the contract
    /// its `refresh(_:)` is written to: commit the rotated token, or fail the
    /// refresh.
    ///
    /// **A nil sink is not a failure.** It means nobody asked for persistence —
    /// a transport test, or an adapter built without a store behind it — and
    /// rotating in memory is coherent for the life of the object. A sink that
    /// was wired and then refused is the opposite: the old token is spent, the
    /// new one has nowhere to live, and reporting success would be the
    /// fake-success pattern this codebase keeps removing.
    private func persistRotation(_ identity: String?) -> @Sendable (ZoomTokens) async throws -> Void {
        guard let sink = onRotation else { return { _ in } }
        return { rotated in
            guard await sink(ZoomGrant(tokens: rotated, identity: identity)) else {
                // A bare marker: `refresh(_:)` catches anything thrown here and
                // re-raises it as `.rotationNotPersisted(refreshed)`, attaching
                // the live tokens. Throwing that case from inside would mean
                // naming the tokens twice and inviting the two copies to drift.
                throw GrantNotStored()
            }
        }
    }

    /// Thrown by the persist closure and never escapes `refresh(_:)`.
    private struct GrantNotStored: Error {}

    /// The refresh currently in flight, if any. `@MainActor`-isolated, so the
    /// check-and-store below spans no suspension point and cannot interleave.
    @MainActor private var inFlightRefresh: Task<Bool, Never>?

    /// Renew the token when it has aged out, or report that we cannot.
    ///
    /// **Single-flight, and on Zoom that is a correctness requirement rather
    /// than an optimisation.** `CloudImportStore` runs three fetches at once
    /// (`maxConcurrentFetches`), and each calls this before reading the token.
    /// Teams' version has no such guard and does not need one: Microsoft
    /// tolerates refresh-token reuse, so three simultaneous renewals are merely
    /// wasteful. Zoom's refresh token is **single-use**, so the same three
    /// calls would send one token three times — Zoom honours the first and
    /// answers `400 invalid_grant` to the other two. Those two then read as
    /// authoritative refusals and tombstone the grant that the first call had
    /// *just successfully renewed*, and the remaining rows of the batch fail
    /// "Signed out." An hour into a twelve-session import is precisely when
    /// this fires, which is to say: the ordinary shape of a real study, not an
    /// edge case.
    ///
    /// So the second and third callers join the first one's task instead of
    /// racing it. Zoom's own docs put it plainly — *"You should always use the
    /// latest refresh token for the next refresh request"* — and there is only
    /// one latest.
    @MainActor
    private func renewedTokenIfNeeded() async -> Bool {
        if let existing = inFlightRefresh { return await existing.value }
        guard let current = tokens else { return false }
        guard current.isExpired else { return true }
        let task = Task { @MainActor [self] in await performRefresh(current) }
        inFlightRefresh = task
        let outcome = await task.value
        inFlightRefresh = nil
        return outcome
    }

    /// The refresh itself. Only ever entered through `renewedTokenIfNeeded`,
    /// which guarantees one at a time.
    ///
    /// Diverges from Teams in two more places, both Zoom's own: the refresh
    /// token is not optional here (a response without one is already
    /// `.refreshRejected` inside the client), and the rotated pair is persisted
    /// before this returns.
    @MainActor
    private func performRefresh(_ current: ZoomTokens) async -> Bool {
        let client = ZoomOAuthClient(config: config,
                                     session: session,
                                     persist: persistRotation(identity))
        do {
            // `refresh` publishes through `persistRotation` before it returns,
            // so by the time this assignment runs the rotated token is already
            // stored. Assigning it here as well keeps the in-memory copy in
            // step; it is not the durable write.
            tokens = try await client.refresh(current)
            return true
        } catch ZoomOAuthError.rotationNotPersisted(let live) {
            // Zoom rotated and we could not write the replacement down. The
            // pair in hand is valid and is the only one that is, so the session
            // continues on it; what has been lost is durability, not access.
            // **Deliberately not a tombstone** — the account is not revoked,
            // and destroying it here would turn a Keychain that refused into a
            // revocation the researcher never made.
            tokens = live
            Self.log.notice("zoom token rotated but could not be stored — session continues, restore will not")
            return true
        } catch ZoomOAuthError.refreshRejected {
            // **Only an authoritative refusal writes a tombstone.** Teams
            // learned this expensively: a `try?` here treated a dropped
            // connection exactly like a revoked grant, so a moment of bad wifi
            // stripped the refresh token permanently and told the researcher
            // their provider had ended the session. This path runs precisely
            // when a token has aged out, which is the ordinary morning-after
            // case the restore feature exists for.
            //
            // **Matched by case, never by a status range.** Teams tests
            // `(400...499).contains(status)`, which sweeps up a `429` — and
            // Zoom's token endpoint is rate-limited, so a burst of renewals is
            // exactly how you earn one. That would destroy a working grant over
            // a condition that clears in seconds. `.refreshRejected` is raised
            // only for a 400 or 401, inside the client, where the
            // classification belongs; everything else falls through below.
            tokens = nil
            publishRefusal()
            return false
        } catch {
            // A `URLError`, a 5xx, a 429. Zoom has not said no, so the grant
            // stays exactly where it is and the next attempt can succeed.
            //
            // **This does re-present the same single-use token later, and that
            // is the considered choice rather than an oversight.** The
            // single-flight guard above stops three *simultaneous* callers
            // spending one token; it does not stop the next batch of fetch
            // slots trying again, so a twelve-row import can present one token
            // up to four times. Where the failure was a timeout *after* Zoom
            // rotated, those retries are token reuse, which some providers
            // answer by revoking the whole family.
            //
            // Refusing to retry would not actually help. If the token really
            // was spent, both paths end in the same place — a consent screen —
            // so refusing buys nothing; and if the failure was an ordinary
            // network blip, refusing costs a re-authorisation that retrying
            // would have avoided. The asymmetry runs the other way, so retrying
            // is weakly better. Worth revisiting only with a measurement of
            // what Zoom actually does on reuse, which no amount of local
            // testing can reach.
            Self.log.notice("zoom refresh failed without a verdict — keeping the grant")
            return false
        }
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
        let client = ZoomOAuthClient(config: config,
                                     session: session,
                                     persist: persistRotation(identity))
        tokens = try await client.signIn()
        identity = try? await fetchIdentity()
        preflight = try? await fetchPreflight()
        // **After the identity, not before it.** The grant is keyed on a hash
        // of the address, so publishing between the two would store it under
        // `unidentified` and then rekey a moment later — two Keychain writes
        // and, on the window that opened before anyone had signed in, a
        // transient second account row. `identity` is best-effort (`try?`), so
        // a `/me` that fails still publishes: a sign-in with no address is
        // still a sign-in worth keeping.
        publishGrant()
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
        // **An absent `recording` object is not "cloud recording is off".**
        // Every field on `ZoomUserSettings` is optional, so a 200 carrying
        // anything else at all decodes cleanly into all-nils — and collapsing
        // that to `false` produced a *blocking* verdict from a response we
        // never understood. That was harmless while `preflight` was only ever
        // filled by `signIn()`; the moment `list()` backfills it, a settings
        // endpoint that changes shape stops every restored session with "Cloud
        // recording is turned off for this Zoom account", which is a confident
        // claim about something we failed to read. Refusing to answer leaves
        // the gate unapplied — the pre-existing behaviour — and that is the
        // right direction to fail.
        guard let recording = settings.recording else {
            throw ZoomAPIError(outcome: .unexpected(status: 200, code: nil))
        }
        return ZoomPreflight(
            cloudRecordingEnabled: recording.cloud_recording ?? false,
            audioTranscriptEnabled: recording.recording_audio_transcript ?? false,
            autoDeleteEnabled: recording.auto_delete_cmr ?? false,
            autoDeleteDays: recording.auto_delete_cmr_days
        )
    }

    // MARK: Listing

    func list(window: DateInterval) async -> MeetingListing {
        // Renew before reading, not after failing. On the restore path an
        // hour-old token is the ordinary case, so 401-ing into a sign-in nobody
        // needed would be the common experience rather than the rare one.
        //
        // **A failed renewal is not automatically a dead account, and saying so
        // undoes the 429 handling one layer down.** `renewedTokenIfNeeded`
        // returns false for a refusal (grant gone, `tokens` nil) *and* for a
        // 429, a 5xx or a dropped connection — where `performRefresh`
        // deliberately keeps the grant so the next attempt can succeed.
        // Reporting the second as `needsReauthentication` would tell a
        // rate-limited researcher their connection expired and send them
        // through a consent screen Zoom does not let a public client skip,
        // which is exactly the outcome the tombstone rule exists to avoid.
        // `tokens` is the discriminator: nil means Zoom said no.
        guard await renewedTokenIfNeeded() else {
            return empty(window, outcome: .failed(
                after: 0,
                outcome: tokens == nil
                    ? .needsReauthentication(reason: "zoom refused the refresh")
                    : .transient(status: 0)))
        }
        guard tokens != nil else {
            return empty(window, outcome: .failed(after: 0,
                                                  outcome: .needsReauthentication(reason: "no token")))
        }

        // **Backfill the eligibility gate, because a restored session never ran
        // `signIn()`.** `preflight` is assigned in exactly one place, and once
        // the grant survives a relaunch that place stops being on the common
        // path — so without this the check below is nil-guarded into silence on
        // every ordinary launch, and an account that cannot cloud-record at all
        // renders as "no recordings in the last 30 days". That is the "factual
        // statement about the wrong question" the branch below exists to
        // prevent, arriving through the door the restore feature opened.
        // `GoogleMeetSource.list` backfills `identity` for the same reason and
        // says so; this is the same fix on the same seam.
        if preflight == nil {
            do {
                preflight = try await fetchPreflight()
            } catch {
                // Logged rather than swallowed: the consequence is a gate that
                // silently does not run for the life of the session, and
                // "why did it not warn me?" is otherwise unanswerable.
                Self.log.notice("zoom preflight unavailable — eligibility gate not applied")
            }
        }
        if identity == nil { identity = try? await fetchIdentity() }

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
            // **`.unsupported` is wrong here and is left standing on purpose.**
            // It means "the platform doesn't offer it at all", which flatly
            // contradicts `CloudPlatform.servesTranscript` — Zoom does serve a
            // VTT, on the same call as the video. A missing one usually means
            // *not yet*: the transcript is produced after the recording, and
            // Zoom's own guidance is 15–30 minutes, occasionally up to 24 hours
            // for a long meeting. So a study imported the same afternoon it was
            // recorded would be told, permanently, that Zoom does not do
            // transcripts.
            //
            // Not fixed because nothing reads this field — `CloudImportRow`
            // stores `transcript` and no view renders it — so the honest cases
            // (`ZoomPreflight.audioTranscriptEnabled` says the account makes
            // none, versus it makes them and this one has not landed) would be
            // a new `ArtifactAvailability` case feeding a dormant value into a
            // dormant field on a parked platform. Whoever renders the transcript
            // column should read this comment first and add the case then.
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
        // Renew before every file, not once per batch. The tail of a long
        // import is exactly where an unrenewed grant fails — after the
        // researcher has stopped watching, on the files they waited longest for.
        //
        // **It matters more here than on Teams.** Graph's URL carries its own
        // `tempauth=`, so a stale token there only breaks re-resolving the link;
        // Zoom's transfer is `.bearer` (see `CloudTransferPolicy.zoom`), so the
        // token below is what authorises the download itself. An hour into a
        // twelve-session study, an unrenewed one turns the whole remainder into
        // an HTML error body wearing a `.mp4` extension.
        //
        // The guard takes the renewal's verdict, not merely the token's
        // presence. A transient failure keeps the grant on purpose, so
        // `tokens` is non-nil *and stale* — and a download sent with a token
        // the adapter already knows is dead earns another rate-limited refusal
        // per row for the rest of the batch. `CloudDownloader` would still
        // refuse to write the error body, so this costs a wrong label rather
        // than a corrupt file; matching `list()` costs nothing and is honest.
        guard await renewedTokenIfNeeded(), let token = tokens?.accessToken else {
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
