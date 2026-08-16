import Foundation
import Testing

@testable import Bristlenose

// Tests for the decisions, not the mechanisms.
//
// Each of these pins a case where the *plausible* implementation is wrong and
// wrong silently — a 403 read as one thing when it is three, a scope set that
// Google refuses, a batch that fetches in the wrong order and loses exactly the
// files nearest deletion. None of them can be caught by running the app once
// against a healthy account, which is the point.

// MARK: - Response classification

@Suite("Google response classification")
struct GoogleResponseClassifierTests {

    /// Google's error envelopes, in the two shapes the adapter meets: the older
    /// Google-API JSON error used by Calendar and Drive, and the
    /// gRPC-transcoded shape used by the Meet REST API. Reading only one is how
    /// a real refusal becomes `.unexpected` and gets no retry policy at all.
    private enum Fixture {
        static let scopeInsufficient = Data("""
        {"error":{"code":403,"message":"Request had insufficient authentication scopes.",
        "errors":[{"message":"Insufficient Permission","domain":"global","reason":"insufficientPermissions"}],
        "status":"PERMISSION_DENIED"}}
        """.utf8)

        /// NB the message is on ONE line. A line break inside a JSON *string
        /// value* is invalid JSON — the other fixtures here break after commas,
        /// which is fine, but wrapping this one for readability made
        /// `JSONDecoder` fail silently, the message read as empty, and the
        /// classifier fall through to its default branch. The test caught it;
        /// the malformed fixture would otherwise have "passed" any assertion
        /// loose enough to accept the fallback.
        static let scopeNamedInMessage = Data(
            #"{"error":{"code":403,"message":"Request is missing required authentication scope https://www.googleapis.com/auth/meetings.space.readonly for this request.","errors":[{"reason":"ACCESS_TOKEN_SCOPE_INSUFFICIENT"}],"status":"PERMISSION_DENIED"}}"#.utf8
        )

        /// Quota exhaustion arriving as 403 rather than 429 — Google does this
        /// on several APIs.
        static let quotaAs403 = Data("""
        {"error":{"code":403,"message":"Rate Limit Exceeded",
        "errors":[{"domain":"usageLimits","reason":"rateLimitExceeded","message":"Rate Limit Exceeded"}]}}
        """.utf8)

        static let editionRefusal = Data("""
        {"error":{"code":403,"message":"This feature requires a Google Workspace edition that supports recording.",
        "status":"PERMISSION_DENIED"}}
        """.utf8)

        static let notOrganiser = Data("""
        {"error":{"code":403,"message":"The caller does not have permission to access this conference record.",
        "status":"PERMISSION_DENIED"}}
        """.utf8)

        static let expiredToken = Data("""
        {"error":{"code":401,"message":"Request had invalid authentication credentials.",
        "status":"UNAUTHENTICATED"}}
        """.utf8)
    }

    @Test("403 splits three ways, and each way has a different remedy")
    func threeWay403() {
        let scope = GoogleResponseClassifier.classify(status: 403, body: Fixture.scopeInsufficient)
        let plan = GoogleResponseClassifier.classify(status: 403, body: Fixture.editionRefusal)
        let resource = GoogleResponseClassifier.classify(status: 403, body: Fixture.notOrganiser)

        // The distinction the type exists for. All three are HTTP 403; only one
        // is fixed by asking for consent again, and telling a researcher to
        // re-consent when their plan can't record wastes their afternoon.
        #expect(scope == .scopeNotGranted(scope: nil))
        #expect(scope.retryPolicy == .afterConsent)

        if case .notAvailableOnThisPlan = plan {} else {
            Issue.record("edition refusal misread as \(plan)")
        }
        #expect(plan.retryPolicy == .never)

        if case .notPermittedForThisResource = resource {} else {
            Issue.record("organiser wall misread as \(resource)")
        }
        #expect(resource.retryPolicy == .never)
    }

    @Test("A quota 403 is a rate limit, not a permission problem")
    func quotaIsNotPermission() {
        let outcome = GoogleResponseClassifier.classify(status: 403, body: Fixture.quotaAs403)
        // Reading this as a permission failure sends the researcher to their IT
        // department over something that clears by itself in a minute.
        #expect(outcome == .rateLimited(retryAfter: nil))
        #expect(outcome.retryPolicy == .backoff(after: nil))
    }

