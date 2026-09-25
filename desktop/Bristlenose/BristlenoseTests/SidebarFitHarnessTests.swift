import AppKit
import Combine
import SwiftUI
import Testing
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

struct SidebarFitHarnessView: View {
    @ObservedObject var probe: SidebarFitProbe
    let placement: ColumnWidthPlacement

    var body: some View {
        let split = NavigationSplitView(columnVisibility: $probe.visibility) {
            sidebar
        } detail: {
            Color.gray.opacity(0.2)
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
        let list = List { ForEach(0..<5, id: \.self) { Text("Project \($0)") } }
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
    init(placement: ColumnWidthPlacement = .onSidebarColumn, width: CGFloat = 1400,
         minWidth: CGFloat = 968) async {
        probe.webMinWidth = minWidth
        let host = NSHostingController(rootView: SidebarFitHarnessView(probe: probe, placement: placement))
        host.sizingOptions = []
        window = NSWindow(
            contentRect: NSRect(x: 40, y: 40, width: width, height: 700),
            styleMask: [.titled, .resizable, .closable, .miniaturizable],
            backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        window.contentViewController = host
        window.setContentSize(NSSize(width: width, height: 700))
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
}
