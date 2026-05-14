import SwiftUI
import UniformTypeIdentifiers

// MARK: - Window title manager

/// Sets NSWindow.title for Cmd+Tab / Mission Control without using
/// `.navigationTitle()` on the detail view (which adds a visible toolbar title
/// item that duplicates the custom icon+name ToolbarItem).
/// Also hides the title bar text via `titleVisibility = .hidden` as belt-and-
/// suspenders in case any navigation layer restores it.
private struct WindowTitleManager: NSViewRepresentable {
    let title: String

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async { Self.apply(title: title, to: view) }
        return view
    }
    func updateNSView(_ view: NSView, context: Context) {
        DispatchQueue.main.async { Self.apply(title: title, to: view) }
    }
    private static func apply(title: String, to view: NSView) {
        guard let window = view.window else { return }
        window.title = title
        window.titleVisibility = .hidden
    }
}

// MARK: - Sidebar empty-click deselection monitor

/// Clears the sidebar selection when the user clicks in the empty area below
/// all list rows. Uses NSEvent local monitor + NSTableView.row(at:) so it
/// doesn't conflict with List's selection gesture (no SwiftUI gesture needed).
/// The monitor is installed once and removed in deinit — no leak risk.
private struct SidebarDeselectMonitor: NSViewRepresentable {
    let deselect: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(deselect: deselect) }
    func makeNSView(context: Context) -> NSView { NSView() }
    func updateNSView(_ view: NSView, context: Context) {
        context.coordinator.deselect = deselect
    }

    final class Coordinator {
        var deselect: () -> Void
        private var monitor: Any?

        init(deselect: @escaping () -> Void) {
            self.deselect = deselect
            monitor = NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown) { [weak self] event in
                self?.handle(event)
                return event  // always pass through — we never consume
            }
        }

        private func handle(_ event: NSEvent) {
            guard let window = event.window,
                  let tableView = Self.sidebarTableView(in: window) else { return }
            let point = tableView.convert(event.locationInWindow, from: nil)
            // Only act when click is inside the table view but below all rows.
            guard tableView.bounds.contains(point) else { return }
            if tableView.row(at: point) < 0 {
                DispatchQueue.main.async { self.deselect() }
            }
        }

        /// Finds the sidebar NSTableView — the first one in the window hierarchy.
        /// The detail area is a WKWebView; it contains no NSTableViews.
        private static func sidebarTableView(in window: NSWindow) -> NSTableView? {
            func find(in view: NSView) -> NSTableView? {
                if let tv = view as? NSTableView { return tv }
                return view.subviews.lazy.compactMap { find(in: $0) }.first
            }
            return window.contentView.flatMap { find(in: $0) }
        }

        deinit { if let m = monitor { NSEvent.removeMonitor(m) } }
    }
}

// MARK: - Duplicate drop alert model

/// State for the "this folder already has a project" alert.
struct DuplicateDropAlert: Identifiable {
    let id = UUID()
    let existingProject: Project
    let urls: [URL]
}

/// State for the Spotlight one-shot confirm sheet. Carries the resume
/// continuation so the LocateFlow can wait for the user's choice.
struct SpotlightConfirmState: Identifiable {
    let id = UUID()
    let project: Project
    let candidate: URL
    let resume: (SpotlightConfirmChoice) -> Void
}

/// State for the post-pick validation error alert. Carries the project so
/// the "Choose Different…" alert button can re-enter the NSOpenPanel step.
struct LocateErrorState: Identifiable {
    let id = UUID()
    let project: Project
    let pickedURL: URL
}

/// State for the "another project is still analysing — cancel and switch?"
/// confirm sheet. Presented when the user selects a different project while
/// the current one has a `bristlenose run` in flight (per Mini-spec 4 step 1).
struct InFlightSwitchPrompt: Identifiable {
    let id = UUID()
    /// The project whose run is currently in flight.
    let runningProject: Project
    /// The new selection the user requested.
    let targetSelection: Set<SidebarSelection>
    /// Selection to restore if the user picks "Stay".
    let priorSelection: Set<SidebarSelection>
}

// MARK: - Row frame preference key

/// Preference key collecting project row frames for drop hit-testing.
/// Each project row reports its frame in the sidebar's named coordinate space.
private struct RowFramePreferenceKey: PreferenceKey {
    static let defaultValue: [UUID: CGRect] = [:]
    static func reduce(value: inout [UUID: CGRect], nextValue: () -> [UUID: CGRect]) {
        value.merge(nextValue(), uniquingKeysWith: { $1 })
    }
}

/// Preference key collecting folder row frames for drop hit-testing.
private struct FolderFramePreferenceKey: PreferenceKey {
    static let defaultValue: [UUID: CGRect] = [:]
    static func reduce(value: inout [UUID: CGRect], nextValue: () -> [UUID: CGRect]) {
        value.merge(nextValue(), uniquingKeysWith: { $1 })
    }
}

/// Preference key carrying the sidebar's global origin so the drop delegate
/// can translate `DropInfo.location` (delegate-local) into the same coord
/// space as the row/folder frames (which we record in `.global`).
private struct SidebarOriginPreferenceKey: PreferenceKey {
    static let defaultValue: CGPoint = .zero
    static func reduce(value: inout CGPoint, nextValue: () -> CGPoint) {
        value = nextValue()
    }
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
    @EnvironmentObject var projectIndex: ProjectIndex
    @EnvironmentObject var pipelineRunner: PipelineRunner
    @EnvironmentObject var toast: ToastStore
    @EnvironmentObject var removalStore: UndoableRemovalStore
    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @AppStorage("selectedProjectID") private var persistedProjectID: String = ""
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    /// Selection binding for the List — uses `SidebarSelection` enum so both
    /// projects and folders are selectable. UUID-based to survive field mutations.
    /// Set enables Cmd+click / Shift+click multi-select natively.
    @State private var selection: Set<SidebarSelection> = []
    /// Tracks whether the project list sidebar column is visible.
    /// Used to gate sidebar-specific toolbar items — if the user has hidden
    /// the project list, don't compensate by moving project controls to the toolbar.
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @State private var showingAIConsent = false
    @State private var aiConsentReviewMode = false
    @State private var showingBuildInfo = false

    /// The ID of the project currently in inline rename mode, or nil.
    @State private var renamingProjectID: UUID?

    /// The ID of the folder currently in inline rename mode, or nil.
    @State private var renamingFolderID: UUID?

    /// The ID of the project currently showing the icon picker popover, or nil.
    @State private var iconPickerProjectID: UUID?

