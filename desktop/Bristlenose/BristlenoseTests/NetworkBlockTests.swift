import Foundation
import Testing

@testable import Bristlenose

/// "This network can't reach Claude" (mockup section H): which refusals are worth a look,
/// what the look decides, and how the pill's in-memory state is lit, hidden and cleared.
/// No test touches the network: the probe and the path watcher are fakes.
@MainActor
@Suite("NetworkBlock", .serialized)
struct NetworkBlockTests {
    // MARK: the pure rules

    @Test func onlyACallThatMayHaveBeenStoppedByTheNetworkIsACandidate() {
        func c(_ p: LLMProvider, _ kind: String, _ phase: String?, _ sig: Bool? = nil) -> Bool {
            NetworkBlockCandidate.isCandidate(provider: p, kind: kind, phase: phase, providerSignature: sig)
        }
        #expect(c(.claude, "network", "connect"))
        #expect(c(.claude, "network", "tls"))
        #expect(c(.chatGPT, "network", "dns"))
        #expect(c(.claude, "unknown", "http", false), "a reply that was not the provider's")
        #expect(c(.claude, "server_error", "http", false))
        #expect(!c(.claude, "network", "response"), "a slow read: the server accepted the call")
        #expect(!c(.claude, "network", "unknown"))
        #expect(!c(.claude, "network", nil))
        #expect(!c(.ollama, "network", "connect"), "a local server is not about this network")
        #expect(!c(.ollama, "unknown", "http", false))
        #expect(!c(.azure, "network", "dns"), "a mistyped Azure resource name fails the same way")
        #expect(c(.azure, "network", "connect"))
        #expect(!c(.claude, "rate_limited", "http", true))
        #expect(!c(.claude, "invalid_key", "http", true))
    }

    @Test func aFailedRunCannotSayWhereItDiedSoOnlyLocalAndAzureAreExcluded() {
        #expect(NetworkBlockCandidate.isRunCandidate(provider: .claude))
        #expect(NetworkBlockCandidate.isRunCandidate(provider: .chatGPT))
        #expect(NetworkBlockCandidate.isRunCandidate(provider: .gemini))
        #expect(!NetworkBlockCandidate.isRunCandidate(provider: .azure))
        #expect(!NetworkBlockCandidate.isRunCandidate(provider: .ollama))
    }

    @Test func theNetworkBlocksOnlyWhenARouteExistsTheInternetAnswersAndTheProviderDoesNot() {
        let up = PathSnapshot(satisfied: true, signature: "a")
        let down = PathSnapshot(satisfied: false, signature: "b")
        func b(_ p: PathSnapshot?, _ c: ControlResult, _ r: ProviderReach) -> Bool {
            NetworkBlockVerdict.blocks(path: p, control: c, provider: r)
        }
        #expect(b(up, .reached, .notReached))
        #expect(b(nil, .reached, .notReached), "no path sample does not veto")
        #expect(!b(up, .reached, .reached), "the provider answers from here: a slept laptop, a slow read, a bad endpoint")
        #expect(!b(down, .reached, .notReached), "offline")
        #expect(!b(up, .failed, .notReached), "internet down, a wrong clock, an inspecting proxy")
        #expect(!b(up, .answeredOtherwise, .notReached), "a sign-in page is not named here")
        #expect(!b(nil, .failed, .notReached))
    }

    @Test func theControlPageIsApplesExactlyAndAProviderReplyIsTheProvidersJSON() {
        let apple = "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"
        #expect(ControlResult.from(status: 200, body: apple) == .reached)
        #expect(ControlResult.from(status: 200, body: "<html>Successfully connected</html>") == .answeredOtherwise)
        #expect(ControlResult.from(status: 302, body: apple) == .answeredOtherwise)
        #expect(ControlResult.from(status: nil, body: "") == .failed)
        #expect(ProviderReach.from(status: 401, body: #"{"type":"error","error":{}}"#) == .reached)
        #expect(ProviderReach.from(status: 403, body: "  \n{\"error\":{\"code\":403}}") == .reached)
        #expect(ProviderReach.from(status: 403, body: "<html>Blocked</html>") == .notReached, "a proxy page")
        #expect(ProviderReach.from(status: nil, body: "") == .notReached)
    }

