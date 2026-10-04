/**
 * UndoStore — the report's one undo stack (docs/design-people.md §B10).
 *
 * Every report act that can be undone pushes one entry here; Edit ▸ Undo on the
 * Mac and ⌘Z / Ctrl+Z in the browser both pop the top of it. One stack, so
 * there is no out-of-order undo to reason about.
 *
 * Module-level state + useSyncExternalStore, matching FocusModeStore, so the
 * native menu bridge, the browser key handler and any view can reach it
 * without provider nesting.
 *
 * **Ephemeral by design.** The stack lives as long as the page: a reload, a
 * project switch on the Mac (which remounts the web view) or a new run ends
 * it. That is the scope of a document's undo on the Mac; a stack that
 * outlived the page would have to live on the server
 * (docs/design-undo-catalog.md § The Swift ↔ Python divide, point 4).
 *
 * An entry carries the locale *key* of its action name, not the string, so a
 * language change re-labels the menu rather than leaving the old language in
 * it. The entry owns its own writes: the store only orders them.
 *
 * @module UndoStore
 */

import { useSyncExternalStore } from "react";

export interface UndoEntry {
  /** Locale key of the action name, e.g. `undo.actions.renameModerator`.
   *  Rendered into "Undo {{action}}" / "Redo {{action}}". */
  actionKey: string;
  undo: () => void | Promise<void>;
  redo: () => void | Promise<void>;
}

export interface UndoState {
  canUndo: boolean;
  canRedo: boolean;
  /** The action key the next undo would reverse, or null. */
  undoActionKey: string | null;
  redoActionKey: string | null;
}

/** Deep enough that nobody runs out in a session; bounded so a long one does
 *  not hold every closure it ever made. */
export const UNDO_DEPTH = 100;

let undoStack: UndoEntry[] = [];
let redoStack: UndoEntry[] = [];

const EMPTY: UndoState = {
  canUndo: false,
  canRedo: false,
  undoActionKey: null,
  redoActionKey: null,
};
let snapshot: UndoState = EMPTY;

const listeners = new Set<() => void>();

function emit(): void {
  const top = undoStack[undoStack.length - 1];
  const redoTop = redoStack[redoStack.length - 1];
  snapshot = {
    canUndo: !!top,
    canRedo: !!redoTop,
    undoActionKey: top?.actionKey ?? null,
    redoActionKey: redoTop?.actionKey ?? null,
  };
  for (const listener of listeners) listener();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getUndoState(): UndoState {
  return snapshot;
}

export function useUndoState(): UndoState {
  return useSyncExternalStore(subscribe, getUndoState);
}

/** Record an act that has just been done. A new act ends the redo branch. */
export function pushUndo(entry: UndoEntry): void {
  undoStack.push(entry);
  if (undoStack.length > UNDO_DEPTH) undoStack.shift();
  redoStack = [];
  emit();
}

/** Reverse the top act. Resolves false when there was nothing to undo. */
export async function undo(): Promise<boolean> {
  const entry = undoStack.pop();
  if (!entry) return false;
  redoStack.push(entry);
  emit();
  await entry.undo();
  return true;
}

/** Re-do the last undone act. Resolves false when there was nothing to redo. */
export async function redo(): Promise<boolean> {
  const entry = redoStack.pop();
  if (!entry) return false;
  undoStack.push(entry);
  emit();
  await entry.redo();
  return true;
}

/** Forget both stacks — the data the entries describe has been replaced. */
export function clearUndo(): void {
  if (undoStack.length === 0 && redoStack.length === 0) return;
  undoStack = [];
  redoStack = [];
  emit();
}

/** Test seam. */
export function resetUndoStore(): void {
  undoStack = [];
  redoStack = [];
  snapshot = EMPTY;
  listeners.clear();
}
