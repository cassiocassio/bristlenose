import SwiftUI

/// Minimal AppDelegate for future delegate needs.
/// Zombie cleanup uses `.onReceive(willTerminateNotification)` on the root View.
final class AppDelegate: NSObject, NSApplicationDelegate {}

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
    @StateObject private var i18n: I18n = {
        let i = I18n()
        if let dir = I18n.findLocalesDirectory() {
            i.configure(localesDirectory: dir)
        }
        return i
    }()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(serveManager)
                .environmentObject(bridgeHandler)
                .environmentObject(projectIndex)
                .environmentObject(pipelineRunner)
                .environmentObject(toast)
                .environmentObject(i18n)
                .overlay { ToastOverlay().environmentObject(toast) }
                .onAppear {
                    volumeWatcher.projectIndex = projectIndex
                    projectIndex.refreshAvailability()
                    pipelineRunner.setProjectIndex(projectIndex)
                    pipelineRunner.scanAllProjects(projectIndex.projects)
                }
                .onReceive(
                    NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)
                ) { _ in
                    serveManager.stop()
                }
        }
        .defaultSize(width: 1000, height: 700)
        .commands {
            MenuCommands(bridgeHandler: bridgeHandler, serveManager: serveManager, projectIndex: projectIndex, i18n: i18n)
        }

        Settings {
            SettingsView()
                .environmentObject(i18n)
        }
    }
}
