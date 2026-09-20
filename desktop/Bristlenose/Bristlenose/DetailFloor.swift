import SwiftUI

/// The width the report needs, and the decision that collapses the projects
/// sidebar to give it that width — the Mail behaviour, done explicitly.
///
/// The number comes from the SPA over `panel-state` (`minWidth`): content
/// floor + the panels the researcher has open + the minimap. Native cannot
/// compute it — the dragged panel widths live only in `SidebarStore` — so it
/// applies the figure rather than deriving one. The SPA posts the *wanted*
/// arrangement, not the one it is currently able to show, which is what keeps
/// the sidebar collapsed while the web-side cascade is closing panels: if the
/// figure dropped every time a panel auto-closed, the sidebar would pop back
/// and take the space the cascade just made.
///
/// Why explicit rather than `navigationSplitViewColumnWidth(min:)` on the
/// detail — measured 20 Sep 2026. `NSSplitView` never clamps: given minimums
/// that add up to more than its width it lays the columns out at those
/// minimums and lets the total run off the window (no Auto Layout conflict
/// is logged; it is deliberate). Pure AppKit never reaches that state because
/// the split view's minimums feed the window's own minimum; SwiftUI let the
/// two disagree, and we wrote both — `ContentView`'s 700-pt frame and a
/// 968-pt column. Result: the report clipped on the left after a resize, and
/// the projects column pushed half off-screen when the tag sidebar opened,
/// since a minimum change is not a resize and the collapse path never ran.
/// The only design with nothing to overflow against is to declare no column
/// minimum at all and collapse the column ourselves from measured widths.
///
/// Lifted out of `ContentView` for the reason `SidebarToggle` was: a SwiftUI
/// view that decides something hands the decision to a plain helper.
enum DetailFloor {
    /// The width the report needs, or `nil` when nothing should be enforced.
    ///
    /// Only the report pane has a floor — the run, drag-interviews and
    /// unavailable panes lay themselves out. And `0` is "the SPA hasn't
    /// reported yet", which must enforce nothing rather than a zero.
    static func resolve(webMinWidth: CGFloat, showingReport: Bool) -> CGFloat? {
        guard showingReport, webMinWidth > 0 else { return nil }
        return webMinWidth
    }
}

/// What to do with the projects column, given the widths.
enum SidebarAutoCollapse {
    enum Action: Equatable {
        case collapse
        case expand
        case none
    }

    /// - Parameters:
    ///   - windowWidth: The split view's width.
    ///   - sidebarWidth: The projects column's width — as measured while it
    ///     showed, or the last such measurement while it is collapsed, so the
    ///     expand test asks whether the column would fit at the width the
    ///     researcher last dragged it to, not at an ideal it may not have.
    ///   - minWidth: `DetailFloor.resolve`, or `nil` to do nothing.
    ///   - sidebarVisible: Whether the column shows now.
    ///   - autoCollapsed: Whether *this* logic hid it. A column the researcher
    ///     hid stays hidden; only one we took is ours to give back.
    ///
    /// Collapse when the detail beside a showing column would be narrower
    /// than the floor. Expand when a column we took would fit again. The two
    /// thresholds are the same figure, so expanding never lands the detail
    /// below the floor and immediately re-collapses.
    static func decide(
        windowWidth: CGFloat,
        sidebarWidth: CGFloat,
        minWidth: CGFloat?,
        sidebarVisible: Bool,
        autoCollapsed: Bool
    ) -> Action {
        guard let minWidth, windowWidth > 0 else { return .none }
        let detailBesideSidebar = windowWidth - sidebarWidth
        if sidebarVisible {
            return detailBesideSidebar < minWidth ? .collapse : .none
        }
        if autoCollapsed {
            return detailBesideSidebar >= minWidth ? .expand : .none
        }
        return .none
    }
}
