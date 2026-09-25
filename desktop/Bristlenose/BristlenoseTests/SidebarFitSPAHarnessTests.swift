import AppKit
import Combine
import SwiftUI
import Testing
import WebKit
@testable import Bristlenose

// The sidebar-fit harness with the REAL report in the detail.
//
// `SidebarFitHarnessTests` hosts a stub page and is clean on every symptom
// reported after ca00e7c8 (S4–S7 in docs/sidebar-column-diagnosis.md). What it
// does not have is the SPA: its `ResizeObserver` → `setLayoutContext` fit
// cascade, its `panel-state` post (the floor), and a `<div class="layout">`
// that is a CSS grid rather than an absolutely-positioned panel. This file
// adds exactly that and nothing else — the same NavigationSplitView, the same
// two geometry readers, the same `onChange`, the same rules
// (`SidebarAutoCollapse`), the same column-width modifier on the sidebar
// column, the same `.ignoresSafeArea(.container, edges: .top)` on the web
// view, the same `ZStack` with a boot cover under it, the same
// `.frame(minWidth: 700, minHeight: 500)` the app puts on the window's root.
//
// It needs a serve to load from. Run one on the smoke fixture first:
//
//     _BRISTLENOSE_AUTH_TOKEN=harness-token .venv/bin/bristlenose serve \
//         tests/fixtures/smoke-test/input --port 8199 --no-open
//
// Every test here SKIPS (records nothing red) when nothing answers on that
// port, so the suite stays green on a machine with no serve up. Diagnosis
// only; no production code is touched.
//
// Each row records three views of one moment: what AppKit laid out (column
// width and thickness range, the divider's legal range, the detail subview's
// frame), where the WKWebView sits in the window, and what the PAGE thinks
// (innerWidth, the `.layout` grid's rect and classes, the `.center` column's
// rect). Symptom S6 (a white strip / a centred page) is native if the web view
// is narrower than the detail, and web if the web view fills the detail but
// `.layout` does not fill the web view. S7 (the left panel does not come back)
// is the `toc-open` class on `.layout`. S4 is the column's width after a show.
// S5 is the divider's legal range: min == max is a divider that cannot move.

// MARK: - The page side

@MainActor
final class SPAProbe: ObservableObject {
    @Published var visibility: NavigationSplitViewVisibility = .all
    var splitWidth: CGFloat = 0
    var detailWidth: CGFloat = 0
    var lastSidebarWidth: CGFloat = SidebarAutoCollapse.columnIdeal
    var autoCollapsed = false
    /// `bridgeHandler.detailMinWidth`: the SPA's `panel-state.minWidth`, 0 until posted.
    var webMinWidth: CGFloat = 0
    var leftOpen = false
    var ready = false
    var panelStatePosts = 0
    var log: [String] = []

    func note(_ s: String) {
        log.append(s + "  [split=\(Int(splitWidth)) detail=\(Int(detailWidth)) last=\(Int(lastSidebarWidth)) floor=\(Int(webMinWidth)) vis=\(SidebarFitProbe.name(visibility)) auto=\(autoCollapsed)]")
    }

    /// ContentView.applySidebarAutoCollapse, with the real floor.
    func apply() {
        let action = SidebarAutoCollapse.decide(
            windowWidth: splitWidth,
            sidebarWidth: lastSidebarWidth,
            minWidth: DetailFloor.resolve(webMinWidth: webMinWidth, showingReport: true),
            sidebarVisible: SidebarToggle.isVisible(visibility),
            autoCollapsed: autoCollapsed
        )
        autoCollapsed = SidebarAutoCollapse.autoCollapsed(after: action, was: autoCollapsed)
        switch action {
        case .collapse: note("apply → COLLAPSE"); withAnimation { visibility = .detailOnly }
        case .expand: note("apply → EXPAND"); withAnimation { visibility = .all }
        case .none: break
        }
    }
}

/// The report's WKWebView, built as `WebView.makeNSView` builds it: embedded
/// flag and token injected at document start, `drawsBackground` off, a
/// `navigation` message handler. Plus one line the app does not have: the
/// left panel (and on Quotes the tag sidebar) opened through localStorage
/// before the SPA's store reads it, so the page carries a wish to fit.
struct SPAWebView: NSViewRepresentable {
    static let port = 8199
    static let token = "harness-token"
    static var last: WKWebView?
    let lens: String
    let probe: SPAProbe

