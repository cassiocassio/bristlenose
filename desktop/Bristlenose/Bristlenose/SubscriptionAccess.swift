import Foundation

/// What a person's subscription lets them do. Pure logic: no StoreKit import,
/// so every rule here is testable without a store.
///
/// **The rule:** a subscription is needed for work that is sent to an AI
/// provider. Everything else stays free, including opening, reading and hand
/// edits (stars, hides, manual tags) on projects that were already analysed.
/// It lives in one place (`canStartAnalysis` / `canOpenProjects`), so changing
/// it is one line.
///
/// Only the App Store channel is gated. The Developer ID `.dmg`, local debug
/// builds and the command line are not: they never meet this code's paywall.
enum SubscriptionAccess {

    /// The product identifier in App Store Connect. It must match exactly, or
    /// the store returns no product and, for someone with no entitlement,
    /// the state is `.storeUnavailable` (the paywall's "try again" state).
    ///
    /// **One product, for early adopters and everyone after them.** The launch
    /// price is kept for existing subscribers by Apple's own price preservation:
    /// when the price rises, App Store Connect is told to "keep the current
    /// price for existing subscribers". Do NOT add a second "early" product to
    /// retire later: "Remove from Sale" stops renewals as well as sign-ups, so it
    /// would cancel every early adopter (Apple's App Store Connect help, "Set
    /// availability for an auto-renewable subscription"; tried and withdrawn
    /// 21 Nov 2026). The decision record is private to the maintainer.
    static let monthlyProductID = "app.bristlenose.subscription.monthly"

    enum State: Equatable {
        /// Not asked yet (launch, before the first `refresh()` finishes).
        /// Treated as *allowed*, so a slow start never locks anyone out.
        case unknown
        /// The store was asked and the product did not load (offline, a proxy,
        /// or a product that is not live), and no entitlement is on record.
        /// Blocks a start and shows the paywall's "try again" state. Anyone
        /// with an entitlement is `.subscribed` instead, so a paid researcher
        /// is never in this state: the entitlement is read from StoreKit's
        /// local record, not from the network.
        case storeUnavailable
        case notSubscribed
        /// `expires` is for display only. Access is decided by StoreKit's
        /// `currentEntitlements` alone, which already includes billing grace
        /// periods (whose transaction `expirationDate` lies in the past) and
        /// already drops expired subscriptions, so this code never compares
        /// dates against the Mac's clock.
        /// `inTrial`: the current period is Apple's free trial (introductory
        /// offer), so Settings can say when it ends and what is charged after.
        case subscribed(expires: Date?, inTrial: Bool = false)
    }

    /// - Parameter productLoaded: whether the store returned our product. If
    ///   it did not, an empty entitlement set proves nothing about the person,
    ///   so the state is `.storeUnavailable` rather than `.notSubscribed`.
    static func state(entitledProductIDs: Set<String>,
                      expirations: [String: Date],
                      trialProductIDs: Set<String> = [],
                      productLoaded: Bool) -> State {
        if entitledProductIDs.contains(monthlyProductID) {
            return .subscribed(expires: expirations[monthlyProductID],
                               inTrial: trialProductIDs.contains(monthlyProductID))
        }
        return productLoaded ? .notSubscribed : .storeUnavailable
    }

    /// Starting an analysis (a paid LLM run on new recordings).
    static func canStartAnalysis(_ state: State, channel: DistributionChannel) -> Bool {
        guard channel == .appStoreOrTestFlight else { return true }
        switch state {
        case .unknown, .subscribed: return true
        case .notSubscribed, .storeUnavailable: return false
        }
    }

    /// Reading something already analysed. Always allowed: a lapsed
    /// subscription must never hold someone's own work hostage.
    static func canOpenProjects(_ state: State, channel: DistributionChannel) -> Bool {
        true
    }

    // MARK: - Early adopters

    /// Whether the launch deal has ended. **Set to `true` in the app update
    /// that ships with the price rise** (owner, 22 Nov 2026). Until then every
    /// active subscriber is an early adopter; after it, only those Apple still
    /// renews below the current price (see `monthlyProductID` for how the
    /// price is kept). Installs that haven't updated keep the old rule.
    static let earlyDealHasEnded = false

    /// Whether this person is an early adopter, and so gets the star.
    ///
    /// - Parameters:
    ///   - state: the subscription state; only `.subscribed` can qualify, so a
    ///     cancelled subscription keeps the star until its paid period ends.
    ///   - renewalPrice: what StoreKit says the subscription next renews at.
    ///   - currentPrice: the product's price in the same storefront.
    ///   - dealHasEnded: `earlyDealHasEnded`, injectable for tests.
    static func isEarlyAdopter(state: State,
                               renewalPrice: Decimal?,
                               currentPrice: Decimal?,
                               dealHasEnded: Bool = earlyDealHasEnded) -> Bool {
        guard case .subscribed = state else { return false }
        guard dealHasEnded else { return true }
        // After the rise, only a preserved (lower) renewal price counts. If
        // either price is unknown (offline, product not loaded), show nothing
        // rather than guess.
        guard let renewalPrice, let currentPrice else { return false }
        return renewalPrice < currentPrice
    }
}
