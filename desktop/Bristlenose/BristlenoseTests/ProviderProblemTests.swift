import Foundation
import Testing
@testable import Bristlenose

/// The decisions behind the title-bar provider-problem pill, and the model that
/// holds them. The argument for each rule is
/// `docs/mockups/provider-problem-surface.html`.

private let t0 = Date(timeIntervalSince1970: 1_800_000_000)

private func record(
    _ condition: ProviderProblemCondition = .outOfCredit,
    provider: String = "anthropic", firstSeen: Date = t0, dismissed: Bool = false
) -> ProviderProblemRecord {
    ProviderProblemRecord(provider: provider, condition: condition, firstSeen: firstSeen,
                          lastRefusal: firstSeen, dismissed: dismissed)
}

@Suite("ProviderProblemRules — stages")
struct ProviderProblemStageTests {
    @Test func loudFirstThenSettledThenCollapsed() {
        let r = record()
        func stage(_ after: TimeInterval) -> ProviderProblemStage? {
            ProviderProblemRules.stage(of: r, now: t0.addingTimeInterval(after))
        }
        #expect(stage(0) == .loud)
        #expect(stage(ProviderProblemRules.loudFor - 1) == .loud)
        #expect(stage(ProviderProblemRules.loudFor) == .settled)
        #expect(stage(ProviderProblemRules.settledFor - 1) == .settled)
        #expect(stage(ProviderProblemRules.settledFor) == .collapsed)
        #expect(stage(60 * 24 * 3600) == .collapsed, "a month on it is still the glyph, never gone")
    }

    @Test func hiddenIsNoStageAtAll() {
        #expect(ProviderProblemRules.stage(of: record(dismissed: true), now: t0) == nil)
        #expect(ProviderProblemRules.stage(
            of: record(dismissed: true), now: t0.addingTimeInterval(30 * 24 * 3600)) == nil)
    }

    @Test func aClockSetBackIsLoudNotNegative() {
        #expect(ProviderProblemRules.stage(of: record(), now: t0.addingTimeInterval(-3600)) == .loud)
    }
}

@Suite("ProviderProblemRules — a refusal")
struct ProviderProblemRefusalTests {
    private let later = t0.addingTimeInterval(3 * 24 * 3600)

    @Test func theFirstRefusalIsLoudAndShown() {
        let r = ProviderProblemRules.applying(
            refusalOf: .keyRejected, provider: "anthropic", explicit: false, to: nil, now: t0)
        #expect(r.condition == .keyRejected)
        #expect(r.firstSeen == t0 && !r.dismissed)
        #expect(ProviderProblemRules.stage(of: r, now: t0) == .loud)
    }

    /// Months of transcript edits on an empty account must not bring a hidden
    /// pill back each time one of them is refused.
    @Test func anIncidentalRepeatOfAHiddenConditionStaysHidden() {
        let hidden = record(.outOfCredit, dismissed: true)
        let r = ProviderProblemRules.applying(
            refusalOf: .outOfCredit, provider: "anthropic", explicit: false, to: hidden, now: later)
        #expect(r.dismissed, "an incidental refusal brought back a pill the researcher hid")
        #expect(r.firstSeen == t0, "an incidental refusal restarted the clock")
        #expect(r.lastRefusal == later)
    }

    @Test func anIncidentalRepeatDoesNotRewindACollapsedPill() {
        let r = ProviderProblemRules.applying(
            refusalOf: .outOfCredit, provider: "anthropic", explicit: false, to: record(), now: later)
        #expect(ProviderProblemRules.stage(of: r, now: later) == .collapsed)
    }

    /// They asked for a run and met the wall again: say so, loudly.
    @Test func aRefusedRunBringsItBackLoud() {
        let hidden = record(.outOfCredit, dismissed: true)
        let r = ProviderProblemRules.applying(
            refusalOf: .outOfCredit, provider: "anthropic", explicit: true, to: hidden, now: later)
        #expect(!r.dismissed)
        #expect(ProviderProblemRules.stage(of: r, now: later) == .loud)
    }

