#if DEBUG
import AppKit
import SwiftUI
import WebKit

/// DEBUG-only sidebar laboratory — how the top of the projects column meets the
/// toolbar when the list scrolls.
///
/// **Why this exists.** Until 29 Sep 2026, the scrolled sidebar showed three
/// artefacts that Photos and Notes (same OS) do not: a hard clip at the
/// toolbar's bottom edge, a 32 pt frosted band, and a 0.5 pt line under it. This
/// window crossed the two suspected causes: the outline hosted *below* the
/// toolbar safe area (so `automaticallyAdjustsContentInsets` had nothing to
/// adjust and the system never drew its soft scroll edge), and the blank lens
/// group row pinning itself (`floatsGroupRows`). The "under toolbar yes, pinned
/// no" corner matched Photos and shipped; "no / yes" reproduces the old build.
/// The two fixed-lens layouts were explored and not chosen
/// (`docs/design-desktop-sidebar-appkit.md` §1.4, §5).
///
/// **What is real here.** Both outlines are the shipping
/// `SidebarOutlineController`, fed a throwaway `ProjectIndex` on a temp file —
/// the same construction `SidebarOutlineExpansionTests` uses. Only the lens
/// block's *placement* and the fixture data are the lab's own.
///
/// **Layout rule.** The `NavigationSplitView` is the window's root and the
/// controls live in an inspector column. Anything stacked above the split view
/// (as Seam Lab does) would move the titlebar geometry this window measures.
struct SidebarLabView: View {

    @EnvironmentObject private var i18n: I18n
    @StateObject private var fixture = SidebarLabFixture()

    @State private var layout: Layout = .outline
    // Defaults match the shipping sidebar; flip both to see the pre-fix build.
    @State private var underlap = true
    @State private var pinHeadings = false
    @State private var lensDivider = true
    @State private var detailMode: DetailMode = .native
    @State private var webUnderlap = true
    @State private var obscuredInsets = false
    @State private var appearance = "light"
    @State private var showInspector = true

    @State private var selection: Set<SidebarSelection> = []
    @State private var activeTab: Tab? = .quotes
    @State private var lensBlockHeight: CGFloat = 192

    @State private var window: NSWindow?
    @State private var projectsController: SidebarOutlineController?
    @State private var lensController: SidebarOutlineController?
    @State private var webView: WKWebView?
    @State private var readout = "Not measured yet."

    enum Layout: String, CaseIterable, Identifiable {
        case outline = "Lenses in outline (today)"
        case fixedLenses = "Fixed lenses, projects scroll"
        case lensBar = "Lens bar, projects under it"
        var id: String { rawValue }
    }

    enum DetailMode: String, CaseIterable, Identifiable {
        case native = "SwiftUI list"
        case web = "WKWebView"
        var id: String { rawValue }
    }

    var body: some View {
        NavigationSplitView {
            sidebar
                .navigationSplitViewColumnWidth(
                    min: SidebarAutoCollapse.columnMin,
                    ideal: SidebarAutoCollapse.columnIdeal,
                    max: SidebarAutoCollapse.columnMax
                )
        } detail: {
            detail
                .navigationTitle("Sidebar Lab")
                .navigationSubtitle(summary)
                .toolbar {
                    // Stand-ins for the main window's back/forward, so the
                    // toolbar band here is the main window's height rather
                    // than a title-only band's.
                    ToolbarItem(placement: .navigation) {
                        ControlGroup {
                            Button {} label: { Label("Back", systemImage: "chevron.left") }
                            Button {} label: { Label("Forward", systemImage: "chevron.right") }
                        }
                    }
                    ToolbarItem(placement: .primaryAction) {
                        Button { showInspector.toggle() } label: {
                            Label("Controls", systemImage: "sidebar.trailing")
                        }
                    }
                }
        }
        .inspector(isPresented: $showInspector) {
            controls.inspectorColumnWidth(min: 300, ideal: 340, max: 440)
        }
        .background(SidebarLabWindowReader { window = $0 })
        .preferredColorScheme(appearance == "dark" ? .dark : .light)
        .onChange(of: layout) { _, _ in remeasureSoon() }
        .onChange(of: underlap) { _, _ in remeasureSoon() }
        .onChange(of: pinHeadings) { _, _ in remeasureSoon() }
        .onChange(of: detailMode) { _, _ in remeasureSoon() }
        .onChange(of: webUnderlap) { _, _ in remeasureSoon() }
        .onChange(of: obscuredInsets) { _, _ in remeasureSoon() }
        .onChange(of: fixture.generation) { _, _ in remeasureSoon() }
        .onAppear { remeasureSoon() }
        .onChange(of: window) { _, _ in remeasureSoon() }
    }

