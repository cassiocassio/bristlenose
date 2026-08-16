import Foundation
import Testing

@testable import Bristlenose

// Fixtures are REAL responses recorded against live Microsoft Graph on
// 14–15 Aug 2026, not invented shapes. That is the point of them: the two 401s
// below look identical to any code that reads only the status line, and the
// bug they exist to prevent — an adapter re-authenticating forever against an
// account that can never work — is invisible when it happens.
//
// One redaction: the real `@microsoft.graph.downloadUrl` carried a live
// `tempauth=` bearer token in its query string. It is replaced here with a
// placeholder of the same shape. Never commit the real one; that finding is
// itself why the design forbids logging these URLs.

private enum Fixture {
    /// GET /v1.0/me — before sign-in completed.
    static let unauthenticatedEmptyToken = Data("""
    {"error":{"code":"InvalidAuthenticationToken","message":"Access token is empty.",
    "innerError":{"date":"2026-08-14T23:11:44","request-id":"8a587c2e-915f-4ee5-9125-64b8a9b80944"}}}
    """.utf8)

    /// GET /v1.0/me/drive/root/children — signed out, drive-specific phrasing.
    static let unauthenticatedDriveSyntax = Data("""
    {"error":{"code":"unauthenticated","message":"Must be authenticated to use '/drive' syntax",
    "innerError":{"date":"2026-08-14T23:13:39","request-id":"55e02037-9b4a-40fc-8036-b75eafa328a7"}}}
    """.utf8)

    /// GET /v1.0/me/chats — signed in, consented, but the account holds no
    /// Microsoft 365 licence. Same 401 as the two above; opposite remedy.
    static let unlicensed = Data("""
    {"error":{"code":"Unauthorized","message":"Invoked API requires a valid license. No valid license found.",
    "innerError":{"date":"2026-08-14T23:34:45","request-id":"58105fb4-ace9-4c38-a5a8-5806cbbe588d"}}}
    """.utf8)

    /// GET /v1.0/me/drive/root:/Recordings:/children — personal account, so the
    /// folder does not exist. Also the shape returned by /me/calendarView on an
    /// account with no mailbox.
    static let itemNotFound = Data("""
    {"error":{"code":"itemNotFound","message":"The resource could not be found.",
    "innerError":{"date":"2026-08-14T23:19:12","request-id":"9d1b9ee8-5bca-4c17-9f19-464e3355921d"}}}
    """.utf8)

    /// GET /v1.0/me/drive/root/children — 200. Trimmed to the fields that carry
    /// design weight: driveType, size, and the hashes that let integrity
    /// verification be exact rather than heuristic.
    static let driveListing = Data("""
    {"value":[{
      "@microsoft.graph.downloadUrl":"https://my.microsoftpersonalcontent.com/personal/x/_layouts/15/download.aspx?UniqueId=x&tempauth=REDACTED_IN_FIXTURE&ApiVersion=2.0",
      "name":"Sdfasdf asdf as.docx","size":10605,
      "parentReference":{"driveType":"personal","driveId":"D04AB4540A4FF324"},
      "file":{"mimeType":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "hashes":{"quickXorHash":"mUHi/V4paZKvlmKMyRYElMCT8oU=",
          "sha1Hash":"F1462B1C07869B2E8874463B900F5ABF51F762A5",
          "sha256Hash":"5799201B988EB4577E0F1C3FEC94B8B34F0AA3DF68039C5BB9B60941557ED7A4"}}
    }]}
    """.utf8)
}

@Suite("Graph response classification")
struct TeamsResponseClassifierTests {

    // MARK: The distinction the type exists for

    @Test("Two 401s with the same status classify differently")
    func twoDistinct401s() {
        let expired = TeamsResponseClassifier.classify(
            status: 401, body: Fixture.unauthenticatedEmptyToken)
        let unlicensed = TeamsResponseClassifier.classify(
            status: 401, body: Fixture.unlicensed)

        #expect(expired == .needsReauthentication(code: "InvalidAuthenticationToken"))
        #expect(unlicensed == .accountNotLicensed)
        #expect(expired != unlicensed)
    }