    @Test func aChangedConditionIsNewsEvenWhenIncidental() {
        let hidden = record(.outOfCredit, dismissed: true)
        let r = ProviderProblemRules.applying(
            refusalOf: .keyRejected, provider: "anthropic", explicit: false, to: hidden, now: later)
        #expect(r.condition == .keyRejected && !r.dismissed)
        #expect(ProviderProblemRules.stage(of: r, now: later) == .loud)
    }

    @Test func aChangedProviderIsNewsEvenWhenIncidental() {
        let hidden = record(.outOfCredit, provider: "anthropic", dismissed: true)
        let r = ProviderProblemRules.applying(
            refusalOf: .outOfCredit, provider: "openai", explicit: false, to: hidden, now: later)
        #expect(r.provider == "openai" && !r.dismissed)
    }

    @Test func newsIsTheFirstOfItsKindAChangeOrARefusedRunNeverAnIncidentalRepeat() {
        func news(_ c: ProviderProblemCondition, _ provider: String = "anthropic", explicit: Bool,
                  existing: ProviderProblemRecord?) -> Bool {
            ProviderProblemRules.isNews(refusalOf: c, provider: provider, explicit: explicit, existing: existing)
        }
        #expect(news(.outOfCredit, explicit: false, existing: nil))
        #expect(!news(.outOfCredit, explicit: false, existing: record(.outOfCredit)))
        #expect(!news(.outOfCredit, explicit: false, existing: record(.outOfCredit, dismissed: true)))
        #expect(news(.outOfCredit, explicit: true, existing: record(.outOfCredit)))
        #expect(news(.keyRejected, explicit: false, existing: record(.outOfCredit)))
        #expect(news(.outOfCredit, "openai", explicit: false, existing: record(.outOfCredit)))
    }

    @Test func theSameRefusalAboutADifferentKeyIsNews() {
        var known = record(.outOfCredit)
        known.keyFingerprint = "key-a"
        func news(_ fp: String?) -> Bool {
            ProviderProblemRules.isNews(refusalOf: .outOfCredit, provider: "anthropic", explicit: false,
                                        keyFingerprint: fp, existing: known)
        }
        #expect(!news("key-a"))
        #expect(news("key-b"), "a different key's refusal was taken for a repeat")
        #expect(!news(nil), "an unknown key must not be taken for a different one")
    }

    /// A record written before it carried the key's fingerprint still decodes.
    @Test func aRecordWithoutAFingerprintStillDecodes() throws {
        let json = #"{"provider":"anthropic","condition":"outOfCredit","firstSeen":0,"lastRefusal":0,"dismissed":false}"#
        let r = try JSONDecoder().decode(ProviderProblemRecord.self, from: Data(json.utf8))
        #expect(r.keyFingerprint == nil)
    }

    /// ChatGPT's Settings check is a free model list that returns 200 for a
    /// bankrupt key, so a good result there is not a cure.
    @Test func aGoodCheckDoesNotCureCreditWhereTheCheckCannotSeeCredit() {
        let r = record(.outOfCredit)
        #expect(ProviderProblemRules.holds(r, verdictForItsKey: .ok, settingsCheckSeesCredit: false))
        #expect(!ProviderProblemRules.holds(r, verdictForItsKey: .ok, settingsCheckSeesCredit: true))
        // ...but it does cure a rejected key, which every check can see.
        #expect(!ProviderProblemRules.holds(record(.keyRejected), verdictForItsKey: .ok,
                                            settingsCheckSeesCredit: false))
        #expect(LLMProvider.claude.settingsCheckSeesCredit)
        #expect(!LLMProvider.chatGPT.settingsCheckSeesCredit)
    }

    @Test func aRecordHoldsOnlyWhileTheKeysVerdictStillSaysSo() {
        let r = record(.keyRejected)
        #expect(ProviderProblemRules.holds(r, verdictForItsKey: .invalid))
        #expect(!ProviderProblemRules.holds(r, verdictForItsKey: .ok), "a good re-validation must clear it")
        #expect(!ProviderProblemRules.holds(r, verdictForItsKey: nil), "a new key has no verdict: gone")
        #expect(!ProviderProblemRules.holds(r, verdictForItsKey: .outOfCredit))
    }
}

