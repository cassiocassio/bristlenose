import Foundation
import OSLog
import Security

// MARK: - Protocol

/// Abstraction for credential storage. Production uses macOS Keychain
/// via `KeychainHelper`, tests use `InMemoryKeychain` to avoid touching
/// real credentials.
///
/// **The account string is a second axis, and it is load-bearing for cloud
/// sign-ins.** An LLM provider key is one per provider, so it lives at the fixed
/// `KeychainHelper.account` — and it must, because the Python side reads it
/// there (`credentials_macos.py`). A cloud sign-in is one per *account*: a
/// consultant has a personal Microsoft account and one per client. Stored at a
/// fixed account string the second sign-in takes `SecItemUpdate` and overwrites
/// the first in place — no error, `set` returns `true`, and the first account
/// stops working at its next refresh with nothing anywhere saying why.
///
/// So the account-bearing methods are the real ones and the fixed-account
/// convenience forms below delegate to them.
protocol KeychainStore {
    func get(provider: String, account: String) -> String?
    @discardableResult func set(provider: String, account: String, value: String) -> Bool
    func delete(provider: String, account: String)
    /// Every account string currently holding an item for this provider.
    ///
    /// The enumeration half of per-account storage: without it a caller can
    /// read a key it already knows but can never discover what is stored, which
    /// is what a list of connected accounts is made of.
    func accounts(provider: String) -> [String]
}

extension KeychainStore {
    func get(provider: String) -> String? {
        get(provider: provider, account: KeychainHelper.account)
    }

    @discardableResult
    func set(provider: String, value: String) -> Bool {
        set(provider: provider, account: KeychainHelper.account, value: value)
    }

    func delete(provider: String) {
        delete(provider: provider, account: KeychainHelper.account)
    }
}

// MARK: - Real implementation

/// Read, write, and delete credentials in the macOS Keychain via Security.framework.
///
/// **A provider key lives in two keychains, and this type keeps them agreeing.**
/// The app's own store is the data-protection keychain: iCloud-synced, scoped to
/// the `keychain-access-groups` entitlement, silent to read across rebuilds. The
/// CLI cannot see it — `/usr/bin/security` searches only the file-based login
/// keychain, and even a Security.framework caller without our access group gets
/// `errSecItemNotFound` (measured 4 Sep 2026, `docs/design-keychain.md`). So every
/// key the CLI also reads — `sharedWithCLI` — is kept in the login keychain as
/// well, at exactly the service and account `bristlenose configure` writes, and
/// `get` reconciles the two copies whenever either has moved. The rule and its
/// prompt budget are on `SharedKeychainItem`. Cloud sign-ins, and anything at a
/// derived account, are Swift-only and stay in the synced keychain alone.
///
/// Uses the same service names and account as the Python `MacOSCredentialStore`
/// in `bristlenose/credentials_macos.py`, so keys written here are picked up by
/// the sidecar via `_populate_keys_from_keychain()` in `config.py` — and, since
/// the login copy, by a plain `bristlenose run` in a terminal.
///
/// If service names change in the Python file, they must be updated here too.
///
/// All methods are static for backward compatibility with existing call sites.
/// For protocol-based usage (e.g. dependency injection in tests), use
/// `KeychainHelper.liveStore` which returns a `KeychainStore` instance.
enum KeychainHelper {

    fileprivate static let log = Logger(subsystem: "app.bristlenose", category: "keychain")

    static let account = "bristlenose"

    /// Provider-to-service-name mapping.
    /// Must match `MacOSCredentialStore.SERVICE_NAMES` in credentials_macos.py.
    static let serviceNames: [String: String] = [
        "anthropic": "Bristlenose Anthropic API Key",
        "openai": "Bristlenose OpenAI API Key",
        "azure": "Bristlenose Azure API Key",
        "google": "Bristlenose Google Gemini API Key",
        "miro": "Bristlenose Miro Access Token",
        // Cloud import sign-ins. **This map is an allowlist, not a naming
        // convention** — `get` and `set` both `guard let service =
        // serviceNames[provider]` and bail, so an unregistered key reads nil
        // and writes false, silently. A store built on an unregistered key
        // looks entirely correct and persists nothing.
        "cloud-google-meet": "Bristlenose Google Meet Sign-In",
        "cloud-microsoft-teams": "Bristlenose Microsoft Teams Sign-In",
        // Registered while Zoom's menu item is still parked
        // (`BristlenoseFlags.cloudImportZoom`), deliberately. The entry costs
        // nothing when nothing writes to it, and its absence is invisible: an
        // unregistered provider persists nothing and reports no error, so the
        // defect surfaces as "why am I signing in again?" months later. Pinned
        // by `CloudGrantKeychainRegistrationTests`, beside the other two.
        "cloud-zoom": "Bristlenose Zoom Sign-In",
    ]

    /// The keys the CLI reads too — and therefore the ones kept in **two**
    /// keychains. Exactly the keys of `MacOSCredentialStore.SERVICE_NAMES`
    /// (`credentials_macos.py`); `tests/test_swift_python_contract.py` fails if
    /// the two sets drift, because a key Python reads that is not mirrored is
    /// invisible to `bristlenose run` the moment it is saved in the app.
    static let sharedWithCLI: Set<String> = ["anthropic", "openai", "azure", "google", "miro"]

    /// A `KeychainStore` backed by the real macOS Keychain.
    static let liveStore: any KeychainStore = LiveKeychain()

