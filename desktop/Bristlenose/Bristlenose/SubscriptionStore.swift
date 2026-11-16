import Foundation
import StoreKit
import os

/// The StoreKit 2 side of the subscription: loads the product, reads the
/// current entitlement, listens for renewals and refunds, buys and restores.
/// Every decision about what the state *allows* lives in `SubscriptionAccess`.
///
/// **Not wired into the app yet.** When it is: own it at app level (like
/// `ServeFleet`) so renewals, refunds and Ask to Buy approvals are observed
/// from launch, create it ONLY when `DistributionChannel.current ==
/// .appStoreOrTestFlight` (a `.dmg` must never call StoreKit: Restore can
/// prompt an Apple ID sign-in), and call `refresh()` again on app activation
/// so a subscription that lapses while the app stays open is noticed.
///
/// Any introductory-price or scheduled-price arrangement is configured in App
/// Store Connect on this one product; this code reads entitlements, not prices.
@MainActor
final class SubscriptionStore: ObservableObject {

    @Published private(set) var state: SubscriptionAccess.State = .unknown
    @Published private(set) var product: Product?

    private var updates: Task<Void, Never>?
    private let log = Logger(subsystem: "app.bristlenose", category: "subscription")

    init() {
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
    /// product did not load, the store has not positively answered, and the
    /// state is `.unknown` (allowed), not `.notSubscribed`.
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

        var ids: Set<String> = []
        var expirations: [String: Date] = [:]
        var trials: Set<String> = []
        for await result in Transaction.currentEntitlements {
            guard case .verified(let t) = result, t.revocationDate == nil else { continue }
            ids.insert(t.productID)
            if let end = t.expirationDate { expirations[t.productID] = end }
            if t.offer?.type == .introductory { trials.insert(t.productID) }
        }
        state = SubscriptionAccess.state(entitledProductIDs: ids,
                                         expirations: expirations,
                                         trialProductIDs: trials,
                                         productLoaded: product != nil)
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
