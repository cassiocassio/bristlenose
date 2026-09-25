import AppKit
import Combine
import SwiftUI
import Testing
@testable import Bristlenose

// Diagnosis harness for the projects-sidebar auto-collapse (DetailFloor.swift,
// ContentView.splitViewCore). NOT a fix, and it changes no production code.
//
// It hosts a real NavigationSplitView in a real NSWindow, wired exactly the way
// ContentView wires it (two onGeometryChange readers, the onChange that clears
// `autoCollapsed`, `SidebarAutoCollapse.decide`, the column-width modifier on
// the split view rather than on the sidebar column), then resizes the window
// and toggles the sidebar through AppKit's own `toggleSidebar:`. After each step
// it records both what SwiftUI believes (`visibility`) and what AppKit shows
// (`NSSplitViewItem.isCollapsed`, the sidebar subview's frame).
//
// Mirror of ContentView as of 25 Sep 2026 — lines 559-577 (apply), 582-640
// (split view + readers + onChange), 672 (column width). If that wiring
// changes, this harness must change with it or it is testing a ghost.

// MARK: - The mirror

@MainActor
final class SidebarFitProbe: ObservableObject {
    @Published var visibility: NavigationSplitViewVisibility = .all
    var splitWidth: CGFloat = 0
    var detailWidth: CGFloat = 0
    var lastSidebarWidth: CGFloat = 220
    var autoCollapsed = false
    /// `bridgeHandler.detailMinWidth` stand-in. 0 = the SPA has not reported.
    var webMinWidth: CGFloat = 968
    var showingReport = true
    /// Every callback in arrival order — the ordering is part of the evidence.
    var log: [String] = []
    /// Every value `lastSidebarWidth` was ever assigned.
    var lastSidebarWidthHistory: [CGFloat] = []
    /// Survey knobs. ContentView = animate: true, deferApply: false.
    var animate = true
    var deferApply = false

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

    func apply() {
        if deferApply {
            DispatchQueue.main.async { self.applyNow() }
        } else {
            applyNow()
        }
    }

    private func set(_ v: NavigationSplitViewVisibility) {
        if animate { withAnimation { visibility = v } } else { visibility = v }
    }

    private func applyNow() {
        let action = SidebarAutoCollapse.decide(
            windowWidth: splitWidth,
            sidebarWidth: lastSidebarWidth,
            minWidth: DetailFloor.resolve(webMinWidth: webMinWidth, showingReport: showingReport),
            sidebarVisible: SidebarToggle.isVisible(visibility),
            autoCollapsed: autoCollapsed
        )
        switch action {
        case .collapse:
            autoCollapsed = true
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

/// Where `.navigationSplitViewColumnWidth` goes. ContentView puts it on the
/// NavigationSplitView; SeamLabView puts it on the sidebar column's content.
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
                    if SidebarToggle.isVisible(probe.visibility), probe.splitWidth > 0 {
                        let sidebar = probe.splitWidth - width
                        if sidebar > 0 {
                            probe.lastSidebarWidth = sidebar
                            probe.lastSidebarWidthHistory.append(sidebar)
                        }
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
            probe.note("visibility → \(SidebarFitProbe.name(now))")
        }
        switch placement {
        case .onSplitView:
            split.navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 300)
        case .onSidebarColumn:
            split
        }
    }

    @ViewBuilder private var sidebar: some View {
        let list = List { ForEach(0..<5, id: \.self) { Text("Project \($0)") } }
        switch placement {
        case .onSplitView: list
        case .onSidebarColumn: list.navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 300)
        }
    }
}

// MARK: - The window driver

@MainActor
struct SidebarFitRig {
    let probe = SidebarFitProbe()
    let window: NSWindow

    init(placement: ColumnWidthPlacement = .onSplitView, width: CGFloat = 1400, minWidth: CGFloat = 968,
         animate: Bool = true, deferApply: Bool = false, styled: Bool = false,
         visible: Bool = false) async {
        probe.webMinWidth = minWidth
        probe.animate = animate
        probe.deferApply = deferApply
        let host = NSHostingController(rootView: SidebarFitHarnessView(probe: probe, placement: placement))
        host.sizingOptions = []
        var mask: NSWindow.StyleMask = [.titled, .resizable, .closable, .miniaturizable]
        // The app's WindowGroup window: unified toolbar over full-size content.
        if styled { mask.insert(.fullSizeContentView) }
        window = NSWindow(
            contentRect: NSRect(x: 40, y: 40, width: width, height: 700),
            styleMask: mask,
            backing: .buffered, defer: false)
        if styled {
            window.toolbar = NSToolbar(identifier: "harness")
            window.toolbarStyle = .unified
            window.titlebarAppearsTransparent = false
        }
        window.isReleasedWhenClosed = false
        window.contentViewController = host
        window.setContentSize(NSSize(width: width, height: 700))
        if visible {
            // Unoccluded: AppKit pauses display-link animation for a window
            // nobody can see, and the test host is never the active app.
            window.level = .floating
            NSApp.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
        } else {
            window.orderFront(nil)
        }
        await settle()
    }

