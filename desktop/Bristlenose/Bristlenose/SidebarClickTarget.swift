import AppKit

/// Where a click landed, for the sidebar's empty-space deselect (`SidebarDeselectMonitor`).
///
/// The monitor sees every left mouse-down in the window, so what it does first must be cheap:
/// it hit-tests, then walks UP from the view that was hit. It used to find the sidebar's table by
/// walking DOWN through every view in the window on every click (~190 ms a click in a Debug trace,
/// 4 Nov 2026). A click counts only if it landed on the table or inside it, so something drawn
/// over the list (on macOS 26 the list slides under the sidebar footer, so Send Feedback sits
/// inside the table's bounds, below the last row) is not the table and never clears the selection.
enum SidebarClickTarget {
    /// The table the view is, or is inside; nil for a view outside any table, and for a table's own
    /// ancestors (its clip view and scroll view), which are not on the list.
    static func enclosingTableView(of view: NSView) -> NSTableView? {
        var current: NSView? = view
        while let v = current {
            if let table = v as? NSTableView { return table }
            current = v.superview
        }
        return nil
    }
}
