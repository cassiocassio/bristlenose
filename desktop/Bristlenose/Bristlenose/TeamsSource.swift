import Foundation

// The live Teams adapter, over Microsoft Graph.
//
// Teams is the platform §5 puts first, and the reason is visible in how little
// this file has to work around: video, roster and list are all delegated,
// own-data, user-consentable. No review, no fee, no annual audit, nothing
// admin-gated on the happy path.
//
// What it *does* have to work around is the shape of the failures, and they are
// different from the other two. Google's are about scope classification; Zoom's
// are about statuses that lie. Microsoft's are about **the same signal meaning
// opposite things** — two 401s with opposite remedies, an empty folder that is
// either "no recordings" or "wrong account tier", and a 403 that is either a
// missing scope or a tenant policy no consent can lift.

// MARK: - Wire shapes

private struct GraphChildren: Decodable {
    struct Item: Decodable {
        struct ParentReference: Decodable {
            let driveType: String?
        }
        struct FileFacet: Decodable {
            struct Hashes: Decodable {
                let quickXorHash: String?
                let sha1Hash: String?
                let sha256Hash: String?
            }
            let mimeType: String?
            let hashes: Hashes?
        }
        let id: String?
        let name: String?
        let size: Int64?
        let parentReference: ParentReference?
        let file: FileFacet?
        /// **Pre-authenticated, and therefore a credential.** It carries a
        /// `tempauth=` bearer token in the query string, which is why §9's
        /// no-logging rule is a hard requirement rather than a precaution, and
        /// why this never reaches a `CloudImportRow`.
        let downloadURL: String?
        /// ⚠️ Unverified against a work tenant. Microsoft's *product* shows
        /// "Expires in 4 days" on exactly this data, but whether Graph serves
        /// it per-driveItem — rather than only on a sharing link — is the
        /// Teams brief's open Q6. Absent, the column renders "—", which is the
        /// honest answer; if it turns out never to be served,
        /// `CloudPlatform.teams.hasPerFileExpiry` must flip to false so the
        /// column disappears rather than standing empty.
        let expirationDateTime: String?

        /// ISO-8601 with an explicit zone, and therefore **the only
        /// trustworthy moment on a Teams recording.** The filename's timestamp
        /// is unmarked on a business tenant and is simply the recorder's local
        /// wall clock — verified against a `Europe/Madrid` machine, where the
        /// filename and `creation_time` agree exactly — so it cannot be placed
        /// on a clock by anyone importing from a different zone. The window
        /// filter, the row's displayed time and the calendar join all take their
        /// moment from here. See the note on `TeamsRecordingName`.
        ///
        /// Always served: the recordings listing sets no `$select`, so the
        /// default driveItem property set arrives whole.
        let createdDateTime: String?

        enum CodingKeys: String, CodingKey {
            case id, name, size, parentReference, file, expirationDateTime, createdDateTime
            case downloadURL = "@microsoft.graph.downloadUrl"
        }
    }
    let value: [Item]?
    let nextLink: String?

    enum CodingKeys: String, CodingKey {
        case value
        case nextLink = "@odata.nextLink"
    }
}

private struct GraphCalendarView: Decodable {
    struct Event: Decodable {
        struct Attendee: Decodable {
            struct EmailAddress: Decodable {
                let name: String?
                let address: String?
            }
            struct Status: Decodable { let response: String? }
            let emailAddress: EmailAddress?
            let status: Status?
            let type: String?
        }
        struct Organizer: Decodable {
            let emailAddress: Attendee.EmailAddress?
        }
        struct When: Decodable { let dateTime: String?; let timeZone: String? }
        let id: String?
        let subject: String?
        let start: When?
        let end: When?
        let attendees: [Attendee]?
        let organizer: Organizer?
    }
    let value: [Event]?
    /// Graph paginates `calendarView` like everything else. This member was
    /// absent, so the continuation could not even be *read*, let alone followed
    /// — and §6 names an unfollowed `@odata.nextLink` as a lead failure mode.
    let nextLink: String?

    enum CodingKeys: String, CodingKey {
        case value
        case nextLink = "@odata.nextLink"
    }
}

// MARK: - The adapter

final class TeamsSource: CloudImportSource {
    private let config: MicrosoftOAuthConfig
    private let sessionOwner: CloudSessionOwner
    private var session: URLSession { sessionOwner.session }
    private var tokens: MicrosoftTokenResponse?
    private var identity: String?
    private var tier: DriveTier = .unknown("")

