import Foundation
import Testing

@testable import Bristlenose

// Teams' failures are a family of their own: not misclassified scopes (Google)
// nor statuses that lie (Zoom), but **the same signal meaning opposite things**.

// MARK: - Scopes

@Suite("Microsoft scope choices")
struct MicrosoftScopeTests {

    @Test("Calendars.Read, never Calendars.ReadBasic")
    func readNotReadBasic() {
        // The intuitive choice is the wrong one. ReadBasic returns attendees
        // WITHOUT bodies — better data minimisation — and requires admin
        // consent, which would move Teams from no-gate to admin-gated and
        // destroy the single property §5's sequencing rests on. Less privileged
        // does not imply easier to consent.
        #expect(MicrosoftScopes.requested.contains("Calendars.Read"))
        #expect(!MicrosoftScopes.requested.contains { $0.contains("ReadBasic") })
    }

    @Test("offline_access is requested — Microsoft issues no refresh token without it")
    func offlineAccess() {
        // The failure is delayed, which is what makes it worth pinning: the
        // grant works for an hour, then every fetch re-prompts.
        #expect(MicrosoftScopes.requested.contains("offline_access"))
    }

    @Test("The admin-walled scopes are never requested")
    func noAdminScopes() {
        // Files.Read.All and Sites.Read.All have been admin-consent-only since
        // Aug 2025 — the procurement gate the customer profile is defined by
        // avoiding, and the only thing standing between this feature and the
        // team's whole SharePoint site.
        for refused in MicrosoftScopes.refused {
            #expect(!MicrosoftScopes.requested.contains(refused))
        }
        #expect(!MicrosoftScopes.requested.contains { $0.hasSuffix(".All") })
    }
}

// MARK: - Configuration

@Suite("Microsoft OAuth configuration")
struct MicrosoftOAuthConfigTests {

    @Test("The default tenant admits personal accounts on purpose")
    func commonTenant() {
        let defaults = UserDefaults(suiteName: "teams-config-test")!
        defaults.removePersistentDomain(forName: "teams-config-test")
        defaults.set("abc-123", forKey: MicrosoftOAuthConfig.clientIDDefaultsKey)
        let config = MicrosoftOAuthConfig.resolve(defaults: defaults, bundle: .main)
        // `common` rather than `organizations`: a personal account must be
        // admitted so the adapter can *diagnose* it. Excluding it at the tenant
        // would turn "your account tier has no /Recordings folder" into an
        // opaque sign-in refusal.
        #expect(config?.tenant == "common")
        #expect(config?.callbackScheme == "msauth.app.bristlenose")
        defaults.removePersistentDomain(forName: "teams-config-test")
    }

    @Test("No client ID means not-configured, not a broken client")
    func missingClientID() {
        let defaults = UserDefaults(suiteName: "teams-empty-test")!
        defaults.removePersistentDomain(forName: "teams-empty-test")
        #expect(MicrosoftOAuthConfig.resolve(defaults: defaults, bundle: Bundle(for: TeamsSource.self)) == nil)
    }
}

// MARK: - Consent refusal

@Suite("Microsoft consent errors")
struct MicrosoftConsentTests {

    @Test("AADSTS90094 is explained as an admin gate, not as a failure")
    func adminConsentRequired() {
        // The Entra analogue of Zoom's pre-approval wall. Telling the
        // researcher to try again would send them at a wall only their IT
        // department can remove.
        let error = MicrosoftOAuthError.consentRefused(
            code: "AADSTS90094: The grant requires admin permission.",
            description: "raw")
        #expect(error.errorDescription?.contains("administrator") == true)
    }

    @Test("Any other refusal keeps Microsoft's own wording")
    func otherRefusal() {
        // Substituting our own sentence for a message we don't understand
        // would replace a specific, searchable string with a vague one.
        let error = MicrosoftOAuthError.consentRefused(
            code: "AADSTS65004", description: "User declined to consent.")
        #expect(error.errorDescription == "User declined to consent.")
    }
}