    /// Row frames for drop hit-testing — populated via preference key.
    @State private var rowFrames: [UUID: CGRect] = [:]

    /// Folder frames for drop hit-testing — populated via preference key.
    @State private var folderFrames: [UUID: CGRect] = [:]

    /// The project row currently targeted by a drag hover, or nil.
    @State private var dropTargetProjectID: UUID?

    /// The folder row currently targeted by a drag hover, or nil.
    @State private var dropTargetFolderID: UUID?

    /// Origin of the sidebar (the `.onDrop`-attached view) in global window
    /// coordinates. `DropInfo.location` is local to that view; row/folder
    /// frames are captured in `.global`. Hit-test needs to translate
    /// info.location → global by adding this origin. macOS 26 SwiftUI
    /// quirk: named-coordinate-space hit-test produced a constant offset
    /// (cohort QA, 14 May 2026); going through `.global` is defensive.
    @State private var sidebarGlobalOrigin: CGPoint = .zero

    /// Alert state for duplicate folder drop warning.
    @State private var duplicateDropAlert: DuplicateDropAlert?

    /// Spotlight one-shot confirm sheet — populated when the Locate flow
    /// found a unique high-confidence match. Resolves the awaiting continuation.
    @State private var spotlightConfirm: SpotlightConfirmState?

    /// Validation-error alert after the user picked a folder without
    /// `bristlenose-output/` inside.
    @State private var locateError: LocateErrorState?

    /// In-flight run confirm sheet — set when the user selects a different
    /// project while the current one has a pipeline run going. The sheet
    /// asks whether to cancel the run and switch, or stay on the current
    /// project. Per Mini-spec 4 step 1.
    @State private var inFlightSwitch: InFlightSwitchPrompt?

    /// Re-entry guard for `handleSelectionChange` — set to true while we
    /// programmatically revert `selection` after the user picks "Stay" on
    /// the in-flight confirm sheet, so the re-entrant `.onChange` callback
    /// doesn't trigger another switch attempt.
    @State private var revertingSelection: Bool = false

    /// The single selected item, if exactly one is selected.
    private var soleSelection: SidebarSelection? {
        selection.count == 1 ? selection.first : nil
    }

    /// The currently selected project (when exactly one project is selected).
    /// Computed so that mutations to `projectIndex.projects` (e.g. rename,
    /// updateLastOpened) don't break selection — the UUID is stable.
    private var selectedProject: Project? {
        guard case .project(let id) = soleSelection else { return nil }
        return projectIndex.projects.first { $0.id == id }
    }

    /// The currently selected folder (when exactly one folder is selected).
    private var selectedFolder: Folder? {
        guard case .folder(let id) = soleSelection else { return nil }
        return projectIndex.folders.first { $0.id == id }
    }

    /// Extract the project UUID from a single selection (for persistence and onChange).
    private var selectedProjectID: UUID? {
        guard case .project(let id) = soleSelection else { return nil }
        return id
    }