    /// Download URLs, held here and never on a row. Re-resolved before each
    /// fetch rather than reused from list time, because they are short-lived by
    /// design — §9.
    private var downloadURLs: [String: URL] = [:]
    private var expectations: [String: ExpectedFile] = [:]

    /// - Parameter restoredTokens: a previously-obtained grant. See the note on
    ///   `ZoomSource.init` — this is the Keychain-restore seam §2 owes, and
    ///   until that exists it is what lets the listing path be driven over a
    ///   stubbed transport.
    /// - Parameter session: injection seam for the transport tests. Omit it and
    ///   the adapter builds — and owns — an ephemeral, redirect-policed session
    ///   (`CloudNetworking`); an injected one is adopted and never invalidated
    ///   here, because this object did not create it.
    init(config: MicrosoftOAuthConfig,
         session: URLSession? = nil,
         restoredTokens: MicrosoftTokenResponse? = nil) {
        self.config = config
        self.sessionOwner = session.map(CloudSessionOwner.init(adopting:)) ?? CloudSessionOwner()
        self.tokens = restoredTokens
    }

    var accountEmail: String? { identity }

    var accountTier: GoogleAccountTier {
        switch tier {
        case .business:
            return .workspace(domain: identity.flatMap(Self.domain) ?? "")
        case .personal:
            return .personal
        case .unknown:
            return .unknown
        }
    }

    private static func domain(_ email: String) -> String? {
        guard let at = email.lastIndex(of: "@") else { return nil }
        return String(email[email.index(after: at)...]).lowercased()
    }

    // MARK: Sign-in

    @MainActor
    func signIn() async throws {
        let client = MicrosoftOAuthClient(config: config, session: session)
        tokens = try await client.signIn()
        identity = try? await fetchIdentity()
    }

    private func fetchIdentity() async throws -> String? {
        struct Me: Decodable { let mail: String?; let userPrincipalName: String? }
        let data = try await get("https://graph.microsoft.com/v1.0/me")
        let me = try? JSONDecoder().decode(Me.self, from: data)
        // `mail` is empty on plenty of real accounts; UPN is the reliable one.
        // Both are the researcher's own address, which §9 needs for exactly two
        // things: dropping "you" from the attendee line, and the domain
        // externality is measured against.
        return me?.mail ?? me?.userPrincipalName
    }

    // MARK: Listing

