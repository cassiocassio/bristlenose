import AppKit
import Testing
@testable import Bristlenose

/// ⌘Z and ⌘⌫ belong to a native text field while it has the keyboard (N140).
///
/// Edit ▸ Undo and Project ▸ Remove from Sidebar claim those keys before any
/// field editor sees them. What the menu items do is decided when they are
/// pressed, by asking the window's first responder, so these tests build a
/// real window with a real `NSTextField` and ask the same questions. Whether
/// SwiftUI's menu actually reaches the code on a keystroke is the by-hand check.
///
/// Serialised: they make a window and its field editor, which are shared AppKit
/// state.
@Suite("Native text fields keep the Edit keys", .serialized)
@MainActor
struct TextEditingFocusTests {

    private func focusedField(_ text: String = "") -> (window: NSWindow, field: NSTextField) {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 320, height: 120),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        let field = NSTextField(frame: NSRect(x: 10, y: 40, width: 280, height: 24))
        field.stringValue = text
        window.contentView?.addSubview(field)
        #expect(window.makeFirstResponder(field), "the field takes the keyboard")
        return (window, field)
    }

    private func keyEvent(in window: NSWindow) -> NSEvent? {
        NSEvent.keyEvent(
            with: .keyDown, location: .zero, modifierFlags: .command, timestamp: 0,
            windowNumber: window.windowNumber, context: nil,
            characters: "\u{7F}", charactersIgnoringModifiers: "\u{7F}",
            isARepeat: false, keyCode: 51)
    }

    private func clickEvent(in window: NSWindow) -> NSEvent? {
        NSEvent.mouseEvent(
            with: .leftMouseUp, location: .zero, modifierFlags: [], timestamp: 0,
            windowNumber: window.windowNumber, context: nil, eventNumber: 0,
            clickCount: 1, pressure: 0)
    }

    // MARK: - The route

    @Test("A field in use is first, ahead of a pending removal and the report")
    func theFieldGoesFirst() {
        #expect(EditUndoRoute.resolve(textEditing: true, removalPending: true,
                                      reportCanUndo: true) == .textField)
        #expect(EditUndoRoute.resolve(textEditing: true, removalPending: false,
                                      reportCanUndo: false) == .textField,
                "even with nothing else to undo, ⌘Z is the field's and must not be dimmed")
        #expect(EditUndoRoute.resolve(removalPending: true, reportCanUndo: true) == .removal)
    }

    // MARK: - Who is editing

    @Test("A focused editable field is a native editor; nothing focused is not")
    func editorDetection() {
        let (window, _) = focusedField("alpha")
        #expect(TextEditingFocus.isEditing(in: window))
        #expect(TextEditingFocus.editor(in: window) != nil)

        window.makeFirstResponder(nil)
        #expect(!TextEditingFocus.isEditing(in: window))
        #expect(!TextEditingFocus.isEditing(in: nil))
    }

    @Test("Text that can only be selected is not an editor")
    func readOnlyTextIsNotAnEditor() {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 320, height: 120),
                              styleMask: [.titled], backing: .buffered, defer: false)
        window.isReleasedWhenClosed = false
        let text = NSTextView(frame: NSRect(x: 10, y: 10, width: 280, height: 80))
        text.string = "Read only"
        text.isEditable = false
        text.isSelectable = true
        window.contentView?.addSubview(text)
        // The precondition that makes the assertion mean something: it is the
        // first responder, an NSTextView, and not editable.
        #expect(window.makeFirstResponder(text))
        #expect(window.firstResponder === text)

        #expect(!TextEditingFocus.isEditing(in: window),
                "⌘⌫ with selectable text focused is still the menu's")
    }

    // MARK: - ⌘Z

    @Test("Undo reverts the field's own typing and is never passed on")
    func undoIsTheFields() throws {
        let (window, _) = focusedField()
        let editor = try #require(TextEditingFocus.editor(in: window))
        editor.insertText("alpha", replacementRange: NSRange(location: 0, length: 0))
        #expect(editor.string == "alpha")

        #expect(TextEditingFocus.undo(in: window), "a field took the key")
        #expect(editor.string == "", "the typing went, and only the typing")

        #expect(TextEditingFocus.redo(in: window))
        #expect(editor.string == "alpha")
    }

    @Test("Undo in a field with nothing to undo is still the field's")
    func undoWithNothingToUndoStillStopsHere() {
        let (window, _) = focusedField("kept")
        #expect(TextEditingFocus.undo(in: window), "it must not fall through to a removal or the report")
        #expect(TextEditingFocus.redo(in: window))
        #expect(TextEditingFocus.editor(in: window)?.string == "kept")
    }

    @Test("With no field focused undo is not claimed")
    func noFieldNoClaim() {
        let (window, _) = focusedField("x")
        window.makeFirstResponder(nil)
        #expect(!TextEditingFocus.undo(in: window))
        #expect(!TextEditingFocus.redo(in: window))
    }

    // MARK: - ⌘⌫

    @Test("⌘⌫ in a field deletes to the start of the line and removes nothing")
    func commandDeleteIsTheFields() throws {
        let (window, _) = focusedField("alpha beta")
        let editor = try #require(TextEditingFocus.editor(in: window))
        editor.selectedRange = NSRange(location: 10, length: 0)

        let took = TextEditingFocus.deleteToStartOfLine(
            invokedBy: keyEvent(in: window), in: window)

        #expect(took)
        #expect(editor.string == "", "the line to the caret went")
    }

    @Test("Choosing the menu item with the mouse is the menu's act, field or not")
    func aClickIsNotTheKey() throws {
        let (window, _) = focusedField("alpha beta")
        let editor = try #require(TextEditingFocus.editor(in: window))
        editor.selectedRange = NSRange(location: 10, length: 0)

        #expect(!TextEditingFocus.deleteToStartOfLine(invokedBy: clickEvent(in: window), in: window))
        #expect(editor.string == "alpha beta", "nothing was deleted from the field")
    }

    /// The two ways to be wrong are not the same size: a swallowed click costs a
    /// second click, a honoured key costs a folder that cannot be brought back.
    /// So an event that is not positively a mouse event is the key.
    @Test("An event that is not a mouse event is taken as the key")
    func anythingButAClickIsTheKey() throws {
        let (window, _) = focusedField("alpha beta")
        let editor = try #require(TextEditingFocus.editor(in: window))
        editor.selectedRange = NSRange(location: 10, length: 0)
        let keyUp = NSEvent.keyEvent(
            with: .keyUp, location: .zero, modifierFlags: [], timestamp: 0,
            windowNumber: window.windowNumber, context: nil,
            characters: "\u{7F}", charactersIgnoringModifiers: "\u{7F}",
            isARepeat: false, keyCode: 51)

        #expect(TextEditingFocus.deleteToStartOfLine(invokedBy: keyUp, in: window),
                "the key-up that replaced the key-down before the action ran")
        #expect(editor.string == "")

        let (other, _) = focusedField("gamma")
        #expect(TextEditingFocus.deleteToStartOfLine(invokedBy: nil, in: other),
                "no event at all is not a click either")
        #expect(TextEditingFocus.editor(in: other)?.string == "")
    }

    @Test("⌘⌫ with no field focused is the menu's")
    func commandDeleteWithNoFieldIsTheMenus() {
        let (window, _) = focusedField("x")
        window.makeFirstResponder(nil)
        #expect(!TextEditingFocus.deleteToStartOfLine(invokedBy: keyEvent(in: window), in: window))
    }

    // MARK: - What the menu shows

    @Test("The watcher follows the focus, so Undo stays lit while typing")
    func watcherPublishesFocus() {
        let (window, _) = focusedField("x")
        let watcher = TextEditingWatcher(window: { window })
        watcher.refresh()
        #expect(watcher.isEditing)

        window.makeFirstResponder(nil)
        watcher.refresh()
        #expect(!watcher.isEditing)
    }
}
