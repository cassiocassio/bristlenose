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
        }
        .defaultSize(width: 1000, height: 700)
        .windowResizability(.contentMinSize)
        .commands {
            MenuCommands(bridgeHandler: bridgeHandler, serveManager: serveManager, projectIndex: projectIndex, removalStore: removalStore, i18n: i18n, ollamaDownload: ollamaDownload)
        }

        Settings {
            SettingsView()
                .environmentObject(i18n)
        }

        #if DEBUG
        // DEBUG-only calibration tool — launched from the Debug menu. Not a
        // shipping surface; the whole TypeParity* file set is #if DEBUG.
        Window("Type Parity Inspector", id: "type-parity") {
            TypeParityView()
        }
        .defaultSize(width: 1200, height: 820)
        #endif
    }
}
