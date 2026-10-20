import AppKit
import SwiftUI

/// Presents the expiry sequence for an expired Developer-ID `.dmg` alpha build
/// (lifecycle stage 2.5) as SwiftUI modals over the serve-less main window:
///
///   Expired alert → (Send Feedback…) → native FeedbackSheet → "Thanks" → quit
///
/// No-op on every non-alpha channel (`AlphaBuild.isExpired()` is false there),
/// so it costs nothing on Debug / App Store / TestFlight builds. The sidecar is
/// separately refused by `ServeManager.start()`'s guard, so the window behind
/// these modals comes up empty. Feedback reuses the existing native
/// `FeedbackSheet` with a serve-free `FeedbackConfig` (it can't read
/// `/api/health` — there's no serve). Send failures are silent (the sheet's own
/// clipboard fallback); there is deliberately no error dialog. English-only:
/// ephemeral alpha-only chrome.
///
/// A single `route` enum drives all three modals so the alert→sheet handoff is
/// one atomic state change (presenting a sheet directly from an alert button is
/// a well-known SwiftUI race).
struct AlphaExpiryFlow: ViewModifier {
    let i18n: I18n
    /// The flow's own, per window: each window owns its toasts (R90), and this
    /// modifier sits outside the window's root view, so it cannot reach that one.
    @StateObject private var toast = ToastStore()

    private enum Route { case expired, feedback, thanks }

    @State private var route: Route?
    /// Set by the sheet's `onSent` (confirmed submit) so `onDismiss` can route
    /// to Thanks rather than back to the Expired alert on a plain cancel.
    @State private var didSend = false

    func body(content: Content) -> some View {
        content
            .overlay { ToastOverlay().environmentObject(toast) }
            .onAppear { if AlphaBuild.isExpired() { route = .expired } }
            .alert("This Bristlenose beta has expired", isPresented: presenting(.expired)) {
                Button("Get Bristlenose") { openSiteAndQuit() }
                    .keyboardShortcut(.defaultAction)
                // Reset here as well as in onDismiss. Cancel stops a send in
                // flight (`FeedbackSheetModel.cancelSend`), so a send that ends
                // after it never calls onSent; this keeps a fresh attempt clean
                // whatever the order.
                Button("Send Feedback…") {
                    FeedbackTrace.opened(by: "alpha-expiry-alert")
                    didSend = false; route = .feedback
                }
                Button("Quit", role: .cancel) { NSApp.terminate(nil) }
            } message: {
                Text("This was a time-limited preview. Get the latest at bristlenose.app. If you have a minute, I'd love to hear how it went.")
            }
            .sheet(isPresented: presenting(.feedback), onDismiss: {
                route = didSend ? .thanks : .expired
                didSend = false
            }) {
                FeedbackSheet(
                    config: .serverless,
                    i18n: i18n,
                    onToast: { toast.show($0) },
                    onSent: { didSend = true }
                )
            }
            .alert("Thanks for the feedback.", isPresented: presenting(.thanks)) {
                Button("Get Bristlenose") { openSiteAndQuit() }
                    .keyboardShortcut(.defaultAction)
                Button("Quit", role: .cancel) { NSApp.terminate(nil) }
            } message: {
                Text("Get the latest at bristlenose.app")
            }
    }

    /// A Bool binding scoped to one route — reads true when it's the active
    /// route, and clears `route` only when the system dismisses *that* modal
    /// (never clobbering a route another button just set).
    private func presenting(_ r: Route) -> Binding<Bool> {
        Binding(
            get: { route == r },
            set: { isPresented in if !isPresented, route == r { route = nil } }
        )
    }

    private func openSiteAndQuit() {
        NSWorkspace.shared.open(AlphaBuild.landingURL)
        NSApp.terminate(nil)
    }
}

extension View {
    /// Attach the expired-alpha modal sequence. Pass the app-level `I18n`
    /// explicitly (the modifier isn't inside its `.environmentObject` scope).
    /// No-op unless this is an expired alpha build.
    func alphaExpiryFlow(i18n: I18n) -> some View {
        modifier(AlphaExpiryFlow(i18n: i18n))
    }
}
