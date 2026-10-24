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
    /// extract-audio / merge into its neighbours and never emits them as a
    /// progress stage; `pii` IS emitted, conditionally, since 12 Sep 2026 —
    /// before that the ring froze through redaction — and so is `discussion`,
    /// only when the Discussion lens is switched on). Verified against real
    /// event logs — events say
    /// `speakers` / `topics`, not `identify_speakers` / `topic_segmentation`.
    /// The verb for each is localised via `desktop.chrome.pipeline.stage.<id>`.
    /// An id outside this set yields no verb: the guard stops an unexpected id
    /// from rendering as a raw key. Keep in sync with `timing.py PROGRESS_STAGES`:
    /// `ALL_STAGES` plus `download` (`RunProgressMath.downloadStage`), which the
    /// run emits before them for a first run's speech model and the estimator
    /// never counts. `tests/test_swift_python_contract.py` holds the two equal.
    static let knownStages: Set<String> = [
        "download", "transcribe", "speakers", "pii", "topics", "quotes", "cluster",
        "discussion", "render",
    ]

    /// Localisation key for a stage verb, or nil when the id is unknown/absent.
    static func stageVerbKey(_ stage: String?) -> String? {
        guard let stage, knownStages.contains(stage) else { return nil }
        return "desktop.chrome.pipeline.stage.\(stage)"
    }

    /// The detail pane's cover over a stale status page while a run goes
    /// (`DetailPaneKind.RunCover.analysing`): "Resuming…" for a run picked up
    /// again until a stage reports, as the row's generic verb reads, and
    /// "Analysing…" otherwise.
    static func coverKey(stage: String?, resuming: Bool) -> String {
        resuming && stageVerbKey(stage) == nil
            ? "desktop.chrome.pipeline.resuming"
            : "desktop.chrome.pipeline.analysing"
    }

    /// Stages that carry no per-session fraction: theming/cluster (s10/s11),
    /// the Discussion stage (its per-session calls emit no count) and render
    /// (s12).
    ///
    /// **Why suppression is needed at all.** `RunProgressMath.apply` overwrites
    /// the session pair only on an event that *carries* it, so whatever the last
    /// emitting stage said persists. Trailing that after "Grouping themes" /
    /// "Building report" reads as "theme-grouping is 4 of 5 done" when it isn't.
    /// Keyed off the stage id, so no Python sentinel is needed.
    ///
    /// **Every per-session stage now emits its own live pair** (13 Sep 2026):
    /// `transcribe`, `pii`, `speakers`, `topics`, `quotes`. Earlier that day
    /// only `transcribe` did, and this comment said so while claiming in the
    /// same breath that the `_SESSION_STAGES` trio carried one too — both
    /// halves could not be right, and the second was the wrong one. That gap
    /// is closed, so nothing in this set is inherited any more.
    ///
    /// **What the number means differs by stage, and it is worth knowing.**
    /// `transcribe` iterates sequentially, so "3 of 8" is both *three done*
    /// and *now on the third*. `speakers`, `topics` and `quotes` gather behind
    /// a `llm_concurrency` semaphore, so sessions finish out of order and the
    /// number is *completions only* — it never identifies a session. Fine for
    /// this display, which never names one; do not build a "now processing X"
    /// on top of it. And the denominator is the **remaining** work on a
    /// resumed run, with `sessions_cached` carrying the rest.
    static let nonSessionStages: Set<String> = ["download", "cluster", "discussion", "render"]

    /// Stages during which a first analysis's sessions are still becoming
    /// readable (progressive lenses): transcription, and speaker identification
    /// for the sessions the chain did not reach. After them every session is
    /// readable, and the count would only repeat the total.
    static let arrivalStages: Set<String> = ["transcribe", "speakers"]

    /// Localised "~N min left" / "<1 min left", or nil when there's no usable
    /// estimate. Minute granularity (not seconds) so the text doesn't jitter at
    /// the 1 Hz poll rate. "min" is invariant, but the word beside it is not:
    /// French, Spanish, Italian, Portuguese and Catalan agree it with the count
    /// ("~1 min restante"), so the minutes go through `pluralize` (`i18n.plural`).
    static func etaText(
        _ seconds: Double?,
        localize: (String, [String: String]) -> String,
        pluralize: (String, Int) -> String
    ) -> String? {
        guard let seconds, seconds.isFinite, seconds > 0 else { return nil }
        if seconds < 60 {
            return localize("desktop.chrome.pipeline.etaUnderMinute", [:])
        }
        let minutes = max(1, Int((seconds / 60).rounded()))
        return pluralize("desktop.chrome.pipeline.etaMinutes", minutes)
    }

    /// Compose the in-flight subtitle from the progress fields. Returns the
    /// "Analysing…" floor when no marker is available. `localize` is the
    /// caller's `i18n.t` (key + interpolation args → resolved string).
    /// - Parameter resuming: true when this run was reconnected from a live
    ///   subprocess at app launch, or is the run Quit interrupted, started
    ///   again by the restored queue (`PipelineProgress.readsAsResuming`). It
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
        sessionsReadable: Int? = nil,
        separator: String,
        localize: (String, [String: String]) -> String,
        pluralize: (String, Int) -> String
    ) -> String {
        // The detail markers (per-session fraction, ETA) that trail the verb.
        var detail: [String] = []
        // Suppress the "N of M" for stages that carry no live per-session count
        // (cluster/discussion/render) — the value there is a stale carry-over from the last
        // per-session stage, not this stage's progress.
        let suppressCount = stage.map(nonSessionStages.contains) ?? false
        if let complete = sessionsComplete, let total = sessionsTotal, total > 0,
            !suppressCount {
            detail.append(localize(
                "desktop.chrome.pipeline.sessionsCount",
                ["complete": String(complete), "total": String(total)]
            ))
        }
        // Progressive lenses, Phase 5: how many sessions can be read already,
        // while they are still arriving. Its own count, not "N of M": the
        // transcription count leaves out platform transcripts, which never go
        // through Whisper, so it cannot be the denominator.
        if let readable = sessionsReadable, readable > 0,
            stage.map(arrivalStages.contains) ?? true {
            detail.append(pluralize("desktop.chrome.pipeline.sessionsReadable", readable))
        }
        // The ETA carried into a first run's speech-model download is the
        // analysis estimate, which does not move while the bytes arrive; the
        // ring shows the download's own progress instead.
        if stage != RunProgressMath.downloadStage,
            let eta = etaText(etaRemainingSeconds, localize: localize, pluralize: pluralize) {
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
