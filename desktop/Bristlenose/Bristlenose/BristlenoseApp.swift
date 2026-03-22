import SwiftUI

@main
struct BristlenoseApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .defaultSize(width: 1000, height: 700)

        Settings {
            Text("Settings coming soon.")
                .frame(width: 400, height: 200)
        }
    }
}