    @Test("The missing scope is lifted out of the message so the UI can name it")
    func scopeHintExtracted() {
        let outcome = GoogleResponseClassifier.classify(status: 403, body: Fixture.scopeNamedInMessage)
        #expect(outcome == .scopeNotGranted(
            scope: "https://www.googleapis.com/auth/meetings.space.readonly"))
    }

    @Test("A message with no scope in it yields nil rather than a guess")
    func scopeHintDoesNotInvent() {
        // A wrong scope name in a consent prompt is worse than no scope name.
        #expect(GoogleResponseClassifier.scopeHint(in: "Insufficient Permission") == nil)
    }

    @Test("401 is reauthentication — Google does not overload it the way Graph does")
    func unauthenticated() {
        let outcome = GoogleResponseClassifier.classify(status: 401, body: Fixture.expiredToken)
        #expect(outcome.retryPolicy == .onceAfterReauthentication)
    }

    @Test("An unclassifiable response fails closed, never into a retry loop")
    func unknownFailsClosed() {
        let outcome = GoogleResponseClassifier.classify(status: 418, body: nil)
        #expect(outcome.retryPolicy == .never)
    }
}

// MARK: - Account tier

@Suite("Google account tier")
struct GoogleAccountTierTests {

    @Test("A consumer account can hold a calendar but never a recording")
    func personalCannotRecord() {
        // The trap this type exists for: unlike Teams — where a personal
        // account has no /Recordings folder and fails early — a personal Google
        // account returns a full, convincing calendar and then cannot produce a
        // single fetchable row.
        let personal = GoogleAccountTier(email: "someone@gmail.com")
        #expect(personal == .personal)
        #expect(personal.canHoldMeetRecordings == false)
        #expect(personal.organisationDomain == nil)
    }

    @Test("googlemail.com is gmail")
    func historicalAlias() {
        #expect(GoogleAccountTier(email: "someone@googlemail.com") == .personal)
    }

    @Test("A Workspace domain supplies the externality yardstick")
    func workspaceDomain() {
        let tier = GoogleAccountTier(email: "martin@stmarystrust.example")
        #expect(tier.canHoldMeetRecordings)
        #expect(tier.organisationDomain == "stmarystrust.example")
    }

    @Test("A malformed address is unknown, not personal")
    func malformed() {
        // Defaulting to .personal would tell a Workspace user their plan can't
        // record, on the strength of a parse failure.
        #expect(GoogleAccountTier(email: "no-at-sign") == .unknown)
        #expect(GoogleAccountTier(email: nil) == .unknown)
    }
}

// MARK: - The attendee line

@Suite("Attendee line degradation")
struct AttendeeLineTests {

    private func attendee(
        _ name: String?,
        _ email: String,
        isSelf: Bool = false,
        declined: Bool = false,
        external: Bool = false
    ) -> CloudImportRow.Attendee {
        CloudImportRow.Attendee(
            displayName: name, email: email,
            isSelf: isSelf, didDecline: declined, isExternal: external
        )
    }

    @Test("You are dropped — you are in every row and say nothing")
    func dropsSelf() {
        let (names, _) = AttendeeLine.compose([
            attendee("Martin Storey", "martin@x.example", isSelf: true),
            attendee("Sarah Chen", "s.chen@y.example", external: true),
        ])
        #expect(names == ["Sarah Chen"])
    }

    @Test("A decliner is dropped — strong evidence they are not in the recording")
    func dropsDecliners() {
        let (names, overflow) = AttendeeLine.compose([
            attendee("Sarah Chen", "s.chen@y.example", external: true),
            attendee("K. Lindqvist", "k@x.example", declined: true),
        ])
        #expect(names == ["Sarah Chen"])
        // And they must not be counted in the overflow either — "+1" implying a
        // person who declined is a small lie in a line whose whole job is
        // identifying who was there.
        #expect(overflow == 0)
    }

    @Test("The external participant survives truncation; colleagues are shed")
    func externalityOrdering() {
        let (names, overflow) = AttendeeLine.compose([
            attendee("Colleague One", "c1@x.example", external: false),
            attendee("Colleague Two", "c2@x.example", external: false),
            attendee("Sarah Chen", "s.chen@participant.example", external: true),
        ], limit: 1)
        // The line is for identifying *which call this is*, which means the
        // participant — never the moderator, rarely the observers.
        #expect(names == ["Sarah Chen"])
        #expect(overflow == 2)
    }

