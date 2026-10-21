import Foundation
import Testing

@testable import Bristlenose

/// R27: the ring is stage-weighted. Each `run_progress` line from the run
/// carries the slice of the ring its stage owns (`stage_base`, `stage_span`,
/// `stage_expected_seconds`, from the same Welford means as the ETA), and the
/// ring fills within that slice by the stage's own progress. A ring driven by
/// elapsed over the whole predicted total reaches the near-full band within
/// seconds of "Grouping themes" starting — the last big stage, small and
/// high-variance in the estimate — and sits there for the rest of the run
/// (docs/design-progress-ring-estimate.md).
@MainActor
@Suite struct RunProgressSliceTests {

    // MARK: - Through the reader (the line the run writes, as the runner folds it)

    private func events(_ lines: [String], in project: Project) throws -> URL {
        let url = PipelineRunner.eventsURL(for: project)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try (lines.joined(separator: "\n") + "\n").write(to: url, atomically: true, encoding: .utf8)
        return url
    }

    private let started = #"{"schema_version":1,"ts":"2026-10-21T01:00:00Z","event":"run_started","run_id":"RUN1","kind":"run","started_at":"2026-10-21T01:00:00Z","process":{"pid":1,"start_time":"x","hostname":"h","user":"u","bristlenose_version":"0","python_version":"3.12","os":"darwin-arm64"}}"#

    /// Grouping's entry line: a 100 s run, grouping expected to take 20 s and
    /// owning 15% of the ring after the 80% the stages before it earned.
    private let groupingEntry = #"{"schema_version":1,"ts":"2026-10-21T01:01:00Z","event":"run_progress","run_id":"RUN1","kind":"run","started_at":"2026-10-21T01:00:00Z","stage":"cluster","eta_remaining_seconds":10.0,"predicted_total_seconds":100.0,"stage_base":0.8,"stage_span":0.15,"stage_expected_seconds":20.0}"#

    /// The run is 60% over its whole-run estimate when the poll reads
    /// grouping's entry (the stages before it ran long). The whole-run ring
    /// read 0.89 here — deep in the creep band, "hung at 99%" — the moment
    /// grouping began. Stage-weighted, it is inside grouping's slice: at or
    /// past grouping's base, and short of render's.
    @Test func duringGroupingTheRingSitsInsideGroupingsSlice() async throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-slice-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let project = Project(id: UUID(), name: "Slices", path: dir.path)

        let runner = PipelineRunner()
        runner.beginSpawnedRun(project)          // before any line: nothing prior
        runner.liveData.setProgress(
            PipelineProgress(startedAt: Date().addingTimeInterval(-160)), for: project.id)
        let url = try events([started, groupingEntry], in: project)
        await runner.applyEventProgress(from: url, for: project.id)

