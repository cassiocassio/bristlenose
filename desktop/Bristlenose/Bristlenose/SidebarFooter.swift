import SwiftUI

/// The sidebar's footer: the app version on the left, a Send Feedback button
/// on the right. `docs/design-desktop-sidebar-footer.md`.
///
/// **Plain text, not a capsule.** The version first copied the Debug
/// build-info capsule, which needs its material because it floats over web
/// content. On the sidebar that material sat on top of the sidebar's own, read
/// as one of the app's clickable status pills, and went opaque under Reduce
/// Transparency. Plain `.secondary` text keeps the sidebar's own vibrancy.
///
/// **Not selectable.** Selectable text in a sidebar takes keyboard focus away
/// from the project list. The tooltip carries version and build, since
/// TestFlight ships several builds under one marketing version.
///
/// **The button acts on its own window.** The caller passes a closure that sets
/// this window's sheet flag. Help ▸ Send Feedback… used to broadcast, and every
/// open window answered.
struct SidebarFooter: View {
    @ObservedObject var i18n: I18n
    let onSendFeedback: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            if ReleaseStage.showsPrereleaseVersion {
                Text(i18n.t("desktop.chrome.prereleaseVersion",
                            ["version": BuildInfo.current.appVersion]))
                    .font(.caption2)
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .help("\(BuildInfo.current.appVersion) (\(BuildInfo.current.buildNumber))")
            }
            Spacer(minLength: 0)
            Button(action: onSendFeedback) {
                // The glyph stays small; only the click area is 22 × 22, the
                // HIG's 20 pt minimum plus a little, with no pixels added.
                Image(systemName: "ladybug")
                    .frame(width: 22, height: 22)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.borderless)
            .foregroundStyle(.secondary)
            .help(i18n.t("desktop.chrome.sendFeedbackHelp"))
            .accessibilityLabel(i18n.t("desktop.chrome.sendFeedbackHelp"))
        }
        .padding(.leading, 16)
        .padding(.trailing, 10)
        .padding(.vertical, 6)
    }
}

/// Whether this build presents itself as pre-release ("0.32.0 beta").
///
/// **Compile-time on purpose.** It cannot be decided at runtime: App Review
/// runs under the same StoreKit sandbox receipt as TestFlight
/// (`DistributionChannel.swift`), so a "TestFlight only" check would also show
/// the word to the App Store reviewer, and Guideline 2.2 rejects apps presented
/// as betas. Set this to `false` before the first App Store submission.
enum ReleaseStage {
    static let showsPrereleaseVersion = true
}