    /// How many items are currently selected.
    private var selectionCount: Int { selection.count }

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
        // No .navigationTitle on the detail view — that would add a visible
        // toolbar title item that duplicates the custom icon+name ToolbarItem.
        // NSWindow.title is managed by WindowTitleManager below.
        }
        .background(WindowTitleManager(title: selectedProject?.name ?? "Bristlenose"))
        .background(SidebarDeselectMonitor { selection = [] })
        .overlay(alignment: .bottomTrailing) {
            // Compact build-info diagnostic — Debug only by default; Release
            // exposure gated on a custom build flag so internal/ad-hoc archives
            // can opt in. Never shipped to TestFlight / App Store users.
            // See BuildInfo.swift for the rationale and target format.
            #if DEBUG || BRISTLENOSE_SHOW_DIAGNOSTIC_OVERLAY
            Text(BuildInfo.current.oneLine(sidecar: serveManager.mode?.shortSummary ?? "?"))
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Color.secondary.opacity(0.6))
                .textSelection(.enabled)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .allowsHitTesting(true)
                .accessibilityHidden(true)
            #endif
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
        .onChange(of: selection) { oldSelection, newSelection in
            handleSelectionChange(from: oldSelection, to: newSelection)
        }
        // When consent is granted (version updated), start serve for the
        // already-selected project if one exists.
        .onChange(of: consentVersion) { _, _ in
            if hasConsent, let project = selectedProject {
                if !project.path.isEmpty && project.isAvailable {
                    serveManager.start(projectPath: project.path)
                }
            }
        }
        .onAppear {
            // Restore last-selected project from persisted ID.
            if selection.isEmpty, !persistedProjectID.isEmpty,
               let id = UUID(uuidString: persistedProjectID),
               projectIndex.projects.contains(where: { $0.id == id }) {
                selection = [.project(id)]
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
        .onReceive(NotificationCenter.default.publisher(for: .showBuildInfoSheet)) { _ in
            showingBuildInfo = true
        }
        .sheet(isPresented: $showingBuildInfo) {
            BuildInfoSheet(
                sidecar: serveManager.mode?.shortSummary ?? "?",
                onDismiss: { showingBuildInfo = false }
            )
        }
        // File > New Project (Cmd+N) and sidebar [+] button.
        .onReceive(NotificationCenter.default.publisher(for: .createNewProject)) { _ in
            createNewProject()
        }
        // Undo restored a removal batch — re-apply the prior selection.
        .onReceive(NotificationCenter.default.publisher(for: .undoableRemovalRestoredSelection)) { note in
            if let restored = note.userInfo?["selection"] as? Set<SidebarSelection> {
                selection = restored
            }
        }
        // File > New Folder (⇧⌘N) and sidebar folder.badge.plus button.
        .onReceive(NotificationCenter.default.publisher(for: .createNewFolder)) { _ in
            createNewFolder()
        }
        .modifier(ProjectNotificationReceivers(
            selection: $selection,
            renamingProjectID: $renamingProjectID,
            renamingFolderID: $renamingFolderID,
            projectIndex: projectIndex,
            onLocate: { project in locateProject(project) },
            onRemoveFromSidebar: { removeSelectedProjectsFromSidebar() }
        ))
        .sheet(isPresented: $showingAIConsent) {
            AIConsentView(
                isReviewMode: aiConsentReviewMode,
                onDismiss: { showingAIConsent = false }
            )
            .environmentObject(i18n)
            .interactiveDismissDisabled(!aiConsentReviewMode)
        }
        .alert(
            i18n.t("desktop.chrome.duplicateProject"),
            isPresented: Binding(
                get: { duplicateDropAlert != nil },
                set: { if !$0 { duplicateDropAlert = nil } }
            ),
            presenting: duplicateDropAlert
        ) { alert in
            Button(i18n.t("desktop.chrome.openExisting")) {
                selection = [.project(alert.existingProject.id)]
            }
            Button(i18n.t("desktop.chrome.createAnyway")) {
                let directories = alert.urls.filter { $0.hasDirectoryPath }
                let files = alert.urls.filter { !$0.hasDirectoryPath }
                createProjectFromURLs(directories: directories, files: files)
            }
            Button(i18n.t("common.cancel"), role: .cancel) {}
        } message: { alert in
            Text(String(
                format: i18n.t("desktop.chrome.duplicateProjectMessage"),
                alert.existingProject.name
            ))
        }
        .sheet(item: $spotlightConfirm) { state in
            SpotlightConfirmSheet(
                project: state.project,
                candidate: state.candidate,
                onChoose: { choice in
                    state.resume(choice)
                    spotlightConfirm = nil
                }
            )
            .environmentObject(i18n)
        }
        .alert(
            i18n.t("desktop.chrome.locateError.title"),
            isPresented: Binding(
                get: { locateError != nil },
                set: { if !$0 { locateError = nil } }
            ),
            presenting: locateError
        ) { err in
            Button(i18n.t("desktop.chrome.spotlight.chooseDifferent")) {
                let project = err.project
                locateError = nil
                // Re-enter the flow at the NSOpenPanel step. Skip Spotlight
                // since the user has already rejected its suggestion (if any).
                Task { @MainActor in
                    chooseDifferentFolder(for: project)
                }
            }
            .keyboardShortcut(.defaultAction)
            Button(i18n.t("common.cancel"), role: .cancel) {}
        } message: { _ in
            // One honest message — the prior split (noOutputFolder /
            // wrongFolder) leaned on a heuristic that misclassified
            // researchers who keep recordings in subdirs. William's pick.
            Text(i18n.t("desktop.chrome.locateError.message"))
        }
        // In-flight pipeline-run guard (Mini-spec 4 step 1). Presented when
        // the user picks a different project while the prior one's run is
        // still going. Choosing "Stay" reverts the sidebar selection.
        .alert(
            i18n.t("desktop.chrome.inFlightSwitchTitle"),
            isPresented: Binding(
                get: { inFlightSwitch != nil },
                set: { if !$0 { inFlightSwitch = nil } }
            ),
            presenting: inFlightSwitch
        ) { prompt in
            Button(i18n.t("desktop.chrome.cancelAndSwitch"), role: .destructive) {
                resolveInFlightSwitch(prompt, cancelAndSwitch: true)
            }
            // "Stay" reverts the sidebar selection — it mutates state, not a
            // no-op dismissal. Drop `.cancel` role; make it the default action
            // so Return commits Stay (gruber-pass finding 39; HIG pattern).
            Button(i18n.t("desktop.chrome.stay")) {
                resolveInFlightSwitch(prompt, cancelAndSwitch: false)
            }
            .keyboardShortcut(.defaultAction)
        } message: { prompt in
            Text(String(
                format: i18n.t("desktop.chrome.inFlightSwitchMessage"),
                prompt.runningProject.name
            ))
        }
    }

    /// Re-enter the Locate flow at the NSOpenPanel step (skips Spotlight,
    /// since this fires after the user already rejected one folder).
    private func chooseDifferentFolder(for project: Project) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.message = String(format: i18n.t("desktop.chrome.locateMessage"), project.name)
        panel.begin { response in
            Task { @MainActor in
                guard response == .OK, let url = panel.url else { return }
                if LocateFlow.folderLooksAnalysed(url: url) {
                    projectIndex.relocateProject(id: project.id, newPath: url.path)
                    bridgeHandler.selectedProjectPath = url.path
                    bridgeHandler.selectedProjectAvailable = true
                    bridgeHandler.selectedProjectRevealablePath = url.path
                    if selection.contains(.project(project.id)), hasConsent {
                        serveManager.start(projectPath: url.path)
                    }
                } else {
                    locateError = LocateErrorState(project: project, pickedURL: url)
                }
            }
        }
    }

    // MARK: - Selection change

    /// Extract the sole-selected project UUID from a selection set, or nil.
    private func soleProjectID(in selection: Set<SidebarSelection>) -> UUID? {
        guard selection.count == 1,
              case .project(let id) = selection.first else { return nil }
        return id
    }

    private func handleSelectionChange(
        from oldSelection: Set<SidebarSelection>,
        to newSelection: Set<SidebarSelection>
    ) {
        // Re-entry guard — see `revertingSelection` documentation.
        if revertingSelection {
            revertingSelection = false
            return
        }

        // In-flight run guard (Mini-spec 4 step 1). If the user is leaving a
        // project whose pipeline run is going, present the confirm sheet
        // before any teardown — UX needs the chance to back out.
        if let oldID = soleProjectID(in: oldSelection),
           soleProjectID(in: newSelection) != oldID,
           pipelineRunner.state[oldID] == .running,
           let runningProject = projectIndex.projects.first(where: { $0.id == oldID }) {
            inFlightSwitch = InFlightSwitchPrompt(
                runningProject: runningProject,
                targetSelection: newSelection,
                priorSelection: oldSelection
            )
            return
        }

        applySelectionChange(newSelection)
    }

    /// Resolve a sidebar selection — wires bridge state and orchestrates the
    /// sidecar lifecycle via `switchProject`. Separated from
    /// `handleSelectionChange` so the in-flight confirm path can call it
    /// after cancelling the prior run.
    private func applySelectionChange(_ newSelection: Set<SidebarSelection>) {
        bridgeHandler.reset()

        let sole = newSelection.count == 1 ? newSelection.first : nil

        switch sole {
        case .project(let id):
            bridgeHandler.selectedFolderName = ""
            if let project = projectIndex.projects.first(where: { $0.id == id }) {
                persistedProjectID = id.uuidString
                bridgeHandler.selectedProjectPath = project.path
                bridgeHandler.selectedProjectAvailable = project.isAvailable
                bridgeHandler.selectedProjectRevealablePath = revealPath(for: project) ?? ""
                projectIndex.updateLastOpened(id: id)
                // Gate serve on consent + availability — no data leaves the machine
                // before the user has seen the AI data disclosure (Apple 5.1.2(i)).
                if hasConsent && !project.path.isEmpty && project.isAvailable {
                    let path = project.path
                    Task { @MainActor in
                        await serveManager.switchProject(to: path)
                    }
                }
            }
        case .folder(let id):
            persistedProjectID = ""
            bridgeHandler.selectedProjectPath = ""
            bridgeHandler.selectedProjectRevealablePath = ""
            bridgeHandler.selectedFolderName =
                projectIndex.folders.first { $0.id == id }?.name ?? ""
            serveManager.stop()
        default:
            // Multi-select or empty — stop serve, clear state.
            persistedProjectID = ""
            bridgeHandler.selectedProjectPath = ""
            bridgeHandler.selectedProjectRevealablePath = ""
            bridgeHandler.selectedFolderName = ""
            serveManager.stop()
        }
    }

    /// Resolve the in-flight switch confirm sheet. Called from the alert
    /// button handlers. On "Cancel and Switch" we cancel the running pipeline
    /// then proceed with the deferred selection; on "Stay" we restore the
    /// prior selection.
    private func resolveInFlightSwitch(_ prompt: InFlightSwitchPrompt, cancelAndSwitch: Bool) {
        inFlightSwitch = nil
        if cancelAndSwitch {
            pipelineRunner.cancel(project: prompt.runningProject)
            applySelectionChange(prompt.targetSelection)
        } else {
            // Revert the SwiftUI selection back to the running project.
            // The re-entrant `.onChange` is suppressed by `revertingSelection`.
            revertingSelection = true
            selection = prompt.priorSelection
        }
    }

    // MARK: - Notification receivers (extracted to reduce body complexity)
    // Split into a ViewModifier to keep the main body within type-checker limits.

    // MARK: - Project and folder creation

    /// Create a new project and put it in inline rename mode.
    private func createNewProject() {
        let project = projectIndex.addProject(name: i18n.t("desktop.chrome.newProject"), path: "")
        selection = [.project(project.id)]
        renamingProjectID = project.id
    }

    /// Create a new folder and put it in inline rename mode.
    private func createNewFolder() {
        let folder = projectIndex.addFolder(name: i18n.t("desktop.chrome.newFolder"))
        selection = [.folder(folder.id)]
        renamingFolderID = folder.id
    }

    /// Folder-context-menu delete. Project removals go through
    /// `removeFromSidebarContextMenu(targetingProject:)` which routes via
    /// `UndoableRemovalStore`. Folders don't get undo today (separate scope).
    private func deleteFromContextMenu(targetingFolder id: UUID) {
        if selection.contains(.folder(id)) {
            let folderIds = selection.compactMap { sel -> UUID? in
                if case .folder(let fid) = sel { return fid }
                return nil
            }
            for fid in folderIds {
                selection.remove(.folder(fid))
                projectIndex.removeFolder(id: fid)
            }
        } else {
            // Right-clicked row is not in the current selection — leave
            // selection alone (Finder behaviour) and act only on the target.
            projectIndex.removeFolder(id: id)
        }
    }

    /// Best path to reveal in Finder. For `.ready` projects use the live path;
    /// for `.cantFind`, fall back to `lastSeenPath` so Finder can show its
    /// own dead-alias UX (HANDOFF §7). Returns nil when there is no path to
    /// hand to Finder, which is the signal to dim the menu item.
    private func revealPath(for project: Project) -> String? {
        if project.isAvailable, !project.path.isEmpty { return project.path }
        let fallback = project.lastSeenPath
        return fallback.isEmpty ? nil : fallback
    }

    private func canRevealInFinder(_ project: Project) -> Bool {
        revealPath(for: project) != nil
    }

    private func revealInFinder(_ project: Project) {
        guard let path = revealPath(for: project) else { return }
        NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: path)
    }

    private func locateProject(_ project: Project) {
        let flow = LocateFlow(project: project, i18n: i18n)
        flow.run(
            confirm: { candidate in
                await withCheckedContinuation { (cont: CheckedContinuation<SpotlightConfirmChoice, Never>) in
                    Task { @MainActor in
                        spotlightConfirm = SpotlightConfirmState(
                            project: project, candidate: candidate, resume: { choice in
                                cont.resume(returning: choice)
                            }
                        )
                    }
                }
            },
            completion: { [self] result in
                switch result {
                case .located(let url):
                    projectIndex.relocateProject(id: project.id, newPath: url.path)
                    bridgeHandler.selectedProjectPath = url.path
                    bridgeHandler.selectedProjectAvailable = true
                    bridgeHandler.selectedProjectRevealablePath = url.path
                    if selection.contains(.project(project.id)), hasConsent {
                        serveManager.start(projectPath: url.path)
                    }
                case .invalidFolder(let pickedURL):
                    locateError = LocateErrorState(project: project, pickedURL: pickedURL)
                case .cancelled:
                    break
                }
            }
        )
    }

    /// Remove the selected project(s) from the sidebar via the undoable store.
    /// All selected projects go into a single Pending batch — undo restores
    /// the whole batch at once, toast reads "N projects removed" when N>1.
    /// Projects whose pipeline is .running / .queued are skipped with a
    /// per-project toast (symmetric with `handleDropOnProject`).
    private func removeSelectedProjectsFromSidebar() {
        let candidates: [Project] = selection.compactMap { sel in
            guard case .project(let id) = sel else { return nil }
            return projectIndex.projects.first { $0.id == id }
        }
        let (removable, blockedNames) = partitionRemovable(candidates)
        if !blockedNames.isEmpty {
            // One toast even when multiple are blocked — the first name is
            // enough to point the user at the issue.
            let first = blockedNames.first ?? ""
            toast.show(String(
                format: i18n.t("desktop.toast.removeBlockedByRun"),
                first
            ))
        }
        guard !removable.isEmpty else { return }
        let priorSelection = selection
        for project in removable {
            selection.remove(.project(project.id))
        }
        removalStore.removeFromSidebar(removable, priorSelection: priorSelection)
    }

    /// Same logic but for the context-menu single-row case (Finder pattern —
    /// applies to all selected rows if the clicked row is part of the selection,
    /// otherwise to only that row).
    private func removeFromSidebarContextMenu(targetingProject id: UUID) {
        if selection.contains(.project(id)) {
            removeSelectedProjectsFromSidebar()
            return
        }
        guard let project = projectIndex.projects.first(where: { $0.id == id }) else { return }
        let (removable, blockedNames) = partitionRemovable([project])
        if let first = blockedNames.first {
            toast.show(String(
                format: i18n.t("desktop.toast.removeBlockedByRun"),
                first
            ))
            return
        }
        guard !removable.isEmpty else { return }
        removalStore.removeFromSidebar(removable, priorSelection: selection)
    }

    /// Split candidates into (removable, blocked-by-running-pipeline).
    /// Pipeline-state coupling avoids the "remove + sidecar keeps writing for
    /// hours" footgun. Symmetric with `handleDropOnProject`'s `.running` /
    /// `.queued` rejection.
    private func partitionRemovable(_ projects: [Project]) -> (removable: [Project], blockedNames: [String]) {
        var removable: [Project] = []
        var blocked: [String] = []
        for project in projects {
            switch pipelineRunner.state[project.id] {
            case .running, .queued:
                blocked.append(project.name)
            default:
                removable.append(project)
            }
        }
        return (removable, blocked)
    }

    // MARK: - Drag and drop

    /// File extensions accepted by the Bristlenose pipeline.
    /// Matches `ALL_EXTENSIONS` in `bristlenose/models.py` plus `.txt` (analyze mode).
    /// Directories are always accepted (they become project roots).
    private static let acceptedExtensions: Set<String> = [
        // Audio
        "wav", "mp3", "m4a", "flac", "ogg", "wma", "aac",
        // Video
        "mp4", "m4v", "mov", "avi", "mkv", "webm",
        // Subtitles
        "srt", "vtt",
        // Documents
        "docx", "txt",
    ]

    /// Filter URLs to only accepted media types. Directories always pass.
    private static func filterAcceptedURLs(_ urls: [URL]) -> [URL] {
        urls.filter { url in
            if url.hasDirectoryPath { return true }
            let ext = url.pathExtension.lowercased()
            return acceptedExtensions.contains(ext)
        }
    }

    /// Handle files/folders dropped from Finder onto the sidebar free space.
    /// - Folder: create project pointing to that directory (scan all files)
    /// - File(s): create project with inputFiles restricting to the dropped files
    /// De-duplicates by path — if a project already exists for that folder, selects it.
    private func handleDrop(providers: [NSItemProvider]) {
        Task {
            let urls = await loadURLs(from: providers)
            let accepted = Self.filterAcceptedURLs(urls)
            await MainActor.run {
                processDroppedURLs(accepted)
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
        guard !urls.isEmpty else { return }

        let directories = urls.filter { $0.hasDirectoryPath }
        let files = urls.filter { !$0.hasDirectoryPath }

        // Check for duplicate: single folder that already has a project.
        if directories.count == 1 && files.isEmpty {
            if let existing = projectIndex.findByPath(directories[0].path) {
                duplicateDropAlert = DuplicateDropAlert(
                    existingProject: existing, urls: urls
                )
                return
            }
        }

        createProjectFromURLs(directories: directories, files: files)
    }

    /// Create a project from classified URLs (after duplicate check passes).
    private func createProjectFromURLs(directories: [URL], files: [URL]) {
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
            selection = [.project(project.id)]
            renamingProjectID = project.id
            // Folder-drop is the explicit signal to analyse — auto-run.
            // Plan §Phase 3 point 2 (the ~90% happy path).
            pipelineRunner.start(project: project)
        } else if !directories.isEmpty || !files.isEmpty {
            // Multiple items — one project with explicit input list.
            // CLI's `discover_files` doesn't accept a subset list yet
            // (memory project_inputfiles_model), so we capture the files but
            // do NOT start the pipeline. The project content area will show
            // the unsupported-subset state (Slice 6) — for now the project
            // simply sits in `.idle`.
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
            selection = [.project(project.id)]
            renamingProjectID = project.id
        }
    }

    /// Handle files/folders dropped onto an existing project row.
    /// Adds the dropped interviews to that project's input list and — when
    /// appropriate — kicks off a pipeline run on them.
    ///
    /// Drop-policy matrix (plan §Phase 5 finding 40):
    /// - target `.running` / `.queued`: reject (toast); never silently queue
    ///   another drop on a busy project
    /// - target `.ready` (already analysed): accept the addFiles, show the
    ///   "extra interviews not supported yet" toast, do NOT re-run
    /// - target `.idle` / `.failed` / `.scanning` / `.unreachable`: accept,
    ///   addFiles, kick off pipeline (`PipelineRunner` will queue if another
    ///   project is currently running)
    private func handleDropOnProject(id: UUID, providers: [NSItemProvider]) {
        Task {
            let urls = await loadURLs(from: providers)
            let accepted = Self.filterAcceptedURLs(urls)
            await MainActor.run {
                guard let project = projectIndex.projects.first(where: { $0.id == id }) else {
                    return
                }

                // Plan §11 data-integrity guards:
                // 1. Silently dedupe a drop of the project's own folder
                //    (researcher dragged the project root back onto itself).
                // 2. Reject a drop that contains a *different* folder which
                //    is itself a Bristlenose project — adding it as files
                //    would corrupt directory structure / leak its outputs.
                let projectPath = URL(fileURLWithPath: project.path)
                    .standardizedFileURL.path
                var filteredURLs: [URL] = []
                for url in accepted {
                    let path = url.standardizedFileURL.path
                    if url.hasDirectoryPath, path == projectPath {
                        // Self-drop — ignore silently. No toast (this is the
                        // gesture that produces the 0.4s flash in the full
                        // §11 spec; for cohort 1 we just no-op).
                        continue
                    }
                    if url.hasDirectoryPath, LocateFlow.folderLooksAnalysed(url: url) {
                        // Plan §11 reject — non-modal toast, not an alert.
                        // The cohort-confidence UX rule: don't open a modal
                        // to apologise for a thing the user shouldn't have
                        // tried; tell them what to do instead, briefly, and
                        // get out of the way. Apple-HIG-aligned: alerts are
                        // for decisions, toasts are for acknowledgements.
                        let message = String(
                            format: i18n.t("desktop.chrome.dropProjectOntoProjectToast"),
                            url.lastPathComponent
                        )
                        toast.show(message)
                        return
                    }
                    filteredURLs.append(url)
                }

                let paths = filteredURLs.map { $0.path }
                guard !paths.isEmpty else { return }

                switch pipelineRunner.state[id] {
                case .running, .queued:
                    toast.show("Finish or stop the current run before adding more.")
                    return
                case .ready:
                    projectIndex.addFiles(to: id, files: paths)
                    selection = [.project(id)]
                    toast.show("Adding extra interviews to an analysed project isn't supported yet.")
                    return
                case .failed:
                    // Don't silently retry a known-broken pipeline (would burn
                    // LLM spend repeating the same failure). User explicitly
                    // re-runs from the toolbar pill's Retry button.
                    toast.show("Use Retry on the toolbar to try this run again.")
                    return
                case .unreachable:
                    // Volume not mounted / folder gone — addFiles would write
                    // to a path that doesn't exist; pipeline would fail with
                    // a generic error stacked on top. Surface the real cause.
                    toast.show("This project's folder isn't reachable right now.")
                    return
                default:
                    break
                }

                projectIndex.addFiles(to: id, files: paths)
                selection = [.project(id)]
                // Toast confirmation: "Added 3 interviews to Project Name"
                let count = paths.count
                let message = String(
                    format: i18n.t("desktop.chrome.addedInterviews"),
                    count, project.name
                )
                toast.show(message)

                // Re-fetch the project — addFiles may have mutated inputFiles.
                if let updated = projectIndex.projects.first(where: { $0.id == id }) {
                    // Only auto-run if this project is folder-shaped
                    // (`inputFiles == nil`). File-subset projects can't run
                    // until the CLI gains `--files` support.
                    if updated.inputFiles == nil {
                        pipelineRunner.start(project: updated)
                    }
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
        // Project icon + name — replaces the system title lozenge (.toolbar(removing: .title)
        // is set on the detail view). Shows the project's custom SF Symbol and name directly
        // on the toolbar surface, matching the Finder visual pattern.
        ToolbarItem(placement: .navigation) {
            HStack(spacing: 4) {
                if let project = selectedProject {
                    Image(systemName: project.icon ?? IconPickerPopover.defaultIcon)
                        .foregroundStyle(.secondary)
                }
                Text(selectedProject?.name ?? "Bristlenose")
                    .lineLimit(1)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel(selectedProject?.name ?? "Bristlenose")
        }

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

        // Back / forward as a joined Finder-style control group.
        // .controlGroupStyle(.navigation) renders the chevrons in a single
        // bordered pill — the same appearance as Finder and Safari.
        ToolbarItem(placement: .navigation) {
            ControlGroup {
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
            .controlGroupStyle(.navigation)
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

        // Pipeline activity pill — only visible when the selected project's
        // run is .running / .queued / .failed. Self-hides otherwise.
        if let project = selectedProject {
            ToolbarItem(placement: .primaryAction) {
                PipelineActivityItem(
                    project: project,
                    pipelineRunner: pipelineRunner,
                    liveData: pipelineRunner.liveData
                )
            }
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
                .onMove { source, destination in
                    projectIndex.moveSidebarItems(from: source, to: destination)
                }

                // Empty state hint when no projects exist.
                if projectIndex.projects.isEmpty {
                    Text(i18n.t("desktop.chrome.emptyStateHint"))
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.top, 20)
                        .listRowSeparator(.hidden)
                }
            } header: {
                Text(i18n.t("desktop.chrome.projects"))
            }
        }
        .accessibilityLabel(i18n.t("desktop.chrome.projects"))
        // Capture the sidebar's origin in global window coordinates so the
        // drop delegate can translate DropInfo.location (local to this view)
        // into the same global space the row/folder frames are recorded in.
        .background(
            GeometryReader { geo in
                Color.clear.preference(
                    key: SidebarOriginPreferenceKey.self,
                    value: geo.frame(in: .global).origin
                )
            }
        )
        .onPreferenceChange(SidebarOriginPreferenceKey.self) { origin in
            sidebarGlobalOrigin = origin
        }
        .onPreferenceChange(RowFramePreferenceKey.self) { frames in
            rowFrames = frames
        }
        .onPreferenceChange(FolderFramePreferenceKey.self) { frames in
            folderFrames = frames
        }
        .onDrop(of: [.fileURL, .utf8PlainText], delegate: SidebarDropDelegate(
            rowFrames: rowFrames,
            folderFrames: folderFrames,
            receiverGlobalOrigin: sidebarGlobalOrigin,
            dropTargetProjectID: $dropTargetProjectID,
            dropTargetFolderID: $dropTargetFolderID,
            onDropOnProject: { id, providers in handleDropOnProject(id: id, providers: providers) },
            onDropOnFreeSpace: { providers in handleDrop(providers: providers) },
            onMoveProjectToFolder: { projectId, folderId in
                projectIndex.moveProject(projectId: projectId, toFolder: folderId)
            }
        ))
        .focusSection()
        // Empty-space deselection is handled by SidebarDeselectMonitor (NSEvent
        // local monitor on the NavigationSplitView background) — no SwiftUI
        // gesture needed here, which avoids macOS 26 List selection conflicts.
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
            .onMove { source, destination in
                projectIndex.moveProjectsInFolder(folder.id, from: source, to: destination)
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
                    selection.remove(.folder(folder.id))
                    projectIndex.removeFolder(id: folder.id)
                }
            )
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
                    deleteFromContextMenu(targetingFolder: folder.id)
                }
            }
        }
        .tag(SidebarSelection.folder(folder.id))
        .background(
            GeometryReader { geo in
                Color.clear.preference(
                    key: FolderFramePreferenceKey.self,
                    value: [folder.id: geo.frame(in: .global)]
                )
            }
        )
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(Color.accentColor, lineWidth: 2)
                .opacity(dropTargetFolderID == folder.id ? 1 : 0)
        )
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
            isDropTarget: dropTargetProjectID == project.id,
            liveData: pipelineRunner.liveData,
            onRename: { newName in
                projectIndex.renameProject(id: project.id, newName: newName)
            },
            onShowInFinder: { revealInFinder(project) },
            onDelete: {
                removeFromSidebarContextMenu(targetingProject: project.id)
            },
            onLocate: project.isAvailable ? nil : { locateProject(project) }
        )
        .background(
            GeometryReader { geo in
                Color.clear.preference(
                    key: RowFramePreferenceKey.self,
                    value: [project.id: geo.frame(in: .global)]
                )
            }
        )
        .tag(SidebarSelection.project(project.id))
        .draggable(project.id.uuidString)
        .contextMenu {
            // "Locate…" for moved/deleted projects — actionable first.
            if case .cantFind = project.availability {
                Button(i18n.t("desktop.chrome.locate")) {
                    locateProject(project)
                }
                Divider()
            }

            Button(i18n.t("desktop.menu.project.showInFinder")) {
                revealInFinder(project)
            }
            .disabled(!canRevealInFinder(project))

            Button(i18n.t("desktop.menu.project.rename")) {
                renamingProjectID = project.id
            }

            Button(i18n.t("desktop.menu.project.chooseIcon")) {
                iconPickerProjectID = project.id
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
            Button(i18n.t("desktop.menu.project.removeFromSidebar"), role: .destructive) {
                removeFromSidebarContextMenu(targetingProject: project.id)
            }
        }
        .popover(
            isPresented: Binding(
                get: { iconPickerProjectID == project.id },
                set: { if !$0 { iconPickerProjectID = nil } }
            ),
            arrowEdge: .trailing
        ) {
            IconPickerPopover(
                selectedIcon: project.icon,
                onSelect: { icon in
                    projectIndex.setIcon(id: project.id, icon: icon)
                    iconPickerProjectID = nil
                }
            )
        }
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        if let project = selectedProject {
            if !project.isAvailable {
                // Project directory is not accessible — volume ejected or folder moved.
                unavailableProjectView(project)
            } else if project.path.isEmpty {
                // New project with no files yet — prompt user to add interviews.
                ContentUnavailableView(
                    i18n.t("desktop.chrome.dragInterviews"),
                    systemImage: "square.and.arrow.down",
                    description: Text(i18n.t("desktop.chrome.dragInterviewsDescription"))
                )
            } else if project.inputFiles != nil {
                // File-subset project — CLI can't analyse this shape yet.
                // Show files + Show-in-Finder; pipeline never starts.
                UnsupportedSubsetView(project: project)
            } else {
                ZStack {
                    switch serveManager.state {
                    case .idle, .starting:
                        BootView(phase: .startingSidecar)

                    case .running:
                        WebView(url: serveURLWithLocale, bridgeHandler: bridgeHandler, authToken: serveManager.authToken)
                            .id(project.id)
                            .accessibilityLabel(i18n.t("desktop.chrome.reportContent"))
                            .accessibilityHidden(!bridgeHandler.isReady)
                            .focusSection()

                        // Boot surface stays visible until the React SPA posts "ready"
                        // — same icon + tagline as the sidecar-starting phase, just
                        // with a different status line, so the eye doesn't relocate.
                        if !bridgeHandler.isReady {
                            ZStack {
                                Color(nsColor: .windowBackgroundColor)
                                BootView(phase: .loadingReport)
                            }
                            .transition(.opacity)
                        }

                    case .failed(let error):
                        BootView(phase: .failed(message: error, retry: {
                            serveManager.start(projectPath: project.path)
                        }))
                    }
                }
                .animation(reduceMotion ? nil : .easeInOut(duration: 0.2), value: bridgeHandler.isReady)
            }
        } else if selectionCount > 1 {
            ContentUnavailableView(
                String(format: i18n.t("desktop.chrome.multipleSelected"), selectionCount),
                systemImage: "square.stack",
                description: Text(i18n.t("desktop.chrome.multipleSelectedHint"))
            )
        } else {
            WelcomeView(
                variant: projectIndex.projects.isEmpty ? .firstRun : .noSelection,
                onNewProject: { createNewProject() },
                onDropFolders: { urls in
                    let directories = urls.filter { $0.hasDirectoryPath }
                    let files = urls.filter { !$0.hasDirectoryPath }
                    createProjectFromURLs(directories: directories, files: files)
                },
                onShowAIPrivacy: {
                    NotificationCenter.default.post(name: .showAIConsentSheet, object: nil)
                }
            )
        }
    }

    /// Detail pane for an unavailable project — shows why and offers Locate action.
    @ViewBuilder
    private func unavailableProjectView(_ project: Project) -> some View {
        switch project.availability {
        case .cantFind(let reason):
            switch reason {
            case .unmountedVolume(let name), .networkUnreachable(let name):
                ContentUnavailableView {
                    Label(i18n.t("desktop.chrome.projectUnavailable"),
                          systemImage: "externaldrive.trianglebadge.exclamationmark")
                } description: {
                    Text(name)
                    Text(i18n.t("desktop.chrome.projectUnavailableHint"))
                }
            case .moved, .missingBookmark:
                ContentUnavailableView {
                    Label(i18n.t("desktop.chrome.projectMoved"),
                          systemImage: "questionmark.folder")
                } description: {
                    Text(i18n.t("desktop.chrome.projectMovedDescription"))
                } actions: {
                    Button(i18n.t("desktop.chrome.locate")) {
                        locateProject(project)
                    }
                }
            }
        case .inCloud:
            ContentUnavailableView {
                Label(i18n.t("desktop.availability.inCloud"),
                      systemImage: "icloud.and.arrow.down")
            } description: {
                Text(i18n.t("desktop.chrome.projectUnavailableHint"))
            }
        case .ready:
            EmptyView()
        }
    }
}