    /// The regression this whole file is for. If an unlicensed account is ever
    /// classified as retryable, the adapter re-authenticates in a loop while the
    /// researcher watches a spinner that will never resolve.
    @Test("An unlicensed account is never retryable")
    func unlicensedNeverRetries() {
        let outcome = TeamsResponseClassifier.classify(status: 401, body: Fixture.unlicensed)
        #expect(outcome.retryPolicy == .never)
        #expect(outcome.isUserActionable)
    }

    @Test("An expired token retries exactly once, after re-authenticating")
    func expiredTokenRetriesOnce() {
        let outcome = TeamsResponseClassifier.classify(
            status: 401, body: Fixture.unauthenticatedEmptyToken)
        #expect(outcome.retryPolicy == .onceAfterReauthentication)
        #expect(!outcome.isUserActionable)
    }

    @Test("The drive-specific unauthenticated phrasing is still a token problem")
    func driveSyntaxUnauthenticated() {
        let outcome = TeamsResponseClassifier.classify(
            status: 401, body: Fixture.unauthenticatedDriveSyntax)
        #expect(outcome == .needsReauthentication(code: "unauthenticated"))
    }

    // MARK: The rest of the surface

    @Test("A missing resource is not retryable")
    func notFound() {
        let outcome = TeamsResponseClassifier.classify(status: 404, body: Fixture.itemNotFound)
        #expect(outcome == .notFound)
        #expect(outcome.retryPolicy == .never)
    }

    @Test("A successful listing classifies as ok")
    func success() {
        #expect(TeamsResponseClassifier.classify(status: 200, body: Fixture.driveListing) == .ok)
    }

    @Test("403 is a consent problem, distinct from a token problem")
    func forbidden() {
        let outcome = TeamsResponseClassifier.classify(status: 403, body: nil)
        #expect(outcome == .scopeNotGranted)
        #expect(outcome.retryPolicy == .never)
        #expect(outcome.isUserActionable)
    }

    @Test("Throttling carries the server's own advice through")
    func throttled() {
        let outcome = TeamsResponseClassifier.classify(status: 429, body: nil, retryAfter: 30)
        #expect(outcome == .rateLimited(retryAfter: 30))
        #expect(outcome.retryPolicy == .backoff(after: 30))
    }

    @Test("5xx backs off")
    func serverError() {
        let outcome = TeamsResponseClassifier.classify(status: 503, body: nil)
        #expect(outcome == .transient(status: 503))
        #expect(outcome.retryPolicy == .backoff(after: nil))
    }

    /// Fail closed. An unclassifiable response must not earn a free retry — a
    /// retry loop is the failure mode this type is built to prevent, so the
    /// unknown case surfaces rather than spins.
    @Test("An unrecognised status fails closed rather than retrying")
    func unknownFailsClosed() {
        let outcome = TeamsResponseClassifier.classify(status: 418, body: nil)
        #expect(outcome == .unexpected(status: 418, code: nil))
        #expect(outcome.retryPolicy == .never)
    }

    @Test("A body that is not Graph's error envelope does not crash classification")
    func malformedBody() {
        let outcome = TeamsResponseClassifier.classify(status: 401, body: Data("not json".utf8))
        #expect(outcome == .needsReauthentication(code: "unknown"))
    }
}

@Suite("Drive tier")
struct DriveTierTests {

    @Test("A personal drive cannot hold Teams recordings")
    func personalCannotHoldRecordings() {
        // Verified live: a personal account has no /Recordings folder at all,
        // because the recording is attached to the meeting chat instead.
        #expect(DriveTier(driveType: "personal") == .personal)
        #expect(!DriveTier(driveType: "personal").canHoldTeamsRecordings)
    }

    @Test("Business and document-library drives can")
    func businessCanHoldRecordings() {
        #expect(DriveTier(driveType: "business").canHoldTeamsRecordings)
        #expect(DriveTier(driveType: "documentLibrary").canHoldTeamsRecordings)
    }

