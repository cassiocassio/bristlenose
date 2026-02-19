import SwiftUI

/// First-run onboarding screen shown when no API key is configured.
///
/// Prompts the user to paste their Claude API key, validates the format,
/// and stores it in macOS Keychain via `KeychainHelper`.
struct SetupView: View {
    var onComplete: () -> Void

    @State private var apiKey = ""
    @State private var errorMessage: String?
    @State private var isSaving = false

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            Text("Welcome to Bristlenose")
                .font(.largeTitle)
                .fontWeight(.semibold)

            Text("To analyse interviews, you need a Claude API key.")
                .foregroundStyle(.secondary)

            // API key input
            VStack(alignment: .leading, spacing: 8) {
                SecureField("sk-ant-...", text: $apiKey)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: 400)
                    .onSubmit { saveKey() }

                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                }
            }

            // Save button
            Button(action: saveKey) {
                if isSaving {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    Text("Save and Continue")
                }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(apiKey.isEmpty || isSaving)

            // Help text
            VStack(spacing: 4) {
                Link(
                    "Get a Claude API key at console.anthropic.com",
                    destination: URL(string: "https://console.anthropic.com/settings/keys")!
                )
                .font(.callout)

                Text("Your key is stored in macOS Keychain, never sent anywhere except Anthropic.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }

            Spacer()
        }
        .frame(minWidth: 480)
        .padding()
    }

    private func saveKey() {
        let trimmed = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !trimmed.isEmpty else { return }

        guard trimmed.hasPrefix("sk-ant-") else {
            errorMessage = "Claude API keys start with sk-ant-"
            return
        }

        guard trimmed.count > 20 else {
            errorMessage = "That key looks too short. Paste the full key from console.anthropic.com"
            return
        }

        errorMessage = nil
        isSaving = true

        let success = KeychainHelper.set(provider: "anthropic", value: trimmed)
        isSaving = false

        if success {
            onComplete()
        } else {
            errorMessage = "Failed to save to Keychain. Check System Settings > Privacy & Security."
        }
    }
}
