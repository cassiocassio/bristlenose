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
    /// the store returns no product and the state stays `.unknown` (allowed).
    static let monthlyProductID = "app.bristlenose.subscription.monthly"

    enum State: Equatable {
        /// Not asked yet, or the store has not positively answered (the
        /// product did not load). Treated as *allowed* by `canStartAnalysis`
        /// so a slow or offline store, or a build whose product is not yet
        /// live, never locks a paying researcher out or shows a paywall with
        /// nothing to buy.
        case unknown
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
    ///   it did not, an empty entitlement set proves nothing, so the state is
    ///   `.unknown` rather than `.notSubscribed`.
    static func state(entitledProductIDs: Set<String>,
                      expirations: [String: Date],
                      trialProductIDs: Set<String> = [],
                      productLoaded: Bool) -> State {
        if entitledProductIDs.contains(monthlyProductID) {
            return .subscribed(expires: expirations[monthlyProductID],
                               inTrial: trialProductIDs.contains(monthlyProductID))
        }
        return productLoaded ? .notSubscribed : .unknown
    }

    /// Starting an analysis (a paid LLM run on new recordings).
    static func canStartAnalysis(_ state: State, channel: DistributionChannel) -> Bool {
        guard channel == .appStoreOrTestFlight else { return true }
        switch state {
        case .unknown, .subscribed: return true
        case .notSubscribed: return false
        }
    }

    /// Reading something already analysed. Always allowed: a lapsed
    /// subscription must never hold someone's own work hostage.
    static func canOpenProjects(_ state: State, channel: DistributionChannel) -> Bool {
        true
    }
}
