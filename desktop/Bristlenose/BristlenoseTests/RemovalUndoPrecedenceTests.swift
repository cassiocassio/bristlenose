import Foundation
import Testing
@testable import Bristlenose

/// A sidebar removal and the report's undo stack share one ⌘Z.
///
/// The removal store is checked first and, since 19 Aug 2026, never expires,
/// so a removal made an hour ago used to answer ⌘Z ahead of every report edit
/// made since — in every window. The fix: a new act on the report settles the
/// pending removal, as moving on in Mail does. Undoing and redoing through the
/// report's history is not a new act, and a removal with nothing after it
/// stays undoable.
@MainActor
struct RemovalUndoPrecedenceTests {

    private static func makeStore() -> (UndoableRemovalStore, ProjectIndex, URL) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("RemovalUndoPrecedenceTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        let store = UndoableRemovalStore()
        store.setProjectIndex(index)
        return (store, index, dir)
    }

    private static func undoState(_ canUndo: Bool, pushes: Int) -> [String: Any] {
        ["type": "undo-state", "canUndo": canUndo, "canRedo": false,
         "undoLabel": canUndo ? "Undo Star" : NSNull(), "redoLabel": NSNull(),
         "pushes": pushes]
    }

    @Test func aNewReportActSettlesThePendingRemoval() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let bridge = BridgeHandler()
        bridge.removalStore = store
        bridge.handleMessage(Self.undoState(false, pushes: 0))

        store.removeFromSidebar(index.addProject(name: "Alpha", path: "/tmp/a"))
        #expect(EditUndoRoute.resolve(removalPending: store.hasPending,
                                      reportCanUndo: bridge.canUndo) == .removal)

        // The researcher stars a quote: the report records a new act.
        bridge.handleMessage(Self.undoState(true, pushes: 1))
        #expect(!store.hasPending)
        #expect(EditUndoRoute.resolve(removalPending: store.hasPending,
                                      reportCanUndo: bridge.canUndo) == .report)
    }

    @Test func aRemovalWithNothingAfterItStaysUndoable() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let bridge = BridgeHandler()
        bridge.removalStore = store
        // The report already had history before the removal.
        bridge.handleMessage(Self.undoState(true, pushes: 3))

        store.removeFromSidebar(index.addProject(name: "Alpha", path: "/tmp/a"))
        // Another post with no new act — a re-render, a locale change.
        bridge.handleMessage(Self.undoState(true, pushes: 3))

        #expect(store.hasPending)
        #expect(EditUndoRoute.resolve(removalPending: store.hasPending,
                                      reportCanUndo: bridge.canUndo) == .removal)
        store.undoLastRemoval()
        #expect(index.projects.count == 1)
    }

    @Test func aPageReloadIsNotANewAct() {
        let (store, index, dir) = Self.makeStore()
        defer { try? FileManager.default.removeItem(at: dir) }
        let bridge = BridgeHandler()
        bridge.removalStore = store
        bridge.handleMessage(Self.undoState(true, pushes: 2))
        store.removeFromSidebar(index.addProject(name: "Alpha", path: "/tmp/a"))

        // A reload of the page restarts the count; an undo or redo leaves it.
        bridge.handleMessage(Self.undoState(false, pushes: 0))
        #expect(store.hasPending)
    }

    @Test func theRouteIsTheNewerStackOrNothing() {
        #expect(EditUndoRoute.resolve(removalPending: true, reportCanUndo: true) == .removal)
        #expect(EditUndoRoute.resolve(removalPending: false, reportCanUndo: true) == .report)
        #expect(EditUndoRoute.resolve(removalPending: false, reportCanUndo: false) == .none)
    }
}
