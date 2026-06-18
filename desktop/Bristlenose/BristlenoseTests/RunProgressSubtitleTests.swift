import Foundation
import Testing

@testable import Bristlenose

/// Pins the in-flight subtitle ladder (Phase 0b text tier): which markers
/// compose, how they degrade as fields drop out, the ETA buckets, and the
/// "Analysing…" floor. Uses a fake localiser that mimics i18next `{{var}}`
/// interpolation so the assertions read as the rendered English — the real
/// locale strings are covered by the i18n key-coverage check, not here.
@Suite struct RunProgressSubtitleTests {

    /// Minimal i18next-style interpolation over a fixed template table.
    private func localize(_ key: String, _ args: [String: String]) -> String {
        let templates: [String: String] = [
            "desktop.chrome.pipeline.stage.transcribe": "Transcribing",
            "desktop.chrome.pipeline.stage.topics": "Finding topics",
            "desktop.chrome.pipeline.sessionsCount": "{{complete}} of {{total}}",
            "desktop.chrome.pipeline.etaMinutes": "~{{count}} min left",
            "desktop.chrome.pipeline.etaUnderMinute": "<1 min left",
            "desktop.chrome.pipeline.analysing": "Analysing…",
        ]
        var s = templates[key] ?? key
        for (k, v) in args { s = s.replacingOccurrences(of: "{{\(k)}}", with: v) }
        return s
    }

    private func compose(
        stage: String? = nil,
        complete: Int? = nil,
        total: Int? = nil,
        eta: Double? = nil,
        separator: String = " · "
    ) -> String {
        RunProgressSubtitle.compose(
            stage: stage, sessionsComplete: complete, sessionsTotal: total,
            etaRemainingSeconds: eta, separator: separator, localize: localize
        )
    }

    // MARK: - Ladder composition

    @Test func fullLadder() {
        #expect(compose(stage: "transcribe", complete: 7, total: 8, eta: 62)
            == "Transcribing · 7 of 8 · ~1 min left")
    }

    @Test func stageAndCountWhenNoEta() {
        #expect(compose(stage: "transcribe", complete: 7, total: 8)
            == "Transcribing · 7 of 8")
    }

    @Test func stageAndEtaWhenNoCount() {
        #expect(compose(stage: "transcribe", eta: 62) == "Transcribing · ~1 min left")
    }

    @Test func stageOnlyWhenStageOnly() {
        #expect(compose(stage: "topics") == "Finding topics")
    }

    @Test func floorWhenNothingKnown() {
        // Uncalibrated first run, before any measured signal — reads as it did
        // pre-text-tier. No regression.
        #expect(compose() == "Analysing…")
    }

    // MARK: - Edge cases

    @Test func unknownStageFallsBackToGenericVerb() {
        // The Python side only emits the six estimator ids; an unexpected id
        // (e.g. a finer manifest stage that never reaches the progress channel)
        // must not render a raw key — there's no specific verb, so the generic
        // "Analysing" leads instead of dropping the verb entirely.
        #expect(RunProgressSubtitle.stageVerbKey("bogus") == nil)
        #expect(RunProgressSubtitle.stageVerbKey("topic_segmentation") == nil)  // manifest id, not emitted
        #expect(RunProgressSubtitle.stageVerbKey(nil) == nil)
        #expect(compose(stage: "bogus", complete: 7, total: 8) == "Analysing · 7 of 8")
    }

    @Test func genericVerbWhenNoStageButEta() {
        // The initial post-ingest estimate (stage == nil) and cached runs that
        // only emit it must read "Analysing · <1 min left", never a bare ETA.
        #expect(compose(stage: nil, eta: 45) == "Analysing · <1 min left")
        #expect(compose(stage: nil, eta: 130) == "Analysing · ~2 min left")
        // Accessibility separator path stays consistent.
        #expect(compose(stage: nil, eta: 45, separator: ", ") == "Analysing, <1 min left")
    }

    @Test func knownStageMapsToKey() {
        #expect(RunProgressSubtitle.stageVerbKey("speakers")
            == "desktop.chrome.pipeline.stage.speakers")
    }

    /// Pins the known-stage set to `timing.py ALL_STAGES` — the actual wire
    /// vocabulary of `run_progress.stage`. If Python adds/renames an estimator
    /// stage, this fails loudly rather than silently dropping its verb (the bug
    /// that shipped the first cut: the manifest ids didn't match the wire ids).
    @Test func knownStagesMatchEstimatorVocabulary() {
        #expect(RunProgressSubtitle.knownStages
            == ["transcribe", "speakers", "topics", "quotes", "cluster", "render"])
    }

    @Test func zeroTotalOmitsCount() {
        // total == 0 is not a meaningful fraction — drop it rather than "7 of 0".
        #expect(compose(stage: "transcribe", complete: 0, total: 0) == "Transcribing")
    }

    @Test func accessibilitySeparatorUsesCommas() {
        #expect(compose(stage: "transcribe", complete: 7, total: 8, eta: 62, separator: ", ")
            == "Transcribing, 7 of 8, ~1 min left")
    }

    // MARK: - ETA buckets

    @Test func etaUnderAMinute() {
        #expect(RunProgressSubtitle.etaText(45, localize: localize) == "<1 min left")
    }

    @Test func etaRoundsToNearestMinute() {
        #expect(RunProgressSubtitle.etaText(130, localize: localize) == "~2 min left")
        #expect(RunProgressSubtitle.etaText(62, localize: localize) == "~1 min left")
    }

    @Test func etaNilForNonPositiveOrNonFinite() {
        #expect(RunProgressSubtitle.etaText(0, localize: localize) == nil)
        #expect(RunProgressSubtitle.etaText(-5, localize: localize) == nil)
        #expect(RunProgressSubtitle.etaText(nil, localize: localize) == nil)
        #expect(RunProgressSubtitle.etaText(.infinity, localize: localize) == nil)
        #expect(RunProgressSubtitle.etaText(.nan, localize: localize) == nil)
    }
}