@Suite("ProviderProblemCondition — where a refusal is read")
struct ProviderProblemSourceTests {
    @Test func theBridgeKindsWeActOn() {
        #expect(ProviderProblemCondition.fromLLMFailureKind("out_of_credit") == .outOfCredit)
        #expect(ProviderProblemCondition.fromLLMFailureKind("invalid_key") == .keyRejected)
    }

    /// A rate limit is transient and the verdict cache is sticky: acting on it
    /// would leave a durable amber for a condition that cleared in seconds.
    @Test func everyOtherBridgeKindIsLeftAlone() {
        for kind in ["rate_limited", "server_error", "network", "model_unavailable",
                     "bad_request", "unknown", "", nil] as [String?] {
            #expect(ProviderProblemCondition.fromLLMFailureKind(kind) == nil, "\(kind ?? "nil")")
        }
    }

    @Test func aRunsBillingFailureCountsWhereverItWasRead() {
        #expect(ProviderProblemCondition.fromRun(category: .outOfCredit, structured: true) == .outOfCredit)
        #expect(ProviderProblemCondition.fromRun(category: .outOfCredit, structured: false) == .outOfCredit)
    }

    /// The stderr fallback matches `401` and `authentication` anywhere in the
    /// tail, and it has been wrong before. A guess must not light a global pill.
    @Test func aRunsRejectedKeyCountsOnlyFromTheStructuredCause() {
        #expect(ProviderProblemCondition.fromRun(category: .auth, structured: true) == .keyRejected)
        #expect(ProviderProblemCondition.fromRun(category: .auth, structured: false) == nil,
                "a stderr guess lit the app-wide pill")
    }

    @Test func noOtherRunCategoryRaisesIt() {
        for c in [PipelineFailureCategory.network, .quota, .disk, .whisper, .unknown, .userSignal] {
            #expect(ProviderProblemCondition.fromRun(category: c, structured: true) == nil, "\(c)")
        }
    }
}

@Suite("ProviderProblemPresentation")
struct ProviderProblemPresentationTests {
    @Test func theGlyphIsTheKindNotAnInvention() {
        #expect(ProviderProblemPresentation(condition: .keyRejected).kind == .error)
        #expect(ProviderProblemPresentation(condition: .outOfCredit).kind == .warning)
    }

    /// Two buttons at most, the default last; and "Switch provider…" only where
    /// it is a different act from the primary one.
    @Test func theButtons() {
        #expect(ProviderProblemPresentation(condition: .outOfCredit).actions == [.switchProvider, .addFunds])
        #expect(ProviderProblemPresentation(condition: .keyRejected).actions == [.openSettings])
        for c in ProviderProblemCondition.allCases {
            let actions = ProviderProblemPresentation(condition: c).actions
            #expect(actions.count <= 2, "a third button is back")
            #expect(Set(actions).count == actions.count)
        }
    }

    @Test func theShippedOutOfCreditWordsAreKept() {
        let p = ProviderProblemPresentation(condition: .outOfCredit)
        #expect(p.pillKey == "desktop.outOfCredit.pill")
        #expect(p.titleKey == "desktop.outOfCredit.title")
        #expect(p.bodyKey == "desktop.outOfCredit.body")
        #expect(p.usesPrintfProviderFormat)
        #expect(!ProviderProblemPresentation(condition: .keyRejected).usesPrintfProviderFormat)
    }

    @Test func theKindWordsAreThePairTheVoiceoverValueUses() {
        #expect(ProviderProblemPresentation(condition: .keyRejected).kindWordKey
                == "desktop.providerProblem.kind.error")
        #expect(ProviderProblemPresentation(condition: .outOfCredit).kindWordKey
                == "desktop.providerProblem.kind.warning")
    }
}

