import SwiftUI

/// Settings tab for Whisper transcription engine preferences.
struct TranscriptionSettingsView: View {

    @AppStorage("whisperBackend") private var backend: String = "auto"
    @AppStorage("whisperModel") private var model: String = "large-v3-turbo"

    var body: some View {
        Form {
            Section {
                Picker("Backend", selection: $backend) {
                    Text("Auto").tag("auto")
                    Text("MLX").tag("mlx")
                    Text("faster-whisper").tag("faster-whisper")
                }
                Text("Auto detects the best engine for your Mac.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section {
                Picker("Model", selection: $model) {
                    Text("large-v3-turbo (recommended)").tag("large-v3-turbo")
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
