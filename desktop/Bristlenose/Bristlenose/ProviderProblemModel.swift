import AppKit
import Foundation
import os

/// App-global: is the **active** provider refusing us, and how loudly should the
/// title bar say so? The state behind `ProviderProblemPill`.
///
/// **A refused call lights it, not a stored verdict.** The shipped out-of-credit
/// pill read `LLMValidator`'s sticky verdict, so a key that had run dry in
/// January was still amber in March for someone who had come back only for their
/// old data. Settings validation still writes the verdict (the Settings dot is
/// the place that always tells), but it no longer raises the pill. Two sources
/// raise it, both a call that was actually made and refused:
/// - a finished run (`PipelineRunner.deriveFailureState`), which is something
///   the researcher asked for (`explicit`);
/// - the sidecar's `llm-failure` bridge post, for calls inside the report
///   (AutoCode, and any later call that reports), which are not.
///
/// **It is held to the verdict.** The record says what was refused; the verdict
/// cache for that key says whether that is still so. A new key or a good
/// re-validation clears it with no further bookkeeping; a run that worked
/// clears it directly (`noteRunSucceeded`), because for ChatGPT a good Settings
/// check proves nothing about credit.
///
/// **A refusal belongs to the key the call used.** A run's key is fingerprinted
/// at spawn, and a refusal that arrives after the key was replaced is dropped
/// and logged: stamping `.invalid` over a fresh, working key would put a false
/// red on both the pill and the Settings dot.
///
/// **Cloud-only.** Ollama has no credit and no key, so a local provider is never
/// here, which also keeps this pill and the Ollama download pill apart.
///
/// Every path that declines to record a refusal says so in the log: a pill that
/// silently never appears is worse than one that is wrong loudly.
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

    private static let log = Logger(subsystem: "app.bristlenose", category: "provider-problem")

    @Published private(set) var presented: Presented?

    /// "This network can't reach the provider": in memory only (see `NetworkBlock.swift`).
    struct NetworkBlock: Equatable {
        let provider: LLMProvider
        let firstSeen: Date
        var dismissed: Bool
    }
    @Published private(set) var networkBlock: NetworkBlock?
    private let probe: any NetworkProbing
    private let makeWatcher: () -> any NetworkPathWatching
    private var watcher: (any NetworkPathWatching)?
    /// A look is in flight: a refusal that arrives meanwhile joins it rather than asking
    /// Apple again.
    private var looking: Task<Void, Never>?
    /// When a look last found nothing, and which providers' calls worked while one ran.
    private var lastNegativeLook: Date?
    private var callsSucceededDuringLook: Set<String> = []
    static let negativeLookCooldown: TimeInterval = 60
    /// Whether a look is in flight (tests wait on it).
    var isLooking: Bool { looking != nil }

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

    /// Set once by the app, so a refusal can be announced to VoiceOver in the
    /// researcher's language. The model announces, not the pill: the pill is in
    /// every window and would announce once per window, and again on every
    /// launch for a record that is not news.
    var i18n: I18n?

    private let defaults: UserDefaults
    private let now: () -> Date
    private let activeProvider: () -> LLMProvider?
    private let keyFor: (LLMProvider) -> String?
    private let center: NotificationCenter
    private var observers: [NSObjectProtocol] = []
    /// So the "no readable key" line is written when that starts, not at every
    /// refresh (which runs on each app activation and prefs change).
    private var loggedNoReadableKey = false

    static let recordKey = "providerProblemRecord"

    init(
        defaults: UserDefaults = .standard,
        now: @escaping () -> Date = Date.init,
        activeProvider: @escaping () -> LLMProvider? = ProviderProblemModel.liveActiveProvider,
        keyFor: @escaping (LLMProvider) -> String? = ProviderProblemModel.liveKey,
        observing center: NotificationCenter = .default,
        probe: any NetworkProbing = LiveNetworkProbe(),
        makeWatcher: @escaping () -> any NetworkPathWatching = { LivePathWatcher() }
    ) {
        self.defaults = defaults
        self.now = now
        self.activeProvider = activeProvider
        self.keyFor = keyFor
        self.center = center
        self.probe = probe
        self.makeWatcher = makeWatcher
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
        // A call worked: a network block on that provider was about a moment that has passed.
        observers.append(center.addObserver(
            forName: .bristlenoseProviderCallSucceeded, object: nil, queue: .main
        ) { [weak self] note in
            let raw = note.object as? String
            Task { @MainActor in self?.providerCallSucceeded(raw) }
        })
        // Back to the app: a top-up or a new key happens in the browser or in
        // Settings, and the stage may have moved on while it was away.
        observers.append(center.addObserver(
            forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main
        ) { [weak self] _ in Task { @MainActor in self?.refresh() } })
    }

    deinit { observers.forEach(center.removeObserver) }

    // MARK: - Live sources

    nonisolated static func liveActiveProvider() -> LLMProvider? {
        UserDefaults.standard.string(forKey: "activeProvider").flatMap(LLMProvider.init(rawValue:))
    }

    /// The provider's stored key, or nil. Cloud providers only. Nil covers both
    /// "no key" and "the Keychain would not say" (a quiet read that was refused);
    /// callers must not treat it as proof the key is gone.
    @MainActor
    static func liveKey(_ provider: LLMProvider) -> String? {
        guard provider.needsAPIKey, let keychainProvider = provider.keychainProvider,
              let key = KeychainHelper.get(provider: keychainProvider), !key.isEmpty
        else { return nil }
        return key
    }

    /// The fingerprint of the key a call is about to use, for `recordRefusal`.
    @MainActor
    static func liveKeyFingerprint(_ provider: LLMProvider) -> String? {
        liveKey(provider).map(LLMValidator.keyFingerprint)
    }

    // MARK: - Reading

    /// Recompute `presented` from the stored record, the key's verdict and the
    /// clock. Called at launch, on activation and when a refusal is recorded; no
    /// timer calls it, so the stage never changes while someone is looking.
    func refresh() {
        refreshAccountProblem()
        if presented == nil { presentNetworkBlockIfAny() }
    }

    /// The account problem (a rejected key, no credit) from the stored record.
    private func refreshAccountProblem() {
        guard let record = Self.load(from: defaults) else {
            presented = nil
            return
        }
        guard let provider = LLMProvider(rawValue: record.provider) else {
            Self.log.notice("record names a provider this build does not know (\(record.provider, privacy: .public)): dropped")
            Self.clear(in: defaults)
            presented = nil
            return
        }
        // No readable key: "gone" and "the Keychain would not say right now" look
        // the same here, and only one of them means the record is stale. Say
        // nothing, keep it; a different key later fails `holds` and clears it.
        guard let key = keyFor(provider) else {
            if !loggedNoReadableKey {
                Self.log.info("no readable key for \(provider.rawValue, privacy: .public): showing nothing, keeping the record")
                loggedNoReadableKey = true
            }
            presented = nil
            return
        }
        loggedNoReadableKey = false
        // A record is about one key. A different key now (pasted in Settings, which
        // validates it on the spot) makes it untrue of anything, whatever the new
        // key's own check says, and that matters most where a good check cannot see
        // credit: there only this tells a new funded key from the old empty one.
        if let was = record.keyFingerprint, was != LLMValidator.keyFingerprint(key) {
            Self.log.info("\(record.condition.rawValue, privacy: .public) on \(provider.rawValue, privacy: .public) was about a key that has been replaced: cleared")
            Self.clear(in: defaults)
            presented = nil
            return
        }
        // Held to the verdict for the key it was recorded against. Gone is gone:
        // the record is dropped, so a later refusal is news, not a repeat.
        let verdict = LLMValidator.cachedVerdict(provider: provider, key: key)
        guard ProviderProblemRules.holds(
            record, verdictForItsKey: verdict, settingsCheckSeesCredit: provider.settingsCheckSeesCredit
        ) else {
            Self.log.info("\(record.condition.rawValue, privacy: .public) on \(provider.rawValue, privacy: .public) no longer holds (verdict \(verdict?.rawValue ?? "none", privacy: .public)): cleared")
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

    /// The ✕. Hides an account problem until the next refusal that counts (`applying`).
    /// A network block, once hidden, stays hidden until it clears (a network change, a call
    /// that worked, a provider switch): it is about a place, and a repeat from the same
    /// place has nothing new to say.
    func dismiss() {
        if presented?.condition == .networkBlocks, var block = networkBlock {
            block.dismissed = true
            networkBlock = block
            refresh()
            return
        }
        guard var record = Self.load(from: defaults) else {
            Self.log.notice("dismiss with no record to hide: refreshing so the pill and the store agree")
            refresh()
            return
        }
        record.dismissed = true
        Self.save(record, to: defaults)
        refresh()
    }

    // MARK: - Announcing

    /// Said to VoiceOver once, where a refusal becomes news. High for an error
    /// (as a failed key check is, `ValidationAnnouncement`), medium for a warning.
    func announce(_ condition: ProviderProblemCondition, provider: LLMProvider) {
        guard let i18n else {
            Self.log.info("announcement skipped: the app has not given the model its translator yet")
            return
        }
        let presentation = ProviderProblemPresentation(condition: condition)
        let priority: NSAccessibilityPriorityLevel = condition.kind == .error ? .high : .medium
        NSAccessibility.post(
            element: NSApp as Any, notification: .announcementRequested,
            userInfo: [
                .announcement: presentation.title(provider: provider.displayName, i18n: i18n),
                .priority: priority.rawValue,
            ])
    }

    // MARK: - A network block (in memory)

    /// A call to `provider` was refused in a way that may be this network's doing (see
    /// `NetworkBlockCandidate`). Asks once whether the internet works from here; if it
    /// does, the provider could not be reached and the pill says so. Only for the active
    /// cloud provider, and never when an account problem is already on show.
    func noteNetworkRefusal(provider: LLMProvider, explicit: Bool = false) {
        guard provider.needsAPIKey, activeProvider() == provider else {
            Self.log.notice("network refusal for \(provider.rawValue, privacy: .public) not looked at: not the active cloud provider")
            return
        }
        // An account problem is the truer thing to say, and a block stored behind it would
        // surface, stale, the day that clears. A record the researcher hid still outranks it:
        // the ✕ on one problem must not reveal another.
        if let shown = presented, shown.condition != .networkBlocks {
            Self.log.notice("network refusal on \(provider.rawValue, privacy: .public) not looked at: \(shown.condition.rawValue, privacy: .public) is on show")
            return
        }
        if let record = Self.load(from: defaults), record.provider == provider.rawValue {
            Self.log.notice("network refusal on \(provider.rawValue, privacy: .public) not looked at: \(record.condition.rawValue, privacy: .public) is on record (hidden)")
            return
        }
        if let block = networkBlock, block.provider == provider {
            // Something the researcher asked for (a run) failed here again: bring a hidden
            // notice back, with no second look. An incidental repeat has nothing new to say.
            if block.dismissed, explicit {
                var shown = block
                shown.dismissed = false
                networkBlock = shown
                Self.log.notice("network refusal on \(provider.rawValue, privacy: .public): a refused run brings the hidden block back")
                refresh()
            } else {
                Self.log.notice("network refusal on \(provider.rawValue, privacy: .public): a block is already held (\(block.dismissed ? "hidden" : "shown", privacy: .public)), not looked at again")
            }
            return
        }
        if looking != nil {
            Self.log.notice("network refusal joins the look already under way")
            return
        }
        // A look that found nothing is not repeated for a minute: a signal refresh or an
        // AutoCode pass on a dead network makes a refusal per call, and each is not a
        // reason to ask Apple again.
        if let at = lastNegativeLook, now().timeIntervalSince(at) < Self.negativeLookCooldown {
            Self.log.notice("network refusal on \(provider.rawValue, privacy: .public) not looked at: the last look found nothing less than a minute ago")
            return
        }
        callsSucceededDuringLook = []
        looking = Task { @MainActor [weak self] in
            guard let self else { return }
            defer { self.looking = nil }
            let seen = await self.probe.look(provider: provider)
            guard NetworkBlockVerdict.blocks(path: seen.path, control: seen.control, provider: seen.provider) else {
                self.lastNegativeLook = self.now()
                Self.log.notice("network refusal on \(provider.rawValue, privacy: .public): not this network's doing (path satisfied=\(seen.path?.satisfied.description ?? "unknown", privacy: .public) control=\(String(describing: seen.control), privacy: .public) provider=\(String(describing: seen.provider), privacy: .public))")
                return
            }
            guard self.activeProvider() == provider else {
                Self.log.notice("network block on \(provider.rawValue, privacy: .public) dropped: the provider changed during the look")
                return
            }
            if self.callsSucceededDuringLook.contains(provider.rawValue) {
                Self.log.notice("network block on \(provider.rawValue, privacy: .public) dropped: a call to it worked during the look")
                return
            }
            self.networkBlock = NetworkBlock(provider: provider, firstSeen: self.now(), dismissed: false)
            self.watcher?.stop()
            let watcher = self.makeWatcher()
            self.watcher = watcher
            watcher.start(baseline: seen.path?.signature) { [weak self] in
                Task { @MainActor in self?.clearNetworkBlock(because: "the network changed") }
            }
            Self.log.notice("network blocks \(provider.rawValue, privacy: .public): the internet answers, the provider does not")
            self.refresh()
            if self.presented?.condition == .networkBlocks { self.announce(.networkBlocks, provider: provider) }
        }
    }

    /// Light the pill from the in-memory block, unless it was hidden or belongs to a
    /// provider that is no longer the active one (switch provider and it goes).
    private func presentNetworkBlockIfAny() {
        guard let block = networkBlock else { return }
        guard activeProvider() == block.provider else {
            clearNetworkBlock(because: "the provider changed")
            return
        }
        guard !block.dismissed else { return }
        if let record = Self.load(from: defaults), record.provider == block.provider.rawValue { return }
        let age = now().timeIntervalSince(block.firstSeen)
        let stage: ProviderProblemStage = age < ProviderProblemRules.loudFor ? .loud
            : age < ProviderProblemRules.settledFor ? .settled : .collapsed
        presented = Presented(provider: block.provider, condition: .networkBlocks, stage: stage)
    }

    func clearNetworkBlock(because why: String) {
        guard networkBlock != nil else { return }
        Self.log.notice("network block cleared: \(why, privacy: .public)")
        networkBlock = nil
        watcher?.stop()
        watcher = nil
        refresh()
    }

    private func providerCallSucceeded(_ raw: String?) {
        guard let raw else {
            Self.log.notice("provider-call-succeeded cue with no provider: ignored")
            return
        }
        if looking != nil { callsSucceededDuringLook.insert(raw) }
        guard networkBlock?.provider.rawValue == raw else { return }
        clearNetworkBlock(because: "a call to \(raw) worked")
    }

    // MARK: - Recording (called where a refusal is seen)

    /// A call was refused. Writes the verdict (so Settings and the pill agree),
    /// updates the record, tells the model, and announces it if it is news.
    ///
    /// - Parameter provider: the provider the call used; defaults to the active
    ///   one. Pass it explicitly so a switch mid-run can't blame the wrong one.
    /// - Parameter explicit: the researcher asked for this (a run), as opposed
    ///   to something incidental.
    /// - Parameter keyFingerprint: the fingerprint of the key the call used. If
    ///   the key held now is a different one, the refusal is not about it and is
    ///   dropped (logged). Nil when unknown (a reconnected run), which skips the
    ///   check.
    /// - Returns: whether a refusal was recorded. Every `false` is logged.
    @discardableResult
    static func recordRefusal(
        _ condition: ProviderProblemCondition,
        provider explicitProvider: LLMProvider? = nil,
        explicit: Bool,
        keyFingerprint: String? = nil,
        defaults: UserDefaults = .standard,
        now: Date = Date(),
        activeProvider: () -> LLMProvider? = ProviderProblemModel.liveActiveProvider,
        keyFor: (LLMProvider) -> String? = ProviderProblemModel.liveKey,
        center: NotificationCenter = .default,
        announce: @MainActor (ProviderProblemCondition, LLMProvider) -> Void = {
            ProviderProblemModel.shared.announce($0, provider: $1)
        }
    ) -> Bool {
        let what = condition.rawValue
        guard let provider = explicitProvider ?? activeProvider() else {
            log.notice("\(what, privacy: .public) refusal not recorded: no active provider")
            return false
        }
        guard provider.needsAPIKey else {
            log.notice("\(what, privacy: .public) refusal not recorded: \(provider.rawValue, privacy: .public) has no key to refuse")
            return false
        }
        guard let key = keyFor(provider) else {
            log.notice("\(what, privacy: .public) refusal not recorded: no readable key for \(provider.rawValue, privacy: .public)")
            return false
        }
        if let keyFingerprint, keyFingerprint != LLMValidator.keyFingerprint(key) {
            log.notice("\(what, privacy: .public) refusal for \(provider.rawValue, privacy: .public) not recorded: the key was replaced after the call was made")
            return false
        }
        guard let verdict = condition.verdict else {
            log.notice("\(what, privacy: .public) is not an account refusal: not recorded here")
            return false
        }
        LLMValidator.recordVerdict(provider: provider, key: key, status: verdict.status)
        let existing = load(from: defaults)
        let fingerprint = LLMValidator.keyFingerprint(key)
        let news = ProviderProblemRules.isNews(
            refusalOf: condition, provider: provider.rawValue, explicit: explicit,
            keyFingerprint: fingerprint, existing: existing)
        save(ProviderProblemRules.applying(
            refusalOf: condition, provider: provider.rawValue, explicit: explicit,
            keyFingerprint: fingerprint, to: existing, now: now), to: defaults)
        center.post(name: .bristlenoseProviderProblemChanged, object: nil)
        // News is the first of its kind, a changed condition, provider or key, or
        // a refused run. An incidental repeat is not, and nor is a record restored
        // at launch (which never passes through here). Said only when the pill will
        // show it: a refusal for a provider that is not the active one is kept but
        // is not on screen, so it is not spoken either.
        if news {
            if activeProvider() == provider {
                announce(condition, provider)
            } else {
                log.info("\(what, privacy: .public) on \(provider.rawValue, privacy: .public) is news but that provider is not active: recorded, not announced")
            }
        }
        return true
    }

    /// A run finished having made an LLM call with `provider`: whatever the
    /// pill said about it was wrong (R40). Clears the verdict where one says so,
    /// and the record whatever the verdict says (for ChatGPT a good Settings
    /// check overwrote the verdict while the account was still empty, so the
    /// verdict can no longer be the witness).
    static func noteRunSucceeded(
        provider: LLMProvider,
        defaults: UserDefaults = .standard,
        keyFor: (LLMProvider) -> String? = ProviderProblemModel.liveKey,
        center: NotificationCenter = .default
    ) {
        guard provider.needsAPIKey else { return }
        center.post(name: .bristlenoseProviderCallSucceeded, object: provider.rawValue)
        guard let key = keyFor(provider) else {
            // A run that worked proves any refusal on record stale, and clearing the
            // record needs no key. The verdict cannot be touched without one.
            let hadRecord = load(from: defaults)?.provider == provider.rawValue
            if hadRecord { clear(in: defaults) }
            log.notice("a run worked on \(provider.rawValue, privacy: .public) but its key could not be read: record \(hadRecord ? "cleared" : "absent"), verdict left as it is")
            if hadRecord { center.post(name: .bristlenoseProviderProblemChanged, object: nil) }
            return
        }
        let clearedVerdict = clearAfterSuccessfulRun(provider: provider, key: key)
        let hadRecord = load(from: defaults)?.provider == provider.rawValue
        if hadRecord { clear(in: defaults) }
        if clearedVerdict || hadRecord {
            log.info("a run that worked cleared the refusal on \(provider.rawValue, privacy: .public)")
            center.post(name: .bristlenoseProviderProblemChanged, object: nil)
        }
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

    /// The stored record. A record that no longer decodes (a later build changed
    /// the struct) is logged and dropped, so the store and the pill agree and the
    /// next refusal starts clean; it is not left to fail the same way forever.
    static func load(from defaults: UserDefaults) -> ProviderProblemRecord? {
        guard let data = defaults.data(forKey: recordKey) else { return nil }
        do {
            return try JSONDecoder().decode(ProviderProblemRecord.self, from: data)
        } catch {
            log.error("stored record did not decode (\(data.count, privacy: .public) bytes): dropped")
            defaults.removeObject(forKey: recordKey)
            return nil
        }
    }

    static func save(_ record: ProviderProblemRecord, to defaults: UserDefaults) {
        do {
            defaults.set(try JSONEncoder().encode(record), forKey: recordKey)
        } catch {
            log.error("could not encode the record: \(error.localizedDescription, privacy: .public)")
        }
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
        case .networkBlocks: return "Network blocks it (warning)"
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
