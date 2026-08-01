import AppKit
import SwiftUI

// MARK: - Menu bar

/// Native menu bar — every command reachable, keyboard shortcuts discoverable.
///
/// Uses the `View`-inside-`Commands` pattern: `@ObservedObject` is unreliable
/// directly in `Commands.body`, so each menu section is a small `View` struct
/// that owns `@ObservedObject var bridgeHandler`. Views inside `CommandMenu` /
/// `CommandGroup` follow normal SwiftUI view lifecycle and observe correctly.
///
/// All actions dispatch through `bridgeHandler.menuAction(_:payload:)` which
/// calls `callAsyncJavaScript` with structured arguments (security rule 3).
///
/// Menu order: Bristlenose · File · Edit · View · Project · Codes · Quotes · Video · Window · Help
///
/// Menu item labels are translated via `I18n` (reads from shared JSON locale files).
/// `CommandMenu` titles stay in English — SwiftUI resolves `LocalizedStringKey`
/// from `.lproj` bundles, not runtime JSON. Matches ATLAS.ti/MAXQDA precedent.
struct MenuCommands: Commands {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var removalStore: UndoableRemovalStore
    @ObservedObject var i18n: I18n
    /// Used only by the Diagnostics menu's DEBUG harness section (Ollama
    /// setup-pill state forcing).
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    /// Gates the Diagnostics menu's presence. `@AppStorage` is a
    /// DynamicProperty, so flipping the toggle in Appearance settings should
    /// re-evaluate menu presence live; if a macOS release regresses that, the
    /// documented fallback is applies-on-next-launch (Safari-acceptable).
    @AppStorage(DiagnosticsPreference.key)
    private var showDiagnosticsMenu: Bool = DiagnosticsPreference.defaultValue

