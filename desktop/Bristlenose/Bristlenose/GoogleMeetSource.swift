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
    private let session: URLSession
    private var tokens: GoogleTokens?
    private var identity: String?

    /// Drive file ids the user has granted through the Picker, keyed by row.
    /// Held because the grant is per-file: a row whose id is absent needs a
    /// Picker round trip before its bytes are reachable.
    private var grantedFileIDs: Set<String> = []

    init(config: GoogleOAuthConfig, session: URLSession = .shared) {
        self.config = config
        self.session = session
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
        var rows: [CloudImportRow] = []

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

            let isOrganiser = event.organizer?.isSelf == true
            let attendees = Self.attendees(of: event, domain: GoogleAccountTier(email: identity).organisationDomain)

            var video: ArtifactAvailability = .available
            var fileID: String?
            var duration: TimeInterval?
            var expiresAt: Date?

            if !isOrganiser {
                video = .notOrganiser(organiser: event.organizer?.displayName
                                      ?? event.organizer?.email)
            } else if !canReachMeet {
                video = .needsScope(GoogleScopes.meetReadonly)
            } else if let code = event.conferenceData?.conferenceId {
                let found = await recording(forMeetingCode: code,
                                            near: start,
                                            accessToken: tokens.accessToken)
                fileID = found?.fileID
                expiresAt = found?.recordExpires
                if found?.fileID == nil {
                    // The meeting happened, we could look, and there is no
                    // recording. Distinct from "we weren't allowed to look".
                    video = .notOnThisPlan
                }
            }

            if let end = event.end?.dateTime.flatMap(Self.parseRFC3339) {
                duration = end.timeIntervalSince(start)
            }

            rows.append(CloudImportRow(
                id: event.id ?? (fileID ?? UUID().uuidString),
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

    private func recording(
        forMeetingCode code: String,
        near start: Date,
        accessToken: String
    ) async -> (fileID: String?, recordExpires: Date?)? {
        // TRAP: the filter string uses snake_case field names while the JSON
        // response is camelCase. `space.meetingCode = …` returns an empty list
        // with HTTP 200 — a silent no-match that looks exactly like "there was
        // no recording".
        //
        // The start_time clause is not an optimisation. A recurring meeting
        // reuses ONE meeting code across every instance, so the code alone
        // cannot say which Tuesday's recording this is.
        let dayStart = start.addingTimeInterval(-3600)
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

        var recURL = URLComponents(string: "https://meet.googleapis.com/v2/\(name)/recordings")!
        recURL.queryItems = []
        var recRequest = URLRequest(url: recURL.url!)
        recRequest.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        guard let (recData, recResponse) = try? await session.data(for: recRequest),
              GoogleResponseClassifier.classify(
                status: (recResponse as? HTTPURLResponse)?.statusCode ?? 0, body: recData) == .ok,
              let recPage = try? JSONDecoder().decode(RecordingsPage.self, from: recData)
        else { return (nil, expires) }

        // Only a FILE_GENERATED recording has bytes behind it. STARTED and
        // ENDED both mean "not yet", and Google's own propagation delay is
        // roughly the length of the meeting — so offering a row for those
        // would produce a fetch that 404s minutes after the researcher ticks it.
        let generated = recPage.recordings?.first { $0.state == "FILE_GENERATED" }
        return (generated?.driveDestination?.file, expires)
    }

    // MARK: Fetching

    /// Ask for the file grant over the whole ticked batch, in one Picker round
    /// trip. Called by the store before the first `fetch`.
    @MainActor
    func requestMediaGrant(for fileIDs: [String]) async throws {
        let client = GoogleOAuthClient(config: config, session: session)
        let (_, picked) = try await client.pickMedia(fileIDs: fileIDs)
        // Honour what was granted, never what was asked for: the researcher
        // may deselect inside the Picker, and treating the request as the
        // answer would produce a batch that 403s on the rows they removed.
        grantedFileIDs.formUnion(picked)
    }

    func fetch(
        row: CloudImportRow,
        destination: URL,
        progress: @escaping @Sendable (FetchProgress) -> Void
    ) async -> FetchOutcome {
        // Deliberately not implemented against the network yet: the download
        // half needs the Picker grant proven against a real Meet recording
        // first (the one open question the research could not close), and a
        // half-written download that silently produces a truncated MP4 is the
        // exact failure §6 exists to prevent. Failing loudly beats guessing.
        .failed(reason: "Download not wired yet — the Picker grant is unproven.",
                isRetryable: false)
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
