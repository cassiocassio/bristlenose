import SwiftUI

/// The paywall sheet (`docs/private/mockups/purchase-journey.html` steps 9 and
/// 16). Shown when Analyse is pressed on the App Store build without a
/// subscription. The price is whatever StoreKit returns; no figure is typed
/// here. Guideline 3.1.2: price and period, renewal terms, Terms and Privacy
/// links, Restore Purchases.
struct PaywallView: View {
    @EnvironmentObject var i18n: I18n
    @ObservedObject var store: SubscriptionStore
    var onNotNow: () -> Void
    var onSubscribed: () -> Void

    @State private var working = false
    @State private var message: String?

    static let termsURL = URL(string: "https://bristlenose.app/terms.html")!
    static let privacyURL = URL(string: "https://bristlenose.app/privacy.html")!
    static let manageURL = URL(string: "https://apps.apple.com/account/subscriptions")!

    /// Wide enough for German's link row on one line: 483 pt measured, plus
    /// the padding, is 531 pt (owner, 27 Nov 2026: "make German work and stack
    /// the others"). Every locale wider than the content stacks its links
    /// (`PaywallLinkRow`): at this width, Russian's offer face only.
    static let width: CGFloat = 540
    static let padding: CGFloat = 24
    static var contentWidth: CGFloat { width - 2 * padding }

    /// The free trial in words ("7 days"), read from the product's own offer,
    /// or nil when there is no free trial to promise.
    private var trialLength: String? {
        guard let t = store.freeTrial else { return nil }
        if let days = SubscriptionAccess.trialDays(unit: t.unit, value: t.value) {
            return i18n.plural("desktop.subscription.trialDays", count: days)
        }
        return SubscriptionAccess.trialLength(unit: t.unit, value: t.value,
                                              localeIdentifier: i18n.locale)
    }
    /// The trial wording only when this account may take it AND the product
    /// offers one: eligibility alone would promise a trial that may not exist.
    private var trial: Bool { store.introEligible && trialLength != nil }
    private var price: String { store.product?.displayPrice ?? "" }
    private var planName: String { store.product?.displayName ?? "" }

    /// Which of the sheet's two faces to show.
    enum Face: Equatable {
        case offer, unavailable

        /// The offer needs the product: without it the title read "/month"
        /// with no price and Subscribe could not be pressed (review, 25 Nov
        /// 2026). No product is the store-unavailable face, whatever the
        /// state says, so the sheet always offers Try Again or a working
        /// Subscribe.
        static func of(_ state: SubscriptionAccess.State, productLoaded: Bool) -> Face {
            state == .storeUnavailable || !productLoaded ? .unavailable : .offer
        }
    }

    /// What the message line says after Try Again or Restore Purchases
    /// (owner, 27 Nov 2026). A press that still failed used to change nothing
    /// on the unavailable face, and a restore that never reached the store
    /// said "No subscription found" (review, 25 Nov 2026).
    enum Message {
        enum Press: Equatable { case tryAgain, restore(reached: Bool) }

        /// The key to show, or nil for no message. A subscription closes the
        /// sheet, so it never has one.
        static func after(_ press: Press, state: SubscriptionAccess.State,
                          productLoaded: Bool) -> String? {
            if case .subscribed = state { return nil }
            switch press {
            case .tryAgain:
                return Face.of(state, productLoaded: productLoaded) == .unavailable
                    ? "desktop.subscription.stillUnavailable" : nil
            case .restore(let reached):
                // "Not found" only when the store answered and found nothing.
                return reached ? "desktop.subscription.notFound" : "desktop.subscription.restoreFailed"
            }
        }
    }

    private func show(after press: Message.Press) {
        message = Message.after(press, state: store.state, productLoaded: store.product != nil)
            .map { i18n.t($0) }
    }

    var body: some View {
        Group {
            switch Face.of(store.state, productLoaded: store.product != nil) {
            case .unavailable: unavailableBody
            case .offer: offerBody
            }
        }
        // Here, not on each face: Try Again that finds the product and a
        // subscription at once swaps the face, and a new face's `.onChange`
        // never sees the change that put it on screen.
        .onChange(of: store.state) { _, new in
            if case .subscribed = new { onSubscribed() }
        }
        // A face that changes by itself (a refresh on activation, or from
        // `Transaction.updates`) drops the other face's message: "Still can't
        // reach the App Store" must not sit above a working Subscribe. A
        // press's own change keeps it: `show` runs before `working` clears.
        .onChange(of: Face.of(store.state, productLoaded: store.product != nil)) { _, _ in
            if !working { message = nil }
        }
    }

