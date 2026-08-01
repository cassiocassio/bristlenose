import Testing
import Foundation
@testable import Bristlenose

/// Exhaustive table test for the unified drag-insertion routing — the Phase-B
/// "apocalypse fix" gate (spec §5). Each case is a structural gap the SwiftUI
/// `.onMove` islands could not cross.
@Suite struct DropRoutingTests {
    private let anything: (SidebarDragItem) -> Bool = { _ in true }

    // MARK: - Routing

    @Test func outOfFolder_toRoot() {
        let p = UUID()
        let d = DropRouting.resolve(dragged: [.project(p)], onto: .root, at: 0, isKnown: anything)
        #expect(d == .move(DropPlan(items: [.project(p)], toFolder: nil, atIndex: 0)))
    }

    @Test func betweenFolders() {
        let p = UUID(); let folderB = UUID()
        let d = DropRouting.resolve(dragged: [.project(p)], onto: .folder(folderB),
                                    at: DropRouting.append, isKnown: anything)
        #expect(d == .move(DropPlan(items: [.project(p)], toFolder: folderB,
                                    atIndex: DropRouting.append)))
    }

    @Test func intoFolder_fromRoot() {
        let p = UUID(); let folderA = UUID()
        let d = DropRouting.resolve(dragged: [.project(p)], onto: .folder(folderA),
                                    at: DropRouting.append, isKnown: anything)
        #expect(d == .move(DropPlan(items: [.project(p)], toFolder: folderA,
                                    atIndex: DropRouting.append)))
    }

    @Test func reorderAtRoot_keepsTargetIndex() {
        let p = UUID()
        let d = DropRouting.resolve(dragged: [.project(p)], onto: .root, at: 2, isKnown: anything)
        #expect(d == .move(DropPlan(items: [.project(p)], toFolder: nil, atIndex: 2)))
    }

    @Test func multiDrag_preservesDragOrder() {
        let a = UUID(); let b = UUID()
        let d = DropRouting.resolve(dragged: [.project(a), .project(b)], onto: .root, at: 3,
                                    isKnown: anything)
        #expect(d == .move(DropPlan(items: [.project(a), .project(b)], toFolder: nil, atIndex: 3)))
    }

    @Test func folderReordersAtRoot() {
        let f = UUID()
        let d = DropRouting.resolve(dragged: [.folder(f)], onto: .root, at: 1, isKnown: anything)
        #expect(d == .move(DropPlan(items: [.folder(f)], toFolder: nil, atIndex: 1)))
    }

    @Test func mixedFolderAndProject_atRoot_isValid() {
        let f = UUID(); let p = UUID()
        let d = DropRouting.resolve(dragged: [.folder(f), .project(p)], onto: .root, at: 0,
                                    isKnown: anything)
        #expect(d == .move(DropPlan(items: [.folder(f), .project(p)], toFolder: nil, atIndex: 0)))
    }

    /// One level only — `OutlineNode` models folder → project, so nesting is refused.
    @Test func folderIntoFolder_isInvalid() {
        let d = DropRouting.resolve(dragged: [.folder(UUID())], onto: .folder(UUID()),
                                    at: DropRouting.append, isKnown: anything)
        #expect(d == .invalid)
    }

    /// A mixed drag is refused wholesale rather than silently dropping the folder —
    /// a partial move is a worse surprise than none.
    @Test func mixedDragIntoFolder_isInvalid() {
        let d = DropRouting.resolve(dragged: [.folder(UUID()), .project(UUID())],
                                    onto: .folder(UUID()), at: 0, isKnown: anything)
        #expect(d == .invalid)
    }

    @Test func empty_isInvalid() {
        let d = DropRouting.resolve(dragged: [], onto: .root, at: 0, isKnown: anything)
        #expect(d == .invalid)
    }

    @Test func unknownPayload_isInvalid() {
        let d = DropRouting.resolve(dragged: [.project(UUID())], onto: .root, at: 0,
                                    isKnown: { _ in false })
        #expect(d == .invalid)
    }

    // MARK: - Pasteboard codec

    @Test func pasteboardString_roundTrips() {
        let items: [SidebarDragItem] = [.project(UUID()), .folder(UUID())]
        for item in items {
            #expect(SidebarDragItem(pasteboardString: item.pasteboardString) == item)
        }
    }

    /// A bare UUID is what the old project-only payload wrote. Rejecting it keeps a
    /// stale drag from a previous build out of the new routing.
    @Test func pasteboardString_rejectsMalformed() {
        #expect(SidebarDragItem(pasteboardString: UUID().uuidString) == nil)
        #expect(SidebarDragItem(pasteboardString: "project:not-a-uuid") == nil)
        #expect(SidebarDragItem(pasteboardString: "lens:\(UUID().uuidString)") == nil)
        #expect(SidebarDragItem(pasteboardString: "") == nil)
    }

    // MARK: - Insertion arithmetic

    /// `at` is in pre-removal coordinates, so a downward move has to compensate for the
    /// dragged row vacating a slot above the insertion line. Dragging index 0 to the
    /// line at index 2 of [a,b,c,d] lands it *between* b and c, not after c.
    @Test func reordered_downwardMove_compensatesForVacatedSlot() {
        let a = UUID(); let b = UUID(); let c = UUID(); let d = UUID()
        let out = DropRouting.reordered(scope: [a, b, c, d], inserting: [a], at: 2)
        #expect(out == [b, a, c, d])
    }

    @Test func reordered_upwardMove_needsNoCompensation() {
        let a = UUID(); let b = UUID(); let c = UUID(); let d = UUID()
        let out = DropRouting.reordered(scope: [a, b, c, d], inserting: [d], at: 1)
        #expect(out == [a, d, b, c])
    }

    @Test func reordered_append_goesToEnd() {
        let a = UUID(); let b = UUID(); let c = UUID()
        let out = DropRouting.reordered(scope: [a, b, c], inserting: [a],
                                        at: DropRouting.append)
        #expect(out == [b, c, a])
    }

    /// Cross-scope: the dragged id isn't in this scope at all, so nothing is removed
    /// and the index needs no adjustment.
    @Test func reordered_insertFromAnotherScope() {
        let a = UUID(); let b = UUID(); let newcomer = UUID()
        let out = DropRouting.reordered(scope: [a, b], inserting: [newcomer], at: 1)
        #expect(out == [a, newcomer, b])
    }

    @Test func reordered_multiRun_staysContiguousAndOrdered() {
        let a = UUID(); let b = UUID(); let c = UUID(); let d = UUID()
        let out = DropRouting.reordered(scope: [a, b, c, d], inserting: [a, c], at: 3)
        #expect(out == [b, a, c, d])
    }

    @Test func reordered_indexBeyondScope_clampsToEnd() {
        let a = UUID(); let b = UUID()
        let out = DropRouting.reordered(scope: [a, b], inserting: [a], at: 99)
        #expect(out == [b, a])
    }

    @Test func reordered_movingEverything_keepsDragOrder() {
        let a = UUID(); let b = UUID()
        let out = DropRouting.reordered(scope: [a, b], inserting: [b, a], at: 0)
        #expect(out == [b, a])
    }

    /// A negative index that isn't `append` clamps to the front rather than being
    /// mistaken for "end of list" — the two sentinels must not blur into each other.
    @Test func reordered_negativeIndexOtherThanAppend_clampsToFront() {
        let a = UUID(); let b = UUID()
        let out = DropRouting.reordered(scope: [a, b], inserting: [b], at: -5)
        #expect(out == [b, a])
    }

    /// Dropping a row back onto its own slot is a no-op, not an off-by-one shuffle.
    @Test func reordered_dropOntoOwnSlot_isStable() {
        let a = UUID(); let b = UUID(); let c = UUID()
        let out = DropRouting.reordered(scope: [a, b, c], inserting: [b], at: 1)
        #expect(out == [a, b, c])
    }

    /// The invariant that matters most: whatever the index, the result is a
    /// permutation of the scope plus the newcomers — nothing lost, nothing duplicated.
    /// A duplicate id would mean two rows claiming one `position`.
    @Test func reordered_isAlwaysAPermutation() {
        let a = UUID(); let b = UUID(); let c = UUID(); let d = UUID(); let newcomer = UUID()
        let scope = [a, b, c, d]
        for at in [DropRouting.append, -5, 0, 1, 2, 3, 4, 99] {
            for run in [[a], [d, b], [newcomer], [a, b, c, d]] {
                let out = DropRouting.reordered(scope: scope, inserting: run, at: at)
                #expect(Set(out) == Set(scope).union(run))
                #expect(out.count == Set(out).count)
            }
        }
    }
}