    var isVisibleOnScreen: Bool { window.occlusionState.contains(.visible) }

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

    @Test func s00_whatAppKitIsTold() async {
        // Is the column-width declaration live where ContentView puts it?
        for placement in [ColumnWidthPlacement.onSplitView, .onSidebarColumn] {
            let rig = await SidebarFitRig(placement: placement)
            defer { rig.close() }
            rig.dump("s00 placement=\(placement)")
            #expect(rig.splitController != nil, "no NSSplitViewController found — harness blind")
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
        // DEFECT A (mount): the detail reader reports width 0 once, while the
        // column shows, so lastSidebarWidth = split − 0 = the WINDOW width.
        withKnownIssue("defect A: detail geometry 0 at mount records the window width as the column's") {
            #expect(rig.probe.lastSidebarWidthHistory.allSatisfy { $0 <= 320 },
                    "lastSidebarWidth took a value no column had: \(rig.probe.lastSidebarWidthHistory)")
        }
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
        rig.probe.autoCollapsed = false               // the harness launch leaves it stale (s13)
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
        // DEFECTS A + C: the mount value, then every frame of each expand
        // animation (1, 2, 4, 7 … pt) lands in lastSidebarWidth.
        withKnownIssue("defects A + C: lastSidebarWidth takes the window width and mid-animation widths") {
            #expect(rig.probe.lastSidebarWidthHistory.allSatisfy { $0 >= 140 && $0 <= 320 },
                    "lastSidebarWidth history: \(rig.probe.lastSidebarWidthHistory)")
        }
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

    /// Not a pass/fail scenario: a matrix of the knobs that could decide
    /// whether a programmatic collapse/expand made from inside the window's
    /// geometry callback actually lands. One attachment, one row per variant.
    /// Only the "visible pt" column is ground truth (the sidebar subview's
    /// frame); the rest is what each layer believes.
    @Test func survey_whatDecidesAZeroWidthReturn() async {
        var rows = "variant | after 1000: vis/itemCollapsed/visiblePt | after 1700: vis/itemCollapsed/visiblePt\n"
        for placement in [ColumnWidthPlacement.onSplitView, .onSidebarColumn] {
            for animate in [true, false] {
                for deferApply in [false, true] {
                    for styled in [false, true] { for visible in [false, true] {
                        let rig = await SidebarFitRig(placement: placement, width: 1400,
                                                animate: animate, deferApply: deferApply, styled: styled,
                                                visible: visible)
                        await rig.resize(to: 1000)
                        let a = "\(SidebarFitProbe.name(rig.probe.visibility))/\(rig.appKitCollapsed.map(String.init) ?? "nil")/\(Int(rig.appKitSidebarWidth ?? -1))"
                        await rig.resize(to: 1700)
                        let b = "\(SidebarFitProbe.name(rig.probe.visibility))/\(rig.appKitCollapsed.map(String.init) ?? "nil")/\(Int(rig.appKitSidebarWidth ?? -1))"
                        rows += "\(placement) animate=\(animate) defer=\(deferApply) styled=\(styled) onScreen=\(rig.isVisibleOnScreen) | \(a) | \(b)\n"
                        rig.close()
                    } }
                }
            }
        }
        Attachment.record(rows, named: "survey.txt")
    }

