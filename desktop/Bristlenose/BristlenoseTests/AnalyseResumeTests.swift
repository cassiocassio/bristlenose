import Foundation
import Testing
@testable import Bristlenose

/// A run that did not finish can always be resumed with **Analyse** (R19
/// follow-up, 20 Oct 2026).
///
/// `analyseIsOffered` asked only "is there work to do", which `hasWorkToDo`
/// answers from the folder: sessions in the database and no new files means
/// analysed, nothing to do. A run stopped or failed after transcription is
/// exactly that shape — every recording has its session, the quotes and themes
/// were never made — so Analyse was hidden and the only verb left was
/// **Re-analyse…**, which starts from scratch and discards the researcher's
/// work. Quitting mid-run now ends in Stopped (`fa686f9a`), so this is the
/// state a quit leaves behind.
@Suite struct AnalyseResumeTests {

    /// Every recording transcribed and in the sessions table; nothing new.
    private let transcribed = UnanalysedState(
        newFiles: [], missingFiles: [], sessionCount: 8, totalDurationSeconds: nil,
        ingestableFileCount: 8
    )

    private let unfinished: [PipelineState] = [
        .stopped(stagesComplete: ["s01_ingest", "s05_transcribe"]),
        .failed(.passthrough("boom"), category: .network),
        .failedWithDiagnostic(summary: PipelineSummary()),
    ]

    @Test func aRunThatDidNotFinishOffersAnalyseWithNothingNew() {
        for state in unfinished {
            #expect(SidebarOutlineController.analyseIsOffered(
                hasPath: true, isAvailable: true,
                state: state, data: transcribed),
                "\(state): the only verb left would be Re-analyse…, which discards the work")
        }
    }

    /// The other gates still hold for an unfinished run.
    @Test func anUnfinishedRunStillNeedsItsFolder() {
        for state in unfinished {
            #expect(!SidebarOutlineController.analyseIsOffered(
                hasPath: true, isAvailable: false,
                state: state, data: transcribed), "\(state): ejected drive (R63)")
        }
    }

    /// A finished analysis with nothing new still wants Re-analyse, not Analyse.
    @Test func aFinishedAnalysisWithNothingNewIsUnchanged() {
        for state in [PipelineState.idle, .ready(Date()), .completedPartial(summary: PipelineSummary())] {
            #expect(!SidebarOutlineController.analyseIsOffered(
                hasPath: true, isAvailable: true,
                state: state, data: transcribed), "\(state)")
        }
    }
}
