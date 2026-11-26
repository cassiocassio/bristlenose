import Foundation
import Testing

@testable import Bristlenose

// What `SubscriptionStore` publishes when its reads overlap or lag, with the
// reads faked so their order is the test's to choose. Review, 25 Nov 2026: a
// purchase that charged could still report "failed", from the store's record
// lagging the purchase and from an older refresh landing after a newer one.
// The paths App Review's sandbox purchase takes.

@MainActor
@Suite("The subscription store's reads, overlapping and lagging")
struct SubscriptionStoreRefreshTests {

    private let id = SubscriptionAccess.monthlyProductID
    private let live = SubscriptionAccess.Entitlement(
        productID: SubscriptionAccess.monthlyProductID, start: Date().addingTimeInterval(-60),
        expires: Date().addingTimeInterval(30 * 24 * 60 * 60), inTrial: true)

    /// Entitlement reads that answer in the order the test releases them.
    @MainActor
    final class Script {
        private var held: [Int: CheckedContinuation<Void, Never>] = [:]
        /// What each read returns, in call order; past the end, the last.
        var answers: [[SubscriptionAccess.EntitlementRead]]
        /// Which calls wait for `release()` before answering.
        var holds: Set<Int>
        private(set) var calls = 0
        var waiting: Int { held.count }

        init(_ answers: [[SubscriptionAccess.EntitlementRead]], holds: Set<Int> = []) {
            self.answers = answers
            self.holds = holds
        }

        func read() async -> [SubscriptionAccess.EntitlementRead] {
            let n = calls
            calls += 1
            if holds.contains(n) {
                await withCheckedContinuation { held[n] = $0 }
            }
            return answers[min(n, answers.count - 1)]
        }

        func release() {
            let all = held
            held = [:]
            all.values.forEach { $0.resume() }
        }

        func release(call n: Int) {
            held.removeValue(forKey: n)?.resume()
        }
    }

    private func store(_ script: Script) -> SubscriptionStore {
        SubscriptionStore(reads: .init(
            product: { nil },
            eligible: { _ in false },
            entitlements: { await script.read() },
            history: { [] }
        ))
    }

    private func until(_ condition: () -> Bool) async {
        for _ in 0..<200 {
            if condition() { return }
            try? await Task.sleep(for: .milliseconds(5))
        }
    }

    @Test("an older refresh that comes back last does not put the state back")
    func olderRefreshLandsLast() async {
        // The first read began before the purchase and sees nothing; the
        // second, after it, sees the entitlement.
        let script = Script([[], [.verified(live)]], holds: [0])
        let s = store(script)
        let older = Task { await s.refresh() }
        await until { script.waiting == 1 }
        await s.refresh()
        #expect(s.state == .subscribed(expires: live.expires, inTrial: true))
        script.release()
        await older.value
        #expect(s.state == .subscribed(expires: live.expires, inTrial: true),
                "the slower, older read overwrote the newer one")
    }

    /// Seen in the StoreKit suite, 26 Nov 2026: the store's own launch refresh
    /// began just after the caller's, so the caller's returned unpublished and
    /// it read `.unknown`. Restore and Try Again read `state` this way.
    @Test("a refresh that a newer one overtakes returns only once the newer one has published")
    func outpacedRefreshWaitsForTheNewer() async {
        let script = Script([[], [.verified(live)]], holds: [0, 1])
        let s = store(script)
        final class Flag { var done = false }
        let olderDone = Flag()
        let older = Task { @MainActor in await s.refresh(); olderDone.done = true }
        await until { script.waiting == 1 }
        let newer = Task { await s.refresh() }
        await until { script.waiting == 2 }
        script.release(call: 0)
        try? await Task.sleep(for: .milliseconds(100))
        #expect(!olderDone.done, "the overtaken refresh returned before any answer as fresh as its call")
        script.release(call: 1)
        await older.value
        #expect(s.state == .subscribed(expires: live.expires, inTrial: true))
        await newer.value
    }

    @Test("a verified purchase reads as subscribed before the store's record lists it")
    func verifiedPurchaseBeforeTheRecord() async {
        let script = Script([[]])  // the store's record lags: lists nothing
        let s = store(script)
        s.accept(live)
        #expect(s.state == .subscribed(expires: live.expires, inTrial: true))
        await s.refresh()
        #expect(s.state == .subscribed(expires: live.expires, inTrial: true),
                "a refresh in the store's lag told a buyer who had paid that they had not")
    }

    @Test("a refresh begun before the purchase cannot undo it")
    func refreshBegunBeforeThePurchase() async {
        let script = Script([[]], holds: [0])
        let s = store(script)
        let before = Task { await s.refresh() }
        await until { script.waiting == 1 }
        s.accept(live)
        script.release()
        await before.value
        #expect(s.state == .subscribed(expires: live.expires, inTrial: true))
    }

    @Test("an unverified entitlement grants nothing")
    func unverifiedGrantsNothing() async {
        let s = store(Script([[.unverified(productID: id)]]))
        await s.refresh()
        #expect(s.state == .storeUnavailable)
    }
}