// MARK: - Export toolbar menu

// MARK: - Project notification receivers (extracted ViewModifier)

/// Receives project-related notifications (rename, delete, move, locate) from the
/// native menu bar. Extracted from ContentView's body to keep the SwiftUI expression
/// within the type-checker's complexity limits.
private struct ProjectNotificationReceivers: ViewModifier {
    @Binding var selection: Set<SidebarSelection>
    @Binding var renamingProjectID: UUID?
    @Binding var renamingFolderID: UUID?
    let projectIndex: ProjectIndex
    let onLocate: (Project) -> Void
    let onRemoveFromSidebar: () -> Void

    /// The single selected item, if exactly one.
    private var sole: SidebarSelection? {
        selection.count == 1 ? selection.first : nil
    }

    func body(content: Content) -> some View {
        content
            .onReceive(NotificationCenter.default.publisher(for: .renameSelectedProject)) { _ in
                if case .project(let id) = sole {
                    renamingProjectID = id
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .renameSelectedFolder)) { _ in
                if case .folder(let id) = sole {
                    renamingFolderID = id
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .deleteSelectedFolder)) { _ in
                // Delete all selected folders.
                let folderIds = selection.compactMap { sel -> UUID? in
                    if case .folder(let id) = sel { return id }
                    return nil
                }
                for id in folderIds {
                    selection.remove(.folder(id))
                    projectIndex.removeFolder(id: id)
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .moveSelectedProject)) { notification in
                guard case .project(let projectId) = sole else { return }
                let folderId = notification.userInfo?["folderId"] as? UUID
                projectIndex.moveProject(projectId: projectId, toFolder: folderId)
            }
            .onReceive(NotificationCenter.default.publisher(for: .locateSelectedProject)) { _ in
                guard case .project(let id) = sole else { return }
                if let project = projectIndex.projects.first(where: { $0.id == id }) {
                    onLocate(project)
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .removeSelectedProjectsFromSidebar)) { _ in
                onRemoveFromSidebar()
            }
    }
}

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

