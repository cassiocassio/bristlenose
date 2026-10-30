import Foundation
import Testing
@testable import Bristlenose

/// "Picking up Signals…" on the sidebar row (`docs/design-signals-lens-readiness.md`
/// §3.3): where it sits in the precedence chain, what it says, whether it
/// shimmers, and the native prior that holds it across a run's end.

// MARK: - Precedence

@Suite struct PreparingSignalsPrecedenceTests {

    private func resolve(
        availability: ProjectAvailability = .ready,
        pipelineState: PipelineState? = nil,
        isStopping: Bool = false,
        addingCount: Int? = nil,
        exportingReport: Bool = false,
        preparingSignals: Bool = true,
        copy: CopyDisplay? = nil,
        importBatch: (done: Int, total: Int)? = nil,
        screens: (done: Int, total: Int)? = nil,
        reportCrash: ReportCrash? = nil,
        missingCount: Int = 0,
        unanalysedCount: Int = 0,
        databaseForked: Bool = false
    ) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: availability, pipelineState: pipelineState, isStopping: isStopping,
            addingCount: addingCount, exportingReport: exportingReport,
            preparingSignals: preparingSignals, copy: copy, importBatch: importBatch,
            screens: screens, reportCrash: reportCrash, lastRunAt: nil,
            missingCount: missingCount, unanalysedCount: unanalysedCount,
            databaseForked: databaseForked)
    }

    private let crash = ReportCrash(route: "/report/quotes", message: "TypeError: x", frames: [])

    @Test func itShowsOnAnOtherwiseQuietRow() {
        #expect(resolve() == .preparingSignals)
        #expect(resolve(preparingSignals: false) == .placeholder)
    }

    /// The build is told first by a window the researcher can see, but a run in
    /// flight always has the line: "Analysing…" wins, and so does Stopping.
    @Test func aRunOutranksIt() {
        #expect(resolve(pipelineState: .running) == .running)
        #expect(resolve(pipelineState: .running, isStopping: true) == .stopping)
        #expect(resolve(pipelineState: .queued(position: 2)) == .queued(position: 2))
    }

    @Test func theDistressAndVerbStatesOutrankIt() {
        #expect(resolve(availability: .cantFind(reason: .moved)) == .cantFind(reason: .moved))
        #expect(resolve(pipelineState: .stopped(stagesComplete: [])) == .stopped)
        #expect(resolve(pipelineState: .partial(kind: "transcribe-only", stagesComplete: []))
            == .partial(transcribeOnly: true))
        #expect(resolve(pipelineState: .unreachable(reason: .timedOut))
            == .unreachable(reason: .timedOut))
    }

    /// Everything the researcher started by a gesture keeps the line.
    @Test func theActsTheResearcherStartedOutrankIt() {
        #expect(resolve(addingCount: 2) == .addingInterviews(count: 2))
        #expect(resolve(exportingReport: true) == .exportingReport)
        #expect(resolve(importBatch: (done: 1, total: 4)) == .importingBatch(done: 1, total: 4))
        #expect(resolve(copy: .copying(fraction: 0.5)) == .copying(fraction: 0.5))
        #expect(resolve(copy: .cancelling) == .copyCancelling)
    }

    /// An error-kind delta and the window's crash are graver than a few seconds
    /// of waiting, and say something no other line does.
    @Test func aForkedDatabaseAndTheReportCrashOutrankIt() {
        #expect(resolve(databaseForked: true) == .deltaOnly(.databaseForked))
        #expect(resolve(reportCrash: crash) == .reportError(crash))
    }

    /// Owner's call: short-lived above long. The screen read can last hours, so
    /// the other order would never show this line at all.
    @Test func itOutranksScreenReading() {
        #expect(resolve(screens: (done: 3, total: 10)) == .preparingSignals)
        // …and the Screens count comes back when the build ends.
        #expect(resolve(preparingSignals: false, screens: (done: 3, total: 10))
            == .readingScreens(done: 3, total: 10))
    }

    /// Being short, it can stand in front of the warning and info deltas; they
    /// are still there when it ends.
    @Test func itOutranksTheQuietAndWarningDeltas() {
        #expect(resolve(unanalysedCount: 5) == .preparingSignals)
        #expect(resolve(missingCount: 2) == .preparingSignals)
        #expect(resolve(preparingSignals: false, missingCount: 2) == .deltaOnly(.missing(count: 2)))
    }

    /// Info, no glyph, no door: a ring or a glyph would promise a stop or a
    /// help that does not exist.
    @Test func itCarriesNoGlyphAndNoDoor() {
        #expect(SubtitleVariant.preparingSignals.glyphKind == nil)
        #expect(SubtitleVariant.preparingSignals.glyphAction == .none)
        #expect(!SubtitleVariant.preparingSignals.isUnreachable)
    }
}

