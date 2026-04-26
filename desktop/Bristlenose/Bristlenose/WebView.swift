import SwiftUI
import WebKit

/// WKWebView wrapper for displaying the Bristlenose React SPA in embedded mode.
///
/// Security hardening (design doc lines 1149–1161):
/// 1. Navigation restricted to 127.0.0.1 — external URLs open in system browser
/// 2. Bridge origin validation — messages only accepted from 127.0.0.1
/// 3. No string interpolation — use callAsyncJavaScript for native→web calls
/// 4. Ephemeral storage — WKWebsiteDataStore.nonPersistent() per project
/// 5. Settings interception — handled by BridgeHandler
struct WebView: NSViewRepresentable {

    let url: URL?
    let bridgeHandler: BridgeHandler
    /// Bearer token for localhost API access control.
    /// Injected via WKUserScript at document start.
    var authToken: String?

    func makeCoordinator() -> Coordinator {
        Coordinator(bridgeHandler: bridgeHandler)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()

        // Ephemeral storage — no cross-project cookie/sessionStorage leakage.
        config.websiteDataStore = .nonPersistent()

        let userContentController = WKUserContentController()

        // Inject embedded flag before the page loads. The React SPA checks
        // window.__BRISTLENOSE_EMBEDDED__ to suppress NavBar/Footer/Header.
        let embeddedScript = WKUserScript(
            source: "window.__BRISTLENOSE_EMBEDDED__ = true;",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true
        )
        userContentController.addUserScript(embeddedScript)

        // Inject auth token for localhost API access control.
        // Validates format before interpolation (security rule 3 compliance).
        if let token = authToken,
           token.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil {
            let tokenScript = WKUserScript(
                source: "window.__BRISTLENOSE_AUTH_TOKEN__ = '\(token)';",
                injectionTime: .atDocumentStart,
                forMainFrameOnly: true
            )
            userContentController.addUserScript(tokenScript)
        }

        // Register message handler for bridge messages from the web layer.
        // The web side posts via: window.webkit.messageHandlers.navigation.postMessage(msg)
        userContentController.add(context.coordinator, name: "navigation")

        config.userContentController = userContentController

        // Allow media autoplay without user gesture — the popout player
        // calls video.play() programmatically. This must be set on the
        // parent config because child WKWebViews inherit media permissions.
        config.mediaTypesRequiringUserActionForPlayback = []

        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        context.coordinator.webView = webView

        // Enable Web Inspector (right-click → Inspect Element) for debugging.
        #if DEBUG
        webView.isInspectable = true
        #endif

        // Give BridgeHandler a reference for outbound calls (goBack, switchToTab).
        bridgeHandler.webView = webView

        // KVO — observe canGoBack/canGoForward for toolbar button enable state.
        context.coordinator.canGoBackObservation = webView.observe(
            \.canGoBack, options: [.new]
        ) { [weak bridgeHandler] _, change in
            Task { @MainActor in
                bridgeHandler?.canGoBack = change.newValue ?? false
            }
        }
        context.coordinator.canGoForwardObservation = webView.observe(
            \.canGoForward, options: [.new]
        ) { [weak bridgeHandler] _, change in
            Task { @MainActor in
                bridgeHandler?.canGoForward = change.newValue ?? false
            }
        }

        // Load the initial URL if provided.
        if let url {
            webView.load(URLRequest(url: url))
            context.coordinator.lastLoadedURL = url
        }

        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        // Guard against SwiftUI re-render reloads — only load if URL changed.
        guard let url, url != context.coordinator.lastLoadedURL else { return }
        webView.load(URLRequest(url: url))
        context.coordinator.lastLoadedURL = url
    }

    // MARK: - Coordinator

    /// Handles WKScriptMessageHandler, WKNavigationDelegate, and WKUIDelegate.
    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate {

        let bridgeHandler: BridgeHandler
        @MainActor var webView: WKWebView?
        @MainActor var lastLoadedURL: URL?

        /// KVO observations for back/forward button enable state.
        /// Stored strongly — auto-invalidated on Coordinator dealloc when the
        /// WebView is recreated via `.id(project.id)` on project switch.
        var canGoBackObservation: NSKeyValueObservation?
        var canGoForwardObservation: NSKeyValueObservation?

        /// The popout player window. Retained to prevent deallocation.
        /// Not @MainActor — WKUIDelegate callbacks are already on main thread.
        var popoutWindow: NSWindow?
        /// KVO observation for syncing popout document.title → NSWindow title.
        var popoutTitleObservation: NSKeyValueObservation?

        init(bridgeHandler: BridgeHandler) {
            self.bridgeHandler = bridgeHandler
        }

        // MARK: - WKScriptMessageHandler

        func userContentController(
            _ userContentController: WKUserContentController,
            didReceive message: WKScriptMessage
        ) {
            // Validate origin — only accept messages from localhost.
            guard let origin = message.frameInfo.request.url,
                  origin.host == "127.0.0.1" else {
                return
            }

            guard let body = message.body as? [String: Any] else {
                return
            }

            Task { @MainActor in
                bridgeHandler.handleMessage(body)
            }
        }

        // MARK: - WKNavigationDelegate

        /// Restrict navigation to the project's assigned serve port on
        /// 127.0.0.1. External URLs open in the system browser via NSWorkspace.
        ///
        /// SECURITY #8: previously allowed any 127.0.0.1 port and any `about:`
        /// scheme. An iframe, `window.open`, or bridge-driven navigation
        /// could target a different localhost port (a colleague's dev server,
        /// an open debugger, an exposed admin UI) and load its content into
        /// our WKWebView. Now restricted to the loaded URL's port; `about:`
        /// narrowed to `about:blank` only.
        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            guard let url = navigationAction.request.url else {
                decisionHandler(.cancel)
                return
            }

            if isAllowedServeURL(url) || url.absoluteString == "about:blank" {
                decisionHandler(.allow)
                return
            }

            // External URL — open in default browser, cancel in-app navigation.
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        }