    /// Pins the default as a decision rather than a magic number. Three is a
    /// claim about the shape of a research session — researcher (dropped as
    /// self), one or two participants, at most one observer — not about pixels.
    /// Two was the original and put a "+1" badge on a routine three-person
    /// interview in a window 760pt wide at its narrowest.
    @Test("The default limit fits a research session, not a phone")
    func defaultLimitFitsASession() {
        let (names, overflow) = AttendeeLine.compose([
            attendee("Martin Storey", "martin@x.example", isSelf: true),
            attendee("Sarah Chen", "s.chen@y.example", external: true),
            attendee("Priya Raman", "p.raman@y.example", external: true),
            attendee("Dana Okonkwo", "d.okonkwo@x.example"),
            attendee("Tomas Lind", "t.lind@x.example"),
        ])
        #expect(names.count == 3)
        #expect(overflow == 1)
    }

    @Test("Overflow is a count, not an ellipsis")
    func countNotEllipsis() {
        let people = (1...6).map { attendee("Person \($0)", "p\($0)@y.example", external: true) }
        let (names, overflow) = AttendeeLine.compose(people, limit: 2)
        // "+4" says there are six. A trailing "…" says nothing.
        #expect(names.count == 2)
        #expect(overflow == 4)
    }

    @Test("An attendee with no display name falls back to the local part")
    func noDisplayName() {
        // The case that matters most: Google returns bare addresses for people
        // outside the organiser's directory, and discards displayName for
        // @gmail.com attendees outright — so the participant the researcher
        // actually interviewed is the one most likely to arrive nameless.
        let (names, _) = AttendeeLine.compose([
            attendee(nil, "j.whitfield@gmail.com", external: true)
        ])
        #expect(names == ["j.whitfield"])
    }
}

// MARK: - Scopes

@Suite("Google scope sets")
struct GoogleScopeTests {

    @Test("drive.file is NOT in the listing grant — Google refuses the combination")
    func driveFileIsSeparate() {
        // Not a style preference. The desktop Picker's own documentation:
        // "only the drive.file scope is permitted for these apps and it can't
        // be combined with any other scope." Putting it in `requested` produces
        // an authorization request Google rejects — at the consent screen, in
        // front of the user, on a path no unit test would otherwise reach.
        #expect(!GoogleScopes.requested.contains(GoogleScopes.driveFile))
        #expect(GoogleScopes.mediaGrant == [GoogleScopes.driveFile])
    }

    @Test("No restricted scope is ever requested")
    func noRestrictedScopes() {
        // The whole affordability argument. `drive.meet.readonly` is Restricted
        // — annual paid third-party assessment — and is declared only so the
        // name has its price attached.
        #expect(!GoogleScopes.requested.contains(GoogleScopes.driveMeetReadonly))
        #expect(!GoogleScopes.mediaGrant.contains(GoogleScopes.driveMeetReadonly))
    }

    @Test("The Meet scope is readonly, never created")
    func meetReadonlyNotCreated() {
        // `meetings.space.created` scopes to spaces THIS APP created, so an
        // import tool gets an empty list and no error. The names invite the
        // wrong choice.
        #expect(GoogleScopes.meetReadonly.hasSuffix("meetings.space.readonly"))
        #expect(GoogleScopes.requested.allSatisfy { !$0.hasSuffix("meetings.space.created") })
    }
}

// MARK: - OAuth configuration

@Suite("Google OAuth configuration")
struct GoogleOAuthConfigTests {

    @Test("The redirect is the reversed client ID with a SINGLE slash")
    func redirectDerivation() {
        let config = GoogleOAuthConfig(
            clientID: "123456-abcdef.apps.googleusercontent.com")
        #expect(config.callbackScheme == "com.googleusercontent.apps.123456-abcdef")
        // Google: "the path should begin with a single slash, which is
        // different from regular HTTP URLs." The instinct is to write "://",
        // and it fails at the redirect rather than at the request — so the
        // error surfaces as redirect_uri_mismatch, which reads like a console
        // misconfiguration rather than a typo.
        #expect(config.redirectURI == "com.googleusercontent.apps.123456-abcdef:/oauth2redirect")
        #expect(!config.redirectURI.contains("://"))
    }

    @Test("A client ID without the suffix still derives a usable scheme")
    func toleratesBareClientID() {
        let config = GoogleOAuthConfig(clientID: "123456-abcdef")
        #expect(config.callbackScheme == "com.googleusercontent.apps.123456-abcdef")
    }
}

// MARK: - PKCE

@Suite("PKCE")
struct PKCEPairTests {

