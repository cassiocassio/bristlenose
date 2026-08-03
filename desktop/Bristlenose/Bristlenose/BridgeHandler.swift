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

    // Sidebar visibility deliberately does NOT live here. It is per-window
    // state, and this object is a single app-level `@StateObject` shared by
    // every window — so mirroring it here made the View-menu label describe
    // whichever window moved last. It now reaches the menu as a scene focused
    // value; see `SidebarVisibilityFocus.swift`.

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

    /// Whether the Star command would *unstar* — i.e. the target set (the
    /// selection, or the focused quote) is already all-starred. Mirrors the
    /// click/`s`-key intent so the Quotes menu can flip its label Star⇄Unstar.
    /// Owned by the SPA's `quote-action-state` message (Swift has no per-quote
    /// starred map to derive it locally).
    @Published var starActionIsUnstar = false

    /// Name of the last-applied tag this session, or nil if none. Drives the
    /// "Apply <name>" menu label and its disabled state. Pushed via
    /// `quote-action-state`.
    @Published var lastTagName: String?

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

    /// Whether the report is in Focus Mode. Mirrored from the SPA (`focus-mode`
    /// message) — the web side owns the state; this drives only the View-menu
    /// checkmark. Resets to false on `reset()` because a project switch remounts
    /// the web view, and Focus is deliberately ephemeral (a freshly-opened
    /// project boots in normal view). See docs/design-focus-mode.md.
    @Published var focusModeActive: Bool = false

    /// Whether the web left panel (Contents / Sessions / Codes / Signals) is
    /// showing. Mirrored from the SPA via `panel-state`. Native can't see inside
    /// the WKWebView, so without this the View menu has to guess — this is what
    /// lets Hide All Sidebars pick its verb honestly.
    @Published var leftPanelOpen: Bool = false

    /// Whether the web tag sidebar is showing. Mirrored via `panel-state`.
    @Published var rightPanelOpen: Bool = false

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

    // Appearance is NOT pushed over the bridge. `syncAppearance()` (removed
    // 30 Jul 2026) sent `set-appearance` on every `ready` and **nothing ever
    // consumed it** — it routed via `menuAction`, so it needed a `case` in
    // AppLayout's switch and never had one. The feature works without it:
    // `ContentView` applies `.preferredColorScheme(…)` to the window, the
    // WKWebView inherits the effective appearance, and the report's CSS
    // `prefers-color-scheme` follows. Don't re-add a second channel for a fact
    // the platform already carries.

    /// Push the "Show animation while analysing" toggle to the web layer, so the
    /// web thinking-shimmer (activity chip label) obeys it — the twin of the
    /// native shimmer's `showAnalysisAnimation && !reduceMotion` gate. The web
    /// side keys off `data-analysis-animation` (atoms/shimmer.css); "off" freezes
    /// to static text, absent animates. Default `true` matches the AppStorage
    /// default. Fired on `ready`; re-push on toggle change is a follow-up (the
    /// value is also re-pushed on every reload via `ready`).
    func syncAnalysisAnimation() {
        let on = UserDefaults.standard.object(forKey: "showAnalysisAnimation") as? Bool ?? true
        guard let webView else { return }
        Task {
            try? await webView.callAsyncJavaScript(
                "window.__bristlenose?.setAnalysisAnimation?.(on)",
                arguments: ["on": on],
                in: nil,
                in: .page
            )
        }
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

    // MARK: - Toolbar inset sync (translucent chrome spike)

    /// Push the *residual* toolbar overlap (in CSS px) the SPA still needs to
    /// pad past — the chrome height NOT already absorbed by the WebView's native
    /// top content inset. The WebView extends behind the unified toolbar via
    /// `.ignoresSafeArea(.container, edges: .top)` (ContentView), but the OS
    /// already insets the *layout viewport* below the toolbar: the red-background
    /// test (23 Jul 2026) proved CSS content, scroll-0 origin, and every
    /// getBoundingClientRect() start at the toolbar's bottom, not the window top.
    /// The paint region extends under the toolbar (scroll-underlap works) while
    /// layout does not — that combination IS the Notes/Mail idiom, provided by
    /// the platform. So the old "push the full titlebar+toolbar height" double-
    /// counted the native inset, leaving ~52px of dead space at the top of every
    /// lens. See docs/design-lens-template.md § "Native geometry — ground truth".
    ///
    /// Residual = (toolbar region height) − (native inset the WebView already
    /// applied to its layout viewport). In today's geometry the OS insets the
    /// full toolbar, so the residual is 0 and report.css's
    /// `calc(var(--bn-toolbar-inset,0px) + var(--bn-space-xl))` body pad
    /// collapses to just --bn-space-xl. Keep the plumbing, not the value: a
    /// future window configuration that makes the WebView underlap at rest
    /// (safe-area top 0) revives a non-zero residual and the pad returns.
    ///
    /// Fired on `ready` and re-posted on full-screen enter/exit + resize
    /// (ContentView). The toolbar-region height is the same combined
    /// titlebar+toolbar delta an AppKit view sees as its top safe-area inset;
    /// in full-screen the frame-minus-contentLayoutRect delta collapses (no
    /// titlebar chrome to subtract), so fall back to the contentView's top
    /// safeAreaInset (what AppKit hands SwiftUI's `.ignoresSafeArea` machinery)
    /// and take the larger — but subtract the WebView's own applied inset either
    /// way, so the residual stays correct across the transition.
    func syncToolbarInset() {
        guard let webView, let window = webView.window else { return }
        let frameDelta = window.frame.height - window.contentLayoutRect.height
        let contentSafeAreaTop = window.contentView?.safeAreaInsets.top ?? 0
        let toolbarRegion = max(frameDelta, contentSafeAreaTop)
        // The WebView's own top safe-area inset is the portion of the toolbar
        // overlap macOS has already told the web content to avoid (the layout
        // viewport starts below it). Only the un-absorbed remainder needs a CSS
        // pad. Today toolbarRegion == this inset → residual 0.
        let nativeInset = webView.safeAreaInsets.top
        let residual = max(0, toolbarRegion - nativeInset)
        Task {
            try? await webView.callAsyncJavaScript(
                "window.__bristlenose?.setToolbarInset?.(inset)",
                arguments: ["inset": residual],
                in: nil,
                in: .page
            )
        }
    }

    // MARK: - Colour palette sync

    /// Push the native colour-palette choice to the web layer — live, no reload.
    /// The report is a runtime `data-color-theme` CSS swap, so (unlike the
    /// prefs/typography path, which restarts the serve sidecar) the picker applies
    /// the palette in place. Called on `.bristlenosePaletteChanged` from Settings.
    func setColorPalette() {
        let palette = UserDefaults.standard.string(forKey: "palette") ?? "default"
        guard let webView else { return }
        Task {
            try? await webView.callAsyncJavaScript(
                "window.__bristlenose?.setColorPalette?.(palette)",
                arguments: ["palette": palette],
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
            syncAnalysisAnimation()
            syncLocale()
            syncToolbarInset()
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
            // Sole writer of `focusedQuoteId`, posted by the SPA whenever the
            // report's keyboard focus moves. Carries the focused quote id only
            // (JS null → nil): `selectedQuoteCount` stays owned by
            // `export-counts` so the focus and selection signals can't drift.
            focusedQuoteId = body["quoteId"] as? String

        case "undo-state":
            canUndo = body["canUndo"] as? Bool ?? false
            canRedo = body["canRedo"] as? Bool ?? false
            undoLabel = body["undoLabel"] as? String

        case "export-counts":
            if let n = body["total"] as? Int { totalQuoteCount = n }
            if let n = body["selected"] as? Int { selectedQuoteCount = n }
            if let n = body["starred"] as? Int { starredQuoteCount = n }

        case "quote-action-state":
            // Derived Star⇄Unstar intent + last-tag name for the Quotes menu.
            starActionIsUnstar = body["starIsUnstar"] as? Bool ?? false
            lastTagName = body["lastTagName"] as? String  // JS null → nil

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

        case "focus-mode":
            // Sole writer. The SPA owns Focus Mode; the View-menu checkmark is a
            // mirror, never a second source of truth — a native @State flag would
            // keep claiming Focus was on after a project switch or the post-run
            // reload, both of which remount the web view and reset it to off.
            // The SPA re-posts on mount, which is what re-syncs us.
            let on = body["active"] as? Bool ?? false
            if on != focusModeActive { focusModeActive = on }

        case "panel-state":
            // Sole writer. Equality-guarded like `quotes-filter` — the SPA
            // re-posts on mount and on every sidebar change, and an unchanged
            // post shouldn't churn @Published and re-render the whole menu.
            let left = body["leftOpen"] as? Bool ?? false
            let right = body["rightOpen"] as? Bool ?? false
            if left != leftPanelOpen { leftPanelOpen = left }
            if right != rightPanelOpen { rightPanelOpen = right }

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

        case "store-miro-token":
            // The Send-to-Miro panel hands the validated paste-token to the host
            // so it persists in the Keychain — the sandboxed Python sidecar can't
            // write the Keychain itself. Carried to the next sidecar launch as
            // BRISTLENOSE_MIRO_ACCESS_TOKEN by BristlenoseShared.overlayMiroToken.
            if let token = body["token"] as? String, !token.isEmpty {
                KeychainHelper.set(provider: "miro", value: token)
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
        starActionIsUnstar = false
        lastTagName = nil
        hasPlayer = false
        playerPlaying = false
        canUndo = false
        canRedo = false
        undoLabel = nil
        quotesSearchQuery = ""
        quotesViewMode = "all"
        focusModeActive = false
        leftPanelOpen = false
        rightPanelOpen = false
        selectedProjectPath = ""
        selectedProjectRevealablePath = ""
        selectedFolderName = ""
        selectedProjectAvailable = true
        selectedProjectIsRunning = false
        webView = nil
    }

    // MARK: - Private

    /// Present the native feedback sheet. Bristlenose is a native Mac app, so
    /// feedback is native in EVERY state — the normal report lens (SPA mounted)
    /// AND the degraded status page after a cancelled/failed run. The React
    /// `FeedbackModal` is browser-only; it must never surface in-app. The sheet
    /// reads `/api/health` itself, so it doesn't depend on the SPA being mounted.
    ///
    /// This replaces the old probe-then-route (SPA-up → web modal), which was
    /// backwards: it made the browser-only modal the "normal path" and only fell
    /// through to native when the SPA was absent, so the report lens showed the
    /// web HTML modal. See `docs/design-feedback-native.md` (Phase 0).
    func openFeedback() {
        NotificationCenter.default.post(name: .showFeedbackSheet, object: nil)
    }

    private func handleProjectAction(_ action: String, data: [String: Any]?) {
        switch action {
        case "open-settings":
            NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)

        case "open-feedback":
            // Status page (SPA absent) asked for the native feedback sheet.
            NotificationCenter.default.post(name: .showFeedbackSheet, object: nil)

        case "reveal-in-finder":
            // Reveal a folder (highlighted in its parent) in Finder. Sandbox-safe:
            // Finder performs the reveal in its own process, so no read access or
            // security-scoped bookmark is required on our side. The URI comes from
            // the web layer (`source_folder_uri`, a `file:` URI) — validate the
            // scheme before handing it to NSWorkspace (defence-in-depth, mirrors
            // the `openExternal` scheme gate in WebView.swift).
            guard let uri = data?["uri"] as? String,
                  let url = URL(string: uri),
                  url.isFileURL else {
                break
            }
            NSWorkspace.shared.activateFileViewerSelecting([url])

        default:
            break
        }
    }
}
