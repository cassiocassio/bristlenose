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
                .environmentObject(i18n)
                .overlay { ToastOverlay().environmentObject(toast) }
                .overlay { RemoveToast().environmentObject(removalStore).environmentObject(i18n) }
                .onAppear {
                    volumeWatcher.projectIndex = projectIndex
                    projectIndex.refreshAvailability()
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

        Settings {
            SettingsView()
                .environmentObject(i18n)
                // Every SwiftUI Scene needs its own `.tint` — the modifier
                // applied to WindowGroup(id: "main") doesn't propagate across
                // scene boundaries. Without this, the Settings toggles and tab
                // icons stay `AccentColor.colorset` system blue even under Edo.
                .tint(paletteAccent)
        }

        #if DEBUG
        // DEBUG-only calibration tool — launched from the Debug menu. Not a
        // shipping surface; the whole TypeParity* file set is #if DEBUG.
        Window("Type Parity Inspector", id: "type-parity") {
            TypeParityView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 1200, height: 820)

        // DEBUG-only Run Inspector — infoviz over the last run's instrumentation,
        // served from `/api/dev/run`. Needs the serve URL + token, so inject the
        // shared ServeManager.
        Window("Run Inspector", id: "run-inspector") {
            RunInspectorView()
                .environmentObject(serveManager)
                .tint(paletteAccent)
        }
        .defaultSize(width: 1000, height: 720)

        // DEBUG-only viewing harness for the resurrected typographic shoal
        // (v0.1 canned WordPool, no live data). Debug ▸ Shoal Screensaver.
        Window("Shoal Screensaver", id: "shoal") {
            ShoalDebugView()
                .tint(paletteAccent)
        }
        .defaultSize(width: 800, height: 600)
        #endif
    }
}
