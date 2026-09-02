import OSLog
import SwiftUI

private let appLog = Logger(subsystem: "app.bristlenose", category: "app")

/// App-lifecycle hooks: launch provenance, the appearance seam, and the
/// Dock-icon reopen. Sidecar teardown on quit is *not* here — `ServeManager`
/// observes termination itself, because it owns the process.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Symmetry with the existing `Mode:` line in ServeManager — this one
        // captures provenance facts known at *build* time so support sessions
        // can disambiguate Debug vs Release archives even when the screenshot
        // doesn't include the diagnostic footer. Sidecar mode is appended
        // when ServeManager finishes its own resolve, so emit "?" here and
        // let the per-launch ServeManager line carry the sidecar slot.
        appLog.info("BuildInfo: \(BuildInfo.current.oneLine(sidecar: "?"), privacy: .public)")

        // One seam for light/dark. Every window, panel, alert, menu and popover
        // the app creates inherits `NSApp.appearance` — so no individual surface
        // has to apply the Settings ▸ Appearance preference itself. See
        // `AppAppearance`. AppKit calls this delegate method on the main thread.
        MainActor.assumeIsolated { AppAppearance.beginApplying() }

        // The expired-alpha `.dmg` block is presented by `AlphaExpiryFlow` as
        // SwiftUI modals over the (serve-less) main window — see ContentView's
        // `.alphaExpiryFlow(...)`. Serve is refused by `ServeManager.start()`'s
        // AlphaBuild guard, so nothing runs behind them. No-op off the alpha
        // channel.
    }

    /// Opens a project window. Set once at launch by the App scene, which is
    /// where `openWindow` is reachable from.
    @MainActor var openProjectWindow: (() -> Void)?

    /// Clicking the Dock icon with no project window open.
    ///
    /// Until 16 Aug 2026 this did nothing: `Window ▸ Bristlenose` was the only
    /// way back, and it has since become `File ▸ New Window`. The menu bar
    /// outlives windows, so that item is still reachable from an empty state —
    /// but the Dock icon is where a Mac user reaches first, and an app that
    /// ignores a click on it reads as hung.
    ///
    /// Asks the roster rather than trusting AppKit's `hasVisibleWindows`, which
    /// counts Settings and the Import window too and would answer "yes, there's
    /// a window" when there is nothing to come back to.
    func applicationShouldHandleReopen(
        _ sender: NSApplication, hasVisibleWindows flag: Bool
    ) -> Bool {
        MainActor.assumeIsolated {
            if !WindowRoster.shared.hasProjectWindow {
                openProjectWindow?()
            }
        }
        return true
    }

    /// Responder-chain entry point for opening Settings. The web bridge
    /// (`BridgeHandler` "open-settings") and the out-of-credit pill call
    /// `NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, ...)`,
    /// which the SwiftUI `Settings {}` scene used to answer. Now that Settings
    /// is an AppKit `SettingsWindowController`, the app delegate answers it —
    /// so those call sites need no change.
    @MainActor
    @objc func showSettingsWindow(_ sender: Any?) {
        SettingsWindow.shared.show()
    }
}

