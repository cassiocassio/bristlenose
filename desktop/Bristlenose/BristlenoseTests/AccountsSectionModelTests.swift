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
                            needsSignIn: Bool = false,
                            driveTier: DriveTier? = nil) -> CloudGrantStore.Connection {
        CloudGrantStore.Connection(platform: platform,
                                   accountKey: CloudAccountKey.derive(address),
                                   address: address,
                                   needsSignIn: needsSignIn,
                                   driveTier: driveTier)
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

    @Test("Every connectable service is listed, connected or not")
    func catalogueIsFixed() {
        // The list is the catalogue: a service appears whether or not there is
        // a sign-in for it, so "what could I connect?" is answerable without a
        // modal. `AccountService.all` decides membership; this pins that the
        // pane renders one section per member, in order.
        #expect(sections().map(\.service.id) == AccountService.all.map(\.id))
        #expect(sections().map(\.service.id).contains("miro"))
    }

    @Test("A parked service is not listed at all")
    func parkedServiceIsAbsent() {
        // _Reversed 18 Aug 2026._ Zoom used to get a permanent row reading
        // "Not available — Bristlenose can't sign in to Zoom", on the argument
        // that a catalogue hiding what is not ready cannot say what the app can
        // talk to. That answers a question nobody asked and spends a quarter of
        // the pane doing it. `AccountService.all` reads `CloudPlatform.shipping`
        // now, so a parked platform is simply absent — safe only because a
        // parked platform cannot hold a grant.
        #expect(!AccountService.all.map(\.id).contains("zoom"),
                "Zoom is parked and must not be offered a row")
        #expect(CloudGrantStore.connections(store: InMemoryKeychain())
                .allSatisfy { $0.platform != .zoom })
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
        // Not the parked case any more — a parked service is absent entirely.
        // This is the other route in: a build carrying no OAuth client for a
        // platform that is otherwise shipping. Not the researcher's doing and
        // not something they can fix, so the row carries no way to connect.
        let result = sections(available: [.meet])
        #expect(state(result, "teams") == .unavailable(strandedIdentity: nil))
    }

    @Test("Unavailable wins over a grant left behind by an earlier build")
    func unavailableBeatsAStaleGrant() {
        // The order matters: a stored sign-in whose client id has since gone
        // would otherwise render as a working connection nothing can use.
        let result = sections(available: [.meet],
                              connections: [connection(.teams, "martin@clientco.com")])
        #expect(state(result, "teams")
                == .unavailable(strandedIdentity: "martin@clientco.com"))
    }

    @Test("A grant stranded on an unavailable service can still be removed")
    func strandedGrantIsStillDisconnectable() {
        // _Reversed 18 Aug 2026._ This assertion used to be
        // `accountKey == nil`, with the comment "an unavailable service must not
        // offer something to disconnect" — which pinned a defect rather than a
        // property. The `.unavailable` guard exists *because* a stored grant can
        // outlive its client id, and answering that by making the grant
        // undeletable leaves a client's refresh token on disk with no UI
        // anywhere that can reach it, in a pane whose entire purpose is removal.
        // Connect stays suppressed; only the removal survives.
        let result = sections(available: [.meet],
                              connections: [connection(.teams, "martin@clientco.com")])
        #expect(result.first { $0.service.id == "teams" }?.accountKey
                == CloudAccountKey.derive("martin@clientco.com"))
    }

    @Test("An unavailable service with nothing stored offers nothing to remove")
    func unavailableWithoutAGrantHasNoKey() {
        let result = sections(available: [.meet])
        #expect(state(result, "teams") == .unavailable(strandedIdentity: nil))
        #expect(result.first { $0.service.id == "teams" }?.accountKey == nil)
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
        #expect(state(result, "miro") == .notConnected)
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

    @Test("A personal Microsoft account is flagged once a listing has established it")
    func teamsPersonalTierIsFlagged() {
        // _Inverted 18 Aug 2026._ This asserted the opposite — that the pane
        // could not know — and was correct while nothing persisted the verdict.
        // It is kept rather than deleted because the reason it was true is the
        // reason the fix has the shape it does: the pane still makes **no**
        // network call, and `GET /me/drive?$select=driveType` is still the only
        // way to learn this. What changed is that `TeamsSource` now writes what
        // the listing already told it onto the grant, so the pane reads a fact
        // instead of making a call.
        let result = sections(connections: [
            connection(.teams, "martin@outlook.com", driveTier: .personal)])
        #expect(state(result, "teams")
                == .attention(identity: "martin@outlook.com", .cannotHoldRecordings))
    }

    @Test("A work Microsoft account is left alone")
    func teamsBusinessTierIsNotFlagged() {
        let result = sections(connections: [
            connection(.teams, "martin@clientco.com", driveTier: .business)])
        #expect(state(result, "teams") == .connected(identity: "martin@clientco.com"))
    }

    @Test("A Microsoft account nobody has listed yet is not accused of anything")
    func teamsUnestablishedTierIsNotAnAccusation() {
        // The state that keeps the old test's lesson alive. Sign in, never open
        // the import window, and no listing has run — so nothing knows. Nil must
        // read as silence, not as a verdict, and it is the state every account
        // passes through.
        let result = sections(connections: [connection(.teams, "martin@outlook.com")])
        #expect(state(result, "teams") == .connected(identity: "martin@outlook.com"),
                "an unasked question is not an answer")
    }

    @Test("An unrecognised drive type is not treated as a personal account")
    func teamsUnknownTierIsNotFlagged() {
        // `DriveTier.unknown` means Graph returned something this code has not
        // seen. Reading that as "cannot hold recordings" would turn every future
        // Microsoft drive type into an accusation against a working account —
        // the same failure direction the Google test above guards.
        let result = sections(connections: [
            connection(.teams, "martin@clientco.com", driveTier: .unknown("sharePoint"))])
        #expect(state(result, "teams") == .connected(identity: "martin@clientco.com"))
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
