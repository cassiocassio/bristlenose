/**
 * Split and join, web side (design-transcript-editing.md §"Split and join,
 * stage 1"): the caret becomes a word count, the edit is one undoable act, and
 * the page is told to re-read.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUndoState, redo, resetUndoStore, undo } from "../contexts/UndoStore";
import {
  deleteParagraphEdit,
  postParagraphJoin,
  postParagraphReassign,
  postParagraphSplit,
  toastSaveFailed,
} from "./api";
import {
  TRANSCRIPT_WRITTEN_EVENT,
  caretAtStart,
  caretWords,
  drawnTokens,
  joinParagraphs,
  reassignParagraph,
  splitParagraph,
  verifyOf,
} from "./paragraphEdits";

vi.mock("./api", async (importOriginal) => {
  const real = await importOriginal<typeof import("./api")>();
  return {
    ...real,
    postParagraphSplit: vi.fn(),
    postParagraphJoin: vi.fn(),
    postParagraphReassign: vi.fn(),
    deleteParagraphEdit: vi.fn(),
    toastSaveFailed: vi.fn(),
  };
});

beforeEach(() => {
  vi.mocked(postParagraphSplit).mockReset().mockResolvedValue({ id: 7 });
  vi.mocked(postParagraphJoin).mockReset().mockResolvedValue({ id: 8 });
  vi.mocked(postParagraphReassign).mockReset().mockResolvedValue({ id: 6 });
  vi.mocked(deleteParagraphEdit).mockReset().mockResolvedValue(undefined);
  vi.mocked(toastSaveFailed).mockReset();
});

afterEach(() => {
  resetUndoStore();
  document.body.innerHTML = "";
});

function caretIn(body: HTMLElement, node: Node, offset: number): void {
  const range = document.createRange();
  range.setStart(node, offset);
  range.collapse(true);
  const sel = window.getSelection()!;
  sel.removeAllRanges();
  sel.addRange(range);
  void body;
}

describe("the caret, in words", () => {
  const body = () => {
    const el = document.createElement("div");
    el.textContent = "Thanks for having me, it is good";
    document.body.appendChild(el);
    return el;
  };

  it("between two words counts the words before it", () => {
    const el = body();
    caretIn(el, el.firstChild!, "Thanks for having me, ".length);
    expect(caretWords(el)).toBe(4);
  });

  it("at the end of a word counts that word", () => {
    const el = body();
    caretIn(el, el.firstChild!, "Thanks for having me,".length);
    expect(caretWords(el)).toBe(4);
  });

  it("inside a word cuts before it", () => {
    const el = body();
    caretIn(el, el.firstChild!, "Thanks for hav".length);
    expect(caretWords(el)).toBe(2);
  });

  it("at the start is zero, and outside the paragraph is nothing", () => {
    const el = body();
    caretIn(el, el.firstChild!, 0);
    expect(caretWords(el)).toBe(0);
    const other = document.createElement("p");
    other.textContent = "elsewhere";
    document.body.appendChild(other);
    caretIn(other, other.firstChild!, 2);
    expect(caretWords(el)).toBeNull();
  });

  it("is at the start only before the first character, where Backspace joins", () => {
    const el = body();
    caretIn(el, el.firstChild!, 0);
    expect(caretAtStart(el)).toBe(true);
    caretIn(el, el.firstChild!, "Tha".length);
    expect(caretWords(el)).toBe(0);
    expect(caretAtStart(el)).toBe(false);
    const cjk = document.createElement("div");
    cjk.textContent = "今日はよろしくお願いします";
    document.body.appendChild(cjk);
    caretIn(cjk, cjk.firstChild!, 4);
    expect(caretAtStart(cjk)).toBe(false);
  });

  it("counts the words the page draws: Whisper's where there are any", () => {
    expect(drawnTokens("a  b c", null)).toEqual(["a", "b", "c"]);
    expect(drawnTokens("ignored", [{ text: " it" }, { text: "is" }])).toEqual(["it", "is"]);
    expect(verifyOf(["a", "b", "c", "d", "e", "f", "g", "h"], 1)).toBe("b c d e f g");
  });
});

describe("splitParagraph and joinParagraphs", () => {
  it("a split is one write, undone by forgetting it and redone by making it again", async () => {
    const written = vi.fn();
    window.addEventListener(TRANSCRIPT_WRITTEN_EVENT, written);
    try {
      await splitParagraph("s1", 3, 4, "it is good");
      expect(postParagraphSplit).toHaveBeenCalledWith("s1", 3, 4, "it is good");
      expect(getUndoState().undoAction).toBe("splitParagraph");
      await undo();
      expect(deleteParagraphEdit).toHaveBeenCalledWith("s1", 7);
      vi.mocked(postParagraphSplit).mockResolvedValue({ id: 9 });
      await redo();
      await undo();
      expect(deleteParagraphEdit).toHaveBeenLastCalledWith("s1", 9);
      expect(written).toHaveBeenCalledTimes(4);
    } finally {
      window.removeEventListener(TRANSCRIPT_WRITTEN_EVENT, written);
    }
  });

  it("a refused split records nothing to undo", async () => {
    vi.mocked(postParagraphSplit).mockRejectedValue(new Error("POST 409"));
    await expect(splitParagraph("s1", 3, 4, "x")).rejects.toThrow();
    expect(getUndoState().canUndo).toBe(false);
  });

  it("a join is undone the same way", async () => {
    await joinParagraphs("s1", 2, "it is good");
    expect(postParagraphJoin).toHaveBeenCalledWith("s1", 2, "it is good");
    expect(getUndoState().undoAction).toBe("joinParagraphs");
    await undo();
    expect(deleteParagraphEdit).toHaveBeenCalledWith("s1", 8);
  });
});

// R9: an undo or redo the server refuses used to be silent, and the store had
// already moved the act across, so Edit offered Redo for a split still standing.
describe("an undo or redo that does not land says why and keeps its place", () => {
  const refused = () => Object.assign(new Error("DELETE 409"), { status: 409, reason: "run_in_progress" });
  const acts = [
    ["splitParagraph", () => splitParagraph("s1", 3, 4, "it is good"), postParagraphSplit],
    ["joinParagraphs", () => joinParagraphs("s1", 2, "it is good"), postParagraphJoin],
    [
      "reassignParagraph",
      () => reassignParagraph("s1", 2, "it is good", { slot: "p2" }),
      postParagraphReassign,
    ],
  ] as const;

  it.each(acts)("%s: a refused undo toasts, and Edit still offers the same Undo", async (action, act) => {
    await act();
    const written = vi.fn();
    window.addEventListener(TRANSCRIPT_WRITTEN_EVENT, written);
    try {
      const err = refused();
      vi.mocked(deleteParagraphEdit).mockRejectedValueOnce(err);
      expect(await undo()).toBe(false);
      expect(toastSaveFailed).toHaveBeenCalledWith(err);
      expect(getUndoState()).toMatchObject({ undoAction: action, canRedo: false });
      expect(written).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(TRANSCRIPT_WRITTEN_EVENT, written);
    }
  });

  it.each(acts)("%s: a refused redo toasts, and Edit still offers the same Redo", async (action, act, post) => {
    await act();
    await undo();
    const err = new TypeError("Load failed");
    vi.mocked(post).mockRejectedValueOnce(err);
    expect(await redo()).toBe(false);
    expect(toastSaveFailed).toHaveBeenCalledWith(err);
    expect(getUndoState()).toMatchObject({ redoAction: action, canUndo: false });
  });
});

describe("a paragraph edit that does not land says why", () => {
  it("names a running analysis on a refused move to a new moderator", async () => {
    const { postParagraphReassign, toastSaveFailed } = await import("./api");
    const { reassignParagraph } = await import("./paragraphEdits");
    const refused = Object.assign(new Error("POST 409"), { status: 409, reason: "run_in_progress" });
    vi.mocked(postParagraphReassign).mockRejectedValueOnce(refused);
    await expect(reassignParagraph("s1", 2, "a b c", { new: "moderator" })).rejects.toBe(refused);
    expect(vi.mocked(toastSaveFailed)).toHaveBeenCalledWith(refused);
    expect(getUndoState().canUndo).toBe(false);
  });

  it("says so for a split and a join too", async () => {
    const { toastSaveFailed } = await import("./api");
    vi.mocked(postParagraphSplit).mockRejectedValueOnce(new TypeError("Load failed"));
    vi.mocked(postParagraphJoin).mockRejectedValueOnce(new TypeError("Load failed"));
    await expect(splitParagraph("s1", 1, 2, "x")).rejects.toThrow();
    await expect(joinParagraphs("s1", 1, "x")).rejects.toThrow();
    expect(vi.mocked(toastSaveFailed)).toHaveBeenCalledTimes(2);
  });
});