    static func url(_ lens: String) -> URL { URL(string: "http://127.0.0.1:\(port)/report/\(lens)/")! }

    func makeCoordinator() -> Coordinator { Coordinator(probe: probe) }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        let ucc = WKUserContentController()
        let wish = lens == "quotes"
            ? "localStorage.setItem('bn-toc-open','true');localStorage.setItem('bn-tags-open','true');"
            : "localStorage.setItem('bn-toc-open','true');"
        ucc.addUserScript(WKUserScript(
            source: "window.__BRISTLENOSE_EMBEDDED__ = true; window.__BRISTLENOSE_AUTH_TOKEN__ = '\(Self.token)'; try { \(wish) } catch (e) {}",
            injectionTime: .atDocumentStart, forMainFrameOnly: true))
        ucc.add(context.coordinator, name: "navigation")
        config.userContentController = ucc
        let web = WKWebView(frame: .zero, configuration: config)
        web.setValue(false, forKey: "drawsBackground")
        web.load(URLRequest(url: Self.url(lens)))
        Self.last = web
        return web
    }

    func updateNSView(_ web: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKScriptMessageHandler {
        let probe: SPAProbe
        init(probe: SPAProbe) { self.probe = probe }
        func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
            guard let body = message.body as? [String: Any], let type = body["type"] as? String else { return }
            let probe = self.probe
            Task { @MainActor in
                switch type {
                case "ready": probe.ready = true; probe.note("page ready")
                case "panel-state":
                    let min = CGFloat(body["minWidth"] as? Double ?? 0)
                    let left = body["leftOpen"] as? Bool ?? false
                    probe.panelStatePosts += 1
                    if min != probe.webMinWidth || left != probe.leftOpen {
                        probe.webMinWidth = min; probe.leftOpen = left
                        probe.note("panel-state minWidth=\(Int(min)) leftOpen=\(left)")
                    }
                default: break
                }
            }
        }
    }
}

struct SPAHarnessView: View {
    @ObservedObject var probe: SPAProbe
    let lens: String
    /// Whether the detail mirrors ContentView's extra layers (ZStack + boot
    /// cover, toolbar, navigationTitle) or is the bare web view.
    var dressed = true

    var body: some View {
        NavigationSplitView(columnVisibility: $probe.visibility) {
            List { ForEach(0..<5, id: \.self) { Text("Project \($0)") } }
                .navigationSplitViewColumnWidth(
                    min: SidebarAutoCollapse.columnMin, ideal: SidebarAutoCollapse.columnIdeal,
                    max: SidebarAutoCollapse.columnMax)
        } detail: {
            detail
                .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { width in
                    probe.detailWidth = width
                    if let sidebar = SidebarAutoCollapse.restingColumnWidth(
                        splitWidth: probe.splitWidth, detailWidth: width,
                        sidebarVisible: SidebarToggle.isVisible(probe.visibility)) {
                        probe.lastSidebarWidth = sidebar
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
                splitWidth: probe.splitWidth, detailWidth: probe.detailWidth,
                sidebarVisible: SidebarToggle.isVisible(now)) {
                probe.lastSidebarWidth = sidebar
            }
            probe.note("visibility → \(SidebarFitProbe.name(now))")
        }
        .frame(minWidth: 700, minHeight: 500)   // BristlenoseApp.swift:149
    }

    @ViewBuilder private var detail: some View {
        if dressed {
            ZStack {
                SPAWebView(lens: lens, probe: probe)
                    .focusSection()
                    .ignoresSafeArea(.container, edges: .top)
                if !probe.ready {
                    ZStack { Color(nsColor: .windowBackgroundColor); Text("loading") }
                        .transition(.opacity)
                }
            }
            .toolbar {
                ToolbarItem(placement: .navigation) {
                    Button { } label: { Image(systemName: "sidebar.leading") }
                }
            }
            .navigationTitle("Harness")
        } else {
            SPAWebView(lens: lens, probe: probe)
                .ignoresSafeArea(.container, edges: .top)
        }
    }
}

// MARK: - The rig

@MainActor
struct SPARig {
    let probe = SPAProbe()
    let window: NSWindow
    let lens: String