        let ring = try #require(runner.liveData.progress[project.id]?.ringFraction)
        let base = RunProgressMath.stageWeightedFraction(
            base: 0.8, span: 0.15, fill: 0, wholeRunTimeRatio: 1.6)
        let rendersBase = RunProgressMath.stageWeightedFraction(
            base: 0.95, span: 0.05, fill: 0, wholeRunTimeRatio: 1.6)
        #expect(ring >= base - 1e-6, "grouping starts where quotes left the ring")
        #expect(ring < rendersBase, "grouping cannot reach past its own slice (read \(ring))")
    }

    @Test func theReaderDecodesTheBudgetAndToleratesItsAbsence() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-slice-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let project = Project(id: UUID(), name: "Reader", path: dir.path)
        let url = try events([started, groupingEntry], in: project)
        let ev = try #require(EventLogReader.latestProgress(at: url))
        #expect(ev.stageBase == 0.8)
        #expect(ev.stageSpan == 0.15)
        #expect(ev.stageExpectedSeconds == 20)

        // A sidecar that predates the budget: the keys are not there, and that
        // is nil, not a failure.
        let older = groupingEntry.replacingOccurrences(
            of: #","stage_base":0.8,"stage_span":0.15,"stage_expected_seconds":20.0"#, with: "")
        #expect(older != groupingEntry, "the fixture line must actually change")
        _ = try events([started, older], in: project)
        let old = try #require(EventLogReader.latestProgress(at: url))
        #expect(old.stage == "cluster")
        #expect(old.stageBase == nil && old.stageSpan == nil && old.stageExpectedSeconds == nil)
    }

    // MARK: - The math, at the 1 Hz poll's cadence

    private let start = Date(timeIntervalSince1970: 1_000)

    private func at(_ p: PipelineProgress, _ t: Double, stage: String?,
                    complete: Int? = nil, total: Int? = nil, fraction: Double? = nil,
                    predicted: Double? = 100,
                    base: Double? = nil, span: Double? = nil, expected: Double? = nil
    ) -> PipelineProgress {
        RunProgressMath.apply(
            stage: stage, sessionsComplete: complete, sessionsTotal: total,
            stageFraction: fraction, etaRemainingSeconds: nil,
            predictedTotalSeconds: predicted,
            stageBase: base, stageSpan: span, stageExpectedSeconds: expected,
            to: p, startedAt: start, now: start.addingTimeInterval(t)
        )
    }

    /// The ring for a slice fill with the whole run on time: the headroom
    /// scale of the slices, no creep.
    private func onTime(_ base: Double, _ span: Double, fill: Double) -> Double {
        RunProgressMath.stageWeightedFraction(
            base: base, span: span, fill: fill, wholeRunTimeRatio: 0.5)
    }

    private let mark = RunProgressMath.expectedCompletionMark

    /// Grouping expected at 20 s runs for 60 on a run that is otherwise on
    /// time. The ring keeps moving the whole time, stays below render's base,
    /// and at grouping's expected end sits at the headroom mark of its slice —
    /// the same creep shape as the whole run's, now per slice.
    @Test func aLongGroupingCreepsInsideItsSliceAndNeverReachesRenders() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 0, stage: "quotes", predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        p = at(p, 10, stage: "cluster", predicted: 1_000, base: 0.8, span: 0.15, expected: 20)
        #expect(abs((p.ringFraction ?? -1) - onTime(0.8, 0.15, fill: 0)) < 1e-9)
        var last = p.ringFraction ?? 0
        for t in stride(from: 11.0, through: 70.0, by: 1.0) {
            p = at(p, t, stage: "cluster", predicted: 1_000, base: 0.8, span: 0.15, expected: 20)
            let now = p.ringFraction ?? 0
            #expect(now > last, "stalled at t=\(t)")
            #expect(now < onTime(0.95, 0.05, fill: 0), "reached render's slice at t=\(t): \(now)")
            last = now
            if t == 30 {
                #expect(abs(now - onTime(0.8, 0.15, fill: mark)) < 1e-9)
            }
        }
        // Render then starts at its base, ahead of wherever grouping crept to.
        p = at(p, 71, stage: "render", predicted: 1_000, base: 0.95, span: 0.05, expected: 2)
        #expect(abs((p.ringFraction ?? -1) - onTime(0.95, 0.05, fill: 0)) < 1e-9)
    }

    /// A slice of a few per cent cannot show its own creep on a 16 pt ring, so
    /// a run that overruns its whole estimate keeps the whole-run creep through
    /// the headroom reserve: over a minute's overrun the ring must move by an
    /// amount a person can see, not by float increments.
    @Test func aRunOverItsEstimateStillVisiblyMovesThroughTheTail() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 100, stage: "cluster", base: 0.8, span: 0.15, expected: 20)   // 100 s predicted
        let atEstimate = p.ringFraction ?? 0
        p = at(p, 160, stage: "cluster", base: 0.8, span: 0.15, expected: 20)
        let aMinuteOver = p.ringFraction ?? 0
        #expect(aMinuteOver - atEstimate >= 0.03, "moved \(aMinuteOver - atEstimate) in a minute")
        #expect(aMinuteOver < RunProgressMath.asymptoteCap)
        // And render's own base, read at the same instant, is still ahead.
        let rendersBase = RunProgressMath.stageWeightedFraction(
            base: 0.95, span: 0.05, fill: 0, wholeRunTimeRatio: 1.6)
        #expect(aMinuteOver < rendersBase)
    }

    @Test func aPerSessionStageFillsItsSliceAsSessionsFinish() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 0, stage: "topics", predicted: 1_000, base: 0.3, span: 0.2, expected: 75)
        p = at(p, 50, stage: "quotes", predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        p = at(p, 55, stage: "quotes", complete: 2, total: 8, fraction: 0.25,
               predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        // A quarter of the sessions, five seconds in: the sessions lead the clock.
        #expect(abs((p.ringFraction ?? -1) - onTime(0.5, 0.3, fill: 0.25)) < 1e-9)
        p = at(p, 120, stage: "quotes", complete: 8, total: 8, fraction: 1,
               predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        #expect(abs((p.ringFraction ?? -1) - onTime(0.5, 0.3, fill: 1)) < 1e-9)   // full
    }

    /// Between two sessions the clock moves the ring on from the last
    /// measured step toward the next, and never past it: a stage whose clock
    /// is well ahead of its sessions does not claim sessions that have not
    /// finished.
    @Test func betweenSessionsTheClockMovesTowardTheNextStepAndNotPastIt() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 0, stage: "quotes", complete: 2, total: 8, fraction: 0.25,
               predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        let atStep = p.ringFraction ?? 0
        p = at(p, 30, stage: "quotes", complete: 2, total: 8, fraction: 0.25,
               predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        #expect((p.ringFraction ?? 0) > atStep)
        #expect((p.ringFraction ?? 0) <= onTime(0.5, 0.3, fill: 3.0 / 8) + 1e-9)
        // Far over time, the ring is at the next step and no further.
        p = at(p, 300, stage: "quotes", complete: 2, total: 8, fraction: 0.25,
               predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        #expect(abs((p.ringFraction ?? -1) - onTime(0.5, 0.3, fill: 3.0 / 8)) < 1e-9)
    }

    @Test func aCacheServedStageHoldsAtItsBase() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 10, stage: "speakers", predicted: 1_000, base: 0.14, span: 0, expected: 0)
        p = at(p, 110, stage: "speakers", predicted: 1_000, base: 0.14, span: 0, expected: 0)
        #expect(abs((p.ringFraction ?? -1) - onTime(0.14, 0, fill: 0)) < 1e-9)
    }

    /// A stage's time fill counts from when that stage was first seen, not
    /// from the run's start — quotes' 70 s must not read as grouping's.
    @Test func aLaterStageStartsItsOwnClock() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 0, stage: "quotes", predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        p = at(p, 70, stage: "quotes", predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        p = at(p, 70, stage: "cluster", predicted: 1_000, base: 0.8, span: 0.15, expected: 20)
        #expect(p.stageStartedAt == start.addingTimeInterval(70))
        #expect(abs((p.ringFraction ?? -1) - onTime(0.8, 0.15, fill: 0)) < 1e-9)
    }

    /// A run with the model already here sends no transcribe entry: its first
    /// transcribe line is the first file done. That stage was running from
    /// the run's start, so its clock is the run's, not the line's.
    @Test func theFirstStageSeenWasRunningFromTheStart() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 2, stage: nil, predicted: 1_000)                // the opening estimate
        p = at(p, 40, stage: "transcribe", complete: 1, total: 3, fraction: 1.0 / 3,
               predicted: 1_000, base: 0, span: 0.14, expected: 90)
        #expect(p.stageStartedAt == start)
        // 40 s of an expected 90 is ahead of a third of the files: the clock
        // moves the ring toward the second file, not past it.
        let fill = RunProgressMath.sliceFill(
            measuredFraction: 1.0 / 3, nextMeasuredStep: 2.0 / 3,
            stageElapsedSeconds: 40, stageExpectedSeconds: 90)
        #expect(fill > 1.0 / 3 && fill <= 2.0 / 3)
        #expect(abs((p.ringFraction ?? -1) - onTime(0, 0.14, fill: fill)) < 1e-9)
    }

    /// A session becoming readable is a line with no stage, and the newest one
    /// for as long as a file takes to transcribe. It is the same stage still
    /// running, so its slice stays; the ring does not swap models for a tick.
    @Test func aLineWithNoStageKeepsTheStagesSlice() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 0, stage: "topics", predicted: 1_000, base: 0.3, span: 0.2, expected: 75)
        p = at(p, 50, stage: "quotes", complete: 2, total: 8, fraction: 0.25,
               predicted: 1_000, base: 0.5, span: 0.3, expected: 75)
        p = at(p, 110, stage: nil, predicted: nil)               // sessions_readable only
        #expect(p.stageBase == 0.5 && p.stageSpan == 0.3)
        #expect(p.stageStartedAt == start.addingTimeInterval(50))
        let ring = p.ringFraction ?? 0
        #expect(ring > onTime(0.5, 0.3, fill: 0.25))
        #expect(ring <= onTime(0.5, 0.3, fill: 3.0 / 8) + 1e-9, "left quotes' slice: \(ring)")
    }

    /// No budget on the line (a sidecar that predates it, thin history): the
    /// whole-run time ring — 40 s of a predicted 100 is 0.4 × headroom.
    @Test func withoutABudgetTheRingIsTheWholeRunTimeRing() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 40, stage: "transcribe", complete: 2, total: 8, predicted: 100)
        #expect(p.ringFraction == 0.4 * RunProgressMath.expectedCompletionMark)
        #expect(p.stageBase == nil)
    }

    /// R32 then R27: the download fills by bytes; the analysis that follows is
    /// stage-weighted from transcription's entry, timed from the download's end.
    @Test func afterTheDownloadTheSlicesStartWithTranscription() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 10, stage: "download", fraction: 0.5, predicted: nil)
        p = at(p, 900, stage: "download", fraction: 1, predicted: nil)
        p = at(p, 901, stage: "transcribe", predicted: 1_000, base: 0, span: 0.14, expected: 40)
        #expect(p.ringFraction == 0)
        #expect(p.timeBaseline == start.addingTimeInterval(901))
        #expect(p.stageStartedAt == start.addingTimeInterval(901))
        p = at(p, 921, stage: "transcribe", predicted: 1_000, base: 0, span: 0.14, expected: 40)
        let expected = onTime(0, 0.14, fill: RunProgressMath.displayFraction(timeRatio: 0.5))
        #expect(abs((p.ringFraction ?? -1) - expected) < 1e-9)
    }
}