    /// **Under a test host, the live statics never reach the real keychain.**
    /// The test bundle runs inside the real app, so a test that renders a view
    /// reaches this type's statics — the convention "tests use `InMemoryKeychain`"
    /// cannot reach a static a view calls. On 4 Sep 2026 `SettingsRefitTests`
    /// rendered `LLMSettingsView` to measure it, the pane read CLI-created login
    /// items with interaction allowed (three dialogs, answered by hand, one
    /// eleven minutes later), and its focus handler wrote the Gemini key back
    /// into the developer's keychain. Detected by the XCTest harness the host is
    /// launched under; production never carries those. Both raw keychains and the
    /// reconciler's ledger swap to volatile stand-ins, and `accounts` enumerates
    /// nothing. `KeychainHelperTests` pins this by type, without a single write.
    static let isUnderTestHost: Bool = {
        let env = ProcessInfo.processInfo.environment
        return env["XCTestConfigurationFilePath"] != nil
            || env["XCTestBundlePath"] != nil
            || env["XCTestSessionIdentifier"] != nil
            || NSClassFromString("XCTestCase") != nil
    }()

    /// The app's own store: the data-protection keychain, iCloud-synced.
    static let syncedKeychain: any RawKeychain =
        isUnderTestHost ? InMemoryRawKeychain() : DataProtectionKeychain()

    /// The file-based login keychain — the one `/usr/bin/security` reads.
    static let loginKeychain: any RawKeychain =
        isUnderTestHost ? InMemoryRawKeychain() : LoginKeychain()

    /// Where `SharedKeychainItem` keeps its ledger. A throwaway suite under a
    /// test host, so a test cannot leave the real app a ledger about keychains
    /// that only existed in memory.
    static let ledgerDefaults: UserDefaults = {
        guard isUnderTestHost else { return .standard }
        let name = "app.bristlenose.test-ledger"
        let suite = UserDefaults(suiteName: name)!
        suite.removePersistentDomain(forName: name)
        return suite
    }()

    private static func isSharedWithCLI(provider: String, account: String) -> Bool {
        account == KeychainHelper.account && sharedWithCLI.contains(provider)
    }

    /// Read a key from Keychain. Returns nil if not found.
    ///
    /// `account` defaults to the fixed string the LLM provider keys use. Cloud
    /// sign-ins pass a per-account key instead — see `KeychainStore`.
    ///
    /// **Quiet by default.** A read can reach a login-keychain item that
    /// `bristlenose configure` created, and decrypting one of those the first
    /// time is a system dialog — which, from a spawn path or a launch-time
    /// model, blocks the app on it (the test host hung on exactly that, 4 Sep
    /// 2026). So the default forbids the dialog and reports the app's own copy;
    /// only Settings ▸ LLM Provider passes `.allowed`, and that is where a CLI
    /// key is adopted. See `KeychainInteraction`.
    static func get(provider: String,
                    account: String = KeychainHelper.account,
                    interaction: KeychainInteraction = .quiet) -> String? {
        guard let service = serviceNames[provider] else { return nil }
        if isSharedWithCLI(provider: provider, account: account) {
            return SharedKeychainItem.read(service: service, account: account,
                                           synced: syncedKeychain, login: loginKeychain,
                                           interaction: interaction, defaults: ledgerDefaults)
        }
        return syncedKeychain.read(service: service, account: account, interaction: interaction).value
    }

    /// Write a key to Keychain, and read it back. `true` only if it round-tripped.
    ///
    /// The synced copy is stored with `kSecUseDataProtectionKeychain` +
    /// `kSecAttrSynchronizable` — see `DataProtectionKeychain`. A key the CLI
    /// shares is written to the login keychain as well — see `SharedKeychainItem`.
    @discardableResult
    static func set(provider: String,
                    account: String = KeychainHelper.account,
                    value: String,
                    interaction: KeychainInteraction = .allowed) -> Bool {
        guard let service = serviceNames[provider] else { return false }
        if isSharedWithCLI(provider: provider, account: account) {
            return SharedKeychainItem.write(service: service, account: account, value: value,
                                            synced: syncedKeychain, login: loginKeychain,
                                            interaction: interaction, defaults: ledgerDefaults)
        }
        guard syncedKeychain.write(service: service, account: account, value: value,
                                   interaction: interaction) else {
            return false
        }
        // A clean return is not evidence anything was stored — read it back.
        return syncedKeychain.read(service: service, account: account,
                                   interaction: interaction).value == value
    }

    /// Delete a key from Keychain. No-op if not found.
    static func delete(provider: String,
                       account: String = KeychainHelper.account,
                       interaction: KeychainInteraction = .allowed) {
        guard let service = serviceNames[provider] else { return }
        if isSharedWithCLI(provider: provider, account: account) {
            SharedKeychainItem.remove(service: service, account: account,
                                      synced: syncedKeychain, login: loginKeychain,
                                      interaction: interaction, defaults: ledgerDefaults)
            return
        }
        syncedKeychain.delete(service: service, account: account, interaction: interaction)
    }