    func list(window: DateInterval) async -> MeetingListing {
        guard tokens != nil else {
            return empty(window, outcome: .failed(after: 0,
                                                  outcome: .needsReauthentication(reason: "no token")))
        }

        var items: [GraphChildren.Item] = []
        var next: String? = "https://graph.microsoft.com/v1.0/me/drive/root:/Recordings:/children"
        var pagesFetched = 0
        let pageCap = 20
        var outcome: ListOutcome = .exhausted

        while let url = next {
            do {
                let data = try await get(url)
                let page = try JSONDecoder().decode(GraphChildren.self, from: data)
                items.append(contentsOf: page.value ?? [])
                // **Follow `@odata.nextLink` or lose rows silently.** An
                // unfollowed continuation returns HTTP 200 with a partial page
                // — the designed output of this feature and its failure mode
                // are both "a shorter list", so the paginator's terminal state
                // is carried rather than inferred.
                next = page.nextLink
                pagesFetched += 1
                if next != nil && pagesFetched >= pageCap {
                    outcome = .pageCapHit(pagesFetched: pagesFetched)
                    break
                }
            } catch let error as TeamsAPIError {
                // `itemNotFound` on /Recordings is the tier problem, not an
                // empty folder: a personal Teams account attaches recordings to
                // the meeting chat and never creates the folder at all. Naming
                // that turns a baffling empty list into one sentence.
                // …but only on the FIRST page. A 404 partway through a walk is
                // an expired `@odata.nextLink`, not a personal account — and
                // returning `empty(.exhausted)` there discarded every row
                // already collected and told a researcher with hundreds of
                // recordings that they had none, misdiagnosed as the wrong
                // account tier, with `isExact` true.
                if error.outcome == .notFound, pagesFetched == 0 {
                    tier = .personal
                    return empty(window, outcome: .exhausted)
                }
                // A 404 on a later page falls through to the ordinary failure
                // path below, which reports `.failed(after:)` and keeps the rows
                // already collected.
                outcome = .failed(after: pagesFetched, outcome: mapOutcome(error.outcome))
                break
            } catch {
                outcome = .failed(after: pagesFetched,
                                  outcome: .unexpected(status: 0, reason: error.localizedDescription))
                break
            }
        }

        if let driveType = items.first?.parentReference?.driveType {
            tier = DriveTier(driveType: driveType)
        }

        // The roster is a separate, optional read. A researcher who declined
        // the calendar scope still gets a usable list — the title and date come
        // free from the filename, which is why §6 could move title filtering
        // out of the calendar's reach entirely.
        let events = await calendarEvents(window: window)

        let rows = items.compactMap { makeRow($0, window: window, events: events) }
        return MeetingListing(
            rows: rows,
            arithmetic: JoinArithmetic(
                eventsInWindow: max(events.count, rows.count),
                fetchable: rows.filter(\.isSelectable).count,
                // **Count it, don't subtract it.**
                //
                // This was `max(0, events.count - rows.count)`, which is not the
                // quantity it names. `events` is the researcher's entire diary
                // for the window; `rows` is their own recordings. Every meeting
                // they attended and did not record — most of a working week —
                // landed in "organised by someone else", and any bug that
                // emptied `rows` made the number equal the whole diary. It did:
                // when the filename parser rejected every business recording,
                // the window reported one meeting "organised by someone else"
                // about a meeting the user had organised themselves.
                //
                // The organiser is on the event, so ask it. Meetings with no
                // organiser field, and the whole calendar when the scope was
                // declined, count as zero rather than as somebody else's —
                // §6's requirement is that this line never overstates.
                organisedByOthers: events.filter { event in
                    guard let organiser = event.organizer?.emailAddress?.address?.lowercased(),
                          let me = identity?.lowercased()
                    else { return false }
                    return organiser != me
                }.count,
                outcome: outcome
            ),
            window: window
        )
    }

    /// The calendar window, for the roster. Failure is silent by design: the
    /// list works without it.
    private func calendarEvents(window: DateInterval) async -> [GraphCalendarView.Event] {
        var components = URLComponents(
            string: "https://graph.microsoft.com/v1.0/me/calendarView")!
        components.queryItems = [
            URLQueryItem(name: "startDateTime", value: Self.iso(window.start)),
            URLQueryItem(name: "endDateTime", value: Self.iso(window.end)),
            // §3's compensating control for holding `Calendars.Read` rather
            // than `ReadBasic`: ask for the fields the roster needs and nothing
            // else, so bodies — every agenda, dial-in PIN and medical
            // appointment in the researcher's diary — are never fetched at all.
            URLQueryItem(name: "$select", value: "id,subject,start,end,organizer,attendees"),
            URLQueryItem(name: "$top", value: "250"),
        ]
        guard let url = components.url else { return [] }
        // `calendarView` honours `Prefer: outlook.timezone`, and a UTC-vs-local
        // mismatch shifts the window boundary by up to a day at each edge —
        // silently dropping a 9am Monday interview out of "last 30 days". Pin
        // it rather than accept the mailbox default.
        // Walk the continuation. A researcher with a busy diary exceeds `$top`
        // easily, and a truncated roster is silent: rows still render, they just
        // lose their attendees — and the footer went on reporting `.exhausted`
        // because this read never touched `outcome`. Capped like the recordings
        // walk, for the same reason.
        var events: [GraphCalendarView.Event] = []
        var next: String? = url.absoluteString
        var pages = 0
        let pageCap = 20

        while let link = next, pages < pageCap {
            guard let data = try? await get(link,
                                            headers: ["Prefer": "outlook.timezone=\"UTC\""]),
                  let page = try? JSONDecoder().decode(GraphCalendarView.self, from: data)
            else { break }
            events.append(contentsOf: page.value ?? [])
            next = page.nextLink
            pages += 1
        }
        return events
    }

