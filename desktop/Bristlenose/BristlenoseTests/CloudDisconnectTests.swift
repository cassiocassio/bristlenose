import Foundation
import Testing

@testable import Bristlenose

// Disconnecting an account has to reach a window that is already open.
//
// The failure this guards is quiet and bad: clearing the Keychain copy while a
// live adapter holds its tokens in memory leaves a window that keeps listing and
// fetching against the account the researcher has just disconnected. The control
// appears to work and does not — and the privacy policy is about to claim it
// does, which turns a UI gap into a false statement.
//
// Nothing here touches the real Keychain. `openFixture` builds a store from a
// `FixtureCloudSource`, so a live session exists with no credentials anywhere,
// and the tests post the notification directly rather than calling
// `CloudGrantStore.disconnect` — which would delete a real grant from the
// developer's own Keychain.

// **`.serialized`, and every test on a different platform — both deliberate.**
// These coordinators observe the process-wide `NotificationCenter`, so under
// Swift Testing's default parallelism one test's post is delivered to every
// other test's live coordinator. That is exactly how `otherPlatformIsIgnored`
// first failed: a sibling posted `teams` while this suite held an open `teams`
// window, and the store it expected to survive was cleared by a notification
// meant for someone else. Serialising removes the interleaving; giving each test
// its own platform removes the collision even if it ever runs parallel again.
@MainActor
@Suite("Disconnecting reaches an open import window", .serialized)
struct CloudDisconnectTests {

