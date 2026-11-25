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

    private var unavailable: Bool { store.state == .storeUnavailable }

    var body: some View {
        if unavailable { unavailableBody } else { offerBody }
    }

    /// The store cannot be reached and nothing on record says this person has
    /// paid. Not a dead end: Try Again, and Restore for a paid person on a new
    /// Mac behind a proxy.
    private var unavailableBody: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(i18n.t("desktop.subscription.unavailable"))
                .font(.title3.bold())
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button(i18n.t("desktop.subscription.notNow"), action: onNotNow)
                    .keyboardShortcut(.cancelAction)
                    .disabled(working)
                Button(i18n.t("desktop.subscription.tryAgain")) { Task { await tryAgain() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(working)
            }
            HStack(spacing: 12) {
                Link(i18n.t("desktop.subscription.terms"), destination: Self.termsURL)
                Link(i18n.t("desktop.subscription.privacy"), destination: Self.privacyURL)
                Button(i18n.t("desktop.subscription.restore")) { Task { await restore() } }
                    .buttonStyle(.link).disabled(working)
            }
            .font(.footnote)
        }
        .padding(24)
        .frame(width: 460)
        .onChange(of: store.state) { _, new in
            if case .subscribed = new { onSubscribed() }
        }
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

            HStack(spacing: 12) {
                Link(i18n.t("desktop.subscription.terms"), destination: Self.termsURL)
                Link(i18n.t("desktop.subscription.privacy"), destination: Self.privacyURL)
                Button(i18n.t("desktop.subscription.restore")) { Task { await restore() } }
                    .buttonStyle(.link).disabled(working)
                Link(i18n.t("desktop.subscription.manage"), destination: Self.manageURL)
            }
            .font(.footnote)
        }
        .padding(24)
        .frame(width: 460)
        .onChange(of: store.state) { _, new in
            if case .subscribed = new { onSubscribed() }
        }
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
        await store.restore()
        if case .subscribed = store.state { onSubscribed() }
        else if store.state == .notSubscribed { message = i18n.t("desktop.subscription.notFound") }
        working = false
    }

    private func tryAgain() async {
        working = true
        await store.refresh()
        working = false
    }
}
