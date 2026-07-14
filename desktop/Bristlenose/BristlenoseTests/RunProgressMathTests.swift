import Foundation
import Testing

@testable import Bristlenose

/// Pins the determinate-ring honesty rules (Phase 0b): the ring never runs
/// backwards (monotonic), never shows a literal 100% before the run ends
/// (asymptote), prefers the time estimate over the within-stage fraction, and
/// degrades to nil (spinner) when nothing is known. Since 13 Jul it also reserves
/// headroom (the estimate's end-point is 0.85, not the cap) and creeps through the
/// reserve on overrun so an over-running tail keeps moving rather than freezing
/// flat at the cap. Cadence / field-set are deliberately NOT pinned — impl detail.
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

        // First event: calibrated, 40s of 100s → ratio 0.4 → 0.4 × 0.85 headroom.
        p = RunProgressMath.apply(
            stage: "transcribe", sessionsComplete: 2, sessionsTotal: 8,
            stageFraction: nil, etaRemainingSeconds: 60, predictedTotalSeconds: 100,
            to: p, startedAt: start,
            now: start.addingTimeInterval(40)
        )
        #expect(p.ringFraction == 0.4 * RunProgressMath.expectedCompletionMark)
        #expect(p.sessionsComplete == 2)

        // Second event: estimate revised up (predicted 200), elapsed 50 → ratio
        // 0.25 — but the ring holds at its prior value, never reversing.
        let held = p.ringFraction
        p = RunProgressMath.apply(
            stage: "transcribe", sessionsComplete: 3, sessionsTotal: 8,
            stageFraction: nil, etaRemainingSeconds: 150, predictedTotalSeconds: 200,
            to: p, startedAt: start,
            now: start.addingTimeInterval(50)
        )
        #expect(p.ringFraction == held)
        #expect(p.sessionsComplete == 3)
    }

    // MARK: - Headroom + overrun creep (13 Jul — the "stalled 99%" fix)

    @Test func displayReservesHeadroomAtEstimatedEnd() {
        // When elapsed reaches the predicted total, the ring sits at the reserved
        // mark (0.85), NOT the cap — so it reads "nearly there, still working".
        #expect(
            RunProgressMath.displayFraction(timeRatio: 1.0)
                == RunProgressMath.expectedCompletionMark
        )
        #expect(RunProgressMath.displayFraction(timeRatio: 1.0) < RunProgressMath.asymptoteCap)
    }

    @Test func displayIsLinearBeforeEstimatedEnd() {
        #expect(RunProgressMath.displayFraction(timeRatio: 0.0) == 0.0)
        #expect(
            RunProgressMath.displayFraction(timeRatio: 0.5)
                == 0.5 * RunProgressMath.expectedCompletionMark
        )
    }

    @Test func displayCreepsOnOverrunAndNeverReachesCap() {
        // Past the estimate the ring keeps inching toward — but never reaches —
        // the cap. This is the anti-stall guarantee: strictly increasing, bounded.
        let a = RunProgressMath.displayFraction(timeRatio: 1.0)   // at estimate
        let b = RunProgressMath.displayFraction(timeRatio: 1.5)   // 50% over
        let c = RunProgressMath.displayFraction(timeRatio: 3.0)   // 200% over
        #expect(a < b)
        #expect(b < c)
        #expect(c < RunProgressMath.asymptoteCap)
        // Deep overrun asymptotes to the cap without touching it.
        #expect(RunProgressMath.displayFraction(timeRatio: 100) < RunProgressMath.asymptoteCap)
        #expect(RunProgressMath.displayFraction(timeRatio: 100) > 0.91)
    }

    /// Regression for the reported bug: a run that over-runs its Welford estimate
    /// through the LLM-heavy tail must keep the ring MOVING, not freeze it flat at
    /// the cap. Drives `apply` at 1 Hz cadence against a fixed predicted total
    /// (the pipeline stops re-emitting one in the render tail) with elapsed past
    /// the estimate. Pre-fix this pinned to 0.92 on every tick (dead-frozen).
    @Test func applyRingKeepsMovingWhenRunOverrunsEstimate() {
        let start = Date(timeIntervalSince1970: 1_000)
        var p = PipelineProgress(startedAt: start)

        // Calibrate: 90s of a predicted 100s.
        p = RunProgressMath.apply(
            stage: "cluster", sessionsComplete: nil, sessionsTotal: nil,
            stageFraction: nil, etaRemainingSeconds: 10, predictedTotalSeconds: 100,
            to: p, startedAt: start, now: start.addingTimeInterval(90)
        )

        // Tail: elapsed marches past the estimate while later events omit the
        // predicted total (nil) — apply must fall back to the stored one and keep
        // advancing. Sample every 20s from the estimated end well into overrun.
        var last = p.ringFraction ?? 0
        for t in stride(from: 100.0, through: 220.0, by: 20.0) {
            p = RunProgressMath.apply(
                stage: "render", sessionsComplete: nil, sessionsTotal: nil,
                stageFraction: nil, etaRemainingSeconds: nil, predictedTotalSeconds: nil,
                to: p, startedAt: start, now: start.addingTimeInterval(t)
            )
            let now = p.ringFraction ?? 0
            #expect(now > last)                              // never stalled
            #expect(now < RunProgressMath.asymptoteCap)      // never "done"
            last = now
        }
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
