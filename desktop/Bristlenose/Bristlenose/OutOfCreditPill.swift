import AppKit
import SwiftUI

/// App-global toolbar pill: the active cloud provider is out of credit.
///
/// Sibling to `OllamaDownloadPill` — both are `.status`-zone pills sharing the
/// `StatusPill` envelope. The dot is `ProviderStatus.dotColor` (`.orange`), the
/// same amber dot shown in LLM Settings, so one dot reads across both surfaces.
/// Red stays reserved for a genuinely failed run (per the register rules in
/// docs/mockups/out-of-credit-ux.html). The popover is the only place to
/// resolve it — nothing goes in the content area.
struct OutOfCreditPill: View {
    @ObservedObject var model: OutOfCreditModel
    @EnvironmentObject var i18n: I18n
    @State private var showingDetail = false

    var body: some View {
        if model.isActive, let provider = model.provider {
            StatusPill(
                isPresented: $showingDetail,
                accessibilityLabel: pillText(provider)
            ) {
                // Amber dot — matches ProviderStatus.dotColor in Settings.
                Image(systemName: "circle.fill")
                    .imageScale(.small)
                    .foregroundStyle(.orange)
                Text(pillText(provider))
                    .font(.system(.caption).weight(.medium))
                    .lineLimit(1)
            } detail: {
                popover(provider)
            }
        }
    }

    private func popover(_ provider: LLMProvider) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(String(format: i18n.t("desktop.outOfCredit.title"), provider.displayName))
                .font(.system(.callout).weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            Text(i18n.t("desktop.outOfCredit.body"))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                // Secondary first, default (Add funds) trailing — macOS places
                // the default/confirm button rightmost.
                Button(i18n.t("desktop.outOfCredit.switchProvider")) {
                    showingDetail = false
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                Button(i18n.t("desktop.outOfCredit.addFunds")) {
                    showingDetail = false
                    let links = provider.links
                    if let url = links.billing ?? links.console {
                        NSWorkspace.shared.open(url)
                    }
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding(.top, 6)
        }
        .padding(16)
        .frame(width: 280)
    }

    private func pillText(_ provider: LLMProvider) -> String {
        String(format: i18n.t("desktop.outOfCredit.pill"), provider.displayName)
    }
}