/// The model, with a private defaults suite, a fixed clock and a fake key store.
///
/// `.serialized` and the swap of `LLMValidator.verdictStore` (process-global):
/// two tests interleaving would restore each other's throwaway store. Not
/// `async`-safe if a test here ever suspends while another suite swaps it too;
/// `LLMValidatorTests` swaps it the same way and is not serialised.
@MainActor
@Suite("ProviderProblemModel", .serialized)
struct ProviderProblemModelTests {
    private let key = "sk-ant-test-key-1234567890"

    /// A reference type, so the model's closures see the clock, the active
    /// provider and the keys as the test changes them. One notification centre
    /// is shared by the model and `refuse`, so the model's observer is proven.
    @MainActor private final class Rig {
        let defaults: UserDefaults
        let center = NotificationCenter()
        var clock = t0
        var active: LLMProvider?
        var keys: [LLMProvider: String]
        var announced: [(ProviderProblemCondition, LLMProvider)] = []
        init(defaults: UserDefaults, active: LLMProvider?, keys: [LLMProvider: String]) {
            self.defaults = defaults
            self.active = active
            self.keys = keys
        }
        func model() -> ProviderProblemModel {
            ProviderProblemModel(
                defaults: defaults, now: { [unowned self] in self.clock },
                activeProvider: { [unowned self] in self.active },
                keyFor: { [unowned self] in self.keys[$0] },
                observing: center)
        }
    }

    private func withRig(
        active: LLMProvider? = .claude, keys: [LLMProvider: String]? = nil,
        _ body: (Rig) async -> Void
    ) async {
        let suiteName = "ProviderProblemModelTests-\(UUID().uuidString)"
        let suite = UserDefaults(suiteName: suiteName)!
        let verdicts = UserDefaults(suiteName: suiteName + "-verdicts")!
        let original = LLMValidator.verdictStore
        LLMValidator.verdictStore = verdicts
        defer {
            LLMValidator.verdictStore = original
            suite.removePersistentDomain(forName: suiteName)
            verdicts.removePersistentDomain(forName: suiteName + "-verdicts")
        }
        await body(Rig(defaults: suite, active: active,
                       keys: keys ?? [.claude: key, .chatGPT: "sk-openai-test-key-123456",
                                      .ollama: "not-a-key"]))
    }

    @discardableResult
    private func refuse(_ rig: Rig, _ condition: ProviderProblemCondition,
                        provider: LLMProvider = .claude, explicit: Bool = true,
                        fingerprint: String? = nil) -> Bool {
        ProviderProblemModel.recordRefusal(
            condition, provider: provider, explicit: explicit, keyFingerprint: fingerprint,
            defaults: rig.defaults, now: rig.clock,
            activeProvider: { rig.active }, keyFor: { rig.keys[$0] }, center: rig.center,
            announce: { rig.announced.append(($0, $1)) })
    }

