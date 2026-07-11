import Testing
import Foundation
@testable import Bristlenose

/// Tests for BristlenoseShared.overlayAPIKeys — C3 credential injection path,
/// shared by both spawn sites (ServeManager serve + PipelineRunner run).
/// Uses InMemoryKeychain; no real macOS Keychain access.
///
/// Contract (post sandbox-walk #7 fix): only the active provider's key is
/// injected. Other providers' keys stay in Keychain untouched. Ollama
/// (active = "local") injects nothing — Ollama is keyless.
///
/// The `childEnvironment` wiring test is the real regression guard for this
/// slice: it proves the shared env factory injects the key, so BOTH spawn
/// sites (which route through `childEnvironment`) get it. The run path
/// historically forgot the overlay; the factory makes that un-forgettable.
///
/// In addition to that contract test, the invariant is protected
/// structurally: both spawn sites call `childEnvironment`, which always
/// injects the key, so there is no per-site line to forget (the bug this
/// slice fixed).
@Suite("BristlenoseShared.overlayAPIKeys")
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
            BristlenoseShared.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-test-anthropic")
        // Inactive providers' keys must NOT be injected even when present.
        #expect(env["BRISTLENOSE_OPENAI_API_KEY"] == nil)
        #expect(env["BRISTLENOSE_AZURE_API_KEY"] == nil)
        #expect(env["BRISTLENOSE_GOOGLE_API_KEY"] == nil)
    }

    /// No active provider → the key overlay scopes to `pythonDefaultProvider`
    /// (the `?? Self.pythonDefaultProvider` branch). overlayPreferences injects
    /// no BRISTLENOSE_LLM_PROVIDER in this case, so Python falls back to its own
    /// config.py default; the key overlay MUST inject THAT provider's key or a
    /// defaulted run 404s on a missing/mismatched key. This proves the Swift
    /// code PATH uses the constant; tests/test_swift_python_contract.py proves
    /// the constant's VALUE still equals Python's default. Different failure
    /// modes — defence-in-depth, not duplication.
    @Test func no_active_provider_falls_back_to_python_default_key() {
        withIsolatedDefaults { defaults in
            // activeProvider deliberately unset on this isolated suite.
            let fallback = BristlenoseShared.pythonDefaultProvider
            let store = InMemoryKeychain()
            store.set(provider: fallback, value: "sk-default-fallback")
            // A non-default provider's key is present but must NOT leak in.
            store.set(provider: "openai", value: "sk-openai-should-not-leak")

            var env: [String: String] = [:]
            BristlenoseShared.overlayAPIKeys(into: &env, using: store, defaults: defaults)

            #expect(env["BRISTLENOSE_\(fallback.uppercased())_API_KEY"] == "sk-default-fallback")
            #expect(env["BRISTLENOSE_OPENAI_API_KEY"] == nil)
        }
    }

    @Test func ollama_active_injects_no_key() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-test-anthropic")

        var env: [String: String] = [:]
        withActiveProvider("local") {
            BristlenoseShared.overlayAPIKeys(into: &env, using: store)
        }

        let bristlenoseKeys = env.keys.filter { $0.hasPrefix("BRISTLENOSE_") && $0.hasSuffix("_API_KEY") }
        #expect(bristlenoseKeys.isEmpty)
    }

    @Test func empty_store_injects_nothing() {
        let store = InMemoryKeychain()
        var env: [String: String] = [:]

        withActiveProvider("anthropic") {
            BristlenoseShared.overlayAPIKeys(into: &env, using: store)
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
            BristlenoseShared.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == nil)
    }

    @Test func round_trip_preserves_exact_value() {
        let weirdValue = "sk-ant-api03-" + String(repeating: "A", count: 95)
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: weirdValue)

        var env: [String: String] = [:]
        withActiveProvider("anthropic") {
            BristlenoseShared.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == weirdValue)
    }

    @Test func existing_env_preserved() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-from-keychain")

        var env: [String: String] = ["PATH": "/usr/bin", "HOME": "/tmp/fake"]
        withActiveProvider("anthropic") {
            BristlenoseShared.overlayAPIKeys(into: &env, using: store)
        }

        #expect(env["PATH"] == "/usr/bin")
        #expect(env["HOME"] == "/tmp/fake")
        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-from-keychain")
    }

    /// Wiring guard: the shared env factory injects the active provider's key.
    /// This is what makes BOTH spawn sites correct — they route through
    /// `childEnvironment`, so neither can forget the overlay. The run path
    /// previously omitted it, breaking `bristlenose run` under App Sandbox.
    /// Uses `.devSidecar` mode: sslEnvironment/bundledBinaryEnvironment return
    /// empty for non-bundled modes, so no real bundle resources are needed.
    @Test func childEnvironment_injects_active_provider_key() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-from-keychain")
        let mode = SidecarMode.devSidecar(path: URL(fileURLWithPath: "/tmp/fake-bristlenose"))

        let env = withActiveProvider("anthropic") {
            BristlenoseShared.childEnvironment(for: mode, store: store)
        }

        // The key the run path used to miss.
        #expect(env["BRISTLENOSE_ANTHROPIC_API_KEY"] == "sk-ant-from-keychain")
        // And the parent-death handshake every desktop-spawned child needs.
        #expect(env["_BRISTLENOSE_HOSTED_BY_DESKTOP"] == "1")
    }

    /// Keyless provider through the factory injects no key (local-only users
    /// trigger no Keychain access — the "loudest possible local-only failure"
    /// the single-provider scoping was designed to avoid).
    @Test func childEnvironment_keyless_provider_injects_no_key() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-from-keychain")
        let mode = SidecarMode.devSidecar(path: URL(fileURLWithPath: "/tmp/fake-bristlenose"))

        let env = withActiveProvider("local") {
            BristlenoseShared.childEnvironment(for: mode, store: store)
        }

        let bristlenoseKeys = env.keys.filter { $0.hasPrefix("BRISTLENOSE_") && $0.hasSuffix("_API_KEY") }
        #expect(bristlenoseKeys.isEmpty)
    }

    /// The desktop presentation themes are activated through the shared factory:
    /// `data-platform="desktop"` (rendered from BRISTLENOSE_PLATFORM by app.py)
    /// gates the SF Pro type scale, and the colour palette is injected as
    /// BRISTLENOSE_PALETTE (canonical; was BRISTLENOSE_COLOR_THEME before
    /// 5b997d26), defaulting to "default" so Edo stays opt-in.
    /// Without the platform var the native type system ships dark.
    @Test func childEnvironment_activates_desktop_presentation_themes() {
        // childEnvironment reads UserDefaults.standard directly, so isolate the
        // palette pref to exercise the default path (the test host is the app,
        // where a pulldown-set palette would otherwise leak in). Restored after.
        let defaults = UserDefaults.standard
        let savedPalette = defaults.string(forKey: "palette")
        defaults.removeObject(forKey: "palette")
        defer { if let savedPalette { defaults.set(savedPalette, forKey: "palette") } }

        let mode = SidecarMode.devSidecar(path: URL(fileURLWithPath: "/tmp/fake-bristlenose"))
        let env = BristlenoseShared.childEnvironment(for: mode, store: InMemoryKeychain())
        #expect(env["BRISTLENOSE_PLATFORM"] == "desktop")
        #expect(env["BRISTLENOSE_PALETTE"] == "default")
    }

    /// Typography opt-out rides overlayPreferences: default "sf" injects nothing
    /// (the server's implicit default is SF Pro), "inter" injects the var so
    /// app.py emits data-typography="inter" and the desktop app shows Inter.
    @Test func overlayPreferences_injects_typography_only_when_inter() {
        withIsolatedDefaults { defaults in
            var env: [String: String] = [:]
            defaults.set("sf", forKey: "typography")
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_TYPOGRAPHY"] == nil)

            defaults.set("inter", forKey: "typography")
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_TYPOGRAPHY"] == "inter")
        }
    }

    /// UI locale rides overlayPreferences: default "en" (or unset) injects
    /// nothing (the server defaults to English), any other locale injects
    /// BRISTLENOSE_LANG so the Python-rendered status page calls set_locale and
    /// the failed-run surface matches the app's chosen language.
    @Test func overlayPreferences_injects_lang_only_when_not_english() {
        withIsolatedDefaults { defaults in
            var env: [String: String] = [:]
            // Unset → no injection
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LANG"] == nil)

            // Explicit English → no injection
            defaults.set("en", forKey: "language")
            env = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LANG"] == nil)

            // Non-English → injected
            defaults.set("pt-BR", forKey: "language")
            env = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LANG"] == "pt-BR")
        }
    }

    // MARK: - overlayPreferences provider+model coherence (Defect M invariant)

    /// Isolated UserDefaults suite for overlayPreferences tests — avoids
    /// polluting `.standard` and gives each test a clean slate.
    private func withIsolatedDefaults(_ body: (UserDefaults) -> Void) {
        let name = "ServeManagerEnvTests-\(UUID().uuidString)"
        let suite = UserDefaults(suiteName: name)!
        defer { suite.removePersistentDomain(forName: name) }
        body(suite)
    }

    /// The active provider and a matching model are injected TOGETHER, from the
    /// per-provider `llmModel_<provider>` key. This is the activation-persistence
    /// invariant: a chosen provider reaches the env overlay with a coherent
    /// model, so `bristlenose run` analyses with the provider+model the user
    /// actually selected.
    @Test func overlayPreferences_injects_provider_and_matching_model_together() {
        withIsolatedDefaults { defaults in
            defaults.set("openai", forKey: "activeProvider")
            defaults.set("gpt-4o-mini", forKey: "llmModel_openai")
            var env: [String: String] = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LLM_PROVIDER"] == "openai")
            #expect(env["BRISTLENOSE_LLM_MODEL"] == "gpt-4o-mini")
        }
    }

    /// Defect M invariant: NEVER a model without a provider. With no active
    /// provider, inject NEITHER and let Python default both coherently — not a
    /// bare global model that would mismatch Python's default provider (the
    /// gpt-4o-rejected-by-Anthropic 404 this branch was opened to fix).
    @Test func overlayPreferences_no_active_provider_injects_neither() {
        withIsolatedDefaults { defaults in
            defaults.set("gpt-4o", forKey: "llmModel")  // stale global model, no provider
            var env: [String: String] = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LLM_PROVIDER"] == nil)
            #expect(env["BRISTLENOSE_LLM_MODEL"] == nil)
        }
    }

    /// Provider set, no per-provider model → model falls back to the provider's
    /// built-in default. Still a coherent provider+model pair (never one without
    /// the other).
    @Test func overlayPreferences_provider_without_per_provider_model_uses_default() {
        withIsolatedDefaults { defaults in
            defaults.set("anthropic", forKey: "activeProvider")
            var env: [String: String] = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LLM_PROVIDER"] == "anthropic")
            #expect(env["BRISTLENOSE_LLM_MODEL"] == LLMProvider.claude.defaultModel)
        }
    }

    /// Ollama (`local`) execution reads `local_model` (BRISTLENOSE_LOCAL_MODEL),
    /// NOT cloud `llm_model` (BRISTLENOSE_LLM_MODEL) — see bristlenose/config.py.
    /// The resolved model must land on the local axis, or the user's picked
    /// Ollama model is silently dropped and the pipeline falls back to the
    /// `local_model` default (llama3.2:3b), which is too small for structured
    /// output and 100%-fails topic segmentation.
    @Test func overlayPreferences_local_provider_routes_model_to_local_axis() {
        withIsolatedDefaults { defaults in
            defaults.set("local", forKey: "activeProvider")
            defaults.set("gemma4:31b", forKey: "llmModel_local")
            var env: [String: String] = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(env["BRISTLENOSE_LLM_PROVIDER"] == "local")
            #expect(env["BRISTLENOSE_LOCAL_MODEL"] == "gemma4:31b")
            // The cloud axis must NOT carry the Ollama model.
            #expect(env["BRISTLENOSE_LLM_MODEL"] == nil)
        }
    }

    // MARK: - resolvedProviderModel (shared source of truth)

    /// `resolvedProviderModel` is the single source overlayPreferences and
    /// hostResolutionTrace both read, so the env vars and the ledger line can't
    /// disagree about what was injected — a disagreement there would be the
    /// trace LYING about the 8 Jun 404, the one thing it exists to expose.
    @Test func resolvedProviderModel_matches_what_overlayPreferences_injects() {
        withIsolatedDefaults { defaults in
            defaults.set("openai", forKey: "activeProvider")
            defaults.set("gpt-4o-mini", forKey: "llmModel_openai")
            let resolved = BristlenoseShared.resolvedProviderModel(defaults: defaults)
            var env: [String: String] = [:]
            BristlenoseShared.overlayPreferences(into: &env, defaults: defaults)
            #expect(resolved.provider == env["BRISTLENOSE_LLM_PROVIDER"])
            #expect(resolved.model == env["BRISTLENOSE_LLM_MODEL"])
        }
    }

    @Test func resolvedProviderModel_no_provider_resolves_neither() {
        withIsolatedDefaults { defaults in
            defaults.set("gpt-4o", forKey: "llmModel")  // stale global, no provider
            let resolved = BristlenoseShared.resolvedProviderModel(defaults: defaults)
            #expect(resolved.provider == nil)
            #expect(resolved.model == nil)
        }
    }

    // MARK: - hostResolutionTrace (cross-seam ledger)

    /// The host emits a `step=host-defaults` ledger line naming the provider and
    /// model it resolved, plus `key=present` when the active provider's key is in
    /// Keychain. Provider/model NAMES are not secret; only the key value is
    /// withheld (reported as present/absent).
    @Test func hostResolutionTrace_reports_provider_model_and_key_present() {
        withIsolatedDefaults { defaults in
            defaults.set("openai", forKey: "activeProvider")
            defaults.set("gpt-4o-mini", forKey: "llmModel_openai")
            let store = InMemoryKeychain()
            store.set(provider: "openai", value: "sk-test-openai")
            let lines = BristlenoseShared.hostResolutionTrace(
                defaults: defaults, store: store
            )
            #expect(lines.count == 1)
            let line = lines[0]
            #expect(line.contains("step=host-defaults"))
            #expect(line.contains("activeProvider='openai'"))
            #expect(line.contains("model='gpt-4o-mini'"))
            #expect(line.contains("key=present"))
            // SECURITY: the key VALUE must never appear (env var is ps -E-visible).
            #expect(!line.contains("sk-test-openai"))
        }
    }

    /// No key in Keychain for the active cloud provider → `key=absent` (still no
    /// secret leaked, and the absence is exactly what a 401/"add a key" failure
    /// would want to confirm in the log).
    @Test func hostResolutionTrace_reports_key_absent_when_missing() {
        withIsolatedDefaults { defaults in
            defaults.set("anthropic", forKey: "activeProvider")
            let store = InMemoryKeychain()  // empty
            let lines = BristlenoseShared.hostResolutionTrace(
                defaults: defaults, store: store
            )
            #expect(lines[0].contains("key=absent"))
        }
    }

    /// Keyless provider (local/Ollama) → `key=keyless`, never a Keychain miss
    /// dressed up as `absent`.
    @Test func hostResolutionTrace_reports_keyless_for_local() {
        withIsolatedDefaults { defaults in
            defaults.set("local", forKey: "activeProvider")
            let store = InMemoryKeychain()
            let lines = BristlenoseShared.hostResolutionTrace(
                defaults: defaults, store: store
            )
            #expect(lines[0].contains("activeProvider='local'"))
            #expect(lines[0].contains("key=keyless"))
        }
    }

    /// No active provider → activeProvider=nil but effectiveProvider names
    /// Python's default, and key presence is judged against THAT (the
    /// defaulted-run path the 404 came through).
    @Test func hostResolutionTrace_no_provider_uses_python_default() {
        withIsolatedDefaults { defaults in
            let store = InMemoryKeychain()
            store.set(
                provider: BristlenoseShared.pythonDefaultProvider,
                value: "sk-default"
            )
            let lines = BristlenoseShared.hostResolutionTrace(
                defaults: defaults, store: store
            )
            #expect(lines[0].contains("activeProvider=nil"))
            #expect(lines[0].contains(
                "effectiveProvider='\(BristlenoseShared.pythonDefaultProvider)'"
            ))
            #expect(lines[0].contains("key=present"))
        }
    }

    /// The shared env factory injects the cross-seam trace env var, so BOTH
    /// spawn sites carry it (structural guarantee, same as the API-key overlay).
    @Test func childEnvironment_injects_host_resolution_trace() {
        let store = InMemoryKeychain()
        store.set(provider: "anthropic", value: "sk-ant-from-keychain")
        let mode = SidecarMode.devSidecar(path: URL(fileURLWithPath: "/tmp/fake-bristlenose"))
        let env = withActiveProvider("anthropic") {
            BristlenoseShared.childEnvironment(for: mode, store: store)
        }
        let trace = env["_BRISTLENOSE_HOST_RESOLUTION_TRACE"]
        #expect(trace != nil)
        #expect(trace?.contains("step=host-defaults") == true)
        #expect(trace?.contains("activeProvider='anthropic'") == true)
        #expect(trace?.contains("sk-ant-from-keychain") == false)
    }
}