// MARK: - Drive tier

@Suite("Teams drive tier")
struct TeamsDriveTierTests {

    @Test("A personal account cannot hold Teams recordings")
    func personalTier() {
        // Verified 15 Aug 2026: on a personal account the recording is attached
        // to the meeting chat and nothing lands in OneDrive, so a Graph probe
        // of /Recordings returns itemNotFound. Reading that as "no recordings"
        // rather than "wrong tier" is the baffling-empty-list failure.
        let personal = DriveTier(driveType: "personal")
        #expect(personal == .personal)
        #expect(!personal.canHoldTeamsRecordings)
    }

    @Test("Both business drive types can")
    func businessTiers() {
        #expect(DriveTier(driveType: "business").canHoldTeamsRecordings)
        #expect(DriveTier(driveType: "documentLibrary").canHoldTeamsRecordings)
    }

    @Test("An unknown drive type is not assumed capable")
    func unknownTier() {
        #expect(!DriveTier(driveType: nil).canHoldTeamsRecordings)
        #expect(!DriveTier(driveType: "somethingNew").canHoldTeamsRecordings)
    }
}

// MARK: - Transfer policy

@Suite("Teams transfer policy")
struct TeamsTransferTests {

    @Test("Graph's download URL carries its own credential, so no header is sent")
    func preAuthorized() {
        // @microsoft.graph.downloadUrl arrives with tempauth= in the query
        // string. That is also exactly why §9 forbids logging these URLs: the
        // URL IS the credential, and it appears in an ordinary listing response.
        #expect(CloudTransferPolicy.teams.authorization == .preAuthorizedURL)
        #expect(!CloudTransferPolicy.teams.keepAuthorizationAcrossRedirect)
    }

    @Test("Teams is the one platform that can verify exactly")
    func hashAvailable() {
        // Graph returns quickXorHash/sha1Hash/sha256Hash alongside size in the
        // listing — BEFORE the download — so verification is exact rather than
        // heuristic. Neither other platform publishes one.
        let expected = ExpectedFile(
            sizeBytes: 1_000,
            hash: FileHash(algorithm: .sha256, value: "ABCD"),
            expectedFormat: .mp4)
        let head: [UInt8] = [0, 0, 0, 0x20] + Array("ftypisom".utf8)
        #expect(CloudDownloadVerification.verifyPayload(
            received: 1_000, head: head, expected: expected,
            computedHash: "abcd") == .usable)
        #expect(CloudDownloadVerification.verifyPayload(
            received: 1_000, head: head, expected: expected,
            computedHash: "0000") == .hashMismatch(algorithm: .sha256))
    }
}

// MARK: - Three platforms built; which are offered is a flag

@Suite("Platform vocabulary and the Zoom parking rule")
struct ShippingPlatformTests {

    @Test("All three adapters are built")
    func allBuilt() {
        #expect(Set(CloudPlatform.built) == Set(CloudPlatform.allCases))
    }

    /// Zoom was parked 16 Aug 2026 so Teams and Meet could reach releasable
    /// quality first. These pin the *outcome a user would see* — which items
    /// the File menu offers — not the mechanism, so they still mean something
    /// if the filter is reimplemented.
    @Test("Parked: the File menu offers Teams and Meet, and withholds Zoom")
    func zoomParkedByDefault() {
        let offered = CloudPlatform.offered(zoomEnabled: false)
        #expect(offered == [.teams, .meet])
        #expect(!offered.contains(.zoom))
    }

    @Test("Unparked: the flag restores Zoom, in sequence order")
    func zoomReturnsWhenEnabled() {
        #expect(CloudPlatform.offered(zoomEnabled: true) == [.teams, .meet, .zoom])
    }

