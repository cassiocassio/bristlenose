import Testing
import Foundation
@testable import Bristlenose

/// Pins when **Analyse** is worth offering.
///
/// The predicate used to ask three questions — right kind of project, pipeline
/// free, path non-empty — and never the fourth: *is there work to do*. So the
/// item appeared, highlighted, on a project with no recordings at all, directly
/// beside a pane reading "Add interview recordings or transcripts to get
/// started". On a fully-analysed project it appeared too, where running it is a
/// measured 0.1s of cache hits and a re-render.
///
/// Matrix: `docs/design-analysis-lifecycle.md` §4.1.
@Suite struct AnalyseAffordanceTests {

    private func state(
        newFiles: Int = 0,
        sessions: Int? = nil,
        files: Int = 1
    ) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [],
            sessionCount: sessions,
            totalDurationSeconds: nil,
            ingestableFileCount: files
        )
    }

    // MARK: - The matrix

    @Test func emptyProject_isNotOffered() {
        // The bug: highlighted "Analyse" beside "Add interview recordings…".
        #expect(!SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: nil, files: 0)))
    }

    @Test func mediaButNeverAnalysed_isOffered() {
        // The trap this predicate is built around: F14 zeroes `newFiles` for a
        // project with no baseline, so a fresh folder of recordings reports
        // none. Reading that as "nothing to do" would hide Analyse on exactly
        // the project that needs it.
        #expect(SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: nil, files: 1)))
    }

    @Test func analysedWithNothingNew_isNotOffered() {
        // Running it here is 0.1s of cache hits and a re-render. Offering a
        // control whose only observable effect is a re-render teaches the
        // researcher the button is broken. This state wants Re-analyse…
        #expect(!SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: 14, files: 1)))
    }

    @Test func analysedWithNewFiles_isOffered() {
        #expect(SidebarOutlineController.hasWorkToDo(
            state(newFiles: 3, sessions: 14, files: 1)))
    }

    @Test func failedRunWithMediaPresent_isOffered() {
        // Nothing was ingested, so every file still reads as new — the retry
        // must stay reachable.
        #expect(SidebarOutlineController.hasWorkToDo(
            state(newFiles: 5, sessions: 0, files: 1)))
    }

    // MARK: - Unknown state

    @Test func noWatcherYet_isOffered() {
        // `nil` means no watcher running (project not ready, or the first scan
        // hasn't landed) — NOT "nothing to do". Wrongly showing a control costs
        // a click; wrongly hiding one leaves no way forward at all.
        #expect(SidebarOutlineController.hasWorkToDo(nil))
    }

    @Test func ingestableIsAuthoritative_evenWithSessions() {
        // Folder emptied after an analysis: nothing left to ingest, so Analyse
        // has nothing to do regardless of the session count on record.
        #expect(!SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: 14, files: 0)))
    }

    // MARK: - The first scan must publish, or "absent" is ambiguous

    @Test func firstScanPublishesEvenWhenItFoundNothing() {
        // The hole this suite missed on its first pass. `lastPublished` was
        // seeded to `.empty`, so a scan of an empty folder equalled it and was
        // suppressed — the project's entry stayed absent, absent reads as
        // "unknown", unknown resolves to *offer*, and Analyse kept appearing on
        // empty projects even after canAnalyse learned to check. Caught by a
        // screenshot of a build that already contained the fix.
        #expect(ProjectFolderWatcher.shouldPublish(.empty, lastPublished: nil),
                "an empty folder must publish its emptiness, not stay silent")
    }

    @Test func repeatScansStillDeduplicate() {
        // The property the seed was there to provide, which must survive.
        #expect(!ProjectFolderWatcher.shouldPublish(.empty, lastPublished: .empty))
        let s = state(newFiles: 2, sessions: 5)
        #expect(!ProjectFolderWatcher.shouldPublish(s, lastPublished: s))
        #expect(ProjectFolderWatcher.shouldPublish(s, lastPublished: .empty))
    }

    @Test func anEmptyFolderOncePublishedHidesAnalyse() {
        // End to end through the two halves: publish `.empty`, and the
        // predicate reads it as "nothing to do".
        #expect(ProjectFolderWatcher.shouldPublish(.empty, lastPublished: nil))
        #expect(!SidebarOutlineController.hasWorkToDo(.empty))
    }

    // MARK: - The companion-type exclusion

    @Test func companionExtensionsAreNotIngestable() {
        // `.txt` is accepted into a project so a researcher's notes travel with
        // the recordings, but `classify_file` returns None for it. A folder of
        // only notes has nothing to analyse.
        #expect(ProjectFolderWatcher.companionExtensions.contains("txt"))
        #expect(ProjectFolderWatcher.eligibleExtensions.contains("txt"),
                "companion types must still be accepted into the project")
        for real in ["mp4", "mov", "m4a", "wav", "srt", "vtt", "docx"] {
            #expect(!ProjectFolderWatcher.companionExtensions.contains(real),
                    "\(real) is ingestable and must not be treated as a companion")
        }
    }

    // MARK: - The pane promises a number, and it has to be the same measurement

    @Test func paneCountsWhatTheMenuGatesOn() {
        // One field, two readers. The menu asks "is there anything here" and the
        // pane asks "how much" — if those came from separate measurements the
        // app could offer Analyse beside a pane denying there was anything to
        // analyse, which is the bug this whole slice exists to close.
        for n in [0, 1, 6, 58] {
            let d = state(newFiles: 0, sessions: nil, files: n)
            #expect(ContentView.filesToAnalyse(d) == n)
            #expect(SidebarOutlineController.hasWorkToDo(d) == (n > 0))
        }
    }

    @Test func unknownStateShowsTheDropTargetRatherThanACount() {
        // Deliberately the opposite resolution to `hasWorkToDo(nil)`. Hiding a
        // menu item leaves no way forward, so unknown resolves to *offer*; the
        // pane's alternative is the drop target, which is the right thing to
        // show when we do not yet know what the folder holds. A pane that
        // guessed a count would be asserting something it has not measured.
        #expect(ContentView.filesToAnalyse(nil) == 0)
        #expect(SidebarOutlineController.hasWorkToDo(nil))
    }

    @Test func companionFilesAreNotCounted() {
        // The acceptance criterion, end to end through the two pure helpers the
        // watcher itself uses: five recordings beside a researcher's notes are
        // "5 files to analyse", because five is what a run then ingests.
        // `isDirectory: true` is load-bearing: `filterEligible` compares each
        // candidate's parent against the root, and a parent URL always carries
        // the trailing slash a file-style `URL(fileURLWithPath:)` omits — so a
        // file-style root matches nothing and the filter silently returns [].
        // Production passes the watcher's real directory URL, which has it.
        let root = URL(fileURLWithPath: "/tmp/study", isDirectory: true)
        let dropped = ["a.mp4", "b.mov", "c.m4a", "d.srt", "e.docx", "notes.txt"]
            .map { root.appendingPathComponent($0) }
        let eligible = ProjectFolderWatcher.filterEligible(at: root, candidates: dropped)
        #expect(eligible.count == 6, "the notes travel with the recordings")
        #expect(ProjectFolderWatcher.ingestableCount(eligible) == 5)
    }

    @Test func aFolderOfOnlyNotesOffersNothing() {
        let root = URL(fileURLWithPath: "/tmp/study", isDirectory: true)
        let eligible = ProjectFolderWatcher.filterEligible(
            at: root, candidates: ["one.txt", "two.txt"].map(root.appendingPathComponent))
        #expect(ProjectFolderWatcher.ingestableCount(eligible) == 0)
    }
}

