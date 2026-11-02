import AppKit
import Foundation

/// App-global: is the **active** provider refusing us, and how loudly should the
/// title bar say so? The state behind `ProviderProblemPill`.
///
/// **A refused call lights it, not a stored verdict.** The shipped out-of-credit
/// pill read `LLMValidator`'s sticky verdict, so a key that had run dry in
/// January was still amber in March for someone who had come back only for their
/// old data. Settings validation still writes the verdict (the Settings dot is
/// the place that always tells), but it no longer raises the pill. Three sources
/// raise it, all of them a call that was actually made and refused:
/// - a finished run (`PipelineRunner.deriveFailureState`), which is something
///   the researcher asked for (`explicit`);
/// - the sidecar's `llm-failure` bridge post, for calls inside the report
///   (AutoCode, and any later call that reports), which are not.
///
/// **It is held to the verdict.** The record says what was refused; the verdict
/// cache for that key says whether that is still so. A new key, a good
/// re-validation or a run that worked clears it with no further bookkeeping.
///
/// **Cloud-only.** Ollama has no credit and no key, so a local provider is never
/// here, which also keeps this pill and the Ollama download pill apart.
@MainActor
final class ProviderProblemModel: ObservableObject {
    /// What the pill draws.
    struct Presented: Equatable {
        let provider: LLMProvider
        let condition: ProviderProblemCondition
        let stage: ProviderProblemStage
    }

    /// One instance for the app, like `WhisperDownloadModel.shared`: the toolbar
    /// item and the Diagnostics menu share it, and no scene needs it injected.
    static let shared = ProviderProblemModel()

    @Published private(set) var presented: Presented?

    #if DEBUG
    /// Diagnostics ▸ Provider problem pill forces a state here, so every look can
    /// be seen without running a provider dry. Wins over the real state.
    @Published var debugForced: Presented?
    #endif

    /// What the pill should draw now.
    var shown: Presented? {
        #if DEBUG
        if let debugForced { return debugForced }
        #endif
        return presented
    }

    private let defaults: UserDefaults
    private let now: () -> Date
    private let activeProvider: () -> LLMProvider?
    private let keyFor: (LLMProvider) -> String?
    private var observers: [NSObjectProtocol] = []

    static let recordKey = "providerProblemRecord"

    init(
        defaults: UserDefaults = .standard,
        now: @escaping () -> Date = Date.init,
        activeProvider: @escaping () -> LLMProvider? = ProviderProblemModel.liveActiveProvider,
        keyFor: @escaping (LLMProvider) -> String? = ProviderProblemModel.liveKey,
        observing center: NotificationCenter = .default
    ) {
        self.defaults = defaults
        self.now = now
        self.activeProvider = activeProvider
        self.keyFor = keyFor
        refresh()
        // Provider switch, key change and consent all ride prefsChanged.
        observers.append(center.addObserver(
            forName: .bristlenosePrefsChanged, object: nil, queue: .main
        ) { [weak self] _ in Task { @MainActor in self?.refresh() } })
        // A refusal was recorded: light (or reword) the pill at once, without a
        // serve restart.
        observers.append(center.addObserver(
            forName: .bristlenoseProviderProblemChanged, object: nil, queue: .main
        ) { [weak self] _ in Task { @MainActor in self?.refresh() } })
        // Back to the app: a top-up or a new key happens in the browser or in
        // Settings, and the stage may have moved on while it was away.
        observers.append(center.addObserver(
            forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main
        ) { [weak self] _ in Task { @MainActor in self?.refresh() } })
    }

    deinit { observers.forEach(NotificationCenter.default.removeObserver) }

    // MARK: - Live sources

    nonisolated static func liveActiveProvider() -> LLMProvider? {
        UserDefaults.standard.string(forKey: "activeProvider").flatMap(LLMProvider.init(rawValue:))
    }

    /// The provider's stored key, or nil. Cloud providers only.
    @MainActor
    static func liveKey(_ provider: LLMProvider) -> String? {
        guard provider.needsAPIKey, let keychainProvider = provider.keychainProvider,
              let key = KeychainHelper.get(provider: keychainProvider), !key.isEmpty
        else { return nil }
        return key
    }

    // MARK: - Reading

    /// Recompute `presented` from the stored record, the key's verdict and the
    /// clock. Called at launch, on activation and when a refusal is recorded; no
    /// timer calls it, so the stage never changes while someone is looking.
    func refresh() {
        guard let record = Self.load(from: defaults),
              let provider = LLMProvider(rawValue: record.provider)
        else {
            presented = nil
            return
        }
        // Held to the verdict for the key it was recorded against. Gone is gone:
        // the record is dropped, so a later refusal is news, not a repeat.
        guard let key = keyFor(provider),
              ProviderProblemRules.holds(
                record, verdictForItsKey: LLMValidator.cachedVerdict(provider: provider, key: key))
        else {
            Self.clear(in: defaults)
            presented = nil
            return
        }
        // Another provider is active now: say nothing, keep the record. Switching
        // back to a provider that is still refusing brings it back.
        guard activeProvider() == provider,
              let stage = ProviderProblemRules.stage(of: record, now: now())
        else {
            presented = nil
            return
        }
        presented = Presented(provider: provider, condition: record.condition, stage: stage)
    }

