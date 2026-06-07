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
    /// Rules (defect #1 fix, 6 Jun 2026 — supersedes the 31 May verdict gate):
    /// - If the current `active` provider is a cloud provider that has a
    ///   stored Keychain key (`activeHasKey`), return `nil` — never override
    ///   a deliberate cloud choice the user has set up. A *missing* cached
    ///   `.online` verdict means "not validated yet" (stale cache, post-
    ///   relaunch before re-validation, key just re-read), NOT "invalid" —
    ///   and re-validation happens on the run path. Flipping the provider
    ///   here would silently send data to a provider the user didn't choose,
    ///   make the consent disclosure false, and write a wrong DPIA record.
    /// - Otherwise (`active` is local, empty, unknown, or a cloud with *no*
    ///   stored key), return the first cloud provider — in
    ///   `LLMProvider.allCases.filter(\.needsAPIKey)` order — whose status is
    ///   `.online`. The fixed `allCases` order makes the choice deterministic
    ///   when several providers are validated.
    /// - If no cloud provider is validated, return `nil` (true first run: no
    ///   key exists yet, so keep the cloud default and just record consent).
    ///
    /// Pure: no I/O, no actor isolation. `activeHasKey` is the only fact about
    /// the active provider's Keychain state the decision needs; `statuses`
    /// carries cached `.online` verdicts for the *fallback* search only.
    static func resolve(
        active: String,
        activeHasKey: Bool,
        statuses: [LLMProvider: ProviderStatus]
    ) -> LLMProvider? {
        let cloudProviders = LLMProvider.allCases.filter(\.needsAPIKey)

        // Deliberate cloud choice with a stored key → never override it,
        // even if its verdict isn't cached as `.online` right now.
        if let current = LLMProvider(rawValue: active),
           current.needsAPIKey,
           activeHasKey {
            return nil
        }

        // active is local / unknown / cloud-with-no-key → adopt the first
        // validated cloud provider, deterministically by allCases order.
        return cloudProviders.first { statuses[$0]?.isConfigured == true }
    }

    /// Whether the active provider is a cloud provider with a non-empty stored
    /// Keychain key. Impure (Keychain read) — the one fact `resolve` needs
    /// about the active provider that the verdict-only `cloudStatuses` snapshot
    /// can't carry. Reads only the active provider's own item: no cascade.
    @MainActor
    static func hasStoredKey(forActive active: String) -> Bool {
        guard let provider = LLMProvider(rawValue: active),
              provider.needsAPIKey,
              let keychainProvider = provider.keychainProvider,
              let stored = KeychainHelper.get(provider: keychainProvider)
        else { return false }
        return !stored.isEmpty
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