/// Pins that every surface offering **Analyse** asks one question.
///
/// The context menu and the unanalysed sheet both offer the verb. They agreed
/// by coincidence for as long as only one of them existed; `analyseIsOffered`
/// makes them agree by construction, the same way `ingestableFileCount` made
/// the pane and the menu agree about whether there was anything to analyse.
@Suite struct AnalyseOfferedTests {

    private func data(newFiles: Int = 0, sessions: Int? = nil, files: Int = 1) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [], sessionCount: sessions, totalDurationSeconds: nil,
            ingestableFileCount: files
        )
    }

    @Test func theEverydayCase_analysedProjectWithFinderAdditions() {
        // What the sheet exists for: files arrived in Finder, the watcher saw
        // them, and the sheet can now start the run it is describing.
        #expect(SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle,
            data: data(newFiles: 3, sessions: 14)))
    }

    @Test func aFileSubsetProjectIsNotOffered() {
        // The CLI cannot scope a run to a file list, so the sheet stays
        // informational rather than dimming a control nothing could enable.
        #expect(!SidebarOutlineController.analyseIsOffered(
            isFolderShaped: false, hasPath: true, state: .idle,
            data: data(newFiles: 3, sessions: 14)))
    }

    @Test func aPlaceholderWithNoFolderIsNotOffered() {
        #expect(!SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: false, state: .idle, data: data(newFiles: 3)))
    }

    @Test func aRunningProjectIsNotOffered() {
        #expect(!SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .running,
            data: data(newFiles: 3, sessions: 14)))
    }

    @Test func aStoppedOrFailedProjectKeepsTheRetry() {
        for state in [PipelineState.stopped(stagesComplete: []), .failed("boom", category: .unknown)] {
            #expect(SidebarOutlineController.analyseIsOffered(
                isFolderShaped: true, hasPath: true, state: state,
                data: data(newFiles: 5, sessions: 0)),
                "\(state) must stay retryable")
        }
    }

    @Test func nothingToDoIsNotOffered() {
        // Analysed, nothing new — the state that wants Re-analyse and nothing
        // else. The sheet cannot reach this case (it opens on deltas), but the
        // predicate is shared, so it is pinned here too.
        #expect(!SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle,
            data: data(newFiles: 0, sessions: 14)))
    }
}

