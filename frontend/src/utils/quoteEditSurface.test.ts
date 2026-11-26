import { describe, expect, it } from "vitest";
import {
  autoBreaks,
  blockRanges,
  caretPlace,
  clampCaret,
  draw,
  judgeInput,
  rangeKeepsSurface,
  read,
  replaceRange,
  sameBreaks,
  type EditModel,
} from "./quoteEditSurface";
import { breakIntoBlocks } from "./breakParagraphs";

const words = (t: string) => t.split(/\s+/).filter(Boolean);

function drawn(m: EditModel, mode: "hybrid" | "crop" = "hybrid") {
  const host = document.createElement("span");
  draw(host, m, { mode, leftEllipsis: false, rightEllipsis: false, bracketsVisible: true });
  return host;
}

describe("quoteEditSurface", () => {
  it("automatic breaks are the break function's blocks, as word positions", () => {
    const text = Array.from({ length: 90 }, (_, i) => (i % 12 === 11 ? `w${i}.` : `w${i}`)).join(" ");
    const blocks = breakIntoBlocks(text);
    expect(blocks.length).toBeGreaterThan(1);
    const ranges = blockRanges(words(text).length, autoBreaks(text));
    expect(ranges.map(([s, e]) => words(text).slice(s, e).join(" "))).toEqual(blocks);
  });

  it("reads back what it drew: words, breaks and a trim", () => {
    const m: EditModel = { words: words("a b c d e f g"), breaks: [1, 4], cropStart: 1, cropEnd: 6 };
    expect(read(drawn(m))).toEqual(m);
  });

  it("draws one block per paragraph, the quote marks in the first and last", () => {
    const host = drawn({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    const blocks = host.querySelectorAll(":scope > .bn-block");
    expect(Array.from(blocks).map((b) => b.textContent)).toEqual(["“[a b", "c d”]"]);
  });

  it("a paragraph emptied by typing takes its break with it", () => {
    const host = drawn({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    host.querySelectorAll(".crop-editable")[1].textContent = "";
    expect(read(host)).toEqual({ words: ["a", "b"], breaks: [], cropStart: 0, cropEnd: 2 });
  });

  it("a line break the browser inserted is a space between words, never a joint", () => {
    const host = drawn({ words: words("a b"), breaks: [], cropStart: 0, cropEnd: 2 });
    const run = host.querySelector(".crop-editable")!;
    run.innerHTML = "a<br>b";
    expect(read(host).words).toEqual(["a", "b"]);
  });

  it("keeps the trimmed words out of the typed text", () => {
    const host = drawn({ words: words("a b c d"), breaks: [], cropStart: 1, cropEnd: 3 }, "crop");
    expect(Array.from(host.querySelectorAll(".crop-word.excluded")).map((w) => w.textContent?.trim())).toEqual(["a", "d"]);
    expect(Array.from(host.querySelectorAll(".crop-word.included")).map((w) => w.textContent)).toEqual(["b", "c"]);
  });

  it("compares break lists by value, with null as automatic", () => {
    expect(sameBreaks([1, 2], [1, 2])).toBe(true);
    expect(sameBreaks([], null)).toBe(false);
    expect(sameBreaks(null, null)).toBe(true);
  });

  it("a drop's paragraphs are spaces between words, never a joint", () => {
    const host = drawn({ words: words("a b"), breaks: [], cropStart: 0, cropEnd: 2 });
    host.querySelector(".crop-editable")!.innerHTML = "end of<p>next</p>";
    expect(read(host).words).toEqual(["end", "of", "next"]);
  });
});

function caretAt(node: Node, offset: number) {
  const r = document.createRange();
  r.setStart(node, offset);
  r.collapse(true);
  window.getSelection()!.removeAllRanges();
  window.getSelection()!.addRange(r);
}

function select(start: Node, so: number, end: Node, eo: number) {
  const r = document.createRange();
  r.setStart(start, so);
  r.setEnd(end, eo);
  window.getSelection()!.removeAllRanges();
  window.getSelection()!.addRange(r);
}

const input = (inputType: string, init: InputEventInit = {}) =>
  new InputEvent("beforeinput", { inputType, cancelable: true, ...init });

describe("keeping the surface whole (review 21 Nov)", () => {
  const twoBlocks = () => {
    const host = drawn({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    document.body.append(host);
    return host;
  };
  const runs = (host: HTMLElement) => Array.from(host.querySelectorAll(".crop-editable"));

  it("refuses line breaks, drops and formatting; lets an input method compose", () => {
    const host = twoBlocks();
    caretAt(runs(host)[0].firstChild!, 1);
    expect(judgeInput(host, input("insertParagraph"))).toBe("refuse");
    expect(judgeInput(host, input("insertLineBreak"))).toBe("refuse");
    expect(judgeInput(host, input("insertFromDrop"))).toBe("refuse");
    expect(judgeInput(host, input("formatBold"))).toBe("refuse");
    expect(judgeInput(host, input("insertCompositionText", { isComposing: true }))).toBe("allow");
    expect(judgeInput(host, input("insertText", { data: "x" }))).toBe("allow");
  });

  it("a selection over a quote mark or a paragraph break is typed over or deleted by the card", () => {
    const host = twoBlocks();
    const [first, second] = runs(host);
    select(host.querySelector(".bn-block")!, 0, first.firstChild!, 1); // over the opening mark
    expect(judgeInput(host, input("deleteWordBackward"))).toBe("replace");
    select(first.firstChild!, 2, second.firstChild!, 1); // across the paragraph break
    expect(judgeInput(host, input("deleteContentBackward"))).toBe("replace");
    expect(judgeInput(host, input("insertText", { data: "x" }))).toBe("replace");
    expect(judgeInput(host, input("deleteByDrag"))).toBe("refuse");
    select(first.firstChild!, 0, first.firstChild!, 1); // inside the typed text
    expect(judgeInput(host, input("deleteContentBackward"))).toBe("allow");
  });

  it("a word delete from a caret that would take a quote mark is still refused", () => {
    const host = twoBlocks();
    const [first] = runs(host);
    caretAt(first.firstChild!, 1);
    const over = document.createRange();
    over.setStart(host.querySelector(".bn-block")!, 0);
    over.setEnd(first.firstChild!, 1);
    const e = input("deleteWordBackward");
    Object.defineProperty(e, "getTargetRanges", { value: () => [over] });
    expect(judgeInput(host, e)).toBe("refuse");
  });

  it("text typed outside the typed run is moved into it, and the caret is kept there", () => {
    const host = drawn({ words: words("a b c d e"), breaks: [], cropStart: 2, cropEnd: 4 });
    document.body.append(host);
    const block = host.querySelector(".bn-block")!;
    const between = Array.from(block.childNodes).indexOf(block.querySelectorAll(".excluded")[1]);
    caretAt(block, between); // between the two trimmed words
    expect(judgeInput(host, input("insertText", { data: "X" }))).toBe("retype");
    clampCaret(host);
    const at = window.getSelection()!.getRangeAt(0).startContainer;
    const el = at instanceof Element ? at : at.parentElement;
    expect(el?.closest(".crop-editable")).toBe(runs(host)[0]);
  });

  // An emptied paragraph as Chromium and WebKit leave it: the run is removed
  // once all its text is deleted (probed 25 Nov), so the block holds a <br>.
  const emptyMiddle = () => {
    const host = drawn({ words: words("a b c d e f"), breaks: [1, 3], cropStart: 0, cropEnd: 6 });
    document.body.append(host);
    const middle = host.querySelectorAll(":scope > .bn-block")[1];
    middle.replaceChildren(document.createElement("br"));
    return { host, middle };
  };

  it("numbers paragraphs as read() does when one has been emptied", () => {
    const { host, middle } = emptyMiddle();
    const last = runs(host)[1];
    caretAt(last.firstChild!, 0);
    expect(caretPlace(host)).toMatchObject({ block: 1, empty: false, atStart: true });
    caretAt(middle, 0);
    expect(caretPlace(host)).toMatchObject({ block: 1, empty: true });
    expect(read(host).breaks).toEqual([1]);
  });

  it("leaves the caret in an emptied paragraph, so retyping it stays there (finding 28)", () => {
    const { host, middle } = emptyMiddle();
    caretAt(middle, 0);
    clampCaret(host);
    expect(window.getSelection()!.getRangeAt(0).startContainer).toBe(middle);
    expect(judgeInput(host, input("insertText", { data: "n" }))).toBe("allow");
    middle.prepend(document.createTextNode("new words"));
    expect(read(host).words.join(" ")).toBe("a b new words e f");
    expect(read(host).breaks).toEqual([1, 3]);
  });

  it("refuses the delete half of a drag that moves words (finding 34)", () => {
    const host = twoBlocks();
    select(runs(host)[0].firstChild!, 0, runs(host)[0].firstChild!, 1);
    expect(judgeInput(host, input("deleteByDrag"))).toBe("refuse");
  });

  it("a range a paste may replace stays in one paragraph and takes no island (finding 33)", () => {
    const host = twoBlocks();
    const [first, second] = runs(host);
    const range = (a: Node, ao: number, b: Node, bo: number) => {
      const r = document.createRange();
      r.setStart(a, ao);
      r.setEnd(b, bo);
      return r;
    };
    expect(rangeKeepsSurface(host, range(first.firstChild!, 0, first.firstChild!, 1))).toBe(true);
    expect(rangeKeepsSurface(host, range(first.firstChild!, 2, second.firstChild!, 1))).toBe(false);
    expect(rangeKeepsSurface(host, range(host.querySelector(".bn-block")!, 0, first.firstChild!, 1))).toBe(false);
  });

  it("hides the islands from screen readers while the words are edited, and only then (finding 40)", () => {
    const m = { words: words("a b c d e"), breaks: [], cropStart: 1, cropEnd: 4 };
    const islands = (h: HTMLElement) => Array.from(h.querySelectorAll('[contenteditable="false"]'));
    const text = drawn(m);
    expect(islands(text).length).toBeGreaterThan(0);
    expect(islands(text).every((n) => n.getAttribute("aria-hidden") === "true")).toBe(true);
    expect(drawn(m, "crop").querySelector('[aria-hidden="true"]')).toBeNull();
  });
});

// ── A selection typed over, deleted or cut (owner, 26 Nov 2026) ──

describe("replacing a selection", () => {
  const opts = { mode: "hybrid" as const, leftEllipsis: false, rightEllipsis: false, bracketsVisible: false };
  const host = (m: EditModel) => {
    const h = drawn(m);
    document.body.append(h);
    return h;
  };
  const runs = (h: HTMLElement) => Array.from(h.querySelectorAll(".crop-editable"));
  const blocks = (h: HTMLElement) => Array.from(h.querySelectorAll(":scope > .bn-block"));
  const marks = (h: HTMLElement) => h.querySelectorAll(".bn-mark").length;
  const range = (sn: Node, so: number, en: Node, eo: number) => {
    const r = document.createRange();
    r.setStart(sn, so);
    r.setEnd(en, eo);
    return r;
  };

  it("a delete across a paragraph break takes the selected words and joins the paragraphs", () => {
    const h = host({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    const [first, second] = runs(h);
    const out = replaceRange(h, range(first.firstChild!, 2, second.firstChild!, 1), "", opts)!;
    expect(out.model).toEqual({ words: ["a", "d"], breaks: [], cropStart: 0, cropEnd: 2 });
    expect(out.removed).toBe("b\nc");
    expect(out.joined).toBe(true);
    expect(read(h)).toEqual(out.model);
    expect(blocks(h)).toHaveLength(1);
    expect(marks(h)).toBe(2);
    const caret = window.getSelection()!.getRangeAt(0);
    expect(caret.startContainer).toBe(runs(h)[0].firstChild);
    expect(caret.startOffset).toBe("a ".length);
  });

  it("typing over a selection that takes in a quote mark replaces the words and keeps the mark", () => {
    const h = host({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    const [first] = runs(h);
    const out = replaceRange(h, range(blocks(h)[0], 0, first.firstChild!, 1), "X", opts)!;
    expect(out.model).toEqual({ words: ["X", "b", "c", "d"], breaks: [1], cropStart: 0, cropEnd: 4 });
    expect(out.joined).toBe(false);
    expect(marks(h)).toBe(2);
  });

  it("a selection that ends at a paragraph's very start, as a triple-click's does, leaves that paragraph", () => {
    const h = host({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    const [first] = runs(h);
    const out = replaceRange(h, range(first.firstChild!, 0, blocks(h)[1], 0), "X", opts)!;
    expect(out.model.words).toEqual(["X", "c", "d"]);
    expect(out.model.breaks).toEqual([0]);
    expect(out.joined).toBe(false);
  });

  it("trimmed words in the selection stay, and stay trimmed", () => {
    const h = host({ words: words("a b c d e"), breaks: [], cropStart: 1, cropEnd: 4 });
    const b = blocks(h)[0];
    const out = replaceRange(h, range(b, 0, b, b.childNodes.length), "Z", opts)!;
    expect(out.model).toEqual({ words: ["a", "Z", "e"], breaks: [], cropStart: 1, cropEnd: 2 });
    expect(out.removed).toBe("b c d");
    expect(h.querySelectorAll(".excluded")).toHaveLength(2);
  });

  it("deleting whole paragraphs leaves an empty one to type in, which read() drops", () => {
    const h = host({ words: words("a b c d e f"), breaks: [1, 3], cropStart: 0, cropEnd: 6 });
    const [, second, third] = runs(h);
    const out = replaceRange(h, range(second.firstChild!, 0, third.firstChild!, 3), "", opts)!;
    expect(out.removed).toBe("c d\ne f");
    expect(blocks(h)).toHaveLength(2);
    const empty = blocks(h)[1];
    expect(empty.querySelector(".crop-editable br")).not.toBeNull();
    expect(empty.querySelector(".bn-mark")).not.toBeNull(); // the closing mark stays with the last paragraph
    expect(read(h)).toEqual({ words: ["a", "b"], breaks: [], cropStart: 0, cropEnd: 2 });
    const caret = window.getSelection()!.getRangeAt(0).startContainer;
    expect(caret).toBe(empty.querySelector(".crop-editable"));
    empty.querySelector(".crop-editable")!.prepend("x y");
    expect(read(h).words).toEqual(["a", "b", "x", "y"]);
    expect(read(h).breaks).toEqual([1]);
  });

  it("deleting every word keeps the quote marks and a place to type", () => {
    const h = host({ words: words("a b c d"), breaks: [1], cropStart: 0, cropEnd: 4 });
    const out = replaceRange(h, range(h, 0, h, h.childNodes.length), "", opts)!;
    expect(out.model.words).toEqual([]);
    expect(blocks(h)).toHaveLength(1);
    expect(marks(h)).toBe(2);
    expect(h.querySelector(".crop-editable br")).not.toBeNull();
  });
});
