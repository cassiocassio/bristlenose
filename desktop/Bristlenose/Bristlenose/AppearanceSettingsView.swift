import SwiftUI

/// Settings tab for appearance and language preferences.
///
/// Appearance choice is injected into the embedded web app via bridge
/// (native wins — web Settings modal hides its own appearance picker
/// in embedded mode).
struct AppearanceSettingsView: View {

    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"
    @AppStorage("language") private var language: String = "en"

    var body: some View {
        Form {
            Section {
                Picker(i18n.t("settings.appearance.legend"), selection: $appearance) {
                    Text(i18n.t("settings.appearance.auto")).tag("auto")
                    Text(i18n.t("settings.appearance.light")).tag("light")
                    Text(i18n.t("settings.appearance.dark")).tag("dark")
                }
                .pickerStyle(.radioGroup)
            }

            Section {
                // Language names are always in their own language (autonyms),
                // not translated — a Spanish speaker needs to recognise "Español"
                // even when the UI is currently in Japanese.
                Picker(i18n.t("settings.language.legend"), selection: $language) {
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
        .onChange(of: language) { _, newValue in
            i18n.setLocale(newValue)
            // VoiceOver language for web content is set via the bridge
            // (syncLocale → HTML lang attribute). Native SwiftUI elements
            // inherit the system language — no per-window override needed.
            // Restart serve to update BRISTLENOSE_WHISPER_LANGUAGE
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }
}
