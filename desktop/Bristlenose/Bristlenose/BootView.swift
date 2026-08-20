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
/// sheet). Unlike the progress phases it *does* carry chrome — the icon,
/// message, and Retry — because failure is the exception that warrants words.
struct BootView: View {
    enum Phase {
        /// Sidecar is starting up (Python process spawn → Uvicorn ready).
        case startingSidecar
        /// Sidecar is up; React SPA is mounting.
        case loadingReport
        /// Sidecar failed to start. `message` is shown verbatim under the
        /// status line; `retry` reattempts; `details` reveals raw output.
        case failed(message: String, retry: () -> Void)
    }

    let phase: Phase
    @EnvironmentObject var i18n: I18n
    @State private var detailsExpanded = false
    /// The fleet, not a manager: under Stage 3b there is one serve per project,
    /// and this view is about whichever is fronted.
    @EnvironmentObject var serveFleet: ServeFleet

    private var statusText: String {
        switch phase {
        case .startingSidecar: i18n.t("desktop.boot.startingSidecar")
        case .loadingReport: i18n.t("desktop.boot.loadingReport")
        case .failed: i18n.t("desktop.boot.failedTitle")
        }
    }

    private var isFailed: Bool {
        if case .failed = phase { return true }
        return false
    }

    var body: some View {
        VStack(spacing: 18) {
            Spacer()

            // Brand block — only in the failure phase. The progress phases show
            // just the bar (see the type doc-comment): identity is already carried
            // by the native chrome, and this surface reappears on every project
            // switch. Failure is the exception that warrants the icon + wordmark.
            // Combine icon + wordmark + tagline into a single VoiceOver element so
            // the screen reader announces "Bristlenose, <tagline>" once; the status
            // zone below stays in its own group so Retry / Show details / error
            // message remain individually reachable.
            if isFailed {
                VStack(spacing: 18) {
                    Image(nsImage: NSApp.applicationIconImage)
                        .resizable()
                        .interpolation(.high)
                        .frame(width: 96, height: 96)
                        .opacity(0.7)

                    VStack(spacing: 4) {
                        Text("Bristlenose")
                            .font(.title)
                            .foregroundStyle(.primary)
                        Text(i18n.t("desktop.boot.tagline"))
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Bristlenose — \(i18n.t("desktop.boot.tagline"))")
            }

            // Status zone — fixed height so the icon+title don't shift when
            // the progress/error block changes. Children stay individually
            // accessible so VoiceOver can reach Retry + Show details.
            statusZone
                .frame(maxWidth: 420, minHeight: 64)
                .padding(.top, 8)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    @ViewBuilder
    private var statusZone: some View {
        switch phase {
        case .startingSidecar, .loadingReport:
            // Just the bar — unchanged. The confusing text is what's removed here.
            ProgressView()
                .progressViewStyle(.linear)
                .frame(maxWidth: 240)

        case .failed(let message, let retry):
            VStack(spacing: 10) {
                Text(statusText)
                    .font(.headline)
                Text(message)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                HStack(spacing: 12) {
                    Button(i18n.t("desktop.boot.retry"), action: retry)
                        .keyboardShortcut(.defaultAction)
                    Button(i18n.t(detailsExpanded
                                  ? "desktop.boot.hideDetails"
                                  : "desktop.boot.showDetails")) {
                        detailsExpanded.toggle()
                    }
                }
                if detailsExpanded {
                    ScrollView {
                        Text((serveFleet.fronted?.outputLines ?? []).suffix(40).joined(separator: "\n"))
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
        }
    }
}
