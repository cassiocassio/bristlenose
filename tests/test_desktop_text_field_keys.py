"""⌘Z and ⌘⌫ belong to a native text field while it has the keyboard (N140).

Edit ▸ Undo and Redo are our own menu items, and Project ▸ Remove from Sidebar and
Folder ▸ Delete carry ⌘⌫. A menu key equivalent is matched before the first responder's
key handling, so with the Quotes search box or a rename field focused, ⌘Z undid the report or
restored a removed study and ⌘⌫ removed the selected study, or deleted the folder being
renamed (which cannot be undone).

The behaviour is tested in `TextEditingFocusTests` against a real window and field editor.
What no test can reach is SwiftUI's `Commands` body: that the four Button actions ask
`TextEditingFocus` *when pressed*. That wiring is pinned here in the source, the way
`test_desktop_toast_scope.py` pins the toast stores, because deleting one line of it
leaves every Swift test green and brings the bug back:

- Undo and Redo ask the focused field first;
- both ⌘⌫ items ask it before they act, and only for the key;
- the route is decided at the press, from the live responder, not from a published flag.
"""

from __future__ import annotations

import re
from pathlib import Path

_MENU = (
    Path(__file__).resolve().parent.parent
    / "desktop" / "Bristlenose" / "Bristlenose" / "MenuCommands.swift"
)


def _menu() -> str:
    return _MENU.read_text(encoding="utf-8")


def _struct(text: str, name: str) -> str:
    start = text.index(f"struct {name}")
    nxt = re.search(r"^(private )?struct |^// MARK:", text[start + 10:], flags=re.M)
    return text[start : start + 10 + nxt.start()] if nxt else text[start:]


def _button_action(struct: str, title: str) -> str:
    """The closure of the first `Button(<title>...) { ... }` in a struct, up to its modifiers."""
    start = struct.index(title)
    open_brace = struct.index("{", struct.index(")", start))
    end = struct.index("}\n            .", open_brace)
    return struct[open_brace:end]


def test_undo_asks_the_focused_field_when_pressed() -> None:
    undo = _struct(_menu(), "UndoRedoMenuContent")
    # In the Button's own action, not in `.disabled(...)`, where the stale flag is right.
    action = _button_action(undo, "Button(undoLabel")
    assert "route(textEditing: TextEditingFocus.isEditing())" in action
    assert "case .textField: TextEditingFocus.undo()" in action


def test_redo_asks_the_focused_field_first() -> None:
    undo = _struct(_menu(), "UndoRedoMenuContent")
    assert re.search(r"if !TextEditingFocus\.redo\(\) \{\s*bridgeHandler\.menuAction\(\"redo\"\)", undo)


def test_both_command_delete_items_defer_to_a_focused_field_for_the_key() -> None:
    text = _menu()
    for label, act in (
        ("desktop.menu.folder.delete", ".deleteFolder"),
        ("desktop.menu.project.removeFromSidebar", ".removeFromSidebar"),
    ):
        # The guard sits between the button and the act, and carries the event that
        # tells a keystroke from a click on the item.
        pattern = (
            rf'i18n\.t\("{re.escape(label)}"\).*?\{{\s*(?://[^\n]*\n\s*)*'
            r"if TextEditingFocus\.deleteToStartOfLine\(invokedBy: NSApp\.currentEvent\) \{ return \}"
            rf"\s*windowCommands\?\.perform\({re.escape(act)}\)"
        )
        assert re.search(pattern, text, flags=re.S), label
        # ...and it is the only place that performs the act, so a second, unguarded
        # Button added earlier in the file cannot satisfy the pattern above.
        assert text.count(f"windowCommands?.perform({act})") == 1, act


def test_the_undo_route_has_a_text_field_case_ahead_of_the_others() -> None:
    store = (_MENU.parent / "UndoableRemovalStore.swift").read_text(encoding="utf-8")
    resolve = store[store.index("static func resolve(") :]
    assert resolve.index("if textEditing { return .textField }") < resolve.index(
        "if removalPending"
    )
