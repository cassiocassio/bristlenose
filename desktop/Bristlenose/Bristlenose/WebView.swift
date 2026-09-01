import AppKit
import OSLog
import SwiftUI
import UniformTypeIdentifiers
import WebKit

private let log = Logger(subsystem: "app.bristlenose", category: "webview")

/// WKWebView subclass that declines the ⌘, key equivalent so it propagates to
/// the app's native Settings menu item. A plain WKWebView claims command-key
/// equivalents while it hosts the window's first responder, so ⌘, was swallowed
/// whenever the user was focused in the report content (the common case) — the
/// Settings menu item fired only when focus sat in native chrome. Returning
/// `false` here lets AppKit route ⌘, to the main menu from any focus, restoring
/// the standard macOS "⌘, opens Settings from anywhere" behaviour. Every other
/// key equivalent (the web layer's own shortcuts, copy/paste, …) is untouched.
final class BristlenoseWebView: WKWebView {
    /// Set in `WebView.makeNSView` so the ⌘A interception below can read the
    /// active tab / editing state and dispatch a menu action. Weak — the
    /// handler is owned at the App level and outlives the web view.
    weak var bridgeHandler: BridgeHandler?

    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
        if flags == .command, event.charactersIgnoringModifiers == "," {
            return false  // not handled here → AppKit routes ⌘, to the main menu
        }

        // ⌘A on the Quotes lens → select all quotes as objects (ready to
        // star/hide/tag), not "select all text" across the report DOM. A
        // WKWebView's performKeyEquivalent runs *before* the main menu (the
        // same ordering the ⌘, case above relies on), so claiming ⌘A here
        // preempts the standard Edit ▸ Select All. Only when the Quotes tab
        // is showing and the user isn't editing text inline — an inline
        // quote/heading edit still gets native text select-all, and other
        // tabs (transcripts, etc.) keep native select-all for copying.
        if flags == .command, event.charactersIgnoringModifiers == "a",
           let handler = bridgeHandler,
           handler.activeTab == .quotes, !handler.isEditing {
            handler.menuAction("selectAllQuotes")
            return true
        }

        // ⌘C on the Quotes lens with quotes selected → copy the selected
        // quotes' text (same as Copy Quotes ▸ Selected). Object selection isn't
        // a text selection, so the standard Edit ▸ Copy would grab nothing
        // after ⌘A. With no quotes selected we fall through to native copy so
        // ordinary text selection still copies; editing / other tabs likewise.
        if flags == .command, event.charactersIgnoringModifiers == "c",
           let handler = bridgeHandler,
           handler.activeTab == .quotes, !handler.isEditing,
           handler.selectedQuoteCount > 0 {
            handler.menuAction("copyQuotes", payload: ["scope": "selected"])
            return true
        }

