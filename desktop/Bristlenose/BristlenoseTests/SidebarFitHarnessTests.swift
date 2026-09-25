import AppKit
import Combine
import SwiftUI
import Testing
import WebKit
@testable import Bristlenose

// Diagnosis harness for the projects-sidebar auto-collapse (DetailFloor.swift,
// ContentView.splitViewCore). NOT a fix, and it changes no production code.
//
// It hosts a real NavigationSplitView in a real NSWindow, wired the way
// ContentView wires it (two onGeometryChange readers, the onChange that clears
// `autoCollapsed` and re-measures, `SidebarAutoCollapse.decide`, the
// column-width modifier on the sidebar column), then resizes the window
// and toggles the sidebar through AppKit's own `toggleSidebar:`. After each step
// it records both what SwiftUI believes (`visibility`) and what AppKit shows
// (`NSSplitViewItem.isCollapsed`, the sidebar subview's frame).
//
// The two rules that decide — what width to remember, and whether the column
// is ours — are ContentView's own (`SidebarAutoCollapse.restingColumnWidth`,
// `.autoCollapsed(after:was:)`), called here rather than copied. The wiring
// around them (two readers, the onChange, the animated write, the column-width
// modifier on the sidebar column) mirrors `ContentView.splitViewCore`; if that
// changes, this harness must change with it or it is testing a ghost.

// MARK: - The mirror

@MainActor
final class SidebarFitProbe: ObservableObject {
    @Published var visibility: NavigationSplitViewVisibility = .all
    var splitWidth: CGFloat = 0
    var detailWidth: CGFloat = 0
    var lastSidebarWidth: CGFloat = SidebarAutoCollapse.columnIdeal
    var autoCollapsed = false
    /// `bridgeHandler.detailMinWidth` stand-in. 0 = the SPA has not reported.
    var webMinWidth: CGFloat = 968
    var showingReport = true
    /// Every callback in arrival order — the ordering is part of the evidence.
    var log: [String] = []
    /// Every value `lastSidebarWidth` was ever assigned.
    var lastSidebarWidthHistory: [CGFloat] = []

    func note(_ s: String) {
        log.append(s + "  [split=\(Int(splitWidth)) detail=\(Int(detailWidth)) last=\(Int(lastSidebarWidth)) vis=\(Self.name(visibility)) auto=\(autoCollapsed)]")
    }

    static func name(_ v: NavigationSplitViewVisibility) -> String {
        switch v {
        case .all: return "all"
        case .detailOnly: return "detailOnly"
        case .doubleColumn: return "doubleColumn"
        case .automatic: return "automatic"
        default: return "?"
        }
    }

    /// ContentView writes the visibility animated; so does this.
    private func set(_ v: NavigationSplitViewVisibility) {
        withAnimation { visibility = v }
    }

    func apply() {
        let action = SidebarAutoCollapse.decide(
            windowWidth: splitWidth,
            sidebarWidth: lastSidebarWidth,
            minWidth: DetailFloor.resolve(webMinWidth: webMinWidth, showingReport: showingReport),
            sidebarVisible: SidebarToggle.isVisible(visibility),
            autoCollapsed: autoCollapsed
        )
        autoCollapsed = SidebarAutoCollapse.autoCollapsed(after: action, was: autoCollapsed)
        switch action {
        case .collapse:
            note("apply → COLLAPSE")
            set(.detailOnly)
        case .expand:
            note("apply → EXPAND")
            set(.all)
        case .none:
            break
        }
    }
}

/// Where `.navigationSplitViewColumnWidth` goes. ContentView and SeamLabView
/// put it on the sidebar column; on the NavigationSplitView it is inert, which
/// is how it shipped until 25 Sep 2026 (s00 keeps that measured).
enum ColumnWidthPlacement { case onSplitView, onSidebarColumn }

/// What the sidebar column hosts. The app runs the AppKit outline
/// (`ProjectSidebarOutline`, an NSViewControllerRepresentable); `outlineShape`
/// is a stand-in built the way its `loadView` builds it — a zero-frame
/// autoresizing container around a source-list NSOutlineView in a scroll view
/// — without its dozen data dependencies.
enum SidebarKind { case list, outlineShape }

/// What the detail hosts. The app hosts the report in a WKWebView that
/// ignores the top safe area only (ContentView, `.ignoresSafeArea(.container,
/// edges: .top)`), under a sidebar that floats over it on macOS 26.
enum DetailKind { case color, webView }

/// A page with a 200-px left panel at x = 0, standing in for the report's
/// Contents panel: wherever the page's own left edge lands, the panel shows it.
struct HarnessWebView: NSViewRepresentable {
    static var last: WKWebView?
    func makeNSView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.setValue(false, forKey: "drawsBackground")   // as WebView.swift does
        web.loadHTMLString("""
            <html><body style="margin:0"><div id="panel" style="position:absolute;left:0;top:0;\
            width:200px;height:100vh;background:#ddd"></div></body></html>
            """, baseURL: nil)
        Self.last = web
        return web
    }
    func updateNSView(_ web: WKWebView, context: Context) {}
}

