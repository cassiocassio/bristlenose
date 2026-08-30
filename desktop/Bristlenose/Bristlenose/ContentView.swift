import SwiftUI
import UniformTypeIdentifiers
import os

// MARK: - Sidebar empty-click deselection monitor

/// Clears the sidebar selection when the user clicks in the empty area below
/// all list rows. Uses NSEvent local monitor + NSTableView.row(at:) so it
/// doesn't conflict with List's selection gesture (no SwiftUI gesture needed).
/// The monitor is installed once and removed in deinit — no leak risk.
///
/// **Scoped to its own window.** `addLocalMonitorForEvents` is *app*-wide: every
/// window installs one, and every one of them sees every click anywhere in the
/// app. Each then called its **own** `deselect`, so one click in one window's
/// empty sidebar area deselected every open window — which showed up as going to
/// the welcome screen putting all six windows on Welcome at once (reported
/// 17 Aug 2026, the first multi-window run). Harmless while there was only ever
/// one window; total the moment there are two.
private struct SidebarDeselectMonitor: NSViewRepresentable {
    let deselect: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(deselect: deselect) }

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        // How the coordinator learns which window it belongs to. Read at click
        // time, not now: `view.window` is nil until SwiftUI inserts it.
        context.coordinator.host = view
        return view
    }

    func updateNSView(_ view: NSView, context: Context) {
        context.coordinator.deselect = deselect
        context.coordinator.host = view
    }

    final class Coordinator {
        var deselect: () -> Void
        /// The view this monitor was installed for — its window is the only one
        /// whose clicks count. Weak: the coordinator outlives nothing, but the
        /// view is owned by the view hierarchy.
        weak var host: NSView?
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
                  // Our window, or none of our business — see the type doc.
                  window === host?.window,
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
    /// Resolves the sheet's primary action, or `nil` when this project cannot
    /// run right now. Resolved per presentation rather than captured once, so
    /// the answer reflects the pipeline state at the moment the sheet opens.
    let analyseAction: (NewFilesSheetState) -> (() -> Void)?

    func body(content: Content) -> some View {
        content
            .sheet(item: $newFilesSheet) { state in
                NewFilesSheet(
                    state: state,
                    onDismiss: { newFilesSheet = nil },
                    onAnalyse: analyseAction(state)
                )
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

    @Environment(\.openWindow) private var openWindow
    @EnvironmentObject var serveFleet: ServeFleet

    /// This window's serve, or nil when it shows no study.
    ///
    /// Optional by decision, not by accident: a window with no study genuinely
    /// has no serve, and every alternative is a hack — an idle manager keyed on
    /// the window id mixes the fleet's key space, and a shared null manager is a
    /// second source of state by another name. The type now enforces what a gate
    /// used to: **no window may read a serve it has no study for**, which is
    /// `design-workspace.md` constraint 5 expressed as a type.
    var serveManager: ServeManager? {
        selectedProject.map { serveFleet.manager(for: $0.id) }
    }
    /// **This window's** bridge to its web view — Stage 3a.
    ///
    /// Was one app-level `@StateObject` injected into every window, which meant
    /// `activeTab` and its ~28 siblings were global: two windows physically
    /// could not sit on different lenses, and the menu bar's labels described
    /// whichever window moved last. `@StateObject` here gives each window its
    /// own, and `.focusedSceneValue(\.bridge, …)` is how the menu bar finds the
    /// front one. Both windows still point at the *same* sidecar — this is the
    /// half of multi-window that needs no serve rework.
    @StateObject private var bridgeHandler = BridgeHandler()
    @EnvironmentObject var projectIndex: ProjectIndex
    @EnvironmentObject var pipelineRunner: PipelineRunner
    @EnvironmentObject var toast: ToastStore
    @EnvironmentObject var removalStore: UndoableRemovalStore
    @EnvironmentObject var copyMachinery: CopyMachinery
    /// Read only to hand to the sidebar, so a row can show a cloud batch after
    /// the import window is closed.
    @EnvironmentObject var cloudImport: CloudImportCoordinator
    @EnvironmentObject var ollamaDownload: OllamaDownloadModel
    @EnvironmentObject var outOfCredit: OutOfCreditModel
    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @AppStorage("showAnalysisAnimation") private var showAnalysisAnimation = true
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// Whether this window is the key one. `.key` while it is frontmost,
    /// `.active` when a sibling window is, `.inactive` when the app itself
    /// isn't — so this is per-window without any AppKit plumbing.
    @Environment(\.controlActiveState) private var controlActiveState
    @AppStorage("selectedProjectID") private var persistedProjectID: String = ""
    @AppStorage("aiConsentVersion") private var consentVersion: Int = 0
    /// Selection binding for the List — uses `SidebarSelection` enum so both
    /// projects and folders are selectable. UUID-based to survive field mutations.
    /// Set enables Cmd+click / Shift+click multi-select natively.
    /// This window's study, as its scene value.
    ///
    /// Stage 3b: `WindowGroup(for:)` carries it, so restoration gives each
    /// window **its own** study back rather than all of them the last-used one.
    ///
    /// A **binding**, because it is written as well as read: a window that
    /// switches study writes the new one back, or restoration would return it to
    /// whatever it was opened on. nil means "no particular study" — a plain
    /// ⌥⌘N, which deliberately passes no value so SwiftUI's per-value window
    /// dedup cannot swallow the command — and then `persistedProjectID` supplies
    /// the last-used study, which is what that global is now for.
    @Binding var seed: WindowSeed?

    @State private var selection: Set<SidebarSelection> = []
    /// Tracks whether the project list sidebar column is visible.
    /// Used to gate sidebar-specific toolbar items — if the user has hidden
    /// the project list, don't compensate by moving project controls to the toolbar.
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @State private var showingAIConsent = false
    @State private var aiConsentReviewMode = false
    @State private var showingMiroSheet = false
    @State private var showingFeedbackSheet = false

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
    /// The project awaiting a Re-analyse confirmation, with the measurements
    /// the sheet reads out. Nil when nothing is pending — and *never* set for a
    /// project with no curation, which runs straight away (see `askToReAnalyse`).
    @State private var reAnalyseConfirm: PendingReAnalyse?

    /// Spotlight one-shot confirm sheet — populated when the Locate flow
    /// found a unique high-confidence match. Resolves the awaiting continuation.
    @State private var spotlightConfirm: SpotlightConfirmState?

    /// Validation-error alert after the user picked a folder without
    /// `bristlenose-output/` inside.
    @State private var locateError: LocateErrorState?

    /// This window's identity, for the `WindowCommandSink` published as a scene
    /// focused value. Stable for the window's lifetime and the only thing the
    /// menu bar compares, since the sink's closure is rebuilt every body pass.
    @State private var windowID = UUID()


    /// Bumped by Project ▸ Rename …; consumed by this window's sidebar outline.
    /// See `ProjectSidebarOutline.renameRequest`.
    @State private var renameRequest = 0

    /// Bumped by View ▸ Switch Session (⌘⌥L on the Sessions lens); consumed by
    /// this window's `SessionsSwitcherButton`.
    @State private var sessionsSwitcherRequest = 0

    /// The roster, observed rather than merely called: a window's number can
    /// change after it was handed out — the last window left in a group gives
    /// its number up — so the title has to follow, not cache. See
    /// `WindowRoster.compact`.
    @ObservedObject private var windowRoster = WindowRoster.shared

    /// The project this window has already restored the remembered lens for.
    ///
    /// Load-bearing twice, which is why it isn't a bool. It stops the restore
    /// re-firing on the *next* `isReady` — a run-completion reload raises that
    /// flag again, and yanking the researcher back to a lens they had since
    /// navigated away from would be worse than not restoring at all. And it
    /// gates the *capture*: the SPA lands on the dashboard and reports it before
    /// the restore runs, so capturing unconditionally would overwrite the
    /// memory with `project` and then dutifully restore that.
    @State private var lensRestoredFor: UUID?

    /// Handle to the in-flight project-switch Task. Switching is async (serve
    /// sidecar teardown + respawn); a background pipeline run makes rapid
    /// switching routine, so we cancel the prior switch before starting the
    /// next — only one switch is ever in flight. `switchProject` itself honours
    /// the cancellation (guards before `start()`), so a superseded switch bails
    /// rather than clobbering the winner's sidecar.
    @State private var switchTask: Task<Void, Never>?

    /// A study this window wants served, deferred until the window is looked at.
    ///
    /// Carries the **project id as well as the path**. Holding a bare path let a
    /// stale defer fire against whatever study the window had moved on to:
    /// defer A → A removed → pick C → lose and regain key → C's manager started
    /// on A's folder. Window titled C, sidebar highlighting C, sidecar serving
    /// A — and `Send to Miro` would export A's quotes to a board named C.
    @State private var pendingStart: (id: UUID, path: String)?

    /// A live mirror of `isKeyWindow`, for reading inside an async Task.
    ///
    /// `controlActiveState` is an `@Environment` value resolved into the view
    /// *value*, so a Task started from `body` captures the state as it was a
    /// turn ago. A window that became key in between took the defer branch and
    /// nothing re-armed it — `.onChange(of: isKeyWindow)` had already fired —
    /// so it sat unstarted until the user clicked away and back. The converse
    /// bit the folder loop: each window is transiently key as it is created.
    @State private var windowIsKey = false
    /// In-flight retry task that reloads the detail WebView after a run finishes
    /// — see scheduleReportReloadIfNeeded.
    @State private var reportReloadTask: Task<Void, Never>?

    /// Is this the front window?
    private var isKeyWindow: Bool { controlActiveState == .key }

    /// The position to remember for the current lens.
    ///
    /// Two sources because the two lenses mean different things by "position":
    /// Quotes and Codebook report a heading id over the bridge as the reader
    /// scrolls, while Sessions' position is which transcript is open — a route,
    /// already tracked per window by `SessionsRouteMemory`. See `LensAnchor`.
    private var capturedAnchor: String? {
        guard let tab = bridgeHandler.activeTab else { return nil }
        if tab == .sessions { return bridgeHandler.restoreSessionID }
        // Only honour an anchor reported *for this lens*. The two messages are
        // independent, so a stale one can arrive either side of a lens switch.
        guard bridgeHandler.currentAnchorLens == tab.rawValue else { return nil }
        return bridgeHandler.currentAnchor
    }

    /// Put the window back where it was within the restored lens.
    private func restoreAnchor(_ anchor: String?, on tab: Tab) {
        switch LensAnchor.action(lens: tab, anchor: anchor) {
        case .scroll(let id):
            bridgeHandler.scrollToAnchor(id)
        case .session(let id):
            bridgeHandler.navigateToSession(id)
        case .top:
            break
        }
    }

    /// Which set of windows this one is a duplicate of, for titling — keyed on
    /// the **menu row**, not the lens. Nil on the welcome screen: an unselected
    /// window shows "Welcome", and two of those are not worth numbering.
    ///
    /// `countSubtitle` rather than `activeTab`, because Project, Sessions and a
    /// not-yet-reported lens all render the same session count — see
    /// `WindowRoster.Group`.
    private var windowGroup: WindowRoster.Group? {
        guard let id = windowProject?.id else { return nil }
        return WindowRoster.Group(projectID: id, subtitle: countSubtitle)
    }

    /// The project this window is *about* — the single source its whole chrome
    /// reads from.
    ///
    /// **A master picks it; a child inherits it.** The master's comes from its
    /// own `selection`. A child has no selection at all — "masters get projects,
    /// children get lenses" is meant literally — so its project is whatever the
    /// sidecar is currently serving.
    ///
    /// That asymmetry is the whole design. A child has no second source, so it
    /// has nothing to drift *from*, so it cannot name a study it isn't showing.
    /// The failure `design-workspace.md` constraint 5 describes becomes
    /// unrepresentable rather than guarded.
    ///
    /// The master still needs a guard, because between "clicked study B" and
    /// "sidecar for B is up" its title already says B while the pane shows A —
    /// see the mount site in `detail`.
    /// The project this window is about — its **own selection**, kept in step
    /// with the serve by the sync above.
    ///
    /// Deliberately not derived from the serve. Four detail panes exist for
    /// studies that are legitimately *not* served — a volume-ejected project, a
    /// brand-new one with no path yet, an unsupported subset, a never-analysed
    /// folder — and reading the serve here would render Welcome for all of them,
    /// so `File ▸ New Project` would show the welcome screen instead of its drop
    /// target. The **content** gates on the serve; the **window** does not.
    private var windowProject: Project? { selectedProject }

    /// The window's title: the project's name, or "Welcome" with none selected,
    /// plus an ordinal when a sibling window already shows the same lens of the
    /// same study (mockup E4 — nine identical Window-menu rows is the case that
    /// earned it).
    private var windowTitle: String {
        let base = windowProject?.name ?? i18n.t("desktop.welcome.windowTitle")
        return base + WindowRoster.suffix(for: windowRoster.assignments[windowID] ?? 1)
    }

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

    /// The resting body of the window subtitle — the per-lens count. An
    /// in-flight run outranks it (`WindowSubtitleModifier`), and a name clash
    /// prefixes it with the folder (`WindowSubtitle.folderDisambiguator`).
    ///
    /// Sessions/Project show the session count + total time from the local
    /// analysis DB — stable, and painted instantly before the report loads. The
    /// report-derived lenses (Quotes/Codebook/Analysis) carry *live* counts only
    /// the SPA can compute (Signals don't exist in the DB; visible-quote/tag
    /// counts shift as the researcher edits), so they arrive over the bridge as
    /// `lensSubtitle` — including the empty string the SPA now sends when a lens
    /// counts zero, so the title stops commenting on a filter that found
    /// nothing. Empty renders as no subtitle, the title centring on its own.
    /// Recomputes reactively: `activeTab`/`lensSubtitle` are `@Published`, as is
    /// `unanalysed`.
    private var countSubtitle: String {
        switch bridgeHandler.activeTab {
        case .quotes?, .codebook?, .analysis?:
            // Honour the bridged subtitle only when it's for the lens we're on,
            // so a tab switch never momentarily shows the previous lens's count.
            guard bridgeHandler.lensSubtitleTab == bridgeHandler.activeTab?.rawValue else {
                return ""
            }
            return bridgeHandler.lensSubtitle
        default:
            return sessionsSubtitle
        }
    }

    /// "16 Sessions · 18h 23m" — session count + summed duration from the
    /// project's analysis DB (the same figures the Project dashboard shows).
    /// Empty when no project is selected or the DB isn't readable yet
    /// (pre-analysis). Recomputes when the watcher republishes `unanalysed`.
    private var sessionsSubtitle: String {
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
        i18n.plural("desktop.chrome.titleSessions", count: count)
    }

    /// The selected project's folder, present only when another project shares
    /// its name — see `WindowSubtitle.folderDisambiguator` for why the trigger
    /// is the index rather than the open windows.
    private var subtitleFolder: String? {
        guard let project = selectedProject else { return nil }
        return WindowSubtitle.folderDisambiguator(
            for: project,
            projects: projectIndex.projects,
            folders: projectIndex.folders
        )
    }

    /// Whether the selected project's run is in flight. Read off
    /// `pipelineRunner.state`, which is low-frequency and which ContentView
    /// already observes; the per-second progress churn lives in `liveData` and
    /// is observed by `WindowSubtitleModifier` instead.
    private var isSelectedProjectRunning: Bool {
        guard let id = selectedProject?.id else { return false }
        if case .running = pipelineRunner.state[id] { return true }
        return false
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
        guard var components = serveManager?.serveURL.flatMap({
            URLComponents(url: $0, resolvingAgainstBaseURL: false)
        }) else { return serveManager?.serveURL }
        let locale = i18n.locale
        if locale != "en" {
            var items = components.queryItems ?? []
            items.append(URLQueryItem(name: "locale", value: locale))
            components.queryItems = items
        }
        return components.url ?? serveManager?.serveURL
    }

    /// SwiftUI's spelling of the appearance preference. `AppAppearance` already
    /// applies it app-wide via `NSApp.appearance`, so this is belt-and-braces —
    /// it states the window's appearance locally, which is also what the
    /// WKWebView inherits to drive the report's `prefers-color-scheme` CSS
    /// (see the note at `BridgeHandler.swift:234`).
    private var colorScheme: ColorScheme? {
        AppAppearance.colorScheme(for: appearance)
    }

    /// The NavigationSplitView plus structural modifiers and the first cluster
    /// of lifecycle / state-sync handlers. Split out of `body` so each modifier
    /// chain type-checks within the Swift compiler's per-expression budget — the
    /// merged chain tripped "unable to type-check this expression in reasonable
    /// time". Pure refactor; no behaviour change.
    private var splitViewCore: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
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
                .navigationTitle(windowTitle)
                // Subtitle composition lives in `WindowSubtitle.swift` — it has
                // to observe `liveData` itself to tick during a run, and its
                // precedence rules are testable decisions, not view code.
                .modifier(WindowSubtitleModifier(
                    liveData: pipelineRunner.liveData,
                    projectID: selectedProject?.id,
                    isRunning: isSelectedProjectRunning,
                    narratesRun: isKeyWindow,
                    folder: subtitleFolder,
                    countSubtitle: countSubtitle,
                    i18n: i18n
                ))
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
            Text(BuildInfo.current.oneLine(sidecar: serveManager?.mode?.shortSummary ?? "?"))
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
        // Report chrome follows *this* window's key state. Was two
        // `NSWindow.did{Become,Resign}Key` observers with a TODO on them: they
        // fire for any window in the app — Settings, the video pop-out — so a
        // second content window would have been told it went inactive whenever
        // its sibling came forward. `controlActiveState` is the per-window
        // answer SwiftUI already computes, and it correctly reports `.inactive`
        // for the whole app losing focus, which is the other half the
        // notifications covered.
        .onChange(of: isKeyWindow, initial: true) { _, isKey in
            bridgeHandler.setWindowActive(isKey)
            windowIsKey = isKey
            // The other half of lazy start: a window that deferred its serve
            // because nobody was looking at it starts now that they are.
            //
            // Also tells the fleet this is the fronted study — which restarts it
            // if a preference or the consent state changed while it was in the
            // background, the exception that makes the lazy env fan-out safe.
            guard isKey else { return }
            if let pending = pendingStart {
                pendingStart = nil
                // Only if the window still shows the study the defer was for.
                if pending.id == selectedProjectID {
                    serveFleet.manager(for: pending.id).start(projectPath: pending.path)
                }
            }
            if let id = selectedProjectID { serveFleet.front(id) }
        }
        .onReceive(NotificationCenter.default.publisher(for: .bristlenosePaletteChanged)) { _ in
            // Colour-palette picker changed — apply live to the report webview
            // (runtime data-color-theme swap, no serve restart).
            bridgeHandler.setColorPalette()
        }
        // Translucent chrome (spike): the toolbar-inset was static-at-ready;
        // full-screen entry/exit swaps the window styleMask (no titlebar in
        // full-screen), so the frame-minus-contentLayoutRect delta shrinks
        // and the SPA's cached padding-top overshoots — top of content ends
        // up half-tucked under the visible toolbar. Re-post on the transition
        // notifications; both fire AFTER Apple's animation completes so the
        // window frame is stable when we read it.
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didEnterFullScreenNotification)) { _ in
            bridgeHandler.syncToolbarInset()
        }
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didExitFullScreenNotification)) { _ in
            bridgeHandler.syncToolbarInset()
        }
        // Belt-and-braces: didResize fires many times during the full-screen
        // animation as the window frame interpolates, and once more when it
        // settles. If the fullscreen notifications don't wire the way we
        // expect, this covers it. Also covers manual resize (harmless — the
        // toolbar height doesn't change with drag-resize, so the recomputed
        // inset just re-posts the same value).
        .onReceive(NotificationCenter.default.publisher(for: NSWindow.didResizeNotification)) { _ in
            bridgeHandler.syncToolbarInset()
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
                    serveFleet.manager(for: project.id).start(projectPath: project.path)
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
            // Stamp the analysis baseline. Narrower than the rescan above — a
            // passive `.scanning` read must not open the F14 drift gate, since
            // no analysis happened. Write-only field; see
            // `ProjectIndex.recordPipelineRun`.
            for id in CompletionRescan.projectsFinishingRun(old: old, new: new) {
                projectIndex.recordPipelineRun(id: id)
            }
        }
        .onAppear {
            // This window's own study first; the last-used one only as a
            // fallback. Under Stage 3b the scene value is per window, so five
            // restored windows come back on five studies rather than five
            // copies of whichever was selected last.
            if selection.isEmpty {
                // **A window opens on a study only if its seed names one.**
                //
                // No fallback, deliberately — and this is the second attempt.
                // The first kept a "last-used study" fallback for a seed with no
                // project, which made ⌥⌘N from a **Welcome** window open a study:
                // observed 20 Aug, and wrong twice over. New Window's job is
                // *another view of what I'm looking at*, and what you are looking
                // at is Welcome; and the fallback conjured a sidecar on a study
                // the researcher had not chosen, which is the exact decision the
                // launch behaviour above exists to stop the app making.
                //
                // Restoration is unaffected: a restored window carries the seed
                // it wrote back. `@AppStorage("selectedProjectID")` keeps only
                // its non-window jobs; it stopped being *the* selection the
                // moment windows became independent.
                if let wanted = seed?.project,
                   projectIndex.projects.contains(where: { $0.id == wanted }) {
                    selection = [.project(wanted)]
                }
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
            // Give the ordinal back. Deliberately does NOT renumber the
            // survivors — see `WindowRoster.claim`.
            WindowRoster.shared.release(windowID: windowID)
            // This window's study may have just lost its last window. The sweep
            // decides — it is a function of the roster, so it is safe to call
            // more often than strictly needed and safe to miss once.
            serveFleet.sweep(shownProjects: WindowRoster.shared.shownProjects)
        }
    }

    var body: some View {
        splitViewCore
        // Every window-scoped menu command arrives through here, routed to
        // whichever window is key rather than broadcast to all of them — see
        // `WindowCommandFocus.swift`. Scene-scoped, not view-scoped, for the
        // reason `SidebarVisibilityFocus` documents: focus spends most of its
        // life inside the WKWebView, and a view-scoped value would drop out.
        .focusedSceneValue(
            \.windowCommands,
            WindowCommandSink(windowID: windowID, perform: { perform($0) })
        )
        // The state half of the same seam: the menu bar reads *this* window's
        // lens, undo stack and selection mirror when it is frontmost.
        .focusedSceneValue(\.bridge, bridgeHandler)
        // Take a place in the roster whenever what this window shows changes —
        // a different study, or a different lens of the same one. `initial`
        // covers the window opening already showing something.
        .onChange(of: windowGroup, initial: true) { _, group in
            windowRoster.claim(windowID: windowID, showing: group)
            serveFleet.sweep(shownProjects: windowRoster.shownProjects)
        }
        // Restore the lens this project was left on, once the report is up.
        // `isReady` is cleared by `BridgeHandler.reset()` on every project
        // switch, so this transition marks each fresh open. See `LensMemory`.
        .onChange(of: bridgeHandler.isReady) { _, ready in
            guard ready, let id = selectedProjectID, lensRestoredFor != id else { return }
            lensRestoredFor = id
            guard let project = projectIndex.projects.first(where: { $0.id == id }) else { return }
            // The seed's lens wins over the study's remembered one: it is a
            // deliberate "open THIS lens over there", and it is what makes the
            // lens row's Open in New Window one gesture rather than two.
            guard let tab = LensMemory.restore(seed?.lens)
                    ?? LensMemory.restore(project.lastLens) else { return }
            bridgeHandler.activateLens(tab)
            restoreAnchor(project.lastAnchor, on: tab)
        }
        // Remember where they leave it. Gated on having restored first — see
        // `lensRestoredFor`.
        .onChange(of: bridgeHandler.activeTab) { _, tab in
            guard let id = selectedProjectID, lensRestoredFor == id,
                  let lens = LensMemory.remember(tab) else { return }
            projectIndex.setLastLens(id: id, lens: lens)
            // A lens with no remembered position must clear the old one, or a
            // stale Quotes anchor would be restored against Codebook.
            if !LensAnchor.remembersPosition(tab) {
                projectIndex.setLastAnchor(id: id, anchor: nil)
            }
        }
        // …and where in it. Sessions reports its position as a route rather
        // than a scroll offset, so it comes from the window's own route memory
        // instead of the SPA's scroll reporter.
        .onChange(of: capturedAnchor) { _, anchor in
            guard let id = selectedProjectID, lensRestoredFor == id,
                  LensAnchor.remembersPosition(bridgeHandler.activeTab) else { return }
            projectIndex.setLastAnchor(id: id, anchor: anchor)
        }
        // A lens switch retires the old lens's anchor before the new lens has
        // reported one, so `capturedAnchor` goes nil without meaning "the top".
        // Clearing is handled by the activeTab observer above; this only exists
        // to note that the nil is expected.
        // Whatever `NewItemFallback` staged while there was no window to put it
        // in. `.onAppear` covers the window opened *to receive* it; `.onChange`
        // covers a window that was already up. Both drain the same one-shot.
        .onAppear { consumePendingSelection() }
        .onChange(of: projectIndex.pendingSelection) { _, _ in consumePendingSelection() }
        .sheet(isPresented: $showingMiroSheet) {
            if let port = serveManager?.runningPort {
                MiroSheet(
                    port: port,
                    token: serveManager?.authToken,
                    projectName: selectedProject?.name ?? "",
                    i18n: i18n
                )
            }
        }
        // Send Feedback (native) — Help ▸ Send Feedback and the status-page bridge
        // both post `.showFeedbackSheet`. Present in EVERY state: with a live serve
        // the sheet reads its config from `/api/health`; with no serve (the welcome
        // screen, before any project is selected) it falls back to the serve-free
        // `.serverless` config (canonical endpoint, enabled — same path the alpha
        // expiry flow uses), so the menu item is never a dead click.
        .onReceive(NotificationCenter.default.publisher(for: .showFeedbackSheet)) { _ in
            showingFeedbackSheet = true
        }
        .sheet(isPresented: $showingFeedbackSheet) {
            if let port = serveManager?.runningPort {
                FeedbackSheet(port: port, i18n: i18n, onToast: { toast.show($0) })
            } else {
                FeedbackSheet(config: .serverless, i18n: i18n, onToast: { toast.show($0) })
            }
        }
        // View ▸ Hide/Show Projects (⌘⌥S) acts on THIS window: publish our
        // `columnVisibility` binding as a scene focused value and let the menu
        // drive it directly. Replaces a `.toggleProjectsSidebar` broadcast that
        // every open window received (so two windows toggled in lockstep) plus a
        // mirror into the app-global `bridgeHandler.sidebarVisible` that the menu
        // label read (so the label could describe a different window). The
        // binding is the single source of truth the auto toolbar button already
        // drives. See `SidebarVisibilityFocus.swift`.
        .focusedSceneValue(\.sidebarVisibility, $columnVisibility)
        // Undo restored a removal batch — re-apply the prior selection.
        .onReceive(NotificationCenter.default.publisher(for: .undoableRemovalRestoredSelection)) { note in
            if let restored = note.userInfo?["selection"] as? Set<SidebarSelection> {
                selection = restored
            }
        }
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
            diskSpaceMessage: diskSpaceMessage(for:),
            analyseAction: analyseActionForSheet(_:)
        ))
        .sheet(item: $reAnalyseConfirm) { pending in
            ReAnalyseConfirmSheet(
                projectName: pending.project.name,
                sessionCount: pending.sessionCount,
                counts: pending.counts,
                onCancel: { reAnalyseConfirm = nil },
                onConfirm: {
                    let project = pending.project
                    reAnalyseConfirm = nil
                    pipelineRunner.start(project: project, clean: true)
                }
            )
            .environmentObject(i18n)
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
        panel.adoptHostAppearance()
        panel.begin { response in
            Task { @MainActor in
                guard response == .OK, let url = panel.url else { return }
                if LocateFlow.folderLooksAnalysed(url: url) {
                    projectIndex.relocateProject(id: project.id, newPath: url.path)
                    bridgeHandler.selectedProjectPath = url.path
                    bridgeHandler.selectedProjectAvailable = true
                    bridgeHandler.selectedProjectRevealablePath = url.path
                    if selection.contains(.project(project.id)), hasConsent {
                        serveFleet.manager(for: project.id).start(projectPath: url.path)
                    }
                } else {
                    locateError = LocateErrorState(project: project, pickedURL: url)
                }
            }
        }
    }

    /// File ▸ Add Files… — the menu-driven twin of drag-drop. Presents an open
    /// panel, then routes the chosen files through `handleDropOnProject` (the
    /// same intake path as a drop: guards → copy → incremental run for
    /// folder-shaped analysed projects). Toasts if no single project is selected.
    private func addFilesToSelectedProject() {
        // Unreachable from the menu, which now dims without a selection, and
        // unreachable by drag, where you drop *on* something. Kept as a guard,
        // not as a message: there is no researcher to inform here.
        guard let id = selectedProjectID else { return }
        let projectName = projectIndex.projects.first(where: { $0.id == id })?.name ?? ""
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.prompt = i18n.t("desktop.chrome.addFilesPrompt")
        panel.message = String(format: i18n.t("desktop.chrome.addFilesMessage"), projectName)
        // Match the app's appearance (window's forced `.preferredColorScheme`);
        // a free-floating panel otherwise follows the system theme.
        panel.adoptHostAppearance()
        panel.begin { response in
            Task { @MainActor in
                guard response == .OK, !panel.urls.isEmpty else { return }
                // Reuse the drop path — extension filtering, copy, and the
                // incremental-run wire (Phase 1) all live in handleDropOnProject.
                handleDropOnProject(id: id, urls: panel.urls)
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
                // …and into this window's scene value, so restoration brings it
                // back on the study it was SHOWING, not the one it opened on.
                if seed?.project != id {
                    // Keep this window's own token — replacing it would change
                    // the window's identity mid-life. Clear the seeded lens once
                    // consumed, so a later switch honours the study's own memory.
                    seed = WindowSeed(token: seed?.token ?? UUID(), project: id, lens: nil)
                }
                bridgeHandler.selectedProjectPath = project.path
                bridgeHandler.selectedProjectAvailable = project.isAvailable
                bridgeHandler.selectedProjectRevealablePath = revealPath(for: project) ?? ""
                bridgeHandler.hasSelectedProject = true
                bridgeHandler.selectedProjectIsRunning =
                    isRunningOrQueued(pipelineRunner.state[id])
                bridgeHandler.selectedProjectIsAnalysed =
                    SidebarOutlineController.reAnalyseIsOffered(
                        isFolderShaped: project.inputFiles == nil,
                        hasPath: !project.path.isEmpty,
                        state: pipelineRunner.state[id],
                        data: projectIndex.unanalysed[id]
                    )
                projectIndex.updateLastOpened(id: id)
                // Gate serve on consent + availability — nothing is sent to a
                // provider before the user has seen the AI data disclosure
                // (Apple 5.1.2(i)). ("No data leaves the machine" is not the
                // claim: the analysis IS an outbound call. See SECURITY.md.)
                if hasConsent && !project.path.isEmpty && project.isAvailable {
                    let path = project.path
                    // No switch: under the fleet a window *observes a different
                    // manager*, and that manager starts its own sidecar. The old
                    // `switchProject`'s same-path no-op, generation bump and
                    // liveness probe all guarded ONE shared serve from concurrent
                    // switchers; none has a per-project analogue.
                    //
                    // `switchTask` stays, and stays per-window: it serialises
                    // *this window's* async work, not the serve. That distinction
                    // is what keeps one epoch counter per instance rather than two
                    // ownership axes accreting.
                    switchTask?.cancel()
                    switchTask = Task { @MainActor in
                        guard !Task.isCancelled else { return }
                        // **Lazy: a background window does not spawn a sidecar.**
                        //
                        // The appliance copes rather than asking the researcher
                        // to. Select twelve projects and open them all and you
                        // get twelve windows and one or two serves — the rest
                        // start when you look at them. Which is why the folder
                        // command needs no "are you sure" dialog counting
                        // servers at you: Finder, InDesign and Photoshop all let
                        // you select-all-and-open without a word, and the cost
                        // should be ours to manage.
                        //
                        // `design-workspace.md`'s memory model already said this
                        // — live-if-visible, discarded-if-occluded — and
                        // `ServeReaping` is the other half.
                        //
                        // **Live question, parked 20 Aug — judge by feel first.**
                        // This gates on `isKeyWindow`, which is live-if-*focused*
                        // and stricter than the model's live-if-*visible*: three
                        // windows side by side on a big screen are all visible,
                        // only one is key, so two sit unstarted while you look
                        // straight at them. `NSWindow.occlusionState` is the
                        // honest signal and switching is cheap.
                        //
                        // Whether any of it is tolerable depends on **cold-start
                        // time**, which nobody has measured since the A2 warm
                        // pool was deleted — and that pool existed precisely
                        // because cold start was "multi-second". Under ~500 ms
                        // lazy is invisible; at multi-second it grates on every
                        // switch regardless of the predicate. Measure before
                        // tuning, and be willing to revert to eager and pay the
                        // memory: the researcher expects to switch context and
                        // see their work.
                        guard windowIsKey else {
                            pendingStart = (id: id, path: path)
                            return
                        }
                        serveFleet.manager(for: id).start(projectPath: path)
                        // App-level windows (System Health, Run Inspector) and
                        // the boot log are about "the serve you are looking at".
                        // The window that most recently adopted a study is it —
                        // and `front` also restarts it if a preference or the
                        // consent state changed while nobody was looking at it.
                        serveFleet.front(id)
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
                    stopServeIfLastProjectWindow()
                }
            }
        case .folder(let id):
            pendingStart = nil
            persistedProjectID = ""
            bridgeHandler.selectedProjectPath = ""
            bridgeHandler.selectedProjectRevealablePath = ""
            bridgeHandler.selectedProjectIsRunning = false
            bridgeHandler.selectedProjectIsAnalysed = false
            bridgeHandler.hasSelectedProject = false
            bridgeHandler.selectedFolderName =
                projectIndex.folders.first { $0.id == id }?.name ?? ""
            stopServeIfLastProjectWindow()
        default:
            // Multi-select or empty — stop serve, clear state.
            pendingStart = nil
            persistedProjectID = ""
            bridgeHandler.selectedProjectPath = ""
            bridgeHandler.selectedProjectRevealablePath = ""
            bridgeHandler.selectedProjectIsRunning = false
            bridgeHandler.selectedProjectIsAnalysed = false
            bridgeHandler.hasSelectedProject = false
            bridgeHandler.selectedFolderName = ""
            stopServeIfLastProjectWindow()
        }
    }

    /// Stop the sidecar — but only if this window is the last one that needed it.
    ///
    /// Selection is per window; the sidecar is not. Every arm of
    /// `applySelectionChange` that isn't "serve this project" used to call
    /// `serveManager.stop()` on everyone's behalf, and the blast radius was
    /// total: killing the serve mints a new port on the next start, every
    /// window's web view is keyed on the port (`ServeSession.viewID`), so they
    /// all remount and land back on the Project dashboard.
    ///
    /// That made two ordinary acts destructive as soon as a second window
    /// existed — **opening a new window** (it starts with no selection and hits
    /// the default arm before restoring its project) and **going to the welcome
    /// screen** (deselecting). Both reset every other window. Reported from the
    /// first real multi-window run, 16 Aug 2026.
    ///
    /// The cancel stays unconditional: `switchTask` is this window's own.
    private func stopServeIfLastProjectWindow() {
        switchTask?.cancel()
        guard !windowRoster.anyProjectShown(excluding: windowID) else { return }
        serveManager?.stop()
    }

    // MARK: - Notification receivers (extracted to reduce body complexity)
    // Split into a ViewModifier to keep the main body within type-checker limits.

    // MARK: - Window-scoped menu commands

    /// Run a menu command in **this** window.
    ///
    /// The single door the menu bar reaches this window through, published as
    /// `WindowCommandSink`. Replaces fourteen `NotificationCenter` receivers
    /// that every open window answered — see `WindowCommandFocus.swift` for the
    /// taxonomy and `docs/design-workspace.md` §"P1's taxonomy".
    private func perform(_ command: WindowCommand) {
        switch command {
        case .newProject:
            createNewProject()
        case .newFolder:
            createNewFolder()

        case .showAIConsent:
            aiConsentReviewMode = true
            showingAIConsent = true
        case .showMiro:
            // The native sheet drives the same Python REST endpoints the web
            // panel uses, so it needs a live serve. The entry is only reachable
            // with a project open; this is the belt.
            if serveManager?.runningPort != nil { showingMiroSheet = true }
        case .showWelcome:
            // Deselect — the same effect as clicking the sidebar's empty space.
            selection = []
        case .showSessionsSwitcher:
            sessionsSwitcherRequest += 1
        case .applyDebugFixture(let scenario):
            applyDebugFixture(named: scenario)

        case .addFiles:
            addFilesToSelectedProject()
        case .renameProject:
            // Both paths, deliberately: the AppKit outline is the shipping
            // sidebar and answers `renameRequest`; `renamingProjectID` drives
            // the SwiftUI sidebar, which is inert while the outline renders.
            if case .project(let id) = soleSelection { renamingProjectID = id }
            renameRequest += 1
        case .renameFolder:
            if case .folder(let id) = soleSelection { renamingFolderID = id }
            renameRequest += 1
        case .deleteFolder:
            deleteSelectedFolders()
        case .moveProject(let folderID):
            guard case .project(let projectID) = soleSelection else { return }
            projectIndex.moveProject(projectId: projectID, toFolder: folderID)
        case .revealTranscripts:
            guard let target = TranscriptsRevealTarget.resolve(
                projectPath: bridgeHandler.selectedProjectPath
            ) else { return }
            NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: target)
        case .locateProject:
            if let project = selectedProject { locateProject(project) }
        case .stopProject:
            if let project = selectedProject { pipelineRunner.cancel(project: project) }
        case .reAnalyseProject:
            // Ask, always. `--clean` is `shutil.rmtree(output_dir)` — the whole
            // directory, database included — so this discards the analysis and
            // every edit made on top of it. The ellipsis on the menu item
            // promises a question; skipping it on a project that happens to
            // carry no curation would make the ellipsis a lie and would still
            // be throwing away finished work and re-spending on the provider.
            if let project = selectedProject { askToReAnalyse(project) }
        case .removeFromSidebar:
            removeSelectedProjectsFromSidebar()
        }
    }

    /// Delete every selected folder. Projects inside them are unaffected —
    /// `removeFolder` re-parents rather than cascading.
    private func deleteSelectedFolders() {
        let folderIds = selection.compactMap { sel -> UUID? in
            if case .folder(let id) = sel { return id }
            return nil
        }
        for id in folderIds {
            selection.remove(.folder(id))
            projectIndex.removeFolder(id: id)
        }
    }

    /// Diagnostics ▸ Diagnostic fixtures — inject a synthesised state into this
    /// window's selected project. No-op outside DEBUG, where the harness that
    /// applies it doesn't ship.
    private func applyDebugFixture(named scenario: String) {
        #if DEBUG
        guard let id = selectedProjectID else { return }
        pipelineRunner.applyDebugFixture(named: scenario, to: id)
        #endif
    }

    /// Take whatever `NewItemFallback` staged for the next window to appear.
    /// One-shot: `consumePendingSelection` clears as it reads, so a second
    /// window opening in the same run loop doesn't also grab it.
    private func consumePendingSelection() {
        guard let pending = projectIndex.consumePendingSelection() else { return }
        selection = [pending]
    }

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
        renamingFolderID = folder.id            // SwiftUI sidebar path (flag-off)
        projectIndex.pendingRename = folder.id  // AppKit sidebar path (shipping)
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

    /// Ask before rebuilding — unless there is nothing of the researcher's to
    /// lose, in which case just do what they asked.
    ///
    /// The counts come off the project database at the moment of asking rather
    /// than from anything cached: a sheet that measures has to measure now. The
    /// read is a handful of `COUNT(*)`s over an already-open-and-closed
    /// connection, and it happens once per menu click.
    private func askToReAnalyse(_ project: Project) {
        let counts = CurationCountsReader.read(
            projectRoot: URL(fileURLWithPath: project.path))
        guard !counts.isEmpty else {
            // Nothing curated: the analysis is derived output the researcher
            // just asked to have rebuilt, so there is nothing to weigh and a
            // modal would be a speed bump.
            pipelineRunner.start(project: project, clean: true)
            return
        }
        reAnalyseConfirm = PendingReAnalyse(
            project: project,
            sessionCount: projectIndex.unanalysed[project.id]?.sessionCount ?? 0,
            counts: counts
        )
    }

    /// The sheet's primary action, or `nil` when **Analyse** is not on offer
    /// for this project right now.
    ///
    /// Asks `SidebarOutlineController.analyseIsOffered` — the same predicate
    /// the context menu asks — rather than re-deriving "folder-shaped, has a
    /// path, pipeline free". Two copies of that reasoning is how a sheet comes
    /// to offer a run the menu says is unavailable.
    private func analyseActionForSheet(_ sheet: NewFilesSheetState) -> (() -> Void)? {
        guard let project = projectIndex.projects.first(where: { $0.id == sheet.projectID })
        else { return nil }
        guard SidebarOutlineController.analyseIsOffered(
            isFolderShaped: project.inputFiles == nil,
            hasPath: !project.path.isEmpty,
            state: pipelineRunner.state[project.id],
            data: projectIndex.unanalysed[project.id]
        ) else { return nil }
        return { pipelineRunner.start(project: project) }
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
                        serveFleet.manager(for: project.id).start(projectPath: url.path)
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
        // A running project is not removable, and both menus now decline to
        // offer the command for one — so this partition is the multi-select
        // case. The removable rows go and the running one stays, selected and
        // visible, which is the feedback: the thing that changed is the
        // message. There used to be a toast naming the blocked project; it was
        // telling the researcher something the sidebar was about to show them.
        let (removable, _) = partitionRemovable(candidates)
        guard !removable.isEmpty else { return }
        // Puff the rows before they leave the model — the rect is only
        // computable while the row exists. See `handleWillRemoveProjects`.
        NotificationCenter.default.post(
            name: .bristlenoseWillRemoveProjects,
            object: nil,
            userInfo: ["ids": removable.map(\.id)]
        )
        // Don't leave a warm sidecar serving a project the user just removed.
        for project in removable { serveFleet.discard(project.id) }
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
        // Unreachable while running — the context menu omits the item entirely
        // for a running project (`buildProjectMenu`). Kept as a guard, without
        // a message: there is nothing to tell someone who was never offered it.
        let (removable, _) = partitionRemovable([project])
        guard !removable.isEmpty else { return }
        for project in removable { serveFleet.discard(project.id) }
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
    /// Matches `ALL_EXTENSIONS` in `bristlenose/models.py` (includes `.txt` transcripts).
    /// Directories are always accepted (they become project roots).
    private static let acceptedExtensions: Set<String> = [
        // Audio
        "wav", "mp3", "m4a", "flac", "ogg", "wma", "aac",
        "aiff", "aif", "caf",
        // Video
        "mp4", "m4v", "mov", "avi", "mkv", "webm",
        "wmv", "asf", "mts", "m2ts", "3gp", "flv", "mpg", "mpeg",
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
            // Loose files / multi-folder / mixed — no single clean folder, so
            // there's no natural project location. Ask via NSSavePanel (the
            // sandbox-clean way to a write-granted spot): the user names +
            // places the project, we create the folder, copy the files in, and
            // it analyses like any folder-shaped project. Replaces the old
            // file-subset project the CLI's `discover_files` couldn't run.
            let looseURLs = directories + files
            // Prefill the standard "New project" placeholder (what "+ New
            // Project" gives), deduped against existing sidebar project names so
            // we don't suggest one that already exists → "New project 2", etc.
            // The *disk* path can't be pre-checked under App Sandbox (~/Documents
            // isn't granted until the user picks it), so a folder clash there is
            // handled by NSSavePanel's own "replace?" prompt at Create.
            let base = i18n.t("desktop.chrome.newProject")
            var suggestedName = base
            var n = 2
            while projectIndex.projects.contains(where: { $0.name == suggestedName }) {
                suggestedName = "\(base) \(n)"
                n += 1
            }
            createFolderProjectViaSavePanel(
                looseURLs: looseURLs, suggestedName: suggestedName,
                intoFolder: folderID
            )
        }
    }

    /// Loose files / multi-folder / mixed drops don't resolve to a single
    /// folder, so there's no natural project location. Under App Sandbox the
    /// app can't silently create one (Home-root isn't user-selected/entitled),
    /// so we ask via `NSSavePanel` — the user names + places the project, which
    /// grants write access to that spot. We create the folder, copy the files
    /// in, and it becomes a normal folder-shaped project that analyses like any
    /// other. Cancel → nothing created, nothing moved (copy runs only after
    /// Create). §7 storyboard + `docs/private/handoffs/incremental-swift-step4.md`.
    private func createFolderProjectViaSavePanel(
        looseURLs: [URL], suggestedName: String,
        intoFolder folderID: UUID? = nil, relocating relocateID: UUID? = nil
    ) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = suggestedName
        panel.directoryURL = ProjectFolderDefaults.suggestedDirectory()
        panel.canCreateDirectories = true
        panel.title = i18n.t("desktop.chrome.newProjectSaveTitle")
        panel.prompt = i18n.t("desktop.chrome.newProjectSavePrompt")
        panel.message = i18n.plural(
            "desktop.chrome.newProjectSaveMessage", count: looseURLs.count
        )
        // Resolve the host window for the sheet. A drop-initiated present runs
        // just after the drag's modal event loop, when keyWindow is momentarily
        // nil — `PanelHost` owns that fallback chain. Without a host the panel
        // lands via the free-floating `begin` fallback, which follows the
        // *system* theme (light on a dark app) and isn't window-modal.
        let host = PanelHost.window
        panel.adoptHostAppearance(host)
        // Window-modal sheet: the drop can't complete without a name + location,
        // so block the initiating window until the user decides — the HIG
        // modality for a window-scoped decision (a sheet, not an app-modal dialog
        // that freezes the whole app). A sheet also inherits the window's dark
        // appearance; the free-floating panel is the fallback only when there's
        // genuinely no window to attach to.
        func present(_ handler: @escaping (NSApplication.ModalResponse) -> Void) {
            if let host {
                panel.beginSheetModal(for: host, completionHandler: handler)
            } else {
                panel.begin(completionHandler: handler)
            }
        }
        present { response in
            Task { @MainActor in
                guard response == .OK, let target = panel.url else { return }
                do {
                    try FileManager.default.createDirectory(
                        at: target, withIntermediateDirectories: true
                    )
                    // Where studies live, learned rather than configured — the
                    // next New Project panel starts here instead of Documents.
                    ProjectFolderDefaults.remember(projectFolder: target)
                    // Folder-shaped (inputFiles == nil) → analysable. The project
                    // name follows the panel filename (single source of truth).
                    let project: Project
                    if let relocateID {
                        // Adopt the existing "New Project" placeholder rather than
                        // spawn a duplicate — relocate it into the chosen folder and
                        // take the panel name (keeps its id / position / icon).
                        projectIndex.relocateProject(id: relocateID, newPath: target.path)
                        projectIndex.renameProject(
                            id: relocateID, newName: target.lastPathComponent
                        )
                        guard let relocated = projectIndex.projects
                            .first(where: { $0.id == relocateID }) else { return }
                        project = relocated
                    } else {
                        project = projectIndex.addProject(
                            name: target.lastPathComponent, path: target.path,
                            intoFolder: folderID
                        )
                    }
                    selection = [.project(project.id)]
                    pipelineRunner.beginAddingInterviews(
                        projectID: project.id, count: looseURLs.count
                    )
                    let copied = try await copyMachinery.copy(
                        urls: looseURLs, into: target,
                        projectID: project.id, projectName: project.name,
                        acceptedExtensions: Self.acceptedExtensions
                    )
                    projectIndex.seedKnownBasenames(
                        projectID: project.id,
                        basenames: Set(copied.map { $0.lastPathComponent })
                    )
                    // Folder-shaped: the CLI rescans the folder at run time and
                    // folds the copied files in — the incremental-add machinery
                    // on a fresh project.
                    pipelineRunner.start(project: project)
                } catch is CancellationError {
                    // Copy cancelled via the row ring; pill rolled back. No toast.
                } catch CopyMachinery.CopyError.insufficientDiskSpace(
                    let needed, let available
                ) {
                    copyDiskSpaceAlert = CopyDiskSpaceAlertState(
                        needed: needed, available: available
                    )
                } catch {
                    toast.show(error.localizedDescription)
                }
            }
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
        // Belt-and-braces only. `SidebarOutlineController.acceptsFinderDrop`
        // refuses these three during the drag — no row highlight, the
        // operation-not-allowed pointer, the item springing back — so a drop
        // in these states should never arrive here. It is kept because the
        // pane's own `.dropDestination` is a second door, and because a silent
        // return is the correct answer either way.
        //
        // The three toasts that used to live here are gone. They announced at
        // drop-time what the drag now says, and one of them ("Use Retry on the
        // toolbar") signposted a control that is one right-click away.
        // `docs/design-analysis-lifecycle.md` §4.2.
        guard SidebarOutlineController.acceptsFinderDrop(state: pipelineRunner.state[id])
        else { return }

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

        // Immediate "Adding N interviews…" ack (Phase 2), held for a ~2 s floor
        // so it can't flash on a near-instant clonefile copy; yields to the
        // copy/scan states and then the stage ladder once the run starts.
        pipelineRunner.beginAddingInterviews(projectID: id, count: filteredURLs.count)

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
                    // Only the file-subset path surfaces the "Added N…" sheet — it
                    // doesn't auto-run, so the sheet is its sole feedback. On the
                    // folder-shaped auto-run path the sheet is a modal the §7
                    // storyboard explicitly rejects (the "Adding N interviews…"
                    // subtitle + the run IS the acknowledgement). See
                    // docs/mockups/incremental-analysis-flows.html §7.
                    newFilesSheet = NewFilesSheetState(
                        projectID: id,
                        projectName: project.name,
                        files: copied
                    )
                }
                if wasFolderShaped {
                    // Seed the watcher with the copied names so the "+N
                    // unanalysed" pill stays hidden — a run starts immediately
                    // below, so they are "known", not surprise drops. Handoff
                    // §Watcher lifecycle / Stacking rule.
                    projectIndex.seedKnownBasenames(
                        projectID: id,
                        basenames: Set(copied.map { $0.lastPathComponent })
                    )
                }
                // ...and deliberately NOT on the file-subset path, where no run
                // starts. Those files are exactly the drift the pill exists for,
                // so seeding them switched off the only durable signal the
                // researcher had — which is precisely why a toast had grown here
                // to replace it. The row now says "+N unanalysed" and keeps
                // saying it. `docs/design-analysis-lifecycle.md` §4.2.
                if alreadyAnalysed && !wasFolderShaped {
                    // The copy succeeded and the files are in the folder; a run
                    // is folder-scoped (`["run", project.path]`), so a
                    // re-analysis picks them up. The row carries that state now
                    // — nothing to announce.
                    return
                }
                if wasFolderShaped {
                    // Folder-shaped project (analysed or not): the CLI rescans
                    // the folder at run time, so the freshly-copied files fold in
                    // incrementally — the per-session cache re-transcribes only
                    // the new sessions + re-clusters, and curation is preserved
                    // on re-import. This is the incremental-add path (Phase 1).
                    // NB Beta-must: #post-TF gating (destructive re-analyse +
                    // warning modal is the TF path) is a product decision — see
                    // docs/private/handoffs/incremental-swift-step4.md.
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
            // Loose files / multi-folder / mixed dropped onto the "New Project"
            // placeholder — no single clean folder to adopt. Route to the same
            // NSSavePanel create flow as a sidebar drop, but *relocate* this
            // placeholder into the chosen folder instead of spawning a duplicate.
            // Replaces the old file-subset "can't be analysed" dead-end.
            let placeholderName = projectIndex.projects
                .first(where: { $0.id == id })?.name
                ?? i18n.t("desktop.chrome.newProject")
            createFolderProjectViaSavePanel(
                looseURLs: directories + files,
                suggestedName: placeholderName, relocating: id
            )
        }
    }

    // MARK: - Toolbar

    /// Per-tab label for the left-panel toolbar button.
    ///
    /// Per-tab label for the left-panel toggle. `.sessions` is absent: that
    /// lens's toolbar slot is the session-switcher popover
    /// (`SessionsSwitcherButton`), not a panel toggle.
    private var leftPanelToolbarLabel: String {
        switch bridgeHandler.activeTab {
        case .quotes:   return i18n.t("desktop.toolbar.contents")
        // v2 is the same lens; without this it falls to `default` and the
        // toggle reads "Contents". A `default:` arm sealing a new case into
        // the wrong string is how the sidebar acquired five unlocalised
        // labels once already.
        case .codebook, .codebookV2: return i18n.t("desktop.toolbar.codes")
        case .analysis: return i18n.t("desktop.toolbar.signals")
        default:        return i18n.t("desktop.toolbar.contents")
        }
    }

    /// Per-tab tooltip for the left-panel toolbar button.
    private var leftPanelToolbarHelp: String {
        switch bridgeHandler.activeTab {
        case .quotes:   return i18n.t("desktop.toolbar.showContents")
        case .codebook, .codebookV2: return i18n.t("desktop.toolbar.showCodes")
        case .analysis: return i18n.t("desktop.toolbar.showSignals")
        default:        return i18n.t("desktop.toolbar.showContents")
        }
    }

    @ToolbarContentBuilder
    private var toolbarLeading: some ToolbarContent {
        // Project name + subtitle render NATIVELY — `.navigationTitle` /
        // `.navigationSubtitle` on the detail view (see `body`), not a toolbar
        // item (the old chip sat where the system back affordance lives, the
        // wrong real estate). `.navigationTitle` drives NSWindow.title too, so
        // Mission Control / window-menu / Cmd+~ still show the project name.
        // The old `WindowTitleManager` is gone — its forced
        // `titleVisibility = .hidden` was what had suppressed the subtitle.

        // Contextual — Sessions: the native session-switcher popover.
        // Same glyph, same slot as the panel toggles below, but a different
        // KIND (momentary chooser, not a stateful toggle) — the accepted
        // list.bullet double-meaning; the menu twin is what keeps it honest.
        if bridgeHandler.activeTab == .sessions {
            ToolbarItem(placement: .navigation) {
                if let serveManager {
                    SessionsSwitcherButton(bridgeHandler: bridgeHandler,
                                           serveManager: serveManager,
                                           i18n: i18n,
                                           presentRequest: sessionsSwitcherRequest)
                }
            }
        }

        // Contextual — Quotes/Codebook/Analysis: left panel toggle
        // The native sidebar toggle (for the project list) is provided by
        // NavigationSplitView automatically — Mail-style: lives inside the
        // sidebar column when open, snaps left to traffic lights when closed.
        // This standalone button controls the web navigation sidebar
        // (sections/themes on Quotes, codebooks on Codebook, signals on
        // Analysis). Gestalt proximity: each toggle is near the thing it
        // controls.
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
        // Never-run folder project — `detail` shows the drag-interviews pane, not
        // the webview. (It used to show the serve's no-run status page *with* a
        // Search field and Export button hanging over it.)
        if case .idle = pipelineRunner.state[project.id] ?? .scanning { return false }
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
                ExportMenuButton(bridgeHandler: bridgeHandler, i18n: i18n,
                                 onMiro: { perform(.showMiro) })
            }

            // Contextual — Quotes tab: starred filter toggle + tag sidebar toggle
            if bridgeHandler.activeTab == .quotes {
                ToolbarItem(placement: .primaryAction) {
                    QuotesStarredToggle(bridgeHandler: bridgeHandler, i18n: i18n)
                }
                ToolbarItem(placement: .primaryAction) {
                    Button { bridgeHandler.menuAction("toggleRightPanel") } label: {
                        Label(i18n.t("desktop.toolbar.tags"), systemImage: "sidebar.right")
                    }
                    .help(i18n.t("desktop.toolbar.showTags"))
                }
            }

            // Contextual — Codebook tab: the Codebook Library picker. Promotes
            // the existing `Codes ▸ Browse Codebooks…` menu command (same
            // action string, same `books.vertical` symbol) into the toolbar,
            // which is the standard macOS promotion for a command the lens is
            // about. The web SPA keeps its own in-pane button; `ct()` in
            // CodebookPanel.tsx suppresses that copy here so the action appears
            // once per surface, not twice on one screen.
            if bridgeHandler.activeTab == .codebook {
                ToolbarItem(placement: .primaryAction) {
                    // The help string is reused, not minted — it is the menu
                    // command's own label, already reviewed in all 21 locales.
                    // The label is a new key because neither candidate twin
                    // worked: `codebook.browseCodebooks` is a verb phrase up to
                    // 31 chars ("Parcourir les grilles de codage"), and
                    // `codebook.frameworks` still reads "Frameworks" in all 20
                    // non-en locales — its English value drifted to "Library"
                    // without a re-seed, which no locale gate can detect.
                    Button { bridgeHandler.menuAction("browseCodebooks") } label: {
                        Label(i18n.t("desktop.toolbar.library"), systemImage: "books.vertical")
                    }
                    .help(i18n.t("desktop.menu.codes.browseCodebooks"))
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

            // Search — rightmost in `.primaryAction` (Notes / Mail / Finder
            // convention). Quotes has a native expanding search field wired to
            // the SPA store; the other lenses show a disabled button that
            // reserves the slot until per-lens search lands (Sessions →
            // transcript, Codebook → codes, Analysis → signals). The Project
            // dashboard has nothing to search, so no item there.
            ToolbarItem(placement: .primaryAction) {
                switch bridgeHandler.activeTab {
                case .quotes:
                    QuotesSearchToolbarControl(bridgeHandler: bridgeHandler, i18n: i18n)
                case .sessions, .codebook, .analysis:
                    SearchComingSoonButton(i18n: i18n)
                default:
                    EmptyView()
                }
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
        // reserved for genuinely app-global concerns — now a multi-pill shelf
        // sharing the `StatusPill` envelope: Ollama model-download, provider
        // out-of-credit, and the alpha-expiry notice. (Per-project vs app-global
        // is the placement axis: `docs/design-desktop-project-status.md` §4.)
        ToolbarItem(placement: .status) {
            OllamaDownloadPill(model: ollamaDownload)
        }
        // Sibling app-global pill: the active cloud provider is out of credit.
        // Cloud-only, so it never co-occurs with the Ollama (local) pill above.
        ToolbarItem(placement: .status) {
            OutOfCreditPill(model: outOfCredit)
        }
        // Sibling app-global pill: an expiring `.dmg` alpha build in its final
        // week. Self-gates (nil off the .developerID channel / outside the last
        // 7 days), so it renders nothing on App Store / TestFlight / CLI builds.
        ToolbarItem(placement: .status) {
            AlphaExpiryPill()
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
                onActivateLens: { bridgeHandler.activateLens($0) },
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
                onReAnalyse: { id in
                    // Targets the *clicked* project, not the selection — a
                    // right-click on a row the user hasn't selected must not
                    // wipe the one they had selected.
                    if let p = projectIndex.projects.first(where: { $0.id == id }) {
                        askToReAnalyse(p)
                    }
                },
                onShowInFinder: { id in
                    if let p = projectIndex.projects.first(where: { $0.id == id }) { revealInFinder(p) }
                },
                canShowInFinder: { id in
                    projectIndex.projects.first(where: { $0.id == id }).map(canRevealInFinder) ?? false
                },
                canShareWithAgents: { id in
                    projectIndex.projects.first(where: { $0.id == id }).map {
                        AgentAccessPolicy.canShare(
                            $0, sessionCount: projectIndex.unanalysed[id]?.sessionCount)
                    } ?? false
                },
                mcpMounted: serveFleet.mcpMounted,
                onRemoveProject: { id in removeFromSidebarContextMenu(targetingProject: id) },
                // Passes the project as the scene value, so per-value window
                // dedup applies deliberately: on a study that already has a
                // window this reveals it rather than opening a duplicate, which
                // is what a reveal-or-open command should do. ⌥⌘N is the one
                // that must always spawn, and it passes a fresh token instead.
                onOpenInNewWindow: { id in
                    openWindow(id: "main", value: WindowSeed.revealing(project: id))
                },
                onOpenLensInNewWindow: { lens in
                    // This study, that lens, over there — one gesture. Fresh
                    // token so it always opens, even alongside a window already
                    // on this study, which is the entire point.
                    openWindow(id: "main",
                               value: WindowSeed.fresh(project: selectedProject?.id,
                                                       lens: LensMemory.remember(lens)))
                },
                onRemoveFolder: { id in deleteFromContextMenu(targetingFolder: id) },
                pipelineRunner: pipelineRunner,
                liveData: pipelineRunner.liveData,
                copyMachinery: copyMachinery,
                cloudImport: cloudImport,
                // Exposure, not activity (§5a-bis). Read the handshake
                // writer's own answer rather than re-deriving it: "serve is
                // up" is that predicate minus mcpInstanceID and mcpToken,
                // and the gap is reachable on every start and switch.
                handshakeProjectPaths: serveFleet.handshakeProjectPaths,
                lastAgentCallAt: serveFleet.lastAgentCallAt,
                renameRequest: renameRequest
            )
            .navigationTitle(i18n.t("desktop.chrome.projects"))
        } else {
            swiftUISidebar
        }
    }

    /// The sidebar. In a child this is the *same* view with the project list
    /// omitted — same width, same metrics, the lens rail simply sitting where it
    /// always sat. An omission, not a second control, which is what keeps the
    /// child one flag rather than a window type of its own.
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
            // `windowProject`, not `selectedProject`: a child has no selection,
            // so reading the selection here would dim the lens rail — the one
            // control a child exists for — in every child window.
            isEnabled: windowProject != nil && bridgeHandler.isReady
        )
        .padding(.horizontal, 8)
        .padding(.top, 6)
        .padding(.bottom, 2)

        projectList
        }
    }

    /// The studies list — a master's half of the sidebar.
    ///
    /// Extracted from `swiftUISidebar` unchanged so the child gate is one
    /// `if` rather than an indentation change over seventy lines.
    private var projectList: some View {
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

    /// Whether the decorative shoal animation takes the detail pane — while
    /// analysing, when the user hasn't switched it off, and when Reduce Motion
    /// is off. Falls through to the boot / "drop interviews" screens otherwise
    /// (the same surfaces it replaces), so the off-switch needs no separate UI.
    private func shouldShowShoal(_ project: Project) -> Bool {
        showAnalysisAnimation
            && !reduceMotion
            && isAnalysing(pipelineRunner.state[project.id])
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
        // A run may have renumbered the positional session ids — a remembered
        // `s3` would then restore *successfully* to a different participant's
        // transcript. Clearing beats validating: renumbering only happens via
        // a run, and this is the transition that marks one (SessionsRouteMemory).
        bridgeHandler.clearSessionsRouteMemory()
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
                guard case .running = serveManager?.state else {
                    Self.reloadLog.info("reload wait attempt=\(attempt)")
                    continue
                }
                // Phase 6 — idle-flag hold: never reload the report out from
                // under an in-progress edit. A WKWebView reload destroys unsaved
                // text in a focused field, the exact collision §9 exists to
                // prevent. Ride out the edit like we ride out the re-import; if
                // still editing when attempts run out, skip the reload — a stale
                // report is recoverable, a clobbered edit is not (it refreshes on
                // the next selection/run). NB the SPA is assumed authoritative for
                // applying fresh /quotes once idle; this only stops Swift from
                // blunt-reloading over the user.
                if bridgeHandler.isEditing {
                    Self.reloadLog.info("reload defer (editing) attempt=\(attempt)")
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
            bridgeHandler.selectedProjectIsAnalysed = false
            bridgeHandler.hasSelectedProject = false
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
        if let project = windowProject {
            if !project.isAvailable {
                // Project directory is not accessible — volume ejected or folder moved.
                unavailableProjectView(project)
            } else if shouldShowShoal(project) {
                // Analysing with nothing to show yet — the typographic shoal
                // takes the pane in place of the boot / "drop interviews"
                // screens. Decorative; the real progress signal is the sidebar
                // row's ring + subtitle. Reduce Motion / the preference fall
                // back to those same screens (see shouldShowShoal).
                ShoalRunView(
                    projectID: project.id,
                    liveData: pipelineRunner.liveData,
                    feedURL: ShoalFeed.feedURL(projectPath: project.path)
                )
            } else if project.path.isEmpty {
                // New project with no files yet — prompt user to add interviews.
                dragInterviewsPane(project)
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
            } else if case .idle = pipelineRunner.state[project.id] ?? .scanning {
                // Folder-shaped project that has never produced a report. The
                // webview's own no-run status page (`status_page.detect_status`,
                // `entry is None`) used to own this pane, which meant two
                // different-looking empty states for the same user-perceived
                // condition — and its "drop a folder of interviews here" copy was
                // a promise the WebView couldn't keep (no drop target). Same pane
                // as the empty-path case above: one look, and a drop that lands
                // (folder-drop is the explicit signal to analyse — see
                // `handleDropOnProject`).
                //
                // Deliberately `.idle` only. `.scanning` still falls through to
                // the serve gate so an already-analysed project shows BootView
                // rather than flashing an empty pane before the manifest read
                // resolves; failed / cancelled / partial states keep the status
                // page, which carries the cause and log tail.
                dragInterviewsPane(project)
            } else {
                ZStack {
                    // This pane renders ONE project, so it reads that
                    // project's serve — not `serveManager`, which is derived
                    // from the window's selection. Under the fleet they agree
                    // in every normal state, and where they could diverge the
                    // project is the honest source: it is what the pane is
                    // about. Non-optional by construction, which is why this
                    // switch needs no nil arm.
                    switch serveFleet.manager(for: project.id).state {
                    // `.idle` used to mean "about to start" and mapped to the
                    // same view as `.starting`. Under lazy start it also means
                    // "deliberately deferred", and those must not look alike.
                    case .idle:
                        BootView(phase: .deferred, project: project.id)

                    case .starting:
                        BootView(phase: .startingSidecar, project: project.id)

                    // **The window's project is not what the sidecar is serving.**
                    //
                    // Only a master can reach this: it owns a `selection`, and
                    // between "clicked study B" and "sidecar for B is up" its
                    // title already says B while the pane would still show A.
                    // Rendering the boot state is the honest answer; rendering
                    // the running serve would put another study's participant
                    // data under this window's name, which is the failure
                    // `design-workspace.md` constraint 5 describes and the one
                    // that reaches an outbound edge — `Send to Miro` would
                    // export the wrong study's quotes to a board named for the
                    // right one.
                    //
                    // A child cannot arrive here mismatched: `windowProject` is
                    // *derived* from `currentProjectPath`, so the two agree by
                    // construction. The guard is the master's alone.
                    case .running where serveFleet.manager(for: project.id)
                        .currentProjectPath != project.path:
                        BootView(phase: .startingSidecar, project: project.id)

                    case .running(let port):
                        // Key on project id AND serve port. A warm-pool re-point
                        // (Phase A2) keeps the same project id but hands off to a
                        // sidecar on a different port — keying on id alone would
                        // NOT re-mount, so updateNSView would reload the new port
                        // while reusing the previous sidecar's injected auth token
                        // → silent 401s / blank report. The port in the key forces
                        // a fresh makeNSView that re-injects the right token.
                        // `viewID` is also the storage-partition key, so the
                        // re-mount and the re-key can't drift apart.
                        WebView(url: serveURLWithLocale,
                                bridgeHandler: bridgeHandler,
                                session: ServeSession(projectID: project.id, port: port),
                                authToken: serveManager?.authToken)
                            .id(ServeSession(projectID: project.id, port: port).viewID)
                            .accessibilityLabel(i18n.t("desktop.chrome.reportContent"))
                            .accessibilityHidden(!bridgeHandler.isReady)
                            .focusSection()
                            // Translucent chrome (spike): extend the WebView
                            // behind the unified toolbar so the toolbar frost
                            // samples real report content, matching the
                            // Notes/Mail idiom on macOS 26 Tahoe. The SPA gets
                            // the toolbar inset via the bridge on `ready`
                            // (BridgeHandler.syncToolbarInset) and pads its
                            // top so first-of-content isn't cropped.
                            .ignoresSafeArea(.container, edges: .top)

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
                            serveFleet.manager(for: project.id).start(projectPath: project.path)
                        }), project: project.id)
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
            // New rotating-slots welcome home (design-welcome-screen.md).
            WelcomeHomeView(onDropURLs: { urls in
                let directories = urls.filter { $0.hasDirectoryPath }
                let files = urls.filter { !$0.hasDirectoryPath }
                createProjectFromURLs(directories: directories, files: files)
            })
        }
    }

    /// How many files a run would ingest — the number the pane promises.
    ///
    /// Reads the same field the Analyse predicate gates on, so the pane and the
    /// menu cannot disagree about whether there is anything here. Absent state
    /// (no watcher yet) counts as zero: `hasWorkToDo` resolves unknown to
    /// *offer* because hiding a control leaves no way forward, but the pane's
    /// alternative is not a dead end — it is the drop target, which is the
    /// right thing to show when we do not yet know what the folder holds.
    nonisolated static func filesToAnalyse(_ data: UnanalysedState?) -> Int {
        data?.ingestableFileCount ?? 0
    }

    /// Detail pane for a project with nothing to show yet — no folder at all, a
    /// folder that has never produced a report, or one holding recordings that
    /// have not been analysed.
    ///
    /// Two states, because "add some interviews" is a lie to a researcher who
    /// has already added six. With files present the pane counts them and
    /// carries the same **Analyse** the sidebar offers; the description line is
    /// dropped, since a sentence about how to get started only restates the
    /// button beneath it.
    ///
    /// **Files, not sessions.** Files are what we know before stage 1; sessions
    /// are what `group_into_sessions` decides, and six files from a Teams export
    /// can be three sessions. A session count here would be a prediction the
    /// sidebar then contradicts — the app disagreeing with itself about the size
    /// of the study.
    ///
    /// Accepts a Finder drop in both states, routed through the same
    /// `handleDropOnProject` as the project's sidebar row (→
    /// `establishEmptyProject` for the no-folder case, → auto-run for a folder
    /// drop), so the "Drag interviews here" copy is a promise the pane can keep.
    @ViewBuilder
    private func dragInterviewsPane(_ project: Project) -> some View {
        let waiting = Self.filesToAnalyse(projectIndex.unanalysed[project.id])
        Group {
            if waiting > 0 {
                ContentUnavailableView {
                    Label(i18n.plural("desktop.chrome.filesToAnalyse", count: waiting),
                          systemImage: "square.and.arrow.down")
                } description: {
                    EmptyView()
                } actions: {
                    Button(i18n.t("desktop.menu.project.analyse")) {
                        pipelineRunner.start(project: project)
                    }
                }
            } else {
                ContentUnavailableView(
                    i18n.t("desktop.chrome.dragInterviews"),
                    systemImage: "square.and.arrow.down",
                    description: Text(i18n.t("desktop.chrome.dragInterviewsDescription"))
                )
            }
        }
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

// (`ProjectNotificationReceivers` lived here until 16 Aug 2026 — nine
// `NotificationCenter` receivers for the Project menu, every one of which every
// open window answered. They are now `ContentView.perform(_:)` cases, reached
// through this window's `WindowCommandSink`.)

/// Toolbar export button — the macOS surface of the canonical export list,
/// at parity with the SPA dropdown (see docs/mockups/export-menu-comparison.html).
///
/// Rendered as a **richer popover** (Variant Ⓑ) rather than a plain `NSMenu`,
/// so each action carries a descriptive subtitle — matching the SPA dropdown's
/// information density. Layout: a global Anonymise pill toggle, a divider, then
/// "Export Report…" followed by the quote actions (Copy Quotes · Save as
/// Spreadsheet · Extract Video Clips) shown only on the Quotes tab. No group
/// headers — the subtitles carry the grouping.
///
/// Every item dispatches through `bridgeHandler.menuAction(_:payload:)`, which
/// the web layer (`AppLayout` `bn:menu-action`) routes into `utils/exportActions`
/// — the single source of truth shared with the SPA dropdown. The `anonymise`
/// flag rides the payload so it applies to whichever export the user picks.
///
/// Parked (future ideas, not shown): PowerPoint quote slides. (Send to Miro is
/// now shipped — the "Send to Miro…" row below; see docs/design-miro-bridge.md.)
struct ExportMenuButton: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    /// Present the Miro sheet, which `ContentView` owns. A closure rather than
    /// the `.showMiroSheet` broadcast it used to post — this button is in one
    /// window's toolbar, and the sheet belongs to that window.
    let onMiro: () -> Void

    @State private var isPresented = false

    var body: some View {
        Button {
            isPresented.toggle()
        } label: {
            Label(i18n.t("desktop.toolbar.export"), systemImage: "square.and.arrow.up")
        }
        .help(i18n.t("desktop.toolbar.exportShortcut"))
        .popover(isPresented: $isPresented, arrowEdge: .bottom) {
            ExportPopoverContent(bridgeHandler: bridgeHandler, i18n: i18n, onMiro: onMiro) {
                isPresented = false
            }
        }
    }
}

/// Contents of the export popover. Holds the (non-persisted) Anonymise state,
/// renders the grouped action rows, and dismisses the popover after a pick.
private struct ExportPopoverContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    let onMiro: () -> Void
    let dismiss: () -> Void

    /// Global Anonymise — strips participant *names* (display names) from every
    /// export; participant codes (p1, p2) are kept. Deliberately not persisted:
    /// the popover is recreated each open, so it defaults off and a researcher
    /// never ships an unexpectedly-anonymised export.
    @State private var anonymise = false

    private var payload: [String: Any] { ["anonymise": anonymise] }

    /// Dispatch a canonical export action, merging any per-action extras (e.g.
    /// the spreadsheet `format`) onto the global payload (currently `anonymise`).
    private func dispatch(_ action: String, _ extra: [String: Any] = [:]) {
        var p = payload
        for (key, value) in extra { p[key] = value }
        bridgeHandler.menuAction(action, payload: p)
        dismiss()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Global toggle — applies to whichever export the user picks next.
            Toggle(isOn: $anonymise) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(i18n.t("desktop.menu.quotes.anonymise"))
                    Text(i18n.t("desktop.menu.quotes.anonymiseHint"))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .toggleStyle(.switch)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider().padding(.horizontal, 10)

            ExportPopoverRow(
                icon: "square.and.arrow.up",
                title: i18n.t("desktop.menu.file.exportReport"),
                subtitle: i18n.t("desktop.menu.quotes.reportHint")
            ) { dispatch("exportReport") }

            if bridgeHandler.activeTab == .quotes {
                // Copy Quotes: a plain "copy all visible" action by default; it
                // grows into a scope disclosure only when there's something to
                // narrow to (a selection or starred quotes). Zero-count scopes
                // are hidden here (toolbar morphs); the menu bar keeps them dimmed.
                if bridgeHandler.selectedQuoteCount > 0 || bridgeHandler.starredQuoteCount > 0 {
                    ExportPopoverDisclosureRow(
                        icon: "doc.on.clipboard",
                        title: i18n.t("desktop.menu.quotes.copyQuotes"),
                        subtitle: i18n.t("desktop.menu.quotes.copyHint")
                    ) {
                        ExportPopoverSubRow(
                            title: i18n.t(
                                "desktop.menu.quotes.copyScopeAll",
                                ["count": String(bridgeHandler.totalQuoteCount)]
                            )
                        ) { dispatch("copyQuotes", ["scope": "all"]) }
                        if bridgeHandler.selectedQuoteCount > 0 {
                            ExportPopoverSubRow(
                                title: i18n.t(
                                    "desktop.menu.quotes.copyScopeSelected",
                                    ["count": String(bridgeHandler.selectedQuoteCount)]
                                )
                            ) { dispatch("copyQuotes", ["scope": "selected"]) }
                        }
                        if bridgeHandler.starredQuoteCount > 0 {
                            ExportPopoverSubRow(
                                title: i18n.t(
                                    "desktop.menu.quotes.copyScopeStarred",
                                    ["count": String(bridgeHandler.starredQuoteCount)]
                                )
                            ) { dispatch("copyQuotes", ["scope": "starred"]) }
                        }
                    }
                } else {
                    ExportPopoverRow(
                        icon: "doc.on.clipboard",
                        title: i18n.t("desktop.menu.quotes.copyQuotes"),
                        subtitle: i18n.t("desktop.menu.quotes.copyHint")
                    ) { dispatch("copyQuotes", ["scope": "all"]) }
                }
                // Spreadsheet is a disclosure: pick CSV or XLSX. Both endpoints
                // exist server-side; the `format` extra selects which.
                ExportPopoverDisclosureRow(
                    icon: "tablecells",
                    title: i18n.t("desktop.menu.quotes.saveSpreadsheet"),
                    subtitle: i18n.t("desktop.menu.quotes.spreadsheetHint")
                ) {
                    ExportPopoverSubRow(title: i18n.t("desktop.menu.quotes.formatCSV")) {
                        dispatch("saveSpreadsheet", ["format": "csv"])
                    }
                    ExportPopoverSubRow(title: i18n.t("desktop.menu.quotes.formatXLSX")) {
                        dispatch("saveSpreadsheet", ["format": "xlsx"])
                    }
                }
                ExportPopoverRow(
                    icon: "film",
                    title: i18n.t("desktop.menu.quotes.extractClips"),
                    subtitle: i18n.t("desktop.menu.quotes.clipsHint")
                ) { dispatch("extractClips") }
            }

            // Sessions lens: the transcripts already live on disk in the
            // project's bristlenose-output/ — reveal them in Finder rather than
            // re-exporting what's already a folder of files (local-first). The
            // drag-to-sidebar affordance hides where the folder lives, so the
            // macOS surface needs a way back to it (CLI users are already there).
            if bridgeHandler.activeTab == .sessions {
                ExportPopoverRow(
                    icon: "folder",
                    title: i18n.t("desktop.menu.quotes.revealTranscripts"),
                    subtitle: i18n.t("desktop.menu.quotes.revealTranscriptsHint")
                ) { revealTranscripts() }
            }

            // Send to Miro — always available (uploads the project's quotes as a
            // new board of sticky notes). Presents the native MiroSheet, which
            // drives the same Python REST endpoints the web panel uses; this
            // window's ContentView owns the .sheet (via `onMiro`).
            Divider().padding(.horizontal, 10)
            ExportPopoverRow(
                icon: "square.grid.2x2",
                title: i18n.t("common.miro.menuLabel"),
                subtitle: i18n.t("common.miro.popoverSubtitle")
            ) {
                dismiss()
                onMiro()
            }
        }
        .frame(width: 308)
        .padding(.vertical, 6)
    }

    /// Open a Finder window on the project's transcripts. Prefers the
    /// PII-redacted `transcripts-cooked/` (present only when `--redact-pii`
    /// ran), else `transcripts-raw/`, else the output / project folder. This is
    /// a native action — it reveals files already on disk, so it does NOT honour
    /// the Anonymise toggle (an anonymised transcript bundle is a separate,
    /// deferred export). Output lives at `<project>/bristlenose-output/`.
    private func revealTranscripts() {
        dismiss()
        guard let target = TranscriptsRevealTarget.resolve(
            projectPath: bridgeHandler.selectedProjectPath
        ) else { return }
        NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: target)
    }
}

