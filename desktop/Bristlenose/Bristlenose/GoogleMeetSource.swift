import Foundation

// The live adapter: Google Calendar + Meet + Drive.
//
// Every query parameter below is chosen against a documented trap. The ones
// that would otherwise be silent are marked TRAP, because each produces a
// *plausible wrong answer* rather than an error — and this feature's whole
// hazard is that its success output and its failure output are both a shorter
// list.

// MARK: - Wire shapes

/// Only the fields the design actually reads. Decoding narrowly is deliberate:
/// §3's compensating control for holding a calendar scope is that event bodies
/// are never fetched and never persisted, and a struct that has nowhere to put
/// a `description` cannot accidentally keep one.
private struct CalendarEventsPage: Decodable {
    struct Event: Decodable {
        struct When: Decodable {
            let dateTime: String?
            let date: String?
        }
        struct Person: Decodable {
            let email: String?
            let displayName: String?
            let organizer: Bool?
            /// "Whether this entry represents the calendar on which this copy of
            /// the event appears" — how we find the researcher without knowing
            /// their address.
            ///
            /// Google's JSON key is `self`, which Swift cannot expose as a
            /// stored property: `p.self` is the postfix that returns `p`, so a
            /// property of that name is unreadable and the compiler's
            /// complaint points at the *call site* rather than the
            /// declaration. Renamed here and mapped below.
            let isSelf: Bool?
            let responseStatus: String?
            let optional: Bool?
            /// A room or a piece of equipment. Must be filtered, or the
            /// participant line gains "Meeting Room 4B".
            let resource: Bool?

            enum CodingKeys: String, CodingKey {
                case email, displayName, organizer, responseStatus, optional, resource
                case isSelf = "self"
            }
        }
        struct Conference: Decodable {
            struct Solution: Decodable {
                struct Key: Decodable { let type: String? }
                let key: Key?
            }
            /// For `hangoutsMeet` this is the meeting code (`aaa-bbbb-ccc`) —
            /// the join key to the Meet API. Google: "should not be displayed
            /// to users", so it stays internal.
            let conferenceId: String?
            let conferenceSolution: Solution?
        }
        let id: String?
        let summary: String?
        let start: When?
        let end: When?
        let attendees: [Person]?
        let organizer: Person?
        let conferenceData: Conference?
        /// TRAP: the honesty flag. True means the attendee array is a lie of
        /// omission, and any roster built from it is incomplete.
        let attendeesOmitted: Bool?
        let recurringEventId: String?
    }
    let items: [Event]?
    let nextPageToken: String?
}

private struct ConferenceRecordsPage: Decodable {
    struct Record: Decodable {
        let name: String?
        let startTime: String?
        let endTime: String?
        let expireTime: String?
    }
    let conferenceRecords: [Record]?
    let nextPageToken: String?
}

private struct RecordingsPage: Decodable {
    struct Recording: Decodable {
        struct DriveDestination: Decodable {
            /// The Drive fileId for the MP4. NOT a download URL — `exportUri`
            /// beside it is `drive.google.com/file/d/{id}/view`, a browser page.
            /// Bytes come from the Drive API or not at all.
            let file: String?
            let exportUri: String?
        }
        let name: String?
        let state: String?
        let driveDestination: DriveDestination?
    }
    let recordings: [Recording]?
}

// MARK: - The adapter

final class GoogleMeetSource: CloudImportSource {
    private let config: GoogleOAuthConfig
    private let sessionOwner: CloudSessionOwner
    private var session: URLSession { sessionOwner.session }
    private var tokens: GoogleTokens?
    private var identity: String?

    /// Drive file ids the user has granted through the Picker.
    ///
    /// Held because the grant is genuinely per-file on `drive.file`: a row
    /// whose id is absent is not reachable, however valid the token is.
    private var grantedFileIDs: Set<String> = []

    /// The Drive file id backing each row, kept from list time. Not on the row
    /// itself — see the Zoom adapter's note; download handles are credentials
    /// and do not belong on a value type the view layer holds.
    private var driveFileIDs: [String: String] = [:]

    /// The `drive.file` token from the Picker exchange. Separate from the
    /// listing token by construction: Zoom's desktop Picker permits `drive.file`
    /// and *no other scope*, so these two grants can never be the same token.
    private var mediaToken: GoogleTokens?

