import Testing
@testable import Bristlenose

/// Tests for ServeManager.overlayAPIKeys — C3 credential injection path.
/// Uses InMemoryKeychain; no real macOS Keychain access.
///
/// NOTE: BristlenoseTests target is not wired into Xcode yet (qa-backlog).
/// These tests are aspirational reference code. Compile-standalone when
/// referenced via @testable import once the target lands.
@Suite("ServeManager.overlayAPIKeys")
@MainActor
struct ServeManagerEnvTests {

    @Test func populated_providers_become_env_vars() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-test-anthropic")
        store.set(provider: "openai", value: "sk-test-openai")

        var env: [String: String] = [:]
        ServeManager.overlayAPIKeys(into: &env, using: store)

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-test-anthropic")
        #expect(env["BRISTLENOSE_OPENAI_API_KEY"] == "sk-test-openai")
        #expect(env["BRISTLENOSE_AZURE_API_KEY"] == nil)
        #expect(env["BRISTLENOSE_GOOGLE_API_KEY"] == nil)
    }

    @Test func empty_store_injects_nothing() {
        let store = InMemoryKeychain()
        var env: [String: String] = [:]

        ServeManager.overlayAPIKeys(into: &env, using: store)

        let bristlenoseKeys = env.keys.filter { $0.hasPrefix("BRISTLENOSE_") && $0.hasSuffix("_API_KEY") }
        #expect(bristlenoseKeys.isEmpty)
    }

    @Test func empty_string_value_is_skipped() {
        // InMemoryKeychain's get() rejects empty strings, but test the guard
        // explicitly — if the store implementation ever changes, the env var
        // must still not be set to an empty string.
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "")  // InMemoryKeychain returns nil for this

        var env: [String: String] = [:]
        ServeManager.overlayAPIKeys(into: &env, using: store)

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == nil)
    }

    @Test func round_trip_preserves_exact_value() {
        let weirdValue = "sk-ant-api03-" + String(repeating: "A", count: 95)
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: weirdValue)

        var env: [String: String] = [:]
        ServeManager.overlayAPIKeys(into: &env, using: store)

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == weirdValue)
    }

    @Test func existing_env_preserved() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-from-keychain")

        var env: [String: String] = ["PATH": "/usr/bin", "HOME": "/tmp/fake"]
        ServeManager.overlayAPIKeys(into: &env, using: store)

        #expect(env["PATH"] == "/usr/bin")
        #expect(env["HOME"] == "/tmp/fake")
        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-from-keychain")
    }
}
