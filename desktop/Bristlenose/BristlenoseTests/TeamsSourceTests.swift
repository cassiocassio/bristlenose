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

// MARK: - Every platform is live

@Suite("All three platforms shipping")
struct ShippingPlatformTests {

    @Test("All three appear in the File menu")
    func allShipping() {
        #expect(Set(CloudPlatform.shipping) == Set(CloudPlatform.allCases))
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
        #expect(CloudPlatform.teams.accountNoun == "work or school account")
        #expect(CloudPlatform.meet.accountNoun == nil)
        #expect(CloudPlatform.zoom.accountNoun == nil)
    }
}