    /// - Parameter session: injection seam for the transport tests. Omit it and
    ///   the adapter builds — and owns — an ephemeral, redirect-policed session
    ///   (`CloudNetworking`); an injected one is adopted and never invalidated
    ///   here, because this object did not create it.
    ///
    /// - Parameter restoredTokens: a previously-obtained listing grant, matching
    ///   the seam Teams and Zoom already had. §2 needs an adapter to be
    ///   constructible already-authenticated so the Keychain restore has
    ///   somewhere to land; today the only caller is the transport suite, which
    ///   is also the only way to drive Google's listing path over a stub.
    ///
    /// - Parameter restoredMediaGrant: the Picker grant, which on Google is a
    ///   **pair** and not a token. `fetch` guards on `grantedFileIDs` *before*
    ///   it reads `mediaToken`, so a token restored without its file ids sits
    ///   unused behind a failing guard — a seam that looks restored and is not.
    ///   Restore both or neither.
    init(config: GoogleOAuthConfig,
         session: URLSession? = nil,
         restoredTokens: GoogleTokens? = nil,
         restoredMediaGrant: (tokens: GoogleTokens, fileIDs: Set<String>)? = nil) {
        self.config = config
        self.sessionOwner = session.map(CloudSessionOwner.init(adopting:)) ?? CloudSessionOwner()
        self.tokens = restoredTokens
        self.mediaToken = restoredMediaGrant?.tokens
        self.grantedFileIDs = restoredMediaGrant?.fileIDs ?? []
    }

    var accountEmail: String? { identity }
    var accountTier: GoogleAccountTier { GoogleAccountTier(email: identity) }

    // MARK: Sign-in

    @MainActor
    func signIn() async throws {
        let client = GoogleOAuthClient(config: config, session: session)
        // requireAll: false — a partial grant is a usable product, not a
        // failure. Declining Meet costs the transcript and keeps the list.
        let granted = try await client.signIn(scopes: GoogleScopes.requested, requireAll: false)
        tokens = granted
        identity = try? await fetchIdentity(accessToken: granted.accessToken)
    }

    /// One `files.get` for `size`, using the media grant.
    ///
    /// Deliberately not called at list time: the Picker grant does not exist
    /// then, so this would 403 on every row. Returns nil on any failure — an
    /// unknown size is a state the verifier already models honestly, and a
    /// guessed one would be worse than none.
    private func driveFileSize(fileID: String, accessToken: String) async -> Int64? {
        guard var components = URLComponents(
            string: "https://www.googleapis.com/drive/v3/files/\(fileID)")
        else { return nil }
        components.queryItems = [URLQueryItem(name: "fields", value: "size")]
        guard let url = components.url else { return nil }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        guard let (data, response) = try? await session.data(for: request),
              GoogleResponseClassifier.classify(
                  status: (response as? HTTPURLResponse)?.statusCode ?? 0, body: data) == .ok
        else { return nil }

        // Drive returns `size` as a STRING, not a number — a JSON int64 would
        // lose precision in some clients, so Google quotes it. Decoding it as
        // `Int64` silently yields nil.
        struct Meta: Decodable { let size: String? }
        return (try? JSONDecoder().decode(Meta.self, from: data)).flatMap { $0.size }.flatMap(Int64.init)
    }

    private func fetchIdentity(accessToken: String) async throws -> String? {
        var request = URLRequest(url: URL(string: "https://openidconnect.googleapis.com/v1/userinfo")!)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await session.data(for: request)
        struct Info: Decodable { let email: String? }
        return (try? JSONDecoder().decode(Info.self, from: data))?.email
    }

    // MARK: Listing

