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
                                          state: state) == nil,
                "a study that won't take the files lit up under the drag")
    }

    @Test(arguments: busy)
    func aBusyStudySpringsTheDropBack(state: PipelineState) {
        #expect(!StudyFinderDrop.accepts(state: state),
                "the drop was accepted and then nothing happened")
    }

    @Test(arguments: free)
    func aStudyThatCanTakeFilesLightsAndAccepts(state: PipelineState?) {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: nil,
                                          state: state) == study)
        #expect(StudyFinderDrop.accepts(state: state))
    }

    // MARK: - The drop itself, as the SwiftUI closures ask it

    static let video = URL(fileURLWithPath: "/tmp/bn-drop/Session 1.MOV")
    static let pdf = URL(fileURLWithPath: "/tmp/bn-drop/brief.pdf")

    @MainActor @Test(arguments: busy)
    func aBusyStudyRefusesARecording(state: PipelineState) {
        #expect(!StudyFinderDrop.takesDrop(state: state, urls: [Self.video]))
    }

    /// R48 on this path: a drag of nothing a study ingests is sprung back,
    /// not accepted and then thrown away.
    @MainActor @Test(arguments: free)
    func aDragOfNothingIngestibleIsRefused(state: PipelineState?) {
        #expect(!StudyFinderDrop.takesDrop(state: state, urls: [Self.pdf]))
    }

    @MainActor @Test(arguments: free)
    func aFreeStudyTakesARecording(state: PipelineState?) {
        #expect(StudyFinderDrop.takesDrop(state: state, urls: [Self.pdf, Self.video]))
    }

    // MARK: - Decision #100: a study being analysed takes files

    @MainActor @Test(arguments: analysing)
    func aStudyBeingAnalysedTakesARecording(state: PipelineState) {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: nil,
                                          state: state) == study)
        #expect(StudyFinderDrop.takesDrop(state: state, urls: [Self.video]),
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

    @Test func leavingAStudyClearsOnlyItsOwnHighlight() {
        let study = UUID(), other = UUID()
        #expect(StudyFinderDrop.highlight(isOver: false, study: study, current: study,
                                          state: .idle) == nil)
        // The 0.4 s acknowledgement on another row is not this row's to clear.
        #expect(StudyFinderDrop.highlight(isOver: false, study: study, current: other,
                                          state: .idle) == other)
    }

    @Test func aStudyThatTurnsBusyUnderTheDragStopsLighting() {
        let study = UUID()
        #expect(StudyFinderDrop.highlight(isOver: true, study: study, current: study,
                                          state: .unreachable(reason: .timedOut)) == nil)
    }
}
