import SwiftUI

/// Per-window projects-sidebar visibility, published to the menu bar as a
/// **scene** focused value.
///
/// ## Why this replaces a NotificationCenter broadcast
///
/// `ContentView` already owned `columnVisibility` as `@State`, so the sidebar
/// state was *always* per-window. The bug was the **command**: View ▸ Hide/Show
/// Projects posted `.toggleProjectsSidebar` to `NotificationCenter.default`,
/// which every open window received — so two windows toggled in lockstep. The
/// menu's Hide↔Show *label* had a second, related fault: it read an app-global
/// `BridgeHandler.sidebarVisible`, which reflected whichever window moved last
/// and so could describe the wrong window.
///
/// Both symptoms, one cause: an app-wide channel carrying a window-scoped
/// command. `focusedSceneValue` is the SwiftUI mechanism for "this menu command
/// acts on the front window" — the key window publishes its binding and
/// `.commands` reads whichever is current, with no broadcast in between.
///
/// **Scene-scoped, not view-scoped.** `focusedSceneValue` (rather than
/// `focusedValue`) stays published while the window is key even as focus moves
/// *within* it — into the WKWebView, the sidebar outline, an inline-rename text
/// field. A view-scoped value would drop out the moment the web view took focus,
/// silently disabling ⌘⌥S.
///
/// This is the first `FocusedValue` seam in the app. The other 16 menu commands
/// still broadcast via `NotificationCenter` and therefore still fire in every
/// window — see `docs/design-workspace.md` for the staged plan to convert them.
struct SidebarVisibilityKey: FocusedValueKey {
    typealias Value = Binding<NavigationSplitViewVisibility>
}

extension FocusedValues {
    /// The key window's projects-sidebar binding. `nil` when no project window
    /// is frontmost (e.g. only Settings or a diagnostics window is open), which
    /// the View menu renders as a dimmed item.
    var sidebarVisibility: Binding<NavigationSplitViewVisibility>? {
        get { self[SidebarVisibilityKey.self] }
        set { self[SidebarVisibilityKey.self] = newValue }
    }
}

/// The two decisions the View ▸ Hide/Show Projects item makes, lifted out of the
/// view so they're unit-testable (house convention: a SwiftUI view that decides
/// something hands the decision to a plain helper — cf. `ProjectSubtitle.resolve`,
/// `LensItem.systemImage(for:)`).
enum SidebarToggle {
    /// Is the projects sidebar showing? Drives the Hide↔Show label.
    ///
    /// `.detailOnly` is the only genuinely-hidden case; `.all`, `.doubleColumn`
    /// and `.automatic` all show the first column in this two-column split view.
    static func isVisible(_ visibility: NavigationSplitViewVisibility) -> Bool {
        visibility != .detailOnly
    }

    /// The state the menu item moves to: hidden ⇄ shown. Anything currently
    /// showing collapses to `.detailOnly`; `.detailOnly` expands to `.all`.
    static func next(_ visibility: NavigationSplitViewVisibility) -> NavigationSplitViewVisibility {
        visibility == .detailOnly ? .all : .detailOnly
    }
}