/// Pins when **Re-analyse…** is worth offering — the mirror of `analyseIsOffered`.
///
/// It was `.disabled(true)` hardcoded, firing a bridge event that nothing in
/// `frontend/src` listened for. Dimming said "not right now" when the truth was
/// "not in this build", which sends a researcher hunting for a state that does
/// not exist.
@Suite struct ReAnalyseOfferedTests {

    private func data(newFiles: Int = 0, sessions: Int? = nil, files: Int = 1) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [], sessionCount: sessions, totalDurationSeconds: nil,
            ingestableFileCount: files
        )
    }

    @Test func analysedAndIdleIsTheStateItBelongsIn() {
        // The one state where Analyse is a measured no-op is exactly the state
        // Re-analyse is for.
        let d = data(newFiles: 0, sessions: 14)
        #expect(SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle, data: d))
        #expect(!SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle, data: d))
    }

    @Test func nothingToReplaceMeansNothingToOffer() {
        // A project that has never produced an analysis has nothing to throw
        // away — that is Analyse's job, and offering both would be two names
        // for one act.
        for sessions in [nil, 0] {
            #expect(!SidebarOutlineController.reAnalyseIsOffered(
                isFolderShaped: true, hasPath: true, state: .idle,
                data: data(sessions: sessions)))
        }
        #expect(!SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle, data: nil))
    }

    @Test func aRunningProjectIsNotOffered() {
        #expect(!SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .running, data: data(sessions: 14)))
    }

    @Test func aDriftedProjectIsOfferedBoth() {
        // Deliberate: re-analysing a drifted project is legitimate — it picks
        // the new files up too, just the expensive way. Hiding it would leave a
        // researcher who wants a clean rebuild with no route to one; the labels
        // are what distinguish the two.
        let d = data(newFiles: 3, sessions: 14)
        #expect(SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle, data: d))
        #expect(SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle, data: d))
    }

    @Test func aFileSubsetProjectIsNotOffered() {
        #expect(!SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: false, hasPath: true, state: .idle, data: data(sessions: 14)))
    }

    @Test func aFailedRunCanStillBeRebuiltFromScratch() {
        // Sessions on record plus a failed attempt: the retry is Analyse, but a
        // clean rebuild has to stay reachable — it is the only route past an
        // output directory the CLI refuses to overwrite.
        #expect(SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: true, hasPath: true,
            state: .failed("boom", category: .unknown), data: data(sessions: 14)))
    }
}

