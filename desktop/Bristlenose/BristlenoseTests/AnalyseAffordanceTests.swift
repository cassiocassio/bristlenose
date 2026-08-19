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
        ingestable: Bool = true
    ) -> UnanalysedState {
        UnanalysedState(
            newFiles: (0..<newFiles).map { URL(fileURLWithPath: "/tmp/p\($0).mp4") },
            missingFiles: [],
            sessionCount: sessions,
            totalDurationSeconds: nil,
            hasIngestableFiles: ingestable
        )
    }

    // MARK: - The matrix

    @Test func emptyProject_isNotOffered() {
        // The bug: highlighted "Analyse" beside "Add interview recordings…".
        #expect(!SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: nil, ingestable: false)))
    }

    @Test func mediaButNeverAnalysed_isOffered() {
        // The trap this predicate is built around: F14 zeroes `newFiles` for a
        // project with no baseline, so a fresh folder of recordings reports
        // none. Reading that as "nothing to do" would hide Analyse on exactly
        // the project that needs it.
        #expect(SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: nil, ingestable: true)))
    }

    @Test func analysedWithNothingNew_isNotOffered() {
        // Running it here is 0.1s of cache hits and a re-render. Offering a
        // control whose only observable effect is a re-render teaches the
        // researcher the button is broken. This state wants Re-analyse…
        #expect(!SidebarOutlineController.hasWorkToDo(
            state(newFiles: 0, sessions: 14, ingestable: true)))
    }

    @Test func analysedWithNewFiles_isOffered() {
        #expect(SidebarOutlineController.hasWorkToDo(
            state(newFiles: 3, sessions: 14, ingestable: true)))
    }

    @Test func failedRunWithMediaPresent_isOffered() {
        // Nothing was ingested, so every file still reads as new — the retry
        // must stay reachable.
        #expect(SidebarOutlineController.hasWorkToDo(
            state(newFiles: 5, sessions: 0, ingestable: true)))
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
            state(newFiles: 0, sessions: 14, ingestable: false)))
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
}
