import Foundation

/// Read, write, and delete API keys in macOS Keychain using the `security` CLI.
///
/// Uses the same service names and account as the Python `MacOSCredentialStore`
/// in `bristlenose/credentials_macos.py`, so keys written here are automatically
/// picked up by the sidecar via `_populate_keys_from_keychain()` in `config.py`.
///
/// If service names change in the Python file, they must be updated here too.
enum KeychainHelper {

    static let account = "bristlenose"

    /// Provider-to-service-name mapping.
    /// Must match `MacOSCredentialStore.SERVICE_NAMES` in credentials_macos.py.
    static let serviceNames: [String: String] = [
        "anthropic": "Bristlenose Anthropic API Key",
        "openai": "Bristlenose OpenAI API Key",
        "azure": "Bristlenose Azure API Key",
        "google": "Bristlenose Google Gemini API Key",
    ]

    /// Read a key from Keychain. Returns nil if not found.
    static func get(provider: String) -> String? {
        guard let service = serviceNames[provider] else { return nil }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/security")
        proc.arguments = [
            "find-generic-password",
            "-a", account,
            "-s", service,
            "-w",
        ]

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = Pipe()

        do {
            try proc.run()
            proc.waitUntilExit()
            if proc.terminationStatus != 0 { return nil }

            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let value = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
            return (value?.isEmpty == true) ? nil : value
        } catch {
            return nil
        }
    }

    /// Write a key to Keychain. Uses delete-then-add (matching Python implementation).
    @discardableResult
    static func set(provider: String, value: String) -> Bool {
        guard let service = serviceNames[provider] else { return false }

        // Delete existing entry (ignore errors if not found)
        let delProc = Process()
        delProc.executableURL = URL(fileURLWithPath: "/usr/bin/security")
        delProc.arguments = [
            "delete-generic-password",
            "-a", account,
            "-s", service,
        ]
        delProc.standardOutput = Pipe()
        delProc.standardError = Pipe()
        try? delProc.run()
        delProc.waitUntilExit()

        // Add new entry
        let addProc = Process()
        addProc.executableURL = URL(fileURLWithPath: "/usr/bin/security")
        addProc.arguments = [
            "add-generic-password",
            "-a", account,
            "-s", service,
            "-w", value,
            "-U",
        ]
        addProc.standardOutput = Pipe()
        addProc.standardError = Pipe()

        do {
            try addProc.run()
            addProc.waitUntilExit()
            return addProc.terminationStatus == 0
        } catch {
            return false
        }
    }

    /// Delete a key from Keychain. No-op if not found.
    static func delete(provider: String) {
        guard let service = serviceNames[provider] else { return }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/security")
        proc.arguments = [
            "delete-generic-password",
            "-a", account,
            "-s", service,
        ]
        proc.standardOutput = Pipe()
        proc.standardError = Pipe()
        try? proc.run()
        proc.waitUntilExit()
    }

    /// Check if any usable API key exists (Keychain or environment).
    static func hasAnyAPIKey() -> Bool {
        if get(provider: "anthropic") != nil { return true }

        let env = ProcessInfo.processInfo.environment
        if env["ANTHROPIC_API_KEY"] != nil { return true }
        if env["BRISTLENOSE_ANTHROPIC_API_KEY"] != nil { return true }
        return false
    }
}
