import SwiftUI

/// The minimum width the detail column declares to the split view, so that
/// shrinking the window collapses the projects sidebar (the Mail behaviour)
/// instead of squeezing the report below its reading measure.
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
/// Lifted out of `ContentView` for the reason `SidebarToggle` was: a SwiftUI
/// view that decides something hands the decision to a plain helper.
enum DetailFloor {
    /// The width to declare, or `nil` to declare nothing.
    ///
    /// Only the report pane has a floor — the run, drag-interviews and
    /// unavailable panes lay themselves out. And `0` is "the SPA hasn't
    /// reported yet", which must leave the split view exactly as it was
    /// rather than declare a zero minimum that differs from an absent one.
    static func resolve(webMinWidth: CGFloat, showingReport: Bool) -> CGFloat? {
        guard showingReport, webMinWidth > 0 else { return nil }
        return webMinWidth
    }
}

/// Applies `DetailFloor.resolve` to the detail column.
struct DetailFloorModifier: ViewModifier {
    let webMinWidth: CGFloat
    let showingReport: Bool

    func body(content: Content) -> some View {
        if let width = DetailFloor.resolve(webMinWidth: webMinWidth, showingReport: showingReport) {
            content.navigationSplitViewColumnWidth(min: width, ideal: width)
        } else {
            content
        }
    }
}
