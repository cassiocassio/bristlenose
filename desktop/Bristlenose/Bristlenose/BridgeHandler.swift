import AppKit
import Foundation
import WebKit
import os

/// Holds state derived from WKScriptMessageHandler bridge messages.
///
/// The web layer (React SPA in WKWebView) posts messages via
/// `window.webkit.messageHandlers.navigation.postMessage(...)`.
/// WebView's Coordinator validates the origin and delegates to this handler.
///
/// Published properties let ContentView react to bridge state changes
/// (e.g. show/hide loading overlay based on `isReady`).
///
/// Also provides outbound actions (goBack, goForward, switchToTab) that
/// call into the WKWebView via `callAsyncJavaScript`.
@MainActor
final class BridgeHandler: ObservableObject {

    /// True once the web layer posts `{ type: "ready" }` — first meaningful
    /// paint complete. Used to dismiss the loading overlay.
    @Published var isReady = false

    /// Current React Router pathname, updated on `route-change` messages.
    /// Used to keep the native toolbar tab highlight in sync.
    @Published var currentPath = ""

    /// True while the user is editing inline content (quote text, heading,
    /// name). Used to disable conflicting native menu items.
    @Published var isEditing = false

    /// Whether the WKWebView can navigate back in its history.
    /// Updated via KVO observation in WebView.Coordinator.
    @Published var canGoBack = false

    /// Whether the WKWebView can navigate forward in its history.
    /// Updated via KVO observation in WebView.Coordinator.
    @Published var canGoForward = false

    // MARK: - Menu state (driven by bridge messages)

    /// ID of the currently focused quote, or nil. Enables quote-specific
    /// menu items (Star, Hide, Add Tag, Reveal in Transcript).
    @Published var focusedQuoteId: String?

    /// Number of currently selected quotes. Enables bulk actions
    /// (Clear Selection, Copy as CSV).
    @Published var selectedQuoteCount: Int = 0

    /// Total number of quotes currently in the report. Labels the export
    /// popover's "All N quotes" scope choice. Pushed via `export-counts`.
    @Published var totalQuoteCount: Int = 0

    /// Number of starred quotes. Labels the "N Starred quotes" scope choice.
    @Published var starredQuoteCount: Int = 0

    /// Whether a video/audio player is open. Enables the Video menu.
    @Published var hasPlayer = false

    /// Whether the player is currently playing. Swaps Play/Pause label.
    @Published var playerPlaying = false

    /// Whether the web layer has an undo action available.
    @Published var canUndo = false

    /// Whether the web layer has a redo action available.
    @Published var canRedo = false

    /// Optional label for the undo action (e.g. "Undo Star").
    @Published var undoLabel: String?

    /// Whether the web layer is in dark mode. Swaps View menu label.
    @Published var isDarkMode = false

    /// The active lens's subtitle, pushed by the SPA (e.g. "163 Quotes",
    /// "3 Codebooks · 47 Tags"). The SPA owns the live count + formatting — only
    /// it can compute Signals, and the visible-quote / tag counts shift as the
    /// researcher edits. The window subtitle just renders this; empty off the
    /// report-derived lenses (Sessions/Project come from the local DB read).
    @Published var lensSubtitle: String = ""

    /// Which lens `lensSubtitle` is for ("quotes"/"codebook"/"analysis"),
    /// matched against `activeTab` so a tab switch never momentarily shows the
    /// previous lens's count.
    @Published var lensSubtitleTab: String?

    /// Live Quotes-lens search text, mirrored from the SPA via `quotes-filter`.
    /// The native search field reads this so it reflects store changes it didn't
    /// originate (All Quotes reset, Cmd+E selection). The native field is the
    /// sole search input in embedded mode; web has no SearchBox there.
    @Published var quotesSearchQuery: String = ""

    /// Live Quotes-lens view mode ("all" / "starred"), mirrored from the SPA via
    /// `quotes-filter`. Drives the toolbar starred toggle's active state and the
    /// View-menu All Quotes / Starred Quotes Only checkmarks.
    @Published var quotesViewMode: String = "all"

    /// The filesystem path of the currently selected project.
    /// Set by ContentView on project selection. Used by Project menu actions
    /// (Show in Finder) and disable guards.
    @Published var selectedProjectPath: String = ""

    /// Non-empty when a folder is selected in the sidebar.
    /// Used by the Project menu to show folder-specific items.
    @Published var selectedFolderName: String = ""

    /// Whether the currently selected project's directory is accessible on disk.
    /// Set by ContentView on selection change. Used by the Project menu to
    /// enable/disable "Locate…" and "Show in Finder".
    @Published var selectedProjectAvailable: Bool = true