    @Test("An unrecognised or absent driveType is not assumed capable")
    func unknownIsNotCapable() {
        #expect(!DriveTier(driveType: nil).canHoldTeamsRecordings)
        #expect(!DriveTier(driveType: "somethingNew").canHoldTeamsRecordings)
    }
}

@Suite("Import row state")
struct ImportRowStateTests {

    /// The expensive confusion: a placeholder offered as fetchable makes the
    /// researcher re-pull gigabytes from Teams for a file they already hold,
    /// spending an expiry-limited remote read on a purely local problem.
    @Test("A cloud placeholder is held, not fetchable, and not an error")
    func placeholderIsHeldNotFetchable() {
        let state = ImportRowState.notDownloaded(provider: "Dropbox")
        #expect(!state.isSelectable)
        #expect(state.showsCheckbox)
        // The wording moved to `desktop.cloudImport.statusOnProvider`, where
        // `check-locales.py` enforces that every locale keeps the
        // `{{provider}}` placeholder — which is the actual invariant here
        // (name the provider, don't say "missing"). What stays behavioural is
        // asserted above and below.
        #expect(!state.isWarning, "a placeholder is a healthy file, not a failure")
    }

    @Test("A damaged file is the one held state that re-fetches")
    func damagedRefetches() {
        #expect(ImportRowState.damaged.isSelectable)
        #expect(ImportRowState.damaged.isWarning)
    }

    @Test("An unmounted volume names the volume rather than saying missing")
    func unmountedNamesVolume() {
        let state = ImportRowState.driveNotConnected(volume: "T7")
        #expect(!state.isSelectable, "re-fetching is the wrong fix for an unplugged drive")
        // Same: the string is now `desktop.cloudImport.statusOnVolume` and its
        // `{{volume}}` placeholder is locale-checked. A volume that went
        // unnamed would fail there, not here.
    }

    /// No checkbox at all, rather than a disabled one: there is nothing to tick,
    /// and offering a control that cannot act would be a lie.
    @Test("States with no possible fetch offer no checkbox")
    func noFetchNoCheckbox() {
        #expect(!ImportRowState.viewOnly.showsCheckbox)
        #expect(!ImportRowState.noLongerAvailable.showsCheckbox)
    }

    /// Absence is information. The checkbox already says imported or not, so the
    /// Status column carries only what the checkbox cannot.
    @Test("The common states leave the Status column empty")
    func commonStatesAreSilent() {
        #expect(ImportRowState.notImported.statusLabel == nil)
        #expect(ImportRowState.imported.statusLabel == nil)
    }

    @Test("Only actionable conditions are warning-coloured")
    func warningIsEarned() {
        #expect(!ImportRowState.imported.isWarning)
        #expect(!ImportRowState.notImported.isWarning)
        #expect(!ImportRowState.notDownloaded(provider: "iCloud Drive").isWarning)
        #expect(ImportRowState.viewOnly.isWarning)
    }
}

// MARK: - Counting things in a sentence

@Suite("Counted nouns")
struct CloudCountTests {

    /// Written after the first live Google list drew **"1 meetings are here"**
    /// and **"1 meetings in window"** on the same screen — in a window whose
    /// entire job is to be believed about quantities, and whose own design doc
    /// says its success output and its failure output are both a shorter list.
    /// A count the reader can see is wrong is a poor advertisement for the
    /// counts they can't check.
    @Test("One is singular, and nothing else is")
    func singularAtOne() {
        #expect(CloudCount.noun(1, "meeting") == "1 meeting")
        #expect(CloudCount.noun(2, "meeting") == "2 meetings")
        // Zero is plural in English — "0 meetings" — which is easy to get
        // wrong by reaching for `n > 1` and reading it as "not singular".
        #expect(CloudCount.noun(0, "meeting") == "0 meetings")
    }

    @Test("An irregular plural is passed in rather than derived")
    func explicitPlural() {
        // No inflection engine here by choice; the CLI has one and the SPA has
        // CLDR. This must therefore be given anything a bare `s` won't form,
        // and quietly producing "persons" would be the failure.
        #expect(CloudCount.noun(2, "person", plural: "people") == "2 people")
        #expect(CloudCount.noun(1, "person", plural: "people") == "1 person")
    }
}
