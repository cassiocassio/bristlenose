import Testing
import Foundation
@testable import Bristlenose

/// Tests for ServeManager.overlayAPIKeys — C3 credential injection path.
/// Uses InMemoryKeychain; no real macOS Keychain access.
///
/// Contract (post sandbox-walk #7 fix): only the active provider's key is
/// injected. Other providers' keys stay in Keychain untouched. Ollama
/// (active = "local") injects nothing — Ollama is keyless.
///
/// NOTE: BristlenoseTests target is not wired into Xcode yet (qa-backlog).
/// These tests are aspirational reference code. Compile-standalone when
/// referenced via @testable import once the target lands.
@Suite("ServeManager.overlayAPIKeys")
@MainActor
struct ServeManagerEnvTests {

    /// Set the active-provider UserDefault for the duration of a test, then
    /// restore. Avoids cross-test pollution since `overlayAPIKeys` reads
    /// `UserDefaults.standard` directly.
    private func withActiveProvider<R>(_ value: String, _ body: () throws -> R) rethrows -> R {
        let key = "activeProvider"
        let prior = UserDefaults.standard.string(forKey: key)
        UserDefaults.standard.set(value, forKey: key)
        defer {
            if let prior { UserDefaults.standard.set(prior, forKey: key) }
            else { UserDefaults.standard.removeObject(forKey: key) }
        }
        return try body()
    }

    @Test func only_active_provider_key_is_injected() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-test-anthropic")
        store.set(provider: "openai", value: "sk-test-openai")

        var env: [String: String] = [:]
        withActiveProvider("anthropic") {
            ServeManager.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-test-anthropic")
        // Inactive providers' keys must NOT be injected even when present.
        #expect(env["BRISTLENOSE_OPENAI_API_KEY"] == nil)
        #expect(env["BRISTLENOSE_AZURE_API_KEY"] == nil)
        #expect(env["BRISTLENOSE_GOOGLE_API_KEY"] == nil)
    }

    @Test func ollama_active_injects_no_key() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-test-anthropic")

        var env: [String: String] = [:]
        withActiveProvider("local") {
            ServeManager.overlayAPIKeys(into: &env, using: store)
        }

        let bristlenoseKeys = env.keys.filter { $0.hasPrefix("BRISTLENOSE_") && $0.hasSuffix("_API_KEY") }
        #expect(bristlenoseKeys.isEmpty)
    }

    @Test func empty_store_injects_nothing() {
        let store = InMemoryKeychain()
        var env: [String: String] = [:]

        withActiveProvider("anthropic") {
            ServeManager.overlayAPIKeys(into: &env, using: store)
        }

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
        withActiveProvider("anthropic") {
            ServeManager.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == nil)
    }

    @Test func round_trip_preserves_exact_value() {
        let weirdValue = "sk-ant-api03-" + String(repeating: "A", count: 95)
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: weirdValue)

        var env: [String: String] = [:]
        withActiveProvider("anthropic") {
            ServeManager.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == weirdValue)
    }

    @Test func existing_env_preserved() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-from-keychain")

        var env: [String: String] = ["PATH": "/usr/bin", "HOME": "/tmp/fake"]
        withActiveProvider("anthropic") {
            ServeManager.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["PATH"] == "/usr/bin")
        #expect(env["HOME"] == "/tmp/fake")
        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-from-keychain")
    }
}