    /// Best-effort path to hand to Finder for the currently selected project.
    /// Equal to `selectedProjectPath` for available projects; falls back to
    /// `lastSeenPath` when the project is `cantFind` so Finder can show its
    /// dead-alias UX (HANDOFF §7). Empty string means there's nothing usable
    /// to reveal — menu items should dim.
    @Published var selectedProjectRevealablePath: String = ""

    /// Whether the currently selected project has a run in flight (running or
    /// queued). Mirrored from `PipelineRunner.state` by ContentView on both
    /// selection change and state change. Drives the enable/disable of
    /// Project ▸ Stop Analysis (⌘.) — the menu-bar accelerator for the
    /// hover-× / context-menu Stop. Dimmed (not hidden) when false, per HIG.
    @Published var selectedProjectIsRunning: Bool = false

    /// Reference to the WKWebView for outbound calls (goBack, switchToTab).
    /// Set by WebView.makeNSView, cleared on reset(). Weak to avoid retain cycles.
    weak var webView: WKWebView?

    private static let log = Logger(subsystem: "app.bristlenose", category: "bridge")

    /// Force the detail WebView to re-fetch its current URL from the serve — used
    /// after a run finishes so the now-served report replaces the stale status
    /// page. `reloadFromOrigin` bypasses the cache. Direct WKWebView reload, so it
    /// doesn't depend on SwiftUI recreating the view (the `.id` approach was
    /// defeated by updateNSView's same-URL guard). Returns false when there's no
    /// WebView to reload (e.g. momentarily nil mid project-switch) so the caller
    /// can retry.
    @discardableResult
    func reloadWebView() -> Bool {
        Self.log.info("reloadWebView webView=\(self.webView != nil)")
        guard let webView else { return false }
        webView.reloadFromOrigin()
        return true
    }

    /// The currently active tab, derived from `currentPath`.
    var activeTab: Tab? {
        Tab.from(path: currentPath)
    }

    // MARK: - Outbound navigation

    /// Navigate the WKWebView back in its browser history.
    func goBack() {
        webView?.goBack()
    }

    /// Navigate the WKWebView forward in its browser history.
    func goForward() {
        webView?.goForward()
    }

    /// Switch the React SPA to the given tab by calling `window.switchToTab(tab)`.
    ///
    /// Uses `callAsyncJavaScript` with structured arguments (security rule 3 —
    /// no string interpolation into JavaScript). Content world is `.page`
    /// because `window.switchToTab` is installed by page-level JS.
    func switchToTab(_ tab: Tab) {
        guard let webView else { return }
        Task {
            do {
                try await webView.callAsyncJavaScript(
                    "window.switchToTab(tab)",
                    arguments: ["tab": tab.rawValue],
                    in: nil,
                    in: .page
                )
                // Ensure WKWebView has focus so bare-key shortcuts (s, h, [, ], m)
                // work immediately after Cmd+1-5 tab switch.
                webView.window?.makeFirstResponder(webView)
            } catch {
                print("[BridgeHandler] switchToTab(\(tab)) FAILED: \(error)")
            }
        }
    }

    /// Push the Quotes-lens search text from the native search field into the
    /// SPA store (`setSearchQuery` action → live filtering). Fire-and-forget;
    /// the SPA is the single source of truth for `quotesSearchQuery` — it's
    /// written ONLY by the inbound `quotes-filter` echo, never optimistically
    /// here, so native state can't claim a value the SPA never applied (a
    /// dropped JS dispatch then self-heals on the next keystroke rather than
    /// wedging). The control debounces before calling this.
    func setQuotesSearch(_ text: String) {
        menuAction("setSearchQuery", payload: ["text": text])
    }

    // MARK: - Window active state

    /// Toggle the `bn-window-inactive` CSS class on the document root.
    /// Called by ContentView on NSWindow key/resign notifications.
    func setWindowActive(_ active: Bool) {
        guard let webView else { return }
        let js = """
            if (active) {
                document.documentElement.classList.remove('bn-window-inactive');
            } else {
                document.documentElement.classList.add('bn-window-inactive');
            }
            """
        Task {
            try? await webView.callAsyncJavaScript(
                js, arguments: ["active": active], in: nil, in: .page
            )
        }
    }

    // MARK: - Appearance sync

    /// Push the native appearance preference to the web layer.
    /// Called when: (1) `isReady` becomes true, (2) user changes appearance in Settings.
    func syncAppearance() {
        let appearance = UserDefaults.standard.string(forKey: "appearance") ?? "auto"
        menuAction("set-appearance", payload: ["value": appearance])
    }

    // MARK: - Locale sync

