import SwiftUI

@main
struct BristlenoseApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 520, height: 480)

        Settings {
            SettingsView()
        }
    }
}
