import SwiftUI
import UniformTypeIdentifiers

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
    @EnvironmentObject var projectIndex: ProjectIndex
    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @AppStorage("selectedProjectID") private var persistedProjectID: String = ""
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    /// Selection binding for the List — uses `SidebarSelection` enum so both
    /// projects and folders are selectable. UUID-based to survive field mutations.
    @State private var selection: SidebarSelection?
    @State private var showingAIConsent = false
    @State private var aiConsentReviewMode = false

    /// The ID of the project currently in inline rename mode, or nil.
    @State private var renamingProjectID: UUID?

    /// The ID of the folder currently in inline rename mode, or nil.
    @State private var renamingFolderID: UUID?

    /// The currently selected project, derived from `selection`.
    /// Computed so that mutations to `projectIndex.projects` (e.g. rename,
    /// updateLastOpened) don't break selection — the UUID is stable.
    private var selectedProject: Project? {
        guard case .project(let id) = selection else { return nil }
        return projectIndex.projects.first { $0.id == id }
    }

    /// The currently selected folder, derived from `selection`.
    private var selectedFolder: Folder? {
        guard case .folder(let id) = selection else { return nil }
        return projectIndex.folders.first { $0.id == id }
    }

    /// Extract the project UUID from the selection (for persistence and onChange).
    private var selectedProjectID: UUID? {
        guard case .project(let id) = selection else { return nil }
        return id
    }

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
        .onChange(of: selection) { _, newSelection in
            bridgeHandler.reset()
            switch newSelection {
            case .project(let id):
                bridgeHandler.selectedFolderName = ""
                if let project = projectIndex.projects.first(where: { $0.id == id }) {
                    persistedProjectID = id.uuidString
                    bridgeHandler.selectedProjectPath = project.path
                    projectIndex.updateLastOpened(id: id)
                    // Gate serve on consent — no data leaves the machine before
                    // the user has seen the AI data disclosure (Apple 5.1.2(i)).
                    if hasConsent && !project.path.isEmpty {
                        serveManager.start(projectPath: project.path)
                    }
                }
            case .folder(let id):
                persistedProjectID = ""
                bridgeHandler.selectedProjectPath = ""
                bridgeHandler.selectedFolderName =
                    projectIndex.folders.first { $0.id == id }?.name ?? ""
                serveManager.stop()
            case nil:
                persistedProjectID = ""
                bridgeHandler.selectedProjectPath = ""
                bridgeHandler.selectedFolderName = ""
                serveManager.stop()
            }
        }
        // When consent is granted (version updated), start serve for the
        // already-selected project if one exists.
        .onChange(of: consentVersion) { _, _ in
            if hasConsent, let project = selectedProject {
                if !project.path.isEmpty {
                    serveManager.start(projectPath: project.path)
                }
            }
        }
        .onAppear {
            // Restore last-selected project from persisted ID.
            if selection == nil, !persistedProjectID.isEmpty,
               let id = UUID(uuidString: persistedProjectID),
               projectIndex.projects.contains(where: { $0.id == id }) {
                selection = .project(id)
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
        // File > New Project (Cmd+N) and sidebar [+] button.
        .onReceive(NotificationCenter.default.publisher(for: .createNewProject)) { _ in
            createNewProject()
        }
        // File > New Folder (⇧⌘N) and sidebar folder.badge.plus button.
        .onReceive(NotificationCenter.default.publisher(for: .createNewFolder)) { _ in
            createNewFolder()
        }
        // Project > Rename — trigger inline rename on the selected project.
        .onReceive(NotificationCenter.default.publisher(for: .renameSelectedProject)) { _ in
            if case .project(let id) = selection {
                renamingProjectID = id
            }
        }
        // Project > Rename Folder — trigger inline rename on the selected folder.
        .onReceive(NotificationCenter.default.publisher(for: .renameSelectedFolder)) { _ in
            if case .folder(let id) = selection {
                renamingFolderID = id
            }
        }
        // Project > Delete — remove the selected project.
        .onReceive(NotificationCenter.default.publisher(for: .deleteSelectedProject)) { _ in
            if case .project(let id) = selection {
                selection = nil
                projectIndex.removeProject(id: id)
            }
        }
        // Project > Delete Folder — remove the selected folder (projects move to root).
        .onReceive(NotificationCenter.default.publisher(for: .deleteSelectedFolder)) { _ in
            if case .folder(let id) = selection {
                selection = nil
                projectIndex.removeFolder(id: id)
            }
        }
        // Project > Move to — move the selected project into/out of a folder.
        .onReceive(NotificationCenter.default.publisher(for: .moveSelectedProject)) { notification in
            guard case .project(let projectId) = selection else { return }
            let folderId = notification.userInfo?["folderId"] as? UUID
            projectIndex.moveProject(projectId: projectId, toFolder: folderId)
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

    // MARK: - Project and folder creation

    /// Create a new project and put it in inline rename mode.
    private func createNewProject() {
        let project = projectIndex.addProject(name: "New Project", path: "")
        selection = .project(project.id)
        renamingProjectID = project.id
    }

    /// Create a new folder and put it in inline rename mode.
    private func createNewFolder() {
        let folder = projectIndex.addFolder(name: i18n.t("desktop.chrome.newFolder"))
        selection = .folder(folder.id)
        renamingFolderID = folder.id
    }

    // MARK: - Drag and drop

    /// Handle files/folders dropped from Finder onto the sidebar free space.
    /// - Folder: create project pointing to that directory (scan all files)
    /// - File(s): create project with inputFiles restricting to the dropped files
    /// De-duplicates by path — if a project already exists for that folder, selects it.
    private func handleDrop(providers: [NSItemProvider]) {
        Task {
            let urls = await loadURLs(from: providers)
            await MainActor.run {
                processDroppedURLs(urls)
            }
        }
    }

    /// Load file URLs from drop providers.
    private func loadURLs(from providers: [NSItemProvider]) async -> [URL] {
        await withTaskGroup(of: URL?.self) { group in
            for provider in providers {
                group.addTask {
                    await withCheckedContinuation { continuation in
                        provider.loadItem(
                            forTypeIdentifier: UTType.fileURL.identifier
                        ) { data, _ in
                            guard let data = data as? Data,
                                  let url = URL(
                                      dataRepresentation: data, relativeTo: nil
                                  ) else {
                                continuation.resume(returning: nil)
                                return
                            }
                            continuation.resume(returning: url)
                        }
                    }
                }
            }
            var results: [URL] = []
            for await url in group {
                if let url { results.append(url) }
            }
            return results
        }
    }

    /// Process collected URLs from a sidebar drop.
    private func processDroppedURLs(_ urls: [URL]) {
        let directories = urls.filter { $0.hasDirectoryPath }
        let files = urls.filter { !$0.hasDirectoryPath }

        // All drops create one project. The name comes from the first item.
        // - Single folder: path = folder, inputFiles = nil (scan whole directory)
        // - Multiple folders: path = first folder, inputFiles = all folder paths
        // - File(s): path = first file's parent, inputFiles = file paths
        // - Mix of files and folders: path = first item's dir, inputFiles = all paths
        if directories.count == 1 && files.isEmpty {
            // Single folder — classic mode, scan everything in it.
            let url = directories[0]
            let project = projectIndex.addProject(
                name: url.lastPathComponent, path: url.path
            )
            selection = .project(project.id)
            renamingProjectID = project.id
        } else if !directories.isEmpty || !files.isEmpty {
            // Multiple items — one project with explicit input list.
            let allPaths = directories.map { $0.path } + files.map { $0.path }
            let firstName: String
            let firstPath: String
            if let firstDir = directories.first {
                firstName = firstDir.lastPathComponent
                firstPath = firstDir.path
            } else {
                firstName = files[0].deletingPathExtension().lastPathComponent
                firstPath = files[0].deletingLastPathComponent().path
            }
            let project = projectIndex.addProject(
                name: firstName, path: firstPath, inputFiles: allPaths
            )
            selection = .project(project.id)
            renamingProjectID = project.id
        }
    }

    /// Handle files/folders dropped onto an existing project row.
    /// Adds the dropped interviews to that project's input list.
    private func handleDropOnProject(id: UUID, providers: [NSItemProvider]) {
        Task {
            let urls = await loadURLs(from: providers)
            await MainActor.run {
                let paths = urls.map { $0.path }
                if !paths.isEmpty {
                    projectIndex.addFiles(to: id, files: paths)
                }
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
        List(selection: $selection) {
            Section {
                // "+ New Project" at the top of the list — always visible.
                Button {
                    createNewProject()
                } label: {
                    Label(i18n.t("desktop.menu.file.newProject"), systemImage: "plus")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)

                ForEach(projectIndex.sidebarItems) { item in
                    switch item {
                    case .folder(let folder):
                        folderSection(folder)

                    case .project(let project):
                        projectRow(project)
                    }
                }
            } header: {
                Text(i18n.t("desktop.chrome.projects"))
            }
        }
        .accessibilityLabel(i18n.t("desktop.chrome.projects"))
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            handleDrop(providers: providers)
            return true
        }
        .focusSection()
        // New Folder button in the sidebar title bar.
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    createNewFolder()
                } label: {
                    Image(systemName: "folder.badge.plus")
                }
                .help(i18n.t("desktop.chrome.newFolder"))
            }
        }
        .navigationTitle(i18n.t("desktop.chrome.projects"))
    }

    // MARK: - Sidebar rows

    /// A collapsible folder with its child projects.
    @ViewBuilder
    private func folderSection(_ folder: Folder) -> some View {
        DisclosureGroup(
            isExpanded: Binding(
                get: { !folder.collapsed },
                set: { projectIndex.setFolderCollapsed(id: folder.id, collapsed: !$0) }
            )
        ) {
            ForEach(projectIndex.projectsInFolder(folder.id)) { project in
                projectRow(project)
            }
        } label: {
            FolderRow(
                folder: folder,
                isRenaming: Binding(
                    get: { renamingFolderID == folder.id },
                    set: { newValue in
                        renamingFolderID = newValue ? folder.id : nil
                    }
                ),
                onRename: { newName in
                    projectIndex.renameFolder(id: folder.id, newName: newName)
                },
                onDelete: {
                    if case .folder(folder.id) = selection { selection = nil }
                    projectIndex.removeFolder(id: folder.id)
                }
            )
        }
        .tag(SidebarSelection.folder(folder.id))
        .contextMenu {
            Button(i18n.t("desktop.menu.folder.rename")) {
                renamingFolderID = folder.id
            }
            Button(i18n.t("desktop.menu.folder.archive")) {
                // Phase 5
            }
            .disabled(true)
            Divider()
            Button(i18n.t("desktop.menu.folder.delete"), role: .destructive) {
                if case .folder(folder.id) = selection { selection = nil }
                projectIndex.removeFolder(id: folder.id)
            }
        }
    }

    /// A single project row with context menu (used at root level and inside folders).
    @ViewBuilder
    private func projectRow(_ project: Project) -> some View {
        ProjectRow(
            project: project,
            isRenaming: Binding(
                get: { renamingProjectID == project.id },
                set: { newValue in
                    renamingProjectID = newValue ? project.id : nil
                }
            ),
            onRename: { newName in
                projectIndex.renameProject(id: project.id, newName: newName)
            },
            onShowInFinder: {
                if !project.path.isEmpty {
                    NSWorkspace.shared.selectFile(
                        nil, inFileViewerRootedAtPath: project.path
                    )
                }
            },
            onDelete: {
                if case .project(project.id) = selection { selection = nil }
                projectIndex.removeProject(id: project.id)
            }
        )
        .tag(SidebarSelection.project(project.id))
        .contextMenu {
            Button(i18n.t("desktop.menu.project.showInFinder")) {
                if !project.path.isEmpty {
                    NSWorkspace.shared.selectFile(
                        nil, inFileViewerRootedAtPath: project.path
                    )
                }
            }
            Button(i18n.t("desktop.menu.project.rename")) {
                renamingProjectID = project.id
            }

            // "Move to" submenu — lists all folders + "No Folder" for root.
            if !projectIndex.folders.isEmpty {
                Menu(i18n.t("desktop.menu.project.moveTo")) {
                    Button(i18n.t("desktop.menu.project.noFolder")) {
                        projectIndex.moveProject(projectId: project.id, toFolder: nil)
                    }
                    .disabled(project.folderId == nil)

                    Divider()

                    ForEach(projectIndex.folders) { folder in
                        Button(folder.name) {
                            projectIndex.moveProject(projectId: project.id, toFolder: folder.id)
                        }
                        .disabled(project.folderId == folder.id)
                    }
                }
            }

            Divider()
            Button(i18n.t("desktop.menu.project.delete"), role: .destructive) {
                if case .project(project.id) = selection { selection = nil }
                projectIndex.removeProject(id: project.id)
            }
        }
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        if let project = selectedProject {
            if project.path.isEmpty {
                // New project with no files yet — prompt user to add interviews.
                ContentUnavailableView(
                    i18n.t("desktop.chrome.dragInterviews"),
                    systemImage: "square.and.arrow.down",
                    description: Text(i18n.t("desktop.chrome.dragInterviewsDescription"))
                )
            } else {
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
            }
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