    /// Every account string currently holding an item for this provider.
    ///
    /// Synced keychain only: the per-account classes are Swift-only, and the
    /// login copies of the shared keys all sit at the one fixed account.
    static func accounts(provider: String) -> [String] {
        guard let service = serviceNames[provider], !isUnderTestHost else { return [] }
        return DataProtectionKeychain().accounts(service: service)
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

    /// **Not `#if DEBUG`.** A Keychain read that fails returns nil, and an
    /// enumeration that fails returns `[]` — which the Accounts pane renders as
    /// "Not connected" while live grants sit on disk, inviting a re-sign-in
    /// nobody needed. Without a line here that state is unfalsifiable on a
    /// tester's machine, and the cohort is people you cannot screen-share with
    /// on demand. The `OSStatus` is not sensitive; nothing else is logged.
    fileprivate static func logKeychainError(_ operation: String, status: OSStatus) {
        let message = SecCopyErrorMessageString(status, nil) as String? ?? "unknown"
        log.error("\(operation, privacy: .public) failed: \(status, privacy: .public) (\(message, privacy: .public))")
    }
}

// MARK: - Raw keychains

/// Whether a keychain operation may put a dialog on screen.
///
/// The data-protection keychain never asks. The login keychain asks the first
/// time this app decrypts an item another tool created — one `bristlenose
/// configure` wrote — and it asks the *process*: a read from a spawn path or a
/// launch-time model blocks the app on the dialog. `quiet` forbids it for the
/// duration of the call (`SecKeychainSetUserInteractionAllowed(false)`; the
/// per-query `kSecUseAuthenticationUI` key does not reach legacy items — SecItem.h
/// says so) and the read reports `wouldPrompt` instead. Measured 4 Sep 2026: a
/// foreign item under the toggle returns `-25293` and shows nothing. `allowed`
/// is for the one place a person is looking — Settings ▸ LLM Provider.
enum KeychainInteraction { case quiet, allowed }

/// What a raw read found.
enum RawRead: Equatable {
    case found(String)
    case missing
    /// The item exists but decrypting it would ask the user, and asking was
    /// forbidden. Not a refusal: ask again from a place that may.
    case wouldPrompt
    /// Asked and declined, a locked keychain, or any other refusal.
    case refused

    var value: String? {
        if case .found(let value) = self { return value }
        return nil
    }
}

/// One physical keychain, addressed without policy: no allowlist, no
/// reconciliation, no read-back. Two live implementations — the data-protection
/// keychain and the file-based login keychain — and one in-memory fake.
protocol RawKeychain {
    /// When the item was last written. Attributes only: never decrypts, so never
    /// prompts. `nil` when there is no such item.
    func modificationDate(service: String, account: String) -> Date?
    /// The secret, decrypted. Empty counts as `missing`.
    func read(service: String, account: String, interaction: KeychainInteraction) -> RawRead
    /// Replace the item. `false` on refusal — never a throw, so a caller reads back.
    @discardableResult
    func write(service: String, account: String, value: String,
               interaction: KeychainInteraction) -> Bool
    func delete(service: String, account: String, interaction: KeychainInteraction)
}

/// The data-protection keychain: iCloud-synced, entitlement-scoped, prompt-free.
///
/// Items are stored with `kSecUseDataProtectionKeychain` + `kSecAttrSynchronizable`,
/// so they sync across the user's Macs via iCloud Keychain (when it's enabled; they
/// stay local silently otherwise) and survive a damaged login keychain — the
/// data-protection partition is separate from the file-based login keychain.
/// Accessibility is `kSecAttrAccessibleAfterFirstUnlock` (sync-compatible;
/// `*ThisDeviceOnly` classes can't sync). NO biometric `SecAccessControl`: it is
/// mutually exclusive with sync, and would prompt Touch ID on every headless
/// sidecar read. A deliberate Touch ID gate lives at the app level on the
/// reveal/edit action instead. The `keychain-access-groups` entitlement (Keychain
/// Sharing capability) is required for the data-protection keychain under App
/// Sandbox — see docs/private/handoffs/keychain-sandbox-entitlement.md.
struct DataProtectionKeychain: RawKeychain {

    /// Base match query — `kSecAttrSynchronizableAny` so every operation finds a
    /// pre-existing item regardless of its sync flag. Without it a default query
    /// only matches non-synchronizable items, so synced keys would be invisible.
    private func query(service: String, account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecUseDataProtectionKeychain as String: true,
            kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
        ]
    }

    func modificationDate(service: String, account: String) -> Date? {
        var q = query(service: service, account: account)
        q[kSecReturnAttributes as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        if status != errSecSuccess && status != errSecItemNotFound {
            KeychainHelper.logKeychainError("SecItemCopyMatching (synced attributes)", status: status)
        }
        guard status == errSecSuccess, let attrs = result as? [String: Any] else { return nil }
        return attrs[kSecAttrModificationDate as String] as? Date
    }

    /// `interaction` is accepted for the protocol and ignored: this keychain
    /// validates by Team ID and never asks.
    func read(service: String, account: String, interaction: KeychainInteraction) -> RawRead {
        var q = query(service: service, account: account)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        switch status {
        case errSecSuccess:
            guard let data = result as? Data,
                  let value = String(data: data, encoding: .utf8),
                  !value.isEmpty
            else { return .missing }
            return .found(value)
        case errSecItemNotFound:
            return .missing
        default:
            KeychainHelper.logKeychainError("SecItemCopyMatching", status: status)
            return .refused
        }
    }

    @discardableResult
    func write(service: String, account: String, value: String,
               interaction: KeychainInteraction) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        let q = query(service: service, account: account)
        let attrs: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
            kSecAttrSynchronizable as String: true,
        ]