    var body: some Commands {
        CommandGroup(replacing: .appInfo) {
            AppMenuContent(serveManager: serveManager, i18n: i18n)
        }

        CommandGroup(replacing: .newItem) {
            FileMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(replacing: .undoRedo) {
            UndoRedoMenuContent(bridgeHandler: bridgeHandler, removalStore: removalStore, i18n: i18n)
        }

        CommandGroup(after: .textEditing) {
            FindMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        CommandGroup(replacing: .toolbar) {
            ViewMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        // CommandMenu titles stay in English (see doc comment above).
        // Grouped into a child Commands struct to stay under CommandsBuilder's
        // 10-element limit.
        CustomMenus(
            bridgeHandler: bridgeHandler,
            projectIndex: projectIndex,
            i18n: i18n
        )

        // Window > Bristlenose — reopen the main window if the user has closed it
        // but the app process is still alive (Notes / Music / Pages convention).
        // No keyboard shortcut: ⌘0 collides with WKWebView's "reset zoom" and
        // there's no recognisable alternative. Cohort feedback can revisit.
        CommandGroup(before: .windowList) {
            ShowMainWindowMenuContent()
            Divider()
        }

        CommandGroup(replacing: .help) {
            HelpMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }

        // Diagnostics menu — gated by the `showDiagnosticsMenu` preference
        // (Appearance settings; off by default, on in local DEBUG builds), so
        // a keen tester on ANY channel can opt into the poke-around tools.
        // Contents compound by build inside the one menu: Section 1 (user
        // diagnostics) ships everywhere; Section 2 (devtools — the SQLAdmin
        // browser) only where `exposesDebugTools` (local DEBUG + Developer-ID
        // .dmg beta, never App Store/TestFlight); Section 3 (fake-state
        // harness) is `#if DEBUG` only. See docs/design-diagnostics-menu.md.
        if showDiagnosticsMenu {
            CommandMenu("Diagnostics") {
                DiagnosticsMenuContent(
                    ollamaDownload: ollamaDownload,
                    serveManager: serveManager,
                    bridgeHandler: bridgeHandler
                )
            }
        }
    }
}

/// The single Diagnostics menu — three sections, gates compounding inside it
/// (the pref gates the menu; the channel + build-config gates pick sections).
/// Labels are commands only, no ellipsis on open-window items (HIG — opening a
/// window that IS the thing takes no further input). English-only for now,
/// matching the menu's tester-facing register.
private struct DiagnosticsMenuContent: View {
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    @ObservedObject var serveManager: ServeManager
    /// Used by the DEBUG harness section's "Grid Specimen" (navigates the SPA).
    @ObservedObject var bridgeHandler: BridgeHandler
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        // Section 1 — user diagnostics, every channel. Reveal-existing-data
        // actions for the served project + the Shoal animation at defaults.
        // (Web Inspector is a side-effect of the preference toggle, not a menu
        // item — there's no public API to open a hosted WKWebView's inspector.)

        // Check Health — opens the native Health window (`DoctorReportView`),
        // which runs the doctor-style local system checks via `GET /api/doctor`
        // and renders them as a native list. No ellipsis: opening a window that
        // IS the thing takes no further input (HIG). Replaced the dead
        // `menuAction("checkSystemHealth")` bridge dispatch (28 Jul 2026).
        Button("Check Health") {
            openWindow(id: "health")
        }

        Divider()

        Button("Reveal .bristlenose/ in Finder") {
            DiagnosticsActions.revealInternalDir(serveManager: serveManager)
        }
        Button("Open Log in Console") {
            DiagnosticsActions.openLog(serveManager: serveManager)
        }
        Button("Copy Build Provenance") {
            DiagnosticsActions.copyBuildProvenance(serveManager: serveManager)
        }
        Button("Shoal Screensaver") { openWindow(id: "shoal-view") }

        if DistributionChannel.current.exposesDebugTools {
            Divider()
            // Section 2 — developer tools (.dmg beta + local DEBUG only).
            // No ellipsis — opens the panel directly in the browser.
            Button("Open Admin Panel") {
                AdminPanelAction.open(serveManager: serveManager)
            }
            .disabled(serveManager.runningPort == nil)
        }

        #if DEBUG
        Divider()
        // Section 3 — full-fat harness, dev machines only.
        DebugMenuContent(
            ollamaDownload: ollamaDownload,
            serveManager: serveManager,
            bridgeHandler: bridgeHandler
        )
        #endif
    }
}

#if DEBUG
/// DEBUG-only menu driving the Ollama setup pill through every state for live
/// UX QA — no daemon or network needed. Forcing any scene also resurrects the
/// pill from idle (the `BRISTLENOSE_DEBUG_OLLAMA_PHASE` bootstrap only fires at
/// launch). View struct per the `@ObservedObject`-in-Commands pattern.
private struct DebugMenuContent: View {
    @ObservedObject var ollamaDownload: OllamaDownloadModel
    @ObservedObject var serveManager: ServeManager
    /// "Grid Specimen" navigates the report SPA (no native window scene).
    @ObservedObject var bridgeHandler: BridgeHandler
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        // Diagnostics windows take NO keyboard shortcut — except Run Inspector,
        // the one tool slated to ship to users (Tier U per design-diagnostics-menu.md),
        // which keeps ⌃⌘R. Rationale + canonical rule: docs/design-keyboard-shortcuts.md
        // § "Diagnostics windows".
        // No ellipsis: opening a window that IS the thing takes no further input
        // (HIG — ellipsis means "needs more input before it completes").
        Button("Type Parity Inspector") { openWindow(id: "type-parity") }

        Button("Run Inspector") { openWindow(id: "run-inspector") }
            .keyboardShortcut("r", modifiers: [.command, .control])

        // The tuning harness (sliders/presets/FPS probe) — distinct from the
        // Section-1 "Shoal Screensaver" (the animation at defaults).
        Button("Shoal Tuner") { openWindow(id: "shoal") }

        Button("Shimmer Tuner") { openWindow(id: "shimmer-tuner") }

        Button("Keycap Gallery") { openWindow(id: "keycap-gallery") }

        // Debug lens — test content on a visible grid, inside the report
        // webview itself (measures the production CSS in situ). Routes the
        // SPA to /report/specimen; needs a served project.
        Button("Grid Specimen") { bridgeHandler.menuAction("openSpecimen") }
            .disabled(serveManager.runningPort == nil)

        // (Reveal / Open Log / Copy Provenance moved to Section 1 — they ship
        // to every channel now. See DiagnosticsActions.)

        // Inject a synthesized diagnostic state into the SELECTED project's
        // sidebar row — flip popover/indicator scenes live, no relaunch. Posts
        // to ContentView, which owns the selection. (Previously env-var-only.)
        Menu("Diagnostic fixtures ▸ selected project") {
            ForEach(DiagnosticFixture.summaryScenarioNames, id: \.self) { name in
                Button(name) { postFixture(name) }
            }
            Divider()
            ForEach(DiagnosticFixture.simpleStateNames, id: \.self) { name in
                Button(name) { postFixture(name) }
            }
            Divider()
            Button(DiagnosticFixture.noSummaryScenarioName) {
                postFixture(DiagnosticFixture.noSummaryScenarioName)
            }
        }

        Divider()

        // Flyout submenu — the pill state harness is a deep but rarely-needed
        // list; keep the top-level Debug menu to the inspectors + a Cycle
        // shortcut, and tuck the per-scene buttons behind one hover.
        Button("Cycle Ollama pill ▸ next state") { ollamaDownload.debugCycleNext() }
            .keyboardShortcut("o", modifiers: [.command, .control])
        Menu("Ollama setup pill") {
            ForEach(OllamaDownloadModel.DebugScene.allCases, id: \.self) { scene in
                Button(scene.label) { ollamaDownload.debugApply(scene) }
            }
            Divider()
            Button("Hide pill (idle)") { ollamaDownload.cancel() }
        }
    }

    /// Ask ContentView (which owns the sidebar selection) to inject `name` into
    /// the selected project. Mirrors the `.createNewProject` notification idiom.
    private func postFixture(_ name: String) {
        NotificationCenter.default.post(
            name: .applyDebugFixture, object: nil, userInfo: ["scenario": name]
        )
    }
}

extension Notification.Name {
    /// DEBUG only — posted by Debug ▸ Diagnostic fixtures; observed by
    /// ContentView, which applies the named fixture to the selected project.
    static let applyDebugFixture = Notification.Name("bristlenoseApplyDebugFixture")
}
#endif

// MARK: - Custom CommandMenus grouped

private struct CustomMenus: Commands {
    let bridgeHandler: BridgeHandler
    let projectIndex: ProjectIndex
    let i18n: I18n

    var body: some Commands {
        CommandMenu("Project") {
            ProjectMenuContent(bridgeHandler: bridgeHandler, projectIndex: projectIndex, i18n: i18n)
        }
        CommandMenu("Codes") {
            CodesMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Quotes") {
            QuotesMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
        CommandMenu("Video") {
            VideoMenuContent(bridgeHandler: bridgeHandler, i18n: i18n)
        }
    }
}

// MARK: - Window > Bristlenose

private struct ShowMainWindowMenuContent: View {
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        // Brand name, not a translatable phrase — Notes / Music / Pages all
        // use the app's own name here regardless of system language.
        Button("Bristlenose") {
            openWindow(id: "main")
        }
    }
}

// MARK: - App menu (Bristlenose)

private struct AppMenuContent: View {
    @ObservedObject var serveManager: ServeManager
    @ObservedObject var i18n: I18n

