import Foundation
import Testing

@testable import Bristlenose

/// Pins the sidebar-subtitle precedence chain (`ProjectSubtitle.resolve`):
/// which concurrent condition wins, and in what order. Asserts the resolved
/// *case*, not the rendered string — i18n + date formatting are the view's job
/// (covered by the i18n key-coverage check), and the settled grammar isn't
/// re-tested here. (Build one-liner, 18 Jun 2026.)
@Suite struct ProjectSubtitleTests {

    private let summary = PipelineSummary(transcripts: nil, topics: nil, quotes: nil, themes: nil)
    private let aDate = Date(timeIntervalSince1970: 1_000_000)

    /// Resolve with `.ready` availability + no run as the baseline, overriding
    /// only the inputs a given case cares about.
    private func resolve(
        availability: ProjectAvailability = .ready,
        pipelineState: PipelineState? = nil,
        isStopping: Bool = false,
        copy: CopyDisplay? = nil,
        lastRunAt: Date? = nil,
        missingCount: Int = 0,
        unanalysedCount: Int = 0
    ) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: availability,
            pipelineState: pipelineState,
            isStopping: isStopping,
            copy: copy,
            lastRunAt: lastRunAt,
            missingCount: missingCount,
            unanalysedCount: unanalysedCount
        )
    }

    // MARK: - Tier 1 — availability outranks ALL activity (18 Jun ruling)

    @Test func cantFindBeatsRunning() {
        #expect(resolve(availability: .cantFind(reason: .moved),
                        pipelineState: .running) == .cantFind(reason: .moved))
    }

    @Test func cantFindBeatsFailed() {
        #expect(resolve(availability: .cantFind(reason: .unmountedVolume(name: "T7")),
                        pipelineState: .failed("boom", category: .unknown))
            == .cantFind(reason: .unmountedVolume(name: "T7")))
    }

    @Test func cantFindBeatsDeltasAndDate() {
        #expect(resolve(availability: .cantFind(reason: .moved),
                        lastRunAt: aDate, missingCount: 3, unanalysedCount: 2)
            == .cantFind(reason: .moved))
    }

    @Test func inCloudFallsThroughToDate() {
        // iCloud-evicted is NOT cantFind (macOS materialises on open): it shows
        // the bare date, with the cloud glyph riding the row's right slot.
        #expect(resolve(availability: .inCloud(downloading: nil), lastRunAt: aDate)
            == .ready(date: aDate, delta: nil))
    }

    // MARK: - Tier 2–4 — pipeline activity

    @Test func failedCarriesSummary() {
        #expect(resolve(pipelineState: .failed("provider 404", category: .unknown))
            == .failed(summary: "provider 404"))
    }

    @Test func failedWithDiagnosticMapsToHeaderCase() {
        #expect(resolve(pipelineState: .failedWithDiagnostic(summary: summary))
            == .failedDiagnostic)
    }

    @Test func completedPartialMapsToOwnCase() {
        #expect(resolve(pipelineState: .completedPartial(summary: summary)) == .completedPartial)
    }

    @Test func runningWhenNotStopping() {
        #expect(resolve(pipelineState: .running) == .running)
    }

    @Test func stoppingOutranksRunningProgress() {
        #expect(resolve(pipelineState: .running, isStopping: true) == .stopping)
    }

    @Test func isStoppingIgnoredWhenNotRunning() {
        // isStopping is meaningful only for a running run; elsewhere it's inert.
        #expect(resolve(pipelineState: .ready(Date()), isStopping: true, lastRunAt: aDate)
            == .ready(date: aDate, delta: nil))
    }

    @Test func queuedCarriesPosition() {
        #expect(resolve(pipelineState: .queued(position: 2)) == .queued(position: 2))
    }

    @Test func stoppedMapsToOwnCase() {
        #expect(resolve(pipelineState: .stopped(stagesComplete: [])) == .stopped)
    }

    @Test func partialTranscribeOnly() {
        #expect(resolve(pipelineState: .partial(kind: "transcribe-only", stagesComplete: []))
            == .partial(transcribeOnly: true))
    }

    @Test func partialOtherKind() {
        #expect(resolve(pipelineState: .partial(kind: "analyze", stagesComplete: []))
            == .partial(transcribeOnly: false))
    }

    @Test func unreachableCarriesReason() {
        #expect(resolve(pipelineState: .unreachable(reason: "volume gone"))
            == .unreachable(reason: "volume gone"))
    }

    // MARK: - Tier 5+ — idle / ready (date + single delta)

    @Test func readyBareDateWhenNoDelta() {
        #expect(resolve(pipelineState: .ready(Date()), lastRunAt: aDate)
            == .ready(date: aDate, delta: nil))
    }

    @Test func readyWithMissingDelta() {
        #expect(resolve(pipelineState: .ready(Date()), lastRunAt: aDate, missingCount: 3)
            == .ready(date: aDate, delta: .missing(count: 3)))
    }

    @Test func readyWithUnanalysedDelta() {
        #expect(resolve(pipelineState: .ready(Date()), lastRunAt: aDate, unanalysedCount: 2)
            == .ready(date: aDate, delta: .unanalysed(count: 2)))
    }

    @Test func missingDeltaBeatsUnanalysed() {
        // Data drift wins over the feature gap when both are present. Pass an
        // explicit `.ready` so the test keeps probing *delta* precedence even
        // if `pipelineState`'s default ever changes (it currently falls through
        // `nil` → the idle chain, same path).
        #expect(resolve(pipelineState: .ready(Date()),
                        lastRunAt: aDate, missingCount: 1, unanalysedCount: 5)
            == .ready(date: aDate, delta: .missing(count: 1)))
    }

    @Test func deltaOnlyWhenNoDateAnchor() {
        // CLI-analysed / imported project: render the delta without a date anchor.
        #expect(resolve(missingCount: 2) == .deltaOnly(.missing(count: 2)))
        #expect(resolve(unanalysedCount: 4) == .deltaOnly(.unanalysed(count: 4)))
    }

    @Test func placeholderWhenNothingToSay() {
        #expect(resolve() == .placeholder)
    }

    @Test func idleNoneScanningShareTheIdleChain() {
        // The scan spinner lives in the title-line right slot, not the subtitle,
        // so `.scanning` resolves the same as `.idle` / no state.
        for state: PipelineState? in [nil, .idle, .scanning] {
            #expect(resolve(pipelineState: state, lastRunAt: aDate)
                == .ready(date: aDate, delta: nil))
        }
    }

    // MARK: - Copying (idle tier: copying > deltas > date)

    @Test func copyingShownWhenFractionPresent() {
        #expect(resolve(copy: .copying(fraction: 0.6), lastRunAt: aDate) == .copying(fraction: 0.6))
    }

    @Test func copyingBeatsMissingDelta() {
        // The one delta that can co-occur with an active copy on an analysed
        // project — copying must win (it's the active operation).
        #expect(resolve(copy: .copying(fraction: 0.4), lastRunAt: aDate, missingCount: 3)
            == .copying(fraction: 0.4))
    }

    @Test func copyingBeatsUnanalysedAndBareDate() {
        #expect(resolve(copy: .copying(fraction: 0.1), lastRunAt: aDate, unanalysedCount: 2)
            == .copying(fraction: 0.1))
        // No date anchor either — still copying.
        #expect(resolve(copy: .copying(fraction: 0.9)) == .copying(fraction: 0.9))
    }

    @Test func cancellingCopyShownAsCancelVariant() {
        // The rollback window after the user hits cancel — outranks the resting
        // date the same way copying does.
        #expect(resolve(copy: .cancelling, lastRunAt: aDate) == .copyCancelling)
    }

    @Test func runningOutranksCopying() {
        // A run and a copy don't co-occur in practice, but the precedence keeps
        // it honest: verb-led activity wins over an import.
        #expect(resolve(pipelineState: .running, copy: .copying(fraction: 0.5)) == .running)
    }

    @Test func stoppedOutranksCopying() {
        #expect(resolve(pipelineState: .stopped(stagesComplete: []),
                        copy: .copying(fraction: 0.5)) == .stopped)
    }

    // (cantFind-outranks-copying is covered structurally: copying is only reached
    // in `resolveIdle`, after the cantFind guard — and `cantFindBeatsRunning` /
    // `cantFindBeatsDeltasAndDate` already pin tier-1 dominance.)

    // MARK: - pickDelta unit

    @Test func pickDeltaMissingWins() {
        #expect(ProjectSubtitle.pickDelta(missingCount: 2, unanalysedCount: 9)
            == .missing(count: 2))
    }

    @Test func pickDeltaUnanalysedWhenNoMissing() {
        #expect(ProjectSubtitle.pickDelta(missingCount: 0, unanalysedCount: 9)
            == .unanalysed(count: 9))
    }

    @Test func pickDeltaNilWhenNeither() {
        #expect(ProjectSubtitle.pickDelta(missingCount: 0, unanalysedCount: 0) == nil)
    }

    // MARK: - SubtitleVariant.isDiagnostic (failure-glyph clickability, review F35)

    @Test func isDiagnostic_trueForFailureAndPartial() {
        #expect(SubtitleVariant.failed(summary: "boom").isDiagnostic)
        #expect(SubtitleVariant.failedDiagnostic.isDiagnostic)
        #expect(SubtitleVariant.completedPartial.isDiagnostic)
    }

    @Test func isDiagnostic_falseForNonDistressStates() {
        #expect(!SubtitleVariant.running.isDiagnostic)
        #expect(!SubtitleVariant.stopping.isDiagnostic)
        #expect(!SubtitleVariant.ready(date: aDate, delta: nil).isDiagnostic)
        #expect(!SubtitleVariant.copying(fraction: 0.5).isDiagnostic)
        #expect(!SubtitleVariant.placeholder.isDiagnostic)
    }
}