    private func makeRow(
        _ item: GraphChildren.Item,
        window: DateInterval,
        events: [GraphCalendarView.Event]
    ) -> CloudImportRow? {
        guard let id = item.id, let name = item.name else { return nil }
        // The **title** comes from the filename, free, with no calendar scope.
        // That is what this parse is for (§6).
        guard let parsed = TeamsRecordingName(filename: name) else { return nil }

        // The **moment** does not. A business filename writes the recorder's
        // local wall clock with no zone marker, so it cannot be placed on a
        // clock by any regex run on a machine in a different zone.
        // `createdDateTime` carries its zone explicitly; the filename's value
        // is used only when it declared itself UTC, which personal tenants do.
        guard let startedAt = item.createdDateTime.flatMap(Self.parseISO)
                ?? parsed.startedAtUTC
        else { return nil }
        guard window.contains(startedAt) else { return nil }

        if let raw = item.downloadURL, let url = URL(string: raw) {
            downloadURLs[id] = url
        }

        // Microsoft is the only one of the three that publishes a content hash
        // *before* the download, which lets verification be exact rather than
        // heuristic. Business OneDrive has historically returned only
        // quickXorHash, so prefer sha256 and degrade rather than require it.
        let hashes = item.file?.hashes
        let hash: FileHash? = hashes?.sha256Hash.map { FileHash(algorithm: .sha256, value: $0) }
        expectations[id] = ExpectedFile(
            sizeBytes: item.size,
            hash: hash,
            expectedFormat: .mp4
        )

        let matched = Self.matchEvent(events, near: startedAt)
        let attendees = matched.map { Self.attendees(of: $0, ownAddress: identity) } ?? []

        return CloudImportRow(
            id: id,
            title: matched?.subject ?? parsed.title,
            startsAt: startedAt,
            duration: nil,
            sizeBytes: item.size,
            expiresAt: item.expirationDateTime.flatMap(Self.parseISO),
            attendees: attendees,
            localState: .notImported,
            video: item.downloadURL == nil ? .unsupported : .available,
            roster: attendees.isEmpty ? .needsScope(MicrosoftScopes.calendarsRead) : .available,
            // Admin-consent-only, even delegated. Not requested, so never
            // available — stated rather than silently missing.
            transcript: .needsScope("OnlineMeetingTranscript.Read.All"),
            organiser: nil
        )
    }

    /// Joins a recording to its calendar event.
    ///
    /// Fuzzy on purpose, and bounded on purpose. The key is (title, timestamp)
    /// where the title is user-mutable and the timestamp is *recording start*,
    /// not meeting start — everyone joins a minute or two late. A 30-minute
    /// window absorbs that without letting a back-to-back session steal the
    /// match; widening it would silently attach the wrong roster to a row,
    /// which is worse than no roster at all.
    /// Takes the moment rather than the parsed filename: the join must run
    /// against a zone-qualified instant, and on a business tenant the filename
    /// cannot supply one.
    private static func matchEvent(
        _ events: [GraphCalendarView.Event],
        near recordingStart: Date
    ) -> GraphCalendarView.Event? {
        events
            .compactMap { event -> (GraphCalendarView.Event, TimeInterval)? in
                guard let start = event.start?.dateTime.flatMap(parseISO) else { return nil }
                let delta = abs(start.timeIntervalSince(recordingStart))
                guard delta <= 1_800 else { return nil }
                return (event, delta)
            }
            .min { $0.1 < $1.1 }?
            .0
    }

    private static func attendees(
        of event: GraphCalendarView.Event,
        ownAddress: String?
    ) -> [CloudImportRow.Attendee] {
        let domain = ownAddress.flatMap(domain)
        return (event.attendees ?? []).compactMap { person in
            let address = person.emailAddress?.address
            guard address != nil || person.emailAddress?.name != nil else { return nil }
            let isSelf = address?.caseInsensitiveCompare(ownAddress ?? "") == .orderedSame
            let external = domain.map { d in !(address?.lowercased().hasSuffix("@\(d)") ?? false) } ?? true
            return CloudImportRow.Attendee(
                // Graph populates `name` far more reliably than Google does —
                // the org directory resolves colleagues — but an external
                // participant not in it comes back as a bare address or
                // whatever the organiser typed. The list falls back to the
                // local part rather than showing nothing.
                displayName: person.emailAddress?.name,
                email: address,
                isSelf: isSelf,
                isOrganiser: false,
                // A decline is strong evidence they were not in the recording,
                // so dropping them is an accuracy improvement, not a space
                // saving.
                didDecline: person.status?.response == "declined",
                isExternal: external
            )
        }
    }

    // MARK: Fetching