    var body: some View {
        Button(i18n.t("desktop.menu.app.about")) {
            let buildNumber = Bundle.main.infoDictionary?["CFBundleVersion"] as? String
            var options: [NSApplication.AboutPanelOptionKey: Any] = [:]

            if let version = serveManager.serverVersion {
                var versionString = version
                if let build = buildNumber {
                    versionString += " (\(build))"
                }
                options[.applicationVersion] = versionString
            }

            // Stash the BuildInfo block in the standard panel's Credits area
            // so users posting an "About" screenshot already include enough
            // provenance to disambiguate the build.
            let credits = BuildInfo.current.detailed(
                sidecar: serveManager.mode?.shortSummary ?? "?"
            )
            options[.credits] = NSAttributedString(
                string: credits,
                attributes: [
                    .font: NSFont.monospacedSystemFont(ofSize: 10, weight: .regular),
                    .foregroundColor: NSColor.secondaryLabelColor,
                ]
            )

            options[.version] = ""
            NSApp.orderFrontStandardAboutPanel(options: options)
        }

        Divider()

        Button(i18n.t("desktop.menu.app.aiPrivacy"), systemImage: "hand.raised") {
            NotificationCenter.default.post(
                name: .showAIConsentSheet, object: nil)
        }

        Divider()

        // Connect an Agent… — the plain word where discovery happens; the
        // pane it opens says MCP everywhere (the precise word where the
        // work happens). Honest that it only opens Settings — the same
        // shape as Mail's Add Account…, which also opens a pane. Setup is
        // a once-ever, app-level act, so it lives in the app menu, not the
        // project menu (that one gets the per-project verb swap).
        Button(i18n.t("desktop.menu.app.connectAgent"),
               systemImage: "antenna.radiowaves.left.and.right") {
            SettingsWindow.shared.show(pane: .mcpAgents)
        }
    }
}

// MARK: - File menu

private struct FileMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Button(i18n.t("desktop.menu.file.newProject"), systemImage: "plus") {
            NotificationCenter.default.post(name: .createNewProject, object: nil)
        }
        .keyboardShortcut("n", modifiers: .command)

        Button(i18n.t("desktop.menu.file.newFolder"), systemImage: "folder.badge.plus") {
            NotificationCenter.default.post(name: .createNewFolder, object: nil)
        }
        .keyboardShortcut("n", modifiers: [.command, .shift])

        // Add Files… — the menu twin of drag-drop. ⇧⌘A mirrors Apple Mail's
        // File ▸ Attach Files. Posts unconditionally (like New Project/Folder);
        // ContentView resolves the current selection and toasts if none.
        Button(i18n.t("desktop.menu.file.addFiles"), systemImage: "plus.rectangle.on.folder") {
            NotificationCenter.default.post(name: .addFilesToSelectedProject, object: nil)
        }
        .keyboardShortcut("a", modifiers: [.command, .shift])

        Button(i18n.t("desktop.menu.file.openInNewWindow"), systemImage: "macwindow.badge.plus") {
            bridgeHandler.menuAction("openInNewWindow")
        }
        .keyboardShortcut("o", modifiers: [.command, .shift])

        Divider()

        Button(i18n.t("desktop.menu.file.exportReport"), systemImage: "square.and.arrow.up") {
            bridgeHandler.menuAction("exportReport")
        }
        .keyboardShortcut("e", modifiers: [.command, .shift])

        // "Export Anonymised…" was removed here on 28 Jul 2026: anonymise is a
        // checkbox on the export save panel itself (`ExportAccessoryView`, attached
        // as the NSSavePanel accessoryView in `WebView.swift`), so a second menu
        // item offering the same choice was redundant — one command, one dialog,
        // the option lives in the dialog. Export Report… now stands alone here:
        // the File menu carries the whole-report export; per-quote destinations
        // (Miro, clips, spreadsheets) live in the Quotes menu.

        Divider()

        // Page Setup / Print are NATIVE (`NSPrintOperation`), not bridge calls.
        // They used to dispatch `menuAction("pageSetup"/"print")`, which no SPA
        // handler consumed — silent no-ops. `window.print()` inside a WKWebView
        // can't raise the macOS print panel, so the bridge was never the right
        // target. Prints whatever lens is on screen; see `PrintActions`.
        Button(i18n.t("desktop.menu.file.pageSetup")) {
            PrintActions.pageSetup()
        }

        Button(i18n.t("desktop.menu.file.print"), systemImage: "printer") {
            PrintActions.print(webView: bridgeHandler.webView, window: PanelHost.window)
        }
        .keyboardShortcut("p", modifiers: .command)
        // `isReady` is the only published signal that a web view has loaded
        // (`webView` itself is a plain weak var, so it can't drive SwiftUI).
        // It's an imperfect proxy — see the "isReady is NOT 'the report is
        // showing'" gotcha in desktop/CLAUDE.md — but it correctly separates
        // "nothing to print yet" from "something is on screen".
        .disabled(!bridgeHandler.isReady)
    }
}

// MARK: - Edit > Undo/Redo

private struct UndoRedoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var removalStore: UndoableRemovalStore
    @ObservedObject var i18n: I18n

    /// Removal-undo takes priority over web-side undo when pending: it's the
    /// most recent action and has a strict 8s window. After commit it falls
    /// back to the previous (web) behaviour.
    private var undoLabel: String {
        if let name = removalStore.pendingName {
            return String(format: i18n.t("desktop.menu.edit.undoRemove"), name)
        }
        return bridgeHandler.undoLabel ?? i18n.t("desktop.menu.edit.undo")
    }

    private var canUndo: Bool {
        removalStore.hasPending || bridgeHandler.canUndo
    }

    var body: some View {
        if !bridgeHandler.isEditing {
            Button(undoLabel, systemImage: "arrow.uturn.backward") {
                if removalStore.hasPending {
                    removalStore.undoLastRemoval()
                } else {
                    bridgeHandler.menuAction("undo")
                }
            }
            .keyboardShortcut("z", modifiers: .command)
            .disabled(!canUndo)

            Button(i18n.t("desktop.menu.edit.redo"), systemImage: "arrow.uturn.forward") {
                bridgeHandler.menuAction("redo")
            }
            .keyboardShortcut("z", modifiers: [.command, .shift])
            .disabled(!bridgeHandler.canRedo)
        }
    }
}

