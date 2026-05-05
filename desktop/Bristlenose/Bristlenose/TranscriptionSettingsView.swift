import SwiftUI

/// Settings tab for Whisper transcription engine preferences.
struct TranscriptionSettingsView: View {

    @EnvironmentObject var i18n: I18n

    @AppStorage("whisperBackend") private var backend: String = "auto"
    @AppStorage("whisperModel") private var model: String = "large-v3-turbo"

    var body: some View {
        Form {
            Section {
                Picker(i18n.t("desktop.transcriptionSettings.backendLabel"), selection: $backend) {
                    Text(i18n.t("desktop.transcriptionSettings.backendAuto")).tag("auto")
                    Text("MLX").tag("mlx")
                    Text("faster-whisper").tag("faster-whisper")
                }
                Text(i18n.t("desktop.transcriptionSettings.backendHint"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
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
        }
        .formStyle(.grouped)
        .frame(width: 660)
        .onChange(of: backend) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        .onChange(of: model) { _, _ in
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
    }
}