        // Try add first
        var addQuery = q
        addQuery.merge(attrs) { _, new in new }
        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)

        if addStatus == errSecSuccess { return true }

        if addStatus == errSecDuplicateItem {
            // Already exists — update in place (atomic, no race window).
            let updateStatus = SecItemUpdate(q as CFDictionary, attrs as CFDictionary)
            if updateStatus == errSecSuccess { return true }
            if updateStatus == errSecAuthFailed {
                // ACL of a pre-existing entry can't be satisfied — e.g. a
                // biometric item left by an older build, or a locked keychain.
                // Distinct log line so this is greppable from Console.app.
                KeychainHelper.logKeychainError("SecItemUpdate (auth failed)", status: updateStatus)
            } else {
                KeychainHelper.logKeychainError("SecItemUpdate", status: updateStatus)
            }
            return false
        }

        KeychainHelper.logKeychainError("SecItemAdd", status: addStatus)
        return false
    }

    func delete(service: String, account: String, interaction: KeychainInteraction) {
        let status = SecItemDelete(query(service: service, account: account) as CFDictionary)
        if status != errSecSuccess && status != errSecItemNotFound {
            KeychainHelper.logKeychainError("SecItemDelete", status: status)
        }
    }

    /// Every account string currently holding an item for this service.
    ///
    /// `kSecMatchLimitAll` + `kSecReturnAttributes` — attributes, deliberately
    /// **not** `kSecReturnData`: enumerating is a question about which accounts
    /// exist, and answering it should not decrypt every stored credential to
    /// find out. Callers read the ones they need afterwards.
    ///
    /// Sorted, so the order is at least stable. Keychain's own is not specified,
    /// and a list of accounts that shuffles between openings looks broken.
    func accounts(service: String) -> [String] {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecUseDataProtectionKeychain as String: true,
            kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
            kSecMatchLimit as String: kSecMatchLimitAll,
            kSecReturnAttributes as String: true,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        if status != errSecSuccess && status != errSecItemNotFound {
            KeychainHelper.logKeychainError("SecItemCopyMatching (all)", status: status)
        }
        guard status == errSecSuccess, let items = result as? [[String: Any]] else { return [] }
        return items.compactMap { $0[kSecAttrAccount as String] as? String }.sorted()
    }
}

/// The file-based login keychain — where `bristlenose configure` writes and
/// `bristlenose run` reads, through `/usr/bin/security`.
///
/// A query with neither `kSecUseDataProtectionKeychain` nor `kSecAttrSynchronizable`
/// is what routes to the file-based keychains, and the default keychain there is
/// `login` — the same search list `security` uses. Items are bound by ACL to the
/// application that created them, which is the difference from the synced
/// keychain that matters here: reading a CLI-created item from the app, or an
/// app-created item from `security`, is the system's one-time "wants to use your
/// confidential information" dialog, and Always Allow ends it for that item.
///
/// **Every call runs on one serial queue under the process-wide interaction
/// toggle** for its `KeychainInteraction`, restored to allowed afterwards, so a
/// quiet call on one thread cannot silence an allowed one on another.
struct LoginKeychain: RawKeychain {

    private static let queue = DispatchQueue(label: "app.bristlenose.login-keychain")

    /// Not re-entrant: a body must not call another `perform`. `write` folds
    /// its delete in for that reason.
    private static func perform<T>(_ interaction: KeychainInteraction, _ body: () -> T) -> T {
        queue.sync {
            legacyKeychainUI.setUserInteractionAllowed(interaction == .allowed)
            defer { legacyKeychainUI.setUserInteractionAllowed(true) }
            return body()
        }
    }

