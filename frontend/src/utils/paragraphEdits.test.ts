/**
 * Split and join, web side (design-transcript-editing.md §"Split and join,
 * stage 1"): the caret becomes a word count, the edit is one undoable act, and
 * the page is told to re-read.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUndoState, redo, resetUndoStore, undo } from "../contexts/UndoStore";
import { deleteParagraphEdit, postParagraphJoin, postParagraphSplit } from "./api";
import {
  TRANSCRIPT_WRITTEN_EVENT,
  caretWords,
  drawnTokens,
  joinParagraphs,
  splitParagraph,
  verifyOf,
} from "./paragraphEdits";

vi.mock("./api", async (importOriginal) => {
  const real = await importOriginal<typeof import("./api")>();
  return { ...real, postParagraphSplit: vi.fn(), postParagraphJoin: vi.fn(), deleteParagraphEdit: vi.fn() };
});

beforeEach(() => {
  vi.mocked(postParagraphSplit).mockReset().mockResolvedValue({ id: 7 });
  vi.mocked(postParagraphJoin).mockReset().mockResolvedValue({ id: 8 });
  vi.mocked(deleteParagraphEdit).mockReset().mockResolvedValue(undefined);
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
