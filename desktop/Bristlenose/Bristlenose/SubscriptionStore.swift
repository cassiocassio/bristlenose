import Foundation
import StoreKit
import os

/// The StoreKit 2 side of the subscription: loads the product, reads the
/// current entitlement, listens for renewals and refunds, buys and restores.
/// Every decision about what the state *allows* lives in `SubscriptionAccess`.
///
/// **Wired** through `SubscriptionGate` (`PaywallGate.swift`), which the app owns
/// like `ServeFleet`, so renewals, refunds and Ask to Buy approvals are observed
/// from launch and `refresh()` runs again on app activation. It is created ONLY
/// through `make(channel:)`, which returns nil unless the channel is
/// `.appStoreOrTestFlight`: a `.dmg` must never call StoreKit (Restore can
/// prompt an Apple ID sign-in).
///
/// Any introductory-price or scheduled-price arrangement is configured in App
/// Store Connect on this one product; this code reads entitlements, not prices.
@MainActor
final class SubscriptionStore: ObservableObject {

    @Published private(set) var state: SubscriptionAccess.State = .unknown
    @Published private(set) var product: Product?
    /// Whether this Apple Account can still take the free trial (Apple allows
    /// one per account). Decides which wording the paywall uses.
    @Published private(set) var introEligible = false

    /// The product's free-trial period as `SubscriptionAccess` takes it, or nil
    /// when App Store Connect offers no free trial (an introductory offer that
    /// is a discounted price, not free, is also nil). Eligibility alone is not
    /// enough to promise a trial: `isEligibleForIntroOffer` answers for the
    /// account and the group, whatever the product offers.
    var freeTrial: (unit: SubscriptionAccess.PeriodUnit, value: Int)? {
        guard let offer = product?.subscription?.introductoryOffer,
              offer.paymentMode == .freeTrial else { return nil }
        let unit: SubscriptionAccess.PeriodUnit
        switch offer.period.unit {
        case .day: unit = .day
        case .week: unit = .week
        case .month: unit = .month
        case .year: unit = .year
        @unknown default: return nil
        }
        return (unit, offer.period.value * max(offer.periodCount, 1))
    }

    /// When this person became an early adopter (the start of their unbroken
    /// run of subscription), or nil if they are not one. Drives the
    /// early-adopter star; the rule is `SubscriptionAccess.earlyAdopterSince`.
    @Published private(set) var earlyAdopterSince: Date?

    private var updates: Task<Void, Never>?
    private let log = Logger(subsystem: "app.bristlenose", category: "subscription")
    private let reads: Reads

    /// What the store reads from StoreKit, behind a seam so a test can decide
    /// the order in which overlapping reads come back.
    struct Reads {
        var product: () async throws -> Product?
        var eligible: (Product) async -> Bool
        var entitlements: () async -> [SubscriptionAccess.EntitlementRead]
        var history: () async -> [SubscriptionAccess.Period]

        static let live = Reads(
            product: { try await Product.products(for: [SubscriptionAccess.monthlyProductID]).first },
            eligible: { await $0.subscription?.isEligibleForIntroOffer ?? false },
            entitlements: {
                var reads: [SubscriptionAccess.EntitlementRead] = []
                for await result in Transaction.currentEntitlements {
                    switch result {
                    case .verified(let t):
                        if let e = SubscriptionStore.entitlement(t) { reads.append(.verified(e)) }
                    case .unverified(let t, _):
                        reads.append(.unverified(productID: t.productID))
                    }
                }
                return reads
            },
            history: { await SubscriptionStore.history() }
        )
    }

    /// Each `refresh()` takes the next number; only the newest publishes.
    /// Refreshes overlap (launch, activation, `Transaction.updates`, a
    /// purchase), and an older one that comes back last, say one that read
    /// the entitlements before a purchase landed, would otherwise put the
    /// state back. Not serialised: a refresh stalled on `Product.products`
    /// must not hold up the ones behind it. A refresh begun before a purchase
    /// cannot undo it either: it reads `verifiedPurchase` after its awaits.
    private var generation = 0
    /// The newest generation that has published.
    private var publishedGeneration = 0
    /// Refreshes that lost to a newer one, waiting for it to publish: a caller
    /// reads `state` straight after `await refresh()` (Restore, Try Again),
    /// and must read an answer at least as fresh as its own call.
    private var outpaced: [(generation: Int, token: UUID, done: CheckedContinuation<Void, Never>)] = []

    /// The purchase this app last saw verified, counted as an entitlement
    /// until the store's own record lists it (`SubscriptionAccess.including`).
    private var verifiedPurchase: SubscriptionAccess.Entitlement?

