import AppKit
import Foundation

/// App-global observable: is the **active** cloud provider out of credit?
///
/// Read-side only — reuses the existing detection. `LLMValidator` records a
/// sticky `.outOfCredit` verdict (from an HTTP 402) per credential; this reads
/// that back for whichever provider is active. The read mirrors
/// `ConsentActivation.cloudStatuses()`. Cloud-only: Ollama has no credit
/// concept, so a local active provider is never out of credit — which also
/// means this pill and the Ollama download pill never contend for the
/// `.status` zone.
///
/// `OutOfCreditPill` observes `isActive`.
///
/// Two triggers keep the cache fresh so the pill is timely: (1) Settings
/// validation / `revalidateAll` (the pre-existing path), and (2) a run that
/// fails with the `.outOfCredit` category calls `recordActiveProviderOutOfCredit`
/// from `PipelineRunner.deriveFailureState` — the authoritative run-failure path,
/// keyed on the distinct billing category (never a transient `.quota`/429). A
/// remaining limitation (tracked): the pill clears only when a fresh validation
/// records `.online`; refocus currently re-reads the cache without revalidating,
/// so after a browser top-up it lingers until Settings next checks. And the
/// OpenAI Settings probe is unbilled (GET /v1/models), so Settings can't detect
/// OpenAI credit-out — the run-failure trigger covers it instead.
@MainActor
final class OutOfCreditModel: ObservableObject {
    /// True when the active provider's cached verdict is `.outOfCredit`.
    @Published private(set) var isActive = false

    /// The out-of-credit provider — drives the pill label and the "Add funds"
    /// destination. `nil` whenever `isActive` is false.
    @Published private(set) var provider: LLMProvider?

    private var observers: [NSObjectProtocol] = []

    init() {
        refresh()
        let center = NotificationCenter.default
        // Provider switch, key change, and consent all ride prefsChanged.
        observers.append(center.addObserver(
            forName: .bristlenosePrefsChanged, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        })
        // A run/serve that failed on billing records the verdict then posts
        // this — lights the pill immediately without a serve restart.
        observers.append(center.addObserver(
            forName: .bristlenoseOutOfCreditChanged, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        })
        // Re-read when the app is refocused — a top-up happens in the browser,
        // so the fix lands out-of-band and we want the pill to clear on return.
        observers.append(center.addObserver(
            forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        })
    }

    /// Record a sticky out-of-credit verdict for `provider` (the run's provider;
    /// defaults to the active one) after a run fails on billing, then post a
    /// refresh so the pill lights at once. The pill reads `LLMValidator`'s verdict
    /// cache; a run 402 wouldn't otherwise touch it until Settings re-validates.
    /// Pass the run's provider explicitly so a mid-run `activeProvider` switch
    /// can't attribute the verdict to the wrong provider. Mirrors the read
    /// pattern in `refresh()` / `ConsentActivation.cloudStatuses`.
    static func recordActiveProviderOutOfCredit(provider explicitProvider: LLMProvider? = nil) {
        let active = explicitProvider
            ?? UserDefaults.standard.string(forKey: "activeProvider")
                .flatMap(LLMProvider.init(rawValue:))
        guard
            let active,
            active.needsAPIKey,
            let keychainProvider = active.keychainProvider,
            let key = KeychainHelper.get(provider: keychainProvider), !key.isEmpty
        else { return }
        LLMValidator.recordVerdict(provider: active, key: key, status: .outOfCredit)
        NotificationCenter.default.post(name: .bristlenoseOutOfCreditChanged, object: nil)
    }

    deinit {
        observers.forEach(NotificationCenter.default.removeObserver)
    }

    /// Recompute from the active provider + its cached verdict.
    func refresh() {
        guard
            let raw = UserDefaults.standard.string(forKey: "activeProvider"),
            let active = LLMProvider(rawValue: raw),
            active.needsAPIKey,
            let keychainProvider = active.keychainProvider,
            let key = KeychainHelper.get(provider: keychainProvider), !key.isEmpty,
            LLMValidator.cachedVerdict(provider: active, key: key) == .outOfCredit
        else {
            isActive = false
            provider = nil
            return
        }
        provider = active
        isActive = true
    }
}
