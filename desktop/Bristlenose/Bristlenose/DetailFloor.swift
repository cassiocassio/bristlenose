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
    ///     showed, or the last such measurement while it is collapsed. Read by
    ///     BOTH branches: the collapse test (window − this) while it shows, and
    ///     the expand test, which asks whether the column would fit at the
    ///     width the researcher last dragged it to, not at an ideal it may not
    ///     have. See `restingColumnWidth` for what is accepted as a measurement.
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
        // A split narrower than any window can be is a mount reading, not a
        // width: SwiftUI reports the split at 1 pt before the window lays out
        // (defect A's sibling, on the split reader). Deciding on it collapsed
        // the column and then expanded it inside one animation — and on macOS
        // 15 the collapse's late visibility write landed after the expand, so
        // the column ended hidden and no longer ours (measured on a 15.7.3
        // VM, 25 Sep 2026: six harness scenarios; macOS 27 happened to recover).
        guard let minWidth, windowWidth >= windowMinWidth else { return .none }
        let detailBesideSidebar = windowWidth - sidebarWidth
        if sidebarVisible {
            return detailBesideSidebar < minWidth ? .collapse : .none
        }
        if autoCollapsed {
            return detailBesideSidebar >= minWidth ? .expand : .none
        }
        return .none
    }

    /// The projects column's width range, declared on the column itself
    /// (`navigationSplitViewColumnWidth` on the sidebar view — on the split
    /// view it is inert: AppKit reported min 140 and no maximum, measured
    /// 25 Sep 2026 by `SidebarFitHarnessTests.s00`).
    ///
    /// The minimum is the COLUMN; the rows the researcher reads are 20 pt
    /// narrower (a 10 pt inset each side on macOS 26/27, measured by AX on
    /// 25 Sep 2026: a 180 column drew 160 pt cells, which read as "the column
    /// came back below its minimum"). 200 puts the cells at the 180 the design
    /// meant. Raising it also raises the collapse threshold by the same
    /// amount — window − column is compared with the floor — which is correct.
    /// Widths stored below it are removed at launch (`SidebarAutosaveMigration`).
    static let columnMin: CGFloat = 200
    /// The main window's minimum content width — the `.frame(minWidth:)` on
    /// `ContentView` in `BristlenoseApp`, which reads this. A split reading
    /// below it cannot be a window, so `decide` ignores it.
    static let windowMinWidth: CGFloat = 700
    static let columnIdeal: CGFloat = 220
    static let columnMax: CGFloat = 300
    /// How far above `columnMax` a genuine resting reading can land, per OS —
    /// measured on VMs, 25 Sep 2026, at the same commit:
    /// - macOS 15.7.3: a classic split with a real 1-pt divider, which split −
    ///   detail counts as column (a 220 column reads 221).
    /// - macOS 26.6.2: AppKit adds 8 pt to every width it applies FROM the
    ///   declaration — the ideal at launch (220 → 228) and both clamps
    ///   (minimum 200 → 208, maximum 300 → 308) — while a divider placed by
    ///   hand lands exactly (220, 260, 300 read as themselves).
    /// - macOS 27: exact.
    /// The rule never uses the declared widths for its arithmetic — it uses the
    /// measured column — so the offset moves the thresholds only by the space
    /// the report really loses. This slack only keeps a column at its maximum
    /// from being rejected as an animation frame.
    static let platformSlack: CGFloat = 8

    /// The column width to remember from one detail-geometry reading, or
    /// `nil` to keep the last one.
    ///
    /// The width is inferred as split − detail, and the two readers report
    /// widths the column never has at rest: a detail of 0 when it mounts (so
    /// "the column" is the whole window, and a taken column never fits again),
    /// and every frame of a hide or show animation (1, 2, 4, 7 … pt). The
    /// column cannot rest outside its declared range, so any reading outside
    /// it is one of those, and is ignored rather than clamped — clamping would
    /// store a width the column did not have either.
    static func restingColumnWidth(splitWidth: CGFloat, detailWidth: CGFloat, sidebarVisible: Bool) -> CGFloat? {
        guard sidebarVisible, splitWidth > 0 else { return nil }
        let width = splitWidth - detailWidth
        guard width >= columnMin, width <= columnMax + platformSlack else { return nil }
        return width
    }

    /// Whether the column is ours after acting on `action`. Set here, at the
    /// write, rather than cleared by `onChange(of: columnVisibility)`: a
    /// collapse and an expand inside one SwiftUI update net to no change, the
    /// onChange never fires, and a showing column stayed marked as ours — so a
    /// column the researcher then hid was given back on the next resize.
    static func autoCollapsed(after action: Action, was current: Bool) -> Bool {
        switch action {
        case .collapse: return true
        case .expand: return false
        case .none: return current
        }
    }
}
