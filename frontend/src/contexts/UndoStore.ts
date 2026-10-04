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
 * An entry carries an action *id*, not a string: the menu labels are the
 * locale keys `undo.undo.<action>` and `undo.redo.<action>`, written whole per
 * language — Apple's own "Undo Rename" is not "Undo" + "Rename" in Spanish,
 * Russian or Norwegian — and a language change re-labels the menu rather than
 * leaving the old language in it. The entry owns its own writes: the store
 * only orders them.
 *
 * @module UndoStore
 */

import { useSyncExternalStore } from "react";

export interface UndoEntry {
  /** The act, e.g. `renameModerator` — labelled by `undo.undo.<action>` and
   *  `undo.redo.<action>`. */
  action: string;
  undo: () => void | Promise<void>;
  redo: () => void | Promise<void>;
}

export interface UndoState {
  canUndo: boolean;
  canRedo: boolean;
  /** The act the next undo would reverse, or null. */
  undoAction: string | null;
  redoAction: string | null;
  /** How many acts have been recorded since the page loaded. Rises only on a
   *  new act — never on undo, redo or clear — so the Mac can tell "the
   *  researcher did something new" from "they moved through the history"
   *  (it settles a pending sidebar removal on the first; see BridgeHandler). */
  pushes: number;
}

/** Deep enough that nobody runs out in a session; bounded so a long one does
 *  not hold every closure it ever made. */
export const UNDO_DEPTH = 100;

let undoStack: UndoEntry[] = [];
let redoStack: UndoEntry[] = [];

const EMPTY: UndoState = {
  canUndo: false,
  canRedo: false,
  undoAction: null,
  redoAction: null,
  pushes: 0,
};
let snapshot: UndoState = EMPTY;
let pushes = 0;

const listeners = new Set<() => void>();

function emit(): void {
  const top = undoStack[undoStack.length - 1];
  const redoTop = redoStack[redoStack.length - 1];
  snapshot = {
    canUndo: !!top,
    canRedo: !!redoTop,
    undoAction: top?.action ?? null,
    redoAction: redoTop?.action ?? null,
    pushes,
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
  pushes += 1;
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
  pushes = 0;
  snapshot = EMPTY;
  listeners.clear();
}
