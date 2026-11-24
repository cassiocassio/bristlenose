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

    @discardableResult
    private func buy(daysAgo: Double,
                     _ behavior: Product.PurchaseOption.SubscriptionRenewalBehavior) async throws -> Transaction {
        try await session.buyProduct(identifier: id,
                                     options: [.purchaseDate(ago(daysAgo), renewalBehavior: behavior)])
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
        try await buy(daysAgo: 200, .renewUntilNow)
        let history = await SubscriptionStore.history()
        // A one-week trial, then about six monthly periods.
        #expect(history.count >= 6)
        #expect(history.allSatisfy { $0.end != nil })
    }

    @Test("subscribed since before the deal ended: an early adopter, dated from the first purchase")
    func continuousEarlyAdopter() async throws {
        try await buy(daysAgo: 300, .renewUntilNow)
        #expect(near(await since(dealEndedDaysAgo: 100), ago(300)))
    }

    @Test("subscribed only after the deal ended: no star")
    func newcomer() async throws {
        try await buy(daysAgo: 20, .renewUntilNow)
        #expect(await since(dealEndedDaysAgo: 100) == nil)
    }

    @Test("a 30-day lapse keeps the run, so the star stays")
    func shortLapse() async throws {
        // A one-week trial, then cancelled: expires about 193 days ago.
        try await buy(daysAgo: 200, .cancelImmediately)
        try await buy(daysAgo: 163, .renewUntilNow)
        #expect(near(await since(dealEndedDaysAgo: 170), ago(200)))
    }

    @Test("a 90-day lapse breaks the run: they came back after the deal, so no star")
    func longLapse() async throws {
        try await buy(daysAgo: 300, .cancelImmediately)
        try await buy(daysAgo: 200, .renewUntilNow)
        #expect(await since(dealEndedDaysAgo: 250) == nil)
    }

    @Test("a refunded purchase is not part of the history")
    func refundIsLeftOut() async throws {
        let t = try await buy(daysAgo: 3, .cancelImmediately)
        try session.refundTransaction(identifier: UInt(t.id))
        #expect(await SubscriptionStore.history().isEmpty)
    }
}
