import Foundation
import Security
import StoreKit
import StoreKitTest
import Testing

@testable import Bristlenose

// The early-adopter rule against StoreKit's own local test store, with no App
// Store Connect and no real money. `SubscriptionAccessTests` proves the date
// arithmetic on hand-built histories; this suite proves the other half: that
// what `SubscriptionStore.history()` reads from `Transaction.all` after real
// (local) purchases, renewals, lapses and refunds is the history the rule
// expects.
//
// Purchases are backdated with `PurchaseOption.purchaseDate(_:renewalBehavior:)`
// (StoreKitTest, macOS 14), which makes StoreKit generate the renewals up to
// now (`.renewUntilNow`) or stop after one period (`.cancelImmediately`). That
// is how a 30- or 90-day lapse is built in a test that runs in seconds. The
// product in `Bristlenose.storekit` starts with a one-week free trial.

// StoreKit's local test store answers only a team-signed test host: an unsigned one (CI=1,
// `CODE_SIGNING_ALLOWED=NO`, which is GitHub's Mac runner and the guest matrix) gets
// `.notEntitled` from every purchase. So this suite runs in a signed local run and is skipped,
// by name, in an unsigned one. Found red on both guests on 24 Nov 2026, two days after it landed.
enum StoreKitTestHost {
    /// Whether this test process carries a Team ID in its signature.
    static var isTeamSigned: Bool {
        var code: SecCode?
        guard SecCodeCopySelf([], &code) == errSecSuccess, let code else { return false }
        var staticCode: SecStaticCode?
        guard SecCodeCopyStaticCode(code, [], &staticCode) == errSecSuccess, let staticCode else {
            return false
        }
        var info: CFDictionary?
        guard SecCodeCopySigningInformation(staticCode, SecCSFlags(rawValue: kSecCSSigningInformation),
                                            &info) == errSecSuccess,
              let dict = info as? [String: Any] else { return false }
        return (dict[kSecCodeInfoTeamIdentifier as String] as? String)?.isEmpty == false
    }
}

@MainActor
@Suite("Early adopters against the local StoreKit test store", .serialized,
       .enabled(if: StoreKitTestHost.isTeamSigned,
                "StoreKit's test store needs a team-signed host; this run is unsigned"))
struct EarlyAdopterStoreKitTests {

    private let id = SubscriptionAccess.monthlyProductID
    private let day: TimeInterval = 24 * 60 * 60
    private let session: SKTestSession

    init() throws {
        let file = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Bristlenose.storekit")
        session = try SKTestSession(contentsOf: file)
        session.disableDialogs = true
        session.resetToDefaultState()
        session.clearTransactions()
    }

    private func ago(_ days: Double) -> Date { Date().addingTimeInterval(-days * day) }