struct OutlineShapeStandIn: NSViewControllerRepresentable {
    func makeNSViewController(context: Context) -> NSViewController {
        let controller = NSViewController()
        let outline = NSOutlineView()
        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("main"))
        column.resizingMask = .autoresizingMask
        outline.addTableColumn(column)
        outline.outlineTableColumn = column
        outline.headerView = nil
        outline.style = .sourceList
        outline.autoresizingMask = [.width, .height]
        let scroll = NSScrollView()
        scroll.documentView = outline
        scroll.drawsBackground = false
        let container = NSView()
        container.autoresizingMask = [.width, .height]
        scroll.frame = container.bounds
        scroll.autoresizingMask = [.width, .height]
        container.addSubview(scroll)
        controller.view = container
        return controller
    }
    func updateNSViewController(_ controller: NSViewController, context: Context) {}
}

struct SidebarFitHarnessView: View {
    @ObservedObject var probe: SidebarFitProbe
    let placement: ColumnWidthPlacement
    var kind: SidebarKind = .list
    var detailKind: DetailKind = .color

    var body: some View {
        let split = NavigationSplitView(columnVisibility: $probe.visibility) {
            sidebar
        } detail: {
            Group {
                switch detailKind {
                case .color: Color.gray.opacity(0.2)
                case .webView: HarnessWebView().ignoresSafeArea(.container, edges: .top)
                }
            }
                .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { width in
                    probe.detailWidth = width
                    if let sidebar = SidebarAutoCollapse.restingColumnWidth(
                        splitWidth: probe.splitWidth,
                        detailWidth: width,
                        sidebarVisible: SidebarToggle.isVisible(probe.visibility)
                    ) {
                        probe.lastSidebarWidth = sidebar
                        probe.lastSidebarWidthHistory.append(sidebar)
                    }
                    probe.note("detail geometry \(Int(width))")
                }
        }
        .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { width in
            probe.splitWidth = width
            probe.note("split geometry \(Int(width))")
            probe.apply()
        }
        .onChange(of: probe.visibility) { _, now in
            if SidebarToggle.isVisible(now) { probe.autoCollapsed = false }
            if let sidebar = SidebarAutoCollapse.restingColumnWidth(
                splitWidth: probe.splitWidth,
                detailWidth: probe.detailWidth,
                sidebarVisible: SidebarToggle.isVisible(now)
            ) {
                probe.lastSidebarWidth = sidebar
                probe.lastSidebarWidthHistory.append(sidebar)
            }
            probe.note("visibility → \(SidebarFitProbe.name(now))")
        }
        switch placement {
        case .onSplitView:
            split.navigationSplitViewColumnWidth(
                min: SidebarAutoCollapse.columnMin, ideal: SidebarAutoCollapse.columnIdeal,
                max: SidebarAutoCollapse.columnMax)
        case .onSidebarColumn:
            split
        }
    }

    @ViewBuilder private var sidebar: some View {
        let list = Group {
            switch kind {
            case .list: List { ForEach(0..<5, id: \.self) { Text("Project \($0)") } }
            case .outlineShape: OutlineShapeStandIn()
            }
        }
        switch placement {
        case .onSplitView: list
        case .onSidebarColumn: list.navigationSplitViewColumnWidth(
            min: SidebarAutoCollapse.columnMin, ideal: SidebarAutoCollapse.columnIdeal,
            max: SidebarAutoCollapse.columnMax)
        }
    }
}

// MARK: - The window driver

@MainActor
struct SidebarFitRig {
    let probe = SidebarFitProbe()
    let window: NSWindow

