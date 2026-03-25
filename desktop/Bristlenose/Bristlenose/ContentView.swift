import SwiftUI

/// A placeholder project entry for the sidebar.
/// Will be replaced by a real Project model backed by projects.json.
struct ProjectStub: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let path: String
}

/// Two-column NavigationSplitView: project list sidebar + WKWebView detail.
///
/// Selecting a project starts `bristlenose serve` and loads the React SPA
/// in embedded mode. The WKWebView is recreated on project switch (via .id)
/// to get a fresh ephemeral data store per project.
///
/// The toolbar provides three zones:
/// - Leading: back/forward buttons (Cmd+[/Cmd+])
/// - Centre: tab segmented control (Cmd+1-5)
/// - Trailing: project name as window title
struct ContentView: View {

    @EnvironmentObject var serveManager: ServeManager
    @EnvironmentObject var bridgeHandler: BridgeHandler
    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @AppStorage("selectedProjectPath") private var selectedProjectPath: String = ""
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    @State private var selectedProject: ProjectStub?
    @State private var showingAIConsent = false
    @State private var aiConsentReviewMode = false

    /// Whether the user has acknowledged the current AI data disclosure.
    private var hasConsent: Bool { consentVersion >= AIConsentView.currentVersion }

    /// Inject the native locale as a URL query parameter so the React SPA
    /// can detect it synchronously on first render (prevents language flash).
    private var serveURLWithLocale: URL? {
        guard var components = serveManager.serveURL.flatMap({
            URLComponents(url: $0, resolvingAgainstBaseURL: false)
        }) else { return serveManager.serveURL }
        let locale = i18n.locale
        if locale != "en" {
            var items = components.queryItems ?? []
            items.append(URLQueryItem(name: "locale", value: locale))
            components.queryItems = items
        }
        return components.url ?? serveManager.serveURL
    }

    /// Map the stored appearance string to SwiftUI's ColorScheme.
    private var colorScheme: ColorScheme? {
        switch appearance {
        case "light": .light
        case "dark": .dark
        default: nil  // "auto" → follow system
        }
    }