// MARK: - Edit > Find

private struct FindMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        Divider()

        Button(i18n.t("desktop.menu.edit.find"), systemImage: "magnifyingglass") {
            bridgeHandler.menuAction("find")
        }
        .keyboardShortcut("f", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.findNext")) {
            let text = NSPasteboard(name: .find).string(forType: .string) ?? ""
            bridgeHandler.menuAction("findNext", payload: ["text": text])
        }
        .keyboardShortcut("g", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.findPrevious")) {
            let text = NSPasteboard(name: .find).string(forType: .string) ?? ""
            bridgeHandler.menuAction("findPrevious", payload: ["text": text])
        }
        .keyboardShortcut("g", modifiers: [.command, .shift])

        Button(i18n.t("desktop.menu.edit.useSelectionForFind")) {
            bridgeHandler.menuAction("useSelectionForFind")
        }
        .keyboardShortcut("e", modifiers: .command)

        Button(i18n.t("desktop.menu.edit.jumpToSelection")) {
            bridgeHandler.menuAction("jumpToSelection")
        }
        .keyboardShortcut("j", modifiers: .command)
    }
}

// MARK: - View menu

private struct ViewMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    /// The FRONT window's projects-sidebar binding, published by its
    /// `ContentView` via `focusedSceneValue`. Window-scoped on purpose: Hide/Show
    /// Projects must move one window, not all of them. `nil` when no project
    /// window is key, which dims the item.
    @FocusedValue(\.sidebarVisibility) private var sidebarVisibility

    /// Locale key suffix for the left-panel label, per tab.
    private var leftPanelKey: String? {
        switch bridgeHandler.activeTab {
        case .sessions: return "Sessions"
        case .quotes:   return "Contents"
        case .codebook: return "Codes"
        case .analysis: return "Signals"
        default:        return nil
        }
    }

    private var hasLeftPanel: Bool {
        leftPanelKey != nil
    }

    var body: some View {
        // Tab shortcuts Cmd+1 through Cmd+5
        ForEach(Array(Tab.allCases.enumerated()), id: \.element.id) { index, tab in
            Button(tab.localizedLabel(i18n), systemImage: LensItem.systemImage(for: tab)) {
                bridgeHandler.switchToTab(tab)
            }
            .keyboardShortcut(
                KeyEquivalent(Character("\(index + 1)")),
                modifiers: .command
            )
        }

        // View ▸ Move Focus to Projects was REMOVED 28 Jul 2026 — deliberately
        // not replaced. It existed as a "§10.1 keyboard no-trap" escape, but a
        // menu item is not an accessibility affordance: a keyboard user stuck in
        // the web view will not discover the fourth row of the View menu. macOS
        // already provides the real escapes — ⌃F6 / ⇧⌃F6 cycle split-view panes,
        // ⌃F2 focuses the menu bar, and Tab should exit the WKWebView at document
        // end. WCAG 2.1.2 asks for "unmodified arrow or tab keys, or other
        // standard exit methods"; ⌃F6 is one, a bespoke menu item is not.
        // If a trap is ever demonstrated, the fix is the window's key-view loop,
        // not another unread menu row. Verification task filed in TODO.md.

        Divider()

        // Dynamic Hide/Show label (Finder convention), content-named "Projects"
        // to match the reveal-family (Show Contents / Sessions / Codes / Signals
        // / Tags) and disambiguate from the web left panel. Toggles through the
        // `columnVisibility` binding via ContentView, not the AppKit selector, so
        // the auto toolbar button and this item share one source of truth.
        Button(i18n.t(SidebarToggle.isVisible(sidebarVisibility?.wrappedValue ?? .all)
                      ? "desktop.menu.view.hideProjects"
                      : "desktop.menu.view.showProjects"),
               systemImage: "sidebar.left") {
            guard let sidebarVisibility else { return }
            withAnimation {
                sidebarVisibility.wrappedValue = SidebarToggle.next(sidebarVisibility.wrappedValue)
            }
        }
        .keyboardShortcut("s", modifiers: [.command, .option])
        .disabled(sidebarVisibility == nil)

        Button(i18n.t("desktop.menu.view.show\(leftPanelKey ?? "Contents")"), systemImage: "list.bullet") {
            bridgeHandler.menuAction("toggleLeftPanel")
        }
        .keyboardShortcut("l", modifiers: [.command, .option])
        .disabled(!hasLeftPanel)

        Button(i18n.t("desktop.menu.view.showTags"), systemImage: "sidebar.right") {
            bridgeHandler.menuAction("toggleRightPanel")
        }
        .keyboardShortcut("t", modifiers: [.command, .option])
        .disabled(bridgeHandler.activeTab != .quotes)

        Button(i18n.t("desktop.menu.view.showHeatmap"), systemImage: "square.grid.2x2") {
            bridgeHandler.menuAction("toggleInspectorPanel")
        }
        .disabled(bridgeHandler.activeTab != .analysis)

        Divider()

        // Radio-style pair: the active view mode carries a checkmark. A Toggle
        // inside a menu is the native idiom for "this option is on"; the set
        // closure ignores the new value and dispatches the action (the SPA owns
        // the state, mirrored back via `quotes-filter`). Tag filtering moved to
        // the tag sidebar (View ▸ Show Tags) — the old Filter by Tag item is gone.
        Toggle(i18n.t("desktop.menu.view.allQuotes"), isOn: Binding(
            get: { bridgeHandler.quotesViewMode == "all" },
            set: { _ in bridgeHandler.menuAction("allQuotes") }
        ))
        .disabled(bridgeHandler.activeTab != .quotes)

        Toggle(isOn: Binding(
            get: { bridgeHandler.quotesViewMode == "starred" },
            set: { _ in bridgeHandler.menuAction("starredQuotesOnly") }
        )) {
            Label(i18n.t("desktop.menu.view.starredQuotesOnly"), systemImage: "star")
        }
        .disabled(bridgeHandler.activeTab != .quotes)

        Divider()

        Button(i18n.t("desktop.menu.view.zoomIn"), systemImage: "plus.magnifyingglass") {
            bridgeHandler.menuAction("zoomIn")
        }
        .keyboardShortcut("=", modifiers: .command)

        Button(i18n.t("desktop.menu.view.zoomOut"), systemImage: "minus.magnifyingglass") {
            bridgeHandler.menuAction("zoomOut")
        }
        .keyboardShortcut("-", modifiers: .command)

        // ⌘0 — the platform's reset-zoom binding, and semantically identical to
        // WKWebView's own. Taking it here resolves the collision this file
        // previously worked around rather than creating one.
        Button(i18n.t("desktop.menu.view.actualSize")) {
            bridgeHandler.menuAction("actualSize")
        }
        .keyboardShortcut("0", modifiers: .command)
    }
}

