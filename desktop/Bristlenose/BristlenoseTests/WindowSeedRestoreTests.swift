import Foundation
import Testing
@testable import Bristlenose

// Which study a window opens on, from its seed (WindowSeed.projectToOpen). The seed of a restored
// window arrives after onAppear, so the decision is asked again when the seed changes.

@Suite struct WindowSeedRestoreTests {
    private let study = UUID()
    private func seed(_ project: UUID?) -> WindowSeed { WindowSeed.fresh(project: project) }

    @Test func aSeededEmptyWindowOpensItsStudy() {
        #expect(WindowSeed.projectToOpen(seed: seed(study), selectionIsEmpty: true, knownProjects: [study]) == study)
    }

    @Test func noSeedOrAStudylessSeedOpensNothing() {
        #expect(WindowSeed.projectToOpen(seed: nil, selectionIsEmpty: true, knownProjects: [study]) == nil)
        #expect(WindowSeed.projectToOpen(seed: seed(nil), selectionIsEmpty: true, knownProjects: [study]) == nil)
    }

    @Test func aWindowThatAlreadyShowsAStudyIsLeftAlone() {
        // The write-back after a switch changes the seed; that must not reselect or loop.
        #expect(WindowSeed.projectToOpen(seed: seed(study), selectionIsEmpty: false, knownProjects: [study]) == nil)
    }

    @Test func aStudyRemovedFromTheSidebarIsNotOpened() {
        #expect(WindowSeed.projectToOpen(seed: seed(study), selectionIsEmpty: true, knownProjects: [UUID()]) == nil)
    }

    @Test func theLateRestoredSeedIsTakenOnceItArrives() {
        // The sequence measured on macOS 27: nil at appear, the study a moment later.
        let known: Set<UUID> = [study]
        #expect(WindowSeed.projectToOpen(seed: nil, selectionIsEmpty: true, knownProjects: known) == nil)
        #expect(WindowSeed.projectToOpen(seed: seed(study), selectionIsEmpty: true, knownProjects: known) == study)
    }
}
