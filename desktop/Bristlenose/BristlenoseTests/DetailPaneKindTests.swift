import Foundation
import Testing
@testable import Bristlenose

/// Pins the pane cascade that used to live inline in `ContentView.detail`.
/// The ORDER is the contract — each case here proves one precedence edge, so
/// a reordering of `resolve`'s early returns fails a named test rather than
/// silently changing which pane (and which lens availability) a state maps to.
struct DetailPaneKindTests {

    /// Baseline inputs for a healthy, analysed, folder-shaped project.
    private func resolve(
        hasProject: Bool = true,
        isAvailable: Bool = true,
        showShoal: Bool = false,
        pathIsEmpty: Bool = false,
        isFileSubset: Bool = false,
        pipelineState: PipelineState? = .ready(Date(timeIntervalSince1970: 0))
    ) -> DetailPaneKind {
        DetailPaneKind.resolve(
            hasProject: hasProject,
            isAvailable: isAvailable,
            showShoal: showShoal,
            pathIsEmpty: pathIsEmpty,
            isFileSubset: isFileSubset,
            pipelineState: pipelineState
        )
    }

    @Test func noProjectBeatsEverything() {
        #expect(resolve(hasProject: false, isAvailable: false, showShoal: true) == .noProject)
    }

    @Test func unreachableBeatsShoal() {
        #expect(resolve(isAvailable: false, showShoal: true) == .unavailable)
    }

    @Test func shoalBeatsEmptyPath() {
        #expect(resolve(showShoal: true, pathIsEmpty: true) == .shoal)
    }

    @Test func emptyPathPrompts() {
        #expect(resolve(pathIsEmpty: true) == .dragInterviews)
    }

    @Test func fileSubsetWithoutDataExplainsItself() {
        #expect(resolve(isFileSubset: true, pipelineState: .idle) == .unsupportedSubset)
    }

    /// The trust-UX rule: a subset project that HAS analysis data (analysed
    /// while folder-shaped, files added later) shows the report — the run
    /// state must not block viewing what's already there.
    @Test func fileSubsetWithDataShowsReport() {
        #expect(resolve(isFileSubset: true, pipelineState: .partial(kind: "transcribe-only", stagesComplete: [])) == .report)
        #expect(resolve(isFileSubset: true, pipelineState: .completedPartial(summary: PipelineSummary())) == .report)
    }

    @Test func neverRunFolderPrompts() {
        #expect(resolve(pipelineState: .idle) == .dragInterviews)
    }

    /// `.scanning` (and a missing state, which defaults to it) falls through
    /// to the serve surface so an already-analysed project boots rather than
    /// flashing an empty pane before the manifest read resolves.
    @Test func scanningFallsThroughToReport() {
        #expect(resolve(pipelineState: .scanning) == .report)
        #expect(resolve(pipelineState: nil) == .report)
    }

    /// Failed / cancelled states keep the serve surface — the status page
    /// carries the cause and log tail. (What the *lenses* do over that page
    /// is `LensAvailability`'s job, not the pane's.)
    @Test func failureStatesKeepTheServeSurface() {
        #expect(resolve(pipelineState: .failed("boom", category: .auth)) == .report)
        #expect(resolve(pipelineState: .failedWithDiagnostic(summary: PipelineSummary())) == .report)
        #expect(resolve(pipelineState: .stopped(stagesComplete: [])) == .report)
    }

    @Test func hasViewableDataTable() {
        #expect(DetailPaneKind.hasViewableData(.ready(Date(timeIntervalSince1970: 0))))
        #expect(DetailPaneKind.hasViewableData(.partial(kind: "transcribe-only", stagesComplete: [])))
        #expect(DetailPaneKind.hasViewableData(.completedPartial(summary: PipelineSummary())))
        #expect(!DetailPaneKind.hasViewableData(.idle))
        #expect(!DetailPaneKind.hasViewableData(.scanning))
        #expect(!DetailPaneKind.hasViewableData(.running))
        #expect(!DetailPaneKind.hasViewableData(.failed("x", category: .network)))
        // Abandon path leaves no report on disk — deliberately not viewable.
        #expect(!DetailPaneKind.hasViewableData(.failedWithDiagnostic(summary: PipelineSummary())))
        #expect(!DetailPaneKind.hasViewableData(nil))
    }
}