    func list(window: DateInterval) async -> MeetingListing {
        guard let tokens else {
            return empty(window, outcome: .failed(after: 0,
                                                  outcome: .needsReauthentication(reason: "no token")))
        }

        // Identity is captured during `signIn`, but an adapter built from a
        // restored grant never runs that — and `identity` is the only input to
        // `GoogleAccountTier`. Left nil the tier reads `.unknown`, which marks
        // every attendee external *and* downgrades an un-recorded meeting from
        // "nobody pressed record" to a claim about the account's plan. One
        // call, once, closes both.
        if identity == nil {
            identity = try? await fetchIdentity(accessToken: tokens.accessToken)
        }

        // Ids from an earlier window are not merely clutter. `fetch` resolves a
        // row to a file through this map, so an id that outlives its row is a
        // download aimed at last month's meeting.
        driveFileIDs.removeAll()

        var events: [CalendarEventsPage.Event] = []
        var pageToken: String?
        var pagesFetched = 0
        // A cap, so a pathological calendar cannot spin forever — and, when it
        // bites, `outcome` says so rather than letting a prefix pass for a
        // total.
        let pageCap = 10
        var outcome: ListOutcome = .exhausted

        repeat {
            do {
                let page = try await fetchEventsPage(
                    window: window, pageToken: pageToken, accessToken: tokens.accessToken)
                events.append(contentsOf: page.items ?? [])
                pageToken = page.nextPageToken
                pagesFetched += 1
                if pageToken != nil && pagesFetched >= pageCap {
                    outcome = .pageCapHit(pagesFetched: pagesFetched)
                    break
                }
            } catch let error as GoogleAPIError {
                outcome = .failed(after: pagesFetched, outcome: error.outcome)
                break
            } catch {
                outcome = .failed(after: pagesFetched,
                                  outcome: .unexpected(status: 0, reason: error.localizedDescription))
                break
            }
        } while pageToken != nil

        let rows = await buildRows(from: events, tokens: tokens)
        let fetchable = rows.filter(\.isSelectable).count
        let others = rows.filter { $0.organiser != nil }.count

        return MeetingListing(
            rows: rows,
            arithmetic: JoinArithmetic(
                eventsInWindow: events.count,
                fetchable: fetchable,
                organisedByOthers: others,
                outcome: outcome
            ),
            window: window
        )
    }

    private func fetchEventsPage(
        window: DateInterval,
        pageToken: String?,
        accessToken: String
    ) async throws -> CalendarEventsPage {
        var components = URLComponents(
            string: "https://www.googleapis.com/calendar/v3/calendars/primary/events")!
        var items = [
            // TRAP: RFC3339 with a MANDATORY offset. A bare local timestamp is
            // rejected outright. `.withInternetDateTime` emits a conformant
            // string; never hand-roll the format.
            //
            // Second TRAP in the same pair, and this one is silent: `timeMin`
            // bounds an event's END and `timeMax` bounds its START. It is an
            // overlap query, not a containment one — a multi-day event that
            // began before the window still comes back.
            URLQueryItem(name: "timeMin", value: Self.rfc3339(window.start)),
            URLQueryItem(name: "timeMax", value: Self.rfc3339(window.end)),
            // TRAP, and the worst of them. Without this a weekly research sync
            // returns as a single recurring *master* whose start is the
            // series' original start — possibly years ago — so it either
            // vanishes from the window or is dated wrongly. Also a hard
            // prerequisite for orderBy=startTime.
            URLQueryItem(name: "singleEvents", value: "true"),
            URLQueryItem(name: "orderBy", value: "startTime"),
            // Drops out-of-office, birthdays, focus time and working-location
            // entries, which are noise in a meeting list and would inflate the
            // footer's "meetings in window" count into nonsense.
            URLQueryItem(name: "eventTypes", value: "default"),
            URLQueryItem(name: "maxResults", value: "250"),
            // NOT set: `maxAttendees`. It reads like a truncation and is a
            // CLIFF — Google: "If there are more than the specified number of
            // attendees, only the participant is returned." Capping at 10 on an
            // 11-person event yields a roster of exactly one, silently.
            //
            // **`fields` is what makes this file's opening claim true.** The
            // header says event bodies "are never fetched and never persisted",
            // and the narrow `Decodable` guaranteed only the second half — with
            // no projection Google returns the full event resource, so every
            // agenda, dial-in PIN and medical appointment in the researcher's
            // diary crossed the wire and could land in a URL cache. Teams has
            // always done this (`$select`); Google was the asymmetry. The list
            // below must stay in step with `CalendarEventsPage`.
            URLQueryItem(
                name: "fields",
                value: "items(id,summary,start,end,attendees,organizer,"
                    + "conferenceData,attendeesOmitted,recurringEventId),nextPageToken"
            ),
        ]
        if let pageToken { items.append(URLQueryItem(name: "pageToken", value: pageToken)) }
        components.queryItems = items

        var request = URLRequest(url: components.url!)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        let classified = GoogleResponseClassifier.classify(status: status, body: data)
        guard classified == .ok else { throw GoogleAPIError(outcome: classified) }
        return try JSONDecoder().decode(CalendarEventsPage.self, from: data)
    }

