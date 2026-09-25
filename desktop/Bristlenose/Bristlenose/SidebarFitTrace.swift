import AppKit
import OSLog
import SwiftUI
import WebKit

/// Opt-in trace of the projects-column auto-collapse (`SidebarAutoCollapse`),
/// for catching the rare "column gone and won't come back" in a real session.
/// Diagnostic only — it reads, never decides.
///
/// Off unless asked for, because the geometry readers fire on every frame of a
/// live resize:
///
///     -BristlenoseDebugSidebarFit YES      (launch argument, in the scheme)
///     /usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "sidebar-fit"'
///
/// Not `defaults write`: the app is sandboxed and Terminal cannot write its
/// container's preferences ("Could not write domain", measured). `.notice` so
/// the default `log stream` shows it; `/usr/bin/log` because zsh's `log`
/// builtin shadows it.
///
/// Each line pairs what the SwiftUI side believes (split/detail/last widths,
/// `columnVisibility`, the ours-flag, the floor) with what AppKit has actually
/// laid out for the key window's sidebar — the two disagreeing is the bug
/// class `SidebarFitHarnessTests` was built to find.
enum SidebarFitTrace {
    private static let log = Logger(subsystem: "app.bristlenose", category: "sidebar-fit")

    static var isEnabled: Bool {
        UserDefaults.standard.bool(forKey: "BristlenoseDebugSidebarFit")
    }

    @MainActor
    static func note(
        _ event: String,
        split: CGFloat,
        detail: CGFloat,
        lastSidebar: CGFloat,
        floor: @autoclosure () -> CGFloat?,
        visibility: NavigationSplitViewVisibility,
        autoCollapsed: Bool
    ) {
        guard isEnabled else { return }
        let floorText = floor().map { "\(Int($0))" } ?? "nil"
        let state = "split=\(Int(split)) detail=\(Int(detail)) last=\(Int(lastSidebar)) "
            + "floor=\(floorText) vis=\(name(visibility)) auto=\(autoCollapsed)"
        log.notice("\(event, privacy: .public) | \(state, privacy: .public) | \(appKitTruth(), privacy: .public)")
    }

    private static func name(_ v: NavigationSplitViewVisibility) -> String {
        switch v {
        case .all: return "all"
        case .detailOnly: return "detailOnly"
        case .doubleColumn: return "doubleColumn"
        case .automatic: return "automatic"
        default: return "?"
        }
    }

    /// The key window's sidebar as AppKit has it. The key window is a
    /// stand-in for "this ContentView's window" — good enough for a trace
    /// read one window at a time.
    @MainActor
    private static func appKitTruth() -> String {
        guard let window = NSApp.keyWindow, let root = window.contentView else { return "appKit=no-key-window" }
        guard let split = findSplitView(in: root) else { return "appKit=no-split win=\(window.windowNumber)" }
        let item = (split.delegate as? NSSplitViewController)?.splitViewItems.first
        let first = split.arrangedSubviews.first
        let fullScreen = window.styleMask.contains(.fullScreen)
        // The report's web view: where it starts in the window and any leading
        // inset it carries. A white strip left of the page after a hide is
        // either this frame (native) or the page's own layout (web) — this
        // line separates the two.
        let web = findWebView(in: root)
        let webFrame = web.map { $0.convert($0.bounds, to: nil) }
        return "appKit win=\(window.windowNumber) frameW=\(Int(window.frame.width)) "
            + "liveResize=\(window.inLiveResize) fullScreen=\(fullScreen) "
            + "itemCollapsed=\(item.map { String($0.isCollapsed) } ?? "nil") "
            + "sidebarW=\(first.map { "\(Int($0.frame.width))" } ?? "nil") "
            + "sidebarHidden=\(first.map { String($0.isHidden) } ?? "nil") "
            + "thickness=\(item.map { "\(Int($0.minimumThickness))…\(Int($0.maximumThickness))" } ?? "nil") "
            + "canCollapseFromResize=\(item.map { String($0.canCollapseFromWindowResize) } ?? "nil") "
            + "webX=\(webFrame.map { "\(Int($0.minX))" } ?? "nil") webW=\(webFrame.map { "\(Int($0.width))" } ?? "nil") "
            + "webSafeLeft=\(web.map { "\(Int($0.safeAreaInsets.left))" } ?? "nil")"
    }

    @MainActor
    private static func findWebView(in view: NSView) -> WKWebView? {
        if let web = view as? WKWebView { return web }
        for sub in view.subviews {
            if let web = findWebView(in: sub) { return web }
        }
        return nil
    }

    @MainActor
    private static func findSplitView(in view: NSView) -> NSSplitView? {
        if let split = view as? NSSplitView { return split }
        for sub in view.subviews {
            if let split = findSplitView(in: sub) { return split }
        }
        return nil
    }
}
