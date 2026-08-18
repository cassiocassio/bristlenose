import Foundation
import os

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
        /// A Drive file hung off the event. **Probe, not yet a feature.**
        ///
        /// Observed 16 Aug 2026: a recorded Meet event carries its Recording,
        /// its Transcript and its Gemini notes here as attachments, each with a
        /// `fileId`. If that is reliable it is a far shorter road to the video
        /// than `conferenceRecords` — no meeting-code match, no start-time
        /// window, no organiser wall — and it would retire the three findings
        /// that exist only to make that join work.
        ///
        /// Decoded narrowly for the same reason as everything else here: a
        /// struct with nowhere to put an agenda cannot keep one.
        struct Attachment: Decodable {
            let fileId: String?
            let title: String?
            let mimeType: String?
        }
        let id: String?
        let summary: String?
        let start: When?
        let end: When?
        let attendees: [Person]?
        let organizer: Person?
        let conferenceData: Conference?
        let attachments: [Attachment]?
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
        /// `spaces/<id>` — the room the call was held in.
        ///
        /// **The join key, one dereference away.** The code a calendar event
        /// carries (`conferenceData.conferenceId`) is the same string
        /// `spaces.get` returns as `meetingCode`, so resolving this turns the
        /// calendar↔recording join from a time heuristic into an equality.
        let space: String?
    }
    let conferenceRecords: [Record]?
    let nextPageToken: String?
}

/// One Meet space, reduced to the only field this adapter reads.
///
/// Narrow on purpose, like every other decode here: a struct with nowhere to put
/// `activeConference` cannot accidentally hold a pointer to a call in progress.
private struct MeetSpace: Decodable {
    /// `abc-mnop-xyz`. The string a person types to join, and the string a
    /// calendar event stores — which is what makes the join exact.
    let meetingCode: String?
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
        /// **The canonical session boundary, if Google serves it.**
        ///
        /// Decided 16 Aug 2026: the *video* is the session. Not the calendar
        /// event — which may not exist, and which one call can hold several
        /// sessions inside — and not the conference record, which spans
        /// everything said before anyone pressed record.
        ///
        /// Optional because it is unproven on the wire: these fields are
        /// documented on the Recording resource but this adapter has never
        /// asked for them. Absent, the row falls back to the event's start and
        /// reports **no** duration at all — never the meeting's, which is the
        /// number that told a 20-second file it was 1h 30m.
        let startTime: String?
        let endTime: String?
    }
    let recordings: [Recording]?
    /// Decoded so the truncation can at least be *seen*. Google returns at most
    /// ten recordings per page by default and this call sends no page size, so
    /// a call segmented past that loses its tail — and, before this member
    /// existed, could not even report that it had.
    let nextPageToken: String?
}

// MARK: - The harvest

/// Every Meet call in the window, with what it produced and which room it was
/// in — the whole remote half of the join, gathered before a single row exists.
///
/// This is the shape the inversion needed. The adapter used to hold one lookup
/// per calendar event, which meant a call could only be *found* by starting from
/// a booking. Here the calls are the primary list and the calendar is joined
/// onto them, so a call nobody booked is an ordinary member rather than an
/// impossibility.
private struct MeetHarvest: Sendable {

    /// One recording with bytes behind it.
    struct Recording: Sendable {
        let fileID: String
        /// When the record button was actually pressed, and for how long — the
        /// session's real boundary. Nil when Google didn't serve it.
        let startedAt: Date?
        let duration: TimeInterval?
    }

    /// One call.
    struct Record: Sendable {
        /// `conferenceRecords/<id>`.
        let name: String
        /// The room's join code, resolved through `spaces.get`. Nil when the
        /// space could not be read — and then this call can never be joined to a
        /// booking, because the code is the only key they share.
        let meetingCode: String?
        /// When the *call* began. Not when anyone pressed record: a conference
        /// record spans everything said before the button.
        let start: Date?
        let end: Date?
        let expires: Date?

        /// **Every** generated recording, in the order Google returned them.
        ///
        /// This used to be a single optional taken with `.first`, and the second
        /// half of any meeting where somebody stopped and restarted recording
        /// was dropped in silence — a half-session analyses perfectly cleanly
        /// and reads as complete, so nothing ever told the researcher that forty
        /// minutes never arrived.
        let recordings: [Recording]

        /// Whether Google reported any `FILE_GENERATED` recording at all,
        /// regardless of whether we could resolve a file for it.
        ///
        /// The two are not the same fact and the difference is a false claim:
        /// with this false, "nobody recorded this meeting" is true; with it true
        /// and `recordings` empty, a completed recording exists and we simply
        /// could not reach it.
        let sawGeneratedRecordings: Bool
    }

    var records: [MeetHarvest.Record] = []

    /// Why the set is incomplete, when it is.
    ///
    /// **Load-bearing, not diagnostic.** Every row reads this: a failure here
    /// means "we could not look", and the one thing the window must never do is
    /// render that as "nobody recorded". Nil means the window's calls were read
    /// end to end and an absence is genuinely an absence.
    var failure: GoogleAPIOutcome?
}

/// One call and what asking about it returned. Named rather than a tuple so it
/// can cross a task-group boundary.
private struct HarvestedCall: Sendable {
    let record: ConferenceRecordsPage.Record
    let recordings: [MeetHarvest.Recording]
    let sawGenerated: Bool
}

