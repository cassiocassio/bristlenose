import Foundation
import Testing
@testable import Bristlenose

/// The line a successful run leaves on its row for a few seconds
/// (`RunUsageLine`, Settings ▸ Appearance ▸ Show analysis usage,
/// docs/design-llm-usage.md): which runs get one, which one, and where it sits
/// in the row's precedence. Decisions, not translations.

// MARK: - Which line

@Suite struct RunUsageLineResolveTests {

    /// A terminus line as `run_lifecycle` writes it.
    private func terminus(
        event: String = "run_completed", runId: String = "01RUN",
        input: Int? = 400_000, output: Int? = 12_000, cost: Double? = 1.24
    ) -> EventLogReader.Event? {
        func field(_ name: String, _ value: String?) -> String {
            value.map { #","\#(name)":\#($0)"# } ?? ""
        }
        let json = #"{"schema_version":1,"ts":"2026-11-18T10:00:00Z","event":"\#(event)","run_id":"\#(runId)","kind":"run","started_at":"2026-11-18T09:30:00Z","ended_at":"2026-11-18T10:00:00Z","outcome":"completed","cause":null"#
            + field("input_tokens", input.map(String.init))
            + field("output_tokens", output.map(String.init))
            + field("cost_usd_estimate", cost.map { String($0) })
            + "}"
        return try? JSONDecoder().decode(EventLogReader.Event.self, from: Data(json.utf8))
    }

    private func line(
        _ terminus: EventLogReader.Event?, provider: LLMProvider? = .claude,
        display: AnalysisUsageDisplay = .tokens, priorRunId: String? = "01PRIOR"
    ) -> RunUsageLine? {
        RunUsageLine.resolve(terminus: terminus, priorRunId: priorRunId,
                             provider: provider, display: display)
    }

    @Test func theTerminusDecodesItsCost() {
        #expect(terminus()?.costUsdEstimate == 1.24)
        #expect(terminus(cost: nil)?.costUsdEstimate == nil)
    }

    @Test func tokensByDefaultAndInputPlusOutput() {
        #expect(AnalysisUsageDisplay.defaultValue == .tokens)
        #expect(line(terminus()) == .tokens(412_000))
    }

    @Test func costWhenAskedForAndPriced() {
        #expect(line(terminus(), display: .cost) == .costUSD(1.24))
    }

    @Test func costAskedForButUnpricedFallsBackToTokens() {
        // An Azure deployment, an any-llm route: no price on record.
        #expect(line(terminus(cost: nil), provider: .azure, display: .cost) == .tokens(412_000))
    }

    @Test func offSaysNothing() {
        #expect(line(terminus(), display: .off) == nil)
    }

    @Test func aLocalRunSaysNothing() {
        // Owner, 18 Nov 2026: Ollama shows nothing, whatever the setting.
        #expect(line(terminus(), provider: .ollama) == nil)
        #expect(line(terminus(), provider: .ollama, display: .cost) == nil)
    }

    @Test func aRunServedFromCacheSaysNothing() {
        // No LLM call: the terminus carries no tokens.
        #expect(line(terminus(input: nil, output: nil, cost: nil)) == nil)
        #expect(line(terminus(input: 0, output: 0, cost: 0)) == nil)
    }

    @Test func onlyACompletionGetsALine() {
        // A failure, a stop: their own line matters more, and little was spent.
        #expect(line(terminus(event: "run_failed")) == nil)
        #expect(line(terminus(event: "run_cancelled")) == nil)
        #expect(line(nil) == nil)
    }

    @Test func thePreviousRunsTerminusIsNotThisRuns() {
        #expect(line(terminus(runId: "01PRIOR"), priorRunId: "01PRIOR") == nil)
    }

    @Test func aBadOrZeroCostFallsBackToTokens() {
        #expect(line(terminus(cost: -1), display: .cost) == .tokens(412_000))
        #expect(line(terminus(cost: 0), display: .cost) == .tokens(412_000))
    }

    @Test func aRunWithNoProviderOnRecordSaysNothing() {
        // As the credit check does: it may have been local.
        #expect(line(terminus(), provider: nil) == nil)
    }

    @Test func numbersAreWrittenTheLocalesWay() {
        let us = Locale(identifier: "en_US")
        #expect(RunUsageLine.compactTokens(412_000, locale: us) == "412K")
        #expect(RunUsageLine.dollars(1.24, locale: us) == "$1.24")
        #expect(RunUsageLine.dollars(0.01, locale: us) == "$0.01")
    }

    @Test func thePreferenceReadsItsStoredValue() {
        let key = AnalysisUsageDisplay.defaultsKey
        let saved = UserDefaults.standard.object(forKey: key)
        defer { UserDefaults.standard.set(saved, forKey: key) }
        UserDefaults.standard.set("cost", forKey: key)
        #expect(AnalysisUsageDisplay.current == .cost)
        UserDefaults.standard.set("nonsense", forKey: key)
        #expect(AnalysisUsageDisplay.current == .tokens)
        UserDefaults.standard.removeObject(forKey: key)
        #expect(AnalysisUsageDisplay.current == .tokens)
    }
}

// MARK: - Where it sits

@Suite struct RunUsagePrecedenceTests {

    private let usage = RunUsageLine.tokens(412_000)

    private func resolve(
        pipelineState: PipelineState? = nil,
        preparingSignals: Bool = false,
        runUsage: RunUsageLine? = .tokens(412_000),
        screens: (done: Int, total: Int)? = nil,
        missingCount: Int = 0,
        unanalysedCount: Int = 0,
        databaseForked: Bool = false
    ) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: .ready, pipelineState: pipelineState, isStopping: false,
            addingCount: nil, preparingSignals: preparingSignals, runUsage: runUsage,
            copy: nil, importBatch: nil, screens: screens, lastRunAt: nil,
            missingCount: missingCount, unanalysedCount: unanalysedCount,
            databaseForked: databaseForked)
    }

    @Test func itTakesTheMomentThatWasSilence() {
        #expect(resolve() == .runUsage(usage))
        #expect(resolve(runUsage: nil) == .placeholder)
    }

    @Test func aWarningAnInfoOrAnErrorKeepsItsLine() {
        // "Failure, warning, info: unchanged" (owner, 18 Nov 2026).
        #expect(resolve(missingCount: 2) == .deltaOnly(.missing(count: 2)))
        #expect(resolve(unanalysedCount: 3) == .deltaOnly(.unanalysed(count: 3)))
        #expect(resolve(databaseForked: true) == .deltaOnly(.databaseForked))
    }

    @Test func itIsNotLostBehindWhatStartsAsARunEnds() {
        // Signals and screen reading start as a run ends and can last long;
        // the line takes its few seconds first, and they come back after.
        #expect(resolve(preparingSignals: true) == .runUsage(usage))
        #expect(resolve(screens: (done: 0, total: 4)) == .runUsage(usage))
        #expect(resolve(preparingSignals: true, runUsage: nil) == .preparingSignals)
    }

    @Test func aRunningRunOutranksIt() {
        #expect(resolve(pipelineState: .running) == .running)
    }

    @Test func itIsCalmNewsWithNoGlyphAndNoDoor() {
        #expect(SubtitleVariant.runUsage(usage).glyphKind == nil)
        #expect(SubtitleVariant.runUsage(usage).glyphAction == .none)
        #expect(ProjectCellSpec.isTwoLine(.runUsage(usage)))
    }
}
