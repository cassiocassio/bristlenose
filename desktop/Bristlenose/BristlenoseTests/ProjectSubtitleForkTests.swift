import Foundation
import Testing
@testable import Bristlenose

/// The forked-database delta: a defect signal from `SourceFilesReader`, routed
/// through `UnanalysedState.databaseForked` into the row's subtitle.
struct ProjectSubtitleForkTests {

    @Test func aForkOutranksMissingAndUnanalysed() {
        #expect(ProjectSubtitle.pickDelta(missingCount: 3, unanalysedCount: 2, databaseForked: true) == .databaseForked)
        #expect(ProjectSubtitle.pickDelta(missingCount: 3, unanalysedCount: 2, databaseForked: false) == .missing(count: 3))
        #expect(ProjectSubtitle.pickDelta(missingCount: 0, unanalysedCount: 0, databaseForked: false) == nil)
    }

    @Test func aForkRendersAsAnErrorGlyphThatOpensTheFilesPopover() {
        let v = SubtitleVariant.deltaOnly(.databaseForked)
        #expect(v.glyphKind == .error)
        #expect(v.glyphAction == .files)
    }

    @Test func resolveSurfacesAForkOnAnIdleRow() {
        let v = ProjectSubtitle.resolve(
            availability: .ready, pipelineState: .ready(Date()), isStopping: false,
            addingCount: nil, copy: nil, importBatch: nil, lastRunAt: nil,
            missingCount: 0, unanalysedCount: 0, databaseForked: true)
        #expect(v == .deltaOnly(.databaseForked))
    }

    /// The watcher's F14 gate zeroes `newFiles` on a never-analysed project; it
    /// must not swallow the fork, which is about the database, not drift.
    @Test func theDriftGateCarriesTheFork() {
        let state = UnanalysedState(
            newFiles: [URL(fileURLWithPath: "/p/a.mov")], missingFiles: [],
            sessionCount: 0, totalDurationSeconds: 0, ingestableFileCount: 1,
            discussionWanted: false, databaseForked: true)
        let gated = ProjectIndex.driftGated(state)
        #expect(gated.newFiles.isEmpty)
        #expect(gated.databaseForked)
    }

    @Test func aTwoRowSnapshotIsForkedAndAnUnreadableOneIsNot() {
        let two = ProjectDBSnapshot(ingestedBasenames: [], ingestedPaths: [], sessionCount: 1,
                                    totalDurationSeconds: 0, projectRowCount: 2)
        let one = ProjectDBSnapshot(ingestedBasenames: [], ingestedPaths: [], sessionCount: 1,
                                    totalDurationSeconds: 0, projectRowCount: 1)
        #expect(two.isForked)
        #expect(!one.isForked)
        #expect(!ProjectDBSnapshot.empty.isForked)
    }
}