@main
struct BristlenoseApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    /// Handed to the app delegate so a Dock-icon click can open a window when
    /// none is open. `openWindow` is a scene affordance, so this is the only
    /// place that can reach it on the delegate's behalf.
    @Environment(\.openWindow) private var openWindow

    // State lifted from ContentView so .commands and .onReceive can access them.

    /// One serve per project (Stage 3b). Injected alongside `serveManager`
    /// rather than replacing it: the fleet is live and observable, but until
    /// `ContentView` derives its manager from it (§1a-ter A3, which turns
    /// `serveManager` optional) the app still runs the single manager above.
    ///
    /// Additive on purpose. The migration re-derives `applySelectionChange`
    /// from a different premise — a window changing study *observes a different
    /// manager* rather than switching one — and that is a re-write, not a
    /// line-by-line move. Landing the fleet first means the crossing is one
    /// well-scoped change with everything under it already proven.
    @StateObject private var serveFleet = ServeFleet()

    /// Holds the prefs/consent observer that fans out to every sidecar.
    @State private var prefsFanOut: (any NSObjectProtocol)?
    /// Holds the agent-access observer that designates the exposed study.
    @State private var agentAccessFanOut: (any NSObjectProtocol)?
    @StateObject private var projectIndex = ProjectIndex()

    /// Owns the single import window's store. App-level rather than
    /// scene-level: one window globally (§9), so one store, or two windows
    /// would race for the same destination with two tick sets.
    @StateObject private var cloudImport = CloudImportCoordinator()
    @StateObject private var pipelineRunner = PipelineRunner()
    @StateObject private var volumeWatcher = VolumeWatcher()
    @StateObject private var toast = ToastStore()
    @StateObject private var removalStore = UndoableRemovalStore()
    @StateObject private var copyMachinery = CopyMachinery()
    // Ambient local-model pull (Beat 3). Owned at app level so the download
    // survives the consent sheet's dismissal and surfaces in the toolbar pill.
    @StateObject private var ollamaDownload = OllamaDownloadModel()
    // App-global out-of-credit state for the active provider; drives the
    // sibling `.status` toolbar pill (OutOfCreditPill).
    @StateObject private var outOfCredit = OutOfCreditModel()
    @StateObject private var i18n: I18n = {
        let i = I18n()
        if let dir = I18n.findLocalesDirectory() {
            i.configure(localesDirectory: dir)
        }
        return i
    }()

    /// Active palette (Settings ▸ Appearance ▸ Palette). Read here so a
    /// palette-aware `.tint` can propagate through every Scene — otherwise
    /// SwiftUI `.tint` / `.foregroundStyle(.tint)` consumers resolve to
    /// `AccentColor.colorset` (system blue) even under Edo, producing a
    /// visible seam between the sidebar chrome accent and the Edo palette.
    @AppStorage("palette") private var palette: String = "default"

    /// Palette accent as a SwiftUI `Color`, resolved via the asset catalogue
    /// so Xcode picks the Any/Dark variant per effective appearance.
    private var paletteAccent: Color {
        Color("Palette\(palette.capitalized)Accent")
    }

    var body: some Scene {
        // `id` is what `File ▸ New Window` (⌥⌘N) and the Dock-icon reopen both
        // open — `openWindow(id:)` against a `WindowGroup` spawns a window,
        // which is what both of them want.
        WindowGroup(id: "main", for: WindowSeed.self) { $seed in
            // The BINDING, not a snapshot. A window that switches study must
            // write the new one back, or restoration returns it to the study it
            // was *opened* on rather than the one it was showing.
            ContentView(seed: $seed)
                .frame(minWidth: 700, minHeight: 500)
                .environmentObject(serveFleet)
                .environmentObject(projectIndex)
                .environmentObject(pipelineRunner)
                .environmentObject(toast)
                .environmentObject(removalStore)
                .environmentObject(copyMachinery)
                // The main window reads this so a sidebar row can show a cloud
                // batch after the import window is closed. It was already
                // injected into the import scene (:238) and nowhere else — and
                // an `@EnvironmentObject` that is declared but not injected is
                // a **launch crash**, not a nil: SwiftUI traps in
                // `EnvironmentObject.error()` the first time the body reads it.
                .environmentObject(cloudImport)
                .environmentObject(ollamaDownload)
                .environmentObject(outOfCredit)
                .environmentObject(i18n)
                .overlay { ToastOverlay().environmentObject(toast) }
                .onAppear {
                    // The AppKit Settings window is built lazily on first open;
                    // hand it the app's i18n so its SwiftUI panes can translate.
                    SettingsWindow.shared.i18n = i18n
                    // Dock-icon click with no project window open — see
                    // `AppDelegate.applicationShouldHandleReopen`.
                    appDelegate.openProjectWindow = { openWindow(id: "main") }
                    // The MCP Agents pane's live inputs (Now-showing line,
                    // payloads, the agent-access list).
                    SettingsWindow.shared.serveFleet = serveFleet
                    SettingsWindow.shared.projectIndex = projectIndex
                    // What a landed cloud batch is handed to. The coordinator
                    // is the one app-wide owner of the import store, so it is
                    // the only place this can live without a second open window
                    // starting a second run for the same batch.
                    cloudImport.projectIndex = projectIndex
                    cloudImport.pipelineRunner = pipelineRunner
                    volumeWatcher.projectIndex = projectIndex
                    projectIndex.refreshAvailability()
                    // The handshake writer's policy input: which projects have
                    // Agent Access on. A closure, not a stored ProjectIndex —
                    // ServeManager stays ignorant of the sidebar model.
                    // (Both objects are app-lifetime; the capture is benign.)
                    serveFleet.agentAccessResolver = { [weak projectIndex] path in
                        projectIndex?.agentAccess(forPath: path) ?? false
                    }
                    // …and the same permission keyed by id, which is what
                    // `syncHandshake` reads. The path-keyed form resolves
                    // first-match, so two entries whose paths standardise
                    // equal could answer for each other; the Settings register
                    // keys on the id, and the two must read one value.
                    serveFleet.agentAccessByID = { [weak projectIndex] id in
                        projectIndex?.projects.first { $0.id == id }?.agentAccess ?? false
                    }
                    // A sidecar bakes provider, model, key, anonymise and
                    // consent into its environment at spawn. One notification,
                    // N sidecars — the action is a fan-out, not a restart.
                    // Exposure follows turning Agent Access ON — a deliberate
                    // act with a visible control — never fronting a window,
                    // which would silently re-point an external agent at a
                    // different study because someone pressed Cmd-backtick.
                    agentAccessFanOut = NotificationCenter.default.addObserver(
                        forName: .bristlenoseAgentAccessChanged, object: nil, queue: .main
                    ) { note in
                        // The payload is deliberately unread. Scope is derived
                        // from the permission plus the window roster, so the
                        // sweep re-reads every project — which is also what
                        // makes it correct when several change at once. Binding
                        // `id`/`enabled` to silence them was the shape that
                        // left one of the two as a build warning; this target
                        // has no CI, so warnings are its only mechanical signal.
                        Task { @MainActor in
                            serveFleet.syncHandshake()
                        }
                    }
                    prefsFanOut = NotificationCenter.default.addObserver(
                        forName: .bristlenosePrefsChanged, object: nil, queue: .main
                    ) { _ in
                        Task { @MainActor in serveFleet.applyEnvChange() }
                    }
                    pipelineRunner.setProjectIndex(projectIndex)
                    pipelineRunner.scanAllProjects(projectIndex.projects)
                    removalStore.setProjectIndex(projectIndex)
                    // Selection-restore is owned by ContentView (the @State
                    // selection holder); wired via NotificationCenter to keep
                    // the store SwiftUI-free.
                    removalStore.setOnUndo { restoredSelection in
                        NotificationCenter.default.post(
                            name: .undoableRemovalRestoredSelection,
                            object: nil,
                            userInfo: ["selection": restoredSelection]
                        )
                    }
                }
                // (Sidecar teardown on quit moved into `ServeManager`'s own
                // termination observer, 16 Aug 2026. It was here, on a view
                // inside the WindowGroup, so quitting with no window open never
                // ran it — and the serve now deliberately outlives its windows.)
                // Palette-aware SwiftUI accent. Reads `PaletteDefaultAccent` /
                // `PaletteEdoAccent` (see `SidebarPalette` / Assets.xcassets)
                // so every SwiftUI `.tint` consumer downstream — tab labels,
                // toolbar buttons, selection highlights — tracks the palette
                // instead of falling through to the palette-agnostic
                // `AccentColor.colorset`. AppKit chrome (title bar, traffic
                // lights, `NSOutlineView` capsule) still reads system accent —
                // deliberate, per the seam-alignment discipline.
                .tint(paletteAccent)
                // Expired-alpha `.dmg` modal sequence (Expired → feedback sheet
                // → Thanks → quit). No-op unless this is an expired alpha build;
                // i18n + toast passed explicitly (the modifier isn't inside their
                // .environmentObject scope).
                .alphaExpiryFlow(i18n: i18n, toast: toast)
                // Opens the cloud-import scene. Lives here rather than in
                // ContentView so it is alive even with no project selected.
                .modifier(CloudImportOpener(
                    coordinator: cloudImport,
                    projectIndex: projectIndex,
                    selectedProjectID: nil
                ))
        }
        .defaultSize(width: 1000, height: 700)
        .windowResizability(.contentMinSize)
        .commands {
            // No `bridgeHandler` parameter: each window owns its own (Stage
            // 3a), so the menu bar reads the key window's through
            // `@FocusedValue(\.bridge)`. Passing an app-level one here is what
            // made every window show the same lens.
            MenuCommands(serveManager: serveFleet.frontedOrIdle, projectIndex: projectIndex, removalStore: removalStore, i18n: i18n, ollamaDownload: ollamaDownload, cloudImport: cloudImport)
        }
        .commands {
            // The Settings window is an AppKit `SettingsWindowController`
            // (`SettingsWindow` in SettingsView.swift), not a SwiftUI
            // `Settings {}` scene — so we own the App-menu item + Cmd+, that
            // the scene would otherwise provide for free. `showSettingsWindow(_:)`
            // on AppDelegate handles the responder-chain callers (web bridge,
            // out-of-credit pill).
            CommandGroup(replacing: .appSettings) {
                Button(i18n.t("desktop.menu.app.settings")) { SettingsWindow.shared.show() }
                    .keyboardShortcut(",", modifiers: .command)
            }
        }

        // Shipping Shoal animation window (Diagnostics ▸ Shoal Screensaver —
        // Tier U, every channel, beta-era). Animation at defaults only; the
        // tuning harness stays DEBUG ("Shoal Tuner" below). `.commandsRemoved()`
        // is a hard acceptance criterion, not polish: this scene ships, and
        // without it SwiftUI adds a stray Window-menu row to every App Store /
        // TestFlight user even with the Diagnostics toggle off.
        // Cloud import. A WINDOW, not a sheet — Image Capture is the system
        // analogue and it is a window. Mechanically a sheet cannot work here:
        // it is window-modal, so keeping it up would hide the sidebar-row
        // progress behind it, and dismissing it would destroy the per-row
        // outcomes recovery depends on (`docs/design-cloud-import.md` §9).
        //
        // `.commandsRemoved()` for the usual reason — a titled Window scene
        // otherwise contributes an automatic Window-menu reopen entry, and HIG
        // reserves that menu for windows that are *currently open*. Reopening
        // belongs in File, which is where the import item lives.
        Window("Import", id: "cloud-import") {
            CloudImportWindowHost()
                .environmentObject(projectIndex)
                .environmentObject(cloudImport)
                .environmentObject(i18n)
                .tint(paletteAccent)
        }
        .defaultSize(width: 900, height: 560)
        .commandsRemoved()

        Window("Shoal Screensaver", id: "shoal-view") {
            ShoalWindowView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 800, height: 600)
        .commandsRemoved()

        // Shipping Health window (Diagnostics ▸ Check Health — every channel,
        // gated by the Diagnostics preference). Runs the doctor-style local
        // system checks via `GET /api/doctor` and renders them natively. Needs
        // the serve URL + token, so inject the shared ServeManager.
        // `.commandsRemoved()` is a hard requirement (not polish): this is a
        // non-DEBUG titled `Window` scene, so without it SwiftUI leaks a stray
        // Window-menu row to every App Store / TestFlight user even with the
        // Diagnostics toggle off. See desktop/CLAUDE.md "titled Window scenes
        // auto-populate the Window menu".
        Window("System Health", id: "health") {
            DoctorReportView()
                .environmentObject(serveFleet)
                .tint(paletteAccent)
        }
        .defaultSize(width: 480, height: 420)
        .commandsRemoved()

        #if DEBUG
        // DEBUG-only calibration tool — launched from the Diagnostics menu's
        // harness section. Not a shipping surface; the whole TypeParity* file
        // set is #if DEBUG.
        Window("Type Parity Inspector", id: "type-parity") {
            TypeParityView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 1200, height: 820)
        // Debug/diagnostics windows are launched from the Debug menu. Suppress the
        // entry SwiftUI auto-adds to the standard Window menu for every titled
        // `Window` scene — otherwise each doubles up (Window menu + Debug menu).
        // See desktop/CLAUDE.md "titled Window scenes auto-populate the Window menu".
        .commandsRemoved()

        // DEBUG-only Run Inspector — infoviz over the last run's instrumentation,
        // served from `/api/dev/run`. Needs the serve URL + token, so inject the
        // shared ServeManager.
        Window("Run Inspector", id: "run-inspector") {
            RunInspectorView()
                .environmentObject(serveFleet)
                .tint(paletteAccent)
        }
        .defaultSize(width: 1000, height: 720)
        .commandsRemoved()   // no auto Window-menu entry — see Type Parity above

        // DEBUG-only tuning harness for the typographic shoal (sliders, FPS
        // probe, presets). Diagnostics ▸ Shoal Tuner. Distinct from the
        // shipping "Shoal Screensaver" viewer scene above.
        Window("Shoal Tuner", id: "shoal") {
            ShoalDebugView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 800, height: 600)
        .commandsRemoved()   // no auto Window-menu entry — see Type Parity above

        // DEBUG-only "thinking" shimmer tuner — native half of the shimmer spike,
        // mirrors docs/mockups/shimmer-tuner.html. Debug ▸ Shimmer Tuner.
        Window("Shimmer Tuner", id: "shimmer-tuner") {
            ShimmerTunerView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 900, height: 620)
        .commandsRemoved()   // no auto Window-menu entry — see Type Parity above

        // DEBUG-only keycap gallery — native half of "how do we show a key to
        // press?", mirrors docs/mockups/keycap-gallery.html. Debug ▸ Keycap Gallery.
        Window("Keycap Gallery", id: "keycap-gallery") {
            KeycapGalleryView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 680, height: 720)
        .commandsRemoved()   // no auto Window-menu entry — see Type Parity above

        // DEBUG-only degradation rig — how welcome-cell content gives way when
        // the fixed golden slot is too short. Diagnostics ▸ Degradation Lab.
        Window("Degradation Lab", id: "degradation-lab") {
            WelcomeDegradationLab()
                .tint(paletteAccent)
        }
        .defaultSize(width: 1240, height: 900)
        .commandsRemoved()   // no auto Window-menu entry — see Type Parity above

        // DEBUG-only seam laboratory — the join between the AppKit sidebar and
        // the WKWebView. Borrows the fronted project's sidecar so the surface
        // under test is the real one, cycles the candidate CSS treatments as an
        // additive overlay, and reports the live geometry (safe-area inset,
        // visual-effect frames + corner radii) rather than assuming it. Needs
        // the fleet for the serve URL/token and i18n because WebView requires
        // it. Diagnostics ▸ Seam Lab.
        Window("Seam Lab", id: "seam-lab") {
            SeamLabView()
                .environmentObject(serveFleet)
                .environmentObject(i18n)
                .tint(paletteAccent)
        }
        .defaultSize(width: 1100, height: 760)
        .commandsRemoved()   // no auto Window-menu entry — see Type Parity above

        #endif
    }
}
