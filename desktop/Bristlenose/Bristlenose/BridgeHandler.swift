import AppKit
import Foundation
import WebKit

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

    /// The filesystem path of the currently selected project.
    /// Set by ContentView on project selection. Used by Project menu actions
    /// (Show in Finder) and disable guards.
    @Published var selectedProjectPath: String = ""

    /// Reference to the WKWebView for outbound calls (goBack, switchToTab).
    /// Set by WebView.makeNSView, cleared on reset(). Weak to avoid retain cycles.
    weak var webView: WKWebView?

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
            if let ids = body["selectedIds"] as? [String] {
                selectedQuoteCount = ids.count
            }

        case "undo-state":
            canUndo = body["canUndo"] as? Bool ?? false
            canRedo = body["canRedo"] as? Bool ?? false
            undoLabel = body["undoLabel"] as? String

        case "player-state":
            hasPlayer = body["hasPlayer"] as? Bool ?? false
            playerPlaying = body["playing"] as? Bool ?? false

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
        hasPlayer = false
        playerPlaying = false
        canUndo = false
        canRedo = false
        undoLabel = nil
        isDarkMode = false
        selectedProjectPath = ""
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