// MARK: - Project menu

private struct ProjectMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var i18n: I18n

    /// Whether a folder is selected.
    private var hasFolder: Bool {
        !bridgeHandler.selectedFolderName.isEmpty
    }

    /// The single selected project, resolved by path — empty
    /// `selectedProjectPath` covers both no-selection and multi-selection
    /// (Rename's guard). Same path standardisation the badge identity uses.
    private var selectedProject: Project? {
        let path = bridgeHandler.selectedProjectPath
        guard !path.isEmpty else { return nil }
        return projectIndex.projects.first { AgentActivity.samePath($0.path, path) }
    }

    private var selectedProjectAccessOn: Bool { selectedProject?.agentAccess ?? false }

    private var selectedProjectCanShare: Bool {
        selectedProject.map {
            AgentAccessPolicy.canShare(
                $0, sessionCount: projectIndex.unanalysed[$0.id]?.sessionCount)
        } ?? false
    }

    var body: some View {
        if hasFolder {
            // Folder-specific items
            Button(i18n.t("desktop.menu.folder.rename"), systemImage: "pencil") {
                NotificationCenter.default.post(name: .renameSelectedFolder, object: nil)
            }

            Button(i18n.t("desktop.menu.folder.archive"), systemImage: "archivebox") {
                // Phase 5
            }
            .disabled(true)

            Divider()

            Button(i18n.t("desktop.menu.folder.delete"), systemImage: "trash", role: .destructive) {
                NotificationCenter.default.post(name: .deleteSelectedFolder, object: nil)
            }
            .keyboardShortcut(.delete, modifiers: .command)
        } else {
            // Project-specific items (or nothing selected)
            Button(i18n.t("desktop.menu.project.showInFinder"), systemImage: "folder") {
                let path = bridgeHandler.selectedProjectRevealablePath
                if !path.isEmpty {
                    NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: path)
                }
            }
            .keyboardShortcut("r", modifiers: [.command, .shift])
            .disabled(bridgeHandler.selectedProjectRevealablePath.isEmpty)

            // Show Transcripts in Finder — the menu twin of the export popover's
            // row, which was the only surface carrying it (the menu bar is the
            // canonical accessible one). Sits with Show in Finder because the
            // object is the same — the selected project's files, one level down.
            // `doc.text`, not a second `folder`, so two adjacent reveals don't
            // share a glyph.
            Button(i18n.t("desktop.menu.quotes.revealTranscripts"), systemImage: "doc.text") {
                NotificationCenter.default.post(name: .revealTranscripts, object: nil)
            }
            .disabled(bridgeHandler.selectedProjectPath.isEmpty)

            Button(i18n.t("desktop.chrome.locate"), systemImage: "location.magnifyingglass") {
                NotificationCenter.default.post(name: .locateSelectedProject, object: nil)
            }
            .disabled(bridgeHandler.selectedProjectAvailable)

            // HIG: every context-menu item is also reachable from the menu
            // bar. Turn On/Off Agent Access — the context menu's verb swap
            // (§3.6a). Opposite visibility rule to the context menu: menus
            // dim, context menus hide. Rename's single-selection guard, the
            // antenna on both label states, and deliberately NO keyboard
            // shortcut — exposure is a deliberate act, and accelerators are
            // for things fired without looking.
            Button(selectedProjectAccessOn
                       ? i18n.t("desktop.menu.project.turnOffAgentAccess")
                       : i18n.t("desktop.menu.project.turnOnAgentAccess"),
                   systemImage: "antenna.radiowaves.left.and.right") {
                if let project = selectedProject {
                    projectIndex.setAgentAccess(id: project.id, enabled: !project.agentAccess)
                }
            }
            .disabled(!selectedProjectCanShare)

            Button(i18n.t("desktop.menu.project.rename"), systemImage: "pencil") {
                NotificationCenter.default.post(name: .renameSelectedProject, object: nil)
            }
            // Single-selection-only operation; receiver guards on `sole`.
            // `selectedProjectPath.isEmpty` covers both no-selection AND
            // multi-selection (cleared by applySelectionChange's default
            // branch). Indie-consensus: Finder/Notes/Mail/Things disable
            // Rename on multi-select rather than silently no-op.
            .disabled(bridgeHandler.selectedProjectPath.isEmpty)

            // "Move to" submenu — lists all folders + "No Folder" for root.
            // Disabled on no-selection AND multi-selection for the same
            // reason as Rename — receiver guards on `sole`, so submenu
            // children would silently no-op (and that's especially bad in
            // a submenu, where the user has invested two clicks before
            // discovering the dead end).
            if !projectIndex.folders.isEmpty {
                Menu(i18n.t("desktop.menu.project.moveTo"), systemImage: "folder") {
                    Button(i18n.t("desktop.menu.project.noFolder")) {
                        NotificationCenter.default.post(
                            name: .moveSelectedProject, object: nil
                        )
                    }

                    Divider()

                    ForEach(projectIndex.folders) { folder in
                        Button(folder.name) {
                            NotificationCenter.default.post(
                                name: .moveSelectedProject, object: nil,
                                userInfo: ["folderId": folder.id]
                            )
                        }
                    }
                }
                .disabled(bridgeHandler.selectedProjectPath.isEmpty)
            }

            // ⌘. is the canonical macOS Stop/Cancel; here it's the keyboard
            // accelerator for the row's hover-× and context-menu Stop. Acts on
            // the sole-selected project; dimmed (not hidden) when it isn't
            // running, per menu-bar HIG (context menus hide instead).
            Button(i18n.t("desktop.menu.project.stopAnalysis"), systemImage: "stop.circle") {
                NotificationCenter.default.post(name: .stopSelectedProject, object: nil)
            }
            .keyboardShortcut(".", modifiers: .command)
            .disabled(!bridgeHandler.selectedProjectIsRunning)

            Button(i18n.t("desktop.menu.project.reAnalyse"), systemImage: "arrow.clockwise") {
                bridgeHandler.menuAction("reAnalyse")
            }
            .disabled(true)  // Future — Phase 2+

            Button(i18n.t("desktop.menu.project.archive"), systemImage: "archivebox") {
                bridgeHandler.menuAction("archive")
            }
            .disabled(true)  // Future — Phase 5

            Divider()

            Button(i18n.t("desktop.menu.project.removeFromSidebar"), systemImage: "minus.circle") {
                NotificationCenter.default.post(
                    name: .removeSelectedProjectsFromSidebar, object: nil
                )
            }
            .keyboardShortcut(.delete, modifiers: .command)
        }
    }
}

