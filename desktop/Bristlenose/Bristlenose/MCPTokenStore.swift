import CryptoKit
import Foundation
import os
import Security

/// A stable per-project bearer token for the sidecar's MCP endpoint.
///
/// **Why this exists.** `create_app` mints a fresh `secrets.token_urlsafe(32)`
/// on every start *unless* `_BRISTLENOSE_AUTH_TOKEN` is already in the
/// environment (the path that keeps `uvicorn --reload` continuous). The CLI
/// takes the rotating token and asks the researcher to re-paste after a
/// restart — acceptable in a terminal, where the new token is printed right
/// in front of them. In the app it would be a defect they meet weekly: the
/// config they pasted into Claude Desktop on Monday 401s on Tuesday.
///
/// So the host mints the token instead, once per project, and injects it.
/// Nothing on the Python side changes — this rides a documented, existing
/// mechanism. See `docs/design-mcp-server.md` §6/§10 Q2.
///
/// **Scope is per project, deliberately.** The connect sheet grants access to
/// one project; a token that spanned projects would silently widen that grant
/// when the researcher switched. Rotating a single project's token (Revoke)
/// must not break the others.
///
/// **Storage.** macOS Keychain, same data-protection attributes as
/// `KeychainHelper` (own service name, project id as the account). Not
/// `UserDefaults` — that is a world-readable plist, and while this token is a
/// localhost speed bump rather than an authentication boundary (SECURITY.md),
/// it is still a credential the researcher pastes into another application.
///
/// **Not synchronizable.** Unlike provider API keys, this token names a server
/// on *this* machine; syncing it to another Mac via iCloud Keychain would
/// propagate a credential that is meaningless there.
enum MCPTokenStore {

    private static let service = "Bristlenose MCP Token"
    private static let log = Logger(subsystem: "app.bristlenose", category: "mcp")

    /// Return this project's token, minting and storing one on first use.
    ///
    /// Keyed by the project's **resolved path**, which is how `ServeManager`
    /// identifies a project — and how the Python importer does too (it matches
    /// via `os.path.samefile`, per `bristlenose/server/CLAUDE.md`). Consequence
    /// worth knowing: moving a project folder mints a new token, so agent
    /// configs pasted before the move stop working. That is the honest
    /// behaviour — the alternative is a token that follows a folder the
    /// researcher may have moved deliberately.
    ///
    /// Returns `nil` only if the Keychain refuses to store — in which case
    /// the caller mints an ephemeral scoped token via `mintEphemeral()`
    /// (NEVER the sidecar's unscoped rotating token — that one opens
    /// `/api/*` and the handshake file publishes whatever the caller
    /// holds). MCP still works; only durability across restarts is lost.
    static func token(forProjectPath path: String) -> String? {
        let account = accountKey(for: path)
        if let existing = read(account: account) { return existing }
        let minted = mint()
        guard write(account: account, value: minted) else {
            log.error("could not persist the MCP token — falling back to the sidecar's rotating token")
            return nil
        }
        log.info("minted a stable MCP token for this project")
        return minted
    }

    /// A process-lifetime scoped token for when the Keychain refuses to
    /// store (always on ad-hoc builds, -34018). Same shape and entropy as
    /// the durable one; nothing downstream can tell them apart. Exists so
    /// `ServeManager` NEVER falls back to the unscoped server token — the
    /// handshake file and the Connect sheet must only ever carry a
    /// credential that opens `/mcp` and nothing else (design §3.1).
    static func mintEphemeral() -> String { mint() }

    /// Discard this project's token. The next serve start mints a fresh one,
    /// which is exactly what "Revoke" means to the researcher: previously
    /// pasted agent configs stop working.
    static func revoke(forProjectPath path: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: accountKey(for: path),
            kSecUseDataProtectionKeychain as String: true,
            kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
        ]
        let status = SecItemDelete(query as CFDictionary)
        if status != errSecSuccess && status != errSecItemNotFound {
            log.error("MCP token delete failed: \(status, privacy: .public)")
        }
    }

    // MARK: - Internals

    /// SHA-256 of the standardised path. Hashed rather than stored raw so a
    /// client's folder name (`~/Clients/Acme/…`) never becomes Keychain item
    /// metadata, which is readable without unlocking the item's data.
    static func accountKey(for path: String) -> String {
        let standardised = URL(fileURLWithPath: path).standardizedFileURL.path
        let digest = SHA256.hash(data: Data(standardised.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    /// 32 random bytes, URL-safe base64 — the same shape and entropy as the
    /// Python side's `secrets.token_urlsafe(32)`, so nothing downstream can
    /// tell which end minted it.
    private static func mint() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        if SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) != errSecSuccess {
            // SecRandom does not fail in practice; if it ever does, fall back
            // (UUIDs are CSPRNG-backed on Apple platforms) — loudly, so the
            // "does not fail" claim stays checkable.
            log.fault("SecRandomCopyBytes failed — minting from UUID fallback")
            return UUID().uuidString + UUID().uuidString
        }
        return Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    private static func read(account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecUseDataProtectionKeychain as String: true,
            kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess,
              let data = item as? Data,
              let value = String(data: data, encoding: .utf8),
              !value.isEmpty
        else {
            if status != errSecItemNotFound {
                log.error("MCP token read failed: \(status, privacy: .public)")
            }
            return nil
        }
        return value
    }

    private static func write(account: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecUseDataProtectionKeychain as String: true,
            kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
        ]
        let attrs: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
            kSecAttrSynchronizable as String: false,
        ]
        var addQuery = query
        addQuery.merge(attrs) { _, new in new }
        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
        if addStatus == errSecSuccess { return true }
        if addStatus == errSecDuplicateItem {
            let updateStatus = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
            if updateStatus != errSecSuccess {
                log.error("MCP token update failed: \(updateStatus, privacy: .public)")
            }
            return updateStatus == errSecSuccess
        }
        log.error("MCP token write failed: \(addStatus, privacy: .public)")
        return false
    }
}
