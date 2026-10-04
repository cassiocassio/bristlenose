import Foundation
import Testing
@testable import Bristlenose

/// Edit ▸ Undo / Redo take their state and their names from the report.
///
/// The SPA posts `undo-state` from `UndoSync.tsx` whenever its stack changes,
/// with whole per-language labels ("Undo Rename Moderator"). These pin the
/// Swift end of that wire: every field lands, a JS null clears a label, and a
/// new document starts with nothing to undo — the stack belongs to the page.
@MainActor
struct UndoStateBridgeTests {

    @Test func everyFieldLands() {
        let bridge = BridgeHandler()
        bridge.handleMessage([
            "type": "undo-state", "canUndo": true, "canRedo": true,
            "undoLabel": "Undo Rename Moderator", "redoLabel": "Redo Confirm Name",
        ])
        #expect(bridge.canUndo)
        #expect(bridge.canRedo)
        #expect(bridge.undoLabel == "Undo Rename Moderator")
        #expect(bridge.redoLabel == "Redo Confirm Name")
    }

    @Test func aNullLabelClearsIt() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "undo-state", "canUndo": true, "canRedo": true,
                              "undoLabel": "Undo Rename Moderator", "redoLabel": "Redo Rename Moderator"])
        bridge.handleMessage(["type": "undo-state", "canUndo": false, "canRedo": true,
                              "undoLabel": NSNull(), "redoLabel": "Redo Rename Moderator"])
        #expect(!bridge.canUndo)
        #expect(bridge.undoLabel == nil)
        #expect(bridge.redoLabel == "Redo Rename Moderator")
    }

    @Test func aNewDocumentHasNothingToUndo() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "undo-state", "canUndo": true, "canRedo": true,
                              "undoLabel": "Undo Rename Moderator", "redoLabel": "Redo Rename Moderator"])
        bridge.reset()
        #expect(!bridge.canUndo)
        #expect(!bridge.canRedo)
        #expect(bridge.undoLabel == nil)
        #expect(bridge.redoLabel == nil)
    }
}