/// Pins **which pipeline states can start a run at all** — the shared gate under
/// both verbs, and the half that had no test.
///
/// `AnalyseAffordanceTests` above covers "is there work to do" thoroughly and
/// passed throughout, because every one of its cases leaves `state` at its
/// `.idle` default. The state axis was never varied, so an allowlist that
/// silently refused `.ready` — a finished analysis — sailed past a green suite
/// and shipped a project on which the context menu offered neither **Analyse**
/// nor **Re-analyse…** and the Project menu showed Re-analyse permanently
/// dimmed. Two surfaces agreeing, both wrong, exactly as designed.
///
/// The regression is worth naming precisely: `a1de4e51`'s message says
/// Re-analyse belongs in "the one state where Analyse is a measured no-op —
/// analysed, nothing new", and the switch it shipped excluded that state. Intent
/// and implementation disagreed and nothing could tell.
///
/// Matrix: `docs/design-analysis-lifecycle.md` §4.1.
@Suite struct PipelineFreeGateTests {

    private func analysed(newFiles: Int = 0, sessions: Int? = 3) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [],
            sessionCount: sessions,
            totalDurationSeconds: nil,
            ingestableFileCount: 4
        )
    }

    private func offered(_ state: PipelineState?, _ data: UnanalysedState)
        -> (analyse: Bool, reAnalyse: Bool) {
        (
            SidebarOutlineController.analyseIsOffered(
                isFolderShaped: true, hasPath: true, state: state, data: data),
            SidebarOutlineController.reAnalyseIsOffered(
                isFolderShaped: true, hasPath: true, state: state, data: data)
        )
    }

    // MARK: - Terminal states can start a run

    @Test func readyOffersReAnalyse() {
        // THE defect. A finished analysis is precisely what Re-analyse replaces.
        #expect(SidebarOutlineController.pipelineIsFree(.ready(Date())))
        #expect(offered(.ready(Date()), analysed()).reAnalyse)
    }

    @Test func readyAndDriftedOffersBoth() {
        // A researcher drops a fourth recording into an analysed folder in
        // Finder. Analyse folds it in; Re-analyse rebuilds from scratch and
        // picks it up the expensive way. Both are legitimate, so both show.
        let r = offered(.ready(Date()), analysed(newFiles: 1))
        #expect(r.analyse)
        #expect(r.reAnalyse)
    }

    @Test func completedPartialOffersBoth() {
        // A report exists at reduced fidelity — the state most likely to WANT a
        // rebuild, and it was refused one.
        let r = offered(.completedPartial(summary: PipelineSummary()), analysed(newFiles: 1))
        #expect(r.analyse)
        #expect(r.reAnalyse)
    }

    @Test func transcribeOnlyPartialCanContinue() {
        // `.partial` is a clean transcribe-only run: transcripts, no analysis.
        // "Continue (analyse)" is its documented CTA, so the gate must not be
        // what stops it.
        #expect(SidebarOutlineController.pipelineIsFree(.partial(kind: "transcribe-only", stagesComplete: [])))
    }

    @Test func stoppedAndFailedStillOffered() {
        // Already true before the fix — pinned so the fix didn't narrow anything.
        #expect(SidebarOutlineController.pipelineIsFree(.stopped(stagesComplete: [])))
        #expect(SidebarOutlineController.pipelineIsFree(.failed("boom", category: .unknown)))
        #expect(SidebarOutlineController.pipelineIsFree(.idle))
    }

    // MARK: - Busy and unknown states cannot

    @Test func runningAndQueuedRefuse() {
        // Single-slot FIFO: a second run cannot start.
        #expect(!SidebarOutlineController.pipelineIsFree(.running))
        #expect(!SidebarOutlineController.pipelineIsFree(.queued(position: 1)))
        #expect(!offered(.running, analysed()).analyse)
        #expect(!offered(.running, analysed()).reAnalyse)
    }

    @Test func scanningRefuses() {
        // The manifest read hasn't resolved — we don't yet know what a run would
        // be doing. Deliberately NOT the `hasWorkToDo(nil)` "unknown resolves to
        // offer" case: that one is about the *watcher*, this is about whether a
        // run can start.
        #expect(!SidebarOutlineController.pipelineIsFree(.scanning))
    }

    @Test func unreachableRefuses() {
        // A run against a vanished folder is doomed; availability tops the
        // severity chain (`design-desktop-project-status.md` §5).
        #expect(!SidebarOutlineController.pipelineIsFree(.unreachable(reason: .folderMissing)))
    }

    // MARK: - The gate is not the only guard

    @Test func readyButNoSessionsRefusesReAnalyse() {
        // Free pipeline, but nothing to throw away — `sessionCount` still rules.
        #expect(!offered(.ready(Date()), analysed(newFiles: 0, sessions: 0)).reAnalyse)
    }
}