    private func query(service: String, account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    func modificationDate(service: String, account: String) -> Date? {
        var q = query(service: service, account: account)
        q[kSecReturnAttributes as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(q as CFDictionary, &result)
        if status != errSecSuccess && status != errSecItemNotFound {
            KeychainHelper.logKeychainError("SecItemCopyMatching (login attributes)", status: status)
        }
        guard status == errSecSuccess, let attrs = result as? [String: Any] else { return nil }
        return attrs[kSecAttrModificationDate as String] as? Date
    }

    func read(service: String, account: String, interaction: KeychainInteraction) -> RawRead {
        Self.perform(interaction) {
            var q = query(service: service, account: account)
            q[kSecReturnData as String] = true
            q[kSecMatchLimit as String] = kSecMatchLimitOne
            var result: AnyObject?
            let status = SecItemCopyMatching(q as CFDictionary, &result)
            switch status {
            case errSecSuccess:
                guard let data = result as? Data,
                      let value = String(data: data, encoding: .utf8),
                      !value.isEmpty
                else { return .missing }
                return .found(value)
            case errSecItemNotFound:
                return .missing
            case errSecAuthFailed, errSecUserCanceled, errSecInteractionNotAllowed:
                // Quiet: the item needs this app to be allowed, and the asking was
                // forbidden — measured as -25293 with no dialog. Allowed: the dialog
                // was declined, or the keychain is locked.
                if interaction == .quiet { return .wouldPrompt }
                KeychainHelper.logKeychainError("SecItemCopyMatching (login, declined)", status: status)
                return .refused
            default:
                KeychainHelper.logKeychainError("SecItemCopyMatching (login)", status: status)
                return .refused
            }
        }
    }

    /// Replace the item where the app may, update it where it may not.
    ///
    /// For the app's own item, delete-then-add re-applies the ACL that trusts
    /// `/usr/bin/security`, so `bristlenose run` can read the copy: the legacy
    /// `SecAccess` API is deprecated but is also the only way to say so (it is
    /// how `security add-generic-password -T` works). For an item another tool
    /// created the delete is **refused** — `-25244 errSecInvalidOwnerEdit`,
    /// measured 4 Sep 2026; an earlier version of this comment said a delete
    /// consults no ACL, and it does — so the write falls through to
    /// `SecItemUpdate`, which asks the user when asking is allowed and fails
    /// quietly when it is not. Either way the item stays that tool's.
    @discardableResult
    func write(service: String, account: String, value: String,
               interaction: KeychainInteraction) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }
        let q = query(service: service, account: account)
        return Self.perform(interaction) {
            let deleteStatus = SecItemDelete(q as CFDictionary)
            if deleteStatus != errSecSuccess && deleteStatus != errSecItemNotFound
                && deleteStatus != errSecInvalidOwnerEdit {
                KeychainHelper.logKeychainError("SecItemDelete (login, before add)", status: deleteStatus)
            }

            var add = q
            add[kSecValueData as String] = data
            // What Keychain Access shows as the name; `security add-generic-password`
            // defaults its label to the service too, so the two copies read alike.
            add[kSecAttrLabel as String] = service
            if let access = loginKeychainAccess.makeAccess(label: service,
                                                           trustedToolPaths: ["/usr/bin/security"]) {
                add[kSecAttrAccess as String] = access
            }
            var status = SecItemAdd(add as CFDictionary, nil)
            if status == errSecDuplicateItem {
                // Another tool's item: the delete was refused (-25244). Update in
                // place — a dialog when allowed, `-25293` when quiet.
                status = SecItemUpdate(q as CFDictionary, [kSecValueData as String: data] as CFDictionary)
            }
            if status != errSecSuccess {
                KeychainHelper.logKeychainError("SecItemAdd (login)", status: status)
                return false
            }
            return true
        }
    }

    func delete(service: String, account: String, interaction: KeychainInteraction) {
        let q = query(service: service, account: account)
        Self.perform(interaction) {
            let status = SecItemDelete(q as CFDictionary)
            if status != errSecSuccess && status != errSecItemNotFound {
                KeychainHelper.logKeychainError("SecItemDelete (login)", status: status)
            }
        }
    }
}

/// The process-wide "may Keychain Services show UI" toggle, behind a witness
/// for the same reason as the ACL maker below: the API is deprecated, and it is
/// the only one that reaches legacy items.
private protocol LegacyKeychainUIControlling {
    func setUserInteractionAllowed(_ allowed: Bool)
}

private struct LegacyKeychainUIController: LegacyKeychainUIControlling {
    @available(macOS, deprecated: 10.10)
    func setUserInteractionAllowed(_ allowed: Bool) {
        let status = SecKeychainSetUserInteractionAllowed(allowed)
        if status != errSecSuccess {
            KeychainHelper.logKeychainError("SecKeychainSetUserInteractionAllowed", status: status)
        }
    }
}

private let legacyKeychainUI: any LegacyKeychainUIControlling = LegacyKeychainUIController()

/// The deprecation of the legacy ACL API is carried by the *witness*, not the
/// requirement: callers dispatch through the protocol and compile clean, and
/// the one place that names `SecTrustedApplication` says why it still does.
private protocol LoginKeychainAccessMaking {
    func makeAccess(label: String, trustedToolPaths: [String]) -> SecAccess?
}

private struct LoginKeychainAccessMaker: LoginKeychainAccessMaking {
    /// An access object trusting this app and the tools at `trustedToolPaths`.
    /// `nil` when the API refuses — the item is then created with the default
    /// ACL (this app only), which still works; the CLI's first read just prompts.
    @available(macOS, deprecated: 10.10)
    func makeAccess(label: String, trustedToolPaths: [String]) -> SecAccess? {
        var apps: [SecTrustedApplication] = []
        var me: SecTrustedApplication?
        if SecTrustedApplicationCreateFromPath(nil, &me) == errSecSuccess, let me {
            apps.append(me)
        }
        for path in trustedToolPaths {
            var tool: SecTrustedApplication?
            if SecTrustedApplicationCreateFromPath(path, &tool) == errSecSuccess, let tool {
                apps.append(tool)
            }
        }
        var access: SecAccess?
        let status = SecAccessCreate(label as CFString, apps as CFArray, &access)
        guard status == errSecSuccess, let access else {
            KeychainHelper.logKeychainError("SecAccessCreate", status: status)
            return nil
        }
        return access
    }
}

private let loginKeychainAccess: any LoginKeychainAccessMaking = LoginKeychainAccessMaker()

// MARK: - Shared items

