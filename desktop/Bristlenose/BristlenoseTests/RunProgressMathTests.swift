import Foundation
import Testing

@testable import Bristlenose

/// Pins the determinate-ring honesty rules (Phase 0b): the ring never runs
/// backwards (monotonic), never shows a literal 100% before the run ends
/// (asymptote), prefers the time estimate over the within-stage fraction, and
/// degrades to nil (spinner) when nothing is known. Cadence / field-set are
/// deliberately NOT pinned — implementation detail.
@Suite struct RunProgressMathTests {

    @Test func clampNeverRunsBackwards() {
        #expect(RunProgressMath.clampedFraction(raw: 0.5, previous: 0.3) == 0.5)
        // Estimate revised up → raw drops, but the ring holds.
        #expect(RunProgressMath.clampedFraction(raw: 0.2, previous: 0.5) == 0.5)
    }

    @Test func clampNeverReachesOne() {
        let v = RunProgressMath.clampedFraction(raw: 1.0, previous: 0.9)
        #expect(v == RunProgressMath.asymptoteCap)
        #expect(v < 1.0)
    }

    @Test func clampBoundsNegativeRaw() {
        #expect(RunProgressMath.clampedFraction(raw: -0.5, previous: 0.0) == 0.0)
    }

    @Test func rawPrefersEtaWhenCalibrated() {
        // ETA (40/100) wins over the within-stage fraction (0.9).
        let r = RunProgressMath.rawFraction(
            predictedTotalSeconds: 100, localElapsedSeconds: 40, stageFraction: 0.9
        )
        #expect(r == 0.4)
    }

    @Test func rawFallsBackToStageFraction() {
        let r = RunProgressMath.rawFraction(
            predictedTotalSeconds: nil, localElapsedSeconds: 40, stageFraction: 0.6
        )
        #expect(r == 0.6)
    }

    @Test func rawNilWhenNothingKnown() {
        let r = RunProgressMath.rawFraction(
            predictedTotalSeconds: nil, localElapsedSeconds: 40, stageFraction: nil
        )
        #expect(r == nil)
    }

    @Test func applyIsMonotonicAcrossEvents() {
        let start = Date(timeIntervalSince1970: 1_000)
        var p = PipelineProgress(startedAt: start)

        // First event: calibrated, 40s of 100s → 0.4.
        p = RunProgressMath.apply(
            stage: "transcribe", sessionsComplete: 2, sessionsTotal: 8,
            stageFraction: nil, etaRemainingSeconds: 60, predictedTotalSeconds: 100,
            to: p, startedAt: start,
            now: start.addingTimeInterval(40)
        )
        #expect(p.ringFraction == 0.4)
        #expect(p.sessionsComplete == 2)

        // Second event: estimate revised up (predicted 200), elapsed 50 → raw
        // 0.25 — but the ring holds at 0.4, never reversing.
        p = RunProgressMath.apply(
            stage: "transcribe", sessionsComplete: 3, sessionsTotal: 8,
            stageFraction: nil, etaRemainingSeconds: 150, predictedTotalSeconds: 200,
            to: p, startedAt: start,
            now: start.addingTimeInterval(50)
        )
        #expect(p.ringFraction == 0.4)
        #expect(p.sessionsComplete == 3)
    }

    @Test func applyUsesStageFractionWhenUncalibrated() {
        let start = Date(timeIntervalSince1970: 1_000)
        var p = PipelineProgress(startedAt: start)
        // No predicted total (first-ever run): within-file stage fraction drives it.
        p = RunProgressMath.apply(
            stage: "transcribe", sessionsComplete: 1, sessionsTotal: 3,
            stageFraction: 0.5, etaRemainingSeconds: nil, predictedTotalSeconds: nil,
            to: p, startedAt: start,
            now: start.addingTimeInterval(20)
        )
        #expect(p.ringFraction == 0.5)
    }
}
