import Foundation
import Testing

@testable import Bristlenose

// The state engine behind Settings ▸ Accounts.
//
// Worth its own suite because the pane's whole design rests on one claim — that
// every state can be worked out from what is already on disk, with no network
// call — and that claim is only checkable at this layer. A view test would
// prove the row draws; these prove the row is *entitled* to draw.

@Suite("What each account section shows")
struct AccountsSectionModelTests {

    private let allAvailable: Set<CloudPlatform> = [.teams, .meet, .zoom]

    private func connection(_ platform: CloudPlatform,
                            _ address: String?,
                            needsSignIn: Bool = false) -> CloudGrantStore.Connection {
        CloudGrantStore.Connection(platform: platform,
                                   accountKey: CloudAccountKey.derive(address),
                                   address: address,
                                   needsSignIn: needsSignIn)
    }

    private func sections(available: Set<CloudPlatform>? = nil,
                          connections: [CloudGrantStore.Connection] = [],
                          miroConnected: Bool = false,
                          miroIdentity: String? = nil) -> [AccountSection] {
        AccountsSectionModel.sections(available: available ?? allAvailable,
                                      connections: connections,
                                      miroConnected: miroConnected,
                                      miroIdentity: miroIdentity)
    }

    private func state(_ sections: [AccountSection], _ id: String) -> AccountSectionState? {
        sections.first { $0.service.id == id }?.state
    }

    // MARK: The catalogue

    @Test("All four services are always listed, connected or not")
    func catalogueIsFixed() {
        // A catalogue that hides what is not ready cannot answer "what can this
        // thing talk to?", which is half of why the pane is opened.
        #expect(sections().map(\.service.id) == ["teams", "meet", "zoom", "miro"])
    }

    @Test("Nothing connected reads as not connected, not as broken")
    func emptyIsNotConnected() {
        for section in sections() {
            #expect(section.state == .notConnected, "\(section.service.id)")
            #expect(section.accountKey == nil)
        }
    }

    // MARK: Unavailable

    @Test("A service this build can't sign in to says so, and offers no verb")
    func unavailableWhenNoClient() {
        // Zoom today: parked behind a flag, no OAuth client. Not the
        // researcher's doing and not something they can fix.
        let result = sections(available: [.teams, .meet])
        #expect(state(result, "zoom") == .unavailable)
    }