    /// Joins each Meet-bearing event to its conference record and recording.
    ///
    /// The join key is `conferenceData.conferenceId`, which for `hangoutsMeet`
    /// is the 10-letter meeting code, and matches the Meet API's
    /// `space.meetingCode`.
    private func buildRows(
        from events: [CalendarEventsPage.Event],
        tokens: GoogleTokens
    ) async -> [CloudImportRow] {
        let canReachMeet = tokens.has(GoogleScopes.meetReadonly)
        let tier = GoogleAccountTier(email: identity)
        let domain = tier.organisationDomain

        // Pass 1 — narrow to the events that can become rows, in calendar
        // order, before any network call is made.
        var candidates: [(event: CalendarEventsPage.Event, start: Date, isOrganiser: Bool)] = []
        for event in events {
            guard let start = event.start?.dateTime.flatMap(Self.parseRFC3339) else {
                // No `dateTime` means an all-day event (Google returns `date`
                // instead, and the two are mutually exclusive). An interview
                // always has a time, so requiring one filters leave, holidays
                // and OOO for free.
                continue
            }
            guard event.conferenceData?.conferenceSolution?.key?.type == "hangoutsMeet" else {
                // No Meet call attached. Counted in the window total — which is
                // what makes the footer's arithmetic honest — but not a row.
                continue
            }
            candidates.append((event, start, event.organizer?.isSelf == true))
        }

        // Pass 2 — the Meet lookups, concurrently.
        //
        // **This is the pass that decides whether the window feels broken.**
        // Each lookup is two sequential round trips (conference record, then
        // its recordings), and the obvious shape — resolve each row inside the
        // loop that builds it — makes them all sequential too. A researcher
        // with thirty Meet calls in a month therefore waits on sixty serial
        // requests behind a spinner with no progress, for a list Teams renders
        // from a single call. Nothing errors; it is just slow enough to read as
        // a hang, which is the failure mode that gets a feature abandoned
        // rather than reported.
        //
        // Only organiser-owned events with a meeting code are queued: the
        // others are already decided and a request for them would 403.
        let jobs: [(index: Int, code: String, start: Date)] = canReachMeet
            ? candidates.indices.compactMap { i in
                guard candidates[i].isOrganiser,
                      let code = candidates[i].event.conferenceData?.conferenceId
                else { return nil }
                return (index: i, code: code, start: candidates[i].start)
            }
            : []
        let lookups = await Self.lookUpRecordings(
            jobs: jobs, accessToken: tokens.accessToken, session: session)

        // Pass 3 — assemble, in the original order.
        var rows: [CloudImportRow] = []
        for (index, candidate) in candidates.enumerated() {
            let event = candidate.event
            let start = candidate.start
            let isOrganiser = candidate.isOrganiser
            let attendees = Self.attendees(of: event, domain: domain)

            var video: ArtifactAvailability = .available
            var fileID: String?
            var duration: TimeInterval?
            var expiresAt: Date?

            if !isOrganiser {
                video = .notOrganiser(organiser: event.organizer?.displayName
                                      ?? event.organizer?.email)
            } else if !canReachMeet {
                video = .needsScope(GoogleScopes.meetReadonly)
            } else {
                // Nil covers three shapes: no meeting code to search on, no
                // conference record, and no FILE_GENERATED recording. All three
                // mean the same thing to the researcher — there is nothing to
                // fetch — and none of them is a fault.
                let found = lookups[index]
                fileID = found?.fileID
                expiresAt = found?.recordExpires
                if fileID == nil {
                    // Only a personal account earns the plan verdict, where it
                    // is literally true. A Workspace account with an unrecorded
                    // meeting is not a capability problem, and saying so sends
                    // a paying customer to argue with their admin.
                    video = tier == .personal ? .notOnThisPlan : .notRecorded
                }
            }

            if let end = event.end?.dateTime.flatMap(Self.parseRFC3339) {
                duration = end.timeIntervalSince(start)
            }

            let rowID = event.id ?? (fileID ?? UUID().uuidString)
            if let fileID { driveFileIDs[rowID] = fileID }

            rows.append(CloudImportRow(
                id: rowID,
                title: event.summary ?? "Untitled meeting",
                startsAt: start,
                duration: duration,
                // Size needs a Drive metadata read, which needs the file grant
                // this row may not have yet. Left nil rather than guessed —
                // the free-space precheck reads it and a fabricated number
                // there would be worse than an absent one.
                sizeBytes: nil,
                expiresAt: expiresAt,
                attendees: attendees,
                localState: .notImported,
                video: video,
                roster: attendees.isEmpty ? .unsupported : .available,
                transcript: canReachMeet ? .available : .needsScope(GoogleScopes.meetReadonly),
                organiser: isOrganiser ? nil : Self.person(event.organizer, domain: nil)
            ))
        }
        return rows
    }

