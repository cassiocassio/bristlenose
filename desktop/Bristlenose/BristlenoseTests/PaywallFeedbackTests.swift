import Foundation
import Testing

@testable import Bristlenose

// What the paywall says after Try Again or Restore Purchases fails. Review,
// 25 Nov 2026: on the store-unavailable face a press that still failed changed
// nothing on screen, and a restore that never reached the store said "No
// subscription found", which tells a researcher who has paid the wrong thing.
// Owner, 27 Nov 2026: option B, the offer face's message line on both faces.

@MainActor
@Suite("Paywall feedback after Try Again and Restore")
struct PaywallFeedbackTests {

    typealias Message = PaywallView.Message
    private let live = SubscriptionAccess.Entitlement(
        productID: SubscriptionAccess.monthlyProductID, start: Date().addingTimeInterval(-60),
        expires: Date().addingTimeInterval(30 * 24 * 60 * 60), inTrial: false)

    // MARK: The message each outcome shows

    @Test("Try Again that still cannot reach the store says so")
    func tryAgainStillUnavailable() {
        #expect(Message.after(.tryAgain, state: .storeUnavailable, productLoaded: false)
                == "desktop.subscription.stillUnavailable")
    }

    @Test("Try Again that reaches the store shows the offer, with no message")
    func tryAgainReached() {
        #expect(Message.after(.tryAgain, state: .notSubscribed, productLoaded: true) == nil)
    }

    @Test("a Restore that could not reach the store says so, on either face")
    func restoreNotReached() {
        #expect(Message.after(.restore(reached: false), state: .notSubscribed, productLoaded: true)
                == "desktop.subscription.restoreFailed")
        #expect(Message.after(.restore(reached: false), state: .storeUnavailable, productLoaded: false)
                == "desktop.subscription.restoreFailed")
    }

    @Test("a Restore that reached the store and found nothing says no subscription was found")
    func restoreFoundNothing() {
        #expect(Message.after(.restore(reached: true), state: .notSubscribed, productLoaded: true)
                == "desktop.subscription.notFound")
        // The store answered the restore though the product did not load:
        // it still found nothing, so the sheet says so.
        #expect(Message.after(.restore(reached: true), state: .storeUnavailable, productLoaded: false)
                == "desktop.subscription.notFound")
    }

    @Test("a subscription found by either button closes the sheet, with no message")
    func subscribedSaysNothing() {
        let subscribed = SubscriptionAccess.State.subscribed(expires: live.expires, inTrial: false)
        #expect(Message.after(.tryAgain, state: subscribed, productLoaded: false) == nil)
        #expect(Message.after(.restore(reached: true), state: subscribed, productLoaded: true) == nil)
        #expect(Message.after(.restore(reached: false), state: subscribed, productLoaded: true) == nil)
    }

    @Test("every message key has an English value")
    func keysExist() {
        let locales = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("bristlenose/locales")
        let i = I18n()
        i.configure(localesDirectory: locales)
        i.setLocale("en")
        for key in ["desktop.subscription.stillUnavailable", "desktop.subscription.restoreFailed",
                    "desktop.subscription.notFound"] {
            #expect(i.t(key) != key, "\(key) has no English value")
        }
    }

    // MARK: Whether Restore reached the store

    private func store(sync: @escaping () async throws -> Void,
                       entitlements: [SubscriptionAccess.EntitlementRead] = []) -> SubscriptionStore {
        SubscriptionStore(reads: .init(
            product: { nil }, eligible: { _ in false }, entitlements: { entitlements },
            history: { [] }, sync: sync))
    }

    struct Offline: Error {}

    @Test("Restore reports that the store answered, and refreshes")
    func restoreReached() async {
        let s = store(sync: {}, entitlements: [.verified(live)])
        #expect(await s.restore())
        #expect(s.state == .subscribed(expires: live.expires, inTrial: false))
    }

    @Test("Restore reports that the store could not be reached, and still refreshes")
    func restoreThrew() async {
        let s = store(sync: { throw Offline() }, entitlements: [.verified(live)])
        #expect(await s.restore() == false)
        #expect(s.state == .subscribed(expires: live.expires, inTrial: false),
                "a restore that could not sync still reads what the Mac already holds")
    }

    @Test("a store built for a test never reaches the App Store")
    func defaultSyncNeverReaches() async {
        let s = SubscriptionStore(reads: .init(
            product: { nil }, eligible: { _ in false }, entitlements: { [] }, history: { [] }))
        #expect(await s.restore() == false)
    }
}