    @Test("Disconnecting the open platform drops the live session")
    func matchingPlatformClearsStore() async {
        let coordinator = CloudImportCoordinator()
        coordinator.openFixture(.teams, .populated, preselecting: nil)
        #expect(coordinator.store != nil, "fixture store did not open")

        post(.teams)
        await settle()

        #expect(coordinator.store == nil,
                "the window outlived the account it was signed in to")
    }

    @Test("Disconnecting a different platform leaves the window alone")
    func otherPlatformIsIgnored() async {
        // The off-by-one that matters. A researcher with two accounts connected
        // who removes one must not have the other's open window silently
        // emptied — and since the batch, the ticks and the outcomes all live in
        // that store, the cost of getting it wrong is their work, not just a
        // re-open.
        let coordinator = CloudImportCoordinator()
        coordinator.openFixture(.meet, .populated, preselecting: nil)

        post(.teams)
        await settle()

        #expect(coordinator.store != nil,
                "disconnecting Teams closed a Meet window")
    }

    @Test("A malformed notification is ignored rather than clearing everything")
    func missingPlatformIsIgnored() async {
        // Fail closed in the safe direction: an unreadable payload must not be
        // treated as "disconnect whatever is open".
        let coordinator = CloudImportCoordinator()
        coordinator.openFixture(.zoom, .populated, preselecting: nil)

        NotificationCenter.default.post(
            name: .bristlenoseCloudAccountDisconnected, object: nil, userInfo: nil)
        await settle()

        #expect(coordinator.store != nil)
    }

    @Test("Connection identity is platform AND account, so a list can hold two of one")
    func connectionIdentity() {
        // _Reversed 18 Aug 2026._ This previously asserted `id ==
        // platform.rawValue`, on the reasoning that "two rows for one platform
        // is not a state that should be representable". It is exactly the state
        // that must be representable: a consultant has a personal Microsoft
        // account and one per client. Keyed on the platform alone, `ForEach`
        // renders one row and the second account silently disappears from the
        // pane while sitting perfectly well in the Keychain.
        //
        // Not the address either — that is optional, and a grant whose `/me`
        // lookup failed is still a real connection that must be removable.
        let work = CloudGrantStore.Connection(
            platform: .teams, accountKey: "aaa",
            address: "martin@clientco.com", needsSignIn: false, driveTier: .business)
        let personal = CloudGrantStore.Connection(
            platform: .teams, accountKey: "bbb", address: nil, needsSignIn: false,
            driveTier: nil)
        #expect(work.id != personal.id)
    }

    @Test("Disconnecting the other account on the same platform leaves the window alone")
    func otherAccountOnSamePlatformIsIgnored() {
        // The off-by-one the account key exists for. Two Teams accounts, and
        // removing the personal one must not empty a window signed in to the
        // work one — where the ticks, the outcomes and the batch live.
        #expect(!CloudDisconnectMatch.dropsSession(
            livePlatform: .teams,
            liveAccountKey: "work",
            notedPlatform: CloudPlatform.teams.rawValue,
            notedAccountKey: "personal"))
    }

    @Test("Disconnecting the account the window is signed in to drops it")
    func matchingAccountDrops() {
        #expect(CloudDisconnectMatch.dropsSession(
            livePlatform: .teams,
            liveAccountKey: "work",
            notedPlatform: CloudPlatform.teams.rawValue,
            notedAccountKey: "work"))
    }

    @Test("An unknown account on either side drops, because the safe direction is dropping")
    func unknownAccountDrops() {
        // A session with no key holds no credentials (a fixture window) or has
        // not learned one yet; a notification with no key predates them. Either
        // way the choice is between a needless re-open and a window fetching
        // under a disconnected account, and only one of those is recoverable by
        // noticing.
        #expect(CloudDisconnectMatch.dropsSession(
            livePlatform: .teams, liveAccountKey: nil,
            notedPlatform: CloudPlatform.teams.rawValue, notedAccountKey: "work"))
        #expect(CloudDisconnectMatch.dropsSession(
            livePlatform: .teams, liveAccountKey: "work",
            notedPlatform: CloudPlatform.teams.rawValue, notedAccountKey: nil))
    }

    @Test("A different platform never matches, whatever the account says")
    func platformStillGatesFirst() {
        #expect(!CloudDisconnectMatch.dropsSession(
            livePlatform: .meet, liveAccountKey: "same",
            notedPlatform: CloudPlatform.teams.rawValue, notedAccountKey: "same"))
        #expect(!CloudDisconnectMatch.dropsSession(
            livePlatform: .meet, liveAccountKey: nil,
            notedPlatform: nil, notedAccountKey: nil))
    }

    @Test("A live window is signed in to the account the store found")
    func liveSessionCarriesItsAccountKey() async {
        // The composition nothing pinned. The three fixture tests above set no
        // account key at all — `openFixture` leaves it nil — and their `post`
        // helper sends no account either, so `dropsSession` short-circuits to
        // the old platform-only check and they pass identically against the
        // pre-change code. What was untested is the wiring the whole per-account
        // change turns on: `open` finds a key, hands it to the writer, and the
        // disconnect matcher reads it back.
        let coordinator = CloudImportCoordinator()
        coordinator.accountKeyResolver = { _ in "work-account" }
        coordinator.openLive(.teams, preselecting: nil)
        #expect(coordinator.store != nil, "live store did not open")

        // The *other* account on the same platform must not touch it.
        post(.teams, account: "personal-account")
        await settle()
        #expect(coordinator.store != nil,
                "disconnecting a different account closed this window")

        post(.teams, account: "work-account")
        await settle()
        #expect(coordinator.store == nil,
                "the window outlived the account it was actually signed in to")
    }

    @Test("A window opened before anyone signed in uses the anonymous slot")
    func liveSessionWithNoStoredAccount() async {
        // `?? CloudAccountKey.unidentified` — the first grant such a window
        // writes lands there and rekeys when the address arrives.
        let coordinator = CloudImportCoordinator()
        coordinator.accountKeyResolver = { _ in nil }
        coordinator.openLive(.teams, preselecting: nil)

        post(.teams, account: CloudAccountKey.unidentified)
        await settle()
        #expect(coordinator.store == nil)
    }

    private func post(_ platform: CloudPlatform, account: String) {
        NotificationCenter.default.post(
            name: .bristlenoseCloudAccountDisconnected,
            object: nil,
            userInfo: ["platform": platform.rawValue, "account": account])
    }

    private func post(_ platform: CloudPlatform) {
        NotificationCenter.default.post(
            name: .bristlenoseCloudAccountDisconnected,
            object: nil,
            userInfo: ["platform": platform.rawValue])
    }

    /// The observer is registered on the main queue, so the block runs after the
    /// post returns rather than during it. Yielding a few times is enough and
    /// keeps the test free of a sleep.
    private func settle() async {
        for _ in 0..<10 { await Task.yield() }
    }
}
