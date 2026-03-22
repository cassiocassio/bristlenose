import SwiftUI

/// Top-level Settings window with icon tabs (Apple canonical pattern).
///
/// Three tabs: Appearance, LLM, Transcription.
/// Each tab sets its own frame — the Settings scene resizes automatically.
struct SettingsView: View {

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
                .tabItem { Label("Appearance", systemImage: "paintbrush") }

            LLMSettingsView()
                .tabItem { Label("LLM", systemImage: "brain") }

            TranscriptionSettingsView()
                .tabItem { Label("Transcription", systemImage: "waveform") }
        }
        .preferredColorScheme(colorScheme)
    }
}