    static func serveIsUp() async -> Bool {
        var req = URLRequest(url: URL(string: "http://127.0.0.1:\(SPAWebView.port)/api/health")!)
        req.setValue("Bearer \(SPAWebView.token)", forHTTPHeaderField: "Authorization")
        req.timeoutInterval = 2
        guard let (_, resp) = try? await URLSession.shared.data(for: req) else { return false }
        return (resp as? HTTPURLResponse)?.statusCode == 200
    }

    init(lens: String, width: CGFloat = 1200, dressed: Bool = true, unifiedToolbar: Bool = true) async {
        self.lens = lens
        let host = NSHostingController(rootView: SPAHarnessView(probe: probe, lens: lens, dressed: dressed))
        host.sizingOptions = []
        var style: NSWindow.StyleMask = [.titled, .resizable, .closable, .miniaturizable]
        if unifiedToolbar { style.insert(.fullSizeContentView) }
        window = NSWindow(contentRect: NSRect(x: 40, y: 40, width: width, height: 700),
                          styleMask: style, backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        if unifiedToolbar { window.toolbarStyle = .unified }
        window.contentViewController = host
        window.setContentSize(NSSize(width: width, height: 700))
        window.orderFront(nil)
        await settle()
    }

    func close() { window.orderOut(nil); window.close() }

    func settle(_ seconds: Double = 0.7) async {
        try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
    }

    /// Waits for the SPA's `ready` and its first `panel-state`, up to `limit`.
    func waitForPage(limit: Double = 12) async -> Bool {
        let start = Date()
        while Date().timeIntervalSince(start) < limit {
            if probe.ready && probe.panelStatePosts > 0 { await settle(0.5); return true }
            await settle(0.2)
        }
        return false
    }

    func resize(to width: CGFloat, settleFor s: Double = 0.8) async {
        var f = window.frame; f.size.width = width
        window.setFrame(f, display: true, animate: false)
        probe.note("── window → \(Int(width))")
        await settle(s)
    }

    func drag(from a: CGFloat, to b: CGFloat, step: CGFloat = 12) async {
        let n = max(1, Int(abs(b - a) / step))
        for i in 1...n {
            var f = window.frame
            f.size.width = a + (b - a) * CGFloat(i) / CGFloat(n)
            window.setFrame(f, display: true, animate: false)
            await settle(0.016)
        }
        probe.note("── drag \(Int(a))→\(Int(b)) done")
        await settle()
    }

    func appKitToggle() async {
        let sent = NSApp.sendAction(#selector(NSSplitViewController.toggleSidebar(_:)), to: splitController, from: nil)
        probe.note("── appKit toggleSidebar sent=\(sent)")
        await settle(1.0)
    }

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
    var detailItem: NSSplitViewItem? { splitController?.splitViewItems.dropFirst().first }
    var appKitCollapsed: Bool? { sidebarItem?.isCollapsed }
    var appKitSidebarWidth: CGFloat? {
        guard let sv = splitController?.splitView, let first = sv.arrangedSubviews.first else { return nil }
        return sv.isSubviewCollapsed(first) ? 0 : first.frame.width
    }
    var columnEdge: CGFloat { appKitCollapsed == true ? 0 : (appKitSidebarWidth ?? -1) }
    /// What the eye reads as "the sidebar" on macOS 26/27: the glass card
    /// (an `NSVisualEffectView`, else the outermost scroll view) inside the
    /// column, which is inset from the column's own edges. Reported in the
    /// split view's coordinates so it compares with `appKitSidebarWidth`.
    var cardFrame: CGRect? {
        guard let sv = splitController?.splitView, let column = sv.arrangedSubviews.first else { return nil }
        func find(_ v: NSView, _ test: (NSView) -> Bool) -> NSView? {
            if test(v) { return v }
            for sub in v.subviews { if let hit = find(sub, test) { return hit } }
            return nil
        }
        let glass = find(column) { $0 is NSVisualEffectView && $0 !== column }
            ?? find(column) { $0 is NSScrollView }
        return glass.map { $0.convert($0.bounds, to: sv) }
    }
    var detailFrame: CGRect {
        guard let sv = splitController?.splitView, sv.arrangedSubviews.count > 1 else { return .zero }
        return sv.arrangedSubviews[1].frame
    }
    /// The divider's legal range as NSSplitViewController's delegate answers
    /// it — what a drag can reach. Equal ends = a divider that cannot move.
    /// Optional-protocol calls: SwiftUI's `NavigationSplitViewController`
    /// does NOT implement `constrainMinCoordinate` (an unconditional call
    /// crashed the test host with `unrecognized selector`, 25 Sep 2026), so
    /// the split view's own possible range is what remains when it doesn't.
    var dividerRange: (min: CGFloat, max: CGFloat, fromDelegate: Bool)? {
        guard let c = splitController else { return nil }
        let sv = c.splitView
        let rawLo = sv.minPossiblePositionOfDivider(at: 0), rawHi = sv.maxPossiblePositionOfDivider(at: 0)
        let d = c as NSSplitViewDelegate
        if let lo = d.splitView?(sv, constrainMinCoordinate: rawLo, ofSubviewAt: 0),
           let hi = d.splitView?(sv, constrainMaxCoordinate: rawHi, ofSubviewAt: 0) {
            return (lo, hi, true)
        }
        return (rawLo, rawHi, false)
    }

    struct PageReading {
        var innerWidth: Double = -1
        var layoutLeft: Double = -1, layoutWidth: Double = -1
        var centerLeft: Double = -1, centerWidth: Double = -1
        var tocLeft: Double = -1, tocWidth: Double = -1
        var classes = "?"
        var bodyWidth: Double = -1
        var ok = false
    }

    func readPage() async -> PageReading {
        var r = PageReading()
        guard let web = SPAWebView.last else { return r }
        let js = """
        (() => {
          const rect = (sel) => { const e = document.querySelector(sel); if (!e) return [-1,-1]; const b = e.getBoundingClientRect(); return [b.left, b.width]; };
          const l = rect('.layout'), c = rect('.layout > .center'), t = rect('.toc-sidebar');
          const cls = (document.querySelector('.layout') || {}).className || '?';
          return JSON.stringify({iw: innerWidth, l, c, t, cls, bw: document.body.getBoundingClientRect().width});
        })()
        """
        guard let s = try? await web.evaluateJavaScript(js) as? String,
              let data = s.data(using: .utf8),
              let o = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return r }
        r.ok = true
        r.innerWidth = o["iw"] as? Double ?? -1
        if let l = o["l"] as? [Double] { r.layoutLeft = l[0]; r.layoutWidth = l[1] }
        if let c = o["c"] as? [Double] { r.centerLeft = c[0]; r.centerWidth = c[1] }
        if let t = o["t"] as? [Double] { r.tocLeft = t[0]; r.tocWidth = t[1] }
        r.classes = o["cls"] as? String ?? "?"
        r.bodyWidth = o["bw"] as? Double ?? -1
        return r
    }

    struct Row {
        let step: String
        let split: CGFloat, sidebarW: CGFloat, collapsed: Bool?
        let cardX: CGFloat, cardW: CGFloat
        let thickness: String, divider: String
        let detailX: CGFloat, detailW: CGFloat
        let webX: CGFloat, webW: CGFloat, webSafeLeft: CGFloat, webSafeTop: CGFloat
        let page: PageReading
        let vis: String, last: CGFloat, floor: CGFloat, auto: Bool, toolbar: Bool

        var text: String {
            "\(step) | split=\(Int(split)) col=\(Int(sidebarW)) card x/w=\(Int(cardX))/\(Int(cardW)) collapsed=\(collapsed.map(String.init) ?? "nil") thick=\(thickness) divider=\(divider) | "
            + "detail x/w=\(Int(detailX))/\(Int(detailW)) | web x/w=\(Int(webX))/\(Int(webW)) safeL=\(Int(webSafeLeft)) safeT=\(Int(webSafeTop)) | "
            + "page iw=\(Int(page.innerWidth)) body=\(Int(page.bodyWidth)) layout l/w=\(Int(page.layoutLeft))/\(Int(page.layoutWidth)) "
            + "center l/w=\(Int(page.centerLeft))/\(Int(page.centerWidth)) toc l/w=\(Int(page.tocLeft))/\(Int(page.tocWidth)) cls='\(page.classes)' | "
            + "swiftUI vis=\(vis) last=\(Int(last)) floor=\(Int(floor)) auto=\(auto) toolbar=\(toolbar)"
        }
    }

    func row(_ step: String) async -> Row {
        let web = SPAWebView.last
        let frame = web.map { $0.convert($0.bounds, to: nil) } ?? .zero
        let item = sidebarItem
        let d = dividerRange
        let page = await readPage()
        let r = Row(
            step: step,
            split: splitController?.splitView.frame.width ?? -1,
            sidebarW: appKitSidebarWidth ?? -1, collapsed: appKitCollapsed,
            cardX: cardFrame?.minX ?? -1, cardW: cardFrame?.width ?? -1,
            thickness: "\(Int(item?.minimumThickness ?? -1))…\(Int(item?.maximumThickness ?? -1))/detail \(Int(detailItem?.minimumThickness ?? -1))…\(Int(detailItem?.maximumThickness ?? -1))",
            divider: d.map { "\(Int($0.min))…\(Int($0.max))\($0.fromDelegate ? "" : "(raw)")" } ?? "nil",
            detailX: detailFrame.minX, detailW: detailFrame.width,
            webX: frame.minX, webW: frame.width,
            webSafeLeft: web?.safeAreaInsets.left ?? -1, webSafeTop: web?.safeAreaInsets.top ?? -1,
            page: page,
            vis: SidebarFitProbe.name(probe.visibility), last: probe.lastSidebarWidth,
            floor: probe.webMinWidth, auto: probe.autoCollapsed, toolbar: window.toolbar != nil)
        probe.note("=== \(step): \(r.text)")
        return r
    }

    func snapshot(_ label: String) {
        guard let view = window.contentView,
              let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { return }
        view.cacheDisplay(in: view.bounds, to: rep)
        if let png = rep.representation(using: .png, properties: [:]) {
            Attachment.record(png, named: label.replacingOccurrences(of: " ", with: "_") + ".png")
        }
    }

    func dump(_ label: String) {
        var text = "=== \(label)\n"
        for line in probe.log { text += "    " + line + "\n" }
        probe.log.removeAll()
        Attachment.record(text, named: label.replacingOccurrences(of: " ", with: "_") + ".txt")
    }
}

// MARK: - What every row must satisfy once the page is up

@MainActor
private func expectFills(_ r: SPARig.Row, _ rig: SPARig, _ label: String) {
    let edge = rig.columnEdge
    let detailW = r.split - edge
    #expect(abs(r.webX - edge) <= 1, "\(label): web view starts at \(Int(r.webX)), column edge \(Int(edge))")
    #expect(abs(r.webW - detailW) <= 1, "\(label): web view \(Int(r.webW)) wide in a detail of \(Int(detailW))")
    #expect(r.page.ok, "\(label): page unreadable")
    if r.page.ok {
        #expect(abs(r.page.innerWidth - r.webW) <= 1, "\(label): innerWidth \(Int(r.page.innerWidth)) vs web view \(Int(r.webW))")
        #expect(abs(r.page.layoutWidth - r.page.innerWidth) <= 1, "\(label): .layout \(Int(r.page.layoutWidth)) wide in a page of \(Int(r.page.innerWidth))")
        #expect(abs(r.page.layoutLeft) <= 1, "\(label): .layout starts at \(Int(r.page.layoutLeft))")
    }
}

// MARK: - Scenarios

@Suite(.serialized) @MainActor struct SidebarFitSPAHarnessTests {

