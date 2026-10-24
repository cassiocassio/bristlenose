import Foundation
import Testing
@testable import Bristlenose

/// R47: a Finder drop on a study that can't take files (failed or
/// unreachable) lit the SwiftUI sidebar's row, was accepted, and then did
/// nothing. The AppKit outline already refused it mid-drag; these pin the
/// decision the SwiftUI drop closures now call and nothing else (21 Oct 2026).
///
/// A running or queued study was refused too until decision #100 (22 Oct
/// 2026): it now takes the files, and starts nothing for them.
@Suite("A Finder drop on a study")
struct StudyFinderDropTests {
    static let busy: [PipelineState] = [
        .failed(.passthrough("boom"), category: .unknown),
        .failedWithDiagnostic(summary: PipelineSummary()),
        .unreachable(reason: .timedOut),
    ]

    /// A run under way or waiting: files are taken, and no run is started.
    static let analysing: [PipelineState] = [.running, .queued(position: 1)]

    static let free: [PipelineState?] = [
        nil, .idle, .scanning, .ready(Date()), .stopped(stagesComplete: []),
        .completedPartial(summary: PipelineSummary()),
        .partial(kind: "transcribe-only", stagesComplete: []),
    ]

    @Test(arguments: busy)
    func aBusyStudyDoesNotLightUp(state: PipelineState) {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: nil,
                                          state: state, folder: "") == nil,
                "a study that won't take the files lit up under the drag")
    }

    @Test(arguments: busy)
    func aBusyStudySpringsTheDropBack(state: PipelineState) {
        #expect(!StudyFinderDrop.accepts(state: state, folder: ""),
                "the drop was accepted and then nothing happened")
    }

    @Test(arguments: free)
    func aStudyThatCanTakeFilesLightsAndAccepts(state: PipelineState?) {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: nil,
                                          state: state, folder: "") == study)
        #expect(StudyFinderDrop.accepts(state: state, folder: ""))
    }

    // MARK: - The drop itself, as the SwiftUI closures ask it

    static let video = URL(fileURLWithPath: "/tmp/bn-drop/Session 1.MOV")
    static let pdf = URL(fileURLWithPath: "/tmp/bn-drop/brief.pdf")

    @MainActor @Test(arguments: busy)
    func aBusyStudyRefusesARecording(state: PipelineState) {
        #expect(!StudyFinderDrop.takesDrop(state: state, folder: "", urls: [Self.video]))
    }

    /// R48 on this path: a drag of nothing a study ingests is sprung back,
    /// not accepted and then thrown away.
    @MainActor @Test(arguments: free)
    func aDragOfNothingIngestibleIsRefused(state: PipelineState?) {
        #expect(!StudyFinderDrop.takesDrop(state: state, folder: "", urls: [Self.pdf]))
    }

    @MainActor @Test(arguments: free)
    func aFreeStudyTakesARecording(state: PipelineState?) {
        #expect(StudyFinderDrop.takesDrop(state: state, folder: "", urls: [Self.pdf, Self.video]))
    }

    // MARK: - Decision #100: a study being analysed takes files

    @MainActor @Test(arguments: analysing)
    func aStudyBeingAnalysedTakesARecording(state: PipelineState) {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: nil,
                                          state: state, folder: "") == study)
        #expect(StudyFinderDrop.takesDrop(state: state, folder: "", urls: [Self.video]),
                "files added while the study was being analysed were dropped")
    }

    /// The files wait as "+N unanalysed": no run is started for them, and
    /// they are not seeded as known.
    @Test(arguments: analysing)
    func filesAddedDuringARunStartNothing(state: PipelineState) {
        #expect(!SidebarOutlineController.startsRunAfterCopy(state: state))
    }

    @Test(arguments: free)
    func filesAddedToAFreeStudyStartARun(state: PipelineState?) {
        #expect(SidebarOutlineController.startsRunAfterCopy(state: state))
    }

    /// Asked again when the copy ends (review of 8332d20c): Analyse pressed
    /// while a slow batch copies starts a run whose scan may already have
    /// passed, so the files must not be seeded as known, and a run that ended
    /// mid-copy still starts nothing.
    @Test func aRunStartedOrEndedDuringTheCopyStartsNothing() {
        #expect(!SidebarOutlineController.startsRunAfterCopy(droppedOn: .idle, copyEnded: .running))
        #expect(!SidebarOutlineController.startsRunAfterCopy(droppedOn: .idle, copyEnded: .queued(position: 1)))
        #expect(!SidebarOutlineController.startsRunAfterCopy(droppedOn: .running, copyEnded: .ready(Date())))
        #expect(SidebarOutlineController.startsRunAfterCopy(droppedOn: .idle, copyEnded: .idle))
        #expect(SidebarOutlineController.startsRunAfterCopy(droppedOn: .ready(Date()), copyEnded: .ready(Date())))
    }

    @Test func leavingAStudyClearsOnlyItsOwnHighlight() {
        let study = UUID(), other = UUID()
        #expect(StudyFinderDrop.highlight(isOver: false, study: study, current: study,
                                          state: .idle, folder: "") == nil)
        // The 0.4 s acknowledgement on another row is not this row's to clear.
        #expect(StudyFinderDrop.highlight(isOver: false, study: study, current: other,
                                          state: .idle, folder: "") == other)
    }

    @Test func aStudyThatTurnsBusyUnderTheDragStopsLighting() {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: study,
                                          state: .unreachable(reason: .timedOut), folder: "") == nil)
    }

    // MARK: - RE#20 #110 follow-up: a folder `run` refuses by name

    /// The home folder and the system roots (`ScanSelection.refusal`). The
    /// pane says the folder can't be analysed; a drop used to copy the files
    /// in anyway, for a run that then refused the folder.
    static let refusedFolders = [UserHome.path, "/Applications", "/"]

    @MainActor @Test(arguments: refusedFolders)
    func aStudyInAFolderRunRefusesTakesNothing(folder: String) {
        let study = UUID()
        #expect(!StudyFinderDrop.accepts(state: .idle, folder: folder))
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: nil,
                                          state: .idle, folder: folder) == nil,
                "a study whose folder can't be analysed lit up under the drag")
        #expect(!StudyFinderDrop.takesDrop(state: .idle, folder: folder, urls: [Self.video]))
    }

    /// Only the roots themselves: ~/Documents is an ordinary place for a study.
    @Test func aFolderInsideTheHomeFolderStillTakesFiles() {
        #expect(StudyFinderDrop.accepts(state: .idle, folder: UserHome.path + "/Documents"))
        #expect(StudyFinderDrop.accepts(state: .idle, folder: NSTemporaryDirectory()))
    }
}