// MARK: - Codes menu

private struct CodesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var isCodeTab: Bool {
        bridgeHandler.activeTab == .codebook || bridgeHandler.activeTab == .quotes
    }

    var body: some View {
        Button(i18n.t("desktop.menu.codes.createCodeGroup"), systemImage: "folder.badge.plus") {
            bridgeHandler.menuAction("createCodeGroup")
        }

        Button(i18n.t("desktop.menu.codes.renameCodeGroup"), systemImage: "pencil") {
            bridgeHandler.menuAction("renameCodeGroup")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.deleteCodeGroup"), systemImage: "trash") {
            bridgeHandler.menuAction("deleteCodeGroup")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.showHideCodeGroup"), systemImage: "eye") {
            bridgeHandler.menuAction("toggleCodeGroup")
        }
        .disabled(!isCodeTab)

        Divider()

        Button(i18n.t("desktop.menu.codes.createCode"), systemImage: "tag") {
            bridgeHandler.menuAction("createCode")
        }

        Button(i18n.t("desktop.menu.codes.renameCode"), systemImage: "pencil") {
            bridgeHandler.menuAction("renameCode")
        }
        .disabled(!isCodeTab)

        Button(i18n.t("desktop.menu.codes.deleteCode"), systemImage: "trash") {
            bridgeHandler.menuAction("deleteCode")
        }
        .disabled(!isCodeTab)

        // Merge Codes — withdrawn from the menu 28 Jul 2026, deliberately left
        // in place rather than deleted.
        //
        // Merging needs a *source* and a *target*. The codebook lens has no
        // multi-select, so the only way to express "merge A into B" is the
        // existing drag-one-code-onto-another in `CodebookPanel` — a menu item
        // simply cannot say which two codes it means. That's why `mergeCode` had
        // no handler on either side of the bridge and clicked through to nothing.
        //
        // Restore this when codebook selection lands (tracked in the sprint
        // planning notes). The web half already exists and works —
        // `mergeCodebookTags` in `frontend/src/utils/api.ts`, driven by the
        // panel's drag merge — so this becomes a one-line re-enable plus a
        // `case "mergeCode"` that reads the selection.
        //
        // Button(i18n.t("desktop.menu.codes.mergeCodes"), systemImage: "arrow.triangle.merge") {
        //     bridgeHandler.menuAction("mergeCode")
        // }
        // .disabled(!isCodeTab)

        Divider()

        Button(i18n.t("desktop.menu.codes.browseCodebooks"), systemImage: "books.vertical") {
            bridgeHandler.menuAction("browseCodebooks")
        }

        Button(i18n.t("desktop.menu.codes.importFramework"), systemImage: "square.and.arrow.down") {
            bridgeHandler.menuAction("importFramework")
        }

        Button(i18n.t("desktop.menu.codes.removeFramework"), systemImage: "minus.circle") {
            bridgeHandler.menuAction("removeFramework")
        }
        .disabled(!isCodeTab)
    }
}

// MARK: - Quotes menu

