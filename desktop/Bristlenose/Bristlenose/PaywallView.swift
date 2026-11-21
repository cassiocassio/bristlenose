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

    private var trial: Bool { store.introEligible }
    private var price: String { store.product?.displayPrice ?? "" }

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

    private var offerBody: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(i18n.t(trial ? "desktop.subscription.trialTitle" : "desktop.subscription.lapsedTitle"))
                .font(.title2.bold())
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
                        ["price": price]))
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