    static let lenses = ["codebook", "signals", "quotes"]

    /// S6/S7: after a toolbar hide, does the report fill the detail, and does
    /// the page's own grid fill the report? Then widen, then show again (S4).
    @Test(arguments: lenses) func hideShowWithTheRealReport(lens: String) async {
        guard await SPARig.serveIsUp() else {
            Attachment.record("no serve on :\(SPAWebView.port) — skipped", named: "spa-\(lens)-skipped.txt")
            return
        }
        let rig = await SPARig(lens: lens, width: 1200)
        defer { rig.close() }
        let loaded = await rig.waitForPage()
        #expect(loaded, "\(lens): page never posted ready + panel-state")
        var rows: [SPARig.Row] = []
        func step(_ name: String) async { let r = await rig.row(name); rows.append(r); rig.snapshot("spa-\(lens)-\(name)") }

        await step("start 1200")
        let colBefore = rig.appKitSidebarWidth ?? -1
        expectFills(rows.last!, rig, "\(lens) start")

        await rig.appKitToggle(); await step("toolbar hide")
        #expect(rig.appKitCollapsed == true)
        expectFills(rows.last!, rig, "\(lens) after toolbar hide")

        await rig.drag(from: 1200, to: 800); await step("dragged 800")
        expectFills(rows.last!, rig, "\(lens) at 800")
        await rig.drag(from: 800, to: 1500); await step("dragged 1500")
        expectFills(rows.last!, rig, "\(lens) at 1500")
        // The researcher hid it, so it stays hidden — and the page has the width.
        #expect(rig.appKitCollapsed == true, "\(lens): a column the researcher hid came back on resize")
        if lens != "quotes" {
            #expect(rows.last!.page.classes.contains("toc-open"), "\(lens): left panel closed at 1500 (S7): \(rows.last!.page.classes)")
        }

        await rig.appKitToggle(); await step("toolbar show")
        #expect(rig.appKitCollapsed == false)
        expectFills(rows.last!, rig, "\(lens) after toolbar show")
        // S4: the column comes back at the width it had.
        #expect(abs((rig.appKitSidebarWidth ?? -1) - colBefore) <= 2,
                "\(lens): column was \(Int(colBefore)) before the hide, \(Int(rig.appKitSidebarWidth ?? -1)) after the show")

