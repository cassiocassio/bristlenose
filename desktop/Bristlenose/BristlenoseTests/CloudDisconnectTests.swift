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

    @Test("Connection identity is the platform, so a list can't hold two of one")
    func connectionIdentity() {
        // `Identifiable` off the platform rather than the address: the address
        // is optional, and two rows for one platform is not a state that should
        // be representable in a list keyed this way.
        let connection = CloudGrantStore.Connection(platform: .teams, address: nil)
        #expect(connection.id == CloudPlatform.teams.rawValue)
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
