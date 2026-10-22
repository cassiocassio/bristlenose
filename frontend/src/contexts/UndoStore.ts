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
/** Bumped by every clear, so a write that fails after one puts nothing back. */
let clears = 0;
/** Acts an undo or redo has run on: their writes may have landed, so they
 *  are not taken off the stack at once (`dropUndo`). */
let stepped = new WeakSet<UndoEntry>();
/** Acts an undo or redo of which has landed: real, whatever their own write
 *  did, so never withdrawn. */
let landed = new WeakSet<UndoEntry>();
/** Stepped acts whose own write failed before any step of them landed: they
 *  leave the stack as soon as an undo or redo of them fails too, and stay if
 *  one lands. */
let withdrawn = new WeakSet<UndoEntry>();

/** What a push replaced: the redo branch it ended and any act it pushed off
 *  the bottom, so withdrawing that act puts them back. */
interface PushRecord {
  entry: UndoEntry;
  redo: UndoEntry[];
  shifted: UndoEntry[];
}
/** The pushes still on the undo stack, oldest first. */
let pushLog: PushRecord[] = [];

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
  const shifted = undoStack.length > UNDO_DEPTH ? undoStack.shift() : undefined;
  pushLog.push({ entry, redo: redoStack, shifted: shifted ? [shifted] : [] });
  if (pushLog.length > UNDO_DEPTH) pushLog.shift();
  redoStack = [];
  emit();
}

/** Reverse the top act. Resolves false when there was nothing to undo, or
 *  the undo's write failed. */
export function undo(): Promise<boolean> {
  return step("undo");
}

/** Re-do the last undone act. Resolves false when there was nothing to redo,
 *  or the redo's write failed. */
export function redo(): Promise<boolean> {
  return step("redo");
}

/**
 * Move the top act across, then run its write. The label moves at once, so a
 * second ⌘Z takes the next entry; if the write fails the act goes back where it
 * was — beneath any act done meanwhile — because what it describes is still
 * true (R9: Edit used to offer Redo for a split the server never undid). A
 * failed redo after a new act is dropped instead: the new act ended the redo
 * branch. The entry's own write tells the researcher why (`toastSaveFailed`);
 * the stack keeps its place and logs, so the rejection stops here.
 */
async function step(kind: "undo" | "redo"): Promise<boolean> {
  // Read through a function: a new act replaces the redo array, a clear both.
  const stacks = () => (kind === "undo" ? [undoStack, redoStack] : [redoStack, undoStack]);
  const [from, to] = stacks();
  const entry = from.pop();
  if (!entry) return false;
  stepped.add(entry);
  const at = from.length;
  const clearedAt = clears;
  const pushedAt = pushes;
  to.push(entry);
  emit();
  try {
    await (kind === "undo" ? entry.undo() : entry.redo());
    // A write of it landed: whatever its own write did, the act is real now.
    landed.add(entry);
    withdrawn.delete(entry);
    return true;
  } catch (err) {
    console.error(`${kind} ${entry.action} failed`, err);
    // A clear means the data the entry describes was replaced: nothing to put back.
    if (clears !== clearedAt) return false;
    const [home, away] = stacks();
    const i = away.lastIndexOf(entry);
    if (i >= 0) away.splice(i, 1);
    // Its own write failed and so did this one: nothing of it landed.
    if (withdrawn.has(entry)) {
      handBack(entry);
      emit();
      return false;
    }
    const branchEnded = kind === "redo" && pushes !== pushedAt;
    if (!branchEnded && !home.includes(entry)) home.splice(Math.min(at, home.length), 0, entry);
    emit();
    return false;
  }
}

/**
 * Withdraw an act whose own write failed (decision #15): it never happened, so
 * Edit ▸ Undo names the act before it rather than one whose undo does nothing.
 * The redo branch it ended and any act it pushed off the bottom come back too:
 * at once when it was the last act recorded, or handed to the next act, which
 * was recorded with nothing to redo because this one had just ended it. An act
 * an undo or redo is running on waits for that write: it stays if the write
 * lands, and leaves if it fails (R9). `pushes` does not go back — the Mac has
 * already read the rise.
 */
export function dropUndo(entry: UndoEntry): void {
  if (landed.has(entry)) return;
  if (stepped.has(entry)) {
    withdrawn.add(entry);
    return;
  }
  const i = undoStack.lastIndexOf(entry);
  if (i < 0) return;
  undoStack.splice(i, 1);
  handBack(entry);
  emit();
}

/**
 * Give back what a withdrawn act's push replaced: to the stacks when no act
 * was recorded after it, else to the next push, which in time would have
 * ended that branch itself. Its record leaves the log, so an earlier act
 * withdrawn later hands on past it.
 */
function handBack(entry: UndoEntry): void {
  const r = pushLog.findIndex((p) => p.entry === entry);
  if (r < 0) return;
  const [record] = pushLog.splice(r, 1);
  const next = pushLog[r];
  if (next) {
    next.redo = [...record.redo, ...next.redo.filter((e) => e !== entry)];
    next.shifted = [...record.shifted, ...next.shifted];
  } else {
    // Beneath anything undone since: those were undone after it was recorded.
    redoStack = [...record.redo, ...redoStack.filter((e) => e !== entry)];
    undoStack.unshift(...record.shifted);
  }
}

/** Forget both stacks — the data the entries describe has been replaced. */
export function clearUndo(): void {
  clears += 1;
  pushLog = [];
  if (undoStack.length === 0 && redoStack.length === 0) return;
  undoStack = [];
  redoStack = [];
  emit();
}

/** Test seam. */
export function resetUndoStore(): void {
  clears += 1;
  undoStack = [];
  redoStack = [];
  stepped = new WeakSet();
  landed = new WeakSet();
  withdrawn = new WeakSet();
  pushLog = [];
  pushes = 0;
  snapshot = EMPTY;
  listeners.clear();
}
