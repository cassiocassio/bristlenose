import Foundation
import Testing
@testable import Bristlenose

/// R57 (owner, 9 Nov 2026: animate a study row's height as work starts and ends, instead of the rows below
/// jumping). The in-place path is behind a default-off Debug switch; what is pinned here is the decision of
/// WHEN it may be used and WHICH rows animate. Whether it looks smooth is for the eye, not a test.
struct SidebarRowHeightRefreshTests {
    private let a = UUID()
    private let b = UUID()

    private var rows: [OutlineNode.Kind] { [.group("Projects"), .project(a), .project(b)] }

    @Test("The same rows, selection and no pending gesture may be refreshed in place")
    func sameRowsRefreshInPlace() {
        #expect(OutlineTree.canRefreshInPlace(
            displayed: rows.map(Optional.some), next: rows, selectionChanged: false, oneShotPending: false))
    }

    @Test("Different rows, in any way, take the full reload")
    func differentRowsReload() {
        let displayed = rows.map(Optional.some)
        #expect(!OutlineTree.canRefreshInPlace(
            displayed: displayed, next: rows + [.project(UUID())], selectionChanged: false, oneShotPending: false),
            "a study added")
        #expect(!OutlineTree.canRefreshInPlace(
            displayed: displayed, next: Array(rows.dropLast()), selectionChanged: false, oneShotPending: false),
            "a study removed")
        #expect(!OutlineTree.canRefreshInPlace(
            displayed: displayed, next: [rows[0], rows[2], rows[1]], selectionChanged: false, oneShotPending: false),
            "two studies swapped")
        #expect(!OutlineTree.canRefreshInPlace(
            displayed: [nil, .project(a), .project(b)], next: rows, selectionChanged: false, oneShotPending: false),
            "a displayed row that is not one of ours")
    }

    @Test("A selection change takes the full reload, which scrolls to it")
    func selectionChangeReloads() {
        #expect(!OutlineTree.canRefreshInPlace(
            displayed: rows.map(Optional.some), next: rows, selectionChanged: true, oneShotPending: false))
    }

    @Test("A pending icon reveal or rename takes the full reload, which starts it")
    func oneShotGesturesReload() {
        #expect(!OutlineTree.canRefreshInPlace(
            displayed: rows.map(Optional.some), next: rows, selectionChanged: false, oneShotPending: true))
    }

    @Test("An empty tree is never refreshed in place")
    func emptyReloads() {
        #expect(!OutlineTree.canRefreshInPlace(displayed: [], next: [], selectionChanged: false, oneShotPending: false))
    }

    @Test("Only the rows whose height differs are named")
    func onlyChangedRowsAreNamed() {
        let changed = OutlineTree.rowsWhoseHeightChanged(old: [28, 44, 44, 28], new: [28, 28, 44, 44])
        #expect(changed == IndexSet([1, 3]))
    }

    @Test("A sub-point difference is rounding, not a change")
    func roundingIsNotAChange() {
        #expect(OutlineTree.rowsWhoseHeightChanged(old: [44, 28], new: [44.4, 27.6]).isEmpty)
    }

    @Test("Unchanged heights name no rows")
    func nothingChanged() {
        #expect(OutlineTree.rowsWhoseHeightChanged(old: [28, 44], new: [28, 44]).isEmpty)
    }

    @Test("Counts that differ are not the same rows, so every row is named")
    func countMismatchNamesEverything() {
        #expect(OutlineTree.rowsWhoseHeightChanged(old: [28, 44], new: [28, 44, 44]) == IndexSet(integersIn: 0..<3))
    }
}