    /// Parking must withhold the menu item and nothing else. If a future
    /// cleanup amputates the adapter, `built` shrinks and `allBuilt` fails —
    /// but this says the parked platform is still fully *spoken*, which is
    /// what keeps the Diagnostics fixture menu honest while Zoom is away.
    @Test("A parked platform keeps its full vocabulary and transfer policy")
    func parkedPlatformStaysComplete() {
        _ = CloudTransferPolicy.for(.zoom)
        #expect(!CloudPlatform.zoom.displayName.isEmpty)
        #expect(!CloudPlatform.zoom.signInTitle.isEmpty)
        // `windowTitle` is a lookup now, so its presence is `check-locales.py`'s
        // job rather than this suite's. What stays here is the vocabulary the
        // vendor mandates, which is platform data.
        #expect(CloudPlatform.zoom.mandatesAccountNoun == false)
    }

    @Test("Each platform has a transfer policy and a distinct vocabulary")
    func vocabularies() {
        var titles = Set<String>()
        for platform in CloudPlatform.allCases {
            _ = CloudTransferPolicy.for(platform)
            #expect(!platform.displayName.isEmpty)
            titles.insert(platform.signInTitle)
        }
        // Each vendor mandates its own string; a shared one would breach all
        // three sets of brand guidelines at once.
        #expect(titles.count == CloudPlatform.allCases.count)
    }

    @Test("Only Microsoft mandates an account noun")
    func accountNouns() {
        // Their guidelines require "work or school account" beside the button
        // and forbid three synonyms. The other two mandate nothing, and
        // inventing one for Google would actively mislead.
        #expect(CloudPlatform.teams.mandatesAccountNoun)
        #expect(!CloudPlatform.meet.mandatesAccountNoun)
        #expect(!CloudPlatform.zoom.mandatesAccountNoun)
    }

    // MARK: - Keeping the sign-in

    @Test("A renewal that omits the refresh token keeps the one we hold")
    func renewalCarriesForwardTheRefreshToken() {
        // **The silent-death case, and the reason this is a named function
        // rather than an assignment.** Microsoft omits `refresh_token` whenever
        // it chooses not to rotate, and the omission is routine. Storing the
        // response verbatim therefore writes a grant with no way to renew —
        // which works fine for an hour and then strands the account, long after
        // the change that caused it.
        let previous = MicrosoftTokenResponse(
            accessToken: "old", refreshToken: "KEEP-ME",
            expiresAt: Date().addingTimeInterval(-10))
        let renewedWithout = MicrosoftTokenResponse(
            accessToken: "new", refreshToken: nil,
            expiresAt: Date().addingTimeInterval(3600))

        let merged = renewedWithout.carryingForwardRefreshToken(from: previous)
        #expect(merged.accessToken == "new")
        #expect(merged.refreshToken == "KEEP-ME")
    }

    @Test("A rotated refresh token replaces the old one, never the reverse")
    func rotationPrefersTheNewToken() {
        // The other direction, which the `??` gets right only by being written
        // the correct way round — and getting it backwards would pin the
        // account to a token the server has already retired.
        let previous = MicrosoftTokenResponse(
            accessToken: "old", refreshToken: "STALE",
            expiresAt: Date().addingTimeInterval(-10))
        let rotated = MicrosoftTokenResponse(
            accessToken: "new", refreshToken: "FRESH",
            expiresAt: Date().addingTimeInterval(3600))

        #expect(rotated.carryingForwardRefreshToken(from: previous).refreshToken == "FRESH")
    }

    @Test("A grant survives the round trip it is stored by")
    func grantRoundTrips() {
        // The stored shape is the type's own properties, not the OAuth wire
        // payload `init?(data:)` parses. Two formats, one type — so the encoder
        // and decoder agreeing is worth asserting rather than assuming.
        let grant = MicrosoftGrant(
            tokens: MicrosoftTokenResponse(
                accessToken: "A", refreshToken: "R",
                expiresAt: Date(timeIntervalSince1970: 1_800_000_000)),
            identity: "martin@clientco.com")

        let data = try? JSONEncoder().encode(grant)
        let decoded = data.flatMap { try? JSONDecoder().decode(MicrosoftGrant.self, from: $0) }
        #expect(decoded == grant)
    }
}
