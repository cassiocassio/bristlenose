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

    /// The only way the app makes a store. nil off the App Store channel, so a
    /// `.dmg`, a debug build and the command line never reach StoreKit.
    static func make(channel: DistributionChannel) -> SubscriptionStore? {
        channel == .appStoreOrTestFlight ? SubscriptionStore() : nil
    }

    /// A store frozen in a given state, with no StoreKit listener. For tests.
    init(frozenAt state: SubscriptionAccess.State, earlyAdopterSince: Date? = nil) {
        self.state = state
        self.earlyAdopterSince = earlyAdopterSince
    }

    private init() {
        updates = Task { [weak self] in
            for await result in Transaction.updates {
                if case .verified(let transaction) = result {
                    await transaction.finish()
                }
                await self?.refresh()
            }
        }
        Task { [weak self] in await self?.refresh() }
    }

    deinit { updates?.cancel() }

    /// Ask the store for the product and the current entitlement. If the
    /// product did not load and there is no entitlement, the state is
    /// `.storeUnavailable`, not `.notSubscribed`. An entitlement wins either
    /// way: `currentEntitlements` is read from StoreKit's on-device record.
    func refresh() async {
        if product == nil {
            do {
                product = try await Product.products(for: [SubscriptionAccess.monthlyProductID]).first
                if product == nil {
                    log.error("store returned no product for \(SubscriptionAccess.monthlyProductID, privacy: .public)")
                }
            } catch {
                log.error("product load failed: \(error.localizedDescription, privacy: .public)")
            }
        }

        if let sub = product?.subscription {
            introEligible = await sub.isEligibleForIntroOffer
        }

        var ids: Set<String> = []
        var expirations: [String: Date] = [:]
        var trials: Set<String> = []
        var entitled: [SubscriptionAccess.Period] = []
        for await result in Transaction.currentEntitlements {
            guard case .verified(let t) = result, t.revocationDate == nil else { continue }
            ids.insert(t.productID)
            if let end = t.expirationDate { expirations[t.productID] = end }
            if t.offer?.type == .introductory { trials.insert(t.productID) }
            if t.productID == SubscriptionAccess.monthlyProductID {
                entitled.append(.init(start: t.purchaseDate, end: t.expirationDate))
            }
        }
        let newState = SubscriptionAccess.state(entitledProductIDs: ids,
                                                expirations: expirations,
                                                trialProductIDs: trials,
                                                productLoaded: product != nil)
        // Work the star out before publishing anything, then publish the state
        // and the star together: two refreshes can overlap (launch, activation,
        // `Transaction.updates`), and publishing in two steps let a slower one
        // put a date back after a faster one had cleared it, or blink the star
        // off for a frame. The current entitlement is added to the history so
        // an active subscriber always has a run, even if the history read
        // comes back empty.
        var since: Date?
        if case .subscribed = newState {
            since = SubscriptionAccess.earlyAdopterSince(state: newState,
                                                         history: await Self.history() + entitled)
        }
        state = newState
        earlyAdopterSince = since
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

    enum PurchaseOutcome: Equatable { case subscribed, cancelled, pending, failed }

    func purchase() async -> PurchaseOutcome {
        guard let product else { return .failed }
        do {
            switch try await product.purchase() {
            case .success(let verification):
                guard case .verified(let t) = verification else { return .failed }
                await t.finish()
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
        do { try await AppStore.sync() } catch {
            log.error("restore failed: \(error.localizedDescription, privacy: .public)")
        }
        await refresh()
    }
}