// MARK: - Text, tooltip, shimmer

@MainActor
@Suite struct PreparingSignalsTextTests {

    private func english() throws -> I18n {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("signals-i18n-\(UUID().uuidString)")
        let en = dir.appendingPathComponent("en")
        try FileManager.default.createDirectory(at: en, withIntermediateDirectories: true)
        let desktop: [String: Any] = ["chrome": ["pipeline": [
            "pickingUpSignals": "Picking up Signals…",
        ]]]
        try JSONSerialization.data(withJSONObject: desktop)
            .write(to: en.appendingPathComponent("desktop.json"))
        let i18n = I18n()
        i18n.configure(localesDirectory: dir)
        i18n.setLocale("en")
        return i18n
    }

    @Test func theRowSaysPickingUpSignals() throws {
        let i18n = try english()
        #expect(SidebarSubtitleText.text(for: .preparingSignals, availability: .ready,
                                         progress: nil, i18n: i18n) == "Picking up Signals…")
        #expect(SidebarSubtitleText.activityText(.preparingSignals, progress: nil,
                                                 separator: " · ", i18n: i18n)
            == "Picking up Signals…")
    }

    /// Hover is where a long locale's truncated row reads in full.
    @Test func theTooltipCarriesTheWholeSentence() throws {
        let i18n = try english()
        #expect(SidebarSubtitleText.tooltip(for: .preparingSignals, data: nil, progress: nil,
                                            i18n: i18n) == "Picking up Signals…")
    }

    /// The same two gates as a run's line: the preference and Reduce Motion.
    @Test func itShimmersUnderTheSameGatesAsARun() {
        for variant in [SubtitleVariant.running, .preparingSignals] {
            #expect(SidebarOutlineController.shimmers(variant, animationOn: true, reduceMotion: false))
            #expect(!SidebarOutlineController.shimmers(variant, animationOn: false, reduceMotion: false))
            #expect(!SidebarOutlineController.shimmers(variant, animationOn: true, reduceMotion: true))
        }
        // …and no other line starts to.
        for variant in [SubtitleVariant.exportingReport, .readingScreens(done: 1, total: 2),
                        .stopping, .queued(position: 1), .placeholder] {
            #expect(!SidebarOutlineController.shimmers(variant, animationOn: true, reduceMotion: false))
        }
    }
}

// MARK: - The discriminator

@Suite struct SignalsOnlyWithheldTests {

    /// A build after a run withholds Signals alone.
    @Test func signalsAloneIsABuild() {
        #expect(LensReadiness(unavailable: [.signals]).isPreparingSignals)
        #expect(LensReadiness(message: ["sessions": true, "quotes": true, "signals": false])
            .isPreparingSignals)
    }

    /// A progressive run's shape (Project and Codebooks withheld beside it,
    /// `lens_readiness._lens_readiness`) is never mistaken for a build, nor is
    /// a stopped run's overlay, which keeps them withheld.
    @Test func aRunsShapeIsNotABuild() {
        let run = LensReadiness(message: ["sessions": true, "quotes": false, "signals": false,
                                          "codebook": false, "project": false])
        #expect(!run.isPreparingSignals)
        let joinedRun = LensReadiness(message: ["sessions": true, "quotes": true, "signals": true,
                                                "codebook": false, "project": false])
        #expect(!joinedRun.isPreparingSignals)
        #expect(!LensReadiness.all.isPreparingSignals)
        #expect(!LensReadiness(unavailable: [.quotes]).isPreparingSignals)
        #expect(!LensReadiness(unavailable: [.signals, .quotes]).isPreparingSignals)
    }
}