    /// Start from a history that is empty and STAYS empty. A `.renewUntilNow` purchase makes
    /// StoreKit's test store write its backdated renewals a beat at a time, after the call
    /// returns, so an earlier case's renewals keep landing after this case's
    /// `clearTransactions()` (25 Nov 2026: 4 of 6 solo runs read a previous case's 300-day
    /// run; waiting for one empty read did not help). Clear, and clear again whenever a late
    /// renewal shows up, until the history has read empty for half a second running.
    private func clean() async {
        var quietSince: Date?
        for _ in 0..<100 {
            if await SubscriptionStore.history().isEmpty {
                if let q = quietSince, Date().timeIntervalSince(q) >= 0.5 { return }
                if quietSince == nil { quietSince = Date() }
            } else {
                session.clearTransactions()
                quietSince = nil
            }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        // Ten seconds without half a second of quiet: the case would start on
        // another case's transactions, so say so rather than pass on them.
        Issue.record("the test store's history never settled empty; this case may read another's")
    }

    @discardableResult
    private func buy(daysAgo: Double,
                     _ behavior: Product.PurchaseOption.SubscriptionRenewalBehavior) async throws -> Transaction {
        let t = try await session.buyProduct(identifier: id,
                                             options: [.purchaseDate(ago(daysAgo), renewalBehavior: behavior)])
        if behavior == .renewUntilNow { await renewalsReachToday() }
        return t
    }

    /// `.renewUntilNow` writes its backdated renewals a beat at a time after the
    /// purchase returns, and a history read in between has a gap that reads as
    /// a lapse (25 Nov 2026: `continuousEarlyAdopter` failed 1 run in 3 on it).
    /// Wait until a period runs past now, which only the last renewal does.
    private func renewalsReachToday() async {
        for _ in 0..<50 {
            if await SubscriptionStore.history().contains(where: { ($0.end ?? .distantFuture) > Date() }) { return }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        Issue.record("the test store's renewals never reached today")
    }

    private func since(dealEndedDaysAgo: Double) async -> Date? {
        SubscriptionAccess.earlyAdopterSince(state: .subscribed(expires: nil),
                                             history: await SubscriptionStore.history(),
                                             dealEnds: ago(dealEndedDaysAgo))
    }

    /// Within a day: StoreKit stamps its own times on backdated purchases.
    private func near(_ a: Date?, _ b: Date) -> Bool {
        guard let a else { return false }
        return abs(a.timeIntervalSince(b)) < day
    }

    @Test("the store's history holds every renewal of a long subscription")
    func historyHasTheRenewals() async throws {
        await clean()
        try await buy(daysAgo: 200, .renewUntilNow)
        let history = await SubscriptionStore.history()
        // A one-week trial, then about six monthly periods.
        #expect(history.count >= 6)
        #expect(history.allSatisfy { $0.end != nil })
    }

    @Test("subscribed since before the deal ended: an early adopter, dated from the first purchase")
    func continuousEarlyAdopter() async throws {
        await clean()
        try await buy(daysAgo: 300, .renewUntilNow)
        #expect(near(await since(dealEndedDaysAgo: 100), ago(300)))
    }

    @Test("subscribed only after the deal ended: no star")
    func newcomer() async throws {
        await clean()
        try await buy(daysAgo: 20, .renewUntilNow)
        #expect(await since(dealEndedDaysAgo: 100) == nil)
    }

    @Test("a 30-day lapse keeps the run, so the star stays")
    func shortLapse() async throws {
        await clean()
        // A one-week trial, then cancelled: expires about 193 days ago.
        try await buy(daysAgo: 200, .cancelImmediately)
        try await buy(daysAgo: 163, .renewUntilNow)
        #expect(near(await since(dealEndedDaysAgo: 170), ago(200)))
    }

    @Test("a 90-day lapse breaks the run: they came back after the deal, so no star")
    func longLapse() async throws {
        await clean()
        try await buy(daysAgo: 300, .cancelImmediately)
        try await buy(daysAgo: 200, .renewUntilNow)
        #expect(await since(dealEndedDaysAgo: 250) == nil)
    }

    /// Two periods, one refunded. The store keeps the refunded transaction,
    /// marked revoked, so the history's own `revocationDate` guard is what
    /// leaves it out: without the guard the count is 2. (The earlier version
    /// refunded the only purchase and asserted an empty history, which a store
    /// that simply dropped refunds would also have passed.)
    @Test("a refunded purchase is not part of the history")
    func refundIsLeftOut() async throws {
        await clean()
        try await buy(daysAgo: 100, .cancelImmediately)
        let refunded = try await buy(daysAgo: 3, .cancelImmediately)
        try session.refundTransaction(identifier: UInt(refunded.id))
        #expect(await revoked(refunded.id), "the store should keep the refund, marked revoked")
        #expect(await SubscriptionStore.history().count == 1)
    }

    /// Whether `Transaction.all` lists this transaction as revoked, allowing
    /// the test store a moment to write the refund.
    private func revoked(_ id: UInt64) async -> Bool {
        for _ in 0..<20 {
            for await result in Transaction.all {
                if case .verified(let t) = result, t.id == id, t.revocationDate != nil { return true }
            }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        return false
    }

    // MARK: - The store the app uses, against the local test store
    //
    // `refresh`, `purchase` and expiry had never been run against a store
    // (review, 25 Nov 2026). These drive `SubscriptionStore` itself, made the
    // way the App Store build makes it.

    private func appStoreStore() async throws -> SubscriptionStore {
        let store = try #require(SubscriptionStore.make(channel: .appStoreOrTestFlight))
        await store.refresh()
        return store
    }

    @Test("a newcomer sees the product, a one-week free trial, and is not subscribed")
    func newcomerSeesTheOffer() async throws {
        await clean()
        let store = try await appStoreStore()
        #expect(store.product != nil)
        #expect(store.state == .notSubscribed)
        #expect(store.introEligible)
        #expect(store.freeTrial?.unit == .week && store.freeTrial?.value == 1)
    }

    // NEVER call `store.purchase()` or `store.restore()` here. From a test host
    // they reach Apple's real store, not `Bristlenose.storekit`: on 25 Nov 2026
    // a `store.purchase()` case put an Apple Account sign-in window on the
    // developer's screen, waited a minute and failed (SKServiceErrorDomain 2).
    // Both now refuse under a test host (`SubscriptionStore.refusesSignInPrompts`),
    // and the Purchase button is proven by hand in TestFlight. These buy through
    // the test session instead and check what the app's store makes of it.

    /// `purchase()`'s own sequence after a verified transaction: finish it,
    /// then `refreshAfterPurchase()`. Straight after `finish()` a single
    /// `refresh()` reads not subscribed (measured 25 Nov 2026), so `purchase()`
    /// told a buyer who had just paid that it failed; this fails if
    /// `refreshAfterPurchase` goes back to reading once.
    @Test("a finished purchase reads as subscribed, so a buyer is never told it failed")
    func purchaseIsSeen() async throws {
        await clean()
        let store = try await appStoreStore()
        try await buy(daysAgo: 0, .renewUntilNow).finish()
        await store.refreshAfterPurchase()
        guard case .subscribed = store.state else {
            Issue.record("state after purchase: \(store.state)"); return
        }
    }

    // No expiry case here: `session.expireSubscription` left the entitlement
    // unexpired for 3 s and more (25 Nov 2026), so it proves nothing about the
    // app. Expiry is a date rule, covered in `SubscriptionAccessTests`.
}
