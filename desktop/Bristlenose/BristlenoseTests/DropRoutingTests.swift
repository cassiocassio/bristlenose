import Testing
import Foundation
@testable import Bristlenose

/// Exhaustive table test for the unified drag-insertion routing — the Phase-B
/// "apocalypse fix" gate (spec §5). Each case is a structural gap the SwiftUI
/// `.onMove` islands could not cross.
@Suite struct DropRoutingTests {
    private let anyProject: (UUID) -> Bool = { _ in true }

    @Test func outOfFolder_toRoot() {
        let p = UUID()
        let d = DropRouting.resolve(draggedProjectIDs: [p], onto: .root, at: 0,
                                    isProjectID: anyProject)
        #expect(d == .move([ProjectMove(projectID: p, toFolder: nil, toIndex: 0)]))
    }

    @Test func betweenFolders() {
        let p = UUID(); let folderB = UUID()
        let d = DropRouting.resolve(draggedProjectIDs: [p], onto: .folder(folderB),
                                    at: DropRouting.append, isProjectID: anyProject)
        #expect(d == .move([ProjectMove(projectID: p, toFolder: folderB, toIndex: DropRouting.append)]))
    }

    @Test func intoFolder_fromRoot() {
        let p = UUID(); let folderA = UUID()
        let d = DropRouting.resolve(draggedProjectIDs: [p], onto: .folder(folderA),
                                    at: DropRouting.append, isProjectID: anyProject)
        #expect(d == .move([ProjectMove(projectID: p, toFolder: folderA, toIndex: DropRouting.append)]))
    }

    @Test func reorderAtRoot_keepsTargetIndex() {
        let p = UUID()
        let d = DropRouting.resolve(draggedProjectIDs: [p], onto: .root, at: 2,
                                    isProjectID: anyProject)
        #expect(d == .move([ProjectMove(projectID: p, toFolder: nil, toIndex: 2)]))
    }

    @Test func multiDrag_preservesOrderAndIncrementsIndex() {
        let a = UUID(); let b = UUID()
        let d = DropRouting.resolve(draggedProjectIDs: [a, b], onto: .root, at: 3,
                                    isProjectID: anyProject)
        #expect(d == .move([
            ProjectMove(projectID: a, toFolder: nil, toIndex: 3),
            ProjectMove(projectID: b, toFolder: nil, toIndex: 4),
        ]))
    }

    @Test func empty_isInvalid() {
        let d = DropRouting.resolve(draggedProjectIDs: [], onto: .root, at: 0,
                                    isProjectID: anyProject)
        #expect(d == .invalid)
    }

    @Test func nonProjectPayload_isInvalid() {
        let d = DropRouting.resolve(draggedProjectIDs: [UUID()], onto: .root, at: 0,
                                    isProjectID: { _ in false })
        #expect(d == .invalid)
    }
}