    @Test("Unavailable wins over a grant left behind by an earlier build")
    func unavailableBeatsAStaleGrant() {
        // The order matters: a stored sign-in whose client id has since gone
        // would otherwise render as a working connection nothing can use.
        let result = sections(available: [.meet],
                              connections: [connection(.teams, "martin@clientco.com")])
        #expect(state(result, "teams") == .unavailable)
        #expect(result.first { $0.service.id == "teams" }?.accountKey == nil,
                "an unavailable service must not offer something to disconnect")
    }

    // MARK: Connected

    @Test("A connected account is named by its address")
    func connectedCarriesTheAddress() {
        let result = sections(connections: [connection(.teams, "martin@clientco.com")])
        #expect(state(result, "teams") == .connected(identity: "martin@clientco.com"))
    }

    @Test("A sign-in whose address never arrived is still a connection")
    func connectedWithoutAddress() {
        // `/me` can fail while the tokens are perfectly good. A row with no
        // address beats no row — it is still the only place to remove it.
        let result = sections(connections: [connection(.teams, nil)])
        #expect(state(result, "teams") == .connected(identity: nil))
    }

    @Test("Disconnect targets the stored item, not the platform")
    func connectedCarriesTheAccountKey() {
        let result = sections(connections: [connection(.teams, "martin@clientco.com")])
        #expect(result.first { $0.service.id == "teams" }?.accountKey
                == CloudAccountKey.derive("martin@clientco.com"))
    }

    @Test("One service connected leaves the others alone")
    func servicesAreIndependent() {
        let result = sections(connections: [connection(.meet, "martin@finca342.org")])
        #expect(state(result, "meet") == .connected(identity: "martin@finca342.org"))
        #expect(state(result, "teams") == .notConnected)
        #expect(state(result, "zoom") == .notConnected)
    }

    // MARK: Needs attention

    @Test("A consumer Google account is flagged before the researcher goes looking")
    func personalGoogleCannotHoldRecordings() {
        // Rescues "I signed in and there's nothing there". Meet recording is a
        // Workspace feature, so a gmail.com account can hold a meeting, invite
        // participants, produce a perfectly good calendar event — and never a
        // recording to fetch. Today that reads as an empty list.
        let result = sections(connections: [connection(.meet, "martin@gmail.com")])
        #expect(state(result, "meet")
                == .attention(identity: "martin@gmail.com", .cannotHoldRecordings))
    }

    @Test("googlemail.com is the same account kind as gmail.com")
    func historicalGmailAliasCounts() {
        let result = sections(connections: [connection(.meet, "martin@googlemail.com")])
        #expect(state(result, "meet")
                == .attention(identity: "martin@googlemail.com", .cannotHoldRecordings))
    }

    @Test("A Workspace account is just connected")
    func workspaceGoogleIsFine() {
        let result = sections(connections: [connection(.meet, "martin@finca342.org")])
        #expect(state(result, "meet") == .connected(identity: "martin@finca342.org"))
    }

    @Test("A Google sign-in with no address is not accused of being personal")
    func unknownGoogleTierIsNotAnAccusation() {
        // `GoogleAccountTier(email: nil)` is `.unknown`, whose
        // `canHoldMeetRecordings` is false — reading that as "this account
        // can't hold recordings" would tell a Workspace researcher their
        // account is wrong because one `/me` call failed.
        let result = sections(connections: [connection(.meet, nil)])
        #expect(state(result, "meet") == .connected(identity: nil))
    }

    @Test("A personal Microsoft account is NOT flagged, because the pane cannot know")
    func teamsTierIsNotClaimed() {
        // The asymmetry, pinned so it reads as a known gap rather than a bug.
        // Microsoft's equivalent comes from `GET /me/drive?$select=driveType` —
        // a call this pane does not make. Until the adapter writes its
        // `DriveTier` verdict onto the grant, a personal Microsoft account
        // reads as connected and the truth arrives in the import window.
        let result = sections(connections: [connection(.teams, "martin@outlook.com")])
        #expect(state(result, "teams") == .connected(identity: "martin@outlook.com"))
    }

    @Test("A revoked sign-in stays on the list instead of vanishing")
    func revokedGrantKeepsItsRow() {
        // Rescues "it just stopped working and I don't know why". Before the
        // grant survived its own refusal this account disappeared from the
        // pane entirely, which reads exactly like having disconnected it
        // yourself — and left nothing anywhere naming the cause.
        let result = sections(connections: [connection(.teams, "martin@clientco.com",
                                                       needsSignIn: true)])
        #expect(state(result, "teams")
                == .attention(identity: "martin@clientco.com", .signInAgain))
    }

    @Test("A refusal outranks the account tier")
    func refusalBeatsTier() {
        // A revoked consumer Google sign-in is both, and only one is worth
        // saying: telling someone their account is the wrong kind, when what
        // actually happened is that their session ended, sends them to fix
        // something that is not broken.
        let result = sections(connections: [connection(.meet, "martin@gmail.com",
                                                       needsSignIn: true)])
        #expect(state(result, "meet") == .attention(identity: "martin@gmail.com", .signInAgain))
    }

    @Test("Only the recoverable cause offers a way back")
    func recoverability() {
        // The wrong kind of account cannot be fixed by signing in again — the
        // same account would come back — so offering the verb would be a
        // button that reliably does nothing.
        #expect(AccountAttention.signInAgain.isRecoverable)
        #expect(!AccountAttention.cannotHoldRecordings.isRecoverable)
    }

    @Test("A revoked account can still be removed")
    func revokedKeepsItsAccountKey() {
        let result = sections(connections: [connection(.teams, "martin@clientco.com",
                                                       needsSignIn: true)])
        #expect(result.first { $0.service.id == "teams" }?.accountKey
                == CloudAccountKey.derive("martin@clientco.com"))
    }

    @Test("A revoked grant is never usable, so it cannot restore a session")
    func revokedGrantIsInert() {
        // The guard that keeps a kept grant from becoming an unbreakable retry
        // loop — a revoked refresh token fails identically forever, which is
        // exactly why the old code deleted it.
        let teams = MicrosoftGrant.revoked(identity: "martin@clientco.com")
        #expect(teams.usable == nil)
        #expect(teams.tokens.refreshToken == nil, "a tombstone must carry no way to retry")
        #expect(teams.identity == "martin@clientco.com", "the account is still nameable")

        let google = GoogleGrant.revoked(identity: "martin@finca342.org")
        #expect(google.usable == nil)
        #expect(google.tokens.refreshToken == nil)
        #expect(google.media == nil, "the Picker grant goes with the listing grant")
    }

    @Test("A working grant is usable, and a grant from before the flag existed still decodes")
    func liveGrantIsUsable() throws {
        // The optional matters: the synthesised decoder does not apply property
        // defaults for a missing key, it throws — and `loadTeams` discards what
        // it cannot decode, so a non-optional field would have dropped every
        // sign-in stored before this change.
        let legacyJSON = """
        {"tokens":{"accessToken":"a","refreshToken":"r","expiresAt":760000000},\
        "identity":"martin@clientco.com"}
        """
        let decoded = try JSONDecoder().decode(MicrosoftGrant.self,
                                               from: Data(legacyJSON.utf8))
        #expect(decoded.needsSignIn == nil)
        #expect(decoded.usable != nil)
    }

    @Test("An account needing attention can still be disconnected")
    func attentionKeepsTheAccountKey() {
        // The row that says something is wrong is exactly the row a researcher
        // wants to remove.
        let result = sections(connections: [connection(.meet, "martin@gmail.com")])
        #expect(result.first { $0.service.id == "meet" }?.accountKey
                == CloudAccountKey.derive("martin@gmail.com"))
    }

    // MARK: Miro

    @Test("Miro is in the list without being a CloudPlatform")
    func miroIsAService() {
        // §3 issue 3: adding `.miro` to `CloudPlatform` would put it in the
        // import window's platform picker and the fixture harness. The sameness
        // belongs in `AccountService`, not in that enum.
        #expect(AccountService.all.contains(.miro))
        #expect(CloudPlatform.built.count == 3)
    }

    @Test("Miro shows its cached identity when there is one")
    func miroConnectedWithIdentity() {
        let result = sections(miroConnected: true, miroIdentity: "Martin Storey · 144a")
        #expect(state(result, "miro") == .connected(identity: "Martin Storey · 144a"))
    }

    @Test("Miro connected but never resolved shows no filler second line")
    func miroConnectedWithoutIdentity() {
        // "Connected" as a second line says only what the row's presence
        // already says.
        let result = sections(miroConnected: true, miroIdentity: nil)
        #expect(state(result, "miro") == .connected(identity: nil))
    }

    @Test("Miro says where to connect rather than offering a door that fails")
    func miroDoesNotConnectFromSettings() {
        // Its connect is a pasted token inside the export sheet, which needs a
        // running serve and an open project — neither guaranteed in Settings.
        #expect(!AccountService.miro.connectsFromHere)
        #expect(AccountService.cloud(.teams).connectsFromHere)
    }

    @Test("Miro's display line prefers the organisation, falls back to the team")
    func miroDisplayLine() {
        // `orgName` is Enterprise-only, so it is nil on the ordinary account and
        // the team is the next most useful thing to say.
        #expect(MiroConnectionStore.displayLine(
            .init(connected: true, userName: "Martin Storey",
                  teamName: "Research", orgName: "144a")) == "Martin Storey · 144a")
        #expect(MiroConnectionStore.displayLine(
            .init(connected: true, userName: "Martin Storey",
                  teamName: "Research", orgName: nil)) == "Martin Storey · Research")
    }

    @Test("Miro giving us nothing produces no line at all")
    func miroDisplayLineEmpty() {
        #expect(MiroConnectionStore.displayLine(
            .init(connected: true, userName: nil, teamName: nil, orgName: nil)) == nil)
        #expect(MiroConnectionStore.displayLine(
            .init(connected: true, userName: "", teamName: "", orgName: "")) == nil)
    }

    @Test("Miro's token is not per-account, so no row claims a key it hasn't got")
    func miroHasNoAccountKey() {
        let result = sections(miroConnected: true, miroIdentity: "Martin Storey")
        #expect(result.first { $0.service.id == "miro" }?.accountKey == nil)
    }
}