    /// What one meeting's lookup found.
    ///
    /// A named `Sendable` struct rather than the tuple this used to return, so
    /// it can cross a task-group boundary.
    private struct RecordingLookup: Sendable {
        let fileID: String?
        let recordExpires: Date?
    }

    /// How many meeting lookups are in flight at once.
    ///
    /// Four, the same bound §9 puts on concurrent downloads — not because the
    /// two are the same problem, but because one number this codebase can
    /// justify beats two it cannot. The constraint here is Google's per-user
    /// quota, which is per-minute and shared across every call this adapter
    /// makes, so unbounded fan-out on a busy calendar would trade a slow list
    /// for a rate-limited one.
    private static let lookupConcurrency = 4

    /// Runs the per-meeting lookups concurrently and returns them keyed by the
    /// caller's own index, so calendar order survives the reordering that
    /// concurrency guarantees.
    ///
    /// Static, and taking the session and token as parameters, so no child task
    /// captures `self`: this adapter holds mutable state (`driveFileIDs`,
    /// `identity`) that must not be touched off the calling context.
    private static func lookUpRecordings(
        jobs: [(index: Int, code: String, start: Date)],
        accessToken: String,
        session: URLSession
    ) async -> [Int: RecordingLookup] {
        guard !jobs.isEmpty else { return [:] }
        return await withTaskGroup(of: (Int, RecordingLookup?).self) { group in
            var results: [Int: RecordingLookup] = [:]
            var next = 0

            while next < min(lookupConcurrency, jobs.count) {
                let job = jobs[next]
                next += 1
                group.addTask {
                    (job.index, await Self.recording(forMeetingCode: job.code, near: job.start,
                                                     accessToken: accessToken, session: session))
                }
            }
            // Refill as each finishes rather than in waves: a wave stalls on
            // its slowest member while three connections sit idle.
            while let (index, found) = await group.next() {
                if let found { results[index] = found }
                if next < jobs.count {
                    let job = jobs[next]
                    next += 1
                    group.addTask {
                        (job.index, await Self.recording(forMeetingCode: job.code, near: job.start,
                                                         accessToken: accessToken, session: session))
                    }
                }
            }
            return results
        }
    }

