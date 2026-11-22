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

    // MARK: Early adopters (owner, 22 Nov 2026)

    private let subscribed = SubscriptionAccess.State.subscribed(expires: nil)

    @Test("the launch deal has not ended in this build")
    func dealStillOn() {
        // Flipping this is the act that ends the deal; it should be a
        // deliberate edit that also updates this test.
        #expect(SubscriptionAccess.earlyDealHasEnded == false)
    }

    @Test("before the price rise, every active subscriber is an early adopter, trial included")
    func everySubscriberBeforeTheRise() {
        #expect(SubscriptionAccess.isEarlyAdopter(state: subscribed, renewalPrice: nil,
                                                  currentPrice: nil, dealHasEnded: false))
        #expect(SubscriptionAccess.isEarlyAdopter(state: .subscribed(expires: future, inTrial: true),
                                                  renewalPrice: nil, currentPrice: nil, dealHasEnded: false))
    }

    @Test("someone not subscribed is never an early adopter",
          arguments: [SubscriptionAccess.State.unknown, .notSubscribed, .storeUnavailable])
    func notSubscribedIsNotEarly(state: SubscriptionAccess.State) {
        #expect(!SubscriptionAccess.isEarlyAdopter(state: state, renewalPrice: 1, currentPrice: 2,
                                                   dealHasEnded: false))
        #expect(!SubscriptionAccess.isEarlyAdopter(state: state, renewalPrice: 1, currentPrice: 2,
                                                   dealHasEnded: true))
    }

    @Test("after the rise, a preserved (lower) renewal price keeps the star")
    func preservedPriceAfterTheRise() {
        #expect(SubscriptionAccess.isEarlyAdopter(state: subscribed, renewalPrice: Decimal(string: "9.99"),
                                                  currentPrice: Decimal(string: "14.99"), dealHasEnded: true))
    }

    @Test("after the rise, a subscriber paying the current price gets no star")
    func currentPriceAfterTheRise() {
        #expect(!SubscriptionAccess.isEarlyAdopter(state: subscribed, renewalPrice: Decimal(string: "14.99"),
                                                   currentPrice: Decimal(string: "14.99"), dealHasEnded: true))
    }

    @Test("after the rise, an unknown price shows no star rather than a guess")
    func unknownPriceAfterTheRise() {
        #expect(!SubscriptionAccess.isEarlyAdopter(state: subscribed, renewalPrice: nil,
                                                   currentPrice: 14.99, dealHasEnded: true))
        #expect(!SubscriptionAccess.isEarlyAdopter(state: subscribed, renewalPrice: 9.99,
                                                   currentPrice: nil, dealHasEnded: true))
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