// MARK: - The prior

@Suite struct SignalsPreparingPriorTests {

    private let t0 = Date(timeIntervalSince1970: 1_000_000)
    private let building = LensReadiness(unavailable: [.signals])
    private let runShape = LensReadiness(unavailable: [.signals, .quotes, .codebook, .project])
    private func at(_ s: TimeInterval) -> Date { t0.addingTimeInterval(s) }

    @Test func quietWindowSaysNothing() {
        var p = SignalsPreparing()
        #expect(p.evaluate(readiness: .all, posts: 0, now: t0) == .init(show: false, recheckAfter: nil))
    }

    @Test func theBridgeAloneShowsItWithNoTimerOnIt() {
        var p = SignalsPreparing()
        #expect(p.evaluate(readiness: building, posts: 3, now: t0) == .init(show: true, recheckAfter: nil))
    }

    /// The hand-over: a run ends, and the row holds "preparing" before the
    /// bridge has said a word, so it never collapses to one line and grows.
    @Test func aRunsEndHoldsItBeforeTheBridgeSpeaks() {
        var p = SignalsPreparing()
        p.arm(now: t0, posts: 4)
        let v = p.evaluate(readiness: runShape, posts: 4, now: at(0.1))
        #expect(v.show)
        #expect(abs((v.recheckAfter ?? 0) - (SignalsPreparing.priorLimit - 0.1)) < 0.001)
    }

    /// A late post that still wears the run's shape is not the bridge speaking
    /// about the report.
    @Test func aStaleRunShapedPostDoesNotConfirm() {
        var p = SignalsPreparing()
        p.arm(now: t0, posts: 4)
        #expect(p.evaluate(readiness: runShape, posts: 5, now: at(1)).show)
        #expect(p.armed != nil, "the prior was dropped by a post that was not about the report")
    }

    @Test func theBridgeSayingBuildingHandsOverWithoutAGap() {
        var p = SignalsPreparing()
        p.arm(now: t0, posts: 4)
        let v = p.evaluate(readiness: building, posts: 5, now: at(2.5))
        #expect(v == .init(show: true, recheckAfter: nil))
        #expect(p.armed == nil)
        // …and when Signals lights, the line goes (the minimum is long past).
        #expect(!p.evaluate(readiness: .all, posts: 6, now: at(30)).show)
    }

    @Test func theBridgeSayingLitEndsThePriorAfterTheMinimumDisplay() {
        var p = SignalsPreparing()
        p.arm(now: t0, posts: 4)
        _ = p.evaluate(readiness: runShape, posts: 4, now: t0)
        // A small study: the bridge says lit at once, after the report reloads.
        let early = p.evaluate(readiness: .all, posts: 5, now: at(0.5))
        #expect(early.show, "the line flashed away inside its minimum")
        #expect(abs((early.recheckAfter ?? 0) - (SignalsPreparing.minimumDisplay - 0.5)) < 0.001)
        #expect(!p.evaluate(readiness: .all, posts: 5, now: at(2.0)).show)
    }

    /// No cloud model, or a window that never reloads: nothing comes, and the
    /// prior must not hold the line for ever.
    @Test func aSilentBridgeEndsThePriorAtItsLimit() {
        var p = SignalsPreparing()
        p.arm(now: t0, posts: 4)
        #expect(p.evaluate(readiness: .all, posts: 4, now: at(0.1)).show)
        #expect(p.evaluate(readiness: .all, posts: 4, now: at(SignalsPreparing.priorLimit - 1)).show)
        #expect(!p.evaluate(readiness: .all, posts: 4, now: at(SignalsPreparing.priorLimit)).show)
        #expect(p.armed == nil)
    }

