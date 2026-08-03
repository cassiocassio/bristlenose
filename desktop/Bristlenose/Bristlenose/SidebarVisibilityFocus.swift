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

/// The decision behind View ▸ Hide/Show All Sidebars — the umbrella over the
/// projects column (native) and the two web panels (Contents/Tags), which
/// otherwise take three separate keystrokes.
///
/// Lineage is Photoshop's Tab rather than Figma's Show/Hide UI: Figma can get
/// away with a bare toggle because its panels are always both present, whereas
/// here mixed arrangements are normal, so hiding **stashes** and showing puts
/// back what you had. The stash for the web pair lives in `SidebarStore`; the
/// projects column deliberately has none — it is binary, and "Show All
/// Sidebars" showing it is exactly what the label says.
///
/// Scope is the three *sidebars*. The Analysis heatmap inspector is a bottom
/// panel on the data rather than navigation chrome, and including it would make
/// the label a lie. The toolbar stays too — in embedded mode it is the only
/// affordance for the web panels, so hiding it would make this a one-way door.
enum AllSidebars {
    /// Is anything showing? Drives the Hide↔Show verb, and with it the command
    /// the item sends. Native can read the projects column directly; the two
    /// web panels arrive over the `panel-state` bridge mirror.
    static func anyShowing(projects: Bool, leftPanel: Bool, rightPanel: Bool) -> Bool {
        projects || leftPanel || rightPanel
    }

    /// The `menuAction` the web layer should receive. Explicit rather than a
    /// toggle: native owns the verb because it is the only side that can see
    /// all three, and a web-side toggle would invert whenever the column and
    /// the panels disagreed (projects showing, panels closed → native hides,
    /// web sees nothing open and *opens* both).
    static func webAction(hiding: Bool) -> String {
        hiding ? "hideAllSidebars" : "showAllSidebars"
    }

    /// Where the projects column lands. Hiding always collapses it; showing
    /// always expands it — there is no stash to consult, by the design note
    /// above.
    static func nextVisibility(
        _ visibility: NavigationSplitViewVisibility,
        hiding: Bool
    ) -> NavigationSplitViewVisibility {
        hiding ? .detailOnly : .all
    }
}

/// The label decision behind the View menu's four panel rows — Projects, the
/// lens's left list (Contents / Sessions / Codes / Signals), Tags, Heatmap —
/// lifted out of `ViewMenuContent` for the reason `SidebarToggle` was: a
/// SwiftUI view that decides something hands the decision to a plain helper.
///
/// All four rows are toggles, so each reads wrong whenever its panel is already
/// open ("Show Tags" with the tag sidebar showing). Projects can answer that
/// from its own window's `NavigationSplitViewVisibility`; the other three are
/// web state and answer from `BridgeHandler`'s `panel-state` mirror. One helper
/// so the four rows compose their key the same way and can't drift.
enum PanelToggle {

    /// Locale key for a panel row's label: `hide…` when the panel is both
    /// reachable and open, `show…` otherwise.
    ///
    /// `isAvailable` is why this isn't a bare ternary. A dimmed row must read
    /// "Show": on the Project lens there is no left panel to hide, and the
    /// mirrored `isOpen` there is whatever the last lens that *had* one left
    /// behind. Falling back to the reveal verb keeps a dimmed row from
    /// advertising a hide that would do nothing — and matches how the row reads
    /// the instant it becomes available again.
    ///
    /// - Parameter panel: The capitalised key suffix naming the panel
    ///   (`"Projects"`, `"Contents"`, `"Sessions"`, `"Codes"`, `"Signals"`,
    ///   `"Tags"`, `"Heatmap"`). Both verbs exist for every one of these in
    ///   `menu.view` — adding a row means adding both.
    static func labelKey(panel: String, isOpen: Bool, isAvailable: Bool) -> String {
        let verb = (isAvailable && isOpen) ? "hide" : "show"
        return "desktop.menu.view.\(verb)\(panel)"
    }
}
