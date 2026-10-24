import SwiftUI

/// Boot surface shown while the Python sidecar is starting (3–6 s on cold
/// start) and while the React SPA is loading after the sidecar is ready.
///
/// The two *progress* phases show only a centered indeterminate bar. This is
/// the embedded Mac context: the app's identity is already established by the
/// native chrome (Dock icon, menu bar, window), and this surface reappears on
/// every project switch (the detail WebView is keyed on project id) — so an
/// app-launch splash with icon + wordmark + tagline + "Starting…" text would
/// be redundant and read as un-Mac-like on a mere navigation.
///
/// Failure mode is kept inside the same surface (rather than a separate
/// sheet), drawn as the detail panes' one family: a stock
/// `ContentUnavailableView` with the warning triangle, the headline, the
/// reason and the buttons. No app icon, wordmark or tagline — the progress
/// phases are bar-only, so no pane carries the brand block (owner, 24 Oct
/// 2026, `docs/mockups/detail-pane-states.html` Q2, option B).
struct BootView: View {
    enum Phase {
        /// Sidecar is starting up (Python process spawn → Uvicorn ready).
        case startingSidecar
        /// Sidecar is up; React SPA is mounting.
        case loadingReport
        /// The sidecar could not start. The message is a `FailureMessage` so
        /// the line under the localised title is localised too — it was the
        /// English half of a half-translated view. `retry` reattempts;
        /// `sendFeedback` opens this window's feedback sheet as a problem
        /// report, offered once a retry has itself failed (`failureButtons`).
        /// Show details reveals the raw output either way.
        case failed(message: FailureMessage, retry: () -> Void, sendFeedback: () -> Void)
        /// Lazy start: this window has a study but deliberately has not begun
        /// serving it, because nobody is looking. Renders **at rest** — no verb,
        /// no motion. `.idle` used to map to `.startingSidecar`, which was true
        /// when idle only ever meant "about to start"; under lazy start it made
        /// eleven background windows each animate a claim that nothing was
        /// happening behind. Absence is the information.
        case deferred
    }

    let phase: Phase

    /// The study this pane is booting, when it has one. Defaulted so the
    /// call sites that genuinely have no project (pre-selection boot) need
    /// no argument.
    var project: UUID? = nil

    @EnvironmentObject var i18n: I18n
    @State private var detailsExpanded = false
    @EnvironmentObject var serveFleet: ServeFleet

    /// The serve this pane is about.
    ///
    /// Deliberately NOT `serveFleet.fronted`: a pane showing a *failed* boot is
    /// by definition not running, so it is very unlikely to be the fronted one —
    /// and "Show Details" would then print another study's log, or nothing.
    /// `project` is the honest source; nil only where the pane has none.
    private var serveManagerForPane: ServeManager? {
        project.map { serveFleet.manager(for: $0) }
    }

    private var showsActivity: Bool {
        if case .deferred = phase { return false }
        return true
    }

    private var statusText: String {
        switch phase {
        case .startingSidecar: i18n.t("desktop.boot.startingSidecar")
        case .loadingReport: i18n.t("desktop.boot.loadingReport")
        case .failed: i18n.t("desktop.boot.failedTitle")
        // No verb for a window that has deliberately not begun. Deferring is not
        // a status the researcher needs narrated, and naming it would invite a
        // string that has to be true in 21 languages for a state nobody asked
        // about. The window shows the app at rest until it is looked at.
        case .deferred: ""
        }
    }

