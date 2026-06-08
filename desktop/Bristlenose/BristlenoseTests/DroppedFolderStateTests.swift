import Testing
@testable import Bristlenose

// MARK: - DroppedFolderState.classify truth table

@Suite("Single-folder drop classification")
struct DroppedFolderStateTests {

    @Test func notTracked_isUntracked() {
        #expect(
            DroppedFolderState.classify(isTracked: false, folderLooksAnalysed: false) == .untracked
        )
    }

    @Test func notTracked_butAnalysedOnDisk_isStillUntracked() {
        // Untracked-but-analysed (clone, prior CLI run) is handled downstream
        // by the create-then-adopt path, not here.
        #expect(
            DroppedFolderState.classify(isTracked: false, folderLooksAnalysed: true) == .untracked
        )
    }

    // The regression this guards: a folder already in projects.json but with no
    // output marker (run killed before output, or added-and-never-run) used to
    // route to a dead-end duplicate alert. It must be drag-to-analyse-able.
    @Test func tracked_butNotAnalysed_isTrackedUnanalysed() {
        #expect(
            DroppedFolderState.classify(isTracked: true, folderLooksAnalysed: false)
                == .trackedUnanalysed
        )
    }

    @Test func tracked_andAnalysed_isTrackedAnalysed() {
        #expect(
            DroppedFolderState.classify(isTracked: true, folderLooksAnalysed: true)
                == .trackedAnalysed
        )
    }
}
