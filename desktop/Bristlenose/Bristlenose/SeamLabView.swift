#if DEBUG
import AppKit
import SwiftUI
import WebKit

/// DEBUG-only seam laboratory — where the native sidebar meets the WKWebView.
///
/// **Why this exists.** The join between AppKit chrome and web content is the
/// one surface no mockup can settle. An HTML mock draws the sidebar as a flat
/// slab; macOS 26 draws it as an inset, rounded, shadowed plateau in the Liquid
/// Glass layer, and macOS 27 reverts that to an edge-anchored sidebar again.
/// Hand-tuning CSS against either is work you buy twice.
///
/// So this window does three things the real app must not be disturbed to do:
///
/// 1. **Measures.** `Probe` walks the live view tree and reports what *this* OS
///    actually does — the webview's `safeAreaInsets`, the window's frame-minus-
///    contentLayoutRect delta, and every `NSVisualEffectView`'s frame, material
///    and layer `cornerRadius`. On macOS 27 it will report different numbers the
///    day it is installed, which is the point: the geometry is read, never
///    assumed. This is the same discipline as
///    `design-native-colour-alignment.md` §Principles' "Best (bitrot-proof)"
///    tier — bridge the live value rather than sample a hex and re-sample at OS
///    bumps.
///
/// 2. **Cycles treatments.** The candidate fixes (A/B/D + a deepened tint) are
///    injected as a CSS overlay into the *real* report, so what is under test is
///    the shipping stylesheet plus one override — not a reimplementation that
///    could be wrong in its own way.
///
/// 3. **Tests `backgroundExtensionEffect()`.** Apple's sanctioned answer to
///    "extend content under the sidebar" (HIG ▸ Sidebars, updated 8 Jun 2026;
///    macOS 26+). Its documented use case is literally this layout — a detail
///    column extending under the sidebar. The open question it cannot answer on
///    paper is whether the mirror-and-blur works when the detail column hosts a
///    **WKWebView**, which is a hosted layer rather than SwiftUI-rendered
///    content. That is an empirical question and this is where it gets asked.
///
/// Nothing here is reachable from a Release build, and nothing it does touches
/// the real report's stylesheet on disk — the override is injected into the
/// live DOM of this window's own webview only.
struct SeamLabView: View {

    @EnvironmentObject private var serveFleet: ServeFleet
    @EnvironmentObject private var i18n: I18n
    @StateObject private var bridge = BridgeHandler()

    @State private var treatment: Treatment = .today
    @State private var extensionEffect = false
    @State private var fullBleed = false
    @State private var opaqueToolbar = true
    @State private var sidebarVisible = NavigationSplitViewVisibility.all
    @State private var readout = Probe.Readout()
    @AppStorage("palette") private var palette = "default"
    @State private var appearance = "light"

    /// The candidate treatments. Each is a CSS overlay applied on top of the
    /// shipping stylesheet — never a replacement for it.
    enum Treatment: String, CaseIterable, Identifiable {
        case today = "today"
        case transparentA = "A · transparent"
        case bleedB = "B · bleed up"
        case contentD = "D · content bg"
        case deepened = "deepened tint"
        var id: String { rawValue }
    }

    var body: some View {
        VStack(spacing: 0) {
            controls
            Divider()
            stage
            Divider()
            metricsBar
        }
        .frame(minWidth: 900, minHeight: 620)
        .preferredColorScheme(appearance == "dark" ? .dark : .light)
        .onAppear { refreshProbe() }
    }

    // MARK: - Controls