    /// The store cannot be reached and nothing on record says this person has
    /// paid. Not a dead end: Try Again, and Restore for a paid person on a new
    /// Mac behind a proxy.
    private var unavailableBody: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(i18n.t("desktop.subscription.unavailable"))
                .font(.title3.bold())
                .fixedSize(horizontal: false, vertical: true)
            if let message {
                Text(message).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Spacer()
                Button(i18n.t("desktop.subscription.notNow"), action: onNotNow)
                    .keyboardShortcut(.cancelAction)
                    .disabled(working)
                Button(i18n.t("desktop.subscription.tryAgain")) { Task { await tryAgain() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(working)
            }
            PaywallLinkRow(i18n: i18n, manage: false, working: working) { Task { await restore() } }
        }
        .padding(PaywallView.padding)
        .frame(width: PaywallView.width)
    }

    /// The plan's name and the billed amount lead, the amount as the title:
    /// Schedule 2 asks for the billed amount to be the most prominent pricing
    /// element, so "free" is never larger than the price. Mockup
    /// `docs/mockups/paywall-iap-fixes.html`, approved 25 Nov 2026.
    private var offerBody: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                if !planName.isEmpty {
                    Text(planName).font(.headline).foregroundStyle(.secondary)
                }
                Text(i18n.t("desktop.subscription.pricePerMonth", ["price": price]))
                    .font(.title2.bold())
                Text(trial
                     ? i18n.t("desktop.subscription.trialLead", ["trial": trialLength ?? ""])
                     : i18n.t("desktop.subscription.lapsedTitle"))
                    .font(.headline)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if trial {
                Text(i18n.t("desktop.subscription.aiBilling"))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(i18n.t(trial ? "desktop.subscription.trialBody" : "desktop.subscription.lapsedBody"))
                .fixedSize(horizontal: false, vertical: true)

            if let message {
                Text(message).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Spacer()
                Button(i18n.t("desktop.subscription.notNow"), action: onNotNow)
                    .keyboardShortcut(.cancelAction)
                    .disabled(working)
                Button(i18n.t(trial ? "desktop.subscription.startTrial" : "desktop.subscription.subscribe")) {
                    Task { await buy() }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(working || store.product == nil)
            }

            Text(i18n.t(trial ? "desktop.subscription.trialTerms" : "desktop.subscription.renewTerms",
                        ["price": price, "trial": trialLength ?? ""]))
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            PaywallLinkRow(i18n: i18n, manage: true, working: working) { Task { await restore() } }
        }
        .padding(PaywallView.padding)
        .frame(width: PaywallView.width)
    }

    private func buy() async {
        working = true; message = nil
        switch await store.purchase() {
        case .subscribed: onSubscribed()
        case .cancelled: break
        case .pending: message = i18n.t("desktop.subscription.pending")
        case .failed: message = i18n.t("desktop.subscription.failed")
        }
        working = false
    }

    private func restore() async {
        working = true; message = nil
        let reached = await store.restore()
        if case .subscribed = store.state { onSubscribed() }
        else { show(after: .restore(reached: reached)) }
        working = false
    }

    private func tryAgain() async {
        working = true; message = nil
        await store.refresh()
        show(after: .tryAgain)
        working = false
    }
}

/// The footnote links under both faces of the paywall: Terms, Privacy, Restore
/// Purchases and, on the offer, Manage Subscription. On one line when the line
/// fits, otherwise one link a line, so no label is ever broken mid-word (12 of
/// 21 locales broke one at the old 460 pt sheet).
struct PaywallLinkRow: View {
    /// Passed in rather than read from the environment, so a test can measure
    /// `line` and `stack` on their own.
    @ObservedObject var i18n: I18n
    var manage: Bool
    var working: Bool
    var restore: () -> Void

    var body: some View {
        ViewThatFits(in: .horizontal) {
            line
            stack
        }
    }

    var line: some View {
        HStack(spacing: 12) { links }.font(.footnote).fixedSize()
    }

    var stack: some View {
        VStack(alignment: .leading, spacing: 6) { links }.font(.footnote).fixedSize()
    }

    @ViewBuilder private var links: some View {
        Link(i18n.t("desktop.subscription.terms"), destination: PaywallView.termsURL)
        Link(i18n.t("desktop.subscription.privacy"), destination: PaywallView.privacyURL)
        Button(i18n.t("desktop.subscription.restore"), action: restore)
            .buttonStyle(.link).disabled(working)
        if manage {
            Link(i18n.t("desktop.subscription.manage"), destination: PaywallView.manageURL)
        }
    }
}
