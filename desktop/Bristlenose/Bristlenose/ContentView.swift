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
struct ContentView: View {

    @StateObject private var serveManager = ServeManager()
    @StateObject private var bridgeHandler = BridgeHandler()
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
