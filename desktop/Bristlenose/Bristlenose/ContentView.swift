import SwiftUI
import UniformTypeIdentifiers
import os

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

/// State for the disk-space precheck alert thrown by `CopyMachinery`.
struct CopyDiskSpaceAlertState: Identifiable {
    let id = UUID()
    let needed: Int64
    let available: Int64
}

/// Sheet + alert presentation for the drag-onto-project copy flow.
/// Extracted into a ViewModifier so the ContentView body stays inside the
/// Swift type-checker's expression-complexity budget.
private struct CopyDropPresentation: ViewModifier {
    @Binding var newFilesSheet: NewFilesSheetState?
    @Binding var copyDiskSpaceAlert: CopyDiskSpaceAlertState?
    let i18n: I18n
    let diskSpaceMessage: (CopyDiskSpaceAlertState) -> String

    func body(content: Content) -> some View {
        content
            .sheet(item: $newFilesSheet) { state in
                NewFilesSheet(state: state, onDismiss: { newFilesSheet = nil })
                    .environmentObject(i18n)
            }
            .alert(
                i18n.t("desktop.chrome.copyDiskSpaceTitle"),
                isPresented: Binding(
                    get: { copyDiskSpaceAlert != nil },
                    set: { if !$0 { copyDiskSpaceAlert = nil } }
                ),
                presenting: copyDiskSpaceAlert
            ) { _ in
                Button(i18n.t("common.buttons.close"), role: .cancel) {}
            } message: { alert in
                Text(diskSpaceMessage(alert))
            }
    }
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

/// Two-column NavigationSplitView: project list sidebar + WKWebView detail.
///
/// Selecting a project starts `bristlenose serve` and loads the React SPA
/// in embedded mode. The WKWebView is recreated on project switch (via .id)
/// to get a fresh ephemeral data store per project.
///
/// The toolbar provides:
/// - Leading: back/forward buttons (Cmd+[/Cmd+]) + project title (explicit ToolbarItem)
/// - Trailing: Export menu + per-tab actions; Ollama status pill (.status)
/// The five tab lenses moved OUT of the toolbar into the sidebar LensRail
/// (Cmd+1-5 still switch tabs) — see design-desktop-nav-toolbar-rearrangement.md.
struct ContentView: View {

    @EnvironmentObject var serveManager: ServeManager
    @EnvironmentObject var bridgeHandler: BridgeHandler
    @EnvironmentObject var projectIndex: ProjectIndex
    @EnvironmentObject var pipelineRunner: PipelineRunner
    @EnvironmentObject var toast: ToastStore
    @EnvironmentObject var removalStore: UndoableRemovalStore
    @EnvironmentObject var copyMachinery: CopyMachinery
    @EnvironmentObject var ollamaDownload: OllamaDownloadModel
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

    /// The project currently showing the diagnostic popover (anchored to its
    /// failure glyph), or nil. Owned here so both the glyph click and the
    /// context-menu "Show Diagnostics…" backstop open the same popover.
    @State private var diagnosticProjectID: UUID?

    /// The project row currently targeted by a drag hover, or nil.
    /// Bound to per-row `.dropDestination(isTargeted:)` closures; drives the
    /// hover-highlight visual on `ProjectRow`.
    @State private var dropTargetProjectID: UUID?

    /// The folder row currently targeted by a drag hover, or nil.
    /// Bound to per-folder `.dropDestination(isTargeted:)` closures; drives
    /// the accent-stroke overlay on the folder row.
    @State private var dropTargetFolderID: UUID?

    /// Whether a Finder drag is hovering the empty-project content pane ("Drag
    /// interviews here"). Drives the accent-ring drop affordance on that pane.
    @State private var emptyProjectDropTargeted = false

    /// Alert state for duplicate folder drop warning.

    /// "Added N files to X" sheet shown after a copy completes (Plan §11).
    /// nil = sheet hidden. Stub for #14; will gain richer affordances.
    @State private var newFilesSheet: NewFilesSheetState?

    /// Disk-space precheck alert state. Populated when the copy machinery
    /// throws `.insufficientDiskSpace`. Carries needed/available byte counts
    /// for a localised message.
    @State private var copyDiskSpaceAlert: CopyDiskSpaceAlertState?

    /// Spotlight one-shot confirm sheet — populated when the Locate flow
    /// found a unique high-confidence match. Resolves the awaiting continuation.
    @State private var spotlightConfirm: SpotlightConfirmState?

    /// Validation-error alert after the user picked a folder without
    /// `bristlenose-output/` inside.
    @State private var locateError: LocateErrorState?

    /// Handle to the in-flight project-switch Task. Switching is async (serve
    /// sidecar teardown + respawn); a background pipeline run makes rapid
    /// switching routine, so we cancel the prior switch before starting the
    /// next — only one switch is ever in flight. `switchProject` itself honours
    /// the cancellation (guards before `start()`), so a superseded switch bails
    /// rather than clobbering the winner's sidecar.
    @State private var switchTask: Task<Void, Never>?
    /// In-flight retry task that reloads the detail WebView after a run finishes
    /// — see scheduleReportReloadIfNeeded.
    @State private var reportReloadTask: Task<Void, Never>?

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

    /// Native window subtitle (drives `NSWindow.subtitle`): "<N> Sessions ·
    /// <total time>", e.g. "16 Sessions · 18h 23m". Session count + summed
    /// session duration, both from the project's analysis DB — the same figures
    /// the Project dashboard shows. Empty when no project is selected or the DB
    /// isn't readable yet (pre-analysis); an empty subtitle renders as none, the
    /// title centring on its own. Recomputes reactively when the watcher
    /// republishes `unanalysed` after a run.
    private var navigationSubtitle: String {
        guard let project = selectedProject,
              let state = projectIndex.unanalysed[project.id],
              let count = state.sessionCount, count > 0
        else { return "" }
        let sessions = sessionCountPhrase(count)
        guard let seconds = state.totalDurationSeconds, seconds > 0 else { return sessions }
        return "\(sessions) · \(DurationFormat.human(seconds: seconds))"
    }

    /// Localised "<N> Sessions" using the active locale's CLDR plural form,
    /// mirroring `ProjectRow.deltaText` (one/few/many/other + `_other` fallback
    /// for single-form locales like ja/ko).
    private func sessionCountPhrase(_ count: Int) -> String {
        let base = "desktop.chrome.titleSessions"
        let key = "\(base)_\(i18n.pluralCategory(count))"
        let rendered = i18n.t(key, ["count": String(count)])
        if rendered == key {
            return i18n.t("\(base)_other", ["count": String(count)])
        }
        return rendered
    }

    private static let focusLog = Logger(subsystem: "app.bristlenose", category: "focus")

