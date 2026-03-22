import SwiftUI

/// Settings tab for appearance and language preferences.
///
/// Appearance choice is injected into the embedded web app via bridge
/// (native wins — web Settings modal hides its own appearance picker
/// in embedded mode).
struct AppearanceSettingsView: View {

    @AppStorage("appearance") private var appearance: String = "auto"
    @AppStorage("language") private var language: String = "en"

    var body: some View {
        Form {
            Section {
                Picker("Appearance", selection: $appearance) {
                    Text("Use system appearance").tag("auto")
                    Text("Light").tag("light")
                    Text("Dark").tag("dark")
                }
                .pickerStyle(.radioGroup)
            }

            Section {
                Picker("Language", selection: $language) {
                    Text("English").tag("en")
                    Text("Español").tag("es")
                    Text("日本語").tag("ja")
                    Text("Français").tag("fr")
                    Text("Deutsch").tag("de")
                    Text("한국어").tag("ko")
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onChange(of: appearance) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }
}
