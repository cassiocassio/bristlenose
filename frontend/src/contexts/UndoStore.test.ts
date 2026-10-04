import { afterEach, describe, expect, it, vi } from "vitest";

import {
  UNDO_DEPTH,
  clearUndo,
  getUndoState,
  pushUndo,
  redo,
  resetUndoStore,
  subscribe,
  undo,
} from "./UndoStore";

/** An entry whose undo/redo move a shared value, so tests read outcomes. */
function setter(box: { v: string }, from: string, to: string, key = "test") {
  box.v = to;
  pushUndo({ action: key, undo: () => { box.v = from; }, redo: () => { box.v = to; } });
}

afterEach(() => resetUndoStore());

describe("UndoStore", () => {
  it("starts with nothing to undo or redo", async () => {
    expect(getUndoState()).toEqual({
      canUndo: false, canRedo: false, undoAction: null, redoAction: null,
    });
    expect(await undo()).toBe(false);
    expect(await redo()).toBe(false);
  });

  it("undoes the most recent act first, then the one before", async () => {
    const box = { v: "a" };
    setter(box, "a", "b", "first");
    setter(box, "b", "c", "second");
    expect(getUndoState().undoAction).toBe("second");
    await undo();
    expect(box.v).toBe("b");
    expect(getUndoState().undoAction).toBe("first");
    await undo();
    expect(box.v).toBe("a");
    expect(getUndoState().canUndo).toBe(false);
  });

  it("redoes what was undone, in reverse", async () => {
    const box = { v: "a" };
    setter(box, "a", "b");
    setter(box, "b", "c");
    await undo();
    await undo();
    expect(getUndoState().canRedo).toBe(true);
    await redo();
    expect(box.v).toBe("b");
    await redo();
    expect(box.v).toBe("c");
    expect(getUndoState().canRedo).toBe(false);
  });

  it("a new act ends the redo branch", async () => {
    const box = { v: "a" };
    setter(box, "a", "b");
    await undo();
    setter(box, "a", "z");
    expect(getUndoState().canRedo).toBe(false);
    expect(await redo()).toBe(false);
    expect(box.v).toBe("z");
  });

  it("keeps at most UNDO_DEPTH entries, dropping the oldest", async () => {
    const box = { v: "0" };
    for (let i = 0; i < UNDO_DEPTH + 5; i++) setter(box, String(i), String(i + 1));
    let n = 0;
    while (await undo()) n++;
    expect(n).toBe(UNDO_DEPTH);
    expect(box.v).toBe("5");
  });

  it("clear forgets both stacks and tells subscribers", async () => {
    const box = { v: "a" };
    setter(box, "a", "b");
    setter(box, "b", "c");
    await undo();
    const listener = vi.fn();
    subscribe(listener);
    clearUndo();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(getUndoState()).toMatchObject({ canUndo: false, canRedo: false });
  });

  it("the label moves before the write finishes, so a second ⌘Z takes the next entry", async () => {
    let release!: () => void;
    const slow = new Promise<void>((r) => { release = r; });
    pushUndo({ action: "first", undo: () => {}, redo: () => {} });
    pushUndo({ action: "second", undo: () => slow, redo: () => {} });
    const pending = undo();
    expect(getUndoState().undoAction).toBe("first");
    release();
    await pending;
  });
});