        /// True iff `url` is `http://127.0.0.1:<assignedPort>/...`. The
        /// assigned port is read from `lastLoadedURL` (set when WebView loads
        /// the initial serve URL — see makeNSView/updateNSView). Popout
        /// child WKWebViews share this Coordinator, so popout navigations
        /// also resolve against the parent's serve port — correct, because
        /// the popout player is served by the same `bristlenose serve`
        /// instance.
        ///
        /// If `lastLoadedURL` is nil (no initial load yet) or has no explicit
        /// port, return false. Fail closed.
        @MainActor
        private func isAllowedServeURL(_ url: URL) -> Bool {
            guard let allowedPort = lastLoadedURL?.port,
                  url.host == "127.0.0.1",
                  url.scheme == "http",
                  url.port == allowedPort else {
                return false
            }
            return true
        }

        /// Page finished loading — if the bridge `ready` message hasn't arrived
        /// within 2 seconds, show the content anyway. This handles the case where
        /// the served build doesn't include the bridge code (e.g. main branch build
        /// loaded from a feature branch's app).
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            Task { @MainActor [weak self] in
                try? await Task.sleep(for: .seconds(2))
                guard let self else { return }
                if !self.bridgeHandler.isReady {
                    print("[WebView] ready message not received — showing content anyway")
                    self.bridgeHandler.isReady = true
                }
            }
        }

        /// Handle web content process crashes — reload the page.
        /// The serve process is still running; only the renderer crashed.
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            webView.reload()
        }

        // MARK: - WKUIDelegate

        /// Handle window.open() from JavaScript — creates a native NSWindow
        /// with a WKWebView for the popout video player.
        func webView(
            _ webView: WKWebView,
            createWebViewWith configuration: WKWebViewConfiguration,
            for navigationAction: WKNavigationAction,
            windowFeatures: WKWindowFeatures
        ) -> WKWebView? {
            // SECURITY #8: only allow popouts to the project's assigned serve
            // port (not any 127.0.0.1 port). isAllowedServeURL reads the port
            // from the parent's lastLoadedURL.
            guard let url = navigationAction.request.url,
                  isAllowedServeURL(url) else {
                if let url = navigationAction.request.url {
                    NSWorkspace.shared.open(url)
                }
                return nil
            }

            // Close previous popout if still open — one player at a time.
            if let existing = popoutWindow {
                existing.close()
                popoutWindow = nil
                popoutTitleObservation = nil
            }

            // Must use the provided configuration — WKWebView enforces this.
            // Allow media autoplay without user gesture (player.html calls
            // video.play() programmatically after loadAndSeek).
            configuration.mediaTypesRequiringUserActionForPlayback = []
            let popoutWebView = WKWebView(frame: .zero, configuration: configuration)
            popoutWebView.navigationDelegate = self

            #if DEBUG
            popoutWebView.isInspectable = true
            #endif

            let width = windowFeatures.width?.doubleValue ?? 720
            let height = windowFeatures.height?.doubleValue ?? 480

            let window = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: width, height: height),
                styleMask: [.titled, .closable, .resizable, .miniaturizable],
                backing: .buffered,
                defer: false
            )
            window.contentView = popoutWebView
            window.title = "Bristlenose Player"
            window.setFrameAutosaveName("BristlenosePlayer")
            window.makeKeyAndOrderFront(nil)

            // Retain the window — clean up when it closes.
            popoutWindow = window

            // KVO: sync document.title from player.html → NSWindow title bar.
            popoutTitleObservation = popoutWebView.observe(
                \.title, options: [.new]
            ) { [weak window] _, change in
                Task { @MainActor in
                    if let title = change.newValue ?? nil, !title.isEmpty {
                        window?.title = title
                    }
                }
            }

            return popoutWebView
        }

        /// Handle window.close() from JavaScript — close the native window.
        func webViewDidClose(_ webView: WKWebView) {
            if webView.window === popoutWindow {
                popoutWindow?.close()
                popoutWindow = nil
                popoutTitleObservation = nil
            }
        }
    }
}
