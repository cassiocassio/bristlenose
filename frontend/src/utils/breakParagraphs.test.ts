import { describe, expect, it } from "vitest";
import { breakIntoBlocks, THOUGHT_TARGET_WORDS } from "./breakParagraphs";

// The IKEA quote a researcher broke by hand (21, 11, 10 and 8 words), kept here
// as a worked example. It is a test of the rules, not of any taste.
const IKEA =
  "Well, I can see the different sections... across the top quite easily — that makes it easier to select stuff. " +
  "I'm... interested both in the... bed linen, ... that's... right there because that's something I've been looking at at the minute. " +
  "I mean, it looks like an IKEA website.";

const collapse = (s: string): string => s.split(/\s+/).filter(Boolean).join(" ");
const SMALL = ["the", "a", "an", "of", "to", "in", "on", "at", "for", "with", "and", "but", "or", "so", "i", "it", "that"];

/** A deterministic pseudo-random text built from fragments that include sentence ends, cuts and conjunctions. */
function sample(seed: number, words: number): string {
  let s = seed;
  const rnd = (n: number) => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s % n;
  };
  const vocab = ["the", "shelf", "and", "I", "think", "kitchen", "because", "so", "but", "wanted", "to", "see", "what", "brown", "colour", "is", "a", "lot", "of", "storage", "which", "works"];
  const out: string[] = [];
  for (let i = 0; i < words; i++) {
    let w = vocab[rnd(vocab.length)];
    const r = rnd(14);
    if (r === 0) w += ".";
    else if (r === 1) w += "...";
    else if (r === 2) w += ",";
    out.push(w);
    if (rnd(40) === 0) out.push("...");
  }
  return out.join(" ");
}

describe("breakIntoBlocks", () => {
  it("returns a short quote untouched", () => {
    const t = "So obviously the thing I want to replace is somewhere here where it says... it's like cupboards and storage.";
    expect(breakIntoBlocks(t)).toEqual([t]);
  });

  it("returns text untouched when there is nowhere to break", () => {
    const t = Array(120).fill("word").join(" ");
    expect(breakIntoBlocks(t)).toEqual([t]);
  });

  it("returns text with no spaces (CJK) whole", () => {
    const t = "これはとても長い引用ですが、スペースがないので分割できません。".repeat(8);
    expect(breakIntoBlocks(t)).toEqual([t]);
  });

  it("handles empty and one-word input", () => {
    expect(breakIntoBlocks("")).toEqual([""]);
    expect(breakIntoBlocks("Fine.")).toEqual(["Fine."]);
  });

  it("splits the IKEA quote at the first sentence end at a tabloid target", () => {
    const blocks = breakIntoBlocks(IKEA, { target: 28 });
    expect(blocks.length).toBe(2);
    expect(blocks[0].endsWith("select stuff.")).toBe(true);
    expect(blocks[0].split(" ").length).toBe(20);
  });

  it("keeps the IKEA quote whole at the default target (49 words is one thought)", () => {
    expect(THOUGHT_TARGET_WORDS).toBe(35);
    expect(breakIntoBlocks(IKEA)).toEqual([IKEA]);
  });

  it("splits a long quote and never changes a word", () => {
    for (let seed = 1; seed <= 60; seed++) {
      const text = sample(seed, 40 + (seed % 7) * 25);
      const blocks = breakIntoBlocks(text);
      expect(blocks.join(" ")).toBe(collapse(text));
    }
  });

  it("is deterministic", () => {
    for (let seed = 1; seed <= 20; seed++) {
      const text = sample(seed, 150);
      expect(breakIntoBlocks(text)).toEqual(breakIntoBlocks(text));
    }
  });

  it("never leaves a block that is only a cut, or starts one with a cut", () => {
    for (let seed = 1; seed <= 80; seed++) {
      const text = sample(seed, 60 + (seed % 9) * 20);
      for (const b of breakIntoBlocks(text)) {
        expect(b).not.toBe("...");
        expect(b.startsWith("...")).toBe(false);
      }
    }
  });

  it("keeps a leading cut with the words after it", () => {
    const body = sample(3, 90);
    const blocks = breakIntoBlocks(`... ${body}`);
    expect(blocks[0]).not.toBe("...");
    expect(blocks[0].startsWith("... ")).toBe(true);
  });

  it("keeps a leading cut with the words after it even at a tiny target", () => {
    // At target 1 a one-word block is cheap, so only the explicit rule stops "..." standing alone.
    const blocks = breakIntoBlocks("... Okay. Fine. Right. Good. Sure. Yes.", { target: 1 });
    expect(blocks[0]).not.toBe("...");
    expect(blocks[0].startsWith("... ")).toBe(true);
  });

  it("never ends a block on a small word", () => {
    for (let seed = 1; seed <= 80; seed++) {
      const text = sample(seed, 60 + (seed % 9) * 20);
      const blocks = breakIntoBlocks(text);
      // the last block ends where the quote ends; only the breaks are under test
      for (const b of blocks.slice(0, -1)) {
        const last = b.split(" ").pop()!.toLowerCase().replace(/[^a-z']/g, "");
        const endsSentenceOrCut = /[.?!]["”)\]]?$|\.\.\.$/.test(b);
        if (!endsSentenceOrCut) expect(SMALL).not.toContain(last);
      }
    }
  });

  it("breaks every long quote and keeps blocks near the target", () => {
    const text = sample(7, 240);
    const blocks = breakIntoBlocks(text);
    expect(blocks.length).toBeGreaterThan(2);
    for (const b of blocks) expect(b.split(" ").length).toBeLessThan(THOUGHT_TARGET_WORDS * 2.2);
  });

  it("gives more blocks for a smaller target", () => {
    const text = sample(11, 200);
    expect(breakIntoBlocks(text, { target: 20 }).length).toBeGreaterThanOrEqual(breakIntoBlocks(text, { target: 49 }).length);
  });
});