    @Test("The challenge is the unpadded base64url SHA-256 of the verifier")
    func knownAnswer() {
        // RFC 7636 Appendix B's worked example. A known-answer test, because
        // every part of this is unobservable at runtime: a subtly wrong
        // challenge surfaces as invalid_grant at the token exchange, several
        // steps from the cause.
        let pair = PKCEPair(verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        #expect(pair.challenge == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
        #expect(pair.method == "S256")
    }

    @Test("A generated verifier meets the length and alphabet rules")
    func generatedVerifierIsValid() {
        let verifier = PKCEPair.randomVerifier()
        #expect(verifier.count >= 43 && verifier.count <= 128)
        // Unreserved characters only — no padding, no + or /.
        let allowed = CharacterSet(charactersIn:
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
        #expect(verifier.unicodeScalars.allSatisfy { allowed.contains($0) })
    }

    @Test("Two verifiers differ")
    func verifiersAreRandom() {
        #expect(PKCEPair.randomVerifier() != PKCEPair.randomVerifier())
    }
}

// MARK: - The join's arithmetic

@Suite("Join arithmetic")
struct JoinArithmeticTests {

    @Test("Unmatched is the remainder, and never negative")
    func unmatched() {
        let a = JoinArithmetic(eventsInWindow: 11, fetchable: 6,
                               organisedByOthers: 2, outcome: .exhausted)
        #expect(a.unmatched == 3)
        #expect(a.isExact)
    }

    @Test("A capped paginator makes every count a floor, not a total")
    func cappedIsNotExact() {
        // The failure this exists to make visible: an unfollowed page token
        // returns HTTP 200 with a partial page, every error check says fine,
        // and the researcher reads the short list as "it didn't record" while
        // the clock runs.
        let a = JoinArithmetic(eventsInWindow: 14, fetchable: 5,
                               organisedByOthers: 0, outcome: .pageCapHit(pagesFetched: 5))
        #expect(!a.isExact)
        #expect(!a.outcome.isComplete)
    }

    @Test("A nonsense join clamps rather than rendering a negative sentence")
    func clamps() {
        let a = JoinArithmetic(eventsInWindow: 2, fetchable: 5,
                               organisedByOthers: 1, outcome: .exhausted)
        #expect(a.unmatched == 0)
    }
}

// MARK: - Row selectability

@Suite("Import row selectability")
struct CloudImportRowTests {

    private func row(
        local: ImportRowState,
        video: ArtifactAvailability = .available
    ) -> CloudImportRow {
        CloudImportRow(
            id: "r", title: "t", startsAt: Date(), duration: nil, sizeBytes: nil,
            expiresAt: nil, attendees: [], localState: local,
            video: video, roster: .available, transcript: .available, organiser: nil
        )
    }

    @Test("A file we already hold is not re-fetchable, however it is stored")
    func heldRowsAreNotSelectable() {
        // The expensive confusion: if a cloud placeholder shows as fetchable,
        // the researcher re-pulls gigabytes from Google for a file they already
        // own — spending a remote fetch on a purely local problem.
        #expect(!row(local: .imported).isSelectable)
        #expect(!row(local: .notDownloaded(provider: "Dropbox")).isSelectable)
        #expect(!row(local: .driveNotConnected(volume: "T7")).isSelectable)
        // …but each still draws a tick, so the row reads as held rather than
        // as absent.
        #expect(row(local: .notDownloaded(provider: "Dropbox")).showsCheckbox)
    }

    @Test("A wrong-sized file IS re-fetchable — same past fact, opposite remedy")
    func damagedIsSelectable() {
        #expect(row(local: .damaged).isSelectable)
    }

    @Test("A row with no obtainable video offers no checkbox at all")
    func unavailableOffersNoTick() {
        // Offering a tick that cannot be honoured is a lie, and it defers the
        // failure to fetch time — twenty ticked rows returning 403 after the
        // researcher walked away.
        let notMine = row(local: .notImported, video: .notOrganiser(organiser: "A. Bianchi"))
        #expect(!notMine.showsCheckbox)
        #expect(!notMine.isSelectable)
        #expect(notMine.statusLabel == "A. Bianchi")
    }

    /// The two refusals that look identical at row level and are not the same
    /// fact — and this test used to prove they were conflated without anyone
    /// reading it that way. Its name said *the plan can't record*; its one
    /// assertion checked for **"Not recorded"**. The name and the assertion
    /// disagreed, which was the bug (Finding 117) sitting in plain sight.
    ///
    /// The consequence is invisible at row level and severe in the blanket
    /// state: a Workspace researcher whose month happened to contain no
    /// recordings was told their *account* could not record, and sent to argue
    /// with an admin about an edition they already had.
    @Test("Not-recorded and can't-record are different sentences")
    func refusalsAreDistinguished() {
        // Nobody pressed record. An ordinary month, not a fault.
        #expect(row(local: .notImported, video: .notRecorded).statusLabel == "Not recorded")
        // A personal account, which cannot record a Meet call at all — so the
        // recording status of any given meeting is not merely absent, it is
        // unknowable. Saying "not recorded" here would imply it could have been.
        #expect(row(local: .notImported, video: .notOnThisPlan).statusLabel == "Needs a paid plan")
        // Both are equally unfetchable, which is why the labels are the only
        // thing carrying the difference.
        #expect(!row(local: .notImported, video: .notRecorded).showsCheckbox)
        #expect(!row(local: .notImported, video: .notOnThisPlan).showsCheckbox)
    }
}

// MARK: - Fetch ordering

@MainActor
@Suite("Fetch ordering and batch state")
struct CloudImportStoreTests {

    private func store(_ scenario: CloudImportScenario) async -> CloudImportStore {
        let store = CloudImportStore(source: FixtureCloudSource(scenario: scenario))
        await store.load()
        return store
    }

    @Test("Display order is newest-first; fetch order is oldest-first")
    func fetchOrderIsNotDisplayOrder() async {
        let store = await self.store(.populated)
        store.selectAllVisible()

        let displayed = store.visibleRows.map(\.id)
        let fetched = store.fetchOrder.map(\.id)

        // The researcher opened this to find last week, so the list leads with
        // the most recent. But an interrupted batch must not lose exactly the
        // recordings nearest deletion, so execution runs the other way. These
        // two orders disagreeing is the correct state, not a bug.
        #expect(displayed.first != fetched.first)
        #expect(Set(displayed) == Set(fetched.map { $0 }).union(
            displayed.filter { id in !fetched.contains(id) }))

        let dates = store.fetchOrder.map(\.startsAt)
        #expect(dates == dates.sorted())
    }

