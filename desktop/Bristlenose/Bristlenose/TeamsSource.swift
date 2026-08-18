import Foundation
import OSLog

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

        /// **How long the recording runs — and it was here all along.**
        ///
        /// Every Teams row shipped `duration: nil`, and that was written up as
        /// "Graph doesn't serve a duration". It does: the `video` facet is part
        /// of the default driveItem representation, this listing sets no
        /// `$select`, so it has been arriving on the wire and falling on the
        /// floor of a `Decodable` with nowhere to put it. The absence was ours.
        ///
        /// `duration` is **milliseconds**, unlike every other time on this type.
        struct MediaFacet: Decodable { let duration: Int64? }
        /// Present on `.mp4`.
        let video: MediaFacet?
        /// Present on the `.m4a` audio-only variant, same shape.
        let audio: MediaFacet?

        /// Seconds, from whichever facet the file has. Nil only when Graph
        /// genuinely served neither — which is worth telling apart from "we
        /// never asked", the mistake this replaces.
        var mediaDurationSeconds: TimeInterval? {
            guard let ms = video?.duration ?? audio?.duration else { return nil }
            return TimeInterval(ms) / 1000
        }

        enum CodingKeys: String, CodingKey {
            case id, name, size, parentReference, file, expirationDateTime, createdDateTime
            case video, audio
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
    private static let log = Logger(subsystem: "app.bristlenose", category: "cloud-import.teams")

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
    /// - Parameter restoredIdentity: the signed-in address, restored with the
    ///   tokens. Without it `CloudImportStore` opens on `.signedOut` — it reads
    ///   that from `accountEmail` — so a good restored token would sit behind a
    ///   sign-in button and the restore would look like it had failed.
    /// - Parameter onGrantChanged: called whenever the grant materially moves —
    ///   signed in, renewed, or revoked. **Nil means forget it.** One callback
    ///   rather than a `save` for the revoked case: a store only ever told about
    ///   successes keeps a dead grant looking live indefinitely.
    init(config: MicrosoftOAuthConfig,
         session: URLSession? = nil,
         restoredTokens: MicrosoftTokenResponse? = nil,
         restoredIdentity: String? = nil,
         onGrantChanged: (@Sendable (MicrosoftGrant?) -> Void)? = nil) {
        self.config = config
        self.sessionOwner = session.map(CloudSessionOwner.init(adopting:)) ?? CloudSessionOwner()
        self.tokens = restoredTokens
        self.identity = restoredIdentity
        self.onGrantChanged = onGrantChanged
    }

    private let onGrantChanged: (@Sendable (MicrosoftGrant?) -> Void)?

    /// Publish the current grant, or its absence.
    ///
    /// After every move rather than at chosen moments, because the move that
    /// matters is the one nobody remembers to instrument — a silent renewal an
    /// hour in, whose new refresh token is the only one that still works
    /// tomorrow.
    ///
    /// **Never call the store synchronously.** A Keychain write can block on an
    /// authorisation prompt, which on an ad-hoc-signed build is routine rather
    /// than hypothetical — those fall back to the legacy file-based keychain,
    /// which binds grants to the binary hash and re-prompts on every rebuild.
    /// `signIn()` is `@MainActor` and publishes the instant the web auth session
    /// returns, so a blocking write there stalls the main actor behind a dialog
    /// the auth window is covering, and the window spins forever with no error.
    ///
    /// The snapshot is taken here, on the caller's actor, so what gets written
    /// is what was true at the call rather than whatever the adapter has drifted
    /// to by the time the write lands.
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
        let snapshot = tokens.map {
            MicrosoftGrant(tokens: $0, identity: identity, driveType: tier.driveType)
        }
        onGrantChanged?(snapshot)
    }

    /// Persist the drive tier the moment a listing establishes it.
    ///
    /// Settings ▸ Accounts cannot ask — it makes no network calls — so this is
    /// the only path by which the pane ever learns that a personal Microsoft
    /// account has no `/Recordings` folder and never will. Without it that
    /// account reads as plainly *connected* and the researcher finds out in the
    /// import window, one empty list later.
    ///
    /// Called from both places the tier is settled, and guarded on a real
    /// change: the business path gets it free off the listing's own
    /// `parentReference`, the personal path pays for `GET /me/drive` precisely
    /// because the folder was absent. Re-publishing an unchanged tier would
    /// rewrite the Keychain item on every listing for no new fact.
    private func publishTierIfChanged(from previous: DriveTier) {
        guard tier != previous, tokens != nil else { return }
        publishGrant()
    }

    /// Record that the provider ended the session, **keeping the account**.
    ///
    /// This used to publish nil, which deleted the grant — so a revoked session
    /// vanished from Settings ▸ Accounts, indistinguishable from having
    /// disconnected it yourself, and the only evidence was that importing had
    /// quietly stopped working. The tombstone keeps the row and carries no
    /// working credential: `revoked` strips the refresh token and dates the
    /// access token to the distant past, so the unbreakable-retry-loop this
    /// path was guarding against cannot form even if the flag were ignored.
    private func publishRefusal() {
        let snapshot = MicrosoftGrant.revoked(identity: identity)
        onGrantChanged?(snapshot)
    }

    /// Renew the token when it has aged out, or report that we cannot.
    ///
    /// The listing path had no expiry check at all before this, which was
    /// survivable only while the token was minted at sign-in and used minutes
    /// later. Once a sign-in outlives the window — the entire point of restoring
    /// one — an hour-old token is the ordinary case.
    ///
    /// Returns false when the grant is gone for good, **having already told the
    /// store the account needs signing in again**: a revoked refresh token fails
    /// identically forever, so the credential must not survive, but the
    /// *account* does — see `publishRefusal`.
    ///
    /// `@MainActor` because `MicrosoftOAuthClient`'s initialiser is — it can
    /// carry an anchor window. The refresh itself is a plain POST with no UI, so
    /// the hop costs nothing.
    @MainActor
    private func renewedTokenIfNeeded() async -> Bool {
        guard let current = tokens else { return false }
        guard current.isExpired() else { return true }
        guard let refreshToken = current.refreshToken else {
            tokens = nil
            publishRefusal()
            return false
        }
        let client = MicrosoftOAuthClient(config: config, session: session)
        let renewed: MicrosoftTokenResponse
        do {
            renewed = try await client.refresh(refreshToken: refreshToken)
        } catch {
            // **Only an authoritative refusal writes a tombstone.** `try?` here
            // treated a dropped connection exactly like a revoked grant — so a
            // moment of bad wifi stripped the refresh token, permanently, and
            // told the researcher their provider had ended the session. This
            // path runs precisely when a token has aged out, which is the
            // ordinary morning-after case the whole restore feature exists for.
            //
            // A 4xx from the token endpoint is Microsoft saying no. Anything
            // else — a `URLError`, a 5xx — leaves the grant untouched so the
            // next attempt can succeed.
            if case MicrosoftOAuthError.tokenExchangeFailed(let status, _) = error,
               (400...499).contains(status) {
                tokens = nil
                publishRefusal()
            } else {
                Self.log.notice("teams refresh failed without a verdict — keeping the grant")
            }
            return false
        }
        // Carry the refresh token forward when the response omitted it — see
        // `carryingForwardRefreshToken`. Storing the response verbatim is how a
        // renewed session dies an hour later instead of immediately.
        tokens = renewed.carryingForwardRefreshToken(from: current)
        publishGrant()
        return true
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
        // `?? identity` is load-bearing. The address is what derives the
        // Keychain account key, so letting a transient `/me` failure nil a
        // known-good one re-derives `unidentified` — and `saveTeams` then
        // deletes the correctly-keyed item as a stale rekey. A cosmetic lookup
        // must not be able to destroy a credential.
        identity = (try? await fetchIdentity()) ?? identity
        publishGrant()
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

    /// The drive's own `driveType`, which is what decides whether this account
    /// can hold Teams recordings at all.
    ///
    /// Returns nil when the call fails — deliberately not `.unknown`, because
    /// the caller needs to tell "the drive says something I don't recognise"
    /// from "I could not read the drive", and only the second casts doubt on
    /// whether we hold `Files.Read`.
    private func fetchDriveTier() async -> DriveTier? {
        struct Drive: Decodable { let driveType: String? }
        guard let data = try? await get(
                  "https://graph.microsoft.com/v1.0/me/drive?$select=driveType"),
              let drive = try? JSONDecoder().decode(Drive.self, from: data)
        else { return nil }
        return DriveTier(driveType: drive.driveType)
    }

    // MARK: Listing

    func list(window: DateInterval) async -> MeetingListing {
        // Renew before reading, not after failing. On the restore path an
        // hour-old token is the ordinary case, so 401-ing into a sign-in nobody
        // needed would be the common experience rather than the rare one.
        guard await renewedTokenIfNeeded(), tokens != nil else {
            return empty(window, outcome: .failed(after: 0,
                                                  outcome: .needsReauthentication(reason: "no token")))
        }

        var items: [GraphChildren.Item] = []
        // **`special/recordings`, never the `/Recordings:` path.** Graph
        // documents this alias as existing precisely to avoid a path lookup
        // "which would require localization" — so the hardcoded English path
        // was a bug for every non-English tenant, and one that surfaced as an
        // empty list misdiagnosed as the wrong account tier. The alias also
        // survives the user renaming or moving the folder, and it costs no new
        // scope: `Files.Read` is its least-privileged delegated permission.
        var next: String? = "https://graph.microsoft.com/v1.0/me/drive/special/recordings/children"
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
                // **A missing Recordings folder answers 403 OR 404, and neither
                // means what its status line says.** Graph documents both for a
                // read-only app requesting a special folder that does not exist
                // — so the classifier's `403 → scopeNotGranted` would send a
                // researcher who simply has not recorded yet to re-consent a
                // permission they already hold.
                //
                // Disambiguate by reading the drive, and only here: if
                // `/me/drive` answers, we demonstrably hold `Files.Read`, so the
                // refusal is about the folder rather than the grant, and the
                // tier it returns carries the explanation — a personal account
                // never creates the folder at all, because the recording is
                // attached to the meeting chat instead. If the drive is
                // unreadable too, the grant really is in doubt and the original
                // outcome stands.
                //
                // **Lazily, never eagerly.** Reading the tier up-front would put
                // a second request on every successful listing, and the happy
                // path is the one that must stay cheap.
                //
                // Only on the FIRST page. A 404 partway through a walk is an
                // expired `@odata.nextLink`, not a missing folder — returning
                // `empty(.exhausted)` there discarded every row already
                // collected and told a researcher with hundreds of recordings
                // that they had none, with `isExact` true.
                let folderAbsent = error.outcome == .notFound || error.outcome == .scopeNotGranted
                if folderAbsent, pagesFetched == 0, let readTier = await fetchDriveTier() {
                    let before = tier
                    tier = readTier
                    // The one path that *pays* for the tier, and the one whose
                    // answer Settings ▸ Accounts most needs: no `/Recordings`
                    // folder means a personal account, which will never have
                    // one. Written to the grant here or the pane can never say
                    // so — it makes no calls of its own.
                    publishTierIfChanged(from: before)
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
            let before = tier
            tier = DriveTier(driveType: driveType)
            // Free — the listing already carried it. Published so a business
            // account is positively *known* to be fine rather than merely
            // un-flagged, which is what stops the pane guessing from silence.
            publishTierIfChanged(from: before)
        }

        // The roster is a separate, optional read. A researcher who declined
        // the calendar scope still gets a usable list — the title and date come
        // free from the filename, which is why §6 could move title filtering
        // out of the calendar's reach entirely.
        let events = await calendarEvents(window: window)

        // Backfill the address if sign-in never got it — mirroring Google's,
        // which Teams was missing entirely. Without it a grant whose `/me`
        // failed once stays under the anonymous key **permanently**: nameless
        // in Settings ▸ Accounts, and occupying the one slot every other
        // unnamed sign-in shares. `publishGrant` is the half that moves it —
        // see `saveTeams(previousKey:)`.
        //
        // **After the two reads, not before**, for two reasons. It is
        // bookkeeping, and nobody should wait on it for their recordings. And
        // the transport tests pin the listing's request sequence — a `/me` call
        // at the front makes `requests.first` the wrong URL, which is the tests
        // doing their job. It still lands before `organisedByOthers` reads it
        // below, which is the only thing in this method that needs it.
        // Not after a failed listing: on an unlicensed or unauthorised account
        // every Graph call fails identically, and a third doomed request buys
        // nothing while making a network trace look like the retry loop the
        // classifier exists to prevent.
        var listingFailed = false
        if case .failed = outcome { listingFailed = true }
        if identity == nil, !listingFailed, let restored = try? await fetchIdentity() {
            identity = restored
            publishGrant()
        }

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

        // The meeting's own clock, which this adapter has always had in hand
        // and never passed on. Graph gives `start` and `end` on the matched
        // event, so the Scheduled column costs nothing extra — and it is the
        // column that makes Teams' real gap legible rather than baffling: the
        // meeting was booked for an hour, the recording began at 09:34, and
        // how long it ran is genuinely unknown because Graph does not say.
        let scheduledAt = matched?.start?.dateTime.flatMap(Self.parseISO)
        let scheduledEnd = matched?.end?.dateTime.flatMap(Self.parseISO)

        return CloudImportRow(
            id: id,
            title: matched?.subject ?? parsed.title,
            startsAt: startedAt,
            // The recording's own length, from the driveItem's media facet —
            // never the meeting's booked length, which is the number that told
            // a 20-second Google file it was 1h 30m.
            duration: item.mediaDurationSeconds,
            sizeBytes: item.size,
            expiresAt: item.expirationDateTime.flatMap(Self.parseISO),
            attendees: attendees,
            localState: .notImported,
            video: item.downloadURL == nil ? .unsupported : .available,
            roster: attendees.isEmpty ? .needsScope(MicrosoftScopes.calendarsRead) : .available,
            // Admin-consent-only, even delegated. Not requested, so never
            // available — stated rather than silently missing.
            transcript: .needsScope("OnlineMeetingTranscript.Read.All"),
            organiser: nil,
            scheduledAt: scheduledAt,
            scheduledDuration: scheduledEnd.flatMap { end in
                scheduledAt.map { end.timeIntervalSince($0) }
            },
            // `createdDateTime` is when the recording landed, which is the
            // closest thing Graph has to a record-button moment.
            recordedAt: startedAt,
            // **Always nil. Teams is flat, and the settled design says so.**
            //
            // The tempting line here is `matched?.id`, so two files that hit
            // the same event nest as two recordings of one call. It was written
            // that way and is wrong, because `matchEvent` is a ±30-minute
            // proximity guess with no identity check — and it is matched
            // against `createdDateTime`, which is when the recording *landed*,
            // near the meeting's end. A 50-minute session booked at 10:00
            // produces a file stamped ~10:52, which is outside its own event's
            // window and inside the next slot's.
            //
            // Grouping on that guess is worse than a wrong title, because of
            // what the outline does with it: a child row draws only "Recording
            // 2" and its clock, dropping the filename-derived title that is the
            // one thing distinguishing two Teams files. So two unrelated
            // interviews would render as one call's two halves, with the
            // evidence of the mistake removed by the nesting that made it.
            //
            // The event is still trusted for the roster and the Scheduled
            // column — both visible and checkable — just not for a claim about
            // session identity.
            meetingID: nil
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
        // Renew here too, and for a sharper reason than the listing: a batch of
        // multi-gigabyte recordings can easily outlive an hour-long token, so
        // the tail of a long import is exactly where an unrenewed grant fails —
        // after the researcher has stopped watching, on the files they waited
        // longest for. The transfer itself needs no token (the URL carries its
        // own), but re-resolving that URL does.
        _ = await renewedTokenIfNeeded()

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
            title: row.title, startsAt: row.startsAt, fileExtension: "mp4",
            part: row.siblingOrdinal)
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