        await rig.appKitToggle(); await step("toolbar hide 2")
        withAnimation { rig.probe.visibility = .all }; await rig.settle(1.0); await step("menu show")
        #expect(rig.appKitCollapsed == false)
        expectFills(rows.last!, rig, "\(lens) after menu show")

        rig.splitController?.splitView.setPosition(260, ofDividerAt: 0); await rig.settle(); await step("divider 260")
        expectFills(rows.last!, rig, "\(lens) divider 260")

        Attachment.record(rows.map(\.text).joined(separator: "\n"), named: "spa-\(lens)-rows.txt")
        rig.dump("spa-\(lens)-trace")
    }

    /// The auto-collapse path with the real floor: narrow until the logic
    /// takes the column, widen until it gives it back, and read the page at
    /// each end.
    @Test(arguments: lenses) func autoCollapseWithTheRealFloor(lens: String) async {
        guard await SPARig.serveIsUp() else { return }
        let rig = await SPARig(lens: lens, width: 1500)
        defer { rig.close() }
        let loaded = await rig.waitForPage()
        #expect(loaded, "\(lens): page never posted ready + panel-state")
        var rows: [SPARig.Row] = []
        func step(_ name: String) async { let r = await rig.row(name); rows.append(r); rig.snapshot("spa-auto-\(lens)-\(name)") }

        await step("start 1500")
        let floor = rig.probe.webMinWidth
        expectFills(rows.last!, rig, "\(lens) start")
        // Narrow to where window − column < floor, but the window still holds the floor alone.
        let narrow = max(700, floor + 100)
        await rig.drag(from: 1500, to: narrow); await step("dragged \(Int(narrow))")
        #expect(rig.appKitCollapsed == true, "\(lens): column should have given way (floor \(Int(floor)), window \(Int(narrow)))")
        expectFills(rows.last!, rig, "\(lens) narrow")
        await rig.drag(from: narrow, to: 1500); await step("dragged back 1500")
        #expect(rig.appKitCollapsed == false, "\(lens): column we took should come back")
        expectFills(rows.last!, rig, "\(lens) wide again")

        Attachment.record(rows.map(\.text).joined(separator: "\n"), named: "spa-auto-\(lens)-rows.txt")
        rig.dump("spa-auto-\(lens)-trace")
    }
}