/// A single action row in the export popover: leading SF Symbol, title, and a
/// muted subtitle. Highlights on hover (the popover is not a system menu, so
/// the hover affordance is hand-rolled).
private struct ExportPopoverRow: View {
    let icon: String
    let title: String
    let subtitle: String
    let action: () -> Void

    @State private var hovered = false

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: icon)
                    .font(.body)
                    .foregroundStyle(.tint)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .background(hovered ? Color.primary.opacity(0.06) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
        .onHover { hovered = $0 }
        .padding(.horizontal, 6)
    }
}

/// An export row that expands in place to reveal sub-options (e.g. the
/// spreadsheet format chooser). Same visual language as `ExportPopoverRow`
/// plus a trailing chevron that rotates when expanded. Tapping the row toggles
/// the disclosure rather than dispatching — the leaf `ExportPopoverSubRow`s do.
private struct ExportPopoverDisclosureRow<Content: View>: View {
    let icon: String
    let title: String
    let subtitle: String
    @ViewBuilder let content: () -> Content

    @State private var expanded = false
    @State private var hovered = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                expanded.toggle()
            } label: {
                HStack(alignment: .top, spacing: 10) {
                    Image(systemName: icon)
                        .font(.body)
                        .foregroundStyle(.tint)
                        .frame(width: 18)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(title)
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .rotationEffect(.degrees(expanded ? 90 : 0))
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
                .background(hovered ? Color.primary.opacity(0.06) : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.plain)
            .onHover { hovered = $0 }

            if expanded {
                content()
            }
        }
        .padding(.horizontal, 6)
        .animation(reduceMotion ? nil : .easeInOut(duration: 0.15), value: expanded)
    }
}

/// A leaf option inside an `ExportPopoverDisclosureRow` — indented under the
/// parent's icon column, no icon of its own.
private struct ExportPopoverSubRow: View {
    let title: String
    let action: () -> Void

    @State private var hovered = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 0) {
                Spacer().frame(width: 28)
                Text(title)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 5)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
            .background(hovered ? Color.primary.opacity(0.06) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
        .onHover { hovered = $0 }
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
    ///
    /// `UserHome`, not `NSHomeDirectory()` — the latter returns the sandbox
    /// container, so the home prefix never matched and the crumb read
    /// `Users › cassio › Work › Studies`, making VoiceOver speak two junk
    /// components before the useful ones.
    private func breadcrumbSegments(for url: URL) -> [String] {
        UserHome.abbreviatedSegments(url.path)
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