/// Pins the F14 drift gate — the policy that can **delete evidence** before any
/// predicate reads it, and the layer with no coverage until 21 Aug 2026.
///
/// The suites above feed `UnanalysedState` values straight to `hasWorkToDo`, so
/// they test the state the watcher *produces*. The app stores a gated copy, and
/// the gate ran on a different question from the predicate three lines below it:
/// it asked `lastPipelineRunAt == nil` (a host-side stamp written only when a run
/// finishes in-app) while `hasWorkToDo` asked `sessionCount > 0` (the analysis
/// DB). For a project analysed by the CLI, imported, or analysed by an older
/// build, those disagree — and the disagreement composes into "no drift to show,
/// so nothing to analyse", with the drift deleted by the half that said the
/// project was new.
@Suite struct DriftGateTests {

    private func state(newFiles: Int, sessions: Int?, files: Int = 4) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [],
            sessionCount: sessions,
            totalDurationSeconds: nil,
            ingestableFileCount: files
        )
    }

    @Test func cliAnalysedProjectKeepsItsDrift() {
        // THE defect, at the layer that caused it. Three sessions in the DB and
        // a fourth file on disk: a baseline exists, so the drift is real and
        // must survive the gate. Under the old predicate this project had no
        // `lastPipelineRunAt`, so `newFiles` was emptied here and **Analyse
        // disappeared** — the researcher's only route was the destructive
        // Re-analyse, which was itself hidden by the state-gate bug.
        let gated = ProjectIndex.driftGated(state(newFiles: 1, sessions: 3))
        #expect(gated.newFiles.count == 1)
        #expect(SidebarOutlineController.hasWorkToDo(gated))
    }

    @Test func neverAnalysedProjectIsStillGated() {
        // The policy the gate exists for, unchanged: before any baseline every
        // file is "to be analysed", so calling them an exception is noise.
        let gated = ProjectIndex.driftGated(state(newFiles: 6, sessions: nil))
        #expect(gated.newFiles.isEmpty)
    }

    @Test func zeroSessionsIsTreatedAsNoBaseline() {
        // A run that produced nothing is not a baseline. `0` and `nil` agree.
        #expect(ProjectIndex.driftGated(state(newFiles: 6, sessions: 0)).newFiles.isEmpty)
    }

    @Test func gatingNeverTouchesTheOtherFields() {
        // The gate suppresses one *display* signal. Everything the Analyse
        // predicate and the detail pane count must pass through untouched —
        // this is what keeps a fresh folder of recordings analysable.
        let gated = ProjectIndex.driftGated(state(newFiles: 6, sessions: nil, files: 6))
        #expect(gated.ingestableFileCount == 6)
        #expect(gated.hasIngestableFiles)
        #expect(SidebarOutlineController.hasWorkToDo(gated))
    }

    @Test func gatedNeverAnalysedProjectStillOffersAnalyse() {
        // End to end through both halves, in the order the app runs them:
        // watcher → gate → predicate. The F14 trap the original suite named.
        let gated = ProjectIndex.driftGated(state(newFiles: 6, sessions: nil, files: 6))
        #expect(SidebarOutlineController.analyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .idle, data: gated))
    }

    @Test func analysedAndCleanOffersNothingNew() {
        // The invariant the fix must NOT break: a genuinely clean analysed
        // project still shouldn't offer Analyse, because running it is a
        // measured no-op. Re-analyse is the verb for that state.
        let gated = ProjectIndex.driftGated(state(newFiles: 0, sessions: 3))
        #expect(!SidebarOutlineController.hasWorkToDo(gated))
        #expect(SidebarOutlineController.reAnalyseIsOffered(
            isFolderShaped: true, hasPath: true, state: .ready(Date()), data: gated))
    }
}
