import Foundation
import Security

// MARK: - Protocol

/// Abstraction for credential storage. Production uses macOS Keychain
/// via `KeychainHelper`, tests use `InMemoryKeychain` to avoid touching
/// real credentials.
protocol KeychainStore {
    func get(provider: String) -> String?
    @discardableResult func set(provider: String, value: String) -> Bool
    func delete(provider: String)
}

// MARK: - Real implementation

/// Read, write, and delete API keys in macOS Keychain using native Security.framework.
///
/// Uses the same service names and account as the Python `MacOSCredentialStore`
/// in `bristlenose/credentials_macos.py`, so keys written here are automatically
/// picked up by the sidecar via `_populate_keys_from_keychain()` in `config.py`.
///
/// If service names change in the Python file, they must be updated here too.
///
/// All methods are static for backward compatibility with existing call sites.
/// For protocol-based usage (e.g. dependency injection in tests), use
/// `KeychainHelper.liveStore` which returns a `KeychainStore` instance.
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

    /// A `KeychainStore` backed by the real macOS Keychain.
    static let liveStore: any KeychainStore = LiveKeychain()

    /// Read a key from Keychain. Returns nil if not found.
    static func get(provider: String) -> String? {
        guard let service = serviceNames[provider] else { return nil }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        if status != errSecSuccess && status != errSecItemNotFound {
            logKeychainError("SecItemCopyMatching", status: status)
        }

        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8),
              !value.isEmpty
        else { return nil }

        return value
    }

    /// Write a key to Keychain. Uses add-then-update (atomic, no race window).
    @discardableResult
    static func set(provider: String, value: String) -> Bool {
        guard let service = serviceNames[provider],
              let data = value.data(using: .utf8)
        else { return false }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]

        let attrs: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlocked,
        ]

        // Try add first
        var addQuery = query
        addQuery.merge(attrs) { _, new in new }
        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)

        if addStatus == errSecSuccess { return true }

        if addStatus == errSecDuplicateItem {
            // Already exists — update in place (atomic, no race window)
            let updateStatus = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
            if updateStatus != errSecSuccess {
                logKeychainError("SecItemUpdate", status: updateStatus)
            }
            return updateStatus == errSecSuccess
        }

        logKeychainError("SecItemAdd", status: addStatus)
        return false
    }

    /// Delete a key from Keychain. No-op if not found.
    static func delete(provider: String) {
        guard let service = serviceNames[provider] else { return }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]

        let status = SecItemDelete(query as CFDictionary)
        if status != errSecSuccess && status != errSecItemNotFound {
            logKeychainError("SecItemDelete", status: status)
        }
    }

    /// Check if any usable API key exists across all supported providers.
    /// Checks Keychain + both `BRISTLENOSE_<PROVIDER>_API_KEY` (pydantic-settings
    /// convention) and the bare provider-native env var the SDK would auto-read.
    static func hasAnyAPIKey() -> Bool {
        let env = ProcessInfo.processInfo.environment
        // Providers → provider-native env var name (the one each SDK auto-reads
        // when no explicit key is passed). Keep in sync with pydantic-settings
        // field names in `bristlenose/config.py`.
        let nativeEnvNames = [
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_API_KEY",
            "google": "GOOGLE_API_KEY",
        ]
        for provider in serviceNames.keys {
            if get(provider: provider) != nil { return true }
            let bristlenoseEnv = "BRISTLENOSE_\(provider.uppercased())_API_KEY"
            if let value = env[bristlenoseEnv], !value.isEmpty { return true }
            if let native = nativeEnvNames[provider],
               let value = env[native], !value.isEmpty { return true }
        }
        return false
    }

    // MARK: - Private

    private static func logKeychainError(_ operation: String, status: OSStatus) {
        #if DEBUG
        let message = SecCopyErrorMessageString(status, nil) as String? ?? "unknown"
        print("[KeychainHelper] \(operation) failed: \(status) (\(message))")
        #endif
    }
}

// MARK: - Live store (protocol wrapper around static methods)

/// Thin wrapper that delegates to `KeychainHelper` static methods,
/// conforming to `KeychainStore` for dependency injection.
private struct LiveKeychain: KeychainStore {
    func get(provider: String) -> String? { KeychainHelper.get(provider: provider) }
    @discardableResult func set(provider: String, value: String) -> Bool { KeychainHelper.set(provider: provider, value: value) }
    func delete(provider: String) { KeychainHelper.delete(provider: provider) }
}

// MARK: - In-memory mock (for tests)

/// Dictionary-backed keychain mock. No real Keychain access, no side effects.
/// Uses the same provider validation as `KeychainHelper` (unknown providers return nil/false).
final class InMemoryKeychain: KeychainStore {
    private var storage: [String: String] = [:]

    func get(provider: String) -> String? {
        guard KeychainHelper.serviceNames[provider] != nil else { return nil }
        guard let value = storage[provider], !value.isEmpty else { return nil }
        return value
    }

    @discardableResult
    func set(provider: String, value: String) -> Bool {
        guard KeychainHelper.serviceNames[provider] != nil else { return false }
        storage[provider] = value
        return true
    }

    func delete(provider: String) {
        storage.removeValue(forKey: provider)
    }
}
