import Foundation

/// Pure composer for the in-flight run subtitle text (Phase 0b text tier —
/// the sibling of `RunProgressMath`, which owns the ring fill). Reads the same
/// `run_progress`-derived fields the ring consumes and renders them as words:
/// the stage verb, the per-session fraction, and the ETA. No SwiftUI, no I/O,
/// so the ladder + ETA bucketing are unit-testable (same "decisions live in a
/// testable helper, not the view body" convention as `RunProgressMath`).
///
/// **Ladder (graceful degradation).** Leads with the stage verb when the event
/// names a known stage ("Transcribing · 7 of 8 · ~1 min left"); when it doesn't
/// (the initial post-ingest estimate, or a cached run that only emits that), it
/// leads with the generic "Analysing" so the row never shows a bare "<1 min
/// left" with no activity ("Analysing · <1 min left"). With no measured signal
/// at all it returns the indeterminate floor "Analysing…" — exactly as the row
/// read before the text tier landed.
enum RunProgressSubtitle {

    /// Stage ids carried by `run_progress.stage` — the Swift mirror of
    /// `timing.py ALL_STAGES`, the estimator's *coarse* progress vocabulary
    /// (NOT the finer `manifest.py STAGE_ORDER`: the estimator folds ingest /
    /// extract-audio / merge / PII into its neighbours and never emits them as
    /// a progress stage). Verified against real event logs — events say
    /// `speakers` / `topics`, not `identify_speakers` / `topic_segmentation`.
    /// The verb for each is localised via `desktop.chrome.pipeline.stage.<id>`.
    /// An id outside this set yields no verb: the guard stops an unexpected id
    /// from rendering as a raw key. Keep in sync with `timing.py ALL_STAGES`.
    static let knownStages: Set<String> = [
        "transcribe", "speakers", "topics", "quotes", "cluster", "render",
    ]

    /// Localisation key for a stage verb, or nil when the id is unknown/absent.
    static func stageVerbKey(_ stage: String?) -> String? {
        guard let stage, knownStages.contains(stage) else { return nil }
        return "desktop.chrome.pipeline.stage.\(stage)"
    }

    /// Stages that are a single cross-session call and carry no per-session
    /// fraction: theming/cluster (s10/s11) and render (s12). Only `transcribe`
    /// emits `sessions_complete`/`sessions_total`; `RunProgressMath.apply` then
    /// carries that pair forward untouched (it only overwrites on an event that
    /// *has* it), so by these stages the "N of M" is the STALE transcribe file
    /// count. Trailing it after "Grouping themes"/"Building report" reads as
    /// "theme-grouping is 4 of 5 done" when it isn't — suppress the fraction
    /// here (the verb + ETA still compose). Keyed off the stage id so no Python
    /// sentinel is needed. The per-session stages that *do* carry a live
    /// fraction (`transcribe` and the `_SESSION_STAGES` speakers/topics/quotes)
    /// are deliberately absent.
    static let nonSessionStages: Set<String> = ["cluster", "render"]

    /// Localised "~N min left" / "<1 min left", or nil when there's no usable
    /// estimate. Minute granularity (not seconds) so the text doesn't jitter at
    /// the 1 Hz poll rate; "min" is an invariant abbreviation, so no CLDR plural.
    static func etaText(
        _ seconds: Double?, localize: (String, [String: String]) -> String
    ) -> String? {
        guard let seconds, seconds.isFinite, seconds > 0 else { return nil }
        if seconds < 60 {
            return localize("desktop.chrome.pipeline.etaUnderMinute", [:])
        }
        let minutes = max(1, Int((seconds / 60).rounded()))
        return localize("desktop.chrome.pipeline.etaMinutes", ["count": String(minutes)])
    }

    /// Compose the in-flight subtitle from the progress fields. Returns the
    /// "Analysing…" floor when no marker is available. `localize` is the
    /// caller's `i18n.t` (key + interpolation args → resolved string).
    /// - Parameter resuming: true when this run was reconnected from a live
    ///   subprocess at app launch (`PipelineProgress.attachedFromOrphan`). It
    ///   swaps the generic lead verb "Analysing" → "Resuming" so a recovered
    ///   run reads honestly ("Resuming…", "Resuming · <1 min left") during the
    ///   reconnection moment and any indeterminate gap. A *known* stage still
    ///   leads with its own verb ("Transcribing · 7 of 8 · …") — the resume is
    ///   self-evident from live progress, and the active stage is the more
    ///   useful signal once events flow.
    static func compose(
        stage: String?,
        sessionsComplete: Int?,
        sessionsTotal: Int?,
        etaRemainingSeconds: Double?,
        resuming: Bool = false,
        separator: String,
        localize: (String, [String: String]) -> String
    ) -> String {
        // The detail markers (per-session fraction, ETA) that trail the verb.
        var detail: [String] = []
        // Suppress the "N of M" for stages that carry no live per-session count
        // (cluster/render) — the value there is a stale carry-over from the last
        // per-session stage, not this stage's progress.
        let suppressCount = stage.map(nonSessionStages.contains) ?? false
        if let complete = sessionsComplete, let total = sessionsTotal, total > 0,
            !suppressCount {
            detail.append(localize(
                "desktop.chrome.pipeline.sessionsCount",
                ["complete": String(complete), "total": String(total)]
            ))
        }
        if let eta = etaText(etaRemainingSeconds, localize: localize) {
            detail.append(eta)
        }
        // Lead with the stage verb when the event names a known stage.
        if let verbKey = stageVerbKey(stage) {
            return ([localize(verbKey, [:])] + detail).joined(separator: separator)
        }
        // No specific stage (the initial post-ingest estimate, a cached run that
        // only emits that, or an unknown id). The generic lead verb is "Resuming"
        // for a reconnected run, "Analysing" otherwise.
        let genericKey = resuming
            ? "desktop.chrome.pipeline.resuming"
            : "desktop.chrome.pipeline.analysing"
        // If there's nothing measured yet, show the indeterminate floor verbatim
        // ("Analysing…" / "Resuming…", ellipsis intact).
        guard !detail.isEmpty else {
            return localize(genericKey, [:])
        }
        // Otherwise lead with the generic running label so the row always says
        // *what* is happening, never a bare "<1 min left". Drop the floor
        // label's trailing ellipsis so it reads "Analysing · <1 min left", not
        // "Analysing… · <1 min left".
        let generic = localize(genericKey, [:])
            .replacingOccurrences(of: "\u{2026}", with: "")
            .trimmingCharacters(in: .whitespaces)
        return ([generic] + detail).joined(separator: separator)
    }
}
