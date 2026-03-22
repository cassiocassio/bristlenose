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
    @State private var selectedProject: ProjectStub?

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
        .onChange(of: selectedProject) { _, newValue in
            bridgeHandler.reset()
            if let project = newValue {
                serveManager.start(projectPath: project.path)
            } else {
                serveManager.stop()
            }
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

    private var toolbarLeading: some ToolbarContent {
        ToolbarItemGroup(placement: .navigation) {
            Button(action: { bridgeHandler.goBack() }) {
                Image(systemName: "chevron.backward")
            }
            .disabled(!bridgeHandler.canGoBack)
            .keyboardShortcut("[", modifiers: .command)
            .help("Back (⌘[)")

            Button(action: { bridgeHandler.goForward() }) {
                Image(systemName: "chevron.forward")
            }
            .disabled(!bridgeHandler.canGoForward)
            .keyboardShortcut("]", modifiers: .command)
            .help("Forward (⌘])")
        }
    }

    private var toolbarCenter: some ToolbarContent {
        ToolbarItem(placement: .principal) {
            Picker("Tab", selection: tabBinding) {
                ForEach(Tab.allCases) { tab in
                    Text(tab.label).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .disabled(selectedProject == nil || !bridgeHandler.isReady)
        }
    }

    // MARK: - Toolbar trailing (contextual — menus dim, toolbars morph)

    @ToolbarContentBuilder
    private var toolbarTrailing: some ToolbarContent {
        // Universal — Search (active on Quotes tab, dimmed elsewhere as placeholder)
        ToolbarItem(placement: .primaryAction) {
            Button { bridgeHandler.menuAction("find") } label: {
                Label("Search", systemImage: "magnifyingglass")
            }
            .disabled(bridgeHandler.activeTab != .quotes)
            .help("Search (⌘F)")
        }

        // Universal — Export menu (contents morph per tab)
        ToolbarItem(placement: .primaryAction) {
            ExportMenuButton(bridgeHandler: bridgeHandler)
        }

        // Contextual — Codebook tab: tags panel toggle
        if bridgeHandler.activeTab == .codebook {
            ToolbarItem(placement: .primaryAction) {
                Button { bridgeHandler.menuAction("toggleRightPanel") } label: {
                    Label("Tags", systemImage: "tag")
                }
                .help("Toggle Tags Panel")
            }
        }

        // Contextual — Analysis tab: inspector panel toggle
        if bridgeHandler.activeTab == .analysis {
            ToolbarItem(placement: .primaryAction) {
                Button { bridgeHandler.menuAction("toggleInspectorPanel") } label: {
                    Label("Inspector", systemImage: "rectangle.bottomhalf.inset.filled")
                }
                .help("Toggle Inspector Panel (m)")
            }
        }
    }

    // MARK: - Sidebar

    private var sidebar: some View {
        List(projects, selection: $selectedProject) { project in
            Label(project.name, systemImage: "folder")
                .tag(project)
        }
        .navigationTitle("Projects")
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        if let project = selectedProject {
            ZStack {
                switch serveManager.state {
                case .idle, .starting:
                    ProgressView("Starting server...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                case .running:
                    WebView(url: serveManager.serveURL, bridgeHandler: bridgeHandler)
                        .id(project.id)

                    // Loading overlay — shown until the React SPA posts "ready".
                    if !bridgeHandler.isReady {
                        ZStack {
                            Color(nsColor: .windowBackgroundColor)
                            ProgressView("Loading report...")
                        }
                        .transition(.opacity)
                    }

                case .failed(let error):
                    ContentUnavailableView {
                        Label("Server Error", systemImage: "exclamationmark.triangle")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("Retry") {
                            serveManager.start(projectPath: project.path)
                        }
                    }
                }
            }
            .animation(.easeInOut(duration: 0.2), value: bridgeHandler.isReady)
        } else {
            ContentUnavailableView(
                "No Project Selected",
                systemImage: "doc.text.magnifyingglass",
                description: Text("Select a project from the sidebar.")
            )
        }
    }
}

// MARK: - Export toolbar menu

/// Toolbar export button with per-tab dropdown contents.
/// "Export Report..." is always first (universal). Tab-specific exports below a divider.
struct ExportMenuButton: View {
    @ObservedObject var bridgeHandler: BridgeHandler

    var body: some View {
        Menu {
            Button("Export Report...") {
                bridgeHandler.menuAction("exportReport")
            }
            .keyboardShortcut("e", modifiers: [.command, .shift])

            if bridgeHandler.activeTab == .quotes {
                Divider()

                Button("Export Quotes as CSV") {
                    bridgeHandler.menuAction("exportQuotesCSV")
                }

                // Future: "Export Starred Quotes as CSV" when starred filter active
            }

            // Future: Analysis tab → "Export Signal Cards as PPTX"
        } label: {
            Label("Export", systemImage: "square.and.arrow.up")
        }
        .help("Export (⌘⇧E)")
    }
}