/// A credential the CLI reads too, kept in two keychains at once.
///
/// **Why two.** The app's copy is in the data-protection keychain: iCloud-synced,
/// so a stolen Mac does not take the key with it (the 18 Aug 2026 decision, kept),
/// and readable by the app without a prompt. `/usr/bin/security` cannot reach it,
/// and the CLI has no signed helper that could. The login keychain is the one
/// place both a sandboxed app and a shell tool can address, so the CLI's copy
/// lives there — at exactly the service and account `bristlenose configure` writes.
///
/// **The rule.** Each read compares both copies' modification dates with the
/// ledger of what they were when they last agreed. Unchanged: read the app's copy
/// and touch nothing else. Otherwise the copy that moved wins — the CLI rewrote the
/// login copy, so adopt it into the synced one; the synced copy moved (this app,
/// or another Mac), so rewrite the login copy. Both moved, or never reconciled:
/// the newer wins, a tie to the app's own copy. Only one copy exists: the other is
/// made from it. A write goes to both and reads both back. Rewriting a login
/// copy `bristlenose configure` created is an update in place, not a replace —
/// deleting another tool's item is refused (`-25244`) — so it costs a dialog when
/// asking is allowed and is skipped, ledger untouched, when it is not.
///
/// **The prompt budget.** The synced copy never prompts. Decrypting a login item
/// another tool created — one `bristlenose configure` wrote — raises the system's
/// "Bristlenose wants to use your confidential information" dialog, once per such
/// item; Always Allow makes it silent. A `quiet` read (the default — spawn paths,
/// launch-time models, the test host) never raises it: the decrypt is forbidden
/// and the app's own copy serves, with nothing recorded, until an `allowed` read
/// from Settings ▸ LLM Provider adopts the CLI's copy. That decrypt happens only
/// when the login copy has moved since the ledger last saw it, and a declined
/// dialog is recorded so it is not asked again until the copy moves. The steady
/// state is two attribute reads and one silent decrypt of the app's own copy.
/// Dates compare at whole seconds because the login keychain stores no finer.
///
/// **What it cannot do.** A key deleted from one keychain while the other still
/// holds it comes back: absence is indistinguishable from a copy not yet made, and
/// reading absence as deletion would let a locked keychain delete a synced key.
/// Delete through the app, which removes both.
enum SharedKeychainItem {

    private static let log = Logger(subsystem: "app.bristlenose", category: "keychain")

    /// One reconciliation at a time. The ledger is read-compare-write, and the
    /// two copies are read then written; two callers interleaving on one item
    /// — a spawn path and the Settings pane, or three measuring views in a
    /// parallel test run, which is how the Gemini key came to be written and
    /// read back mismatched three times in one second on 4 Sep 2026 — would
    /// each decide from a state the other was changing.
    private static let lock = NSLock()

    /// What the two copies looked like when they last agreed. `nil` = absent.
    struct Ledger: Equatable {
        var synced: Int64?
        var login: Int64?
        /// The last decrypt of the login copy was refused (a declined dialog, a
        /// locked keychain). Carried so the refusal is not re-asked on every read.
        var loginRefused = false

        static func key(service: String, account: String) -> String {
            "keychain.shared.\(service).\(account)"
        }

        static func load(_ defaults: UserDefaults, service: String, account: String) -> Ledger? {
            guard let dict = defaults.dictionary(forKey: key(service: service, account: account))
            else { return nil }
            return Ledger(synced: (dict["synced"] as? NSNumber)?.int64Value,
                          login: (dict["login"] as? NSNumber)?.int64Value,
                          loginRefused: (dict["loginRefused"] as? Bool) ?? false)
        }

        func save(_ defaults: UserDefaults, service: String, account: String) {
            var dict: [String: Any] = ["loginRefused": loginRefused]
            if let synced { dict["synced"] = NSNumber(value: synced) }
            if let login { dict["login"] = NSNumber(value: login) }
            defaults.set(dict, forKey: Self.key(service: service, account: account))
        }
    }

    /// Whole seconds: the login keychain's `mdat` carries nothing finer, and a
    /// sub-second comparison would call the app's own two writes "moved".
    private static func seconds(_ date: Date) -> Int64 {
        Int64(date.timeIntervalSince1970.rounded(.down))
    }

    private static func stamp(_ keychain: any RawKeychain, service: String, account: String) -> Int64? {
        keychain.modificationDate(service: service, account: account).map(seconds)
    }

    static func read(service: String, account: String,
                     synced: any RawKeychain, login: any RawKeychain,
                     interaction: KeychainInteraction = .quiet,
                     defaults: UserDefaults = .standard) -> String? {
        lock.withLock {
            reconcile(service: service, account: account, synced: synced, login: login,
                      interaction: interaction, defaults: defaults)
        }
    }

