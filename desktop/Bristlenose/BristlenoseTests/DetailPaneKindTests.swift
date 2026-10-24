import Foundation
import Testing
@testable import Bristlenose

/// Pins the pane cascade that used to live inline in `ContentView.detail`.
/// The ORDER is the contract — each case here proves one precedence edge, so
/// a reordering of `resolve`'s early returns fails a named test rather than
/// silently changing which pane (and which lens availability) a state maps to.
struct DetailPaneKindTests {

    /// Baseline inputs for a healthy, analysed project.
    private func resolve(
        hasProject: Bool = true,
        isAvailable: Bool = true,
        showShoal: Bool = false,
        pathIsEmpty: Bool = false,
        pipelineState: PipelineState? = .ready(Date(timeIntervalSince1970: 0)),
        folderRefused: Bool = false
    ) -> DetailPaneKind {
        DetailPaneKind.resolve(
            hasProject: hasProject,
            isAvailable: isAvailable,
            showShoal: showShoal,
            pathIsEmpty: pathIsEmpty,
            pipelineState: pipelineState,
            folderRefused: folderRefused
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

    @Test func neverRunFolderPrompts() {
        #expect(resolve(pipelineState: .idle) == .dragInterviews)
    }

    /// A home folder or system root never prompts for interviews: `run`
    /// refuses the folder, so the pane says so (decision #110, 22 Oct 2026).
    @Test func aRefusedFolderSaysWhyInsteadOfPrompting() {
        #expect(resolve(pipelineState: .idle, folderRefused: true) == .unsuitableFolder)
        // The refusal decides only the never-run pane: an unreachable folder
        // and an analysed study keep their own panes.
        #expect(resolve(isAvailable: false, pipelineState: .idle, folderRefused: true) == .unavailable)
        #expect(resolve(folderRefused: true) == .report)
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
        #expect(resolve(pipelineState: .failed(.passthrough("boom"), category: .auth)) == .report)
        #expect(resolve(pipelineState: .failedWithDiagnostic(summary: PipelineSummary())) == .report)
        #expect(resolve(pipelineState: .stopped(stagesComplete: [])) == .report)
    }
}

/// The serve's status page describes the last terminus; a queued or running
/// project must not show it (28 Sep 2026: "Last run failed." under a row
/// reading "Queued · position 1").
struct DetailPaneRunCoverTests {
    private let failedPage = DocumentState.statusPage(.failed)

    @Test func queuedCoversAStaleFailure() {
        #expect(DetailPaneKind.runCover(pipelineState: .queued(position: 1), documentState: failedPage)
                == .queued(position: 1))
    }

    @Test func runningCoversAStaleFailure() {
        #expect(DetailPaneKind.runCover(pipelineState: .running, documentState: failedPage) == .analysing)
        #expect(DetailPaneKind.runCover(pipelineState: .running, documentState: .statusPage(.noRun)) == .analysing)
    }

    /// Reading the previous report while the new run waits is legitimate.
    @Test func aRealReportIsNeverCovered() {
        #expect(DetailPaneKind.runCover(pipelineState: .queued(position: 2), documentState: .spa) == nil)
        #expect(DetailPaneKind.runCover(pipelineState: .running, documentState: .loading) == nil)
    }

    /// With nothing known about the project, the page stays.
    @Test func noStateLeavesThePage() {
        #expect(DetailPaneKind.runCover(pipelineState: nil, documentState: failedPage) == nil)
        #expect(DetailPaneKind.runCover(pipelineState: .idle, documentState: .statusPage(.noRun)) == nil)
    }

    // MARK: - The Mac draws the failed and refused panes (owner, 24 Oct 2026, Q1)

    /// A failure reads its category's sentence; the record's raw English, which
    /// the event log usually carries, is kept for Show details.
    @Test func aFailureIsCoveredWithItsCategorysSentence() {
        #expect(DetailPaneKind.runCover(
            pipelineState: .failed(.passthrough("Error code: 401 - {...}"), category: .auth),
            documentState: failedPage)
                == .failed(sentence: FailureMessage.failure(for: .auth),
                           rawCause: "Error code: 401 - {...}", category: .auth, summary: nil))
    }

    /// The classifier's own keyed sentence, which names the provider it saw,
    /// is kept as it is.
    @Test func aKeyedFailureKeepsItsSentence() {
        let keyed = FailureMessage.failure(for: .auth, provider: .claude)
        guard case .failed(let sentence, _, _, _)? = DetailPaneKind.runCover(
            pipelineState: .failed(keyed, category: .auth), documentState: failedPage)
        else { Issue.record("not covered as failed"); return }
        #expect(sentence == keyed)
    }

    /// A refusal names its one door, not the page's "Not analysed yet."
    @Test func aRunRefusedForAProviderIsCoveredAsNeedingOne() {
        #expect(DetailPaneKind.runCover(
            pipelineState: .failed(.keyed("desktop.pipeline.failure.providerNotSetUpGeneric"),
                                   category: .providerNotSetUp),
            documentState: .statusPage(.noRun)) == .needsProvider)
    }

    /// A stop the classifier filed as a failure is still the researcher's stop.
    @Test func aUserSignalFailureReadsAsStopped() {
        #expect(DetailPaneKind.runCover(
            pipelineState: .failed(.passthrough("x"), category: .userSignal),
            documentState: failedPage) == .stopped)
    }

    /// A failure over a report the serve still shows is left showing.
    @Test func aFailureOverAReportIsNotCovered() {
        #expect(DetailPaneKind.runCover(
            pipelineState: .failed(.passthrough("x"), category: .auth), documentState: .spa) == nil)
    }

    /// The button follows the remedy (error-patterns-and-chrome-crash.html):
    /// the door to the fix, Retry where trying again is the act, else none.
    @Test func theRemedyDecidesTheButton() {
        typealias R = DetailPaneKind.FailureRemedy
        #expect(R.of(.auth) == .setUpProvider)
        #expect(R.of(.modelUnavailable) == .setUpProvider)
        #expect(R.of(.quota) == .retry)
        #expect(R.of(.apiServer) == .retry)
        #expect(R.of(.unknown) == .retry)
        #expect(R.of(.apiRequest) == .retry)
        #expect(R.of(.outOfCredit) == .none)
        #expect(R.of(.network) == .none)
        #expect(R.of(.unusableInput) == .none)
        #expect(R.of(.outputTruncated) == .none)
    }

    // MARK: - A run that ended unfinished (owner, 24 Oct 2026)

    /// The researcher pressed Stop: "Analysis stopped" and Resume Analysis.
    @Test func aStopIsCoveredAsStopped() {
        let page = DocumentState.statusPage(.cancelled)
        #expect(DetailPaneKind.runCover(pipelineState: .stopped(stagesComplete: []), documentState: page)
                == .stopped)
    }

    /// The app left under the run — Quit, a crash — or the run lost its
    /// process: "The analysis stopped before it finished", Resume Analysis.
    @Test func aRunTheAppLeftIsCoveredAsInterrupted() {
        #expect(DetailPaneKind.runCover(
            pipelineState: .stopped(stagesComplete: [], interrupted: true),
            documentState: .statusPage(.cancelled)) == .interrupted)
        #expect(DetailPaneKind.runCover(
            pipelineState: .failed(EventLogReader.stranded, category: .unknown),
            documentState: .statusPage(.stranded)) == .interrupted)
    }

    /// An earlier report the serve still shows is left showing.
    @Test func anUnfinishedRunOverAReportIsNotCovered() {
        #expect(DetailPaneKind.runCover(
            pipelineState: .stopped(stagesComplete: [], interrupted: true), documentState: .spa) == nil)
        #expect(DetailPaneKind.runCover(
            pipelineState: .failed(EventLogReader.stranded, category: .unknown), documentState: .spa) == nil)
    }

    // MARK: - Progressive lenses (docs/design-progressive-lenses.md, Phase 1)

    @Test func theShoalGivesWayAtTheFirstReadableSession() {
        func shoal(_ readable: Int?) -> Bool {
            DetailPaneKind.shoalTakesPane(
                animationOn: true, reduceMotion: false, analysing: true, sessionsReadable: readable
            )
        }
        #expect(shoal(nil))
        #expect(shoal(0))
        #expect(!shoal(1), "session 1 is readable: the report is the surface now")
        #expect(!DetailPaneKind.shoalTakesPane(
            animationOn: true, reduceMotion: false, analysing: false, sessionsReadable: nil))
        #expect(!DetailPaneKind.shoalTakesPane(
            animationOn: false, reduceMotion: false, analysing: true, sessionsReadable: nil))
        #expect(!DetailPaneKind.shoalTakesPane(
            animationOn: true, reduceMotion: true, analysing: true, sessionsReadable: nil))
    }

    @Test func aProgressiveRunThatSucceedsUnderItsLiveReportDoesNotReloadIt() {
        let ready = PipelineState.ready(Date(timeIntervalSince1970: 0))
        func reloads(_ doc: DocumentState, _ state: PipelineState, progressive: Bool = true) -> Bool {
            DetailPaneKind.reloadsOnCompletion(documentState: doc, settled: state, progressive: progressive)
        }
        #expect(!reloads(.spa, ready))
        #expect(reloads(.spa, ready, progressive: false),
                "a re-analyse can renumber sessions under the same route")
        #expect(reloads(.loading, ready))
        #expect(reloads(.spa, .stopped(stagesComplete: [])),
                "a stopped run's page is the serve's to describe")
        #expect(reloads(.spa, .failed(.passthrough("x"), category: .network)))
    }
}
