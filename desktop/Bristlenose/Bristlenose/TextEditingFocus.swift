import AppKit
import SwiftUI

/// Whether a native text field has the keyboard, and what the Edit menu's
/// keys do then.
///
/// Edit ▸ Undo and Redo are our own items (`CommandGroup(replacing: .undoRedo)`
/// — they speak for the report's stack and for a pending sidebar removal), and
/// a menu key equivalent is matched **before** the first responder's key
/// handling. So with one of the app's own text fields focused (the Quotes search
/// box, a study or folder being renamed, a field in Settings or a sheet), ⌘Z
/// never reached the field: it undid the last report change or brought back a
/// removed study. The same ordering gives ⌘⌫ to Project ▸ Remove from Sidebar
/// and Folder ▸ Delete, which cannot be undone for a folder. The guard that
/// existed (`isEditing`) mirrors the report's own web editor only (N140).
///
/// A native field is a field editor — an `NSTextView` — that is the key
/// window's first responder. Whoever acts on one of these keys asks here
/// **when the key is pressed**, not from a published flag: a field focused by
/// code (⌘F, a rename begun from the keyboard) is the first responder before
/// any window update has told the menu, and a ⌘⌫ that read a stale "not
/// editing" would remove a study.
@MainActor
enum TextEditingFocus {

    /// The text view editing in `window`: its first responder, when that is an
    /// editable `NSTextView` (the field editor of an `NSTextField`, or a text
    /// view). Nil for the report's `WKWebView` — its own editor is already
    /// handled through the bridge's `isEditing` — and for read-only text.
    static func editor(in window: NSWindow? = NSApp?.keyWindow) -> NSTextView? {
        guard let view = window?.firstResponder as? NSTextView, view.isEditable else { return nil }
        return view
    }

    /// Whether `window` has a native text editor active.
    static func isEditing(in window: NSWindow? = NSApp?.keyWindow) -> Bool {
        editor(in: window) != nil
    }

    /// Undo in the field. True when a field had the keyboard (whether or not it
    /// had anything to undo: ⌘Z in a field never falls through to the report).
    @discardableResult
    static func undo(in window: NSWindow? = NSApp?.keyWindow) -> Bool {
        guard let editor = editor(in: window) else { return false }
        if let manager = editor.undoManager, manager.canUndo { manager.undo() }
        return true
    }

    /// Redo in the field; the same contract as `undo(in:)`.
    @discardableResult
    static func redo(in window: NSWindow? = NSApp?.keyWindow) -> Bool {
        guard let editor = editor(in: window) else { return false }
        if let manager = editor.undoManager, manager.canRedo { manager.redo() }
        return true
    }

    /// ⌘⌫ pressed with a field focused: the field's own meaning, delete to the
    /// start of the line, in place of the menu item's. Only for the key — a
    /// mouse click on Project ▸ Remove from Sidebar is that menu item's own
    /// act, whatever has focus. True when the field took it.
    @discardableResult
    static func deleteToStartOfLine(
        invokedBy event: NSEvent?, in window: NSWindow? = NSApp?.keyWindow
    ) -> Bool {
        guard event?.type == .keyDown, let editor = editor(in: window) else { return false }
        editor.doCommand(by: #selector(NSResponder.deleteToBeginningOfLine(_:)))
        return true
    }
}

/// Publishes whether a native text field has the keyboard, so Edit ▸ Undo and
/// Redo stay enabled and say "Undo" while the researcher types in one — the
/// report's stack may be empty and the field's is not.
///
/// This drives how the items **read** and whether they are dimmed. What they
/// **do** is decided when pressed (`TextEditingFocus`), so a stale value here
/// costs a dimmed item for one keystroke, never a wrong act. Observed only by
/// the Edit section, like `KeyWindowWatcher`, never by `MenuCommands` itself.
@MainActor
final class TextEditingWatcher: ObservableObject {
    static let shared = TextEditingWatcher()

    @Published private(set) var isEditing = false

    private let window: () -> NSWindow?
    private var observer: NSObjectProtocol?

    /// `window` is injectable so a test can ask about a window that is not key.
    init(window: @escaping () -> NSWindow? = { NSApp?.keyWindow }) {
        self.window = window
        // There is no notification for a change of first responder. A window
        // updates after every event it handles, and a field that took the
        // focus by a click or a key is in place by then.
        observer = NotificationCenter.default.addObserver(
            forName: NSWindow.didUpdateNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.refresh() }
        }
    }

    deinit {
        if let observer { NotificationCenter.default.removeObserver(observer) }
    }

    func refresh() {
        let now = TextEditingFocus.isEditing(in: window())
        if now != isEditing { isEditing = now }
    }
}