    /// Finds the recording for one meeting, or establishes that there isn't one.
    ///
    /// **Returns nil for two different facts, and that conflation is a known
    /// gap.** "There is no recording" and "the lookup failed" both arrive here
    /// as nil, and the caller renders both as *not recorded* — a claim of
    /// knowledge in the second case. It is bounded (a failed lookup makes a row
    /// unfetchable, which is the safe direction) but it is exactly the
    /// plausible-wrong-answer shape this file's header warns about, and closing
    /// it needs an availability case the shared row model does not have yet.
    private static func recording(
        forMeetingCode code: String,
        near start: Date,
        accessToken: String,
        session: URLSession
    ) async -> RecordingLookup? {
        // TRAP: the filter string uses snake_case field names while the JSON
        // response is camelCase. `space.meetingCode = …` returns an empty list
        // with HTTP 200 — a silent no-match that looks exactly like "there was
        // no recording".
        //
        // The start_time clause is not an optimisation. A recurring meeting
        // reuses ONE meeting code across every instance, so the code alone
        // cannot say which Tuesday's recording this is.
        //
        // **The lookback is three hours, not one, and the reason is that people
        // join early.** The conference record is stamped when the call actually
        // starts, the calendar event says when it was meant to; a researcher
        // who opens the room to check their mic before a 3pm session produces a
        // record dated before the event. Observed live on 16 Aug 2026 — a call
        // joined at 2:12pm against a 3:00pm event cleared the old one-hour
        // lookback by twelve minutes. Twenty minutes earlier and the row would
        // have read "Not recorded" about a recording sitting in Drive, which is
        // the false negative this whole file is written against.
        //
        // Three hours is bounded by the recurrence it has to disambiguate: the
        // tightest realistic recurrence is daily, 24 hours apart, so the window
        // must stay under 24 hours wide. At −3/+12 it is 15, with room to
        // spare. Do not widen the trailing edge past +12 without shrinking this
        // one — the sum is the constraint, not either end.
        let dayStart = start.addingTimeInterval(-3 * 3600)
        let dayEnd = start.addingTimeInterval(12 * 3600)
        let filter = "space.meeting_code = \"\(code)\" AND start_time>=\"\(Self.rfc3339(dayStart))\" AND start_time<=\"\(Self.rfc3339(dayEnd))\""

        var components = URLComponents(string: "https://meet.googleapis.com/v2/conferenceRecords")!
        components.queryItems = [URLQueryItem(name: "filter", value: filter)]
        guard let url = components.url else { return nil }

        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        guard let (data, response) = try? await session.data(for: request),
              GoogleResponseClassifier.classify(
                status: (response as? HTTPURLResponse)?.statusCode ?? 0, body: data) == .ok,
              let page = try? JSONDecoder().decode(ConferenceRecordsPage.self, from: data),
              let record = page.conferenceRecords?.first,
              let name = record.name
        else { return nil }

        let expires = record.expireTime.flatMap(Self.parseRFC3339)

        // `name` is remote-controlled (`conferenceRecords/<id>`), so it goes
        // through the failable initialiser rather than a force-unwrap — the
        // same rule this file applies to `fileID` in `fetch`, and for the same
        // reason: a third party decides what is in the string, and a crash is
        // a worse outcome than a row that can't be fetched.
        guard let recURL = URL(string: "https://meet.googleapis.com/v2/\(name)/recordings") else {
            return RecordingLookup(fileID: nil, recordExpires: expires)
        }
        var recRequest = URLRequest(url: recURL)
        recRequest.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        guard let (recData, recResponse) = try? await session.data(for: recRequest),
              GoogleResponseClassifier.classify(
                status: (recResponse as? HTTPURLResponse)?.statusCode ?? 0, body: recData) == .ok,
              let recPage = try? JSONDecoder().decode(RecordingsPage.self, from: recData)
        else { return RecordingLookup(fileID: nil, recordExpires: expires) }

        // Only a FILE_GENERATED recording has bytes behind it. STARTED and
        // ENDED both mean "not yet", and Google's own propagation delay is
        // roughly the length of the meeting — so offering a row for those
        // would produce a fetch that 404s minutes after the researcher ticks it.
        //
        // KNOWN GAP: `.first` where a meeting stopped and restarted recording
        // yields two FILE_GENERATED entries, and the second half is dropped in
        // silence — a §6-class loss, since a half-session analyses cleanly and
        // reads as complete. Fixing it means one row producing two files, which
        // the row model does not express. Unproven either way until a segmented
        // recording is actually observed.
        let generated = recPage.recordings?.first { $0.state == "FILE_GENERATED" }
        return RecordingLookup(fileID: generated?.driveDestination?.file, recordExpires: expires)
    }

    // MARK: Fetching

    /// Ask for the file grant over the whole ticked batch, in one Picker round
    /// trip. Called by the store before the first `fetch`.
    /// Google's batch preparation IS the Picker round trip.
    @MainActor
    func prepareBatch(rowIDs: [String]) async throws {
        try await requestMediaGrant(for: rowIDs)
    }

    @MainActor
    func requestMediaGrant(for rowIDs: [String]) async throws {
        let wanted = rowIDs.compactMap { driveFileIDs[$0] }
        guard !wanted.isEmpty else { return }
        let client = GoogleOAuthClient(config: config, session: session)
        let (tokens, picked) = try await client.pickMedia(fileIDs: wanted)
        mediaToken = tokens
        // Honour what was granted, never what was asked for: the researcher
        // may deselect inside the Picker, and treating the request as the
        // answer would produce a batch that 403s on exactly the rows they
        // chose to remove.
        grantedFileIDs.formUnion(picked)
    }