    private var controls: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 14) {
                Picker("Treatment", selection: $treatment) {
                    ForEach(Treatment.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 420)

                Picker("", selection: $appearance) {
                    Text("light").tag("light")
                    Text("dark").tag("dark")
                }
                .pickerStyle(.segmented)
                .frame(width: 120)

                Picker("", selection: $palette) {
                    Text("default").tag("default")
                    Text("edo").tag("edo")
                }
                .pickerStyle(.segmented)
                .frame(width: 140)
            }

            HStack(spacing: 16) {
                Toggle("backgroundExtensionEffect()", isOn: $extensionEffect)
                    .disabled(!Probe.supportsBackgroundExtension)
                    .help(Probe.supportsBackgroundExtension
                          ? "Apple's sanctioned way to stretch detail content under the sidebar (macOS 26+)."
                          : "Requires macOS 26 or later.")
                Toggle("full-bleed body (24px → 0)", isOn: $fullBleed)
                    .help("report.css:21 sets `padding: xl lg`; the embedded override replaces only padding-top, so 24px survives on each flank.")
                Toggle("opaque toolbar", isOn: $opaqueToolbar)
                Spacer()
                Button("Re-measure") { refreshProbe() }
                Button("Copy metrics") { copyMetrics() }
            }
            .toggleStyle(.checkbox)
            .font(.callout)
        }
        .padding(12)
    }

    // MARK: - Stage

    /// A real `NavigationSplitView` with a real sidebar and the real `WebView`,
    /// so the seam under test is the shipping one.
    private var stage: some View {
        NavigationSplitView(columnVisibility: $sidebarVisible) {
            List {
                Section {
                    ForEach(["Project", "Sessions", "Quotes", "Codebooks", "Analysis"], id: \.self) { row in
                        Label(row, systemImage: "square.dashed")
                    }
                }
                Section("Projects") {
                    Label("project-ikea", systemImage: "books.vertical")
                }
            }
            .navigationSplitViewColumnWidth(min: 168, ideal: 200, max: 280)
        } detail: {
            detailPane
        }
        .navigationSplitViewStyle(.balanced)
        .toolbar { ToolbarItem(placement: .principal) { Text("Seam Lab").font(.headline) } }
        .toolbarBackgroundVisibility(opaqueToolbar ? .visible : .hidden, for: .windowToolbar)
    }

    @ViewBuilder
    private var detailPane: some View {
        Group {
            if let url = serveFleet.fronted?.serveURL,
               let project = serveFleet.frontedProject,
               let port = URLComponents(url: url, resolvingAgainstBaseURL: false)?.port {
                webview(url: url, project: project, port: port)
            } else {
                ContentUnavailableView(
                    "No serve running",
                    systemImage: "bolt.horizontal.circle",
                    description: Text("Open a project in the main window first — the lab borrows its sidecar so the seam under test is the real one.")
                )
            }
        }
    }

    @ViewBuilder
    private func webview(url: URL, project: UUID, port: Int) -> some View {
        let web = WebView(
            url: url,
            bridgeHandler: bridge,
            session: ServeSession(projectID: project, port: port),
            authToken: serveFleet.fronted?.authToken
        )
        .environmentObject(i18n)
        .ignoresSafeArea(.container, edges: .top)
        .onChange(of: treatment) { _, _ in applyOverlay() }
        .onChange(of: fullBleed) { _, _ in applyOverlay() }
        .onChange(of: bridge.isReady) { _, ready in
            if ready { applyOverlay(); refreshProbe() }
        }

        // `backgroundExtensionEffect()` is macOS 26+. The `if #available` keeps
        // the file compiling against the production 15.0 deployment target —
        // don't collapse it, the app still ships to Sequoia.
        if #available(macOS 26.0, *), extensionEffect {
            web.backgroundExtensionEffect()
        } else {
            web
        }
    }

    // MARK: - CSS overlay

    /// The overlay is additive: shipping stylesheet + one `<style>` element.
    /// Nothing is replaced, so a treatment that looks right here is a change we
    /// could actually make, not an approximation of one.
    private func applyOverlay() {
        let css = Self.overlayCSS(
            treatment: treatment,
            fullBleed: fullBleed,
            safeAreaTop: readout.webviewSafeAreaTop
        )
        let js = """
        (function () {
          var id = 'bn-seam-lab-overlay';
          var el = document.getElementById(id);
          if (!el) { el = document.createElement('style'); el.id = id; document.head.appendChild(el); }
          el.textContent = \(Self.jsStringLiteral(css));
        })();
        """
        bridge.webView?.evaluateJavaScript(js)
    }

    static func overlayCSS(treatment: Treatment, fullBleed: Bool, safeAreaTop: CGFloat) -> String {
        var rules: [String] = []

        if fullBleed {
            // report.css:21 — the embedded override at :36 replaces padding-top
            // only, so the horizontal `--bn-space-lg` survives into the app and
            // shows the window surface through the transparent body.
            rules.append("""
            html[data-embedded="true"] body { padding-left: 0 !important; padding-right: 0 !important; }
            """)
        }

        switch treatment {
        case .today:
            break
        case .transparentA:
            rules.append(".toc-sidebar, .tag-sidebar { background: transparent !important; }")
        case .bleedB:
            // The value the bridge already computes and throws away
            // (BridgeHandler.syncToolbarInset, `nativeInset`): how far macOS has
            // pushed the layout viewport down, i.e. how far up the panel must
            // bleed to reach the window top.
            rules.append("""
            .toc-sidebar {
              margin-top: calc(-1 * (\(Int(safeAreaTop))px + var(--bn-space-xl))) !important;
              padding-top: calc(\(Int(safeAreaTop))px + var(--bn-space-xl)) !important;
            }
            """)
        case .contentD:
            rules.append(".toc-sidebar, .tag-sidebar { background: var(--bn-colour-bg) !important; }")
        case .deepened:
            // Toward the material's measured separation rather than the current
            // 1.052 contrast ratio against content — see the hierarchy section
            // of docs/mockups/sidebar-seam-window-edge.html.
            rules.append("""
            .toc-sidebar, .tag-sidebar { background: light-dark(#f0f0f0, #2a2a2a) !important; }
            """)
        }

        return rules.joined(separator: "\n")
    }

    /// JSON-encodes a Swift string into a JavaScript string literal. Hand-rolled
    /// escaping here would be one backslash away from a syntax error inside an
    /// `evaluateJavaScript` payload, which fails silently.
    static func jsStringLiteral(_ s: String) -> String {
        guard let data = try? JSONEncoder().encode(s),
              let literal = String(data: data, encoding: .utf8) else { return "\"\"" }
        return literal
    }

    // MARK: - Probe

    private func refreshProbe() {
        DispatchQueue.main.async {
            readout = Probe.measure(webView: bridge.webView)
            if treatment == .bleedB { applyOverlay() }
        }
    }

    private func copyMetrics() {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(readout.plainText, forType: .string)
    }

    private var metricsBar: some View {
        ScrollView(.vertical) {
            Text(readout.plainText)
                .font(.system(.caption, design: .monospaced))
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
        }
        .frame(height: 128)
    }
}

