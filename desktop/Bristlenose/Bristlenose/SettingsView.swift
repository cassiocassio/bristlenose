import SwiftUI

/// Top-level Settings window with icon tabs (Apple canonical pattern).
///
/// Three tabs: Appearance, LLM, Transcription.
/// Each tab sets its own frame — the Settings scene resizes automatically.
struct SettingsView: View {

    @EnvironmentObject var i18n: I18n
    @AppStorage("appearance") private var appearance: String = "auto"

    private var colorScheme: ColorScheme? {
        switch appearance {
        case "light": .light
        case "dark": .dark
        default: nil
        }
    }

    var body: some View {
        TabView {
            AppearanceSettingsView()
                .environmentObject(i18n)
                .tabItem { Label(i18n.t("desktop.settingsTabs.appearance"), systemImage: "paintbrush") }

            LLMSettingsView()
                .tabItem { Label(i18n.t("desktop.settingsTabs.llm"), systemImage: "brain") }

            TranscriptionSettingsView()
                .tabItem { Label(i18n.t("desktop.settingsTabs.transcription"), systemImage: "waveform") }
        }
        .preferredColorScheme(colorScheme)
    }
}