    /// The only way the app makes a store. nil off the App Store channel, so a
    /// `.dmg`, a debug build and the command line never reach StoreKit.
    static func make(channel: DistributionChannel) -> SubscriptionStore? {
        channel == .appStoreOrTestFlight ? SubscriptionStore() : nil
    }

    /// A store frozen in a given state, with no StoreKit listener. For tests.
    init(frozenAt state: SubscriptionAccess.State, earlyAdopterSince: Date? = nil) {
        self.state = state
        self.earlyAdopterSince = earlyAdopterSince
        self.reads = .live
    }

    /// A store that reads through `reads`, with no StoreKit listener and no
    /// first refresh. For tests.
    init(reads: Reads) {
        self.reads = reads
    }

    private init() {
        reads = .live
        updates = Task { [weak self] in
            for await result in Transaction.updates {
                if case .verified(let transaction) = result {
                    await transaction.finish()
                    // An Ask to Buy approval, or a purchase made on another
                    // Mac, arrives here, and the store's record lags it as it
                    // lags a purchase made in the sheet: take it from the
                    // transaction. A refund of the product arrives here too.
                    if transaction.productID == SubscriptionAccess.monthlyProductID {
                        if transaction.revocationDate != nil {
                            self?.verifiedPurchase = nil
                        } else {
                            _ = self?.accept(transaction)
                        }
                    }
                }
                await self?.refresh()
            }
        }
        Task { [weak self] in await self?.refresh() }
    }

    deinit { updates?.cancel() }

    /// A verified transaction as an entitlement to the product, or nil when
    /// it is another product's, refunded, or already expired.
    nonisolated static func entitlement(_ t: Transaction, now: Date = Date()) -> SubscriptionAccess.Entitlement? {
        guard t.productID == SubscriptionAccess.monthlyProductID, t.revocationDate == nil,
              (t.expirationDate ?? .distantFuture) > now else { return nil }
        return .init(productID: t.productID, start: t.purchaseDate, expires: t.expirationDate,
                     inTrial: t.offer?.type == .introductory)
    }

    /// Take the entitlement from a verified transaction, now, rather than
    /// waiting for the store's record to list it. False when the transaction
    /// grants nothing. Internal so the StoreKit suite can drive it.
    @discardableResult
    func accept(_ transaction: Transaction) -> Bool {
        guard let e = Self.entitlement(transaction) else { return false }
        accept(e)
        return true
    }

    /// The StoreKit-free half of `accept(_:)`, for tests.
    func accept(_ entitlement: SubscriptionAccess.Entitlement) {
        verifiedPurchase = entitlement
        state = .subscribed(expires: entitlement.expires, inTrial: entitlement.inTrial)
    }

    /// Ask the store for the product and the current entitlement. If the
    /// product did not load and there is no entitlement, the state is
    /// `.storeUnavailable`, not `.notSubscribed`. An entitlement wins either
    /// way: `currentEntitlements` is read from StoreKit's on-device record.
    func refresh() async {
        generation += 1
        let mine = generation
        if product == nil {
            do {
                let loaded = try await reads.product()
                // Another refresh may have loaded it meanwhile; keep the first.
                if product == nil { product = loaded }
                if loaded == nil {
                    log.error("store returned no product for \(SubscriptionAccess.monthlyProductID, privacy: .public)")
                }
            } catch {
                log.error("product load failed: \(error.localizedDescription, privacy: .public)")
            }
        }
        let loadedProduct = product

        // Read now, published with the state below: published here, a trial
        // purchase flipped the open sheet to the lapsed wording while the
        // entitlement was still being read.
        var eligible: Bool?
        if let loadedProduct, loadedProduct.subscription != nil {
            eligible = await reads.eligible(loadedProduct)
        }

        let rows = await reads.entitlements()
        let listed = rows.compactMap { row -> SubscriptionAccess.Entitlement? in
            if case .verified(let e) = row { return e }
            return nil
        }
        let entitled = SubscriptionAccess.including(verifiedPurchase, in: listed, now: Date())
        let newState = SubscriptionAccess.state(entitlements: entitled,
                                                productLoaded: loadedProduct != nil)
        // Work the star out before publishing anything, then publish the state
        // and the star together, so neither blinks between two refreshes. The
        // current entitlement is added to the history so an active subscriber
        // always has a run, even if the history read comes back empty.
        var since: Date?
        if case .subscribed = newState {
            let current = entitled.filter { $0.productID == SubscriptionAccess.monthlyProductID }
                .map { SubscriptionAccess.Period(start: $0.start, end: $0.expires) }
            since = SubscriptionAccess.earlyAdopterSince(state: newState,
                                                         history: await reads.history() + current)
        }

        guard mine == generation else {
            log.debug("refresh superseded by a newer one; not published")
            await newerPublish(after: mine)
            return
        }
        if listed.contains(where: { $0.productID == verifiedPurchase?.productID }) {
            verifiedPurchase = nil  // the store's record has caught up
        }
        if let eligible { introEligible = eligible }
        state = newState
        earlyAdopterSince = since
        published(mine)
    }