    /// Looks at a condition 10 ms apart, as the runner tests do: a look is spent
    /// only when it happens, so a starved main actor costs time, never the verdict.
    private func settle(_ looks: Int = 300, _ condition: () -> Bool) async {
        for _ in 0..<looks {
            if condition() { return }
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    // MARK: - Lighting it

    @Test func aRefusedCallLightsItAndWritesTheVerdictSettingsShows() async {
        await withRig { rig in
            let model = rig.model()
            #expect(model.presented == nil)
            refuse(rig, .keyRejected)
            model.refresh()
            #expect(model.presented == .init(provider: .claude, condition: .keyRejected, stage: .loud))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .invalid,
                    "Settings and the pill must agree about the key")
        }
    }

    /// The notification is how a refusal reaches a model that is already running:
    /// no manual refresh. The negative twin settles as long.
    @Test func aRecordedRefusalReachesARunningModelThroughTheNotification() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            await settle { model.presented != nil }
            #expect(model.presented?.condition == .outOfCredit, "the model never heard the refusal")
        }
    }

    @Test func aModelThatWasNotToldDoesNotChangeItsMind() async {
        await withRig { rig in
            let model = rig.model()
            // Written straight to the store, with no notification.
            ProviderProblemModel.save(record(.outOfCredit), to: rig.defaults)
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            await settle(30) { model.presented != nil }
            #expect(model.presented == nil)
        }
    }

    /// The shipped bug this replaces: a verdict recorded by Settings validation
    /// lit the pill for months over work that never needed the provider.
    @Test func aStoredVerdictAloneDoesNotLightIt() async {
        await withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            let model = rig.model()
            model.refresh()
            #expect(model.presented == nil, "a verdict nobody was refused on raised the pill")
        }
    }

    // MARK: - Declining to record, and saying so

    @Test func aLocalProviderNeverShowsAndIsNotRecorded() async {
        await withRig(active: .ollama) { rig in
            // Given a "key" so that only the provider check can be what stops it.
            #expect(rig.keys[.ollama] != nil)
            #expect(refuse(rig, .outOfCredit, provider: .ollama) == false)
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil)
            #expect(rig.announced.isEmpty)
        }
    }

    @Test func aRefusalWithNoProviderOrNoKeyIsNotRecorded() async {
        await withRig(active: nil, keys: [:]) { rig in
            #expect(ProviderProblemModel.recordRefusal(
                .keyRejected, explicit: true, defaults: rig.defaults, now: rig.clock,
                activeProvider: { nil }, keyFor: { _ in nil }, center: rig.center,
                announce: { rig.announced.append(($0, $1)) }) == false, "no active provider")
            #expect(refuse(rig, .keyRejected) == false, "no readable key")
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil)
        }
    }

    /// A run was started with one key; Settings now holds another. The refusal is
    /// not about the new key, and stamping `.invalid` over it would put a false red
    /// on the pill and the Settings dot.
    @Test func aRefusalForAKeyThatWasReplacedIsNotRecorded() async {
        await withRig { rig in
            let used = LLMValidator.keyFingerprint(key)
            rig.keys[.claude] = "sk-ant-a-different-key-0987654321"
            #expect(refuse(rig, .keyRejected, fingerprint: used) == false)
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: rig.keys[.claude]!) == nil,
                    "stamped a verdict on a key that was never tried")
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil)
            // The key the run really used is recorded.
            #expect(refuse(rig, .keyRejected, fingerprint: LLMValidator.keyFingerprint(rig.keys[.claude]!)))
        }
    }

    // MARK: - Hiding it

    @Test func theXHidesItAndAnIncidentalRepeatKeepsItHidden() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            model.dismiss()
            #expect(model.presented == nil)
            rig.clock = t0.addingTimeInterval(3600)
            refuse(rig, .outOfCredit, explicit: false)
            model.refresh()
            #expect(model.presented == nil, "months of edits would bring it back each time")
            // ...but a run they asked for, refused, does.
            refuse(rig, .outOfCredit, explicit: true)
            model.refresh()
            #expect(model.presented?.stage == .loud)
        }
    }

    @Test func dismissingWithNothingStoredStillLeavesPillAndStoreAgreeing() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            #expect(model.presented != nil)
            ProviderProblemModel.clear(in: rig.defaults)   // cleared between draw and click
            model.dismiss()
            #expect(model.presented == nil, "a ✕ on a pill with no record left it on screen")
        }
    }

    // MARK: - Clearing it

    @Test func aNewKeyClearsItAndTheRecord() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .keyRejected)
            model.refresh()
            #expect(model.presented != nil)
            rig.keys[.claude] = "sk-ant-a-different-key-0987654321"
            model.refresh()
            #expect(model.presented == nil)
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil, "the dead record was kept")
        }
    }

    /// "Could not read" and "gone" both arrive as nil. Only one of them means the
    /// record is stale; a transient Keychain refusal must not delete it.
    @Test func aKeyThatCannotBeReadHidesItButKeepsTheRecord() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .keyRejected)
            model.refresh()
            let readable = rig.keys[.claude]
            rig.keys[.claude] = nil
            model.refresh()
            #expect(model.presented == nil)
            #expect(ProviderProblemModel.load(from: rig.defaults) != nil,
                    "one refused Keychain read erased a live refusal")
            rig.keys[.claude] = readable
            model.refresh()
            #expect(model.presented?.condition == .keyRejected)
        }
    }

    @Test func aGoodRevalidationClearsIt() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            model.refresh()
            #expect(model.presented == nil)
        }
    }

    /// ChatGPT's Settings check is unbilled and says "fine" for a bankrupt key:
    /// opening Settings must not wipe the pill, nor the hidden state that stops
    /// the next incidental refusal from bringing it back loud.
    @Test func aGoodSettingsCheckDoesNotCureChatGPTsCredit() async {
        await withRig(active: .chatGPT) { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit, provider: .chatGPT)
            model.refresh()
            model.dismiss()
            LLMValidator.recordVerdict(provider: .chatGPT, key: rig.keys[.chatGPT]!, status: .online)
            model.refresh()
            #expect(ProviderProblemModel.load(from: rig.defaults)?.dismissed == true,
                    "a Settings visit forgot that it was hidden")
            rig.clock = t0.addingTimeInterval(3600)
            refuse(rig, .outOfCredit, provider: .chatGPT, explicit: false)
            model.refresh()
            #expect(model.presented == nil, "the account is still empty and it was hidden")
        }
    }

    /// ChatGPT's Settings check validates a pasted key on the spot and cannot see
    /// credit, so it says "fine" for the new key as it did for the old empty one.
    /// Only the key's identity can tell the two apart.
    @Test func aNewFundedChatGPTKeyClearsCreditEvenThoughItsCheckCannotSeeCredit() async {
        await withRig(active: .chatGPT) { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit, provider: .chatGPT)
            model.refresh()
            #expect(model.presented != nil)
            rig.keys[.chatGPT] = "sk-openai-a-funded-key-9988776655"
            LLMValidator.recordVerdict(provider: .chatGPT, key: rig.keys[.chatGPT]!, status: .online)
            model.refresh()
            #expect(model.presented == nil, "the pill kept saying no credit over a different key")
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil)
        }
    }

    @Test func aRecordedRefusalCarriesTheKeyItWasAbout() async {
        await withRig { rig in
            refuse(rig, .keyRejected)
            #expect(ProviderProblemModel.load(from: rig.defaults)?.keyFingerprint
                    == LLMValidator.keyFingerprint(key))
        }
    }

    /// A refusal on a provider that is not the active one is kept, but nothing is
    /// on screen for it, so nothing is spoken either.
    @Test func aRefusalThatWillNotBeShownIsNotAnnounced() async {
        await withRig(active: .claude) { rig in
            #expect(refuse(rig, .outOfCredit, provider: .chatGPT))
            #expect(rig.announced.isEmpty, "spoke about a pill that is not on screen")
            #expect(ProviderProblemModel.load(from: rig.defaults)?.provider == "openai")
        }
    }

    @Test func anotherActiveProviderHidesItWithoutForgettingIt() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            rig.active = .chatGPT
            model.refresh()
            #expect(model.presented == nil)
            rig.active = .claude
            model.refresh()
            #expect(model.presented?.condition == .outOfCredit,
                    "switching back to a provider that is still refusing should say so")
        }
    }

    @Test func theStageMovesOnWhenItIsRefreshedNotBefore() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            #expect(model.presented?.stage == .loud)
            rig.clock = t0.addingTimeInterval(ProviderProblemRules.settledFor + 60)
            #expect(model.presented?.stage == .loud, "the stage must not change under the pointer")
            model.refresh()
            #expect(model.presented?.stage == .collapsed)
        }
    }

    // MARK: - Across a relaunch

    @Test func aRelaunchedModelFindsTheRefusalWhereItWas() async {
        await withRig { rig in
            refuse(rig, .keyRejected)
            let relaunched = rig.model()
            #expect(relaunched.presented == .init(provider: .claude, condition: .keyRejected, stage: .loud))
            #expect(ProviderProblemModel.load(from: rig.defaults)?.firstSeen == t0,
                    "the refusal's date did not survive the round trip")
        }
    }

    @Test func aRelaunchedModelKeepsAHiddenPillHidden() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            model.dismiss()
            #expect(rig.model().presented == nil)
        }
    }

    /// A later build changes the record's shape: the old one must not fail to
    /// decode forever, silently.
    @Test func aRecordThatNoLongerDecodesIsDroppedNotKept() async {
        await withRig { rig in
            rig.defaults.set(Data(#"{"provider":"anthropic","condition":"outOfCredit"}"#.utf8),
                             forKey: ProviderProblemModel.recordKey)
            #expect(rig.model().presented == nil)
            #expect(rig.defaults.data(forKey: ProviderProblemModel.recordKey) == nil)
        }
    }

    // MARK: - Announcing it

    /// Once, where a refusal becomes news; never for an incidental repeat, and
    /// never from a record that was merely restored at launch.
    @Test func aRefusalIsAnnouncedWhenItIsNewsAndNotWhenItRepeats() async {
        await withRig { rig in
            refuse(rig, .keyRejected)
            #expect(rig.announced.map(\.0) == [.keyRejected])
            refuse(rig, .keyRejected, explicit: false)
            #expect(rig.announced.count == 1, "an incidental repeat spoke again")
            rig.clock = t0.addingTimeInterval(60)
            refuse(rig, .keyRejected, explicit: true)
            #expect(rig.announced.count == 2, "a refused run is news")
            refuse(rig, .outOfCredit, explicit: false)
            #expect(rig.announced.map(\.0) == [.keyRejected, .keyRejected, .outOfCredit],
                    "a changed condition is news even when incidental")
            _ = rig.model()
            #expect(rig.announced.count == 3, "restoring a record at launch announced it again")
        }
    }

    // MARK: - A run that worked

    @Test func aSuccessfulRunClearsBothVerdictsAndTheRecord() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .keyRejected)
            model.refresh()
            ProviderProblemModel.noteRunSucceeded(
                provider: .claude, defaults: rig.defaults, keyFor: { rig.keys[$0] }, center: rig.center)
            model.refresh()
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil)
            #expect(model.presented == nil)
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil)
        }
    }

    /// ChatGPT's verdict was overwritten with "fine" by a Settings visit while the
    /// account stayed empty, so the verdict cannot be the witness that a run worked.
    @Test func aSuccessfulRunClearsTheRecordEvenWhenTheVerdictSaysFine() async {
        await withRig(active: .chatGPT) { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit, provider: .chatGPT)
            LLMValidator.recordVerdict(provider: .chatGPT, key: rig.keys[.chatGPT]!, status: .online)
            model.refresh()
            #expect(model.presented != nil, "precondition: the good check left it standing")
            ProviderProblemModel.noteRunSucceeded(
                provider: .chatGPT, defaults: rig.defaults, keyFor: { rig.keys[$0] }, center: rig.center)
            await settle { model.presented == nil }
            #expect(model.presented == nil)
        }
    }

    @Test func aSuccessfulRunClearsTheRecordEvenWhenTheKeyCannotBeRead() async {
        await withRig { rig in
            let model = rig.model()
            refuse(rig, .keyRejected)
            model.refresh()
            ProviderProblemModel.noteRunSucceeded(
                provider: .claude, defaults: rig.defaults, keyFor: { _ in nil }, center: rig.center)
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil,
                    "a run that worked left the refusal standing because the Keychain would not answer")
        }
    }

    // Ported from OutOfCreditModelTests (R40): the pill stayed lit after a top-up
    // and a successful run, because its verdict was sticky and nothing cleared it.
    @Test func aSuccessfulRunClearsOutOfCredit() async {
        await withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            #expect(ProviderProblemModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil,
                    "the pill's verdict survived a run that worked")
        }
    }

    /// A run that made an LLM call with this key proves it is not rejected.
    @Test func aSuccessfulRunClearsARejectedKeyToo() async {
        await withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            #expect(ProviderProblemModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil)
        }
    }

    @Test func aSuccessfulRunLeavesAGoodVerdictAlone() async {
        await withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            #expect(!ProviderProblemModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
        }
    }
}
