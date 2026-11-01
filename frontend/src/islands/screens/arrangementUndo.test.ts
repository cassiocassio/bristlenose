import { beforeEach, describe, expect, it } from "vitest";

import { getUndoState, resetUndoStore } from "../../contexts/UndoStore";
import { pushArrangementUndo } from "./arrangementUndo";

const entry = (action: string) => ({ action, undo: () => undefined, redo: () => undefined });
const settle = () => new Promise((r) => setTimeout(r, 0));

describe("pushArrangementUndo", () => {
  beforeEach(() => resetUndoStore());

  it("keeps the act when its save landed", async () => {
    pushArrangementUndo(entry("moveQuote"), Promise.resolve(true));
    await settle();
    expect(getUndoState().undoAction).toBe("moveQuote");
  });

  it("offers it at once, so the shortcut works while the save is still out", () => {
    pushArrangementUndo(entry("moveQuote"), new Promise(() => undefined));
    expect(getUndoState().canUndo).toBe(true);
  });

  it("withdraws the act when its save failed: Undo names the act before it, not one that does nothing", async () => {
    pushArrangementUndo(entry("tidy"), Promise.resolve(true));
    pushArrangementUndo(entry("moveQuote"), Promise.resolve(false));
    await settle();
    expect(getUndoState().undoAction).toBe("tidy");
  });
});