    private func published(_ generation: Int) {
        publishedGeneration = generation
        let ready = outpaced.filter { $0.generation <= generation }
        outpaced.removeAll { $0.generation <= generation }
        ready.forEach { $0.done.resume() }
    }

    /// Wait until a refresh newer than `generation` has published, for up to
    /// `patience`: bounded, so a newer refresh stalled on `Product.products`
    /// does not hold this caller for ever.
    private func newerPublish(after generation: Int, patience: Duration = .seconds(10)) async {
        guard publishedGeneration < generation else { return }
        let token = UUID()
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            outpaced.append((generation, token, done))
            Task { @MainActor [weak self] in
                try? await Task.sleep(for: patience)
                guard let self, let i = self.outpaced.firstIndex(where: { $0.token == token }) else { return }
                self.log.notice("refresh outpaced, and the newer one has not published after \(String(describing: patience), privacy: .public)")
                self.outpaced.remove(at: i).done.resume()
            }
        }
    }

    /// Every period of the subscription in the store's history, from
    /// `Transaction.all` ("auto-renewable subscriptions, including all
    /// renewals"). Refunded periods are left out. Internal (not private) so the
    /// StoreKitTest suite can read what the store really returns.
    static func history() async -> [SubscriptionAccess.Period] {
        var periods: [SubscriptionAccess.Period] = []
        for await result in Transaction.all {
            guard case .verified(let t) = result, t.revocationDate == nil,
                  t.productID == SubscriptionAccess.monthlyProductID else { continue }
            periods.append(.init(start: t.purchaseDate, end: t.expirationDate))
        }
        return periods
    }

    /// **Under a test host, nothing here can ask for an Apple Account.**
    /// `purchase()` and `restore()` are the two calls that can raise the
    /// system's App Store sign-in window, and a test that reaches them gets
    /// Apple's real store, not `Bristlenose.storekit`: on 25 Nov 2026 a
    /// `store.purchase()` case in `EarlyAdopterStoreKitTests` put an "Sign in
    /// to your Apple Account" window on the developer's screen, attributed to
    /// the Debug app (the log shows an AMS "In App" authentication). A test
    /// that wants a purchase buys through its `SKTestSession` instead.
    /// Debug only, so the shipped app can never mistake itself for a test.
    /// Same detector as the keychain's (`KeychainHelper.isUnderTestHost`).
    static var refusesSignInPrompts: Bool {
        #if DEBUG
        return KeychainHelper.isUnderTestHost
        #else
        return false
        #endif
    }

    enum PurchaseOutcome: Equatable { case subscribed, cancelled, pending, failed }

    func purchase() async -> PurchaseOutcome {
        if Self.refusesSignInPrompts {
            log.error("purchase refused under a test host: it would reach the real App Store")
            return .failed
        }
        guard let product else { return .failed }
        do {
            switch try await product.purchase() {
            case .success(let verification):
                guard case .verified(let t) = verification else { return .failed }
                await t.finish()
                // The verified transaction is the entitlement. The store's own
                // record lists it about a second later, and reading that record
                // instead told a buyer who had just paid that it failed.
                guard accept(t) else {
                    log.error("purchase verified, but it grants no entitlement to the product")
                    return .failed
                }
                await refresh()
                // Report what the gate will actually do, not what the store said.
                if case .subscribed = state { return .subscribed }
                return .failed
            case .userCancelled:
                return .cancelled
            case .pending:
                return .pending
            @unknown default:
                return .failed
            }
        } catch {
            log.error("purchase failed: \(error.localizedDescription, privacy: .public)")
            return .failed
        }
    }

    /// Restore Purchases (Guideline 3.1.1 requires it on the paywall).
    func restore() async {
        if Self.refusesSignInPrompts {
            log.error("restore's AppStore.sync() skipped under a test host: it would ask for an Apple Account")
        } else {
            do { try await AppStore.sync() } catch {
                log.error("restore failed: \(error.localizedDescription, privacy: .public)")
            }
        }
        await refresh()
    }
}
