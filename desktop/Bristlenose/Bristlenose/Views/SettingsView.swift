import SwiftUI

/// macOS Settings panel for managing the Claude API key.
///
/// Accessible via the standard "Settings..." menu item (Cmd+,).
/// Reads and writes macOS Keychain via `KeychainHelper`.
struct SettingsView: View {
    @State private var currentKey: String = ""
    @State private var newKey: String = ""
    @State private var statusMessage: String?
    @State private var hasKey = false

    var body: some View {
        Form {
            Section("Claude API Key") {
                if hasKey {
                    HStack {
                        Text("Current key:")
                        Text(maskedKey)
                            .font(.system(.body, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Text("No API key configured")
                        .foregroundStyle(.secondary)
                }

                SecureField("New key (sk-ant-...)", text: $newKey)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(.body, design: .monospaced))

                HStack {
                    Button("Save Key") { saveKey() }
                        .disabled(newKey.isEmpty)

                    if hasKey {
                        Button("Delete Key", role: .destructive) { deleteKey() }
                    }
                }

                if let status = statusMessage {
                    Text(status)
                        .font(.caption)
                        .foregroundStyle(status.contains("Saved") ? .green : .red)
                }
            }

            Section {
                Link(
                    "Get a Claude API key",
                    destination: URL(string: "https://console.anthropic.com/settings/keys")!
                )
            }
        }
        .formStyle(.grouped)
        .frame(width: 450, height: 250)
        .onAppear { loadCurrentState() }
    }

    private var maskedKey: String {
        guard currentKey.count > 12 else { return "****" }
        let prefix = String(currentKey.prefix(8))
        let suffix = String(currentKey.suffix(4))
        return "\(prefix)...\(suffix)"
    }

    private func loadCurrentState() {
        if let key = KeychainHelper.get(provider: "anthropic") {
            currentKey = key
            hasKey = true
        } else {
            currentKey = ""
            hasKey = false
        }
    }

    private func saveKey() {
        let trimmed = newKey.trimmingCharacters(in: .whitespacesAndNewlines)

        guard trimmed.hasPrefix("sk-ant-") else {
            statusMessage = "Claude API keys start with sk-ant-"
            return
        }

        if KeychainHelper.set(provider: "anthropic", value: trimmed) {
            statusMessage = "Saved to Keychain"
            newKey = ""
            loadCurrentState()
        } else {
            statusMessage = "Failed to save"
        }
    }

    private func deleteKey() {
        KeychainHelper.delete(provider: "anthropic")
        statusMessage = nil
        loadCurrentState()
    }
}