    @Test func eachCloudProviderWithAFixedHostHasAKeylessProbeAndTheOthersDoNot() {
        #expect(LLMProvider.claude.keylessProbeURL?.host == "api.anthropic.com")
        #expect(LLMProvider.chatGPT.keylessProbeURL?.host == "api.openai.com")
        #expect(LLMProvider.gemini.keylessProbeURL?.host == "generativelanguage.googleapis.com")
        #expect(LLMProvider.azure.keylessProbeURL == nil)
        #expect(LLMProvider.ollama.keylessProbeURL == nil)
    }

    @Test func theConditionHasNoVerdictAndIsAWarning() {
        #expect(ProviderProblemCondition.networkBlocks.verdict == nil)
        #expect(ProviderProblemCondition.networkBlocks.kind == .warning)
        let p = ProviderProblemPresentation(condition: .networkBlocks)
        #expect(p.pillKey == "desktop.providerProblem.networkBlocks.pill")
        #expect(p.titleKey == "desktop.providerProblem.networkBlocks.title")
        #expect(p.bodyKey == "desktop.providerProblem.networkBlocks.body")
        #expect(p.actions == [.switchProvider])
        #expect(!p.usesPrintfProviderFormat)
    }

    @Test func aRecordOfANetworkBlockIsNeverHeldByAVerdict() {
        let record = ProviderProblemRecord(
            provider: "anthropic", condition: .networkBlocks,
            firstSeen: Date(), lastRefusal: Date(), dismissed: false)
        #expect(!ProviderProblemRules.holds(record, verdictForItsKey: nil))
        #expect(!ProviderProblemRules.holds(record, verdictForItsKey: .ok))
    }

    // MARK: the model

    final class FakeProbe: NetworkProbing, @unchecked Sendable {
        var result: (path: PathSnapshot?, control: ControlResult, provider: ProviderReach)
        var delay: Duration = .zero
        private(set) var calls = 0
        init(_ result: (path: PathSnapshot?, control: ControlResult, provider: ProviderReach)) {
            self.result = result
        }
        func look(provider: LLMProvider) async
            -> (path: PathSnapshot?, control: ControlResult, provider: ProviderReach) {
            calls += 1
            if delay > .zero { try? await Task.sleep(for: delay) }
            return result
        }
    }

    final class FakeWatcher: NetworkPathWatching {
        var onChange: (@Sendable () -> Void)?
        var stopped = false
        var baseline: String?
        func start(baseline: String?, onChange: @escaping @Sendable () -> Void) {
            self.baseline = baseline
            self.onChange = onChange
        }
        func stop() { stopped = true; onChange = nil }
    }

    @MainActor private final class Rig {
        let suite: UserDefaults
        let name = "NetworkBlockTests-\(UUID().uuidString)"
        let center = NotificationCenter()
        var active: LLMProvider? = .claude
        var now = Date(timeIntervalSince1970: 1_800_000_000)
        let probe: FakeProbe
        let watcher = FakeWatcher()
        var model: ProviderProblemModel!
        init(_ result: (path: PathSnapshot?, control: ControlResult, provider: ProviderReach)) {
            suite = UserDefaults(suiteName: name)!
            probe = FakeProbe(result)
            // `weak`, not `unowned`: the model starts tasks that can outlive the test, and one that
            // read the freed rig aborted the whole test host ("swift_abortRetainUnowned"), taking
            // every test in flight down with it (seen 8 Nov 2026 in two full-suite runs).
            let fallbackNow = Date(timeIntervalSince1970: 1_800_000_000)
            let fallbackWatcher = watcher
            model = ProviderProblemModel(
                defaults: suite, now: { [weak self] in self?.now ?? fallbackNow },
                activeProvider: { [weak self] in self.flatMap { $0.active } },
                keyFor: { _ in "sk-test-key-1234567890" },
                observing: center, probe: probe, makeWatcher: { [weak self] in self?.watcher ?? fallbackWatcher })
        }
        func done() { suite.removePersistentDomain(forName: name) }
    }