    /// A bridge showing a build from the start is shown for at least the
    /// minimum when it lights again quickly.
    @Test func aBuildThatFinishesInUnderASecondStillShowsForTheMinimum() {
        var p = SignalsPreparing()
        _ = p.evaluate(readiness: building, posts: 1, now: t0)
        let v = p.evaluate(readiness: .all, posts: 2, now: at(0.4))
        #expect(v.show)
        #expect(abs((v.recheckAfter ?? 0) - (SignalsPreparing.minimumDisplay - 0.4)) < 0.001)
        #expect(!p.evaluate(readiness: .all, posts: 2, now: at(2.5)).show)
    }

    @Test func clearForgetsTheLot() {
        var p = SignalsPreparing()
        p.arm(now: t0, posts: 0)
        _ = p.evaluate(readiness: runShape, posts: 0, now: t0)
        p.clear()
        #expect(!p.evaluate(readiness: .all, posts: 0, now: at(0.1)).show)
    }

    // MARK: - What arms it

    @Test func onlyAFirstAnalysisRunToAReportArmsIt() {
        #expect(SignalsPreparing.shouldArm(old: .running, new: .ready(Date()), analysedBefore: false))
        #expect(SignalsPreparing.shouldArm(
            old: .running, new: .completedPartial(summary: PipelineSummary()), analysedBefore: false))
        // A re-analysis or an added interview leaves a report to read, so the
        // serve never withholds the lens over it.
        #expect(!SignalsPreparing.shouldArm(old: .running, new: .ready(Date()), analysedBefore: true))
        // Nothing builds after these.
        #expect(!SignalsPreparing.shouldArm(old: .running, new: .stopped(stagesComplete: []), analysedBefore: false))
        #expect(!SignalsPreparing.shouldArm(
            old: .running, new: .partial(kind: "transcribe-only", stagesComplete: []),
            analysedBefore: false))
        // A passive read of a finished study is not a run ending.
        #expect(!SignalsPreparing.shouldArm(old: .scanning, new: .ready(Date()), analysedBefore: false))
        #expect(!SignalsPreparing.shouldArm(old: nil, new: .ready(Date()), analysedBefore: false))
    }
}

// MARK: - The bridge wiring

@MainActor
@Suite struct SignalsPreparingBridgeTests {

    private final class Clock {
        var now = Date(timeIntervalSince1970: 2_000_000)
    }

    private func bridge(_ clock: Clock) -> BridgeHandler {
        let b = BridgeHandler()
        b.signalsClock = { clock.now }
        return b
    }

    private func post(_ b: BridgeHandler, _ lenses: [String: Bool]) {
        b.handleMessage(["type": "lens-availability", "lenses": lenses])
    }

    @Test func theWindowShowsItWhenTheBridgeWithholdsOnlySignals() {
        let clock = Clock()
        let b = bridge(clock)
        post(b, ["sessions": true, "quotes": true, "signals": false])
        #expect(b.isPreparingSignals)
        clock.now.addTimeInterval(5)
        post(b, ["sessions": true, "quotes": true, "signals": true])
        #expect(!b.isPreparingSignals)
    }

    @Test func aRunsPostsNeverShowIt() {
        let clock = Clock()
        let b = bridge(clock)
        post(b, ["sessions": true, "quotes": false, "signals": false,
                 "codebook": false, "project": false])
        #expect(!b.isPreparingSignals)
    }

    @Test func armingHoldsItUntilTheBridgeSpeaksAndTheMinimumPasses() {
        let clock = Clock()
        let b = bridge(clock)
        // A progressive run's last post.
        post(b, ["sessions": true, "quotes": true, "signals": true,
                 "codebook": false, "project": false])
        b.armSignalsPreparing()
        #expect(b.isPreparingSignals, "the row collapsed in the gap after the run")
        // The reloaded report says all lit, inside the minimum.
        clock.now.addTimeInterval(0.5)
        post(b, [:])
        #expect(b.isPreparingSignals)
        clock.now.addTimeInterval(2)
        post(b, [:])
        #expect(!b.isPreparingSignals)
    }

