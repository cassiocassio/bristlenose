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

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(i18n.t(trial ? "desktop.subscription.trialTitle" : "desktop.subscription.lapsedTitle"))
                .font(.title2.bold())
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
        else { message = i18n.t("desktop.subscription.notFound") }
        working = false
    }
}