private struct QuotesMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var onQuotesTab: Bool {
        bridgeHandler.activeTab == .quotes
    }

    private var hasFocus: Bool {
        onQuotesTab && bridgeHandler.focusedQuoteId != nil
    }

    private var hasSelection: Bool {
        onQuotesTab && bridgeHandler.selectedQuoteCount > 0
    }

    /// Star / Hide / Apply-Last-Tag act on the selection *or* the focused quote
    /// (the same `selection || focused` target the click and `s`/`h`/`r` keys
    /// use). ⌘A produces a selection with no focused quote, so gating these on
    /// `hasFocus` alone would wrongly disable them right after Select All.
    private var hasTarget: Bool {
        hasFocus || hasSelection
    }

    /// Star command label — flips Star⇄Unstar to match the click/`s`-key intent
    /// (unstar when the target set is all-starred), and carries the selection
    /// count when acting on a multi-selection ("Star 3 Quotes"), mirroring the
    /// Copy Quotes scope labels. Falls back to the plain verb for a single
    /// focused quote.
    private var starLabel: String {
        let base = bridgeHandler.starActionIsUnstar ? "unstar" : "star"
        let count = bridgeHandler.selectedQuoteCount
        if count > 0 {
            return i18n.plural("desktop.menu.quotes.\(base)Count", count: count)
        }
        return i18n.t("desktop.menu.quotes.\(base)")
    }

    /// Star glyph, flipped in step with `starLabel`. The icon previews the
    /// *result*, not the negation of it: "Star" shows the filled star the
    /// quote is about to get; "Unstar" shows the open star it reverts to.
    /// (`star.slash` would read as "starring is disabled" — wrong meaning.)
    private var starSymbol: String {
        bridgeHandler.starActionIsUnstar ? "star" : "star.fill"
    }

    /// Apply-last-tag label — names the tag when one has been applied this
    /// session ("Apply “usability”"); otherwise the generic verb (and the item
    /// is disabled, since there's nothing to repeat).
    private var applyLastTagLabel: String {
        if let name = bridgeHandler.lastTagName {
            return i18n.t("desktop.menu.quotes.applyTagNamed", ["name": name])
        }
        return i18n.t("desktop.menu.quotes.applyLastTag")
    }

    var body: some View {
        Button(starLabel, systemImage: starSymbol) {
            bridgeHandler.menuAction("star")
        }
        .disabled(!hasTarget)

        Button(i18n.t("desktop.menu.quotes.hide"), systemImage: "eye.slash") {
            bridgeHandler.menuAction("hide")
        }
        .disabled(!hasTarget)

        // Add Tag opens the tag input on the focused quote specifically, so it
        // stays focus-gated (unlike the bulk-capable Star/Hide/Apply above).
        Button(i18n.t("desktop.menu.quotes.addTag"), systemImage: "tag") {
            bridgeHandler.menuAction("addTag")
        }
        .disabled(!hasFocus)

        Button(applyLastTagLabel, systemImage: "tag.fill") {
            bridgeHandler.menuAction("applyLastTag")
        }
        .disabled(!hasTarget || bridgeHandler.lastTagName == nil)

        Button(i18n.t("desktop.menu.quotes.revealInTranscript"), systemImage: "doc.text.magnifyingglass") {
            bridgeHandler.menuAction("revealInTranscript")
        }
        .disabled(!hasFocus)

        Button(i18n.t("desktop.menu.quotes.playPause"), systemImage: "play") {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button(i18n.t("desktop.menu.quotes.nextQuote")) {
            bridgeHandler.menuAction("nextQuote")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.previousQuote")) {
            bridgeHandler.menuAction("previousQuote")
        }
        .disabled(!onQuotesTab)

        Divider()

        Button(i18n.t("desktop.menu.quotes.extendSelectionDown")) {
            bridgeHandler.menuAction("extendSelectionDown")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.extendSelectionUp")) {
            bridgeHandler.menuAction("extendSelectionUp")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.toggleSelection")) {
            bridgeHandler.menuAction("toggleSelection")
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.clearSelection")) {
            bridgeHandler.menuAction("clearSelection")
        }
        .disabled(!hasSelection)

        Divider()

        // Export — mirrors the toolbar export popover so every export action has
        // a keyboard- and VoiceOver-reachable path (the popover is a convenience;
        // the menu bar is the canonical, accessible surface). Native submenus
        // give scope/format pickers proper keyboard nav + VoiceOver for free.
        // TODO: surface the global Anonymise toggle here too (needs a shared
        // persisted-flag decision) and retire the legacy copyAsCSV item below.
        Menu(i18n.t("desktop.menu.quotes.copyQuotes"), systemImage: "doc.on.clipboard") {
            Button(i18n.t("desktop.menu.quotes.copyScopeAll",
                          ["count": String(bridgeHandler.totalQuoteCount)])) {
                bridgeHandler.menuAction("copyQuotes", payload: ["scope": "all"])
            }
            Button(i18n.t("desktop.menu.quotes.copyScopeSelected",
                          ["count": String(bridgeHandler.selectedQuoteCount)])) {
                bridgeHandler.menuAction("copyQuotes", payload: ["scope": "selected"])
            }
            .disabled(bridgeHandler.selectedQuoteCount == 0)
            Button(i18n.t("desktop.menu.quotes.copyScopeStarred",
                          ["count": String(bridgeHandler.starredQuoteCount)])) {
                bridgeHandler.menuAction("copyQuotes", payload: ["scope": "starred"])
            }
            .disabled(bridgeHandler.starredQuoteCount == 0)
        }
        .disabled(!onQuotesTab)

        Menu(i18n.t("desktop.menu.quotes.saveSpreadsheet"), systemImage: "tablecells") {
            Button(i18n.t("desktop.menu.quotes.formatCSV")) {
                bridgeHandler.menuAction("saveSpreadsheet", payload: ["format": "csv"])
            }
            Button(i18n.t("desktop.menu.quotes.formatXLSX")) {
                bridgeHandler.menuAction("saveSpreadsheet", payload: ["format": "xlsx"])
            }
        }
        .disabled(!onQuotesTab)

        Button(i18n.t("desktop.menu.quotes.extractClips"), systemImage: "film") {
            bridgeHandler.menuAction("extractClips")
        }
        .disabled(!onQuotesTab)

        // Send to Miro — mirrors the toolbar popover's Miro row. Always enabled
        // (uploads the project's quotes regardless of the active tab), matching
        // the popover. Presents the native MiroSheet (ContentView owns the .sheet).
        // Lives HERE, not in File: Miro exports quotes, and File carries the
        // whole-report export. (Briefly moved to File on 28 Jul 2026 and moved
        // straight back — recorded so it isn't "tidied" there again.)
        Button(i18n.t("common.miro.menuLabel")) {
            NotificationCenter.default.post(name: .showMiroSheet, object: nil)
        }

        Divider()

        Button(i18n.t("desktop.menu.quotes.copyAsCSV"), systemImage: "doc.on.clipboard") {
            bridgeHandler.menuAction("copyAsCSV")
        }
        .disabled(!hasSelection)
    }
}