/// One room and its join code, or nil where the room could not be read.
private struct ResolvedSpace: Sendable {
    let space: String
    let code: String?
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
    /// - Parameter restoredIdentity: the signed-in address, restored alongside
    ///   the tokens. Without it `CloudImportStore` opens on `.signedOut` —
    ///   it decides that from `accountEmail` — so a perfectly good restored
    ///   token would sit behind a sign-in button and the whole restore would
    ///   look like it had failed.
    ///
    /// - Parameter onGrantChanged: called whenever the grant materially moves
    ///   — signed in, refreshed, Picker granted, or revoked. **Nil means
    ///   forget it**, and the revoked case is why this is one callback rather
    ///   than a `save`: a store that is only ever told about successes keeps a
    ///   dead grant looking live until the app is reinstalled.
    init(config: GoogleOAuthConfig,
         session: URLSession? = nil,
         restoredTokens: GoogleTokens? = nil,
         restoredMediaGrant: (tokens: GoogleTokens, fileIDs: Set<String>)? = nil,
         restoredIdentity: String? = nil,
         onGrantChanged: (@Sendable (GoogleGrant?) -> Void)? = nil) {
        self.config = config
        self.sessionOwner = session.map(CloudSessionOwner.init(adopting:)) ?? CloudSessionOwner()
        self.tokens = restoredTokens
        self.mediaToken = restoredMediaGrant?.tokens
        self.grantedFileIDs = restoredMediaGrant?.fileIDs ?? []
        self.identity = restoredIdentity
        self.onGrantChanged = onGrantChanged
    }

    private let onGrantChanged: (@Sendable (GoogleGrant?) -> Void)?

    /// Publish the current grant, or its absence.
    ///
    /// Called after every move rather than at chosen moments, because the
    /// moment that matters is the one nobody remembers to instrument — a
    /// silent refresh an hour in, whose new refresh token is the only one that
    /// will still work tomorrow.
    /// **Never call the store synchronously.** Persisting goes to the Keychain,
    /// and a Keychain write can block on an authorisation prompt — which on an
    /// ad-hoc-signed build is not hypothetical, since those fall back to the
    /// legacy file-based keychain that binds grants to the binary hash and
    /// re-prompts on every rebuild. `signIn()` is `@MainActor` and calls this
    /// the instant the web auth session returns, so a blocking write there
    /// stalls the main actor behind a dialog the auth window is covering, and
    /// the window spins forever with no error anywhere.
    ///
    /// The snapshot is taken here, on the caller's actor, so the value that
    /// gets written is the one that was true at the call — not whatever the
    /// adapter has drifted to by the time the write lands.
    /// **Handed to the callback synchronously — the hop lives in the writer.**
    ///
    /// This used to be `Task.detached`, for a good reason: a Keychain write can
    /// block on an authorisation prompt, and one raised from the main actor sits
    /// behind the auth window with everything stalled. But two detached tasks
    /// have no relative ordering, so a refusal published just before a
    /// successful re-sign-in could land *after* it and tombstone a working
    /// grant. `CloudGrantWriter` answers both: it enqueues on a serial queue, so
    /// publishes land in the order they were made **and** off this thread.
    /// The contract that replaces the hop: `onGrantChanged` must not block.
    private func publishGrant() {
        let snapshot: GoogleGrant? = tokens.map { current in
            GoogleGrant(
                tokens: current,
                media: mediaToken.map {
                    GoogleGrant.MediaGrant(tokens: $0, fileIDs: grantedFileIDs.sorted())
                },
                identity: identity)
        }
        onGrantChanged?(snapshot)
    }

    /// Record that Google ended the session, **keeping the account**.
    ///
    /// This used to publish nil, which deleted the grant — so a revoked
    /// sign-in vanished from Settings ▸ Accounts, indistinguishable from
    /// having disconnected it yourself. The tombstone keeps the row and
    /// carries no working credential: `revoked` strips the refresh token and
    /// the media grant, so the unbreakable-retry-loop this path guards against
    /// cannot form even if the flag were ignored.
    private func publishRefusal() {
        let snapshot = GoogleGrant.revoked(identity: identity)
        onGrantChanged?(snapshot)
    }

