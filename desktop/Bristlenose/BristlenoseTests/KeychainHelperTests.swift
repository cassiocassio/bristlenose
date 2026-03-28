import Testing
@testable import Bristlenose

/// Tests for KeychainStore protocol using InMemoryKeychain.
/// No real macOS Keychain is touched — safe in CI, safe on dev machines.
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
    }

    @Test func serviceNames_hasFourProviders() {
        #expect(KeychainHelper.serviceNames.count == 4)
    }
}