    private static let up = PathSnapshot(satisfied: true, signature: "wifi")

    private func waitUntil(_ cond: () -> Bool) async {
        for _ in 0..<300 {
            if cond() { return }
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    private func settle() async { try? await Task.sleep(for: .milliseconds(150)) }

    @Test func whenTheInternetAnswersAndTheProviderDidNotThePillSaysSo() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        #expect(rig.model.presented?.condition == .networkBlocks)
        #expect(rig.model.presented?.provider == .claude)
        #expect(rig.model.presented?.stage == .loud)
        #expect(rig.model.shown?.condition == .networkBlocks)
        #expect(rig.probe.calls == 1)
        #expect(ProviderProblemModel.load(from: rig.suite) == nil, "never written to the stored record")
    }

    @Test func offlineInternetDownASignInPageOrAReachableProviderSaysNothing() async {
        for result in [
            (path: Optional(PathSnapshot(satisfied: false, signature: "x")), control: ControlResult.failed, provider: ProviderReach.notReached),
            (path: Optional(Self.up), control: ControlResult.failed, provider: ProviderReach.notReached),
            (path: Optional(Self.up), control: ControlResult.answeredOtherwise, provider: ProviderReach.notReached),
            (path: Optional(Self.up), control: ControlResult.reached, provider: ProviderReach.reached),
        ] {
            let rig = Rig(result); defer { rig.done() }
            rig.model.noteNetworkRefusal(provider: .claude)
            await waitUntil { rig.probe.calls > 0 }
            await waitUntil { !rig.model.isLooking }
            #expect(rig.probe.calls == 1)
            #expect(rig.model.presented == nil, "\(result)")
            #expect(rig.model.networkBlock == nil, "\(result)")
            #expect(rig.watcher.onChange == nil, "nothing is watched when nothing is shown")
        }
    }

    @Test func aChangeOfNetworkClearsIt() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        let change = rig.watcher.onChange
        #expect(change != nil)
        change?()
        await waitUntil { rig.model.presented == nil }
        #expect(rig.model.presented == nil)
        #expect(rig.model.networkBlock == nil)
        #expect(rig.watcher.stopped)
    }