    /// Renew the listing token when it has aged out, or report that we cannot.
    ///
    /// **The listing path had no expiry check at all** before 17 Aug 2026,
    /// which was survivable only because the token was minted at sign-in and
    /// used minutes later. The moment a sign-in outlives the window — which is
    /// the entire point of restoring one — an hour-old token is the normal
    /// case rather than the edge one.
    ///
    /// Returns false when the grant is gone for good, having already told the
    /// store to forget it: a refresh token Google has revoked will fail
    /// identically forever, and keeping it turns one honest sign-in into an
    /// unbreakable loop of failed listings.
    /// `@MainActor` because `GoogleOAuthClient`'s initialiser is — it can carry
    /// an anchor window. The refresh itself is a plain POST with no UI, so the
    /// hop costs nothing and buys the same isolation the media-token twin
    /// already has.
    @MainActor
    private func renewedListingTokenIfNeeded() async -> Bool {
        guard let current = tokens else { return false }
        guard current.isExpired else { return true }
        guard let refreshToken = current.refreshToken else {
            tokens = nil
            publishRefusal()
            return false
        }
        let client = GoogleOAuthClient(config: config, session: session)
        let renewed: GoogleTokens
        do {
            renewed = try await client.refresh(
                refreshToken: refreshToken, knownGrants: current.granted)
        } catch {
            // **Only an authoritative refusal writes a tombstone.** `try?` here
            // treated a dropped connection exactly like a revoked grant, so a
            // moment of bad wifi stripped the refresh token permanently and
            // told the researcher Google had ended their session. This path
            // runs when a token has aged out — the ordinary next-morning case
            // the whole restore feature exists to serve.
            //
            // A 4xx from the token endpoint is Google saying no. Anything else
            // leaves the grant intact for the next attempt.
            if case GoogleOAuthError.tokenExchangeFailed(let status, _) = error,
               (400...499).contains(status) {
                tokens = nil
                publishRefusal()
            } else {
                Self.log.notice("meet refresh failed without a verdict — keeping the grant")
            }
            return false
        }
        tokens = renewed
        publishGrant()
        return true
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
        // `?? identity` is load-bearing: the address derives the Keychain
        // account key, so a transient userinfo failure that nils a known-good
        // one re-derives `unidentified` and `saveGoogle` deletes the correctly
        // keyed item as a stale rekey. A cosmetic lookup must not be able to
        // destroy a credential.
        identity = (try? await fetchIdentity(accessToken: granted.accessToken)) ?? identity
        // After the identity, not before: `accountEmail` is what decides the
        // window's opening phase on the next restore, so a grant saved without
        // it restores to a sign-in button while holding a working token.
        publishGrant()
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
        // Renew before reading, not after failing. A restored sign-in is
        // routinely older than an access token's hour, so on the restore path
        // "expired" is the ordinary case — and a 401 here surfaces as
        // needsReauthentication, which sends the researcher through a sign-in
        // they did not need.
        guard await renewedListingTokenIfNeeded(), let tokens else {
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
            identity = (try? await fetchIdentity(accessToken: tokens.accessToken)) ?? identity
            // **Publish, or the backfill goes nowhere.** `saveGoogle`'s
            // `previousKey` contract and the rekey it performs both rest on
            // this call: without it the address is known in memory and the
            // stored grant stays under the anonymous key, so the account is
            // nameless in Settings ▸ Accounts and the consumer-account check
            // has nothing to check. Guarded, so a failed lookup does not write.
            if identity != nil { publishGrant() }
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

        // **The calls, listed on their own terms.** One window-wide query rather
        // than one per calendar event — which is what makes a call nobody booked
        // visible at all, and what lets the join key on the meeting code instead
        // of on a ±window around a booking.
        let harvest = await Self.harvestConferenceRecords(
            window: window,
            canReachMeet: tokens.has(GoogleScopes.meetReadonly),
            accessToken: tokens.accessToken,
            session: session)

        // **The join is over two lists, so either one being short makes the
        // output a floor.** The calendar paginator has always reported its own
        // terminus here; the records list is now the other half of the same
        // join and has to report through the same channel, or a refused
        // conference-record read renders as a confident, complete, shorter
        // list — the exact shape `ListOutcome` exists to prevent.
        if outcome == .exhausted, let failure = harvest.failure {
            outcome = .failed(after: pagesFetched, outcome: failure)
        }

        let rows = buildRows(from: events, harvest: harvest, tokens: tokens)
        let fetchable = rows.filter(\.isSelectable).count
        let others = rows.filter { $0.organiser != nil }.count

        // The terminus of the listing path, and it exists because its absence
        // was unreadable: a window stuck on the spinner logged a complete set of
        // per-meeting lookups and then simply stopped, with no way to tell
        // "list never returned" from "list returned and the UI didn't move".
        // One line, at the only place that can distinguish them.
        Self.log.notice("""
            meet_list complete events=\(events.count, privacy: .public) \
            records=\(harvest.records.count, privacy: .public) \
            unscheduled=\(rows.filter(\.isUnscheduled).count, privacy: .public) \
            rows=\(rows.count, privacy: .public) \
            fetchable=\(fetchable, privacy: .public) \
            outcome=\(String(describing: outcome), privacy: .public)
            """)

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
                    + "conferenceData,attendeesOmitted,recurringEventId,"
                    // Probe. Adds file titles and ids, which are meeting-derived
                    // rather than agenda text, so the header's claim about
                    // never fetching event bodies still holds.
                    + "attachments),nextPageToken"
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

    /// Joins the calls that happened to the meetings that were booked.
    ///
    /// **Records lead, events follow — the reverse of what this used to do**,
    /// and the reversal is what makes an unbooked call visible. Walking the
    /// calendar can only ever produce rows for things somebody scheduled, so a
    /// call started from the Meet home screen had no row, no dimmed row and no
    /// footer count. On the tenant this was built against that was two of five
    /// real recordings (16 Aug 2026).
    ///
    /// The join key is the meeting code: `conferenceData.conferenceId` on the
    /// calendar side, `space.meetingCode` on Meet's. Same string, exactly.
    private func buildRows(
        from events: [CalendarEventsPage.Event],
        harvest: MeetHarvest,
        tokens: GoogleTokens
    ) -> [CloudImportRow] {
        let canReachMeet = tokens.has(GoogleScopes.meetReadonly)
        let tier = GoogleAccountTier(email: identity)
        let domain = tier.organisationDomain

        // Pass 1 — narrow to the events that can become rows, in calendar order.
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

            // Probe, logged rather than used. If every recorded meeting carries
            // a `video/*` attachment with a fileId, that is a shorter road to
            // the file than the space resolution below.
            let attachments = event.attachments ?? []
            Self.log.notice("""
                meet_event attachments=\(attachments.count, privacy: .public) \
                kinds=[\(attachments.compactMap(\.mimeType).joined(separator: ","), privacy: .public)] \
                hasFileIDs=\(attachments.allSatisfy { $0.fileId != nil }, privacy: .public)
                """)
            for attachment in attachments {
                Self.log.debug("meet_event attachment title=\(attachment.title ?? "—", privacy: .public)")
            }
        }

        // Pass 2 — the join, on the key rather than on the clock.
        //
        // The event's key is its index in `candidates`: unique by construction
        // and stable for this listing, where `event.id` is optional and the
        // meeting code is shared by every instance of a recurring series.
        let joinEvents = candidates.indices.compactMap { index -> ConferenceRecordJoin.Event? in
            guard let code = candidates[index].event.conferenceData?.conferenceId,
                  !code.isEmpty
            else { return nil }
            return ConferenceRecordJoin.Event(
                id: String(index),
                meetingCode: code,
                start: candidates[index].start,
                end: candidates[index].event.end?.dateTime.flatMap(Self.parseRFC3339))
        }
        let join = ConferenceRecordJoin.join(
            records: harvest.records.map {
                ConferenceRecordJoin.Record(name: $0.name, meetingCode: $0.meetingCode,
                                            start: $0.start, end: $0.end)
            },
            events: joinEvents)
        let byName = Dictionary(harvest.records.map { ($0.name, $0) },
                                uniquingKeysWith: { first, _ in first })

        Self.log.notice("""
            meet_join events=\(joinEvents.count, privacy: .public) \
            records=\(harvest.records.count, privacy: .public) \
            matched=\(join.byEvent.values.reduce(0) { $0 + $1.count }, privacy: .public) \
            unmatched=\(join.unmatched.count, privacy: .public) \
            failure=\(harvest.failure.map { String(describing: $0) } ?? "none", privacy: .public)
            """)

        // Pass 3 — a row per booked meeting, and one per recording it produced.
        var rows: [CloudImportRow] = []
        for (index, candidate) in candidates.enumerated() {
            let event = candidate.event
            let start = candidate.start
            let isOrganiser = candidate.isOrganiser
            let attendees = Self.attendees(of: event, domain: domain)

            let mine = (join.byEvent[String(index)] ?? []).compactMap { byName[$0] }
            let found = Self.unionedRecordings(of: mine)
            let sawGenerated = mine.contains(where: \.sawGeneratedRecordings)
            // Expiry belongs to whichever record holds the file. They share a
            // room and a window, so the first is representative — and the field
            // is nil on every tenant measured so far.
            let expiresAt = mine.compactMap(\.expires).first

            // The calendar's own two facts, kept apart from the recording's.
            // The Scheduled and Recorded columns exist because these *routinely*
            // disagree — a booked hour against a 52-minute file, and a start
            // four minutes late.
            let scheduledEnd = event.end?.dateTime.flatMap(Self.parseRFC3339)
            let scheduledDuration = scheduledEnd.map { $0.timeIntervalSince(start) }
            // A meeting id, so several recordings of one call nest under it.
            // The event id is the right key: the meeting code is reused across
            // every instance of a recurring series, so grouping on it would
            // stack six Tuesdays into one meeting.
            //
            // And **no fallback to the code**, which is what the sentence above
            // rules out and an earlier draft then did anyway. With `event.id`
            // nil, grouping on the code files every instance of a recurring
            // series under one header, titled from whichever arrived first. An
            // ungrouped row is honest; a wrongly-grouped one is not.
            let meetingID = event.id

            // **The ladder, in the order the facts arrive.** Each rung is a
            // different thing we know, and the ones that claim the most sit
            // last: a recording in hand outranks every reason we might have
            // expected not to find one.
            let video: ArtifactAvailability
            if !canReachMeet {
                video = .needsScope(GoogleScopes.meetReadonly)
            } else if !found.isEmpty {
                // **Whoever booked it.** The organiser wall used to be checked
                // first and so answered for rows we could plainly fetch: a
                // colleague's meeting whose recording this account can reach
                // read "Someone else" and drew no checkbox. Ask the data, then
                // explain what it didn't answer.
                video = .available
            } else if harvest.failure != nil {
                // We could not read the whole set of calls, so "nobody recorded
                // this" is a claim we have not earned. On a mono-reason list it
                // becomes the blanket "None of these were recorded" over a
                // month of interviews that are all sitting in Drive.
                video = .unsupported
            } else if sawGenerated {
                // Google told us a completed recording exists and we could not
                // resolve a file for it. `.unsupported` renders "Unavailable",
                // which is what we actually know.
                video = .unsupported
            } else if !isOrganiser {
                // We looked and found nothing — but a call we were only invited
                // to may not be ours to see, so the absence proves nothing.
                // Naming the organiser is the remedy: the fix is to ask them.
                //
                // Through `listLabel`, never the raw address: Google returns
                // bare addresses for people outside the organiser's domain,
                // which is exactly where UR participants live.
                video = .notOrganiser(
                    organiser: Self.person(event.organizer, domain: nil)?.listLabel)
            } else {
                // Only a personal account earns the plan verdict, where it is
                // literally true. A Workspace account with an unrecorded meeting
                // is not a capability problem, and saying so sends a paying
                // customer to argue with their admin.
                video = tier == .personal ? .notOnThisPlan : .notRecorded
            }

            // Common to every row this event produces. Only the recording's own
            // facts differ between siblings.
            func row(
                id: String,
                recordedAt: Date?,
                duration: TimeInterval?,
                siblingOrdinal: Int? = nil
            ) -> CloudImportRow {
                CloudImportRow(
                    id: id,
                    title: event.summary ?? "Untitled meeting",
                    // **The video is the session; the meeting is context.**
                    //
                    // Settled 16 Aug 2026, after a measurement: on one instant
                    // meeting the recording ran 14s and the transcript 38s, so
                    // 63% of what was said sat outside the recording. A
                    // calendar event cannot be the session boundary — it may
                    // not exist at all, one call can hold several sessions
                    // inside it, and it spans everything said before anyone
                    // pressed record.
                    //
                    // So the anchor is the record button where Google tells us
                    // when that was, and the event's start only as a fallback
                    // for a row that has no recording to be anchored to.
                    startsAt: recordedAt ?? start,
                    // The recording's own length, or nothing. It used to come
                    // from `event.end − event.start`, which reported **1h 30m**
                    // over a 20-second file — a wrong number at the exact point
                    // the researcher decides what is worth fetching, and an
                    // input to the free-space precheck. A dash is information;
                    // that was not. The booked hour is still shown, in its own
                    // column, where it cannot be mistaken for this.
                    duration: duration,
                    // Size needs a Drive metadata read, which needs the file
                    // grant this row may not have yet. Left nil rather than
                    // guessed — the free-space precheck reads it and a
                    // fabricated number there would be worse than an absent one.
                    sizeBytes: nil,
                    expiresAt: expiresAt,
                    attendees: attendees,
                    localState: .notImported,
                    video: video,
                    roster: attendees.isEmpty ? .unsupported : .available,
                    transcript: canReachMeet ? .available : .needsScope(GoogleScopes.meetReadonly),
                    organiser: isOrganiser ? nil : Self.person(event.organizer, domain: nil),
                    scheduledAt: start,
                    scheduledDuration: scheduledDuration,
                    recordedAt: recordedAt,
                    meetingID: meetingID,
                    siblingOrdinal: siblingOrdinal
                )
            }

            if found.isEmpty {
                // A meeting with no recording is still a row: it is the
                // difference between "you didn't record that one" and the
                // meeting silently not existing, which is the false negative
                // this whole adapter is written against.
                rows.append(row(id: event.id ?? UUID().uuidString,
                                recordedAt: nil, duration: nil))
            } else {
                let eventKey = event.id ?? event.conferenceData?.conferenceId ?? UUID().uuidString
                for (ordinal, recording) in found.enumerated() {
                    // **Composite, not the bare file id.** One Drive file can be
                    // reached from more than one row's worth of context, and
                    // everything downstream is keyed on row identity:
                    // `NSOutlineView` requires unique items and `Node` equality
                    // is id-only, so a duplicate id means one row never draws;
                    // `ticked`, `progress` and `outcomes` are dictionaries, so
                    // one tick would queue both and one outcome speak for both.
                    let rowID = "\(eventKey)#\(recording.fileID)"
                    // The map is what answers "does this row have a file", which
                    // the row id alone cannot: an un-recorded meeting's row id
                    // is its calendar event id, and `requestMediaGrant` must
                    // never hand that to the Picker.
                    driveFileIDs[rowID] = recording.fileID
                    rows.append(row(id: rowID,
                                    recordedAt: recording.startedAt,
                                    duration: recording.duration,
                                    // Nil for the ordinary one-recording call,
                                    // so its filename and label are unchanged.
                                    siblingOrdinal: found.count > 1 ? ordinal + 1 : nil))
                }
            }
        }

        // Pass 4 — the calls nobody booked.
        //
        // This pass is the reason for the whole inversion, and it is nine lines
        // long. Everything that made it possible happened upstream: listing the
        // records on time alone, and resolving each one's room to a code that
        // the calendar either has or hasn't.
        for name in join.unmatched {
            guard let record = byName[name], !record.recordings.isEmpty else {
                // Nothing to fetch, and nothing to say about it either: an
                // unbooked call that nobody recorded left no trace worth a row.
                continue
            }
            rows.append(contentsOf: unscheduledRows(for: record))
        }

        return rows
    }

    /// Rows for a call that has no booking behind it.
    ///
    /// **Titled with the meeting code**, which is the string the researcher
    /// typed or clicked to join and the only name this call has ever had. Two
    /// such calls in one day are then told apart at a glance — where a shared
    /// "Instant meeting" title would leave them distinguishable only by clock,
    /// and would collide in `CloudDownloadNaming` the moment both were fetched.
    /// That the code is a live join key is a considered trade: the researcher's
    /// own room code, in their own window, against two files overwriting each
    /// other on disk.
    private func unscheduledRows(for record: MeetHarvest.Record) -> [CloudImportRow] {
        let title = record.meetingCode ?? Self.shortID(of: record.name)
        // Siblings only when there really are siblings, so the ordinary
        // one-recording call renders flat rather than behind a triangle.
        let meetingID = record.recordings.count > 1 ? record.name : nil

        return record.recordings.enumerated().map { ordinal, recording in
            let rowID = "\(record.name)#\(recording.fileID)"
            driveFileIDs[rowID] = recording.fileID
            let anchor = recording.startedAt ?? record.start
            if anchor == nil {
                // Neither the recording nor its call carried a clock, which
                // Google's own contract says cannot happen (`ConferenceRecord`
                // documents `startTime` as always set). Said out loud and given
                // an obviously-invented date rather than a plausible one: the
                // row must exist — dropping a recording is the failure this
                // adapter is written against — and a 2001 day header reads as a
                // bug, where "today" would read as a fact.
                Self.log.notice("meet_row unscheduled_without_clock")
            }
            return CloudImportRow(
                id: rowID,
                title: title,
                startsAt: anchor ?? .distantPast,
                duration: recording.duration,
                sizeBytes: nil,
                expiresAt: record.expires,
                // No event, so no invitation list. Not a gap to be filled: the
                // roster genuinely does not exist for a call started from the
                // Meet home screen, and `.unsupported` says so.
                attendees: [],
                localState: .notImported,
                video: .available,
                roster: .unsupported,
                transcript: .available,
                organiser: nil,
                scheduledAt: nil,
                scheduledDuration: nil,
                recordedAt: recording.startedAt,
                meetingID: meetingID,
                siblingOrdinal: record.recordings.count > 1 ? ordinal + 1 : nil,
                // The fact, not an inference from the two nils above. See the
                // property's own note: on Teams those nils mean something else
                // entirely.
                isUnscheduled: true
            )
        }
    }

    /// Every recording across a call's conference records, deduplicated and in
    /// the order they happened.
    ///
    /// One booking can hold several calls into the same room — join, leave,
    /// rejoin — and their recordings are spread across separate records. Asking
    /// only the "best" one reported "Not recorded" over two files sitting in
    /// Drive.
    private static func unionedRecordings(
        of records: [MeetHarvest.Record]
    ) -> [MeetHarvest.Recording] {
        var found: [MeetHarvest.Recording] = []
        var seen = Set<String>()
        for record in records {
            for recording in record.recordings where seen.insert(recording.fileID).inserted {
                found.append(recording)
            }
        }
        // Chronological, so "Recording 1" is the one that happened first across
        // the whole meeting rather than within whichever record it came from.
        found.sort { ($0.startedAt ?? .distantPast) < ($1.startedAt ?? .distantPast) }
        return found
    }

    /// `conferenceRecords/abc123` → `abc123`. A last-resort title, used only
    /// when a call's room could not be resolved to its code.
    private static func shortID(of name: String) -> String {
        String(name.split(separator: "/").last ?? Substring(name))
    }

    // MARK: - The harvest

    /// Diagnostics for the join, which is the one step whose failure the row
    /// model cannot express (Finding 123). Category is dotted so
    /// `--predicate 'subsystem == "app.bristlenose"'` still catches it.
    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import.meet")

    /// How many Meet lookups are in flight at once.
    ///
    /// Four, the same bound §9 puts on concurrent downloads — not because the
    /// two are the same problem, but because one number this codebase can
    /// justify beats two it cannot. The constraint here is Google's per-user
    /// quota, which is per-minute and shared across every call this adapter
    /// makes, so unbounded fan-out on a busy calendar would trade a slow list
    /// for a rate-limited one.
    private static let lookupConcurrency = 4

    /// Every call in the window, with what it produced and which room it was in.
    ///
    /// Three phases, each one a fan-out over the phase before it:
    ///
    /// 1. **The calls**, filtered on time alone. One paginated query for the
    ///    whole window, where the old shape made one per calendar event — so
    ///    this is both fewer round trips and the only version that can see a
    ///    call nobody booked.
    /// 2. **What each produced.** A `FILE_GENERATED` recording is the only kind
    ///    with bytes behind it.
    /// 3. **The room**, for the calls that produced something. Deliberately not
    ///    for the rest: a call with no file contributes nothing a code could
    ///    change, so resolving every space would be a round trip per meeting for
    ///    an answer nobody reads.
    private static func harvestConferenceRecords(
        window: DateInterval,
        canReachMeet: Bool,
        accessToken: String,
        session: URLSession
    ) async -> MeetHarvest {
        // Without the scope there is nothing to ask and no failure to report —
        // every row will say `.needsScope`, which is the accurate and actionable
        // thing, and a recorded "failure" here would compete with it.
        guard canReachMeet else { return MeetHarvest() }

        // TRAP: the filter's field names are snake_case while the JSON response
        // is camelCase. `startTime>=…` returns an empty list with HTTP 200 — a
        // silent no-match that looks exactly like a quiet month.
        //
        // Only our own dates are interpolated now. The old filter spliced a
        // remote-controlled meeting code into this string, which made a
        // malformed-filter 400 reachable by data rather than only by bug.
        let filter = "start_time>=\"\(rfc3339(window.start))\""
            + " AND start_time<=\"\(rfc3339(window.end))\""

        var raw: [ConferenceRecordsPage.Record] = []
        var failure: GoogleAPIOutcome?
        var pageToken: String?
        var pages = 0
        // Every page, not the first: a busy month segments, and an unfollowed
        // continuation is a set of recordings that silently do not exist.
        let pageCap = 10

        repeat {
            var components = URLComponents(
                string: "https://meet.googleapis.com/v2/conferenceRecords")!
            var items = [URLQueryItem(name: "filter", value: filter)]
            if let pageToken { items.append(URLQueryItem(name: "pageToken", value: pageToken)) }
            components.queryItems = items
            guard let url = components.url else {
                log.notice("meet_harvest phase=records unbuildable_url")
                failure = .unexpected(status: 0, reason: "unbuildable url")
                break
            }

            var request = URLRequest(url: url)
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

            let data: Data
            let response: URLResponse
            do {
                (data, response) = try await session.data(for: request)
            } catch {
                log.notice("""
                    meet_harvest phase=records \
                    transport_error=\(error.localizedDescription, privacy: .public)
                    """)
                failure = .unexpected(status: 0, reason: "transport")
                break
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let outcome = GoogleResponseClassifier.classify(status: status, body: data)
            let page = try? JSONDecoder().decode(ConferenceRecordsPage.self, from: data)

            log.notice("""
                meet_harvest phase=records status=\(status, privacy: .public) \
                outcome=\(String(describing: outcome), privacy: .public) \
                page=\(pages, privacy: .public) \
                records=\(page?.conferenceRecords?.count ?? -1, privacy: .public)
                """)
            if status != 200, let body = String(data: data, encoding: .utf8), !body.isEmpty {
                log.notice("meet_harvest phase=records body=\(body.prefix(400), privacy: .private)")
            }
            guard outcome == .ok, let page else {
                // **Recorded, not swallowed.** Every row downstream reads this:
                // a failure here means "we could not look", and the one thing
                // the window must never do is render that as "nobody recorded".
                failure = outcome == .ok ? .unexpected(status: status, reason: "undecodable")
                                         : outcome
                break
            }

            raw.append(contentsOf: page.conferenceRecords ?? [])
            pageToken = page.nextPageToken
            pages += 1
            if pageToken != nil && pages >= pageCap {
                log.notice("meet_harvest phase=records page_cap_hit pages=\(pages, privacy: .public)")
                // A prefix passing for a total is exactly the shape `ListOutcome`
                // exists to prevent, one layer down.
                failure = .unexpected(status: 200, reason: "page cap")
                break
            }
        } while pageToken != nil

        // Phase 2 — what each call produced.
        let calls = await mapConcurrently(raw) { record -> HarvestedCall in
            guard let name = record.name, !name.isEmpty else {
                // The count above already said a record was found, so without
                // this the only tell is a missing `phase=recordings` line.
                log.notice("meet_harvest phase=records record_without_name")
                return HarvestedCall(record: record, recordings: [], sawGenerated: false)
            }
            let (found, generated) = await recordings(
                ofRecord: name, accessToken: accessToken, session: session)
            return HarvestedCall(record: record, recordings: found, sawGenerated: generated)
        }

        // Phase 3 — the room, deduplicated. A researcher's personal room holds
        // many of the month's calls and `spaces.get` returns the same code every
        // time.
        var wanted: [String] = []
        var seenSpaces = Set<String>()
        for call in calls where !call.recordings.isEmpty || call.sawGenerated {
            guard let space = call.record.space, !space.isEmpty else { continue }
            if seenSpaces.insert(space).inserted { wanted.append(space) }
        }
        let resolved = await mapConcurrently(wanted) { space in
            ResolvedSpace(
                space: space,
                code: await meetingCode(ofSpace: space, accessToken: accessToken, session: session))
        }
        var codeBySpace: [String: String] = [:]
        for entry in resolved {
            if let code = entry.code, !code.isEmpty { codeBySpace[entry.space] = code }
        }

        let records: [MeetHarvest.Record] = calls.compactMap { call in
            guard let name = call.record.name, !name.isEmpty else { return nil }
            return MeetHarvest.Record(
                name: name,
                meetingCode: call.record.space.flatMap { codeBySpace[$0] },
                start: call.record.startTime.flatMap(parseRFC3339),
                end: call.record.endTime.flatMap(parseRFC3339),
                expires: call.record.expireTime.flatMap(parseRFC3339),
                recordings: call.recordings,
                sawGeneratedRecordings: call.sawGenerated)
        }

        log.notice("""
            meet_harvest complete records=\(records.count, privacy: .public) \
            withFiles=\(records.filter { !$0.recordings.isEmpty }.count, privacy: .public) \
            spacesResolved=\(codeBySpace.count, privacy: .public) \
            ofSpacesAsked=\(wanted.count, privacy: .public) \
            failure=\(failure.map { String(describing: $0) } ?? "none", privacy: .public)
            """)

        return MeetHarvest(records: records, failure: failure)
    }

    /// The room's join code, which is the join key both sides share.
    ///
    /// Returns nil on any failure. A record with no code can never be matched to
    /// a booking — and that is the safe direction now, because an unmatched
    /// record still becomes a row.
    private static func meetingCode(
        ofSpace space: String,
        accessToken: String,
        session: URLSession
    ) async -> String? {
        // `space` is remote-controlled (`spaces/<id>`), so it goes through the
        // failable initialiser rather than a force-unwrap: a third party decides
        // what is in the string, and a crash is worse than a row that carries a
        // code instead of a title.
        guard let url = URL(string: "https://meet.googleapis.com/v2/\(space)") else {
            log.notice("meet_harvest phase=space unbuildable_url")
            return nil
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            log.notice("""
                meet_harvest phase=space \
                transport_error=\(error.localizedDescription, privacy: .public)
                """)
            return nil
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        let outcome = GoogleResponseClassifier.classify(status: status, body: data)
        // Shape, not value. The code is a join key that opens a room, so its
        // length and dash count are enough to catch a format mismatch; the code
        // itself never reaches the system log.
        let code = (try? JSONDecoder().decode(MeetSpace.self, from: data))?.meetingCode
        log.notice("""
            meet_harvest phase=space status=\(status, privacy: .public) \
            outcome=\(String(describing: outcome), privacy: .public) \
            codeLen=\(code?.count ?? -1, privacy: .public) \
            codeDashes=\(code?.filter { $0 == "-" }.count ?? -1, privacy: .public)
            """)
        guard outcome == .ok else { return nil }
        return code
    }

    /// Runs `transform` over `items` with at most `limit` in flight, preserving
    /// input order.
    ///
    /// Refills as each finishes rather than in waves: a wave stalls on its
    /// slowest member while three connections sit idle. Static, and taking the
    /// session and token as parameters at every call site, so no child task
    /// captures `self` — this adapter holds mutable state (`driveFileIDs`,
    /// `identity`) that must not be touched off the calling context.
    private static func mapConcurrently<In: Sendable, Out: Sendable>(
        _ items: [In],
        limit: Int = lookupConcurrency,
        _ transform: @escaping @Sendable (In) async -> Out
    ) async -> [Out] {
        guard !items.isEmpty else { return [] }
        var results: [Int: Out] = [:]
        await withTaskGroup(of: (Int, Out).self) { group in
            var next = 0
            func enqueue() {
                let index = next
                let item = items[index]
                next += 1
                group.addTask { (index, await transform(item)) }
            }
            while next < min(limit, items.count) { enqueue() }
            while let (index, out) = await group.next() {
                results[index] = out
                if next < items.count { enqueue() }
            }
        }
        return (0..<items.count).compactMap { results[$0] }
    }

    /// One conference record's recordings.
    ///
    /// - Returns: the fetchable ones, and whether Google reported any
    ///   `FILE_GENERATED` at all — the second is what tells "nobody recorded
    ///   this" apart from "a recording exists and we could not resolve it".
    private static func recordings(
        ofRecord name: String,
        accessToken: String,
        session: URLSession
    ) async -> ([MeetHarvest.Recording], Bool) {
        // `name` is remote-controlled (`conferenceRecords/<id>`), so it goes
        // through the failable initialiser rather than a force-unwrap: a third
        // party decides what is in the string, and a crash is a worse outcome
        // than a row that can't be fetched.
        guard let recURL = URL(string: "https://meet.googleapis.com/v2/\(name)/recordings") else {
            log.notice("meet_lookup phase=recordings unbuildable_url")
            return ([], false)
        }
        var request = URLRequest(url: recURL)
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            log.notice("meet_lookup phase=recordings transport_error=\(error.localizedDescription, privacy: .public)")
            return ([], false)
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        let outcome = GoogleResponseClassifier.classify(status: status, body: data)
        let page = try? JSONDecoder().decode(RecordingsPage.self, from: data)

        // The states are the point. `STARTED` and `ENDED` mean the recording
        // exists but has no bytes yet, and Google's propagation runs roughly
        // the length of the call — so "found a record, found a recording, still
        // returned nothing" is a *wait*, not a fault, and only this line tells
        // the two apart.
        log.notice("""
            meet_lookup phase=recordings status=\(status, privacy: .public) \
            outcome=\(String(describing: outcome), privacy: .public) \
            count=\(page?.recordings?.count ?? -1, privacy: .public) \
            states=[\((page?.recordings ?? []).compactMap(\.state).joined(separator: ","), privacy: .public)]
            """)
        guard outcome == .ok, let page else { return ([], false) }

        // Only a FILE_GENERATED recording has bytes behind it. STARTED and
        // ENDED both mean "not yet", so offering a row for those would produce
        // a fetch that 404s minutes after the researcher ticks it.
        let generated = (page.recordings ?? []).filter { $0.state == "FILE_GENERATED" }
        let found: [MeetHarvest.Recording] = generated.compactMap { recording in
            guard let fileID = recording.driveDestination?.file else { return nil }
            let began = recording.startTime.flatMap(Self.parseRFC3339)
            let ended = recording.endTime.flatMap(Self.parseRFC3339)
            return MeetHarvest.Recording(
                fileID: fileID,
                startedAt: began,
                duration: (began != nil && ended != nil)
                    ? ended!.timeIntervalSince(began!)
                    : nil
            )
        }

        // Google returns at most ten recordings per page and this call sends no
        // page size, so a call segmented past that loses its tail. Logged rather
        // than followed, because following it honestly needs a way to say
        // "partial" that this return type has no channel for.
        if page.nextPageToken?.isEmpty == false {
            log.notice("meet_lookup phase=recordings truncated")
        }
        return (found, !generated.isEmpty)
    }

    // MARK: Fetching

    /// Whether a batch needs a Picker round trip, and what to ask for.
    ///
    /// Pure, because both decisions in it are wrong in ways that are invisible
    /// at the call site: asking when we needn't puts a browser, an account
    /// chooser and a consent screen in front of a researcher who granted these
    /// files five minutes ago, and asking too narrowly guarantees another round
    /// trip the moment they tick anything else — which, to them, is
    /// indistinguishable from the first one not having worked.
    enum MediaGrantPlan: Equatable {
        /// Every file in the batch is already granted and the token is good.
        case alreadyHeld
        /// Round-trip the Picker for these file ids.
        case ask(fileIDs: [String])

        /// - Parameter batch: the file ids this batch actually needs.
        /// - Parameter listing: every file id in the window, which is what we
        ///   ask for when we ask at all — the grant binds to ids, so the
        ///   cheapest moment to cover a file is while the researcher is already
        ///   looking at a consent screen. They can still deselect in the
        ///   Picker, and `grantedFileIDs` records what came back, never what
        ///   was requested.
        /// - Parameter tokenUsable: caller has already refreshed if it could.
        ///   A held file with a dead token must still re-ask, or `fetch` sails
        ///   past its `grantedFileIDs` guard and 401s — the harder failure to
        ///   read, because it looks like a network fault rather than a
        ///   permission one.
        static func decide(
            batch: [String],
            listing: Set<String>,
            granted: Set<String>,
            tokenUsable: Bool
        ) -> MediaGrantPlan {
            if tokenUsable, batch.allSatisfy(granted.contains) { return .alreadyHeld }
            // Sorted so one listing produces one request, stably, rather than
            // following dictionary order — a live URL stays diffable between
            // runs, and the tests are not asserting a hash ordering.
            return .ask(fileIDs: listing.union(batch).sorted())
        }
    }

    /// Ask for the file grant, in one Picker round trip covering the whole
    /// listing — or in none at all when we already hold everything the batch
    /// needs. Called by the store before the first `fetch`.
    /// Google's batch preparation IS the Picker round trip.
    @MainActor
    func prepareBatch(rowIDs: [String]) async throws {
        try await requestMediaGrant(for: rowIDs)
    }

    @MainActor
    func requestMediaGrant(for rowIDs: [String]) async throws {
        let wanted = rowIDs.compactMap { driveFileIDs[$0] }
        guard !wanted.isEmpty else { return }

        // The token is consulted before the plan because the two expire
        // independently, and only one of them needs the researcher: a missing
        // *file* is theirs to widen, an aged *token* is ours to renew. Doing
        // the renewal first means an expired token never becomes a consent
        // screen.
        let plan = MediaGrantPlan.decide(
            batch: wanted,
            listing: Set(driveFileIDs.values),
            granted: grantedFileIDs,
            tokenUsable: try await refreshedMediaTokenIsUsable())

        guard case .ask(let fileIDs) = plan else { return }

        let client = GoogleOAuthClient(config: config, session: session)
        let (tokens, picked) = try await client.pickMedia(fileIDs: fileIDs)
        mediaToken = tokens
        // Honour what was granted, never what was asked for: the researcher
        // may deselect inside the Picker, and treating the request as the
        // answer would produce a batch that 403s on exactly the rows they
        // chose to remove.
        grantedFileIDs.formUnion(picked)
        // The grant the researcher just sat through a browser for. Not saving
        // it here is what made every window open ask again.
        publishGrant()
    }

    /// Whether the media token is good, refreshing it in place if it has aged
    /// out and we hold the means to.
    ///
    /// Separated from the grant check because the failure modes are opposite:
    /// a missing *file* needs the researcher (only they can widen the grant),
    /// while an expired *token* needs nothing from them at all. Conflating
    /// them is how a silent refresh becomes a consent screen.
    @MainActor
    private func refreshedMediaTokenIsUsable() async throws -> Bool {
        guard let current = mediaToken else { return false }
        guard current.isExpired else { return true }
        guard let refreshToken = current.refreshToken else { return false }
        let client = GoogleOAuthClient(config: config, session: session)
        // A refresh that fails is not an error to surface — it means we fall
        // through to the Picker, which is the remedy anyway.
        guard let renewed = try? await client.refresh(
            refreshToken: refreshToken, knownGrants: GoogleScopes.mediaGrant)
        else { return false }
        mediaToken = renewed
        return true
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
            title: row.title, startsAt: row.startsAt, fileExtension: "mp4",
            // Two halves of one call share a title, and share `startsAt` too
            // whenever Google omits the recording's own start — so without the
            // ordinal they produce the same path and one silently overwrites
            // the other, with both rows reporting success.
            part: row.siblingOrdinal)
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
