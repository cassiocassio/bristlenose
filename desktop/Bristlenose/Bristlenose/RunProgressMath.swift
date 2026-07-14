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

    /// Where the ring sits when local elapsed reaches the Welford-predicted
    /// total (`timeRatio == 1`). **Reserved headroom, not the cap.** (13 Jul, QA)
    ///
    /// The old mapping sent `timeRatio` straight to `min(cap, ratio)`, so the
    /// ring hit 0.92 the instant elapsed met the estimate — and the high-variance
    /// LLM tail (s10/s11 grouping, s12 render, all under-predicted by the crude
    /// `session_count` proxy in `timing.py`) overruns that estimate on almost
    /// every run. Past `ratio == 1` the fill pinned flat at 0.92 while the 1 Hz
    /// poll re-evaluated to the identical value → a *frozen* near-full ring for
    /// the whole tail, which reads as "hung at 99%" (the MAAS waiting-psychology
    /// failure: a bar that stops moving erodes trust in the estimate).
    ///
    /// Now the estimate's honest end-point is 0.85, leaving `0.85 → 0.92` as a
    /// creep reserve consumed *only* during overrun (see `displayFraction`). A
    /// ring resting at 0.85 reads "nearly there, still working"; the overrun
    /// creep keeps it visibly inching rather than stalled — a moving 85% over a
    /// stalled 99%. Real completion is still rendered by replacing the ring with
    /// the ready/failure state, never by this fill reaching 1.0.
    static let expectedCompletionMark = 0.85

    /// Overrun creep rate. `timeRatio - 1` is the fractional overrun
    /// (`(elapsed − predicted) / predicted`); `displayFraction` maps it through
    /// `1 − exp(−overrun / tau)` so the ring approaches `asymptoteCap` without
    /// reaching it. tau = 0.6 → ~35% overrun spends roughly half the reserve, so
    /// a tail that runs as long again as its estimate still leaves visible gap.
    static let overrunTau = 0.6

    /// Monotonic + asymptote clamp. Never runs backwards (`max(previous, …)`)
    /// and never reaches 1.0 (`min(cap, …)`). `raw` may be any value; it is
    /// bounded into `[0, cap]` first.
    static func clampedFraction(
        raw: Double, previous: Double, cap: Double = asymptoteCap
    ) -> Double {
        let bounded = Swift.min(Swift.max(raw, 0), cap)
        return Swift.max(previous, bounded)
    }

    /// Shape a whole-run time ratio (`localElapsed / predictedTotal`, may exceed
    /// 1) into the displayed fill. Before the estimate is met the ring rises
    /// linearly to `expectedCompletionMark`; past it the ring creeps
    /// asymptotically toward `asymptoteCap`, so an over-running tail keeps moving
    /// instead of pinning flat. Continuous and monotonic across `ratio == 1`
    /// (both branches yield `expectedCompletionMark` there). Only the Welford
    /// time-estimate feeds this — the within-stage fallback fraction is a genuine
    /// 0..1 stage measure and is used unshaped.
    static func displayFraction(timeRatio ratio: Double) -> Double {
        if ratio <= 0 { return 0 }
        if ratio < 1 { return ratio * expectedCompletionMark }
        let overrun = ratio - 1
        return asymptoteCap
            - (asymptoteCap - expectedCompletionMark) * exp(-overrun / overrunTau)
    }

    /// Raw (unclamped) ring fill from a progress event plus the locally-measured
    /// elapsed time. Prefers the Welford time estimate (whole-run — the honest
    /// "how much time is left") and falls back to the measured within-stage
    /// fraction. Returns nil when neither is available → the caller shows the
    /// indeterminate spinner. This is the underlying *ratio* (may exceed 1 on the
    /// time-estimate branch); `apply` shapes the time branch via `displayFraction`.
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
        // Fall back to the last-known predicted total so the ring keeps advancing
        // through the render tail, where the pipeline stops re-emitting it (the
        // Welford remaining-estimate drops below its 10s floor and goes nil).
        let predicted = predictedTotalSeconds ?? p.predictedTotalSeconds
        if let raw = rawFraction(
            predictedTotalSeconds: predicted,
            localElapsedSeconds: elapsed,
            stageFraction: stageFraction
        ) {
            // Shape the whole-run time ratio (headroom + overrun creep); the
            // within-stage fallback fraction is already a true 0..1 and used as-is.
            let display = (predicted ?? 0) > 0 ? displayFraction(timeRatio: raw) : raw
            p.ringFraction = clampedFraction(raw: display, previous: p.ringFraction ?? 0)
        }
        return p
    }
}
