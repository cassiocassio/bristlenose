import { describe, expect, it } from "vitest";
import { autoBreaks, blockRanges, draw, read, sameBreaks, type EditModel } from "./quoteEditSurface";
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
});
