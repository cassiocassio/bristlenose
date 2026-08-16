import OSLog
import WebKit

/// Reloads web views whose content process died — debounced across windows.
///
/// ## Why this is not just `webView.reload()`
///
/// It was, and that was right while one window meant one web view. Sibling
/// windows on one project now share a storage partition (`SharedConfigStore`),
/// which is what lets them talk over BroadcastChannel and lets WebKit
/// consolidate their content processes — and a consolidated content process is
/// a *shared failure*. One renderer crash calls
/// `webViewWebContentProcessDidTerminate` on every view it was hosting, so with
/// five transcript windows open, five reloads fire in the same tick and land on
/// one Python sidecar together.
///
/// Debounced rather than coordinated (decided 16 Aug 2026): the views are
/// collected for a beat and then reloaded, staggered. Coordinating — electing
/// one view to reload and having the others follow it — needs an election and a
/// notion of "followed successfully", and buys nothing here, because each view
/// has to re-fetch its own page regardless.
///
/// Deliberately not in scope: a crash-loop guard. A page that reliably kills
/// the renderer reload-loops today at N=1, and that is a separate bug with a
/// separate fix; making this one quieter would only hide it.
@MainActor
final class RendererRecovery {

    static let shared = RendererRecovery()

    /// How long to collect terminations before acting. Long enough that the
    /// per-view callbacks from a single crash land in one batch, short enough
    /// that the researcher reads it as "it came back", not as a pause.
    static let collectionWindow = Duration.milliseconds(250)

    /// Gap between reloads within a batch, so N views don't hit the sidecar at
    /// once. The first goes immediately once the window closes.
    static let stagger = Duration.milliseconds(150)

    private static let log = Logger(subsystem: "app.bristlenose", category: "renderer")

    /// Views waiting to be reloaded. Boxed weakly: a window closed between the
    /// crash and the reload should not be resurrected, and holding a strong
    /// reference to a dead view's window would do exactly that.
    private var pending: [WeakWebView] = []
    private var drainTask: Task<Void, Never>?

    private init() {}

    /// A content process hosting `webView` died. Reload it, with any siblings
    /// that died in the same beat.
    func webViewDidTerminate(_ webView: WKWebView) {
        guard !pending.contains(where: { $0.value === webView }) else { return }
        pending.append(WeakWebView(webView))
        Self.log.info("content process terminated — pending=\(self.pending.count)")

        // Restart the collection window on each arrival: a crash that takes
        // five views delivers five callbacks, and they should reload as one
        // batch rather than the first one starting a batch of its own.
        drainTask?.cancel()
        drainTask = Task { @MainActor [weak self] in
            try? await Task.sleep(for: Self.collectionWindow)
            guard !Task.isCancelled else { return }
            self?.drain()
        }
    }

    /// Reload everything collected, oldest first, staggered.
    private func drain() {
        let batch = pending.compactMap(\.value)
        pending.removeAll()
        drainTask = nil
        Self.log.info("reloading \(batch.count) view(s) after renderer crash")

        for (index, webView) in batch.enumerated() {
            if index == 0 {
                webView.reload()
                continue
            }
            Task { @MainActor [weak webView] in
                try? await Task.sleep(for: Self.stagger * index)
                webView?.reload()
            }
        }
    }

    /// Weak box — `Array` can't hold `weak` elements directly.
    private struct WeakWebView {
        weak var value: WKWebView?
        init(_ value: WKWebView) { self.value = value }
    }
}