// MARK: - Spotlight confirm sheet

/// Confirms a unique Spotlight match for a `.cantFind` project. Rendered as a
/// SwiftUI sheet so it inherits the window centring + Escape-to-cancel that
/// HIG expects. Three buttons mirror Finder's "Use This / Choose Different /
/// Cancel" pattern.
struct SpotlightConfirmSheet: View {
    let project: Project
    let candidate: URL
    let onChoose: (SpotlightConfirmChoice) -> Void

    @EnvironmentObject var i18n: I18n

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(String(format: i18n.t("desktop.chrome.spotlight.title"), project.name))
                .font(.headline)

            Text(breadcrumb(for: candidate))
                .font(.callout)
                .foregroundStyle(.secondary)
                .lineLimit(2)
                .truncationMode(.middle)
                .textSelection(.enabled)
                // VoiceOver reads `›` literally ("right pointing angle
                // quotation mark") — comma-separated segments read cleanly.
                .accessibilityLabel(String(
                    format: i18n.t("desktop.chrome.spotlight.breadcrumbA11y"),
                    breadcrumbSegments(for: candidate).joined(separator: ", ")
                ))

            HStack {
                Button(i18n.t("common.cancel"), role: .cancel) {
                    onChoose(.cancel)
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Button(i18n.t("desktop.chrome.spotlight.chooseDifferent")) {
                    onChoose(.chooseDifferent)
                }

                Button(i18n.t("desktop.chrome.spotlight.useThisFolder")) {
                    onChoose(.useThisFolder)
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 420)
    }

    /// Finder-style breadcrumb: `~ › Research › 2026 › Project Ikea`.
    private func breadcrumb(for url: URL) -> String {
        breadcrumbSegments(for: url).joined(separator: " › ")
    }

    /// Path segments suitable for a comma-joined VoiceOver label.
    private func breadcrumbSegments(for url: URL) -> [String] {
        let home = NSHomeDirectory()
        let path = url.path
        var trimmed = path
        var leading = ""
        if path.hasPrefix(home) {
            trimmed = String(path.dropFirst(home.count))
            leading = "~"
        }
        let parts = trimmed.split(separator: "/").map(String.init)
        return leading.isEmpty ? parts : ([leading] + parts)
    }
}

// MARK: - Sidebar drop delegate

/// Custom `DropDelegate` that uses geometry hit-testing to determine whether a
/// drop targets an existing project row, a folder, or free sidebar space.
///
/// Handles two drop types:
/// - **File URLs** (from Finder): add files to existing project or create new project
/// - **Plain text** (internal project UUID): move a project into a folder
///
/// This avoids per-row `.onDrop` which breaks List selection on macOS 26.
/// Row/folder frames are collected via preference keys in the "sidebar"
/// coordinate space.
private struct SidebarDropDelegate: DropDelegate {
    /// Row frames recorded in `.global` (window-relative) coordinate space.
    let rowFrames: [UUID: CGRect]
    /// Folder frames recorded in `.global` coordinate space.
    let folderFrames: [UUID: CGRect]
    /// The receiving view's origin in `.global`. `DropInfo.location` is
    /// local to that view; add this origin to translate to global.
    let receiverGlobalOrigin: CGPoint
    @Binding var dropTargetProjectID: UUID?
    @Binding var dropTargetFolderID: UUID?
    let onDropOnProject: (UUID, [NSItemProvider]) -> Void
    let onDropOnFreeSpace: ([NSItemProvider]) -> Void
    let onMoveProjectToFolder: (UUID, UUID?) -> Void

