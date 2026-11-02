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
@MainActor
@Suite("ProviderProblemModel")
struct ProviderProblemModelTests {
    private let key = "sk-ant-test-key-1234567890"

    /// A reference type, so the model's closures see the clock, the active
    /// provider and the keys as the test changes them.
    @MainActor private final class Rig {
        let defaults: UserDefaults
        var clock = t0
        var active: LLMProvider?
        var keys: [LLMProvider: String]
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
                observing: NotificationCenter())
        }
    }

    /// Same isolation as `LLMValidatorTests`: a private verdict store and a
    /// private defaults suite per test.
    private func withRig(
        active: LLMProvider? = .claude, keys: [LLMProvider: String]? = nil,
        _ body: (Rig) -> Void
    ) {
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
        body(Rig(defaults: suite, active: active,
                 keys: keys ?? [.claude: key, .chatGPT: "sk-openai-test-key-123456"]))
    }

    private func refuse(_ rig: Rig, _ condition: ProviderProblemCondition,
                        provider: LLMProvider = .claude, explicit: Bool = true) {
        ProviderProblemModel.recordRefusal(
            condition, provider: provider, explicit: explicit, defaults: rig.defaults,
            now: rig.clock, activeProvider: { rig.active }, keyFor: { rig.keys[$0] },
            center: NotificationCenter())
    }

    @Test func aRefusedCallLightsItAndWritesTheVerdictSettingsShows() {
        withRig { rig in
            let model = rig.model()
            #expect(model.presented == nil)
            refuse(rig, .keyRejected)
            model.refresh()
            #expect(model.presented == .init(provider: .claude, condition: .keyRejected, stage: .loud))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .invalid,
                    "Settings and the pill must agree about the key")
        }
    }

    /// The shipped bug this replaces: a verdict recorded by Settings validation
    /// lit the pill for months over work that never needed the provider.
    @Test func aStoredVerdictAloneDoesNotLightIt() {
        withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            let model = rig.model()
            model.refresh()
            #expect(model.presented == nil, "a verdict nobody was refused on raised the pill")
        }
    }

    @Test func aLocalProviderNeverShows() {
        withRig(active: .ollama, keys: [:]) { rig in
            refuse(rig, .outOfCredit, provider: .ollama)
            let model = rig.model()
            #expect(model.presented == nil)
        }
    }

    @Test func theXHidesItAndAnIncidentalRepeatKeepsItHidden() {
        withRig { rig in
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

    @Test func aNewKeyClearsItAndTheRecord() {
        withRig { rig in
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

    @Test func aGoodRevalidationClearsIt() {
        withRig { rig in
            let model = rig.model()
            refuse(rig, .outOfCredit)
            model.refresh()
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            model.refresh()
            #expect(model.presented == nil)
        }
    }

    @Test func anotherActiveProviderHidesItWithoutForgettingIt() {
        withRig { rig in
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

    @Test func theStageMovesOnWhenItIsRefreshedNotBefore() {
        withRig { rig in
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

    @Test func aSuccessfulRunClearsBothVerdictsAndTheRecord() {
        withRig { rig in
            let model = rig.model()
            refuse(rig, .keyRejected)
            model.refresh()
            ProviderProblemModel.noteRunSucceeded(
                provider: .claude, defaults: rig.defaults, keyFor: { rig.keys[$0] },
                center: NotificationCenter())
            model.refresh()
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil)
            #expect(model.presented == nil)
            #expect(ProviderProblemModel.load(from: rig.defaults) == nil)
        }
    }

    // Ported from OutOfCreditModelTests (R40): the pill stayed lit after a top-up
    // and a successful run, because its verdict was sticky and nothing cleared it.
    @Test func aSuccessfulRunClearsOutOfCredit() {
        withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .outOfCredit)
            #expect(ProviderProblemModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil,
                    "the pill's verdict survived a run that worked")
        }
    }

    /// A run that made an LLM call with this key proves it is not rejected.
    @Test func aSuccessfulRunClearsARejectedKeyToo() {
        withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .invalid)
            #expect(ProviderProblemModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == nil)
        }
    }

    @Test func aSuccessfulRunLeavesAGoodVerdictAlone() {
        withRig { rig in
            LLMValidator.recordVerdict(provider: .claude, key: key, status: .online)
            #expect(!ProviderProblemModel.clearAfterSuccessfulRun(provider: .claude, key: key))
            #expect(LLMValidator.cachedVerdict(provider: .claude, key: key) == .ok)
        }
    }
}
