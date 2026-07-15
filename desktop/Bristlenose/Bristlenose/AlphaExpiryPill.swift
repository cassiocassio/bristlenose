import AppKit
import SwiftUI

/// App-global toolbar pill: an expiring `.dmg` alpha build is in its final week.
///
/// Sibling to `OllamaDownloadPill` / `OutOfCreditPill` — shares the `StatusPill`
/// envelope, lives in the `.status` zone. Silent until the last 7 days (absence
/// is information) and absent entirely off the `.developerID` channel, because
/// `AlphaBuild.daysRemaining()` returns nil everywhere else. The hourglass goes
/// amber when ≤2 days remain; red stays reserved for a genuinely failed run.
/// Tap → popover with the exact date + the one action (Get Bristlenose → the
/// site). English-only by deliberate scope: ephemeral alpha-only chrome.
struct AlphaExpiryPill: View {
    /// Injectable for previews; defaults to the live countdown (nil off-channel).
    var daysRemaining: Int? = AlphaBuild.daysRemaining()

    /// Only surfaces inside the final week.
    static let showWithinDays = 7

    @State private var showingDetail = false

    var body: some View {
        if let days = daysRemaining, (0...Self.showWithinDays).contains(days) {
            StatusPill(
                isPresented: $showingDetail,
                accessibilityLabel: "Bristlenose alpha. \(spokenRemaining(days))."
            ) {
                Image(systemName: "hourglass")
                    .imageScale(.small)
                    .foregroundStyle(days <= 2 ? AnyShapeStyle(.orange) : AnyShapeStyle(.secondary))
                Text(pillText(days))
                    .font(.system(.caption).weight(.medium))
                    .lineLimit(1)
            } detail: {
                popover(days)
            }
        }
    }

    private func popover(_ days: Int) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Bristlenose alpha")
                .font(.system(.callout).weight(.semibold))
            Text(bodyText(days))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button("Get Bristlenose") {
                    showingDetail = false
                    NSWorkspace.shared.open(AlphaBuild.landingURL)
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding(.top, 6)
        }
        .padding(16)
        .frame(width: 280)
    }

    // Terse pill label — the hourglass already says "time-limited".
    private func pillText(_ days: Int) -> String {
        switch days {
        case 0:  return "Alpha · today"
        case 1:  return "Alpha · 1d"
        default: return "Alpha · \(days)d"
        }
    }

    private func spokenRemaining(_ days: Int) -> String {
        switch days {
        case 0:  return "expires today"
        case 1:  return "expires tomorrow"
        default: return "expires in \(days) days"
        }
    }

    private func bodyText(_ days: Int) -> String {
        let when: String
        switch days {
        case 0:  when = "today"
        case 1:  when = "tomorrow"
        default: when = "in \(days) days"
        }
        if let expiry = AlphaBuild.expiryDate {
            let date = expiry.formatted(date: .abbreviated, time: .omitted)
            return "This preview build stops working \(when) (\(date)). Get the latest at bristlenose.app."
        }
        return "This preview build stops working \(when). Get the latest at bristlenose.app."
    }
}
