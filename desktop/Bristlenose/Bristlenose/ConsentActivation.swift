import Foundation

/// Decides which cloud provider the AI-consent sheet's "Continue" / "Done"
/// action should activate — the load-bearing logic behind the Beat 3 fix.
///
/// Split into a **pure** decision (`resolve`) and an **impure** snapshot
/// reader (`cloudStatuses`) so the rule is unit-testable without Keychain or
/// network. The decision is the same one the Settings "Use this provider"
/// toggle makes — we just run it automatically when the user acknowledges
/// the disclosure sheet, instead of forcing a second trip to Settings.
enum ConsentActivation {

    /// The cloud provider to activate, or `nil` to leave `activeProvider`
    /// unchanged.
    ///
    /// Rules (settled 31 May 2026):
    /// - If the current `active` provider is itself a configured (`.online`)
    ///   cloud provider, return `nil` — never override a deliberate, working
    ///   cloud choice.
    /// - Otherwise (`active` is local, empty, unknown, or an *unconfigured*
    ///   cloud), return the first cloud provider — in
    ///   `LLMProvider.allCases.filter(\.needsAPIKey)` order — whose status is
    ///   `.online`. The fixed `allCases` order makes the choice deterministic
    ///   when several providers are validated.
    /// - If no cloud provider is validated, return `nil` (true first run: no
    ///   key exists yet, so keep the cloud default and just record consent).
    ///
    /// Pure: no I/O, no actor isolation. `statuses` carries cached `.online`
    /// verdicts — never mere Keychain presence — so an unvalidated key never
    /// activates a provider the pipeline can't actually use.
    static func resolve(
        active: String,
        statuses: [LLMProvider: ProviderStatus]
    ) -> LLMProvider? {
        let cloudProviders = LLMProvider.allCases.filter(\.needsAPIKey)

        // Already on a working cloud provider → don't touch it.
        if let current = LLMProvider(rawValue: active),
           current.needsAPIKey,
           statuses[current]?.isConfigured == true {
            return nil
        }

        // active is local / unknown / unconfigured-cloud → adopt the first
        // validated cloud provider, deterministically by allCases order.
        return cloudProviders.first { statuses[$0]?.isConfigured == true }
    }

    /// Build a status snapshot for the cloud providers, reading Keychain
    /// presence + cached validation verdict. No network.
    ///
    /// Lazy-load discipline (sandbox walk #7): this reads only providers that
    /// actually have a stored key, and only the app's *own* Keychain items —
    /// a one-shot read on the consent-sheet button press, not the per-Settings
    /// -open cascade that produced the 3× password prompt. Providers with no
    /// key are simply omitted (they'd be `.notSetUp`); providers with a key
    /// but no cached verdict are omitted too, so `resolve` never activates an
    /// unvalidated key.
    @MainActor
    static func cloudStatuses() -> [LLMProvider: ProviderStatus] {
        var out: [LLMProvider: ProviderStatus] = [:]
        for provider in LLMProvider.allCases where provider.needsAPIKey {
            guard let keychainProvider = provider.keychainProvider,
                  let stored = KeychainHelper.get(provider: keychainProvider),
                  !stored.isEmpty
            else { continue }
            if let verdict = LLMValidator.cachedVerdict(provider: provider, key: stored) {
                out[provider] = verdict.status
            }
        }
        return out
    }
}