    private var summary: String {
        "\(layout.rawValue) · under toolbar \(underlap ? "yes" : "no") · pinned \(pinHeadings ? "yes" : "no")"
    }

    // MARK: - Sidebar variants

    @ViewBuilder
    private var sidebar: some View {
        switch layout {
        case .outline:
            outline(roots: OutlineTree.build(lenses: LensItem.all,
                                             projects: fixture.index.projects,
                                             folders: fixture.index.folders))
                .modifier(TopUnderlap(on: underlap))

        case .fixedLenses:
            // Nothing scrolls under the toolbar here, so "under toolbar" does
            // not apply — the lens block sits in the safe area by design.
            VStack(spacing: 0) {
                lensBlock
                if lensDivider { Divider() }
                outline(roots: projectsOnlyRoots)
            }

        case .lensBar:
            if #available(macOS 26.0, *) {
                outline(roots: projectsOnlyRoots)
                    .safeAreaBar(edge: .top, spacing: 0) {
                        VStack(spacing: 0) {
                            lensBlock
                            if lensDivider { Divider() }
                        }
                    }
                    .modifier(TopUnderlap(on: underlap))
            } else {
                ContentUnavailableView("Needs macOS 26",
                                       systemImage: "exclamationmark.triangle",
                                       description: Text("safeAreaBar(edge:) is macOS 26+."))
            }
        }
    }

    /// `OutlineTree.build` omits the lens group when `lenses` is empty
    /// (`OutlineNode.swift`), which is exactly the projects-only tree.
    private var projectsOnlyRoots: [OutlineNode] {
        OutlineTree.build(lenses: [], projects: fixture.index.projects, folders: fixture.index.folders)
    }

    /// The lens group alone, rendered by a second real controller so the rows
    /// are the shipping cells. Sized to its rows and never scrolls.
    private var lensBlock: some View {
        let lensRows = LensItem.all.map { OutlineNode(.lens($0.tab)) }
        return SidebarLabOutline(
            index: fixture.index, i18n: i18n,
            roots: [OutlineNode(.group(OutlineTree.lensesGroupKey), children: lensRows)],
            selection: .constant([]),
            activeTab: activeTab,
            floats: false,
            scrolls: false,
            onActivateLens: { activeTab = $0 },
            onContentHeight: { lensBlockHeight = $0 },
            onController: { lensController = $0 }
        )
        .frame(height: lensBlockHeight)
    }

    private func outline(roots: [OutlineNode]) -> some View {
        SidebarLabOutline(
            index: fixture.index, i18n: i18n,
            roots: roots,
            selection: $selection,
            activeTab: activeTab,
            floats: pinHeadings,
            scrolls: true,
            onActivateLens: { activeTab = $0 },
            onContentHeight: nil,
            onController: { projectsController = $0 }
        )
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        switch detailMode {
        case .native:
            List(0..<80, id: \.self) { i in
                Text("Detail row \(i) — native SwiftUI scroll view, for the system's own edge treatment")
            }
        case .web:
            SidebarLabWeb(obscuredTop: obscuredInsets ? toolbarBand : 0,
                          onWebView: { webView = $0 })
                .modifier(TopUnderlap(on: webUnderlap))
        }
    }

    /// Window frame minus content layout rect — the band the toolbar owns.
    private var toolbarBand: CGFloat {
        guard let window else { return 52 }
        return window.frame.height - window.contentLayoutRect.height
    }

    // MARK: - Controls

    private var controls: some View {
        Form {
            Section("Sidebar") {
                Picker("Layout", selection: $layout) {
                    ForEach(Layout.allCases) { Text($0.rawValue).tag($0) }
                }
                Toggle("Outline extends under toolbar", isOn: $underlap)
                    .disabled(layout == .fixedLenses)
                    .help("`.ignoresSafeArea(.container, edges: .top)` on the outline, so automaticallyAdjustsContentInsets has a titlebar to adjust for.")
                Toggle("Headings pin (floatsGroupRows)", isOn: $pinHeadings)
                Toggle("Divider under fixed lenses", isOn: $lensDivider)
                    .disabled(layout == .outline)
                Stepper("Projects: \(fixture.count)", value: Binding(
                    get: { fixture.count }, set: { fixture.rebuild(count: $0) }
                ), in: 1...60)
                HStack {
                    Text("Scroll")
                    Button("Top") { scroll(rows: 0) }
                    Button("1 row") { scroll(rows: 1) }
                    Button("3 rows") { scroll(rows: 3) }
                    Button("8 rows") { scroll(rows: 8) }
                }
            }

            Section("Detail") {
                Picker("Content", selection: $detailMode) {
                    ForEach(DetailMode.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                Toggle("Web view extends under toolbar", isOn: $webUnderlap)
                    .disabled(detailMode != .web)
                Toggle("obscuredContentInsets.top = toolbar band", isOn: $obscuredInsets)
                    .disabled(detailMode != .web || !Self.supportsObscuredInsets)
                    .help("WKWebView, macOS 26+. Tells WebKit the top of the page sits under the toolbar.")
            }

            Section("Window") {
                HStack {
                    Text("Height")
                    Button("500") { setWindowHeight(500) }
                        .help("The main window's content minimum (BristlenoseApp.swift).")
                    Button("700") { setWindowHeight(700) }
                    Button("900") { setWindowHeight(900) }
                }
                Picker("Appearance", selection: $appearance) {
                    Text("light").tag("light")
                    Text("dark").tag("dark")
                }
                .pickerStyle(.segmented)
            }

            Section("Readout") {
                HStack {
                    Button("Measure") { measure() }
                    Button("Copy") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(readout, forType: .string)
                    }
                }
                Text(readout)
                    .font(.system(.caption, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .formStyle(.grouped)
    }

    static var supportsObscuredInsets: Bool {
        if #available(macOS 26.0, *) { return true }
        return false
    }

    // MARK: - Actions

    private func scroll(rows: Int) {
        guard let sv = projectsController?.outlineView.enclosingScrollView else { return }
        let y = -sv.contentInsets.top + CGFloat(rows) * ProjectCellSpec.singleLineHeight
        sv.contentView.scroll(to: NSPoint(x: 0, y: y))
        sv.reflectScrolledClipView(sv.contentView)
        remeasureSoon()
    }

    /// Keeps the window's top edge where it is, like dragging the bottom edge.
    private func setWindowHeight(_ h: CGFloat) {
        guard let window else { return }
        var f = window.frame
        let top = f.maxY
        f.size.height = h
        f.origin.y = top - h
        window.setFrame(f, display: true, animate: true)
        remeasureSoon()
    }

    private func remeasureSoon() {
        // After SwiftUI has laid the new variant out and AppKit has adjusted insets.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { measure() }
    }

    private func measure() {
        readout = SidebarLabProbe.measure(
            window: window,
            projects: projectsController,
            lenses: layout == .outline ? nil : lensController,
            webView: detailMode == .web ? webView : nil
        )
    }
}

// MARK: - Modifiers

/// Conditional top underlap — a modifier rather than an `if` so the wrapped
/// representable keeps its identity (and its controller) across the toggle.
private struct TopUnderlap: ViewModifier {
    let on: Bool
    func body(content: Content) -> some View {
        content.ignoresSafeArea(.container, edges: on ? .top : [])
    }
}

// MARK: - Fixture

/// A throwaway project list on a temp file. Paths point at real temp
/// directories so rows resolve as present rather than "Locate…".
@MainActor
final class SidebarLabFixture: ObservableObject {
    @Published private(set) var index: ProjectIndex
    @Published private(set) var count = 14
    /// Bumped on every rebuild so the view can re-measure.
    @Published private(set) var generation = 0

    private let root = FileManager.default.temporaryDirectory
        .appendingPathComponent("SidebarLab-\(UUID().uuidString)")

    private static let names = [
        "Checkout friction", "Onboarding interviews", "Pharmacy pilot", "Oral history — Leith",
        "Diary study wave 2", "Clinician handover", "Banking app usability", "Grocery delivery",
        "Screen reader walk-throughs", "Travel booking", "Kiosk field visits", "Parent panel",
    ]

    init() {
        index = ProjectIndex(fileURL: root.appendingPathComponent("unused.json"))
        rebuild(count: count)
    }

    func rebuild(count: Int) {
        self.count = count
        let dir = root.appendingPathComponent("gen-\(generation)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let fresh = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        // One folder, so pinned-heading behaviour covers a nested row too.
        let folder = fresh.addFolder(name: "Archive 2025")
        for i in 0..<count {
            let name = Self.names[i % Self.names.count] + (i >= Self.names.count ? " \(i / Self.names.count + 1)" : "")
            let path = dir.appendingPathComponent("p\(i)")
            try? FileManager.default.createDirectory(at: path, withIntermediateDirectories: true)
            fresh.addProject(name: name, path: path.path, intoFolder: i % 5 == 4 ? folder.id : nil)
        }
        index = fresh
        generation += 1
    }

}

// MARK: - Outline host

/// Hosts the shipping `SidebarOutlineController` with only the knobs the lab
/// varies. Mirrors `ProjectSidebarOutline.updateNSViewController` minus the
/// app services (runner, copy, cloud import), which are optional on the
/// controller and irrelevant to scroll geometry.
private struct SidebarLabOutline: NSViewControllerRepresentable {
    let index: ProjectIndex
    let i18n: I18n
    let roots: [OutlineNode]
    @Binding var selection: Set<SidebarSelection>
    let activeTab: Tab?
    let floats: Bool
    let scrolls: Bool
    let onActivateLens: (Tab) -> Void
    let onContentHeight: ((CGFloat) -> Void)?
    let onController: (SidebarOutlineController) -> Void

    func makeNSViewController(context: Context) -> SidebarOutlineController {
        let controller = SidebarOutlineController()
        controller.projectIndex = index
        controller.i18n = i18n
        DispatchQueue.main.async { onController(controller) }
        return controller
    }

    func updateNSViewController(_ controller: SidebarOutlineController, context: Context) {
        controller.projectIndex = index
        controller.i18n = i18n
        controller.onSelectionChange = { new in
            if selection != new { selection = new }
        }
        controller.onActivateLens = onActivateLens
        controller.update(roots: roots, selection: selection, activeTab: activeTab, lensesEnabled: true)

        let outlineView = controller.outlineView
        outlineView.floatsGroupRows = floats
        if let sv = outlineView.enclosingScrollView {
            sv.hasVerticalScroller = scrolls
            sv.verticalScrollElasticity = scrolls ? .automatic : .none
            // A fixed block must not inherit titlebar insets it never sits under.
            sv.automaticallyAdjustsContentInsets = scrolls
            if !scrolls { sv.contentInsets = NSEdgeInsetsZero }
        }
        if let onContentHeight, outlineView.numberOfRows > 0 {
            let h = outlineView.rect(ofRow: outlineView.numberOfRows - 1).maxY
            DispatchQueue.main.async { onContentHeight(ceil(h)) }
        }
    }
}

// MARK: - Web detail

private struct SidebarLabWeb: NSViewRepresentable {
    let obscuredTop: CGFloat
    let onWebView: (WKWebView) -> Void

    func makeNSView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero)
        web.loadHTMLString(Self.page, baseURL: nil)
        DispatchQueue.main.async { onWebView(web) }
        return web
    }

    func updateNSView(_ web: WKWebView, context: Context) {
        if #available(macOS 26.0, *) {
            web.obscuredContentInsets = NSEdgeInsets(top: obscuredTop, left: 0, bottom: 0, right: 0)
        }
    }

    /// Long, varied content so the edge treatment has something to sample:
    /// text, a coloured block every few paragraphs, and a sticky heading.
    static let page: String = {
        var body = ""
        for i in 0..<40 {
            if i % 6 == 0 {
                body += "<div class=\"band\" style=\"background:hsl(\(i * 37 % 360) 70% 60%)\">Block \(i)</div>"
            }
            body += "<p><b>Paragraph \(i).</b> The participant describes the checkout step in detail, pausing at the address form and returning twice to the basket before continuing.</p>"
        }
        return """
        <!doctype html><meta charset="utf-8">
        <style>
          :root { color-scheme: light dark; font: 15px -apple-system, sans-serif; }
          body { margin: 0; padding: 16px 24px; }
          h1 { position: sticky; top: 0; margin: 0 -24px; padding: 8px 24px;
               background: color-mix(in srgb, Canvas 85%, transparent); font-size: 17px; }
          .band { height: 80px; border-radius: 10px; margin: 16px 0; color: white;
                  display: flex; align-items: center; padding: 0 16px; font-weight: 600; }
        </style>
        <h1>Sticky heading</h1>
        \(body)
        """
    }()
}

// MARK: - Window reader

/// Reports the hosting window once the view is actually in one. An async hop
/// from `makeNSView` is not enough: the view can still be windowless then, and
/// the readout said "No window yet." for the life of the lab.
private struct SidebarLabWindowReader: NSViewRepresentable {
    let onWindow: (NSWindow) -> Void
    func makeNSView(context: Context) -> NSView { Probe(onWindow: onWindow) }
    func updateNSView(_ nsView: NSView, context: Context) {}

    final class Probe: NSView {
        let onWindow: (NSWindow) -> Void
        init(onWindow: @escaping (NSWindow) -> Void) {
            self.onWindow = onWindow
            super.init(frame: .zero)
        }
        required init?(coder: NSCoder) { fatalError("init(coder:) is not used") }
        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            if let window { DispatchQueue.main.async { self.onWindow(window) } }
        }
    }
}

// MARK: - Probe

/// Reads the live geometry. Distances are points from the window's top edge,
/// because that is how the screenshots were measured. Private view classes are
/// *reported*, never relied on: the point is to learn who draws the band and
/// the line, not to reach into them.
@MainActor
enum SidebarLabProbe {

    static func measure(window: NSWindow?, projects: SidebarOutlineController?,
                        lenses: SidebarOutlineController?, webView: WKWebView?) -> String {
        guard let window, let content = window.contentView else { return "No window yet." }
        let v = ProcessInfo.processInfo.operatingSystemVersion
        var lines: [String] = []
        lines.append("macOS \(v.majorVersion).\(v.minorVersion).\(v.patchVersion) · scale \(window.backingScaleFactor)×")
        lines.append("window height          \(f(window.frame.height))")
        lines.append("toolbar band           \(f(window.frame.height - window.contentLayoutRect.height))  (frame − contentLayoutRect)")
        lines.append("contentView safeTop    \(f(content.safeAreaInsets.top))")

        if let outline = projects?.outlineView, let sv = outline.enclosingScrollView {
            lines.append("")
            lines.append("PROJECTS OUTLINE")
            lines.append(contentsOf: describe(scrollView: sv, outline: outline, in: window))
        }
        if let sv = lenses?.outlineView.enclosingScrollView {
            lines.append("")
            lines.append("LENS BLOCK")
            lines.append("  frame top            \(f(top(of: sv, in: window)))  height \(f(sv.frame.height))")
        }
        if let webView {
            lines.append("")
            lines.append("WEB VIEW")
            lines.append("  frame top            \(f(top(of: webView, in: window)))")
            lines.append("  safeAreaInsets.top   \(f(webView.safeAreaInsets.top))")
            if #available(macOS 26.0, *) {
                lines.append("  obscuredInsets.top   \(f(webView.obscuredContentInsets.top))")
            }
        }

        // Everything that is not a row and overlaps the top 120 pt of the
        // sidebar column: candidates for the frost, the band and the line.
        if let sv = projects?.outlineView.enclosingScrollView {
            // Window base coordinates: bottom-left origin whatever the hosting
            // view's flippedness, and they span the titlebar (full-size content).
            let column = sv.convert(sv.bounds, to: nil)
            let windowHeight = window.frame.height
            let band = NSRect(x: column.minX, y: windowHeight - 120,
                              width: column.width, height: 120)
            lines.append("")
            lines.append("VIEWS IN TOP 120 pt OF SIDEBAR (class · top · height · width)")
            var seen = Set<String>()
            walk(content) { view in
                guard !(view is NSTableCellView), !(view is NSTextField), !(view is NSImageView) else { return }
                let r = view.convert(view.bounds, to: nil)
                guard r.intersects(band), r.width < window.frame.width - 1 else { return }
                let name = String(describing: type(of: view))
                let t = windowHeight - r.maxY
                var extra = ""
                if let row = view as? NSTableRowView { extra = row.isFloating ? " FLOATING" : (row.isGroupRowStyle ? " group" : "") }
                if let fx = view as? NSVisualEffectView { extra = " material=\(fx.material.rawValue)" }
                let line = "  \(name)\(extra) · \(f(t)) · \(f(r.height)) · \(f(r.width))"
                if seen.insert(line).inserted { lines.append(line) }
            }
        }
        return lines.joined(separator: "\n")
    }

    private static func describe(scrollView sv: NSScrollView, outline: NSOutlineView, in window: NSWindow) -> [String] {
        var out: [String] = []
        out.append("  frame top            \(f(top(of: sv, in: window)))  ← 0 = reaches the window top")
        out.append("  contentInsets.top    \(f(sv.contentInsets.top))  auto=\(sv.automaticallyAdjustsContentInsets)")
        out.append("  safeAreaInsets.top   \(f(sv.safeAreaInsets.top))")
        out.append("  scrolled by          \(f(sv.contentView.bounds.minY + sv.contentInsets.top))")
        out.append("  floatsGroupRows      \(outline.floatsGroupRows)")
        return out
    }

    private static func top(of view: NSView, in window: NSWindow) -> CGFloat {
        window.frame.height - view.convert(view.bounds, to: nil).maxY
    }

    private static func walk(_ view: NSView, _ visit: (NSView) -> Void) {
        visit(view)
        for sub in view.subviews { walk(sub, visit) }
    }

    private static func f(_ v: CGFloat) -> String { String(format: "%6.1f", Double(v)) }
}
#endif