        return super.performKeyEquivalent(with: event)
    }
}

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
    /// Which running sidecar this view is showing. Selects the storage
    /// partition, so sibling windows on the same serve share one — see
    /// `SharedConfigStore`.
    let session: ServeSession
    /// Bearer token for localhost API access control.
    /// Injected via WKUserScript at document start.
    var authToken: String?

    @EnvironmentObject var i18n: I18n

    func makeCoordinator() -> Coordinator {
        Coordinator(bridgeHandler: bridgeHandler, i18n: i18n)
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()

        // Ephemeral storage — no cross-project cookie/sessionStorage leakage.
        // Shared per serve session rather than minted per view, so sibling
        // windows on the same project can reach each other over BroadcastChannel
        // and WebKit is free to consolidate their content processes. Different
        // projects still never share a partition. See `SharedConfigStore`.
        config.websiteDataStore = SharedConfigStore.shared.dataStore(for: session)

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

        let webView = BristlenoseWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        webView.bridgeHandler = bridgeHandler  // ⌘A → select-all-quotes interception
        context.coordinator.webView = webView

        // Translucent chrome (spike): let the window's vibrancy show through the
        // WKWebView so the unified toolbar / titlebar frost samples real report
        // content behind it, matching the Notes/Mail idiom on macOS 26 Tahoe.
        // The SPA sets `body { background: transparent }` under
        // `__BRISTLENOSE_EMBEDDED__`; without this, the WebView's own opaque
        // paint would still cover the vibrancy. KVC because
        // `drawsBackground` isn't exposed on the WKWebView Swift API.
        webView.setValue(false, forKey: "drawsBackground")

        // Web Inspector (right-click → Inspect Element) rides the Diagnostics
        // preference — disclosed in the toggle's helper text, available on any
        // channel. Read at creation time: flipping the toggle applies to
        // webviews created afterwards (project switch or relaunch).
        webView.isInspectable = DiagnosticsPreference.isEnabled()

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

    /// Handles WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, and WKDownloadDelegate.
    final class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {

        let bridgeHandler: BridgeHandler
        let i18n: I18n
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

        /// Per-download original request URL — used to detect HTML report
        /// downloads (path component) and to build the alternate
        /// `?anonymise=…` URL when the user toggles in the panel.
        @MainActor private var pendingRequestURL: [ObjectIdentifier: URL] = [:]

        init(bridgeHandler: BridgeHandler, i18n: I18n) {
            self.bridgeHandler = bridgeHandler
            self.i18n = i18n
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

            // Anchor-with-`download` clicks (including blob: URLs from the
            // React export modal). Convert to a WKDownload so the
            // download-delegate path runs — under App Sandbox a same-frame
            // navigation to a blob: URL is otherwise dropped silently.
            if navigationAction.shouldPerformDownload {
                decisionHandler(.download)
                return
            }

            if isAllowedServeURL(url) || url.absoluteString == "about:blank" {
                decisionHandler(.allow)
                return
            }

            openExternal(url)
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
        ///
        /// Logs a warning when a 127.0.0.1 URL is rejected on port mismatch
        /// (including port-less URLs, which return `URL.port == nil`). Without
        /// this, the failure mode "SPA emits a port-less localhost link, gets
        /// silently shunted to the user's default browser" is invisible.
        @MainActor
        private func isAllowedServeURL(_ url: URL) -> Bool {
            guard let allowedPort = lastLoadedURL?.port,
                  url.host == "127.0.0.1",
                  url.scheme == "http",
                  url.port == allowedPort else {
                if url.host == "127.0.0.1" {
                    log.warning("rejecting 127.0.0.1 URL with port=\(url.port ?? -1, privacy: .public) (allowed=\(self.lastLoadedURL?.port ?? -1, privacy: .public))")
                }
                return false
            }
            return true
        }

        /// Open a URL in the user's default app, but only for safe schemes.
        ///
        /// Pre-existing fallthrough in decidePolicyFor / createWebViewWith
        /// blindly called `NSWorkspace.shared.open(url)` for any URL the
        /// allow-list rejected. NSWorkspace happily opens `file://` (launches
        /// local apps), `data:` (browser-rendered attacker content), and
        /// `javascript:` URLs. Defence-in-depth: gate the external open on
        /// http(s) / mailto only.
        @MainActor
        private func openExternal(_ url: URL) {
            let scheme = url.scheme?.lowercased() ?? ""
            if scheme == "http" || scheme == "https" || scheme == "mailto" {
                NSWorkspace.shared.open(url)
            } else {
                log.warning("blocking external open for scheme=\(scheme, privacy: .public)")
            }
        }

        /// A new main-frame document is on its way — whatever identity the
        /// previous document posted no longer describes what the view is about
        /// to show, so `documentState` returns to `.loading` until the new
        /// document identifies itself (`ready` / `status-page`). The SPA's
        /// client-side route changes never pass through here (no full loads),
        /// so this fires only on real document turnover: initial load,
        /// reload-on-completion, renderer-crash recovery, serve restart.
        ///
        /// Identity-guarded to the report webView: popout child WKWebViews
        /// (the video player) share this Coordinator, and a popout load must
        /// not un-identify the report behind it.
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            Task { @MainActor [weak self] in
                guard let self, webView === self.webView else { return }
                log.notice("main-frame navigation started (url: \(webView.url?.path ?? "nil", privacy: .public)) → documentState .loading")
                self.bridgeHandler.documentState = .loading
            }
        }

        /// Page finished loading — if the bridge `ready` message hasn't arrived
        /// within 2 seconds, show the content anyway. This handles the case where
        /// the served build doesn't include the bridge code (e.g. main branch build
        /// loaded from a feature branch's app).
        ///
        /// `isReady` is fabricated here on purpose (legacy-bundle compat);
        /// `documentState` deliberately is NOT (design decision D2) — an
        /// unidentified document stays `.loading` and the lens affordances
        /// stay pessimistic, which is the loud dev-time tell for a page that
        /// forgot its identity script. Log it so the cause is one `log stream`
        /// away rather than a mystery.
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            Task { @MainActor [weak self] in
                try? await Task.sleep(for: .seconds(2))
                guard let self else { return }
                if !self.bridgeHandler.isReady {
                    print("[WebView] ready message not received — showing content anyway")
                    self.bridgeHandler.isReady = true
                }
                if webView === self.webView, self.bridgeHandler.documentState == .loading {
                    log.warning("document never identified itself (no ready/status-page message) — lens controls stay pessimistic")
                }
            }
        }

        /// Handle web content process crashes — reload the page.
        ///
        /// The serve process is still running; only the renderer crashed. This
        /// used to be a bare `webView.reload()`, which was right while one
        /// window meant one web view. Sibling windows now share a storage
        /// partition, so WebKit may host several in one content process and a
        /// single crash calls this on all of them — see `RendererRecovery`,
        /// which collects them and reloads the batch staggered.
        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            MainActor.assumeIsolated {
                RendererRecovery.shared.webViewDidTerminate(webView)
            }
        }

        // MARK: - WKNavigationDelegate (downloads)

        /// Convert HTTP responses with `Content-Disposition: attachment` to
        /// downloads. Direct-URL navigation to `/api/.../export` would 401
        /// today (auth lives in a Bearer header injected by JS, not a cookie),
        /// so this branch is reserved for a future server-side cookie or
        /// query-token change. The current path runs the React `fetch()` →
        /// blob URL → `<a download>` click — handled by the navigationAction
        /// `shouldPerformDownload` branch.
        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationResponse: WKNavigationResponse,
            decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
        ) {
            if let httpResp = navigationResponse.response as? HTTPURLResponse,
               let disposition = httpResp.value(forHTTPHeaderField: "Content-Disposition")?.lowercased(),
               disposition.contains("attachment") {
                decisionHandler(.download)
                return
            }
            decisionHandler(.allow)
        }

        func webView(
            _ webView: WKWebView,
            navigationAction: WKNavigationAction,
            didBecome download: WKDownload
        ) {
            download.delegate = self
            Task { @MainActor in
                self.pendingRequestURL[ObjectIdentifier(download)] = navigationAction.request.url
            }
        }

        func webView(
            _ webView: WKWebView,
            navigationResponse: WKNavigationResponse,
            didBecome download: WKDownload
        ) {
            download.delegate = self
            Task { @MainActor in
                self.pendingRequestURL[ObjectIdentifier(download)] = navigationResponse.response.url
            }
        }

        // MARK: - WKDownloadDelegate

        nonisolated func download(
            _ download: WKDownload,
            decideDestinationUsing response: URLResponse,
            suggestedFilename: String,
            completionHandler: @escaping (URL?) -> Void
        ) {
            // NSSavePanel is main-thread only.
            Task { @MainActor in
                self.handleDecideDestination(
                    download: download,
                    response: response,
                    suggestedFilename: suggestedFilename,
                    completionHandler: completionHandler
                )
            }
        }

        @MainActor
        private func handleDecideDestination(
            download: WKDownload,
            response: URLResponse,
            suggestedFilename: String,
            completionHandler: @escaping (URL?) -> Void
        ) {
            let id = ObjectIdentifier(download)
            let requestURL = pendingRequestURL[id] ?? response.url
            defer { pendingRequestURL.removeValue(forKey: id) }

            let suggested = suggestedFilename.isEmpty
                ? (requestURL?.lastPathComponent ?? "export")
                : suggestedFilename
            let ext = (suggested as NSString).pathExtension.lowercased()

            let panel = NSSavePanel()
            panel.nameFieldStringValue = suggested
            panel.allowedContentTypes = Self.contentTypes(forExt: ext)
            panel.canCreateDirectories = true
            // The app forces its own appearance; a panel follows the system's
            // unless told otherwise. See `PanelHost`.
            panel.adoptHostAppearance()
            if let dir = Self.lastSaveDirectory(forExt: ext) {
                panel.directoryURL = dir
            }

            // HTML report from /api/.../export → attach anonymise toggle.
            // Detect by URL path so blob: fallbacks (browsers, dev paths
            // that haven't migrated) don't accidentally show the accessory.
            let isHTMLReport = Self.isHTMLReportURL(requestURL)
            var controller: ExportAccessoryController?
            var initialAnonymise = false
            if isHTMLReport {
                initialAnonymise = Self.anonymiseFlag(in: requestURL)
                let c = ExportAccessoryController(initial: initialAnonymise)
                controller = c
                panel.accessoryView = ExportAccessory.makeView(
                    controller: c,
                    label: i18n.t("common.export.anonymise"),
                    hint: i18n.t("common.export.anonymiseHint")
                )
                panel.message = i18n.t("common.export.savePanelMessage")
            }

            let result = panel.runModal()
            guard result == .OK, let chosen = panel.url else {
                completionHandler(nil)
                return
            }

            Self.persistLastSaveDirectory(
                chosen.deletingLastPathComponent(),
                forExt: chosen.pathExtension.lowercased()
            )

            // Mid-panel anonymise toggle: cancel this download and re-fire a
            // fresh navigation against the alternate URL. The new download
            // re-enters the delegate.
            if isHTMLReport,
               let c = controller,
               c.anonymise != initialAnonymise,
               let original = requestURL,
               let alternate = Self.urlWithAnonymise(c.anonymise, basedOn: original),
               let webView = self.webView {
                download.cancel { _ in }
                webView.load(URLRequest(url: alternate))
                completionHandler(nil)
                return
            }

            completionHandler(chosen)
        }

        nonisolated func downloadDidFinish(_ download: WKDownload) {
            // No toast: panel closing is the success signal. Best-effort
            // quarantine strip on a copy that may be running on a
            // background queue — the file is the user's own data, never
            // from an untrusted external source.
            Task { @MainActor in
                self.stripQuarantineIfPossible(download: download)
            }
        }

        @MainActor
        private func stripQuarantineIfPossible(download: WKDownload) {
            guard let url = download.progress.fileURL else { return }
            var values = URLResourceValues()
            values.quarantineProperties = nil
            do {
                var mutableURL = url
                try mutableURL.setResourceValues(values)
            } catch {
                log.info("quarantine strip failed: \(error.localizedDescription, privacy: .public)")
            }
        }

        nonisolated func download(_ download: WKDownload,
                                  didFailWithError error: Error,
                                  resumeData: Data?) {
            let nsError = error as NSError
            if nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled {
                return  // user-initiated cancel
            }
            Task { @MainActor in
                let alert = NSAlert()
                alert.messageText = self.i18n.t("common.export.saveFailedAlert")
                alert.informativeText = error.localizedDescription
                alert.alertStyle = .warning
                alert.addButton(withTitle: "OK")
                alert.runModal()
            }
        }

        // MARK: - Download helpers

        private static func contentTypes(forExt ext: String) -> [UTType] {
            switch ext {
            case "html", "htm": return [.html]
            case "csv":         return [.commaSeparatedText]
            case "xlsx":
                if let t = UTType(filenameExtension: "xlsx") { return [t] }
                return [.data]
            case "zip":         return [.zip]
            default:            return [.data]
            }
        }

        private static func lastSaveDirectoryKey(forExt ext: String) -> String {
            "export.lastSaveDirectory.\(ext.isEmpty ? "default" : ext)"
        }

        private static func lastSaveDirectory(forExt ext: String) -> URL? {
            let key = lastSaveDirectoryKey(forExt: ext)
            guard let path = UserDefaults.standard.string(forKey: key) else { return nil }
            let url = URL(fileURLWithPath: path)
            var isDir: ObjCBool = false
            guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir),
                  isDir.boolValue else { return nil }
            return url
        }

        private static func persistLastSaveDirectory(_ url: URL, forExt ext: String) {
            UserDefaults.standard.set(url.path, forKey: lastSaveDirectoryKey(forExt: ext))
        }

        /// True iff the URL is the HTML report endpoint.  Path component is
        /// `…/projects/{id}/export` (no trailing slash) — the CSV/XLSX
        /// endpoints have `…/export/quotes.csv` / `…/export/quotes.xlsx`.
        private static func isHTMLReportURL(_ url: URL?) -> Bool {
            guard let url else { return false }
            return url.path.hasSuffix("/export")
        }

        /// Read `?anonymise=true` from a URL's query string.
        private static func anonymiseFlag(in url: URL?) -> Bool {
            guard let url,
                  let comps = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
                return false
            }
            return comps.queryItems?.first(where: { $0.name == "anonymise" })?.value == "true"
        }

        /// Build the alternate URL with the given anonymise flag set or removed.
        private static func urlWithAnonymise(_ on: Bool, basedOn url: URL) -> URL? {
            guard var comps = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
                return nil
            }
            var items = (comps.queryItems ?? []).filter { $0.name != "anonymise" }
            if on {
                items.append(URLQueryItem(name: "anonymise", value: "true"))
            }
            comps.queryItems = items.isEmpty ? nil : items
            return comps.url
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
                    openExternal(url)
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

            // Same Diagnostics-preference gate as the report webview above.
            popoutWebView.isInspectable = DiagnosticsPreference.isEnabled()

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
