import OSLog
import SwiftUI

private let appLog = Logger(subsystem: "app.bristlenose", category: "app")

/// Minimal AppDelegate for future delegate needs.
/// Zombie cleanup uses `.onReceive(willTerminateNotification)` on the root View.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Symmetry with the existing `Mode:` line in ServeManager — this one
        // captures provenance facts known at *build* time so support sessions
        // can disambiguate Debug vs Release archives even when the screenshot
        // doesn't include the diagnostic footer. Sidecar mode is appended
        // when ServeManager finishes its own resolve, so emit "?" here and
        // let the per-launch ServeManager line carry the sidecar slot.
        appLog.info("BuildInfo: \(BuildInfo.current.oneLine(sidecar: "?"), privacy: .public)")

        // The expired-alpha `.dmg` block is presented by `AlphaExpiryFlow` as
        // SwiftUI modals over the (serve-less) main window — see ContentView's
        // `.alphaExpiryFlow(...)`. Serve is refused by `ServeManager.start()`'s
        // AlphaBuild guard, so nothing runs behind them. No-op off the alpha
        // channel.
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

    // State lifted from ContentView so .commands and .onReceive can access them.
    @StateObject private var serveManager = ServeManager()
    @StateObject private var bridgeHandler = BridgeHandler()
    @StateObject private var projectIndex = ProjectIndex()
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
        // `id` lets the Window > Bristlenose menu item reopen this scene via
        // `openWindow(id:)` after the user has closed the main window but the
        // app process is still alive (e.g. after a sidecar crash dialog).
        WindowGroup(id: "main") {
            ContentView()
                .frame(minWidth: 700, minHeight: 500)
                .environmentObject(serveManager)
                .environmentObject(bridgeHandler)
                .environmentObject(projectIndex)
                .environmentObject(pipelineRunner)
                .environmentObject(toast)
                .environmentObject(removalStore)
                .environmentObject(copyMachinery)
                .environmentObject(ollamaDownload)
                .environmentObject(outOfCredit)
                .environmentObject(i18n)
                .overlay { ToastOverlay().environmentObject(toast) }
                .overlay { RemoveToast().environmentObject(removalStore).environmentObject(i18n) }
                .onAppear {
                    // The AppKit Settings window is built lazily on first open;
                    // hand it the app's i18n so its SwiftUI panes can translate.
                    SettingsWindow.shared.i18n = i18n
                    // The MCP Agents pane's live inputs (Now-showing line,
                    // payloads, the agent-access list).
                    SettingsWindow.shared.serveManager = serveManager
                    SettingsWindow.shared.projectIndex = projectIndex
                    volumeWatcher.projectIndex = projectIndex
                    projectIndex.refreshAvailability()
                    // The handshake writer's policy input: which projects have
                    // Agent Access on. A closure, not a stored ProjectIndex —
                    // ServeManager stays ignorant of the sidebar model.
                    // (Both objects are app-lifetime; the capture is benign.)
                    serveManager.agentAccessResolver = { [weak projectIndex] path in
                        projectIndex?.agentAccess(forPath: path) ?? false
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
                .onReceive(
                    NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)
                ) { _ in
                    serveManager.stop()
                }
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
        }
        .defaultSize(width: 1000, height: 700)
        .windowResizability(.contentMinSize)
        .commands {
            MenuCommands(bridgeHandler: bridgeHandler, serveManager: serveManager, projectIndex: projectIndex, removalStore: removalStore, i18n: i18n, ollamaDownload: ollamaDownload)
        }
        .commands {
            // The Settings window is an AppKit `SettingsWindowController`
            // (`SettingsWindow` in SettingsView.swift), not a SwiftUI
            // `Settings {}` scene — so we own the App-menu item + Cmd+, that
            // the scene would otherwise provide for free. `showSettingsWindow(_:)`
            // on AppDelegate handles the responder-chain callers (web bridge,
            // out-of-credit pill).
            CommandGroup(replacing: .appSettings) {
                Button("Settings…") { SettingsWindow.shared.show() }
                    .keyboardShortcut(",", modifiers: .command)
            }
        }

        // Shipping Shoal animation window (Diagnostics ▸ Shoal Screensaver —
        // Tier U, every channel, beta-era). Animation at defaults only; the
        // tuning harness stays DEBUG ("Shoal Tuner" below). `.commandsRemoved()`
        // is a hard acceptance criterion, not polish: this scene ships, and
        // without it SwiftUI adds a stray Window-menu row to every App Store /
        // TestFlight user even with the Diagnostics toggle off.
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
                .environmentObject(serveManager)
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
                .environmentObject(serveManager)
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
        #endif
    }
}