// MARK: - Video menu

private struct VideoMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    private var active: Bool { bridgeHandler.hasPlayer }

    var body: some View {
        Button(bridgeHandler.playerPlaying
               ? i18n.t("desktop.menu.video.pause")
               : i18n.t("desktop.menu.video.play"),
               systemImage: bridgeHandler.playerPlaying ? "pause" : "play") {
            bridgeHandler.menuAction("playPause")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.skipForward5"), systemImage: "goforward.5") {
            bridgeHandler.menuAction("skipForward5")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipBack5"), systemImage: "gobackward.5") {
            bridgeHandler.menuAction("skipBack5")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipForward30"), systemImage: "goforward.30") {
            bridgeHandler.menuAction("skipForward30")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.skipBack30"), systemImage: "gobackward.30") {
            bridgeHandler.menuAction("skipBack30")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.speedUp"), systemImage: "forward") {
            bridgeHandler.menuAction("speedUp")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.slowDown"), systemImage: "backward") {
            bridgeHandler.menuAction("slowDown")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.normalSpeed"), systemImage: "gauge.medium") {
            bridgeHandler.menuAction("normalSpeed")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.volumeUp"), systemImage: "speaker.wave.3") {
            bridgeHandler.menuAction("volumeUp")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.volumeDown"), systemImage: "speaker.wave.1") {
            bridgeHandler.menuAction("volumeDown")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.mute"), systemImage: "speaker.slash") {
            bridgeHandler.menuAction("mute")
        }
        .disabled(!active)

        Divider()

        Button(i18n.t("desktop.menu.video.pictureInPicture"), systemImage: "pip.enter") {
            bridgeHandler.menuAction("pictureInPicture")
        }
        .disabled(!active)

        Button(i18n.t("desktop.menu.video.fullscreen"), systemImage: "arrow.up.left.and.arrow.down.right") {
            bridgeHandler.menuAction("fullscreen")
        }
        .disabled(!active)
    }
}

// MARK: - Help menu

private struct HelpMenuContent: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n

    var body: some View {
        // Help, Keyboard Shortcuts, and Acknowledgements open external pages in
        // the browser — the in-app Help modal is retired ("Help opens browser
        // docs"). They don't route through the web bridge, so they work whether
        // or not the SPA is mounted (e.g. on the status page after a failed run).
        Button(i18n.t("desktop.menu.help.bristlenoseHelp"), systemImage: "questionmark.circle") {
            Self.open("https://bristlenose.app/docs/")
        }
        .keyboardShortcut("?", modifiers: .command)

        // Re-openable way back to the app-level Welcome home pane. No shortcut —
        // it's a rare, unmemorable destination (per the deliberate no-⌘⇧1 call);
        // discoverability comes from living in Help, not a keybinding. Clears the
        // project selection; ContentView shows WelcomeHomeView on no-selection.
        // Reuses the vetted, all-locale `chrome.welcomeTitle` ("Welcome to
        // Bristlenose") kept from the retired WelcomeView — see
        // docs/design-welcome-screen.md §Copy & i18n; this is now a live reference.
        Button(i18n.t("desktop.chrome.welcomeTitle")) {
            NotificationCenter.default.post(name: .showWelcome, object: nil)
        }

        Button(i18n.t("desktop.menu.help.keyboardShortcuts")) {
            Self.open("https://bristlenose.app/docs/keyboard-shortcuts.html")
        }

        Divider()

        Button(i18n.t("desktop.menu.help.releaseNotes")) {
            Self.open("https://bristlenose.app/docs/changelog.html")
        }

        // Always opens the native FeedbackSheet (report lens, status page, or
        // welcome screen). `openFeedback` posts `.showFeedbackSheet`; ContentView
        // presents it with the live-serve config or the serve-free `.serverless`
        // fallback when no project is selected.
        Button(i18n.t("desktop.menu.help.sendFeedback")) {
            bridgeHandler.openFeedback()
        }

        Divider()

        Button(i18n.t("desktop.menu.help.blog")) {
            bridgeHandler.menuAction("openBlog")
        }

        Button(i18n.t("desktop.menu.help.acknowledgements")) {
            Self.open("https://github.com/cassiocassio/bristlenose/blob/main/ACKNOWLEDGEMENTS.md")
        }
    }

    /// Open an external URL in the system browser, scheme-guarded (defence in
    /// depth — this is the native sink, so it doesn't pass through WebView's
    /// navigation allowlist).
    private static func open(_ string: String) {
        guard let url = URL(string: string),
              let scheme = url.scheme?.lowercased(),
              scheme == "https" || scheme == "http" else { return }
        NSWorkspace.shared.open(url)
    }
}
