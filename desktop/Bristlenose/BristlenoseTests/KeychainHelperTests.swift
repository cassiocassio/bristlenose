import Testing
import Foundation
@testable import Bristlenose

/// Tests for KeychainStore protocol using InMemoryKeychain.
/// No real macOS Keychain is touched — safe in CI, safe on dev machines.
@MainActor
@Suite("KeychainStore (in-memory)")
struct KeychainHelperTests {

    @Test func get_unknownProvider_returnsNil() {
        let store = InMemoryKeychain()
        #expect(store.get(provider: "nonexistent") == nil)
    }

    @Test func set_unknownProvider_returnsFalse() {
        let store = InMemoryKeychain()
        #expect(store.set(provider: "nonexistent", value: "key") == false)
    }

    @Test func set_thenGet_roundTrip() {
        let store = InMemoryKeychain()
        let success = store.set(provider: "anthropic", value: "sk-test-123")
        #expect(success == true)
        #expect(store.get(provider: "anthropic") == "sk-test-123")
    }

    @Test func set_overwritesExisting() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "old-key")
        store.set(provider: "anthropic", value: "new-key")
        #expect(store.get(provider: "anthropic") == "new-key")
    }

    @Test func delete_removesKey() {
        let store = InMemoryKeychain()
        store.set(provider: "openai", value: "sk-test")
        store.delete(provider: "openai")
        #expect(store.get(provider: "openai") == nil)
    }

    @Test func delete_unknownProvider_noOp() {
        let store = InMemoryKeychain()
        // Should not crash
        store.delete(provider: "nonexistent")
    }

    @Test func get_emptyString_returnsNil() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "")
        // Empty strings should not be returned (matches real Keychain behaviour)
        #expect(store.get(provider: "anthropic") == nil)
    }

    @Test func allKnownProviders_areAccepted() {
        let store = InMemoryKeychain()
        for provider in KeychainHelper.serviceNames.keys {
            let success = store.set(provider: provider, value: "test-\(provider)")
            #expect(success == true, "Provider '\(provider)' should be accepted")
            #expect(store.get(provider: provider) == "test-\(provider)")
        }
    }

    // MARK: - Service name mapping

    @Test func serviceNames_matchPythonMapping() {
        // These must match MacOSCredentialStore.SERVICE_NAMES in credentials_macos.py
        #expect(KeychainHelper.serviceNames["anthropic"] == "Bristlenose Anthropic API Key")
        #expect(KeychainHelper.serviceNames["openai"] == "Bristlenose OpenAI API Key")
        #expect(KeychainHelper.serviceNames["azure"] == "Bristlenose Azure API Key")
        #expect(KeychainHelper.serviceNames["google"] == "Bristlenose Google Gemini API Key")
        #expect(KeychainHelper.serviceNames["miro"] == "Bristlenose Miro Access Token")
    }

    /// Keys the **Python** side also reads. Adding one here obliges a matching
    /// entry in `MacOSCredentialStore.SERVICE_NAMES` (`credentials_macos.py`)
    /// or the two ends silently disagree about where a credential lives.
    private static let mirroredToPython: Set<String> =
        ["anthropic", "openai", "azure", "google", "miro"]

    /// Keys only the Swift host uses. **Deliberately absent from Python** — a
    /// cloud sign-in is a host-side concern the sidecar never touches, and
    /// adding it to `credentials_macos.py` would imply a reader that does not
    /// exist.
    private static let swiftOnly: Set<String> =
        ["cloud-google-meet", "cloud-microsoft-teams", "cloud-zoom"]

    @Test func serviceNames_pinAllCredentialKeys() {
        // Pinned exactly so adding or removing a key fails loudly with a clear
        // diff. Split into two sets rather than one flat list because the two
        // carry different obligations, and a flat list invites the next person
        // to satisfy this test by editing Python for a key Python never reads.
        #expect(Set(KeychainHelper.serviceNames.keys)
                == Self.mirroredToPython.union(Self.swiftOnly))
    }

    /// The registration itself is load-bearing, not bookkeeping: `get` and
    /// `set` both `guard let service = serviceNames[provider]` and bail, so an
    /// unregistered key reads nil and writes false **silently**.
    /// `CloudGrantStore` shipped against an unregistered key and persisted
    /// nothing at all, with no error anywhere.
    @Test func serviceNames_cloudSignInIsRegistered() {
        for key in Self.swiftOnly {
            #expect(KeychainHelper.serviceNames[key] != nil,
                    "\(key) is unregistered — its store is a silent no-op")
        }
    }

    // MARK: - Keys the CLI reads

    /// Every key Python reads is kept in the login keychain too, so a key saved
    /// in the app is one `bristlenose run` can find. A key in the Python map
    /// but not here would be saved to the synced keychain alone — invisible to
    /// the CLI from the moment it was entered, with nothing red anywhere.
    /// `tests/test_swift_python_contract.py` pins the same set from the Python
    /// side, by reading this file.
    @Test func sharedWithCLI_isExactlyTheSetPythonReads() {
        #expect(KeychainHelper.sharedWithCLI == Self.mirroredToPython)
    }

    /// Cloud sign-ins are Swift-only: no login copy, so the account-derived
    /// items never leave the entitlement-scoped keychain.
    @Test func cloudSignIns_areNotSharedWithTheCLI() {
        #expect(KeychainHelper.sharedWithCLI.isDisjoint(with: Self.swiftOnly))
    }

    // MARK: - The live statics under a test host

    /// The test bundle runs inside the real app, so a test that renders a view
    /// reaches `KeychainHelper`'s statics. Under a test host they must resolve
    /// to in-memory stores: on 4 Sep 2026 a pane-measuring test read the
    /// developer's CLI-created keys with interaction allowed (three dialogs)
    /// and wrote one back. Pinned by *type*, deliberately — a round-trip through
    /// the statics would be the very write this guards against if it failed.
    @Test func underTheTestHost_theLiveStaticsAreInMemory() {
        #expect(KeychainHelper.isUnderTestHost)
        #expect(KeychainHelper.syncedKeychain is InMemoryRawKeychain)
        #expect(KeychainHelper.loginKeychain is InMemoryRawKeychain)
        #expect(KeychainHelper.ledgerDefaults !== UserDefaults.standard)
    }
}