    /// Placeholder projects — replace with real project list from projects.json.
    /// First entry points to a real trial-runs project for testing the serve flow.
    private let projects: [ProjectStub] = [
        ProjectStub(name: "Project IKEA", path: "\(NSHomeDirectory())/Code/bristlenose/trial-runs/project-ikea"),
        ProjectStub(name: "Pilot Interviews", path: "\(NSHomeDirectory())/Documents/pilot"),
        ProjectStub(name: "Onboarding Round 3", path: "\(NSHomeDirectory())/Documents/onboarding-r3"),
    ]

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
                .toolbar {
                    toolbarLeading
                    toolbarCenter
                    toolbarTrailing
                }
                .navigationTitle(selectedProject?.name ?? "Bristlenose")
        }
        .navigationSplitViewColumnWidth(min: 180, ideal: 220, max: 300)
        .preferredColorScheme(colorScheme)
        // TODO: filter by window object when multi-window ships —
        // currently fires for any window (Settings, player, etc.) which is
        // correct single-window behaviour but will over-toggle with >1 content window.
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didBecomeKeyNotification)) { _ in
            bridgeHandler.setWindowActive(true)
        }
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didResignKeyNotification)) { _ in
            bridgeHandler.setWindowActive(false)
        }
        .onChange(of: selectedProject) { _, newValue in
            bridgeHandler.reset()
            if let project = newValue {
                selectedProjectPath = project.path
                // Gate serve on consent — no data leaves the machine before
                // the user has seen the AI data disclosure (Apple 5.1.2(i)).
                if hasConsent {
                    serveManager.start(projectPath: project.path)
                }
            } else {
                selectedProjectPath = ""
                serveManager.stop()
            }
        }
        // When consent is granted (version updated), start serve for the
        // already-selected project if one exists.
        .onChange(of: consentVersion) { _, _ in
            if hasConsent, let project = selectedProject {
                serveManager.start(projectPath: project.path)
            }
        }
        .onAppear {
            if selectedProject == nil, !selectedProjectPath.isEmpty,
               let match = projects.first(where: { $0.path == selectedProjectPath }) {
                selectedProject = match
            }
            // First-run consent check.
            if !hasConsent {
                aiConsentReviewMode = false
                showingAIConsent = true
            }
        }
        // AI & Privacy... re-access from app menu.
        .onReceive(NotificationCenter.default.publisher(for: .showAIConsentSheet)) { _ in
            aiConsentReviewMode = true
            showingAIConsent = true
        }
        .sheet(isPresented: $showingAIConsent) {
            AIConsentView(
                isReviewMode: aiConsentReviewMode,
                onDismiss: { showingAIConsent = false }
            )
            .environmentObject(i18n)
            .interactiveDismissDisabled(!aiConsentReviewMode)
        }
    }

    // MARK: - Toolbar

    /// Two-way binding: reads activeTab from bridge, writes via switchToTab.
    /// Maps nil to .project since segmented Picker requires non-optional selection.
    private var tabBinding: Binding<Tab> {
        Binding(
            get: { bridgeHandler.activeTab ?? .project },
            set: { bridgeHandler.switchToTab($0) }
        )
    }

    /// Per-tab label for the left-panel toolbar button.
    private var leftPanelToolbarLabel: String {
        switch bridgeHandler.activeTab {
        case .quotes:   return i18n.t("desktop.toolbar.contents")
        case .codebook: return i18n.t("desktop.toolbar.codes")
        case .analysis: return i18n.t("desktop.toolbar.signals")
        default:        return i18n.t("desktop.toolbar.contents")
        }
    }

    /// Per-tab tooltip for the left-panel toolbar button.
    private var leftPanelToolbarHelp: String {
        switch bridgeHandler.activeTab {
        case .quotes:   return i18n.t("desktop.toolbar.showContents")
        case .codebook: return i18n.t("desktop.toolbar.showCodes")
        case .analysis: return i18n.t("desktop.toolbar.showSignals")
        default:        return i18n.t("desktop.toolbar.showContents")
        }
    }

    @ToolbarContentBuilder
    private var toolbarLeading: some ToolbarContent {
        // Contextual — Quotes/Codebook/Analysis: left panel toggle
        // The native sidebar toggle (for the project list) is provided by
        // NavigationSplitView automatically — Mail-style: lives inside the
        // sidebar column when open, snaps left to traffic lights when closed.
        // This standalone button controls the web navigation sidebar
        // (sections/themes on Quotes, codebooks on Codebook, signals on Analysis).
        // Gestalt proximity: each toggle is near the thing it controls.
        if bridgeHandler.activeTab == .quotes ||
           bridgeHandler.activeTab == .codebook ||
           bridgeHandler.activeTab == .analysis {
            ToolbarItem(placement: .navigation) {
                Button {
                    bridgeHandler.menuAction("toggleLeftPanel")
                } label: {
                    Label(leftPanelToolbarLabel, systemImage: "list.bullet")
                }
                .help(leftPanelToolbarHelp)
            }
        }

        ToolbarItemGroup(placement: .navigation) {
            Button(action: { bridgeHandler.goBack() }) {
                Image(systemName: "chevron.backward")
            }
            .disabled(!bridgeHandler.canGoBack)
            .keyboardShortcut("[", modifiers: .command)
            .help(i18n.t("desktop.toolbar.back"))

            Button(action: { bridgeHandler.goForward() }) {
                Image(systemName: "chevron.forward")
            }
            .disabled(!bridgeHandler.canGoForward)
            .keyboardShortcut("]", modifiers: .command)
            .help(i18n.t("desktop.toolbar.forward"))
        }
    }

    private var toolbarCenter: some ToolbarContent {
        ToolbarItem(placement: .principal) {
            Picker("Tab", selection: tabBinding) {
                ForEach(Tab.allCases) { tab in
                    Text(tab.localizedLabel(i18n)).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .disabled(selectedProject == nil || !bridgeHandler.isReady)
        }
    }

    // MARK: - Toolbar trailing (contextual — menus dim, toolbars morph)

    @ToolbarContentBuilder
    private var toolbarTrailing: some ToolbarContent {
        // Universal — Export menu (contents morph per tab)
        ToolbarItem(placement: .primaryAction) {
            ExportMenuButton(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        // Contextual — Quotes tab: tag sidebar toggle
        if bridgeHandler.activeTab == .quotes {
            ToolbarItem(placement: .primaryAction) {
                Button { bridgeHandler.menuAction("toggleRightPanel") } label: {
                    Label(i18n.t("desktop.toolbar.tags"), systemImage: "sidebar.right")
                }
                .help(i18n.t("desktop.toolbar.showTags"))
            }
        }

        // Contextual — Analysis tab: heatmap inspector toggle
        if bridgeHandler.activeTab == .analysis {
            ToolbarItem(placement: .primaryAction) {
                Button { bridgeHandler.menuAction("toggleInspectorPanel") } label: {
                    Label(i18n.t("desktop.toolbar.heatmap"), systemImage: "square.grid.2x2")
                }
                .help(i18n.t("desktop.toolbar.showHeatmap"))
            }
        }

        // Search — always rightmost, always active. The web layer handles
        // context: Quotes → search bar, Sessions → transcript search,
        // Codebook → filter codes, Analysis → filter signals.
        ToolbarItem(placement: .primaryAction) {
            Button { bridgeHandler.menuAction("find") } label: {
                Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
            }
            .help(i18n.t("desktop.toolbar.searchShortcut"))
        }
    }

    // MARK: - Sidebar

    private var sidebar: some View {
        List(projects, selection: $selectedProject) { project in
            Label(project.name, systemImage: "folder")
                .tag(project)
        }
        .navigationTitle(i18n.t("desktop.chrome.projects"))
        .accessibilityLabel(i18n.t("desktop.chrome.projects"))
        .focusSection()
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        if let project = selectedProject {
            ZStack {
                switch serveManager.state {
                case .idle, .starting:
                    ProgressView(i18n.t("desktop.chrome.startingServer"))
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                case .running:
                    WebView(url: serveURLWithLocale, bridgeHandler: bridgeHandler, authToken: serveManager.authToken)
                        .id(project.id)
                        .accessibilityLabel(i18n.t("desktop.chrome.reportContent"))
                        .accessibilityHidden(!bridgeHandler.isReady)
                        .focusSection()

                    // Loading overlay — shown until the React SPA posts "ready".
                    if !bridgeHandler.isReady {
                        ZStack {
                            Color(nsColor: .windowBackgroundColor)
                            ProgressView(i18n.t("desktop.chrome.loadingReport"))
                        }
                        .transition(.opacity)
                    }

                case .failed(let error):
                    ContentUnavailableView {
                        Label(i18n.t("desktop.chrome.serverError"), systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button(i18n.t("desktop.chrome.retry")) {
                            serveManager.start(projectPath: project.path)
                        }
                    }
                }
            }
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: bridgeHandler.isReady)
        } else {
            ContentUnavailableView(
                i18n.t("desktop.chrome.noProjectSelected"),
                systemImage: "doc.text.magnifyingglass",
                description: Text(i18n.t("desktop.chrome.selectProject"))
            )
        }
    }
}

// MARK: - Export toolbar menu

/// Toolbar export button with per-tab dropdown contents.
/// "Export Report..." is always first (universal). Tab-specific exports below a divider.
struct ExportMenuButton: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Menu {
            Button(i18n.t("desktop.menu.file.exportReport")) {
                bridgeHandler.menuAction("exportReport")
            }
            .keyboardShortcut("e", modifiers: [.command, .shift])

            if bridgeHandler.activeTab == .quotes {
                Divider()

                Button(i18n.t("desktop.menu.quotes.copyAsCSV")) {
                    bridgeHandler.menuAction("exportQuotesCSV")
                }

                // Future: "Export Starred Quotes as CSV" when starred filter active
            }

            // Future: Analysis tab → "Export Signal Cards as PPTX"
        } label: {
            Label(i18n.t("desktop.toolbar.export"), systemImage: "square.and.arrow.up")
        }
        .help(i18n.t("desktop.toolbar.exportShortcut"))
    }
}