    func fetch(
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        // Re-resolve immediately before fetching, exactly as the note on
        // `downloadURLs` has always claimed and the code did not do.
        //
        // `@microsoft.graph.downloadUrl` is short-lived by design — roughly an
        // hour. Reusing the value captured at list time meant a batch begun
        // forty minutes after the window opened took a `badStatus` on its tail,
        // surfaced as "The download was refused" with `isRetryable: true`, so
        // every retry failed identically. The list-time value is kept only as a
        // fallback for the case where the re-resolve itself fails.
        let url: URL
        do {
            url = try await resolveDownloadURL(itemID: row.id)
        } catch {
            guard let cached = downloadURLs[row.id] else {
                return .failed(reason: "That recording has no download link.", isRetryable: true)
            }
            url = cached
        }
        let name = CloudDownloadNaming.filename(
            title: row.title, startsAt: row.startsAt, fileExtension: "mp4")
        let request = CloudDownloadRequest(
            url: url,
            // No token: Graph's downloadUrl is pre-authenticated. Sending a
            // bearer alongside the tempauth in the query string is at best
            // redundant.
            accessToken: nil,
            policy: .teams,
            expected: expectations[row.id] ?? ExpectedFile(sizeBytes: row.sizeBytes,
                                                           expectedFormat: .mp4),
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
            return .imported(bytes: bytes)
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

    /// Asks Graph for a fresh pre-authenticated download URL for one driveItem.
    ///
    /// `$select=@microsoft.graph.downloadUrl` is the documented way to get the
    /// hand-off without re-listing the folder. The value that comes back is a
    /// **credential** — it carries `tempauth=` in its query string — so it is
    /// returned to the caller and never stored on a row, logged, or held past
    /// the transfer.
    private func resolveDownloadURL(itemID: String) async throws -> URL {
        struct Resolved: Decodable {
            let downloadURL: String?
            enum CodingKeys: String, CodingKey { case downloadURL = "@microsoft.graph.downloadUrl" }
        }
        let encoded = itemID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? itemID
        let data = try await get(
            "https://graph.microsoft.com/v1.0/me/drive/items/\(encoded)"
            + "?$select=id,@microsoft.graph.downloadUrl")
        guard let raw = try? JSONDecoder().decode(Resolved.self, from: data).downloadURL,
              let url = URL(string: raw)
        else { throw TeamsAPIError(outcome: .unexpected(status: 0, code: "no-download-url")) }
        return url
    }

    private func get(_ urlString: String, headers: [String: String] = [:]) async throws -> Data {
        guard let url = URL(string: urlString), let token = tokens?.accessToken else {
            throw TeamsAPIError(outcome: .needsReauthentication(code: "no-token"))
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        for (key, value) in headers { request.setValue(value, forHTTPHeaderField: key) }

        let (data, response) = try await session.data(for: request)
        let http = response as? HTTPURLResponse
        let retryAfter = http?.value(forHTTPHeaderField: "Retry-After").flatMap(TimeInterval.init)
        // The classifier reads status AND body together — the whole reason it
        // exists. Two 401s look identical to anything reading the status line
        // and carry opposite remedies: refresh-and-retry, or tell the user
        // their account has no licence and never retry.
        let outcome = TeamsResponseClassifier.classify(
            status: http?.statusCode ?? 0, body: data, retryAfter: retryAfter)
        guard outcome == .ok else { throw TeamsAPIError(outcome: outcome) }
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

    private func mapOutcome(_ outcome: TeamsAPIOutcome) -> GoogleAPIOutcome {
        switch outcome {
        case .ok:                     return .ok
        case .needsReauthentication:  return .needsReauthentication(reason: "graph")
        case .accountNotLicensed:     return .notAvailableOnThisPlan(detail: nil)
        case .scopeNotGranted:        return .scopeNotGranted(scope: nil)
        case .notFound:               return .notFound
        case .rateLimited(let after): return .rateLimited(retryAfter: after)
        case .transient(let status):  return .transient(status: status)
        case .unexpected(let status, let code):
            return .unexpected(status: status, reason: code)
        }
    }

    static func iso(_ date: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        f.timeZone = TimeZone(secondsFromGMT: 0)
        return f.string(from: date)
    }

    static func parseISO(_ string: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: string) { return d }
        let g = ISO8601DateFormatter()
        g.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return g.date(from: string)
    }
}

struct TeamsAPIError: Error {
    let outcome: TeamsAPIOutcome
}