    @Test func aCallThatWorkedClearsItButAnotherProvidersDoesNot() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        rig.center.post(name: .bristlenoseProviderCallSucceeded, object: "openai")
        await settle()
        #expect(rig.model.presented?.condition == .networkBlocks, "ChatGPT working says nothing about Claude")
        rig.center.post(name: .bristlenoseProviderCallSucceeded, object: "anthropic")
        await waitUntil { rig.model.presented == nil }
        #expect(rig.model.presented == nil)
    }

    @Test func switchingProviderTakesItAway() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        rig.active = .chatGPT
        rig.model.refresh()
        #expect(rig.model.presented == nil)
        #expect(rig.model.networkBlock == nil, "dropped, not merely hidden: it was about Claude")
    }

    @Test func theCrossHidesItAndAnotherRefusalDoesNotBringItBack() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        rig.model.dismiss()
        #expect(rig.model.presented == nil)
        #expect(rig.model.networkBlock?.dismissed == true, "hidden, not forgotten")
        rig.model.noteNetworkRefusal(provider: .claude)
        await settle()
        #expect(rig.model.networkBlock?.dismissed == true)
        #expect(rig.model.presented == nil, "an incidental repeat on a hidden notice says nothing")
        #expect(rig.probe.calls == 1, "and does not ask Apple again")
    }

    @Test func anAccountProblemOnShowOutranksIt() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        let saved = LLMValidator.verdictStore
        let verdicts = UserDefaults(suiteName: rig.name + "-v")!
        LLMValidator.verdictStore = verdicts
        defer { LLMValidator.verdictStore = saved; verdicts.removePersistentDomain(forName: rig.name + "-v") }
        ProviderProblemModel.recordRefusal(
            .outOfCredit, provider: .claude, explicit: true, defaults: rig.suite,
            now: Date(timeIntervalSince1970: 1_800_000_000),
            activeProvider: { rig.active }, keyFor: { _ in "sk-test-key-1234567890" },
            center: rig.center, announce: { _, _ in })
        rig.model.refresh()
        #expect(rig.model.presented?.condition == .outOfCredit)
        rig.model.noteNetworkRefusal(provider: .claude)
        // No suspension in here: `LLMValidator.verdictStore` is process-global and swapped for
        // this test, so an await would let another suite run against it. A look, had one been
        // started, would show as `isLooking` at once.
        #expect(!rig.model.isLooking, "not even looked at: it would sit behind the account problem")
        #expect(rig.probe.calls == 0)
        #expect(rig.model.networkBlock == nil, "and nothing is stored to surface when that clears")
        #expect(rig.model.presented?.condition == .outOfCredit)
    }

    @Test func aBlockReplacedByAnotherProvidersStopsTheOldWatcher() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        rig.watcher.stopped = false
        rig.active = .chatGPT
        rig.model.refresh()                       // the Claude block goes with the provider
        #expect(rig.watcher.stopped)
    }

    @Test func theStageAgesWithTheClockLikeTheOthers() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        #expect(rig.model.presented?.stage == .loud)
        rig.now = Date(timeIntervalSince1970: 1_800_000_000 + 3600)
        rig.model.refresh()
        #expect(rig.model.presented?.stage == .settled)
        rig.now = Date(timeIntervalSince1970: 1_800_000_000 + 2 * 86_400)
        rig.model.refresh()
        #expect(rig.model.presented?.stage == .collapsed)
    }

    @Test func refusalsThatArriveTogetherShareOneLook() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.probe.delay = .milliseconds(120)
        for _ in 0..<5 { rig.model.noteNetworkRefusal(provider: .claude) }
        await waitUntil { rig.model.presented != nil }
        #expect(rig.probe.calls == 1)
    }

    @Test func aLocalOrInactiveProviderIsNeverLookedAt() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .ollama)
        rig.model.noteNetworkRefusal(provider: .chatGPT)   // Claude is active
        await settle()
        #expect(rig.probe.calls == 0)
        #expect(rig.model.presented == nil)
    }

    @Test func theWatcherIsSeededWithTheSignatureTheLookSawSoAChangeDuringItIsNotLost() async {
        let rig = Rig((PathSnapshot(satisfied: true, signature: "wifi|en0"), .reached, .notReached))
        defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        #expect(rig.watcher.baseline == "wifi|en0")
    }

    @Test func aCallThatWorkedDuringTheLookDropsTheFinding() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.probe.delay = .milliseconds(150)
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.probe.calls > 0 }
        rig.center.post(name: .bristlenoseProviderCallSucceeded, object: "anthropic")
        await waitUntil { !rig.model.isLooking }
        #expect(rig.model.presented == nil)
        #expect(rig.model.networkBlock == nil)
    }

    @Test func aLookThatFoundNothingIsNotRepeatedForAMinute() async {
        let rig = Rig((Self.up, .failed, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.probe.calls == 1 && !rig.model.isLooking }
        rig.model.noteNetworkRefusal(provider: .claude)
        rig.model.noteNetworkRefusal(provider: .claude)
        await settle()
        #expect(rig.probe.calls == 1, "a stream of refusals on a dead network is not a stream of requests to Apple")
        rig.now = rig.now.addingTimeInterval(61)
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.probe.calls == 2 }
        #expect(rig.probe.calls == 2)
    }

    @Test func aRefusedRunBringsAHiddenBlockBackWithoutAnotherLookButAnIncidentalOneDoesNot() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        rig.model.dismiss()
        rig.model.noteNetworkRefusal(provider: .claude)
        #expect(rig.model.presented == nil)
        rig.model.noteNetworkRefusal(provider: .claude, explicit: true)
        #expect(rig.model.presented?.condition == .networkBlocks)
        #expect(rig.probe.calls == 1)
    }

    @Test func aHiddenBlockThatTheNetworkChangedOnLightsAgainOnTheNextRefusal() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        rig.model.dismiss()
        rig.watcher.onChange?()
        await waitUntil { rig.model.networkBlock == nil }
        rig.model.noteNetworkRefusal(provider: .claude)
        await waitUntil { rig.model.presented != nil }
        #expect(rig.model.presented?.condition == .networkBlocks)
    }

    @Test func anAccountProblemTheResearcherHidAlsoOutranksIt() async {
        let rig = Rig((Self.up, .reached, .notReached)); defer { rig.done() }
        let saved = LLMValidator.verdictStore
        let verdicts = UserDefaults(suiteName: rig.name + "-v2")!
        LLMValidator.verdictStore = verdicts
        defer { LLMValidator.verdictStore = saved; verdicts.removePersistentDomain(forName: rig.name + "-v2") }
        ProviderProblemModel.recordRefusal(
            .keyRejected, provider: .claude, explicit: true, defaults: rig.suite,
            now: rig.now, activeProvider: { rig.active }, keyFor: { _ in "sk-test-key-1234567890" },
            center: rig.center, announce: { _, _ in })
        rig.model.refresh()
        rig.model.dismiss()
        #expect(rig.model.presented == nil)
        rig.model.noteNetworkRefusal(provider: .claude)
        #expect(!rig.model.isLooking)   // see the note in the test above: no suspension here
        #expect(rig.probe.calls == 0)
        #expect(rig.model.networkBlock == nil)
        #expect(rig.model.presented == nil, "the cross on one problem does not reveal another")
    }

    @Test func aRunThatWorkedPostsTheCueTheBlockClearsOn() {
        let center = NotificationCenter()
        var seen: [String] = []
        let token = center.addObserver(forName: .bristlenoseProviderCallSucceeded, object: nil, queue: nil) {
            seen.append($0.object as? String ?? "")
        }
        defer { center.removeObserver(token) }
        let suite = UserDefaults(suiteName: "NetworkBlockCue-\(UUID().uuidString)")!
        ProviderProblemModel.noteRunSucceeded(
            provider: .claude, defaults: suite, keyFor: { _ in "sk-test-key-1234567890" }, center: center)
        #expect(seen == ["anthropic"])
    }

    // MARK: the sidecar's line reaches it

    @Test func aRefusalLineThatMayBeTheNetworksGoesToTheLookNotTheAccountRecord() throws {
        let m = ServeManager(resolvedMode: .success(.external(port: 1)))
        var account: [ProviderProblemCondition] = []
        var network: [LLMProvider] = []
        m.llmRefusalRecorder = { c, _, _ in account.append(c) }
        m.networkRefusalRecorder = { network.append($0) }
        m.instance.spawnedKeyFingerprints = ServeManager.keyFingerprints(in: [
            "BRISTLENOSE_ANTHROPIC_API_KEY": "k", "BRISTLENOSE_AZURE_API_KEY": "k"])
        func send(_ json: String) throws {
            m.noteLLMRefusal(try #require(LLMRefusalLine.fromLine(LLMRefusalLine.prefix + json)))
        }
        try send(#"{"v":1,"kind":"network","provider":"anthropic","phase":"connect"}"#)
        try send(#"{"v":1,"kind":"unknown","provider":"anthropic","http_status":403,"phase":"http","provider_signature":false}"#)
        #expect(network == [.claude, .claude])
        try send(#"{"v":1,"kind":"network","provider":"azure","phase":"dns"}"#)
        try send(#"{"v":1,"kind":"network","provider":"anthropic","phase":"response"}"#)
        try send(#"{"v":1,"kind":"rate_limited","provider":"anthropic","http_status":429,"phase":"http","provider_signature":true}"#)
        #expect(network.count == 2, "a mistyped Azure host, a slow read and a rate limit are not looked at")
        try send(#"{"v":1,"kind":"out_of_credit","provider":"anthropic","http_status":400,"phase":"http","provider_signature":true}"#)
        #expect(account == [.outOfCredit])
        #expect(network.count == 2)
        // A sidecar that was never given that provider's key cannot have made the call.
        try send(#"{"v":1,"kind":"network","provider":"openai","phase":"connect"}"#)
        #expect(network.count == 2)
    }
}