    var body: some View {
        switch phase {
        case .failed(let message, let retry, let sendFeedback):
            failedPane(message: message, retry: retry, sendFeedback: sendFeedback)
        case .deferred, .startingSidecar, .loadingReport:
            VStack {
                Spacer()
                // Status zone — fixed height, so nothing shifts as the phase
                // changes.
                statusZone
                    .frame(maxWidth: 420, minHeight: 64)
                Spacer()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    @ViewBuilder
    private var statusZone: some View {
        switch phase {
        case .deferred, .failed:
            // Nothing. This window has a study and has deliberately not begun
            // serving it, because nobody is looking — so there is no activity to
            // report and a bar would be a claim, not a status. Absence is the
            // information. It also matters at scale: eleven background windows
            // each animating an indeterminate bar is visible in Mission Control,
            // costs battery, and makes "hasn't begun" indistinguishable from
            // "wedged". The bar starts when the serve does. (`.failed` draws
            // its own pane, `failedPane`.)
            EmptyView()

        case .startingSidecar, .loadingReport:
            // Just the bar — unchanged. The confusing text is what's removed here.
            ProgressView()
                .progressViewStyle(.linear)
                .frame(maxWidth: 240)
        }
    }

    /// The failure, as every other detail pane draws a state: icon, headline,
    /// one line of reason, the buttons. Show details opens the engine's last
    /// lines beneath them.
    private func failedPane(
        message: FailureMessage, retry: @escaping () -> Void, sendFeedback: @escaping () -> Void
    ) -> some View {
        ContentUnavailableView {
            Label(statusText, systemImage: "exclamationmark.triangle")
        } description: {
            Text(message.resolved(i18n))
                .lineLimit(3)
        } actions: {
            HStack(spacing: 12) {
                let set = Self.failureButtons(
                    startedByRetry: serveManagerForPane?.startedByRetry ?? false
                )
                ForEach(set.buttons, id: \.self) { which in
                    failureButton(which, retry: retry, sendFeedback: sendFeedback)
                        .keyboardShortcut(set.defaultButton == which ? .defaultAction : nil)
                }
            }
            if detailsExpanded {
                ScrollView {
                    Text((serveManagerForPane?.outputLines ?? []).suffix(40).joined(separator: "\n"))
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .padding(8)
                }
                .frame(maxWidth: 480, maxHeight: 140)
                .background(Color(nsColor: .textBackgroundColor).opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

extension BootView {
    @ViewBuilder
    private func failureButton(
        _ which: FailureButton, retry: @escaping () -> Void, sendFeedback: @escaping () -> Void
    ) -> some View {
        switch which {
        case .retry:
            Button(i18n.t("desktop.boot.retry"), action: retry)
        case .showDetails:
            Button(i18n.t(detailsExpanded
                          ? "desktop.boot.hideDetails"
                          : "desktop.boot.showDetails")) {
                detailsExpanded.toggle()
            }
        case .sendFeedback:
            Button(i18n.t("desktop.menu.help.sendFeedback"), action: sendFeedback)
        }
    }

    /// The failure pane's buttons.
    enum FailureButton: Equatable, Hashable {
        case retry
        case showDetails
        case sendFeedback
    }

    /// The buttons in order, and which one Return presses, if any.
    struct FailureButtonSet: Equatable {
        let buttons: [FailureButton]
        let defaultButton: FailureButton?
    }

    /// A first failure offers Retry, the default, then Show details. Once a
    /// start the researcher asked for with Retry has failed too, Retry goes:
    /// Show details, then Send Feedback…, and neither takes Return, because
    /// neither is the fix. Owner decisions, 22 and 24 Oct 2026: they don't
    /// want to hit Retry ten times, and a failure that survives a retry is
    /// worth telling us about.
    static func failureButtons(startedByRetry: Bool) -> FailureButtonSet {
        startedByRetry
            ? FailureButtonSet(buttons: [.showDetails, .sendFeedback], defaultButton: nil)
            : FailureButtonSet(buttons: [.retry, .showDetails], defaultButton: .retry)
    }

    /// What a problem report from this pane starts with: the pane's title,
    /// then the sentence under it without the engine output that ends it
    /// (`details`, the last lines the engine printed, which can name a study
    /// folder). A path the sentence names is the app's own; a home folder in it
    /// becomes `~`, so it doesn't carry the user's name. By the path's shape,
    /// not `NSHomeDirectory()`, which under App Sandbox is the container.
    @MainActor
    static func problemReportMessage(for failure: FailureMessage, i18n: I18n) -> String {
        var overrides = ["details": ""]
        if let path = failure.vars["path"] {
            overrides["path"] = path.replacingOccurrences(
                of: #"^/Users/[^/]+(?=/|$)"#, with: "~", options: .regularExpression)
        }
        return i18n.t("desktop.boot.failedTitle") + "\n"
            + failure.resolved(i18n, replacing: overrides)
    }
}
