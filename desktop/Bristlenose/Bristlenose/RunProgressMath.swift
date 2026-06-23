import Foundation

/// Pure math for the determinate progress ring (Phase 0b). Factored out of the
/// view + runner so the honesty rules are unit-testable — no SwiftUI, no I/O.
/// See `docs/design-sidebar-activity-indicators.md` and the review log Finding
/// 19 (the honesty rules want a testable helper, not logic buried in a body).
enum RunProgressMath {

    /// Asymptote ceiling: the ring holds here while a run over-runs its
    /// estimate, so it reads "nearly there" rather than a stalled 100%. Real
    /// completion is rendered by replacing the ring with the ready/failure
    /// state — never by this fill reaching 1.0.
    ///
    /// **0.92, not 0.97** (23 Jun, QA): at 16pt with round line-caps a 0.97 arc
    /// read as a *closed* circle — the ~3% gap (~11°) was swallowed by the caps,
    /// so "nearly there, not done" looked like "done." 0.92 opens the gap to ~29°
    /// so it stays legible. Trade-off accepted: the ring tops out a touch lower
    /// near the end. (Round caps kept — the gap-visibility comes from the cap, not
    /// a cap-style change.)
    static let asymptoteCap = 0.92

    /// Monotonic + asymptote clamp. Never runs backwards (`max(previous, …)`)
    /// and never reaches 1.0 (`min(cap, …)`). `raw` may be any value; it is
    /// bounded into `[0, cap]` first.
    static func clampedFraction(
        raw: Double, previous: Double, cap: Double = asymptoteCap
    ) -> Double {
        let bounded = Swift.min(Swift.max(raw, 0), cap)
        return Swift.max(previous, bounded)
    }

    /// Raw (unclamped) ring fill from a progress event plus the locally-measured
    /// elapsed time. Prefers the Welford time estimate (whole-run — the honest
    /// "how much time is left") and falls back to the measured within-stage
    /// fraction. Returns nil when neither is available → the caller shows the
    /// indeterminate spinner.
    static func rawFraction(
        predictedTotalSeconds: Double?,
        localElapsedSeconds: Double,
        stageFraction: Double?
    ) -> Double? {
        if let total = predictedTotalSeconds, total > 0 {
            return localElapsedSeconds / total
        }
        if let frac = stageFraction {
            return frac
        }
        return nil
    }

    /// Apply a decoded `run_progress` event to a progress value, returning the
    /// updated value (pure). `now` / `startedAt` give the local elapsed used for
    /// the time-based fill (smoother than the event's own `elapsed`, which only
    /// updates per emit). The ring is monotonic across calls via
    /// `previous.ringFraction`.
    static func apply(
        stage: String?,
        sessionsComplete: Int?,
        sessionsTotal: Int?,
        stageFraction: Double?,
        etaRemainingSeconds: Double?,
        predictedTotalSeconds: Double?,
        to previous: PipelineProgress,
        startedAt: Date,
        now: Date
    ) -> PipelineProgress {
        var p = previous
        if let stage { p.stage = stage }
        if let sessionsComplete { p.sessionsComplete = sessionsComplete }
        if let sessionsTotal { p.sessionsTotal = sessionsTotal }
        if let etaRemainingSeconds { p.etaRemainingSeconds = etaRemainingSeconds }
        if let predictedTotalSeconds { p.predictedTotalSeconds = predictedTotalSeconds }

        let elapsed = now.timeIntervalSince(startedAt)
        if let raw = rawFraction(
            predictedTotalSeconds: predictedTotalSeconds ?? p.predictedTotalSeconds,
            localElapsedSeconds: elapsed,
            stageFraction: stageFraction
        ) {
            p.ringFraction = clampedFraction(raw: raw, previous: p.ringFraction ?? 0)
        }
        return p
    }
}