// MARK: - Live geometry probe

/// Reads the seam's geometry off the running view tree.
///
/// Deliberately measurement, not constants. Tahoe renders the sidebar as an
/// inset rounded plateau; macOS 27 reverts it to edge-anchored. Anything this
/// file hardcoded about that would be wrong within a release — so it reports
/// what the OS says and lets the reader draw the conclusion.
enum Probe {

    static var supportsBackgroundExtension: Bool {
        if #available(macOS 26.0, *) { return true }
        return false
    }

    struct Readout {
        var os = ""
        var webviewSafeAreaTop: CGFloat = 0
        var windowFrameDelta: CGFloat = 0
        var contentSafeAreaTop: CGFloat = 0
        var residual: CGFloat = 0
        var effects: [String] = []
        var note = "Not measured yet — press Re-measure once the report has loaded."

        var plainText: String {
            guard !os.isEmpty else { return note }
            var lines: [String] = []
            lines.append("os                       \(os)")
            lines.append("webview safeAreaInsets.top   \(fmt(webviewSafeAreaTop))   ← how far up a panel must bleed to reach the window top")
            lines.append("window frame − contentLayout \(fmt(windowFrameDelta))")
            lines.append("contentView safeArea.top     \(fmt(contentSafeAreaTop))")
            lines.append("residual (what the bridge posts) \(fmt(residual))   ← 0 means CSS is told to add nothing")
            if effects.isEmpty {
                lines.append("visual effect views      none found")
            } else {
                lines.append("visual effect views:")
                for e in effects { lines.append("  \(e)") }
            }
            return lines.joined(separator: "\n")
        }

        private func fmt(_ v: CGFloat) -> String { String(format: "%7.2f", Double(v)) }
    }

    static func measure(webView: WKWebView?) -> Readout {
        var r = Readout()
        let v = ProcessInfo.processInfo.operatingSystemVersion
        r.os = "macOS \(v.majorVersion).\(v.minorVersion).\(v.patchVersion)"

        guard let webView, let window = webView.window else {
            r.note = "No webview/window yet — open a project in the main window, then Re-measure."
            return r
        }

        r.webviewSafeAreaTop = webView.safeAreaInsets.top
        r.windowFrameDelta = window.frame.height - window.contentLayoutRect.height
        r.contentSafeAreaTop = window.contentView?.safeAreaInsets.top ?? 0
        // Mirrors BridgeHandler.syncToolbarInset so the lab and the shipping
        // bridge cannot disagree about what "residual" means.
        r.residual = max(0, max(r.windowFrameDelta, r.contentSafeAreaTop) - r.webviewSafeAreaTop)

        if let root = window.contentView {
            r.effects = visualEffectViews(under: root, in: window)
        }
        return r
    }

    /// Every `NSVisualEffectView` in the window, with the three properties that
    /// decide how the sidebar reads: its frame (is it inset from the window
    /// edge?), its layer corner radius (is it a plateau?), and its material.
    private static func visualEffectViews(under root: NSView, in window: NSWindow) -> [String] {
        var out: [String] = []
        func walk(_ view: NSView, depth: Int) {
            if let fx = view as? NSVisualEffectView {
                let f = view.convert(view.bounds, to: nil)   // window coordinates
                let radius = fx.layer?.cornerRadius ?? 0
                let insetL = f.minX
                let insetR = window.frame.width - f.maxX
                out.append(String(
                    format: "material=%@ blend=%@ frame=(%.1f,%.1f %.0fx%.0f) inset L=%.1f R=%.1f cornerRadius=%.1f",
                    describe(fx.material), fx.blendingMode == .behindWindow ? "behind" : "within",
                    f.minX, f.minY, f.width, f.height, insetL, insetR, radius
                ))
            }
            for sub in view.subviews { walk(sub, depth: depth + 1) }
        }
        walk(root, depth: 0)
        return out
    }

    private static func describe(_ m: NSVisualEffectView.Material) -> String {
        switch m {
        case .sidebar: "sidebar"
        case .headerView: "headerView"
        case .contentBackground: "contentBackground"
        case .underWindowBackground: "underWindowBackground"
        case .windowBackground: "windowBackground"
        case .titlebar: "titlebar"
        case .menu: "menu"
        case .popover: "popover"
        case .hudWindow: "hudWindow"
        case .sheet: "sheet"
        case .fullScreenUI: "fullScreenUI"
        case .toolTip: "toolTip"
        case .selection: "selection"
        default: "raw(\(m.rawValue))"
        }
    }
}
#endif