    /// Push the native locale to the web layer.
    /// Called on `ready` to confirm the URL query param injection,
    /// and on language change in native Settings.
    func syncLocale() {
        let locale = UserDefaults.standard.string(forKey: "language") ?? "en"
        guard let webView else { return }
        Task {
            try? await webView.callAsyncJavaScript(
                "window.__bristlenose?.setLocale?.(locale)",
                arguments: ["locale": locale],
                in: nil,
                in: .page
            )
        }
    }

    // MARK: - Menu action dispatch

    /// Send a menu action to the web layer via `window.__bristlenose.menuAction()`.
    ///
    /// Uses `callAsyncJavaScript` with structured arguments (security rule 3).
    func menuAction(_ action: String, payload: [String: Any]? = nil) {
        guard let webView else {
            print("[BridgeHandler] menuAction(\(action)) — webView is nil")
            return
        }
        let js: String
        var args: [String: Any] = ["action": action]
        if let payload {
            js = "window.__bristlenose.menuAction(action, payload)"
            args["payload"] = payload
        } else {
            js = "window.__bristlenose.menuAction(action)"
        }
        Task {
            do {
                try await webView.callAsyncJavaScript(js, arguments: args, in: nil, in: .page)
            } catch {
                print("[BridgeHandler] menuAction(\(action)) FAILED: \(error)")
            }
        }
    }

    // MARK: - Inbound messages

    /// Dispatch a parsed bridge message. Called by WebView.Coordinator after
    /// origin validation.
    ///
    /// - Parameter body: The message dictionary from `WKScriptMessage.body`.
    func handleMessage(_ body: [String: Any]) {
        guard let type = body["type"] as? String else { return }

        switch type {
        case "ready":
            isReady = true
            syncAppearance()
            syncLocale()
            webView?.window?.makeFirstResponder(webView)

        case "route-change":
            if let url = body["url"] as? String {
                currentPath = url
            }

        case "editing-started":
            isEditing = true

        case "editing-ended":
            isEditing = false

        case "focus-change":
            focusedQuoteId = body["quoteId"] as? String
            // `selectedQuoteCount` is owned solely by `export-counts` (below) —
            // do not also write it here, or the two sources can drift if the
            // web ever starts posting focus-change.

        case "undo-state":
            canUndo = body["canUndo"] as? Bool ?? false
            canRedo = body["canRedo"] as? Bool ?? false
            undoLabel = body["undoLabel"] as? String

        case "export-counts":
            if let n = body["total"] as? Int { totalQuoteCount = n }
            if let n = body["selected"] as? Int { selectedQuoteCount = n }
            if let n = body["starred"] as? Int { starredQuoteCount = n }

        case "player-state":
            hasPlayer = body["hasPlayer"] as? Bool ?? false
            playerPlaying = body["playing"] as? Bool ?? false

        case "lens-subtitle":
            lensSubtitleTab = body["tab"] as? String
            lensSubtitle = body["subtitle"] as? String ?? ""

        case "quotes-filter":
            // Sole writer of these mirrored fields. Equality-guard the assigns so
            // an unchanged re-post (the SPA posts on every quotes-store change)
            // doesn't churn @Published and re-render the toolbar/menu needlessly.
            let q = body["searchQuery"] as? String ?? ""
            let vm = body["viewMode"] as? String ?? "all"
            if q != quotesSearchQuery { quotesSearchQuery = q }
            if vm != quotesViewMode { quotesViewMode = vm }

        case "project-action":
            if let action = body["action"] as? String {
                handleProjectAction(action, data: body["data"] as? [String: Any])
            }

        case "find-pasteboard-write":
            if let text = body["text"] as? String, !text.isEmpty {
                let pb = NSPasteboard(name: .find)
                pb.clearContents()
                pb.setString(text, forType: .string)
            }

        default:
            break
        }
    }

    /// Reset bridge state when switching projects. The new WKWebView will
    /// post a fresh `ready` message once the React SPA mounts.
    func reset() {
        isReady = false
        currentPath = ""
        isEditing = false
        canGoBack = false
        canGoForward = false
        focusedQuoteId = nil
        selectedQuoteCount = 0
        totalQuoteCount = 0
        starredQuoteCount = 0
        hasPlayer = false
        playerPlaying = false
        canUndo = false
        canRedo = false
        undoLabel = nil
        isDarkMode = false
        quotesSearchQuery = ""
        quotesViewMode = "all"
        selectedProjectPath = ""
        selectedProjectRevealablePath = ""
        selectedFolderName = ""
        selectedProjectAvailable = true
        selectedProjectIsRunning = false
        webView = nil
    }

    // MARK: - Private

    private func handleProjectAction(_ action: String, data: [String: Any]?) {
        switch action {
        case "open-settings":
            NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)

        default:
            break
        }
    }
}