    private static func reconcile(service: String, account: String,
                                  synced: any RawKeychain, login: any RawKeychain,
                                  interaction: KeychainInteraction,
                                  defaults: UserDefaults) -> String? {
        let seen = Ledger.load(defaults, service: service, account: account)
        var now = Ledger(synced: stamp(synced, service: service, account: account),
                         login: stamp(login, service: service, account: account),
                         loginRefused: seen?.loginRefused ?? false)

        if let seen, seen.synced == now.synced, seen.login == now.login {
            // Nothing has moved since the copies last agreed. The app's own copy
            // is the one to read; the login copy only when there is no other —
            // an adoption whose synced write was refused (an ad-hoc build, say).
            if now.synced != nil {
                return synced.read(service: service, account: account, interaction: interaction).value
            }
            if now.login != nil, !seen.loginRefused {
                switch login.read(service: service, account: account, interaction: interaction) {
                case .found(let value): return value
                case .refused:
                    now.loginRefused = true
                    now.save(defaults, service: service, account: account)
                    return nil
                case .missing, .wouldPrompt: return nil
                }
            }
            return nil
        }

        switch (now.synced, now.login) {
        case (nil, nil):
            now.loginRefused = false
            now.save(defaults, service: service, account: account)
            return nil

        case (.some, nil):
            // Only the app's copy exists, and the CLI cannot see it. Make the one it can.
            guard case .found(let value) = synced.read(service: service, account: account,
                                                       interaction: interaction)
            else { return nil }
            let copied = login.write(service: service, account: account, value: value,
                                     interaction: interaction)
            if !copied {
                log.error("login copy of \(service, privacy: .public) refused — bristlenose run will not see it")
            }
            // A quiet write that failed may have needed the user: leave the ledger
            // for a read that can ask.
            if copied || interaction == .allowed {
                now.login = stamp(login, service: service, account: account)
                now.loginRefused = false
                now.save(defaults, service: service, account: account)
            }
            return value

        case (nil, .some):
            // Only the login copy exists — `bristlenose configure` wrote it. Adopt it.
            switch login.read(service: service, account: account, interaction: interaction) {
            case .found(let value):
                if !synced.write(service: service, account: account, value: value,
                                 interaction: interaction) {
                    log.error("could not adopt the CLI's copy of \(service, privacy: .public) into the synced store")
                }
                now.synced = stamp(synced, service: service, account: account)
                now.loginRefused = false
                now.save(defaults, service: service, account: account)
                return value
            case .wouldPrompt:
                // Decide when someone is looking; nothing is recorded.
                return nil
            case .refused:
                // Declined. Recorded, so it is not re-asked until the copy moves.
                now.loginRefused = true
                now.save(defaults, service: service, account: account)
                return nil
            case .missing:
                now.save(defaults, service: service, account: account)
                return nil
            }

        case let (.some(syncedAt), .some(loginAt)):
            let syncedValue = synced.read(service: service, account: account,
                                          interaction: interaction).value
            let loginRead = login.read(service: service, account: account, interaction: interaction)
            if loginRead == .wouldPrompt {
                // The app's copy serves until a read that may ask reconciles.
                return syncedValue
            }
            let loginValue = loginRead.value
            now.loginRefused = (loginRead == .refused)
            if loginValue == syncedValue {
                now.save(defaults, service: service, account: account)
                return syncedValue
            }
            let loginWins: Bool
            switch (seen.map { $0.synced != now.synced } ?? true,
                    seen.map { $0.login != now.login } ?? true) {
            case (false, true): loginWins = true          // the CLI wrote since we last looked
            case (true, false): loginWins = false         // this app, or another Mac, wrote
            default:            loginWins = loginAt > syncedAt   // both, or first sight
            }
            if loginWins, let loginValue {
                if !synced.write(service: service, account: account, value: loginValue,
                                 interaction: interaction) {
                    log.error("could not adopt the CLI's copy of \(service, privacy: .public) into the synced store")
                }
                now.synced = stamp(synced, service: service, account: account)
                now.save(defaults, service: service, account: account)
                return loginValue
            }
            if !loginWins, let syncedValue {
                let rewritten = login.write(service: service, account: account, value: syncedValue,
                                            interaction: interaction)
                if !rewritten {
                    log.error("login copy of \(service, privacy: .public) refused — bristlenose run will not see it")
                }
                if rewritten || interaction == .allowed {
                    now.login = stamp(login, service: service, account: account)
                    now.save(defaults, service: service, account: account)
                }
                return syncedValue
            }
            // The winner could not be read. Keep whichever copy answered, and do
            // not ask again until something moves.
            now.save(defaults, service: service, account: account)
            return syncedValue ?? loginValue
        }
    }

    /// Write both copies and read both back. `true` only if the app's own copy
    /// round-tripped; a refused login copy is logged, because that is the CLI's
    /// loss and not the app's. A save is a person's act, so it may ask.
    @discardableResult
    static func write(service: String, account: String, value: String,
                      synced: any RawKeychain, login: any RawKeychain,
                      interaction: KeychainInteraction = .allowed,
                      defaults: UserDefaults = .standard) -> Bool {
        lock.withLock {
            store(service: service, account: account, value: value, synced: synced, login: login,
                  interaction: interaction, defaults: defaults)
        }
    }

    private static func store(service: String, account: String, value: String,
                              synced: any RawKeychain, login: any RawKeychain,
                              interaction: KeychainInteraction,
                              defaults: UserDefaults) -> Bool {
        let syncedWrote = synced.write(service: service, account: account, value: value,
                                       interaction: interaction)
        let loginWrote = login.write(service: service, account: account, value: value,
                                     interaction: interaction)
        // A clean return is not evidence anything was stored — read both back.
        let syncedBack = synced.read(service: service, account: account,
                                     interaction: interaction).value == value
        let loginBack = login.read(service: service, account: account,
                                   interaction: interaction).value == value
        if !loginWrote || !loginBack {
            log.error("login copy of \(service, privacy: .public) did not round-trip — bristlenose run will not see it")
        }
        if !syncedWrote || !syncedBack {
            log.error("synced copy of \(service, privacy: .public) did not round-trip")
        }
        Ledger(synced: stamp(synced, service: service, account: account),
               login: stamp(login, service: service, account: account),
               loginRefused: false)
            .save(defaults, service: service, account: account)
        return syncedWrote && syncedBack
    }

    static func remove(service: String, account: String,
                       synced: any RawKeychain, login: any RawKeychain,
                       interaction: KeychainInteraction = .allowed,
                       defaults: UserDefaults = .standard) {
        lock.withLock {
            synced.delete(service: service, account: account, interaction: interaction)
            login.delete(service: service, account: account, interaction: interaction)
            defaults.removeObject(forKey: Ledger.key(service: service, account: account))
        }
    }
}