    /// Translate `DropInfo.location` (local to the .onDrop view) into the
    /// `.global` coord space the row/folder frames are recorded in.
    private func globalPoint(_ local: CGPoint) -> CGPoint {
        CGPoint(
            x: local.x + receiverGlobalOrigin.x,
            y: local.y + receiverGlobalOrigin.y
        )
    }

    /// Find which project row (if any) contains the given global point.
    private func projectAt(_ globalLocation: CGPoint) -> UUID? {
        for (id, frame) in rowFrames where frame.contains(globalLocation) {
            return id
        }
        return nil
    }

    /// Find which folder (if any) contains the given global point.
    private func folderAt(_ globalLocation: CGPoint) -> UUID? {
        for (id, frame) in folderFrames where frame.contains(globalLocation) {
            return id
        }
        return nil
    }

    /// Whether this drag is an internal project move (vs Finder file drop).
    private func isInternalDrag(_ info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.utf8PlainText]) && !info.hasItemsConforming(to: [.fileURL])
    }

    func validateDrop(info: DropInfo) -> Bool {
        info.hasItemsConforming(to: [.fileURL]) || info.hasItemsConforming(to: [.utf8PlainText])
    }

    func dropUpdated(info: DropInfo) -> DropProposal? {
        let p = globalPoint(info.location)
        if isInternalDrag(info) {
            // Internal project drag — highlight folders only.
            dropTargetProjectID = nil
            dropTargetFolderID = folderAt(p)
            return DropProposal(operation: .move)
        } else {
            // External Finder drop — highlight project rows only.
            dropTargetFolderID = nil
            dropTargetProjectID = projectAt(p)
            return DropProposal(operation: .copy)
        }
    }

    func dropExited(info: DropInfo) {
        dropTargetProjectID = nil
        dropTargetFolderID = nil
    }

    func performDrop(info: DropInfo) -> Bool {
        let p = globalPoint(info.location)
        let targetFolder = folderAt(p)
        let targetProject = projectAt(p)
        dropTargetProjectID = nil
        dropTargetFolderID = nil

        if isInternalDrag(info) {
            // Internal project move — extract UUID from plain text.
            let providers = info.itemProviders(for: [.utf8PlainText])
            guard let provider = providers.first else { return false }
            provider.loadItem(forTypeIdentifier: "public.utf8-plain-text") { data, _ in
                guard let data = data as? Data,
                      let uuidString = String(data: data, encoding: .utf8),
                      let projectId = UUID(uuidString: uuidString) else { return }
                Task { @MainActor in
                    // Drop on folder → move into it. Drop on free space → move to root.
                    onMoveProjectToFolder(projectId, targetFolder)
                }
            }
            return true
        } else {
            // External Finder drop.
            let providers = info.itemProviders(for: [.fileURL])
            if let targetProject {
                onDropOnProject(targetProject, providers)
            } else {
                onDropOnFreeSpace(providers)
            }
            return true
        }
    }
}
