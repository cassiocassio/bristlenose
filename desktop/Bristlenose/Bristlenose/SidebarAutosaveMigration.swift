import Foundation
import OSLog

private let migrationLog = Logger(subsystem: "app.bristlenose", category: "sidebar-fit")

/// Drops stored projects-column widths that AppKit can no longer honour.
///
/// `NavigationSplitView` sits on an `NSSplitView` whose `autosaveName` is the
/// window's identifier plus `", SidebarNavigationSplitView"` —
/// `main-AppWindow-1, SidebarNavigationSplitView` for the first project window.
/// AppKit writes each column's frame to UserDefaults under
/// `NSSplitView Subview Frames <autosaveName>` on every layout, and restores
/// it synchronously when the name is set. So from a window's second launch on,
/// the column opens at the width it last had, and the `ideal` declared on the
/// column (`SidebarAutoCollapse.columnIdeal`) is never consulted again.
/// Measured 25 Sep 2026 from inside the container (`docs/sidebar-column-diagnosis.md`).
///
/// That is right for a width the researcher dragged to. It is wrong for a
/// width stored below today's minimum: AppKit clamps it up to the minimum and
/// re-saves the clamp, so the column opens at its narrowest forever. Fifteen
/// windows on the maintainer's Mac held 148 — the resting width from before
/// the column's width modifier was live — and 0.31.0 shipped that way.
///
/// **The rule removes only what AppKit would clamp.** An entry at or above the
/// minimum is a width somebody chose inside the range, and the autosave exists
/// to keep it. That is also why no version marker is needed: the rule is a
/// function of the stored width and the current minimum, so running it on every
/// launch removes nothing the second time. An entry it cannot parse is left
/// alone — the value format is AppKit's and undocumented.
///
/// Must run before the first window exists; `AppDelegate` calls it from
/// `applicationWillFinishLaunching`.
enum SidebarAutosaveMigration {
    static let keyPrefix = "NSSplitView Subview Frames "
    static let keySuffix = ", SidebarNavigationSplitView"

    /// The projects column's stored width, or `nil` if the value is not the
    /// shape AppKit wrote on 25 Sep 2026: an array of strings, one per column,
    /// each `"x, y, width, height, collapsed, hidden"`, the sidebar first.
    static func sidebarWidth(from value: Any) -> CGFloat? {
        guard let columns = value as? [String], let sidebar = columns.first else { return nil }
        let fields = sidebar.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }
        guard fields.count >= 4, let width = Double(fields[2]), width.isFinite, width >= 0 else { return nil }
        return CGFloat(width)
    }

    /// The keys to remove: projects-column autosaves whose stored width is
    /// below `minimum`. Pure, so the rule is testable without a defaults domain.
    static func keysToRemove(in stored: [String: Any], below minimum: CGFloat) -> [String] {
        stored.compactMap { key, value in
            guard key.hasPrefix(keyPrefix), key.hasSuffix(keySuffix),
                  let width = sidebarWidth(from: value), width < minimum else { return nil }
            return key
        }
        .sorted()
    }

    /// Applies the rule to `defaults` and returns what it removed.
    @discardableResult
    static func run(defaults: UserDefaults = .standard,
                    minimum: CGFloat = SidebarAutoCollapse.columnMin) -> [String] {
        let removed = keysToRemove(in: defaults.dictionaryRepresentation(), below: minimum)
        for key in removed { defaults.removeObject(forKey: key) }
        if !removed.isEmpty {
            migrationLog.notice("autosave migration: removed \(removed.count, privacy: .public) column width(s) below \(Int(minimum), privacy: .public)")
        }
        return removed
    }
}