// MARK: - Live store (protocol wrapper around static methods)

/// Thin wrapper that delegates to `KeychainHelper` static methods,
/// conforming to `KeychainStore` for dependency injection.
private struct LiveKeychain: KeychainStore {
    func get(provider: String, account: String) -> String? {
        KeychainHelper.get(provider: provider, account: account)
    }
    @discardableResult func set(provider: String, account: String, value: String) -> Bool {
        KeychainHelper.set(provider: provider, account: account, value: value)
    }
    func delete(provider: String, account: String) {
        KeychainHelper.delete(provider: provider, account: account)
    }
    func accounts(provider: String) -> [String] { KeychainHelper.accounts(provider: provider) }
}

// MARK: - In-memory mocks (for tests)

/// Dictionary-backed keychain mock. No real Keychain access, no side effects.
/// Uses the same provider validation as `KeychainHelper` (unknown providers return nil/false).
///
/// **Keyed on `(provider, account)`, exactly as the real Keychain is.** Keying
/// it on the provider alone would reproduce the very bug per-account storage
/// exists to fix — a second account's write silently replacing the first — so
/// every test written against it would pass on the broken code.
final class InMemoryKeychain: KeychainStore {
    private struct Key: Hashable { let provider: String; let account: String }
    private var storage: [Key: String] = [:]

    /// Make writes fail, as the real Keychain does.
    ///
    /// **Without this every failure branch in the grant store is unreachable by
    /// any test** — the refused-write returns, the refused migration, the guard
    /// that keeps `previousKey` from advancing. That is the same class of hole
    /// as a mock keyed on the provider alone: a fake that cannot fail can only
    /// prove the happy path, and the happy path is not where credentials get
    /// lost. `-34018` on every write is the *documented ordinary state* of an
    /// ad-hoc-signed build, so this is a real mode, not a hypothetical.
    var refuseWrites = false

    /// Make enumeration fail, which the real one signals as an empty result —
    /// indistinguishable from "no accounts", and the reason a failed read shows
    /// the researcher "Not connected" over a live grant.
    var refuseEnumeration = false

    func get(provider: String, account: String) -> String? {
        guard KeychainHelper.serviceNames[provider] != nil else { return nil }
        guard let value = storage[Key(provider: provider, account: account)], !value.isEmpty
        else { return nil }
        return value
    }

    @discardableResult
    func set(provider: String, account: String, value: String) -> Bool {
        guard !refuseWrites else { return false }
        guard KeychainHelper.serviceNames[provider] != nil else { return false }
        storage[Key(provider: provider, account: account)] = value
        return true
    }

    func delete(provider: String, account: String) {
        storage.removeValue(forKey: Key(provider: provider, account: account))
    }

    func accounts(provider: String) -> [String] {
        guard !refuseEnumeration else { return [] }
        return storage.keys.filter { $0.provider == provider }.map(\.account).sorted()
    }
}

/// One in-memory physical keychain, for testing `SharedKeychainItem`'s rule.
///
/// It counts decrypts and, separately, *dialogs*: an item `plant`ed as another
/// tool's is foreign, a quiet read of it reports `wouldPrompt`, and an allowed
/// read of it is a dialog — counted in `prompts`, answered Always Allow unless
/// `declinePrompts`, after which the item is trusted and reads silently, as the
/// real keychain behaves. `now` is injectable so "newer" is decidable.
final class InMemoryRawKeychain: RawKeychain {
    private struct Key: Hashable { let service: String; let account: String }
    private struct Item { var value: String; var modified: Date; var foreign: Bool; var trusted: Bool }
    private var items: [Key: Item] = [:]

    var now: () -> Date = Date.init
    /// Every read refused — the keychain that cannot answer.
    var refuseReads = false
    /// Every dialog declined.
    var declinePrompts = false
    var refuseWrites = false
    private(set) var reads = 0
    /// Dialogs a real keychain would have shown.
    private(set) var prompts = 0
    private(set) var writes = 0

    func modificationDate(service: String, account: String) -> Date? {
        items[Key(service: service, account: account)]?.modified
    }

    func read(service: String, account: String, interaction: KeychainInteraction) -> RawRead {
        reads += 1
        guard !refuseReads else { return .refused }
        let key = Key(service: service, account: account)
        guard var item = items[key], !item.value.isEmpty else { return .missing }
        if item.foreign && !item.trusted {
            if interaction == .quiet { return .wouldPrompt }
            prompts += 1
            if declinePrompts { return .refused }
            item.trusted = true
            items[key] = item
        }
        return .found(item.value)
    }

    @discardableResult
    func write(service: String, account: String, value: String,
               interaction: KeychainInteraction) -> Bool {
        writes += 1
        guard !refuseWrites else { return false }
        items[Key(service: service, account: account)] =
            Item(value: value, modified: now(), foreign: false, trusted: true)
        return true
    }

    func delete(service: String, account: String, interaction: KeychainInteraction) {
        items.removeValue(forKey: Key(service: service, account: account))
    }

    /// Plant an item as another writer would, at a given moment. `foreign` is
    /// another *tool* — `bristlenose configure` — whose item this app must be
    /// allowed to read; the app on another Mac is not foreign. Not counted as a
    /// write.
    func plant(service: String, account: String, value: String, at date: Date, foreign: Bool) {
        items[Key(service: service, account: account)] =
            Item(value: value, modified: date, foreign: foreign, trusted: !foreign)
    }
}