    /// Window style and occlusion were surveyed during the diagnosis (plain
    /// vs unified toolbar over full-size content, floated vs background) and
    /// changed nothing, so the rig uses the plain window.
    /// `identifier`: give the window an identity, as the app's `WindowGroup`
    /// does (`main-AppWindow-N`). With none — every rig until 25 Sep 2026 —
    /// the split view has no autosave name, so nothing is ever stored or
    /// restored, and restore-over-ideal (the whole of symptom S4) could not
    /// be seen here.
    init(placement: ColumnWidthPlacement = .onSidebarColumn, kind: SidebarKind = .list,
         detail: DetailKind = .color, width: CGFloat = 1400, minWidth: CGFloat = 968,
         identifier: String? = nil) async {
        probe.webMinWidth = minWidth
        let host = NSHostingController(rootView: SidebarFitHarnessView(
            probe: probe, placement: placement, kind: kind, detailKind: detail))
        host.sizingOptions = []
        window = NSWindow(
            contentRect: NSRect(x: 40, y: 40, width: width, height: 700),
            styleMask: [.titled, .resizable, .closable, .miniaturizable],
            backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        if let identifier { window.identifier = NSUserInterfaceItemIdentifier(identifier) }
        window.contentViewController = host
        window.setContentSize(NSSize(width: width, height: 700))
        // SwiftUI names the split view's autosave only for windows it builds
        // from a scene (`main-AppWindow-1, SidebarNavigationSplitView`); a
        // plain NSWindow with an identifier gets none (measured 25 Sep 2026,
        // s21's first run). So the rig names it the same way, as soon as the
        // split view exists and before the window is shown.
        if let identifier {
            window.contentView?.layoutSubtreeIfNeeded()
            splitController?.splitView.autosaveName = identifier + SidebarAutosaveMigration.keySuffix
        }
        window.orderFront(nil)
        await settle()
    }

    func close() { window.orderOut(nil); window.close() }

    /// Suspends rather than spinning the run loop: SwiftUI drives animation
    /// through the main queue, which a synchronous `RunLoop.run` inside a test
    /// body holds — every animation then freezes at frame 0 (measured).
    func settle(_ seconds: Double = 0.7) async {
        try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
    }

    /// One jump, as a full-screen exit or a zoom lands.
    func resize(to width: CGFloat, settleFor s: Double = 0.7) async {
        var f = window.frame
        f.size.width = width
        window.setFrame(f, display: true, animate: false)
        probe.note("── window → \(Int(width))")
        await settle(s)
    }

    /// Many small steps, as a live drag of the window edge delivers them.
    func drag(from a: CGFloat, to b: CGFloat, step: CGFloat = 12, frame: Double = 0.016) async {
        let n = max(1, Int(abs(b - a) / step))
        for i in 1...n {
            var f = window.frame
            f.size.width = a + (b - a) * CGFloat(i) / CGFloat(n)
            window.setFrame(f, display: true, animate: false)
            await settle(frame)
        }
        probe.note("── drag \(Int(a))→\(Int(b)) done")
        await settle()
    }

    /// AppKit's toggle — what the toolbar button and View menu send.
    func appKitToggle() async {
        let sent = NSApp.sendAction(#selector(NSSplitViewController.toggleSidebar(_:)), to: splitController, from: nil)
        probe.note("── appKit toggleSidebar sent=\(sent)")
        await settle()
    }

    /// What ContentView's menu does: write the binding.
    func bindingToggle() async {
        probe.visibility = SidebarToggle.next(probe.visibility)
        probe.note("── binding toggle")
        await settle()
    }

    // AppKit truth.
    var splitController: NSSplitViewController? {
        func find(_ v: NSView) -> NSSplitView? {
            if let s = v as? NSSplitView { return s }
            for sub in v.subviews { if let s = find(sub) { return s } }
            return nil
        }
        guard let root = window.contentView, let sv = find(root) else { return nil }
        return sv.delegate as? NSSplitViewController
    }
    var sidebarItem: NSSplitViewItem? { splitController?.splitViewItems.first }
    var appKitCollapsed: Bool? { sidebarItem?.isCollapsed }
    var appKitSidebarWidth: CGFloat? {
        guard let sv = splitController?.splitView, let first = sv.arrangedSubviews.first else { return nil }
        return sv.isSubviewCollapsed(first) ? 0 : first.frame.width
    }

    var truth: String {
        let item = sidebarItem
        return "appKit collapsed=\(appKitCollapsed.map(String.init) ?? "nil") width=\(appKitSidebarWidth.map { "\(Int($0))" } ?? "nil") "
            + "min=\(item.map { "\(Int($0.minimumThickness))" } ?? "nil") max=\(item.map { "\(Int($0.maximumThickness))" } ?? "nil") "
            + "canCollapseFromResize=\(item.map { String($0.canCollapseFromWindowResize) } ?? "nil") "
            + "subviews=\(subviewDescription) "
            + "| swiftUI vis=\(SidebarFitProbe.name(probe.visibility)) auto=\(probe.autoCollapsed) last=\(Int(probe.lastSidebarWidth))"
    }

    /// Every arranged subview: frame x/width, hidden, split-collapsed.
    var subviewDescription: String {
        guard let sv = splitController?.splitView else { return "nil" }
        return sv.arrangedSubviews.enumerated().map { i, v in
            "[\(i) x=\(Int(v.frame.minX)) w=\(Int(v.frame.width)) hidden=\(v.isHidden) svCollapsed=\(sv.isSubviewCollapsed(v))]"
        }.joined(separator: "")
    }

    /// What is actually drawn, as a PNG attachment.
    func snapshot(_ label: String) {
        guard let view = window.contentView,
              let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        if let png = rep.representation(using: .png, properties: [:]) {
            Attachment.record(png, named: label.replacingOccurrences(of: " ", with: "_") + ".png")
        }
    }

    /// SwiftUI and AppKit agree on whether the column shows.
    var inAgreement: Bool {
        guard let c = appKitCollapsed else { return false }
        return c == !SidebarToggle.isVisible(probe.visibility)
    }

    /// xcodebuild drops test stdout and TCC blocks reading the container tmp
    /// from outside, so the trace rides a Swift Testing attachment into the
    /// .xcresult (`xcresulttool export attachments`).
    func dump(_ label: String) {
        var text = "=== \(label): \(truth)\n"
        for line in probe.log { text += "    " + line + "\n" }
        probe.log.removeAll()
        Attachment.record(text, named: label.replacingOccurrences(of: " ", with: "_") + ".txt")
        snapshot(label)
    }
}

// MARK: - Scenarios
//
// Each scenario asserts the DESIRED behaviour (docs/design-sidebar-playground.md
// § Fit to width) and prints its full trace, so a failure arrives with its
// evidence. Floor = 968 (default panels: 368 + 240 + 280 + 80). Column ≈ 220,
// so the threshold window is ≈ 1188.

@Suite(.serialized) @MainActor struct SidebarFitHarnessTests {

    static let columnRange = SidebarAutoCollapse.columnMin...SidebarAutoCollapse.columnMax

    @Test func s00_whatAppKitIsTold() async {
        // The declared range is load-bearing: `restingColumnWidth` ignores any
        // reading outside it. If the modifier went inert again the column would
        // rest near 144, every reading would be rejected, and the collapse
        // threshold would be off by ~76 pt with nothing else red.
        for placement in [ColumnWidthPlacement.onSplitView, .onSidebarColumn] {
            let rig = await SidebarFitRig(placement: placement)
            defer { rig.close() }
            rig.dump("s00 placement=\(placement)")
            #expect(rig.splitController != nil, "no NSSplitViewController found — harness blind")
            if placement == .onSidebarColumn {
                #expect(rig.sidebarItem?.minimumThickness == SidebarAutoCollapse.columnMin)
                #expect(rig.sidebarItem?.maximumThickness == SidebarAutoCollapse.columnMax)
            }
        }
    }

    @Test func s01_baselineAgrees() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        rig.dump("s01 baseline 1400")
        #expect(rig.inAgreement)
        #expect(rig.appKitCollapsed == false)
        // The measurement the expand test will rely on must equal the real column.
        if let real = rig.appKitSidebarWidth {
            #expect(abs(rig.probe.lastSidebarWidth - real) <= 2,
                    "lastSidebarWidth \(rig.probe.lastSidebarWidth) ≠ real column \(real)")
        }
    }

