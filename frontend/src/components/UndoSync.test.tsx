import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUndoState, pushUndo, resetUndoStore } from "../contexts/UndoStore";
import { postUndoState } from "../shims/bridge";
import { isEmbedded } from "../utils/embedded";
import { UndoSync } from "./UndoSync";

vi.mock("../shims/bridge", () => ({ postUndoState: vi.fn() }));
vi.mock("../utils/embedded", () => ({ isEmbedded: vi.fn(() => false) }));
vi.mock("../contexts/LastRunStore", () => ({
  useLastRun: () => ({ lastRun: null, refreshKey: 0 }),
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => `«${key}»` }),
}));

const postMock = vi.mocked(postUndoState);
const embeddedMock = vi.mocked(isEmbedded);

function entry(box: { v: string }, from: string, to: string, action = "renameModerator") {
  box.v = to;
  pushUndo({ action, undo: () => { box.v = from; }, redo: () => { box.v = to; } });
}

const key = (k: string, init: KeyboardEventInit = {}) =>
  act(() => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true, ...init }));
  });

const menu = (action: string) =>
  act(() => {
    window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action } }));
  });

beforeEach(() => {
  postMock.mockClear();
  embeddedMock.mockReturnValue(false);
});

afterEach(() => {
  resetUndoStore();
  document.body.innerHTML = "";
});

describe("UndoSync — browser keys", () => {
  it("⌘Z undoes and ⇧⌘Z redoes", async () => {
    render(<UndoSync />);
    const box = { v: "a" };
    act(() => entry(box, "a", "b"));
    await key("z", { metaKey: true });
    expect(box.v).toBe("a");
    await key("z", { metaKey: true, shiftKey: true });
    expect(box.v).toBe("b");
  });

  it("Ctrl+Z and Ctrl+Y work off the Mac", async () => {
    render(<UndoSync />);
    const box = { v: "a" };
    act(() => entry(box, "a", "b"));
    await key("z", { ctrlKey: true });
    expect(box.v).toBe("a");
    await key("y", { ctrlKey: true });
    expect(box.v).toBe("b");
  });

  it("leaves ⌘Z to a text field that has focus", async () => {
    render(<UndoSync />);
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    const box = { v: "a" };
    act(() => entry(box, "a", "b"));
    await key("z", { metaKey: true });
    expect(box.v).toBe("b");
  });

  it("does not claim ⌘Z when there is nothing to undo", () => {
    render(<UndoSync />);
    const ev = new KeyboardEvent("keydown", { key: "z", metaKey: true, cancelable: true });
    act(() => { document.dispatchEvent(ev); });
    expect(ev.defaultPrevented).toBe(false);
  });

  it("a bare z is not undo", async () => {
    render(<UndoSync />);
    const box = { v: "a" };
    act(() => entry(box, "a", "b"));
    await key("z");
    expect(box.v).toBe("b");
  });
});

describe("UndoSync — the Mac app", () => {
  beforeEach(() => embeddedMock.mockReturnValue(true));

  it("tells Edit ▸ Undo what it would undo, by name", () => {
    render(<UndoSync />);
    expect(postMock).toHaveBeenLastCalledWith(false, false, null, null, 0);
    act(() => entry({ v: "" }, "a", "b", "confirmName"));
    expect(postMock).toHaveBeenLastCalledWith(true, false, "«undo.undo.confirmName»", null, 1);
  });

  it("the menu's undo and redo actions drive the stack", async () => {
    render(<UndoSync />);
    const box = { v: "a" };
    act(() => entry(box, "a", "b"));
    await menu("undo");
    expect(box.v).toBe("a");
    // An undo is not a new act: the count holds.
    expect(postMock).toHaveBeenLastCalledWith(false, true, null, "«undo.redo.renameModerator»", 1);
    await menu("redo");
    expect(box.v).toBe("b");
    expect(getUndoState().canUndo).toBe(true);
  });

  it("leaves ⌘Z to the Edit menu", async () => {
    render(<UndoSync />);
    const box = { v: "a" };
    act(() => entry(box, "a", "b"));
    await key("z", { metaKey: true });
    expect(box.v).toBe("b");
  });
});