    /// The ✕. Hides it until the next refusal that counts (`applying`).
    func dismiss() {
        guard var record = Self.load(from: defaults) else { return }
        record.dismissed = true
        Self.save(record, to: defaults)
        refresh()
    }

    // MARK: - Recording (called where a refusal is seen)

    /// A call was refused. Writes the verdict (so Settings and the pill agree),
    /// updates the record, and tells the model.
    ///
    /// - Parameter provider: the provider the call used; defaults to the active
    ///   one. Pass it explicitly so a switch mid-run can't blame the wrong one.
    /// - Parameter explicit: the researcher asked for this (a run), as opposed
    ///   to something incidental.
    @discardableResult
    static func recordRefusal(
        _ condition: ProviderProblemCondition,
        provider explicitProvider: LLMProvider? = nil,
        explicit: Bool,
        defaults: UserDefaults = .standard,
        now: Date = Date(),
        activeProvider: () -> LLMProvider? = ProviderProblemModel.liveActiveProvider,
        keyFor: (LLMProvider) -> String? = ProviderProblemModel.liveKey,
        center: NotificationCenter = .default
    ) -> Bool {
        guard let provider = explicitProvider ?? activeProvider(),
              provider.needsAPIKey,
              let key = keyFor(provider)
        else { return false }
        LLMValidator.recordVerdict(provider: provider, key: key, status: condition.verdict.status)
        let record = ProviderProblemRules.applying(
            refusalOf: condition, provider: provider.rawValue, explicit: explicit,
            to: load(from: defaults), now: now)
        save(record, to: defaults)
        center.post(name: .bristlenoseProviderProblemChanged, object: nil)
        return true
    }

    /// A run finished having made an LLM call with `provider`: whatever the
    /// verdict said about its key, it was wrong (R40). Clears it and the record.
    static func noteRunSucceeded(
        provider: LLMProvider,
        defaults: UserDefaults = .standard,
        keyFor: (LLMProvider) -> String? = ProviderProblemModel.liveKey,
        center: NotificationCenter = .default
    ) {
        guard provider.needsAPIKey, let key = keyFor(provider),
              clearAfterSuccessfulRun(provider: provider, key: key)
        else { return }
        if load(from: defaults)?.provider == provider.rawValue { clear(in: defaults) }
        center.post(name: .bristlenoseProviderProblemChanged, object: nil)
    }

    /// Drop a verdict that a working call contradicts: out of credit, or a key
    /// rejected. (A run that made an LLM call with this key proves both false.)
    /// Cleared, not replaced with `.ok`: a run that finished from cache made no
    /// call, and a fresh `.ok` would let `revalidateAll` skip the key for its
    /// whole TTL. With no verdict, Settings re-checks next time. True when it
    /// changed something.
    static func clearAfterSuccessfulRun(provider: LLMProvider, key: String) -> Bool {
        guard let verdict = LLMValidator.cachedVerdict(provider: provider, key: key),
              verdict == .outOfCredit || verdict == .invalid
        else { return false }
        LLMValidator.clearCache(provider: provider)
        return true
    }

    // MARK: - Storage

    static func load(from defaults: UserDefaults) -> ProviderProblemRecord? {
        guard let data = defaults.data(forKey: recordKey) else { return nil }
        return try? JSONDecoder().decode(ProviderProblemRecord.self, from: data)
    }

    static func save(_ record: ProviderProblemRecord, to defaults: UserDefaults) {
        if let data = try? JSONEncoder().encode(record) { defaults.set(data, forKey: recordKey) }
    }

    static func clear(in defaults: UserDefaults) {
        defaults.removeObject(forKey: recordKey)
    }
}

#if DEBUG
// MARK: - Diagnostics harness (DEBUG only)

extension ProviderProblemCondition {
    var debugLabel: String {
        switch self {
        case .keyRejected: return "Key rejected (error)"
        case .outOfCredit: return "Out of credit (warning)"
        }
    }
}

extension ProviderProblemStage {
    var debugLabel: String {
        switch self {
        case .loud: return "1 · First refusal (tinted)"
        case .settled: return "2 · Settled"
        case .collapsed: return "3 · A day later (bare glyph)"
        }
    }
}

extension ProviderProblemModel {
    /// Force a condition, keeping the current forced stage (loud to start).
    func debugForce(condition: ProviderProblemCondition) {
        debugForced = Presented(
            provider: .claude, condition: condition, stage: debugForced?.stage ?? .loud)
    }

    /// Force a stage, keeping the current forced condition (out of credit to start).
    func debugForce(stage: ProviderProblemStage) {
        debugForced = Presented(
            provider: .claude, condition: debugForced?.condition ?? .outOfCredit, stage: stage)
    }
}
#endif