    @Test func aSelectionChangeEndsIt() {
        let clock = Clock()
        let b = bridge(clock)
        b.armSignalsPreparing()
        #expect(b.isPreparingSignals)
        b.reset()
        #expect(!b.isPreparingSignals)
    }

    @Test func aStatusPageEndsABridgeShowing() {
        let clock = Clock()
        let b = bridge(clock)
        post(b, ["signals": false])
        #expect(b.isPreparingSignals)
        clock.now.addTimeInterval(5)
        b.handleMessage(["type": "status-page", "outcome": "failed"])
        #expect(!b.isPreparingSignals)
    }

    /// The status page has no SPA to confirm a prior, so an armed prior must not
    /// outlive it: a run whose import failed lands on a status page.
    @Test func aStatusPageClearsAnArmedPrior() {
        let clock = Clock()
        let b = bridge(clock)
        b.armSignalsPreparing()
        #expect(b.isPreparingSignals)
        b.handleMessage(["type": "status-page", "outcome": "failed"])
        #expect(!b.isPreparingSignals, "a page with no SPA kept saying the report was on its way")
    }

    /// A study with no cloud model posts "all lit" the moment the run's overlay
    /// ends, which can be before the Mac has finished reading the run's end. The
    /// prior is armed against the count at the run's START, so that early post
    /// still speaks: it must not hold the line for the full ten seconds.
    @Test func aPostThatLandedBeforeTheArmStillSpeaks() {
        let clock = Clock()
        let b = bridge(clock)
        post(b, ["sessions": true, "quotes": true, "signals": true,
                 "codebook": false, "project": false])
        let atRunStart = b.lensAvailabilityPosts
        post(b, [:])  // the finished run's shape, before the Mac read the run's end
        b.armSignalsPreparing(postsAtRunStart: atRunStart)
        #expect(!b.isPreparingSignals, "a bridge that had already said all lit was made to wait ten seconds")
        // The same arm against the count at ARM time (the old behaviour) holds it.
        let late = bridge(clock)
        post(late, [:])
        late.armSignalsPreparing()
        #expect(late.isPreparingSignals)
    }

    /// Whether a study already had a report is what it was when its run began,
    /// not whether any run ever ended: a transcribe-only or stopped first run
    /// leaves no report, and the serve withholds the lens over the first one.
    @Test func aStudyHadAReportOnlyIfItsLastRunEndedInOne() {
        #expect(SignalsPreparing.hadReport(before: .ready(Date()), known: true))
        #expect(SignalsPreparing.hadReport(
            before: .completedPartial(summary: PipelineSummary()), known: true))
        #expect(!SignalsPreparing.hadReport(before: .idle, known: true))
        #expect(!SignalsPreparing.hadReport(before: .scanning, known: true))
        #expect(!SignalsPreparing.hadReport(
            before: .partial(kind: "transcribe-only", stagesComplete: []), known: true))
        #expect(!SignalsPreparing.hadReport(
            before: .stopped(stagesComplete: []), known: true))
    }

    /// Not knowing counts as having had one: a missed prior costs a collapse
    /// and regrow, a wrong one says a thing that is not so.
    @Test func notKnowingWhatTheStudyWasCountsAsHavingHadAReport() {
        #expect(SignalsPreparing.hadReport(before: nil, known: false))
        #expect(SignalsPreparing.hadReport(before: .idle, known: false))
    }

    /// Export dims while Signals prepares, by the owner's decision: any
    /// withheld lens makes the report partial, and nothing here changed that.
    @Test func exportReportStillDimsWhileSignalsPrepares() {
        let clock = Clock()
        let b = bridge(clock)
        post(b, ["sessions": true, "quotes": true, "signals": false])
        #expect(b.isPreparingSignals)
        #expect(b.lensReadiness != .all)
    }
}
