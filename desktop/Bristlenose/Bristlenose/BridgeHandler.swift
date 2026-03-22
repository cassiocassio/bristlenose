import AppKit
import Foundation

/// Holds state derived from WKScriptMessageHandler bridge messages.
///
/// The web layer (React SPA in WKWebView) posts messages via
/// `window.webkit.messageHandlers.navigation.postMessage(...)`.
/// WebView's Coordinator validates the origin and delegates to this handler.
///
/// Published properties let ContentView react to bridge state changes
/// (e.g. show/hide loading overlay based on `isReady`).
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

    /// Dispatch a parsed bridge message. Called by WebView.Coordinator after
    /// origin validation.
    ///
    /// - Parameter body: The message dictionary from `WKScriptMessage.body`.
    func handleMessage(_ body: [String: Any]) {
        guard let type = body["type"] as? String else { return }

        switch type {
        case "ready":
            isReady = true

        case "route-change":
            if let url = body["url"] as? String {
                currentPath = url
            }

        case "editing-started":
            isEditing = true

        case "editing-ended":
            isEditing = false

        case "project-action":
            if let action = body["action"] as? String {
                handleProjectAction(action, data: body["data"] as? [String: Any])
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