    @Test func s02_dragNarrowCollapsesThenDragWideRestores() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.drag(from: 1400, to: 1000)
        rig.dump("s02a dragged to 1000")
        #expect(rig.appKitCollapsed == true, "column should have given way at ≈1188")
        #expect(rig.probe.autoCollapsed, "collapse should be marked ours")
        await rig.drag(from: 1000, to: 1400)
        rig.dump("s02b dragged back to 1400")
        #expect(rig.appKitCollapsed == false, "column we took should come back")
        #expect(rig.inAgreement)
    }

    @Test func s03_jumpNarrowAsFullScreenExitDoes() async {
        // Full-screen exit / un-zoom: one frame jump, not a drag.
        let rig = await SidebarFitRig(width: 1700)
        defer { rig.close() }
        await rig.resize(to: 1250)   // still fits: 1250 − 220 = 1030 ≥ 968
        rig.dump("s03a 1700 → 1250 (fits)")
        #expect(rig.appKitCollapsed == false, "column fits at 1250 and must stay")
        // Defect A (fixed 25 Sep 2026): the detail reader reports width 0 once
        // at mount, while the column shows, so split − detail was the WINDOW
        // width — and a column taken after that never fitted again.
        #expect(rig.probe.lastSidebarWidthHistory.allSatisfy { SidebarFitHarnessTests.columnRange.contains($0) },
                "lastSidebarWidth took a value no column had: \(rig.probe.lastSidebarWidthHistory)")
        await rig.resize(to: 1000)   // does not fit
        await rig.resize(to: 1700)   // fits again
        rig.dump("s03b 1250 → 1000 → 1700")
        #expect(rig.appKitCollapsed == false, "column we took should come back after a jump")
        #expect(rig.inAgreement)
    }

    @Test func s04_jumpWideFromCollapsed() async {
        let rig = await SidebarFitRig(width: 1000)
        defer { rig.close() }
        rig.dump("s04a opened at 1000")
        await rig.resize(to: 1728)
        rig.dump("s04b 1000 → 1728")
        // Opened narrow: was it ours? At launch the column shows (.all), so the
        // first geometry pass collapses it and marks it ours → must come back.
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
    }

    @Test func s05_appKitToggleWhileAutoCollapsed() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.resize(to: 1000)
        rig.dump("s05a collapsed by width")
        await rig.appKitToggle()
        rig.dump("s05b appKit toggleSidebar")
        #expect(rig.appKitCollapsed == false, "toolbar toggle must show the column")
        #expect(rig.inAgreement, "SwiftUI and AppKit disagree after an AppKit toggle")
        await rig.appKitToggle()
        await rig.appKitToggle()
        rig.dump("s05c toggled twice more")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
    }

    @Test func s06_bindingToggleWhileAutoCollapsed() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.resize(to: 1000)
        await rig.bindingToggle()
        rig.dump("s06 binding toggle at 1000")
        #expect(rig.appKitCollapsed == false, "menu toggle must show the column")
        #expect(rig.inAgreement)
    }

    @Test func s07_userHidesThenWindowGrows() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.appKitToggle()                      // researcher hides it
        await rig.resize(to: 1000)
        await rig.resize(to: 1700)
        rig.dump("s07 user-hidden, 1400 → 1000 → 1700")
        #expect(rig.appKitCollapsed == true, "a column the researcher hid is never given back")
        #expect(rig.inAgreement)
    }

    @Test func s08_showInNarrowThenNudge() async {
        // Documented: shown in a narrow window stays shown until the next resize.
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.resize(to: 1000)
        await rig.appKitToggle()
        await rig.resize(to: 1010)                    // nudge
        rig.dump("s08 shown at 1000, nudged to 1010")
        #expect(rig.appKitCollapsed == true, "next resize should take it again")
        #expect(rig.probe.autoCollapsed)
        await rig.resize(to: 1700)
        rig.dump("s08b → 1700")
        #expect(rig.appKitCollapsed == false)
    }

    @Test func s09_floorArrivesLate() async {
        // Project switch: detailMinWidth resets to 0, the SPA posts later. The
        // window does not move in between, so nothing re-evaluates.
        let rig = await SidebarFitRig(width: 1100, minWidth: 0)
        defer { rig.close() }
        rig.probe.webMinWidth = 968
        await rig.settle()
        rig.dump("s09 floor 0 → 968 at 1100, no resize")
        // Documented behaviour: the window is the only trigger, so it stays shown.
        #expect(rig.appKitCollapsed == false)
    }

    @Test func s10_repeatedJumpsAcrossThreshold() async {
        // Hammer the threshold with jumps of the sizes a zoom/full-screen gives.
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        for w: CGFloat in [1728, 1180, 1728, 1190, 1500, 900, 1728, 1200, 1728] {
            await rig.resize(to: w, settleFor: 0.5)
        }
        rig.dump("s10 threshold jumps (ends at 1728)")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
    }

    @Test func s11_resizeDuringCollapseAnimation() async {
        // A second resize landing while the collapse animation is in flight.
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.resize(to: 1000, settleFor: 0.05)
        await rig.resize(to: 1700, settleFor: 0.05)
        await rig.resize(to: 1000, settleFor: 0.05)
        await rig.resize(to: 1700)
        rig.dump("s11 flicker through animation, ends 1700")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
    }

    @Test func s12_toggleDuringCollapseAnimation() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.resize(to: 1000, settleFor: 0.05)
        await rig.appKitToggle()
        rig.dump("s12 toggled mid-collapse at 1000")
        #expect(rig.inAgreement)
        await rig.appKitToggle()
        await rig.appKitToggle()
        rig.dump("s12b two more toggles")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
    }

    // MARK: Isolating the two state defects s07 exposed

    /// Invariant: a showing column is never marked as ours. The only scenario
    /// that reproduced defect B — a same-turn pair of window frames did not.
    /// At launch the
    /// split's first geometry pass is 1 pt wide, so the logic collapses and
    /// then expands inside one update — `onChange(of: visibility)` sees
    /// .all → .all and never clears the flag.
    @Test func s13_ownershipFlagClearedWhenShowing_launch() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        rig.dump("s13 launch 1400")
        // Defect B (fixed 25 Sep 2026).
        #expect(!(SidebarToggle.isVisible(rig.probe.visibility) && rig.probe.autoCollapsed),
                "column is showing but still marked auto-collapsed")
    }

    /// Invariant: `lastSidebarWidth` is a width the column really had at
    /// rest. The toolbar button (AppKit toggleSidebar:) starts the collapse
    /// animation before SwiftUI's binding flips, so the detail reader records
    /// the animation's frames as the column's width.
    @Test func s15_toolbarHideKeepsTheColumnWidth() async {
        let rig = await SidebarFitRig(width: 1400, minWidth: 0)   // no floor: logic stays out
        defer { rig.close() }
        let before = rig.probe.lastSidebarWidth
        await rig.appKitToggle()
        rig.dump("s15 toolbar hide at 1400")
        #expect(rig.appKitCollapsed == true)
        // Residual of defect C, deliberately left: the toolbar's hide animation
        // runs before the binding flips, and the frames that fall inside the
        // column's range are still recorded — measured 220 → 182. It lives
        // only while the column is hidden, when the value is read only to give
        // back a column WE took (a researcher-hidden one never is — s07); the
        // show re-measures at rest (s18). Fixing the hide itself would need a
        // signal for "the column is animating", which nothing here has.
        // Note what this does NOT supervise: withKnownIssue absorbs the failure
        // however far the value drifts, so a regression to 90 would read green
        // here too. restingColumnWidth's range is what bounds it (DetailFloorTests).
        // Intermittent: whether an in-range frame is sampled is display-link timing.
        withKnownIssue("residual C: toolbar hide records in-range animation frames (unconsulted)",
                       isIntermittent: true) {
            #expect(abs(rig.probe.lastSidebarWidth - before) <= 2,
                    "lastSidebarWidth \(before) → \(rig.probe.lastSidebarWidth); history \(rig.probe.lastSidebarWidthHistory)")
        }
    }

    /// Control for s15: the menu path writes the binding (animated) first.
    @Test func s16_menuHideKeepsTheColumnWidth() async {
        let rig = await SidebarFitRig(width: 1400, minWidth: 0)
        defer { rig.close() }
        let before = rig.probe.lastSidebarWidth
        withAnimation { rig.probe.visibility = SidebarToggle.next(rig.probe.visibility) }
        await rig.settle()
        rig.dump("s16 menu hide at 1400")
        #expect(rig.appKitCollapsed == true)
        #expect(abs(rig.probe.lastSidebarWidth - before) <= 2,
                "lastSidebarWidth \(before) → \(rig.probe.lastSidebarWidth)")
    }

    /// Invariant during a live expand: the width recorded while the column
    /// animates open is not the column's width. A window resize landing in
    /// that window decides against a column of a few points.
    @Test func s17_expandAnimationFramesAreNotTheColumnWidth() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        await rig.resize(to: 1000)
        rig.probe.lastSidebarWidthHistory.removeAll()
        await rig.resize(to: 1400)
        rig.dump("s17 expand 1000 → 1400")
        let transient = rig.probe.lastSidebarWidthHistory.filter { !SidebarFitHarnessTests.columnRange.contains($0) }
        // Defect C on the expand path (fixed 25 Sep 2026).
        #expect(transient.isEmpty, "recorded mid-animation widths: \(transient)")
    }

    /// The residual's other half: after a toolbar hide (which records in-range
    /// animation frames), does a toolbar show re-record the column at rest?
    /// `lastSidebarWidth` is read in the collapse branch too, so a value that
    /// survives the show would misjudge the next collapse.
    @Test func s18_toolbarShowReRecordsTheColumnAtRest() async {
        let rig = await SidebarFitRig(width: 1400, minWidth: 0)
        defer { rig.close() }
        await rig.appKitToggle()   // hide
        let afterHide = rig.probe.lastSidebarWidth
        await rig.appKitToggle()   // show
        rig.dump("s18 toolbar hide → show at 1400 (after hide: \(Int(afterHide)))")
        #expect(rig.appKitCollapsed == false)
        if let real = rig.appKitSidebarWidth {
            #expect(abs(rig.probe.lastSidebarWidth - real) <= 2,
                    "after hide \(afterHide), after show \(rig.probe.lastSidebarWidth), real column \(real)")
        }
    }

    /// Can the researcher resize the column? Reads AppKit's thickness range
    /// and moves the divider the way a drag ends, for each sidebar kind and
    /// each modifier placement. Reported 25 Sep 2026: with the AppKit outline
    /// the column showed the resize cursor and would not move.
    @Test func s19_theColumnResizesForEachSidebarKind() async {
        var rows = "kind placement | min max | start → after setPosition(260) → after setPosition(210)\n"
        for kind in [SidebarKind.list, .outlineShape] {
            for placement in [ColumnWidthPlacement.onSplitView, .onSidebarColumn] {
                let rig = await SidebarFitRig(placement: placement, kind: kind, minWidth: 0)
                let start = rig.appKitSidebarWidth ?? -1
                rig.splitController?.splitView.setPosition(260, ofDividerAt: 0)
                await rig.settle()
                let wide = rig.appKitSidebarWidth ?? -1
                rig.splitController?.splitView.setPosition(210, ofDividerAt: 0)
                await rig.settle()
                let narrow = rig.appKitSidebarWidth ?? -1
                let item = rig.sidebarItem
                rows += "\(kind) \(placement) | \(Int(item?.minimumThickness ?? -1)) \(Int(item?.maximumThickness ?? -1)) | \(Int(start)) → \(Int(wide)) → \(Int(narrow))\n"
                if placement == .onSidebarColumn {
                    #expect(abs(wide - 260) <= 2, "\(kind): column did not follow the divider to 260 (got \(wide))")
                    #expect(abs(narrow - 210) <= 2, "\(kind): column did not follow the divider to 210 (got \(narrow))")
                }
                rig.close()
            }
        }
        Attachment.record(rows, named: "s19.txt")
    }

    // MARK: Mounted as the app mounts: the floor arrives AFTER the window
    //
    // Every rig above sets the floor before the window exists. The app cannot:
    // the floor is the SPA's `panel-state`, which cannot be posted before the
    // page loads, which cannot happen before the window. On a macOS 15.7.3 VM
    // (25 Sep 2026) six scenarios failed because a 1-pt mount reading with a
    // floor already set collapsed the column, an expand followed inside the
    // same animation, and the collapse's late visibility write landed last —
    // ending hidden, not ours, never given back. These four mount with no
    // floor, post it once the window is up, and then cross the threshold, so
    // whether that ordering reaches the APP is measured rather than assumed.
    // The invariant each asserts beyond its own ending: a column this logic
    // hid is marked ours, so it is never left hidden-and-not-ours without the
    // researcher having hidden it.

    private func rigWithLateFloor(width: CGFloat = 1400) async -> SidebarFitRig {
        let rig = await SidebarFitRig(width: width, minWidth: 0)
        rig.probe.webMinWidth = 968
        await rig.settle(0.3)
        return rig
    }

    private func expectNotStranded(_ rig: SidebarFitRig, _ label: String) {
        let strandedByUs = rig.appKitCollapsed == true && !rig.probe.autoCollapsed
        #expect(!strandedByUs, "\(label): column hidden but not marked ours, with no researcher hide — it will never come back")
    }

    @Test func s22a_lateFloor_dragAcrossAndBack() async {
        let rig = await rigWithLateFloor()
        defer { rig.close() }
        await rig.drag(from: 1400, to: 1000)
        rig.dump("s22a dragged to 1000")
        #expect(rig.appKitCollapsed == true)
        #expect(rig.probe.autoCollapsed)
        await rig.drag(from: 1000, to: 1400)
        rig.dump("s22a dragged back to 1400")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
        expectNotStranded(rig, "s22a")
    }

    @Test func s22b_lateFloor_thresholdJumps() async {
        let rig = await rigWithLateFloor()
        defer { rig.close() }
        for w: CGFloat in [1728, 1180, 1728, 1190, 1500, 900, 1728, 1200, 1728] {
            await rig.resize(to: w, settleFor: 0.5)
        }
        rig.dump("s22b threshold jumps (ends at 1728)")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
        expectNotStranded(rig, "s22b")
    }

    @Test func s22c_lateFloor_flickerThroughAnimation() async {
        let rig = await rigWithLateFloor()
        defer { rig.close() }
        await rig.resize(to: 1000, settleFor: 0.05)
        await rig.resize(to: 1700, settleFor: 0.05)
        await rig.resize(to: 1000, settleFor: 0.05)
        await rig.resize(to: 1700)
        rig.dump("s22c flicker through animation, ends 1700")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
        expectNotStranded(rig, "s22c")
    }

    /// The suspected race on its own: from a stable, shown column, a collapse
    /// and an expand inside one animation.
    @Test func s22d_lateFloor_collapseThenExpandInsideOneAnimation() async {
        let rig = await rigWithLateFloor()
        defer { rig.close() }
        #expect(rig.appKitCollapsed == false, "precondition: shown at 1400 with the floor posted")
        await rig.resize(to: 1000, settleFor: 0.05)
        await rig.resize(to: 1400, settleFor: 1.2)
        rig.dump("s22d 1400 → 1000 → 1400 inside one animation")
        #expect(rig.appKitCollapsed == false)
        #expect(rig.inAgreement)
        expectNotStranded(rig, "s22d")
    }

    /// Restore-over-ideal, and the migration that fixes the clamped case.
    ///
    /// A window with an identity restores its column from
    /// `NSSplitView Subview Frames <identifier>, SidebarNavigationSplitView`,
    /// clamping a stored width below the minimum UP to the minimum — which is
    /// how 148 (the pre-fix resting width) became a column stuck at its
    /// narrowest (docs/sidebar-column-diagnosis.md, S4). The control seeds
    /// 148 and launches: the column opens at the minimum, not the ideal. The
    /// fix seeds 148, runs the migration, and launches: the ideal applies.
    @Test func s21_storedWidthBelowMinimumIsClampedUnlessMigrated() async {
        let defaults = UserDefaults.standard
        let frames148 = ["0.000000, 0.000000, 148.000000, 700.000000, NO, NO",
                         "148.000000, 0.000000, 1252.000000, 700.000000, NO, NO"]
        func key(_ id: String) -> String {
            SidebarAutosaveMigration.keyPrefix + id + SidebarAutosaveMigration.keySuffix
        }
        let control = "harness-s21-control-\(UUID().uuidString.prefix(8))"
        let fixed = "harness-s21-migrated-\(UUID().uuidString.prefix(8))"
        defer {
            defaults.removeObject(forKey: key(control))
            defaults.removeObject(forKey: key(fixed))
        }

        // Control: the stored width is restored, clamped to the minimum.
        defaults.set(frames148, forKey: key(control))
        let before = await SidebarFitRig(width: 1400, minWidth: 0, identifier: control)
        let autosaveName = before.splitController?.splitView.autosaveName ?? "nil"
        let clamped = before.appKitSidebarWidth ?? -1
        before.dump("s21a control, stored 148, autosaveName=\(autosaveName)")
        before.close()
        #expect(autosaveName == control + SidebarAutosaveMigration.keySuffix,
                "the rig did not name the split view's autosave: \(autosaveName)")

        // Fix: migrate before the window exists; the ideal applies.
        defaults.set(frames148, forKey: key(fixed))
        let removed = SidebarAutosaveMigration.run(defaults: defaults)
        #expect(removed.contains(key(fixed)))
        let after = await SidebarFitRig(width: 1400, minWidth: 0, identifier: fixed)
        let restored = after.appKitSidebarWidth ?? -1
        after.dump("s21b migrated, stored 148 removed")
        after.close()
        // Asserted as a DIFFERENCE, because the declared widths land 8 pt wide
        // on macOS 26.6 (min 200 → 208, ideal 220 → 228) and exactly on 15 and
        // 27 (measured on VMs, 25 Sep 2026). Whatever the platform offset, the
        // clamped launch opens at the minimum and the migrated one at the
        // ideal, so they differ by exactly ideal − minimum.
        let offset = restored - SidebarAutoCollapse.columnIdeal
        Attachment.record("clamped \(clamped), migrated \(restored), platform offset \(offset)", named: "s21-widths.txt")
        #expect(abs((restored - clamped) - (SidebarAutoCollapse.columnIdeal - SidebarAutoCollapse.columnMin)) <= 1,
                "clamped launch \(clamped) and migrated launch \(restored) should differ by ideal − minimum")
        #expect((0...SidebarAutoCollapse.platformSlack).contains(offset),
                "migrated launch \(restored) is not the ideal \(SidebarAutoCollapse.columnIdeal) within the measured platform offset")
    }

    /// Where does a web page's left edge land after the column hides again?
    /// Reported 25 Sep 2026: after show → hide, the report's Contents panel
    /// sat ~70 pt in from the window edge with white to its left. Reads the
    /// web view's frame in the window, its leading safe-area inset, and the
    /// page's own panel position from inside the page.
    @Test func s20_webDetailLeftEdgeAcrossHideShow() async {
        var rows = "kind step | sidebarW collapsed | webView x/w | safeArea.left | page innerWidth panelLeft\n"
        for kind in [SidebarKind.list, .outlineShape] {
            let rig = await SidebarFitRig(kind: kind, detail: .webView, width: 1000, minWidth: 0)
            await rig.settle(1.5)   // page load
            func row(_ step: String) async {
                let web = HarnessWebView.last
                let frame = web.map { $0.convert($0.bounds, to: nil) } ?? .zero
                let js = try? await web?.evaluateJavaScript(
                    "innerWidth + ' ' + document.getElementById('panel').getBoundingClientRect().left")
                // The web view starts where the column ends, and the page's own
                // left edge is the web view's — no inset left behind by a hide.
                let columnEdge = rig.appKitCollapsed == true ? 0 : (rig.appKitSidebarWidth ?? -1)
                #expect(abs(frame.minX - columnEdge) <= 1, "\(kind) \(step): web view at \(frame.minX), column edge \(columnEdge)")
                #expect((js as? String)?.hasSuffix(" 0") == true, "\(kind) \(step): page panel at \(String(describing: js))")
                rows += "\(kind) \(step) | \(Int(rig.appKitSidebarWidth ?? -1)) \(rig.appKitCollapsed.map(String.init) ?? "nil") | "
                    + "\(Int(frame.minX))/\(Int(frame.width)) | \(Int(web?.safeAreaInsets.left ?? -1)) | \((js as? String) ?? "js-failed")\n"
            }
            await row("start (shown)")
            await rig.appKitToggle(); await row("toolbar hide")
            await rig.appKitToggle(); await row("toolbar show")
            await rig.appKitToggle(); await row("toolbar hide again")
            withAnimation { rig.probe.visibility = .all }; await rig.settle(); await row("menu show")
            withAnimation { rig.probe.visibility = .detailOnly }; await rig.settle(); await row("menu hide")
            rig.probe.visibility = .all; await rig.settle()
            rig.splitController?.splitView.setPosition(260, ofDividerAt: 0); await rig.settle(); await row("shown, divider → 260")
            rig.close()
        }
        Attachment.record(rows, named: "s20.txt")
    }
}