    /// Control for the survey: the same animated binding write, with the
    /// window standing still. If this also fails, animation is broken in the
    /// test host generally and the survey proves nothing about resizes.
    @Test func control_animatedToggleWithoutResize() async {
        var rows = "step | vis/itemCollapsed/visiblePt | windowVisible\n"
        for visible in [false, true] {
        let rig = await SidebarFitRig(width: 1400, minWidth: 0, visible: visible)   // no floor: logic never acts
        defer { rig.close() }
        func row(_ step: String) {
            rows += "\(visible ? "floated" : "plain") \(step) | \(SidebarFitProbe.name(rig.probe.visibility))/\(rig.appKitCollapsed.map(String.init) ?? "nil")/\(Int(rig.appKitSidebarWidth ?? -1)) | \(rig.isVisibleOnScreen)\n"
        }
        row("start")
        withAnimation { rig.probe.visibility = .detailOnly }; await rig.settle(); row("animated hide")
        withAnimation { rig.probe.visibility = .all }; await rig.settle(); row("animated show")
        rig.probe.visibility = .detailOnly; await rig.settle(); row("plain hide")
        rig.probe.visibility = .all; await rig.settle(); row("plain show")
        }
        // NOT here, because it kills the test host: an animated visibility
        // write followed at once by a programmatic window resize. SwiftUI's
        // NSHostingView.windowDidLayout → updateAnimatedWindowSize and the
        // setFrame fight over the window frame until AppKit's layout-loop
        // guard throws in -[NSWindow _postWindowNeedsUpdateConstraints]
        // (measured 25 Sep 2026). A shipped app logs and swallows that
        // exception — leaving whatever half-applied layout it interrupted.
        Attachment.record(rows, named: "control.txt")
    }

    /// Does an animated hide move anything at all, and over what time? Samples
    /// the sidebar subview's frame, its layer's presentation position, and
    /// the split view's divider every 50 ms for 2 s.
    @Test func control_animatedHideTimeline() async {
        let rig = await SidebarFitRig(width: 1400, minWidth: 0, visible: true)
        defer { rig.close() }
        var rows = "t(ms) | vis | itemCollapsed | sidebar frame x/w | layer pres x | detail frame x/w\n"
        func sample(_ t: Int) {
            guard let sv = rig.splitController?.splitView, sv.arrangedSubviews.count >= 2 else { return }
            let a = sv.arrangedSubviews[0], b = sv.arrangedSubviews[1]
            let pres = a.layer?.presentation()?.position.x ?? a.layer?.position.x ?? -1
            rows += "\(t) | \(SidebarFitProbe.name(rig.probe.visibility)) | \(rig.appKitCollapsed.map(String.init) ?? "nil") | \(Int(a.frame.minX))/\(Int(a.frame.width)) | \(Int(pres)) | \(Int(b.frame.minX))/\(Int(b.frame.width))\n"
        }
        sample(-1)
        withAnimation { rig.probe.visibility = .detailOnly }
        for i in 0..<40 { await rig.settle(0.05); sample(i * 50) }
        rows += "--- animated show\n"
        withAnimation { rig.probe.visibility = .all }
        for i in 0..<40 { await rig.settle(0.05); sample(i * 50) }
        Attachment.record(rows, named: "timeline.txt")
    }

    // MARK: Isolating the two state defects s07 exposed

    /// Invariant: a showing column is never marked as ours. At launch the
    /// split's first geometry pass is 1 pt wide, so the logic collapses and
    /// then expands inside one update — `onChange(of: visibility)` sees
    /// .all → .all and never clears the flag.
    @Test func s13_ownershipFlagClearedWhenShowing_launch() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        rig.dump("s13 launch 1400")
        withKnownIssue("defect B: collapse+expand inside one update never clears the ours-flag") {
            #expect(!(SidebarToggle.isVisible(rig.probe.visibility) && rig.probe.autoCollapsed),
                    "column is showing but still marked auto-collapsed")
        }
    }

    /// Same invariant, reached the way the shipped app can reach it: two
    /// window frames inside one run-loop turn (a zoom or full-screen exit
    /// can deliver an intermediate frame), collapse then expand, one update.
    @Test func s14_ownershipFlagClearedWhenShowing_sameTurnPair() async {
        let rig = await SidebarFitRig(width: 1400)
        defer { rig.close() }
        rig.probe.autoCollapsed = false          // start clean, whatever launch did
        var f = rig.window.frame
        f.size.width = 1000; rig.window.setFrame(f, display: true, animate: false)
        f.size.width = 1400; rig.window.setFrame(f, display: true, animate: false)
        await rig.settle()
        rig.dump("s14 1400 → 1000 → 1400 in one turn")
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
        withKnownIssue("defect C: the toolbar hide's animation frames are recorded as the column width") {
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
        let transient = rig.probe.lastSidebarWidthHistory.filter { $0 < 140 }
        withKnownIssue("defect C: the expand animation's frames are recorded as the column width") {
            #expect(transient.isEmpty, "recorded mid-animation widths: \(transient)")
        }
    }
}
