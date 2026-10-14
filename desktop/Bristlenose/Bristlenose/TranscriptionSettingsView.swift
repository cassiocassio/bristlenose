import SwiftUI

/// Settings tab for Whisper transcription engine preferences, and for reading
/// the text on screens shared in recordings (the Screens lens).
struct TranscriptionSettingsView: View {

    @EnvironmentObject var i18n: I18n

    @AppStorage("whisperBackend") private var backend: String = "auto"
    // Interim model picker: fix, don't grow (docs/design-pluggable-llm-routing.md §Interim model pickers).
    @AppStorage("whisperModel") private var model: String = "large-v3-turbo"
    @AppStorage(ScreenTextPreference.key)
    private var readSharedScreens: Bool = ScreenTextPreference.defaultValue

    var body: some View {
        Form {
            Section {
                // Help text as an in-cell subtitle (no row keyline) — the
                // System Settings idiom, matching the Appearance toggles.
                Picker(selection: $backend) {
                    Text(i18n.t("desktop.transcriptionSettings.backendAuto")).tag("auto")
                    Text("MLX").tag("mlx")
                    Text("faster-whisper").tag("faster-whisper")
                } label: {
                    Text(i18n.t("desktop.transcriptionSettings.backendLabel"))
                    Text(i18n.t("desktop.transcriptionSettings.backendHint"))
                        .foregroundStyle(.secondary)
                }
            }

            Section {
                Picker(i18n.t("desktop.transcriptionSettings.modelLabel"), selection: $model) {
                    Text(i18n.t(
                        "desktop.transcriptionSettings.modelRecommended",
                        ["model": "large-v3-turbo"]
                    )).tag("large-v3-turbo")
                    Text("large-v3").tag("large-v3")
                    Text("medium").tag("medium")
                    Text("small").tag("small")
                    Text("tiny").tag("tiny")
                }
            }

            // Read shared screens — the Screens lens's on-device reading of the
            // text participants shared on screen. Here rather than General: like
            // the transcription engine above, it turns what the recordings hold
            // into text, on this Mac. On by default (`ScreenTextPreference`).
            Section {
                Toggle(isOn: $readSharedScreens) {
                    Text(i18n.t("desktop.transcriptionSettings.readScreensLabel"))
                    Text(i18n.t("desktop.transcriptionSettings.readScreensHint"))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onChange(of: readSharedScreens) { _, _ in
            // It becomes BRISTLENOSE_SCREEN_TEXT, so the baked env is stale.
            // Off restarts every serve still reading screens, at once
            // (`ServeEnvStaleness`); on stays lazy, like every other preference.
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: backend) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: model) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }
}
