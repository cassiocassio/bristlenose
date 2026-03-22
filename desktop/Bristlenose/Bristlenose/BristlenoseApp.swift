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

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(serveManager)
                .environmentObject(bridgeHandler)
                .onReceive(
                    NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)
                ) { _ in
                    serveManager.stop()
                }
        }
        .defaultSize(width: 1000, height: 700)
        .commands {
            MenuCommands(bridgeHandler: bridgeHandler, serveManager: serveManager)
        }

        Settings {
            SettingsView()
        }
    }
}