    /// View ▸ Move Focus to Projects (⌘0) — the §10.1 keyboard no-trap return.
    /// A keyboard user inside the web report is never trapped: this always moves
    /// first responder back to native chrome. Logs via `os.Logger` and falls back
    /// to the window content view when the sidebar table can't be found (e.g. the
    /// sidebar is collapsed) so a no-op is observable, not silent (review F1).
    private func focusProjectsList() {
        guard let window = NSApp.keyWindow else {
            Self.focusLog.warning("focusProjects: no key window")
            return
        }
        guard let tableView = Self.firstSidebarTableView(in: window) else {
            Self.focusLog.warning("focusProjects: no sidebar table view (collapsed?) — focusing content view")
            window.makeFirstResponder(window.contentView)
            return
        }
        let ok = window.makeFirstResponder(tableView)
        Self.focusLog.info("focusProjects: makeFirstResponder=\(ok)")
    }

    /// Finds the first NSTableView in the window — the project list. (The detail
    /// pane is a WKWebView with no NSTableViews.) Mirrors the locator in
    /// `SidebarDeselectMonitor`; duplicated rather than shared to avoid touching
    /// the fragile sidebar monitor (§2.2). Revisit when the project List becomes
    /// an NSOutlineView (review F20).
    private static func firstSidebarTableView(in window: NSWindow) -> NSTableView? {
        func find(in view: NSView) -> NSTableView? {
            if let tv = view as? NSTableView { return tv }
            return view.subviews.lazy.compactMap { find(in: $0) }.first
        }
        return window.contentView.flatMap { find(in: $0) }
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
                    toolbarTrailing
                }
                // Native window title + subtitle (Mail/Notes pattern): title =
                // the project (scope), subtitle = session count · total time.
                // `.navigationTitle` on the detail column drives NSWindow.title;
                // `.navigationSubtitle` drives NSWindow.subtitle. The old custom
                // `.navigation` ToolbarItem + `WindowTitleManager` workaround is
                // gone — the duplicate title item it dodged no longer exists,
                // and forcing `titleVisibility = .hidden` was what suppressed
                // the native subtitle.
                .navigationTitle(selectedProject?.name ?? "Bristlenose")
                .navigationSubtitle(navigationSubtitle)
        }
        .background(SidebarDeselectMonitor { selection = [] })
        .overlay(alignment: .bottomTrailing) {
            // Compact build-info diagnostic — Debug only by default; Release
            // exposure gated on a custom build flag so internal/ad-hoc archives
            // can opt in. Never shipped to TestFlight / App Store users.
            // See BuildInfo.swift for the rationale and target format.
            #if DEBUG || BRISTLENOSE_SHOW_DIAGNOSTIC_OVERLAY
            // Frosted capsule so the diagnostic reads on any background —
            // including the bright empty/welcome state, where first-run QA
            // happens and branch-verification from a screenshot matters most.
            // .thinMaterial + .secondary stay on the system grid (adapts to
            // light/dark automatically); no off-grid colours or opacities.
            Text(BuildInfo.current.oneLine(sidecar: serveManager.mode?.shortSummary ?? "?"))
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(.thinMaterial, in: Capsule())
                .padding(8)
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
        .onChange(of: selection) { _, newSelection in
            // Switching the viewed project never cancels a background run — the
            // pipeline runs as an independent subprocess. (The cancel-on-switch
            // confirm modal was removed in A1; serialization of the async serve
            // switch lives in applySelectionChange via `switchTask`.)
            applySelectionChange(newSelection)
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
        // Keep Project ▸ Stop Analysis (⌘.) enablement current as runs
        // start/stop for the selected project (selection-time sync lives in
        // applySelectionChange; `state` is low-frequency, unlike liveData).
        .onChange(of: pipelineRunner.state) { old, new in
            updateSelectedProjectRunState()
            scheduleReportReloadOnCompletion(old: old, new: new)
            // A finished run's session count is written by the serve importer,
            // which lands ~1s+ after the pipeline-exit signal that fires here
            // (and lives under bristlenose-output/, outside the folder watcher's
            // source-file scope). Ride out that import with a few spaced rescans
            // so the sidebar count refreshes in place — no relaunch needed.
            for id in CompletionRescan.projectsLeavingAnalysis(old: old, new: new) {
                scheduleCountRescan(projectID: id)
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
        #if DEBUG
        // Debug-only: apply BRISTLENOSE_DEBUG_DIAGNOSTIC_FIXTURE only to
        // the currently-selected project, so the other sidebar rows keep
        // their real state for comparison. 500ms delay lets the per-project
        // scan run applyScanResult first; the override survives because
        // applyScanResult early-returns on the diagnostic states.
        //
        // The 500ms is a **heuristic, not a contract** — it's empirically
        // long enough for the initial manifest scan to settle on this Mac
        // under normal load. `_applyDebugFixture` is idempotent per-project
        // (guards via `_debugFixtureApplied: Set<UUID>`), so a late scan
        // racing past it is benign. If a slower machine ever needs a longer
        // wait, the right fix is making the override wait on the scan's
        // completion signal rather than tuning this number.
        .task(id: selectedProjectID) {
            guard let id = selectedProjectID else { return }
            try? await Task.sleep(for: .milliseconds(500))
            pipelineRunner._applyDebugFixture(to: id)
        }
        // Debug-only: if BRISTLENOSE_DEBUG_OLLAMA_PHASE is set, open the
        // local-model pill in that state at launch (no consent dance) so the
        // popover/pill UX can be QA'd without a real daemon. No-op when unset.
        .task {
            ollamaDownload.debugBootstrapFromEnv()
        }
        #endif
        // Defensive cleanup — macOS sometimes fails to fire
        // `isTargeted=false` if the cursor drag-leaves the window
        // entirely (Apple bug, intermittent for years). When the
        // sidebar disappears (window close, scene teardown), clear
        // any stale drop-target highlight state so it doesn't
        // persist into the next appearance. (gruber-pass, fce69e4.)
        .onDisappear {
            dropTargetProjectID = nil
            dropTargetFolderID = nil
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
        // View > Move Focus to Projects (⌘0) — the §10.1 keyboard no-trap return.
        .onReceive(NotificationCenter.default.publisher(for: .focusProjects)) { _ in
            focusProjectsList()
        }
        .modifier(ProjectNotificationReceivers(
            selection: $selection,
            renamingProjectID: $renamingProjectID,
            renamingFolderID: $renamingFolderID,
            projectIndex: projectIndex,
            onLocate: { project in locateProject(project) },
            onRemoveFromSidebar: { removeSelectedProjectsFromSidebar() },
            onStop: { project in pipelineRunner.cancel(project: project) }
        ))
        .sheet(isPresented: $showingAIConsent) {
            AIConsentView(
                isReviewMode: aiConsentReviewMode,
                onDismiss: { showingAIConsent = false }
            )
            .environmentObject(i18n)
            .environmentObject(ollamaDownload)
            .interactiveDismissDisabled(!aiConsentReviewMode)
        }
        .modifier(CopyDropPresentation(
            newFilesSheet: $newFilesSheet,
            copyDiskSpaceAlert: $copyDiskSpaceAlert,
            i18n: i18n,
            diskSpaceMessage: diskSpaceMessage(for:)
        ))
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
            Button(i18n.t("common.buttons.cancel"), role: .cancel) {}
        } message: { _ in
            // One honest message — the prior split (noOutputFolder /
            // wrongFolder) leaned on a heuristic that misclassified
            // researchers who keep recordings in subdirs. William's pick.
            Text(i18n.t("desktop.chrome.locateError.message"))
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

    /// Resolve a sidebar selection — wires bridge state and orchestrates the
    /// serve sidecar lifecycle via `switchProject`. Called directly from
    /// `.onChange(of: selection)`. Switching the viewed project never blocks on
    /// or cancels a background pipeline run — the run is an independent
    /// subprocess (the cancel-on-switch confirm modal was removed in A1).
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
                bridgeHandler.selectedProjectIsRunning =
                    isRunningOrQueued(pipelineRunner.state[id])
                projectIndex.updateLastOpened(id: id)
                // Gate serve on consent + availability — no data leaves the machine
                // before the user has seen the AI data disclosure (Apple 5.1.2(i)).
                if hasConsent && !project.path.isEmpty && project.isAvailable {
                    let path = project.path
                    // Serialize switches: cancel any in-flight switch before
                    // starting the next, so only one is ever live. switchProject
                    // honours the cancellation (bails before start()), so a
                    // superseded switch can't clobber the winner's sidecar.
                    switchTask?.cancel()
                    switchTask = Task { @MainActor in
                        await serveManager.switchProject(to: path)
                    }
                } else {
                    // Not serving this project (empty path, unavailable, or
                    // consent not yet granted) — stop the prior sidecar so it
                    // doesn't linger. Symmetric with the .folder / default arms;
                    // the detail pane shows the onboarding / Locate state, not the
                    // old project's report. Safe in the no-consent case: serve is
                    // consent-gated (never running pre-consent), and granting
                    // consent (re)starts via the .onChange(of: consentVersion) →
                    // start() path, not this one.
                    switchTask?.cancel()
                    serveManager.stop()
                }
            }
        case .folder(let id):
            persistedProjectID = ""
            bridgeHandler.selectedProjectPath = ""
            bridgeHandler.selectedProjectRevealablePath = ""
            bridgeHandler.selectedProjectIsRunning = false
            bridgeHandler.selectedFolderName =
                projectIndex.folders.first { $0.id == id }?.name ?? ""
            switchTask?.cancel()
            serveManager.stop()
        default:
            // Multi-select or empty — stop serve, clear state.
            persistedProjectID = ""
            bridgeHandler.selectedProjectPath = ""
            bridgeHandler.selectedProjectRevealablePath = ""
            bridgeHandler.selectedProjectIsRunning = false
            bridgeHandler.selectedFolderName = ""
            switchTask?.cancel()
            serveManager.stop()
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

    /// Open the watcher-mode unanalysed-files sheet for a project. No-op if
    /// the watcher hasn't reported any deltas yet (shouldn't be reachable
    /// from the subtitle Button, but defended for safety).
    private func openUnanalysedSheet(for project: Project) {
        guard let state = projectIndex.unanalysed[project.id], state.hasDeltas
        else { return }
        newFilesSheet = NewFilesSheetState(
            projectID: project.id,
            projectName: project.name,
            newFiles: state.newFiles,
            missingFiles: state.missingFiles
        )
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
        // Don't leave a warm sidecar serving a project the user just removed.
        serveManager.dropParked(forPaths: Set(removable.map(\.path)))
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
        serveManager.dropParked(forPaths: Set(removable.map(\.path)))
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

    /// Shallow check: does any direct child of `folder` itself look like an
    /// analysed Bristlenose project? If yes, returns that child's basename.
    /// Used to reject drops of a folder that *contains* a project (per
    /// plan §11 drop-matrix row).
    private static func containedAnalysedProjectName(in folder: URL) -> String? {
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(
            at: folder,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles, .skipsSubdirectoryDescendants]
        ) else { return nil }
        for entry in entries where entry.hasDirectoryPath {
            if LocateFlow.folderLooksAnalysed(url: entry) {
                return entry.lastPathComponent
            }
        }
        return nil
    }

    /// Format the disk-space alert body using a ByteCountFormatter.
    /// Extracted from the alert closure to keep the body type-checker
    /// expression-size manageable.
    private func diskSpaceMessage(for alert: CopyDiskSpaceAlertState) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        let needed = formatter.string(fromByteCount: alert.needed)
        let available = formatter.string(fromByteCount: alert.available)
        return String(
            format: i18n.t("desktop.chrome.copyDiskSpaceMessage"),
            needed, available
        )
    }

    /// Whether a pipeline state means the project has analysis data the
    /// user should be able to view. `.ready` and `.partial` both qualify;
    /// everything else (idle/scanning/queued/running/failed/etc.) doesn't.
    /// Used by the detail-pane gating for file-subset projects — they
    /// can't *run* analysis but can *show* it if it exists.
    private static func pipelineHasViewableData(_ state: PipelineState?) -> Bool {
        switch state {
        case .ready, .partial, .completedPartial:
            // `.completedPartial` ran to terminus and wrote a (degraded) report;
            // file-subset projects must be able to view it. `.failedWithDiagnostic`
            // deliberately stays false — abandon path leaves no report on disk.
            return true
        default:
            return false
        }
    }

    /// Handle files/folders dropped from Finder onto the sidebar free space.
    /// - Folder: create project pointing to that directory (scan all files)
    /// - File(s): create project with inputFiles restricting to the dropped files
    /// De-duplicates by path — if a project already exists for that folder, selects it.
    /// `.dropDestination(for: URL.self)` hands us pre-resolved URLs — no
    /// NSItemProvider loading dance. Empty-sidebar drop → create/locate
    /// project; per-row drops route to `handleDropOnProject`.
    private func handleDrop(urls: [URL]) {
        let accepted = Self.filterAcceptedURLs(urls)
        processDroppedURLs(accepted)
    }

    /// Handle Finder content dropped onto a project-sidebar-folder row.
    /// Routes through the same `processDroppedURLs` machinery as the empty-
    /// sidebar path, with `intoFolder:` set so the new project lands inside
    /// the target folder. Auto-expands the folder so the user sees the row
    /// they just created (Q4=a in plan Decisions block).
    ///
    /// Vocabulary discipline (Gruber pass, 19 May 2026): in *code comments*
    /// distinguish "project-sidebar-folder" (the `Folder` model in our
    /// sidebar) from "Finder folder" (a directory on disk). User-facing
    /// strings still collapse to "folder" — sidebar context disambiguates.
    private func handleDropOnFolder(id folderID: UUID, urls: [URL]) {
        let accepted = Self.filterAcceptedURLs(urls)
        guard !accepted.isEmpty else { return }
        projectIndex.setFolderCollapsed(id: folderID, collapsed: false)
        processDroppedURLs(accepted, intoFolder: folderID)
    }

    /// Process collected URLs from a sidebar drop. `intoFolder` is non-nil
    /// for drops on a project-sidebar-folder row (see `handleDropOnFolder`);
    /// nil for empty-sidebar drops, which create at root.
    private func processDroppedURLs(_ urls: [URL], intoFolder folderID: UUID? = nil) {
        guard !urls.isEmpty else { return }

        let directories = urls.filter { $0.hasDirectoryPath }
        let files = urls.filter { !$0.hasDirectoryPath }

        // Single folder already in the index: route by whether it's actually
        // been analysed, not merely tracked. Drop means "analyse these
        // interviews unless I already did — then show me the analysis." A
        // tracked-but-unanalysed folder (run interrupted before output, or
        // added-and-never-run) must still honour drag-to-analyse; a tracked +
        // analysed folder is a navigation gesture ("show me this one"), so it
        // selects + flashes, never re-runs and never prompts. See
        // design-sidebar-drop-behaviour.md action table and DroppedFolderState.
        if directories.count == 1 && files.isEmpty {
            let folder = directories[0]
            let existing = projectIndex.findByPath(folder.path)
            switch DroppedFolderState.classify(
                isTracked: existing != nil,
                folderLooksAnalysed: LocateFlow.folderLooksAnalysed(url: folder)
            ) {
            case .untracked:
                break  // fall through to createProjectFromURLs
            case .trackedUnanalysed:
                if let existing {
                    selection = [.project(existing.id)]
                    // start() is safe if a run is already in flight (no
                    // double-spawn); if there's no media / no provider it
                    // fails with a reason in the detail pane ("say why not").
                    pipelineRunner.start(project: existing)
                }
                return
            case .trackedAnalysed:
                if let existing {
                    // Re-drop of an already-analysed project: navigate to it
                    // (selecting starts serve, which shows the existing
                    // report) with a 0.4s accent flash. No re-run, no modal —
                    // design-sidebar-drop-behaviour.md: "Select existing entry
                    // + 0.4s accent flash. No model change."
                    selection = [.project(existing.id)]
                    dropTargetProjectID = existing.id
                    Task { @MainActor in
                        try? await Task.sleep(nanoseconds: 400_000_000)
                        if dropTargetProjectID == existing.id {
                            dropTargetProjectID = nil
                        }
                    }
                }
                return
            }
        }

        createProjectFromURLs(directories: directories, files: files, intoFolder: folderID)
    }

    /// Create a project from classified URLs (after duplicate check passes).
    private func createProjectFromURLs(directories: [URL], files: [URL],
                                       intoFolder folderID: UUID? = nil) {
        // All drops create one project. The name comes from the first item.
        // - Single folder: path = folder, inputFiles = nil (scan whole directory)
        // - Multiple folders: path = first folder, inputFiles = all folder paths
        // - File(s): path = first file's parent, inputFiles = file paths
        // - Mix of files and folders: path = first item's dir, inputFiles = all paths
        if directories.count == 1 && files.isEmpty {
            // Single folder — classic mode, scan everything in it.
            let url = directories[0]
            let project = projectIndex.addProject(
                name: url.lastPathComponent, path: url.path, intoFolder: folderID
            )
            selection = [.project(project.id)]
            if LocateFlow.folderLooksAnalysed(url: url) {
                // Dropped folder already contains a Bristlenose project —
                // re-open it instead of starting a fresh analysis. Skip
                // inline rename mode: this is an adoption, not a creation,
                // and the folder name was the project name on the prior
                // run. The manifest scan resolves the actual state (.ready
                // / .partial / .stopped / .failed); the user resumes from
                // the row's affordances if the run was interrupted.
                //
                // Asymmetry note: `establishEmptyProject` and
                // `handleDropOnProject` reject analysed-folder drops —
                // they'd corrupt an existing project. The empty-sidebar
                // path adopts instead because there's no project to
                // pollute. Legitimate cases: clone across machines, prior
                // CLI run, removed-then-re-dropped.
                pipelineRunner.scan(project: project)
            } else {
                // Adopt the folder's own name — no inline rename. A researcher
                // who dropped a folder of interviews organised + named it
                // deliberately (often after hours of conducting and fishing
                // files out of Downloads), so it's already the name they want.
                // Contrast "+ New Project", which DOES open rename because its
                // placeholder name is never the intended one. Mirrors the
                // analysed-folder adoption path above (also rename-free).
                // Folder-drop is the explicit signal to analyse — auto-run.
                // Plan §Phase 3 point 2 (the ~90% happy path).
                pipelineRunner.start(project: project)
            }
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
                name: firstName, path: firstPath, inputFiles: allPaths,
                intoFolder: folderID
            )
            selection = [.project(project.id)]
            // Adopt the dropped item's name (folder, else first file) — no
            // inline rename on drag; see the single-folder branch above.
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
    private func handleDropOnProject(id: UUID, urls: [URL]) {
        let accepted = Self.filterAcceptedURLs(urls)
        guard let project = projectIndex.projects.first(where: { $0.id == id }) else {
            return
        }

        // Empty placeholder ("+ New Project" with no folder yet): the drop
        // establishes the project's location instead of copying files into a
        // nonexistent target. Same end-state as a drop on empty sidebar:
        // single folder → adopt path + auto-run; multi-item → file-subset.
        if project.path.isEmpty {
            establishEmptyProject(id: id, accepted: accepted)
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
        var selfDropDetected = false
        for url in accepted {
            let path = url.standardizedFileURL.path
            if url.hasDirectoryPath, path == projectPath {
                // Self-drop — plan §11 calls for a 0.4s accent flash
                // on the project's own row, then no-op. We re-set the
                // hover-highlight state (cleared by isTargeted=false
                // when the drop completed) and schedule a clear.
                selfDropDetected = true
                continue
            }
            if url.hasDirectoryPath, LocateFlow.folderLooksAnalysed(url: url) {
                // Plan §11 reject — non-modal toast. Alerts are for
                // decisions, not apologies. Toast itself is a webism
                // banked for a native replacement (Mac drop-cursor
                // decoration or sidebar HUD) on a later pass.
                let message = String(
                    format: i18n.t("desktop.chrome.dropProjectOntoProjectToast"),
                    url.lastPathComponent
                )
                toast.show(message)
                return
            }
            if url.hasDirectoryPath,
               let containedName = Self.containedAnalysedProjectName(in: url) {
                // Plan §11 reject — dropping a *parent* of a Bristlenose
                // project. Copying would haul that project's output into
                // the target alongside its source media, corrupting both.
                let message = String(
                    format: i18n.t("desktop.chrome.dropFolderContainsProject"),
                    containedName
                )
                toast.show(message)
                return
            }
            filteredURLs.append(url)
        }

        if selfDropDetected {
            dropTargetProjectID = id
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 400_000_000)
                if dropTargetProjectID == id { dropTargetProjectID = nil }
            }
        }

        let paths = filteredURLs.map { $0.path }
        guard !paths.isEmpty else { return }

        // State guards — fail-fast for states where copy doesn't make sense.
        // `.ready` is intentionally NOT an early return; we copy the files
        // into the project folder (so they live alongside the analysed
        // sources) but don't auto-run — re-analysis is post-TF.
        switch pipelineRunner.state[id] {
        case .running, .queued:
            toast.show(i18n.t("desktop.chrome.dropOntoRunningProject"))
            return
        case .failed:
            // Don't silently retry a known-broken pipeline (would burn
            // LLM spend repeating the same failure). User explicitly
            // re-runs from the toolbar pill's Retry button.
            toast.show(i18n.t("desktop.chrome.dropOntoFailedProject"))
            return
        case .unreachable:
            // Volume not mounted / folder gone — copying would fail with
            // a generic OS error. Surface the real cause.
            toast.show(i18n.t("desktop.chrome.dropOntoUnreachableProject"))
            return
        default:
            break
        }

        let alreadyAnalysed: Bool = {
            if case .ready = pipelineRunner.state[id] { return true }
            return false
        }()
        // Folder-shaped projects (inputFiles == nil) scan their folder at
        // run time, so the freshly-copied files become visible to the CLI
        // automatically. File-subset projects must register the new paths
        // via addFiles — but the CLI can't run them (no `--files` yet), so
        // those don't auto-run.
        let wasFolderShaped = (project.inputFiles == nil)
        selection = [.project(id)]

        // Copy is async (cross-volume runs off the main thread). The
        // toolbar pill self-shows while `copyMachinery.inFlight != nil`.
        Task {
            do {
                let copied = try await copyMachinery.copy(
                    urls: filteredURLs,
                    into: URL(fileURLWithPath: project.path),
                    projectID: id,
                    projectName: project.name,
                    acceptedExtensions: Self.acceptedExtensions
                )
                if !wasFolderShaped {
                    projectIndex.addFiles(to: id, files: copied.map(\.path))
                }
                newFilesSheet = NewFilesSheetState(
                    projectID: id,
                    projectName: project.name,
                    files: copied
                )
                // Seed the folder watcher with the copied filenames so the
                // count pill stays hidden — they're "known," not surprise
                // drops. Handoff §Watcher lifecycle / Stacking rule.
                projectIndex.seedKnownBasenames(
                    projectID: id,
                    basenames: Set(copied.map { $0.lastPathComponent })
                )
                if alreadyAnalysed {
                    // Files are now in the folder; analysis won't pick
                    // them up until re-analysis (#post-TF).
                    toast.show(i18n.t("desktop.chrome.dropOntoAnalysedProject"))
                    return
                }
                if wasFolderShaped {
                    pipelineRunner.start(project: project)
                }
            } catch is CancellationError {
                // Pill already showed "Cancelling…" and rolled back. No toast.
            } catch CopyMachinery.CopyError.insufficientDiskSpace(let needed, let available) {
                copyDiskSpaceAlert = CopyDiskSpaceAlertState(
                    needed: needed, available: available
                )
            } catch CopyMachinery.CopyError.noItemsAfterFiltering {
                // Should not happen — we filtered above. Silent.
            } catch CopyMachinery.CopyError.underlying(let msg) {
                toast.show(msg)
            } catch {
                toast.show(error.localizedDescription)
            }
        }
    }

    /// Handle a drop onto an empty placeholder project (path == ""). This
    /// is the "+ New Project then drag here" flow — the drop *establishes*
    /// the project's folder rather than copying files into a non-folder.
    /// Mirrors `createProjectFromURLs` semantics but updates the existing
    /// project in place (preserves ID, user-typed name, position).
    private func establishEmptyProject(id: UUID, accepted: [URL]) {
        // Same integrity guards as the populated-project path — reject
        // dropping another Bristlenose project or a folder that contains
        // one. Self-drop isn't possible here (project has no path).
        for url in accepted where url.hasDirectoryPath {
            if LocateFlow.folderLooksAnalysed(url: url) {
                let message = String(
                    format: i18n.t("desktop.chrome.dropProjectOntoProjectToast"),
                    url.lastPathComponent
                )
                toast.show(message)
                return
            }
            if let containedName = Self.containedAnalysedProjectName(in: url) {
                let message = String(
                    format: i18n.t("desktop.chrome.dropFolderContainsProject"),
                    containedName
                )
                toast.show(message)
                return
            }
        }

        let directories = accepted.filter { $0.hasDirectoryPath }
        let files = accepted.filter { !$0.hasDirectoryPath }
        guard !directories.isEmpty || !files.isEmpty else { return }

        if directories.count == 1 && files.isEmpty {
            // Single folder — adopt as project path; folder-shaped → auto-run.
            let folder = directories[0]
            projectIndex.relocateProject(id: id, newPath: folder.path)
            selection = [.project(id)]
            if let updated = projectIndex.projects.first(where: { $0.id == id }) {
                pipelineRunner.start(project: updated)
            }
        } else {
            // Multi-item or file(s) — file-subset shape; pick first parent
            // as the project path. No auto-run (CLI lacks `--files`).
            let firstPath: String
            if let firstDir = directories.first {
                firstPath = firstDir.path
            } else {
                firstPath = files[0].deletingLastPathComponent().path
            }
            let allPaths = directories.map { $0.path } + files.map { $0.path }
            projectIndex.relocateProject(id: id, newPath: firstPath)
            projectIndex.addFiles(to: id, files: allPaths)
            selection = [.project(id)]
        }
    }

    // MARK: - Toolbar

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
        // Project name / icon intentionally NOT in the toolbar. The chip
        // previously here sat where the system back affordance lives, which
        // is the wrong real estate for a per-project title indicator.
        // `WindowTitleManager` still sets the NSWindow title to the project
        // name so it shows in Mission Control / window-menu / Cmd+~ switcher.
        // A correct in-toolbar project surface will return via a separate
        // design pass — placeholder removed by user request.

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

        // Project name + subtitle render natively now — `.navigationTitle` /
        // `.navigationSubtitle` on the detail view (see `body`), NOT a custom
        // `.navigation` ToolbarItem. The old pill put the title "in a button",
        // off the Mac grain; the convention is window title = scope (project) +
        // subtitle = count ("16 Sessions · 18h 23m"). See desktop CLAUDE.md.
    }

    // MARK: - Toolbar trailing (contextual — menus dim, toolbars morph)

    /// Whether the detail pane is showing an actual report (vs an empty /
    /// unavailable / unsupported state). Mirrors `detail`'s report branch, so the
    /// report-only toolbar actions (Export, Search, the per-tab panel toggles) hide
    /// when there's nothing to act on — e.g. a new project with no interviews that
    /// has never run. (They used to show unconditionally — a Search field + Export
    /// button over a "Drag Interviews Here" empty state.)
    private var selectedProjectShowsReport: Bool {
        guard let project = selectedProject else { return false }
        if !project.isAvailable { return false }
        if project.path.isEmpty { return false }
        if project.inputFiles != nil
            && !Self.pipelineHasViewableData(pipelineRunner.state[project.id]) {
            return false
        }
        return true
    }

    @ToolbarContentBuilder
    private var toolbarTrailing: some ToolbarContent {
        // Report-only actions — hidden when the detail pane has no report to act
        // on (new / never-run / unavailable / unsupported-subset project), so a
        // never-run project no longer shows a Search field + Export button with
        // nothing behind them. Mirrors `detail`'s report branch.
        if selectedProjectShowsReport {
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

            // Search — rightmost in `.primaryAction`, always active. Declared last
            // so it sits at the trailing edge of the capsule (Notes / Mail / Finder
            // convention). The web layer routes per tab: Quotes → search bar,
            // Sessions → transcript search, Codebook → filter codes, Analysis →
            // filter signals.
            ToolbarItem(placement: .primaryAction) {
                Button { bridgeHandler.menuAction("find") } label: {
                    Label(i18n.t("desktop.toolbar.search"), systemImage: "magnifyingglass")
                }
                .help(i18n.t("desktop.toolbar.searchShortcut"))
            }
        }

        // App-wide ambient pills share `placement: .status` (macOS-only) so they
        // sit in their own zone, separate from the `.primaryAction` capsule
        // (Export + contextual toggles + Search) — otherwise macOS 26's unified
        // trailing-actions capsule absorbs them into the search-shaped chrome.
        //
        // Per-project activity lives on the project's sidebar row, not here —
        // status lives where its subject lives. Both pipeline progress (the
        // determinate ring + hover-× Stop, the failure glyph → diagnostic
        // popover) AND copy-in-flight (ring + hover-× Cancel, "Copying · N%")
        // are per-project, so they ride the row. The toolbar `.status` zone is
        // reserved for genuinely app-global concerns — currently just the Ollama
        // model-download pill. (Per-project vs app-global is the placement axis:
        // `docs/design-desktop-project-status.md` §4.)
        ToolbarItem(placement: .status) {
            OllamaDownloadPill(model: ollamaDownload)
        }
    }

    // MARK: - Sidebar

    @ViewBuilder
    private var sidebar: some View {
        if BristlenoseFlags.appKitSidebar {
            // Native AppKit NSOutlineView source-list sidebar (flag-gated, in
            // progress). Selection state stays in SwiftUI so the existing serve
            // wiring is reused. design-desktop-sidebar-appkit.md.
            ProjectSidebarOutline(
                projectIndex: projectIndex,
                i18n: i18n,
                selection: $selection,
                lenses: LensItem.all,
                activeTab: bridgeHandler.activeTab,
                lensesEnabled: selectedProjectShowsReport,
                onActivateLens: { bridgeHandler.switchToTab($0) },
                onExternalDrop: { target, urls in
                    // Route to the same substrate-independent handlers the SwiftUI
                    // sidebar's `.dropDestination` closures use — drop policy lives
                    // there, not in the AppKit view.
                    switch target {
                    case .root:               handleDrop(urls: urls)
                    case .folder(let id):     handleDropOnFolder(id: id, urls: urls)
                    case .project(let id):    handleDropOnProject(id: id, urls: urls)
                    }
                },
                onLocate: { id in
                    if let p = projectIndex.projects.first(where: { $0.id == id }) { locateProject(p) }
                },
                onShowInFinder: { id in
                    if let p = projectIndex.projects.first(where: { $0.id == id }) { revealInFinder(p) }
                },
                canShowInFinder: { id in
                    projectIndex.projects.first(where: { $0.id == id }).map(canRevealInFinder) ?? false
                },
                onRemoveProject: { id in removeFromSidebarContextMenu(targetingProject: id) },
                onRemoveFolder: { id in deleteFromContextMenu(targetingFolder: id) },
                pipelineRunner: pipelineRunner,
                liveData: pipelineRunner.liveData,
                copyMachinery: copyMachinery
            )
            .navigationTitle(i18n.t("desktop.chrome.projects"))
        } else {
            swiftUISidebar
        }
    }

    private var swiftUISidebar: some View {
        VStack(spacing: 0) {
        // Lens rail — relocates the former toolbar tab Picker into the top of the
        // sidebar (spec §2, §3.1). Dimmed until a project is ready, exactly as the
        // Picker's `.disabled(...)` was. All List modifiers below stay ON the List,
        // unchanged — only this wrap is new (review F3; the project List is reused
        // verbatim per §2.2).
        LensRail(
            bridgeHandler: bridgeHandler,
            i18n: i18n,
            isEnabled: selectedProject != nil && bridgeHandler.isReady
        )
        .padding(.horizontal, 8)
        .padding(.top, 6)
        .padding(.bottom, 2)

        List(selection: $selection) {
            // "+ New Project" lives outside the Section. Per desktop/CLAUDE.md:
            // `Section + Button + ForEach.onMove + conditional Text` drops
            // Section content when `projects.isEmpty == true` on macOS 26.
            // Section here contains only the ForEach.
            Button {
                createNewProject()
            } label: {
                Label(i18n.t("desktop.menu.file.newProject"), systemImage: "plus")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)

            Section {
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
            } header: {
                Text(i18n.t("desktop.chrome.projects"))
            }

            // Empty-state hint lives OUTSIDE the Section. Inside the Section,
            // its conditional presence destabilised the ForEach.onMove
            // identity contract — Section content (header, button, folder
            // rows) silently dropped from the rendered List. Tightened to
            // `projects.isEmpty && folders.isEmpty`: folders-only is an
            // intentional setup state (user has filing-cabinet-laid-out
            // their projects but not yet dropped interviews), not empty.
            if projectIndex.projects.isEmpty && projectIndex.folders.isEmpty {
                Text(i18n.t("desktop.chrome.emptyStateHint"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.top, 20)
                    .listRowSeparator(.hidden)
            }
        }
        .accessibilityLabel(i18n.t("desktop.chrome.projects"))
        // Empty-space Finder drops (drops not consumed by a project row or
        // folder row) create a new project. Per-row .dropDestination
        // takes precedence — SwiftUI delivers the drop to the innermost
        // valid target, so this only fires when no row was hit.
        .dropDestination(for: URL.self) { urls, _ in
            handleDrop(urls: urls)
            return true
        }
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
            // Single `.dropDestination(for: SidebarDrop.self)` handles both
            // internal project drags (String payload) and Finder URL drops.
            // Stacking two `.dropDestination` modifiers is unsupported and
            // silently breaks on List rows / DisclosureGroup hosts
            // (FB12980427) — see `SidebarDrop.swift` for the rationale.
            // Attached to FolderRow (the drawn content), not the
            // DisclosureGroup container, per Apple's recommendation.
            .dropDestination(for: SidebarDrop.self) { items, _ in
                var finderURLs: [URL] = []
                for item in items {
                    switch item {
                    case .project(let id):
                        projectIndex.moveProject(projectId: id, toFolder: folder.id)
                    case .url(let url):
                        finderURLs.append(url)
                    }
                }
                if !finderURLs.isEmpty {
                    handleDropOnFolder(id: folder.id, urls: finderURLs)
                }
                return true
            } isTargeted: { isOver in
                if isOver {
                    dropTargetFolderID = folder.id
                } else if dropTargetFolderID == folder.id {
                    dropTargetFolderID = nil
                }
            }
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
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(Color.accentColor, lineWidth: 2)
                .opacity(dropTargetFolderID == folder.id ? 1 : 0)
        )
    }

    /// True when a run is active (or queued) for this project — gates the
    /// context-menu Stop item.
    private func isRunningOrQueued(_ s: PipelineState?) -> Bool {
        switch s {
        case .running, .queued: return true
        default: return false
        }
    }

    /// True for states whose report is on disk + (re-)imported by serve.
    private func isReportReady(_ s: PipelineState?) -> Bool {
        switch s {
        case .ready, .completedPartial: return true
        default: return false
        }
    }

    /// A project actively mid-analysis. Used to distinguish a real run
    /// completion (analysing → ready) from the launch-time disk read of an
    /// already-finished project (nil → ready), which must not trigger a reload.
    private func isAnalysing(_ s: PipelineState?) -> Bool {
        switch s {
        case .scanning, .running: return true
        default: return false
        }
    }

    /// Reload the report after a run finishes. The serve re-imports the finished
    /// report on the run_completed terminus within ~1s (verified in
    /// bristlenose.log) and `last_run` is set — but the detail WebView, loaded
    /// earlier on the empty status page, never reloads itself, so the report only
    /// appears after a manual project switch (which recreates the WebView).
    ///
    /// Fire on the selected project's transition from analysing INTO a
    /// report-ready state — the one moment an in-place WebView (no switch, so not
    /// recreated) is left on stale content. (Gating on the analysing origin, not
    /// just `!ready → ready`, keeps the launch-time disk read of an
    /// already-finished project from triggering a spurious reload.) Then
    /// `reloadFromOrigin` it directly: a real WKWebView
    /// reload that bypasses the cache and doesn't depend on SwiftUI recreating
    /// the view. The earlier `.id`-token approach was silently defeated by
    /// updateNSView's same-URL guard (the serve URL never changes).
    ///
    /// `isReady` can't gate this: the status page never posts `ready`, and
    /// didFinish force-sets isReady true 2s after any load — so it stays true on
    /// stale content. Instead retry only until one real reload lands (webView
    /// present + serve running), riding out the ~1s re-import and the brief
    /// webView-nil window during a concurrent switch. One reloadFromOrigin is
    /// then enough; the loop self-limits (it returns on the first reload).
    private static let reloadLog = Logger(
        subsystem: "app.bristlenose", category: "report-reload"
    )

    private func scheduleReportReloadOnCompletion(
        old: [UUID: PipelineState], new: [UUID: PipelineState]
    ) {
        guard let id = selectedProjectID,
              isAnalysing(old[id]), isReportReady(new[id]) else { return }
        Self.reloadLog.info("completion id=\(id.uuidString, privacy: .public)")
        reportReloadTask?.cancel()
        reportReloadTask = Task { @MainActor in
            // Ride out the serve's ~1s re-import and any brief serve-restart or
            // webView-nil window. Wait through a not-yet-running serve rather
            // than bailing; abandon only if the user navigates away or the
            // project stops being report-ready. One real reload is enough.
            for attempt in 0..<6 {
                try? await Task.sleep(for: .seconds(1.5))
                guard selectedProjectID == id,
                      isReportReady(pipelineRunner.state[id]) else {
                    Self.reloadLog.info("reload abandon attempt=\(attempt)")
                    return
                }
                guard case .running = serveManager.state else {
                    Self.reloadLog.info("reload wait attempt=\(attempt)")
                    continue
                }
                let didReload = bridgeHandler.reloadWebView()
                Self.reloadLog.info("reload attempt=\(attempt) didReload=\(didReload)")
                if didReload { return }
            }
            Self.reloadLog.info("reload gave up")
        }
    }

    /// Refresh a project's sidebar session count after its run finishes.
    ///
    /// The count (sessions in `bristlenose.db`) is written by the serve
    /// sidecar's importer, which polls the events log (~1s) then imports and
    /// checkpoints the WAL — so it lands ~1s+ AFTER the pipeline-exit signal
    /// that set this project `.ready` and drove the caller here. A single
    /// rescan fired now would read the pre-import count. So ride out the import
    /// with a few spaced rescans, exactly as `scheduleReportReloadOnCompletion`
    /// rides out the same re-import for the report WebView. `performScanLocked`'s
    /// `lastPublished` dedup makes the redundant scans free once the count
    /// settles — so, unlike the report reload, these need no cancellation: a
    /// late or duplicate rescan is a harmless idempotent no-op, never a
    /// stale-content write.
    private func scheduleCountRescan(projectID id: UUID) {
        Task { @MainActor in
            for _ in 0..<5 {
                try? await Task.sleep(for: .seconds(1.5))
                projectIndex.rescan(projectID: id)
            }
        }
    }

    /// Mirror the sole-selected project's run state into the bridge so the
    /// Project ▸ Stop Analysis (⌘.) menu item dims when there's nothing to
    /// stop. Called on pipeline-state change; selection-time sync is inline in
    /// `applySelectionChange`.
    private func updateSelectedProjectRunState() {
        if case .project(let id) = (selection.count == 1 ? selection.first : nil) {
            bridgeHandler.selectedProjectIsRunning = isRunningOrQueued(pipelineRunner.state[id])
        } else {
            bridgeHandler.selectedProjectIsRunning = false
        }
    }

    /// True for failure-shaped states that have a diagnostic to show.
    private func isFailureState(_ s: PipelineState?) -> Bool {
        switch s {
        case .failed, .completedPartial, .failedWithDiagnostic: return true
        default: return false
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
            isDropTarget: dropTargetProjectID == project.id,
            liveData: pipelineRunner.liveData,
            unanalysed: projectIndex.unanalysed[project.id],
            // Computed inline (not captured once) so the row re-renders as the
            // byte fraction ticks. Matched to THIS project, both phases — the
            // row is copy's only progress + cancel surface now (the toolbar copy
            // pill was removed; per-project ops live on the row).
            copyState: copyMachinery.inFlight.flatMap { f -> CopyDisplay? in
                guard f.projectID == project.id else { return nil }
                switch f.phase {
                case .copying: return .copying(fraction: f.progress)
                case .cancelling: return .cancelling
                }
            },
            onCancelCopy: { copyMachinery.cancel() },
            onRename: { newName in
                projectIndex.renameProject(id: project.id, newName: newName)
            },
            onShowInFinder: { revealInFinder(project) },
            onDelete: {
                removeFromSidebarContextMenu(targetingProject: project.id)
            },
            onLocate: project.isAvailable ? nil : { locateProject(project) },
            onOpenUnanalysed: { openUnanalysedSheet(for: project) },
            onShowDiagnostics: {
                selection = [.project(project.id)]
                diagnosticProjectID = project.id
            },
            isShowingDiagnostics: Binding(
                get: { diagnosticProjectID == project.id },
                set: { diagnosticProjectID = $0 ? project.id : nil }
            )
        )
        // Finder file drops onto this project row — add files or surface
        // the reject-toast if the dropped folder is itself a project.
        // SwiftUI's per-row .dropDestination handles all hit-testing —
        // no GeometryReader frame capture, no coordinate-space gymnastics.
        // isTargeted drives the hover-highlight on the row.
        .dropDestination(for: URL.self) { urls, _ in
            handleDropOnProject(id: project.id, urls: urls)
            return true
        } isTargeted: { isOver in
            if isOver {
                dropTargetProjectID = project.id
            } else if dropTargetProjectID == project.id {
                dropTargetProjectID = nil
            }
        }
        .tag(SidebarSelection.project(project.id))
        .draggable(ProjectDragID(id: project.id))
        .contextMenu {
            // Run / copy lifecycle, most contextually-relevant first. Hidden
            // (not dimmed) when N/A — context-menu HIG.
            if isRunningOrQueued(pipelineRunner.state[project.id]) {
                Button(i18n.t("desktop.menu.project.stopAnalysis")) {
                    pipelineRunner.cancel(project: project)
                }
                Divider()
            }
            // Copy cancel — the keyboard/VoiceOver path for the row ring's
            // hover-× (which is mouse-only), mirroring Stop Analysis above.
            if let f = copyMachinery.inFlight, f.projectID == project.id, f.phase == .copying {
                Button(i18n.t("desktop.menu.project.cancelCopy")) {
                    copyMachinery.cancel()
                }
                Divider()
            }
            if isFailureState(pipelineRunner.state[project.id]) {
                Button(i18n.t("desktop.menu.project.showDiagnostics")) {
                    selection = [.project(project.id)]
                    diagnosticProjectID = project.id
                }
                Divider()
            }

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
            // Not `.destructive` — Remove from Sidebar is undoable (8s toast)
            // and leaves the on-disk folder untouched. The role would lie
            // about the action's blast radius if Apple ever paints it red.
            Button(i18n.t("desktop.menu.project.removeFromSidebar")) {
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
                // New project with no files yet — prompt user to add interviews,
                // and accept a Finder drop right here. Routes through the same
                // `handleDropOnProject` as the project's sidebar row (→
                // `establishEmptyProject` for the empty case), so the "Drag
                // interviews here" copy is a promise the pane can actually keep.
                ContentUnavailableView(
                    i18n.t("desktop.chrome.dragInterviews"),
                    systemImage: "square.and.arrow.down",
                    description: Text(i18n.t("desktop.chrome.dragInterviewsDescription"))
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .overlay {
                    if emptyProjectDropTargeted {
                        RoundedRectangle(cornerRadius: 10)
                            .strokeBorder(Color.accentColor, lineWidth: 2)
                            .padding(12)
                    }
                }
                .dropDestination(for: URL.self) { urls, _ in
                    handleDropOnProject(id: project.id, urls: urls)
                    return true
                } isTargeted: { emptyProjectDropTargeted = $0 }
            } else if project.inputFiles != nil
                        && !Self.pipelineHasViewableData(pipelineRunner.state[project.id]) {
                // File-subset project with no prior analysis — CLI can't
                // analyse this shape yet. Show files + Show-in-Finder;
                // pipeline never starts.
                //
                // BUT: if the project somehow already has analysis data
                // (state == .ready or .partial — e.g. analysed when it was
                // folder-shaped, then had files added afterwards), don't
                // gate viewing the report. Same principle as pipeline
                // failure trust-UX: the run state shouldn't block the
                // user from seeing what's already there.
                UnsupportedSubsetView(project: project)
            } else {
                ZStack {
                    switch serveManager.state {
                    case .idle, .starting:
                        BootView(phase: .startingSidecar)

                    case .running(let port):
                        // Key on project id AND serve port. A warm-pool re-point
                        // (Phase A2) keeps the same project id but hands off to a
                        // sidecar on a different port — keying on id alone would
                        // NOT re-mount, so updateNSView would reload the new port
                        // while reusing the previous sidecar's injected auth token
                        // → silent 401s / blank report. The port in the key forces
                        // a fresh makeNSView that re-injects the right token.
                        WebView(url: serveURLWithLocale, bridgeHandler: bridgeHandler, authToken: serveManager.authToken)
                            .id("\(project.id.uuidString)-\(port)")
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
    let onStop: (Project) -> Void

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
            .onReceive(NotificationCenter.default.publisher(for: .stopSelectedProject)) { _ in
                guard case .project(let id) = sole else { return }
                if let project = projectIndex.projects.first(where: { $0.id == id }) {
                    onStop(project)
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
            // Shortcut (Cmd+Shift+E) lives on the File > Export Report… item
            // in MenuCommands.swift — single source so re-binding only touches
            // one place. The toolbar Menu item invokes the same bridge action.
            Button(i18n.t("desktop.menu.file.exportReport")) {
                bridgeHandler.menuAction("exportReport")
            }

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
                Button(i18n.t("common.buttons.cancel"), role: .cancel) {
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

// SidebarDropDelegate removed 14 May 2026 — replaced with per-row
// `.dropDestination(for:action:isTargeted:)` modifiers on `ProjectRow`
// and `FolderRow`. SwiftUI handles hit-testing per-row natively; no
// GeometryReader frame capture, no coordinate-space translation, no
// drift between `.global` (bottom-left on macOS Cocoa) and named or
// local spaces (top-left in SwiftUI). The canonical Mac pattern.
//
// The original SidebarDropDelegate is preserved in git history at
// commits 2d3a019 (pre-branch) through 31c5eb2; future archaeology
// should start there if the per-row approach ever needs to be reverted.
