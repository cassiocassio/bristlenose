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

    /// When the launch deal ends, or nil while no date is chosen (owner,
    /// 22 Nov 2026). Before it, every active subscriber is an early adopter;
    /// from it, only someone whose unbroken run of subscription began before
    /// it (see `monthlyProductID` for how Apple keeps their price).
    ///
    /// **Why the app is told a date:** before the deal ends and after it, a
    /// newcomer looks the same to the store; only the date tells them apart.
    /// A date (not a switch) can ship in any release before it, so the update
    /// and the price rise in App Store Connect never need to land together.
    /// An install that never updates gives every subscriber the star, and
    /// never takes one from an early adopter.
    ///
    /// **Why not compare prices:** a later price cut, a tax or exchange-rate
    /// adjustment, or a move of storefront would all change who "pays less";
    /// dates in the store's own history do not move (owner, 22 Nov 2026).
    static let earlyDealEnds: Date? = nil

    /// How long someone may be lapsed and still count as continuously
    /// subscribed: Apple's own window for returning at a preserved price
    /// ("within 60 days of expiration", App Store Connect Help, "Manage
    /// pricing for auto-renewable subscriptions", read 21 Nov 2026), so price
    /// and star agree (owner, 22 Nov 2026). If Apple changes that window,
    /// change this with it.
    static let lapseAllowance: TimeInterval = 60 * 24 * 60 * 60

    /// One paid or trial period from the store's history: a transaction's
    /// purchase date and expiration date.
    struct Period: Equatable {
        let start: Date
        let end: Date?
    }

    /// When the run of subscription that reaches the latest period began. A
    /// run breaks where a period starts more than `allowance` after everything
    /// before it had expired. nil for an empty history.
    static func runStart(of history: [Period], allowance: TimeInterval = lapseAllowance) -> Date? {
        let periods = history.sorted { $0.start < $1.start }
        guard let first = periods.first else { return nil }
        var start = first.start
        var reach = first.end ?? first.start
        for period in periods.dropFirst() {
            if period.start > reach.addingTimeInterval(allowance) { start = period.start }
            reach = max(reach, period.end ?? period.start)
        }
        return start
    }

    /// When this person became an early adopter (the start of their current
    /// run), or nil if they are not one. Only `.subscribed` qualifies, so a
    /// cancelled subscription keeps the star until its paid period ends.
    ///
    /// - Parameters:
    ///   - history: every period of this product in the store's history
    ///     (`Transaction.all` includes all renewals), refunds left out.
    ///   - dealEnds: `earlyDealEnds`, injectable for tests.
    ///
    /// No clock is read: before the end date every run began before it, so
    /// comparing the run's start with the date is the whole rule.
    static func earlyAdopterSince(state: State,
                                  history: [Period],
                                  dealEnds: Date? = earlyDealEnds) -> Date? {
        guard case .subscribed = state, let start = runStart(of: history) else { return nil }
        guard let dealEnds else { return start }
        return start < dealEnds ? start : nil
    }
}
