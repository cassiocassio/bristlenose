import Foundation
import Testing

@testable import Bristlenose

// The rules behind the paywall. A view test would prove a sheet draws; these
// prove who is let through, which is the part that costs trust if it's wrong.

@Suite("Who may start an analysis")
struct SubscriptionAccessTests {

    private let id = SubscriptionAccess.monthlyProductID
    private let past = Date(timeIntervalSince1970: 1_000_000_000)
    private let future = Date(timeIntervalSince1970: 4_000_000_000)

    @Test("no entitlement, with the product loaded, means not subscribed")
    func noEntitlement() {
        let s = SubscriptionAccess.state(entitledProductIDs: [], expirations: [:], productLoaded: true)
        #expect(s == .notSubscribed)
    }

    @Test("no entitlement and no product: the store is unavailable, and Analyse is held")
    func storeDidNotAnswer() {
        let s = SubscriptionAccess.state(entitledProductIDs: [], expirations: [:], productLoaded: false)
        #expect(s == .storeUnavailable)
        #expect(!SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .developerID))
    }

    @Test("a paid person is subscribed even when the product did not load")
    func paidButOffline() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: future], productLoaded: false)
        #expect(s == .subscribed(expires: future))
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
    }

    @Test("an entitlement means subscribed")
    func entitled() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: future], productLoaded: true)
        #expect(s == .subscribed(expires: future))
    }

    @Test("an entitlement with no expiry is still subscribed")
    func entitledNoExpiry() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [:], productLoaded: true)
        #expect(s == .subscribed(expires: nil))
    }

    @Test("billing grace: an entitlement whose period end has passed still lets them in")
    func gracePeriod() {
        // StoreKit keeps a grace-period subscription in currentEntitlements
        // while its transaction's expirationDate is already in the past.
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: past], productLoaded: true)
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
    }

    @Test("a free-trial entitlement is subscribed and marked as a trial")
    func trial() {
        let s = SubscriptionAccess.state(entitledProductIDs: [id], expirations: [id: future],
                                         trialProductIDs: [id], productLoaded: true)
        #expect(s == .subscribed(expires: future, inTrial: true))
        #expect(SubscriptionAccess.canStartAnalysis(s, channel: .appStoreOrTestFlight))
    }

    @Test("someone else's product does not count")
    func otherProduct() {
        let s = SubscriptionAccess.state(entitledProductIDs: ["something.else"], expirations: [:], productLoaded: true)
        #expect(s == .notSubscribed)
    }

    @Test("on the App Store a lapsed subscriber cannot start an analysis")
    func lapsedBlocked() {
        #expect(!SubscriptionAccess.canStartAnalysis(.notSubscribed, channel: .appStoreOrTestFlight))
    }

    @Test("an unanswered store never locks anyone out")
    func unknownAllowed() {
        #expect(SubscriptionAccess.canStartAnalysis(.unknown, channel: .appStoreOrTestFlight))
    }

    @Test("a subscriber can start an analysis")
    func subscribedAllowed() {
        #expect(SubscriptionAccess.canStartAnalysis(.subscribed(expires: nil), channel: .appStoreOrTestFlight))
    }

    @Test("the dmg and debug builds are never gated, whatever the state")
    func otherChannelsUngated() {
        for state in [SubscriptionAccess.State.unknown, .notSubscribed, .subscribed(expires: nil)] {
            #expect(SubscriptionAccess.canStartAnalysis(state, channel: .developerID))
            #expect(SubscriptionAccess.canStartAnalysis(state, channel: .debug))
        }
    }

    @Test("a lapsed subscriber can still open their own projects")
    func readingAlwaysAllowed() {
        #expect(SubscriptionAccess.canOpenProjects(.notSubscribed, channel: .appStoreOrTestFlight))
    }
}