    func fetch(
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        guard let fileID = driveFileIDs[row.id] else {
            return .failed(reason: "That meeting has no recording file.", isRetryable: false)
        }
        // The grant is per-file, so a row the researcher did not include in the
        // Picker selection is unreachable — and saying so beats a 403 that
        // reads like a bug.
        guard grantedFileIDs.contains(fileID), let token = mediaToken?.accessToken else {
            return .failed(
                reason: "Bristlenose doesn't have access to this file yet.",
                isRetryable: true
            )
        }

        // **Ask Drive how big it is, now that we hold the grant.**
        //
        // `row.sizeBytes` is nil on every Google row, because at *list* time the
        // Picker grant does not exist yet. That left Meet as the one platform
        // with no size at all — which silently disabled three things at once:
        // `verifyPayload`'s size comparison, the free-space precheck, and any
        // hope of catching a truncated transfer. A `ftyp` in the first eight
        // bytes was the entire defence, and a truncated MP4 has those.
        //
        // Here the grant *does* exist, so one metadata read closes it. Failure
        // is non-fatal: an absent size is the honest input the verifier already
        // knows how to treat as unknown.
        let knownSize = await driveFileSize(fileID: fileID, accessToken: token)

        // `alt=media` is what turns files.get from metadata into bytes. Without
        // it the response is a perfectly valid JSON description of the file,
        // which — absent the content-type check in the shared verifier — would
        // land on disk named .mp4.
        // Not force-unwrapped: `fileID` is a remote string, and an
        // RFC-3986-invalid character in it would crash the app rather than fail
        // the row. Same reasoning as §9's "every remote-sourced string is
        // untrusted" — a third party controls what Drive hands back.
        guard var components = URLComponents(
            string: "https://www.googleapis.com/drive/v3/files/\(fileID)")
        else { return .failed(reason: "That file has an unusable identifier.", isRetryable: false) }
        components.queryItems = [URLQueryItem(name: "alt", value: "media")]

        let name = CloudDownloadNaming.filename(
            title: row.title, startsAt: row.startsAt, fileExtension: "mp4")
        guard let mediaURL = components.url else {
            return .failed(reason: "That file has an unusable identifier.", isRetryable: false)
        }
        let request = CloudDownloadRequest(
            url: mediaURL,
            accessToken: token,
            policy: .meet,
            expected: ExpectedFile(
                sizeBytes: knownSize ?? row.sizeBytes,
                // Drive exposes md5/sha1/sha256 on files.get, but not on the
                // path this design takes — the Meet API hands over a file id,
                // not a metadata blob — so verification is size + magic bytes.
                // Fetching metadata purely to hash would cost a round trip per
                // row for a check the format probe already largely covers.
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

    // MARK: Helpers

    private func empty(_ window: DateInterval, outcome: ListOutcome) -> MeetingListing {
        MeetingListing(
            rows: [],
            arithmetic: JoinArithmetic(eventsInWindow: 0, fetchable: 0,
                                       organisedByOthers: 0, outcome: outcome),
            window: window
        )
    }

    private static let formatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func rfc3339(_ date: Date) -> String { formatter.string(from: date) }

    static func parseRFC3339(_ string: String) -> Date? {
        if let d = formatter.date(from: string) { return d }
        // Google emits fractional seconds on some resources and not others.
        let withFractional = ISO8601DateFormatter()
        withFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return withFractional.date(from: string)
    }

    /// Builds the attendee list, applying the two filters that are correctness
    /// rather than presentation.
    private static func attendees(
        of event: CalendarEventsPage.Event,
        domain: String?
    ) -> [CloudImportRow.Attendee] {
        (event.attendees ?? [])
            // Rooms and equipment are attendees to Google and noise to a
            // researcher.
            .filter { $0.resource != true }
            .compactMap { person(_: $0, domain: domain) }
    }

    private static func person(
        _ p: CalendarEventsPage.Event.Person?,
        domain: String?
    ) -> CloudImportRow.Attendee? {
        guard let p, p.email != nil || p.displayName != nil else { return nil }
        let external = domain.map { d in !(p.email?.hasSuffix("@\(d)") ?? false) } ?? true
        return CloudImportRow.Attendee(
            // `displayName` is documented "if available" and, for external
            // guests, routinely absent — Google discards it for @gmail.com
            // addresses at insert time. So the participant most likely to have
            // no name is exactly the one the researcher interviewed. The row
            // falls back to the local part rather than showing nothing.
            displayName: p.displayName,
            email: p.email,
            isSelf: p.isSelf == true,
            isOrganiser: p.organizer == true,
            didDecline: p.responseStatus == "declined",
            isExternal: external
        )
    }
}

/// Wraps a classified outcome so it can cross a `throws` boundary.
struct GoogleAPIError: Error {
    let outcome: GoogleAPIOutcome
}
