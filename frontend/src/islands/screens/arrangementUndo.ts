import { dropUndo, pushUndo, type UndoEntry } from "../../contexts/UndoStore";

/**
 * Record an undoable change to a Screens arrangement whose save may fail.
 *
 * The entry is offered at once, so the shortcut works while the save is still out. If the save
 * fails the change never happened (layout.ts puts the board back), so the entry is withdrawn:
 * Edit ▸ Undo names the act before it rather than one whose undo does nothing (decision #15,
 * 22 Oct 2026, which the quote store already follows).
 */
export function pushArrangementUndo(entry: UndoEntry, saved: Promise<boolean>): void {
  pushUndo(entry);
  void saved.then((ok) => {
    if (!ok) dropUndo(entry);
  });
}