    @Test("Select All takes the filtered set, never the whole window")
    func selectAllRespectsFilter() async {
        let store = await self.store(.populated)
        store.filterText = "Interview"
        store.selectAllVisible()

        // The list is *recordings you organised* — research calls mixed with
        // workshops and readouts — so ticking the window is close to always
        // wrong. Post-filter it is coherent.
        #expect(store.tickedCount > 0)
        #expect(store.ticked.allSatisfy { id in
            store.visibleRows.contains { $0.id == id }
        })
        let unfiltered = store.listing?.rows.count ?? 0
        #expect(store.tickedCount < unfiltered)
    }

    @Test("A held row cannot be ticked, even by Select All")
    func selectAllSkipsHeldRows() async {
        let store = await self.store(.allAlreadyImported)
        store.selectAllVisible()
        // Only the damaged row is genuinely re-fetchable.
        #expect(store.tickedCount == 1)
    }

    @Test("A personal account surfaces one sentence, not eleven dead rows")
    func blanketRefusal() async {
        let store = await self.store(.personalAccountNoRecordings)
        // Every row unfetchable for the same reason is a property of the
        // account, and saying it once at the top is the difference between an
        // explanation and a wall of failures.
        #expect(store.blanketRefusal == .notOnThisPlan)
        #expect(store.tickedCount == 0)
    }

    @Test("A mixed list gets no blanket message")
    func noBlanketWhenMixed() async {
        let store = await self.store(.populated)
        #expect(store.blanketRefusal == nil)
    }

    @Test("The terminus survives the batch and counts both halves")
    func terminusCounts() async {
        let store = await self.store(.partialFailure)
        store.selectAllVisible()
        let requested = store.tickedCount
        store.startFetch(destination: URL(fileURLWithPath: NSTemporaryDirectory()))

        // Wait for the batch rather than sleeping a fixed interval.
        for _ in 0..<200 where store.isFetching {
            try? await Task.sleep(for: .milliseconds(50))
        }

        let terminus = try? #require(store.terminus)
        #expect(terminus?.requested == requested)
        // Two named rows fail mid-transfer in this scenario. Partial failure is
        // not only a list problem: stages 10 and 11 cluster ACROSS sessions, so
        // analysing 19 of 20 gives different themes, not "the report minus one".
        #expect((terminus?.failed ?? 0) == 2)
        #expect((terminus?.imported ?? 0) == requested - 2)
    }

    @Test("A failed row stays ticked so Retry has something to act on")
    func failedRowsStayTicked() async {
        let store = await self.store(.partialFailure)
        store.selectAllVisible()
        store.startFetch(destination: URL(fileURLWithPath: NSTemporaryDirectory()))
        for _ in 0..<200 where store.isFetching {
            try? await Task.sleep(for: .milliseconds(50))
        }
        #expect(store.tickedCount == 2)
    }
}
